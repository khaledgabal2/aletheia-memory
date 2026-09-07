"""Validate installed 1.5.0 artifacts using disposable CLI services and databases.

Run with --python /fresh/venv/bin/python --previous-python /1.4.1/venv/bin/python.
Neither environment needs development extras. Secrets never appear in output.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
from importlib import metadata
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time


NAMESPACE = "user/release-fixture"
TABLES = ("claims", "evidence_events", "claim_evidence_links", "candidate_claims", "candidate_evidence_links")


def snapshot(database: str, *, seed: bool = False) -> dict:
    from aletheia import Memory

    memory = Memory.open(database, auto_migrate=seed)
    try:
        if seed:
            memory.remember(namespace=NAMESPACE, memory_type="preference", subject="user",
                            predicate="prefers", object="careful architecture notes", source_type="manual")
            batch = memory.ingest(NAMESPACE, source_type="manual", content="User prefers compact review summaries.")
            memory.extract_candidates(NAMESPACE, batch_id=batch.id)
        connection = memory.store.connection
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert memory.health()["schema_version"] == "1.3.1"
        return {table: hashlib.sha256(repr([tuple(row) for row in connection.execute(
            "SELECT * FROM " + table + " ORDER BY rowid")]).encode()).hexdigest() for table in TABLES}
    finally:
        memory.close()


def run(command: list[str], *, env: dict | None = None) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=45, env=env)
    if result.returncode:
        # Invitation and authentication output must not enter CI logs, even on failure.
        raise RuntimeError(f"Installed command failed (exit {result.returncode}); output withheld.")
    return result.stdout


def request(port: int, path: str, *, method: str = "GET", payload=None, token=None, certificate=None):
    if certificate:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_verify_locations(cadata=certificate)
        connection = http.client.HTTPSConnection("127.0.0.1", port, context=context, timeout=5)
    else:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        connection.request(method, path, body=json.dumps(payload) if payload is not None else None, headers=headers)
        response = connection.getresponse()
        body = response.read(65537)
        assert len(body) <= 65536
        return response.status, json.loads(body), dict(response.getheaders())
    finally:
        connection.close()


class Service:
    def __init__(self, database: str, cli: list[str], env: dict, extra: tuple = ()):
        self.log = tempfile.TemporaryFile(mode="w+")
        self.process = subprocess.Popen([*cli, "serve", "--db", database, "--port", "0", *extra],
                                        env=env, stdout=self.log, stderr=self.log)
        self.port = 0
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    self.log.seek(0)
                    # Startup contains no invitations or issued credentials.
                    raise AssertionError("Installed service exited before startup: " + self.log.read()[-4000:])
                self.log.seek(0)
                match = re.search(r"service running at http://127\.0\.0\.1:(\d+)/v1", self.log.read())
                if match:
                    self.port = int(match[1])
                    status, version, _ = request(self.port, "/v1/version")
                    assert status == 200 and version["data"]["software_version"] == "1.5.0"
                    return
                time.sleep(0.05)
            raise AssertionError("Installed service did not become ready.")
        except BaseException:
            self.stop()
            raise

    def info(self):
        status, response, _ = request(self.port, "/v1/pairing/info")
        assert status == 200
        info = response["data"]
        assert hashlib.sha256(ssl.PEM_cert_to_DER_cert(info["certificate_pem"])).hexdigest() == info["certificate_sha256"]
        return info

    def stop(self, *, crash=False):
        if self.process.poll() is None:
            self.process.kill() if crash else self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
                raise AssertionError("Installed service did not stop cleanly.") from None
            if not crash:
                assert self.process.returncode == 0, "SIGTERM did not produce a clean shutdown."
        self.log.close()


def worker(previous_python: str):
    import aletheia
    from aletheia.help import docs_root

    assert os.name == "posix", "Local pairing currently supports POSIX only."
    package = Path(aletheia.__file__).resolve().parent
    assert "site-packages" in package.parts
    assert metadata.version("aletheia-memory") == "1.5.0"
    assert docs_root().resolve() == package / "docs"
    assert not any(metadata.packages_distributions().get(name) for name in ("pytest", "openai", "torch", "transformers"))
    root = Path.cwd()
    env = dict(os.environ, ALETHEIA_DISCOVERY_DIR=str(root / "discovery"),
               ALETHEIA_IDENTITY_DIR=str(root / "identities"),
               ALETHEIA_BACKUP_PASSPHRASE="synthetic-release-backup-password")
    cli = [str(Path(sys.executable).parent / "aletheia")]
    checks = []

    def passed(message):
        checks.append(message)
        print("PASS: " + message, flush=True)

    def command(*args):
        return run([*cli, *map(str, args)], env=env)

    def database_state(python, database, *, seed=False):
        return json.loads(run([python, "-I", str(Path(__file__).resolve()), "--snapshot", str(database),
                               *(["--seed"] if seed else [])], env=env))

    def records():
        return {path: json.loads(path.read_text()) for path in (root / "discovery").glob("*.json")}

    def invite(database, service):
        output = command("pairing", "invite", "--json", "--db", database, "--port", service.port,
                          "--name", "Release fixture", "--namespace", NAMESPACE,
                          "--capability", "memory:read", "--capability", "memory:audit",
                          "--privacy-ceiling", "personal", "--token-ttl-seconds", "300").strip()
        encoded = json.loads(output)["pairing_code"]
        assert encoded.startswith("aletheia-local-v1.")
        encoded = encoded.split(".", 1)[1]
        code = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        assert code["certificate_sha256"] == service.info()["certificate_sha256"]
        return {key: code[key] for key in ("invitation_id", "secret")}

    def secure(service, path, **kwargs):
        info = service.info()
        return request(info["tls_port"], path, certificate=info["certificate_pem"], **kwargs)

    def pair(database, service):
        payload = invite(database, service)
        status, inspected, _ = secure(service, "/v1/pairing/inspect", method="POST", payload=payload)
        assert status == 200 and inspected["data"]["token_ttl_seconds"] == 300
        assert inspected["data"]["namespace_grants"] == [NAMESPACE]
        assert inspected["data"]["capabilities"] == ["memory:audit", "memory:read"]
        assert inspected["data"]["privacy_ceiling"] == "personal"
        status, result, headers = secure(service, "/v1/pairing/complete", method="POST", payload=payload)
        assert status == 200 and headers["Cache-Control"] == "no-store"
        token = result["data"]["token"]
        assert secure(service, "/v1/auth/me", token=token)[0] == 200
        assert request(service.port, "/v1/auth/me", token=token)[0] == 401
        assert secure(service, "/v1/pairing/complete", method="POST", payload=payload)[0] == 401
        return token

    services = []

    def start(database, *extra):
        service = Service(str(database), cli, env, extra)
        services.append(service)
        return service

    try:
        command("--help")
        command("pairing", "invite", "--help")
        assert "Local Registration And Pairing" in command("docs", "show", "local-pairing-v1")
        fresh = root / "fresh.db"
        command("init", "--new", "--db", fresh)
        command("doctor", "--read-only", "--db", fresh)
        fresh_service = start(fresh)
        fresh_service.info()
        fresh_service.stop()
        assert not records()
        passed("core-only installed CLI, packaged pairing docs, fresh initialization and startup")

        previous_version = run([previous_python, "-I", "-c",
                                "from importlib.metadata import version; print(version('aletheia-memory'))"]).strip()
        assert previous_version == "1.4.1"
        database = root / "previous.db"
        before = database_state(previous_python, database, seed=True)
        spelling = "~/" + os.path.relpath(database, Path.home())
        assert Path(spelling).expanduser().resolve() == database
        assert database_state(sys.executable, spelling) == before
        service = start(spelling)
        identity = service.info()
        registration, initial = next(iter(records().items()))
        assert initial["port"] == service.port
        assert registration.stat().st_mode & 0o777 == 0o600
        token = pair(spelling, service)
        unused = invite(spelling, service)
        passed("1.4.1 database opens without migration; quoted tilde paths, explicit grants and TLS-only credentials")

        deadline = time.monotonic() + 15
        while records()[registration]["expires_at_ms"] <= initial["expires_at_ms"]:
            assert time.monotonic() < deadline, "Automatic registration did not renew."
            time.sleep(0.1)
        service.stop()
        assert not registration.exists()
        service = start(spelling)
        assert service.info()["certificate_sha256"] == identity["certificate_sha256"]
        assert service.info()["service_identity"] != identity["service_identity"]
        assert secure(service, "/v1/auth/me", token=token)[0] == 200
        assert secure(service, "/v1/pairing/complete", method="POST", payload=unused)[0] == 401
        passed("automatic lease renewal, SIGTERM cleanup and restart preserve credentials but invalidate unused codes")

        survivor = start(fresh)
        survivor_paths = {path for path, value in records().items() if value["port"] == survivor.port}
        stale_path, stale = next((path, value) for path, value in records().items() if value["port"] == service.port)
        service.stop(crash=True)
        service = start(spelling)
        assert service.info()["certificate_sha256"] == identity["certificate_sha256"]
        assert secure(service, "/v1/auth/me", token=token)[0] == 200
        assert database_state(sys.executable, database) == before
        deadline = time.monotonic() + 35
        while time.time() * 1000 <= stale["expires_at_ms"]:
            assert time.monotonic() < deadline
            time.sleep(0.1)
        assert json.loads(stale_path.read_text()) == stale
        assert all(path.exists() for path in survivor_paths)
        assert request(survivor.port, "/v1/version")[0] == 200
        passed("SIGKILL recovery preserves data and identity; real crash lease expires while another service stays registered")

        archive = root / "recovery.alet"
        command("backup", "create", "--db", database, "--output", archive, "--encrypt")
        command("backup", "verify", archive, "--db", database)
        restored = root / "restored.db"
        command("restore", "dry-run", archive, "--db", database, "--target-db", restored)
        assert not restored.exists()
        command("restore", "apply", archive, "--db", database, "--target-db", restored, "--confirm", "restore backup")
        assert database_state(sys.executable, restored) == before
        recovered = start(restored)
        assert recovered.info()["certificate_sha256"] != identity["certificate_sha256"]
        assert secure(recovered, "/v1/auth/me", token=token)[0] == 401
        recovered_token = pair(str(restored), recovered)
        assert secure(recovered, "/v1/pairing/current", method="DELETE", token=recovered_token)[0] == 200
        assert secure(recovered, "/v1/auth/me", token=recovered_token)[0] == 401
        recovered.stop()
        passed("encrypted backup verifies and restores; recovered database requires fresh pairing and supports revocation")

        service.stop()
        (root / "identities").rename(root / "preserved-identities")
        service = start(spelling)
        assert service.info()["certificate_sha256"] != identity["certificate_sha256"]
        assert secure(service, "/v1/auth/me", token=token)[0] == 401
        replacement_token = pair(spelling, service)
        assert secure(service, "/v1/pairing/current", method="DELETE", token=replacement_token)[0] == 200
        service.stop()
        # Revoke all pairing-issued credentials before checking the older binary:
        # 1.4.1 does not implement the paired-transport restriction.
        from aletheia import Memory
        from aletheia.service.auth import AuthService
        memory = Memory.open(str(database), auto_migrate=False)
        try:
            auth = AuthService(memory)
            for issued in auth.list_tokens():
                auth.revoke_token(issued.id, reason="release_fixture_rollback")
        finally:
            memory.close()
        assert database_state(previous_python, database) == before
        passed("identity-directory loss rejects old credentials; owner revocation allows 1.4.1 data rollback without migration")

        hidden = start(database, "--no-advertise", "--no-local-pairing")
        assert not any(value["port"] == hidden.port for value in records().values())
        assert request(hidden.port, "/v1/pairing/info")[0] == 503
        hidden.stop()
        passed("advertising and local pairing opt-outs preserve service startup")
    finally:
        for service in reversed(services):
            service.stop()
    print(json.dumps({"status": "passed", "version": metadata.version("aletheia-memory"),
                      "python": sys.version.split()[0], "checks": checks}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python")
    parser.add_argument("--previous-python")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--snapshot", help=argparse.SUPPRESS)
    parser.add_argument("--seed", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.snapshot:
        print(json.dumps(snapshot(args.snapshot, seed=args.seed)))
    elif args.worker:
        worker(args.previous_python)
    else:
        if not args.python or not args.previous_python:
            parser.error("--python and --previous-python are required")
        with tempfile.TemporaryDirectory(prefix="aletheia-installed-recovery-") as directory:
            script = Path(directory) / "check.py"
            shutil.copyfile(__file__, script)
            environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH") if key in os.environ}
            result = subprocess.run([str(Path(args.python).absolute()), "-I", str(script), "--worker",
                                     "--previous-python", str(Path(args.previous_python).absolute())],
                                    cwd=directory, env=environment, timeout=240)
            raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
