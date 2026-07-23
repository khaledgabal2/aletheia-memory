from __future__ import annotations

from aletheia import Memory


def test_health_remember_retrieve_and_audit(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        assert memory.health()["schema_version"] == "1.3.0"
        claim = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="practical and direct",
            confidence=0.9,
            importance=0.8,
        )

        assert claim.evidence_ids
        results = memory.retrieve(
            namespace="user/default",
            query="response style",
        )

        assert results[0].claim_id == claim.id
        assert "practical and direct" in results[0].text

        audit = memory.audit(claim.id)
        assert audit["claim"]["id"] == claim.id
        assert audit["evidence"][0]["id"] == claim.evidence_ids[0]
        assert any(entry["action"] == "claim.write" for entry in audit["audit"])
    finally:
        memory.close()


def test_conflict_detection_and_resolution(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        first = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="practical and direct",
            confidence=0.9,
            importance=0.8,
        )
        second = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="long and highly detailed",
            confidence=0.8,
        )

        conflicts = memory.list_conflicts(namespace="user/default")
        assert len(conflicts) == 1
        assert set(conflicts[0].claim_ids) == {first.id, second.id}
        assert memory.read_claim(first.id).status == "disputed"
        assert memory.read_claim(second.id).status == "disputed"

        resolved = memory.resolve_conflict(
            conflict_id=conflicts[0].id,
            active_claim_id=second.id,
            note="Use the newer explicit preference.",
        )

        assert resolved.status == "resolved"
        assert memory.read_claim(second.id).status == "active"
        assert memory.read_claim(first.id).status == "superseded"
    finally:
        memory.close()


def test_core_claim_stays_retrievable_when_contradicted(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        core = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="practical and direct",
            confidence=0.95,
            importance=0.9,
            status="core",
        )
        incoming = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="long and highly detailed",
            confidence=0.8,
        )

        conflicts = memory.list_conflicts(namespace="user/default")
        assert len(conflicts) == 1
        assert set(conflicts[0].claim_ids) == {core.id, incoming.id}
        assert memory.read_claim(core.id).status == "core"
        assert memory.read_claim(incoming.id).status == "disputed"

        results = memory.retrieve(namespace="user/default", query="response style", limit=5)
        assert any(result.claim_id == core.id for result in results)
        assert all(result.claim_id != incoming.id for result in results)
    finally:
        memory.close()


def test_context_pack_groups_memory(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        preference = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="practical and direct",
            confidence=0.9,
            importance=0.8,
        )
        memory.promote_claim(preference.id, "core", reason="Stable preference.")
        memory.remember(
            namespace="user/default",
            memory_type="project",
            subject="project",
            predicate="has_name",
            object="Aletheia Memory Library",
            confidence=0.85,
        )

        pack = memory.context_pack(
            namespace="user/default",
            query="Aletheia response style",
        )

        assert any("practical and direct" in item for item in pack.core_memory)
        assert any("Aletheia Memory Library" in item for item in pack.project_memory)
        assert pack.sources
    finally:
        memory.close()


def test_feedback_updates_confidence_and_status(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        claim = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="practical and direct",
            confidence=0.5,
        )

        memory.feedback(
            namespace="user/default",
            target_id=claim.id,
            signal="confirmed",
            note="User explicitly confirmed it.",
        )
        confirmed = memory.read_claim(claim.id)
        assert confirmed.confidence_base > claim.confidence_base
        assert confirmed.last_verified_at is not None

        memory.feedback(
            namespace="user/default",
            target_id=claim.id,
            signal="wrong",
            note="User rejected this memory.",
        )
        rejected = memory.read_claim(claim.id)
        assert rejected.status == "rejected"
        assert rejected.confidence_base < confirmed.confidence_base
    finally:
        memory.close()


def test_migrations_are_idempotent_and_create_mvp_tables(tmp_path):
    db_path = str(tmp_path / "aletheia.db")
    memory = Memory.open(db_path)
    memory.close()

    memory = Memory.open(db_path)
    try:
        assert memory.health()["schema_version"] == "1.3.0"
        rows = memory.store.connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type IN ('table', 'virtual table')
            """
        ).fetchall()
        names = {row["name"] for row in rows}
        assert {
            "schema_version",
            "evidence_events",
            "claims",
            "claim_evidence_links",
            "audit_log",
            "conflicts",
            "conflict_claim_links",
            "feedback",
            "sessions",
            "projects",
            "project_claim_links",
            "session_claim_links",
            "retrieval_log",
            "context_pack_log",
            "confidence_events",
            "confidence_snapshots",
            "half_life_policies",
            "claim_relationships",
            "claim_status_history",
            "conflict_families",
            "conflict_family_claims",
            "conflict_resolutions",
            "claim_scopes",
            "curation_decisions",
            "curation_queue",
            "claims_fts",
        }.issubset(names)
    finally:
        memory.close()
