"""Resolve and invalidate complete content dependency graphs for deletion."""
from __future__ import annotations

from collections import deque
import json

from aletheia.core.errors import NotFoundError, ValidationError
from aletheia.core.ids import content_hash
from aletheia.core.time import utc_now_iso

TABLES = {"evidence": "evidence_events", "claim": "claims", "candidate_claim": "candidate_claims",
          "reflection": "reflections", "inference": "inference_candidates",
          "abstraction": "abstraction_records", "source_document": "source_documents"}
ALIASES = {"event": "evidence", "evidence_event": "evidence", "candidate": "candidate_claim"}


def row_for(memory, kind, value):
    kind = ALIASES.get(kind, kind)
    if kind not in TABLES:
        raise ValidationError("Unsupported deletion target.")
    row = memory.store.connection.execute("SELECT * FROM " + TABLES[kind] + " WHERE id = ?", (value,)).fetchone()
    if row is None:
        raise NotFoundError(f"{kind} not found: {value}")
    return row


def closure(memory, roots):
    db = memory.store.connection
    pending, visited, result = deque(roots), set(), []
    while pending:
        kind, value = pending.popleft()
        kind = ALIASES.get(kind, kind)
        if (kind, value) in visited:
            continue
        visited.add((kind, value))
        aliases = [kind] + [alias for alias, canonical in ALIASES.items() if canonical == kind]
        placeholders = ",".join("?" for _ in aliases)
        pending.extend(tuple(row) for row in db.execute(
            f"SELECT target_type, target_id FROM derivation_edges WHERE source_id = ? AND source_type IN ({placeholders})", [value, *aliases]))
        pending.extend(("reflection", row[0]) for row in db.execute(
            f"SELECT reflection_id FROM reflection_sources WHERE source_id = ? AND source_type IN ({placeholders})", [value, *aliases]))
        pending.extend(("abstraction", row[0]) for row in db.execute(
            f"SELECT abstraction_id FROM abstraction_sources WHERE source_id = ? AND source_type IN ({placeholders})", [value, *aliases]))
        if kind == "evidence":
            pending.extend(("claim", row[0]) for row in db.execute("SELECT claim_id FROM claim_evidence_links WHERE evidence_id = ?", (value,)))
            pending.extend(("candidate_claim", row[0]) for row in db.execute("SELECT candidate_id FROM candidate_evidence_links WHERE evidence_id = ?", (value,)))
        elif kind == "candidate_claim":
            pending.extend(("claim", row[0]) for row in db.execute("SELECT claim_id FROM candidate_claim_links WHERE candidate_id = ?", (value,)))
        elif kind == "inference":
            pending.extend(("claim", row[0]) for row in db.execute("SELECT claim_id FROM derived_claim_links WHERE inference_id = ?", (value,)))
        if kind not in TABLES:
            continue
        row = db.execute("SELECT * FROM " + TABLES[kind] + " WHERE id = ?", (value,)).fetchone()
        if row is None:
            continue
        result.append((kind, dict(row)))
        if kind == "source_document":
            pending.extend(("evidence", item[0]) for item in db.execute(
                "SELECT evidence_id FROM ingestion_batch_evidence_links WHERE batch_id = ?", (row["batch_id"],)))
    return result


def impact(memory, target_id, target_type):
    root = row_for(memory, target_type, target_id)
    nodes = closure(memory, [(target_type, target_id)])
    return root["namespace"], {
        "evidence": [row["id"] for kind, row in nodes if kind == "evidence"],
        "claims": [row["id"] for kind, row in nodes if kind == "claim"],
        "candidates": [row["id"] for kind, row in nodes if kind == "candidate_claim"],
        "reflections": [row["id"] for kind, row in nodes if kind == "reflection"],
        "inferences": [row["id"] for kind, row in nodes if kind == "inference"],
        "derived_count": max(0, len(nodes) - 1),
    }


