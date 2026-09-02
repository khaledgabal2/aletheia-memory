"""Exercise the new SDK against an isolated, installed, published 1.3.1 service."""

import argparse
import hashlib
import json
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile

from aletheia.client import AletheiaClient, AletheiaUnsupportedFeatureError


CHILD = r'''
import json, pathlib, sys, threading
sys.path.insert(0, sys.argv[1])
from aletheia import Memory
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaDaemon
import aletheia
assert pathlib.Path(aletheia.__file__).is_relative_to(pathlib.Path(sys.argv[1]))
daemon = AletheiaDaemon(ServiceConfig(db_path=sys.argv[2], port=0, host="127.0.0.1", auto_migrate=True, auth_required=True))
thread = None
try:
    daemon.service.memory.remember(namespace="user/legacy-check", memory_type="preference",
                                   subject="user", predicate="prefers", object="reviewed architecture notes")
    auth = daemon.service.auth
    client = auth.create_client(name="reverse-compatibility-test", client_type="test")
    _, token = auth.create_token(client_id=client.id, namespace_grants=["user/legacy-check"],
                                capabilities=["memory:read", "memory:context"])
    host, port = daemon.start()
    thread = threading.Thread(target=daemon.httpd.serve_forever, daemon=True)
    thread.start()
    print(json.dumps({"url": f"http://{host}:{port}", "token": token}), flush=True)
    sys.stdin.readline()
finally:
    if thread is not None:
        daemon.shutdown()
        thread.join(timeout=5)
    else:
        daemon.service.close()
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-package", type=Path, required=True)
    args = parser.parse_args()
    package = args.legacy_package.resolve()
    root = Path(__file__).resolve().parents[1]
    provenance = json.loads((root / "tests/fixtures/v1_3_1/provenance.json").read_text())
    for name, expected in provenance["runtime_sha256"].items():
        source = package.joinpath(*name.split(".")).with_suffix(".py")
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Expected the published, unchanged 1.3.1 module: {name}")
    with tempfile.TemporaryDirectory(prefix="aletheia-legacy-") as directory:
        process = subprocess.Popen(
            [sys.executable, "-I", "-u", "-c", CHILD, str(package), str(Path(directory) / "legacy.db")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                if not selector.select(timeout=20):
                    raise RuntimeError("Timed out starting the isolated legacy service")
            credentials = json.loads(process.stdout.readline())
            client = AletheiaClient(credentials["url"], credentials["token"])
            report = client.check_compatibility()
            assert report["compatible"] is True and report["limited_capabilities"] is True
            assert report["supported_profiles"] == []
            review = client.check_compatibility(required_profiles=["memory-review-v1"])
            assert review["compatible"] is False
            assert review["missing_profiles"] == ["memory-review-v1"]
            try:
                client.current_principal()
            except AletheiaUnsupportedFeatureError as exc:
                assert exc.details["required_feature"] == "current-principal"
            else:
                raise AssertionError("Legacy service must not invent principal discovery")
            hits = client.retrieve(namespace="user/legacy-check", query="architecture", mode="lexical")
            assert hits and client.context_pack(namespace="user/legacy-check", query="architecture", retrieval_mode="lexical")["items"]
            _, stderr = process.communicate(input="stop\n", timeout=10)
            if process.returncode:
                raise RuntimeError(f"Legacy service failed during shutdown: {stderr}")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    print("New SDK -> published 1.3.1 service: legacy reads/context pass; missing principal/review features are explicit.")


if __name__ == "__main__":
    main()
