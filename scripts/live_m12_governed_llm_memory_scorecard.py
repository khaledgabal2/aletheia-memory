#!/usr/bin/env python3
"""Run live M12 governed LLM memory formation scorecard checks."""

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

import aletheia.extraction as extraction
import aletheia.core.memory as memory_core
from aletheia import Memory
from aletheia.cli.main import main as cli_main
from aletheia.core.errors import ValidationError
from aletheia.storage import SCHEMA_VERSION


NAMESPACE = "live/m12"


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


class M12LiveScorecard:
    def __init__(self, base_dir: Path, db_path: Path):
        self.base_dir = base_dir
        self.db_path = db_path
        self.ids: dict[str, str] = {}

    def memory(self) -> Memory:
        return Memory.open(str(self.db_path), namespace=NAMESPACE)

    def cases(self) -> list[ScoreCase]:
        return [
            ScoreCase("Setup", "Schema and M12 tables initialize", "schema version and LLM provenance tables are present", self.case_init),
            ScoreCase("Extraction", "LLM extraction creates candidates only", "LLM output stores pending candidates, not active claims", self.case_llm_extract),
            ScoreCase("Policy", "LLM extraction obeys candidate policy", "disallowed LLM candidate types are rejected before storage", self.case_policy_filter),
            ScoreCase("Provenance", "Prompt/run/output provenance is inspectable", "llm_runs, prompts, outputs, and candidate metadata link together", self.case_provenance),
            ScoreCase("Persistence", "LLM output storage is metadata-only by default", "stored llm_outputs keep hashes and keys, not full draft text", self.case_metadata_only_output),
            ScoreCase("Privacy", "External LLM is blocked for secret/sensitive inputs", "provider is not called for extraction, query expansion, or conflict explanation and safety flags are recorded", self.case_privacy_block),
            ScoreCase("Query", "Query expansion is non-mutating", "expanded terms are returned without creating memory", self.case_expand_query),
            ScoreCase("Suggestions", "LLM suggestion task surfaces are review-only", "entity/category/scope/merge suggestions record provenance and create no claims", self.case_suggestions),
            ScoreCase("Summary", "Evidence summary is draft-only with backlinks", "summary preserves source evidence ids and creates no claims", self.case_summary),
            ScoreCase("Reflection", "Reflection draft requires review", "LLM reflection is stored as candidate reflection with source links", self.case_reflection),
            ScoreCase("Conflict", "Conflict explanation does not resolve conflict", "explanation records output but leaves conflict unresolved", self.case_conflict),
            ScoreCase("CLI", "LLM run listing and show work", "CLI can inspect M12 provenance records", self.case_cli_runs),
            ScoreCase("Completeness", "Conformance and regression smoke", "LLM governance conformance passes and local recall still works", self.case_completeness),
        ]

    def run(self) -> int:
        print("Aletheia M12 Governed LLM Memory Formation Live Scorecard")
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

    def case_init(self) -> str:
        health = json.loads(run_cli(["init", "--db", str(self.db_path)]))
        assert health["schema_version"] == SCHEMA_VERSION
        memory = self.memory()
        try:
            tables = {row["name"] for row in memory.store.connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
            required = {"llm_prompts", "llm_prompt_versions", "llm_runs", "llm_outputs", "llm_safety_flags"}
            assert required.issubset(tables)
            return f"schema={health['schema_version']}, llm_tables={len(required)}"
        finally:
            memory.close()

    def case_llm_extract(self) -> str:
        memory = self.memory()
        try:
            batch = memory.ingest(NAMESPACE, source_type="live", content="User prefers governed LLM candidate review.")
            self.ids["batch"] = batch.id
            output = run_cli(["extract", "run", "--db", str(self.db_path), "--namespace", NAMESPACE, "--batch", batch.id, "--extractor", "llm"])
            assert "extractor: llm:mock_llm" in output
            candidates = memory.list_candidates(NAMESPACE, status="pending_review")
            assert candidates
            assert memory.list_claims(namespace=NAMESPACE) == []
            self.ids["candidate"] = candidates[0].id
            return f"candidate={candidates[0].id}, claims=0"
        finally:
            memory.close()

    def case_policy_filter(self) -> str:
        class PolicyProvider:
            name = "live_policy"
            provider_type = "mock_llm"
            model = "live"
            provider_version = "test"
            external_network_access = False
            stores_data = "false"
            supports_no_log_mode = "true"

            def complete_json(self, **kwargs):
                evidence = kwargs["metadata"]["evidence"][0]
                text = "User prefers policy filtered output."
                return {
                    "candidates": [
                        {
                            "subject": "user",
                            "predicate": "prefers",
                            "object": "policy filtered output",
                            "memory_type": "preference",
                            "evidence_span": {
                                "evidence_id": evidence["id"],
                                "start_char": 0,
                                "end_char": len(text),
                                "text": text,
                            },
                            "suggested_confidence": 0.90,
                        }
                    ]
                }

        original = extraction.llm_provider_for_name
        extraction.llm_provider_for_name = lambda *args, **kwargs: PolicyProvider()
        memory = self.memory()
        try:
            event = memory.write_event(namespace=NAMESPACE, source_type="live", content="User prefers policy filtered output.")
            run = memory.extract_candidates(
                NAMESPACE,
                evidence_ids=[event.id],
                extractor="llm",
                extraction_policy={"allowed_memory_types": ["project"]},
            )
            assert run.candidate_count == 0
            assert any("not allowed" in warning for warning in run.warnings)
            return f"filtered={len(run.warnings)}, candidates={run.candidate_count}"
        finally:
            extraction.llm_provider_for_name = original
            memory.close()

    def case_provenance(self) -> str:
        memory = self.memory()
        try:
            candidate = memory.read_candidate(self.ids["candidate"])
            llm_run_id = candidate.metadata["llm_run_id"]
            run = memory.read_llm_run(llm_run_id)
            assert run["prompt_template_id"] == "m12.extract_candidates"
            assert run["outputs"][0]["target_id"] == candidate.id
            assert run["input_evidence_ids"]
            return f"llm_run={llm_run_id}, outputs={len(run['outputs'])}"
        finally:
            memory.close()

    def case_metadata_only_output(self) -> str:
        memory = self.memory()
        try:
            event = memory.write_event(namespace=NAMESPACE, source_type="live", content="M12 output persistence should stay metadata only.")
            summary = memory.summarize_evidence(namespace=NAMESPACE, evidence_ids=[event.id])
            run = memory.read_llm_run(summary["llm_run_id"])
            metadata = run["outputs"][0]["metadata"]
            assert metadata["storage_mode"] == "metadata_only"
            assert "summary" not in metadata
            assert "output_hash" in metadata
            return f"storage={metadata['storage_mode']}, keys={len(metadata['output_keys'])}"
        finally:
            memory.close()

    def case_privacy_block(self) -> str:
        calls = {"count": 0}

        class ExternalProvider:
            name = "live_external"
            provider_type = "openai_compatible"
            model = "live"
            provider_version = "test"
            external_network_access = True
            stores_data = "unknown"
            supports_no_log_mode = "unknown"

            def complete_json(self, **kwargs):
                calls["count"] += 1
                return {"candidates": []}

        original = extraction.llm_provider_for_name
        original_core = memory_core.llm_provider_for_name
        extraction.llm_provider_for_name = lambda *args, **kwargs: ExternalProvider()
        memory_core.llm_provider_for_name = lambda *args, **kwargs: ExternalProvider()
        memory = self.memory()
        try:
            secret = memory.write_event(namespace=NAMESPACE, source_type="live", content="secret LLM block", privacy_level="secret")
            sensitive = memory.write_event(namespace=NAMESPACE, source_type="live", content="sensitive LLM block", privacy_level="sensitive")
            memory.extract_candidates(NAMESPACE, evidence_ids=[secret.id], extractor="openai_compatible")
            memory.extract_candidates(NAMESPACE, evidence_ids=[sensitive.id], extractor="openai_compatible")
            first_claim = memory.write_claim(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user",
                predicate="prefers_response_style",
                object="brief",
                evidence_ids=[sensitive.id],
            )
            second_event = memory.write_event(namespace=NAMESPACE, source_type="live", content="personal conflict source", privacy_level="personal")
            second_claim = memory.write_claim(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user",
                predicate="prefers_response_style",
                object="detailed",
                evidence_ids=[second_event.id],
            )
            conflict = memory.list_conflicts(namespace=NAMESPACE)[0]
            assert set(memory.read_conflict(conflict.id).claim_ids) == {first_claim.id, second_claim.id}
            try:
                memory.explain_conflict_with_llm(conflict.id, provider="openai_compatible")
                raise AssertionError("external conflict explanation should be blocked")
            except ValidationError:
                pass
            try:
                memory.expand_query(
                    namespace=NAMESPACE,
                    query="sensitive live query expansion",
                    provider="openai_compatible",
                    privacy_level="sensitive",
                )
                raise AssertionError("external query expansion should be blocked")
            except ValidationError:
                pass
            assert calls["count"] == 0
            runs = memory.list_llm_runs(namespace=NAMESPACE, limit=20)
            unsafe = [run for run in runs if run["status"] == "unsafe"]
            assert len(unsafe) >= 4
            flags = sum(len(memory.read_llm_run(run["id"])["safety_flags"]) for run in unsafe)
            assert flags >= 4
            return f"blocked_runs={len(unsafe)}, provider_calls={calls['count']}, flags={flags}"
        finally:
            extraction.llm_provider_for_name = original
            memory_core.llm_provider_for_name = original_core
            memory.close()

    def case_expand_query(self) -> str:
        output = json.loads(run_cli(["llm", "expand-query", "--db", str(self.db_path), "--namespace", NAMESPACE, "semantic memory privacy recall"]))
        assert "retrieval" in output["expanded_terms"]
        memory = self.memory()
        try:
            assert len(memory.list_candidates(NAMESPACE)) >= 1
            assert not any(claim.object == "semantic memory privacy recall" for claim in memory.list_claims(namespace=NAMESPACE))
            self.ids["expand_run"] = output["llm_run_id"]
            return f"llm_run={output['llm_run_id']}, terms={len(output['expanded_terms'])}"
        finally:
            memory.close()

    def case_suggestions(self) -> str:
        memory = self.memory()
        try:
            batch = memory.ingest(NAMESPACE, source_type="live", content="Aletheia M12 privacy policy suggests review-only categorization.")
            run = memory.extract_candidates(NAMESPACE, batch_id=batch.id, extractor="llm")
            candidate = memory.list_candidates(NAMESPACE, extraction_run_id=run.id)[0]
            entities = memory.suggest_entities(namespace=NAMESPACE, evidence_ids=batch.evidence_ids)
            categories = memory.suggest_categories(namespace=NAMESPACE, evidence_ids=batch.evidence_ids)
            scope = memory.suggest_scope_with_llm(namespace=NAMESPACE, candidate_id=candidate.id)
            merge = memory.suggest_duplicate_merge_with_llm(namespace=NAMESPACE, candidate_id=candidate.id)
            assert entities["review_state"] == "pending_review"
            assert categories["review_state"] == "pending_review"
            assert scope["review_state"] == "pending_review"
            assert merge["review_state"] == "pending_review"
            assert not any(claim.object == "review-only categorization" for claim in memory.list_claims(namespace=NAMESPACE))
            return f"entities={len(entities['entities'])}, categories={len(categories['categories'])}, candidate={candidate.id}"
        finally:
            memory.close()

    def case_summary(self) -> str:
        memory = self.memory()
        try:
            event = memory.write_event(namespace=NAMESPACE, source_type="live", content="M12 summaries must remain draft outputs.")
            summary = memory.summarize_evidence(namespace=NAMESPACE, evidence_ids=[event.id])
            assert event.id in summary["source_evidence_ids"]
            assert summary["status"] == "pending_review"
            self.ids["summary_event"] = event.id
            return f"summary_run={summary['llm_run_id']}, source={event.id}"
        finally:
            memory.close()

    def case_reflection(self) -> str:
        memory = self.memory()
        try:
            claim = memory.remember(namespace=NAMESPACE, memory_type="project", subject="m12", predicate="keeps", object="reflection drafts reviewable", source_type="live")
            reflection = memory.draft_reflection_with_llm(namespace=NAMESPACE, source_claim_ids=[claim.id], title="M12 review reflection")
            assert reflection.status == "candidate"
            assert reflection.builder == "llm"
            assert claim.id in reflection.source_claim_ids
            return f"reflection={reflection.id}, status={reflection.status}"
        finally:
            memory.close()

    def case_conflict(self) -> str:
        memory = self.memory()
        try:
            first = memory.remember(namespace=NAMESPACE, memory_type="project", subject="m12_live_conflict", predicate="chooses_review_mode", object="brief", source_type="live")
            second = memory.remember(namespace=NAMESPACE, memory_type="project", subject="m12_live_conflict", predicate="chooses_review_mode", object="detailed", source_type="live")
            expected_claims = {first.id, second.id}
            conflict = next(
                conflict
                for conflict in memory.list_conflicts(namespace=NAMESPACE)
                if set(conflict.claim_ids) == expected_claims
            )
            explanation = memory.explain_conflict_with_llm(conflict.id)
            assert explanation["resolves_conflict"] is False
            assert memory.read_conflict(conflict.id).status == "unresolved"
            assert set(memory.read_conflict(conflict.id).claim_ids) == expected_claims
            return f"conflict={conflict.id}, llm_run={explanation['llm_run_id']}"
        finally:
            memory.close()

    def case_cli_runs(self) -> str:
        runs = json.loads(run_cli(["llm", "runs", "--db", str(self.db_path), "--namespace", NAMESPACE]))
        assert runs
        shown = json.loads(run_cli(["llm", "show", "--db", str(self.db_path), runs[0]["id"]]))
        assert "outputs" in shown
        return f"runs={len(runs)}, shown={shown['id']}"

    def case_completeness(self) -> str:
        memory = self.memory()
        try:
            suites = [suite.name for suite in memory.list_conformance_suites()]
            assert "llm-governance" in suites
            run = memory.run_conformance(suite="llm-governance")
            assert run.status == "passed"
            claim = memory.remember(namespace=NAMESPACE, memory_type="fact", subject="local recall", predicate="survives", object="m12", source_type="live")
            results = memory.retrieve(NAMESPACE, "local recall m12", mode="lexical")
            assert results[0].claim_id == claim.id
            return f"conformance={run.status}, recall={claim.id}"
        finally:
            memory.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Aletheia M12 live scorecard.")
    parser.add_argument("--db")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="aletheia_m12_live_") as tmp:
        base_dir = Path(tmp)
        db_path = Path(args.db) if args.db else base_dir / "m12.db"
        return M12LiveScorecard(base_dir, db_path).run()


if __name__ == "__main__":
    raise SystemExit(main())
