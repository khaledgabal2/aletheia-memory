"""Live v0.1 polish scorecard for Aletheia.

This complements live_mvp_scorecard.py. It focuses on the polished terminal
surface added after the MVP foundation: evidence inspection, feedback commands,
filtered search, JSON context output, and CLI error handling.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = "user/default"


@dataclass
class CaseResult:
    category: str
    case: str
    passed: bool
    details: str


class PolishRunner:
    def __init__(self, db_path: Path, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self.ids: dict[str, str] = {}
        self.results: list[CaseResult] = []

    def run(self) -> list[CaseResult]:
        cases: list[tuple[str, str, Callable[[], str]]] = [
            (
                "Command Surface",
                "CLI help exposes feedback and events commands",
                self.case_help_surface,
            ),
            (
                "Command Surface",
                "Initialize v0.1 database",
                self.case_init,
            ),
            (
                "Evidence CLI",
                "Remember a claim and inspect its evidence event",
                self.case_events_list_show,
            ),
            (
                "Feedback CLI",
                "Confirmed feedback raises confidence through CLI",
                self.case_feedback_confirmed,
            ),
            (
                "Feedback CLI",
                "Wrong feedback rejects a claim through CLI",
                self.case_feedback_wrong,
            ),
            (
                "Filtered Retrieval",
                "Search by memory type",
                self.case_search_type_filter,
            ),
            (
                "Filtered Retrieval",
                "Rejected memory remains excluded from retrieval",
                self.case_search_status_filter,
            ),
            (
                "Context JSON",
                "Context pack JSON includes grouped memory and sources",
                self.case_context_json,
            ),
            (
                "Audit CLI",
                "Audit raw evidence as a first-class target",
                self.case_audit_evidence,
            ),
            (
                "Negative Path",
                "Invalid feedback signal fails with CLI validation",
                self.case_invalid_feedback_signal,
            ),
        ]
        for category, case, fn in cases:
            try:
                self.results.append(CaseResult(category, case, True, fn()))
            except Exception as exc:  # noqa: BLE001 - keep the scorecard running.
                self.results.append(CaseResult(category, case, False, str(exc)))
        return self.results

    def case_help_surface(self) -> str:
        proc = self.cli("--help", include_db=False)
        assert "feedback" in proc.stdout
        assert "events" in proc.stdout
        assert "context-pack" in proc.stdout
        return "help lists polished v0.1 commands"

    def case_init(self) -> str:
        proc = self.cli("init")
        data = json.loads(proc.stdout)
        assert data["schema_version"] == "1.3.0"
        return "database initialized"

    def case_events_list_show(self) -> str:
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
            "clear and practical",
            "--confidence",
            "0.82",
            "--importance",
            "0.80",
        )
        claim_id = extract_id(proc.stdout, "clm")
        event_id = extract_id(proc.stdout, "evt")
        self.ids["preference_claim"] = claim_id
        self.ids["preference_event"] = event_id

        listed = self.cli("events", "list", "--namespace", NAMESPACE)
        assert event_id in listed.stdout
        assert "manual" in listed.stdout

        shown = self.cli("events", "show", event_id, "--json")
        data = json.loads(shown.stdout)
        assert data["id"] == event_id
        assert data["namespace"] == NAMESPACE
        assert data["source_type"] == "manual"
        return f"event={event_id}, claim={claim_id}"

    def case_feedback_confirmed(self) -> str:
        before = json.loads(
            self.cli("claims", "show", self.ids["preference_claim"]).stdout
        )
        self.cli(
            "feedback",
            self.ids["preference_claim"],
            "--namespace",
            NAMESPACE,
            "--signal",
            "confirmed",
            "--note",
            "Confirmed during polish live test.",
        )
        after = json.loads(
            self.cli("claims", "show", self.ids["preference_claim"]).stdout
        )
        assert after["confidence_base"] > before["confidence_base"]
        assert after["last_verified_at"] is not None
        return f"{before['confidence_base']:.2f}->{after['confidence_base']:.2f}"

    def case_feedback_wrong(self) -> str:
        proc = self.cli(
            "remember",
            "--namespace",
            NAMESPACE,
            "--type",
            "preference",
            "--subject",
            "user",
            "--predicate",
            "prefers_color_scheme",
            "--object",
            "neon orange",
            "--confidence",
            "0.70",
        )
        claim_id = extract_id(proc.stdout, "clm")
        self.ids["rejected_claim"] = claim_id
        rejected = self.cli(
            "feedback",
            claim_id,
            "--namespace",
            NAMESPACE,
            "--signal",
            "wrong",
        )
        assert "status: rejected" in rejected.stdout
        return f"{claim_id} rejected"

    def case_search_type_filter(self) -> str:
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
            "Aletheia Polish",
        )
        self.cli(
            "remember",
            "--namespace",
            NAMESPACE,
            "--type",
            "procedure",
            "--subject",
            "assistant",
            "--predicate",
            "uses_workflow",
            "--object",
            "Aletheia review checklist",
        )
        project_search = self.cli(
            "search",
            "--namespace",
            NAMESPACE,
            "--type",
            "project",
            "Aletheia",
        )
        assert "type: project" in project_search.stdout
        assert "type: procedure" not in project_search.stdout
        return "project filter excluded procedure memory"

    def case_search_status_filter(self) -> str:
        default_search = self.cli("search", "--namespace", NAMESPACE, "neon orange")
        assert "No memories found." in default_search.stdout

        rejected_search = self.cli(
            "search",
            "--namespace",
            NAMESPACE,
            "--status",
            "rejected",
            "neon orange",
        )
        assert "No memories found." in rejected_search.stdout

        shown = self.cli("claims", "show", self.ids["rejected_claim"])
        data = json.loads(shown.stdout)
        assert data["status"] == "rejected"
        return "rejected memory hidden from retrieval, inspectable as a claim"

    def case_context_json(self) -> str:
        self.cli(
            "claims",
            "promote",
            self.ids["preference_claim"],
            "--to",
            "core",
            "--reason",
            "Stable live-test preference.",
        )
        proc = self.cli(
            "context-pack",
            "--namespace",
            NAMESPACE,
            "--json",
            "Aletheia response style",
        )
        data = json.loads(proc.stdout)
        assert any("clear and practical" in item["text"] for item in data["core_memory"])
        assert data["sources"]
        assert self.ids["preference_event"] in data["sources"]
        return "JSON context includes core memory and sources"

    def case_audit_evidence(self) -> str:
        proc = self.cli("audit", self.ids["preference_event"], "--json")
        data = json.loads(proc.stdout)
        assert data["target_type"] == "evidence"
        assert data["evidence"]["id"] == self.ids["preference_event"]
        assert any(entry["action"] == "event.write" for entry in data["audit"])
        return "event audit includes evidence write"

    def case_invalid_feedback_signal(self) -> str:
        proc = self.cli(
            "feedback",
            self.ids["preference_claim"],
            "--namespace",
            NAMESPACE,
            "--signal",
            "self_repeated",
            check=False,
        )
        assert proc.returncode != 0
        assert "invalid choice" in proc.stderr
        return "invalid signal rejected"

    def cli(
        self,
        *args: str,
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
    command = cmd[3] if len(cmd) > 3 else ""
    db_pair = ["--db", db_path]
    if command in {"init", "remember", "search", "context-pack", "feedback"}:
        return [*cmd[:4], *db_pair, *cmd[4:]]
    if command == "audit":
        return [*cmd[:5], *db_pair, *cmd[5:]]
    if command == "claims":
        subcommand = cmd[4] if len(cmd) > 4 else ""
        if subcommand == "list":
            return [*cmd[:5], *db_pair, *cmd[5:]]
        return [*cmd[:6], *db_pair, *cmd[6:]]
    if command == "conflicts":
        subcommand = cmd[4] if len(cmd) > 4 else ""
        if subcommand == "list":
            return [*cmd[:5], *db_pair, *cmd[5:]]
        return [*cmd[:6], *db_pair, *cmd[6:]]
    if command == "events":
        subcommand = cmd[4] if len(cmd) > 4 else ""
        if subcommand == "list":
            return [*cmd[:5], *db_pair, *cmd[5:]]
        return [*cmd[:6], *db_pair, *cmd[6:]]
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
    passed = sum(1 for result in results if result.passed)
    total = len(results)

    print("\nAletheia v0.1 Polish Scorecard")
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
    parser = argparse.ArgumentParser(
        description="Run Aletheia v0.1 polish live scorecard."
    )
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
        results = PolishRunner(db_path, verbose=args.verbose).run()
        print_scorecard(results, db_path)
        return 0 if all(result.passed for result in results) else 1

    with tempfile.TemporaryDirectory(prefix="aletheia-polish-") as temp_dir:
        db_path = Path(temp_dir) / "aletheia-polish.db"
        results = PolishRunner(db_path, verbose=args.verbose).run()
        print_scorecard(results, db_path)
        return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
