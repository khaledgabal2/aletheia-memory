from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

from aletheia import Memory
from aletheia.core.ids import new_id
from aletheia.core.time import utc_now, utc_now_iso
from aletheia.models import ServiceConfig
from aletheia.service.http import AletheiaService, openapi_schema


NAMESPACE = "user/default"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _post(service: AletheiaService, path: str, payload: dict, **headers):
    request_headers = {"X-Request-ID": "req_m7_unit"}
    request_headers.update(headers)
    return service.handle_http(method="POST", path=path, headers=request_headers, body=_json(payload))


def _get(service: AletheiaService, path: str, **headers):
    request_headers = {"X-Request-ID": "req_m7_unit"}
    request_headers.update(headers)
    return service.handle_http(method="GET", path=path, headers=request_headers)


def _delete(service: AletheiaService, path: str, **headers):
    request_headers = {"X-Request-ID": "req_m7_unit"}
    request_headers.update(headers)
    return service.handle_http(method="DELETE", path=path, headers=request_headers)


def _service(tmp_path, *, console_enabled: bool = True) -> AletheiaService:
    db_path = str(tmp_path / "aletheia.db")
    memory = Memory.open(db_path, namespace=NAMESPACE)
    return AletheiaService(
        memory,
        ServiceConfig(
            db_path=db_path,
            auto_migrate=True,
            auth_required=True,
            console_enabled=console_enabled,
        ),
    )


def _issue_console_login_token(memory: Memory, *, namespaces: list[str] | None = None, capabilities: list[str] | None = None) -> str:
    raw = "alc_unit_" + new_id("tok")
    now = utc_now()
    metadata = {
        "expires_at": (now + timedelta(minutes=30)).isoformat(),
        "namespace_grants": namespaces or [NAMESPACE],
        "capabilities": capabilities or ["memory:read", "memory:review", "memory:admin", "memory:jobs", "memory:policy"],
        "privacy_ceiling": "secret",
    }
    with memory.store.connection:
        memory.store.connection.execute(
            """
            INSERT INTO console_action_confirmations (
                id, namespace, action_type, target_id, target_type,
                confirmation_text, reason, actor, created_at, metadata_json
            )
            VALUES (?, ?, 'console_login_token', NULL, NULL, ?, 'Unit console login.', 'pytest', ?, ?)
            """,
            (new_id("conf"), NAMESPACE, _hash(raw), now.isoformat(), json.dumps(metadata, sort_keys=True)),
        )
    return raw


def _login_console(service: AletheiaService) -> tuple[str, str]:
    raw = _issue_console_login_token(service.memory)
    status, envelope = _post(service, "/v1/console/login", {"login_token": raw})
    assert status == 200
    assert "Set-Cookie" in envelope["_headers"]
    return envelope["data"]["session_token"], envelope["data"]["csrf_token"]


def _seed_candidate(memory: Memory):
    batch = memory.ingest(
        namespace=NAMESPACE,
        source_type="unit",
        content=(
            "User: For progress updates, keep it concise. "
            "User: For architecture contracts, I want comprehensive detail. "
            "User: Aletheia M7 should focus on operational observability."
        ),
    )
    memory.extract_candidates(NAMESPACE, batch_id=batch.id)
    candidates = memory.list_candidates(NAMESPACE, status="pending_review")
    assert candidates
    return candidates[0]


def test_m7_migration_adds_operational_tables_without_user_side_effects(tmp_path):
    memory = Memory.open(str(tmp_path / "migrate.db"), namespace=NAMESPACE)
    try:
        health = memory.health()
        assert health["schema_version"] == "1.3.0"
        tables = {
            row["name"]
            for row in memory.store.connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
            ).fetchall()
        }
        assert {
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
        }.issubset(tables)
        assert memory.store.connection.execute("SELECT count(*) AS count FROM console_sessions").fetchone()["count"] == 0
        assert memory.store.connection.execute("SELECT count(*) AS count FROM review_tasks").fetchone()["count"] == 0
        assert memory.store.connection.execute("SELECT count(*) AS count FROM report_exports").fetchone()["count"] == 0
        assert memory.store.connection.execute("SELECT count(*) AS count FROM dashboard_preferences").fetchone()["count"] >= 2
    finally:
        memory.close()


def test_review_tasks_metrics_traces_notifications_and_reports(tmp_path):
    memory = Memory.open(str(tmp_path / "ops.db"), namespace=NAMESPACE)
    try:
        claim = memory.remember(
            namespace=NAMESPACE,
            memory_type="project",
            subject="aletheia",
            predicate="has_console_goal",
            object="observable governance",
            confidence=0.9,
            importance=0.8,
        )
        task = memory.create_review_task(
            NAMESPACE,
            task_type="stale_core_memory",
            title="Review stale memory",
            description="A core memory needs human review.",
            target_id=claim.id,
            target_type="claim",
            severity="high",
            recommended_action="Refresh or resolve.",
        )
        assert memory.list_review_tasks(NAMESPACE, status="open")[0].id == task.id
        deferred = memory.defer_review_task(task.id, reason="Waiting for user.", actor="pytest")
        assert deferred.status == "deferred"
        resolved = memory.resolve_review_task(task.id, resolution="refreshed", reason="Updated.", actor="pytest")
        assert resolved.status == "resolved"
        assert [event.event_type for event in memory.list_review_task_events(task.id)] == ["created", "deferred", "resolved"]

        retrieval_trace = memory.trace_retrieval(NAMESPACE, query="observable governance", limit=5)
        retrieval_items = memory.list_trace_items(retrieval_trace.id)
        assert retrieval_trace.trace_type == "retrieval"
        assert any(item.included for item in retrieval_items)
        context_trace = memory.trace_context_pack(NAMESPACE, query="observable governance", token_budget=800)
        assert context_trace.trace_type == "context_pack"
        assert memory.list_trace_events(context_trace.id)

        snapshot = memory.metrics_snapshot(namespace=NAMESPACE, source="unit")
        assert snapshot.metrics["active_claim_count"] >= 1
        assert memory.latest_metric_snapshot(namespace=NAMESPACE).id == snapshot.id

        notification = memory.create_notification(
            NAMESPACE,
            notification_type="review_task",
            title="Review needed",
            message="A review task is waiting.",
            severity="info",
            target_id=task.id,
            target_type="review_task",
        )
        assert notification.status == "unread"
        assert memory.dismiss_notification(notification.id).status == "dismissed"

        report_path = tmp_path / "report.md"
        report = memory.export_report(
            namespace=NAMESPACE,
            report_type="memory_health",
            format="markdown",
            output_path=str(report_path),
        )
        assert Path(report.file_path).exists()
        assert "# Aletheia Memory Health" in report_path.read_text(encoding="utf-8")
        assert memory.list_reports(namespace=NAMESPACE)[0].id == report.id
    finally:
        memory.close()


