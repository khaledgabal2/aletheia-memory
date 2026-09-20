"""Import evidence and claims with explicit, durable source identity mappings."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from aletheia.core import hardening as storage
from aletheia.core.errors import ValidationError
from aletheia.core.ids import content_hash, new_id
from aletheia.core.time import utc_now_iso
from aletheia.models import ImportRun


def _key(kind, row, namespace):
    return kind, row["namespace"], row["id"], namespace or row["namespace"]


def _rows(payload):
    tables = ("evidence_events", "claims", "claim_evidence_links", "derivation_edges", "deletion_tombstones")
    if "database.sqlite" not in payload:
        return {table: storage._jsonl_rows(payload.get("logical/" + table + ".jsonl", b"")) for table in tables}
    with tempfile.TemporaryDirectory(prefix="aletheia-import-") as temp:
        path = Path(temp) / "source.sqlite"
        path.write_bytes(payload["database.sqlite"])
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA trusted_schema = OFF")
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            return {table: [dict(row) for row in connection.execute("SELECT * FROM " + table)] if table in names else [] for table in tables}
        finally:
            connection.close()


def _index(rows):
    result = {}
    for row in rows:
        if any(not isinstance(row.get(field), str) or not row[field] for field in ("id", "namespace")):
            raise ValidationError("Archive objects require source IDs and namespaces.")
        if row["id"] in result:
            raise ValidationError("Archive contains duplicate source IDs.")
        result[row["id"]] = row
    return result


def _previous_mappings(memory):
    result = {}
    for run in memory.store.connection.execute("SELECT metadata_json FROM import_runs WHERE dry_run = 0 AND status = 'completed' ORDER BY rowid"):
        for item in json.loads(run[0] or "{}").get("source_mappings", []):
            result[tuple(item["source_key"])] = item
    return result


def _guard_legacy_imports(memory, claims, evidence, namespace, previous, manifest_id):
    """Old imports did not retain enough identity/provenance to repair safely."""
    message = "Historical archive import lacks source mappings; review its provenance before reimporting."
    legacy_namespaces = set()
    for run in memory.store.connection.execute(
        "SELECT target_namespace, metadata_json FROM import_runs WHERE dry_run = 0 AND status = 'completed'"
    ):
        metadata = json.loads(run["metadata_json"] or "{}")
        if "source_mappings" not in metadata:
            legacy_namespaces.add(run["target_namespace"])
        if ("source_mappings" not in metadata and metadata.get("manifest_id") == manifest_id
                and run["target_namespace"] == namespace):
            raise ValidationError(message)
    for audit in memory.store.connection.execute(
        "SELECT namespace, details FROM audit_log WHERE action = 'import.claim_as_candidate'"
    ):
        source_id = json.loads(audit["details"] or "{}").get("source_claim_id")
        source = claims.get(source_id)
        if source and audit["namespace"] == (namespace or source["namespace"]):
            if _key("claim", source, namespace) not in previous:
                raise ValidationError(message)
    for source in evidence.values():
        legacy_scope = None in legacy_namespaces or (namespace or source["namespace"]) in legacy_namespaces
        if legacy_scope and _key("evidence", source, namespace) not in previous and memory.store.connection.execute(
            "SELECT 1 FROM evidence_events WHERE id = ?", (source["id"],)
        ).fetchone():
            raise ValidationError(message)


def _sources(claim_id, claims, evidence, links, parents):
    found, seen, pending = set(), set(), [("claim", claim_id)]
    while pending:
        kind, value = pending.pop()
        kind = {"event": "evidence", "evidence_event": "evidence"}.get(kind, kind)
        if (kind, value) in seen:
            continue
        seen.add((kind, value))
        if kind == "evidence":
            if value not in evidence:
                raise ValidationError("Archive claim references missing evidence.")
            found.add(value)
            continue
        direct = links.get(value, []) if kind == "claim" else []
        incoming = parents.get((kind, value), [])
        if kind == "claim" and value not in claims:
            raise ValidationError("Archive contains incomplete claim provenance.")
        if not direct and not incoming:
            raise ValidationError("Archive contains incomplete derived provenance.")
        pending.extend(("evidence", item) for item in direct)
        pending.extend(incoming)
    if not found:
        raise ValidationError("Archive claims must retain evidence provenance.")
    if any(evidence[value]["namespace"] != claims[claim_id]["namespace"] for value in found):
        raise ValidationError("Archive claim evidence belongs to a different namespace.")
    return sorted(found)


def import_into(memory, *, input_path, namespace, dry_run, passphrase):
    if namespace is not None and (not isinstance(namespace, str) or not namespace.strip()):
        raise ValidationError("An import namespace must be a nonempty string.")
    started = utc_now_iso()
    status, warnings, manifest, payload = storage.verify_backup_file(backup_path=input_path, passphrase=passphrase, deep=True)
    if status == "failed":
        raise ValidationError("Import source verification failed: " + "; ".join(warnings))
    if manifest.get("privacy_mode") not in {"full", "namespace_filtered"}:
        raise ValidationError("Redacted or metadata-only archives cannot restore content or provenance; use a full archive.")
    tables = _rows(payload)
    evidence = _index(tables["evidence_events"])
    claims = _index(tables["claims"])
    if not evidence and not claims and not tables["deletion_tombstones"]:
        raise ValidationError("Archive contains no importable evidence or claims.")
    links, parents = {}, {}
    for row in tables["claim_evidence_links"]:
        if row["claim_id"] not in claims or row["evidence_id"] not in evidence:
            raise ValidationError("Archive contains a dangling evidence link.")
        links.setdefault(row["claim_id"], []).append(row["evidence_id"])
    for row in tables["derivation_edges"]:
        parents.setdefault((row["target_type"], row["target_id"]), []).append((row["source_type"], row["source_id"]))
    deleted = {({"event": "evidence", "evidence_event": "evidence"}.get(row["target_type"], row["target_type"]),
                row["namespace"], row["target_id"]) for row in tables["deletion_tombstones"]}
    previous = _previous_mappings(memory)
    _guard_legacy_imports(memory, claims, evidence, namespace, previous, manifest.get("id"))
    mappings, local_evidence, blocked_sources = [], {}, set()
    imported = {"evidence": 0, "claims": 0}
    skipped = {"duplicate_evidence": 0, "duplicate_claims": 0, "deleted_sources": 0}

    def prior(kind, row, source_hash):
        key = _key(kind, row, namespace)
        mapped = previous.get(key)
        if mapped:
            removed = memory.store.connection.execute("SELECT 1 FROM deletion_tombstones WHERE target_id = ?", (mapped["local_id"],)).fetchone()
            if removed:
                return mapped, True
            if mapped["source_hash"] != source_hash:
                raise ValidationError("Previously imported source changed; review it before importing a replacement.")
            table = "evidence_events" if kind == "evidence" else "claims"
            local = memory.store.connection.execute("SELECT namespace FROM " + table + " WHERE id = ?", (mapped["local_id"],)).fetchone()
            if local is None or local[0] != key[3]:
                raise ValidationError("Imported source mapping no longer matches its local object.")
        return mapped, False

    # Source tombstones apply only to objects previously mapped from this source,
    # never to an unrelated local object that happens to have the same ID.
    for tombstone in tables["deletion_tombstones"]:
        kind, source_id = tombstone["target_type"], tombstone["target_id"]
        kind = {"event": "evidence", "evidence_event": "evidence"}.get(kind, kind)
        for key, mapped in previous.items():
            if key[0] != kind or key[1] != tombstone.get("namespace") or key[2] != source_id or (namespace is not None and key[3] != namespace):
                continue
            if not dry_run and not memory.store.connection.execute("SELECT 1 FROM deletion_tombstones WHERE target_id = ?", (mapped["local_id"],)).fetchone():
                storage.redact(memory, target_id=mapped["local_id"], target_type=kind,
                               reason="Imported source tombstone", actor="archive_import", dry_run=False)

    for source in evidence.values():
        if ("evidence", source["namespace"], source["id"]) in deleted:
            blocked_sources.add(source["id"])
            skipped["deleted_sources"] += 1
            continue
        privacy = source.get("privacy_level")
        if privacy not in storage.PRIVACY_ORDER:
            raise ValidationError("Archive evidence requires a valid privacy label.")
        if not isinstance(source.get("content"), str) or not source["content"]:
            raise ValidationError("Archive evidence content is missing.")
        plaintext = storage.reveal_content_from_storage(memory, source["content"])
        normalized = {**source, "content": plaintext}
        digest = content_hash(json.dumps(normalized, sort_keys=True))
        mapped, removed = prior("evidence", source, digest)
        if removed:
            blocked_sources.add(source["id"])
            skipped["deleted_sources"] += 1
            continue
        if mapped:
            local_evidence[source["id"]] = mapped["local_id"]
            skipped["duplicate_evidence"] += 1
            continue
        key = _key("evidence", source, namespace)
        local_id = new_id("evt")
        # No content-hash deduplication: identical bytes may have different
        # privacy, provenance, or ownership.
        if not dry_run:
            memory.store.connection.execute(
                """INSERT INTO evidence_events (id, namespace, session_id, source_type, source_uri, content,
                   content_hash, created_at, observed_at, trust_level, privacy_level, retention_policy)
                   VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (local_id, key[3], source.get("source_type", "imported"), source.get("source_uri"),
                 storage.protect_content_for_storage(memory, plaintext, privacy_level=privacy), content_hash(plaintext),
                 source.get("created_at") or started, source.get("observed_at"), "imported",
                 privacy, source.get("retention_policy", "default")))
        local_evidence[source["id"]] = local_id
        mappings.append({"source_key": list(key), "local_id": local_id, "source_hash": digest})
        imported["evidence"] += 1

    for source in claims.values():
        if ("claim", source["namespace"], source["id"]) in deleted:
            skipped["deleted_sources"] += 1
            continue
        source_ids = _sources(source["id"], claims, evidence, links, parents)
        if set(source_ids) & blocked_sources:
            skipped["deleted_sources"] += 1
            continue
        digest = content_hash(json.dumps({"claim": source, "evidence_ids": source_ids}, sort_keys=True))
        mapped, removed = prior("claim", source, digest)
        if mapped:
            skipped["deleted_sources" if removed else "duplicate_claims"] += 1
            continue
        key = _key("claim", source, namespace)
        for field in ("subject", "predicate", "object", "memory_type"):
            if not isinstance(source.get(field), str) or not source[field].strip():
                raise ValidationError("Archive claim content is incomplete.")
        if not dry_run:
            item = memory.write_claim(namespace=key[3], subject=source["subject"], predicate=source["predicate"],
                object=source["object"], memory_type=source["memory_type"],
                evidence_ids=[local_evidence[value] for value in source_ids],
                confidence=float(source.get("confidence_base", 0.5)),
                importance=float(source.get("importance", 0.5)), half_life_days=source.get("half_life_days"),
                valid_from=source.get("valid_from"), valid_to=source.get("valid_to"),
                status=source["status"] if source.get("status") in {"rejected", "archived"} else "candidate")
            mappings.append({"source_key": list(key), "local_id": item.id, "source_hash": digest})
            memory._write_audit(namespace=key[3], target_type="claim", target_id=item.id,
                action="import.claim_as_candidate", details={"source_claim_id": source["id"], "source_evidence_ids": source_ids})
        imported["claims"] += 1

    run_id = new_id("imp")
    memory.store.connection.execute(
        """INSERT INTO import_runs (id, source_path, target_namespace, dry_run, imported_counts_json,
           skipped_counts_json, conflict_count, status, started_at, finished_at, warnings_json, metadata_json)
           VALUES (?, ?, ?, ?, ?, ?, 0, 'completed', ?, ?, ?, ?)""",
        (run_id, input_path, namespace, int(dry_run), json.dumps(imported, sort_keys=True), json.dumps(skipped, sort_keys=True),
         started, utc_now_iso(), json.dumps(warnings),
         json.dumps({"manifest_id": manifest.get("id"), "source_mappings": mappings if not dry_run else []}, sort_keys=True)))
    memory._write_audit(namespace=namespace or memory.namespace, target_type="import", target_id=run_id,
        action="import.dry_run" if dry_run else "import.apply",
        details={"source_path": input_path, "imported": imported, "skipped": skipped})
    return ImportRun.from_row(memory.store.connection.execute("SELECT * FROM import_runs WHERE id = ?", (run_id,)).fetchone())