def apply(memory, roots, *, reason, actor="user", scrub=False, replacement="[REDACTED]", include_roots=True, tombstone_roots=True):
    from aletheia.core import hardening
    db = memory.store.connection
    nodes = closure(memory, roots)
    root_set = {(ALIASES.get(kind, kind), value) for kind, value in roots}
    for kind, row in nodes:
        value, namespace = row["id"], row["namespace"]
        if not include_roots and (kind, value) in root_set:
            continue
        table = TABLES[kind]
        if kind == "claim":
            db.execute("UPDATE claims SET status = 'archived' WHERE id = ?", (value,))
            db.execute("DELETE FROM claims_fts WHERE claim_id = ?", (value,))
            if row["status"] != "archived":
                memory._write_status_history(namespace=namespace, claim_id=value, old_status=row["status"],
                    new_status="archived", reason=reason, actor=actor)
        elif kind in {"reflection", "inference", "abstraction"}:
            db.execute("UPDATE " + table + " SET status = 'stale' WHERE id = ?", (value,))
            if "updated_at" in row:
                db.execute("UPDATE " + table + " SET updated_at = ? WHERE id = ?", (utc_now_iso(), value))
        elif kind == "candidate_claim":
            db.execute("UPDATE candidate_claims SET candidate_status = 'rejected' WHERE id = ?", (value,))
        if scrub:
            fields = {
                "evidence": ("content", "source_uri"),
                "claim": ("subject", "predicate", "object"),
                "candidate_claim": ("subject", "predicate", "object"),
                "reflection": ("title", "text"),
                "inference": ("subject", "predicate", "object", "text"),
                "abstraction": ("abstraction_text",),
                "source_document": ("title", "source_uri"),
            }[kind]
            db.execute("UPDATE " + table + " SET " + ", ".join(field + " = ?" for field in fields) + " WHERE id = ?",
                       [*[replacement] * len(fields), value])
            if "metadata_json" in row:
                db.execute("UPDATE " + table + " SET metadata_json = '{}' WHERE id = ?", (value,))
            if kind in {"evidence", "source_document"}:
                db.execute("UPDATE " + table + " SET content_hash = ? WHERE id = ?", (content_hash(replacement), value))
            if kind == "evidence":
                db.execute("UPDATE evidence_spans SET span_text = ?, start_char = 0, end_char = ? WHERE evidence_id = ?", (replacement, len(replacement), value))
                db.execute("UPDATE content_risk_flags SET span_text = ?, note = ? WHERE evidence_id = ?", (replacement, replacement, value))
                db.execute("UPDATE entity_mentions SET mention_text = ? WHERE evidence_id = ?", (replacement, value))
                for run in db.execute("SELECT id, input_evidence_ids_json FROM llm_runs").fetchall():
                    if value in json.loads(run["input_evidence_ids_json"] or "[]"):
                        db.execute("UPDATE llm_outputs SET metadata_json = '{}' WHERE llm_run_id = ?", (run["id"],))
                        db.execute("UPDATE llm_runs SET metadata_json = '{}', warnings_json = '[]' WHERE id = ?", (run["id"],))
            if kind == "source_document":
                db.execute("UPDATE ingestion_batches SET title = ?, source_uri = ?, metadata_json = '{}' WHERE id = ?", (replacement, replacement, row["batch_id"]))
            if kind == "inference":
                db.execute("UPDATE inference_explanations SET explanation_text = ?, metadata_json = '{}' WHERE inference_id = ?", (replacement, value))
                db.execute("UPDATE inference_decisions SET reason = ?, edits_json = NULL WHERE inference_id = ?", (replacement, value))
            if kind == "candidate_claim":
                db.execute("UPDATE candidate_claims SET suggested_scope_json = NULL WHERE id = ?", (value,))
                db.execute("UPDATE extraction_decisions SET reason = ?, edits_json = NULL WHERE candidate_id = ?", (replacement, value))
            for trace_table in ("retrieval_trace_items", "context_trace_items"):
                db.execute("DELETE FROM " + trace_table + " WHERE target_id = ?", (value,))
            db.execute("UPDATE audit_log SET details = '{}' WHERE target_id = ?", (value,))
            db.execute("UPDATE derivation_edges SET metadata_json = '{}' WHERE source_id = ? OR target_id = ?", (value, value))
            db.execute("UPDATE review_tasks SET title = ?, description = ?, recommended_action = ?, metadata_json = '{}' WHERE target_id = ?", (replacement, replacement, replacement, value))
            # Keep structural history, but discard content snapshots and vectors.
            db.execute("DELETE FROM embeddings WHERE target_id = ?", (value,))
            if tombstone_roots or (kind, value) not in root_set:
                hardening._write_tombstone(memory, namespace=namespace, target_id=value, target_type=kind,
                    deletion_mode="redact_content", reason=reason, actor=actor, affected_derived_count=0)
        hardening._stale_semantic_for_targets(memory, namespace=namespace, target_ids=[value], reason=reason)
        memory._write_audit(namespace=namespace, target_type=kind, target_id=value,
            action="content.redact" if scrub else "derived.invalidate", details={"reason": reason})
    if scrub:
        affected = {row["id"] for kind, row in nodes if include_roots or (kind, row["id"]) not in root_set}
        for value in affected:
            db.execute("""UPDATE sync_conflicts SET metadata_json = '{}'
                WHERE local_object_id = ? OR EXISTS (
                    SELECT 1 FROM remote_memory_sources r WHERE r.local_object_id = ?
                    AND r.origin_instance_id = sync_conflicts.origin_instance_id
                    AND r.remote_object_id = sync_conflicts.remote_object_id
                    AND r.remote_object_type = sync_conflicts.remote_object_type)""", (value, value))
        # Retain the operation key as a tombstone: dropping the receipt would
        # allow a retry to perform the original mutation again.
        for cached in db.execute("SELECT id, response_json FROM idempotency_records WHERE response_json IS NOT NULL").fetchall():
            response = json.loads(cached["response_json"])
            if (affected and "_authorization" not in response) or any(value in cached["response_json"] for value in affected):
                db.execute("UPDATE idempotency_records SET response_json=NULL, status='redacted', expires_at=NULL WHERE id=?", (cached["id"],))
    return nodes


def delete_evidence(memory, value):
    # Association rows must go first; candidate links also reference spans.
    for table in ("candidate_evidence_links", "claim_evidence_links", "ingestion_batch_evidence_links",
                  "extraction_run_evidence_links", "entity_mentions", "content_risk_flags", "evidence_spans"):
        memory.store.connection.execute("DELETE FROM " + table + " WHERE evidence_id = ?", (value,))
    memory.store.connection.execute("DELETE FROM evidence_events WHERE id = ?", (value,))
