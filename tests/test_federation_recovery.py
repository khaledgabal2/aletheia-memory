"""Synthetic recovery drills: key retirement must not revive old trust."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import asdict
from threading import Barrier
from zipfile import BadZipFile, ZipFile

import pytest

from aletheia import AletheiaClient, AsyncAletheiaClient, Memory
from aletheia.cli.main import main
from aletheia.core import federation as fed
from aletheia.core.errors import ValidationError
from aletheia.models import ServiceConfig
from aletheia.service.auth import AuthService
from aletheia.service.http import AletheiaService, openapi_schema


NS = "recovery/test"
RECOVERY_SECRET = "synthetic-separate-recovery-passphrase"


@pytest.fixture
def pair(tmp_path, monkeypatch):
    monkeypatch.setenv("ALETHEIA_FEDERATION_RECOVERY_KEY", RECOVERY_SECRET)
    monkeypatch.setenv("ALETHEIA_FEDERATION_KEY", "synthetic-live-key-protection")
    left = Memory.open(str(tmp_path / "left.db"), namespace=NS)
    right = Memory.open(str(tmp_path / "right.db"), namespace=NS)
    try:
        left.create_federation_identity(display_name="Left", protected=False)
        right.create_federation_identity(display_name="Right", protected=False)
        recipient = left.add_peer(peer_identity=right.export_federation_identity(), trust_status="trusted_device", reason="fixture")
        sender = right.add_peer(peer_identity=left.export_federation_identity(), trust_status="trusted_device", reason="fixture")
        left.remember(namespace=NS, memory_type="project", subject="project", predicate="state",
                      object="synthetic pending memory", text="synthetic confidential evidence", privacy_level="private")
        yield left, right, recipient, sender
    finally:
        left.close()
        right.close()


def snapshot(memory):
    return list(memory.store.connection.iterdump())


def rotate(memory, path, **overrides):
    options = dict(expected_fingerprint=memory.active_federation_identity().key_fingerprint,
                   recovery_path=str(path), reason="synthetic compromise recovery")
    options.update(overrides)
    return memory.rotate_federation_key(**options)


def approve(memory, peer, identity, **overrides):
    options = dict(peer_identity=identity, expected_fingerprint=peer.key_fingerprint,
                   confirmed_fingerprint=identity["key_fingerprint"], reason="independently verified replacement")
    options.update(overrides)
    return memory.replace_peer_key(peer.id, **options)


def bundle(memory, recipient, path):
    share = memory.create_share_grant(name=path.stem, namespace=NS, recipient_peer_ids=[recipient.id],
                                     permissions=["read_claims", "read_evidence"], privacy_ceiling="private", reason="fixture")
    memory.export_share_bundle(share_id=share.id, output_path=str(path), encrypt=True)
    return share


@pytest.mark.parametrize("protected", [False, True])
def test_rotation_archives_only_decryption_key_and_revokes_grants(pair, tmp_path, protected):
    left, right, recipient, _ = pair
    identity = left.active_federation_identity()
    old_doc = fed._private_key_doc(identity)
    metadata = {**identity.metadata, "protected_private_key": protected,
                "private_key_ref": fed._private_key_ref(old_doc, protected=protected)}
    left.store.connection.execute("UPDATE federation_identities SET metadata_json = ? WHERE id = ?", (json.dumps(metadata), identity.id))
    share = bundle(left, recipient, tmp_path / "old.aletsync")
    recovery_path = tmp_path / "left.recovery"
    new = rotate(left, recovery_path)
    assert new.instance_id == identity.instance_id
    assert new.key_fingerprint != identity.key_fingerprint
    new_doc = fed._private_key_doc(new)
    assert all(old_doc[role]["private_key"] != new_doc[role]["private_key"] for role in ("signing", "encryption"))
    assert left.get_share_grant(share.id).status == "revoked"
    assert left.get_sync_collection(share.id).status == "revoked"
    assert all(item.status == "revoked" for item in left.list_share_recipients(share.id))
    raw = recovery_path.read_text()
    assert all(old_doc[role]["private_key"] not in raw for role in ("signing", "encryption"))
    from aletheia.core import federation_recovery as recovery
    archived = recovery._read_encrypted_document(recovery_path, RECOVERY_SECRET, recovery.KEY_ARCHIVE_FORMAT)
    assert archived["encryption_private_key"] == old_doc["encryption"]["private_key"]
    assert old_doc["signing"]["private_key"] not in json.dumps(archived)
    assert "private_key_ref" not in json.dumps(archived)
    if os.name == "posix":
        assert recovery_path.stat().st_mode & 0o777 == 0o600
    assert identity.metadata["private_key_ref"] not in json.dumps(new.metadata)
    assert any(record.metadata.get("old_fingerprint") == identity.key_fingerprint for record in left.list_revocations())


@pytest.mark.parametrize("failure", ["missing_confirmation", "stale_confirmation", "missing_archive", "missing_secret", "existing_file", "symlink"])
def test_rotation_preconditions_do_not_change_identity(pair, tmp_path, monkeypatch, failure):
    left, _, _, _ = pair
    path = tmp_path / "recovery.key"
    options = {}
    if failure == "missing_confirmation":
        options["expected_fingerprint"] = None
    elif failure == "stale_confirmation":
        options["expected_fingerprint"] = "0" * 32
    elif failure == "missing_archive":
        options["recovery_path"] = None
    elif failure == "missing_secret":
        monkeypatch.delenv("ALETHEIA_FEDERATION_RECOVERY_KEY")
    elif failure == "existing_file":
        path.write_text("must not overwrite")
    else:
        target = tmp_path / "untouched"
        target.write_text("must not overwrite")
        path.symlink_to(target)
    before = snapshot(left)
    with pytest.raises((ValidationError, FileExistsError)):
        rotate(left, path, **options)
    assert snapshot(left) == before
    if failure in {"existing_file", "symlink"}:
        assert path.read_text() == "must not overwrite"
    else:
        assert not path.exists()


def test_old_rotation_call_fails_safely_instead_of_discarding_keys(pair):
    left, _, _, _ = pair
    before = snapshot(left)
    with pytest.raises(ValidationError, match="fingerprint|recovery"):
        left.rotate_federation_key(reason="old caller with no recovery plan")
    assert snapshot(left) == before


def test_rotation_failure_preserves_database_and_encrypted_recovery_copy(pair, tmp_path, monkeypatch):
    left, _, recipient, _ = pair
    share = bundle(left, recipient, tmp_path / "old.aletsync")
    before = snapshot(left)
    original = fed._write_federation_audit

    def fail_after_rotation(*args, **kwargs):
        if kwargs.get("event_type") == "identity.key_rotated":
            raise RuntimeError("simulated audit persistence failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(fed, "_write_federation_audit", fail_after_rotation)
    recovery_path = tmp_path / "recovery.key"
    with pytest.raises(RuntimeError, match="persistence"):
        rotate(left, recovery_path)
    assert snapshot(left) == before
    assert left.get_share_grant(share.id).status == "active"
    assert recovery_path.exists()  # Preserve the encrypted safety copy on failure.
    assert "encryption_private_key" not in recovery_path.read_text()


@pytest.mark.parametrize("initial_status", ["trusted_device", "revoked", "blocked"])
def test_peer_replacement_requires_fresh_trust_and_grants(pair, tmp_path, initial_status):
    left, right, recipient, sender = pair
    old_identity = left.export_federation_identity()
    outgoing = bundle(right, sender, tmp_path / "right-old.aletsync")
    old_bundle = tmp_path / "left-old.aletsync"
    bundle(left, recipient, old_bundle)
    if initial_status == "revoked":
        right.revoke_peer(sender.id, reason="incident")
    elif initial_status == "blocked":
        right.trust_peer(sender.id, trust_status="blocked", reason="incident")
    rotate(left, tmp_path / "left.key")
    replacement = left.export_federation_identity()
    with pytest.raises(ValidationError):
        right.add_peer(peer_identity=replacement, reason="ordinary add must not replace a pin")
    updated = approve(right, sender, replacement)
    assert updated.public_key == replacement["public_key"]
    assert updated.trust_status == "unknown"
    assert updated.trust_domain_id is None and updated.trusted_at is None and updated.revoked_at is None
    assert right.get_share_grant(outgoing.id).status == "revoked"
    assert right.get_sync_collection(outgoing.id).status == "revoked"
    before = snapshot(right)
    with pytest.raises(ValidationError):
        right.import_share_bundle(input_path=str(old_bundle))
    assert snapshot(right) == before
    with pytest.raises(ValidationError, match="retired|revoked"):
        approve(right, updated, old_identity)
    new_bundle = tmp_path / "left-new.aletsync"
    bundle(left, recipient, new_bundle)
    with pytest.raises(ValidationError, match="trusted"):
        right.import_share_bundle(input_path=str(new_bundle), trust_policy="trusted_device")
    right.import_share_bundle(input_path=str(new_bundle))
    assert len(right.list_candidates(NS)) == 1
    assert right.list_claims(namespace=NS) == []


@pytest.mark.parametrize("bad_field", ["expected_fingerprint", "confirmed_fingerprint", "instance_id", "same_keys", "signing_key_reuse", "encryption_key_reuse"])
def test_peer_replacement_rejects_wrong_identity_or_confirmation(pair, tmp_path, bad_field):
    left, right, _, sender = pair
    old_payload = left.export_federation_identity()
    rotate(left, tmp_path / "left.key")
    replacement = left.export_federation_identity()
    options = {}
    if bad_field in {"expected_fingerprint", "confirmed_fingerprint"}:
        options[bad_field] = "0" * 32
    elif bad_field == "instance_id":
        replacement["instance_id"] = "different-instance"
    elif bad_field == "same_keys":
        replacement = old_payload
    else:
        role = "signing" if bad_field == "signing_key_reuse" else "encryption"
        doc = fed._public_key_doc(replacement["public_key"])
        doc[role] = fed._public_key_doc(old_payload["public_key"])[role]
        replacement["public_key"] = fed.FEDERATION_PUBLIC_KEY_PREFIX + fed._b64_json(doc)
        replacement["key_fingerprint"] = fed.sha256_hex(replacement["public_key"])[:32]
    before = snapshot(right)
    with pytest.raises(ValidationError):
        approve(right, sender, replacement, **options)
    assert snapshot(right) == before


def test_replacement_failure_rolls_back_key_trust_and_grants(pair, tmp_path, monkeypatch):
    left, right, _, sender = pair
    bundle(right, sender, tmp_path / "right-old.aletsync")
    rotate(left, tmp_path / "left.key")
    replacement = left.export_federation_identity()
    before = snapshot(right)
    original = fed._write_federation_audit

    def fail_after_replacement(*args, **kwargs):
        if kwargs.get("event_type") == "peer.key_replaced":
            raise RuntimeError("simulated audit failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(fed, "_write_federation_audit", fail_after_replacement)
    with pytest.raises(RuntimeError):
        approve(right, sender, replacement)
    assert snapshot(right) == before


def test_retired_key_cannot_return_after_restart_or_metadata_refresh(pair, tmp_path):
    left, right, _, sender = pair
    old = left.export_federation_identity()
    rotate(left, tmp_path / "left.key")
    replacement = left.export_federation_identity()
    approve(right, sender, replacement)
    right.add_peer(peer_identity=replacement, reason="refresh ordinary peer metadata")
    with closing(Memory.open(str(tmp_path / "right.db"), namespace=NS)) as reopened:
        before = snapshot(reopened)
        with pytest.raises(ValidationError, match="retired|revoked"):
            approve(reopened, reopened.get_peer(sender.id), old)
        with pytest.raises(ValidationError, match="fingerprint|changed"):
            approve(reopened, sender, replacement)
        assert snapshot(reopened) == before


@pytest.mark.parametrize("change", ["replacement", "revocation"])
def test_in_flight_trust_approval_cannot_outlive_key_replacement_or_revocation(pair, tmp_path, monkeypatch, change):
    left, right, _, sender = pair
    rotate(left, tmp_path / "left.key")
    replacement = left.export_federation_identity()
    original = fed.get_peer
    changed = False
    after_change = None

    def read_then_change(memory, peer_id):
        nonlocal changed, after_change
        peer = original(memory, peer_id)
        if memory is right and not changed:
            changed = True
            # Commit the other operator's action between this approval's
            # peer read and its write, using an independent DB connection.
            with closing(Memory.open(str(tmp_path / "right.db"), namespace=NS)) as concurrent:
                if change == "replacement":
                    approve(concurrent, sender, replacement)
                else:
                    concurrent.revoke_peer(sender.id, reason="concurrent incident response")
            after_change = snapshot(right)
        return peer

    monkeypatch.setattr(fed, "get_peer", read_then_change)
    with pytest.raises(ValidationError, match="changed|revoked"):
        right.trust_peer(sender.id, trust_status="trusted_device", reason="approval begun before recovery")
    assert changed and snapshot(right) == after_change
    assert original(right, sender.id).trust_status == ("unknown" if change == "replacement" else "revoked")


@pytest.mark.parametrize("legacy_metadata", [False, True])
def test_pending_bundle_recovery_is_encrypted_and_does_not_import(pair, tmp_path, monkeypatch, legacy_metadata):
    left, right, recipient, _ = pair
    old_identity = right.active_federation_identity()
    pending = tmp_path / "pending.aletsync"
    share = bundle(left, recipient, pending)
    sender_identity = left.active_federation_identity()
    if legacy_metadata:
        # Reproduce the old serialization with real signatures/encryption;
        # the recovery reader itself remains unmodified.
        manifest, payload = fed._read_bundle(right, str(pending))
        payload["peer_identity"] = payload["origin_identity"] = asdict(sender_identity)
        with monkeypatch.context() as legacy_writer:
            legacy_writer.setattr(fed, "_public_identity_payload", asdict)
            fed._write_bundle(str(pending), manifest=manifest, payload=payload, encrypt=True,
                              signer=sender_identity, recipients=left.list_share_recipients(share.id))
        with ZipFile(pending) as exposed:
            assert sender_identity.metadata["private_key_ref"] in exposed.read("origin_identity.json").decode()
    archive = tmp_path / "right.key"
    rotate(right, archive)
    with pytest.raises(ValidationError, match="addressed"):
        right.import_share_bundle(input_path=str(pending))
    output = tmp_path / "pending.review"
    before = snapshot(right)
    result = right.recover_share_bundle_for_review(input_path=str(pending), recovery_path=str(archive),
                                                 expected_fingerprint=old_identity.key_fingerprint,
                                                 output_path=str(output), reason="review old pending data")
    assert result["requires_review"] is True
    assert snapshot(right) == before
    assert "synthetic confidential evidence" not in output.read_text()
    recovered = right.read_federation_recovery_review(input_path=str(output))
    assert recovered["requires_review"] is True
    assert recovered["payloads"]["claims"][0]["object"] == "synthetic pending memory"
    assert recovered["payloads"]["evidence"][0]["content"] == "synthetic confidential evidence"
    assert "private_key_ref" not in json.dumps(recovered)
    assert sender_identity.metadata["private_key_ref"] not in json.dumps(recovered)
    with pytest.raises((ValidationError, BadZipFile)):
        right.import_share_bundle(input_path=str(output))
    assert snapshot(right) == before
    assert RECOVERY_SECRET not in json.dumps(result)


@pytest.mark.parametrize("failure", ["wrong_passphrase", "wrong_fingerprint", "corrupt_archive", "corrupt_bundle", "existing_output"])
def test_pending_recovery_rejects_invalid_inputs_without_writes(pair, tmp_path, failure):
    left, right, recipient, _ = pair
    old = right.active_federation_identity()
    pending = tmp_path / "pending.aletsync"
    bundle(left, recipient, pending)
    archive = tmp_path / "right.key"
    rotate(right, archive)
    output = tmp_path / "pending.review"
    options = {}
    if failure == "wrong_passphrase":
        options["recovery_passphrase"] = "incorrect-secret"
    elif failure == "wrong_fingerprint":
        options["expected_fingerprint"] = "0" * 32
    elif failure == "corrupt_archive":
        data = json.loads(archive.read_text())
        ciphertext = bytearray(fed._unb64(data["ciphertext"]))
        ciphertext[-1] ^= 1
        data["ciphertext"] = fed._b64(bytes(ciphertext))
        archive.write_text(json.dumps(data))
    elif failure == "corrupt_bundle":
        with ZipFile(pending) as source:
            entries = {name: source.read(name) for name in source.namelist()}
        entries["encrypted_payload.bin"] += b"tampered"
        with ZipFile(pending, "w") as target:
            for name, content in entries.items():
                target.writestr(name, content)
    else:
        output.write_text("must not overwrite")
    before = snapshot(right)
    request = dict(input_path=str(pending), recovery_path=str(archive), output_path=str(output),
                   expected_fingerprint=old.key_fingerprint, reason="synthetic recovery check")
    request.update(options)
    with pytest.raises((ValidationError, FileExistsError)):
        right.recover_share_bundle_for_review(**request)
    assert snapshot(right) == before
    if failure == "existing_output":
        assert output.read_text() == "must not overwrite"
    else:
        assert not output.exists()


def test_concurrent_rotation_accepts_only_one_confirmation(pair, tmp_path):
    left, _, _, _ = pair
    old = left.active_federation_identity()
    barrier = Barrier(2)

    def attempt(index):
        with closing(Memory.open(str(tmp_path / "left.db"), namespace=NS)) as memory:
            barrier.wait(timeout=5)
            try:
                rotate(memory, tmp_path / f"rotation-{index}.key", expected_fingerprint=old.key_fingerprint)
                return "rotated"
            except ValidationError:
                return "stale"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, [0, 1]))
    assert sorted(outcomes) == ["rotated", "stale"]
    assert len(list(tmp_path.glob("rotation-*.key"))) == 1
    assert len(left.active_federation_identity().metadata["old_public_keys"]) == 1


def test_cli_recovery_and_peer_approval_do_not_print_private_material(pair, tmp_path, capsys):
    left, right, recipient, _ = pair
    old = right.active_federation_identity()
    pending = tmp_path / "pending.aletsync"
    bundle(left, recipient, pending)
    archive = tmp_path / "right.key"
    assert main(["federation", "rotate-key", "--db", str(tmp_path / "right.db"),
                 "--expected-fingerprint", old.key_fingerprint, "--recovery-output", str(archive),
                 "--reason", "synthetic CLI recovery"]) == 0
    response = json.loads(capsys.readouterr().out)
    assert "private_key_ref" not in json.dumps(response)
    assert response["key_fingerprint"] != old.key_fingerprint
    identity_file = tmp_path / "right.identity.json"
    identity_file.write_text(json.dumps(right.export_federation_identity()))
    assert main(["peers", "replace-key", recipient.id, "--db", str(tmp_path / "left.db"),
                 "--identity", str(identity_file), "--expected-fingerprint", old.key_fingerprint,
                 "--confirmed-fingerprint", response["key_fingerprint"], "--reason", "independent verification"]) == 0
    assert json.loads(capsys.readouterr().out)["trust_status"] == "unknown"
    assert main(["federation", "recover-bundle", "--db", str(tmp_path / "right.db"),
                 "--input", str(pending), "--recovery-key", str(archive), "--expected-fingerprint", old.key_fingerprint,
                 "--output", str(tmp_path / "pending.review"), "--reason", "review pending data"]) == 0
    summary = capsys.readouterr().out
    assert json.loads(summary)["requires_review"] is True
    assert "synthetic confidential evidence" not in summary
    assert right.list_candidates(NS) == []
    assert main(["federation", "init", "--db", str(tmp_path / "fresh.db"), "--display-name", "Fresh"]) == 0
    assert "private_key_ref" not in capsys.readouterr().out


def http(memory, tmp_path, capabilities):
    auth = AuthService(memory)
    client = auth.create_client(name="recovery test", client_type="test")
    _, token = auth.create_token(client_id=client.id, namespace_grants=["*"], capabilities=capabilities)
    service = AletheiaService(memory, ServiceConfig(db_path=str(tmp_path / "right.db"), auth_required=True))

    def call(method, path, payload=None):
        return service.handle_http(method=method, path=path, headers={"Authorization": f"Bearer {token}"},
                                   body=json.dumps(payload).encode() if payload is not None else b"")

    return call


@pytest.mark.parametrize("capabilities,expected", [(["memory:federation", "memory:peers"], 403), (["memory:admin"], 200)])
def test_http_recovery_requires_admin_and_returns_public_identity(pair, tmp_path, capabilities, expected):
    left, right, _, sender = pair
    rotate(left, tmp_path / "left.key")
    replacement = left.export_federation_identity()
    call = http(right, tmp_path, capabilities)
    status, response = call("POST", f"/v1/peers/{sender.id}/replace-key", {
        "peer_identity": replacement, "expected_fingerprint": sender.key_fingerprint,
        "confirmed_fingerprint": replacement["key_fingerprint"], "reason": "independently confirmed replacement",
    })
    assert status == expected, response
    assert "private_key_ref" not in json.dumps(response)
    assert right.get_peer(sender.id).key_fingerprint == (replacement["key_fingerprint"] if expected == 200 else sender.key_fingerprint)
    old = right.active_federation_identity()
    status, response = call("POST", "/v1/federation/identity/rotate", {
        "expected_fingerprint": old.key_fingerprint, "recovery_path": str(tmp_path / "right.key"), "reason": "recovery",
    })
    assert status == expected, response
    assert "private_key_ref" not in json.dumps(response)
    if expected == 200:
        assert right.active_federation_identity().key_fingerprint != old.key_fingerprint
    else:
        assert right.active_federation_identity() == old
        assert not (tmp_path / "right.key").exists()
    for method, path in [("GET", "/v1/federation/identity"), ("GET", "/v1/federation/status")]:
        status, response = call(method, path)
        assert status == 200, response
        assert "private_key_ref" not in json.dumps(response)
    schema = openapi_schema()
    assert schema["paths"]["/v1/peers/{peer_id}/replace-key"]["post"]["x-required-capability"] == "memory:admin"


def test_http_rotation_rejects_missing_confirmation_and_unsafe_output(pair, tmp_path):
    _, right, _, _ = pair
    call = http(right, tmp_path, ["memory:admin"])
    old = right.active_federation_identity()
    occupied = tmp_path / "occupied.key"
    occupied.write_text("untouched")
    for payload in [
        {"reason": "old SDK request"},
        {"reason": "unsafe output", "expected_fingerprint": old.key_fingerprint, "recovery_path": str(tmp_path / "right.db")},
        {"reason": "outside allowed roots", "expected_fingerprint": old.key_fingerprint,
         "recovery_path": str(tmp_path.parent / "outside.key")},
        {"reason": "must not overwrite", "expected_fingerprint": old.key_fingerprint, "recovery_path": str(occupied)},
    ]:
        status, _ = call("POST", "/v1/federation/identity/rotate", payload)
        assert status == 400
        assert right.active_federation_identity() == old
    assert occupied.read_text() == "untouched"


def test_recovery_file_verification_failure_prevents_rotation(pair, tmp_path, monkeypatch):
    from aletheia.core import federation_recovery as recovery
    left, _, _, _ = pair
    before = snapshot(left)
    monkeypatch.setattr(recovery, "_read_encrypted_document", lambda *_args: {"corrupt": True})
    with pytest.raises(ValidationError, match="verification"):
        rotate(left, tmp_path / "failed-verification.key")
    assert snapshot(left) == before


def test_recovery_archive_cannot_be_used_for_a_different_instance(pair, tmp_path):
    left, right, recipient, _ = pair
    old = right.active_federation_identity()
    pending = tmp_path / "pending.aletsync"
    bundle(left, recipient, pending)
    archive = tmp_path / "right.key"
    rotate(right, archive)
    before = snapshot(left)
    output = tmp_path / "wrong-instance.review"
    with pytest.raises(ValidationError, match="another local identity"):
        left.recover_share_bundle_for_review(input_path=str(pending), recovery_path=str(archive),
                                             expected_fingerprint=old.key_fingerprint, output_path=str(output), reason="fixture")
    assert snapshot(left) == before
    assert not output.exists()


def test_recovery_survives_restart_without_restoring_old_import_authority(pair, tmp_path):
    left, right, recipient, _ = pair
    old = right.active_federation_identity()
    pending = tmp_path / "pending.aletsync"
    old_share = bundle(left, recipient, pending)
    archive = tmp_path / "right.key"
    rotate(right, archive)
    approve(left, recipient, right.export_federation_identity())
    left.trust_peer(recipient.id, trust_status="trusted_device", reason="explicit new approval")
    fresh = tmp_path / "fresh.aletsync"
    bundle(left, left.get_peer(recipient.id), fresh)
    assert left.get_share_grant(old_share.id).status == "revoked"
    with closing(Memory.open(str(tmp_path / "right.db"), namespace=NS)) as reopened:
        before = snapshot(reopened)
        reopened.recover_share_bundle_for_review(input_path=str(pending), recovery_path=str(archive),
                                                 expected_fingerprint=old.key_fingerprint, output_path=str(tmp_path / "review"),
                                                 reason="recover after restart")
        assert snapshot(reopened) == before
        with pytest.raises(ValidationError):
            reopened.import_share_bundle(input_path=str(pending))
        reopened.import_share_bundle(input_path=str(fresh))
        assert len(reopened.list_candidates(NS)) == 1
        assert reopened.list_claims(namespace=NS) == []


def test_sdk_recovery_calls_the_guarded_http_routes(pair, tmp_path, monkeypatch):
    left, right, _, sender = pair
    rotate(left, tmp_path / "left.key")
    replacement = left.export_federation_identity()
    call = http(right, tmp_path, ["memory:admin"])

    def request(_self, method, path, payload=None):
        status, body = call(method, path, payload)
        assert status == 200, body
        return body["data"]

    # Exercise both SDKs through real service dispatch without an external server.
    monkeypatch.setattr(AletheiaClient, "_request", request)
    client = AletheiaClient("http://127.0.0.1")
    old = right.active_federation_identity()
    result = client.rotate_federation_key(reason="SDK recovery", expected_fingerprint=old.key_fingerprint,
                                          recovery_path=str(tmp_path / "right.key"))
    assert result["key_fingerprint"] != old.key_fingerprint
    assert "private_key_ref" not in json.dumps(result)
    import asyncio
    async_client = AsyncAletheiaClient("http://127.0.0.1")
    result = asyncio.run(async_client.replace_peer_key(sender.id, peer_identity=replacement,
                        expected_fingerprint=sender.key_fingerprint, confirmed_fingerprint=replacement["key_fingerprint"],
                        reason="SDK independently confirmed peer"))
    assert result["trust_status"] == "unknown"
