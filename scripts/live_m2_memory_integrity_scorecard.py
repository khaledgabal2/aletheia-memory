"""Live M2 scorecard: Memory Integrity, Confidence, Conflict, and Curation."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import Memory
from aletheia.core.time import utc_now

NAMESPACE = "user/default"


@dataclass
class CaseResult:
    category: str
    case: str
    interface: str
    passed: bool
    details: str


class M2Runner:
    def __init__(self, db_path: Path, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self.results: list[CaseResult] = []
        self.ids: dict[str, str] = {}

    def run(self) -> list[CaseResult]:
        cases: list[tuple[str, str, str, Callable[[], str]]] = [
            ("Setup", "Initialize schema 1.3.0 with M2 tables", "CLI/API", self.case_init_schema),
            ("Confidence", "Show explainable confidence snapshot", "CLI", self.case_confidence_show),
            ("Confidence", "Recompute persists snapshots and events", "CLI/API", self.case_recompute_persists),
            ("Feedback", "Useful feedback changes salience, not truth", "API", self.case_useful_feedback),
            ("Feedback", "Confirmed feedback raises truth confidence", "API", self.case_confirmed_feedback),
            ("Feedback", "Assistant self-confirmation is downweighted", "API", self.case_assistant_guard),
            ("Decay", "Half-life policy and decay run lower stale task confidence", "CLI/API", self.case_decay_policy),
            ("Conflict", "Detect preference conflict and surface context warning", "CLI/API", self.case_conflict_warning),
            ("Conflict", "Resolve conflict by context scope", "CLI/API", self.case_context_scope_resolution),
            ("Conflict", "Resolve explicit correction and time-scoped conflicts", "API", self.case_correction_and_time_scope),
            ("Lifecycle", "Promote scoped durable memory to core and inspect history", "CLI", self.case_promote_history),
            ("Lifecycle", "Demote claim and guard core promotion", "CLI/API", self.case_demote_and_core_guard),
            ("Curation", "Preview is dry and apply promotes candidate to active", "CLI/API", self.case_curation),
            ("Duplicates", "Duplicate detection writes relationship without dispute", "API", self.case_duplicate_detection),
            ("Explanation", "Explain claim includes confidence, scope, history, evidence", "API", self.case_explain_claim),
            ("Supersession", "Supersede claim preserves old evidence and relationship", "CLI/API", self.case_supersede),
            ("Migration", "M1-style database migrates idempotently to M2", "CLI/API", self.case_m1_to_m2_migration),
        ]
        for category, case, interface, fn in cases:
            try:
                self.results.append(CaseResult(category, case, interface, True, fn()))
            except Exception as exc:  # noqa: BLE001 - scorecard should continue.
                self.results.append(CaseResult(category, case, interface, False, str(exc)))
        return self.results

    def case_init_schema(self) -> str:
        health = json.loads(self.cli("init", "--db", str(self.db_path)).stdout)
        assert health["schema_version"] == "1.3.0"
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            names = {
                row["name"]
                for row in memory.store.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
                ).fetchall()
            }
            required = {
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
            }
            assert required.issubset(names)
        finally:
            memory.close()
        return "schema_version=1.3.0 and M2 tables present"

    def case_confidence_show(self) -> str:
        remembered = self.cli(
            "remember",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
            "--type",
            "preference",
            "--subject",
            "user",
            "--predicate",
            "prefers_response_style",
            "--object",
            "comprehensive architecture explanations",
            "--confidence",
            "0.92",
            "--importance",
            "0.80",
        ).stdout
        claim_id = extract_id(remembered, "clm")
        self.ids["architecture_claim"] = claim_id
        shown = self.cli(
            "confidence",
            "show",
            claim_id,
            "--db",
            str(self.db_path),
            "--explain",
        ).stdout
        assert "truth_confidence:" in shown
        assert "retrieval_salience:" in shown
        assert "explanation:" in shown
        return f"claim={claim_id}"

    def case_recompute_persists(self) -> str:
        recomputed = self.cli(
            "confidence",
            "recompute",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
        ).stdout
        assert "Recomputed confidence" in recomputed
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            claim_id = self.ids["architecture_claim"]
            snapshots = memory.store.connection.execute(
                "SELECT count(*) AS count FROM confidence_snapshots WHERE claim_id = ?",
                (claim_id,),
            ).fetchone()["count"]
            events = memory.store.connection.execute(
                "SELECT count(*) AS count FROM confidence_events WHERE claim_id = ?",
                (claim_id,),
            ).fetchone()["count"]
            assert snapshots >= 1
            assert events >= 1
            return f"snapshots={snapshots}, events={events}"
        finally:
            memory.close()

    def case_useful_feedback(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            claim_id = self.ids["architecture_claim"]
            before = memory.compute_confidence(claim_id)
            memory.feedback(claim_id, signal="useful", source="user")
            after = memory.compute_confidence(claim_id)
            assert abs(after.truth_confidence - before.truth_confidence) < 0.001
            assert after.retrieval_salience > before.retrieval_salience
            return f"salience {before.retrieval_salience:.3f}->{after.retrieval_salience:.3f}"
        finally:
            memory.close()

    def case_confirmed_feedback(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            claim = memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user",
                predicate="prefers_confirmation_marker",
                object="confirmed memories gain confidence",
                confidence=0.60,
            )
            before = memory.compute_confidence(claim.id)
            memory.feedback(claim.id, signal="confirmed", source="user")
            after = memory.compute_confidence(claim.id)
            assert after.truth_confidence > before.truth_confidence
            assert memory.read_claim(claim.id).last_verified_at is not None
            return f"truth {before.truth_confidence:.3f}->{after.truth_confidence:.3f}"
        finally:
            memory.close()

    def case_assistant_guard(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            claim = memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="assistant",
                predicate="should_not_self_confirm",
                object="true",
                confidence=0.6,
            )
            before = memory.compute_confidence(claim.id)
            record = memory.feedback(claim.id, signal="confirmed", source="assistant")
            after = memory.compute_confidence(claim.id)
            assert record.strength <= 0.05
            assert memory.read_claim(claim.id).last_verified_at is None
            assert after.truth_confidence - before.truth_confidence < 0.02
            return f"assistant confirmation strength={record.strength:.2f}"
        finally:
            memory.close()

    def case_decay_policy(self) -> str:
        self.cli(
            "confidence",
            "policy",
            "set",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
            "--memory-type",
            "task",
            "--half-life-days",
            "1",
            "--reason",
            "Temporary tasks decay quickly in live test.",
        )
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            claim = memory.remember(
                namespace=NAMESPACE,
                memory_type="task",
                subject="task",
                predicate="has_status",
                object="temporary M2 check",
                confidence=0.8,
            )
            stale_time = (utc_now() - timedelta(days=4)).isoformat()
            with memory.store.connection:
                memory.store.connection.execute(
                    "UPDATE claims SET created_at = ?, last_verified_at = NULL WHERE id = ?",
                    (stale_time, claim.id),
                )
        finally:
            memory.close()
        preview = self.cli(
            "decay",
            "preview",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
        ).stdout
        assert "Previewed decay" in preview
        self.cli("decay", "run", "--db", str(self.db_path), "--namespace", NAMESPACE)
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            decayed = memory.read_claim(claim.id)
            assert decayed.confidence_effective < 0.1
            return f"{claim.id} confidence={decayed.confidence_effective:.3f}"
        finally:
            memory.close()

    def case_conflict_warning(self) -> str:
        concise = self.cli(
            "remember",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
            "--type",
            "preference",
            "--subject",
            "user",
            "--predicate",
            "prefers_response_style",
            "--object",
            "concise progress updates",
            "--confidence",
            "0.88",
        ).stdout
        self.ids["concise_claim"] = extract_id(concise, "clm")
        detected = self.cli(
            "conflicts",
            "detect",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
        ).stdout
        conflict_id = extract_id(detected, "conf")
        self.ids["style_conflict"] = conflict_id
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            pack = memory.context_pack(namespace=NAMESPACE, query="response style")
            assert any(warning.warning_type == "unresolved_conflict" for warning in pack.warnings)
            assert not any("concise progress" in item.text for item in pack.items())
            return f"conflict={conflict_id}"
        finally:
            memory.close()

    def case_context_scope_resolution(self) -> str:
        conflict_id = self.ids["style_conflict"]
        self.cli(
            "conflicts",
            "resolve",
            conflict_id,
            "--db",
            str(self.db_path),
            "--strategy",
            "context_scope",
            "--note",
            "Concise for progress; comprehensive for architecture/design.",
        )
        self.cli(
            "claims",
            "scope",
            self.ids["architecture_claim"],
            "--db",
            str(self.db_path),
            "--type",
            "contextual",
            "--applies-when",
            "architecture_or_design_request",
            "--reason",
            "Architecture/design requests need comprehensive explanations.",
        )
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            architecture_pack = memory.context_pack(
                namespace=NAMESPACE,
                query="write an architecture contract and design plan",
            )
            progress_pack = memory.context_pack(
                namespace=NAMESPACE,
                query="give a progress update",
            )
            assert any(
                "comprehensive architecture" in item.text
                for item in architecture_pack.items()
            )
            assert not any(
                "comprehensive architecture" in item.text
                for item in progress_pack.items()
            )
            return "scoped architecture memory included only when scope matches"
        finally:
            memory.close()

    def case_correction_and_time_scope(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            old = memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user",
                predicate="prefers_validation_style",
                object="unit tests only",
                confidence=0.80,
            )
            correction = memory.remember(
                namespace=NAMESPACE,
                memory_type="correction",
                subject="user",
                predicate="prefers_validation_style",
                object="unit and live tests",
                confidence=0.92,
            )
            correction_family = [
                family
                for family in memory.list_conflict_families(namespace=NAMESPACE)
                if old.id in family.claim_ids and correction.id in family.claim_ids
            ][0]
            resolution = memory.resolve_conflict(
                correction_family.id,
                strategy="user_correction_wins",
                note="User correction supersedes weaker memory.",
            )
            assert resolution.active_claim_id == correction.id
            assert memory.read_claim(old.id).status == "superseded"
            assert memory.read_claim(correction.id).status == "active"

            previous = memory.remember(
                namespace=NAMESPACE,
                memory_type="project_state",
                subject="project:aletheia",
                predicate="current_phase",
                object="M1",
                confidence=0.82,
            )
            current = memory.remember(
                namespace=NAMESPACE,
                memory_type="project_state",
                subject="project:aletheia",
                predicate="current_phase",
                object="M2",
                confidence=0.88,
            )
            time_family = [
                family
                for family in memory.list_conflict_families(namespace=NAMESPACE)
                if previous.id in family.claim_ids and current.id in family.claim_ids
            ][0]
            now_text = utc_now().isoformat()
            memory.resolve_conflict(
                time_family.id,
                strategy="time_scope",
                scoped_claims=[
                    {
                        "claim_id": previous.id,
                        "scope_type": "temporal",
                        "valid_to": now_text,
                        "reason": "Previous phase is historical.",
                    },
                    {
                        "claim_id": current.id,
                        "scope_type": "temporal",
                        "valid_from": now_text,
                        "reason": "Current phase applies now.",
                    },
                ],
                note="Resolve project phase by temporal scope.",
            )
            scoped_family = memory.read_conflict_family(time_family.id)
            assert scoped_family.status == "time_scoped"
            assert memory.list_claim_scopes(previous.id)
            assert memory.list_claim_scopes(current.id)
            audit_row = memory.store.connection.execute(
                """
                SELECT 1
                FROM audit_log
                WHERE target_type = 'conflict'
                  AND target_id = ?
                  AND action = 'conflict.resolve'
                LIMIT 1
                """,
                (correction_family.id,),
            ).fetchone()
            assert audit_row is not None
            return "correction superseded old claim; temporal scopes recorded"
        finally:
            memory.close()

    def case_promote_history(self) -> str:
        claim_id = self.ids["architecture_claim"]
        promoted = self.cli(
            "claims",
            "promote",
            claim_id,
            "--db",
            str(self.db_path),
            "--to",
            "core",
            "--reason",
            "Stable scoped architecture preference.",
        ).stdout
        assert "status: core" in promoted
        history = self.cli("claims", "history", claim_id, "--db", str(self.db_path)).stdout
        assert "active -> core" in history
        return f"{claim_id} promoted with status history"

    def case_demote_and_core_guard(self) -> str:
        demoted = self.cli(
            "remember",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
            "--type",
            "preference",
            "--subject",
            "user",
            "--predicate",
            "prefers_deprecated_tool",
            "--object",
            "old experimental tool",
            "--confidence",
            "0.90",
        ).stdout
        demoted_id = extract_id(demoted, "clm")
        demote_output = self.cli(
            "claims",
            "demote",
            demoted_id,
            "--db",
            str(self.db_path),
            "--to",
            "archived",
            "--reason",
            "No longer relevant.",
        ).stdout
        assert "demote_to_archived" in demote_output
        assert "status: archived" in demote_output

        guard_output = self.cli(
            "claims",
            "promote",
            self.ids["concise_claim"],
            "--db",
            str(self.db_path),
            "--to",
            "core",
            "--reason",
            "Disputed preference should not become core.",
            check=False,
        )
        assert guard_output.returncode != 0
        assert "Cannot promote claim" in guard_output.stderr
        return "demotion audited and disputed/weak core promotion rejected"

    def case_curation(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            candidate = memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user",
                predicate="prefers_validation",
                object="unit and live tests after each milestone",
                confidence=0.90,
                importance=0.50,
                status="candidate",
            )
            self.ids["candidate_claim"] = candidate.id
        finally:
            memory.close()
        preview = self.cli(
            "curate",
            "preview",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
        ).stdout
        assert "promote_to_active" in preview
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            assert memory.read_claim(self.ids["candidate_claim"]).status == "candidate"
        finally:
            memory.close()
        applied = self.cli(
            "curate",
            "apply",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
            "--max-decisions",
            "3",
        ).stdout
        assert "applied: true" in applied
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            assert memory.read_claim(self.ids["candidate_claim"]).status == "active"
            return f"{self.ids['candidate_claim']} promoted by curation"
        finally:
            memory.close()

    def case_duplicate_detection(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            first = memory.remember(
                namespace=NAMESPACE,
                memory_type="project",
                subject="project:aletheia",
                predicate="uses_storage",
                object="SQLite",
            )
            second = memory.remember(
                namespace=NAMESPACE,
                memory_type="project",
                subject="project:aletheia",
                predicate="uses_storage",
                object="SQLite",
            )
            duplicates = [
                family
                for family in memory.detect_conflicts(namespace=NAMESPACE)
                if family.conflict_type == "duplicate_claim"
            ]
            assert duplicates
            assert memory.read_claim(first.id).status == "active"
            assert memory.read_claim(second.id).status == "active"
            assert any(
                relationship.relationship_type == "duplicate_of"
                for relationship in memory.list_claim_relationships(second.id)
            )
            return f"duplicate family={duplicates[0].id}"
        finally:
            memory.close()

    def case_explain_claim(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            explanation = memory.explain_claim(self.ids["architecture_claim"])
            assert explanation.evidence
            assert explanation.confidence and explanation.confidence["truth_confidence"] > 0
            assert explanation.scopes
            assert explanation.history
            assert explanation.audit
            return "explanation includes evidence, confidence, scope, history, audit"
        finally:
            memory.close()

    def case_supersede(self) -> str:
        old = self.cli(
            "remember",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
            "--type",
            "project_state",
            "--subject",
            "project:aletheia",
            "--predicate",
            "current_phase",
            "--object",
            "M1",
        ).stdout
        new = self.cli(
            "remember",
            "--db",
            str(self.db_path),
            "--namespace",
            NAMESPACE,
            "--type",
            "project_state",
            "--subject",
            "project:aletheia",
            "--predicate",
            "current_phase",
            "--object",
            "M2",
        ).stdout
        old_id = extract_id(old, "clm")
        new_id = extract_id(new, "clm")
        self.cli(
            "claims",
            "supersede",
            old_id,
            new_id,
            "--db",
            str(self.db_path),
            "--reason",
            "M2 supersedes prior phase.",
        )
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            old_claim = memory.read_claim(old_id)
            assert old_claim.status == "superseded"
            assert old_claim.evidence_ids
            assert any(
                relationship.relationship_type == "supersedes"
                for relationship in memory.list_claim_relationships(new_id)
            )
            return f"{old_id} superseded by {new_id}"
        finally:
            memory.close()

    def case_m1_to_m2_migration(self) -> str:
        with tempfile.TemporaryDirectory(prefix="aletheia-m1-to-m2-") as temp_dir:
            m1_path = Path(temp_dir) / "m1.db"
            create_minimal_m1_database(m1_path)
            first = json.loads(
                self.cli("migrate", "--db", str(m1_path), check=True).stdout
            )
            second = json.loads(
                self.cli("migrate", "--db", str(m1_path), check=True).stdout
            )
            assert first["schema_version"] == "1.3.0"
            assert second["schema_version"] == "1.3.0"
            searched = self.cli(
                "search",
                "--db",
                str(m1_path),
                "--namespace",
                NAMESPACE,
                "direct",
            ).stdout
            assert "direct" in searched
            memory = Memory.open(str(m1_path), namespace=NAMESPACE)
            try:
                audit = memory.audit("clm_m1")
                assert any(entry["action"] == "claim.write" for entry in audit["audit"])
                assert memory.context_pack(namespace=NAMESPACE, query="direct").items()
            finally:
                memory.close()
        return "0.2-style database migrated twice with claim/audit/context intact"

    def cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, "-m", "aletheia.cli.main", *args]
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if self.verbose:
            print(f"\n$ {' '.join(cmd)}")
            if proc.stdout:
                print(proc.stdout.rstrip())
            if proc.stderr:
                print(proc.stderr.rstrip(), file=sys.stderr)
        if check and proc.returncode != 0:
            raise RuntimeError(
                f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr}"
            )
        return proc


def extract_id(text: str, prefix: str) -> str:
    match = re.search(rf"\b({prefix}_[A-Za-z0-9]+)\b", text)
    if not match:
        raise AssertionError(f"Could not find {prefix}_ id in output:\n{text}")
    return match.group(1)


def create_minimal_m1_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );
        INSERT INTO schema_version VALUES (1, '0.2.0', '2026-01-01T00:00:00+00:00');
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
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL,
            agent_id TEXT,
            project_id TEXT,
            title TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            metadata_json TEXT
        );
        CREATE TABLE projects (
            id TEXT NOT NULL,
            namespace TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT,
            PRIMARY KEY (namespace, id)
        );
        CREATE TABLE project_claim_links (
            namespace TEXT NOT NULL,
            project_id TEXT NOT NULL,
            claim_id TEXT NOT NULL,
            relation TEXT NOT NULL DEFAULT 'related',
            created_at TEXT NOT NULL,
            PRIMARY KEY (namespace, project_id, claim_id)
        );
        CREATE TABLE session_claim_links (
            session_id TEXT NOT NULL,
            claim_id TEXT NOT NULL,
            relation TEXT NOT NULL DEFAULT 'created_in_session',
            created_at TEXT NOT NULL,
            PRIMARY KEY (session_id, claim_id)
        );
        CREATE TABLE retrieval_log (
            id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL,
            query TEXT NOT NULL,
            session_id TEXT,
            project_id TEXT,
            result_count INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            metadata_json TEXT
        );
        CREATE TABLE context_pack_log (
            id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL,
            query TEXT NOT NULL,
            session_id TEXT,
            project_id TEXT,
            token_budget INTEGER NOT NULL,
            item_count INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            metadata_json TEXT
        );
        INSERT INTO evidence_events VALUES (
            'evt_m1', 'user/default', NULL, 'manual', NULL,
            'User prefers response style direct.', 'hash',
            '2026-01-01T00:00:00+00:00', NULL, 'user_asserted',
            'personal', 'default'
        );
        INSERT INTO claims VALUES (
            'clm_m1', 'user/default', 'user', 'prefers_response_style', 'direct',
            'preference', 'active', 0.9, 0.9, 180.0, 0.5, 'medium',
            '2026-01-01T00:00:00+00:00', NULL, NULL, NULL, NULL
        );
        INSERT INTO claim_evidence_links VALUES ('clm_m1', 'evt_m1');
        INSERT INTO audit_log VALUES (
            'aud_m1', 'user/default', 'claim', 'clm_m1', 'claim.write', '{}',
            '2026-01-01T00:00:00+00:00'
        );
        INSERT INTO claims_fts VALUES (
            'clm_m1', 'user/default', 'user', 'prefers_response_style',
            'direct', 'preference', 'User prefers response style direct.'
        );
        """
    )
    connection.commit()
    connection.close()


