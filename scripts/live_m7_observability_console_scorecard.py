"""Live M7 scorecard: operational console, observability, and human governance."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aletheia import Memory
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaService, openapi_schema


NAMESPACE = "user/default"
PROJECT = "aletheia"

REQUIRED_M7_TABLES = {
    "console_sessions",
    "console_action_confirmations",
    "review_tasks",
    "review_task_events",
    "notification_events",
    "dashboard_saved_views",
    "dashboard_preferences",
    "metric_snapshots",
    "trace_runs",
    "trace_events",
    "retrieval_trace_items",
    "context_trace_items",
    "report_exports",
}

REQUIRED_M7_ENDPOINTS = {
    "/console",
    "/console/assets/app.css",
    "/v1/console/login",
    "/v1/console/logout",
    "/v1/console/session",
    "/v1/console/actions/candidates/{candidate_id}/promote",
    "/v1/console/actions/conflicts/{conflict_id}/resolve",
    "/v1/dashboard/overview",
    "/v1/dashboard/preferences",
    "/v1/dashboard/saved-views",
    "/v1/reviews",
    "/v1/reviews/generate",
    "/v1/reviews/{review_task_id}/resolve",
    "/v1/traces/retrieval",
    "/v1/traces/context-pack",
    "/v1/metrics/snapshot",
    "/v1/metrics/latest",
    "/v1/notifications",
    "/v1/notifications/{notification_id}/dismiss",
    "/v1/reports/export",
}


@dataclass
class CaseResult:
    category: str
    case: str
    interface: str
    passed: bool
    details: str


class M7Runner:
    def __init__(self, db_path: Path, verbose: bool = False):
        self.db_path = db_path
        self.verbose = verbose
        self.results: list[CaseResult] = []
        self.ids: dict[str, str] = {}
        self.tokens: dict[str, str] = {}
        self.session_token: str | None = None
        self.csrf_token: str | None = None

    def run(self) -> list[CaseResult]:
        cases: list[tuple[str, str, str, Callable[[], str]]] = [
            ("Migration", "M6 database migrates to 1.3.0 with M7 tables and no user side effects", "API", self.case_migration),
            ("CLI", "M7 console login-token, metrics, notifications, reviews, traces, and reports commands run", "CLI", self.case_cli_groups),
            ("Console", "/console is explicitly enabled and console login creates a one-time session", "HTTP", self.case_console_enablement_login),
            ("Security", "Console session requires CSRF for writes and namespace grants are enforced", "HTTP", self.case_console_security),
            ("Dashboard", "Dashboard overview, preferences, and saved views work through console session", "HTTP", self.case_dashboard),
            ("Review", "Review tasks generate from candidates and confirmed console action resolves the task", "HTTP+API", self.case_review_action),
            ("Observability", "Retrieval/context traces and metric snapshots expose inclusion decisions", "HTTP+API", self.case_traces_metrics),
            ("Governance", "Notifications, report exports, audit confirmations, and OpenAPI coverage are present", "HTTP+API", self.case_notifications_reports_openapi),
        ]
        for category, case, interface, fn in cases:
            try:
                detail = fn()
                self.results.append(CaseResult(category, case, interface, True, detail))
            except Exception as exc:  # noqa: BLE001 - live scorecard should continue.
                self.results.append(CaseResult(category, case, interface, False, str(exc)))
        return self.results

    def case_migration(self) -> str:
        memory = Memory.open(str(self.db_path), namespace=NAMESPACE)
        try:
            health = memory.health()
            assert health["schema_version"] == "1.3.0"
            assert REQUIRED_M7_TABLES.issubset(self._tables(memory))
            assert self._count(memory, "console_sessions") == 0
            assert self._count(memory, "review_tasks") == 0
            assert self._count(memory, "report_exports") == 0
            assert self._count(memory, "dashboard_preferences") >= 2
            claim = memory.remember(
                namespace=NAMESPACE,
                memory_type="project",
                subject="aletheia",
                predicate="current_milestone",
                object="M7 Operational Console",
                project_id=PROJECT,
                confidence=0.93,
                importance=0.9,
            )
            self.ids["milestone_claim"] = claim.id
            return f"schema_version={health['schema_version']}, tables={len(REQUIRED_M7_TABLES)}, seed_claim={claim.id}"
        finally:
            memory.close()

    def case_cli_groups(self) -> str:
        login = self.cli_json(
            "console",
            "login-token",
            "--namespace",
            NAMESPACE,
            "--capabilities",
            "memory:read,memory:review,memory:admin,memory:jobs,memory:policy",
            "--privacy-ceiling",
            "secret",
        )
        self.tokens["console_login"] = login["login_token"]
        metric = self.cli_json("metrics", "snapshot", "--namespace", NAMESPACE, "--source", "live_m7_cli")
        note = self.cli_json(
            "notifications",
            "create",
            "--namespace",
            NAMESPACE,
            "--type",
            "scorecard",
            "--severity",
            "info",
            "--title",
            "M7 scorecard",
            "--message",
            "Live M7 CLI notification.",
        )
        self.ids["cli_notification"] = note["id"]
        reviews = self.cli_json("reviews", "list", "--namespace", NAMESPACE)
        traces = self.cli_json("traces", "list", "--namespace", NAMESPACE)
        reports = self.cli_json("reports", "list", "--namespace", NAMESPACE)
        assert metric["source"] == "live_m7_cli"
        assert isinstance(reviews, list)
        assert isinstance(traces, list)
        assert isinstance(reports, list)
        return f"login_token_issued, metric={metric['id']}, notification={note['id']}"

    def case_console_enablement_login(self) -> str:
        with self.open_service(console_enabled=False) as service:
            status, response = self.get(service, "/console")
            assert status == 404
            assert "not enabled" in response["_raw_body"]
        with self.open_service(console_enabled=True) as service:
            status, html = self.get(service, "/console")
            assert status == 200
            assert "Aletheia Console" in html["_raw_body"]
            status, css = self.get(service, "/console/assets/app.css")
            assert status == 200
            assert css["_content_type"].startswith("text/css")
            status, login = self.post(service, "/v1/console/login", None, {"login_token": self.tokens["console_login"]})
            assert status == 200
            assert "Set-Cookie" in login["_headers"]
            self.session_token = login["data"]["session_token"]
            self.csrf_token = login["data"]["csrf_token"]
            status, reused = self.post(service, "/v1/console/login", None, {"login_token": self.tokens["console_login"]})
            assert status == 401
            assert reused["error"]["code"] == "unauthorized"
            status, session = self.get(service, "/v1/console/session", headers=self.console_headers(csrf=False))
            assert status == 200
            assert "memory:review" in session["data"]["capabilities"]
            return f"session={login['data']['session_id']}, csrf_len={len(self.csrf_token or '')}"

    def case_console_security(self) -> str:
        with self.open_service(console_enabled=True) as service:
            status, missing_csrf = self.post(
                service,
                "/v1/metrics/snapshot",
                None,
                {"namespace": NAMESPACE, "source": "missing_csrf"},
                headers=self.console_headers(csrf=False),
            )
            assert status == 403
            status, snapshot = self.post(
                service,
                "/v1/metrics/snapshot",
                None,
                {"namespace": NAMESPACE, "source": "csrf_ok"},
                headers=self.console_headers(),
            )
            assert status == 200
        limited = self.cli_json(
            "console",
            "login-token",
            "--namespace",
            "user/other",
            "--capabilities",
            "memory:read",
        )
        with self.open_service(console_enabled=True) as service:
            status, login = self.post(service, "/v1/console/login", None, {"login_token": limited["login_token"]})
            assert status == 200
            other_headers = {"X-Console-Session": login["data"]["session_token"]}
            status, denied = self.get(service, f"/v1/dashboard/overview?namespace={NAMESPACE}", headers=other_headers)
            assert status == 403
            assert denied["error"]["code"] == "forbidden"
            return f"csrf_blocked={missing_csrf['error']['code']}, namespace_denied={denied['error']['code']}, metric={snapshot['data']['id']}"

    def case_dashboard(self) -> str:
        with self.open_service(console_enabled=True) as service:
            status, overview = self.get(service, f"/v1/dashboard/overview?namespace={NAMESPACE}", headers=self.console_headers(csrf=False))
            assert status == 200
            assert "metrics" in overview["data"]
            status, preference = self.post(
                service,
                "/v1/dashboard/preferences",
                None,
                {"namespace": NAMESPACE, "preference_key": "dashboard.layout", "value": {"density": "compact"}},
                headers=self.console_headers(),
            )
            assert status == 200
            status, created = self.post(
                service,
                "/v1/dashboard/saved-views",
                None,
                {"namespace": NAMESPACE, "name": "Open Reviews", "view_type": "reviews", "filters": {"status": "open"}},
                headers=self.console_headers(),
            )
            assert status == 200
            view_id = created["data"]["id"]
            status, views = self.get(service, f"/v1/dashboard/saved-views?namespace={NAMESPACE}", headers=self.console_headers(csrf=False))
            assert status == 200
            assert any(view["id"] == view_id for view in views["data"])
            status, deleted = self.delete(service, f"/v1/dashboard/saved-views/{view_id}?namespace={NAMESPACE}", headers=self.console_headers())
            assert status == 200
            return f"overview_metrics={len(overview['data']['metrics'])}, preference={preference['data']['preference_key']}, view_deleted={deleted['data']['deleted']}"

    def case_review_action(self) -> str:
        with self.open_service(console_enabled=True) as service:
            candidate = self.seed_candidate(service.memory)
            status, generated = self.post(
                service,
                "/v1/reviews/generate",
                None,
                {"namespace": NAMESPACE},
                headers=self.console_headers(),
            )
            assert status == 200
            task = next(item for item in generated["data"] if item["target_id"] == candidate.id)
            status, bad = self.post(
                service,
                f"/v1/console/actions/candidates/{candidate.id}/promote",
                None,
                {"reason": "Live M7 wrong confirmation.", "confirmation": "approve"},
                headers=self.console_headers(),
            )
            assert status == 400
            status, promoted = self.post(
                service,
                f"/v1/console/actions/candidates/{candidate.id}/promote",
                None,
                {"reason": "Live M7 human confirmation.", "confirmation": "promote candidate"},
                headers=self.console_headers(),
            )
            assert status == 200
            resolved = service.memory.get_review_task(task["id"])
            assert resolved.status == "resolved"
            concise = service.memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user",
                predicate="prefers_console_density",
                object="concise dashboards",
                confidence=0.9,
            )
            detailed = service.memory.remember(
                namespace=NAMESPACE,
                memory_type="preference",
                subject="user",
                predicate="prefers_console_density",
                object="comprehensive dashboards",
                confidence=0.65,
            )
            conflict = service.memory.detect_conflicts(
                namespace=NAMESPACE,
                subject="user",
                predicate="prefers_console_density",
            )[0]
            conflict_task = service.memory.create_review_task(
                NAMESPACE,
                task_type="conflict_resolution",
                title="Resolve dashboard density conflict",
                description="Two dashboard density memories conflict.",
                target_id=conflict.id,
                target_type="conflict",
                severity="high",
            )
            status, conflict_resolution = self.post(
                service,
                f"/v1/console/actions/conflicts/{conflict.id}/resolve",
                None,
                {
                    "reason": "Live M7 conflict resolution.",
                    "confirmation": "resolve conflict",
                    "strategy": "manual",
                    "active_claim_id": concise.id,
                    "superseded_claim_ids": [detailed.id],
                },
                headers=self.console_headers(),
            )
            assert status == 200
            assert conflict_resolution["data"]["conflict_id"] == conflict.id
            assert service.memory.get_review_task(conflict_task.id).status == "resolved"
            confirmations = self._count(service.memory, "console_action_confirmations")
            return f"candidate={candidate.id}, claim={promoted['data']['claim']['id']}, review_status={resolved.status}, conflict={conflict.id}, confirmations={confirmations}"

    def case_traces_metrics(self) -> str:
        with self.open_service(console_enabled=True) as service:
            archived_event = service.memory.write_event(
                namespace=NAMESPACE,
                source_type="live_m7",
                content="archived note should have omission reason",
            )
            service.memory.write_claim(
                namespace=NAMESPACE,
                memory_type="project",
                subject="aletheia",
                predicate="has_archived_console_note",
                object="archived note should have omission reason",
                evidence_ids=[archived_event.id],
                status="archived",
                confidence=0.9,
            )
            status, retrieval = self.post(
                service,
                "/v1/traces/retrieval",
                None,
                {"namespace": NAMESPACE, "query": "M7 Operational Console", "limit": 10},
                headers=self.console_headers(),
            )
            assert status == 200
            trace_id = retrieval["data"]["id"]
            assert retrieval["data"]["policy_version_id"]
            status, items = self.get(service, f"/v1/traces/{trace_id}/items", headers=self.console_headers(csrf=False))
            assert status == 200
            assert any(item["included"] for item in items["data"])
            assert any((not item["included"]) and item["omission_reason"] for item in items["data"])
            status, context = self.post(
                service,
                "/v1/traces/context-pack",
                None,
                {"namespace": NAMESPACE, "query": "M7 Operational Console", "token_budget": 900},
                headers=self.console_headers(),
            )
            assert status == 200
            status, latest = self.get(service, f"/v1/metrics/latest?namespace={NAMESPACE}", headers=self.console_headers(csrf=False))
            assert status == 200
            assert latest["data"]["metrics"]["active_claim_count"] >= 1
            request_paths = {row["path"] for row in service.service_requests(limit=50)}
            assert "/v1/traces/retrieval" in request_paths
            return f"retrieval_trace={trace_id}, retrieval_items={len(items['data'])}, context_trace={context['data']['id']}, active_claims={latest['data']['metrics']['active_claim_count']}, service_logs={len(request_paths)}"

    def case_notifications_reports_openapi(self) -> str:
        report_path = self.db_path.parent / "m7_memory_health.md"
        with self.open_service(console_enabled=True) as service:
            service.memory.write_claim(
                namespace=NAMESPACE,
                memory_type="project",
                subject="aletheia",
                predicate="has_secret_report_note",
                object="m7-secret-report-detail",
                evidence_ids=[
                    service.memory.write_event(
                        namespace=NAMESPACE,
                        source_type="live_m7",
                        content="m7-secret-report-detail",
                        privacy_level="secret",
                    ).id
                ],
            )
            notification = service.memory.create_notification(
                NAMESPACE,
                notification_type="scorecard",
                title="M7 notification",
                message="Live M7 notification.",
                severity="info",
            )
            status, notifications = self.get(service, f"/v1/notifications?namespace={NAMESPACE}", headers=self.console_headers(csrf=False))
            assert status == 200
            assert any(item["id"] == notification.id for item in notifications["data"])
            status, snoozed = self.post(
                service,
                f"/v1/notifications/{notification.id}/snooze",
                None,
                {"until": "2099-01-01T00:00:00+00:00"},
                headers=self.console_headers(),
            )
            assert status == 200
            assert snoozed["data"]["status"] == "snoozed"
            status, dismissed = self.post(
                service,
                f"/v1/notifications/{notification.id}/dismiss",
                None,
                {},
                headers=self.console_headers(),
            )
            assert status == 200
            status, report = self.post(
                service,
                "/v1/reports/export",
                None,
                {"namespace": NAMESPACE, "report_type": "memory_health", "format": "markdown", "output_path": str(report_path)},
                headers=self.console_headers(),
            )
            assert status == 200
            assert report_path.exists()
            report_text = report_path.read_text(encoding="utf-8")
            assert "# Aletheia Memory Health" in report_text
            assert "m7-secret-report-detail" not in report_text
            assert service.memory.list_trace_events(self._latest_trace_id(service.memory))
        paths = openapi_schema()["paths"]
        assert openapi_schema()["info"]["version"] == "1.3.0"
        assert REQUIRED_M7_ENDPOINTS.issubset(paths)
        return f"notification={notification.id}, dismissed={dismissed['data']['status']}, report={report['data']['id']}, openapi_paths={len(paths)}"

    def seed_candidate(self, memory: Memory):
        batch = memory.ingest(
            namespace=NAMESPACE,
            source_type="live_m7",
            content=(
                "User: For progress updates, keep it concise. "
                "User: For architecture contracts, I want comprehensive detail. "
                "User: Aletheia M7 should focus on operational observability."
            ),
            project_id=PROJECT,
        )
        memory.extract_candidates(NAMESPACE, batch_id=batch.id)
        candidates = memory.list_candidates(NAMESPACE, status="pending_review")
        assert candidates
        return candidates[0]

    def cli_json(self, *args: str):
        cmd = [sys.executable, "-m", "aletheia.cli.main", *args, "--db", str(self.db_path)]
        result = subprocess.run(cmd, cwd=ROOT, check=True, text=True, capture_output=True)
        if self.verbose and result.stderr:
            print(result.stderr, file=sys.stderr)
        return json.loads(result.stdout)

    def open_service(self, *, console_enabled: bool):
        runner = self

        class ServiceContext:
            def __enter__(self):
                self.memory = Memory.open(str(runner.db_path), namespace=NAMESPACE)
                self.service = AletheiaService(
                    self.memory,
                    ServiceConfig(
                        db_path=str(runner.db_path),
                        auto_migrate=True,
                        auth_required=True,
                        console_enabled=console_enabled,
                        rate_limit_per_minute=1000,
                    ),
                )
                return self.service

            def __exit__(self, exc_type, exc, tb):
                self.service.close()
                return False

        return ServiceContext()

    def console_headers(self, *, csrf: bool = True) -> dict[str, str]:
        assert self.session_token
        headers = {"X-Console-Session": self.session_token}
        if csrf:
            assert self.csrf_token
            headers["X-CSRF-Token"] = self.csrf_token
        return headers

    def get(self, service: AletheiaService, path: str, *, headers: dict | None = None):
        return service.handle_http(method="GET", path=path, headers=headers or {})

    def post(
        self,
        service: AletheiaService,
        path: str,
        token: str | None,
        payload: dict,
        *,
        headers: dict | None = None,
    ):
        request_headers = dict(headers or {})
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        return service.handle_http(method="POST", path=path, headers=request_headers, body=json.dumps(payload).encode("utf-8"))

    def delete(self, service: AletheiaService, path: str, *, headers: dict | None = None):
        return service.handle_http(method="DELETE", path=path, headers=headers or {})

    def _latest_trace_id(self, memory: Memory) -> str:
        traces = memory.list_traces(namespace=NAMESPACE, limit=1)
        assert traces
        return traces[0].id

    @staticmethod
    def _tables(memory: Memory) -> set[str]:
        return {
            row["name"]
            for row in memory.store.connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
            ).fetchall()
        }

    @staticmethod
    def _count(memory: Memory, table: str) -> int:
        return int(memory.store.connection.execute(f"SELECT count(*) AS count FROM {table}").fetchone()["count"])


def print_scorecard(results: list[CaseResult]) -> None:
    passed = sum(1 for result in results if result.passed)
    total = len(results)
    print("# M7 Observability Console Live Scorecard")
    print(f"Passed: {passed}/{total}")
    print()
    current = None
    for result in results:
        if result.category != current:
            current = result.category
            print(f"## {current}")
        mark = "PASS" if result.passed else "FAIL"
        print(f"- [{mark}] {result.case} ({result.interface})")
        print(f"  {result.details}")
    print()
    if passed != total:
        raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live M7 operational console checks.")
    parser.add_argument("--db")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.db:
        db_path = Path(args.db)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        runner = M7Runner(db_path, verbose=args.verbose)
        print_scorecard(runner.run())
        return 0

    with tempfile.TemporaryDirectory(prefix="aletheia-m7-live-") as temp:
        runner = M7Runner(Path(temp) / "aletheia.db", verbose=args.verbose)
        print_scorecard(runner.run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
