from __future__ import annotations

import sys
import types

import pytest

import aletheia.core.memory as memory_core
from aletheia import Memory
from aletheia.core.errors import ValidationError
from aletheia.llm import provider_for_name


NAMESPACE = "user/default"


def test_llm_extractor_outputs_candidates_only_and_records_provenance(tmp_path):
    memory = Memory.open(str(tmp_path / "m12.db"), namespace=NAMESPACE)
    try:
        batch = memory.ingest(
            NAMESPACE,
            source_type="conversation",
            content="User prefers careful memory governance.",
        )

        run = memory.extract_candidates(NAMESPACE, batch_id=batch.id, extractor="llm")
        candidates = memory.list_candidates(NAMESPACE, extraction_run_id=run.id)
        llm_runs = memory.list_llm_runs(namespace=NAMESPACE, task_type="extract_candidates")

        assert run.extractor_name == "llm:mock_llm"
        assert run.candidate_count == 1
        assert memory.list_claims(namespace=NAMESPACE) == []
        assert candidates[0].candidate_status == "pending_review"
        assert candidates[0].metadata["llm_output"] is True
        assert candidates[0].metadata["provider"] == "mock_llm"
        assert candidates[0].metadata["extraction_prompt_id"] == "m12.extract_candidates"
        assert candidates[0].evidence_spans[0].evidence_id == batch.evidence_ids[0]
        assert llm_runs[0]["provider"] == "mock_llm"
        assert llm_runs[0]["status"] == "completed"
        detailed = memory.read_llm_run(llm_runs[0]["id"])
        assert detailed["outputs"][0]["target_id"] == candidates[0].id
    finally:
        memory.close()


def test_llm_invalid_schema_rejected_without_candidates(tmp_path, monkeypatch):
    class BadProvider:
        name = "bad_llm"
        provider_type = "mock_llm"
        model = "bad"
        provider_version = "test"
        external_network_access = False
        stores_data = "false"
        supports_no_log_mode = "true"

        def complete_json(self, **kwargs):
            return {
                "candidates": [
                    {
                        "subject": "user",
                        "predicate": "prefers",
                        "object": "strict schemas",
                        "memory_type": "preference",
                    }
                ]
            }

    monkeypatch.setattr("aletheia.extraction.llm_provider_for_name", lambda *args, **kwargs: BadProvider())
    memory = Memory.open(str(tmp_path / "m12.db"), namespace=NAMESPACE)
    try:
        event = memory.write_event(namespace=NAMESPACE, source_type="unit", content="User prefers strict schemas.")
        run = memory.extract_candidates(NAMESPACE, evidence_ids=[event.id], extractor="llm")

        assert run.candidate_count == 0
        assert memory.list_candidates(NAMESPACE, extraction_run_id=run.id) == []
        llm_run = memory.list_llm_runs(namespace=NAMESPACE, task_type="extract_candidates")[0]
        assert llm_run["status"] == "invalid_schema"
        assert "evidence_span" in llm_run["warnings"][0]
    finally:
        memory.close()


def test_llm_candidate_cannot_override_provenance_or_lower_privacy(tmp_path, monkeypatch):
    class SpoofingProvider:
        name = "spoofing_llm"
        provider_type = "mock_llm"
        model = "spoof"
        provider_version = "test"
        external_network_access = False
        stores_data = "false"
        supports_no_log_mode = "true"

        def complete_json(self, **kwargs):
            evidence = kwargs["metadata"]["evidence"][0]
            return {
                "candidates": [
                    {
                        "subject": "user",
                        "predicate": "prefers",
                        "object": "authoritative provenance",
                        "memory_type": "preference",
                        "evidence_span": {
                            "evidence_id": evidence["id"],
                            "start_char": 0,
                            "end_char": len(evidence["content"]),
                            "text": evidence["content"],
                        },
                        "privacy_level": "public",
                        "metadata": {
                            "provider": "attacker",
                            "extraction_prompt_id": "evil",
                            "llm_output": False,
                            "custom_note": "kept",
                        },
                    }
                ]
            }

    monkeypatch.setattr("aletheia.extraction.llm_provider_for_name", lambda *args, **kwargs: SpoofingProvider())
    memory = Memory.open(str(tmp_path / "m12.db"), namespace=NAMESPACE)
    try:
        event = memory.write_event(
            namespace=NAMESPACE,
            source_type="unit",
            content="User prefers authoritative provenance.",
            privacy_level="sensitive",
        )
        run = memory.extract_candidates(NAMESPACE, evidence_ids=[event.id], extractor="llm")
        candidate = memory.list_candidates(NAMESPACE, extraction_run_id=run.id)[0]

        assert candidate.privacy_level == "sensitive"
        assert candidate.metadata["provider"] == "spoofing_llm"
        assert candidate.metadata["extraction_prompt_id"] == "m12.extract_candidates"
        assert candidate.metadata["llm_output"] is True
        assert candidate.metadata["custom_note"] == "kept"
    finally:
        memory.close()


