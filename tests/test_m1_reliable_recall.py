from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from aletheia import Memory
from aletheia.cli.main import main


def test_retrieve_filters_and_exclusions(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        keep = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="practical and direct",
            confidence=0.9,
        )
        memory.remember(
            namespace="user/other",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="terse",
            confidence=0.9,
        )
        rejected = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_editor",
            object="rejected editor",
            confidence=0.8,
        )
        archived = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_theme",
            object="archived dark",
            confidence=0.8,
        )
        memory.demote_claim(rejected.id, "rejected", reason="Test rejected memory.")
        memory.demote_claim(archived.id, "archived", reason="Test archived memory.")

        results = memory.retrieve(
            namespace="user/default",
            query="response style practical editor archived",
        )
        ids = {result.claim_id for result in results}
        assert keep.id in ids
        assert rejected.id not in ids
        assert archived.id not in ids
        assert all(result.namespace == "user/default" for result in results)

        archived_results = memory.retrieve(
            namespace="user/default",
            query="archived dark",
            statuses=["archived"],
            include_archived=True,
        )
        assert [result.claim_id for result in archived_results] == [archived.id]

        rejected_results = memory.retrieve(
            namespace="user/default",
            query="rejected editor",
            statuses=["rejected"],
        )
        assert rejected_results == []
    finally:
        memory.close()


def test_retrieve_and_context_pack_are_read_only_by_default_with_bounded_queries(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"), namespace="user/default")
    try:
        claim_ids = []
        for index in range(30):
            event = memory.write_event(
                namespace="user/default",
                source_type="manual",
                content=f"phase3 retrieval candidate {index}",
            )
            claim = memory.write_claim(
                namespace="user/default",
                memory_type="project",
                subject=f"phase3-{index}",
                predicate="has_retrieval_marker",
                object=f"bounded query candidate {index}",
                evidence_ids=[event.id],
                confidence=0.8,
            )
            claim_ids.append(claim.id)

        def count_rows(table: str) -> int:
            return memory.store.connection.execute(
                f"SELECT count(*) AS count FROM {table}"
            ).fetchone()["count"]

        before_counts = {
            table: count_rows(table)
            for table in [
                "retrieval_log",
                "context_pack_log",
                "memory_usage_events",
                "context_usage_events",
            ]
        }
        before_accessed = memory.read_claim(claim_ids[0]).last_accessed_at
        statements: list[str] = []
        memory.store.connection.set_trace_callback(statements.append)
        results = memory.retrieve(
            namespace="user/default",
            query="phase3 retrieval candidate",
            mode="lexical",
            limit=5,
        )
        memory.store.connection.set_trace_callback(None)

        assert len(results) == 5
        assert {
            table: count_rows(table)
            for table in before_counts
        } == before_counts
        assert memory.read_claim(claim_ids[0]).last_accessed_at == before_accessed
        assert not any(statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for statement in statements)
        assert sum(1 for statement in statements if statement.lstrip().upper().startswith("SELECT")) <= 8
        assert any(" LIMIT " in statement.upper() for statement in statements if "FROM claims_fts" in statement)

        hybrid_statements: list[str] = []
        memory.store.connection.set_trace_callback(hybrid_statements.append)
        memory.retrieve(
            namespace="user/default",
            query="phase3 retrieval candidate",
            mode="hybrid",
            limit=5,
        )
        memory.store.connection.set_trace_callback(None)
        assert not any(statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for statement in hybrid_statements)
        assert sum(1 for statement in hybrid_statements if statement.lstrip().upper().startswith("SELECT")) <= 10
        assert any(" LIMIT " in statement.upper() for statement in hybrid_statements if "FROM claims c" in statement)

        pack = memory.context_pack(
            namespace="user/default",
            query="phase3 retrieval candidate",
            include_reflections=False,
            include_warnings=False,
        )
        assert pack.id
        assert {
            table: count_rows(table)
            for table in before_counts
        } == before_counts

        access_results = memory.retrieve(
            namespace="user/default",
            query="phase3 retrieval candidate",
            limit=1,
            record_access=True,
        )
        assert count_rows("retrieval_log") == before_counts["retrieval_log"] + 1
        assert memory.read_claim(access_results[0].claim_id).last_accessed_at is not None

        usage_pack = memory.context_pack(
            namespace="user/default",
            query="phase3 retrieval candidate",
            include_reflections=False,
            include_warnings=False,
            record_usage=True,
        )
        assert usage_pack.id
        assert count_rows("context_pack_log") == before_counts["context_pack_log"] + 1
        assert count_rows("context_usage_events") == before_counts["context_usage_events"] + 1
        assert count_rows("memory_usage_events") >= before_counts["memory_usage_events"] + 1

        job = memory.enqueue_job("user/default", job_type="recompute_confidence", payload={})
        completed = memory.run_jobs(namespace="user/default", job_type="recompute_confidence")
        assert [completed_job.id for completed_job in completed] == [job.id]
        assert memory.get_job(job.id).status == "completed"
    finally:
        memory.close()


def test_retrieve_excludes_disputed_by_default_and_warns_in_context(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        first = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="short",
            confidence=0.9,
        )
        second = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="detailed",
            confidence=0.9,
        )

        results = memory.retrieve(namespace="user/default", query="response style")
        assert first.id not in {result.claim_id for result in results}
        assert second.id not in {result.claim_id for result in results}

        disputed = memory.retrieve(
            namespace="user/default",
            query="response style",
            statuses=["disputed"],
            include_disputed=True,
        )
        assert {result.claim_id for result in disputed} == {first.id, second.id}

        pack = memory.context_pack(
            namespace="user/default",
            query="response style",
        )
        assert not pack.core_memory
        assert any(warning.warning_type == "unresolved_conflict" for warning in pack.warnings)
    finally:
        memory.close()


