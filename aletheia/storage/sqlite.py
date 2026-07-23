"""SQLite storage setup."""

from __future__ import annotations

import sqlite3
import json
import threading
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Iterator

from aletheia.core.ids import content_hash
from aletheia.core.time import utc_now_iso

SCHEMA_VERSION = "1.3.0"

DEFAULT_CATEGORY_LABELS = [
    "identity",
    "preference",
    "project",
    "task",
    "procedure",
    "decision",
    "correction",
    "domain_knowledge",
    "tool_usage",
    "file_knowledge",
    "communication_style",
    "constraint",
    "safety",
    "privacy",
    "schedule",
    "location",
    "inference",
    "session_summary",
    "mistake",
    "success_pattern",
]


class SQLiteStore:
    """Small SQLite wrapper responsible for connection and migrations."""

    def __init__(self, path: str, connection: sqlite3.Connection):
        self.path = path
        self.connection = connection
        self._lock = threading.RLock()
        self._transaction_depth = 0
        self._savepoint_counter = 0

    @classmethod
    def open(cls, path: str, auto_migrate: bool = True) -> "SQLiteStore":
        if path != ":memory:":
            expanded_path = str(Path(path).expanduser())
            Path(expanded_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            expanded_path = path
        connection = sqlite3.connect(expanded_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        if expanded_path != ":memory:":
            connection.execute("PRAGMA journal_mode = WAL")
        store = cls(path=expanded_path, connection=connection)
        if auto_migrate:
            store.migrate()
        return store

    def migrate(self) -> None:
        with self._lock:
            current_version = self._current_schema_version()
            if current_version and self._version_key(current_version) > self._version_key(SCHEMA_VERSION):
                raise RuntimeError(
                    f"Database schema {current_version} is newer than supported schema {SCHEMA_VERSION}."
                )
            if current_version == SCHEMA_VERSION and self._schema_current():
                return

            schema = (
                resources.files("aletheia.storage.migrations")
                .joinpath("schema.sql")
                .read_text()
            )
            self.connection.executescript(schema)
            self._ensure_compatible_columns()
            self._backfill_m2_records()
            self._backfill_m3_records()
            self._backfill_m4_records()
            self._backfill_m5_records()
            self._backfill_m7_records()
            self._backfill_m8_records()
            self._backfill_m9_records()
            self._backfill_m10_records()
            self._backfill_m11_records()
            self._backfill_m12_records()
            self.connection.execute(
                """
                INSERT INTO schema_version (id, version, applied_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    version = excluded.version,
                    applied_at = excluded.applied_at
                """,
                (SCHEMA_VERSION, utc_now_iso()),
            )
            self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Run writes in an atomic transaction with savepoints for nested callers."""
        with self._lock:
            outermost = self._transaction_depth == 0 and not self.connection.in_transaction
            self._transaction_depth += 1
            if outermost:
                try:
                    self.connection.execute("BEGIN")
                    yield
                except Exception:
                    self.connection.rollback()
                    raise
                else:
                    self.connection.commit()
                finally:
                    self._transaction_depth -= 1
                return

            self._savepoint_counter += 1
            savepoint = f"aletheia_sp_{self._savepoint_counter}"
            self.connection.execute(f"SAVEPOINT {savepoint}")
            try:
                yield
            except Exception:
                self.connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                raise
            else:
                self.connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            finally:
                self._transaction_depth -= 1

    def _ensure_compatible_columns(self) -> None:
        feedback_columns = self._columns("feedback")
        additions = {
            "source": "TEXT DEFAULT 'user'",
            "evidence_id": "TEXT",
            "strength": "REAL DEFAULT 1.0",
        }
        for column, definition in additions.items():
            if column not in feedback_columns:
                self.connection.execute(
                    f"ALTER TABLE feedback ADD COLUMN {column} {definition}"
                )
        compatibility_additions = {
            "embeddings": {
                "provider_type": "TEXT DEFAULT 'mock'",
                "provider_version": "TEXT DEFAULT 'm3'",
                "input_hash": "TEXT",
                "privacy_level": "TEXT DEFAULT 'personal'",
                "index_version": "TEXT",
                "chunk_id": "TEXT DEFAULT 'default'",
                "chunk_text_hash": "TEXT",
                "vector_store": "TEXT DEFAULT 'sqlite_local'",
                "vector_id": "TEXT",
                "status": "TEXT DEFAULT 'indexed'",
                "stale_reason": "TEXT",
            },
            "semantic_index_records": {
                "model": "TEXT",
                "dimension": "INTEGER",
                "provider_type": "TEXT DEFAULT 'mock'",
                "vector_store": "TEXT DEFAULT 'sqlite_local'",
                "index_version": "TEXT",
                "content_hash": "TEXT",
                "stale_reason": "TEXT",
            },
            "claim_status_history": {
                "changed_by": "TEXT DEFAULT 'system'",
            },
            "conflict_families": {
                "resolution_id": "TEXT",
            },
            "conflict_resolutions": {
                "metadata_json": "TEXT",
            },
            "claim_scopes": {
                "project_id": "TEXT",
                "session_id": "TEXT",
                "agent_id": "TEXT",
            },
            "curation_decisions": {
                "old_status": "TEXT",
                "proposed_status": "TEXT",
            },
            "curation_queue": {
                "task_type": "TEXT NOT NULL DEFAULT 'review'",
                "reason": "TEXT",
            },
        }
        for table, additions in compatibility_additions.items():
            columns = self._columns(table)
            for column, definition in additions.items():
                if column not in columns:
                    self.connection.execute(
                        f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                    )
        self.connection.execute("DROP INDEX IF EXISTS idx_embeddings_target_provider")
        self._dedupe_embedding_provider_keys()
        self.connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_embeddings_target_provider
            ON embeddings(namespace, target_type, target_id, provider, model, COALESCE(index_version, ''))
            """
        )

    def _current_schema_version(self) -> str | None:
        if not self._table_exists("schema_version"):
            return None
        row = self.connection.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        ).fetchone()
        return row["version"] if row else None

    def _schema_current(self) -> bool:
        required_tables = {"schema_version", "claims", "evidence_events", "claims_fts"}
        if not all(self._table_exists(table) for table in required_tables):
            return False
        if self._table_exists("embeddings"):
            index = self.connection.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = 'idx_embeddings_target_provider'"
            ).fetchone()
            if not index or "COALESCE(index_version" not in (index["sql"] or ""):
                return False
        return True

    def _table_exists(self, table: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'virtual table') AND name = ?",
            (table,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _version_key(version: str) -> tuple[int, ...]:
        parts: list[int] = []
        for part in version.split("."):
            digits = "".join(character for character in part if character.isdigit())
            parts.append(int(digits or "0"))
        return tuple(parts)

    def _dedupe_embedding_provider_keys(self) -> None:
        if not self._table_exists("embeddings"):
            return
        self.connection.execute(
            """
            DELETE FROM embeddings
            WHERE id IN (
                SELECT id
                FROM (
                    SELECT
                        id,
                        row_number() OVER (
                            PARTITION BY namespace, target_type, target_id, provider, model, COALESCE(index_version, '')
                            ORDER BY created_at DESC, id DESC
                        ) AS duplicate_rank
                    FROM embeddings
                )
                WHERE duplicate_rank > 1
            )
            """
        )

    def _columns(self, table: str) -> set[str]:
        rows = self.connection.execute(f"PRAGMA table_info({table})").fetchall()
        return {row["name"] for row in rows}

    def _backfill_m2_records(self) -> None:
        now = utc_now_iso()
        default_policies = [
            ("hlp_default_current_task", None, "current_task", None, 3.0),
            ("hlp_default_task", None, "task", None, 3.0),
            ("hlp_default_temporary_preference", None, "temporary_preference", None, 14.0),
            ("hlp_default_project", None, "project", None, 30.0),
            ("hlp_default_project_state", None, "project_state", None, 30.0),
            ("hlp_default_session_summary", None, "session_summary", None, 45.0),
            ("hlp_default_preference", None, "preference", None, 180.0),
            ("hlp_default_procedure", None, "procedure", None, 365.0),
            ("hlp_default_identity", None, "identity", None, 1000.0),
            ("hlp_default_correction", None, "correction", None, 1000.0),
            ("hlp_default_domain_knowledge", None, "domain_knowledge", None, 1000.0),
            ("hlp_default_inference", None, "inference", None, 14.0),
        ]
        self.connection.executemany(
            """
            INSERT OR IGNORE INTO half_life_policies (
                id, namespace, memory_type, predicate, half_life_days,
                reason, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'M2 default half-life policy.', ?, ?)
            """,
            [(*policy, now, now) for policy in default_policies],
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO claim_status_history (
                id, namespace, claim_id, old_status, new_status, reason, changed_by, created_at
            )
            SELECT
                'hist_m2_' || id,
                namespace,
                id,
                NULL,
                status,
                'M2 migration backfill.',
                'migration',
                ?
            FROM claims
            """,
            (now,),
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO confidence_snapshots (
                id, namespace, claim_id, truth_confidence, retrieval_salience,
                base_confidence, effective_confidence, decay_factor,
                source_reliability_factor, feedback_factor, contradiction_factor,
                verification_factor, half_life_days, age_days, explanation, computed_at
            )
            SELECT
                'snap_m2_' || id,
                namespace,
                id,
                confidence_effective,
                importance,
                confidence_base,
                confidence_effective,
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
                half_life_days,
                0.0,
                'M2 migration backfill snapshot.',
                ?
            FROM claims
            """,
            (now,),
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO confidence_events (
                id, namespace, claim_id, event_type, old_truth_confidence,
                new_truth_confidence, old_retrieval_salience, new_retrieval_salience,
                reason, metadata_json, created_at
            )
            SELECT
                'cevt_m2_' || id,
                namespace,
                id,
                'migration_backfill',
                NULL,
                confidence_effective,
                NULL,
                importance,
                'Initial M2 confidence audit record.',
                '{}',
                ?
            FROM claims
            """,
            (now,),
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO conflict_families (
                id, namespace, subject, predicate, conflict_type, status,
                active_claim_id, resolution_id, resolution_strategy, resolution_note,
                created_at, updated_at, resolved_at
            )
            SELECT
                id,
                namespace,
                subject,
                predicate,
                'direct_value_conflict',
                status,
                active_claim_id,
                NULL,
                CASE WHEN status = 'resolved' THEN 'manual' ELSE NULL END,
                resolution_note,
                created_at,
                COALESCE(resolved_at, created_at),
                resolved_at
            FROM conflicts
            """,
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO conflict_family_claims (
                conflict_id, claim_id, role, created_at
            )
            SELECT
                conflict_id,
                claim_id,
                'member',
                ?
            FROM conflict_claim_links
            """,
            (now,),
        )

    def _backfill_m3_records(self) -> None:
        now = utc_now_iso()
        self.connection.executemany(
            """
            INSERT OR IGNORE INTO category_registry (
                id, namespace, label, parent_label, description, created_at
            )
            VALUES (?, NULL, ?, ?, ?, ?)
            """,
            [
                (
                    f"cat_default_{label.replace('.', '_')}",
                    label,
                    label.rsplit(".", 1)[0] if "." in label else None,
                    f"M3 default category: {label}.",
                    now,
                )
                for label in DEFAULT_CATEGORY_LABELS
            ],
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO memory_category_labels (
                id, namespace, target_id, target_type, label, confidence, reason, created_at
            )
            SELECT
                'lbl_m3_claim_' || id,
                namespace,
                id,
                'claim',
                CASE
                    WHEN memory_type IN ('preference', 'temporary_preference') THEN 'preference'
                    WHEN memory_type IN ('project', 'project_state') THEN 'project'
                    WHEN memory_type IN ('procedure', 'tool_usage') THEN 'procedure'
                    WHEN memory_type = 'correction' THEN 'correction'
                    WHEN memory_type = 'session_summary' THEN 'session_summary'
                    WHEN memory_type = 'inference' THEN 'inference'
                    WHEN memory_type IN ('identity', 'profile') THEN 'identity'
                    ELSE 'domain_knowledge'
                END,
                0.80,
                'M3 deterministic migration label from memory_type.',
                ?
            FROM claims
            """,
            (now,),
        )
        project_rows = self.connection.execute(
            "SELECT namespace, id, title FROM projects"
        ).fetchall()
        for row in project_rows:
            entity_id = _deterministic_entity_id(
                row["namespace"],
                "project",
                row["id"],
            )
            self.connection.execute(
                """
                INSERT OR IGNORE INTO entities (
                    id, namespace, canonical_name, entity_type, created_at,
                    updated_at, metadata_json
                )
                VALUES (?, ?, ?, 'project', ?, ?, ?)
                """,
                (
                    entity_id,
                    row["namespace"],
                    row["title"],
                    now,
                    now,
                    json.dumps(
                        {"source": "m3_migration", "project_id": row["id"]},
                        sort_keys=True,
                    ),
                ),
            )
            for alias in {row["id"], row["title"]}:
                alias_id = _deterministic_entity_id(row["namespace"], entity_id, alias)
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO entity_aliases (
                        id, namespace, entity_id, alias, created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (alias_id, row["namespace"], entity_id, alias, now),
                )

    def _backfill_m4_records(self) -> None:
        now = utc_now_iso()
        default_rules = [
            (
                "rule_m4_superseded_not_current",
                None,
                "superseded_claims_are_not_current",
                "logical",
                "Claims superseded by newer claims are not current.",
                {"relationship_type": "supersedes"},
                {"inference_type": "temporal_currentness", "predicate": "is_current", "object": "false"},
                {"confidence": 0.95, "strength": "entailed"},
            ),
            (
                "rule_m4_expired_not_current",
                None,
                "expired_temporal_claims_are_not_current",
                "temporal",
                "Claims with valid_to in the past are not current.",
                {"claim_valid_to": "past"},
                {"inference_type": "temporal_currentness", "predicate": "is_current", "object": "false"},
                {"confidence": 0.95, "strength": "entailed"},
            ),
            (
                "rule_m4_resolved_conflict_active",
                None,
                "resolved_conflict_active_claim_applies",
                "conflict",
                "Active claims selected by resolved conflicts apply for that conflict.",
                {"conflict_family_status": "resolved"},
                {"inference_type": "logical", "predicate": "active_for_conflict"},
                {"confidence": 0.90, "strength": "entailed"},
            ),
            (
                "rule_m4_unresolved_conflict_warning",
                None,
                "unresolved_disputed_claims_warn",
                "conflict",
                "Unresolved disputed claims should produce context warnings.",
                {"claim_status": "disputed", "conflict_family_status": "unresolved"},
                {"inference_type": "logical", "predicate": "requires_context_warning"},
                {"confidence": 0.85, "strength": "entailed"},
            ),
            (
                "rule_m4_source_invalidation_propagates",
                None,
                "source_invalidation_propagates",
                "dependency",
                "Derived records depending on rejected or superseded claims require refresh.",
                {"source_status": ["rejected", "superseded", "invalidated"]},
                {"action": "queue_refresh"},
                {"confidence": 1.0, "strength": "entailed"},
            ),
            (
                "rule_m4_scoped_claim_matches_context",
                None,
                "scoped_claim_matches_context",
                "scope",
                "Contextual claim scopes can match a query context deterministically.",
                {"scope_type": "contextual"},
                {"inference_type": "scope_match", "predicate": "applies_to_context"},
                {"confidence": 0.88, "strength": "strong"},
            ),
            (
                "rule_m4_semantic_relation",
                None,
                "semantic_similarity_creates_relations_only",
                "classification",
                "Semantically similar memories create retrieval relations, not facts.",
                {"shared_memory_type_and_predicate": True},
                {"relation_type": "related_to", "truth_effect": "none"},
                {"confidence": 0.70, "strength": "retrieval_hint"},
            ),
            (
                "rule_m4_project_focus_factual",
                None,
                "project_focus_candidate_from_milestone_claims",
                "factual",
                "Current milestone and milestone name claims may create conservative factual candidates.",
                {"requires_claims": ["current_milestone", "name"]},
                {"inference_type": "factual", "status": "pending_review"},
                {"confidence_cap": 0.82, "strength": "entailed"},
            ),
            (
                "rule_m4_reflection_suggestion",
                None,
                "response_style_preferences_can_suggest_reflection",
                "reflection",
                "Multiple response-style preferences can suggest a source-backed reflection candidate.",
                {"memory_type": "preference", "predicate": "prefers_response_style"},
                {"inference_type": "reflection", "status": "pending_review"},
                {"confidence_cap": 0.80, "strength": "probable"},
            ),
        ]
        self.connection.executemany(
            """
            INSERT OR IGNORE INTO inference_rules (
                id, namespace, name, rule_type, description, condition_json,
                conclusion_json, confidence_policy_json, enabled, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            [
                (
                    rule_id,
                    namespace,
                    name,
                    rule_type,
                    description,
                    json.dumps(condition, sort_keys=True),
                    json.dumps(conclusion, sort_keys=True),
                    json.dumps(confidence_policy, sort_keys=True),
                    now,
                    now,
                )
                for (
                    rule_id,
                    namespace,
                    name,
                    rule_type,
                    description,
                    condition,
                    conclusion,
                    confidence_policy,
                ) in default_rules
            ],
        )

    def _backfill_m5_records(self) -> None:
        now = utc_now_iso()
        ranking_policy_id = "rpol_default"
        ranking_version_id = "rpv_default_v1"
        ranking_weights = {
            "lexical_score": 0.25,
            "semantic_score": 0.25,
            "effective_confidence": 0.15,
            "retrieval_salience": 0.10,
            "memory_type_priority": 0.08,
            "project_relevance": 0.07,
            "status_priority": 0.05,
            "recency_score": 0.05,
        }
        ranking_filters = {
            "exclude_rejected": True,
            "exclude_superseded": True,
            "exclude_archived": True,
            "exclude_disputed_by_default": True,
            "require_provenance": True,
        }
        ranking_thresholds = {
            "forbidden_memory_leak_rate": 0.0,
            "rejected_memory_leak_rate": 0.0,
            "superseded_memory_leak_rate": 0.0,
            "disputed_memory_leak_rate": 0.02,
            "provenance_preservation_rate": 0.99,
        }
        self.connection.execute(
            """
            INSERT OR IGNORE INTO ranking_policies (
                id, namespace, name, active_version_id, created_at, updated_at
            )
            VALUES (?, NULL, 'default_ranking_policy', ?, ?, ?)
            """,
            (ranking_policy_id, ranking_version_id, now, now),
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO ranking_policy_versions (
                id, policy_id, version, weights_json, filters_json,
                thresholds_json, created_by, status, evaluation_summary_json,
                created_at
            )
            VALUES (?, ?, 1, ?, ?, ?, 'm5_migration', 'active', ?, ?)
            """,
            (
                ranking_version_id,
                ranking_policy_id,
                json.dumps(ranking_weights, sort_keys=True),
                json.dumps(ranking_filters, sort_keys=True),
                json.dumps(ranking_thresholds, sort_keys=True),
                json.dumps({"source": "M5 migration default"}, sort_keys=True),
                now,
            ),
        )
        self.connection.execute(
            """
            UPDATE ranking_policies
            SET active_version_id = COALESCE(active_version_id, ?),
                updated_at = ?
            WHERE id = ?
            """,
            (ranking_version_id, now, ranking_policy_id),
        )

        context_policy_id = "cpol_default"
        context_version_id = "cpv_default_v1"
        context_config = {
            "token_budget": 1500,
            "include_reflections": True,
            "include_inferences": False,
            "include_derivation_metadata": False,
            "preserve_governance": True,
        }
        self.connection.execute(
            """
            INSERT OR IGNORE INTO context_pack_policies (
                id, namespace, name, active_version_id, created_at, updated_at
            )
            VALUES (?, NULL, 'default_context_pack_policy', ?, ?, ?)
            """,
            (context_policy_id, context_version_id, now, now),
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO context_pack_policy_versions (
                id, policy_id, version, config_json, filters_json,
                thresholds_json, created_by, status, evaluation_summary_json,
                created_at
            )
            VALUES (?, ?, 1, ?, ?, ?, 'm5_migration', 'active', ?, ?)
            """,
            (
                context_version_id,
                context_policy_id,
                json.dumps(context_config, sort_keys=True),
                json.dumps({"exclude_invalid": True}, sort_keys=True),
                json.dumps({"provenance_preservation_rate": 0.99}, sort_keys=True),
                json.dumps({"source": "M5 migration default context policy"}, sort_keys=True),
                now,
            ),
        )
        self.connection.execute(
            """
            UPDATE context_pack_policies
            SET active_version_id = COALESCE(active_version_id, ?),
                updated_at = ?
            WHERE id = ?
            """,
            (context_version_id, now, context_policy_id),
        )

    def _backfill_m7_records(self) -> None:
        now = utc_now_iso()
        defaults = {
            "dashboard.layout": {
                "sections": [
                    "memory_health",
                    "review_queue",
                    "conflicts",
                    "candidates",
                    "jobs",
                    "service_activity",
                ]
            },
            "dashboard.sort.review_queue": {"field": "priority", "direction": "desc"},
        }
        for key, value in defaults.items():
            self.connection.execute(
                """
                INSERT OR IGNORE INTO dashboard_preferences (
                    id, namespace, preference_key, preference_value_json, updated_at
                )
                VALUES (?, NULL, ?, ?, ?)
                """,
                (
                    "dpref_" + content_hash(f"global\0{key}")[:24],
                    key,
                    json.dumps(value, sort_keys=True),
                    now,
                ),
            )

    def _backfill_m8_records(self) -> None:
        now = utc_now_iso()
        self.connection.execute(
            """
            INSERT OR IGNORE INTO protected_mode_config (
                id, enabled, content_encryption_enabled,
                backup_encryption_required, indexing_policy,
                request_logging_policy, created_at, updated_at, metadata_json
            )
            VALUES (
                'protected_default', 0, 0, 0,
                'index_public_and_personal_only',
                'metadata_only',
                ?, ?, ?
            )
            """,
            (
                now,
                now,
                json.dumps({"source": "M8 migration default disabled config"}, sort_keys=True),
            ),
        )

    def _backfill_m9_records(self) -> None:
        now = utc_now_iso()

        contracts = [
            ("http_api", "HTTP API v1", "v1", "stable", "openapi:/v1/openapi.json", "docs/http_api_reference.md"),
            ("mcp_tool", "MCP tools v1", "v1", "stable", "mcp:schema", "docs/mcp_reference.md"),
            ("python_api", "Python SDK v1", "1.0.0", "stable", "python:aletheia.client", "docs/sdk_reference.md"),
            ("python_api", "Async Python SDK v1", "1.0.0", "stable", "python:aletheia.client.AsyncAletheiaClient", "docs/sdk_reference.md"),
            ("cli_command", "CLI commands v1", "1.0.0", "stable", "cli:aletheia", "docs/cli_reference.md"),
            ("plugin_interface", "Plugin interface v1", "1.0.0", "stable", "python:aletheia.plugins", "docs/plugin_developer_guide.md"),
            ("config_schema", "Config schema v1", "1.0.0", "stable", "config:aletheia.toml", "docs/configuration.md"),
            ("archive_format", "Aletheia archive format v1", "1", "stable", "archive:alet", "docs/backup_restore_guide.md"),
            ("context_pack_schema", "Context pack schema v1", "1.0.0", "stable", "schema:context_pack", "docs/context_pack_schema.md"),
            ("retrieval_result_schema", "Retrieval result schema v1", "1.0.0", "stable", "schema:retrieval_result", "docs/retrieval_result_schema.md"),
            ("audit_schema", "Audit schema v1", "1.0.0", "stable", "schema:audit", "docs/audit_schema.md"),
            ("database_migration_contract", "Database migration contract v1", "1.0.0", "stable", "schema:migration", "docs/migration_guide.md"),
            ("plugin_interface", "Storage backend plugin interface", "0.1.0", "experimental", "python:storage_backend", "docs/plugin_developer_guide.md"),
        ]
        for contract_type, name, version, stability, schema_ref, docs_ref in contracts:
            contract_id = f"contract_{content_hash(f'{contract_type}\0{name}\0{version}')[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO public_contracts (
                    id, contract_type, name, version, stability, introduced_in,
                    deprecated_in, removed_in, schema_ref, documentation_ref,
                    created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, '1.0.0', NULL, NULL, ?, ?, ?, ?)
                """,
                (
                    contract_id,
                    contract_type,
                    name,
                    version,
                    stability,
                    schema_ref,
                    docs_ref,
                    now,
                    json.dumps({"semver": True, "v1_public": stability == "stable"}, sort_keys=True),
                ),
            )

        api_contracts = [
            ("http", "v1", "stable"),
            ("mcp", "v1", "stable"),
            ("python_sdk", "1.0.0", "stable"),
            ("typescript_sdk", "1.0.0-contract", "experimental"),
            ("plugin", "1.0.0", "stable"),
            ("cli", "1.0.0", "stable"),
            ("archive", "1", "stable"),
        ]
        for api_type, version, status in api_contracts:
            row_id = f"apic_{content_hash(f'{api_type}\0{version}')[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO api_contract_versions (
                    id, api_type, version, status, schema_hash, introduced_in,
                    deprecated_in, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, '1.0.0', NULL, ?, ?)
                """,
                (
                    row_id,
                    api_type,
                    version,
                    status,
                    content_hash(f"{api_type}:{version}:{status}"),
                    now,
                    json.dumps({"registered_by": "M9 migration"}, sort_keys=True),
                ),
            )

        self.connection.execute(
            """
            INSERT OR IGNORE INTO deprecation_notices (
                id, target_type, target_name, deprecated_in,
                removal_not_before, replacement, message, created_at,
                metadata_json
            )
            VALUES (
                'dep_legacy_context_alias', 'cli_command', 'context legacy aliases',
                '1.0.0', '1.3.0', 'context-pack',
                'Legacy context aliases remain available during the v1 deprecation window.',
                ?, ?
            )
            """,
            (now, json.dumps({"window_minor_releases": 2}, sort_keys=True)),
        )

        matrix = [
            ("core", "aletheia-memory", "1.0.0", "supported", "v1 GA platform"),
            ("http_api", "http", "v1", "supported", "OpenAPI v1 contract"),
            ("mcp", "mcp-tools", "v1", "supported", "Local MCP-style tools"),
            ("python_sdk", "aletheia.client", "1.0.0", "supported", "Sync and async clients"),
            ("archive", "aletheia-archive", "1", "supported", "M8/M9 .alet archives"),
            ("plugin_api", "plugin-interface", "1.0.0", "supported", "Manifest and permission model"),
        ]
        for component_type, component_name, version, status, notes in matrix:
            row_id = f"compat_{content_hash(f'{component_type}\0{component_name}\0{version}')[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO compatibility_matrix_entries (
                    id, component_type, component_name, component_version,
                    aletheia_min_version, aletheia_max_version, status,
                    tested_at, notes, metadata_json
                )
                VALUES (?, ?, ?, ?, '1.0.0', NULL, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    component_type,
                    component_name,
                    version,
                    status,
                    now,
                    notes,
                    json.dumps({"source": "M9 defaults"}, sort_keys=True),
                ),
            )

        suites = [
            ("kernel", "kernel", "Kernel governance conformance"),
            ("http-api", "http_api", "HTTP API v1 conformance"),
            ("mcp", "mcp", "MCP tool conformance"),
            ("python-sdk", "sdk", "Python SDK v1 conformance"),
            ("plugin", "plugin", "Plugin manifest and permission conformance"),
            ("agent-adapter", "agent_adapter", "Agent adapter conformance"),
            ("backup-archive", "archive", "Backup/archive conformance"),
            ("protected-mode", "protected_mode", "Protected-mode conformance"),
            ("context-pack-schema", "context_pack", "Context-pack schema conformance"),
        ]
        for name, suite_type, description in suites:
            suite_id = f"suite_{content_hash(name)[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO conformance_suites (
                    id, name, suite_type, version, description,
                    required_for_v1, created_at, metadata_json
                )
                VALUES (?, ?, ?, '1.0.0', ?, 1, ?, ?)
                """,
                (suite_id, name, suite_type, description, now, json.dumps({}, sort_keys=True)),
            )
            cases = [
                ("contract_registered", "Public contract is registered", "critical"),
                ("governance_preserved", "Governance and privacy constraints are preserved", "critical"),
                ("error_envelope", "Failures are reported without raw sensitive content", "high"),
            ]
            for case_name, description, severity in cases:
                case_id = f"case_{content_hash(f'{suite_id}\0{case_name}')[:24]}"
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO conformance_cases (
                        id, suite_id, name, description, severity,
                        required, test_ref, created_at, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        case_id,
                        suite_id,
                        case_name,
                        description,
                        severity,
                        f"m9.{name}.{case_name}",
                        now,
                        json.dumps({}, sort_keys=True),
                    ),
                )

        sdk_records = [
            ("python-sync", "1.0.0", "python", "python_sdk.v1"),
            ("python-async", "1.0.0", "python", "python_sdk.v1"),
            ("typescript", "1.0.0-contract", "typescript", "typescript_sdk.v1"),
        ]
        for sdk_name, version, language, contract in sdk_records:
            row_id = f"sdk_{content_hash(f'{sdk_name}\0{version}')[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO sdk_release_records (
                    id, sdk_name, sdk_version, language,
                    api_contract_version, status, released_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    sdk_name,
                    version,
                    language,
                    contract,
                    "released" if language == "python" else "contract_only",
                    now,
                    json.dumps({"source": "M9 defaults"}, sort_keys=True),
                ),
            )

    def _backfill_m10_records(self) -> None:
        now = utc_now_iso()

        contracts = [
            ("federation_protocol", "Federation protocol v1", "1.0", "experimental", "protocol:federation.v1", "docs/m10_federated_memory_contract.md"),
            ("archive_format", "Aletheia sync bundle format", "1.0", "experimental", "archive:aletsync", "docs/m10_federated_memory_contract.md"),
            ("sync_changeset_schema", "Sync changeset schema v1", "1.0", "experimental", "schema:sync_changeset", "docs/m10_federated_memory_contract.md"),
            ("peer_identity_schema", "Peer identity schema v1", "1.0", "experimental", "schema:peer_identity", "docs/m10_federated_memory_contract.md"),
            ("share_grant_schema", "Share grant schema v1", "1.0", "experimental", "schema:share_grant", "docs/m10_federated_memory_contract.md"),
            ("cli_command", "Federation CLI commands", "1.3.0", "experimental", "cli:aletheia federation", "docs/m10_federated_memory_contract.md"),
            ("http_api", "Federation HTTP API v1", "v1", "experimental", "openapi:/v1/openapi.json", "docs/m10_federated_memory_contract.md"),
            ("python_api", "Python SDK federation methods", "1.3.0", "experimental", "python:aletheia.client.federation", "docs/m10_federated_memory_contract.md"),
        ]
        for contract_type, name, version, stability, schema_ref, docs_ref in contracts:
            contract_id = f"contract_{content_hash(f'{contract_type}\0{name}\0{version}')[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO public_contracts (
                    id, contract_type, name, version, stability, introduced_in,
                    deprecated_in, removed_in, schema_ref, documentation_ref,
                    created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, '1.3.0', NULL, NULL, ?, ?, ?, ?)
                """,
                (
                    contract_id,
                    contract_type,
                    name,
                    version,
                    stability,
                    schema_ref,
                    docs_ref,
                    now,
                    json.dumps({"milestone": "M10", "federation_beta": True}, sort_keys=True),
                ),
            )

        api_contracts = [
            ("federation", "v1", "experimental"),
            ("sync_bundle", "1.0", "experimental"),
            ("sync_changeset", "1.0", "experimental"),
            ("peer_identity", "1.0", "experimental"),
            ("python_sdk", "1.3.0", "stable"),
            ("cli", "1.3.0", "stable"),
        ]
        for api_type, version, status in api_contracts:
            row_id = f"apic_{content_hash(f'{api_type}\0{version}')[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO api_contract_versions (
                    id, api_type, version, status, schema_hash, introduced_in,
                    deprecated_in, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, '1.3.0', NULL, ?, ?)
                """,
                (
                    row_id,
                    api_type,
                    version,
                    status,
                    content_hash(f"{api_type}:{version}:{status}:m10"),
                    now,
                    json.dumps({"registered_by": "M10 migration"}, sort_keys=True),
                ),
            )

        matrix = [
            ("core", "aletheia-memory", "1.3.0", "supported", "M11 production semantic retrieval platform"),
            ("federation_protocol", "federation", "v1", "beta", "Local-first federation protocol"),
            ("sync_bundle", "aletsync", "1.0", "beta", "Encrypted file-based sync bundle"),
            ("python_sdk", "aletheia.client", "1.3.0", "supported", "Federation and memory helper methods"),
            ("cli", "aletheia", "1.3.0", "supported", "Federation and semantic index command groups"),
        ]
        for component_type, component_name, version, status, notes in matrix:
            row_id = f"compat_{content_hash(f'{component_type}\0{component_name}\0{version}')[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO compatibility_matrix_entries (
                    id, component_type, component_name, component_version,
                    aletheia_min_version, aletheia_max_version, status,
                    tested_at, notes, metadata_json
                )
                VALUES (?, ?, ?, ?, '1.3.0', NULL, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    component_type,
                    component_name,
                    version,
                    status,
                    now,
                    notes,
                    json.dumps({"source": "M10 defaults"}, sort_keys=True),
                ),
            )

        trust_domains = [
            ("trust_untrusted_imports", "untrusted_imports", "Unknown peers import candidates only.", "candidate_only", ["project", "task", "decision", "fact", "preference"], "personal", 0, 1, 1, 1),
            ("trust_personal_trusted_devices", "personal_trusted_devices", "User-owned devices may import active project state.", "active_for_project_state", ["project", "task", "decision", "fact", "preference"], "personal", 1, 1, 1, 1),
            ("trust_team_shared_project", "team_shared_project", "Trusted team project memories require conflict review.", "active_if_trusted", ["project", "decision", "procedure", "fact"], "personal", 1, 1, 1, 1),
        ]
        for domain_id, name, description, policy, allowed_types, max_privacy, active, candidate, feedback, redaction in trust_domains:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO trust_domains (
                    id, name, description, default_import_policy,
                    allowed_memory_types_json, max_privacy_level,
                    allow_active_import, allow_candidate_import,
                    allow_feedback_import, allow_remote_redaction,
                    created_at, updated_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    domain_id,
                    name,
                    description,
                    policy,
                    json.dumps(allowed_types, sort_keys=True),
                    max_privacy,
                    active,
                    candidate,
                    feedback,
                    redaction,
                    now,
                    now,
                    json.dumps({"source": "M10 defaults"}, sort_keys=True),
                ),
            )

        policies = [
            ("itp_candidate_only", "candidate_only_default", None, None, None, "candidate_only", 0, 1, 1, 1, 0, 1),
            ("itp_untrusted_imports", "untrusted_imports", "trust_untrusted_imports", None, None, "candidate_only", 0, 1, 1, 1, 0, 1),
            ("itp_trusted_device", "trusted_device_project_state", "trust_personal_trusted_devices", None, None, "active_for_project_state", 1, 1, 1, 1, 0, 1),
            ("itp_team_shared_project", "team_shared_project", "trust_team_shared_project", None, None, "active_if_trusted", 1, 1, 1, 1, 0, 1),
        ]
        for row in policies:
            (
                policy_id,
                name,
                trust_domain_id,
                peer_id,
                namespace,
                mode,
                allow_active,
                allow_candidates,
                allow_evidence,
                allow_reflections,
                allow_inferences,
                require_review,
            ) = row
            self.connection.execute(
                """
                INSERT OR IGNORE INTO import_trust_policies (
                    id, name, trust_domain_id, peer_id, namespace, import_mode,
                    allow_active_claims, allow_candidates, allow_evidence,
                    allow_reflections, allow_inferences,
                    require_review_for_conflicts, created_at, updated_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    policy_id,
                    name,
                    trust_domain_id,
                    peer_id,
                    namespace,
                    mode,
                    allow_active,
                    allow_candidates,
                    allow_evidence,
                    allow_reflections,
                    allow_inferences,
                    require_review,
                    now,
                    now,
                    json.dumps({"source": "M10 defaults"}, sort_keys=True),
                ),
            )

        suites = [
            ("federation-identity", "federation_identity", "Federation identity and key safety conformance"),
            ("peer-trust", "peer_trust", "Peer trust and revocation conformance"),
            ("share-bundle", "share_bundle", "Encrypted share bundle conformance"),
            ("sync-protocol", "sync_protocol", "Sync changeset and import conformance"),
            ("federation-conflict", "federation_conflict", "Sync conflict conformance"),
            ("federation-redaction", "federation_redaction", "Redaction and revocation propagation conformance"),
        ]
        for name, suite_type, description in suites:
            suite_id = f"suite_{content_hash(name)[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO conformance_suites (
                    id, name, suite_type, version, description,
                    required_for_v1, created_at, metadata_json
                )
                VALUES (?, ?, ?, '1.3.0', ?, 0, ?, ?)
                """,
                (suite_id, name, suite_type, description, now, json.dumps({"milestone": "M10"}, sort_keys=True)),
            )
            cases = [
                ("contract_registered", "Federation contract is registered", "critical"),
                ("governance_preserved", "Local sovereignty and candidate-first governance are preserved", "critical"),
                ("privacy_enforced", "Privacy ceilings and secret exclusions are enforced", "critical"),
            ]
            for case_name, description, severity in cases:
                case_id = f"case_{content_hash(f'{suite_id}\0{case_name}')[:24]}"
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO conformance_cases (
                        id, suite_id, name, description, severity,
                        required, test_ref, created_at, metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        case_id,
                        suite_id,
                        case_name,
                        description,
                        severity,
                        f"m10.{name}.{case_name}",
                        now,
                        json.dumps({}, sort_keys=True),
                    ),
                )

        sdk_records = [
            ("python-sync", "1.3.0", "python", "python_sdk.v1.federation"),
            ("python-async", "1.3.0", "python", "python_sdk.v1.federation"),
        ]
        for sdk_name, version, language, contract in sdk_records:
            row_id = f"sdk_{content_hash(f'{sdk_name}\0{version}')[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO sdk_release_records (
                    id, sdk_name, sdk_version, language,
                    api_contract_version, status, released_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, 'released', ?, ?)
                """,
                (
                    row_id,
                    sdk_name,
                    version,
                    language,
                    contract,
                    now,
                    json.dumps({"source": "M10 defaults"}, sort_keys=True),
                ),
            )

    def _backfill_m11_records(self) -> None:
        now = utc_now_iso()
        contracts = [
            ("semantic_retrieval", "Production semantic retrieval", "1.0", "experimental", "python:Memory.index_semantic", "docs/M11_Embedding_Integration_contract.md"),
            ("embedding_provider", "Embedding provider adapters", "1.0", "experimental", "python:aletheia.semantic.provider_for_name", "docs/M11_Embedding_Integration_contract.md"),
            ("vector_store", "SQLite local vector store", "1.0", "experimental", "python:aletheia.semantic.SQLiteVectorStore", "docs/M11_Embedding_Integration_contract.md"),
            ("cli_command", "Semantic index lifecycle CLI", "1.3.0", "experimental", "cli:aletheia index", "docs/M11_Embedding_Integration_contract.md"),
        ]
        for contract_type, name, version, stability, schema_ref, docs_ref in contracts:
            contract_id = f"contract_{content_hash(f'{contract_type}\0{name}\0{version}')[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO public_contracts (
                    id, contract_type, name, version, stability, introduced_in,
                    deprecated_in, removed_in, schema_ref, documentation_ref,
                    created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, '1.3.0', NULL, NULL, ?, ?, ?, ?)
                """,
                (
                    contract_id,
                    contract_type,
                    name,
                    version,
                    stability,
                    schema_ref,
                    docs_ref,
                    now,
                    json.dumps({"milestone": "M11", "semantic_retrieval_beta": True}, sort_keys=True),
                ),
            )

        matrix = [
            ("core", "aletheia-memory", "1.3.0", "supported", "M11 production semantic retrieval"),
            ("embedding_provider", "local_hash", "1.0", "beta", "Local-safe configurable embedding provider"),
            ("vector_store", "sqlite_local", "1.0", "beta", "Embedded SQLite vector storage"),
            ("cli", "aletheia", "1.3.0", "supported", "Semantic index lifecycle commands"),
        ]
        for component_type, component_name, version, status, notes in matrix:
            row_id = f"compat_{content_hash(f'm11\0{component_type}\0{component_name}\0{version}')[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO compatibility_matrix_entries (
                    id, component_type, component_name, component_version,
                    aletheia_min_version, aletheia_max_version, status,
                    tested_at, notes, metadata_json
                )
                VALUES (?, ?, ?, ?, '1.3.0', NULL, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    component_type,
                    component_name,
                    version,
                    status,
                    now,
                    notes,
                    json.dumps({"source": "M11 defaults"}, sort_keys=True),
                ),
            )

        suite_id = f"suite_{content_hash('semantic-retrieval')[:24]}"
        self.connection.execute(
            """
            INSERT OR IGNORE INTO conformance_suites (
                id, name, suite_type, version, description,
                required_for_v1, created_at, metadata_json
            )
            VALUES (?, 'semantic-retrieval', 'semantic_retrieval', '1.3.0', ?, 0, ?, ?)
            """,
            (
                suite_id,
                "Semantic provider, vector-store lifecycle, and governance conformance",
                now,
                json.dumps({"milestone": "M11"}, sort_keys=True),
            ),
        )
        cases = [
            ("contract_registered", "Semantic retrieval contract is registered", "critical"),
            ("governance_preserved", "Semantic results preserve claim governance filters", "critical"),
            ("privacy_enforced", "Protected-mode semantic indexing policy is enforced", "critical"),
        ]
        for case_name, description, severity in cases:
            case_id = f"case_{content_hash(f'{suite_id}\0{case_name}')[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO conformance_cases (
                    id, suite_id, name, description, severity,
                    required, test_ref, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    case_id,
                    suite_id,
                    case_name,
                    description,
                    severity,
                    f"m11.semantic_retrieval.{case_name}",
                    now,
                    json.dumps({}, sort_keys=True),
                ),
            )

    def _backfill_m12_records(self) -> None:
        now = utc_now_iso()
        contracts = [
            ("llm_provider", "Governed LLM provider interface", "1.0", "experimental", "python:aletheia.llm.LLMProvider", "docs/M12_LLM_Integration_contract.md"),
            ("llm_extraction", "Governed LLM candidate extraction", "1.0", "experimental", "python:LLMExtractor", "docs/M12_LLM_Integration_contract.md"),
            ("llm_provenance", "LLM run and output provenance", "1.0", "experimental", "schema:llm_runs", "docs/M12_LLM_Integration_contract.md"),
            ("cli_command", "Governed LLM CLI commands", "1.3.0", "experimental", "cli:aletheia llm", "docs/M12_LLM_Integration_contract.md"),
        ]
        for contract_type, name, version, stability, schema_ref, docs_ref in contracts:
            contract_id = f"contract_{content_hash(f'{contract_type}\0{name}\0{version}')[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO public_contracts (
                    id, contract_type, name, version, stability, introduced_in,
                    deprecated_in, removed_in, schema_ref, documentation_ref,
                    created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, '1.3.0', NULL, NULL, ?, ?, ?, ?)
                """,
                (
                    contract_id,
                    contract_type,
                    name,
                    version,
                    stability,
                    schema_ref,
                    docs_ref,
                    now,
                    json.dumps({"milestone": "M12", "llm_governance_beta": True}, sort_keys=True),
                ),
            )

        matrix = [
            ("core", "aletheia-memory", "1.3.0", "supported", "M12 governed LLM memory formation"),
            ("llm_provider", "mock_llm", "1.0", "beta", "Deterministic structured-output LLM provider"),
            ("cli", "aletheia", "1.3.0", "supported", "Governed LLM command group"),
        ]
        for component_type, component_name, version, status, notes in matrix:
            row_id = f"compat_{content_hash(f'm12\0{component_type}\0{component_name}\0{version}')[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO compatibility_matrix_entries (
                    id, component_type, component_name, component_version,
                    aletheia_min_version, aletheia_max_version, status,
                    tested_at, notes, metadata_json
                )
                VALUES (?, ?, ?, ?, '1.3.0', NULL, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    component_type,
                    component_name,
                    version,
                    status,
                    now,
                    notes,
                    json.dumps({"source": "M12 defaults"}, sort_keys=True),
                ),
            )

        suite_id = f"suite_{content_hash('llm-governance')[:24]}"
        self.connection.execute(
            """
            INSERT OR IGNORE INTO conformance_suites (
                id, name, suite_type, version, description,
                required_for_v1, created_at, metadata_json
            )
            VALUES (?, 'llm-governance', 'llm_governance', '1.3.0', ?, 0, ?, ?)
            """,
            (
                suite_id,
                "LLM candidate-only outputs, provenance, and privacy policy conformance",
                now,
                json.dumps({"milestone": "M12"}, sort_keys=True),
            ),
        )
        cases = [
            ("contract_registered", "LLM governance contract is registered", "critical"),
            ("governance_preserved", "LLM outputs remain candidates/drafts", "critical"),
            ("privacy_enforced", "LLM privacy leak checks are available", "critical"),
        ]
        for case_name, description, severity in cases:
            case_id = f"case_{content_hash(f'{suite_id}\0{case_name}')[:24]}"
            self.connection.execute(
                """
                INSERT OR IGNORE INTO conformance_cases (
                    id, suite_id, name, description, severity,
                    required, test_ref, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    case_id,
                    suite_id,
                    case_name,
                    description,
                    severity,
                    f"m12.llm_governance.{case_name}",
                    now,
                    json.dumps({}, sort_keys=True),
                ),
            )


def _deterministic_entity_id(namespace: str, entity_type: str, value: str) -> str:
    return "ent_" + content_hash(f"{namespace}\0{entity_type}\0{value}")[:24]
