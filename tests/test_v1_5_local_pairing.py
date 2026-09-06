import base64
import http.client
import json
import os
from pathlib import Path
import ssl
import threading
import time
import socket
import subprocess
import sys

import pytest

from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaDaemon
from aletheia.service.local_pairing import create_invitation
from aletheia.service.local_files import read_private, write_private

pytestmark = pytest.mark.skipif(os.name != "posix", reason="Initial local pairing requires POSIX ownership protections")
GRANTS = {"client_name": "Desktop test", "namespace_grants": ["user/default"],
          "capabilities": ["memory:read", "memory:audit"], "privacy_ceiling": "personal", "token_ttl_seconds": 3600}


@pytest.fixture
def services(tmp_path, monkeypatch):
    monkeypatch.setenv("ALETHEIA_DISCOVERY_DIR", str(tmp_path / "discovery"))
    monkeypatch.setenv("ALETHEIA_IDENTITY_DIR", str(tmp_path / "identities"))
    running = []
    def start(name="memory", **patch):
        config = ServiceConfig(db_path=str(tmp_path / f"{name}.db"), port=0, auto_migrate=True,
                               local_pairing_enabled=True, rate_limit_enabled=False, **patch)
        daemon = AletheiaDaemon(config)
        daemon.start()
        thread = threading.Thread(target=daemon.serve_forever, daemon=True)
        thread.start()
        running.append((daemon, thread))
        return daemon
    yield start
    for daemon, thread in running:
        daemon.shutdown()
        thread.join(timeout=5)
        assert not thread.is_alive()


def request(service, path, method="GET", data=None, token=None, tls=True, context=None):
    pairing = service.service.local_pairing
    port = pairing.tls_port if tls else service.httpd.server_port
    if tls:
        if context is None:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.load_verify_locations(cadata=pairing.certificate_pem)
        connection = http.client.HTTPSConnection("127.0.0.1", port, context=context, timeout=5)
    else:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        connection.request(method, path, body=json.dumps(data) if data is not None else None, headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read()), response.getheaders()
    finally:
        connection.close()


def invitation(service, grants=None):
    code = create_invitation(db_path=service.config.db_path, public_port=service.httpd.server_port, grants=grants or GRANTS)
    value = code.split(".", 1)[1]
    parsed = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
    return code, parsed, {key: parsed[key] for key in ("invitation_id", "secret")}


def test_automatic_registration_covers_multiple_instances_renewal_and_orderly_exit(services, tmp_path):
    first, second = services("first"), services("second")
    records = [json.loads(path.read_text()) for path in (tmp_path / "discovery").glob("*.json")]
    assert {r["port"] for r in records} == {first.httpd.server_port, second.httpd.server_port}
    assert len({r["registration_id"] for r in records}) == 2
    assert all(0 < r["expires_at_ms"] - int(time.time()*1000) <= 30000 for r in records)
    old = first._advertisement.record
    first._advertisement.renew()
    assert first._advertisement.record == old
    first.shutdown()
    remaining = [json.loads(path.read_text()) for path in (tmp_path / "discovery").glob("*.json")]
    assert [r["port"] for r in remaining] == [second.httpd.server_port]


def test_advertising_opt_out_keeps_pairing_available(services, tmp_path):
    service = services(advertise_local=False)
    assert not (tmp_path / "discovery").exists()
    assert request(service, "/v1/pairing/info")[0] == 200
    assert request(service, "/v1/version")[1]["data"]["supported_features"] == ["current-principal", "local-pairing-v1"]


