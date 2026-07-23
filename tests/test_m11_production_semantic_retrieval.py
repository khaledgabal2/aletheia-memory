from __future__ import annotations

import json

from aletheia import Memory


NAMESPACE = "user/default"


def _remember(memory: Memory, *, subject: str, predicate: str, object: str, privacy_level: str = "personal"):
    event = memory.write_event(
        namespace=NAMESPACE,
        source_type="unit",
        content=f"{subject} {predicate} {object}",
        privacy_level=privacy_level,
    )
    return memory.write_claim(
        namespace=NAMESPACE,
        subject=subject,
        predicate=predicate,
        object=object,
        memory_type="project",
        evidence_ids=[event.id],
    )


def test_local_embedding_provider_records_lineage_and_retrieves_with_provider(tmp_path):
    memory = Memory.open(str(tmp_path / "m11.db"), namespace=NAMESPACE)
    try:
        target = _remember(
            memory,
            subject="semantic retrieval",
            predicate="uses",
            object="local hash vectors",
        )
        _remember(
            memory,
            subject="backup exports",
            predicate="use",
            object="encrypted archives",
        )

        run = memory.index_semantic(
            NAMESPACE,
            target_type="claims",
            provider="local_hash",
            dimension=32,
            force=True,
        )

        assert run.provider == "local_hash"
        assert run.provider_type == "local"
        assert run.vector_store == "sqlite_local"
        assert run.index_version
        assert run.indexed_count == 2

        row = memory.store.connection.execute(
            """
            SELECT provider_type, dimension, privacy_level, index_version, vector_store, status, metadata_json
            FROM embeddings
            WHERE target_id = ?
            """,
            (target.id,),
        ).fetchone()
        assert row["provider_type"] == "local"
        assert row["dimension"] == 32
        assert row["privacy_level"] == "personal"
        assert row["index_version"] == run.index_version
        assert row["vector_store"] == "sqlite_local"
        assert row["status"] == "indexed"
        assert json.loads(row["metadata_json"])["protected_mode_policy"] == "index_public_and_personal_only"

        results = memory.retrieve(
            NAMESPACE,
            "semantic vector retrieval",
            mode="semantic",
            semantic_provider="local_hash",
        )
        assert results[0].claim_id == target.id
        assert results[0].semantic_score > 0
    finally:
        memory.close()


def test_semantic_reindex_resume_and_dimension_change_marks_stale(tmp_path):
    memory = Memory.open(str(tmp_path / "m11.db"), namespace=NAMESPACE)
    try:
        _remember(memory, subject="m11", predicate="supports", object="semantic reindex resume")

        first = memory.index_semantic(NAMESPACE, provider="local_hash", dimension=32, force=True)
        resumed = memory.index_semantic(NAMESPACE, provider="local_hash", dimension=32)
        changed = memory.index_semantic(NAMESPACE, provider="local_hash", dimension=64, force=True)

        assert first.indexed_count == 1
        assert resumed.indexed_count == 0
        assert resumed.skipped_count == 1
        assert changed.indexed_count == 1
        assert changed.stale_count == 1
        assert changed.index_version != first.index_version

        rows = memory.store.connection.execute(
            "SELECT status, dimension FROM embeddings ORDER BY created_at ASC"
        ).fetchall()
        assert [(row["status"], row["dimension"]) for row in rows] == [
            ("stale", 32),
            ("indexed", 64),
        ]
    finally:
        memory.close()