def test_llm_unsafe_span_or_confidence_is_rejected_before_candidate_storage(tmp_path, monkeypatch):
    class UnsafeProvider:
        name = "unsafe_llm"
        provider_type = "mock_llm"
        model = "unsafe"
        provider_version = "test"
        external_network_access = False
        stores_data = "false"
        supports_no_log_mode = "true"

        def complete_json(self, **kwargs):
            evidence = kwargs["metadata"]["evidence"][0]
            return {
                "candidates": [
                    {
                        "subject": "user",
                        "predicate": "prefers",
                        "object": "unsafe spans",
                        "memory_type": "preference",
                        "evidence_span": {
                            "evidence_id": evidence["id"],
                            "start_char": 0,
                            "end_char": len(evidence["content"]),
                            "text": "different text",
                        },
                        "suggested_confidence": 1.5,
                    }
                ]
            }

    monkeypatch.setattr("aletheia.extraction.llm_provider_for_name", lambda *args, **kwargs: UnsafeProvider())
    memory = Memory.open(str(tmp_path / "m12.db"), namespace=NAMESPACE)
    try:
        event = memory.write_event(namespace=NAMESPACE, source_type="unit", content="User prefers safe spans.")
        run = memory.extract_candidates(NAMESPACE, evidence_ids=[event.id], extractor="llm")

        assert run.candidate_count == 0
        assert memory.list_candidates(NAMESPACE, extraction_run_id=run.id) == []
        llm_run = memory.list_llm_runs(namespace=NAMESPACE, task_type="extract_candidates")[0]
        assert llm_run["status"] == "invalid_schema"
        assert "evidence_span" in llm_run["warnings"][0]
    finally:
        memory.close()


def test_external_llm_blocked_for_secret_and_sensitive_evidence_by_default(tmp_path, monkeypatch):
    calls = {"count": 0}

    class ExternalProvider:
        name = "external_llm"
        provider_type = "openai_compatible"
        model = "external"
        provider_version = "test"
        external_network_access = True
        stores_data = "unknown"
        supports_no_log_mode = "unknown"

        def complete_json(self, **kwargs):
            calls["count"] += 1
            return {"candidates": []}

    monkeypatch.setattr("aletheia.extraction.llm_provider_for_name", lambda *args, **kwargs: ExternalProvider())
    memory = Memory.open(str(tmp_path / "m12.db"), namespace=NAMESPACE)
    try:
        secret = memory.write_event(namespace=NAMESPACE, source_type="unit", content="secret thing", privacy_level="secret")
        sensitive = memory.write_event(namespace=NAMESPACE, source_type="unit", content="sensitive thing", privacy_level="sensitive")

        secret_run = memory.extract_candidates(NAMESPACE, evidence_ids=[secret.id], extractor="openai_compatible")
        sensitive_run = memory.extract_candidates(NAMESPACE, evidence_ids=[sensitive.id], extractor="openai_compatible")

        assert secret_run.candidate_count == 0
        assert sensitive_run.candidate_count == 0
        assert calls["count"] == 0
        runs = memory.list_llm_runs(namespace=NAMESPACE, task_type="extract_candidates", limit=10)
        assert {run["status"] for run in runs} == {"unsafe"}
        assert memory.read_llm_run(runs[0]["id"])["safety_flags"]
    finally:
        memory.close()


def test_llm_extractor_enforces_extraction_policy_before_candidate_storage(tmp_path, monkeypatch):
    class PolicyProvider:
        name = "policy_llm"
        provider_type = "mock_llm"
        model = "policy"
        provider_version = "test"
        external_network_access = False
        stores_data = "false"
        supports_no_log_mode = "true"

        def complete_json(self, **kwargs):
            return {
                "candidates": [
                    {
                        "subject": "user",
                        "predicate": "prefers",
                        "object": "short answers",
                        "memory_type": "preference",
                        "evidence_span": {
                            "evidence_id": kwargs["metadata"]["evidence"][0]["id"],
                            "start_char": 0,
                            "end_char": len("User prefers short answers."),
                            "text": "User prefers short answers.",
                        },
                        "suggested_confidence": 0.95,
                    }
                ]
            }

    monkeypatch.setattr("aletheia.extraction.llm_provider_for_name", lambda *args, **kwargs: PolicyProvider())
    memory = Memory.open(str(tmp_path / "m12.db"), namespace=NAMESPACE)
    try:
        event = memory.write_event(namespace=NAMESPACE, source_type="unit", content="User prefers short answers.")
        run = memory.extract_candidates(
            NAMESPACE,
            evidence_ids=[event.id],
            extractor="llm",
            extraction_policy={"allowed_memory_types": ["project"]},
        )

        assert run.candidate_count == 0
        assert memory.list_candidates(NAMESPACE, extraction_run_id=run.id) == []
        assert any("not allowed" in warning for warning in run.warnings)
        llm_run = memory.list_llm_runs(namespace=NAMESPACE, task_type="extract_candidates")[0]
        assert any("not allowed" in warning for warning in llm_run["warnings"])
    finally:
        memory.close()