def test_console_auth_session_csrf_dashboard_and_confirmed_actions(tmp_path):
    service = _service(tmp_path, console_enabled=True)
    try:
        status, html = _get(service, "/console")
        assert status == 200
        assert html["_content_type"].startswith("text/html")
        status, css = _get(service, "/console/assets/app.css")
        assert status == 200
        assert css["_content_type"].startswith("text/css")

        session_token, csrf_token = _login_console(service)
        status, session = _get(service, "/v1/console/session", **{"X-Console-Session": session_token})
        assert status == 200
        assert "memory:review" in session["data"]["capabilities"]

        status, rejected = _post(
            service,
            "/v1/metrics/snapshot",
            {"namespace": NAMESPACE, "source": "unit"},
            **{"X-Console-Session": session_token},
        )
        assert status == 403
        assert rejected["error"]["code"] == "forbidden"

        status, snapshot = _post(
            service,
            "/v1/metrics/snapshot",
            {"namespace": NAMESPACE, "source": "unit"},
            **{"X-Console-Session": session_token, "X-CSRF-Token": csrf_token},
        )
        assert status == 200
        assert snapshot["data"]["metrics"]

        status, overview = _get(service, f"/v1/dashboard/overview?namespace={NAMESPACE}", **{"X-Console-Session": session_token})
        assert status == 200
        assert "metrics" in overview["data"]

        candidate = _seed_candidate(service.memory)
        review_task = service.memory.create_review_task(
            NAMESPACE,
            task_type="candidate_review",
            title="Review candidate",
            description="Candidate should be promoted from console.",
            target_id=candidate.id,
            target_type="candidate_claim",
        )
        status, bad_confirmation = _post(
            service,
            f"/v1/console/actions/candidates/{candidate.id}/promote",
            {"reason": "Human checked it.", "confirmation": "yes"},
            **{"X-Console-Session": session_token, "X-CSRF-Token": csrf_token},
        )
        assert status == 400

        status, promoted = _post(
            service,
            f"/v1/console/actions/candidates/{candidate.id}/promote",
            {"reason": "Human checked it.", "confirmation": "promote candidate"},
            **{"X-Console-Session": session_token, "X-CSRF-Token": csrf_token},
        )
        assert status == 200
        assert promoted["data"]["claim"]["id"]
        assert service.memory.get_review_task(review_task.id).status == "resolved"
        confirmation_count = service.memory.store.connection.execute(
            "SELECT count(*) AS count FROM console_action_confirmations WHERE action_type = 'candidate.promote'"
        ).fetchone()["count"]
        assert confirmation_count == 1

        status, logout = _post(service, "/v1/console/logout", {}, **{"X-Console-Session": session_token})
        assert status == 200
        assert logout["data"]["logged_out"] is True
        status, expired = _get(service, "/v1/console/session", **{"X-Console-Session": session_token})
        assert status == 401
    finally:
        service.close()


def test_dashboard_saved_views_delete_and_openapi_include_m7_paths(tmp_path):
    service = _service(tmp_path, console_enabled=True)
    try:
        session_token, csrf_token = _login_console(service)
        headers = {"X-Console-Session": session_token, "X-CSRF-Token": csrf_token}
        status, created = _post(
            service,
            f"/v1/dashboard/saved-views?namespace={NAMESPACE}",
            {"namespace": NAMESPACE, "name": "Review Queue", "view_type": "reviews", "filters": {"status": "open"}},
            **headers,
        )
        assert status == 200
        view_id = created["data"]["id"]
        status, views = _get(service, f"/v1/dashboard/saved-views?namespace={NAMESPACE}", **{"X-Console-Session": session_token})
        assert status == 200
        assert any(view["id"] == view_id for view in views["data"])
        status, deleted = _delete(service, f"/v1/dashboard/saved-views/{view_id}?namespace={NAMESPACE}", **headers)
        assert status == 200
        assert deleted["data"]["deleted"] == view_id

        paths = openapi_schema()["paths"]
        assert openapi_schema()["info"]["version"] == "1.3.0"
        assert "/v1/dashboard/overview" in paths
        assert "/v1/reviews/{review_task_id}/resolve" in paths
        assert "/v1/traces/retrieval" in paths
        assert "/v1/metrics/latest" in paths
        assert "/v1/reports/export" in paths
    finally:
        service.close()


def test_console_static_requires_explicit_enablement(tmp_path):
    service = _service(tmp_path, console_enabled=False)
    try:
        status, response = _get(service, "/console")
        assert status == 404
        assert "not enabled" in response["_raw_body"]
    finally:
        service.close()
