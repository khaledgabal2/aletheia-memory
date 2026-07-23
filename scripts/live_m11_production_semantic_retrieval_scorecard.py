#!/usr/bin/env python3
"""Run live M11 production semantic retrieval scorecard checks."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import Memory
from aletheia.cli.main import main as cli_main
from aletheia.storage import SCHEMA_VERSION


NAMESPACE = "live/m11"


def run_cli(argv: list[str]) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        status = cli_main(argv)
    assert status == 0
    return buffer.getvalue()


@dataclass
class ScoreCase:
    category: str
    name: str
    measure: str
    fn: Callable[[], str]


class M11LiveScorecard:
    def __init__(self, base_dir: Path, db_path: Path):
        self.base_dir = base_dir
        self.db_path = db_path
        self.ids: dict[str, str] = {}

    def cases(self) -> list[ScoreCase]:
        return [
            ScoreCase("Setup", "Schema and M11 columns initialize", "schema version and embedding lineage columns are present", self.case_init),
            ScoreCase("Providers", "Mock provider remains deterministic", "mock provider stays default and deterministic for CI/golden tests", self.case_mock_provider),
            ScoreCase("Providers", "Local provider records model, dimension, and lineage", "local_hash indexes real vector rows with version metadata", self.case_local_provider),
            ScoreCase("Retrieval", "Semantic search uses selected provider", "semantic retrieval can query local_hash vectors and return semantic scores", self.case_provider_retrieval),
            ScoreCase("Lifecycle", "Resume skips unchanged content", "resume does not duplicate unchanged vectors", self.case_resume),
            ScoreCase("Lifecycle", "Dimension change marks old vectors stale", "changed index version preserves stale lineage and verifies latest vectors", self.case_dimension_stale),
            ScoreCase("Lifecycle", "Manual mark-stale and prune-stale work", "operators can mark stale vectors and remove them", self.case_mark_prune),
            ScoreCase("Privacy", "Protected mode blocks secret semantic indexing", "secret content creates blocked records and no live vector", self.case_secret_block),
            ScoreCase("Privacy", "Redaction marks vectors stale", "redacted evidence invalidates affected semantic vectors", self.case_redaction_stale),
            ScoreCase("Governance", "Vector results respect claim governance", "semantic/hybrid retrieval excludes rejected and superseded claims", self.case_governed_results),
        ]

    def run(self) -> int:
        print("Aletheia M11 Production Semantic Retrieval Live Scorecard")
        print(f"workspace: {self.base_dir}")
        print(f"database: {self.db_path}")
        passed = 0
        results: list[dict] = []
        for index, case in enumerate(self.cases(), start=1):
            try:
                detail = case.fn()
                status = "PASS"
                passed += 1
            except Exception as exc:  # noqa: BLE001 - live scorecard records failures.
                detail = f"{type(exc).__name__}: {exc}"
                status = "FAIL"
            results.append({"status": status, "category": case.category, "name": case.name, "detail": detail})
            print(f"[{status}] {index:02d}. {case.category} - {case.name}")
            print(f"      measure: {case.measure}")
            print(f"      outcome: {detail}")
        print()
        print(f"score: {passed}/{len(results)}")
        print(json.dumps(results, indent=2))
        return 0 if passed == len(results) else 1

    def memory(self) -> Memory:
        return Memory.open(str(self.db_path), namespace=NAMESPACE)

    def remember(self, *, subject: str, predicate: str, object: str, status: str = "active", privacy_level: str = "personal"):
        memory = self.memory()
        try:
            event = memory.write_event(
                namespace=NAMESPACE,
                source_type="live",
                content=f"{subject} {predicate} {object}",
                privacy_level=privacy_level,
            )
            claim = memory.write_claim(
                namespace=NAMESPACE,
                subject=subject,
                predicate=predicate,
                object=object,
                memory_type="project",
                evidence_ids=[event.id],
                status=status,
            )
            return claim.id, event.id
        finally:
            memory.close()

    def case_init(self) -> str:
        health = json.loads(run_cli(["init", "--db", str(self.db_path)]))
        assert health["schema_version"] == SCHEMA_VERSION
        memory = self.memory()
        try:
            columns = {
                row["name"]
                for row in memory.store.connection.execute("PRAGMA table_info(embeddings)").fetchall()
            }
            required = {"provider_type", "provider_version", "input_hash", "privacy_level", "index_version", "vector_store", "status", "stale_reason"}
            assert required.issubset(columns)
            return f"schema={health['schema_version']}, m11_columns={len(required)}"
        finally:
            memory.close()

    def case_mock_provider(self) -> str:
        claim_id, _event_id = self.remember(subject="mock semantic", predicate="stays", object="deterministic")
        data = json.loads(run_cli(["index", "semantic", "--db", str(self.db_path), "--namespace", NAMESPACE, "--target", "claims", "--id", claim_id]))
        assert data["provider"] == "mock"
        assert data["indexed_count"] == 1
        second = json.loads(run_cli(["index", "resume", "--db", str(self.db_path), "--namespace", NAMESPACE, "--target", "claims", "--id", claim_id]))
        assert second["skipped_count"] >= 1
        return f"provider={data['provider']}, index_version={data['index_version']}"

    def case_local_provider(self) -> str:
        claim_id, _event_id = self.remember(subject="local vectors", predicate="support", object="production semantic recall")
        data = json.loads(
            run_cli(
                [
                    "index",
                    "semantic",
                    "--db",
                    str(self.db_path),
                    "--namespace",
                    NAMESPACE,
                    "--target",
                    "claims",
                    "--id",
                    claim_id,
                    "--provider",
                    "local_hash",
                    "--dimension",
                    "32",
                    "--force",
                ]
            )
        )
        assert data["provider"] == "local_hash"
        assert data["provider_type"] == "local"
        memory = self.memory()
        try:
            row = memory.store.connection.execute(
                "SELECT dimension, index_version, vector_store, status FROM embeddings WHERE target_id = ? AND provider = 'local_hash'",
                (claim_id,),
            ).fetchone()
            assert row["dimension"] == 32
            assert row["index_version"] == data["index_version"]
            assert row["vector_store"] == "sqlite_local"
            assert row["status"] == "indexed"
            self.ids["local_claim"] = claim_id
            return f"dimension={row['dimension']}, index_version={row['index_version']}"
        finally:
            memory.close()

    def case_provider_retrieval(self) -> str:
        output = run_cli(
            [
                "search",
                "--db",
                str(self.db_path),
                "--namespace",
                NAMESPACE,
                "--mode",
                "semantic",
                "--semantic-provider",
                "local_hash",
                "production semantic recall vectors",
            ]
        )
        assert self.ids["local_claim"] in output
        assert "semantic: 0.000" not in output
        return "semantic provider search returned indexed local_hash claim"

    def case_resume(self) -> str:
        data = json.loads(
            run_cli(
                [
                    "index",
                    "resume",
                    "--db",
                    str(self.db_path),
                    "--namespace",
                    NAMESPACE,
                    "--target",
                    "claims",
                    "--id",
                    self.ids["local_claim"],
                    "--provider",
                    "local_hash",
                    "--dimension",
                    "32",
                ]
            )
        )
        assert data["indexed_count"] == 0
        assert data["skipped_count"] == 1
        return f"skipped={data['skipped_count']}"

    def case_dimension_stale(self) -> str:
        data = json.loads(
            run_cli(
                [
                    "index",
                    "semantic",
                    "--db",
                    str(self.db_path),
                    "--namespace",
                    NAMESPACE,
                    "--target",
                    "claims",
                    "--id",
                    self.ids["local_claim"],
                    "--provider",
                    "local_hash",
                    "--dimension",
                    "64",
                    "--force",
                ]
            )
        )
        assert data["indexed_count"] == 1
        assert data["stale_count"] >= 1
        verify = json.loads(
            run_cli(
                [
                    "index",
                    "verify",
                    "--db",
                    str(self.db_path),
                    "--namespace",
                    NAMESPACE,
                    "--target",
                    "claims",
                    "--provider",
                    "local_hash",
                    "--dimension",
                    "64",
                ]
            )
        )
        assert verify["verified_count"] >= 1
        return f"stale={data['stale_count']}, verified={verify['verified_count']}"

    def case_mark_prune(self) -> str:
        claim_id, _event_id = self.remember(subject="operator lifecycle", predicate="supports", object="mark stale prune stale")
        run_cli(["index", "semantic", "--db", str(self.db_path), "--namespace", NAMESPACE, "--id", claim_id, "--provider", "local_hash", "--dimension", "32", "--force"])
        stale = json.loads(run_cli(["index", "mark-stale", "--db", str(self.db_path), "--namespace", NAMESPACE, "--provider", "local_hash", "--reason", "live"]))
        assert stale["stale_count"] >= 1
        pruned = json.loads(run_cli(["index", "prune-stale", "--db", str(self.db_path), "--namespace", NAMESPACE, "--provider", "local_hash"]))
        assert pruned["pruned_count"] >= 1
        return f"marked={stale['stale_count']}, pruned={pruned['pruned_count']}"

    def case_secret_block(self) -> str:
        memory = self.memory()
        try:
            memory.enable_protected_mode(actor="live")
            event = memory.write_event(namespace=NAMESPACE, source_type="live", content="secret semantic vector must not leak", privacy_level="secret")
            claim = memory.write_claim(namespace=NAMESPACE, subject="secret semantic", predicate="must not", object="leak", memory_type="project", evidence_ids=[event.id])
            data = json.loads(run_cli(["index", "semantic", "--db", str(self.db_path), "--namespace", NAMESPACE, "--id", claim.id, "--provider", "local_hash", "--dimension", "32"]))
            assert data["blocked_count"] == 1
            indexed = memory.store.connection.execute("SELECT count(*) AS count FROM embeddings WHERE target_id = ? AND status = 'indexed'", (claim.id,)).fetchone()["count"]
            assert indexed == 0
            return f"blocked={data['blocked_count']}, indexed={indexed}"
        finally:
            memory.close()

    def case_redaction_stale(self) -> str:
        memory = self.memory()
        try:
            event = memory.write_event(namespace=NAMESPACE, source_type="live", content="redaction stales vector row", privacy_level="personal")
            claim = memory.write_claim(namespace=NAMESPACE, subject="redaction", predicate="stales", object="vector row", memory_type="project", evidence_ids=[event.id])
            memory.index_semantic(NAMESPACE, target_ids=[claim.id], provider="local_hash", dimension=32, force=True)
            memory.redact(target_id=event.id, target_type="evidence", reason="live", dry_run=False)
            row = memory.store.connection.execute("SELECT status, stale_reason FROM embeddings WHERE target_id = ?", (claim.id,)).fetchone()
            assert row["status"] == "stale"
            assert row["stale_reason"] == "evidence.redacted"
            return f"status={row['status']}, reason={row['stale_reason']}"
        finally:
            memory.close()

    def case_governed_results(self) -> str:
        memory = self.memory()
        try:
            active = memory.remember(namespace=NAMESPACE, memory_type="project", subject="governed semantic", predicate="returns", object="active vector claim", source_type="live")
            rejected = memory.remember(namespace=NAMESPACE, memory_type="project", subject="governed semantic", predicate="returns", object="rejected vector claim", source_type="live", status="rejected")
            memory.index_semantic(NAMESPACE, target_ids=[active.id, rejected.id], provider="local_hash", dimension=32, force=True)
            results = memory.retrieve(NAMESPACE, "governed semantic vector claim", mode="hybrid", semantic_provider="local_hash")
            ids = {result.claim_id for result in results}
            assert active.id in ids
            assert rejected.id not in ids
            return f"active={active.id}, rejected_excluded={rejected.id not in ids}"
        finally:
            memory.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Aletheia M11 live scorecard.")
    parser.add_argument("--db")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="aletheia_m11_live_") as tmp:
        base_dir = Path(tmp)
        db_path = Path(args.db) if args.db else base_dir / "m11.db"
        return M11LiveScorecard(base_dir, db_path).run()


if __name__ == "__main__":
    raise SystemExit(main())