def test_retrieve_ranking_is_deterministic_and_prefers_core(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        ordinary = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="practical",
            confidence=0.95,
        )
        core = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_answer_style",
            object="practical",
            confidence=0.95,
            importance=0.8,
        )
        memory.promote_claim(core.id, "core", reason="Stable high-importance preference.")

        first = memory.retrieve(namespace="user/default", query="practical")
        second = memory.retrieve(namespace="user/default", query="practical")
        assert [result.claim_id for result in first] == [result.claim_id for result in second]
        assert first[0].claim_id == core.id
        assert ordinary.id in [result.claim_id for result in first]
    finally:
        memory.close()


def test_context_pack_preserves_sources_and_respects_token_budget(tmp_path):
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
        memory.promote_claim(first.id, "core", reason="Stable high-importance preference.")
        second = memory.remember(
            namespace="user/default",
            memory_type="procedure",
            subject="assistant",
            predicate="uses_workflow",
            object="write detailed phased plans with tests and exit criteria",
            confidence=0.85,
        )

        pack = memory.context_pack(
            namespace="user/default",
            query="phased response style tests",
            token_budget=14,
        )

        assert pack.core_memory
        assert pack.sources
        assert first.evidence_ids[0] in pack.sources
        assert any(item.claim_id == first.id for item in pack.items())
        assert any(omitted.claim_id == second.id for omitted in pack.omitted)
        assert "confidence:" in pack.to_markdown()
        assert pack.to_dict()["core_memory"][0]["claim_id"] == first.id
    finally:
        memory.close()


def test_session_and_project_context_continuity(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        project = memory.create_project(
            "user/default",
            "aletheia",
            title="Aletheia Memory Library",
        )
        memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="practical and direct",
            confidence=0.9,
        )
        session = memory.start_session(
            "user/default",
            project_id=project.id,
            title="M1 design",
        )
        memory.remember(
            namespace="user/default",
            memory_type="project",
            subject="project:aletheia",
            predicate="current_milestone",
            object="M1 Reliable Recall and Context Continuity",
            project_id=project.id,
            session_id=session.id,
        )
        memory.end_session(
            session.id,
            summary="Completed the M1 contract for reliable recall and context continuity.",
        )
        next_session = memory.start_session(
            "user/default",
            project_id=project.id,
            title="M1 implementation",
        )
        pack = memory.context_pack(
            namespace="user/default",
            query="Where did we leave off?",
            session_id=next_session.id,
            project_id=project.id,
        )

        assert any("Aletheia Memory Library" in item.text for item in pack.project_memory)
        assert any("M1 Reliable Recall" in item.text for item in pack.project_memory)
        assert any("Completed the M1 contract" in item.text for item in pack.session_memory)
    finally:
        memory.close()


