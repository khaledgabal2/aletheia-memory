"""Memory-owned Phase 0 evidence harness; no production API changes.

Run from an installed package environment:
    python scripts/v1_4_phase0.py --output /tmp/aletheia-phase0-evidence

Only creates disposable synthetic databases and binds an ephemeral loopback port.
Does not access a user's database, provider configuration, or Desktop checkout.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from aletheia import Memory
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaDaemon


ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = "user/phase0-demo"
TEXT = "User prefers careful architecture notes."
FIXTURES = ROOT / "tests/fixtures/v1_3_1"


def load_legacy_client():
    spec = importlib.util.spec_from_file_location("aletheia_legacy_131", FIXTURES / "client.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.AletheiaClient


@contextmanager
def local_service(directory):
    config = ServiceConfig(
        db_path=str(Path(directory) / "service.db"), host="127.0.0.1", port=0,
        auto_migrate=True, auth_required=True, rate_limit_enabled=False,
    )
    daemon = AletheiaDaemon(config)
    thread = None
    try:
        host, port = daemon.start()
        thread = threading.Thread(target=daemon.httpd.serve_forever, daemon=True)
        thread.start()
        auth = daemon.service.auth
        tokens = {}
        for name, capabilities in {
            "agent": ["memory:read", "memory:context", "memory:write_candidate", "memory:audit"],
            "reviewer": ["memory:read", "memory:review", "memory:audit"],
            "reader": ["memory:read"],
        }.items():
            client = auth.create_client(name=f"phase0-{name}", client_type="test")
            _, tokens[name] = auth.create_token(
                client_id=client.id, namespace_grants=[NAMESPACE],
                capabilities=capabilities, privacy_ceiling="personal",
            )
        yield daemon.service, f"http://{host}:{port}", tokens
    finally:
        if thread is not None:
            daemon.shutdown()
            thread.join(timeout=5)
        else:
            if daemon.httpd is not None:
                daemon.httpd.server_close()
            daemon.service.close()


def request(base_url, method, path, *, token=None, payload=None, headers=None):
    request_headers = {"X-Request-ID": "req_phase0", **(headers or {})}
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    data = None
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
        data = json.dumps(payload, sort_keys=True).encode()
    req = Request(base_url + path, data=data, headers=request_headers, method=method)
    try:
        response = urlopen(req, timeout=10)
    except HTTPError as exc:
        response = exc
    with response:
        return {
            "status": response.status,
            "headers": {key: value for key, value in response.headers.items()
                        if key.lower() not in {"date", "server", "content-length"}},
            "body": json.loads(response.read()),
        }


def lifecycle(path):
    """Use existing public APIs and an explicitly supplied automated review decision."""
    started = time.perf_counter()
    memory = Memory.open(str(path), namespace=NAMESPACE)
    try:
        batch = memory.ingest(NAMESPACE, source_type="manual", content=TEXT,
                              trust_level="user_asserted")
        run = memory.extract_candidates(NAMESPACE, batch_id=batch.id, extractor="rule_based")
        candidates = memory.list_candidates(NAMESPACE, extraction_run_id=run.id)
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.candidate_status == "pending_review"
        assert memory.retrieve(NAMESPACE, "architecture", mode="lexical") == []
        claim = memory.promote_candidate(candidate.id, reason="Phase 0 fixture: inspected and approved.")
        hits = memory.retrieve(NAMESPACE, "architecture", mode="lexical")
        pack = memory.context_pack(NAMESPACE, "architecture", retrieval_mode="lexical", record_usage=False)
        explanation = memory.explain_claim(claim.id)
        assert hits and hits[0].claim_id == claim.id
        assert claim.id in [item.claim_id for item in pack.items()]
        assert claim.evidence_ids == batch.evidence_ids
        assert explanation is not None
    finally:
        memory.close()
    reopened = Memory.open(str(path), namespace=NAMESPACE)
    try:
        assert reopened.retrieve(NAMESPACE, "architecture", mode="lexical")[0].claim_id == claim.id
        assert reopened.read_event(batch.evidence_ids[0]).content == TEXT
    finally:
        reopened.close()
    return {
        "input": TEXT, "query": "architecture", "candidate_count": len(candidates),
        "pending_results": 0, "review": "explicit automated fixture decision",
        "retrieval_matches_claim": True, "context_contains_claim": True,
        "evidence_preserved_after_reopen": True,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "timing_scope": "automated lifecycle only; excludes installation and human reading/review",
    }


def capture(output):
    # Refuse to label a later implementation as the historical baseline.
    provenance = json.loads((FIXTURES / "provenance.json").read_text())
    for name, expected in provenance["runtime_sha256"].items():
        module = importlib.import_module(name)
        if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Baseline capture requires unmodified published 1.3.1: {name}")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    records = {}
    with tempfile.TemporaryDirectory(prefix="aletheia-phase0-") as directory:
        journey = lifecycle(Path(directory) / "journey.db")
        with local_service(directory) as (service, base_url, tokens):
            def record(name, method, path, role="agent", payload=None, headers=None):
                result = request(base_url, method, path, token=tokens.get(role), payload=payload, headers=headers)
                records[name] = {"method": method, "path": path, "role": role, **result}
                return result

            for name, path in {
                "health": "/v1/health", "ready": "/v1/ready", "version": "/v1/version",
                "legacy_principal": "/v1/console/session",
                "compatibility": "/v1/compatibility/report?include_plugins=false&include_sdks=false&include_runtime=false",
                "principal_unavailable": "/v1/auth/me",
            }.items():
                record(name, "GET", path)
            schema_response = request(base_url, "GET", "/v1/openapi.json")
            assert schema_response["status"] == 200
            schema = schema_response["body"]["data"]
            payload = {
                "namespace": NAMESPACE, "write_mode": "candidate", "memory_type": "preference",
                "subject": "user", "predicate": "prefers", "object": "careful architecture notes",
                "evidence_text": TEXT, "trust_level": "user_asserted", "privacy_level": "personal",
            }
            created = record("remember", "POST", "/v1/remember", payload=payload,
                             headers={"Idempotency-Key": "phase0-create"})
            assert created["status"] == 200
            candidate_id = created["body"]["data"]["candidate"]["id"]
            replay = record("remember_replay", "POST", "/v1/remember", payload=payload,
                            headers={"Idempotency-Key": "phase0-create"})
            assert replay["body"] == created["body"]
            record("idempotency_conflict", "POST", "/v1/remember", payload={**payload, "object": "changed"},
                   headers={"Idempotency-Key": "phase0-create"})
            record("candidates", "GET", f"/v1/candidates?namespace={NAMESPACE}&limit=1", role="reviewer")
            record("candidate", "GET", f"/v1/candidates/{candidate_id}", role="reviewer")
            record("candidate_denied", "GET", f"/v1/candidates/{candidate_id}", role="reader")
            record("dashboard", "GET", f"/v1/dashboard/overview?namespace={NAMESPACE}", role="reviewer")
            promoted = record("promote", "POST", f"/v1/candidates/{candidate_id}/promote",
                              role="reviewer", payload={"reason": "Explicit Phase 0 fixture review"})
            assert promoted["status"] == 200
            claim_id = promoted["body"]["data"]["id"]
            record("claim", "GET", f"/v1/claims/{claim_id}")
            record("explain", "GET", f"/v1/claims/{claim_id}/explain")
            record("audit", "GET", f"/v1/audit/claim/{claim_id}")
            for name, path in [("retrieve", "/v1/retrieve"), ("search_alias", "/v1/search")]:
                record(name, "POST", path, payload={"namespace": NAMESPACE, "query": "architecture", "mode": "lexical"})
            record("context", "POST", "/v1/context-pack", payload={
                "namespace": NAMESPACE, "query": "architecture", "retrieval_mode": "lexical", "record_usage": False})
            second = record("remember_second", "POST", "/v1/remember", payload={**payload, "object": "another note"})
            second_id = second["body"]["data"]["candidate"]["id"]
            record("reject", "POST", f"/v1/candidates/{second_id}/reject", role="reviewer",
                   payload={"reason": "Explicit Phase 0 fixture rejection"})
            record("unauthenticated", "POST", "/v1/retrieve", role=None, payload={"namespace": NAMESPACE})
            record("namespace_denied", "POST", "/v1/retrieve", payload={"namespace": "user/other"})
            record("validation", "POST", "/v1/retrieve", payload={})
            record("claim_missing", "GET", "/v1/claims/missing")
            legacy = load_legacy_client()(base_url, tokens["agent"]).check_compatibility()
            assert legacy["compatible"] is True

    inventory = json.loads((ROOT / "contracts/v1.4.0/profiles.json").read_text())
    selected_paths = {op["path"] for op in inventory["operations"]}
    selected = {**schema, "paths": {path: item for path, item in schema["paths"].items() if path in selected_paths}}
    operations = [op for item in schema["paths"].values() for op in item.values()]
    summary = {
        "baseline_revision": "1cb3e607450b2d0d345cc3c06d73223b7f3e3fe4", "python": platform.python_version(),
        "openapi": schema["openapi"], "paths": len(schema["paths"]), "operations": len(operations),
        "schemas": len(schema["components"]["schemas"]),
        "unrestricted_request_bodies": sum(
            op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}).get("additionalProperties") is True
            for op in operations),
        "operation_ids": sum("operationId" in op for op in operations),
        "path_query_parameters": sum(p["in"] in {"path", "query"} for op in operations for p in op.get("parameters", [])),
        "full_schema_sha256": hashlib.sha256(json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "schema_capture": "data extracted from real HTTP /v1/openapi.json envelope; selected paths retained",
        "legacy_client_compatible": legacy["compatible"], "lifecycle": journey,
        "limitations": ["Baseline evidence, not v1.4.0 conformance", "No browser or migration verification yet",
                        "Synthetic IDs/times are retained; responses are observations, not byte-for-byte golden outputs"],
    }
    for filename, data in [("summary.json", summary), ("openapi.json", selected), ("responses.json", records)]:
        (output / filename).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--typescript", action="store_true", help="Run compiled generic client against an isolated service")
    args = parser.parse_args()
    if args.typescript:
        import os
        with tempfile.TemporaryDirectory(prefix="aletheia-ts-") as directory:
            with local_service(directory) as (_, base_url, tokens):
                env = {**os.environ, "ALETHEIA_TEST_URL": base_url, "ALETHEIA_TEST_TOKEN": tokens["agent"]}
                subprocess.run(["node", "dist/smoke.js"], cwd=ROOT / "contracts/typescript", env=env, check=True, timeout=30)
    elif args.output:
        print(json.dumps(capture(args.output), indent=2))
    else:
        parser.error("choose --output or --typescript")


if __name__ == "__main__":
    main()