def test_query_expansion_does_not_create_memory(tmp_path):
    memory = Memory.open(str(tmp_path / "m12.db"), namespace=NAMESPACE)
    try:
        expanded = memory.expand_query(namespace=NAMESPACE, query="what should I recall about semantic memory?")

        assert expanded["original_query"] == "what should I recall about semantic memory?"
        assert "retrieval" in expanded["expanded_terms"]
        assert memory.list_claims(namespace=NAMESPACE) == []
        assert memory.list_candidates(NAMESPACE) == []
        run = memory.read_llm_run(expanded["llm_run_id"])
        assert run["task_type"] == "expand_query"
        assert run["outputs"][0]["output_type"] == "query_expansion"
    finally:
        memory.close()


def test_external_query_expansion_blocks_sensitive_input_by_policy(tmp_path, monkeypatch):
    calls = {"count": 0}

    class ExternalProvider:
        name = "external_llm"
        provider_type = "openai_compatible"
        model = "external"
        provider_version = "test"
        external_network_access = True
        stores_data = "unknown"
        supports_no_log_mode = "unknown"

        def complete_json(self, **kwargs):
            calls["count"] += 1
            return {"original_query": "sensitive", "expanded_terms": []}

    monkeypatch.setattr(memory_core, "llm_provider_for_name", lambda *args, **kwargs: ExternalProvider())
    memory = Memory.open(str(tmp_path / "m12.db"), namespace=NAMESPACE)
    try:
        with pytest.raises(ValidationError):
            memory.expand_query(
                namespace=NAMESPACE,
                query="sensitive project recall",
                provider="openai_compatible",
                privacy_level="sensitive",
            )

        assert calls["count"] == 0
        run = memory.list_llm_runs(namespace=NAMESPACE, task_type="expand_query")[0]
        detail = memory.read_llm_run(run["id"])
        assert run["status"] == "unsafe"
        assert detail["safety_flags"][0]["risk_type"] == "privacy_policy"
    finally:
        memory.close()


def test_summary_preserves_source_backlinks_and_is_draft_only(tmp_path):
    memory = Memory.open(str(tmp_path / "m12.db"), namespace=NAMESPACE)
    try:
        event = memory.write_event(
            namespace=NAMESPACE,
            source_type="unit",
            content="Aletheia M12 should keep LLM summaries as drafts.",
        )

        summary = memory.summarize_evidence(namespace=NAMESPACE, evidence_ids=[event.id])

        assert summary["status"] == "pending_review"
        assert event.id in summary["source_evidence_ids"]
        assert "drafts" in summary["summary"]
        assert memory.list_claims(namespace=NAMESPACE) == []
        run = memory.read_llm_run(summary["llm_run_id"])
        metadata = run["outputs"][0]["metadata"]
        assert metadata["storage_mode"] == "metadata_only"
        assert "summary" not in metadata
        assert "output_hash" in metadata
    finally:
        memory.close()


def test_llm_suggestion_tasks_are_review_only_and_record_provenance(tmp_path):
    memory = Memory.open(str(tmp_path / "m12.db"), namespace=NAMESPACE)
    try:
        batch = memory.ingest(
            NAMESPACE,
            source_type="unit",
            content="Aletheia M12 privacy policy should keep suggestions review-only.",
        )
        run = memory.extract_candidates(NAMESPACE, batch_id=batch.id, extractor="llm")
        candidate = memory.list_candidates(NAMESPACE, extraction_run_id=run.id)[0]

        entities = memory.suggest_entities(namespace=NAMESPACE, evidence_ids=batch.evidence_ids)
        categories = memory.suggest_categories(namespace=NAMESPACE, evidence_ids=batch.evidence_ids)
        scope = memory.suggest_scope_with_llm(namespace=NAMESPACE, candidate_id=candidate.id)
        merge = memory.suggest_duplicate_merge_with_llm(namespace=NAMESPACE, candidate_id=candidate.id)

        assert entities["review_state"] == "pending_review"
        assert "Aletheia" in [entity["name"] for entity in entities["entities"]]
        assert categories["review_state"] == "pending_review"
        assert "governance" in categories["categories"]
        assert scope["candidate_id"] == candidate.id
        assert scope["review_state"] == "pending_review"
        assert merge["candidate_id"] == candidate.id
        assert merge["review_state"] == "pending_review"
        assert memory.list_claims(namespace=NAMESPACE) == []
        tasks = {run["task_type"] for run in memory.list_llm_runs(namespace=NAMESPACE, limit=20)}
        assert {"suggest_entities", "suggest_categories", "suggest_scope", "suggest_duplicate_merge"} <= tasks
    finally:
        memory.close()