def test_paired_credential_requires_pinned_tls_and_preserves_approved_grants(services):
    service = services()
    _, parsed, payload = invitation(service)
    status, body, headers = request(service, "/v1/pairing/inspect", "POST", payload)
    assert status == 200
    assert dict(headers)["Cache-Control"] == "no-store"
    assert body["data"]["namespace_grants"] == ["user/default"]
    assert body["data"]["capabilities"] == ["memory:audit", "memory:read"]
    assert "token" not in body["data"]
    assert request(service, "/v1/pairing/complete", "POST", payload, tls=False)[0] == 403
    status, result, _ = request(service, "/v1/pairing/complete", "POST", payload)
    assert status == 200
    token = result["data"]["token"]
    assert result["data"]["certificate_sha256"] == parsed["certificate_sha256"]
    status, access, _ = request(service, "/v1/auth/me", token=token)
    assert status == 200
    assert access["data"]["granted_capabilities"] == ["memory:audit", "memory:read"]
    assert access["data"]["privacy_ceiling"] == "personal"
    assert access["data"]["expires_at"]
    assert request(service, "/v1/auth/me", token=token, tls=False)[0] == 401
    assert request(service, "/v1/pairing/complete", "POST", payload)[0] == 401
    assert request(service, "/v1/pairing/current", "DELETE", token=token)[0] == 200
    assert request(service, "/v1/auth/me", token=token)[0] == 401


def test_invalid_expired_canceled_and_changed_instance_codes_fail_closed(services):
    service = services()
    for alteration in ("wrong_secret", "expired", "changed_instance", "canceled"):
        _, parsed, payload = invitation(service)
        path = service.service.local_pairing.directory / f"invitation-{parsed['invitation_id']}.json"
        if alteration == "wrong_secret":
            payload["secret"] = "x" * 43
        elif alteration == "canceled":
            assert request(service, "/v1/pairing/cancel", "POST", payload)[0] == 200
        else:
            ticket = json.loads(read_private(path))
            if alteration == "expired":
                ticket["expires_at_ms"] = int(time.time()*1000)-1
            else:
                ticket["service_identity"] = "service_other"
            write_private(path, json.dumps(ticket).encode())
        assert request(service, "/v1/pairing/complete", "POST", payload)[0] == 401
    assert service.service.auth.list_tokens() == []


def test_replay_race_can_issue_only_one_token_and_client_cannot_expand_grants(services):
    service = services()
    _, _, payload = invitation(service)
    assert request(service, "/v1/pairing/complete", "POST", {**payload, "capabilities": ["memory:admin"]})[0] == 400
    results = []
    threads = [threading.Thread(target=lambda: results.append(request(service, "/v1/pairing/complete", "POST", payload)[0])) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join(timeout=5)
    assert sorted(results) == [200, 401]
    assert len(service.service.auth.list_tokens()) == 1


def test_wrong_certificate_is_rejected_during_tls_handshake(services):
    first, second = services("first"), services("second")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cadata=first.service.local_pairing.certificate_pem)
    with pytest.raises(ssl.SSLCertVerificationError):
        request(second, "/v1/auth/me", token="synthetic-never-delivered", context=context)
    count = second.service.memory.store.connection.execute("SELECT COUNT(*) FROM service_request_log WHERE path='/v1/auth/me'").fetchone()[0]
    assert count == 0


def test_restart_preserves_certificate_and_credentials_but_invalidates_unconsumed_codes(services):
    first = services()
    fingerprint = first.service.local_pairing.fingerprint
    _, _, payload = invitation(first)
    token = request(first, "/v1/pairing/complete", "POST", payload)[1]["data"]["token"]
    _, _, unused = invitation(first)
    instance = first.service.service_identity
    first.shutdown()
    second = services()
    assert second.service.local_pairing.fingerprint == fingerprint
    assert second.service.service_identity != instance
    assert request(second, "/v1/auth/me", token=token)[0] == 200
    assert request(second, "/v1/pairing/complete", "POST", unused)[0] == 401


def test_owner_only_identity_and_tickets_do_not_contain_raw_credentials(services):
    service = services()
    code, parsed, payload = invitation(service)
    root = service.service.local_pairing.directory
    ticket = root / f"invitation-{parsed['invitation_id']}.json"
    assert (root.stat().st_mode & 0o777) == 0o700
    assert (ticket.stat().st_mode & 0o777) == 0o600
    assert parsed["secret"].encode() not in ticket.read_bytes()
    assert code.encode() not in ticket.read_bytes()
    ticket.chmod(0o644)
    assert request(service, "/v1/pairing/complete", "POST", payload)[0] == 401


