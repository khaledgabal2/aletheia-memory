"""Explicit operator-owned local demo. Keeps agent and review credentials separate."""
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from urllib.request import build_opener, install_opener, ProxyHandler

from aletheia import Memory
from aletheia.client import AletheiaClient
from aletheia.core.time import utc_now
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaDaemon


def main():
    path = Path("aletheia-http-demo.db")
    for suffix in ("-wal", "-shm", "-journal"):
        companion = Path(str(path) + suffix)
        if companion.exists() or companion.is_symlink():
            raise SystemExit("Database companion file already exists. Preserve it and choose a new directory.")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
    except FileExistsError:
        raise SystemExit("Demo database already exists. Choose a new directory; nothing was overwritten.")
    Memory.open(str(path)).close()
    # This disposable service is local; do not send demo credentials to a proxy.
    install_opener(build_opener(ProxyHandler({})))
    namespace = "user/demo"
    daemon = AletheiaDaemon(ServiceConfig(db_path=str(path), host="127.0.0.1", port=0,
        auto_migrate=False, auth_required=True, worker_enabled=False))
    thread = None
    token_ids = []
    claim_id = None
    try:
        auth = daemon.service.auth
        def credential(name, capabilities):
            client = auth.create_client(name=name, client_type="test")
            token, raw = auth.create_token(client_id=client.id, capabilities=capabilities,
                namespace_grants=[namespace], privacy_ceiling="personal", expires_at=(utc_now() + timedelta(minutes=30)).isoformat())
            token_ids.append(token.id)
            return raw
        agent_token = credential("Demo agent", ["memory:read", "memory:context", "memory:write_candidate"])
        operator_token = credential("Demo operator", ["memory:read", "memory:review", "memory:audit"])
        host, port = daemon.start()
        thread = threading.Thread(target=daemon.httpd.serve_forever, daemon=True)
        thread.start()
        url = f"http://{host}:{port}"
        # No inherited provider settings, operator tokens, or unrelated credentials.
        environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP") if key in os.environ}
        environment.update(ALETHEIA_URL=url, ALETHEIA_AGENT_TOKEN=agent_token,
                           ALETHEIA_NAMESPACE=namespace, PYTHONIOENCODING="utf-8")
        def agent(action):
            result = subprocess.run([sys.executable, "-I", str(Path(__file__).with_name("agent.py")), action],
                                    env=environment, capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise SystemExit("Agent step failed. Inspect the retained demo database with doctor --read-only; do not blindly replay a write.")
            return result.stdout
        receipt = json.loads(agent("capture"))
        reviewer = AletheiaClient(url, operator_token, timeout=10)
        audit = reviewer.audit("candidate", receipt["candidate_id"])
        candidate = audit["candidate"]
        print("Pending candidate:", candidate["subject"], candidate["predicate"], candidate["object"])
        print("Source:", audit["evidence"][0]["content"])
        print("Agent before review:")
        print(agent("read"))
        try:
            approve = input("Operator: inspect the candidate and source. Type approve to promote it: ").strip() == "approve"
        except EOFError:
            approve = False
        if approve:
            claim = reviewer.promote_candidate(candidate["id"], reason="Operator inspected and approved this demo candidate.")
            claim_id = claim["id"]
            print("Agent after operator approval:")
            print(agent("read"))
        else:
            print("Nothing promoted. The candidate remains pending review.")
    finally:
        # The demo does not leave usable credentials after it stops.
        with daemon.service.lock:
            for token_id in token_ids:
                daemon.service.auth.revoke_token(token_id, reason="Demo finished")
        if thread is not None:
            daemon.shutdown()
            thread.join(timeout=5)
        else:
            if daemon.httpd is not None:
                daemon.httpd.server_close()
            daemon.service.close()
    if claim_id:
        memory = Memory.open(str(path), namespace=namespace, auto_migrate=False)
        try:
            assert memory.retrieve(namespace, "architecture", mode="lexical")[0].claim_id == claim_id
            print("Reopened successfully: reviewed HTTP memory persists; demo credentials are revoked.")
        finally:
            memory.close()


if __name__ == "__main__":
    main()