def test_plugin_llm_provider_entrypoint_loads_local_provider(monkeypatch):
    module = types.ModuleType("test_m12_plugin_llm")

    class Provider:
        name = "plugin_unit"
        model = "plugin-test"
        external_network_access = False
        stores_data = "false"
        supports_no_log_mode = "true"

        def complete_json(self, **kwargs):
            return {"original_query": "plugin", "expanded_terms": ["plugin", "provider"]}

    module.Provider = Provider
    monkeypatch.setitem(sys.modules, "test_m12_plugin_llm", module)

    provider = provider_for_name("plugin:test_m12_plugin_llm:Provider")
    output = provider.complete_json(messages=[], schema={}, temperature=0.0, max_tokens=None)

    assert provider.provider_type == "plugin"
    assert provider.name == "plugin_unit"
    assert output["expanded_terms"] == ["plugin", "provider"]


def test_reflection_draft_requires_review(tmp_path):
    memory = Memory.open(str(tmp_path / "m12.db"), namespace=NAMESPACE)
    try:
        claim = memory.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="m12",
            predicate="requires",
            object="reviewed reflection drafts",
            source_type="unit",
        )

        reflection = memory.draft_reflection_with_llm(
            namespace=NAMESPACE,
            source_claim_ids=[claim.id],
            title="M12 reflection",
        )

        assert reflection.status == "candidate"
        assert reflection.builder == "llm"
        assert claim.id in reflection.source_claim_ids
    finally:
        memory.close()


def test_llm_conflict_explanation_does_not_resolve_conflict(tmp_path):
    memory = Memory.open(str(tmp_path / "m12.db"), namespace=NAMESPACE)
    try:
        first = memory.remember(
            namespace=NAMESPACE,
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="brief",
            source_type="unit",
        )
        second = memory.remember(
            namespace=NAMESPACE,
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="detailed",
            source_type="unit",
        )
        conflict = memory.list_conflicts(namespace=NAMESPACE)[0]

        explanation = memory.explain_conflict_with_llm(conflict.id)

        assert explanation["resolves_conflict"] is False
        assert memory.read_conflict(conflict.id).status == "unresolved"
        assert set(memory.read_conflict(conflict.id).claim_ids) == {first.id, second.id}
        run = memory.read_llm_run(explanation["llm_run_id"])
        assert run["outputs"][0]["target_id"] == conflict.id
    finally:
        memory.close()


def test_external_llm_conflict_explanation_checks_source_evidence_privacy(tmp_path, monkeypatch):
    calls = {"count": 0}

    class ExternalProvider:
        name = "external_llm"
        provider_type = "openai_compatible"
        model = "external"
        provider_version = "test"
        external_network_access = True
        stores_data = "unknown"
        supports_no_log_mode = "unknown"

        def complete_json(self, **kwargs):
            calls["count"] += 1
            return {"explanation": "unsafe", "resolves_conflict": False}

    monkeypatch.setattr(memory_core, "llm_provider_for_name", lambda *args, **kwargs: ExternalProvider())
    memory = Memory.open(str(tmp_path / "m12.db"), namespace=NAMESPACE)
    try:
        first_evidence = memory.write_event(
            namespace=NAMESPACE,
            source_type="unit",
            content="User prefers concise responses.",
            privacy_level="sensitive",
        )
        second_evidence = memory.write_event(
            namespace=NAMESPACE,
            source_type="unit",
            content="User prefers detailed responses.",
            privacy_level="personal",
        )
        memory.write_claim(
            namespace=NAMESPACE,
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="concise",
            evidence_ids=[first_evidence.id],
        )
        memory.write_claim(
            namespace=NAMESPACE,
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="detailed",
            evidence_ids=[second_evidence.id],
        )
        conflict = memory.list_conflicts(namespace=NAMESPACE)[0]

        with pytest.raises(ValidationError):
            memory.explain_conflict_with_llm(conflict.id, provider="openai_compatible")

        assert calls["count"] == 0
        run = memory.list_llm_runs(namespace=NAMESPACE, task_type="safety_block")[0]
        detail = memory.read_llm_run(run["id"])
        assert run["status"] == "unsafe"
        assert detail["safety_flags"]
        assert detail["safety_flags"][0]["evidence_id"] == first_evidence.id
    finally:
        memory.close()