def test_project_claim_linking_and_project_isolation(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        memory.create_project("user/default", "aletheia", title="Aletheia")
        memory.create_project("user/default", "other", title="Other")
        aletheia_claim = memory.remember(
            namespace="user/default",
            memory_type="project",
            subject="project:aletheia",
            predicate="current_milestone",
            object="Reliable Recall",
        )
        other_claim = memory.remember(
            namespace="user/default",
            memory_type="project",
            subject="project:other",
            predicate="current_milestone",
            object="Unrelated Project",
        )

        pack = memory.context_pack(
            namespace="user/default",
            query="current milestone",
            project_id="aletheia",
        )
        project_ids = {item.claim_id for item in pack.project_memory}
        assert aletheia_claim.id in project_ids
        assert other_claim.id not in project_ids
    finally:
        memory.close()


def test_cli_context_sessions_projects_and_migrate(tmp_path, capsys):
    db = str(tmp_path / "aletheia.db")
    assert main(["migrate", "--db", db]) == 0
    assert '"schema_version": "1.3.0"' in capsys.readouterr().out

    assert main(
        [
            "projects",
            "create",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--id",
            "aletheia",
            "--title",
            "Aletheia Memory Library",
        ]
    ) == 0
    assert '"id": "aletheia"' in capsys.readouterr().out

    assert main(
        [
            "sessions",
            "start",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--project",
            "aletheia",
            "--title",
            "M1 contract design",
        ]
    ) == 0
    session_output = capsys.readouterr().out
    session_id = re.search(r'"id": "(sess_[^"]+)"', session_output).group(1)

    assert main(
        [
            "remember",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--type",
            "preference",
            "--subject",
            "user",
            "--predicate",
            "prefers_response_style",
            "--object",
            "practical and direct",
        ]
    ) == 0
    capsys.readouterr()

    assert main(
        [
            "context",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--project",
            "aletheia",
            "--session",
            session_id,
            "--query",
            "Continue designing Aletheia",
            "--budget",
            "1200",
        ]
    ) == 0
    markdown = capsys.readouterr().out
    assert "## Memory Context" in markdown
    assert "Aletheia Memory Library" in markdown
    assert "practical and direct" in markdown

    assert main(
        [
            "context",
            "--db",
            db,
            "--namespace",
            "user/default",
            "--query",
            "response style",
            "--json",
        ]
    ) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["namespace"] == "user/default"
    assert data["sources"]

    assert main(
        [
            "sessions",
            "end",
            "--db",
            db,
            "--session",
            session_id,
            "--summary",
            "Completed M1 CLI context flow.",
        ]
    ) == 0
    assert '"ended_at":' in capsys.readouterr().out

    assert main(["sessions", "list", "--db", db, "--namespace", "user/default"]) == 0
    assert session_id in capsys.readouterr().out


def test_migration_from_m0_database_preserves_claims_and_audit(tmp_path):
    db_path = tmp_path / "m0.db"
    _create_minimal_m0_database(db_path)

    memory = Memory.open(str(db_path))
    try:
        assert memory.health()["schema_version"] == "1.3.0"
        results = memory.retrieve(namespace="user/default", query="direct")
        assert results
        assert results[0].object == "direct"
        audit = memory.audit("clm_m0")
        assert audit["claim"]["id"] == "clm_m0"
        table_names = {
            row["name"]
            for row in memory.store.connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
            ).fetchall()
        }
        assert {
            "sessions",
            "projects",
            "retrieval_log",
            "context_pack_log",
            "confidence_snapshots",
            "claim_status_history",
            "conflict_families",
        }.issubset(table_names)
    finally:
        memory.close()