def test_semantic_status_verify_mark_stale_and_prune(tmp_path):
    memory = Memory.open(str(tmp_path / "m11.db"), namespace=NAMESPACE)
    try:
        _remember(memory, subject="semantic index", predicate="has", object="operational lifecycle")
        memory.index_semantic(NAMESPACE, provider="local_hash", dimension=32, force=True)

        status = memory.semantic_index_status(NAMESPACE, target_type="claims")
        assert status["embeddings"][0]["status"] == "indexed"

        verified = memory.verify_semantic_index(NAMESPACE, provider="local_hash", dimension=32)
        assert verified.verified_count == 1
        assert verified.stale_count == 0

        stale = memory.mark_stale_semantic_index(NAMESPACE, provider="local_hash", reason="unit")
        assert stale.stale_count == 1
        pruned = memory.prune_stale_semantic_index(NAMESPACE, provider="local_hash")
        assert pruned.pruned_count == 1

        remaining = memory.store.connection.execute(
            "SELECT count(*) AS count FROM embeddings WHERE namespace = ?",
            (NAMESPACE,),
        ).fetchone()["count"]
        assert remaining == 0
    finally:
        memory.close()


def test_protected_mode_blocks_secret_semantic_indexing_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("ALETHEIA_PROTECTED_KEY", "m11-test-protected-key")
    memory = Memory.open(str(tmp_path / "m11.db"), namespace=NAMESPACE)
    try:
        memory.enable_protected_mode(actor="pytest")
        secret = _remember(
            memory,
            subject="launch",
            predicate="has secret code",
            object="blue",
            privacy_level="secret",
        )

        run = memory.index_semantic(NAMESPACE, provider="local_hash", dimension=32)

        assert run.indexed_count == 0
        assert run.blocked_count == 1
        assert "blocked" in run.warnings[0]
        indexed = memory.store.connection.execute(
            "SELECT count(*) AS count FROM embeddings WHERE target_id = ?",
            (secret.id,),
        ).fetchone()["count"]
        record = memory.store.connection.execute(
            "SELECT status, stale_reason FROM semantic_index_records WHERE target_id = ?",
            (secret.id,),
        ).fetchone()
        assert indexed == 0
        assert record["status"] == "blocked"
        assert record["stale_reason"] == "privacy_level_blocked"
    finally:
        memory.close()


def test_external_provider_not_called_for_secret_content_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("ALETHEIA_PROTECTED_KEY", "m11-test-protected-key")
    memory = Memory.open(str(tmp_path / "m11.db"), namespace=NAMESPACE)
    calls = {"count": 0}

    class ExternalProvider:
        name = "external_unit"
        provider_type = "openai_compatible"
        model = "external-test"
        dimension = 3
        provider_version = "test"
        external_network_access = True
        stores_data = "unknown"
        supports_no_log_mode = "unknown"

        def embed_texts(self, texts, **kwargs):
            calls["count"] += 1
            return [[1.0, 0.0, 0.0] for _ in texts]

    monkeypatch.setattr("aletheia.core.memory.provider_for_name", lambda *args, **kwargs: ExternalProvider())
    try:
        memory.enable_protected_mode(actor="pytest")
        _remember(
            memory,
            subject="secret roadmap",
            predicate="contains",
            object="external provider leak test",
            privacy_level="secret",
        )

        run = memory.index_semantic(NAMESPACE, provider="openai_compatible")

        assert run.blocked_count == 1
        assert calls["count"] == 0
    finally:
        memory.close()


def test_redaction_marks_semantic_vectors_stale(tmp_path):
    memory = Memory.open(str(tmp_path / "m11.db"), namespace=NAMESPACE)
    try:
        event = memory.write_event(
            namespace=NAMESPACE,
            source_type="unit",
            content="redaction should stale semantic vectors",
            privacy_level="personal",
        )
        claim = memory.write_claim(
            namespace=NAMESPACE,
            subject="redaction",
            predicate="stales",
            object="semantic vectors",
            memory_type="project",
            evidence_ids=[event.id],
        )
        memory.index_semantic(NAMESPACE, provider="local_hash", dimension=32, force=True)

        applied = memory.redact(target_id=event.id, target_type="evidence", reason="unit", dry_run=False)
        assert applied.dry_run is False

        row = memory.store.connection.execute(
            "SELECT status, stale_reason FROM embeddings WHERE target_id = ?",
            (claim.id,),
        ).fetchone()
        assert row["status"] == "stale"
        assert row["stale_reason"] == "evidence.redacted"
    finally:
        memory.close()
