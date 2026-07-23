"""Live MVP scorecard for Aletheia.

This script exercises the v0.1 memory kernel through realistic user cases.
It uses the CLI for user-facing flows and the Python API for selected core
checks where direct state inspection is clearer than parsing command output.
"""

from __future__ import annotations

import argparse
import json
import re
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
    interface: str
    passed: bool
    details: str


class LiveRunner:
    def __init__(self, db_path: Path, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self.results: list[CaseResult] = []
        self.ids: dict[str, str] = {}

    def run(self) -> list[CaseResult]:
        cases: list[tuple[str, str, str, Callable[[], str]]] = [
            (
                "Setup and Schema",
                "Initialize SQLite database and report health",
                "CLI",
                self.case_init,
            ),
            (
                "Setup and Schema",
                "Reopen database and verify MVP tables",
                "API",
                self.case_schema_tables,
            ),
            (
                "Evidence and Claims",
                "Remember explicit preference as evidence-backed claim",
                "CLI",
                self.case_remember_preference,
            ),
            (
                "Evidence and Claims",
                "Read claim and raw evidence through core API",
                "API",
                self.case_read_claim_and_evidence,
            ),
            (
                "Retrieval",
                "Search active memory by lexical query",
                "CLI",
                self.case_search_preference,
            ),
            (
                "Claim Lifecycle",
                "List, show, and promote a claim to core",
                "CLI",
                self.case_claim_lifecycle_promote,
            ),
            (
                "Context Pack",
                "Build grouped agent-ready context",
                "CLI",
                self.case_context_pack,
            ),
            (
                "Auditability",
                "Show human-readable and JSON audit trail",
                "CLI",
                self.case_audit,
            ),
            (
                "Feedback and Confidence",
                "Confirmed feedback raises confidence and verification time",
                "API",
                self.case_feedback_confirmed,
            ),
            (
                "Feedback and Confidence",
                "Wrong feedback rejects a claim",
                "API",
                self.case_feedback_wrong,
            ),
            (
                "Feedback and Confidence",
                "Half-life decay lowers stale task memory confidence",
                "API",
                self.case_decay,
            ),
            (
                "Contradictions",
                "Detect same subject/predicate contradiction",
                "CLI",
                self.case_detect_conflict,
            ),
            (
                "Contradictions",
                "Show and resolve conflict, superseding old claim",
                "CLI",
                self.case_resolve_conflict,
            ),
            (
                "Namespaces",
                "Keep separate namespaces isolated",
                "CLI",
                self.case_namespace_isolation,
            ),
            (
                "Persistence",
                "Reopen database and retrieve resolved memory",
                "API",
                self.case_persistence,
            ),
            (
                "Negative Path",
                "Missing audit target returns a nonzero CLI error",
                "CLI",
                self.case_missing_audit_target,
            ),
        ]

        for category, case, interface, fn in cases:
            try:
                details = fn()
                self.results.append(
                    CaseResult(category, case, interface, True, details)
                )
            except Exception as exc:  # noqa: BLE001 - scorecard should continue.
                self.results.append(
                    CaseResult(category, case, interface, False, str(exc))
                )
        return self.results

    def case_init(self) -> str:
        proc = self.cli("init")
        data = json.loads(proc.stdout)
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert data["schema_version"] == "1.3.0"
        return f"schema_version={data['schema_version']}"

    def case_schema_tables(self) -> str:
        memory = Memory.open(str(self.db_path))
        try:
            rows = memory.store.connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type IN ('table', 'virtual table')
                """
            ).fetchall()
            names = {row["name"] for row in rows}
            expected = {
                "schema_version",
                "evidence_events",
                "claims",
                "claim_evidence_links",
                "audit_log",
                "conflicts",
                "conflict_claim_links",
                "feedback",
                "claims_fts",
            }
            missing = sorted(expected - names)
            assert not missing, f"missing tables: {missing}"
            return f"{len(expected)} MVP tables present"
        finally:
            memory.close()

    def case_remember_preference(self) -> str:
        proc = self.cli(
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
            "0.95",
            "--importance",
            "0.80",
        )
        claim_id = extract_id(proc.stdout, "clm")
        evidence_id = extract_id(proc.stdout, "evt")
        self.ids["preference_claim"] = claim_id
        self.ids["preference_evidence"] = evidence_id
        assert "status: active" in proc.stdout
        return f"claim={claim_id}, evidence={evidence_id}"

    def case_read_claim_and_evidence(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            claim = memory.read_claim(self.ids["preference_claim"])
            assert claim.evidence_ids == [self.ids["preference_evidence"]]
            event = memory.read_event(claim.evidence_ids[0])
            assert event.content
            assert event.namespace == NAMESPACE
            return f"{claim.id} links to {event.id}"
        finally:
            memory.close()

    def case_search_preference(self) -> str:
        proc = self.cli("search", "--namespace", NAMESPACE, "response style")
        assert self.ids["preference_claim"] in proc.stdout
        assert "practical and direct" in proc.stdout
        return "search found explicit preference"

    def case_claim_lifecycle_promote(self) -> str:
        list_proc = self.cli("claims", "list", "--namespace", NAMESPACE)
        assert self.ids["preference_claim"] in list_proc.stdout

        show_proc = self.cli("claims", "show", self.ids["preference_claim"])
        show_data = json.loads(show_proc.stdout)
        assert show_data["id"] == self.ids["preference_claim"]

        promote_proc = self.cli(
            "claims",
            "promote",
            self.ids["preference_claim"],
            "--to",
            "core",
            "--reason",
            "Stable response style preference.",
        )
        assert "status: core" in promote_proc.stdout
        return f"{self.ids['preference_claim']} promoted to core"

    def case_context_pack(self) -> str:
        self.cli(
            "remember",
            "--namespace",
            NAMESPACE,
            "--type",
            "project",
            "--subject",
            "project",
            "--predicate",
            "has_name",
            "--object",
            "Aletheia Memory Library",
            "--confidence",
            "0.85",
        )
        proc = self.cli(
            "context-pack",
            "--namespace",
            NAMESPACE,
            "Aletheia response style",
        )
        assert "## Memory Context" in proc.stdout
        assert "### Core Memory" in proc.stdout
        assert "### Project Memory" in proc.stdout
        assert "practical and direct" in proc.stdout
        assert "Aletheia Memory Library" in proc.stdout
        return "core and project memory grouped"

    def case_audit(self) -> str:
        human = self.cli("audit", self.ids["preference_claim"])
        assert "Target: claim" in human.stdout
        assert "Evidence:" in human.stdout
        assert "Audit Trail:" in human.stdout

        raw = self.cli("audit", self.ids["preference_claim"], "--json")
        data = json.loads(raw.stdout)
        assert data["claim"]["id"] == self.ids["preference_claim"]
        assert data["evidence"][0]["id"] == self.ids["preference_evidence"]
        assert any(entry["action"] == "claim.write" for entry in data["audit"])
        return "audit shows claim, evidence, and mutations"

    def case_feedback_confirmed(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            before = memory.read_claim(self.ids["preference_claim"])
            memory.feedback(
                namespace=NAMESPACE,
                target_id=before.id,
                signal="confirmed",
                note="Live scorecard confirmation.",
            )
            after = memory.read_claim(before.id)
            assert after.confidence_base > before.confidence_base
            assert after.last_verified_at is not None
            return f"confidence {before.confidence_base:.2f}->{after.confidence_base:.2f}"
        finally:
            memory.close()

    def case_feedback_wrong(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            claim = memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user",
                predicate="prefers_color_scheme",
                object="neon orange",
                confidence=0.7,
            )
            memory.feedback(
                namespace=NAMESPACE,
                target_id=claim.id,
                signal="wrong",
                note="Live scorecard rejection.",
            )
            rejected = memory.read_claim(claim.id)
            assert rejected.status == "rejected"
            return f"{claim.id} rejected"
        finally:
            memory.close()

    def case_decay(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            claim = memory.remember(
                namespace=NAMESPACE,
                memory_type="task",
                subject="task",
                predicate="has_status",
                object="temporary setup check",
                confidence=0.8,
                half_life_days=1.0,
            )
            stale_time = (datetime.now(UTC) - timedelta(days=4)).isoformat()
            with memory.store.connection:
                memory.store.connection.execute(
                    "UPDATE claims SET created_at = ?, last_verified_at = NULL WHERE id = ?",
                    (stale_time, claim.id),
                )
            memory.recompute_confidence(namespace=NAMESPACE)
            decayed = memory.read_claim(claim.id)
            assert decayed.confidence_effective < 0.1
            return f"{claim.id} decayed to {decayed.confidence_effective:.3f}"
        finally:
            memory.close()

    def case_detect_conflict(self) -> str:
        proc = self.cli(
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
            "long and highly detailed",
            "--confidence",
            "0.80",
        )
        contradiction_claim = extract_id(proc.stdout, "clm")
        self.ids["contradiction_claim"] = contradiction_claim
        assert "status: disputed" in proc.stdout

        conflicts = self.cli("conflicts", "list", "--namespace", NAMESPACE)
        conflict_id = extract_id(conflicts.stdout, "conf")
        self.ids["response_style_conflict"] = conflict_id
        assert contradiction_claim in conflicts.stdout
        assert self.ids["preference_claim"] in conflicts.stdout
        return f"conflict={conflict_id}"

    def case_resolve_conflict(self) -> str:
        shown = self.cli("conflicts", "show", self.ids["response_style_conflict"])
        data = json.loads(shown.stdout)
        assert self.ids["contradiction_claim"] in data["claim_ids"]

        resolved = self.cli(
            "conflicts",
            "resolve",
            self.ids["response_style_conflict"],
            "--active",
            self.ids["contradiction_claim"],
            "--note",
            "Use newer explicit live-test preference.",
        )
        assert "status: resolved" in resolved.stdout

        old_claim = json.loads(
            self.cli("claims", "show", self.ids["preference_claim"]).stdout
        )
        new_claim = json.loads(
            self.cli("claims", "show", self.ids["contradiction_claim"]).stdout
        )
        assert old_claim["status"] == "superseded"
        assert new_claim["status"] == "active"
        return "old claim superseded, new claim active"

    def case_namespace_isolation(self) -> str:
        self.cli(
            "remember",
            "--namespace",
            "user/other",
            "--type",
            "preference",
            "--subject",
            "user",
            "--predicate",
            "prefers_response_style",
            "--object",
            "terse bullets",
            "--confidence",
            "0.90",
        )
        own = self.cli("search", "--namespace", NAMESPACE, "terse bullets")
        other = self.cli("search", "--namespace", "user/other", "terse bullets")
        assert "terse bullets" not in own.stdout
        assert "terse bullets" in other.stdout
        return "cross-namespace search isolated"

    def case_persistence(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            claim = memory.resolve_claim(
                namespace=NAMESPACE,
                subject="user",
                predicate="prefers_response_style",
            )
            assert claim is not None
            assert claim.id == self.ids["contradiction_claim"]
            assert claim.object == "long and highly detailed"
            return f"resolved current claim={claim.id}"
        finally:
            memory.close()

    def case_missing_audit_target(self) -> str:
        proc = self.cli("audit", "clm_missing", check=False)
        assert proc.returncode != 0
        assert "Audit target not found" in proc.stderr
        return "missing target rejected"

    def cli(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        cmd = [
            sys.executable,
            "-m",
            "aletheia.cli.main",
            *args,
            "--db",
            str(self.db_path),
        ]
        # Some subcommands place --db before positional arguments. The CLI accepts
        # both command-specific styles, so normalize simple top-level commands here.
        cmd = normalize_db_arg(cmd)
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


def normalize_db_arg(cmd: list[str]) -> list[str]:
    """Move trailing --db pair into the right place for argparse subcommands."""

    if "--db" not in cmd:
        return cmd
    idx = cmd.index("--db")
    db_pair = cmd[idx : idx + 2]
    rest = cmd[:idx] + cmd[idx + 2 :]
    command = rest[3] if len(rest) > 3 else ""
    if command in {"init", "remember", "search", "context-pack"}:
        return [*rest[:4], *db_pair, *rest[4:]]
    if command == "audit":
        return [*rest[:5], *db_pair, *rest[5:]]
    if command == "claims":
        subcommand = rest[4] if len(rest) > 4 else ""
        if subcommand == "list":
            return [*rest[:5], *db_pair, *rest[5:]]
        return [*rest[:6], *db_pair, *rest[6:]]
    if command == "conflicts":
        subcommand = rest[4] if len(rest) > 4 else ""
        if subcommand == "list":
            return [*rest[:5], *db_pair, *rest[5:]]
        return [*rest[:6], *db_pair, *rest[6:]]
    return cmd


def extract_id(text: str, prefix: str) -> str:
    match = re.search(rf"\b({prefix}_[A-Za-z0-9]+)\b", text)
    if not match:
        raise AssertionError(f"Could not find {prefix}_ id in output:\n{text}")
    return match.group(1)


def print_scorecard(results: list[CaseResult], db_path: Path) -> None:
    categories: dict[str, list[CaseResult]] = {}
    for result in results:
        categories.setdefault(result.category, []).append(result)

    total = len(results)
    passed = sum(1 for result in results if result.passed)
    print("\nAletheia Live MVP Scorecard")
    print("=" * 72)
    print(f"Database: {db_path}")
    print(f"Score: {passed}/{total} ({passed / total:.0%})")

    for category, grouped in categories.items():
        cat_passed = sum(1 for result in grouped if result.passed)
        print(f"\n{category} ({cat_passed}/{len(grouped)})")
        print("-" * 72)
        for result in grouped:
            mark = "PASS" if result.passed else "FAIL"
            print(f"{mark:4} | {result.interface:3} | {result.case}")
            print(f"     |     | {result.details}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Aletheia live MVP scorecard.")
    parser.add_argument(
        "--db",
        type=Path,
        help="Optional database path. Defaults to a temporary live-test database.",
    )
    parser.add_argument(
        "--allow-existing",
        action="store_true",
        help="Allow using an existing --db path. The script will add live-test data.",
    )
    parser.add_argument("--verbose", action="store_true", help="Print every command.")
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
        runner = LiveRunner(db_path, verbose=args.verbose)
        results = runner.run()
        print_scorecard(results, db_path)
        return 0 if all(result.passed for result in results) else 1

    with tempfile.TemporaryDirectory(prefix="aletheia-live-") as temp_dir:
        db_path = Path(temp_dir) / "aletheia-live.db"
        runner = LiveRunner(db_path, verbose=args.verbose)
        results = runner.run()
        print_scorecard(results, db_path)
        return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