def test_golden_context_section_membership(tmp_path):
    memory = Memory.open(str(tmp_path / "aletheia.db"))
    try:
        memory.create_project("user/default", "aletheia", title="Aletheia")
        preference = memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_response_style",
            object="practical direct answers",
            confidence=0.9,
            importance=0.8,
        )
        memory.promote_claim(preference.id, "core", reason="Stable high-importance preference.")
        memory.remember(
            namespace="user/default",
            memory_type="project",
            subject="project:aletheia",
            predicate="current_focus",
            object="reliable recall",
        )
        memory.remember(
            namespace="user/default",
            memory_type="procedure",
            subject="assistant",
            predicate="uses_response_pattern",
            object="phased plans with deliverables and tests",
        )
        memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_length",
            object="short",
        )
        memory.remember(
            namespace="user/default",
            memory_type="preference",
            subject="user",
            predicate="prefers_length",
            object="detailed",
        )

        pack = memory.context_pack(
            namespace="user/default",
            query="architecture plan recall tests",
            project_id="aletheia",
        )

        assert any("practical direct" in item.text for item in pack.core_memory)
        assert any("reliable recall" in item.text for item in pack.project_memory)
        assert any("phased plans" in item.text for item in pack.procedural_memory)
        assert any(warning.warning_type == "unresolved_conflict" for warning in pack.warnings)
        all_item_text = "\n".join(item.text for item in pack.items())
        assert "prefers length short" not in all_item_text
        assert "prefers length detailed" not in all_item_text
    finally:
        memory.close()


def _create_minimal_m0_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );
        INSERT INTO schema_version VALUES (1, '0.1.0', '2026-01-01T00:00:00+00:00');

        CREATE TABLE evidence_events (
            id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL,
            session_id TEXT,
            source_type TEXT NOT NULL,
            source_uri TEXT,
            content TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            observed_at TEXT,
            trust_level TEXT DEFAULT 'unknown',
            privacy_level TEXT DEFAULT 'personal',
            retention_policy TEXT DEFAULT 'default'
        );
        CREATE TABLE claims (
            id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence_base REAL NOT NULL,
            confidence_effective REAL NOT NULL,
            half_life_days REAL NOT NULL,
            importance REAL DEFAULT 0.5,
            volatility TEXT DEFAULT 'medium',
            created_at TEXT NOT NULL,
            last_verified_at TEXT,
            last_accessed_at TEXT,
            valid_from TEXT,
            valid_to TEXT
        );
        CREATE TABLE claim_evidence_links (
            claim_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            PRIMARY KEY (claim_id, evidence_id)
        );
        CREATE TABLE audit_log (
            id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE conflicts (
            id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            status TEXT NOT NULL,
            active_claim_id TEXT,
            resolution_note TEXT,
            created_at TEXT NOT NULL,
            resolved_at TEXT
        );
        CREATE TABLE conflict_claim_links (
            conflict_id TEXT NOT NULL,
            claim_id TEXT NOT NULL,
            PRIMARY KEY (conflict_id, claim_id)
        );
        CREATE TABLE feedback (
            id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            signal TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE claims_fts USING fts5(
            claim_id UNINDEXED,
            namespace UNINDEXED,
            subject,
            predicate,
            object,
            memory_type UNINDEXED,
            content
        );
        INSERT INTO evidence_events VALUES (
            'evt_m0', 'user/default', NULL, 'manual', NULL,
            'User prefers response style direct.', 'hash',
            '2026-01-01T00:00:00+00:00', NULL, 'user_asserted',
            'personal', 'default'
        );
        INSERT INTO claims VALUES (
            'clm_m0', 'user/default', 'user', 'prefers_response_style', 'direct',
            'preference', 'active', 0.9, 0.9, 180.0, 0.5, 'medium',
            '2026-01-01T00:00:00+00:00', NULL, NULL, NULL, NULL
        );
        INSERT INTO claim_evidence_links VALUES ('clm_m0', 'evt_m0');
        INSERT INTO audit_log VALUES (
            'aud_m0', 'user/default', 'claim', 'clm_m0', 'claim.write', '{}',
            '2026-01-01T00:00:00+00:00'
        );
        INSERT INTO claims_fts VALUES (
            'clm_m0', 'user/default', 'user', 'prefers_response_style',
            'direct', 'preference', 'User prefers response style direct.'
        );
        """
    )
    connection.commit()
    connection.close()