def print_scorecard(results: list[CaseResult], db_path: Path) -> None:
    categories: dict[str, list[CaseResult]] = {}
    for result in results:
        categories.setdefault(result.category, []).append(result)
    passed = sum(1 for result in results if result.passed)
    total = len(results)
    print("\nAletheia M2 Memory Integrity Scorecard")
    print("=" * 72)
    print(f"Database: {db_path}")
    print(f"Score: {passed}/{total} ({passed / total:.0%})")
    for category, grouped in categories.items():
        category_passed = sum(1 for result in grouped if result.passed)
        print(f"\n{category} ({category_passed}/{len(grouped)})")
        print("-" * 72)
        for result in grouped:
            mark = "PASS" if result.passed else "FAIL"
            print(f"{mark:4} | {result.interface:7} | {result.case}")
            print(f"     | {result.details}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Aletheia M2 live scorecard.")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--allow-existing", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.db:
        db_path = args.db.expanduser().resolve()
        if db_path.exists() and not args.allow_existing:
            print(
                f"Refusing to use existing database without --allow-existing: {db_path}",
                file=sys.stderr,
            )
            return 2
        db_path.parent.mkdir(parents=True, exist_ok=True)
        results = M2Runner(db_path, verbose=args.verbose).run()
        print_scorecard(results, db_path)
        return 0 if all(result.passed for result in results) else 1
    with tempfile.TemporaryDirectory(prefix="aletheia-m2-") as temp_dir:
        db_path = Path(temp_dir) / "aletheia-m2.db"
        results = M2Runner(db_path, verbose=args.verbose).run()
        print_scorecard(results, db_path)
        return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
