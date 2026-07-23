"""Live M1 scorecard: Reliable Recall and Context Continuity."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import Memory

NAMESPACE = "user/default"


@dataclass
class CaseResult:
    category: str
    case: str
    passed: bool
    details: str


class M1Runner:
    def __init__(self, db_path: Path, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self.results: list[CaseResult] = []
        self.ids: dict[str, str] = {}

    def run(self) -> list[CaseResult]:
        cases: list[tuple[str, str, Callable[[], str]]] = [
            ("Command Surface", "M1 CLI commands are exposed", self.case_help),
            ("Migration", "M0 database migrates to 1.3.0", self.case_m0_migration),
            ("Setup", "Initialize clean M1 database", self.case_init),
            ("Projects", "Create and inspect project", self.case_project_create),
            ("Sessions", "Start project session", self.case_session_start),
            ("Memory", "Remember user preference and project milestone", self.case_memory_setup),
            ("Retrieval", "Mark M1 retrieval acceptance criteria", self.case_retrieval_acceptance),
            ("Context", "Markdown context includes project, preference, milestone", self.case_context_markdown),
            ("Context", "JSON context preserves claim and evidence provenance", self.case_context_json),
            ("Sessions", "End session with summary claim", self.case_session_end_summary),
            ("Continuity", "New session recalls previous session summary", self.case_cross_session_recall),
            ("Warnings", "Unresolved conflict appears only as warning", self.case_conflict_warning),
            ("Isolation", "Separate project context does not contaminate", self.case_project_isolation),
        ]
        for category, case, fn in cases:
            try:
                self.results.append(CaseResult(category, case, True, fn()))
            except Exception as exc:  # noqa: BLE001 - keep scorecard running.
                self.results.append(CaseResult(category, case, False, str(exc)))
        return self.results

    def case_help(self) -> str:
        proc = self.cli(["--help"], include_db=False)
        for command in ["migrate", "context", "sessions", "projects"]:
            assert command in proc.stdout
        return "migrate/context/sessions/projects available"

    def case_m0_migration(self) -> str:
        with tempfile.TemporaryDirectory(prefix="aletheia-m0-") as temp_dir:
            m0_path = Path(temp_dir) / "m0.db"
            create_m0_database(m0_path)
            migrated = self.cli(["migrate", "--db", str(m0_path)], include_db=False)
            health = json.loads(migrated.stdout)
            assert health["schema_version"] == "1.3.0"
            searched = self.cli(
                [
                    "search",
                    "--db",
                    str(m0_path),
                    "--namespace",
                    NAMESPACE,
                    "direct",
                ],
                include_db=False,
            )
            assert "direct" in searched.stdout
        return "0.1.0 data preserved after migration"

    def case_init(self) -> str:
        health = json.loads(self.cli(["init"]).stdout)
        assert health["schema_version"] == "1.3.0"
        return "schema_version=1.3.0"

    def case_project_create(self) -> str:
        created = json.loads(
            self.cli(
                [
                    "projects",
                    "create",
                    "--namespace",
                    NAMESPACE,
                    "--id",
                    "aletheia",
                    "--title",
                    "Aletheia Memory Library",
                ]
            ).stdout
        )
        assert created["id"] == "aletheia"
        shown = json.loads(
            self.cli(
                [
                    "projects",
                    "show",
                    "--namespace",
                    NAMESPACE,
                    "--id",
                    "aletheia",
                ]
            ).stdout
        )
        assert shown["title"] == "Aletheia Memory Library"
        return "project=aletheia"

    def case_session_start(self) -> str:
        session = json.loads(
            self.cli(
                [
                    "sessions",
                    "start",
                    "--namespace",
                    NAMESPACE,
                    "--project",
                    "aletheia",
                    "--title",
                    "M1 contract design",
                ]
            ).stdout
        )
        self.ids["session"] = session["id"]
        assert session["project_id"] == "aletheia"
        return f"session={session['id']}"

    def case_memory_setup(self) -> str:
        preference = self.cli(
            [
                "remember",
                "--namespace",
                NAMESPACE,
                "--type",
                "preference",
                "--subject",
                "user",
                "--predicate",
                "prefers_response_style",
                "--object",
                "practical and direct",
                "--confidence",
                "0.90",
            ]
        ).stdout
        self.ids["preference_claim"] = extract_id(preference, "clm")

        milestone = self.cli(
            [
                "remember",
                "--namespace",
                NAMESPACE,
                "--type",
                "project",
                "--subject",
                "project:aletheia",
                "--predicate",
                "current_milestone",
                "--object",
                "M1 Reliable Recall and Context Continuity",
                "--project",
                "aletheia",
                "--session",
                self.ids["session"],
            ]
        ).stdout
        self.ids["milestone_claim"] = extract_id(milestone, "clm")
        return "preference and milestone remembered"

    def case_retrieval_acceptance(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            other_namespace = memory.remember(
                namespace="user/other",
                memory_type="preference",
                subject="user",
                predicate="acceptance_namespace_marker",
                object="other namespace only",
                confidence=0.9,
            )
            rejected = memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user",
                predicate="acceptance_rejected_marker",
                object="hidden rejected marker",
                confidence=0.8,
            )
            archived = memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user",
                predicate="acceptance_archived_marker",
                object="hidden archived marker",
                confidence=0.8,
            )
            memory.demote_claim(rejected.id, "rejected", reason="M1 live acceptance.")
            memory.demote_claim(archived.id, "archived", reason="M1 live acceptance.")

            ordinary = memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user",
                predicate="acceptance_ranking_marker",
                object="ranking alpha",
                confidence=0.95,
                importance=0.5,
            )
            core = memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user",
                predicate="acceptance_core_marker",
                object="ranking alpha",
                confidence=0.95,
                importance=0.8,
            )
            memory.promote_claim(
                core.id,
                "core",
                reason="M1 live core-ranking acceptance.",
            )

            project_claim = memory.remember(
                namespace=NAMESPACE,
                memory_type="project",
                subject="project:aletheia",
                predicate="acceptance_project_marker",
                object="project scoped memory",
                project_id="aletheia",
            )
            unrelated_project_claim = memory.remember(
                namespace=NAMESPACE,
                memory_type="project",
                subject="project:other",
                predicate="acceptance_project_marker",
                object="unrelated project scoped memory",
                project_id="other",
            )

            stale = memory.remember(
                namespace=NAMESPACE,
                memory_type="task",
                subject="task",
                predicate="acceptance_stale_marker",
                object="stale confidence marker",
                confidence=0.8,
                half_life_days=1.0,
            )
            stale_time = (datetime.now(UTC) - timedelta(days=4)).isoformat()
            with memory.store.connection:
                memory.store.connection.execute(
                    "UPDATE claims SET created_at = ?, last_verified_at = NULL WHERE id = ?",
                    (stale_time, stale.id),
                )

            namespace_results = memory.retrieve(
                namespace=NAMESPACE,
                query="other namespace only ranking alpha",
                memory_types=["preference"],
            )
            namespace_ids = {result.claim_id for result in namespace_results}
            assert other_namespace.id not in namespace_ids
            assert namespace_results[0].claim_id == core.id
            assert ordinary.id in namespace_ids
            assert all(result.evidence_ids for result in namespace_results)

            default_hidden = memory.retrieve(
                namespace=NAMESPACE,
                query="hidden rejected marker hidden archived marker",
            )
            default_hidden_ids = {result.claim_id for result in default_hidden}
            assert rejected.id not in default_hidden_ids
            assert archived.id not in default_hidden_ids

            archived_results = memory.retrieve(
                namespace=NAMESPACE,
                query="hidden archived marker",
                statuses=["archived"],
                include_archived=True,
            )
            assert [result.claim_id for result in archived_results] == [archived.id]

            rejected_results = memory.retrieve(
                namespace=NAMESPACE,
                query="hidden rejected marker",
                statuses=["rejected"],
            )
            assert rejected_results == []

            project_results = memory.retrieve(
                namespace=NAMESPACE,
                query="project scoped memory",
                project_id="aletheia",
                memory_types=["project"],
            )
            project_ids = {result.claim_id for result in project_results}
            assert project_claim.id in project_ids
            assert unrelated_project_claim.id not in project_ids

            memory.retrieve(namespace=NAMESPACE, query="stale confidence marker")
            assert memory.read_claim(stale.id).confidence_effective < 0.1
            return (
                "namespace/type/status/project filters, core ranking, "
                "confidence recompute, exclusions, provenance marked"
            )
        finally:
            memory.close()

    def case_context_markdown(self) -> str:
        markdown = self.cli(
            [
                "context",
                "--namespace",
                NAMESPACE,
                "--project",
                "aletheia",
                "--session",
                self.ids["session"],
                "--query",
                "Continue designing Aletheia",
                "--budget",
                "1200",
            ]
        ).stdout
        assert "## Memory Context" in markdown
        assert "Aletheia Memory Library" in markdown
        assert "practical and direct" in markdown
        assert "M1 Reliable Recall and Context Continuity" in markdown
        assert "claim:" in markdown
        return "markdown context includes required M1 memories"

    def case_context_json(self) -> str:
        data = json.loads(
            self.cli(
                [
                    "context",
                    "--namespace",
                    NAMESPACE,
                    "--project",
                    "aletheia",
                    "--session",
                    self.ids["session"],
                    "--query",
                    "Continue designing Aletheia",
                    "--json",
                ]
            ).stdout
        )
        all_items = (
            data["core_memory"]
            + data["project_memory"]
            + data["session_memory"]
            + data["procedural_memory"]
            + data["relevant_memory"]
        )
        assert all_items
        assert all("claim_id" in item for item in all_items)
        assert all("evidence_ids" in item for item in all_items)
        assert data["sources"]
        return f"{len(all_items)} structured context item(s)"

    def case_session_end_summary(self) -> str:
        ended = json.loads(
            self.cli(
                [
                    "sessions",
                    "end",
                    "--session",
                    self.ids["session"],
                    "--summary",
                    "Completed the M1 contract for reliable recall and context continuity.",
                ]
            ).stdout
        )
        assert ended["ended_at"]
        searched = self.cli(
            [
                "search",
                "--namespace",
                NAMESPACE,
                "--type",
                "session_summary",
                "Completed M1 contract",
            ]
        ).stdout
        assert "Completed the M1 contract" in searched
        return "session summary remembered"

    def case_cross_session_recall(self) -> str:
        next_session = json.loads(
            self.cli(
                [
                    "sessions",
                    "start",
                    "--namespace",
                    NAMESPACE,
                    "--project",
                    "aletheia",
                    "--title",
                    "M1 implementation",
                ]
            ).stdout
        )
        data = json.loads(
            self.cli(
                [
                    "context",
                    "--namespace",
                    NAMESPACE,
                    "--project",
                    "aletheia",
                    "--session",
                    next_session["id"],
                    "--query",
                    "Where did we leave off?",
                    "--json",
                ]
            ).stdout
        )
        assert any(
            "Completed the M1 contract" in item["text"]
            for item in data["session_memory"]
        )
        return "previous summary appears in new session context"

    def case_conflict_warning(self) -> str:
        self.cli(
            [
                "remember",
                "--namespace",
                NAMESPACE,
                "--type",
                "preference",
                "--subject",
                "user",
                "--predicate",
                "prefers_length",
                "--object",
                "short",
            ]
        )
        self.cli(
            [
                "remember",
                "--namespace",
                NAMESPACE,
                "--type",
                "preference",
                "--subject",
                "user",
                "--predicate",
                "prefers_length",
                "--object",
                "detailed",
            ]
        )
        data = json.loads(
            self.cli(
                [
                    "context",
                    "--namespace",
                    NAMESPACE,
                    "--project",
                    "aletheia",
                    "--query",
                    "How long should the answer be?",
                    "--json",
                ]
            ).stdout
        )
        assert any(
            warning["warning_type"] == "unresolved_conflict"
            for warning in data["warnings"]
        )
        all_text = "\n".join(
            item["text"]
            for section in [
                "core_memory",
                "project_memory",
                "session_memory",
                "procedural_memory",
                "relevant_memory",
            ]
            for item in data[section]
        )
        assert "prefers length short" not in all_text
        assert "prefers length detailed" not in all_text
        return "disputed claims moved to warnings"

    def case_project_isolation(self) -> str:
        self.cli(
            [
                "projects",
                "create",
                "--namespace",
                NAMESPACE,
                "--id",
                "other",
                "--title",
                "Other Project",
            ]
        )
        self.cli(
            [
                "remember",
                "--namespace",
                NAMESPACE,
                "--type",
                "project",
                "--subject",
                "project:other",
                "--predicate",
                "current_milestone",
                "--object",
                "Other Milestone",
                "--project",
                "other",
            ]
        )
        data = json.loads(
            self.cli(
                [
                    "context",
                    "--namespace",
                    NAMESPACE,
                    "--project",
                    "aletheia",
                    "--query",
                    "current milestone",
                    "--json",
                ]
            ).stdout
        )
        project_text = "\n".join(item["text"] for item in data["project_memory"])
        assert "Other Milestone" not in project_text
        return "other project memory excluded"

    def cli(
        self,
        args: list[str],
        *,
        include_db: bool = True,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        cmd = [sys.executable, "-m", "aletheia.cli.main", *args]
        if include_db:
            cmd = insert_db_arg(cmd, str(self.db_path))
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


def insert_db_arg(cmd: list[str], db_path: str) -> list[str]:
    return [*cmd, "--db", db_path]


def extract_id(text: str, prefix: str) -> str:
    match = re.search(rf"\b({prefix}_[A-Za-z0-9]+)\b", text)
    if not match:
        raise AssertionError(f"Could not find {prefix}_ id in output:\n{text}")
    return match.group(1)


def print_scorecard(results: list[CaseResult], db_path: Path) -> None:
    categories: dict[str, list[CaseResult]] = {}
    for result in results:
        categories.setdefault(result.category, []).append(result)
    passed = sum(1 for result in results if result.passed)
    total = len(results)
    print("\nAletheia M1 Reliable Recall Scorecard")
    print("=" * 72)
    print(f"Database: {db_path}")
    print(f"Score: {passed}/{total} ({passed / total:.0%})")
    for category, grouped in categories.items():
        category_passed = sum(1 for result in grouped if result.passed)
        print(f"\n{category} ({category_passed}/{len(grouped)})")
        print("-" * 72)
        for result in grouped:
            mark = "PASS" if result.passed else "FAIL"
            print(f"{mark:4} | {result.case}")
            print(f"     | {result.details}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Aletheia M1 live scorecard.")
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
        results = M1Runner(db_path, verbose=args.verbose).run()
        print_scorecard(results, db_path)
        return 0 if all(result.passed for result in results) else 1
    with tempfile.TemporaryDirectory(prefix="aletheia-m1-") as temp_dir:
        db_path = Path(temp_dir) / "aletheia-m1.db"
        results = M1Runner(db_path, verbose=args.verbose).run()
        print_scorecard(results, db_path)
        return 0 if all(result.passed for result in results) else 1


def create_m0_database(path: Path) -> None:
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


if __name__ == "__main__":
    raise SystemExit(main())