@pytest.mark.parametrize("patch", [{"capabilities": ["memory:admin"]}, {"namespace_grants": []}, {"token_ttl_seconds": 0}, {"privacy_ceiling": "anything"}])
def test_operator_must_choose_supported_explicit_grants(services, patch):
    service = services()
    with pytest.raises(Exception):
        invitation(service, {**GRANTS, **patch})
    assert service.service.auth.list_tokens() == []


def test_pairing_contract_and_audit_never_record_secrets(services):
    from jsonschema import Draft202012Validator
    from openapi_spec_validator import validate
    service = services()
    schema = request(service, "/v1/openapi.json", tls=False)[1]
    schema = schema.get("data", schema)
    # Legacy operations still have generic path parameters. Certify this exact
    # profile, as the existing discovery/read/review contract suites do.
    validate({**schema, "paths": {path: value for path, value in schema["paths"].items()
        if path.startswith("/v1/pairing/") or path == "/v1/auth/me"}})
    code, parsed, payload = invitation(service)
    for path, method, body in [("/v1/pairing/info", "GET", None),
            ("/v1/pairing/inspect", "POST", payload), ("/v1/pairing/complete", "POST", payload)]:
        status, response, _ = request(service, path, method, body)
        assert status == 200
        reference = schema["paths"][path][method.lower()]["responses"]["200"]["content"]["application/json"]["schema"]
        Draft202012Validator({**reference, "components": schema["components"]}).validate(response)
    token = response["data"]["token"]
    request(service, "/v1/pairing/current", "DELETE", token=token)
    rows = service.service.memory.store.connection.execute("SELECT action, details FROM audit_log WHERE target_type='api_token'").fetchall()
    assert {row["action"] for row in rows} == {"local_pairing.completed", "local_pairing.revoked"}
    log = json.dumps([dict(row) for row in rows])
    assert all(secret not in log for secret in (code, parsed["secret"], token))


def test_failed_guesses_are_bounded_and_stalled_tls_does_not_block_accept(services):
    service = services()
    _, _, payload = invitation(service)
    for _ in range(5):
        assert request(service, "/v1/pairing/inspect", "POST", {**payload, "secret": "x" * 43})[0] == 401
    assert request(service, "/v1/pairing/complete", "POST", payload)[0] == 401
    slow = socket.create_connection(("127.0.0.1", service.service.local_pairing.tls_port), timeout=5)
    try:
        assert request(service, "/v1/pairing/info")[0] == 200
    finally:
        slow.close()


def test_database_replacement_changes_identity(services, tmp_path):
    from aletheia.service.local_files import identity_directory
    service = services()
    home_relative = "~/" + os.path.relpath(service.config.db_path, Path.home())
    assert identity_directory(home_relative) == service.service.local_pairing.directory
    fingerprint = service.service.local_pairing.fingerprint
    service.shutdown()
    database = tmp_path / "memory.db"
    # Keep the old inode allocated while the new database is created.
    database.rename(tmp_path / "original.db")
    replacement = services()
    assert replacement.service.local_pairing.fingerprint != fingerprint


@pytest.mark.parametrize("crash", [False, True])
def test_cli_registration_shutdown_and_crash_lease(tmp_path, crash):
    directory = tmp_path / "discovery"
    command = [sys.executable, "-m", "aletheia.cli.main", "serve", "--db", str(tmp_path / "cli.db"),
        "--port", "0", "--auto-migrate", "--discovery-dir", str(directory), "--identity-dir", str(tmp_path / "identities")]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 10
        records = []
        while time.monotonic() < deadline and not records and process.poll() is None:
            records = list(directory.glob("*.json"))
            time.sleep(0.05)
        assert len(records) == 1
        record = json.loads(records[0].read_text())
        assert 0 < record["expires_at_ms"] - time.time() * 1000 <= 30000
        if crash:
            process.kill()
        else:
            process.terminate()
        process.wait(timeout=10)
        assert records[0].exists() == crash
        if crash:
            assert json.loads(records[0].read_text())["expires_at_ms"] == record["expires_at_ms"]
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
