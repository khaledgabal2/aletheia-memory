"""Scoped HTTP read views. Embedded APIs remain trusted local interfaces.

Visibility is evaluated from stored provenance, never from a caller-supplied
project label. Instances are request-local; grants and data are not cached across
requests. Unknown, removed, or incomplete provenance fails closed.
"""

from dataclasses import asdict, replace

from aletheia.core.errors import NotFoundError
from aletheia.core.ids import new_id
from aletheia.core.time import utc_now_iso
from aletheia.service.errors import ServiceError, forbidden, not_found
from aletheia.service.auth import PRIVACY_ORDER


READ_POST_PATHS = {"/v1/retrieve", "/v1/search", "/v1/context-pack", "/v1/context"}


def is_read_path(path):
    return (path in READ_POST_PATHS or path == "/v1/dashboard/overview"
            or path.startswith(("/v1/claims/", "/v1/audit/", "/v1/candidates/"))
            or path == "/v1/candidates")


class ReadAccess:
    def __init__(self, service, context):
        self.service, self.memory, self.auth, self.context = service, service.memory, service.auth, context
        self.db = self.memory.store.connection
        self.checked = {}
        self.visiting = set()

    def capability(self, name):
        return name in self.context.capabilities or "memory:admin" in self.context.capabilities

    def namespace(self, namespace, projects=()):
        for project in [None, *projects]:
            try:
                self.auth.require_namespace(self.context, namespace=namespace, project_id=project)
                return True
            except ServiceError:
                pass
        return False

    def removed(self, target_id):
        return self.db.execute("SELECT 1 FROM deletion_tombstones WHERE target_id = ? LIMIT 1", (target_id,)).fetchone() is not None

    def projects(self, claim_id):
        return [row[0] for row in self.db.execute(
            "SELECT p.project_id FROM project_claim_links p JOIN claims c ON c.id = p.claim_id WHERE c.id = ? AND p.namespace = c.namespace", (claim_id,))]

    def evidence(self, evidence_id):
        row = self.db.execute("SELECT * FROM evidence_events WHERE id = ?", (evidence_id,)).fetchone()
        if row is None or self.removed(evidence_id) or row["privacy_level"] not in PRIVACY_ORDER or not self.auth.privacy_allows(self.context, row["privacy_level"]):
            return False
        projects = [item[0] for item in self.db.execute("""
            SELECT b.project_id FROM ingestion_batches b
            JOIN ingestion_batch_evidence_links l ON l.batch_id = b.id
            WHERE l.evidence_id = ? AND b.namespace = ? AND b.project_id IS NOT NULL
            UNION SELECT project_id FROM sessions WHERE id = ? AND namespace = ? AND project_id IS NOT NULL
        """, (evidence_id, row["namespace"], row["session_id"], row["namespace"]))]
        if not projects:
            projects = [item[0] for item in self.db.execute("""
                SELECT p.project_id FROM project_claim_links p
                JOIN claim_evidence_links l ON l.claim_id = p.claim_id
                WHERE l.evidence_id = ? AND p.namespace = ?
            """, (evidence_id, row["namespace"]))]
        removed_source = self.db.execute("""
            SELECT 1 FROM ingestion_batch_evidence_links l
            JOIN source_documents d ON d.batch_id = l.batch_id
            JOIN deletion_tombstones t ON t.target_id = d.id
            WHERE l.evidence_id = ? LIMIT 1
        """, (evidence_id,)).fetchone()
        return not removed_source and self.namespace(row["namespace"], projects)

    def evidence_set(self, ids):
        return all(self.allowed("evidence", item) for item in ids) if ids else self.auth.privacy_allows(self.context, "personal")

    def allowed(self, kind, target_id):
        kind = {"candidate": "candidate_claim", "event": "evidence"}.get(kind, kind)
        key = kind, target_id
        if key in self.checked:
            return self.checked[key]
        if key in self.visiting or len(self.visiting) >= 64 or self.removed(target_id):
            return False
        self.visiting.add(key)
        try:
            result = self._allowed(kind, target_id)
        except NotFoundError:
            result = False
        finally:
            self.visiting.remove(key)
        self.checked[key] = bool(result)
        return bool(result)

    def _allowed(self, kind, target_id):
        if kind == "evidence":
            return self.evidence(target_id)
        if kind == "claim":
            claim = self.memory.read_claim(target_id)
            if not self.namespace(claim.namespace, self.projects(target_id)) or not self.evidence_set(claim.evidence_ids):
                return False
            parents = self.db.execute("SELECT inference_id FROM derived_claim_links WHERE claim_id = ?", (target_id,))
            return all(self.allowed("inference", row[0]) for row in parents)
        if kind == "candidate_claim":
            item = self.memory.read_candidate(target_id)
            return (self.capability("memory:review") and item.privacy_level in PRIVACY_ORDER and self.auth.privacy_allows(self.context, item.privacy_level)
                    and self.namespace(item.namespace, [self.memory._project_id_for_candidate(item)])
                    and self.evidence_set(item.evidence_ids))
        if kind in {"inference", "reflection"}:
            if kind == "inference":
                item = self.memory.read_inference(target_id)
                project = self.memory.read_inference_run(item.inference_run_id).project_id
                parents = [("claim", value) for value in item.source_claim_ids]
                parents += [("candidate_claim", value) for value in item.source_candidate_ids]
                parents += [("evidence", value) for value in item.source_evidence_ids]
            else:
                item = self.memory.get_reflection(target_id)
                project = item.project_id
                parents = [(row["source_type"], row["source_id"]) for row in self.db.execute(
                    "SELECT source_type, source_id FROM reflection_sources WHERE reflection_id = ?", (target_id,))]
            return (self.namespace(item.namespace, [project]) and bool(parents)
                    and all(self.allowed(source, value) for source, value in parents))
        if kind in {"conflict", "conflict_family"}:
            item = self.memory.read_conflict_family(target_id) if kind == "conflict_family" else self.memory.read_conflict(target_id)
            return bool(item.claim_ids) and all(self.allowed("claim", value) for value in item.claim_ids)
        return False

    def require(self, kind, target_id):
        # Keep capability failures distinct; do not disclose a denied resource's contents.
        if kind in {"candidate", "candidate_claim"}:
            self.auth.require_capability(self.context, "memory:review")
        table = {"claim": "claims", "candidate": "candidate_claims", "candidate_claim": "candidate_claims",
                 "evidence": "evidence_events", "event": "evidence_events"}.get(kind)
        if table is None or not self.db.execute(f"SELECT 1 FROM {table} WHERE id = ?", (target_id,)).fetchone():
            raise not_found("Read target not found.")
        if not self.allowed(kind, target_id):
            raise forbidden("Read target is unavailable under the current access policy.")

    def conflicts(self, conflicts):
        return [item for item in conflicts if item["claim_ids"]
                and all(self.allowed("claim", value) for value in item["claim_ids"])]

    def explanation(self, claim_id):
        self.require("claim", claim_id)
        data = asdict(self.memory.explain_claim(claim_id))
        data["conflicts"] = self.conflicts(data["conflicts"])
        data["relationships"] = [item for item in data["relationships"]
                                 if self.allowed("claim", item["source_claim_id"]) and self.allowed("claim", item["target_claim_id"])]
        # Audit/history are separately permissioned. Their free-form details have
        # no privacy label, so expose structural history with explicit redaction.
        data["audit"] = self.audit_rows(data["audit"]) if self.capability("memory:audit") else []
        data["history"] = [{**row, "reason": "[REDACTED]"} for row in data["history"]] if self.capability("memory:audit") else []
        return data

    def audit_rows(self, rows):
        return [{**row, "details": "{}"} for row in rows
                if self.namespace(row["namespace"]) or self.allowed(row["target_type"], row["target_id"])]

    def audit(self, kind, target_id):
        self.require(kind, target_id)
        data = self.memory.audit(target_id)
        data["requested_target_type"] = kind
        data["audit"] = self.audit_rows(data["audit"])
        if "conflicts" in data:
            data["conflicts"] = self.conflicts(data["conflicts"])
        if "claim_links" in data:
            data["claim_links"] = [row for row in data["claim_links"] if self.allowed("claim", row["claim_id"])]
            data["decisions"] = [{**row, "reason": "[REDACTED]", "edits_json": None} for row in data["decisions"]]
        return data

    def filter_context(self, pack):
        omitted = 0
        def visible(items):
            nonlocal omitted
            result = []
            for item in items:
                kind = "reflection" if item.reflection_id else "inference" if item.inference_id else "claim"
                target = item.reflection_id or item.inference_id or item.claim_id
                if self.allowed(kind, target) and self.evidence_set(item.evidence_ids):
                    # Derivation graphs contain unclassified metadata and unrelated
                    # branches. The read profile promises source provenance only.
                    result.append(replace(item, derivation=None))
                else:
                    omitted += 1
            return result
        fields = {name: visible(getattr(pack, name)) for name in (
            "core_memory", "project_memory", "session_memory", "procedural_memory", "reflection_memory", "relevant_memory")}
        warnings = [item for item in pack.warnings if item.warning_type == "unresolved_conflict"
                    and item.claim_ids and all(self.allowed("claim", value) for value in item.claim_ids)
                    and all(self.allowed("conflict", value) for value in item.conflict_ids)]
        # Omitted IDs and warning text must not become a secondary read channel.
        dropped = [item for item in pack.omitted if self.allowed("claim", item.claim_id)]
        metadata = {**pack.metadata,
                    "included_item_ids": [item.claim_id for items in fields.values() for item in items],
                    "omitted_item_ids": [item.claim_id for item in dropped]}
        return replace(pack, **fields, warnings=warnings, omitted=dropped, metadata=metadata), omitted

    def overview(self, namespace, project_id=None):
        claims = [self.memory.read_claim(row[0]) for row in self.db.execute(
            "SELECT id FROM claims WHERE namespace = ? ORDER BY created_at DESC, id", (namespace,))]
        claims = [item for item in claims if self.allowed("claim", item.id)
                  and (project_id is None or project_id in self.projects(item.id))]
        visible_ids = {item.id for item in claims}
        review = self.capability("memory:review")
        candidates = self.memory.list_candidates(namespace, limit=2147483647, project_id=project_id) if review else []
        candidates = [item for item in candidates if self.allowed("candidate_claim", item.id)]
        conflicts = [item for item in self.memory.list_conflict_families(namespace=namespace, status="unresolved", limit=2147483647)
                     if item.claim_ids and set(item.claim_ids) <= visible_ids]
        tasks = self.memory.list_review_tasks(namespace=namespace, status="open", limit=2147483647) if review else []
        tasks = [item for item in tasks if self.allowed(item.target_type, item.target_id)
                 and (project_id is None or item.target_id in visible_ids or item.target_id in {c.id for c in candidates})]
        metrics = {
            "active_claim_count": sum(item.status == "active" for item in claims),
            "core_memory_count": sum(item.status == "core" for item in claims),
            "stale_claim_count": sum(item.status in {"disputed", "archived"} for item in claims),
            "candidate_count": len(candidates) if review else None,
            "pending_review_count": sum(item.candidate_status == "pending_review" for item in candidates) if review else None,
            "unresolved_conflict_count": len(conflicts),
            "open_review_task_count": len(tasks) if review else None,
            "critical_review_task_count": sum(item.severity == "critical" for item in tasks) if review else None,
            "project_id": project_id,
        }
        # Keep optional sections explicit. Operational payloads have no per-record
        # privacy classification and are unavailable through this read view.
        return {
            "metrics": metrics,
            "health": {"id": new_id("health_view"), "namespace": namespace, "project_id": project_id,
                       "generated_at": utc_now_iso(), "metrics": metrics, "warnings": [], "recommendations": []},
            "review_tasks": [{**asdict(item), "metadata": {}} for item in tasks[:10]],
            "candidates": [asdict(item) for item in candidates if item.candidate_status == "pending_review"][:10],
            "conflicts": [asdict(item) for item in conflicts[:10]], "jobs": [], "service_requests": [],
            "unavailable_sections": ["jobs", "service_requests"] + ([] if review else ["review_tasks", "candidates"]),
        }
