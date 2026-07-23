"""Aletheia local memory kernel."""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import aletheia.core.federation as federation
import aletheia.core.hardening as production
import aletheia.core.platform as stable_platform
from aletheia.core.errors import NotFoundError, ValidationError
from aletheia.core.ids import content_hash, new_id, stable_event_id
from aletheia.core.time import parse_iso, utc_now, utc_now_iso
from aletheia.extraction import extractor_for_name
from aletheia.llm import LLMInvocation, input_hash as llm_input_hash, output_hash as llm_output_hash, provider_for_name as llm_provider_for_name
from aletheia.models import (
    AbstractionRecord,
    CandidateClaim,
    CategoryLabel,
    Claim,
    ClaimExplanation,
    ClaimRelationship,
    ClaimScope,
    ConfidenceSnapshot,
    Conflict,
    ConflictFamily,
    ConflictResolution,
    ContextTraceItem,
    ContentRiskFlag,
    ContextItem,
    ContextPack,
    ContextUsageEvent,
    ContextWarning,
    CurationDecision,
    DerivationEdge,
    DerivationTrace,
    Entity,
    EntityMention,
    EvaluationCase,
    EvaluationMetric,
    EvaluationRun,
    EvaluationSet,
    EvidenceSpan,
    EvidenceEvent,
    ExtractionDecision,
    ExtractionPolicy,
    ExtractionRun,
    FeedbackRecord,
    HalfLifePolicy,
    InferenceCandidate,
    InferenceDecision,
    InferenceExplanation,
    InferenceRule,
    InferenceRun,
    InvalidationEvent,
    IngestionBatch,
    LearningRun,
    LocalJob,
    MemoryHealthReport,
    MemoryUsageEvent,
    MetricSnapshot,
    NotificationEvent,
    OmittedMemory,
    OptimizationRun,
    PolicyApplicationRecord,
    PolicyProposal,
    Project,
    ProcedureUpdateProposal,
    ProcedureVersion,
    RankingPolicy,
    RankingPolicyVersion,
    Reflection,
    ReflectionExpansion,
    ReportExport,
    RetrievalJudgment,
    RetrievalTraceItem,
    ReviewTask,
    ReviewTaskEvent,
    RollbackRecord,
    SemanticIndexRun,
    RuleExecutionResult,
    SemanticCluster,
    SemanticRelation,
    SourceDocument,
    Session,
    TaskOutcome,
    TraceEvent,
    TraceRun,
)
from aletheia.models.retrieval import RetrievalResult
from aletheia.retrieval.lexical import (
    EXCLUDED_ALWAYS,
    MEMORY_TYPE_PRIORITY,
    STATUS_PRIORITY,
    SQLiteFTSRetriever,
    claim_text,
    governed_claim_filter,
    lexical_score,
    recency_score,
)
from aletheia.semantic import (
    SQLiteVectorStore,
    VectorRecord,
    embed_texts_with_metadata,
    provider_for_name,
    semantic_index_version,
)
from aletheia.storage import SCHEMA_VERSION, SQLiteStore

ACTIVE_STATUSES = ("active", "core")
RETRIEVABLE_STATUSES = ("candidate", "active", "core")
CLAIM_STATUSES = {
    "candidate",
    "active",
    "core",
    "disputed",
    "superseded",
    "rejected",
    "archived",
}
DEFAULT_HALF_LIVES = {
    "current_task": 3.0,
    "task": 3.0,
    "temporary_preference": 14.0,
    "project": 30.0,
    "project_state": 30.0,
    "session_summary": 45.0,
    "preference": 180.0,
    "identity": 1000.0,
    "profile": 1000.0,
    "domain_knowledge": 1000.0,
    "procedure": 365.0,
    "tool_usage": 90.0,
    "inference": 14.0,
    "correction": 1000.0,
}
PRIVACY_LEVELS = {"public", "personal", "private", "sensitive", "secret"}
CANDIDATE_MEMORY_TYPES = set(DEFAULT_HALF_LIVES) | {"fact", "decision", "episodic"}
FEEDBACK_SIGNALS = {
    "confirmed",
    "wrong",
    "stale",
    "useful",
    "not_useful",
    "contradicted",
    "verified",
    "irrelevant",
    "important",
    "unimportant",
}
RELATIONSHIP_TYPES = {
    "supports",
    "contradicts",
    "supersedes",
    "duplicate_of",
    "refines",
    "scopes",
    "derived_from",
}
SCOPE_TYPES = {"temporal", "contextual", "project", "session", "agent", "conditional"}
PROMOTION_TARGETS = {"active", "core"}
DEMOTION_TARGETS = {"candidate", "disputed", "superseded", "archived", "rejected"}
RESOLUTION_STRATEGIES = {
    "latest_wins",
    "highest_confidence_wins",
    "user_correction_wins",
    "verified_source_wins",
    "context_scope",
    "time_scope",
    "merge_duplicates",
    "mark_unresolved",
    "reject_weak_claims",
    "manual",
}
CANDIDATE_STATUSES = {
    "pending_review",
    "validated",
    "promoted",
    "rejected",
    "merged",
    "duplicate",
    "needs_evidence",
    "needs_scope",
    "needs_conflict_resolution",
    "invalid",
}
CANDIDATE_EDITABLE_STATUSES = {
    "pending_review",
    "needs_evidence",
    "needs_scope",
    "needs_conflict_resolution",
    "invalid",
}
REVIEW_DECISIONS = {
    "validate",
    "reject",
    "edit",
    "mark_duplicate",
    "needs_scope",
    "needs_conflict_resolution",
    "defer",
    "promote",
}
ENTITY_TYPES = {
    "user",
    "agent",
    "project",
    "person",
    "organization",
    "file",
    "tool",
    "concept",
    "location",
    "event",
    "memory_system",
    "unknown",
}
EVIDENCE_SPAN_ROLES = {"supporting", "contradicting", "context", "source_metadata"}
RISK_LEVELS = {"low", "medium", "high", "critical"}
SEMANTIC_TARGET_TYPES = {"evidence", "candidate_claims", "claims", "source_documents"}
INFERENCE_ENGINES = {"logical", "semantic", "factual", "reflection"}
INFERENCE_TYPES = {
    "logical",
    "semantic",
    "factual",
    "reflection",
    "abstraction",
    "scope_match",
    "temporal_currentness",
    "duplicate_relation",
    "category_relation",
    "project_relation",
}
INFERENCE_STRENGTHS = {
    "entailed",
    "strong",
    "probable",
    "weak",
    "speculative",
    "retrieval_hint",
}
INFERENCE_STATUSES = {
    "pending_review",
    "validated",
    "promoted",
    "rejected",
    "superseded",
    "stale",
    "invalidated",
    "needs_source_review",
    "needs_conflict_resolution",
}
INFERENCE_EDITABLE_STATUSES = {
    "pending_review",
    "stale",
    "invalidated",
    "needs_source_review",
    "needs_conflict_resolution",
}
INFERENCE_REVIEW_DECISIONS = {
    "validate",
    "reject",
    "edit",
    "defer",
    "mark_speculative",
    "needs_conflict_resolution",
    "needs_source_review",
}
RULE_TYPES = {
    "logical",
    "temporal",
    "scope",
    "conflict",
    "dependency",
    "factual",
    "classification",
    "reflection",
}
DERIVATION_RELATIONSHIPS = {
    "derived_from",
    "entailed_by",
    "supported_by",
    "summarizes",
    "abstracts",
    "clusters_with",
    "semantically_related_to",
    "depends_on",
    "invalidated_by",
    "refreshes",
}
REFLECTION_STATUSES = {"candidate", "active", "core", "stale", "invalidated", "archived", "rejected"}
INVALIDATION_MODES = {"mark_stale", "invalidate", "queue_refresh", "recompute"}
SEMANTIC_RELATION_TYPES = {
    "related_to",
    "similar_to",
    "possibly_duplicate",
    "category_related",
    "conceptually_near",
    "retrieval_hint",
}
USAGE_TARGET_TYPES = {
    "claim",
    "candidate_claim",
    "inference",
    "reflection",
    "abstraction",
    "context_pack",
    "procedure",
    "policy",
}
USAGE_TYPES = {
    "retrieved",
    "included_in_context",
    "used_by_agent",
    "ignored",
    "expanded",
    "audited",
    "corrected",
    "confirmed",
    "rejected",
}
TASK_OUTCOMES = {
    "success",
    "partial_success",
    "failure",
    "user_corrected",
    "user_rejected",
    "user_confirmed",
    "irrelevant_context",
    "missing_context",
    "stale_context",
    "conflicting_context",
    "unsafe_context",
    "unknown",
}
RETRIEVAL_JUDGMENTS = {
    "relevant",
    "irrelevant",
    "missing",
    "too_stale",
    "conflicting",
    "wrong",
    "useful",
    "not_useful",
    "should_rank_higher",
    "should_rank_lower",
}
POLICY_TYPES = {
    "ranking",
    "context_pack",
    "curation",
    "half_life",
    "reflection_refresh",
    "candidate_promotion",
    "inference_promotion",
}
POLICY_PROPOSAL_STATUSES = {
    "draft",
    "pending_review",
    "approved",
    "rejected",
    "applied",
    "superseded",
    "rolled_back",
}
POLICY_REVIEW_DECISIONS = {"approve", "reject", "defer", "request_changes"}
OPTIMIZATION_OBJECTIVES = {
    "balanced",
    "maximize_recall",
    "maximize_precision",
    "minimize_conflict_leakage",
    "minimize_stale_leakage",
    "maximize_token_efficiency",
    "project_recall",
    "procedure_recall",
}
LEARNING_TARGETS = {
    "retrieval_policy",
    "context_pack_policy",
    "curation_policy",
    "half_life_policy",
    "procedure_memory",
    "reflection_refresh",
    "candidate_promotion_policy",
}
JOB_TYPES = {
    "recompute_confidence",
    "run_decay",
    "detect_conflicts",
    "curate",
    "refresh_reflections",
    "run_inference",
    "index_semantic",
    "run_evaluation",
    "optimize_retrieval",
    "run_learning",
    "memory_health_check",
}
JOB_STATUSES = {"pending", "running", "completed", "failed", "cancelled", "deferred"}
REVIEW_TASK_TYPES = {
    "candidate_review",
    "conflict_resolution",
    "inference_review",
    "reflection_refresh",
    "policy_review",
    "procedure_review",
    "stale_core_memory",
    "health_warning",
    "privacy_warning",
    "risk_flag_review",
    "job_failure",
    "access_review",
    "service_warning",
}
REVIEW_TASK_STATUSES = {"open", "in_progress", "resolved", "dismissed", "deferred", "blocked"}
REVIEW_SEVERITIES = {"info", "low", "medium", "high", "critical"}
REVIEW_EVENT_TYPES = {"created", "assigned", "commented", "action_taken", "resolved", "dismissed", "deferred", "reopened"}
NOTIFICATION_STATUSES = {"unread", "read", "dismissed", "snoozed", "resolved"}
TRACE_TYPES = {"retrieval", "context_pack", "curation", "inference", "policy_evaluation"}
REPORT_TYPES = {
    "memory_health",
    "review_queue",
    "conflict_summary",
    "candidate_summary",
    "policy_review",
    "audit_summary",
    "service_activity",
}
BASE_CATEGORY_LABELS = [
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
RISK_PATTERNS = [
    ("prompt_injection", "high", r"ignore\s+(all\s+)?previous\s+instructions"),
    ("memory_poisoning_attempt", "high", r"store\s+this\s+as\s+(a\s+)?core\s+memory"),
    ("memory_poisoning_attempt", "high", r"promote\s+this\s+to\s+core"),
    ("unsafe_instruction", "critical", r"delete\s+all\s+other\s+memories"),
    ("memory_poisoning_attempt", "medium", r"permanent\s+memory"),
]


class Memory:
    """Public center of the Aletheia memory kernel."""

    def __init__(
        self,
        store: SQLiteStore,
        namespace: str = "user/default",
        config: dict[str, Any] | None = None,
    ):
        self.store = store
        self.namespace = namespace
        self.config = config or {}
        self.retriever = SQLiteFTSRetriever(store.connection)

    @classmethod
    def open(
        cls,
        path: str,
        namespace: str = "user/default",
        config: dict[str, Any] | None = None,
        auto_migrate: bool = True,
    ) -> "Memory":
        return cls(
            SQLiteStore.open(path, auto_migrate=auto_migrate),
            namespace=namespace,
            config=config,
        )

    def migrate(self) -> dict[str, str]:
        self.store.migrate()
        return self.health()

    def close(self) -> None:
        self.store.close()

    def health(self) -> dict[str, str]:
        row = self.store.connection.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        ).fetchone()
        return {
            "status": "ok",
            "database": "connected",
            "schema_version": row["version"] if row else SCHEMA_VERSION,
        }

    def create_backup(self, **kwargs):
        return production.create_backup(self, **kwargs)

    def verify_backup(self, **kwargs):
        return production.verify_backup(self, **kwargs)

    def get_backup(self, backup_id: str):
        return production.get_backup(self, backup_id)

    def list_backups(self, **kwargs):
        return production.list_backups(self, **kwargs)

    def restore_backup(self, **kwargs):
        return production.restore_backup(**kwargs)

    def protected_mode_status(self):
        return production.protected_mode_status(self)

    def enable_protected_mode(self, **kwargs):
        return production.enable_protected_mode(self, **kwargs)

    def create_key(self, **kwargs):
        return production.create_key(self, **kwargs)

    def get_key(self, key_id: str):
        return production.get_key(self, key_id)

    def list_keys(self, **kwargs):
        return production.list_keys(self, **kwargs)

    def rotate_key(self, **kwargs):
        return production.rotate_key(self, **kwargs)

    def redact(self, **kwargs):
        return production.redact(self, **kwargs)

    def forget(self, **kwargs):
        return production.forget(self, **kwargs)

    def list_tombstones(self, **kwargs):
        return production.list_tombstones(self, **kwargs)

    def create_retention_policy(self, **kwargs):
        return production.create_retention_policy(self, **kwargs)

    def list_retention_policies(self, **kwargs):
        return production.list_retention_policies(self, **kwargs)

    def run_retention(self, **kwargs):
        return production.run_retention(self, **kwargs)

    def integrity_check(self, **kwargs):
        return production.integrity_check(self, **kwargs)

    def list_integrity_runs(self, **kwargs):
        return production.list_integrity_runs(self, **kwargs)

    def list_integrity_findings(self, **kwargs):
        return production.list_integrity_findings(self, **kwargs)

    def repair_integrity(self, **kwargs):
        return production.repair_integrity(self, **kwargs)

    def migration_plan(self, **kwargs):
        return production.migration_plan(self, **kwargs)

    def migration_apply(self, **kwargs):
        return production.migration_apply(self, **kwargs)

    def compact_database(self, **kwargs):
        return production.compact_database(self, **kwargs)

    def export_archive(self, **kwargs):
        return production.export_archive(self, **kwargs)

    def import_archive(self, **kwargs):
        return production.import_archive(self, **kwargs)

    def support_bundle(self, **kwargs):
        return production.support_bundle(self, **kwargs)

    def benchmark_run(self, **kwargs):
        return production.benchmark_run(self, **kwargs)

    def list_benchmarks(self, **kwargs):
        return production.list_benchmarks(self, **kwargs)

    def list_benchmark_results(self, benchmark_run_id: str):
        return production.list_benchmark_results(self, benchmark_run_id)

    def release_manifest(self, **kwargs):
        return production.release_manifest(self, **kwargs)

    def readiness_check(self, **kwargs):
        return production.readiness_check(self, **kwargs)

    def register_public_contract(self, **kwargs):
        return stable_platform.register_public_contract(self, **kwargs)

    def list_public_contracts(self, **kwargs):
        return stable_platform.list_public_contracts(self, **kwargs)

    def get_public_contract(self, contract_id_or_name: str):
        return stable_platform.get_public_contract(self, contract_id_or_name)

    def list_api_contract_versions(self, **kwargs):
        return stable_platform.list_api_contract_versions(self, **kwargs)

    def list_deprecations(self, **kwargs):
        return stable_platform.list_deprecations(self, **kwargs)

    def check_deprecations(self):
        return stable_platform.check_deprecations(self)

    def discover_plugins(self, path: str):
        return stable_platform.discover_plugins(path)

    def install_plugin(self, **kwargs):
        return stable_platform.install_plugin(self, **kwargs)

    def enable_plugin(self, plugin_id: str, **kwargs):
        return stable_platform.enable_plugin(self, plugin_id, **kwargs)

    def disable_plugin(self, plugin_id: str, **kwargs):
        return stable_platform.disable_plugin(self, plugin_id, **kwargs)

    def list_plugins(self, **kwargs):
        return stable_platform.list_plugins(self, **kwargs)

    def get_plugin_installation(self, plugin_id_or_name: str):
        return stable_platform.get_plugin_installation(self, plugin_id_or_name)

    def get_plugin_manifest(self, manifest_id: str):
        return stable_platform.get_plugin_manifest(self, manifest_id)

    def list_plugin_logs(self, **kwargs):
        return stable_platform.list_plugin_logs(self, **kwargs)

    def log_plugin_execution(self, **kwargs):
        return stable_platform.log_plugin_execution(self, **kwargs)

    def run_plugin_operation(self, **kwargs):
        return stable_platform.run_plugin_operation(self, **kwargs)

    def list_conformance_suites(self):
        return stable_platform.list_conformance_suites(self)

    def get_conformance_suite(self, suite: str):
        return stable_platform.get_conformance_suite(self, suite)

    def list_conformance_cases(self, suite_id: str):
        return stable_platform.list_conformance_cases(self, suite_id)

    def run_conformance(self, **kwargs):
        return stable_platform.run_conformance(self, **kwargs)

    def list_conformance_runs(self, **kwargs):
        return stable_platform.list_conformance_runs(self, **kwargs)

    def get_conformance_run(self, run_id: str):
        return stable_platform.get_conformance_run(self, run_id)

    def list_conformance_results(self, run_id: str):
        return stable_platform.list_conformance_results(self, run_id)

    def compatibility_report(self, **kwargs):
        return stable_platform.compatibility_report(self, **kwargs)

    def list_compatibility_matrix(self, **kwargs):
        return stable_platform.list_compatibility_matrix(self, **kwargs)

    def compatibility_status(self, **kwargs):
        return stable_platform.compatibility_status(self, **kwargs)

    def list_sdk_releases(self):
        return stable_platform.list_sdk_releases(self)

    def scaffold_adapter(self, **kwargs):
        return stable_platform.scaffold_adapter(self, **kwargs)

    def list_examples(self):
        return stable_platform.list_examples(self)

    def build_docs(self, **kwargs):
        return stable_platform.build_docs(self, **kwargs)

    def list_documentation_builds(self, **kwargs):
        return stable_platform.list_documentation_builds(self, **kwargs)

    def docs_status(self):
        return stable_platform.docs_status(self)

    def test_doc_examples(self):
        return stable_platform.test_doc_examples(self)

    def doctor_run(self, **kwargs):
        return stable_platform.doctor_run(self, **kwargs)

    def list_doctor_runs(self, **kwargs):
        return stable_platform.list_doctor_runs(self, **kwargs)

    def get_doctor_run(self, run_id: str):
        return stable_platform.get_doctor_run(self, run_id)

    def v1_gate_run(self, **kwargs):
        return stable_platform.v1_gate_run(self, **kwargs)

    def list_v1_gate_runs(self, **kwargs):
        return stable_platform.list_v1_gate_runs(self, **kwargs)

    def get_v1_gate_run(self, run_id: str):
        return stable_platform.get_v1_gate_run(self, run_id)

    def certify_adapter(self, **kwargs):
        return stable_platform.certify_adapter(self, **kwargs)

    def list_adapter_certifications(self):
        return stable_platform.list_adapter_certifications(self)

    def create_federation_identity(self, **kwargs):
        return federation.create_federation_identity(self, **kwargs)

    def active_federation_identity(self, **kwargs):
        return federation.active_federation_identity(self, **kwargs)

    def get_federation_identity(self, identity_id: str):
        return federation.get_federation_identity(self, identity_id)

    def list_federation_identities(self):
        return federation.list_federation_identities(self)

    def export_federation_identity(self, **kwargs):
        return federation.export_federation_identity(self, **kwargs)

    def rotate_federation_key(self, **kwargs):
        return federation.rotate_federation_key(self, **kwargs)

    def federation_status(self):
        return federation.federation_status(self)

    def add_peer(self, **kwargs):
        return federation.add_peer(self, **kwargs)

    def get_peer(self, peer_id: str):
        return federation.get_peer(self, peer_id)

    def list_peers(self, **kwargs):
        return federation.list_peers(self, **kwargs)

    def trust_peer(self, peer_id: str, **kwargs):
        return federation.trust_peer(self, peer_id, **kwargs)

    def revoke_peer(self, peer_id: str, **kwargs):
        return federation.revoke_peer(self, peer_id, **kwargs)

    def list_trust_domains(self):
        return federation.list_trust_domains(self)

    def get_trust_domain(self, trust_domain_id_or_name: str):
        return federation.get_trust_domain(self, trust_domain_id_or_name)

    def create_share_grant(self, **kwargs):
        return federation.create_share_grant(self, **kwargs)

    def get_share_grant(self, share_id: str):
        return federation.get_share_grant(self, share_id)

    def list_share_grants(self, **kwargs):
        return federation.list_share_grants(self, **kwargs)

    def list_share_recipients(self, share_grant_id: str | None = None):
        return federation.list_share_recipients(self, share_grant_id)

    def revoke_share_grant(self, share_id: str, **kwargs):
        return federation.revoke_share_grant(self, share_id, **kwargs)

    def get_sync_collection(self, collection_id_or_share: str):
        return federation.get_sync_collection(self, collection_id_or_share)

    def list_sync_collections(self, **kwargs):
        return federation.list_sync_collections(self, **kwargs)

    def export_share_bundle(self, **kwargs):
        return federation.export_share_bundle(self, **kwargs)

    def import_share_bundle(self, **kwargs):
        return federation.import_share_bundle(self, **kwargs)

    def sync(self, **kwargs):
        return federation.sync(self, **kwargs)

    def get_sync_run(self, sync_run_id: str):
        return federation.get_sync_run(self, sync_run_id)

    def list_sync_runs(self, **kwargs):
        return federation.list_sync_runs(self, **kwargs)

    def get_sync_changeset(self, changeset_id: str):
        return federation.get_sync_changeset(self, changeset_id)

    def list_sync_change_items(self, changeset_id: str):
        return federation.list_sync_change_items(self, changeset_id)

    def list_replication_cursors(self, **kwargs):
        return federation.list_replication_cursors(self, **kwargs)

    def list_remote_sources(self, **kwargs):
        return federation.list_remote_sources(self, **kwargs)

    def list_import_trust_policies(self):
        return federation.list_import_trust_policies(self)

    def list_sync_conflicts(self, **kwargs):
        return federation.list_sync_conflicts(self, **kwargs)

    def get_sync_conflict(self, conflict_id: str):
        return federation.get_sync_conflict(self, conflict_id)

    def resolve_sync_conflict(self, conflict_id: str, **kwargs):
        return federation.resolve_sync_conflict(self, conflict_id, **kwargs)

    def list_sync_conflict_resolutions(self, conflict_id: str | None = None):
        return federation.list_sync_conflict_resolutions(self, conflict_id)

    def list_revocations(self, **kwargs):
        return federation.list_revocations(self, **kwargs)

    def propagate_revocations(self, **kwargs):
        return federation.propagate_revocations(self, **kwargs)

    def list_consent_records(self, **kwargs):
        return federation.list_consent_records(self, **kwargs)

    def list_federation_audit_events(self, **kwargs):
        return federation.list_federation_audit_events(self, **kwargs)

    def list_sync_tombstones(self, **kwargs):
        return federation.list_sync_tombstones(self, **kwargs)

    def create_workspace(self, **kwargs):
        return federation.create_workspace(self, **kwargs)

    def get_workspace(self, workspace_id_or_name: str):
        return federation.get_workspace(self, workspace_id_or_name)

    def list_workspaces(self, **kwargs):
        return federation.list_workspaces(self, **kwargs)

    def add_workspace_member(self, workspace_id: str, **kwargs):
        return federation.add_workspace_member(self, workspace_id=workspace_id, **kwargs)

    def remove_workspace_member(self, workspace_id: str, member_id: str, **kwargs):
        return federation.remove_workspace_member(self, workspace_id=workspace_id, member_id=member_id, **kwargs)

    def get_workspace_member(self, workspace_id: str, member_type: str, member_id: str):
        return federation.get_workspace_member(self, workspace_id, member_type, member_id)

    def list_workspace_members(self, workspace_id: str):
        return federation.list_workspace_members(self, workspace_id)

    def workspace_role_allows(self, role: str, action: str) -> bool:
        return federation.workspace_role_allows(role, action)

    def create_agent_group(self, **kwargs):
        return federation.create_agent_group(self, **kwargs)

    def get_agent_group(self, group_id_or_name: str):
        return federation.get_agent_group(self, group_id_or_name)

    def list_agent_groups(self, **kwargs):
        return federation.list_agent_groups(self, **kwargs)

    def add_agent_group_member(self, group_id: str, **kwargs):
        return federation.add_agent_group_member(self, agent_group_id=group_id, **kwargs)

    def get_agent_group_member(self, group_id: str, agent_id: str):
        return federation.get_agent_group_member(self, group_id, agent_id)

    def list_agent_group_members(self, group_id: str):
        return federation.list_agent_group_members(self, group_id)

    def agent_group_allows(self, group_id: str, capability: str) -> bool:
        return federation.agent_group_allows(self, agent_group_id=group_id, capability=capability)

    def federation_conformance(self):
        return federation.federation_conformance(self)

    def write_event(
        self,
        *,
        namespace: str | None = None,
        source_type: str,
        content: str,
        session_id: str | None = None,
        source_uri: str | None = None,
        observed_at: str | None = None,
        trust_level: str = "unknown",
        privacy_level: str = "personal",
        retention_policy: str = "default",
    ) -> EvidenceEvent:
        namespace = namespace or self.namespace
        self._require_text(namespace, "namespace")
        self._require_text(source_type, "source_type")
        self._require_text(content, "content")

        event_id = stable_event_id(
            namespace=namespace,
            session_id=session_id,
            source_type=source_type,
            source_uri=source_uri,
            content=content,
        )
        existing = self.store.connection.execute(
            "SELECT * FROM evidence_events WHERE id = ?",
            (event_id,),
        ).fetchone()
        if existing:
            return self.read_event(event_id)

        now = utc_now_iso()
        content_digest = content_hash(content)
        stored_content = production.protect_content_for_storage(
            self,
            content,
            privacy_level=privacy_level,
        )
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO evidence_events (
                    id, namespace, session_id, source_type, source_uri, content,
                    content_hash, created_at, observed_at, trust_level,
                    privacy_level, retention_policy
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    namespace,
                    session_id,
                    source_type,
                    source_uri,
                    stored_content,
                    content_digest,
                    now,
                    observed_at,
                    trust_level,
                    privacy_level,
                    retention_policy,
                ),
            )
            self._write_audit(
                namespace=namespace,
                target_type="evidence",
                target_id=event_id,
                action="event.write",
                details={"source_type": source_type, "content_hash": content_digest},
            )
        return self.read_event(event_id)

    def read_event(self, event_id: str) -> EvidenceEvent:
        row = self.store.connection.execute(
            "SELECT * FROM evidence_events WHERE id = ?",
            (event_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Evidence event not found: {event_id}")
        event = EvidenceEvent.from_row(row)
        revealed = production.reveal_content_from_storage(self, event.content)
        if revealed != event.content:
            return replace(event, content=revealed)
        return event

    def list_events(
        self, *, namespace: str | None = None, limit: int = 50
    ) -> list[EvidenceEvent]:
        namespace = namespace or self.namespace
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM evidence_events
            WHERE namespace = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (namespace, limit),
        ).fetchall()
        return [self.read_event(row["id"]) for row in rows]

    def ingest(
        self,
        namespace: str,
        *,
        source_type: str,
        content: str,
        source_uri: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        title: str | None = None,
        metadata: dict | None = None,
        privacy_level: str = "personal",
        trust_level: str = "unknown",
    ) -> IngestionBatch:
        self._require_text(namespace, "namespace")
        self._require_text(source_type, "source_type")
        self._require_text(content, "content")
        event = self.write_event(
            namespace=namespace,
            source_type=source_type,
            source_uri=source_uri,
            session_id=session_id,
            content=content,
            trust_level=trust_level,
            privacy_level=privacy_level,
        )
        batch_id = new_id("ing")
        document_id = new_id("src")
        now = utc_now_iso()
        digest = content_hash(content)
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO ingestion_batches (
                    id, namespace, source_type, source_uri, title, project_id,
                    session_id, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    namespace,
                    source_type,
                    source_uri,
                    title,
                    project_id,
                    session_id,
                    now,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            self.store.connection.execute(
                """
                INSERT INTO ingestion_batch_evidence_links (batch_id, evidence_id)
                VALUES (?, ?)
                """,
                (batch_id, event.id),
            )
            self.store.connection.execute(
                """
                INSERT INTO source_documents (
                    id, namespace, batch_id, title, source_type, source_uri,
                    content_hash, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    namespace,
                    batch_id,
                    title,
                    source_type,
                    source_uri,
                    digest,
                    now,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            self._write_audit(
                namespace=namespace,
                target_type="ingestion_batch",
                target_id=batch_id,
                action="ingestion.create",
                details={
                    "source_type": source_type,
                    "source_uri": source_uri,
                    "project_id": project_id,
                    "session_id": session_id,
                    "evidence_ids": [event.id],
                },
            )
            self._write_audit(
                namespace=namespace,
                target_type="evidence",
                target_id=event.id,
                action="ingestion.link_evidence",
                details={"batch_id": batch_id, "source_document_id": document_id},
            )
            self._flag_content_risks(
                namespace=namespace,
                evidence_id=event.id,
                content=content,
            )
        return self.read_ingestion_batch(batch_id)

    def read_ingestion_batch(self, batch_id: str) -> IngestionBatch:
        row = self.store.connection.execute(
            "SELECT * FROM ingestion_batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Ingestion batch not found: {batch_id}")
        return IngestionBatch.from_row(row, self._evidence_ids_for_batch(batch_id))

    def list_source_documents(
        self,
        *,
        namespace: str | None = None,
        batch_id: str | None = None,
        limit: int = 50,
    ) -> list[SourceDocument]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if batch_id:
            clause += " AND batch_id = ?"
            params.append(batch_id)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM source_documents
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [SourceDocument.from_row(row) for row in rows]

    def list_content_risk_flags(
        self,
        *,
        namespace: str | None = None,
        evidence_id: str | None = None,
    ) -> list[ContentRiskFlag]:
        params: list[object] = []
        clauses: list[str] = []
        if evidence_id:
            clauses.append("evidence_id = ?")
            params.append(evidence_id)
        else:
            namespace = namespace or self.namespace
            clauses.append("namespace = ?")
            params.append(namespace)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM content_risk_flags
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at ASC, id ASC
            """,
            params,
        ).fetchall()
        return [ContentRiskFlag.from_row(row) for row in rows]

    def extract_candidates(
        self,
        namespace: str,
        *,
        batch_id: str | None = None,
        evidence_ids: list[str] | None = None,
        extractor: str = "rule_based",
        extraction_policy: str | dict | ExtractionPolicy | None = None,
        dry_run: bool = False,
        max_candidates: int | None = None,
    ) -> ExtractionRun:
        self._require_text(namespace, "namespace")
        if batch_id:
            batch = self.read_ingestion_batch(batch_id)
            if batch.namespace != namespace:
                raise ValidationError("Ingestion batch belongs to a different namespace.")
            selected_evidence_ids = list(batch.evidence_ids)
        else:
            selected_evidence_ids = list(evidence_ids or [])
        if not selected_evidence_ids:
            raise ValidationError("extract_candidates requires batch_id or evidence_ids.")
        evidence = [self.read_event(evidence_id) for evidence_id in selected_evidence_ids]
        for event in evidence:
            if event.namespace != namespace:
                raise ValidationError(f"Evidence {event.id} belongs to {event.namespace!r}.")
        policy = self._coerce_extraction_policy(extraction_policy)
        if max_candidates is not None:
            policy = ExtractionPolicy(
                allowed_memory_types=policy.allowed_memory_types,
                max_candidates_per_event=max_candidates,
                require_evidence_spans=policy.require_evidence_spans,
                allow_inference_candidates=policy.allow_inference_candidates,
                allow_preference_candidates=policy.allow_preference_candidates,
                allow_procedure_candidates=policy.allow_procedure_candidates,
                allow_project_candidates=policy.allow_project_candidates,
                min_candidate_confidence=policy.min_candidate_confidence,
                privacy_mode=policy.privacy_mode,
                auto_promote=False,
            )
        try:
            engine = extractor_for_name(extractor)
            drafts = engine.extract(
                namespace=namespace,
                evidence=evidence,
                policy=policy,
            )
        except NotImplementedError as exc:
            raise ValidationError(str(exc)) from exc
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        if max_candidates is not None:
            drafts = drafts[:max_candidates]
        warnings: list[str] = []
        run_id = new_id("run")
        now = utc_now_iso()
        stored_count = 0 if dry_run else len(drafts)
        llm_invocation = getattr(engine, "last_invocation", None)
        llm_run_id: str | None = None
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO extraction_runs (
                    id, namespace, batch_id, extractor_name, extractor_version,
                    policy_json, candidate_count, stored_candidate_count, dry_run,
                    created_at, warnings_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    namespace,
                    batch_id,
                    engine.name,
                    engine.version,
                    json.dumps(policy.to_dict(), sort_keys=True),
                    len(drafts),
                    stored_count,
                    int(dry_run),
                    now,
                    json.dumps(warnings, sort_keys=True),
                ),
            )
            if isinstance(llm_invocation, LLMInvocation):
                llm_run_id = self._store_llm_invocation(
                    namespace=namespace,
                    invocation=llm_invocation,
                    related_run_id=run_id,
                )
                warnings.extend(llm_invocation.warnings)
                if warnings:
                    self.store.connection.execute(
                        "UPDATE extraction_runs SET warnings_json = ? WHERE id = ?",
                        (json.dumps(warnings, sort_keys=True), run_id),
                    )
            for evidence_id in selected_evidence_ids:
                self.store.connection.execute(
                    """
                    INSERT INTO extraction_run_evidence_links (
                        extraction_run_id, evidence_id
                    )
                    VALUES (?, ?)
                    """,
                    (run_id, evidence_id),
                )
            if not dry_run:
                evidence_by_id = {event.id: event for event in evidence}
                for draft in drafts:
                    if llm_run_id:
                        draft = replace(
                            draft,
                            metadata={
                                **dict(draft.metadata),
                                "llm_run_id": llm_run_id,
                                "llm_task_type": "extract_candidates",
                            },
                        )
                    candidate_warnings = self._store_candidate_draft(
                        namespace=namespace,
                        run_id=run_id,
                        draft=draft,
                        evidence_by_id=evidence_by_id,
                    )
                    warnings.extend(candidate_warnings)
                if warnings:
                    self.store.connection.execute(
                        """
                        UPDATE extraction_runs
                        SET warnings_json = ?
                        WHERE id = ?
                        """,
                        (json.dumps(warnings, sort_keys=True), run_id),
                    )
                if llm_run_id:
                    self._store_llm_outputs_for_targets(
                        llm_run_id=llm_run_id,
                        output_type="candidate_claim",
                        rows=self.store.connection.execute(
                            "SELECT id, candidate_status, metadata_json FROM candidate_claims WHERE extraction_run_id = ?",
                            (run_id,),
                        ).fetchall(),
                    )
            self._write_audit(
                namespace=namespace,
                target_type="extraction_run",
                target_id=run_id,
                action="extraction.run",
                details={
                    "batch_id": batch_id,
                    "evidence_ids": selected_evidence_ids,
                    "extractor": engine.name,
                    "dry_run": dry_run,
                    "candidate_count": len(drafts),
                    "stored_candidate_count": stored_count,
                },
            )
        return self.read_extraction_run(run_id)

    def read_extraction_run(self, run_id: str) -> ExtractionRun:
        row = self.store.connection.execute(
            "SELECT * FROM extraction_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Extraction run not found: {run_id}")
        return ExtractionRun.from_row(row, self._evidence_ids_for_extraction_run(run_id))

    def list_llm_runs(
        self,
        *,
        namespace: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        clauses: list[str] = []
        if namespace:
            clauses.append("namespace = ?")
            params.append(namespace)
        if task_type:
            clauses.append("task_type = ?")
            params.append(task_type)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM llm_runs
            {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [self._llm_run_dict(row) for row in rows]

    def read_llm_run(self, llm_run_id: str) -> dict[str, Any]:
        row = self.store.connection.execute("SELECT * FROM llm_runs WHERE id = ?", (llm_run_id,)).fetchone()
        if not row:
            raise NotFoundError(f"LLM run not found: {llm_run_id}")
        result = self._llm_run_dict(row)
        output_rows = self.store.connection.execute(
            "SELECT * FROM llm_outputs WHERE llm_run_id = ? ORDER BY created_at ASC",
            (llm_run_id,),
        ).fetchall()
        flag_rows = self.store.connection.execute(
            "SELECT * FROM llm_safety_flags WHERE llm_run_id = ? ORDER BY created_at ASC",
            (llm_run_id,),
        ).fetchall()
        result["outputs"] = [self._llm_output_dict(output) for output in output_rows]
        result["safety_flags"] = [dict(flag) for flag in flag_rows]
        return result

    def expand_query(
        self,
        *,
        namespace: str,
        query: str,
        provider: str = "mock_llm",
        model: str | None = None,
        privacy_level: str = "personal",
    ) -> dict[str, Any]:
        self._require_text(namespace, "namespace")
        self._require_text(query, "query")
        if privacy_level not in {"public", "personal", "private", "sensitive", "secret"}:
            raise ValidationError("Unknown LLM query privacy level.")
        engine = llm_provider_for_name(provider, model=model)
        warnings = []
        if privacy_level == "secret":
            warnings.append("Query input is secret and blocked for LLM task.")
        if privacy_level in {"private", "sensitive"} and getattr(engine, "external_network_access", False):
            warnings.append(f"Query input is {privacy_level} and blocked for external LLM task.")
        if warnings:
            invocation = LLMInvocation(
                task_type="expand_query",
                provider=engine.name,
                provider_type=getattr(engine, "provider_type", "unknown"),
                model=engine.model,
                prompt_template_id="m12.expand_query",
                prompt_version="1",
                temperature=0.0,
                schema_version="query_expansion.v1",
                input_hash=llm_input_hash({"query": query, "privacy_level": privacy_level}),
                status="unsafe",
                warnings=warnings,
                metadata={"privacy_level": privacy_level},
            )
            with self.store.transaction():
                self._store_llm_invocation(namespace=namespace, invocation=invocation)
            raise ValidationError("; ".join(warnings))
        messages = [
            {"role": "system", "content": "Expand the query for retrieval only. Do not introduce facts."},
            {"role": "user", "content": query},
        ]
        output = engine.complete_json(
            messages=messages,
            schema={"type": "object", "required": ["original_query", "expanded_terms"]},
            temperature=0.0,
            max_tokens=512,
            metadata={"task_type": "expand_query", "namespace": namespace, "query": query, "privacy_level": privacy_level},
        )
        invocation = LLMInvocation(
            task_type="expand_query",
            provider=engine.name,
            provider_type=getattr(engine, "provider_type", "unknown"),
            model=engine.model,
            prompt_template_id="m12.expand_query",
            prompt_version="1",
            temperature=0.0,
            schema_version="query_expansion.v1",
            input_hash=llm_input_hash({"query": query, "privacy_level": privacy_level}),
            output_hash=llm_output_hash(output),
            status="completed",
            output=output,
            metadata={"privacy_level": privacy_level},
        )
        with self.store.transaction():
            run_id = self._store_llm_invocation(namespace=namespace, invocation=invocation)
            self._store_llm_output(llm_run_id=run_id, output_type="query_expansion", target_id=None, status="pending_review", metadata=output)
            self._write_audit(namespace=namespace, target_type="llm_run", target_id=run_id, action="llm.expand_query", details={"query_hash": llm_input_hash(query)})
        return {**output, "llm_run_id": run_id}

    def suggest_entities(
        self,
        *,
        namespace: str,
        evidence_ids: list[str],
        provider: str = "mock_llm",
        model: str | None = None,
    ) -> dict[str, Any]:
        evidence = self._llm_allowed_evidence(namespace=namespace, evidence_ids=evidence_ids, provider=provider, model=model)
        output = self._llm_source_task(
            namespace=namespace,
            task_type="suggest_entities",
            prompt_template_id="m12.suggest_entities",
            provider=provider,
            model=model,
            evidence=evidence,
            metadata={},
        )
        output.setdefault("entities", [])
        output["review_state"] = output.get("review_state", "pending_review")
        return output

    def suggest_categories(
        self,
        *,
        namespace: str,
        evidence_ids: list[str],
        provider: str = "mock_llm",
        model: str | None = None,
    ) -> dict[str, Any]:
        evidence = self._llm_allowed_evidence(namespace=namespace, evidence_ids=evidence_ids, provider=provider, model=model)
        output = self._llm_source_task(
            namespace=namespace,
            task_type="suggest_categories",
            prompt_template_id="m12.suggest_categories",
            provider=provider,
            model=model,
            evidence=evidence,
            metadata={},
        )
        output.setdefault("categories", [])
        output["review_state"] = output.get("review_state", "pending_review")
        return output

    def suggest_scope_with_llm(
        self,
        *,
        namespace: str,
        candidate_id: str,
        provider: str = "mock_llm",
        model: str | None = None,
    ) -> dict[str, Any]:
        candidate = self.read_candidate(candidate_id)
        if candidate.namespace != namespace:
            raise ValidationError("LLM scope suggestion candidate belongs to a different namespace.")
        evidence = self._llm_allowed_evidence(namespace=namespace, evidence_ids=candidate.evidence_ids, provider=provider, model=model)
        output = self._llm_source_task(
            namespace=namespace,
            task_type="suggest_scope",
            prompt_template_id="m12.suggest_scope",
            provider=provider,
            model=model,
            evidence=evidence,
            metadata={"candidate": asdict(candidate)},
        )
        output.setdefault("candidate_id", candidate_id)
        output.setdefault("suggested_scope", candidate.suggested_scope or {"type": "review_required"})
        output["review_state"] = output.get("review_state", "pending_review")
        return output

    def suggest_duplicate_merge_with_llm(
        self,
        *,
        namespace: str,
        candidate_id: str,
        provider: str = "mock_llm",
        model: str | None = None,
    ) -> dict[str, Any]:
        candidate = self.read_candidate(candidate_id)
        if candidate.namespace != namespace:
            raise ValidationError("LLM duplicate merge suggestion candidate belongs to a different namespace.")
        evidence = self._llm_allowed_evidence(namespace=namespace, evidence_ids=candidate.evidence_ids, provider=provider, model=model)
        merge_candidates = self._llm_merge_candidates(candidate)
        output = self._llm_source_task(
            namespace=namespace,
            task_type="suggest_duplicate_merge",
            prompt_template_id="m12.suggest_duplicate_merge",
            provider=provider,
            model=model,
            evidence=evidence,
            metadata={"candidate": asdict(candidate), "merge_candidates": merge_candidates},
        )
        output.setdefault("candidate_id", candidate_id)
        output.setdefault("merge_suggestion", "review_possible_duplicate" if merge_candidates else "no_merge_target_found")
        output["review_state"] = output.get("review_state", "pending_review")
        return output

    def summarize_evidence(
        self,
        *,
        namespace: str,
        evidence_ids: list[str],
        provider: str = "mock_llm",
        model: str | None = None,
    ) -> dict[str, Any]:
        evidence = self._llm_allowed_evidence(namespace=namespace, evidence_ids=evidence_ids, provider=provider, model=model)
        return self._llm_source_task(
            namespace=namespace,
            task_type="summarize_evidence",
            prompt_template_id="m12.summarize_evidence",
            provider=provider,
            model=model,
            evidence=evidence,
            metadata={},
        )

    def draft_reflection_with_llm(
        self,
        *,
        namespace: str,
        source_claim_ids: list[str] | None = None,
        source_evidence_ids: list[str] | None = None,
        title: str = "LLM Reflection Draft",
        provider: str = "mock_llm",
        model: str | None = None,
    ) -> Reflection:
        source_claim_ids = list(source_claim_ids or [])
        source_evidence_ids = list(source_evidence_ids or [])
        evidence_ids = list(source_evidence_ids)
        for claim_id in source_claim_ids:
            claim = self.read_claim(claim_id)
            if claim.namespace != namespace:
                raise ValidationError("LLM reflection sources must share namespace.")
            evidence_ids.extend(claim.evidence_ids)
        evidence = self._llm_allowed_evidence(namespace=namespace, evidence_ids=sorted(set(evidence_ids)), provider=provider, model=model)
        output = self._llm_source_task(
            namespace=namespace,
            task_type="draft_reflection",
            prompt_template_id="m12.draft_reflection",
            provider=provider,
            model=model,
            evidence=evidence,
            metadata={"source_claim_ids": source_claim_ids, "title": title},
        )
        reflection = self.build_reflection(
            namespace,
            source_claim_ids=source_claim_ids,
            source_evidence_ids=source_evidence_ids,
            title=output.get("title") or title,
            text=output.get("reflection_text") or output.get("summary") or "LLM reflection draft requires review.",
            reason="LLM draft requires review.",
            builder="llm",
            require_review=True,
        )
        with self.store.transaction():
            self._store_llm_output(
                llm_run_id=output["llm_run_id"],
                output_type="reflection_draft",
                target_id=reflection.id,
                status=reflection.status,
                metadata={"reflection_id": reflection.id},
            )
        return reflection

    def explain_conflict_with_llm(
        self,
        conflict_id: str,
        *,
        provider: str = "mock_llm",
        model: str | None = None,
    ) -> dict[str, Any]:
        conflict = self.read_conflict(conflict_id)
        source_evidence_ids = sorted(
            {
                evidence_id
                for claim_id in conflict.claim_ids
                for evidence_id in self.read_claim(claim_id).evidence_ids
            }
        )
        self._llm_allowed_evidence(
            namespace=conflict.namespace,
            evidence_ids=source_evidence_ids,
            provider=provider,
            model=model,
        )
        engine = llm_provider_for_name(provider, model=model)
        claim_payload = [asdict(self.read_claim(claim_id)) for claim_id in conflict.claim_ids]
        metadata = {"task_type": "explain_conflict", "conflict_id": conflict_id, "claims": claim_payload}
        output = engine.complete_json(
            messages=[
                {"role": "system", "content": "Explain this conflict without resolving it."},
                {"role": "user", "content": json.dumps(metadata, sort_keys=True)},
            ],
            schema={"type": "object", "required": ["explanation", "resolves_conflict"]},
            temperature=0.0,
            max_tokens=512,
            metadata=metadata,
        )
        output["resolves_conflict"] = False
        invocation = LLMInvocation(
            task_type="explain_conflict",
            provider=engine.name,
            provider_type=getattr(engine, "provider_type", "unknown"),
            model=engine.model,
            prompt_template_id="m12.explain_conflict",
            prompt_version="1",
            temperature=0.0,
            schema_version="conflict_explanation.v1",
            input_hash=llm_input_hash(metadata),
            output_hash=llm_output_hash(output),
            status="completed",
            output=output,
        )
        with self.store.transaction():
            run_id = self._store_llm_invocation(namespace=conflict.namespace, invocation=invocation)
            self._store_llm_output(llm_run_id=run_id, output_type="conflict_explanation", target_id=conflict_id, status="pending_review", metadata=output)
            self._write_audit(namespace=conflict.namespace, target_type="conflict", target_id=conflict_id, action="llm.explain_conflict", details={"llm_run_id": run_id})
        return {**output, "llm_run_id": run_id}

    def read_candidate(self, candidate_id: str) -> CandidateClaim:
        row = self.store.connection.execute(
            "SELECT * FROM candidate_claims WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Candidate claim not found: {candidate_id}")
        return CandidateClaim.from_row(
            row,
            evidence_ids=self._evidence_ids_for_candidate(candidate_id),
            evidence_spans=self._evidence_spans_for_candidate(candidate_id),
            suggested_categories=self._labels_for_target(candidate_id, "candidate_claim"),
            suggested_entities=self._entity_ids_for_candidate(candidate_id),
        )

    def list_candidates(
        self,
        namespace: str,
        *,
        status: str | None = None,
        memory_type: str | None = None,
        project_id: str | None = None,
        extraction_run_id: str | None = None,
        limit: int = 50,
    ) -> list[CandidateClaim]:
        params: list[object] = [namespace]
        clauses = ["cc.namespace = ?"]
        if status:
            clauses.append("cc.candidate_status = ?")
            params.append(status)
        if memory_type:
            clauses.append("cc.memory_type = ?")
            params.append(memory_type)
        if extraction_run_id:
            clauses.append("cc.extraction_run_id = ?")
            params.append(extraction_run_id)
        if project_id:
            clauses.append(
                """
                EXISTS (
                    SELECT 1
                    FROM extraction_runs er
                    JOIN ingestion_batches ib ON ib.id = er.batch_id
                    WHERE er.id = cc.extraction_run_id
                      AND ib.project_id = ?
                )
                """
            )
            params.append(project_id)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT cc.*
            FROM candidate_claims cc
            WHERE {' AND '.join(clauses)}
            ORDER BY cc.created_at DESC, cc.id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [self.read_candidate(row["id"]) for row in rows]

    def review_candidate(
        self,
        candidate_id: str,
        *,
        decision: str,
        reason: str,
        reviewer: str = "user",
        edits: dict | None = None,
    ) -> ExtractionDecision:
        if decision not in REVIEW_DECISIONS:
            raise ValidationError(f"Unknown candidate review decision: {decision}")
        self._require_text(reason, "reason")
        candidate = self.read_candidate(candidate_id)
        new_status = {
            "validate": "validated",
            "reject": "rejected",
            "mark_duplicate": "duplicate",
            "needs_scope": "needs_scope",
            "needs_conflict_resolution": "needs_conflict_resolution",
            "defer": candidate.candidate_status,
            "edit": candidate.candidate_status,
            "promote": "promoted",
        }[decision]
        decision_id = new_id("xdec")
        now = utc_now_iso()
        edits = edits or None
        with self.store.transaction():
            if edits:
                self._apply_candidate_edits(candidate_id, edits)
                if decision == "edit":
                    new_status = edits.get("candidate_status", "pending_review")
            self.store.connection.execute(
                """
                UPDATE candidate_claims
                SET candidate_status = ?
                WHERE id = ?
                """,
                (new_status, candidate_id),
            )
            self.store.connection.execute(
                """
                INSERT INTO extraction_decisions (
                    id, namespace, candidate_id, decision, reason, reviewer,
                    edits_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    candidate.namespace,
                    candidate_id,
                    decision,
                    reason,
                    reviewer,
                    json.dumps(edits, sort_keys=True) if edits is not None else None,
                    now,
                ),
            )
            self._write_audit(
                namespace=candidate.namespace,
                target_type="candidate_claim",
                target_id=candidate_id,
                action=f"candidate.{decision}",
                details={"reason": reason, "reviewer": reviewer, "edits": edits},
            )
        row = self.store.connection.execute(
            "SELECT * FROM extraction_decisions WHERE id = ?",
            (decision_id,),
        ).fetchone()
        return ExtractionDecision.from_row(row)

    def promote_candidate(
        self,
        candidate_id: str,
        *,
        reason: str,
        target_status: str = "active",
        reviewer: str = "user",
        edits: dict | None = None,
        force: bool = False,
    ) -> Claim:
        if target_status not in PROMOTION_TARGETS:
            raise ValidationError(f"Candidate promotion target must be one of {sorted(PROMOTION_TARGETS)}.")
        self._require_text(reason, "reason")
        candidate = self.read_candidate(candidate_id)
        if edits:
            self.review_candidate(
                candidate_id,
                decision="edit",
                reason="Edits applied during candidate promotion.",
                reviewer=reviewer,
                edits=edits,
            )
            candidate = self.read_candidate(candidate_id)
        failures = self._candidate_promotion_failures(candidate, target_status)
        if failures and not force:
            raise ValidationError("Cannot promote candidate: " + "; ".join(failures))
        confidence = min(
            candidate.suggested_confidence,
            self._evidence_trust_adjusted_confidence(candidate.evidence_ids),
        )
        project_id = self._project_id_for_candidate(candidate)
        claim = self.write_claim(
            namespace=candidate.namespace,
            subject=candidate.subject,
            predicate=candidate.predicate,
            object=candidate.object,
            memory_type=candidate.memory_type,
            evidence_ids=candidate.evidence_ids,
            confidence=confidence,
            status="active",
            half_life_days=candidate.suggested_half_life_days,
            importance=candidate.suggested_importance,
            project_id=project_id,
        )
        if target_status == "core" and claim.status != "core":
            self.promote_claim(claim.id, "core", reason=reason, force=force)
            claim = self.read_claim(claim.id)
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT OR IGNORE INTO candidate_claim_links (
                    candidate_id, claim_id, relation, created_at
                )
                VALUES (?, ?, 'promoted_to', ?)
                """,
                (candidate_id, claim.id, utc_now_iso()),
            )
            self.store.connection.execute(
                """
                UPDATE candidate_claims
                SET candidate_status = 'promoted'
                WHERE id = ?
                """,
                (candidate_id,),
            )
            self._write_extraction_decision_in_transaction(
                namespace=candidate.namespace,
                candidate_id=candidate_id,
                decision="promote",
                reason=reason,
                reviewer=reviewer,
                edits=edits,
            )
            for label in candidate.suggested_categories:
                self._label_memory_in_transaction(
                    namespace=candidate.namespace,
                    target_id=claim.id,
                    target_type="claim",
                    label=label,
                    reason="Promoted from candidate label.",
                    confidence=0.85,
                )
            for entity_id in candidate.suggested_entities:
                self.store.connection.execute(
                    """
                    INSERT OR IGNORE INTO claim_entity_links (
                        claim_id, entity_id, role, created_at
                    )
                    VALUES (?, ?, 'related', ?)
                    """,
                    (claim.id, entity_id, utc_now_iso()),
                )
            self._write_audit(
                namespace=candidate.namespace,
                target_type="candidate_claim",
                target_id=candidate_id,
                action="candidate.promote",
                details={"claim_id": claim.id, "reason": reason},
            )
            self._write_audit(
                namespace=candidate.namespace,
                target_type="claim",
                target_id=claim.id,
                action="candidate.promoted_to_claim",
                details={"candidate_id": candidate_id, "reason": reason},
            )
        scope = candidate.suggested_scope or {}
        if scope and scope.get("type") in SCOPE_TYPES and scope.get("applies_when"):
            self.scope_claim(
                claim.id,
                scope_type=scope["type"],
                applies_when=scope.get("applies_when"),
                reason="Candidate suggested scope during promotion.",
            )
            claim = self.read_claim(claim.id)
        return claim

    def reject_candidate(
        self,
        candidate_id: str,
        *,
        reason: str,
        reviewer: str = "user",
    ) -> ExtractionDecision:
        return self.review_candidate(
            candidate_id,
            decision="reject",
            reason=reason,
            reviewer=reviewer,
        )

    def run_inference(
        self,
        namespace: str,
        *,
        engines: list[str] | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        target_claim_ids: list[str] | None = None,
        target_evidence_ids: list[str] | None = None,
        target_entity_ids: list[str] | None = None,
        rule_ids: list[str] | None = None,
        dry_run: bool = True,
        max_inferences: int | None = None,
        policy: dict | None = None,
    ) -> InferenceRun:
        self._require_text(namespace, "namespace")
        selected_engines = self._normalize_inference_engines(engines)
        target_claim_ids = list(target_claim_ids or [])
        target_evidence_ids = list(target_evidence_ids or [])
        rule_ids = list(rule_ids or [])
        run_id = new_id("irun")
        now = utc_now_iso()
        warnings: list[str] = []
        drafts = self._generate_inference_drafts(
            namespace=namespace,
            engines=selected_engines,
            project_id=project_id,
            session_id=session_id,
            target_claim_ids=target_claim_ids,
            target_evidence_ids=target_evidence_ids,
            target_entity_ids=target_entity_ids or [],
            rule_ids=rule_ids,
            policy=policy or {},
        )
        if max_inferences is not None:
            drafts = drafts[:max_inferences]
        persisted_count = 0 if dry_run else len(drafts)
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO inference_runs (
                    id, namespace, engines_json, project_id, session_id,
                    target_claim_ids_json, target_evidence_ids_json, rule_ids_json,
                    dry_run, inference_count, persisted_count, created_at,
                    warnings_json, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    namespace,
                    json.dumps(selected_engines, sort_keys=True),
                    project_id,
                    session_id,
                    json.dumps(target_claim_ids, sort_keys=True),
                    json.dumps(target_evidence_ids, sort_keys=True),
                    json.dumps(rule_ids, sort_keys=True),
                    int(dry_run),
                    len(drafts),
                    persisted_count,
                    now,
                    json.dumps(warnings, sort_keys=True),
                    json.dumps({"policy": policy or {}}, sort_keys=True),
                ),
            )
            for engine in selected_engines:
                matched = sum(1 for draft in drafts if draft["engine"] == engine)
                self._write_rule_execution_log(
                    namespace=namespace,
                    rule_id=self._rule_id_for_engine(engine),
                    inference_run_id=run_id,
                    matched_count=matched,
                    inference_count=matched,
                    dry_run=dry_run,
                    warnings=[],
                )
            for rule_id in rule_ids:
                matched = sum(
                    1
                    for draft in drafts
                    if draft.get("rule_id") == rule_id
                    or (self._rule_exists(rule_id) and draft["engine"] == self.get_rule(rule_id).rule_type)
                )
                self._write_rule_execution_log(
                    namespace=namespace,
                    rule_id=rule_id,
                    inference_run_id=run_id,
                    matched_count=matched,
                    inference_count=matched,
                    dry_run=dry_run,
                    warnings=[],
                )
            if not dry_run:
                for draft in drafts:
                    self._store_inference_draft(namespace=namespace, run_id=run_id, draft=draft)
                if "semantic" in selected_engines:
                    self._persist_semantic_inference(
                        namespace=namespace,
                        project_id=project_id,
                        target_claim_ids=target_claim_ids,
                    )
            self._write_audit(
                namespace=namespace,
                target_type="inference_run",
                target_id=run_id,
                action="inference.run",
                details={
                    "engines": selected_engines,
                    "dry_run": dry_run,
                    "inference_count": len(drafts),
                    "persisted_count": persisted_count,
                },
            )
        return self.read_inference_run(run_id)

    def read_inference_run(self, run_id: str) -> InferenceRun:
        row = self.store.connection.execute(
            "SELECT * FROM inference_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Inference run not found: {run_id}")
        return InferenceRun.from_row(row)

    def read_inference(self, inference_id: str) -> InferenceCandidate:
        row = self.store.connection.execute(
            "SELECT * FROM inference_candidates WHERE id = ?",
            (inference_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Inference candidate not found: {inference_id}")
        return InferenceCandidate.from_row(
            row,
            source_claim_ids=self._source_ids_for_target(inference_id, "inference", "claim"),
            source_evidence_ids=self._source_ids_for_target(inference_id, "inference", "evidence"),
            source_candidate_ids=self._source_ids_for_target(inference_id, "inference", "candidate_claim"),
        )

    def list_inferences(
        self,
        namespace: str,
        *,
        status: str | None = None,
        inference_type: str | None = None,
        engine: str | None = None,
        project_id: str | None = None,
        source_claim_id: str | None = None,
        limit: int = 50,
    ) -> list[InferenceCandidate]:
        params: list[object] = [namespace]
        clauses = ["ic.namespace = ?"]
        if status:
            clauses.append("ic.status = ?")
            params.append(status)
        if inference_type:
            clauses.append("ic.inference_type = ?")
            params.append(inference_type)
        if engine:
            clauses.append("ic.engine = ?")
            params.append(engine)
        if project_id:
            clauses.append(
                """
                EXISTS (
                    SELECT 1 FROM inference_runs ir
                    WHERE ir.id = ic.inference_run_id
                      AND ir.project_id = ?
                )
                """
            )
            params.append(project_id)
        if source_claim_id:
            clauses.append(
                """
                EXISTS (
                    SELECT 1 FROM derivation_edges de
                    WHERE de.target_id = ic.id
                      AND de.target_type = 'inference'
                      AND de.source_type = 'claim'
                      AND de.source_id = ?
                )
                """
            )
            params.append(source_claim_id)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT ic.*
            FROM inference_candidates ic
            WHERE {' AND '.join(clauses)}
            ORDER BY ic.created_at DESC, ic.id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [self.read_inference(row["id"]) for row in rows]

    def review_inference(
        self,
        inference_id: str,
        *,
        decision: str,
        reason: str,
        reviewer: str = "user",
        edits: dict | None = None,
    ) -> InferenceDecision:
        if decision not in INFERENCE_REVIEW_DECISIONS:
            raise ValidationError(f"Unknown inference review decision: {decision}")
        self._require_text(reason, "reason")
        inference = self.read_inference(inference_id)
        new_status = {
            "validate": "validated",
            "reject": "rejected",
            "edit": inference.status,
            "defer": inference.status,
            "mark_speculative": "pending_review",
            "needs_conflict_resolution": "needs_conflict_resolution",
            "needs_source_review": "needs_source_review",
        }[decision]
        decision_id = new_id("idec")
        with self.store.transaction():
            if edits:
                self._apply_inference_edits(inference_id, edits)
                new_status = edits.get("status", new_status)
            if decision == "mark_speculative":
                self.store.connection.execute(
                    "UPDATE inference_candidates SET inference_strength = 'speculative' WHERE id = ?",
                    (inference_id,),
                )
            self.store.connection.execute(
                "UPDATE inference_candidates SET status = ? WHERE id = ?",
                (new_status, inference_id),
            )
            self.store.connection.execute(
                """
                INSERT INTO inference_decisions (
                    id, namespace, inference_id, decision, reason, reviewer,
                    edits_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    inference.namespace,
                    inference_id,
                    decision,
                    reason,
                    reviewer,
                    json.dumps(edits, sort_keys=True) if edits else None,
                    utc_now_iso(),
                ),
            )
            self._write_audit(
                namespace=inference.namespace,
                target_type="inference",
                target_id=inference_id,
                action=f"inference.{decision}",
                details={"reason": reason, "reviewer": reviewer, "edits": edits},
            )
        row = self.store.connection.execute(
            "SELECT * FROM inference_decisions WHERE id = ?",
            (decision_id,),
        ).fetchone()
        return InferenceDecision.from_row(row)

    def promote_inference(
        self,
        inference_id: str,
        *,
        target_type: str = "claim",
        target_status: str = "active",
        reason: str,
        reviewer: str = "user",
        force: bool = False,
    ):
        inference = self.read_inference(inference_id)
        failures = self._inference_promotion_failures(inference, target_type, target_status)
        if failures and not force:
            raise ValidationError("Cannot promote inference: " + "; ".join(failures))
        if target_type == "reflection":
            reflection = self.build_reflection(
                inference.namespace,
                source_claim_ids=inference.source_claim_ids,
                source_evidence_ids=inference.source_evidence_ids,
                title=inference.text[:80],
                text=inference.text,
                abstraction_level=max(inference.abstraction_level, 2),
                project_id=self._project_id_for_inference(inference),
                reason=reason,
                builder=f"inference:{inference.engine}",
                require_review=False,
            )
            with self.store.transaction():
                self.store.connection.execute(
                    "UPDATE inference_candidates SET status = 'promoted' WHERE id = ?",
                    (inference_id,),
                )
                self._write_inference_decision_in_transaction(
                    namespace=inference.namespace,
                    inference_id=inference_id,
                    decision="promote",
                    reason=reason,
                    reviewer=reviewer,
                    edits={"target_type": target_type},
                )
                self._create_derivation_edge(
                    namespace=inference.namespace,
                    source_id=inference_id,
                    source_type="inference",
                    target_id=reflection.id,
                    target_type="reflection",
                    relationship="derived_from",
                    rule_id=inference.rule_id,
                    confidence=inference.derivation_confidence,
                )
            return reflection
        if target_type != "claim":
            raise ValidationError("target_type must be claim or reflection.")
        subject = inference.subject or "inference"
        predicate = inference.predicate or "suggests"
        object_text = inference.object or inference.text
        claim = self.write_claim(
            namespace=inference.namespace,
            subject=subject,
            predicate=predicate,
            object=object_text,
            memory_type="inference",
            evidence_ids=inference.source_evidence_ids,
            confidence=min(inference.suggested_truth_confidence, inference.derivation_confidence),
            status="active",
            importance=inference.suggested_retrieval_salience,
            project_id=self._project_id_for_inference(inference),
        )
        if target_status == "core":
            self.promote_claim(claim.id, "core", reason=reason, force=force)
            claim = self.read_claim(claim.id)
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT OR IGNORE INTO derived_claim_links (
                    inference_id, claim_id, relation, created_at
                )
                VALUES (?, ?, 'promoted_to_claim', ?)
                """,
                (inference_id, claim.id, utc_now_iso()),
            )
            self.store.connection.execute(
                "UPDATE inference_candidates SET status = 'promoted' WHERE id = ?",
                (inference_id,),
            )
            self._write_inference_decision_in_transaction(
                namespace=inference.namespace,
                inference_id=inference_id,
                decision="promote",
                reason=reason,
                reviewer=reviewer,
                edits={"target_type": target_type, "claim_id": claim.id},
            )
            self._create_derivation_edge(
                namespace=inference.namespace,
                source_id=inference_id,
                source_type="inference",
                target_id=claim.id,
                target_type="claim",
                relationship="derived_from",
                rule_id=inference.rule_id,
                confidence=inference.derivation_confidence,
            )
            self._write_audit(
                namespace=inference.namespace,
                target_type="claim",
                target_id=claim.id,
                action="inference.promoted_to_claim",
                details={"inference_id": inference_id, "reason": reason},
            )
        return claim

    def reject_inference(
        self,
        inference_id: str,
        *,
        reason: str,
        reviewer: str = "user",
    ) -> InferenceDecision:
        return self.review_inference(
            inference_id,
            decision="reject",
            reason=reason,
            reviewer=reviewer,
        )

    def define_rule(
        self,
        namespace: str | None,
        *,
        name: str,
        rule_type: str,
        description: str,
        condition: dict,
        conclusion: dict,
        confidence_policy: dict | None = None,
        enabled: bool = True,
    ) -> InferenceRule:
        self._require_text(name, "name")
        self._require_text(description, "description")
        if rule_type not in RULE_TYPES:
            raise ValidationError(f"Unknown rule type: {rule_type}")
        now = utc_now_iso()
        rule_id = self._stable_id("rule", namespace or "global", name)
        existing = self.store.connection.execute(
            """
            SELECT id, created_at
            FROM inference_rules
            WHERE namespace IS ?
              AND name = ?
            """,
            (namespace, name),
        ).fetchone()
        if existing:
            rule_id = existing["id"]
            created_at = existing["created_at"]
        else:
            created_at = now
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO inference_rules (
                    id, namespace, name, rule_type, description, condition_json,
                    conclusion_json, confidence_policy_json, enabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    rule_type = excluded.rule_type,
                    description = excluded.description,
                    condition_json = excluded.condition_json,
                    conclusion_json = excluded.conclusion_json,
                    confidence_policy_json = excluded.confidence_policy_json,
                    enabled = excluded.enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    rule_id,
                    namespace,
                    name,
                    rule_type,
                    description,
                    json.dumps(condition, sort_keys=True),
                    json.dumps(conclusion, sort_keys=True),
                    json.dumps(confidence_policy or {}, sort_keys=True),
                    int(enabled),
                    created_at,
                    now,
                ),
            )
            self._write_audit(
                namespace=namespace or "global",
                target_type="inference_rule",
                target_id=rule_id,
                action="rule.define",
                details={"name": name, "rule_type": rule_type, "enabled": enabled},
            )
        return self.get_rule(rule_id)

    def get_rule(self, rule_id: str) -> InferenceRule:
        row = self.store.connection.execute(
            "SELECT * FROM inference_rules WHERE id = ?",
            (rule_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Inference rule not found: {rule_id}")
        return InferenceRule.from_row(row)

    def list_rules(
        self,
        *,
        namespace: str | None = None,
        enabled: bool | None = None,
    ) -> list[InferenceRule]:
        params: list[object] = []
        clauses: list[str] = []
        if namespace is not None:
            clauses.append("(namespace = ? OR namespace IS NULL)")
            params.append(namespace)
        if enabled is not None:
            clauses.append("enabled = ?")
            params.append(int(enabled))
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM inference_rules
            {where}
            ORDER BY namespace IS NOT NULL, rule_type, name
            """,
            params,
        ).fetchall()
        return [InferenceRule.from_row(row) for row in rows]

    def set_rule_enabled(self, rule_id: str, *, enabled: bool) -> InferenceRule:
        rule = self.get_rule(rule_id)
        with self.store.transaction():
            self.store.connection.execute(
                "UPDATE inference_rules SET enabled = ?, updated_at = ? WHERE id = ?",
                (int(enabled), utc_now_iso(), rule_id),
            )
            self._write_audit(
                namespace=rule.namespace or "global",
                target_type="inference_rule",
                target_id=rule_id,
                action="rule.enable" if enabled else "rule.disable",
                details={},
            )
        return self.get_rule(rule_id)

    def run_rule(
        self,
        rule_id: str,
        *,
        namespace: str,
        target_claim_ids: list[str] | None = None,
        dry_run: bool = True,
    ) -> RuleExecutionResult:
        rule = self.get_rule(rule_id)
        engine = {
            "temporal": "logical",
            "scope": "logical",
            "conflict": "logical",
            "dependency": "logical",
            "classification": "semantic",
        }.get(rule.rule_type, rule.rule_type)
        run = self.run_inference(
            namespace,
            engines=[engine],
            target_claim_ids=target_claim_ids,
            rule_ids=[rule_id],
            dry_run=dry_run,
        )
        row = self.store.connection.execute(
            """
            SELECT *
            FROM rule_execution_log
            WHERE inference_run_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (run.id,),
        ).fetchone()
        return RuleExecutionResult.from_row(row)

    def build_reflection(
        self,
        namespace: str,
        *,
        source_claim_ids: list[str] | None = None,
        source_evidence_ids: list[str] | None = None,
        source_reflection_ids: list[str] | None = None,
        title: str,
        text: str | None = None,
        abstraction_level: int = 2,
        project_id: str | None = None,
        reason: str,
        builder: str = "manual",
        require_review: bool = True,
    ) -> Reflection:
        source_claim_ids = list(source_claim_ids or [])
        source_evidence_ids = list(source_evidence_ids or [])
        source_reflection_ids = list(source_reflection_ids or [])
        if not (source_claim_ids or source_evidence_ids or source_reflection_ids):
            raise ValidationError("Reflection requires at least one source.")
        self._require_text(title, "title")
        self._require_text(reason, "reason")
        for claim_id in source_claim_ids:
            claim = self.read_claim(claim_id)
            if claim.namespace != namespace:
                raise ValidationError("Reflection source claims must share namespace.")
            source_evidence_ids.extend(claim.evidence_ids)
        source_evidence_ids = sorted(set(source_evidence_ids))
        for evidence_id in source_evidence_ids:
            event = self.read_event(evidence_id)
            if event.namespace != namespace:
                raise ValidationError("Reflection source evidence must share namespace.")
        reflection_text = text or self._reflection_text_from_sources(source_claim_ids)
        confidence = self._derived_confidence_from_claims(source_claim_ids)
        salience = min(max(0.5, confidence), 1.0)
        status = "candidate" if require_review else "active"
        reflection_id = new_id("ref")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO reflections (
                    id, namespace, title, text, abstraction_level, project_id,
                    status, confidence_effective, retrieval_salience, builder,
                    created_at, updated_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reflection_id,
                    namespace,
                    title,
                    reflection_text,
                    abstraction_level,
                    project_id,
                    status,
                    confidence,
                    salience,
                    builder,
                    now,
                    now,
                    json.dumps({"reason": reason}, sort_keys=True),
                ),
            )
            for claim_id in source_claim_ids:
                self._link_reflection_source(reflection_id, claim_id, "claim")
                self._create_derivation_edge(
                    namespace=namespace,
                    source_id=claim_id,
                    source_type="claim",
                    target_id=reflection_id,
                    target_type="reflection",
                    relationship="summarizes",
                    confidence=confidence,
                )
            for evidence_id in source_evidence_ids:
                self._link_reflection_source(reflection_id, evidence_id, "evidence")
                self._create_derivation_edge(
                    namespace=namespace,
                    source_id=evidence_id,
                    source_type="evidence",
                    target_id=reflection_id,
                    target_type="reflection",
                    relationship="supported_by",
                    confidence=1.0,
                )
            for source_reflection_id in source_reflection_ids:
                self._link_reflection_source(reflection_id, source_reflection_id, "reflection")
                self._create_derivation_edge(
                    namespace=namespace,
                    source_id=source_reflection_id,
                    source_type="reflection",
                    target_id=reflection_id,
                    target_type="reflection",
                    relationship="abstracts",
                    confidence=confidence,
                )
            self._write_audit(
                namespace=namespace,
                target_type="reflection",
                target_id=reflection_id,
                action="reflection.build",
                details={"reason": reason, "status": status, "builder": builder},
            )
        return self.get_reflection(reflection_id)

    def get_reflection(self, reflection_id: str) -> Reflection:
        row = self.store.connection.execute(
            "SELECT * FROM reflections WHERE id = ?",
            (reflection_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Reflection not found: {reflection_id}")
        return Reflection.from_row(
            row,
            source_claim_ids=self._source_ids_for_reflection(reflection_id, "claim"),
            source_evidence_ids=self._source_ids_for_reflection(reflection_id, "evidence"),
            source_reflection_ids=self._source_ids_for_reflection(reflection_id, "reflection"),
        )

    def list_reflections(
        self,
        *,
        namespace: str | None = None,
        status: str | None = None,
        project_id: str | None = None,
        limit: int = 50,
    ) -> list[Reflection]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clauses = ["namespace = ?"]
        if status:
            clauses.append("status = ?")
            params.append(status)
        if project_id:
            clauses.append("(project_id = ? OR project_id IS NULL)")
            params.append(project_id)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT id
            FROM reflections
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC, id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [self.get_reflection(row["id"]) for row in rows]

    def expand_reflection(
        self,
        reflection_id: str,
        *,
        include_claims: bool = True,
        include_evidence: bool = True,
        include_derivation: bool = True,
    ) -> ReflectionExpansion:
        reflection = self.get_reflection(reflection_id)
        warnings: list[str] = []
        claims = []
        evidence = []
        if include_claims:
            for claim_id in reflection.source_claim_ids:
                try:
                    claims.append(self.read_claim(claim_id))
                except NotFoundError:
                    warnings.append(f"Missing source claim: {claim_id}")
        if include_evidence:
            for evidence_id in reflection.source_evidence_ids:
                try:
                    evidence.append(self.read_event(evidence_id))
                except NotFoundError:
                    warnings.append(f"Missing source evidence: {evidence_id}")
        edges = (
            self._derivation_edges_for_target(reflection_id, "reflection")
            if include_derivation
            else []
        )
        return ReflectionExpansion(
            reflection_id=reflection_id,
            reflection_text=reflection.text,
            source_claims=claims,
            source_evidence=evidence,
            derivation_edges=edges,
            warnings=warnings,
        )

    def create_abstraction(
        self,
        namespace: str,
        *,
        source_ids: list[str],
        source_type: str,
        abstraction_text: str,
        abstraction_level: int,
        information_loss_policy: str = "lossless_via_backlinks",
        reason: str,
    ) -> AbstractionRecord:
        if not source_ids:
            raise ValidationError("Abstraction requires at least one source.")
        self._require_text(abstraction_text, "abstraction_text")
        self._require_text(reason, "reason")
        if information_loss_policy not in {
            "lossless_via_backlinks",
            "lossy_summary",
            "index_only",
            "compressed_view",
        }:
            raise ValidationError("Unknown information loss policy.")
        abstraction_id = new_id("abs")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO abstraction_records (
                    id, namespace, abstraction_text, abstraction_level, source_type,
                    information_loss_policy, status, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    abstraction_id,
                    namespace,
                    abstraction_text,
                    abstraction_level,
                    source_type,
                    information_loss_policy,
                    now,
                    json.dumps({"reason": reason}, sort_keys=True),
                ),
            )
            for source_id in source_ids:
                self.store.connection.execute(
                    """
                    INSERT OR IGNORE INTO abstraction_sources (
                        abstraction_id, source_id, source_type, created_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (abstraction_id, source_id, source_type, now),
                )
                self._create_derivation_edge(
                    namespace=namespace,
                    source_id=source_id,
                    source_type=source_type,
                    target_id=abstraction_id,
                    target_type="abstraction",
                    relationship="abstracts",
                    confidence=1.0,
                )
            self._write_audit(
                namespace=namespace,
                target_type="abstraction",
                target_id=abstraction_id,
                action="abstraction.create",
                details={"reason": reason, "source_type": source_type},
            )
        return self.get_abstraction(abstraction_id)

    def get_abstraction(self, abstraction_id: str) -> AbstractionRecord:
        row = self.store.connection.execute(
            "SELECT * FROM abstraction_records WHERE id = ?",
            (abstraction_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Abstraction not found: {abstraction_id}")
        rows = self.store.connection.execute(
            """
            SELECT source_id
            FROM abstraction_sources
            WHERE abstraction_id = ?
            ORDER BY source_id
            """,
            (abstraction_id,),
        ).fetchall()
        return AbstractionRecord.from_row(row, [source["source_id"] for source in rows])

    def list_abstractions(
        self,
        *,
        namespace: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AbstractionRecord]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if status:
            clause += " AND status = ?"
            params.append(status)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT id
            FROM abstraction_records
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [self.get_abstraction(row["id"]) for row in rows]

    def trace_derivation(
        self,
        target_id: str,
        *,
        target_type: str,
        max_depth: int = 10,
    ) -> DerivationTrace:
        seen: set[tuple[str, str]] = set()
        nodes: list[dict] = []
        edges: list[DerivationEdge] = []
        root_evidence: set[str] = set()
        risks: list[str] = []
        frontier = [(target_id, target_type, 0)]
        while frontier:
            node_id, node_type, depth = frontier.pop(0)
            key = (node_id, node_type)
            if key in seen or depth > max_depth:
                continue
            seen.add(key)
            nodes.append({"id": node_id, "type": node_type, "depth": depth})
            if node_type == "claim":
                try:
                    root_evidence.update(self.read_claim(node_id).evidence_ids)
                except NotFoundError:
                    risks.append(f"Missing claim: {node_id}")
            elif node_type == "evidence":
                root_evidence.add(node_id)
            for edge in self._derivation_edges_for_target(node_id, node_type):
                edges.append(edge)
                frontier.append((edge.source_id, edge.source_type, depth + 1))
            for event in self._invalidation_events_for_target(node_id, node_type):
                risks.append(f"{node_type} {node_id} {event.action}: {event.reason}")
        return DerivationTrace(
            target_id=target_id,
            target_type=target_type,
            nodes=nodes,
            edges=edges,
            invalidation_risks=risks,
            root_evidence_ids=sorted(root_evidence),
        )

    def explain_inference(
        self,
        inference_id: str,
        *,
        include_sources: bool = True,
        include_rule: bool = True,
        include_confidence: bool = True,
        include_invalidation: bool = True,
    ) -> InferenceExplanation:
        inference = self.read_inference(inference_id)
        sources: list[dict] = []
        if include_sources:
            for claim_id in inference.source_claim_ids:
                sources.append({"type": "claim", "value": asdict(self.read_claim(claim_id))})
            for evidence_id in inference.source_evidence_ids:
                sources.append({"type": "evidence", "value": asdict(self.read_event(evidence_id))})
        rule = asdict(self.get_rule(inference.rule_id)) if include_rule and inference.rule_id else None
        confidence = None
        if include_confidence:
            confidence = {
                "derivation_confidence": inference.derivation_confidence,
                "suggested_truth_confidence": inference.suggested_truth_confidence,
                "suggested_retrieval_salience": inference.suggested_retrieval_salience,
                "inference_strength": inference.inference_strength,
            }
        invalidation = []
        if include_invalidation:
            invalidation = [
                f"{event.action}: {event.reason}"
                for event in self._invalidation_events_for_target(inference_id, "inference")
            ]
        failures = self._inference_promotion_failures(inference, "claim", "active")
        explanation = (
            f"{inference.engine} produced a {inference.inference_type} inference "
            f"with {inference.inference_strength} strength from "
            f"{len(inference.source_claim_ids)} claim source(s) and "
            f"{len(inference.source_evidence_ids)} evidence source(s)."
        )
        model = InferenceExplanation(
            inference_id=inference_id,
            inference=asdict(inference),
            sources=sources,
            rule=rule,
            confidence=confidence,
            invalidation=invalidation,
            can_promote=not failures,
            promotion_failures=failures,
            explanation=explanation,
        )
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO inference_explanations (
                    id, namespace, inference_id, explanation_text, generated_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("iexp"),
                    inference.namespace,
                    inference_id,
                    explanation,
                    utc_now_iso(),
                    json.dumps(
                        {
                            "can_promote": model.can_promote,
                            "promotion_failures": model.promotion_failures,
                            "include_sources": include_sources,
                            "include_rule": include_rule,
                            "include_confidence": include_confidence,
                            "include_invalidation": include_invalidation,
                        },
                        sort_keys=True,
                    ),
                ),
            )
        return model

    def invalidate_derived(
        self,
        *,
        namespace: str,
        source_id: str,
        source_type: str,
        reason: str,
        mode: str = "mark_stale",
    ) -> list[InvalidationEvent]:
        if mode not in INVALIDATION_MODES:
            raise ValidationError(f"Unknown invalidation mode: {mode}")
        events: list[InvalidationEvent] = []
        queue = [(source_id, source_type)]
        visited: set[tuple[str, str]] = set()
        with self.store.transaction():
            while queue:
                current_id, current_type = queue.pop(0)
                if (current_id, current_type) in visited:
                    continue
                visited.add((current_id, current_type))
                rows = self.store.connection.execute(
                    """
                    SELECT DISTINCT target_id, target_type
                    FROM derivation_edges
                    WHERE namespace = ?
                      AND source_id = ?
                      AND source_type = ?
                    """,
                    (namespace, current_id, current_type),
                ).fetchall()
                for row in rows:
                    action = self._apply_invalidation_action(
                        namespace=namespace,
                        affected_id=row["target_id"],
                        affected_type=row["target_type"],
                        reason=reason,
                        mode=mode,
                    )
                    event_id = new_id("inv")
                    created_at = utc_now_iso()
                    self.store.connection.execute(
                        """
                        INSERT INTO invalidation_events (
                            id, namespace, source_id, source_type, affected_id,
                            affected_type, action, reason, created_at, metadata_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            namespace,
                            source_id,
                            source_type,
                            row["target_id"],
                            row["target_type"],
                            action,
                            reason,
                            created_at,
                            json.dumps({"mode": mode}, sort_keys=True),
                        ),
                    )
                    self._write_audit(
                        namespace=namespace,
                        target_type=row["target_type"],
                        target_id=row["target_id"],
                        action="derived.invalidate",
                        details={"source_id": source_id, "source_type": source_type, "mode": mode, "reason": reason},
                    )
                    events.append(
                        InvalidationEvent(
                            id=event_id,
                            namespace=namespace,
                            source_id=source_id,
                            source_type=source_type,
                            affected_id=row["target_id"],
                            affected_type=row["target_type"],
                            action=action,
                            reason=reason,
                            created_at=created_at,
                            metadata={"mode": mode},
                        )
                    )
                    queue.append((row["target_id"], row["target_type"]))
        return events

    def list_invalidations(
        self,
        *,
        namespace: str | None = None,
        target_id: str | None = None,
        target_type: str | None = None,
        limit: int = 50,
    ) -> list[InvalidationEvent]:
        params: list[object] = []
        clauses: list[str] = []
        if target_id:
            clauses.append("affected_id = ?")
            params.append(target_id)
        if target_type:
            clauses.append("affected_type = ?")
            params.append(target_type)
        if not clauses:
            namespace = namespace or self.namespace
            clauses.append("namespace = ?")
            params.append(namespace)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM invalidation_events
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [InvalidationEvent.from_row(row) for row in rows]

    def build_semantic_clusters(
        self,
        namespace: str,
        *,
        target: str = "claims",
    ) -> list[SemanticCluster]:
        self.run_inference(namespace, engines=["semantic"], dry_run=False)
        return self.list_semantic_clusters(namespace=namespace)

    def list_semantic_clusters(
        self,
        *,
        namespace: str | None = None,
        limit: int = 50,
    ) -> list[SemanticCluster]:
        namespace = namespace or self.namespace
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM semantic_clusters
            WHERE namespace = ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (namespace, limit),
        ).fetchall()
        return [self.get_semantic_cluster(row["id"]) for row in rows]

    def get_semantic_cluster(self, cluster_id: str) -> SemanticCluster:
        row = self.store.connection.execute(
            "SELECT * FROM semantic_clusters WHERE id = ?",
            (cluster_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Semantic cluster not found: {cluster_id}")
        member_rows = self.store.connection.execute(
            """
            SELECT member_id
            FROM semantic_cluster_members
            WHERE cluster_id = ?
            ORDER BY member_id
            """,
            (cluster_id,),
        ).fetchall()
        return SemanticCluster.from_row(row, [member["member_id"] for member in member_rows])

    def list_semantic_relations(
        self,
        *,
        namespace: str | None = None,
        source_id: str | None = None,
        limit: int = 50,
    ) -> list[SemanticRelation]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if source_id:
            clause += " AND source_id = ?"
            params.append(source_id)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM semantic_relations
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [SemanticRelation.from_row(row) for row in rows]

    def record_usage(
        self,
        namespace: str,
        *,
        target_id: str,
        target_type: str,
        usage_type: str,
        query: str | None = None,
        session_id: str | None = None,
        project_id: str | None = None,
        context_pack_id: str | None = None,
        rank: int | None = None,
        score: float | None = None,
        metadata: dict | None = None,
    ) -> MemoryUsageEvent:
        self._require_text(namespace, "namespace")
        if target_type not in USAGE_TARGET_TYPES:
            raise ValidationError(f"Unknown usage target_type: {target_type}")
        if usage_type not in USAGE_TYPES:
            raise ValidationError(f"Unknown usage_type: {usage_type}")
        with self.store.transaction():
            usage_id = self._record_usage_in_transaction(
                namespace=namespace,
                target_id=target_id,
                target_type=target_type,
                usage_type=usage_type,
                query=query,
                session_id=session_id,
                project_id=project_id,
                context_pack_id=context_pack_id,
                rank=rank,
                score=score,
                metadata=metadata,
            )
            self._write_audit(
                namespace=namespace,
                target_type=target_type,
                target_id=target_id,
                action="usage.record",
                details={"usage_id": usage_id, "usage_type": usage_type},
            )
        return self.read_usage(usage_id)

    def read_usage(self, usage_id: str) -> MemoryUsageEvent:
        row = self.store.connection.execute(
            "SELECT * FROM memory_usage_events WHERE id = ?",
            (usage_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Usage event not found: {usage_id}")
        return MemoryUsageEvent.from_row(row)

    def list_usage(
        self,
        *,
        namespace: str | None = None,
        target_id: str | None = None,
        target_type: str | None = None,
        context_pack_id: str | None = None,
        limit: int = 50,
    ) -> list[MemoryUsageEvent]:
        params: list[object] = []
        clauses: list[str] = []
        if target_id:
            clauses.append("target_id = ?")
            params.append(target_id)
        if target_type:
            clauses.append("target_type = ?")
            params.append(target_type)
        if context_pack_id:
            clauses.append("context_pack_id = ?")
            params.append(context_pack_id)
        if not clauses:
            namespace = namespace or self.namespace
            clauses.append("namespace = ?")
            params.append(namespace)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM memory_usage_events
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [MemoryUsageEvent.from_row(row) for row in rows]

    def record_outcome(
        self,
        namespace: str,
        *,
        task_id: str,
        outcome: str,
        used_context_pack_id: str | None = None,
        session_id: str | None = None,
        project_id: str | None = None,
        user_feedback: str | None = None,
        score: float | None = None,
        note: str | None = None,
        metadata: dict | None = None,
    ) -> TaskOutcome:
        self._require_text(task_id, "task_id")
        if outcome not in TASK_OUTCOMES:
            raise ValidationError(f"Unknown task outcome: {outcome}")
        outcome_id = new_id("out")
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO task_outcomes (
                    id, namespace, task_id, outcome, used_context_pack_id,
                    session_id, project_id, user_feedback, score, note,
                    created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outcome_id,
                    namespace,
                    task_id,
                    outcome,
                    used_context_pack_id,
                    session_id,
                    project_id,
                    user_feedback,
                    score,
                    note,
                    utc_now_iso(),
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            self._write_audit(
                namespace=namespace,
                target_type="task_outcome",
                target_id=outcome_id,
                action="outcome.record",
                details={
                    "task_id": task_id,
                    "outcome": outcome,
                    "used_context_pack_id": used_context_pack_id,
                    "truth_effect": "none",
                },
            )
        return self.read_outcome(outcome_id)

    def read_outcome(self, outcome_id: str) -> TaskOutcome:
        row = self.store.connection.execute(
            "SELECT * FROM task_outcomes WHERE id = ?",
            (outcome_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Task outcome not found: {outcome_id}")
        return TaskOutcome.from_row(row)

    def list_outcomes(
        self,
        *,
        namespace: str | None = None,
        project_id: str | None = None,
        limit: int = 50,
    ) -> list[TaskOutcome]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if project_id:
            clause += " AND project_id = ?"
            params.append(project_id)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM task_outcomes
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [TaskOutcome.from_row(row) for row in rows]

    def judge_retrieval(
        self,
        namespace: str,
        *,
        query: str,
        result_id: str,
        result_type: str,
        judgment: str,
        judge: str = "user",
        reason: str | None = None,
        expected_rank: int | None = None,
        session_id: str | None = None,
        project_id: str | None = None,
    ) -> RetrievalJudgment:
        self._require_text(query, "query")
        if judgment not in RETRIEVAL_JUDGMENTS:
            raise ValidationError(f"Unknown retrieval judgment: {judgment}")
        judgment_id = new_id("rj")
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO retrieval_judgments (
                    id, namespace, query, result_id, result_type, judgment,
                    judge, reason, expected_rank, session_id, project_id,
                    created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    judgment_id,
                    namespace,
                    query,
                    result_id,
                    result_type,
                    judgment,
                    judge,
                    reason,
                    expected_rank,
                    session_id,
                    project_id,
                    utc_now_iso(),
                    json.dumps({"truth_effect": "none"}, sort_keys=True),
                ),
            )
            self._write_audit(
                namespace=namespace,
                target_type=result_type,
                target_id=result_id,
                action="retrieval.judge",
                details={"judgment_id": judgment_id, "judgment": judgment, "reason": reason},
            )
        return self.read_retrieval_judgment(judgment_id)

    def read_retrieval_judgment(self, judgment_id: str) -> RetrievalJudgment:
        row = self.store.connection.execute(
            "SELECT * FROM retrieval_judgments WHERE id = ?",
            (judgment_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Retrieval judgment not found: {judgment_id}")
        return RetrievalJudgment.from_row(row)

    def list_retrieval_judgments(
        self,
        *,
        namespace: str | None = None,
        result_id: str | None = None,
        limit: int = 50,
    ) -> list[RetrievalJudgment]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if result_id:
            clause += " AND result_id = ?"
            params.append(result_id)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM retrieval_judgments
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [RetrievalJudgment.from_row(row) for row in rows]

    def create_eval_set(
        self,
        namespace: str,
        *,
        name: str,
        description: str | None = None,
        project_id: str | None = None,
        metadata: dict | None = None,
    ) -> EvaluationSet:
        self._require_text(name, "name")
        eval_set_id = self._stable_id("eval", namespace, name)
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO evaluation_sets (
                    id, namespace, name, description, project_id,
                    created_at, updated_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace, name) DO UPDATE SET
                    description = excluded.description,
                    project_id = excluded.project_id,
                    updated_at = excluded.updated_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    eval_set_id,
                    namespace,
                    name,
                    description,
                    project_id,
                    now,
                    now,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            self._write_audit(
                namespace=namespace,
                target_type="evaluation_set",
                target_id=eval_set_id,
                action="eval_set.create",
                details={"name": name},
            )
        return self.get_eval_set(eval_set_id)

    def get_eval_set(self, eval_set_id: str) -> EvaluationSet:
        row = self.store.connection.execute(
            "SELECT * FROM evaluation_sets WHERE id = ?",
            (eval_set_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Evaluation set not found: {eval_set_id}")
        return EvaluationSet.from_row(row)

    def list_eval_sets(
        self,
        *,
        namespace: str | None = None,
        project_id: str | None = None,
    ) -> list[EvaluationSet]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if project_id:
            clause += " AND (project_id = ? OR project_id IS NULL)"
            params.append(project_id)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM evaluation_sets
            WHERE {clause}
            ORDER BY updated_at DESC
            """,
            params,
        ).fetchall()
        return [EvaluationSet.from_row(row) for row in rows]

    def add_eval_case(
        self,
        eval_set_id: str,
        *,
        query: str,
        expected_claim_ids: list[str] | None = None,
        expected_reflection_ids: list[str] | None = None,
        forbidden_claim_ids: list[str] | None = None,
        expected_sections: dict | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        tags: list[str] | None = None,
        note: str | None = None,
    ) -> EvaluationCase:
        eval_set = self.get_eval_set(eval_set_id)
        case_id = new_id("ecase")
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO evaluation_cases (
                    id, eval_set_id, namespace, query, expected_claim_ids_json,
                    expected_reflection_ids_json, forbidden_claim_ids_json,
                    expected_sections_json, project_id, session_id, tags_json,
                    note, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    eval_set_id,
                    eval_set.namespace,
                    query,
                    json.dumps(expected_claim_ids or [], sort_keys=True),
                    json.dumps(expected_reflection_ids or [], sort_keys=True),
                    json.dumps(forbidden_claim_ids or [], sort_keys=True),
                    json.dumps(expected_sections or {}, sort_keys=True),
                    project_id or eval_set.project_id,
                    session_id,
                    json.dumps(tags or [], sort_keys=True),
                    note,
                    utc_now_iso(),
                ),
            )
            self._write_audit(
                namespace=eval_set.namespace,
                target_type="evaluation_case",
                target_id=case_id,
                action="eval_case.add",
                details={"eval_set_id": eval_set_id, "query": query},
            )
        return self.get_eval_case(case_id)

    def get_eval_case(self, case_id: str) -> EvaluationCase:
        row = self.store.connection.execute(
            "SELECT * FROM evaluation_cases WHERE id = ?",
            (case_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Evaluation case not found: {case_id}")
        return EvaluationCase.from_row(row)

    def list_eval_cases(self, eval_set_id: str) -> list[EvaluationCase]:
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM evaluation_cases
            WHERE eval_set_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (eval_set_id,),
        ).fetchall()
        return [EvaluationCase.from_row(row) for row in rows]

    def run_evaluation(
        self,
        namespace: str,
        *,
        eval_set_id: str,
        policy_version_id: str | None = None,
        retrieval_mode: str = "hybrid",
        context_pack: bool = True,
        limit: int = 10,
        dry_run: bool = False,
    ) -> EvaluationRun:
        eval_set = self.get_eval_set(eval_set_id)
        if eval_set.namespace != namespace:
            raise ValidationError("Evaluation set belongs to a different namespace.")
        cases = self.list_eval_cases(eval_set_id)
        started = utc_now()
        result_rows: list[dict[str, Any]] = []
        aggregate = {
            "recall_at_1": 0.0,
            "recall_at_3": 0.0,
            "recall_at_5": 0.0,
            "precision_at_5": 0.0,
            "mean_reciprocal_rank": 0.0,
            "forbidden_memory_leak_rate": 0.0,
            "disputed_memory_leak_rate": 0.0,
            "rejected_memory_leak_rate": 0.0,
            "superseded_memory_leak_rate": 0.0,
            "stale_memory_leak_rate": 0.0,
            "provenance_preservation_rate": 0.0,
            "context_section_accuracy": 0.0,
            "token_efficiency": 0.0,
            "average_latency_ms": 0.0,
        }
        for case in cases:
            case_started = utc_now()
            results = self.retrieve(
                namespace=namespace,
                query=case.query,
                mode=retrieval_mode,
                limit=limit,
                project_id=case.project_id,
                session_id=case.session_id,
            )
            pack = (
                self.context_pack(
                    namespace=namespace,
                    query=case.query,
                    project_id=case.project_id,
                    session_id=case.session_id,
                    retrieval_mode=retrieval_mode,
                    token_budget=1500,
                    include_derivation_metadata=False,
                    policy_version_id=policy_version_id,
                    record_usage=False,
                )
                if context_pack
                else None
            )
            retrieved_ids = [result.claim_id for result in results]
            if pack:
                for item in pack.items():
                    if item.reflection_id:
                        retrieved_ids.append(item.reflection_id)
                    else:
                        retrieved_ids.append(item.claim_id)
            retrieved_ids = list(dict.fromkeys(retrieved_ids))
            expected = case.expected_claim_ids + case.expected_reflection_ids
            case_metrics = self._evaluation_case_metrics(
                case=case,
                retrieved_ids=retrieved_ids,
                results=results,
                pack=pack,
                started=case_started,
            )
            failure_reasons = self._evaluation_failure_reasons(case_metrics)
            result_rows.append(
                {
                    "case": case,
                    "retrieved_ids": retrieved_ids,
                    "context_pack_id": pack.id if pack else None,
                    "metrics": case_metrics,
                    "passed": not failure_reasons and (not expected or case_metrics["recall_at_5"] >= 1.0),
                    "failure_reasons": failure_reasons,
                }
            )
            for key in aggregate:
                aggregate[key] += float(case_metrics.get(key, 0.0))
        case_count = max(len(cases), 1)
        metrics = {key: value / case_count for key, value in aggregate.items()}
        metrics["case_count"] = len(cases)
        if cases:
            metrics["average_latency_ms"] = (
                sum(row["metrics"]["average_latency_ms"] for row in result_rows) / len(cases)
            )
        passed = bool(
            cases
            and all(row["passed"] for row in result_rows)
            and metrics["forbidden_memory_leak_rate"] == 0.0
            and metrics["rejected_memory_leak_rate"] == 0.0
            and metrics["superseded_memory_leak_rate"] == 0.0
            and metrics["provenance_preservation_rate"] >= 0.99
        )
        run_id = new_id("erun")
        if dry_run:
            return EvaluationRun(
                id=run_id,
                namespace=namespace,
                eval_set_id=eval_set_id,
                policy_version_id=policy_version_id,
                retrieval_mode=retrieval_mode,
                case_count=len(cases),
                metrics=metrics,
                passed=passed,
                created_at=utc_now_iso(),
                metadata={"dry_run": True},
            )
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO evaluation_runs (
                    id, namespace, eval_set_id, policy_version_id, retrieval_mode,
                    case_count, passed, created_at, metrics_json, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    namespace,
                    eval_set_id,
                    policy_version_id,
                    retrieval_mode,
                    len(cases),
                    int(passed),
                    now,
                    json.dumps(metrics, sort_keys=True),
                    json.dumps({"duration_ms": (utc_now() - started).total_seconds() * 1000}, sort_keys=True),
                ),
            )
            for row in result_rows:
                self.store.connection.execute(
                    """
                    INSERT INTO evaluation_results (
                        id, evaluation_run_id, evaluation_case_id, passed,
                        retrieved_ids_json, context_pack_id, metrics_json,
                        failure_reasons_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("eres"),
                        run_id,
                        row["case"].id,
                        int(row["passed"]),
                        json.dumps(row["retrieved_ids"], sort_keys=True),
                        row["context_pack_id"],
                        json.dumps(row["metrics"], sort_keys=True),
                        json.dumps(row["failure_reasons"], sort_keys=True),
                        now,
                    ),
                )
            for metric_name, metric_value in metrics.items():
                if isinstance(metric_value, (int, float)):
                    threshold = self._evaluation_metric_threshold(metric_name)
                    metric_passed = None
                    if threshold is not None:
                        metric_passed = metric_value <= threshold if "leak_rate" in metric_name else metric_value >= threshold
                    self.store.connection.execute(
                        """
                        INSERT INTO evaluation_metrics (
                            id, evaluation_run_id, metric_name, metric_value,
                            threshold, passed, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            new_id("emet"),
                            run_id,
                            metric_name,
                            float(metric_value),
                            threshold,
                            None if metric_passed is None else int(metric_passed),
                            now,
                        ),
                    )
            self._write_audit(
                namespace=namespace,
                target_type="evaluation_run",
                target_id=run_id,
                action="evaluation.run",
                details={"eval_set_id": eval_set_id, "passed": passed, "metrics": metrics},
            )
        return self.read_evaluation_run(run_id)

    def read_evaluation_run(self, run_id: str) -> EvaluationRun:
        row = self.store.connection.execute(
            "SELECT * FROM evaluation_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Evaluation run not found: {run_id}")
        return EvaluationRun.from_row(row)

    def list_evaluation_runs(
        self,
        *,
        namespace: str | None = None,
        eval_set_id: str | None = None,
        limit: int = 50,
    ) -> list[EvaluationRun]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if eval_set_id:
            clause += " AND eval_set_id = ?"
            params.append(eval_set_id)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM evaluation_runs
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [EvaluationRun.from_row(row) for row in rows]

    def optimize_retrieval(
        self,
        namespace: str,
        *,
        eval_set_id: str | None = None,
        baseline_policy_version_id: str | None = None,
        objective: str = "balanced",
        dry_run: bool = True,
        max_trials: int = 50,
        constraints: dict | None = None,
    ) -> OptimizationRun:
        if objective not in OPTIMIZATION_OBJECTIVES:
            raise ValidationError(f"Unknown optimization objective: {objective}")
        baseline_version_id = baseline_policy_version_id or self._active_ranking_policy_version_id()
        baseline = self.get_ranking_policy_version(baseline_version_id)
        proposed_weights = dict(baseline.weights)
        if objective in {"maximize_recall", "project_recall"}:
            proposed_weights["project_relevance"] = min(proposed_weights.get("project_relevance", 0.07) + 0.05, 0.25)
            proposed_weights["semantic_score"] = min(proposed_weights.get("semantic_score", 0.25) + 0.03, 0.35)
        elif objective == "maximize_precision":
            proposed_weights["effective_confidence"] = min(proposed_weights.get("effective_confidence", 0.15) + 0.05, 0.30)
        elif objective == "minimize_conflict_leakage":
            proposed_weights["unresolved_conflict_penalty"] = 0.30
        proposed_config = {
            "weights": proposed_weights,
            "filters": dict(baseline.filters),
            "thresholds": dict(baseline.thresholds),
            "objective": objective,
        }
        eval_run_id = None
        metrics: dict[str, Any] = {"proposal": proposed_config}
        if eval_set_id:
            eval_run = self.run_evaluation(
                namespace,
                eval_set_id=eval_set_id,
                policy_version_id=baseline_version_id,
                retrieval_mode="hybrid",
            )
            eval_run_id = eval_run.id
            metrics = eval_run.metrics
            proposed_config["evaluation_summary"] = {
                "evaluation_run_id": eval_run.id,
                "passed": eval_run.passed,
                "metrics": eval_run.metrics,
            }
        proposal_id = None
        if not dry_run:
            proposal = self.propose_policy_update(
                namespace,
                policy_type="ranking",
                target_policy_id=baseline.policy_id,
                proposed_config=proposed_config,
                reason=f"Retrieval optimization objective: {objective}.",
                source_run_id=None,
                evaluation_run_id=eval_run_id,
            )
            proposal_id = proposal.id
        run_id = new_id("opt")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO optimization_runs (
                    id, namespace, optimization_type, objective,
                    baseline_policy_version_id, eval_set_id, trial_count,
                    best_metrics_json, proposal_id, dry_run, created_at,
                    metadata_json
                )
                VALUES (?, ?, 'retrieval', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    namespace,
                    objective,
                    baseline_version_id,
                    eval_set_id,
                    max(1, min(max_trials, 3)),
                    json.dumps(metrics, sort_keys=True),
                    proposal_id,
                    int(dry_run),
                    now,
                    json.dumps({"constraints": constraints or {}}, sort_keys=True),
                ),
            )
            if proposal_id:
                self.store.connection.execute(
                    "UPDATE policy_proposals SET source_run_id = ? WHERE id = ?",
                    (run_id, proposal_id),
                )
            self._write_audit(
                namespace=namespace,
                target_type="optimization_run",
                target_id=run_id,
                action="optimize.retrieval",
                details={"dry_run": dry_run, "proposal_id": proposal_id},
            )
        return self.read_optimization_run(run_id)

    def read_optimization_run(self, run_id: str) -> OptimizationRun:
        row = self.store.connection.execute(
            "SELECT * FROM optimization_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Optimization run not found: {run_id}")
        return OptimizationRun.from_row(row)

    def propose_policy_update(
        self,
        namespace: str,
        *,
        policy_type: str,
        target_policy_id: str | None,
        proposed_config: dict,
        reason: str,
        source_run_id: str | None = None,
        evaluation_run_id: str | None = None,
    ) -> PolicyProposal:
        if policy_type not in POLICY_TYPES:
            raise ValidationError(f"Unknown policy_type: {policy_type}")
        self._require_text(reason, "reason")
        proposal_id = new_id("prop")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO policy_proposals (
                    id, namespace, policy_type, target_policy_id,
                    proposed_config_json, reason, source_run_id,
                    evaluation_run_id, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending_review', ?)
                """,
                (
                    proposal_id,
                    namespace,
                    policy_type,
                    target_policy_id,
                    json.dumps(proposed_config, sort_keys=True),
                    reason,
                    source_run_id,
                    evaluation_run_id,
                    now,
                ),
            )
            gate_passed, failures = self._policy_gate_status(evaluation_run_id)
            self.store.connection.execute(
                """
                INSERT INTO learning_gate_results (
                    id, namespace, proposal_id, gate_type, passed,
                    metrics_json, failure_reasons_json, created_at
                )
                VALUES (?, ?, ?, 'default_policy_gate', ?, ?, ?, ?)
                """,
                (
                    new_id("gate"),
                    namespace,
                    proposal_id,
                    int(gate_passed),
                    json.dumps(
                        {"evaluation_run_id": evaluation_run_id, "has_evaluation": evaluation_run_id is not None},
                        sort_keys=True,
                    ),
                    json.dumps(failures, sort_keys=True),
                    now,
                ),
            )
            self._write_audit(
                namespace=namespace,
                target_type="policy_proposal",
                target_id=proposal_id,
                action="policy.propose",
                details={"policy_type": policy_type, "evaluation_run_id": evaluation_run_id},
            )
        return self.get_policy_proposal(proposal_id)

    def get_policy_proposal(self, proposal_id: str) -> PolicyProposal:
        row = self.store.connection.execute(
            "SELECT * FROM policy_proposals WHERE id = ?",
            (proposal_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Policy proposal not found: {proposal_id}")
        return PolicyProposal.from_row(row)

    def list_policy_proposals(
        self,
        *,
        namespace: str | None = None,
        status: str | None = None,
        policy_type: str | None = None,
        limit: int = 50,
    ) -> list[PolicyProposal]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if status:
            clause += " AND status = ?"
            params.append(status)
        if policy_type:
            clause += " AND policy_type = ?"
            params.append(policy_type)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM policy_proposals
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [PolicyProposal.from_row(row) for row in rows]

    def review_policy_proposal(
        self,
        proposal_id: str,
        *,
        decision: str,
        reason: str,
        reviewer: str = "user",
    ) -> PolicyProposal:
        if decision not in POLICY_REVIEW_DECISIONS:
            raise ValidationError(f"Unknown policy proposal decision: {decision}")
        proposal = self.get_policy_proposal(proposal_id)
        status = {
            "approve": "approved",
            "reject": "rejected",
            "defer": proposal.status,
            "request_changes": "pending_review",
        }[decision]
        with self.store.transaction():
            self.store.connection.execute(
                """
                UPDATE policy_proposals
                SET status = ?, reviewed_at = ?, reviewer = ?, review_note = ?
                WHERE id = ?
                """,
                (status, utc_now_iso(), reviewer, reason, proposal_id),
            )
            self._write_audit(
                namespace=proposal.namespace,
                target_type="policy_proposal",
                target_id=proposal_id,
                action=f"policy.{decision}",
                details={"reason": reason, "reviewer": reviewer},
            )
        return self.get_policy_proposal(proposal_id)

    def apply_policy_proposal(
        self,
        proposal_id: str,
        *,
        reason: str,
        applied_by: str = "user",
        require_evaluation_pass: bool = True,
    ) -> PolicyApplicationRecord:
        proposal = self.get_policy_proposal(proposal_id)
        if proposal.status != "approved":
            raise ValidationError("Policy proposal must be approved before application.")
        if require_evaluation_pass:
            passed, failures = self._policy_gate_status(proposal.evaluation_run_id)
            if not passed:
                raise ValidationError("Policy proposal failed evaluation gate: " + "; ".join(failures))
        old_version_id = None
        if proposal.policy_type == "ranking":
            policy_id = proposal.target_policy_id or "rpol_default"
            policy = self.get_ranking_policy(policy_id)
            old_version_id = policy.active_version_id
            new_version_id = self._create_ranking_policy_version(
                policy_id=policy_id,
                config=proposal.proposed_config,
                created_by=f"proposal:{proposal.id}",
                status="active",
                evaluation_summary=self._evaluation_summary(proposal.evaluation_run_id),
            )
            with self.store.transaction():
                if old_version_id:
                    self.store.connection.execute(
                        "UPDATE ranking_policy_versions SET status = 'superseded' WHERE id = ?",
                        (old_version_id,),
                    )
                self.store.connection.execute(
                    "UPDATE ranking_policies SET active_version_id = ?, updated_at = ? WHERE id = ?",
                    (new_version_id, utc_now_iso(), policy_id),
                )
        elif proposal.policy_type == "context_pack":
            policy_id = proposal.target_policy_id or "cpol_default"
            old_version_id = self._active_context_policy_version_id(policy_id)
            new_version_id = self._create_context_policy_version(
                policy_id=policy_id,
                config=proposal.proposed_config,
                created_by=f"proposal:{proposal.id}",
                status="active",
                evaluation_summary=self._evaluation_summary(proposal.evaluation_run_id),
            )
            with self.store.transaction():
                if old_version_id:
                    self.store.connection.execute(
                        "UPDATE context_pack_policy_versions SET status = 'superseded' WHERE id = ?",
                        (old_version_id,),
                    )
                self.store.connection.execute(
                    "UPDATE context_pack_policies SET active_version_id = ?, updated_at = ? WHERE id = ?",
                    (new_version_id, utc_now_iso(), policy_id),
                )
        else:
            new_version_id = self._stable_id("polv", proposal.policy_type, proposal.id)
        app_id = new_id("app")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO policy_application_history (
                    id, namespace, proposal_id, policy_type, old_version_id,
                    new_version_id, reason, applied_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    app_id,
                    proposal.namespace,
                    proposal_id,
                    proposal.policy_type,
                    old_version_id,
                    new_version_id,
                    reason,
                    applied_by,
                    now,
                ),
            )
            self.store.connection.execute(
                "UPDATE policy_proposals SET status = 'applied' WHERE id = ?",
                (proposal_id,),
            )
            self.store.connection.execute(
                """
                INSERT INTO rollback_records (
                    id, namespace, target_type, target_id, from_version_id,
                    to_version_id, reason, rolled_back_by, created_at,
                    metadata_json
                )
                VALUES (?, ?, 'policy', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("roll"),
                    proposal.namespace,
                    proposal.target_policy_id or proposal.policy_type,
                    new_version_id,
                    old_version_id,
                    "Rollback target created during policy application.",
                    applied_by,
                    now,
                    json.dumps({"proposal_id": proposal_id, "record_type": "rollback_target"}, sort_keys=True),
                ),
            )
            self._write_audit(
                namespace=proposal.namespace,
                target_type="policy_proposal",
                target_id=proposal_id,
                action="policy.apply",
                details={"old_version_id": old_version_id, "new_version_id": new_version_id, "reason": reason},
            )
        return self.read_policy_application(app_id)

    def read_policy_application(self, app_id: str) -> PolicyApplicationRecord:
        row = self.store.connection.execute(
            "SELECT * FROM policy_application_history WHERE id = ?",
            (app_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Policy application not found: {app_id}")
        return PolicyApplicationRecord.from_row(row)

    def list_policy_applications(
        self,
        *,
        namespace: str | None = None,
        policy_type: str | None = None,
        limit: int = 50,
    ) -> list[PolicyApplicationRecord]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if policy_type:
            clause += " AND policy_type = ?"
            params.append(policy_type)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM policy_application_history
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [PolicyApplicationRecord.from_row(row) for row in rows]

    def get_ranking_policy(self, policy_id: str) -> RankingPolicy:
        row = self.store.connection.execute(
            "SELECT * FROM ranking_policies WHERE id = ?",
            (policy_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Ranking policy not found: {policy_id}")
        return RankingPolicy.from_row(row)

    def get_ranking_policy_version(self, version_id: str) -> RankingPolicyVersion:
        row = self.store.connection.execute(
            "SELECT * FROM ranking_policy_versions WHERE id = ?",
            (version_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Ranking policy version not found: {version_id}")
        return RankingPolicyVersion.from_row(row)

    def list_ranking_policies(self, *, namespace: str | None = None) -> list[RankingPolicy]:
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM ranking_policies
            WHERE namespace IS NULL OR namespace = ?
            ORDER BY namespace IS NOT NULL, name
            """,
            (namespace or self.namespace,),
        ).fetchall()
        return [RankingPolicy.from_row(row) for row in rows]

    def list_ranking_policy_versions(self, policy_id: str) -> list[RankingPolicyVersion]:
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM ranking_policy_versions
            WHERE policy_id = ?
            ORDER BY version ASC
            """,
            (policy_id,),
        ).fetchall()
        return [RankingPolicyVersion.from_row(row) for row in rows]

    def rollback_policy(
        self,
        namespace: str,
        *,
        policy_id: str,
        target_version_id: str,
        reason: str,
        rolled_back_by: str = "user",
    ) -> RollbackRecord:
        policy = self.get_ranking_policy(policy_id)
        self.get_ranking_policy_version(target_version_id)
        from_version_id = policy.active_version_id
        rollback_id = new_id("roll")
        with self.store.transaction():
            if from_version_id:
                self.store.connection.execute(
                    "UPDATE ranking_policy_versions SET status = 'rolled_back' WHERE id = ?",
                    (from_version_id,),
                )
            self.store.connection.execute(
                "UPDATE ranking_policy_versions SET status = 'active' WHERE id = ?",
                (target_version_id,),
            )
            self.store.connection.execute(
                "UPDATE ranking_policies SET active_version_id = ?, updated_at = ? WHERE id = ?",
                (target_version_id, utc_now_iso(), policy_id),
            )
            self.store.connection.execute(
                """
                INSERT INTO rollback_records (
                    id, namespace, target_type, target_id, from_version_id,
                    to_version_id, reason, rolled_back_by, created_at,
                    metadata_json
                )
                VALUES (?, ?, 'policy', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rollback_id,
                    namespace,
                    policy_id,
                    from_version_id,
                    target_version_id,
                    reason,
                    rolled_back_by,
                    utc_now_iso(),
                    json.dumps({}, sort_keys=True),
                ),
            )
            self._write_audit(
                namespace=namespace,
                target_type="policy",
                target_id=policy_id,
                action="policy.rollback",
                details={"from_version_id": from_version_id, "to_version_id": target_version_id, "reason": reason},
            )
        return self.read_rollback(rollback_id)

    def propose_procedure_update(
        self,
        namespace: str,
        *,
        procedure_claim_id: str | None = None,
        title: str,
        proposed_text: str,
        reason: str,
        source_ids: list[str] | None = None,
        source_type: str | None = None,
        evaluation_run_id: str | None = None,
        require_review: bool = True,
    ) -> ProcedureUpdateProposal:
        normalized_source_ids = list(source_ids or [])
        normalized_source_type = source_type
        if not normalized_source_ids and not evaluation_run_id:
            normalized_source_ids = [self._stable_id("manual_reason", namespace, title, reason)]
            normalized_source_type = normalized_source_type or "manual_reason"
        if not require_review and self._procedure_update_risk_level(title, proposed_text, reason) in {
            "high",
            "critical",
        }:
            raise ValidationError("High-risk procedure updates require explicit review.")
        status = "pending_review" if require_review else "approved"
        proposal_id = new_id("procprop")
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO procedure_update_proposals (
                    id, namespace, procedure_claim_id, title, proposed_text,
                    reason, source_ids_json, source_type, evaluation_run_id,
                    status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    namespace,
                    procedure_claim_id,
                    title,
                    proposed_text,
                    reason,
                    json.dumps(normalized_source_ids, sort_keys=True),
                    normalized_source_type,
                    evaluation_run_id,
                    status,
                    utc_now_iso(),
                ),
            )
            self._write_audit(
                namespace=namespace,
                target_type="procedure_update_proposal",
                target_id=proposal_id,
                action="procedure.propose",
                details={
                    "title": title,
                    "source_ids": normalized_source_ids,
                    "source_type": normalized_source_type,
                    "risk_level": self._procedure_update_risk_level(title, proposed_text, reason),
                },
            )
        return self.get_procedure_update_proposal(proposal_id)

    def get_procedure_update_proposal(self, proposal_id: str) -> ProcedureUpdateProposal:
        row = self.store.connection.execute(
            "SELECT * FROM procedure_update_proposals WHERE id = ?",
            (proposal_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Procedure update proposal not found: {proposal_id}")
        return ProcedureUpdateProposal.from_row(row)

    def list_procedure_update_proposals(
        self,
        *,
        namespace: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ProcedureUpdateProposal]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if status:
            clause += " AND status = ?"
            params.append(status)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM procedure_update_proposals
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [ProcedureUpdateProposal.from_row(row) for row in rows]

    def review_procedure_update(
        self,
        proposal_id: str,
        *,
        decision: str,
        reason: str,
        reviewer: str = "user",
    ) -> ProcedureUpdateProposal:
        if decision not in POLICY_REVIEW_DECISIONS:
            raise ValidationError(f"Unknown procedure proposal decision: {decision}")
        proposal = self.get_procedure_update_proposal(proposal_id)
        status = {
            "approve": "approved",
            "reject": "rejected",
            "defer": proposal.status,
            "request_changes": "pending_review",
        }[decision]
        with self.store.transaction():
            self.store.connection.execute(
                """
                UPDATE procedure_update_proposals
                SET status = ?, reviewed_at = ?, reviewer = ?, review_note = ?
                WHERE id = ?
                """,
                (status, utc_now_iso(), reviewer, reason, proposal_id),
            )
            self._write_audit(
                namespace=proposal.namespace,
                target_type="procedure_update_proposal",
                target_id=proposal_id,
                action=f"procedure.{decision}",
                details={"reason": reason},
            )
        return self.get_procedure_update_proposal(proposal_id)

    def apply_procedure_update(
        self,
        proposal_id: str,
        *,
        reason: str,
        applied_by: str = "user",
    ) -> ProcedureVersion:
        proposal = self.get_procedure_update_proposal(proposal_id)
        if proposal.status != "approved":
            raise ValidationError("Procedure update proposal must be approved before application.")
        rows = self.store.connection.execute(
            """
            SELECT version
            FROM procedure_versions
            WHERE namespace = ?
              AND (procedure_claim_id IS ? OR title = ?)
            ORDER BY version DESC
            LIMIT 1
            """,
            (proposal.namespace, proposal.procedure_claim_id, proposal.title),
        ).fetchone()
        next_version = (rows["version"] + 1) if rows else 1
        version_id = new_id("pver")
        with self.store.transaction():
            self.store.connection.execute(
                """
                UPDATE procedure_versions
                SET status = 'superseded'
                WHERE namespace = ?
                  AND status = 'active'
                  AND (procedure_claim_id IS ? OR title = ?)
                """,
                (proposal.namespace, proposal.procedure_claim_id, proposal.title),
            )
            self.store.connection.execute(
                """
                INSERT INTO procedure_versions (
                    id, namespace, procedure_claim_id, version, title, text,
                    status, source_proposal_id, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    version_id,
                    proposal.namespace,
                    proposal.procedure_claim_id,
                    next_version,
                    proposal.title,
                    proposal.proposed_text,
                    proposal.id,
                    utc_now_iso(),
                    json.dumps(
                        {
                            "reason": reason,
                            "applied_by": applied_by,
                            "source_ids": proposal.source_ids,
                            "source_type": proposal.source_type,
                        },
                        sort_keys=True,
                    ),
                ),
            )
            self.store.connection.execute(
                "UPDATE procedure_update_proposals SET status = 'applied' WHERE id = ?",
                (proposal_id,),
            )
            if proposal.procedure_claim_id:
                claim = self.read_claim(proposal.procedure_claim_id)
                if claim.namespace != proposal.namespace:
                    raise ValidationError("Procedure claim belongs to a different namespace.")
                self.store.connection.execute(
                    """
                    UPDATE claims
                    SET object = ?, last_verified_at = ?
                    WHERE id = ?
                    """,
                    (proposal.proposed_text, utc_now_iso(), proposal.procedure_claim_id),
                )
                self._write_audit(
                    namespace=proposal.namespace,
                    target_type="claim",
                    target_id=proposal.procedure_claim_id,
                    action="procedure_claim.update",
                    details={"procedure_version_id": version_id, "reason": reason},
                )
            self._write_audit(
                namespace=proposal.namespace,
                target_type="procedure_version",
                target_id=version_id,
                action="procedure.apply",
                details={"proposal_id": proposal_id, "reason": reason},
            )
        return self.get_procedure_version(version_id)

    def get_procedure_version(self, version_id: str) -> ProcedureVersion:
        row = self.store.connection.execute(
            "SELECT * FROM procedure_versions WHERE id = ?",
            (version_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Procedure version not found: {version_id}")
        return ProcedureVersion.from_row(row)

    def list_procedure_versions(
        self,
        *,
        namespace: str | None = None,
        procedure_claim_id: str | None = None,
        title: str | None = None,
    ) -> list[ProcedureVersion]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if procedure_claim_id:
            clause += " AND procedure_claim_id = ?"
            params.append(procedure_claim_id)
        if title:
            clause += " AND title = ?"
            params.append(title)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM procedure_versions
            WHERE {clause}
            ORDER BY version ASC
            """,
            params,
        ).fetchall()
        return [ProcedureVersion.from_row(row) for row in rows]

    def rollback_procedure(
        self,
        namespace: str,
        *,
        procedure_claim_id: str | None,
        target_version_id: str,
        reason: str,
        rolled_back_by: str = "user",
    ) -> RollbackRecord:
        target = self.get_procedure_version(target_version_id)
        if target.namespace != namespace:
            raise ValidationError("Procedure version belongs to a different namespace.")
        current = self.store.connection.execute(
            """
            SELECT id
            FROM procedure_versions
            WHERE namespace = ?
              AND status = 'active'
              AND (procedure_claim_id IS ? OR title = ?)
            LIMIT 1
            """,
            (namespace, procedure_claim_id, target.title),
        ).fetchone()
        rollback_id = new_id("roll")
        with self.store.transaction():
            if current:
                self.store.connection.execute(
                    "UPDATE procedure_versions SET status = 'rolled_back' WHERE id = ?",
                    (current["id"],),
                )
            self.store.connection.execute(
                "UPDATE procedure_versions SET status = 'active' WHERE id = ?",
                (target_version_id,),
            )
            self.store.connection.execute(
                """
                INSERT INTO rollback_records (
                    id, namespace, target_type, target_id, from_version_id,
                    to_version_id, reason, rolled_back_by, created_at,
                    metadata_json
                )
                VALUES (?, ?, 'procedure', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rollback_id,
                    namespace,
                    procedure_claim_id or target.title,
                    current["id"] if current else None,
                    target_version_id,
                    reason,
                    rolled_back_by,
                    utc_now_iso(),
                    json.dumps({}, sort_keys=True),
                ),
            )
            self._write_audit(
                namespace=namespace,
                target_type="procedure",
                target_id=procedure_claim_id or target.title,
                action="procedure.rollback",
                details={"to_version_id": target_version_id, "reason": reason},
            )
        return self.read_rollback(rollback_id)

    def run_learning(
        self,
        namespace: str,
        *,
        project_id: str | None = None,
        learning_targets: list[str] | None = None,
        eval_set_id: str | None = None,
        dry_run: bool = True,
        max_proposals: int = 10,
    ) -> LearningRun:
        targets = learning_targets or ["retrieval_policy", "procedure_memory"]
        unknown = [target for target in targets if target not in LEARNING_TARGETS]
        if unknown:
            raise ValidationError(f"Unknown learning targets: {', '.join(unknown)}")
        warnings: list[str] = []
        proposals: list[str] = []
        if dry_run:
            run_id = new_id("learn")
            return LearningRun(
                id=run_id,
                namespace=namespace,
                project_id=project_id,
                learning_targets=targets,
                eval_set_id=eval_set_id,
                dry_run=True,
                proposals_created=[],
                warnings=["dry_run: no proposals created"],
                created_at=utc_now_iso(),
                metadata={},
            )
        if "retrieval_policy" in targets and len(proposals) < max_proposals:
            opt = self.optimize_retrieval(
                namespace,
                eval_set_id=eval_set_id,
                objective="balanced",
                dry_run=False,
            )
            if opt.proposal_id:
                proposals.append(opt.proposal_id)
        if "procedure_memory" in targets and len(proposals) < max_proposals:
            outcomes = self.list_outcomes(namespace=namespace, project_id=project_id, limit=20)
            if outcomes:
                proposal = self.propose_procedure_update(
                    namespace,
                    title="Milestone contract writing procedure",
                    proposed_text=(
                        "For architecture milestone contracts, include scope, APIs, storage, "
                        "CLI, tests, migration, acceptance criteria, and demo script."
                    ),
                    reason="Derived from successful task outcomes and M5 learning run.",
                    source_ids=[outcome.id for outcome in outcomes[:5]],
                    source_type="task_outcome",
                    evaluation_run_id=None,
                )
                proposals.append(proposal.id)
            else:
                warnings.append("No task outcomes available for procedure proposal.")
        run_id = new_id("learn")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO learning_runs (
                    id, namespace, project_id, learning_targets_json,
                    eval_set_id, dry_run, proposals_created_json,
                    warnings_json, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    namespace,
                    project_id,
                    json.dumps(targets, sort_keys=True),
                    eval_set_id,
                    int(dry_run),
                    json.dumps(proposals, sort_keys=True),
                    json.dumps(warnings, sort_keys=True),
                    now,
                    json.dumps({"learning_mode": "proposal_only"}, sort_keys=True),
                ),
            )
            self._write_audit(
                namespace=namespace,
                target_type="learning_run",
                target_id=run_id,
                action="learning.run",
                details={"targets": targets, "proposals_created": proposals},
            )
        return self.read_learning_run(run_id)

    def read_learning_run(self, run_id: str) -> LearningRun:
        row = self.store.connection.execute(
            "SELECT * FROM learning_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Learning run not found: {run_id}")
        return LearningRun.from_row(row)

    def list_learning_runs(
        self,
        *,
        namespace: str | None = None,
        limit: int = 50,
    ) -> list[LearningRun]:
        namespace = namespace or self.namespace
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM learning_runs
            WHERE namespace = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (namespace, limit),
        ).fetchall()
        return [LearningRun.from_row(row) for row in rows]

    def enqueue_job(
        self,
        namespace: str,
        *,
        job_type: str,
        payload: dict,
        priority: float = 0.5,
        run_after: datetime | None = None,
    ) -> LocalJob:
        if job_type not in JOB_TYPES:
            raise ValidationError(f"Unknown job_type: {job_type}")
        job_id = new_id("job")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO local_jobs (
                    id, namespace, job_type, payload_json, priority, status,
                    run_after, attempts, max_attempts, last_error, created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?, 0, ?, NULL, ?, ?)
                """,
                (
                    job_id,
                    namespace,
                    job_type,
                    json.dumps(payload, sort_keys=True),
                    self._clamp(priority),
                    run_after.isoformat() if run_after else None,
                    int(payload.get("max_attempts", 3)),
                    now,
                    now,
                ),
            )
            self._write_audit(
                namespace=namespace,
                target_type="local_job",
                target_id=job_id,
                action="job.enqueue",
                details={"job_type": job_type},
            )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> LocalJob:
        row = self.store.connection.execute(
            "SELECT * FROM local_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Local job not found: {job_id}")
        return LocalJob.from_row(row)

    def list_jobs(
        self,
        *,
        namespace: str | None = None,
        job_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[LocalJob]:
        params: list[object] = []
        clauses: list[str] = []
        if namespace is not None:
            clauses.append("namespace = ?")
            params.append(namespace)
        if job_type:
            clauses.append("job_type = ?")
            params.append(job_type)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM local_jobs
            {where}
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [LocalJob.from_row(row) for row in rows]

    def run_jobs(
        self,
        *,
        namespace: str | None = None,
        job_type: str | None = None,
        max_jobs: int = 10,
    ) -> list[LocalJob]:
        params: list[object] = [utc_now_iso()]
        clauses = ["status = 'pending'", "(run_after IS NULL OR run_after <= ?)"]
        if namespace:
            clauses.append("namespace = ?")
            params.append(namespace)
        if job_type:
            clauses.append("job_type = ?")
            params.append(job_type)
        params.append(max_jobs)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM local_jobs
            WHERE {' AND '.join(clauses)}
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        completed: list[LocalJob] = []
        for row in rows:
            job = LocalJob.from_row(row)
            self._run_single_job(job)
            completed.append(self.get_job(job.id))
        return completed

    def health_report(
        self,
        namespace: str,
        *,
        project_id: str | None = None,
        include_recommendations: bool = True,
    ) -> MemoryHealthReport:
        metrics = self._health_metrics(namespace=namespace, project_id=project_id)
        warnings: list[str] = []
        recommendations: list[str] = []
        if metrics["unresolved_conflict_count"] > 0:
            warnings.append("Unresolved conflicts need review.")
            recommendations.append("Run conflict resolution for unresolved conflict families.")
        if metrics["pending_review_count"] > 0:
            warnings.append("Pending candidates or inferences need review.")
            recommendations.append("Review candidate and inference queues.")
        if metrics["invalidated_derived_count"] > 0:
            warnings.append("Invalidated or stale derived memories need refresh.")
            recommendations.append("Refresh or rebuild stale reflections and inferences.")
        if metrics["low_confidence_active_count"] > 0:
            warnings.append("Active low-confidence memories need verification.")
            recommendations.append("Collect explicit evidence or demote weak active memories.")
        if metrics["unindexed_claim_count"] > 0:
            recommendations.append("Run semantic indexing for active claims.")
        if not include_recommendations:
            recommendations = []
        report_id = new_id("health")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO memory_health_snapshots (
                    id, namespace, project_id, metrics_json, warnings_json,
                    recommendations_json, generated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    namespace,
                    project_id,
                    json.dumps(metrics, sort_keys=True),
                    json.dumps(warnings, sort_keys=True),
                    json.dumps(recommendations, sort_keys=True),
                    now,
                ),
            )
            self._write_audit(
                namespace=namespace,
                target_type="memory_health_report",
                target_id=report_id,
                action="health.report",
                details={"metrics": metrics},
            )
        return self.read_health_report(report_id)

    def read_health_report(self, report_id: str) -> MemoryHealthReport:
        row = self.store.connection.execute(
            "SELECT * FROM memory_health_snapshots WHERE id = ?",
            (report_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Memory health report not found: {report_id}")
        return MemoryHealthReport.from_row(row)

    def create_review_task(
        self,
        namespace: str,
        *,
        task_type: str,
        title: str,
        description: str,
        target_id: str,
        target_type: str,
        priority: float = 0.5,
        severity: str = "medium",
        recommended_action: str | None = None,
        due_at: str | None = None,
        metadata: dict | None = None,
    ) -> ReviewTask:
        self._require_text(namespace, "namespace")
        if task_type not in REVIEW_TASK_TYPES:
            raise ValidationError(f"Unknown review task type: {task_type}")
        if severity not in REVIEW_SEVERITIES:
            raise ValidationError(f"Unknown review task severity: {severity}")
        existing = self.store.connection.execute(
            """
            SELECT *
            FROM review_tasks
            WHERE namespace = ?
              AND task_type = ?
              AND target_id = ?
              AND target_type = ?
              AND status IN ('open', 'in_progress', 'deferred', 'blocked')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (namespace, task_type, target_id, target_type),
        ).fetchone()
        if existing:
            return ReviewTask.from_row(existing)
        task_id = new_id("rev")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO review_tasks (
                    id, namespace, task_type, title, description, target_id,
                    target_type, priority, severity, status, recommended_action,
                    created_at, updated_at, due_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    namespace,
                    task_type,
                    title,
                    description,
                    target_id,
                    target_type,
                    self._clamp(priority),
                    severity,
                    recommended_action,
                    now,
                    now,
                    due_at,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            self._write_review_task_event(
                review_task_id=task_id,
                event_type="created",
                actor="system",
                note="Review task created.",
                metadata={"target_id": target_id, "target_type": target_type},
            )
            self._write_audit(
                namespace=namespace,
                target_type="review_task",
                target_id=task_id,
                action="review_task.create",
                details={"task_type": task_type, "target_id": target_id, "target_type": target_type},
            )
        return self.get_review_task(task_id)

    def get_review_task(self, review_task_id: str) -> ReviewTask:
        row = self.store.connection.execute(
            "SELECT * FROM review_tasks WHERE id = ?",
            (review_task_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Review task not found: {review_task_id}")
        return ReviewTask.from_row(row)

    def list_review_tasks(
        self,
        namespace: str | None = None,
        *,
        status: str | None = None,
        task_type: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[ReviewTask]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clauses = ["namespace = ?"]
        if status:
            clauses.append("status = ?")
            params.append(status)
        if task_type:
            clauses.append("task_type = ?")
            params.append(task_type)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM review_tasks
            WHERE {' AND '.join(clauses)}
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 5
                    WHEN 'high' THEN 4
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 2
                    ELSE 1
                END DESC,
                priority DESC,
                created_at ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [ReviewTask.from_row(row) for row in rows]

    def list_review_task_events(self, review_task_id: str) -> list[ReviewTaskEvent]:
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM review_task_events
            WHERE review_task_id = ?
            ORDER BY created_at ASC
            """,
            (review_task_id,),
        ).fetchall()
        return [ReviewTaskEvent.from_row(row) for row in rows]

    def resolve_review_task(
        self,
        review_task_id: str,
        *,
        resolution: str,
        reason: str,
        actor: str = "user",
    ) -> ReviewTask:
        return self._transition_review_task(
            review_task_id,
            status="resolved",
            event_type="resolved",
            note=reason,
            actor=actor,
            metadata={"resolution": resolution},
        )

    def dismiss_review_task(self, review_task_id: str, *, reason: str, actor: str = "user") -> ReviewTask:
        return self._transition_review_task(
            review_task_id,
            status="dismissed",
            event_type="dismissed",
            note=reason,
            actor=actor,
        )

    def defer_review_task(self, review_task_id: str, *, reason: str, actor: str = "user") -> ReviewTask:
        return self._transition_review_task(
            review_task_id,
            status="deferred",
            event_type="deferred",
            note=reason,
            actor=actor,
        )

    def generate_review_tasks(self, namespace: str, *, limit: int = 200) -> list[ReviewTask]:
        generated: list[ReviewTask] = []
        for candidate in self.list_candidates(namespace, status="pending_review", limit=limit):
            generated.append(
                self.create_review_task(
                    namespace,
                    task_type="candidate_review",
                    title=f"Review candidate {candidate.id}",
                    description=claim_text(candidate.subject, candidate.predicate, candidate.object),
                    target_id=candidate.id,
                    target_type="candidate_claim",
                    priority=max(0.4, candidate.suggested_importance),
                    severity="medium" if candidate.contradiction_risk < 0.5 else "high",
                    recommended_action="Promote, edit, reject, or defer this candidate.",
                    metadata={"candidate_status": candidate.candidate_status},
                )
            )
        for conflict in self.list_conflict_families(namespace=namespace, status="unresolved"):
            generated.append(
                self.create_review_task(
                    namespace,
                    task_type="conflict_resolution",
                    title=f"Resolve conflict for {conflict.subject}.{conflict.predicate}",
                    description=f"{len(conflict.claim_ids)} claims conflict for {conflict.subject}.{conflict.predicate}.",
                    target_id=conflict.id,
                    target_type="conflict",
                    priority=0.8,
                    severity="high",
                    recommended_action="Resolve by scope, correction, confidence, or manual review.",
                    metadata={"claim_ids": conflict.claim_ids},
                )
            )
        for inference in self.list_inferences(namespace, status="pending_review", limit=limit):
            generated.append(
                self.create_review_task(
                    namespace,
                    task_type="inference_review",
                    title=f"Review inference {inference.id}",
                    description=inference.conclusion,
                    target_id=inference.id,
                    target_type="inference",
                    priority=0.55,
                    severity="medium",
                    recommended_action="Validate, reject, or promote the inference through integrity gates.",
                    metadata={"engine": inference.engine, "inference_type": inference.inference_type},
                )
            )
        for reflection in [
            *self.list_reflections(namespace=namespace, status="stale", limit=limit),
            *self.list_reflections(namespace=namespace, status="invalidated", limit=limit),
        ]:
            generated.append(
                self.create_review_task(
                    namespace,
                    task_type="reflection_refresh",
                    title=f"Refresh reflection {reflection.title}",
                    description=f"Reflection {reflection.id} is {reflection.status}.",
                    target_id=reflection.id,
                    target_type="reflection",
                    priority=0.5,
                    severity="medium",
                    recommended_action="Refresh, archive, or rebuild from current sources.",
                    metadata={"status": reflection.status},
                )
            )
        for proposal in self.list_policy_proposals(namespace=namespace, status="pending_review"):
            generated.append(
                self.create_review_task(
                    namespace,
                    task_type="policy_review",
                    title=f"Review policy proposal {proposal.id}",
                    description=proposal.reason,
                    target_id=proposal.id,
                    target_type="policy_proposal",
                    priority=0.7,
                    severity="high" if proposal.risk_level == "high" else "medium",
                    recommended_action="Approve, reject, request changes, or apply after gates pass.",
                    metadata={"policy_type": proposal.policy_type, "risk_level": proposal.risk_level},
                )
            )
        for proposal in self.list_procedure_update_proposals(namespace=namespace, status="pending_review"):
            generated.append(
                self.create_review_task(
                    namespace,
                    task_type="procedure_review",
                    title=f"Review procedure proposal {proposal.title}",
                    description=proposal.reason,
                    target_id=proposal.id,
                    target_type="procedure_proposal",
                    priority=0.65,
                    severity="high" if proposal.risk_level == "high" else "medium",
                    recommended_action="Approve, reject, or request changes.",
                    metadata={"risk_level": proposal.risk_level},
                )
            )
        for job in self.list_jobs(namespace=namespace, status="failed", limit=limit):
            generated.append(
                self.create_review_task(
                    namespace,
                    task_type="job_failure",
                    title=f"Failed job {job.job_type}",
                    description=job.last_error or "Job failed without a stored error.",
                    target_id=job.id,
                    target_type="local_job",
                    priority=0.75,
                    severity="high",
                    recommended_action="Inspect payload, fix cause, and retry or dismiss.",
                    metadata={"job_type": job.job_type, "attempts": job.attempts},
                )
            )
        for row in self.store.connection.execute(
            """
            SELECT *
            FROM content_risk_flags
            WHERE namespace = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (namespace, limit),
        ).fetchall():
            generated.append(
                self.create_review_task(
                    namespace,
                    task_type="risk_flag_review",
                    title=f"Review {row['risk_type']} risk flag",
                    description=row["description"],
                    target_id=row["id"],
                    target_type="content_risk_flag",
                    priority=0.85,
                    severity="high",
                    recommended_action="Inspect source evidence and reject unsafe candidates if needed.",
                    metadata={"risk_type": row["risk_type"], "severity": row["severity"]},
                )
            )
        return generated

    def trace_retrieval(
        self,
        namespace: str,
        *,
        query: str,
        retrieval_mode: str = "hybrid",
        project_id: str | None = None,
        session_id: str | None = None,
        limit: int = 10,
    ) -> TraceRun:
        started = perf_counter()
        results = self.retrieve(
            namespace=namespace,
            query=query,
            mode=retrieval_mode,
            limit=limit,
            project_id=project_id,
            session_id=session_id,
        )
        trace_id = new_id("trc")
        now = utc_now_iso()
        included_ids = {result.claim_id for result in results}
        policy_version_id = self._active_ranking_policy_version_id()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO trace_runs (
                    id, namespace, trace_type, query, project_id, session_id,
                    retrieval_mode, policy_version_id, duration_ms, created_at,
                    metadata_json
                )
                VALUES (?, ?, 'retrieval', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    namespace,
                    query,
                    project_id,
                    session_id,
                    retrieval_mode,
                    policy_version_id,
                    int((perf_counter() - started) * 1000),
                    now,
                    json.dumps({"limit": limit}, sort_keys=True),
                ),
            )
            self._write_trace_event(trace_id, "retrieval.started", "Retrieval trace captured.", {"query": query})
            for rank, result in enumerate(results, start=1):
                self.store.connection.execute(
                    """
                    INSERT INTO retrieval_trace_items (
                        id, trace_run_id, target_id, target_type, final_score,
                        lexical_score, semantic_score, confidence_score,
                        salience_score, included, omission_reason, rank,
                        metadata_json
                    )
                    VALUES (?, ?, ?, 'claim', ?, ?, ?, ?, ?, 1, NULL, ?, ?)
                    """,
                    (
                        new_id("rti"),
                        trace_id,
                        result.claim_id,
                        result.score,
                        result.lexical_score,
                        result.semantic_score,
                        result.confidence_effective,
                        result.importance,
                        rank,
                        json.dumps(asdict(result), sort_keys=True),
                    ),
                )
            for row in self._trace_candidate_claim_rows(namespace=namespace, project_id=project_id, limit=max(limit * 4, 20)):
                if row["id"] in included_ids:
                    continue
                reason = self._omission_reason_for_claim_row(row, project_id=project_id)
                text = claim_text(row["subject"], row["predicate"], row["object"])
                self.store.connection.execute(
                    """
                    INSERT INTO retrieval_trace_items (
                        id, trace_run_id, target_id, target_type, final_score,
                        lexical_score, semantic_score, confidence_score,
                        salience_score, included, omission_reason, rank,
                        metadata_json
                    )
                    VALUES (?, ?, ?, 'claim', NULL, ?, NULL, ?, ?, 0, ?, NULL, ?)
                    """,
                    (
                        new_id("rti"),
                        trace_id,
                        row["id"],
                        lexical_score(query, text),
                        row["confidence_effective"],
                        row["importance"],
                        reason,
                        json.dumps({"status": row["status"], "memory_type": row["memory_type"], "text": text}, sort_keys=True),
                    ),
                )
            self._write_audit(
                namespace=namespace,
                target_type="trace_run",
                target_id=trace_id,
                action="trace.retrieval",
                details={"query": query, "mode": retrieval_mode, "result_count": len(results)},
            )
        return self.get_trace(trace_id)

    def trace_context_pack(
        self,
        namespace: str,
        *,
        query: str,
        project_id: str | None = None,
        session_id: str | None = None,
        retrieval_mode: str = "hybrid",
        token_budget: int = 2000,
    ) -> TraceRun:
        started = perf_counter()
        pack = self.context_pack(
            namespace=namespace,
            query=query,
            project_id=project_id,
            session_id=session_id,
            retrieval_mode=retrieval_mode,
            token_budget=token_budget,
            include_derivation_metadata=True,
        )
        trace_id = new_id("trc")
        now = utc_now_iso()
        included_claim_ids = {item.claim_id for item in pack.items()}
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO trace_runs (
                    id, namespace, trace_type, query, project_id, session_id,
                    retrieval_mode, policy_version_id, duration_ms, created_at,
                    metadata_json
                )
                VALUES (?, ?, 'context_pack', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    namespace,
                    query,
                    project_id,
                    session_id,
                    retrieval_mode,
                    pack.context_policy_version_id,
                    int((perf_counter() - started) * 1000),
                    now,
                    json.dumps(
                        {
                            "context_pack_id": pack.id,
                            "token_budget": token_budget,
                            "ranking_policy_version_id": pack.ranking_policy_version_id,
                            "warnings": [asdict(warning) for warning in pack.warnings],
                        },
                        sort_keys=True,
                    ),
                ),
            )
            self._write_trace_event(trace_id, "context_pack.built", "Context pack trace captured.", {"context_pack_id": pack.id})
            section_by_id: dict[str, str] = {}
            for section, items in [
                ("core_memory", pack.core_memory),
                ("project_memory", pack.project_memory),
                ("session_memory", pack.session_memory),
                ("procedural_memory", pack.procedural_memory),
                ("reflections", pack.reflection_memory),
                ("relevant_memory", pack.relevant_memory),
            ]:
                for item in items:
                    section_by_id[item.claim_id] = section
            for rank, item in enumerate(pack.items(), start=1):
                self.store.connection.execute(
                    """
                    INSERT INTO context_trace_items (
                        id, trace_run_id, target_id, target_type, section,
                        included, omission_reason, token_estimate, rank,
                        metadata_json
                    )
                    VALUES (?, ?, ?, 'claim', ?, 1, NULL, ?, ?, ?)
                    """,
                    (
                        new_id("cti"),
                        trace_id,
                        item.claim_id,
                        section_by_id.get(item.claim_id),
                        len(item.text.split()),
                        rank,
                        json.dumps(asdict(item), sort_keys=True),
                    ),
                )
            for omitted in pack.omitted:
                self.store.connection.execute(
                    """
                    INSERT INTO context_trace_items (
                        id, trace_run_id, target_id, target_type, section,
                        included, omission_reason, token_estimate, rank,
                        metadata_json
                    )
                    VALUES (?, ?, ?, 'claim', NULL, 0, ?, NULL, NULL, ?)
                    """,
                    (
                        new_id("cti"),
                        trace_id,
                        omitted.claim_id,
                        omitted.reason,
                        json.dumps(asdict(omitted), sort_keys=True),
                    ),
                )
            for row in self._trace_candidate_claim_rows(namespace=namespace, project_id=project_id, limit=50):
                if row["id"] in included_claim_ids:
                    continue
                if any(omitted.claim_id == row["id"] for omitted in pack.omitted):
                    continue
                reason = self._omission_reason_for_claim_row(row, project_id=project_id)
                self.store.connection.execute(
                    """
                    INSERT INTO context_trace_items (
                        id, trace_run_id, target_id, target_type, section,
                        included, omission_reason, token_estimate, rank,
                        metadata_json
                    )
                    VALUES (?, ?, ?, 'claim', NULL, 0, ?, NULL, NULL, ?)
                    """,
                    (
                        new_id("cti"),
                        trace_id,
                        row["id"],
                        reason,
                        json.dumps({"status": row["status"], "memory_type": row["memory_type"]}, sort_keys=True),
                    ),
                )
            self._write_audit(
                namespace=namespace,
                target_type="trace_run",
                target_id=trace_id,
                action="trace.context_pack",
                details={"query": query, "context_pack_id": pack.id},
            )
        return self.get_trace(trace_id)

    def get_trace(self, trace_id: str) -> TraceRun:
        row = self.store.connection.execute("SELECT * FROM trace_runs WHERE id = ?", (trace_id,)).fetchone()
        if not row:
            raise NotFoundError(f"Trace not found: {trace_id}")
        return TraceRun.from_row(row)

    def list_traces(
        self,
        *,
        namespace: str | None = None,
        trace_type: str | None = None,
        limit: int = 50,
    ) -> list[TraceRun]:
        params: list[object] = []
        clauses: list[str] = []
        if namespace:
            clauses.append("namespace = ?")
            params.append(namespace)
        if trace_type:
            clauses.append("trace_type = ?")
            params.append(trace_type)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM trace_runs
            {where}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [TraceRun.from_row(row) for row in rows]

    def list_trace_events(self, trace_id: str) -> list[TraceEvent]:
        rows = self.store.connection.execute(
            "SELECT * FROM trace_events WHERE trace_run_id = ? ORDER BY created_at ASC",
            (trace_id,),
        ).fetchall()
        return [TraceEvent.from_row(row) for row in rows]

    def list_trace_items(self, trace_id: str) -> list[RetrievalTraceItem | ContextTraceItem]:
        trace = self.get_trace(trace_id)
        if trace.trace_type == "retrieval":
            rows = self.store.connection.execute(
                "SELECT * FROM retrieval_trace_items WHERE trace_run_id = ? ORDER BY included DESC, rank ASC",
                (trace_id,),
            ).fetchall()
            return [RetrievalTraceItem.from_row(row) for row in rows]
        rows = self.store.connection.execute(
            "SELECT * FROM context_trace_items WHERE trace_run_id = ? ORDER BY included DESC, rank ASC",
            (trace_id,),
        ).fetchall()
        return [ContextTraceItem.from_row(row) for row in rows]

    def metrics_snapshot(
        self,
        *,
        namespace: str | None = None,
        project_id: str | None = None,
        source: str = "manual",
    ) -> MetricSnapshot:
        metrics = self._operational_metrics(namespace=namespace, project_id=project_id)
        snapshot_id = new_id("met")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO metric_snapshots (
                    id, namespace, project_id, metrics_json, source,
                    generated_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    namespace,
                    project_id,
                    json.dumps(metrics, sort_keys=True),
                    source,
                    now,
                    json.dumps({}, sort_keys=True),
                ),
            )
        return self.get_metric_snapshot(snapshot_id)

    def get_metric_snapshot(self, snapshot_id: str) -> MetricSnapshot:
        row = self.store.connection.execute("SELECT * FROM metric_snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        if not row:
            raise NotFoundError(f"Metric snapshot not found: {snapshot_id}")
        return MetricSnapshot.from_row(row)

    def latest_metric_snapshot(
        self,
        *,
        namespace: str | None = None,
        project_id: str | None = None,
    ) -> MetricSnapshot | None:
        clauses: list[str] = []
        params: list[object] = []
        if namespace is None:
            clauses.append("namespace IS NULL")
        else:
            clauses.append("namespace = ?")
            params.append(namespace)
        if project_id is None:
            clauses.append("project_id IS NULL")
        else:
            clauses.append("project_id = ?")
            params.append(project_id)
        row = self.store.connection.execute(
            f"""
            SELECT *
            FROM metric_snapshots
            WHERE {' AND '.join(clauses)}
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
        return MetricSnapshot.from_row(row) if row else None

    def list_metric_snapshots(
        self,
        *,
        namespace: str | None = None,
        project_id: str | None = None,
        limit: int = 50,
    ) -> list[MetricSnapshot]:
        params: list[object] = []
        clauses: list[str] = []
        if namespace:
            clauses.append("namespace = ?")
            params.append(namespace)
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(limit)
        rows = self.store.connection.execute(
            f"SELECT * FROM metric_snapshots {where} ORDER BY generated_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [MetricSnapshot.from_row(row) for row in rows]

    def create_notification(
        self,
        namespace: str | None,
        *,
        notification_type: str,
        title: str,
        message: str,
        severity: str = "info",
        target_id: str | None = None,
        target_type: str | None = None,
        metadata: dict | None = None,
    ) -> NotificationEvent:
        if severity not in REVIEW_SEVERITIES:
            raise ValidationError(f"Unknown notification severity: {severity}")
        notification_id = new_id("ntf")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO notification_events (
                    id, namespace, notification_type, title, message, severity,
                    status, target_id, target_type, created_at, dismissed_at,
                    snoozed_until, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, 'unread', ?, ?, ?, NULL, NULL, ?)
                """,
                (
                    notification_id,
                    namespace,
                    notification_type,
                    title,
                    message,
                    severity,
                    target_id,
                    target_type,
                    now,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
        return self.get_notification(notification_id)

    def get_notification(self, notification_id: str) -> NotificationEvent:
        row = self.store.connection.execute(
            "SELECT * FROM notification_events WHERE id = ?",
            (notification_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Notification not found: {notification_id}")
        return NotificationEvent.from_row(row)

    def list_notifications(
        self,
        *,
        namespace: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[NotificationEvent]:
        params: list[object] = []
        clauses: list[str] = []
        if namespace is not None:
            clauses.append("(namespace = ? OR namespace IS NULL)")
            params.append(namespace)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(limit)
        rows = self.store.connection.execute(
            f"SELECT * FROM notification_events {where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [NotificationEvent.from_row(row) for row in rows]

    def dismiss_notification(self, notification_id: str) -> NotificationEvent:
        with self.store.transaction():
            self.store.connection.execute(
                """
                UPDATE notification_events
                SET status = 'dismissed', dismissed_at = ?
                WHERE id = ?
                """,
                (utc_now_iso(), notification_id),
            )
        return self.get_notification(notification_id)

    def snooze_notification(self, notification_id: str, *, until: str) -> NotificationEvent:
        with self.store.transaction():
            self.store.connection.execute(
                """
                UPDATE notification_events
                SET status = 'snoozed', snoozed_until = ?
                WHERE id = ?
                """,
                (until, notification_id),
            )
        return self.get_notification(notification_id)

    def export_report(
        self,
        *,
        namespace: str | None,
        report_type: str,
        format: str = "markdown",
        output_path: str | None = None,
        filters: dict | None = None,
    ) -> ReportExport:
        if report_type not in REPORT_TYPES:
            raise ValidationError(f"Unknown report type: {report_type}")
        if format not in {"markdown", "json"}:
            raise ValidationError("Report format must be markdown or json.")
        report_id = new_id("rep")
        path = Path(output_path or f"{report_id}.{ 'md' if format == 'markdown' else 'json' }")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._report_payload(namespace=namespace, report_type=report_type, filters=filters or {})
        if format == "json":
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        else:
            path.write_text(self._report_markdown(payload), encoding="utf-8")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO report_exports (
                    id, namespace, report_type, format, file_path, created_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_id,
                    namespace,
                    report_type,
                    format,
                    str(path),
                    now,
                    json.dumps({"filters": filters or {}}, sort_keys=True),
                ),
            )
        return self.get_report(report_id)

    def get_report(self, report_id: str) -> ReportExport:
        row = self.store.connection.execute("SELECT * FROM report_exports WHERE id = ?", (report_id,)).fetchone()
        if not row:
            raise NotFoundError(f"Report export not found: {report_id}")
        return ReportExport.from_row(row)

    def list_reports(
        self,
        *,
        namespace: str | None = None,
        report_type: str | None = None,
        limit: int = 50,
    ) -> list[ReportExport]:
        params: list[object] = []
        clauses: list[str] = []
        if namespace is not None:
            clauses.append("namespace = ?")
            params.append(namespace)
        if report_type:
            clauses.append("report_type = ?")
            params.append(report_type)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(limit)
        rows = self.store.connection.execute(
            f"SELECT * FROM report_exports {where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [ReportExport.from_row(row) for row in rows]

    def read_rollback(self, rollback_id: str) -> RollbackRecord:
        row = self.store.connection.execute(
            "SELECT * FROM rollback_records WHERE id = ?",
            (rollback_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Rollback record not found: {rollback_id}")
        return RollbackRecord.from_row(row)

    def list_rollbacks(
        self,
        *,
        namespace: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        limit: int = 50,
    ) -> list[RollbackRecord]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if target_type:
            clause += " AND target_type = ?"
            params.append(target_type)
        if target_id:
            clause += " AND target_id = ?"
            params.append(target_id)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM rollback_records
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [RollbackRecord.from_row(row) for row in rows]

    def resolve_entity(
        self,
        namespace: str,
        *,
        mention: str,
        entity_type: str | None = None,
        create_if_missing: bool = True,
    ) -> Entity:
        self._require_text(namespace, "namespace")
        self._require_text(mention, "mention")
        entity_type = entity_type or self._infer_entity_type(mention)
        if entity_type not in ENTITY_TYPES:
            raise ValidationError(f"Unknown entity type: {entity_type}")
        with self.store.transaction():
            return self._resolve_entity_in_transaction(
                namespace=namespace,
                mention=mention,
                entity_type=entity_type,
                create_if_missing=create_if_missing,
            )

    def get_entity(self, entity_id: str) -> Entity:
        row = self.store.connection.execute(
            "SELECT * FROM entities WHERE id = ?",
            (entity_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Entity not found: {entity_id}")
        return Entity.from_row(row, self._aliases_for_entity(entity_id))

    def list_entities(
        self,
        *,
        namespace: str | None = None,
        entity_type: str | None = None,
        limit: int = 50,
    ) -> list[Entity]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if entity_type:
            clause += " AND entity_type = ?"
            params.append(entity_type)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM entities
            WHERE {clause}
            ORDER BY updated_at DESC, canonical_name ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [Entity.from_row(row, self._aliases_for_entity(row["id"])) for row in rows]

    def list_entity_mentions(
        self,
        *,
        namespace: str | None = None,
        entity_id: str | None = None,
        evidence_id: str | None = None,
    ) -> list[EntityMention]:
        params: list[object] = []
        clauses: list[str] = []
        if entity_id:
            clauses.append("entity_id = ?")
            params.append(entity_id)
        if evidence_id:
            clauses.append("evidence_id = ?")
            params.append(evidence_id)
        if not clauses:
            namespace = namespace or self.namespace
            clauses.append("namespace = ?")
            params.append(namespace)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM entity_mentions
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at ASC, id ASC
            """,
            params,
        ).fetchall()
        return [EntityMention.from_row(row) for row in rows]

    def merge_entities(
        self,
        namespace: str,
        *,
        source_entity_id: str,
        target_entity_id: str,
        reason: str,
    ) -> Entity:
        self._require_text(reason, "reason")
        source = self.get_entity(source_entity_id)
        target = self.get_entity(target_entity_id)
        if source.namespace != namespace or target.namespace != namespace:
            raise ValidationError("Merged entities must belong to the provided namespace.")
        if source.id == target.id:
            return target
        now = utc_now_iso()
        metadata = dict(source.metadata)
        metadata["merged_into"] = target.id
        metadata["merge_reason"] = reason
        with self.store.transaction():
            self.store.connection.execute(
                """
                UPDATE OR IGNORE entity_aliases
                SET entity_id = ?
                WHERE entity_id = ?
                """,
                (target.id, source.id),
            )
            for alias in set(source.aliases + [source.canonical_name]):
                alias_id = self._stable_id("alias", namespace, target.id, alias)
                self.store.connection.execute(
                    """
                    INSERT OR IGNORE INTO entity_aliases (
                        id, namespace, entity_id, alias, created_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (alias_id, namespace, target.id, alias, now),
                )
            self.store.connection.execute(
                "UPDATE entity_mentions SET entity_id = ? WHERE entity_id = ?",
                (target.id, source.id),
            )
            self.store.connection.execute(
                "UPDATE claim_entity_links SET entity_id = ? WHERE entity_id = ?",
                (target.id, source.id),
            )
            self.store.connection.execute(
                "UPDATE candidate_entity_links SET entity_id = ? WHERE entity_id = ?",
                (target.id, source.id),
            )
            self.store.connection.execute(
                """
                UPDATE entities
                SET metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(metadata, sort_keys=True), now, source.id),
            )
            self.store.connection.execute(
                "UPDATE entities SET updated_at = ? WHERE id = ?",
                (now, target.id),
            )
            self._write_audit(
                namespace=namespace,
                target_type="entity",
                target_id=target.id,
                action="entity.merge",
                details={"source_entity_id": source.id, "reason": reason},
            )
        return self.get_entity(target.id)

    def list_categories(self, *, namespace: str | None = None) -> list[dict[str, Any]]:
        params: list[object] = []
        where = ""
        if namespace is not None:
            where = "WHERE namespace = ? OR namespace IS NULL"
            params.append(namespace)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM category_registry
            {where}
            ORDER BY namespace IS NOT NULL, label ASC
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]

    def label_memory(
        self,
        target_id: str,
        *,
        target_type: str,
        labels: list[str],
        reason: str,
        confidence: float = 1.0,
    ) -> list[CategoryLabel]:
        self._require_text(target_id, "target_id")
        self._require_text(target_type, "target_type")
        self._require_text(reason, "reason")
        if not labels:
            raise ValidationError("At least one label is required.")
        namespace = self._namespace_for_target(target_id, target_type)
        with self.store.transaction():
            return [
                self._label_memory_in_transaction(
                    namespace=namespace,
                    target_id=target_id,
                    target_type=target_type,
                    label=label,
                    reason=reason,
                    confidence=confidence,
                )
                for label in labels
            ]

    def index_semantic(
        self,
        namespace: str,
        *,
        target_type: str = "claims",
        target_ids: list[str] | None = None,
        provider: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
        force: bool = False,
        resume: bool = True,
        protected_mode_policy: str | None = None,
        vector_store: str = "sqlite_local",
    ) -> SemanticIndexRun:
        if target_type not in SEMANTIC_TARGET_TYPES:
            raise ValidationError(f"Unknown semantic target type: {target_type}")
        if vector_store != "sqlite_local":
            raise ValidationError("Only sqlite_local vector_store is bundled in core.")
        engine = provider_for_name(provider, model=model, dimension=dimension)
        protected = self.protected_mode_status()
        semantic_policy = protected_mode_policy or protected.indexing_policy or "index_public_and_personal_only"
        index_version = semantic_index_version(provider=engine, redaction_policy=semantic_policy)
        targets = self._semantic_targets(
            namespace=namespace,
            target_type=target_type,
            target_ids=target_ids,
        )
        now = utc_now_iso()
        indexed: list[str] = []
        skipped = 0
        blocked = 0
        stale = 0
        warnings: list[str] = []
        store = SQLiteVectorStore(self.store.connection)
        with self.store.transaction():
            stale += self._mark_stale_semantic_versions(
                namespace=namespace,
                target_type=target_type,
                provider=engine.name,
                model=engine.model,
                index_version=index_version,
                reason="semantic.index_version.changed",
            )
            for target_id, text in targets:
                digest = content_hash(text)
                privacy_level = self._semantic_target_privacy_level(
                    target_id=target_id,
                    target_type=target_type,
                )
                allowed, indexed_text, blocked_reason = self._semantic_index_policy_decision(
                    text=text,
                    privacy_level=privacy_level,
                    provider_external=bool(getattr(engine, "external_network_access", False)),
                    protected_mode_policy=semantic_policy,
                )
                if not allowed:
                    blocked += 1
                    self._write_semantic_index_record(
                        namespace=namespace,
                        target_id=target_id,
                        target_type=target_type,
                        provider=engine.name,
                        model=engine.model,
                        dimension=engine.dimension,
                        provider_type=getattr(engine, "provider_type", "unknown"),
                        vector_store=vector_store,
                        index_version=index_version,
                        content_hash=digest,
                        status="blocked",
                        stale_reason=blocked_reason,
                        indexed_at=now,
                    )
                    continue
                input_digest = content_hash(indexed_text)
                existing = self.store.connection.execute(
                    """
                    SELECT 1
                    FROM embeddings
                    WHERE namespace = ?
                      AND target_id = ?
                      AND target_type = ?
                      AND provider = ?
                      AND model = ?
                      AND index_version = ?
                      AND input_hash = ?
                      AND COALESCE(status, 'indexed') = 'indexed'
                    LIMIT 1
                    """,
                    (
                        namespace,
                        target_id,
                        target_type,
                        engine.name,
                        engine.model,
                        index_version,
                        input_digest,
                    ),
                ).fetchone()
                if existing and resume and not force:
                    skipped += 1
                    self._write_semantic_index_record(
                        namespace=namespace,
                        target_id=target_id,
                        target_type=target_type,
                        provider=engine.name,
                        model=engine.model,
                        dimension=engine.dimension,
                        provider_type=getattr(engine, "provider_type", "unknown"),
                        vector_store=vector_store,
                        index_version=index_version,
                        content_hash=digest,
                        status="skipped",
                        stale_reason=None,
                        indexed_at=now,
                    )
                    continue
                embedding = embed_texts_with_metadata(
                    engine,
                    [indexed_text],
                    namespace=namespace,
                    privacy_level=privacy_level,
                    purpose="semantic_index",
                    metadata={"target_type": target_type, "target_id": target_id},
                )[0]
                store.upsert(
                    [
                        VectorRecord(
                            id=new_id("emb"),
                            namespace=namespace,
                            target_id=target_id,
                            target_type=target_type,
                            vector=embedding.vector,
                            provider=engine.name,
                            model=engine.model,
                            dimension=engine.dimension,
                            content_hash=digest,
                            input_hash=input_digest,
                            privacy_level=privacy_level,
                            index_version=index_version,
                            created_at=now,
                            metadata={
                                "text_hash": digest,
                                "input_hash": input_digest,
                                "provider_type": embedding.provider_type,
                                "provider_version": embedding.provider_version,
                                "privacy_level": privacy_level,
                                "protected_mode_policy": semantic_policy,
                                "redacted_input": indexed_text != text,
                                "chunk_id": "default",
                                "chunk_text_hash": input_digest,
                            },
                        )
                    ]
                )
                self._write_semantic_index_record(
                    namespace=namespace,
                    target_id=target_id,
                    target_type=target_type,
                    provider=engine.name,
                    model=engine.model,
                    dimension=engine.dimension,
                    provider_type=getattr(engine, "provider_type", "unknown"),
                    vector_store=vector_store,
                    index_version=index_version,
                    content_hash=digest,
                    status="indexed",
                    stale_reason=None,
                    indexed_at=now,
                )
                indexed.append(target_id)
            self._write_audit(
                namespace=namespace,
                target_type="semantic_index",
                target_id=f"{target_type}:{engine.name}",
                action="semantic.index",
                details={
                    "target_type": target_type,
                    "provider": engine.name,
                    "model": engine.model,
                    "provider_type": getattr(engine, "provider_type", "unknown"),
                    "vector_store": vector_store,
                    "index_version": index_version,
                    "indexed_count": len(indexed),
                    "skipped_count": skipped,
                    "blocked_count": blocked,
                    "stale_count": stale,
                },
            )
        if not targets:
            warnings.append("No eligible targets found for semantic indexing.")
        if blocked:
            warnings.append(f"{blocked} target(s) were blocked by semantic indexing policy.")
        if stale:
            warnings.append(f"{stale} stale vector record(s) were marked stale.")
        return SemanticIndexRun(
            namespace=namespace,
            target_type=target_type,
            provider=engine.name,
            model=engine.model,
            indexed_count=len(indexed),
            skipped_count=skipped,
            blocked_count=blocked,
            stale_count=stale,
            provider_type=getattr(engine, "provider_type", "unknown"),
            vector_store=vector_store,
            index_version=index_version,
            target_ids=indexed,
            created_at=now,
            warnings=warnings,
        )

    def write_claim(
        self,
        *,
        namespace: str | None = None,
        subject: str,
        predicate: str,
        object: str,
        memory_type: str,
        evidence_ids: list[str],
        confidence: float | None = None,
        status: str = "active",
        half_life_days: float | None = None,
        importance: float = 0.5,
        volatility: str = "medium",
        valid_from: str | None = None,
        valid_to: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
    ) -> Claim:
        namespace = namespace or self.namespace
        self._validate_claim_input(
            namespace=namespace,
            subject=subject,
            predicate=predicate,
            object=object,
            memory_type=memory_type,
            status=status,
        )
        if not evidence_ids:
            raise ValidationError("Claims must link to at least one evidence event.")
        for evidence_id in evidence_ids:
            event = self.read_event(evidence_id)
            if event.namespace != namespace:
                raise ValidationError(
                    f"Evidence {evidence_id} belongs to namespace {event.namespace!r}."
                )

        confidence_base = self._clamp(
            confidence
            if confidence is not None
            else float(self.config.get("default_confidence", 0.75))
        )
        half_life = half_life_days or DEFAULT_HALF_LIVES.get(memory_type, 180.0)
        now = utc_now_iso()
        claim_id = new_id("clm")
        effective = self.compute_effective_confidence(
            confidence_base=confidence_base,
            half_life_days=half_life,
            created_at=now,
            last_verified_at=None,
        )
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO claims (
                    id, namespace, subject, predicate, object, memory_type,
                    status, confidence_base, confidence_effective, half_life_days,
                    importance, volatility, created_at, last_verified_at,
                    last_accessed_at, valid_from, valid_to
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    namespace,
                    subject,
                    predicate,
                    object,
                    memory_type,
                    status,
                    confidence_base,
                    effective,
                    half_life,
                    importance,
                    volatility,
                    now,
                    None,
                    None,
                    valid_from,
                    valid_to,
                ),
            )
            for evidence_id in evidence_ids:
                self.store.connection.execute(
                    """
                    INSERT INTO claim_evidence_links (claim_id, evidence_id)
                    VALUES (?, ?)
                    """,
                    (claim_id, evidence_id),
                )
            inferred_project_id = project_id or self._infer_project_id(subject)
            if inferred_project_id:
                self._link_claim_to_project(
                    namespace=namespace,
                    project_id=inferred_project_id,
                    claim_id=claim_id,
                    relation="created_with_claim",
                )
            if session_id:
                self._link_claim_to_session(
                    session_id=session_id,
                    claim_id=claim_id,
                    relation="created_in_session",
                )
            self._index_claim(
                claim_id=claim_id,
                namespace=namespace,
                subject=subject,
                predicate=predicate,
                object=object,
                memory_type=memory_type,
            )
            self._write_audit(
                namespace=namespace,
                target_type="claim",
                target_id=claim_id,
                action="claim.write",
                details={
                    "subject": subject,
                    "predicate": predicate,
                    "object": object,
                    "memory_type": memory_type,
                    "status": status,
                },
            )
            self._write_status_history(
                namespace=namespace,
                claim_id=claim_id,
                old_status=None,
                new_status=status,
                reason="claim.write",
                actor="system",
            )
        claim = self.read_claim(claim_id)
        if status in ACTIVE_STATUSES:
            self.detect_conflicts(namespace=namespace, claim_id=claim_id)
            claim = self.read_claim(claim_id)
        self.recompute_confidence(claim_id=claim_id)
        return claim

    def read_claim(self, claim_id: str) -> Claim:
        row = self.store.connection.execute(
            "SELECT * FROM claims WHERE id = ?",
            (claim_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Claim not found: {claim_id}")
        return Claim.from_row(row, self._evidence_ids_for_claim(claim_id))

    def list_claims(
        self,
        *,
        namespace: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Claim]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if status:
            clause += " AND status = ?"
            params.append(status)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM claims
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [Claim.from_row(row, self._evidence_ids_for_claim(row["id"])) for row in rows]

    def remember(
        self,
        *,
        namespace: str | None = None,
        memory_type: str,
        subject: str,
        predicate: str,
        object: str,
        source_type: str = "manual",
        text: str | None = None,
        confidence: float | None = None,
        status: str = "active",
        importance: float = 0.5,
        half_life_days: float | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
    ) -> Claim:
        namespace = namespace or self.namespace
        event_text = text or claim_text(subject, predicate, object)
        event = self.write_event(
            namespace=namespace,
            source_type=source_type,
            content=event_text,
            trust_level="user_asserted" if source_type == "manual" else "unknown",
        )
        return self.write_claim(
            namespace=namespace,
            subject=subject,
            predicate=predicate,
            object=object,
            memory_type=memory_type,
            evidence_ids=[event.id],
            confidence=confidence,
            status=status,
            importance=importance,
            half_life_days=half_life_days,
            project_id=project_id,
            session_id=session_id,
        )

    def retrieve(
        self,
        namespace: str | None = None,
        query: str | None = None,
        *,
        mode: str = "lexical",
        filters: dict | None = None,
        limit: int = 10,
        memory_types: list[str] | None = None,
        statuses: list[str] | None = None,
        subject: str | None = None,
        predicate: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        min_confidence: float | None = None,
        categories: list[str] | None = None,
        semantic_provider: str | None = None,
        include_disputed: bool = False,
        include_archived: bool = False,
        include_candidates: bool = False,
        recompute_confidence: bool = False,
        record_access: bool = False,
    ) -> list[RetrievalResult]:
        namespace = namespace or self.namespace
        query = query or ""
        if mode not in {"lexical", "semantic", "hybrid"}:
            raise ValidationError("Retrieval mode must be lexical, semantic, or hybrid.")
        if recompute_confidence:
            self.recompute_confidence(namespace=namespace)
        merged_filters = dict(filters or {})
        if memory_types is not None:
            merged_filters["memory_types"] = memory_types
        if statuses is not None:
            merged_filters["statuses"] = statuses
        if subject is not None:
            merged_filters["subject"] = subject
        if predicate is not None:
            merged_filters["predicate"] = predicate
        if project_id is not None:
            merged_filters["project_id"] = project_id
        if session_id is not None:
            merged_filters["session_id"] = session_id
        if min_confidence is not None:
            merged_filters["min_confidence"] = min_confidence
        if categories is not None:
            merged_filters["categories"] = categories
        merged_filters["include_disputed"] = include_disputed
        merged_filters["include_archived"] = include_archived
        merged_filters["include_candidates"] = include_candidates
        if mode == "lexical":
            results = self.retriever.retrieve(
                namespace=namespace,
                query=query,
                filters=merged_filters,
                limit=limit,
            )
        else:
            results = self._retrieve_semantic_or_hybrid(
                namespace=namespace,
                query=query,
                mode=mode,
                filters=merged_filters,
                limit=limit,
                provider=semantic_provider,
            )
        results = self._filter_results_by_scope(
            results,
            query=query,
            project_id=project_id,
            session_id=session_id,
        )[:limit]
        if record_access:
            now = utc_now_iso()
            with self.store.transaction():
                for result in results:
                    self.store.connection.execute(
                        "UPDATE claims SET last_accessed_at = ? WHERE id = ?",
                        (now, result.claim_id),
                    )
                self._write_retrieval_log(
                    namespace=namespace,
                    query=query,
                    session_id=session_id,
                    project_id=project_id,
                    result_count=len(results),
                    metadata={
                        "mode": mode,
                        "memory_types": memory_types,
                        "statuses": statuses,
                        "subject": subject,
                        "predicate": predicate,
                        "min_confidence": min_confidence,
                        "categories": categories,
                        "semantic_provider": semantic_provider,
                        "include_candidates": include_candidates,
                    },
                )
        return results

    def context_pack(
        self,
        namespace: str | None = None,
        query: str | None = None,
        *,
        session_id: str | None = None,
        project_id: str | None = None,
        token_budget: int = 1500,
        include_sources: bool = True,
        include_confidence: bool = True,
        include_warnings: bool = True,
        retrieval_mode: str = "lexical",
        include_candidate_warnings: bool = False,
        include_reflections: bool = True,
        include_inferences: bool = False,
        include_derivation_metadata: bool = False,
        policy_version_id: str | None = None,
        record_usage: bool = False,
        explain_policy: bool = False,
    ) -> ContextPack:
        namespace = namespace or self.namespace
        query = query or ""
        context_pack_id = new_id("ctx")
        ranking_policy_version_id = policy_version_id or self._active_ranking_policy_version_id()
        context_policy_version_id = self._active_context_policy_version_id()
        results = self.retrieve(
            namespace=namespace,
            query=query,
            mode=retrieval_mode,
            limit=50,
            project_id=project_id,
            session_id=None,
            recompute_confidence=False,
        )
        ambient_results = self.retrieve(
            namespace=namespace,
            query="",
            mode=retrieval_mode,
            limit=20,
            memory_types=["preference", "identity", "procedure"],
            statuses=["core", "active"],
            min_confidence=0.70,
            project_id=project_id,
            recompute_confidence=False,
        )
        result_by_id = {result.claim_id: result for result in results}
        for result in ambient_results:
            result_by_id.setdefault(result.claim_id, result)
        results = sorted(
            result_by_id.values(),
            key=lambda result: (-result.score, result.claim_id),
        )
        if project_id:
            project_results = self.retrieve(
                namespace=namespace,
                query="",
                mode=retrieval_mode,
                limit=20,
                project_id=project_id,
                memory_types=["project", "project_state", "session_summary"],
                recompute_confidence=False,
            )
            result_by_id = {result.claim_id: result for result in results}
            for result in project_results:
                result_by_id.setdefault(result.claim_id, result)
            results = sorted(
                result_by_id.values(),
                key=lambda result: (-result.score, result.claim_id),
            )
        if session_id:
            session_results = self._session_continuity_results(
                namespace=namespace,
                session_id=session_id,
                project_id=project_id,
            )
            result_by_id = {result.claim_id: result for result in results}
            for result in session_results:
                result_by_id.setdefault(result.claim_id, result)
            results = sorted(
                result_by_id.values(),
                key=lambda result: (-result.score, result.claim_id),
            )

        core_memory: list[ContextItem] = []
        project_memory: list[ContextItem] = []
        session_memory: list[ContextItem] = []
        procedural_memory: list[ContextItem] = []
        reflection_memory: list[ContextItem] = []
        relevant_memory: list[ContextItem] = []
        warnings: list[ContextWarning] = []
        omitted: list[OmittedMemory] = []

        if include_warnings:
            warnings.extend(
                self._context_warnings(namespace=namespace, project_id=project_id)
            )
            if include_candidate_warnings:
                warnings.extend(
                    self._candidate_context_warnings(
                        namespace=namespace,
                        project_id=project_id,
                        query=query,
                    )
                )
            warnings.extend(
                self._derived_context_warnings(
                    namespace=namespace,
                    project_id=project_id,
                )
            )

        used_tokens = self._estimate_warning_tokens(warnings)
        if include_reflections:
            for reflection in self.list_reflections(
                namespace=namespace,
                status="active",
                project_id=project_id,
                limit=12,
            ):
                item = ContextItem(
                    text=reflection.text,
                    claim_id=reflection.id,
                    memory_type="reflection",
                    confidence_effective=reflection.confidence_effective,
                    status=reflection.status,
                    evidence_ids=reflection.source_evidence_ids if include_sources else [],
                    reason="active reflection",
                    source_kind="reflection",
                    reflection_id=reflection.id,
                    abstraction_level=reflection.abstraction_level,
                    is_reflected=True,
                    derivation=(
                        asdict(self.trace_derivation(reflection.id, target_type="reflection"))
                        if include_derivation_metadata
                        else None
                    ),
                )
                item_tokens = self._estimate_tokens(item.text)
                if used_tokens + item_tokens > token_budget:
                    omitted.append(
                        OmittedMemory(
                            claim_id=reflection.id,
                            reason="token_budget_exceeded",
                            score=reflection.retrieval_salience,
                        )
                    )
                    continue
                reflection_memory.append(item)
                used_tokens += item_tokens

        if include_inferences:
            for inference in self.list_inferences(
                namespace,
                status="validated",
                project_id=project_id,
                limit=10,
            ):
                item = ContextItem(
                    text=inference.text,
                    claim_id=inference.id,
                    memory_type="inference_candidate",
                    confidence_effective=inference.suggested_truth_confidence,
                    status=inference.status,
                    evidence_ids=inference.source_evidence_ids if include_sources else [],
                    reason="validated inference",
                    source_kind="inference",
                    inference_id=inference.id,
                    abstraction_level=inference.abstraction_level,
                    is_inferred=True,
                    derivation=(
                        asdict(self.trace_derivation(inference.id, target_type="inference"))
                        if include_derivation_metadata
                        else None
                    ),
                )
                item_tokens = self._estimate_tokens(item.text)
                if used_tokens + item_tokens > token_budget:
                    omitted.append(
                        OmittedMemory(
                            claim_id=inference.id,
                            reason="token_budget_exceeded",
                            score=inference.suggested_retrieval_salience,
                        )
                    )
                    continue
                relevant_memory.append(item)
                used_tokens += item_tokens

        for result in results:
            item = self._context_item(
                result,
                include_derivation_metadata=include_derivation_metadata,
            )
            section = relevant_memory
            reason = "relevant to query"
            if result.status == "core":
                section = core_memory
                reason = "core memory"
            elif result.memory_type == "session_summary":
                section = session_memory
                reason = "session continuity"
            elif project_id and project_id in result.project_ids:
                section = project_memory
                reason = "linked to project"
            elif result.memory_type in {"project", "project_state"}:
                section = project_memory
                reason = "project memory"
            elif result.memory_type == "procedure":
                section = procedural_memory
                reason = "procedural memory"
            item = ContextItem(
                text=item.text,
                claim_id=item.claim_id,
                memory_type=item.memory_type,
                confidence_effective=item.confidence_effective,
                status=item.status,
                evidence_ids=item.evidence_ids if include_sources else [],
                reason=reason,
                scope=item.scope,
                source_kind=item.source_kind,
                reflection_id=item.reflection_id,
                inference_id=item.inference_id,
                abstraction_level=item.abstraction_level,
                is_inferred=item.is_inferred,
                is_reflected=item.is_reflected,
                is_stale=item.is_stale,
                derivation=item.derivation,
            )
            item_tokens = self._estimate_tokens(item.text)
            if used_tokens + item_tokens > token_budget:
                omitted.append(
                    OmittedMemory(
                        claim_id=result.claim_id,
                        reason="token_budget_exceeded",
                        score=result.score,
                    )
                )
                continue
            section.append(item)
            used_tokens += item_tokens

        pack = ContextPack(
            namespace=namespace,
            query=query,
            session_id=session_id,
            project_id=project_id,
            token_budget=token_budget,
            generated_at=utc_now_iso(),
            id=context_pack_id,
            ranking_policy_version_id=ranking_policy_version_id,
            context_policy_version_id=context_policy_version_id,
            metadata={
                "retrieval_mode": retrieval_mode,
                "explain_policy": explain_policy,
                "included_item_ids": [item.claim_id for item in [
                    *core_memory,
                    *project_memory,
                    *session_memory,
                    *procedural_memory,
                    *reflection_memory,
                    *relevant_memory,
                ]],
                "omitted_item_ids": [item.claim_id for item in omitted],
            },
            core_memory=core_memory,
            project_memory=project_memory,
            session_memory=session_memory,
            procedural_memory=procedural_memory,
            reflection_memory=reflection_memory,
            relevant_memory=relevant_memory,
            warnings=warnings,
            omitted=omitted,
        )
        if record_usage:
            with self.store.transaction():
                self._write_context_pack_log(
                    context_pack_id=context_pack_id,
                    namespace=namespace,
                    query=query,
                    session_id=session_id,
                    project_id=project_id,
                    token_budget=token_budget,
                    item_count=len(pack.items()),
                    metadata={
                        "omitted_count": len(omitted),
                        "include_confidence": include_confidence,
                        "include_reflections": include_reflections,
                        "include_inferences": include_inferences,
                        "include_derivation_metadata": include_derivation_metadata,
                        "ranking_policy_version_id": ranking_policy_version_id,
                        "context_policy_version_id": context_policy_version_id,
                    },
                )
                self._record_context_usage_in_transaction(
                    namespace=namespace,
                    context_pack_id=context_pack_id,
                    query=query,
                    session_id=session_id,
                    project_id=project_id,
                    item_count=len(pack.items()),
                    token_estimate=used_tokens,
                    metadata=pack.metadata,
                )
                for index, item in enumerate(pack.items(), start=1):
                    target_type = "claim"
                    target_id = item.claim_id
                    if item.reflection_id:
                        target_type = "reflection"
                        target_id = item.reflection_id
                    elif item.inference_id:
                        target_type = "inference"
                        target_id = item.inference_id
                    self._record_usage_in_transaction(
                        namespace=namespace,
                        target_id=target_id,
                        target_type=target_type,
                        usage_type="included_in_context",
                        query=query,
                        session_id=session_id,
                        project_id=project_id,
                        context_pack_id=context_pack_id,
                        rank=index,
                        score=None,
                        metadata={"section": item.reason, "source_kind": item.source_kind},
                    )
        return pack

    def resolve_claim(
        self,
        *,
        namespace: str | None = None,
        subject: str,
        predicate: str,
    ) -> Claim | None:
        namespace = namespace or self.namespace
        self.recompute_confidence(namespace=namespace)
        row = self.store.connection.execute(
            """
            SELECT *
            FROM claims
            WHERE namespace = ?
              AND subject = ?
              AND predicate = ?
              AND status IN ('active', 'core')
            ORDER BY confidence_effective DESC, created_at DESC
            LIMIT 1
            """,
            (namespace, subject, predicate),
        ).fetchone()
        if not row:
            return None
        return Claim.from_row(row, self._evidence_ids_for_claim(row["id"]))

    def create_project(
        self,
        namespace: str,
        project_id: str,
        *,
        title: str,
        description: str | None = None,
        status: str = "active",
        metadata: dict | None = None,
    ) -> Project:
        self._require_text(namespace, "namespace")
        self._require_text(project_id, "project_id")
        self._require_text(title, "title")
        now = utc_now_iso()
        existing = self.store.connection.execute(
            "SELECT * FROM projects WHERE namespace = ? AND id = ?",
            (namespace, project_id),
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO projects (
                    id, namespace, title, description, status, created_at,
                    updated_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace, id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    project_id,
                    namespace,
                    title,
                    description,
                    status,
                    created_at,
                    now,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            self._write_audit(
                namespace=namespace,
                target_type="project",
                target_id=project_id,
                action="project.upsert",
                details={"title": title, "status": status},
            )
        # Make the project title retrievable as project memory.
        if not self.resolve_claim(
            namespace=namespace,
            subject=f"project:{project_id}",
            predicate="has_title",
        ):
            event = self.write_event(
                namespace=namespace,
                source_type="project",
                source_uri=f"project:{project_id}",
                content=f"Project {project_id} is titled {title}.",
                trust_level="tool_verified",
            )
            self.write_claim(
                namespace=namespace,
                subject=f"project:{project_id}",
                predicate="has_title",
                object=title,
                memory_type="project",
                evidence_ids=[event.id],
                confidence=0.95,
                status="active",
                project_id=project_id,
            )
        return self.get_project(namespace=namespace, project_id=project_id)

    def get_project(self, *, namespace: str, project_id: str) -> Project:
        row = self.store.connection.execute(
            "SELECT * FROM projects WHERE namespace = ? AND id = ?",
            (namespace, project_id),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Project not found: {namespace}/{project_id}")
        return Project.from_row(row)

    def list_projects(
        self, *, namespace: str | None = None, status: str | None = None
    ) -> list[Project]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if status:
            clause += " AND status = ?"
            params.append(status)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM projects
            WHERE {clause}
            ORDER BY updated_at DESC, id ASC
            """,
            params,
        ).fetchall()
        return [Project.from_row(row) for row in rows]

    def start_session(
        self,
        namespace: str,
        *,
        agent_id: str | None = None,
        project_id: str | None = None,
        title: str | None = None,
        metadata: dict | None = None,
    ) -> Session:
        self._require_text(namespace, "namespace")
        session_id = new_id("sess")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO sessions (
                    id, namespace, agent_id, project_id, title, started_at,
                    ended_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    session_id,
                    namespace,
                    agent_id,
                    project_id,
                    title,
                    now,
                    json.dumps(metadata or {}, sort_keys=True),
                ),
            )
            self._write_audit(
                namespace=namespace,
                target_type="session",
                target_id=session_id,
                action="session.start",
                details={"agent_id": agent_id, "project_id": project_id, "title": title},
            )
        return self.get_session(session_id)

    def end_session(
        self,
        session_id: str,
        *,
        summary: str | None = None,
        remember_summary: bool = True,
    ) -> Session:
        session = self.get_session(session_id)
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ?",
                (now, session_id),
            )
            self._write_audit(
                namespace=session.namespace,
                target_type="session",
                target_id=session_id,
                action="session.end",
                details={"summary": summary, "remember_summary": remember_summary},
            )
        if summary and remember_summary:
            event = self.write_event(
                namespace=session.namespace,
                session_id=session_id,
                source_type="session_summary",
                source_uri=f"session:{session_id}",
                content=summary,
                trust_level="tool_verified",
            )
            self.write_claim(
                namespace=session.namespace,
                subject=f"session:{session_id}",
                predicate="has_summary",
                object=summary,
                memory_type="session_summary",
                evidence_ids=[event.id],
                confidence=0.90,
                status="active",
                project_id=session.project_id,
                session_id=session_id,
            )
        return self.get_session(session_id)

    def get_session(self, session_id: str) -> Session:
        row = self.store.connection.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Session not found: {session_id}")
        return Session.from_row(row)

    def list_sessions(
        self,
        *,
        namespace: str | None = None,
        project_id: str | None = None,
        limit: int = 50,
    ) -> list[Session]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if project_id:
            clause += " AND project_id = ?"
            params.append(project_id)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM sessions
            WHERE {clause}
            ORDER BY started_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [Session.from_row(row) for row in rows]

    def promote_claim(
        self,
        claim_id: str,
        target_status: str | None = None,
        *,
        reason: str | None = None,
        force: bool = False,
    ) -> CurationDecision:
        if target_status is None:
            raise ValidationError("target_status is required.")
        if target_status not in PROMOTION_TARGETS:
            raise ValidationError(f"Promotion target must be one of {sorted(PROMOTION_TARGETS)}.")
        if not reason:
            raise ValidationError("Promotion requires a reason.")
        claim = self.read_claim(claim_id)
        snapshot = self.compute_confidence(claim_id, explain=True)
        failures = self._promotion_failures(claim, snapshot, target_status)
        if failures and not force:
            raise ValidationError("Cannot promote claim: " + "; ".join(failures))
        with self.store.transaction():
            self._set_claim_status(
                claim_id=claim_id,
                status=target_status,
                action="claim.promote.force" if force else "claim.promote",
                details={
                    "reason": reason,
                    "from": claim.status,
                    "to": target_status,
                    "force": force,
                    "overrides": failures,
                },
            )
        after = self.recompute_confidence(claim_id=claim_id)[0]
        return self._write_curation_decision(
            namespace=claim.namespace,
            claim_id=claim_id,
            decision_type=f"promote_to_{target_status}",
            target_status=target_status,
            reason=reason,
            confidence_before=snapshot.effective_confidence,
            confidence_after=after.effective_confidence,
            dry_run=False,
            applied=True,
            force=force,
            metadata={"overrides": failures, "old_status": claim.status},
        )

    def demote_claim(
        self,
        claim_id: str,
        target_status: str | None = None,
        *,
        reason: str | None = None,
    ) -> CurationDecision:
        if target_status is None:
            raise ValidationError("target_status is required.")
        if target_status not in DEMOTION_TARGETS:
            raise ValidationError(f"Demotion target must be one of {sorted(DEMOTION_TARGETS)}.")
        if not reason:
            raise ValidationError("Demotion requires a reason.")
        claim = self.read_claim(claim_id)
        before = self.compute_confidence(claim_id)
        with self.store.transaction():
            self._set_claim_status(
                claim_id=claim_id,
                status=target_status,
                action="claim.demote",
                details={"reason": reason, "from": claim.status, "to": target_status},
            )
        after = self.recompute_confidence(claim_id=claim_id)[0]
        return self._write_curation_decision(
            namespace=claim.namespace,
            claim_id=claim_id,
            decision_type=f"demote_to_{target_status}",
            target_status=target_status,
            reason=reason,
            confidence_before=before.effective_confidence,
            confidence_after=after.effective_confidence,
            dry_run=False,
            applied=True,
            force=False,
            metadata={"old_status": claim.status},
        )

    def feedback(
        self,
        target_id: str | None = None,
        *,
        target_type: str = "claim",
        signal: str,
        namespace: str | None = None,
        source: str = "user",
        note: str | None = None,
        evidence_id: str | None = None,
        strength: float = 1.0,
    ) -> FeedbackRecord:
        if target_id is None:
            raise ValidationError("target_id is required.")
        if signal not in FEEDBACK_SIGNALS:
            raise ValidationError(f"Unknown feedback signal: {signal}")
        namespace = namespace or self.namespace
        strength = max(0.0, min(float(strength), 1.0))
        if source == "assistant" and signal == "confirmed" and not evidence_id:
            strength = min(strength, 0.05)
            note = (note + " " if note else "") + "Assistant repetition downweighted by M2."
        if evidence_id:
            self.read_event(evidence_id)
        feedback_id = new_id("fbk")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO feedback (
                    id, namespace, target_type, target_id, signal, source, note,
                    evidence_id, strength, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    namespace,
                    target_type,
                    target_id,
                    signal,
                    source,
                    note,
                    evidence_id,
                    strength,
                    now,
                ),
            )
            if target_type == "claim":
                self._apply_feedback_to_claim(target_id, signal, source, evidence_id, strength)
            self._write_audit(
                namespace=namespace,
                target_type=target_type,
                target_id=target_id,
                action="feedback.write",
                details={
                    "signal": signal,
                    "source": source,
                    "note": note,
                    "evidence_id": evidence_id,
                    "strength": strength,
                },
            )
        if target_type == "claim":
            self.recompute_confidence(claim_id=target_id)
        row = self.store.connection.execute(
            "SELECT * FROM feedback WHERE id = ?",
            (feedback_id,),
        ).fetchone()
        return FeedbackRecord.from_row(row)

    def audit(self, target_id: str) -> dict[str, Any]:
        claim_row = self.store.connection.execute(
            "SELECT * FROM claims WHERE id = ?",
            (target_id,),
        ).fetchone()
        candidate_row = self.store.connection.execute(
            "SELECT * FROM candidate_claims WHERE id = ?",
            (target_id,),
        ).fetchone()
        evidence_row = self.store.connection.execute(
            "SELECT * FROM evidence_events WHERE id = ?",
            (target_id,),
        ).fetchone()
        target_type = (
            "claim"
            if claim_row
            else "candidate_claim"
            if candidate_row
            else "evidence"
            if evidence_row
            else None
        )
        if not target_type:
            raise NotFoundError(f"Audit target not found: {target_id}")
        audit_rows = self.store.connection.execute(
            """
            SELECT *
            FROM audit_log
            WHERE target_id = ?
            ORDER BY created_at ASC
            """,
            (target_id,),
        ).fetchall()
        result: dict[str, Any] = {
            "target_type": target_type,
            "target_id": target_id,
            "audit": [dict(row) for row in audit_rows],
        }
        if claim_row:
            claim = Claim.from_row(claim_row, self._evidence_ids_for_claim(target_id))
            result["claim"] = asdict(claim)
            result["evidence"] = [
                asdict(self.read_event(evidence_id)) for evidence_id in claim.evidence_ids
            ]
            result["conflicts"] = [
                asdict(conflict)
                for conflict in self.list_conflicts_for_claim(target_id)
            ]
        elif candidate_row:
            candidate = self.read_candidate(target_id)
            decision_rows = self.store.connection.execute(
                """
                SELECT *
                FROM extraction_decisions
                WHERE candidate_id = ?
                ORDER BY created_at ASC
                """,
                (target_id,),
            ).fetchall()
            link_rows = self.store.connection.execute(
                """
                SELECT claim_id, relation, created_at
                FROM candidate_claim_links
                WHERE candidate_id = ?
                ORDER BY created_at ASC
                """,
                (target_id,),
            ).fetchall()
            result["candidate"] = asdict(candidate)
            result["evidence"] = [
                asdict(self.read_event(evidence_id))
                for evidence_id in candidate.evidence_ids
            ]
            result["decisions"] = [dict(row) for row in decision_rows]
            result["claim_links"] = [dict(row) for row in link_rows]
        else:
            result["evidence"] = asdict(self.read_event(target_id))
        return result

    def compute_confidence(
        self,
        claim_id: str,
        *,
        at_time: datetime | str | None = None,
        explain: bool = False,
    ) -> ConfidenceSnapshot:
        claim = self.read_claim(claim_id)
        computed_at = self._coerce_time(at_time) or utc_now()
        half_life_days = self._half_life_for_claim(claim)
        start = parse_iso(claim.last_verified_at) or parse_iso(claim.created_at)
        age_days = max((computed_at - start).total_seconds() / 86400.0, 0.0) if start else 0.0
        decay_factor = 1.0 if half_life_days <= 0 else 2 ** (-age_days / half_life_days)
        source_reliability_factor = self._source_reliability_factor(claim)
        feedback_factor = self._feedback_factor(claim.id)
        contradiction_factor = self._contradiction_factor(claim)
        verification_factor = self._verification_factor(claim)
        effective = self._clamp(
            claim.confidence_base
            * decay_factor
            * source_reliability_factor
            * feedback_factor
            * contradiction_factor
            * verification_factor
        )
        retrieval_salience = self._retrieval_salience(
            claim=claim,
            age_days=age_days,
            usefulness_factor=self._usefulness_factor(claim.id),
        )
        explanation = None
        if explain:
            explanation = (
                f"Base confidence {claim.confidence_base:.2f}; "
                f"decay {decay_factor:.2f} over {age_days:.1f} days; "
                f"source reliability {source_reliability_factor:.2f}; "
                f"feedback {feedback_factor:.2f}; "
                f"contradiction {contradiction_factor:.2f}; "
                f"verification {verification_factor:.2f}; "
                f"final effective confidence {effective:.2f}; "
                f"retrieval salience {retrieval_salience:.2f}."
            )
        return ConfidenceSnapshot(
            claim_id=claim_id,
            truth_confidence=effective,
            retrieval_salience=retrieval_salience,
            base_confidence=claim.confidence_base,
            effective_confidence=effective,
            decay_factor=decay_factor,
            source_reliability_factor=source_reliability_factor,
            feedback_factor=feedback_factor,
            contradiction_factor=contradiction_factor,
            verification_factor=verification_factor,
            half_life_days=half_life_days,
            age_days=age_days,
            computed_at=computed_at.isoformat(),
            explanation=explanation,
        )

    def recompute_confidence(
        self,
        *,
        namespace: str | None = None,
        claim_id: str | None = None,
        memory_types: list[str] | None = None,
        persist: bool = True,
    ) -> list[ConfidenceSnapshot]:
        params: list[object] = []
        clauses: list[str] = []
        if claim_id:
            clauses.append("id = ?")
            params.append(claim_id)
        else:
            namespace = namespace or self.namespace
            clauses.append("namespace = ?")
            params.append(namespace)
        if memory_types:
            clauses.append(f"memory_type IN ({','.join('?' for _ in memory_types)})")
            params.extend(memory_types)
        rows = self.store.connection.execute(
            f"SELECT id, namespace, confidence_effective, importance FROM claims WHERE {' AND '.join(clauses)}",
            params,
        ).fetchall()
        snapshots: list[ConfidenceSnapshot] = []
        with self.store.transaction():
            for row in rows:
                old_truth = row["confidence_effective"]
                old_salience = row["importance"]
                snapshot = self.compute_confidence(row["id"], explain=False)
                snapshots.append(snapshot)
                if persist:
                    self._persist_confidence_snapshot(
                        namespace=row["namespace"],
                        snapshot=snapshot,
                        old_truth_confidence=old_truth,
                        old_retrieval_salience=old_salience,
                        event_type="confidence.recompute",
                        reason="M2 confidence recompute.",
                    )
        return snapshots

    def compute_effective_confidence(
        self,
        *,
        confidence_base: float,
        half_life_days: float,
        created_at: str,
        last_verified_at: str | None,
    ) -> float:
        start = parse_iso(last_verified_at) or parse_iso(created_at)
        if not start:
            return self._clamp(confidence_base)
        age_days = max((utc_now() - start).total_seconds() / 86400.0, 0.0)
        if half_life_days <= 0:
            return self._clamp(confidence_base)
        decay = 2 ** (-age_days / half_life_days)
        return self._clamp(confidence_base * decay)

    def detect_conflicts(
        self,
        *,
        namespace: str | None = None,
        subject: str | None = None,
        predicate: str | None = None,
        include_resolved: bool = False,
        create: bool = True,
        claim_id: str | None = None,
    ) -> list[ConflictFamily]:
        namespace = namespace or self.namespace
        if claim_id:
            claim = self.read_claim(claim_id)
            namespace = claim.namespace
            subject = claim.subject
            predicate = claim.predicate
        params: list[object] = [namespace]
        clauses = ["namespace = ?", "status IN ('active', 'core')"]
        if subject:
            clauses.append("subject = ?")
            params.append(subject)
        if predicate:
            clauses.append("predicate = ?")
            params.append(predicate)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM claims
            WHERE {' AND '.join(clauses)}
            ORDER BY subject, predicate, created_at
            """,
            params,
        ).fetchall()
        grouped: dict[tuple[str, str], list[Claim]] = {}
        for row in rows:
            claim = Claim.from_row(row, self._evidence_ids_for_claim(row["id"]))
            grouped.setdefault((claim.subject, claim.predicate), []).append(claim)
        families: list[ConflictFamily] = []
        for (claim_subject, claim_predicate), claims in grouped.items():
            by_object: dict[str, list[Claim]] = {}
            for claim in claims:
                by_object.setdefault(claim.object.strip().lower(), []).append(claim)
            if len(by_object) > 1:
                claim_ids = sorted(claim.id for claim in claims)
                if create:
                    conflict = self._create_or_update_conflict(
                        namespace=namespace,
                        subject=claim_subject,
                        predicate=claim_predicate,
                        claim_ids=claim_ids,
                        conflict_type=self._conflict_type_for_claims(claims),
                        mark_disputed=True,
                    )
                    families.append(self.read_conflict_family(conflict.id))
            for duplicates in by_object.values():
                if len(duplicates) > 1:
                    claim_ids = sorted(claim.id for claim in duplicates)
                    if create:
                        conflict = self._create_or_update_conflict(
                            namespace=namespace,
                            subject=claim_subject,
                            predicate=claim_predicate,
                            claim_ids=claim_ids,
                            conflict_type="duplicate_claim",
                            mark_disputed=False,
                        )
                        self._link_duplicate_claims(duplicates)
                        families.append(self.read_conflict_family(conflict.id))
        if not create:
            status = None if include_resolved else "unresolved"
            return self.list_conflict_families(namespace=namespace, status=status)
        existing_ids = {family.id for family in families}
        existing_status = None if include_resolved else "unresolved"
        for family in self.list_conflict_families(
            namespace=namespace,
            status=existing_status,
        ):
            if family.id not in existing_ids:
                families.append(family)
        return families

    def list_conflicts(
        self,
        *,
        namespace: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Conflict]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if status:
            clause += " AND status = ?"
            params.append(status)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM conflicts
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [
            Conflict.from_row(row, self._claim_ids_for_conflict(row["id"]))
            for row in rows
        ]

    def read_conflict(self, conflict_id: str) -> Conflict:
        row = self.store.connection.execute(
            "SELECT * FROM conflicts WHERE id = ?",
            (conflict_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Conflict not found: {conflict_id}")
        return Conflict.from_row(row, self._claim_ids_for_conflict(conflict_id))

    def list_conflicts_for_claim(self, claim_id: str) -> list[Conflict]:
        rows = self.store.connection.execute(
            """
            SELECT c.*
            FROM conflicts c
            JOIN conflict_claim_links l ON l.conflict_id = c.id
            WHERE l.claim_id = ?
            ORDER BY c.created_at DESC
            """,
            (claim_id,),
        ).fetchall()
        return [
            Conflict.from_row(row, self._claim_ids_for_conflict(row["id"]))
            for row in rows
        ]

    def read_conflict_family(self, conflict_id: str) -> ConflictFamily:
        row = self.store.connection.execute(
            "SELECT * FROM conflict_families WHERE id = ?",
            (conflict_id,),
        ).fetchone()
        if not row:
            conflict = self.read_conflict(conflict_id)
            return ConflictFamily(
                id=conflict.id,
                namespace=conflict.namespace,
                subject=conflict.subject,
                predicate=conflict.predicate,
                conflict_type="direct_value_conflict",
                status=conflict.status,
                active_claim_id=conflict.active_claim_id,
                resolution_strategy=None,
                resolution_note=conflict.resolution_note,
                created_at=conflict.created_at,
                updated_at=conflict.resolved_at or conflict.created_at,
                resolved_at=conflict.resolved_at,
                claim_ids=conflict.claim_ids,
            )
        return ConflictFamily.from_row(row, self._claim_ids_for_conflict_family(conflict_id))

    def list_conflict_families(
        self,
        *,
        namespace: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ConflictFamily]:
        namespace = namespace or self.namespace
        params: list[object] = [namespace]
        clause = "namespace = ?"
        if status:
            clause += " AND status = ?"
            params.append(status)
        params.append(limit)
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM conflict_families
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [
            ConflictFamily.from_row(row, self._claim_ids_for_conflict_family(row["id"]))
            for row in rows
        ]

    def resolve_conflict(
        self,
        conflict_id: str | None = None,
        *,
        strategy: str = "manual",
        active_claim_id: str | None = None,
        superseded_claim_ids: list[str] | None = None,
        rejected_claim_ids: list[str] | None = None,
        scoped_claims: list[dict] | None = None,
        note: str | None = None,
    ) -> ConflictResolution:
        if conflict_id is None:
            raise ValidationError("conflict_id is required.")
        if strategy not in RESOLUTION_STRATEGIES:
            raise ValidationError(f"Unknown conflict resolution strategy: {strategy}")
        note = note or f"Resolved with {strategy}."
        family = self.read_conflict_family(conflict_id)
        claim_ids = family.claim_ids
        if active_claim_id and active_claim_id not in claim_ids:
            raise ValidationError("Active claim must belong to the conflict.")
        selected_active = active_claim_id or self._select_active_claim_for_strategy(
            family,
            strategy,
        )
        if selected_active and selected_active not in claim_ids:
            raise ValidationError("Selected active claim must belong to the conflict.")
        superseded_claim_ids = list(superseded_claim_ids or [])
        rejected_claim_ids = list(rejected_claim_ids or [])
        scoped_claims = list(scoped_claims or [])
        if selected_active and not superseded_claim_ids and strategy not in {
            "context_scope",
            "time_scope",
            "mark_unresolved",
        }:
            superseded_claim_ids = [claim_id for claim_id in claim_ids if claim_id != selected_active]
        if strategy == "reject_weak_claims" and selected_active:
            rejected_claim_ids = [claim_id for claim_id in claim_ids if claim_id != selected_active]
            superseded_claim_ids = []
        family_status = {
            "context_scope": "context_scoped",
            "time_scope": "time_scoped",
            "mark_unresolved": "unresolved",
            "reject_weak_claims": "rejected",
            "merge_duplicates": "resolved",
        }.get(strategy, "resolved")
        resolution_id = new_id("res")
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO conflict_resolutions (
                    id, namespace, conflict_id, strategy, active_claim_id,
                    superseded_claim_ids_json, rejected_claim_ids_json,
                    scoped_claims_json, metadata_json, note, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolution_id,
                    family.namespace,
                    conflict_id,
                    strategy,
                    selected_active,
                    json.dumps(superseded_claim_ids, sort_keys=True),
                    json.dumps(rejected_claim_ids, sort_keys=True),
                    json.dumps(scoped_claims, sort_keys=True),
                    json.dumps(
                        {
                            "family_status": family_status,
                            "claim_ids": claim_ids,
                        },
                        sort_keys=True,
                    ),
                    note,
                    now,
                ),
            )
            resolved_at = None if family_status == "unresolved" else now
            self.store.connection.execute(
                """
                UPDATE conflict_families
                SET status = ?,
                    active_claim_id = ?,
                    resolution_id = ?,
                    resolution_strategy = ?,
                    resolution_note = ?,
                    updated_at = ?,
                    resolved_at = ?
                WHERE id = ?
                """,
                (
                    family_status,
                    selected_active,
                    resolution_id,
                    strategy,
                    note,
                    now,
                    resolved_at,
                    conflict_id,
                ),
            )
            self.store.connection.execute(
                """
                UPDATE conflicts
                SET status = ?,
                    active_claim_id = ?,
                    resolution_note = ?,
                    resolved_at = ?
                WHERE id = ?
                """,
                (
                    "unresolved" if family_status == "unresolved" else "resolved",
                    selected_active,
                    note,
                    resolved_at,
                    conflict_id,
                ),
            )
            if selected_active:
                self._set_claim_status(
                    claim_id=selected_active,
                    status="active",
                    action="conflict.resolve",
                    details={
                        "conflict_id": conflict_id,
                        "strategy": strategy,
                        "role": "active",
                        "note": note,
                    },
                )
            for claim_id in superseded_claim_ids:
                self._set_claim_status(
                    claim_id=claim_id,
                    status="superseded",
                    action="conflict.resolve",
                    details={
                        "conflict_id": conflict_id,
                        "strategy": strategy,
                        "role": "superseded",
                        "note": note,
                    },
                )
                if selected_active:
                    self._create_relationship(
                        source_claim_id=selected_active,
                        target_claim_id=claim_id,
                        relationship_type=(
                            "duplicate_of" if strategy == "merge_duplicates" else "supersedes"
                        ),
                        reason=note,
                    )
            for claim_id in rejected_claim_ids:
                self._set_claim_status(
                    claim_id=claim_id,
                    status="rejected",
                    action="conflict.resolve",
                    details={
                        "conflict_id": conflict_id,
                        "strategy": strategy,
                        "role": "rejected",
                        "note": note,
                    },
                )
            for scoped in scoped_claims:
                scoped_claim_id = scoped.get("claim_id")
                if scoped_claim_id not in claim_ids:
                    raise ValidationError("Scoped claim must belong to the conflict.")
                self._scope_claim_in_transaction(
                    claim_id=scoped_claim_id,
                    scope_type=scoped.get("scope_type", "contextual"),
                    applies_when=scoped.get("applies_when"),
                    valid_from=scoped.get("valid_from"),
                    valid_to=scoped.get("valid_to"),
                    reason=scoped.get("reason") or note,
                    activate=True,
                )
            self._write_audit(
                namespace=family.namespace,
                target_type="conflict",
                target_id=conflict_id,
                action="conflict.resolve",
                details={
                    "strategy": strategy,
                    "active_claim_id": selected_active,
                    "superseded_claim_ids": superseded_claim_ids,
                    "rejected_claim_ids": rejected_claim_ids,
                    "scoped_claims": scoped_claims,
                    "note": note,
                },
            )
        for linked_claim_id in claim_ids:
            self.recompute_confidence(claim_id=linked_claim_id)
        row = self.store.connection.execute(
            "SELECT * FROM conflict_resolutions WHERE id = ?",
            (resolution_id,),
        ).fetchone()
        return ConflictResolution.from_row(row)

    def set_half_life_policy(
        self,
        *,
        namespace: str | None = None,
        memory_type: str | None = None,
        predicate: str | None = None,
        half_life_days: float,
        reason: str,
    ) -> HalfLifePolicy:
        if half_life_days <= 0:
            raise ValidationError("half_life_days must be positive.")
        if not any([namespace, memory_type, predicate]):
            raise ValidationError("Policy must target a namespace, memory type, or predicate.")
        self._require_text(reason, "reason")
        now = utc_now_iso()
        row = self.store.connection.execute(
            """
            SELECT *
            FROM half_life_policies
            WHERE namespace IS ?
              AND memory_type IS ?
              AND predicate IS ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (namespace, memory_type, predicate),
        ).fetchone()
        policy_id = row["id"] if row else new_id("hlp")
        created_at = row["created_at"] if row else now
        with self.store.transaction():
            self.store.connection.execute(
                """
                INSERT INTO half_life_policies (
                    id, namespace, memory_type, predicate, half_life_days,
                    reason, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    half_life_days = excluded.half_life_days,
                    reason = excluded.reason,
                    updated_at = excluded.updated_at
                """,
                (
                    policy_id,
                    namespace,
                    memory_type,
                    predicate,
                    half_life_days,
                    reason,
                    created_at,
                    now,
                ),
            )
        return self.get_half_life_policy(policy_id)

    def list_half_life_policies(
        self,
        *,
        namespace: str | None = None,
        memory_type: str | None = None,
    ) -> list[HalfLifePolicy]:
        params: list[object] = []
        clauses: list[str] = []
        if namespace is not None:
            clauses.append("(namespace = ? OR namespace IS NULL)")
            params.append(namespace)
        if memory_type is not None:
            clauses.append("(memory_type = ? OR memory_type IS NULL)")
            params.append(memory_type)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM half_life_policies
            {where}
            ORDER BY namespace IS NULL, memory_type IS NULL, predicate IS NULL, updated_at DESC
            """,
            params,
        ).fetchall()
        return [HalfLifePolicy.from_row(row) for row in rows]

    def get_half_life_policy(self, policy_id: str) -> HalfLifePolicy:
        row = self.store.connection.execute(
            "SELECT * FROM half_life_policies WHERE id = ?",
            (policy_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Half-life policy not found: {policy_id}")
        return HalfLifePolicy.from_row(row)

    def supersede_claim(
        self,
        old_claim_id: str,
        new_claim_id: str,
        *,
        reason: str,
    ) -> ClaimRelationship:
        old_claim = self.read_claim(old_claim_id)
        new_claim = self.read_claim(new_claim_id)
        if old_claim.namespace != new_claim.namespace:
            raise ValidationError("Superseded claims must share a namespace.")
        self._require_text(reason, "reason")
        with self.store.transaction():
            relationship = self._create_relationship(
                source_claim_id=new_claim_id,
                target_claim_id=old_claim_id,
                relationship_type="supersedes",
                reason=reason,
            )
            self._set_claim_status(
                claim_id=old_claim_id,
                status="superseded",
                action="claim.supersede",
                details={"reason": reason, "new_claim_id": new_claim_id},
            )
            self._write_audit(
                namespace=new_claim.namespace,
                target_type="claim",
                target_id=new_claim_id,
                action="claim.supersede",
                details={"reason": reason, "old_claim_id": old_claim_id},
            )
        self.recompute_confidence(claim_id=old_claim_id)
        self.recompute_confidence(claim_id=new_claim_id)
        return relationship

    def scope_claim(
        self,
        claim_id: str,
        *,
        scope_type: str,
        applies_when: str | None = None,
        valid_from: datetime | str | None = None,
        valid_to: datetime | str | None = None,
        reason: str,
    ) -> ClaimScope:
        self.read_claim(claim_id)
        if scope_type not in SCOPE_TYPES:
            raise ValidationError(f"Unknown scope type: {scope_type}")
        self._require_text(reason, "reason")
        valid_from_text = self._time_arg_to_text(valid_from)
        valid_to_text = self._time_arg_to_text(valid_to)
        with self.store.transaction():
            scope = self._scope_claim_in_transaction(
                claim_id=claim_id,
                scope_type=scope_type,
                applies_when=applies_when,
                valid_from=valid_from_text,
                valid_to=valid_to_text,
                reason=reason,
                activate=True,
            )
        self.recompute_confidence(claim_id=claim_id)
        return scope

    def curate(
        self,
        *,
        namespace: str | None = None,
        dry_run: bool = True,
        memory_types: list[str] | None = None,
        max_decisions: int | None = None,
    ) -> list[CurationDecision]:
        namespace = namespace or self.namespace
        snapshots = self.recompute_confidence(
            namespace=namespace,
            memory_types=memory_types,
            persist=not dry_run,
        )
        snapshot_by_claim = {snapshot.claim_id: snapshot for snapshot in snapshots}
        claims = self.list_claims(namespace=namespace, limit=1000)
        if memory_types:
            claims = [claim for claim in claims if claim.memory_type in memory_types]
        decisions: list[CurationDecision] = []
        duplicate_families = [
            family
            for family in self.detect_conflicts(namespace=namespace, create=False, include_resolved=False)
            if family.conflict_type == "duplicate_claim"
        ]
        duplicate_claim_ids = {claim_id for family in duplicate_families for claim_id in family.claim_ids}
        for claim in sorted(claims, key=lambda item: item.id):
            snapshot = snapshot_by_claim.get(claim.id) or self.compute_confidence(claim.id)
            decision_type: str | None = None
            target_status: str | None = None
            reason: str | None = None
            if claim.id in duplicate_claim_ids:
                decision_type = "merge_duplicate"
                reason = "Duplicate claim family needs merge review."
            elif claim.status == "disputed":
                decision_type = "needs_review"
                reason = "Disputed claim needs manual resolution."
            elif claim.status == "candidate" and snapshot.effective_confidence >= 0.65 and claim.importance >= 0.30:
                decision_type = "promote_to_active"
                target_status = "active"
                reason = "Candidate meets active confidence and importance thresholds."
            elif claim.status == "active" and snapshot.effective_confidence >= 0.85 and claim.importance >= 0.70:
                decision_type = "promote_to_core"
                target_status = "core"
                reason = "Active claim meets conservative core thresholds."
            elif claim.status in {"active", "candidate"} and (
                snapshot.effective_confidence < 0.25 or snapshot.retrieval_salience < 0.05
            ):
                decision_type = "archive_stale"
                target_status = "archived"
                reason = "Claim has low confidence or retrieval salience."
            if not decision_type:
                continue
            if dry_run or not target_status:
                decision = self._write_curation_decision(
                    namespace=claim.namespace,
                    claim_id=claim.id,
                    decision_type=decision_type,
                    target_status=target_status,
                    reason=reason or decision_type,
                    confidence_before=snapshot.effective_confidence,
                    confidence_after=None,
                    dry_run=dry_run,
                    applied=False,
                    force=False,
                    metadata={},
                    persist=not dry_run,
                )
                decisions.append(decision)
            else:
                try:
                    if decision_type.startswith("promote"):
                        applied = self.promote_claim(
                            claim.id,
                            target_status,
                            reason=reason,
                            force=False,
                        )
                    else:
                        applied = self.demote_claim(claim.id, target_status, reason=reason)
                except ValidationError as exc:
                    decisions.append(
                        self._write_curation_decision(
                            namespace=claim.namespace,
                            claim_id=claim.id,
                            decision_type=decision_type,
                            target_status=target_status,
                            reason=reason or decision_type,
                            confidence_before=snapshot.effective_confidence,
                            confidence_after=None,
                            dry_run=False,
                            applied=False,
                            force=False,
                            metadata={"skipped_reason": str(exc)},
                            persist=True,
                        )
                    )
                else:
                    decisions.append(applied)
            if max_decisions and len(decisions) >= max_decisions:
                break
        return decisions

    def explain_claim(
        self,
        claim_id: str,
        *,
        include_evidence: bool = True,
        include_confidence: bool = True,
        include_conflicts: bool = True,
        include_history: bool = True,
    ) -> ClaimExplanation:
        claim = self.read_claim(claim_id)
        explanation = ClaimExplanation(claim_id=claim_id, claim=asdict(claim))
        evidence = []
        if include_evidence:
            evidence = [asdict(self.read_event(evidence_id)) for evidence_id in claim.evidence_ids]
        confidence = asdict(self.compute_confidence(claim_id, explain=True)) if include_confidence else None
        conflicts = []
        if include_conflicts:
            conflicts = [asdict(conflict) for conflict in self.list_conflicts_for_claim(claim_id)]
        relationships = [asdict(relationship) for relationship in self.list_claim_relationships(claim_id)]
        scopes = [asdict(scope) for scope in self.list_claim_scopes(claim_id)]
        history = self.claim_history(claim_id) if include_history else []
        audit_rows = self.audit(claim_id)["audit"] if include_history else []
        return ClaimExplanation(
            claim_id=claim_id,
            claim=asdict(claim),
            evidence=evidence,
            confidence=confidence,
            conflicts=conflicts,
            relationships=relationships,
            scopes=scopes,
            history=history,
            audit=audit_rows,
        )

    def claim_history(self, claim_id: str) -> list[dict[str, Any]]:
        self.read_claim(claim_id)
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM claim_status_history
            WHERE claim_id = ?
            ORDER BY created_at ASC
            """,
            (claim_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_claim_scopes(self, claim_id: str) -> list[ClaimScope]:
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM claim_scopes
            WHERE claim_id = ?
            ORDER BY created_at ASC
            """,
            (claim_id,),
        ).fetchall()
        return [ClaimScope.from_row(row) for row in rows]

    def list_claim_relationships(self, claim_id: str) -> list[ClaimRelationship]:
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM claim_relationships
            WHERE source_claim_id = ? OR target_claim_id = ?
            ORDER BY created_at ASC
            """,
            (claim_id, claim_id),
        ).fetchall()
        return [ClaimRelationship.from_row(row) for row in rows]

    def link_claim_to_project(
        self,
        *,
        namespace: str,
        project_id: str,
        claim_id: str,
        relation: str = "related",
    ) -> None:
        self.read_claim(claim_id)
        self.get_project(namespace=namespace, project_id=project_id)
        with self.store.transaction():
            self._link_claim_to_project(
                namespace=namespace,
                project_id=project_id,
                claim_id=claim_id,
                relation=relation,
            )
            self._write_audit(
                namespace=namespace,
                target_type="claim",
                target_id=claim_id,
                action="project.link_claim",
                details={"project_id": project_id, "relation": relation},
            )

    def _context_item(
        self,
        result: RetrievalResult,
        *,
        include_derivation_metadata: bool = False,
    ) -> ContextItem:
        inference_id = None
        if result.memory_type == "inference":
            row = self.store.connection.execute(
                """
                SELECT inference_id
                FROM derived_claim_links
                WHERE claim_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (result.claim_id,),
            ).fetchone()
            inference_id = row["inference_id"] if row else None
        return ContextItem(
            text=result.text,
            claim_id=result.claim_id,
            memory_type=result.memory_type,
            confidence_effective=result.confidence_effective,
            status=result.status,
            evidence_ids=result.evidence_ids,
            reason="relevant",
            scope=self._scope_label(result.claim_id),
            source_kind="inference" if result.memory_type == "inference" else "direct_claim",
            inference_id=inference_id,
            is_inferred=result.memory_type == "inference",
            derivation=(
                asdict(self.trace_derivation(result.claim_id, target_type="claim"))
                if include_derivation_metadata
                else None
            ),
        )

    def _context_warnings(
        self, *, namespace: str, project_id: str | None = None
    ) -> list[ContextWarning]:
        warnings: list[ContextWarning] = []
        for conflict in self.list_conflicts(namespace=namespace, status="unresolved"):
            claim_ids = conflict.claim_ids
            warnings.append(
                ContextWarning(
                    text=(
                        f"Unresolved memory conflict for "
                        f"{conflict.subject}.{conflict.predicate}; do not treat "
                        "those disputed memories as facts."
                    ),
                    warning_type="unresolved_conflict",
                    claim_ids=claim_ids,
                    conflict_ids=[conflict.id],
                )
            )
        return warnings

    def _derived_context_warnings(
        self,
        *,
        namespace: str,
        project_id: str | None = None,
    ) -> list[ContextWarning]:
        warnings: list[ContextWarning] = []
        reflections = [
            *self.list_reflections(namespace=namespace, status="stale", project_id=project_id),
            *self.list_reflections(namespace=namespace, status="invalidated", project_id=project_id),
        ]
        for reflection in reflections:
            warnings.append(
                ContextWarning(
                    text=(
                        f"Reflection {reflection.id} is {reflection.status}; "
                        "do not present it as fresh memory."
                    ),
                    warning_type=f"reflection_{reflection.status}",
                    claim_ids=reflection.source_claim_ids,
                )
            )
        stale_inference_rows = self.store.connection.execute(
            """
            SELECT id
            FROM inference_candidates
            WHERE namespace = ?
              AND status IN ('stale', 'invalidated')
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (namespace,),
        ).fetchall()
        for row in stale_inference_rows:
            warnings.append(
                ContextWarning(
                    text=(
                        f"Inference {row['id']} is stale or invalidated; "
                        "do not use it as current context."
                    ),
                    warning_type="inference_stale",
                    claim_ids=[],
                )
            )
        return warnings

    def _candidate_context_warnings(
        self,
        *,
        namespace: str,
        project_id: str | None,
        query: str,
    ) -> list[ContextWarning]:
        candidates = self.list_candidates(
            namespace,
            status="pending_review",
            project_id=project_id,
            limit=10,
        )
        query_terms = set(query.lower().split())
        warnings = []
        for candidate in candidates:
            text = claim_text(candidate.subject, candidate.predicate, candidate.object)
            if query_terms and not (query_terms & set(text.lower().split())):
                continue
            warnings.append(
                ContextWarning(
                    text=(
                        "Unreviewed candidate memory suggests: "
                        f"{text} It is not promoted and must not be treated as fact."
                    ),
                    warning_type="candidate_memory",
                    claim_ids=[],
                    conflict_ids=[],
                )
            )
        return warnings

    def _coerce_extraction_policy(
        self, value: str | dict | ExtractionPolicy | None
    ) -> ExtractionPolicy:
        if value is None:
            return ExtractionPolicy()
        if isinstance(value, ExtractionPolicy):
            return value
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, dict):
            raise ValidationError("extraction_policy must be a dict, JSON string, or ExtractionPolicy.")
        defaults = ExtractionPolicy()
        merged = defaults.to_dict()
        merged.update(value)
        return ExtractionPolicy(**merged)

    def _llm_run_dict(self, row) -> dict[str, Any]:
        result = dict(row)
        result["input_evidence_ids"] = json.loads(row["input_evidence_ids_json"] or "[]")
        result["warnings"] = json.loads(row["warnings_json"] or "[]")
        result["metadata"] = json.loads(row["metadata_json"] or "{}")
        return result

    def _llm_output_dict(self, row) -> dict[str, Any]:
        result = dict(row)
        result["metadata"] = json.loads(row["metadata_json"] or "{}")
        return result

    def _store_llm_invocation(
        self,
        *,
        namespace: str,
        invocation: LLMInvocation,
        related_run_id: str | None = None,
    ) -> str:
        now = utc_now_iso()
        prompt_id = invocation.prompt_template_id
        prompt_version_id = f"{prompt_id}.v{invocation.prompt_version}"
        self.store.connection.execute(
            """
            INSERT OR IGNORE INTO llm_prompts (
                id, name, purpose, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                prompt_id,
                prompt_id,
                invocation.task_type,
                now,
                json.dumps({"provider_type": invocation.provider_type}, sort_keys=True),
            ),
        )
        self.store.connection.execute(
            """
            INSERT OR IGNORE INTO llm_prompt_versions (
                id, prompt_id, version, schema_version, template_hash, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prompt_version_id,
                prompt_id,
                invocation.prompt_version,
                invocation.schema_version,
                llm_input_hash({"prompt": prompt_id, "version": invocation.prompt_version}),
                now,
                json.dumps({"metadata_only": True}, sort_keys=True),
            ),
        )
        run_id = new_id("llm")
        metadata = dict(invocation.metadata)
        if related_run_id:
            metadata["related_run_id"] = related_run_id
        self.store.connection.execute(
            """
            INSERT INTO llm_runs (
                id, namespace, task_type, provider, provider_type, model,
                prompt_template_id, prompt_version, temperature, schema_version,
                input_evidence_ids_json, input_hash, output_hash, status,
                warnings_json, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                namespace,
                invocation.task_type,
                invocation.provider,
                invocation.provider_type,
                invocation.model,
                invocation.prompt_template_id,
                invocation.prompt_version,
                invocation.temperature,
                invocation.schema_version,
                json.dumps(invocation.input_evidence_ids, sort_keys=True),
                invocation.input_hash,
                invocation.output_hash,
                invocation.status,
                json.dumps(invocation.warnings, sort_keys=True),
                now,
                json.dumps(metadata, sort_keys=True),
            ),
        )
        for warning in invocation.warnings:
            evidence_id = None
            match = re.search(r"Evidence ([A-Za-z0-9_]+)", warning)
            if match:
                evidence_id = match.group(1)
            self.store.connection.execute(
                """
                INSERT INTO llm_safety_flags (
                    id, llm_run_id, evidence_id, risk_type, severity,
                    note, created_at, metadata_json
                )
                VALUES (?, ?, ?, 'privacy_policy', 'high', ?, ?, ?)
                """,
                (
                    new_id("lsf"),
                    run_id,
                    evidence_id,
                    warning,
                    now,
                    json.dumps({"source": "m12_leak_check"}, sort_keys=True),
                ),
            )
        return run_id

    def _store_llm_output(
        self,
        *,
        llm_run_id: str,
        output_type: str,
        target_id: str | None,
        status: str,
        metadata: dict[str, Any],
    ) -> None:
        self.store.connection.execute(
            """
            INSERT INTO llm_outputs (
                id, llm_run_id, output_type, target_id, status,
                output_hash, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("llo"),
                llm_run_id,
                output_type,
                target_id,
                status,
                llm_output_hash(metadata),
                utc_now_iso(),
                json.dumps(self._llm_persisted_output_metadata(metadata), sort_keys=True),
            ),
        )

    def _store_llm_outputs_for_targets(self, *, llm_run_id: str, output_type: str, rows: list[Any]) -> None:
        for row in rows:
            metadata = json.loads(row["metadata_json"] or "{}")
            self._store_llm_output(
                llm_run_id=llm_run_id,
                output_type=output_type,
                target_id=row["id"],
                status=row["candidate_status"],
                metadata=metadata,
            )

    def _llm_allowed_evidence(
        self,
        *,
        namespace: str,
        evidence_ids: list[str],
        provider: str,
        model: str | None,
    ) -> list[EvidenceEvent]:
        if not evidence_ids:
            raise ValidationError("LLM source tasks require evidence_ids.")
        engine = llm_provider_for_name(provider, model=model)
        evidence = [self.read_event(evidence_id) for evidence_id in evidence_ids]
        warnings = []
        for event in evidence:
            if event.namespace != namespace:
                raise ValidationError("LLM source evidence must share namespace.")
            if event.privacy_level == "secret":
                warnings.append(f"Evidence {event.id} is secret and blocked for LLM task.")
            if event.privacy_level in {"private", "sensitive"} and getattr(engine, "external_network_access", False):
                warnings.append(f"Evidence {event.id} is {event.privacy_level} and blocked for external LLM task.")
        if warnings:
            invocation = LLMInvocation(
                task_type="safety_block",
                provider=engine.name,
                provider_type=getattr(engine, "provider_type", "unknown"),
                model=engine.model,
                prompt_template_id="m12.safety_block",
                prompt_version="1",
                temperature=0.0,
                schema_version="safety_block.v1",
                input_evidence_ids=[event.id for event in evidence],
                input_hash=llm_input_hash([asdict(event) for event in evidence]),
                status="unsafe",
                warnings=warnings,
            )
            with self.store.transaction():
                self._store_llm_invocation(namespace=namespace, invocation=invocation)
            raise ValidationError("; ".join(warnings))
        return evidence

    def _llm_source_task(
        self,
        *,
        namespace: str,
        task_type: str,
        prompt_template_id: str,
        provider: str,
        model: str | None,
        evidence: list[EvidenceEvent],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        engine = llm_provider_for_name(provider, model=model)
        evidence_payload = [asdict(event) for event in evidence]
        request_metadata = {"task_type": task_type, "namespace": namespace, "evidence": evidence_payload, **metadata}
        output = engine.complete_json(
            messages=[
                {"role": "system", "content": "Produce a governed draft only. Preserve source backlinks."},
                {"role": "user", "content": json.dumps(request_metadata, sort_keys=True)},
            ],
            schema={"type": "object"},
            temperature=0.0,
            max_tokens=1024,
            metadata=request_metadata,
        )
        invocation = LLMInvocation(
            task_type=task_type,
            provider=engine.name,
            provider_type=getattr(engine, "provider_type", "unknown"),
            model=engine.model,
            prompt_template_id=prompt_template_id,
            prompt_version="1",
            temperature=0.0,
            schema_version=f"{task_type}.v1",
            input_evidence_ids=[event.id for event in evidence],
            input_hash=llm_input_hash(request_metadata),
            output_hash=llm_output_hash(output),
            status="completed",
            output=output,
            metadata={"source_count": len(evidence)},
        )
        with self.store.transaction():
            run_id = self._store_llm_invocation(namespace=namespace, invocation=invocation)
            self._store_llm_output(llm_run_id=run_id, output_type=task_type, target_id=None, status="pending_review", metadata=output)
            self._write_audit(namespace=namespace, target_type="llm_run", target_id=run_id, action=f"llm.{task_type}", details={"evidence_ids": [event.id for event in evidence]})
        return {**output, "llm_run_id": run_id, "status": "pending_review"}

    def _llm_persisted_output_metadata(self, output: dict[str, Any]) -> dict[str, Any]:
        if os.environ.get("ALETHEIA_LLM_OUTPUT_STORAGE", "metadata_only").strip().lower() == "full":
            return {"storage_mode": "full", "output": output}
        summary: dict[str, Any] = {
            "storage_mode": "metadata_only",
            "output_hash": llm_output_hash(output),
            "output_keys": sorted(str(key) for key in output.keys()),
        }
        for key in [
            "review_state",
            "status",
            "candidate_id",
            "conflict_id",
            "source_evidence_ids",
            "source_claim_ids",
            "target_id",
            "merge_suggestion",
        ]:
            if key in output:
                summary[key] = output[key]
        return summary

    def _llm_merge_candidates(self, candidate: CandidateClaim) -> list[dict[str, Any]]:
        rows = self.store.connection.execute(
            """
            SELECT id, 'claim' AS target_type, subject, predicate, object, status
            FROM claims
            WHERE namespace = ?
              AND lower(subject) = lower(?)
              AND lower(predicate) = lower(?)
              AND status NOT IN ('rejected', 'archived', 'superseded')
            UNION ALL
            SELECT id, 'candidate_claim' AS target_type, subject, predicate, object, candidate_status AS status
            FROM candidate_claims
            WHERE namespace = ?
              AND id != ?
              AND lower(subject) = lower(?)
              AND lower(predicate) = lower(?)
              AND candidate_status NOT IN ('rejected', 'promoted', 'invalid')
            LIMIT 5
            """,
            (
                candidate.namespace,
                candidate.subject,
                candidate.predicate,
                candidate.namespace,
                candidate.id,
                candidate.subject,
                candidate.predicate,
            ),
        ).fetchall()
        return [dict(row) for row in rows]

    def _store_candidate_draft(
        self,
        *,
        namespace: str,
        run_id: str,
        draft,
        evidence_by_id: dict[str, EvidenceEvent],
    ) -> list[str]:
        status, warnings = self._validate_candidate_draft(draft, namespace, evidence_by_id)
        duplicate_risk = self._candidate_duplicate_risk(
            namespace=namespace,
            subject=draft.subject,
            predicate=draft.predicate,
            object=draft.object,
        )
        contradiction_risk = self._candidate_contradiction_risk(
            namespace=namespace,
            subject=draft.subject,
            predicate=draft.predicate,
            object=draft.object,
        )
        metadata = dict(draft.metadata)
        if duplicate_risk >= 0.95 and status == "pending_review":
            status = "duplicate"
        if contradiction_risk >= 0.85 and status == "pending_review":
            status = "needs_conflict_resolution"
        candidate_id = new_id("cand")
        now = utc_now_iso()
        self.store.connection.execute(
            """
            INSERT INTO candidate_claims (
                id, namespace, extraction_run_id, subject, predicate, object,
                memory_type, candidate_status, suggested_confidence,
                suggested_importance, suggested_half_life_days, suggested_scope_json,
                contradiction_risk, duplicate_risk, privacy_level, created_at,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                namespace,
                run_id,
                draft.subject,
                draft.predicate,
                draft.object,
                draft.memory_type,
                status,
                self._clamp(float(draft.suggested_confidence)),
                self._clamp(float(draft.suggested_importance)),
                draft.suggested_half_life_days,
                json.dumps(draft.suggested_scope, sort_keys=True)
                if draft.suggested_scope is not None
                else None,
                contradiction_risk,
                duplicate_risk,
                draft.privacy_level,
                now,
                json.dumps(metadata, sort_keys=True),
            ),
        )
        linked_evidence: set[str] = set()
        for span in draft.evidence_spans:
            if span.role not in EVIDENCE_SPAN_ROLES:
                continue
            span_id = self._store_evidence_span_in_transaction(namespace=namespace, span=span)
            self.store.connection.execute(
                """
                INSERT OR IGNORE INTO candidate_evidence_links (
                    candidate_id, evidence_id, evidence_span_id, role
                )
                VALUES (?, ?, ?, ?)
                """,
                (candidate_id, span.evidence_id, span_id, span.role),
            )
            linked_evidence.add(span.evidence_id)
        for label in draft.suggested_categories or [draft.memory_type]:
            self._label_memory_in_transaction(
                namespace=namespace,
                target_id=candidate_id,
                target_type="candidate_claim",
                label=label,
                reason="Candidate extraction suggested category.",
                confidence=0.80,
            )
        for mention in draft.suggested_entities:
            entity = self._resolve_entity_in_transaction(
                namespace=namespace,
                mention=mention,
                entity_type=self._infer_entity_type(mention),
                create_if_missing=True,
            )
            self.store.connection.execute(
                """
                INSERT OR IGNORE INTO candidate_entity_links (
                    candidate_id, entity_id, role, created_at
                )
                VALUES (?, ?, 'related', ?)
                """,
                (candidate_id, entity.id, now),
            )
            for evidence_id in linked_evidence:
                event = evidence_by_id[evidence_id]
                self._link_entity_mention_in_transaction(
                    namespace=namespace,
                    entity_id=entity.id,
                    evidence_id=evidence_id,
                    mention_text=mention,
                    content=event.content,
                    confidence=0.80,
                )
        self._write_audit(
            namespace=namespace,
            target_type="candidate_claim",
            target_id=candidate_id,
            action="candidate.extract",
            details={
                "extraction_run_id": run_id,
                "status": status,
                "duplicate_risk": duplicate_risk,
                "contradiction_risk": contradiction_risk,
            },
        )
        if metadata.get("risk_severity") in {"high", "critical"}:
            warnings.append(f"Candidate {candidate_id} includes high-risk imported instructions.")
        return warnings

    def _validate_candidate_draft(
        self,
        draft,
        namespace: str,
        evidence_by_id: dict[str, EvidenceEvent],
    ) -> tuple[str, list[str]]:
        warnings: list[str] = []
        for field_name in ["subject", "predicate", "object", "memory_type"]:
            if not isinstance(getattr(draft, field_name, None), str) or not getattr(draft, field_name).strip():
                return "invalid", [f"Candidate missing {field_name}."]
        if draft.memory_type not in CANDIDATE_MEMORY_TYPES:
            return "invalid", [f"Unknown memory type: {draft.memory_type}."]
        if not 0.0 <= float(draft.suggested_confidence) <= 1.0:
            return "invalid", ["Candidate confidence is outside 0..1."]
        if draft.privacy_level not in PRIVACY_LEVELS:
            return "invalid", ["Candidate privacy_level is invalid."]
        supporting = [span for span in draft.evidence_spans if span.role == "supporting"]
        if not supporting:
            return "needs_evidence", ["Candidate has no supporting evidence span."]
        for span in draft.evidence_spans:
            event = evidence_by_id.get(span.evidence_id)
            if not event:
                return "needs_evidence", [f"Evidence span references unknown event: {span.evidence_id}."]
            if event.namespace != namespace:
                return "invalid", ["Evidence span namespace mismatch."]
            if span.start_char < 0 or span.end_char <= span.start_char:
                return "invalid", ["Evidence span offsets are invalid."]
            if span.end_char > len(event.content):
                return "invalid", ["Evidence span exceeds evidence content length."]
            if event.content[span.start_char:span.end_char] != span.text:
                return "invalid", ["Evidence span text does not match evidence offsets."]
        return "pending_review", warnings

    def _store_evidence_span_in_transaction(
        self,
        *,
        namespace: str,
        span: EvidenceSpan,
    ) -> str:
        span_id = new_id("span")
        self.store.connection.execute(
            """
            INSERT INTO evidence_spans (
                id, namespace, evidence_id, start_char, end_char, span_text,
                role, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                span_id,
                namespace,
                span.evidence_id,
                span.start_char,
                span.end_char,
                span.text,
                span.role,
                utc_now_iso(),
            ),
        )
        return span_id

    def _candidate_duplicate_risk(
        self,
        *,
        namespace: str,
        subject: str,
        predicate: str,
        object: str,
    ) -> float:
        row = self.store.connection.execute(
            """
            SELECT 1
            FROM claims
            WHERE namespace = ?
              AND lower(subject) = lower(?)
              AND lower(predicate) = lower(?)
              AND lower(object) = lower(?)
              AND status NOT IN ('rejected', 'archived', 'superseded')
            LIMIT 1
            """,
            (namespace, subject, predicate, object),
        ).fetchone()
        if row:
            return 1.0
        row = self.store.connection.execute(
            """
            SELECT 1
            FROM candidate_claims
            WHERE namespace = ?
              AND lower(subject) = lower(?)
              AND lower(predicate) = lower(?)
              AND lower(object) = lower(?)
              AND candidate_status NOT IN ('rejected', 'promoted')
            LIMIT 1
            """,
            (namespace, subject, predicate, object),
        ).fetchone()
        return 0.95 if row else 0.0

    def _candidate_contradiction_risk(
        self,
        *,
        namespace: str,
        subject: str,
        predicate: str,
        object: str,
    ) -> float:
        row = self.store.connection.execute(
            """
            SELECT 1
            FROM claims
            WHERE namespace = ?
              AND lower(subject) = lower(?)
              AND lower(predicate) = lower(?)
              AND lower(object) <> lower(?)
              AND status IN ('active', 'core', 'disputed')
            LIMIT 1
            """,
            (namespace, subject, predicate, object),
        ).fetchone()
        return 0.90 if row else 0.0

    def _candidate_promotion_failures(
        self,
        candidate: CandidateClaim,
        target_status: str,
    ) -> list[str]:
        failures: list[str] = []
        if candidate.candidate_status in {"invalid", "rejected", "needs_evidence"}:
            failures.append(f"candidate status is {candidate.candidate_status}")
        if candidate.candidate_status == "duplicate" or candidate.duplicate_risk >= 0.95:
            failures.append("candidate is a duplicate without merge strategy")
        if candidate.contradiction_risk >= 0.85:
            failures.append("candidate has unresolved high contradiction risk")
        if not candidate.evidence_ids or not candidate.evidence_spans:
            failures.append("candidate has no evidence span")
        if not any(span.role == "supporting" for span in candidate.evidence_spans):
            failures.append("candidate has no supporting evidence span")
        if candidate.metadata.get("risk_severity") in {"high", "critical"} and not self._candidate_has_validation(candidate.id):
            failures.append("high-risk candidate requires explicit validation review")
        if target_status == "core":
            if candidate.suggested_confidence < 0.85:
                failures.append("candidate confidence is below core threshold")
            if candidate.suggested_importance < 0.70:
                failures.append("candidate importance is below core threshold")
            if candidate.memory_type in {"current_task", "task", "temporary_preference", "inference"}:
                failures.append("candidate memory type is not durable enough for core")
        return failures

    def _candidate_has_validation(self, candidate_id: str) -> bool:
        row = self.store.connection.execute(
            """
            SELECT 1
            FROM extraction_decisions
            WHERE candidate_id = ?
              AND decision = 'validate'
            LIMIT 1
            """,
            (candidate_id,),
        ).fetchone()
        return row is not None

    def _apply_candidate_edits(self, candidate_id: str, edits: dict) -> None:
        if not edits:
            return
        self.read_candidate(candidate_id)
        allowed = {
            "subject",
            "predicate",
            "object",
            "memory_type",
            "candidate_status",
            "suggested_confidence",
            "suggested_importance",
            "suggested_half_life_days",
            "suggested_scope",
            "privacy_level",
        }
        assignments: list[str] = []
        params: list[object] = []
        for key, value in edits.items():
            if key not in allowed:
                raise ValidationError(f"Unsupported candidate edit field: {key}")
            if key in {"subject", "predicate", "object"}:
                self._require_text(value, key)
            if key == "memory_type":
                self._require_text(value, key)
                if value not in CANDIDATE_MEMORY_TYPES:
                    raise ValidationError(f"Unknown candidate memory type: {value}")
            if key == "candidate_status":
                if not isinstance(value, str):
                    raise ValidationError("candidate_status must be a string.")
                if value not in CANDIDATE_STATUSES:
                    raise ValidationError(f"Unknown candidate status: {value}")
                if value not in CANDIDATE_EDITABLE_STATUSES:
                    raise ValidationError(
                        f"Candidate status {value!r} requires the dedicated review or promotion flow."
                    )
            if key in {"suggested_confidence", "suggested_importance"}:
                try:
                    value = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValidationError(f"{key} must be numeric.") from exc
                if not 0.0 <= value <= 1.0:
                    raise ValidationError(f"{key} must be between 0 and 1.")
            if key == "suggested_half_life_days" and value is not None:
                try:
                    value = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValidationError("suggested_half_life_days must be numeric.") from exc
                if value <= 0:
                    raise ValidationError("suggested_half_life_days must be positive.")
            if key == "suggested_scope" and value is not None and not isinstance(value, dict):
                raise ValidationError("suggested_scope must be an object.")
            if key == "privacy_level":
                if not isinstance(value, str):
                    raise ValidationError("privacy_level must be a string.")
                if value not in PRIVACY_LEVELS:
                    raise ValidationError(f"Unknown privacy level: {value}")
            column = "suggested_scope_json" if key == "suggested_scope" else key
            assignments.append(f"{column} = ?")
            if key == "suggested_scope":
                params.append(json.dumps(value, sort_keys=True) if value is not None else None)
            else:
                params.append(value)
        if assignments:
            params.append(candidate_id)
            self.store.connection.execute(
                f"UPDATE candidate_claims SET {', '.join(assignments)} WHERE id = ?",
                params,
            )

    def _write_extraction_decision_in_transaction(
        self,
        *,
        namespace: str,
        candidate_id: str,
        decision: str,
        reason: str,
        reviewer: str,
        edits: dict | None,
    ) -> None:
        self.store.connection.execute(
            """
            INSERT INTO extraction_decisions (
                id, namespace, candidate_id, decision, reason, reviewer,
                edits_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("xdec"),
                namespace,
                candidate_id,
                decision,
                reason,
                reviewer,
                json.dumps(edits, sort_keys=True) if edits is not None else None,
                utc_now_iso(),
            ),
        )

    def _evidence_trust_adjusted_confidence(self, evidence_ids: list[str]) -> float:
        if not evidence_ids:
            return 0.50
        factors = []
        for evidence_id in evidence_ids:
            event = self.read_event(evidence_id)
            factors.append(
                {
                    "tool_verified": 0.95,
                    "user_confirmed": 0.90,
                    "user_asserted": 0.85,
                    "external_verified": 0.90,
                    "imported": 0.70,
                    "model_generated": 0.55,
                    "unknown": 0.72,
                }.get(event.trust_level, 0.72)
            )
        return sum(factors) / len(factors)

    def _project_id_for_candidate(self, candidate: CandidateClaim) -> str | None:
        row = self.store.connection.execute(
            """
            SELECT ib.project_id
            FROM extraction_runs er
            JOIN ingestion_batches ib ON ib.id = er.batch_id
            WHERE er.id = ?
            """,
            (candidate.extraction_run_id,),
        ).fetchone()
        if row and row["project_id"]:
            return row["project_id"]
        scope = candidate.suggested_scope or {}
        if scope.get("type") == "project":
            return scope.get("applies_when")
        if candidate.subject.startswith("project:"):
            return candidate.subject.split(":", 1)[1]
        return None

    def _evidence_ids_for_batch(self, batch_id: str) -> list[str]:
        rows = self.store.connection.execute(
            """
            SELECT evidence_id
            FROM ingestion_batch_evidence_links
            WHERE batch_id = ?
            ORDER BY evidence_id
            """,
            (batch_id,),
        ).fetchall()
        return [row["evidence_id"] for row in rows]

    def _evidence_ids_for_extraction_run(self, run_id: str) -> list[str]:
        rows = self.store.connection.execute(
            """
            SELECT evidence_id
            FROM extraction_run_evidence_links
            WHERE extraction_run_id = ?
            ORDER BY evidence_id
            """,
            (run_id,),
        ).fetchall()
        return [row["evidence_id"] for row in rows]

    def _evidence_ids_for_candidate(self, candidate_id: str) -> list[str]:
        rows = self.store.connection.execute(
            """
            SELECT DISTINCT evidence_id
            FROM candidate_evidence_links
            WHERE candidate_id = ?
            ORDER BY evidence_id
            """,
            (candidate_id,),
        ).fetchall()
        return [row["evidence_id"] for row in rows]

    def _evidence_spans_for_candidate(self, candidate_id: str) -> list[EvidenceSpan]:
        rows = self.store.connection.execute(
            """
            SELECT es.*
            FROM candidate_evidence_links cel
            JOIN evidence_spans es ON es.id = cel.evidence_span_id
            WHERE cel.candidate_id = ?
            ORDER BY es.evidence_id, es.start_char, es.id
            """,
            (candidate_id,),
        ).fetchall()
        return [EvidenceSpan.from_row(row) for row in rows]

    def _labels_for_target(self, target_id: str, target_type: str) -> list[str]:
        rows = self.store.connection.execute(
            """
            SELECT label
            FROM memory_category_labels
            WHERE target_id = ?
              AND target_type = ?
            ORDER BY confidence DESC, label ASC
            """,
            (target_id, target_type),
        ).fetchall()
        return [row["label"] for row in rows]

    def _entity_ids_for_candidate(self, candidate_id: str) -> list[str]:
        rows = self.store.connection.execute(
            """
            SELECT entity_id
            FROM candidate_entity_links
            WHERE candidate_id = ?
            ORDER BY entity_id
            """,
            (candidate_id,),
        ).fetchall()
        return [row["entity_id"] for row in rows]

    def _aliases_for_entity(self, entity_id: str) -> list[str]:
        rows = self.store.connection.execute(
            """
            SELECT alias
            FROM entity_aliases
            WHERE entity_id = ?
            ORDER BY alias ASC
            """,
            (entity_id,),
        ).fetchall()
        return [row["alias"] for row in rows]

    def _resolve_entity_in_transaction(
        self,
        *,
        namespace: str,
        mention: str,
        entity_type: str,
        create_if_missing: bool,
    ) -> Entity:
        aliases = self._entity_aliases_for_mention(mention)
        placeholders = ",".join("?" for _ in aliases)
        row = self.store.connection.execute(
            f"""
            SELECT e.*
            FROM entity_aliases ea
            JOIN entities e ON e.id = ea.entity_id
            WHERE ea.namespace = ?
              AND lower(ea.alias) IN ({placeholders})
            ORDER BY e.updated_at DESC
            LIMIT 1
            """,
            [namespace, *[alias.lower() for alias in aliases]],
        ).fetchone()
        if row:
            return Entity.from_row(row, self._aliases_for_entity(row["id"]))
        row = self.store.connection.execute(
            """
            SELECT *
            FROM entities
            WHERE namespace = ?
              AND lower(canonical_name) = lower(?)
            LIMIT 1
            """,
            (namespace, self._canonical_entity_name(mention)),
        ).fetchone()
        if row:
            return Entity.from_row(row, self._aliases_for_entity(row["id"]))
        if not create_if_missing:
            raise NotFoundError(f"Entity not found for mention: {mention}")
        now = utc_now_iso()
        entity_id = self._stable_id("ent", namespace, entity_type, self._canonical_entity_name(mention))
        self.store.connection.execute(
            """
            INSERT OR IGNORE INTO entities (
                id, namespace, canonical_name, entity_type, created_at,
                updated_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                namespace,
                self._canonical_entity_name(mention),
                entity_type,
                now,
                now,
                json.dumps({"created_by": "m3_entity_resolution"}, sort_keys=True),
            ),
        )
        for alias in aliases:
            self.store.connection.execute(
                """
                INSERT OR IGNORE INTO entity_aliases (
                    id, namespace, entity_id, alias, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (self._stable_id("alias", namespace, entity_id, alias), namespace, entity_id, alias, now),
            )
        self._write_audit(
            namespace=namespace,
            target_type="entity",
            target_id=entity_id,
            action="entity.resolve",
            details={"mention": mention, "entity_type": entity_type},
        )
        return self.get_entity(entity_id)

    def _link_entity_mention_in_transaction(
        self,
        *,
        namespace: str,
        entity_id: str,
        evidence_id: str,
        mention_text: str,
        content: str,
        confidence: float,
    ) -> None:
        match = re.search(re.escape(mention_text), content, re.I)
        start = match.start() if match else None
        end = match.end() if match else None
        self.store.connection.execute(
            """
            INSERT INTO entity_mentions (
                id, namespace, entity_id, evidence_id, mention_text,
                start_char, end_char, confidence, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("ment"),
                namespace,
                entity_id,
                evidence_id,
                mention_text,
                start,
                end,
                confidence,
                utc_now_iso(),
            ),
        )

    def _canonical_entity_name(self, mention: str) -> str:
        normalized = " ".join(mention.strip().split())
        if normalized.lower() in {"aletheia", "aletheia memory", "aletheia memory library"}:
            return "Aletheia Memory Library"
        if normalized.lower() == "user":
            return "user"
        return normalized

    def _entity_aliases_for_mention(self, mention: str) -> list[str]:
        canonical = self._canonical_entity_name(mention)
        aliases = {mention.strip(), canonical}
        if canonical == "Aletheia Memory Library":
            aliases.update({"Aletheia", "Aletheia Memory", "Aletheia Memory Library"})
        return sorted(alias for alias in aliases if alias)

    def _infer_entity_type(self, mention: str) -> str:
        lower = mention.lower().strip()
        if lower == "user":
            return "user"
        if lower.startswith("project:"):
            return "project"
        if lower in {"aletheia", "aletheia memory", "aletheia memory library"}:
            return "memory_system"
        if re.fullmatch(r"m\d+", lower):
            return "event"
        return "unknown"

    def _namespace_for_target(self, target_id: str, target_type: str) -> str:
        if target_type == "claim":
            return self.read_claim(target_id).namespace
        if target_type == "candidate_claim":
            return self.read_candidate(target_id).namespace
        if target_type == "evidence_event":
            return self.read_event(target_id).namespace
        if target_type == "entity":
            return self.get_entity(target_id).namespace
        table_by_type = {
            "source_document": "source_documents",
            "project": "projects",
            "session": "sessions",
        }
        table = table_by_type.get(target_type)
        if not table:
            raise ValidationError(f"Unsupported label target type: {target_type}")
        row = self.store.connection.execute(
            f"SELECT namespace FROM {table} WHERE id = ?",
            (target_id,),
        ).fetchone()
        if not row:
            raise NotFoundError(f"Target not found: {target_type} {target_id}")
        return row["namespace"]

    def _label_memory_in_transaction(
        self,
        *,
        namespace: str,
        target_id: str,
        target_type: str,
        label: str,
        reason: str,
        confidence: float,
    ) -> CategoryLabel:
        self._ensure_category_in_transaction(label)
        label_id = new_id("lbl")
        now = utc_now_iso()
        self.store.connection.execute(
            """
            INSERT INTO memory_category_labels (
                id, namespace, target_id, target_type, label, confidence,
                reason, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                label_id,
                namespace,
                target_id,
                target_type,
                label,
                self._clamp(confidence),
                reason,
                now,
            ),
        )
        self._write_audit(
            namespace=namespace,
            target_type=target_type,
            target_id=target_id,
            action="category.label",
            details={"label": label, "confidence": confidence, "reason": reason},
        )
        row = self.store.connection.execute(
            "SELECT * FROM memory_category_labels WHERE id = ?",
            (label_id,),
        ).fetchone()
        return CategoryLabel.from_row(row)

    def _ensure_category_in_transaction(self, label: str) -> None:
        if not label:
            raise ValidationError("Category label cannot be empty.")
        now = utc_now_iso()
        self.store.connection.execute(
            """
            INSERT OR IGNORE INTO category_registry (
                id, namespace, label, parent_label, description, created_at
            )
            VALUES (?, NULL, ?, ?, ?, ?)
            """,
            (
                self._stable_id("cat", "default", label),
                label,
                label.rsplit(".", 1)[0] if "." in label else None,
                f"M3 category: {label}.",
                now,
            ),
        )

    def _target_has_any_label(
        self,
        target_id: str,
        target_type: str,
        labels: list[str],
    ) -> bool:
        if not labels:
            return True
        row = self.store.connection.execute(
            f"""
            SELECT 1
            FROM memory_category_labels
            WHERE target_id = ?
              AND target_type = ?
              AND label IN ({','.join('?' for _ in labels)})
            LIMIT 1
            """,
            [target_id, target_type, *labels],
        ).fetchone()
        return row is not None

    def _flag_content_risks(
        self,
        *,
        namespace: str,
        evidence_id: str,
        content: str,
    ) -> None:
        for risk_type, severity, pattern in RISK_PATTERNS:
            for match in re.finditer(pattern, content, re.I):
                existing = self.store.connection.execute(
                    """
                    SELECT 1
                    FROM content_risk_flags
                    WHERE evidence_id = ?
                      AND risk_type = ?
                      AND start_char = ?
                      AND end_char = ?
                    LIMIT 1
                    """,
                    (evidence_id, risk_type, match.start(), match.end()),
                ).fetchone()
                if existing:
                    continue
                flag_id = new_id("risk")
                self.store.connection.execute(
                    """
                    INSERT INTO content_risk_flags (
                        id, namespace, evidence_id, risk_type, severity,
                        span_text, start_char, end_char, note, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        flag_id,
                        namespace,
                        evidence_id,
                        risk_type,
                        severity,
                        content[match.start():match.end()],
                        match.start(),
                        match.end(),
                        "Imported content treated as untrusted evidence.",
                        utc_now_iso(),
                    ),
                )
                self._write_audit(
                    namespace=namespace,
                    target_type="evidence",
                    target_id=evidence_id,
                    action="risk.flag",
                    details={"risk_type": risk_type, "severity": severity, "flag_id": flag_id},
                )

    def _stable_id(self, prefix: str, *parts: str) -> str:
        digest = content_hash("\0".join(str(part) for part in parts))[:24]
        return f"{prefix}_{digest}"

    def _normalize_inference_engines(self, engines: list[str] | None) -> list[str]:
        if not engines or "all" in engines:
            return ["logical", "semantic", "factual", "reflection"]
        normalized = []
        for engine in engines:
            if engine not in INFERENCE_ENGINES:
                raise ValidationError(f"Unknown inference engine: {engine}")
            if engine not in normalized:
                normalized.append(engine)
        return normalized

    def _rule_id_for_engine(self, engine: str) -> str:
        return {
            "logical": "rule_m4_superseded_not_current",
            "semantic": "rule_m4_semantic_relation",
            "factual": "rule_m4_project_focus_factual",
            "reflection": "rule_m4_reflection_suggestion",
        }.get(engine, f"rule_m4_{engine}")

    def _generate_inference_drafts(
        self,
        *,
        namespace: str,
        engines: list[str],
        project_id: str | None,
        session_id: str | None,
        target_claim_ids: list[str],
        target_evidence_ids: list[str],
        target_entity_ids: list[str],
        rule_ids: list[str],
        policy: dict,
    ) -> list[dict[str, Any]]:
        claims = self._eligible_claims_for_inference(
            namespace=namespace,
            project_id=project_id,
            session_id=session_id,
            target_claim_ids=target_claim_ids,
        )
        drafts: list[dict[str, Any]] = []
        if "logical" in engines:
            drafts.extend(self._logical_inference_drafts(claims, policy=policy))
        if "factual" in engines:
            drafts.extend(self._factual_inference_drafts(claims, project_id=project_id))
        if "reflection" in engines:
            drafts.extend(self._reflection_inference_drafts(claims))
        if rule_ids:
            allowed_rules = set(rule_ids)
            drafts = [
                draft
                for draft in drafts
                if draft.get("rule_id") in allowed_rules
                or draft.get("engine") in {self.get_rule(rule_id).rule_type for rule_id in rule_ids if self._rule_exists(rule_id)}
            ]
        return self._dedupe_inference_drafts(drafts)

    def _eligible_claims_for_inference(
        self,
        *,
        namespace: str,
        project_id: str | None,
        session_id: str | None,
        target_claim_ids: list[str],
    ) -> list[Claim]:
        if target_claim_ids:
            claims = [self.read_claim(claim_id) for claim_id in target_claim_ids]
            return [claim for claim in claims if claim.namespace == namespace]
        rows = self._governed_claim_rows(
            namespace=namespace,
            filters={
                "project_id": project_id,
                "session_id": session_id,
                "include_disputed": True,
                "include_archived": False,
            },
        )
        return [Claim.from_row(row, self._evidence_ids_for_claim(row["id"])) for row in rows]

    def _logical_inference_drafts(self, claims: list[Claim], *, policy: dict) -> list[dict[str, Any]]:
        drafts: list[dict[str, Any]] = []
        query_context = str(policy.get("query_context") or "")
        for claim in claims:
            if claim.status in {"active", "core"} and not self._has_unresolved_conflicts(claim.id):
                if not claim.valid_to or not (parse_iso(claim.valid_to) and parse_iso(claim.valid_to) < utc_now()):
                    drafts.append(
                        self._inference_draft(
                            namespace=claim.namespace,
                            engine="logical",
                            inference_type="logical",
                            text=f"Claim {claim.id} is current.",
                            subject=claim.id,
                            predicate="is_current",
                            object="true",
                            source_claim_ids=[claim.id],
                            source_evidence_ids=claim.evidence_ids,
                            rule_id="rule_m4_superseded_not_current",
                            strength="entailed",
                            confidence=self.compute_confidence(claim.id).effective_confidence,
                        )
                    )
            if claim.valid_to and (parse_iso(claim.valid_to) and parse_iso(claim.valid_to) < utc_now()):
                drafts.append(
                    self._inference_draft(
                        namespace=claim.namespace,
                        engine="logical",
                        inference_type="temporal_currentness",
                        text=f"Claim {claim.id} is not current because it expired.",
                        subject=claim.id,
                        predicate="is_current",
                        object="false",
                        source_claim_ids=[claim.id],
                        source_evidence_ids=claim.evidence_ids,
                        rule_id="rule_m4_expired_not_current",
                        strength="entailed",
                        confidence=0.95,
                    )
                )
            for scope in self.list_claim_scopes(claim.id):
                if scope.scope_type == "contextual" and query_context and self._scope_matches_text(scope.applies_when, query_context):
                    drafts.append(
                        self._inference_draft(
                            namespace=claim.namespace,
                            engine="logical",
                            inference_type="scope_match",
                            text=f"Claim {claim.id} applies to context {scope.applies_when}.",
                            subject=claim.id,
                            predicate="applies_to_context",
                            object=scope.applies_when or "context",
                            source_claim_ids=[claim.id],
                            source_evidence_ids=claim.evidence_ids,
                            rule_id="rule_m4_scoped_claim_matches_context",
                            strength="strong",
                            confidence=0.88,
                        )
                    )
        relationship_rows = self.store.connection.execute(
            """
            SELECT *
            FROM claim_relationships
            WHERE relationship_type = 'supersedes'
            """
        ).fetchall()
        claim_ids = {claim.id for claim in claims}
        for row in relationship_rows:
            if row["source_claim_id"] in claim_ids or row["target_claim_id"] in claim_ids:
                source = self.read_claim(row["source_claim_id"])
                target = self.read_claim(row["target_claim_id"])
                drafts.append(
                    self._inference_draft(
                        namespace=target.namespace,
                        engine="logical",
                        inference_type="temporal_currentness",
                        text=f"Claim {target.id} is not current because {source.id} supersedes it.",
                        subject=target.id,
                        predicate="is_current",
                        object="false",
                        source_claim_ids=[source.id, target.id],
                        source_evidence_ids=sorted(set(source.evidence_ids + target.evidence_ids)),
                        rule_id="rule_m4_superseded_not_current",
                        strength="entailed",
                        confidence=0.95,
                    )
                )
        for family in self.list_conflict_families(namespace=claims[0].namespace if claims else self.namespace):
            if family.status == "resolved" and family.active_claim_id:
                active = self.read_claim(family.active_claim_id)
                drafts.append(
                    self._inference_draft(
                        namespace=family.namespace,
                        engine="logical",
                        inference_type="logical",
                        text=f"Claim {active.id} is active for resolved conflict {family.id}.",
                        subject=active.id,
                        predicate="active_for_conflict",
                        object=family.id,
                        source_claim_ids=[active.id],
                        source_evidence_ids=active.evidence_ids,
                        rule_id="rule_m4_resolved_conflict_active",
                        strength="entailed",
                        confidence=0.90,
                    )
                )
            if family.status == "unresolved":
                for claim_id in family.claim_ids:
                    claim = self.read_claim(claim_id)
                    drafts.append(
                        self._inference_draft(
                            namespace=family.namespace,
                            engine="logical",
                            inference_type="logical",
                            text=f"Claim {claim.id} requires a context warning because conflict {family.id} is unresolved.",
                            subject=claim.id,
                            predicate="requires_context_warning",
                            object=family.id,
                            source_claim_ids=[claim.id],
                            source_evidence_ids=claim.evidence_ids,
                            rule_id="rule_m4_unresolved_conflict_warning",
                            strength="entailed",
                            confidence=0.85,
                        )
                    )
        return drafts

    def _factual_inference_drafts(self, claims: list[Claim], *, project_id: str | None) -> list[dict[str, Any]]:
        drafts: list[dict[str, Any]] = []
        for milestone in [claim for claim in claims if claim.predicate in {"current_milestone", "has_current_milestone"}]:
            name_claims = [
                claim
                for claim in claims
                if claim.subject.lower() in {milestone.object.lower(), f"milestone:{milestone.object.lower()}"}
                and claim.predicate in {"short_name", "has_name", "name"}
            ]
            for name_claim in name_claims:
                confidence = min(
                    self.compute_confidence(milestone.id).effective_confidence,
                    self.compute_confidence(name_claim.id).effective_confidence,
                    0.82,
                )
                drafts.append(
                    self._inference_draft(
                        namespace=milestone.namespace,
                        engine="factual",
                        inference_type="factual",
                        text=f"Project Aletheia is currently focused on {name_claim.object}.",
                        subject=milestone.subject if milestone.subject.startswith("project:") else f"project:{project_id or 'aletheia'}",
                        predicate="currently_focused_on",
                        object=name_claim.object,
                        source_claim_ids=[milestone.id, name_claim.id],
                        source_evidence_ids=sorted(set(milestone.evidence_ids + name_claim.evidence_ids)),
                        rule_id="rule_m4_project_focus_factual",
                        strength="entailed",
                        confidence=confidence,
                    )
                )
        return drafts

    def _reflection_inference_drafts(self, claims: list[Claim]) -> list[dict[str, Any]]:
        response_claims = [
            claim
            for claim in claims
            if claim.memory_type == "preference"
            and claim.predicate == "prefers_response_style"
            and claim.status in {"active", "core"}
        ]
        if len(response_claims) < 2:
            return []
        selected = sorted(response_claims, key=lambda claim: claim.id)[:3]
        confidence = self._derived_confidence_from_claims([claim.id for claim in selected])
        text = "The user prefers response depth to match context: " + "; ".join(
            claim.object for claim in selected
        ) + "."
        return [
            self._inference_draft(
                namespace=selected[0].namespace,
                engine="reflection",
                inference_type="reflection",
                text=text,
                subject="user",
                predicate="prefers_context_sensitive_response_depth",
                object=text,
                source_claim_ids=[claim.id for claim in selected],
                source_evidence_ids=sorted({evidence_id for claim in selected for evidence_id in claim.evidence_ids}),
                rule_id="rule_m4_reflection_suggestion",
                strength="probable",
                confidence=min(confidence, 0.80),
                abstraction_level=2,
            )
        ]

    def _inference_draft(
        self,
        *,
        namespace: str,
        engine: str,
        inference_type: str,
        text: str,
        subject: str | None,
        predicate: str | None,
        object: str | None,
        source_claim_ids: list[str],
        source_evidence_ids: list[str],
        rule_id: str | None,
        strength: str,
        confidence: float,
        abstraction_level: int = 1,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        return {
            "namespace": namespace,
            "engine": engine,
            "inference_type": inference_type,
            "text": text,
            "subject": subject,
            "predicate": predicate,
            "object": object,
            "source_claim_ids": sorted(set(source_claim_ids)),
            "source_evidence_ids": sorted(set(source_evidence_ids)),
            "source_candidate_ids": [],
            "rule_id": rule_id,
            "derivation_confidence": self._clamp(confidence),
            "suggested_truth_confidence": self._clamp(min(confidence, 0.80)),
            "suggested_retrieval_salience": self._clamp(max(0.30, min(confidence, 0.80))),
            "inference_strength": strength,
            "abstraction_level": abstraction_level,
            "invalidation_policy": "mark_stale",
            "metadata": metadata or {},
        }

    def _dedupe_inference_drafts(self, drafts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple] = set()
        deduped = []
        for draft in drafts:
            key = (
                draft["engine"],
                draft["inference_type"],
                draft.get("subject"),
                draft.get("predicate"),
                draft.get("object"),
                tuple(draft.get("source_claim_ids", [])),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(draft)
        return deduped

    def _store_inference_draft(self, *, namespace: str, run_id: str, draft: dict[str, Any]) -> str:
        if not draft.get("source_claim_ids") and not draft.get("source_evidence_ids"):
            raise ValidationError("Inference candidates require source lineage.")
        if draft["inference_type"] not in INFERENCE_TYPES:
            raise ValidationError(f"Unknown inference type: {draft['inference_type']}")
        if draft["inference_strength"] not in INFERENCE_STRENGTHS:
            raise ValidationError(f"Unknown inference strength: {draft['inference_strength']}")
        inference_id = new_id("inf")
        now = utc_now_iso()
        self.store.connection.execute(
            """
            INSERT INTO inference_candidates (
                id, namespace, inference_run_id, inference_type, subject,
                predicate, object, text, status, engine, rule_id,
                derivation_confidence, suggested_truth_confidence,
                suggested_retrieval_salience, inference_strength,
                abstraction_level, invalidation_policy, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending_review', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inference_id,
                namespace,
                run_id,
                draft["inference_type"],
                draft.get("subject"),
                draft.get("predicate"),
                draft.get("object"),
                draft["text"],
                draft["engine"],
                draft.get("rule_id"),
                draft["derivation_confidence"],
                draft["suggested_truth_confidence"],
                draft["suggested_retrieval_salience"],
                draft["inference_strength"],
                draft["abstraction_level"],
                draft["invalidation_policy"],
                now,
                json.dumps(draft.get("metadata") or {}, sort_keys=True),
            ),
        )
        for claim_id in draft.get("source_claim_ids", []):
            self._create_derivation_edge(
                namespace=namespace,
                source_id=claim_id,
                source_type="claim",
                target_id=inference_id,
                target_type="inference",
                relationship="entailed_by" if draft["inference_strength"] == "entailed" else "derived_from",
                rule_id=draft.get("rule_id"),
                confidence=draft["derivation_confidence"],
            )
        for evidence_id in draft.get("source_evidence_ids", []):
            self._create_derivation_edge(
                namespace=namespace,
                source_id=evidence_id,
                source_type="evidence",
                target_id=inference_id,
                target_type="inference",
                relationship="supported_by",
                rule_id=draft.get("rule_id"),
                confidence=1.0,
            )
        self._write_audit(
            namespace=namespace,
            target_type="inference",
            target_id=inference_id,
            action="inference.create",
            details={"engine": draft["engine"], "type": draft["inference_type"]},
        )
        return inference_id

    def _persist_semantic_inference(
        self,
        *,
        namespace: str,
        project_id: str | None,
        target_claim_ids: list[str],
    ) -> None:
        claims = [
            claim
            for claim in self._eligible_claims_for_inference(
                namespace=namespace,
                project_id=project_id,
                session_id=None,
                target_claim_ids=target_claim_ids,
            )
            if claim.status in ACTIVE_STATUSES
        ]
        groups: dict[tuple[str, str], list[Claim]] = {}
        for claim in claims:
            groups.setdefault((claim.memory_type, claim.predicate), []).append(claim)
        now = utc_now_iso()
        for (memory_type, predicate), grouped_claims in groups.items():
            if len(grouped_claims) < 2:
                continue
            grouped_claims = sorted(grouped_claims, key=lambda claim: claim.id)
            cluster_key = "\0".join(claim.id for claim in grouped_claims)
            cluster_id = self._stable_id("scl", namespace, memory_type, predicate, cluster_key)
            self.store.connection.execute(
                """
                INSERT INTO semantic_clusters (
                    id, namespace, label, cluster_type, created_by, confidence,
                    created_at, updated_at, metadata_json
                )
                VALUES (?, ?, ?, 'claim_similarity', 'm4.semantic', ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    cluster_id,
                    namespace,
                    f"{memory_type}:{predicate}",
                    0.72,
                    now,
                    now,
                    json.dumps(
                        {
                            "memory_type": memory_type,
                            "predicate": predicate,
                            "policy": "semantic relation only; no truth confidence change",
                        },
                        sort_keys=True,
                    ),
                ),
            )
            for claim in grouped_claims:
                self.store.connection.execute(
                    """
                    INSERT OR IGNORE INTO semantic_cluster_members (
                        cluster_id, member_id, member_type, membership_confidence, created_at
                    )
                    VALUES (?, ?, 'claim', ?, ?)
                    """,
                    (cluster_id, claim.id, 0.72, now),
                )
                self._create_derivation_edge(
                    namespace=namespace,
                    source_id=claim.id,
                    source_type="claim",
                    target_id=cluster_id,
                    target_type="semantic_cluster",
                    relationship="clusters_with",
                    rule_id="rule_m4_semantic_relation",
                    confidence=0.72,
                )
            for index, source in enumerate(grouped_claims):
                for target in grouped_claims[index + 1 :]:
                    relation_id = self._stable_id(
                        "semrel",
                        namespace,
                        source.id,
                        target.id,
                        "related_to",
                    )
                    self.store.connection.execute(
                        """
                        INSERT OR IGNORE INTO semantic_relations (
                            id, namespace, source_id, source_type, target_id,
                            target_type, relation_type, confidence, created_at,
                            metadata_json
                        )
                        VALUES (?, ?, ?, 'claim', ?, 'claim', 'related_to', ?, ?, ?)
                        """,
                        (
                            relation_id,
                            namespace,
                            source.id,
                            target.id,
                            0.70,
                            now,
                            json.dumps(
                                {
                                    "reason": "Shared memory_type and predicate.",
                                    "truth_effect": "none",
                                },
                                sort_keys=True,
                            ),
                        ),
                    )
                    self._create_derivation_edge(
                        namespace=namespace,
                        source_id=source.id,
                        source_type="claim",
                        target_id=relation_id,
                        target_type="semantic_relation",
                        relationship="semantically_related_to",
                        rule_id="rule_m4_semantic_relation",
                        confidence=0.70,
                    )
                    self._create_derivation_edge(
                        namespace=namespace,
                        source_id=target.id,
                        source_type="claim",
                        target_id=relation_id,
                        target_type="semantic_relation",
                        relationship="semantically_related_to",
                        rule_id="rule_m4_semantic_relation",
                        confidence=0.70,
                    )

    def _write_rule_execution_log(
        self,
        *,
        namespace: str,
        rule_id: str,
        inference_run_id: str | None,
        matched_count: int,
        inference_count: int,
        dry_run: bool,
        warnings: list[str],
    ) -> None:
        self.store.connection.execute(
            """
            INSERT INTO rule_execution_log (
                id, namespace, rule_id, inference_run_id, matched_count,
                inference_count, dry_run, created_at, warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("rlog"),
                namespace,
                rule_id,
                inference_run_id,
                matched_count,
                inference_count,
                int(dry_run),
                utc_now_iso(),
                json.dumps(warnings, sort_keys=True),
            ),
        )

    def _source_ids_for_target(
        self,
        target_id: str,
        target_type: str,
        source_type: str,
    ) -> list[str]:
        rows = self.store.connection.execute(
            """
            SELECT DISTINCT source_id
            FROM derivation_edges
            WHERE target_id = ?
              AND target_type = ?
              AND source_type = ?
            ORDER BY source_id
            """,
            (target_id, target_type, source_type),
        ).fetchall()
        return [row["source_id"] for row in rows]

    def _source_ids_for_reflection(self, reflection_id: str, source_type: str) -> list[str]:
        rows = self.store.connection.execute(
            """
            SELECT source_id
            FROM reflection_sources
            WHERE reflection_id = ?
              AND source_type = ?
            ORDER BY source_id
            """,
            (reflection_id, source_type),
        ).fetchall()
        return [row["source_id"] for row in rows]

    def _link_reflection_source(
        self,
        reflection_id: str,
        source_id: str,
        source_type: str,
        relation: str = "source",
    ) -> None:
        self.store.connection.execute(
            """
            INSERT OR IGNORE INTO reflection_sources (
                reflection_id, source_id, source_type, relation, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (reflection_id, source_id, source_type, relation, utc_now_iso()),
        )

    def _create_derivation_edge(
        self,
        *,
        namespace: str,
        source_id: str,
        source_type: str,
        target_id: str,
        target_type: str,
        relationship: str,
        rule_id: str | None = None,
        confidence: float = 1.0,
        metadata: dict | None = None,
    ) -> None:
        if relationship not in DERIVATION_RELATIONSHIPS:
            raise ValidationError(f"Unknown derivation relationship: {relationship}")
        edge_id = self._stable_id(
            "der",
            namespace,
            source_type,
            source_id,
            target_type,
            target_id,
            relationship,
        )
        self.store.connection.execute(
            """
            INSERT OR IGNORE INTO derivation_edges (
                id, namespace, source_id, source_type, target_id, target_type,
                relationship, rule_id, confidence, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                edge_id,
                namespace,
                source_id,
                source_type,
                target_id,
                target_type,
                relationship,
                rule_id,
                self._clamp(confidence),
                utc_now_iso(),
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )

    def _derivation_edges_for_target(
        self,
        target_id: str,
        target_type: str,
    ) -> list[DerivationEdge]:
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM derivation_edges
            WHERE target_id = ?
              AND target_type = ?
            ORDER BY created_at ASC, id ASC
            """,
            (target_id, target_type),
        ).fetchall()
        return [DerivationEdge.from_row(row) for row in rows]

    def _invalidation_events_for_target(
        self,
        target_id: str,
        target_type: str,
    ) -> list[InvalidationEvent]:
        rows = self.store.connection.execute(
            """
            SELECT *
            FROM invalidation_events
            WHERE affected_id = ?
              AND affected_type = ?
            ORDER BY created_at ASC, id ASC
            """,
            (target_id, target_type),
        ).fetchall()
        return [InvalidationEvent.from_row(row) for row in rows]

    def _apply_invalidation_action(
        self,
        *,
        namespace: str,
        affected_id: str,
        affected_type: str,
        reason: str,
        mode: str,
    ) -> str:
        action = "queued_refresh"
        if affected_type == "reflection":
            new_status = "invalidated" if mode == "invalidate" else "stale"
            self.store.connection.execute(
                "UPDATE reflections SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, utc_now_iso(), affected_id),
            )
            action = "invalidated" if new_status == "invalidated" else "marked_stale"
        elif affected_type == "inference":
            new_status = "invalidated" if mode == "invalidate" else "stale"
            self.store.connection.execute(
                """
                UPDATE inference_candidates
                SET status = ?
                WHERE id = ?
                  AND status NOT IN ('rejected', 'promoted')
                """,
                (new_status, affected_id),
            )
            action = "invalidated" if new_status == "invalidated" else "marked_stale"
        elif affected_type == "abstraction":
            new_status = "invalidated" if mode == "invalidate" else "stale"
            self.store.connection.execute(
                "UPDATE abstraction_records SET status = ? WHERE id = ?",
                (new_status, affected_id),
            )
            action = "invalidated" if new_status == "invalidated" else "marked_stale"
        elif affected_type == "claim":
            row = self.store.connection.execute(
                "SELECT memory_type, status FROM claims WHERE id = ?",
                (affected_id,),
            ).fetchone()
            if row and row["memory_type"] == "inference":
                new_status = "rejected" if mode == "invalidate" else "disputed"
                self.store.connection.execute(
                    "UPDATE claims SET status = ? WHERE id = ?",
                    (new_status, affected_id),
                )
                action = "invalidated" if new_status == "rejected" else "marked_stale"
        if mode in {"mark_stale", "queue_refresh", "recompute"}:
            refresh_id = self._stable_id("refq", namespace, affected_type, affected_id, reason)
            now = utc_now_iso()
            self.store.connection.execute(
                """
                INSERT OR IGNORE INTO refresh_queue (
                    id, namespace, target_id, target_type, reason, priority,
                    status, created_at, updated_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, 0.75, 'pending', ?, ?, ?)
                """,
                (
                    refresh_id,
                    namespace,
                    affected_id,
                    affected_type,
                    reason,
                    now,
                    now,
                    json.dumps({"mode": mode}, sort_keys=True),
                ),
            )
        return action

    def _apply_inference_edits(self, inference_id: str, edits: dict) -> None:
        if not edits:
            return
        allowed = {
            "subject",
            "predicate",
            "object",
            "text",
            "status",
            "inference_strength",
            "derivation_confidence",
            "suggested_truth_confidence",
            "suggested_retrieval_salience",
            "abstraction_level",
            "invalidation_policy",
            "metadata",
        }
        assignments: list[str] = []
        values: list[object] = []
        for key, value in edits.items():
            if key not in allowed:
                raise ValidationError(f"Unsupported inference edit field: {key}")
            if key == "text":
                self._require_text(value, key)
            if key in {"subject", "predicate", "object"} and value is not None:
                self._require_text(value, key)
            if key == "status":
                if not isinstance(value, str):
                    raise ValidationError("status must be a string.")
                if value not in INFERENCE_STATUSES:
                    raise ValidationError(f"Unknown inference status: {value}")
                if value not in INFERENCE_EDITABLE_STATUSES:
                    raise ValidationError(
                        f"Inference status {value!r} requires the dedicated review or promotion flow."
                    )
            if key == "inference_strength":
                if not isinstance(value, str):
                    raise ValidationError("inference_strength must be a string.")
                if value not in INFERENCE_STRENGTHS:
                    raise ValidationError(f"Unknown inference strength: {value}")
            if key == "invalidation_policy":
                if not isinstance(value, str):
                    raise ValidationError("invalidation_policy must be a string.")
                if value not in INVALIDATION_MODES:
                    raise ValidationError(f"Unknown invalidation policy: {value}")
            if key == "abstraction_level":
                try:
                    value = int(value)
                except (TypeError, ValueError) as exc:
                    raise ValidationError("abstraction_level must be an integer.") from exc
                if value < 1:
                    raise ValidationError("abstraction_level must be at least 1.")
            if key == "metadata" and not isinstance(value or {}, dict):
                raise ValidationError("metadata must be an object.")
            column = "metadata_json" if key == "metadata" else key
            if key in {
                "derivation_confidence",
                "suggested_truth_confidence",
                "suggested_retrieval_salience",
            }:
                try:
                    value = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValidationError(f"{key} must be numeric.") from exc
                if not 0.0 <= value <= 1.0:
                    raise ValidationError(f"{key} must be between 0 and 1.")
            if key == "metadata":
                value = json.dumps(value or {}, sort_keys=True)
            assignments.append(f"{column} = ?")
            values.append(value)
        values.append(inference_id)
        self.store.connection.execute(
            f"UPDATE inference_candidates SET {', '.join(assignments)} WHERE id = ?",
            values,
        )

    def _write_inference_decision_in_transaction(
        self,
        *,
        namespace: str,
        inference_id: str,
        decision: str,
        reason: str,
        reviewer: str,
        edits: dict | None = None,
    ) -> None:
        self.store.connection.execute(
            """
            INSERT INTO inference_decisions (
                id, namespace, inference_id, decision, reason, reviewer,
                edits_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("idec"),
                namespace,
                inference_id,
                decision,
                reason,
                reviewer,
                json.dumps(edits, sort_keys=True) if edits else None,
                utc_now_iso(),
            ),
        )
        self._write_audit(
            namespace=namespace,
            target_type="inference",
            target_id=inference_id,
            action=f"inference.{decision}",
            details={"reason": reason, "reviewer": reviewer, "edits": edits},
        )

    def _inference_promotion_failures(
        self,
        inference: InferenceCandidate,
        target_type: str,
        target_status: str,
    ) -> list[str]:
        failures: list[str] = []
        if target_type not in {"claim", "reflection"}:
            failures.append("target_type must be claim or reflection")
        if target_type == "claim" and target_status not in PROMOTION_TARGETS:
            failures.append("claim target_status must be active or core")
        if not inference.source_claim_ids and not inference.source_evidence_ids:
            failures.append("inference has no source lineage")
        if inference.status != "validated":
            failures.append("inference must be validated before promotion")
        if inference.inference_strength in {"weak", "speculative", "retrieval_hint"}:
            failures.append("speculative or retrieval-only inferences cannot promote by default")
        if inference.suggested_truth_confidence < 0.50:
            failures.append("suggested truth confidence is too low")
        for claim_id in inference.source_claim_ids:
            claim = self.read_claim(claim_id)
            if claim.status in {"rejected", "superseded", "archived"}:
                failures.append(f"source claim {claim_id} is {claim.status}")
            if self._has_unresolved_conflicts(claim_id):
                failures.append(f"source claim {claim_id} has an unresolved conflict")
        if target_status == "core" and (
            inference.inference_strength != "entailed"
            or inference.suggested_truth_confidence < 0.90
        ):
            failures.append("core promotion requires an entailed high-confidence inference")
        if target_type == "claim" and inference.subject and inference.predicate and inference.object:
            rows = self.store.connection.execute(
                """
                SELECT id
                FROM claims
                WHERE namespace = ?
                  AND subject = ?
                  AND predicate = ?
                  AND object != ?
                  AND status IN ('active', 'core')
                LIMIT 1
                """,
                (
                    inference.namespace,
                    inference.subject,
                    inference.predicate,
                    inference.object,
                ),
            ).fetchone()
            if rows:
                failures.append("inference conflicts with an active claim")
        return sorted(set(failures))

    def _project_id_for_inference(self, inference: InferenceCandidate) -> str | None:
        row = self.store.connection.execute(
            "SELECT project_id FROM inference_runs WHERE id = ?",
            (inference.inference_run_id,),
        ).fetchone()
        if row and row["project_id"]:
            return row["project_id"]
        if inference.subject:
            return self._infer_project_id(inference.subject)
        return None

    def _reflection_text_from_sources(self, source_claim_ids: list[str]) -> str:
        if not source_claim_ids:
            return "Reflection over source evidence."
        claims = [self.read_claim(claim_id) for claim_id in source_claim_ids]
        return " ".join(claim_text(claim.subject, claim.predicate, claim.object) for claim in claims)

    def _derived_confidence_from_claims(self, source_claim_ids: list[str]) -> float:
        if not source_claim_ids:
            return 0.50
        confidences = [
            self.compute_confidence(claim_id).effective_confidence
            for claim_id in source_claim_ids
        ]
        return self._clamp(min(confidences))

    def _rule_exists(self, rule_id: str) -> bool:
        row = self.store.connection.execute(
            "SELECT 1 FROM inference_rules WHERE id = ? LIMIT 1",
            (rule_id,),
        ).fetchone()
        return row is not None

    def _record_usage_in_transaction(
        self,
        *,
        namespace: str,
        target_id: str,
        target_type: str,
        usage_type: str,
        query: str | None,
        session_id: str | None,
        project_id: str | None,
        context_pack_id: str | None,
        rank: int | None,
        score: float | None,
        metadata: dict | None,
    ) -> str:
        usage_id = new_id("use")
        self.store.connection.execute(
            """
            INSERT INTO memory_usage_events (
                id, namespace, target_id, target_type, usage_type, query,
                session_id, project_id, context_pack_id, rank, score,
                created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                usage_id,
                namespace,
                target_id,
                target_type,
                usage_type,
                query,
                session_id,
                project_id,
                context_pack_id,
                rank,
                score,
                utc_now_iso(),
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )
        return usage_id

    def _record_context_usage_in_transaction(
        self,
        *,
        namespace: str,
        context_pack_id: str,
        query: str,
        session_id: str | None,
        project_id: str | None,
        item_count: int,
        token_estimate: int,
        metadata: dict | None,
    ) -> str:
        usage_id = new_id("ctxuse")
        self.store.connection.execute(
            """
            INSERT INTO context_usage_events (
                id, namespace, context_pack_id, query, session_id, project_id,
                item_count, token_estimate, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                usage_id,
                namespace,
                context_pack_id,
                query,
                session_id,
                project_id,
                item_count,
                token_estimate,
                utc_now_iso(),
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )
        return usage_id

    def _active_ranking_policy_version_id(self, policy_id: str = "rpol_default") -> str | None:
        row = self.store.connection.execute(
            "SELECT active_version_id FROM ranking_policies WHERE id = ?",
            (policy_id,),
        ).fetchone()
        return row["active_version_id"] if row else None

    def _active_context_policy_version_id(self, policy_id: str = "cpol_default") -> str | None:
        row = self.store.connection.execute(
            "SELECT active_version_id FROM context_pack_policies WHERE id = ?",
            (policy_id,),
        ).fetchone()
        return row["active_version_id"] if row else None

    def _evaluation_case_metrics(
        self,
        *,
        case: EvaluationCase,
        retrieved_ids: list[str],
        results: list[RetrievalResult],
        pack: ContextPack | None,
        started: datetime,
    ) -> dict[str, float]:
        expected = case.expected_claim_ids + case.expected_reflection_ids
        retrieved_set = set(retrieved_ids)

        def recall_at(k: int) -> float:
            if not expected:
                return 1.0
            return len(set(expected).intersection(retrieved_ids[:k])) / len(set(expected))

        precision_denominator = min(5, max(len(retrieved_ids[:5]), 1))
        precision_at_5 = (
            len(set(expected).intersection(retrieved_ids[:5])) / precision_denominator
            if expected
            else 1.0
        )
        mrr = 0.0
        for index, item_id in enumerate(retrieved_ids, start=1):
            if item_id in expected:
                mrr = 1.0 / index
                break
        forbidden_leak = 1.0 if set(case.forbidden_claim_ids).intersection(retrieved_set) else 0.0
        status_counts = self._leaked_status_counts(retrieved_ids)
        provenance_total = len(results) + (len(pack.items()) if pack else 0)
        provenance_ok = sum(1 for result in results if result.evidence_ids)
        if pack:
            provenance_ok += sum(1 for item in pack.items() if item.evidence_ids or item.source_kind in {"reflection", "inference"})
        provenance_rate = 1.0 if provenance_total == 0 else provenance_ok / provenance_total
        section_accuracy = self._context_section_accuracy(pack, case.expected_sections)
        token_efficiency = 1.0
        if pack:
            estimated = sum(self._estimate_tokens(item.text) for item in pack.items())
            token_efficiency = min(1.0, pack.token_budget / max(estimated, 1))
        return {
            "recall_at_1": recall_at(1),
            "recall_at_3": recall_at(3),
            "recall_at_5": recall_at(5),
            "precision_at_5": precision_at_5,
            "mean_reciprocal_rank": mrr,
            "forbidden_memory_leak_rate": forbidden_leak,
            "disputed_memory_leak_rate": 1.0 if status_counts["disputed"] else 0.0,
            "rejected_memory_leak_rate": 1.0 if status_counts["rejected"] else 0.0,
            "superseded_memory_leak_rate": 1.0 if status_counts["superseded"] else 0.0,
            "stale_memory_leak_rate": 1.0 if status_counts["stale"] else 0.0,
            "provenance_preservation_rate": provenance_rate,
            "context_section_accuracy": section_accuracy,
            "token_efficiency": token_efficiency,
            "average_latency_ms": max((utc_now() - started).total_seconds() * 1000.0, 0.0),
        }

    def _evaluation_failure_reasons(self, metrics: dict[str, float]) -> list[str]:
        failures = []
        for name in [
            "forbidden_memory_leak_rate",
            "rejected_memory_leak_rate",
            "superseded_memory_leak_rate",
            "stale_memory_leak_rate",
        ]:
            if metrics.get(name, 0.0) > 0.0:
                failures.append(name)
        if metrics.get("disputed_memory_leak_rate", 0.0) > 0.02:
            failures.append("disputed_memory_leak_rate")
        if metrics.get("provenance_preservation_rate", 1.0) < 0.99:
            failures.append("provenance_preservation_rate")
        return failures

    def _evaluation_metric_threshold(self, metric_name: str) -> float | None:
        thresholds = {
            "forbidden_memory_leak_rate": 0.0,
            "rejected_memory_leak_rate": 0.0,
            "superseded_memory_leak_rate": 0.0,
            "stale_memory_leak_rate": 0.0,
            "disputed_memory_leak_rate": 0.02,
            "provenance_preservation_rate": 0.99,
            "recall_at_5": 0.0,
        }
        return thresholds.get(metric_name)

    def _leaked_status_counts(self, ids: list[str]) -> dict[str, int]:
        counts = {"disputed": 0, "rejected": 0, "superseded": 0, "stale": 0}
        for item_id in ids:
            if item_id.startswith("clm_"):
                row = self.store.connection.execute(
                    "SELECT status FROM claims WHERE id = ?",
                    (item_id,),
                ).fetchone()
                if row and row["status"] in counts:
                    counts[row["status"]] += 1
            elif item_id.startswith("ref_"):
                row = self.store.connection.execute(
                    "SELECT status FROM reflections WHERE id = ?",
                    (item_id,),
                ).fetchone()
                if row and row["status"] in {"stale", "invalidated"}:
                    counts["stale"] += 1
            elif item_id.startswith("inf_"):
                row = self.store.connection.execute(
                    "SELECT status FROM inference_candidates WHERE id = ?",
                    (item_id,),
                ).fetchone()
                if row and row["status"] in {"stale", "invalidated", "rejected"}:
                    counts["stale" if row["status"] != "rejected" else "rejected"] += 1
        return counts

    def _context_section_accuracy(self, pack: ContextPack | None, expected_sections: dict) -> float:
        if not expected_sections:
            return 1.0
        if not pack:
            return 0.0
        sections = {
            "core_memory": pack.core_memory,
            "project_memory": pack.project_memory,
            "session_memory": pack.session_memory,
            "procedural_memory": pack.procedural_memory,
            "reflection_memory": pack.reflection_memory,
            "relevant_memory": pack.relevant_memory,
        }
        checks = 0
        passed = 0
        for section, fragments in expected_sections.items():
            section_text = "\n".join(item.text for item in sections.get(section, []))
            for fragment in fragments:
                checks += 1
                if str(fragment).lower() in section_text.lower():
                    passed += 1
        return 1.0 if checks == 0 else passed / checks

    def _procedure_update_risk_level(self, title: str, text: str, reason: str) -> str:
        content = f"{title} {text} {reason}".lower()
        critical_terms = {
            "delete evidence",
            "delete claims",
            "autonomous deletion",
            "privacy labels downward",
            "send email",
            "external communication",
            "auto apply policy",
            "auto apply procedure",
        }
        high_terms = {
            "privacy",
            "safety",
            "deletion",
            "delete",
            "external",
            "tool execution",
            "autonomous promotion",
            "auto-promote",
            "promote to core",
        }
        if any(term in content for term in critical_terms):
            return "critical"
        if any(term in content for term in high_terms):
            return "high"
        return "low"

    def _policy_gate_status(self, evaluation_run_id: str | None) -> tuple[bool, list[str]]:
        if not evaluation_run_id:
            return False, ["missing evaluation run"]
        run = self.read_evaluation_run(evaluation_run_id)
        failures = self._evaluation_failure_reasons(run.metrics)
        if not run.passed:
            failures.append("evaluation run did not pass")
        return not failures, sorted(set(failures))

    def _evaluation_summary(self, evaluation_run_id: str | None) -> dict | None:
        if not evaluation_run_id:
            return None
        run = self.read_evaluation_run(evaluation_run_id)
        return {"evaluation_run_id": run.id, "passed": run.passed, "metrics": run.metrics}

    def _create_ranking_policy_version(
        self,
        *,
        policy_id: str,
        config: dict,
        created_by: str,
        status: str,
        evaluation_summary: dict | None,
    ) -> str:
        row = self.store.connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM ranking_policy_versions WHERE policy_id = ?",
            (policy_id,),
        ).fetchone()
        version = int(row["version"]) + 1
        version_id = new_id("rpv")
        self.store.connection.execute(
            """
            INSERT INTO ranking_policy_versions (
                id, policy_id, version, weights_json, filters_json,
                thresholds_json, created_by, status, evaluation_summary_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                policy_id,
                version,
                json.dumps(config.get("weights") or config, sort_keys=True),
                json.dumps(config.get("filters") or {}, sort_keys=True),
                json.dumps(config.get("thresholds") or {}, sort_keys=True),
                created_by,
                status,
                json.dumps(evaluation_summary, sort_keys=True) if evaluation_summary else None,
                utc_now_iso(),
            ),
        )
        return version_id

    def _create_context_policy_version(
        self,
        *,
        policy_id: str,
        config: dict,
        created_by: str,
        status: str,
        evaluation_summary: dict | None,
    ) -> str:
        row = self.store.connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM context_pack_policy_versions WHERE policy_id = ?",
            (policy_id,),
        ).fetchone()
        version = int(row["version"]) + 1
        version_id = new_id("cpv")
        self.store.connection.execute(
            """
            INSERT INTO context_pack_policy_versions (
                id, policy_id, version, config_json, filters_json,
                thresholds_json, created_by, status, evaluation_summary_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                policy_id,
                version,
                json.dumps(config, sort_keys=True),
                json.dumps(config.get("filters") or {}, sort_keys=True),
                json.dumps(config.get("thresholds") or {}, sort_keys=True),
                created_by,
                status,
                json.dumps(evaluation_summary, sort_keys=True) if evaluation_summary else None,
                utc_now_iso(),
            ),
        )
        return version_id

    def _write_review_task_event(
        self,
        *,
        review_task_id: str,
        event_type: str,
        actor: str,
        note: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        if event_type not in REVIEW_EVENT_TYPES:
            raise ValidationError(f"Unknown review task event type: {event_type}")
        self.store.connection.execute(
            """
            INSERT INTO review_task_events (
                id, review_task_id, event_type, actor, note, created_at,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("reve"),
                review_task_id,
                event_type,
                actor,
                note,
                utc_now_iso(),
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )

    def _transition_review_task(
        self,
        review_task_id: str,
        *,
        status: str,
        event_type: str,
        note: str,
        actor: str,
        metadata: dict | None = None,
    ) -> ReviewTask:
        if status not in REVIEW_TASK_STATUSES:
            raise ValidationError(f"Unknown review task status: {status}")
        task = self.get_review_task(review_task_id)
        now = utc_now_iso()
        with self.store.transaction():
            self.store.connection.execute(
                "UPDATE review_tasks SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, review_task_id),
            )
            self._write_review_task_event(
                review_task_id=review_task_id,
                event_type=event_type,
                actor=actor,
                note=note,
                metadata=metadata,
            )
            self._write_audit(
                namespace=task.namespace,
                target_type="review_task",
                target_id=review_task_id,
                action=f"review_task.{status}",
                details={"note": note, "actor": actor, **(metadata or {})},
            )
        return self.get_review_task(review_task_id)

    def _write_trace_event(self, trace_run_id: str, event_type: str, message: str, metadata: dict | None = None) -> None:
        self.store.connection.execute(
            """
            INSERT INTO trace_events (
                id, trace_run_id, event_type, message, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("tev"),
                trace_run_id,
                event_type,
                message,
                utc_now_iso(),
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )

    def _trace_candidate_claim_rows(
        self,
        *,
        namespace: str,
        project_id: str | None,
        limit: int,
    ):
        params: list[object] = [namespace]
        project_clause = ""
        if project_id:
            project_clause = """
              AND (
                NOT EXISTS (
                  SELECT 1 FROM project_claim_links pcl_any
                  WHERE pcl_any.claim_id = claims.id
                )
                OR EXISTS (
                  SELECT 1 FROM project_claim_links pcl
                  WHERE pcl.claim_id = claims.id
                    AND pcl.project_id = ?
                )
              )
            """
            params.append(project_id)
        params.append(limit)
        return self.store.connection.execute(
            f"""
            SELECT *
            FROM claims
            WHERE namespace = ?
              {project_clause}
            ORDER BY importance DESC, confidence_effective DESC, created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    def _omission_reason_for_claim_row(self, row, *, project_id: str | None) -> str:
        status = row["status"]
        if status == "rejected":
            return "rejected"
        if status == "superseded":
            return "superseded"
        if status == "archived":
            return "status_excluded"
        if status == "disputed":
            return "unresolved_conflict"
        if row["confidence_effective"] is not None and float(row["confidence_effective"]) < 0.2:
            return "low_confidence"
        if project_id and not self._claim_applies_to_project(row["id"], project_id):
            return "scope_mismatch"
        return "low_relevance"

    def _claim_applies_to_project(self, claim_id: str, project_id: str) -> bool:
        project_links = self.store.connection.execute(
            "SELECT project_id FROM project_claim_links WHERE claim_id = ?",
            (claim_id,),
        ).fetchall()
        if project_links and not any(row["project_id"] == project_id for row in project_links):
            return False
        scopes = self.store.connection.execute(
            """
            SELECT scope_type, applies_when
            FROM claim_scopes
            WHERE claim_id = ?
            """,
            (claim_id,),
        ).fetchall()
        for scope in scopes:
            if scope["scope_type"] == "project" and scope["applies_when"] != project_id:
                return False
        return True

    def _operational_metrics(self, *, namespace: str | None, project_id: str | None) -> dict[str, Any]:
        ns_clause = "namespace = ?" if namespace else "1 = 1"
        ns_params: list[object] = [namespace] if namespace else []

        def scalar(sql: str, params: list[object] | None = None) -> int | float:
            row = self.store.connection.execute(sql, params or []).fetchone()
            if not row:
                return 0
            value = row[0]
            return 0 if value is None else value

        active_claim_count = scalar(f"SELECT count(*) FROM claims WHERE {ns_clause} AND status = 'active'", ns_params)
        core_memory_count = scalar(f"SELECT count(*) FROM claims WHERE {ns_clause} AND status = 'core'", ns_params)
        candidate_count = scalar(f"SELECT count(*) FROM candidate_claims WHERE {ns_clause}", ns_params)
        pending_review_count = scalar(f"SELECT count(*) FROM candidate_claims WHERE {ns_clause} AND candidate_status = 'pending_review'", ns_params)
        unresolved_conflict_count = scalar(f"SELECT count(*) FROM conflict_families WHERE {ns_clause} AND status = 'unresolved'", ns_params)
        stale_claim_count = scalar(f"SELECT count(*) FROM claims WHERE {ns_clause} AND status IN ('disputed', 'archived')", ns_params)
        invalidated_reflection_count = scalar(f"SELECT count(*) FROM reflections WHERE {ns_clause} AND status IN ('stale', 'invalidated')", ns_params)
        open_review_task_count = scalar(f"SELECT count(*) FROM review_tasks WHERE {ns_clause} AND status = 'open'", ns_params)
        critical_review_task_count = scalar(f"SELECT count(*) FROM review_tasks WHERE {ns_clause} AND status = 'open' AND severity = 'critical'", ns_params)
        failed_job_count = scalar(
            "SELECT count(*) FROM local_jobs WHERE (? IS NULL OR namespace = ?) AND status = 'failed'",
            [namespace, namespace],
        )
        pending_job_count = scalar(
            "SELECT count(*) FROM local_jobs WHERE (? IS NULL OR namespace = ?) AND status = 'pending'",
            [namespace, namespace],
        )
        recent_context_pack_count = scalar(
            "SELECT count(*) FROM service_request_log WHERE path IN ('/v1/context-pack', '/v1/context')",
        )
        recent_service_request_count = scalar("SELECT count(*) FROM service_request_log")
        avg_retrieval_latency = scalar(
            "SELECT avg(duration_ms) FROM service_request_log WHERE path IN ('/v1/retrieve', '/v1/search')"
        )
        avg_context_latency = scalar(
            "SELECT avg(duration_ms) FROM service_request_log WHERE path IN ('/v1/context-pack', '/v1/context')"
        )
        policy_proposals_pending = scalar(f"SELECT count(*) FROM policy_proposals WHERE {ns_clause} AND status = 'pending_review'", ns_params)
        warning_count = 0
        latest_health = self.store.connection.execute(
            """
            SELECT warnings_json
            FROM memory_health_snapshots
            WHERE (? IS NULL OR namespace = ?)
            ORDER BY generated_at DESC
            LIMIT 1
            """,
            (namespace, namespace),
        ).fetchone()
        if latest_health:
            warning_count = len(json.loads(latest_health["warnings_json"] or "[]"))
        eval_rows = self.store.connection.execute(
            """
            SELECT metric_name, metric_value, passed
            FROM evaluation_metrics
            ORDER BY created_at DESC
            LIMIT 100
            """
        ).fetchall()
        eval_pass_rate = 1.0
        if eval_rows:
            eval_pass_rate = sum(1 for row in eval_rows if row["passed"] in (None, 1)) / len(eval_rows)
        return {
            "active_claim_count": active_claim_count,
            "core_memory_count": core_memory_count,
            "candidate_count": candidate_count,
            "pending_review_count": pending_review_count,
            "unresolved_conflict_count": unresolved_conflict_count,
            "stale_claim_count": stale_claim_count,
            "invalidated_reflection_count": invalidated_reflection_count,
            "open_review_task_count": open_review_task_count,
            "critical_review_task_count": critical_review_task_count,
            "failed_job_count": failed_job_count,
            "pending_job_count": pending_job_count,
            "last_health_report_status": "warning" if warning_count else "ok",
            "last_eval_run_status": "ok" if eval_pass_rate >= 1.0 else "needs_review",
            "recent_context_pack_count": recent_context_pack_count,
            "recent_service_request_count": recent_service_request_count,
            "average_retrieval_latency": avg_retrieval_latency,
            "average_context_pack_latency": avg_context_latency,
            "context_packs_generated": recent_context_pack_count,
            "service_requests_by_endpoint": self._service_requests_by_endpoint(),
            "failed_jobs": failed_job_count,
            "pending_jobs": pending_job_count,
            "evaluation_pass_rate": eval_pass_rate,
            "policy_proposals_pending": policy_proposals_pending,
            "memory_health_warning_count": warning_count,
            "project_id": project_id,
        }

    def _service_requests_by_endpoint(self) -> dict[str, int]:
        rows = self.store.connection.execute(
            """
            SELECT path, count(*) AS count
            FROM service_request_log
            GROUP BY path
            ORDER BY count DESC, path ASC
            """
        ).fetchall()
        return {row["path"]: row["count"] for row in rows}

    def _report_payload(self, *, namespace: str | None, report_type: str, filters: dict) -> dict:
        payload: dict[str, Any] = {
            "report_type": report_type,
            "namespace": namespace,
            "generated_at": utc_now_iso(),
            "filters": filters,
        }
        if report_type == "memory_health":
            if namespace:
                payload["health_report"] = asdict(self.health_report(namespace, include_recommendations=True))
            payload["metrics"] = self._operational_metrics(namespace=namespace, project_id=filters.get("project_id"))
        elif report_type == "review_queue":
            payload["review_tasks"] = [asdict(task) for task in self.list_review_tasks(namespace=namespace, status=filters.get("status"), limit=100)]
        elif report_type == "conflict_summary":
            payload["conflicts"] = [asdict(item) for item in self.list_conflict_families(namespace=namespace, limit=100)]
        elif report_type == "candidate_summary":
            payload["candidates"] = [asdict(item) for item in self.list_candidates(namespace or self.namespace, limit=100)]
        elif report_type == "policy_review":
            payload["policy_proposals"] = [asdict(item) for item in self.list_policy_proposals(namespace=namespace, limit=100)]
        elif report_type == "service_activity":
            rows = self.store.connection.execute(
                "SELECT * FROM service_request_log ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
            payload["service_requests"] = [dict(row) for row in rows]
        elif report_type == "audit_summary":
            params: list[object] = []
            clause = ""
            if namespace:
                clause = "WHERE namespace = ?"
                params.append(namespace)
            rows = self.store.connection.execute(
                f"SELECT * FROM audit_log {clause} ORDER BY created_at DESC LIMIT 100",
                params,
            ).fetchall()
            payload["audit"] = [dict(row) for row in rows]
        return payload

    def _report_markdown(self, payload: dict) -> str:
        lines = [
            f"# Aletheia {payload['report_type'].replace('_', ' ').title()}",
            "",
            f"Generated: {payload['generated_at']}",
            f"Namespace: {payload.get('namespace') or 'all'}",
            "",
        ]
        for key, value in payload.items():
            if key in {"report_type", "namespace", "generated_at", "filters"}:
                continue
            lines.append(f"## {key.replace('_', ' ').title()}")
            if isinstance(value, dict):
                for metric, metric_value in value.items():
                    lines.append(f"- {metric}: {metric_value}")
            elif isinstance(value, list):
                for item in value[:100]:
                    if isinstance(item, dict):
                        label = item.get("title") or item.get("id") or item.get("target_id") or str(item)
                        status = item.get("status") or item.get("severity") or ""
                        lines.append(f"- {label} {status}".rstrip())
                    else:
                        lines.append(f"- {item}")
            else:
                lines.append(str(value))
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _run_single_job(self, job: LocalJob) -> None:
        if not self._claim_pending_job(job):
            return
        try:
            self._execute_job(job)
        except Exception as exc:  # noqa: BLE001 - job queue records operational failures.
            updated = self.get_job(job.id)
            status = "failed" if updated.attempts >= updated.max_attempts else "pending"
            with self.store.transaction():
                self.store.connection.execute(
                    """
                    UPDATE local_jobs
                    SET status = ?, last_error = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, str(exc), utc_now_iso(), job.id),
                )
                self._write_audit(
                    namespace=job.namespace or "global",
                    target_type="local_job",
                    target_id=job.id,
                    action="job.failed",
                    details={"error": str(exc), "status": status},
                )
            return
        with self.store.transaction():
            self.store.connection.execute(
                """
                UPDATE local_jobs
                SET status = 'completed', last_error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (utc_now_iso(), job.id),
            )
            self._write_audit(
                namespace=job.namespace or "global",
                target_type="local_job",
                target_id=job.id,
                action="job.completed",
                details={"job_type": job.job_type},
            )

    def _claim_pending_job(self, job: LocalJob) -> bool:
        now = utc_now_iso()
        with self.store.transaction():
            cursor = self.store.connection.execute(
                """
                UPDATE local_jobs
                SET status = 'running', attempts = attempts + 1, updated_at = ?
                WHERE id = ?
                  AND status = 'pending'
                  AND attempts < max_attempts
                  AND (run_after IS NULL OR run_after <= ?)
                """,
                (now, job.id, now),
            )
        return cursor.rowcount == 1

    def _execute_job(self, job: LocalJob) -> None:
        namespace = job.namespace or self.namespace
        payload = job.payload
        if job.job_type in {"recompute_confidence", "run_decay"}:
            self.recompute_confidence(namespace=namespace)
        elif job.job_type == "detect_conflicts":
            self.detect_conflicts(namespace=namespace)
        elif job.job_type == "curate":
            self.curate(namespace=namespace, dry_run=bool(payload.get("dry_run", False)))
        elif job.job_type == "refresh_reflections":
            for reflection in self.list_reflections(namespace=namespace, status="stale"):
                self.store.connection.execute(
                    "UPDATE reflections SET status = 'candidate', updated_at = ? WHERE id = ?",
                    (utc_now_iso(), reflection.id),
                )
        elif job.job_type == "run_evaluation":
            self.run_evaluation(
                namespace,
                eval_set_id=payload["eval_set_id"],
                retrieval_mode=payload.get("retrieval_mode", "hybrid"),
            )
        elif job.job_type == "optimize_retrieval":
            self.optimize_retrieval(
                namespace,
                eval_set_id=payload.get("eval_set_id"),
                objective=payload.get("objective", "balanced"),
                dry_run=bool(payload.get("dry_run", True)),
            )
        elif job.job_type == "run_learning":
            self.run_learning(
                namespace,
                project_id=payload.get("project_id"),
                learning_targets=payload.get("learning_targets"),
                eval_set_id=payload.get("eval_set_id"),
                dry_run=bool(payload.get("dry_run", True)),
            )
        elif job.job_type == "memory_health_check":
            self.health_report(namespace, project_id=payload.get("project_id"))
        elif job.job_type == "run_inference":
            self.run_inference(
                namespace,
                engines=payload.get("engines"),
                project_id=payload.get("project_id"),
                dry_run=bool(payload.get("dry_run", True)),
            )
        elif job.job_type == "index_semantic":
            self.index_semantic(namespace, target_type=payload.get("target_type", "claims"))
        else:
            raise ValidationError(f"Unsupported job type: {job.job_type}")

    def _health_metrics(self, *, namespace: str, project_id: str | None) -> dict[str, float | int | None]:
        project_clause = ""
        project_params: list[object] = []
        if project_id:
            project_clause = """
                AND (
                    NOT EXISTS (
                        SELECT 1 FROM project_claim_links pcl_any
                        WHERE pcl_any.claim_id = claims.id
                    )
                    OR EXISTS (
                        SELECT 1 FROM project_claim_links pcl
                        WHERE pcl.claim_id = claims.id
                          AND pcl.project_id = ?
                    )
                )
            """
            project_params.append(project_id)
        def count_claims(where: str, params: list[object] | None = None) -> int:
            row = self.store.connection.execute(
                f"""
                SELECT count(*) AS count
                FROM claims
                WHERE namespace = ?
                  {project_clause}
                  AND {where}
                """,
                [namespace, *project_params, *(params or [])],
            ).fetchone()
            return int(row["count"])

        active_claim_count = count_claims("status = 'active'")
        core_memory_count = count_claims("status = 'core'")
        candidate_count = self.store.connection.execute(
            "SELECT count(*) AS count FROM candidate_claims WHERE namespace = ?",
            (namespace,),
        ).fetchone()["count"]
        pending_candidates = self.store.connection.execute(
            """
            SELECT count(*) AS count
            FROM candidate_claims
            WHERE namespace = ?
              AND candidate_status = 'pending_review'
            """,
            (namespace,),
        ).fetchone()["count"]
        pending_inferences = self.store.connection.execute(
            """
            SELECT count(*) AS count
            FROM inference_candidates
            WHERE namespace = ?
              AND status = 'pending_review'
            """,
            (namespace,),
        ).fetchone()["count"]
        unresolved_conflict_count = len(self.list_conflict_families(namespace=namespace, status="unresolved"))
        stale_memory_count = count_claims("valid_to IS NOT NULL AND valid_to < ?", [utc_now_iso()])
        invalidated_derived_count = self.store.connection.execute(
            """
            SELECT
                (SELECT count(*) FROM reflections WHERE namespace = ? AND status IN ('stale', 'invalidated')) +
                (SELECT count(*) FROM inference_candidates WHERE namespace = ? AND status IN ('stale', 'invalidated')) +
                (SELECT count(*) FROM abstraction_records WHERE namespace = ? AND status IN ('stale', 'invalidated')) AS count
            """,
            (namespace, namespace, namespace),
        ).fetchone()["count"]
        orphaned_evidence_count = self.store.connection.execute(
            """
            SELECT count(*) AS count
            FROM evidence_events ee
            WHERE ee.namespace = ?
              AND NOT EXISTS (
                SELECT 1 FROM claim_evidence_links cel
                WHERE cel.evidence_id = ee.id
              )
            """,
            (namespace,),
        ).fetchone()["count"]
        unindexed_claim_count = self.store.connection.execute(
            """
            SELECT count(*) AS count
            FROM claims c
            WHERE c.namespace = ?
              AND c.status IN ('active', 'core')
              AND NOT EXISTS (
                SELECT 1 FROM embeddings e
                WHERE e.target_id = c.id
                  AND e.target_type = 'claims'
              )
            """,
            (namespace,),
        ).fetchone()["count"]
        low_confidence_active_count = count_claims("status IN ('active', 'core') AND confidence_effective < 0.50")
        high_salience_low_confidence_count = count_claims(
            "status IN ('active', 'core') AND importance >= 0.75 AND confidence_effective < 0.60"
        )
        retrieval_judgment_count = self.store.connection.execute(
            "SELECT count(*) AS count FROM retrieval_judgments WHERE namespace = ?",
            (namespace,),
        ).fetchone()["count"]
        recent_failure_count = self.store.connection.execute(
            """
            SELECT count(*) AS count
            FROM task_outcomes
            WHERE namespace = ?
              AND outcome IN ('failure', 'user_rejected', 'irrelevant_context', 'missing_context', 'stale_context', 'conflicting_context')
            """,
            (namespace,),
        ).fetchone()["count"]
        last_eval = self.store.connection.execute(
            """
            SELECT passed, metrics_json
            FROM evaluation_runs
            WHERE namespace = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (namespace,),
        ).fetchone()
        last_evaluation_score = None
        if last_eval:
            metrics = json.loads(last_eval["metrics_json"] or "{}")
            last_evaluation_score = metrics.get("recall_at_5", 0.0) * (1.0 if last_eval["passed"] else 0.5)
        return {
            "active_claim_count": active_claim_count,
            "core_memory_count": core_memory_count,
            "candidate_count": int(candidate_count),
            "pending_review_count": int(pending_candidates) + int(pending_inferences),
            "unresolved_conflict_count": unresolved_conflict_count,
            "stale_memory_count": stale_memory_count,
            "invalidated_derived_count": int(invalidated_derived_count),
            "orphaned_evidence_count": int(orphaned_evidence_count),
            "unindexed_claim_count": int(unindexed_claim_count),
            "low_confidence_active_count": low_confidence_active_count,
            "high_salience_low_confidence_count": high_salience_low_confidence_count,
            "retrieval_judgment_count": int(retrieval_judgment_count),
            "recent_failure_count": int(recent_failure_count),
            "last_evaluation_score": last_evaluation_score,
        }

    def semantic_index_status(self, namespace: str, *, target_type: str | None = None) -> dict[str, Any]:
        params: list[Any] = [namespace]
        target_clause = ""
        if target_type:
            target_clause = " AND target_type = ?"
            params.append(target_type)
        rows = self.store.connection.execute(
            f"""
            SELECT
                target_type,
                provider,
                model,
                COALESCE(provider_type, 'unknown') AS provider_type,
                COALESCE(vector_store, 'sqlite_local') AS vector_store,
                COALESCE(index_version, 'legacy') AS index_version,
                COALESCE(status, 'indexed') AS status,
                count(*) AS count
            FROM embeddings
            WHERE namespace = ?
              {target_clause}
            GROUP BY target_type, provider, model, provider_type, vector_store, index_version, status
            ORDER BY target_type, provider, model, index_version, status
            """,
            params,
        ).fetchall()
        records = self.store.connection.execute(
            f"""
            SELECT
                target_type,
                provider,
                COALESCE(status, 'indexed') AS status,
                count(*) AS count
            FROM semantic_index_records
            WHERE namespace = ?
              {target_clause}
            GROUP BY target_type, provider, status
            ORDER BY target_type, provider, status
            """,
            params,
        ).fetchall()
        return {
            "namespace": namespace,
            "target_type": target_type,
            "vector_store": SQLiteVectorStore(self.store.connection).stats(namespace),
            "embeddings": [dict(row) for row in rows],
            "records": [dict(row) for row in records],
        }

    def verify_semantic_index(
        self,
        namespace: str,
        *,
        target_type: str = "claims",
        provider: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
    ) -> SemanticIndexRun:
        engine = provider_for_name(provider, model=model, dimension=dimension)
        now = utc_now_iso()
        rows = self.store.connection.execute(
            """
            SELECT id, target_id, dimension, vector_blob, input_hash
            FROM embeddings
            WHERE namespace = ?
              AND target_type = ?
              AND provider = ?
              AND model = ?
            """,
            (namespace, target_type, engine.name, engine.model),
        ).fetchall()
        verified = 0
        stale = 0
        warnings: list[str] = []
        with self.store.transaction():
            for row in rows:
                reason = None
                if row["vector_blob"] is None:
                    reason = "missing_vector"
                elif row["dimension"] != engine.dimension:
                    reason = "dimension_mismatch"
                elif not row["input_hash"]:
                    reason = "missing_input_hash"
                if reason:
                    stale += 1
                    self.store.connection.execute(
                        "UPDATE embeddings SET status = 'stale', stale_reason = ? WHERE id = ?",
                        (reason, row["id"]),
                    )
                else:
                    verified += 1
            self._write_audit(
                namespace=namespace,
                target_type="semantic_index",
                target_id=f"{target_type}:{engine.name}",
                action="semantic.verify",
                details={"verified_count": verified, "stale_count": stale, "model": engine.model},
            )
        if stale:
            warnings.append(f"{stale} vector record(s) were marked stale during verification.")
        return SemanticIndexRun(
            namespace=namespace,
            target_type=target_type,
            provider=engine.name,
            model=engine.model,
            indexed_count=0,
            skipped_count=0,
            stale_count=stale,
            verified_count=verified,
            provider_type=getattr(engine, "provider_type", "unknown"),
            vector_store="sqlite_local",
            status="verified" if not stale else "verified_with_stale",
            created_at=now,
            warnings=warnings,
        )

    def mark_stale_semantic_index(
        self,
        namespace: str,
        *,
        target_type: str = "claims",
        provider: str | None = None,
        model: str | None = None,
        reason: str = "manual",
    ) -> SemanticIndexRun:
        engine = provider_for_name(provider, model=model)
        now = utc_now_iso()
        with self.store.transaction():
            count = self._mark_stale_semantic_versions(
                namespace=namespace,
                target_type=target_type,
                provider=engine.name,
                model=engine.model,
                index_version=None,
                reason=reason,
            )
            self._write_audit(
                namespace=namespace,
                target_type="semantic_index",
                target_id=f"{target_type}:{engine.name}",
                action="semantic.mark_stale",
                details={"stale_count": count, "reason": reason},
            )
        return SemanticIndexRun(
            namespace=namespace,
            target_type=target_type,
            provider=engine.name,
            model=engine.model,
            indexed_count=0,
            skipped_count=0,
            stale_count=count,
            provider_type=getattr(engine, "provider_type", "unknown"),
            vector_store="sqlite_local",
            status="stale_marked",
            created_at=now,
        )

    def prune_stale_semantic_index(
        self,
        namespace: str,
        *,
        target_type: str = "claims",
        provider: str | None = None,
        model: str | None = None,
    ) -> SemanticIndexRun:
        engine = provider_for_name(provider, model=model)
        now = utc_now_iso()
        with self.store.transaction():
            count = self.store.connection.execute(
                """
                SELECT count(*) AS count
                FROM embeddings
                WHERE namespace = ?
                  AND target_type = ?
                  AND provider = ?
                  AND model = ?
                  AND COALESCE(status, 'indexed') = 'stale'
                """,
                (namespace, target_type, engine.name, engine.model),
            ).fetchone()["count"]
            self.store.connection.execute(
                """
                DELETE FROM embeddings
                WHERE namespace = ?
                  AND target_type = ?
                  AND provider = ?
                  AND model = ?
                  AND COALESCE(status, 'indexed') = 'stale'
                """,
                (namespace, target_type, engine.name, engine.model),
            )
            self._write_audit(
                namespace=namespace,
                target_type="semantic_index",
                target_id=f"{target_type}:{engine.name}",
                action="semantic.prune_stale",
                details={"pruned_count": count},
            )
        return SemanticIndexRun(
            namespace=namespace,
            target_type=target_type,
            provider=engine.name,
            model=engine.model,
            indexed_count=0,
            skipped_count=0,
            pruned_count=count,
            provider_type=getattr(engine, "provider_type", "unknown"),
            vector_store="sqlite_local",
            status="stale_pruned",
            created_at=now,
        )

    def _mark_stale_semantic_versions(
        self,
        *,
        namespace: str,
        target_type: str,
        provider: str,
        model: str,
        index_version: str | None,
        reason: str,
    ) -> int:
        params: list[Any] = [reason, namespace, target_type, provider, model]
        version_clause = ""
        if index_version:
            version_clause = " AND COALESCE(index_version, '') != ?"
            params.append(index_version)
        cursor = self.store.connection.execute(
            f"""
            UPDATE embeddings
            SET status = 'stale', stale_reason = ?
            WHERE namespace = ?
              AND target_type = ?
              AND provider = ?
              AND model = ?
              AND COALESCE(status, 'indexed') = 'indexed'
              {version_clause}
            """,
            params,
        )
        return cursor.rowcount if cursor.rowcount is not None else 0

    def _write_semantic_index_record(
        self,
        *,
        namespace: str,
        target_id: str,
        target_type: str,
        provider: str,
        model: str,
        dimension: int,
        provider_type: str,
        vector_store: str,
        index_version: str,
        content_hash: str,
        status: str,
        stale_reason: str | None,
        indexed_at: str,
    ) -> None:
        self.store.connection.execute(
            """
            INSERT INTO semantic_index_records (
                id, namespace, target_id, target_type, provider,
                indexed_at, status, metadata_json, model, dimension,
                provider_type, vector_store, index_version, content_hash, stale_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("sidx"),
                namespace,
                target_id,
                target_type,
                provider,
                indexed_at,
                status,
                json.dumps(
                    {
                        "model": model,
                        "dimension": dimension,
                        "provider_type": provider_type,
                        "vector_store": vector_store,
                        "index_version": index_version,
                        "content_hash": content_hash,
                        "stale_reason": stale_reason,
                    },
                    sort_keys=True,
                ),
                model,
                dimension,
                provider_type,
                vector_store,
                index_version,
                content_hash,
                stale_reason,
            ),
        )

    def _semantic_index_policy_decision(
        self,
        *,
        text: str,
        privacy_level: str,
        provider_external: bool,
        protected_mode_policy: str,
    ) -> tuple[bool, str, str | None]:
        private_levels = {"private", "sensitive", "secret"}
        if protected_mode_policy in {"no_sensitive_indexing", "index_public_and_personal_only"}:
            if privacy_level in private_levels:
                return False, text, "privacy_level_blocked"
        if protected_mode_policy == "local_only_sensitive" and provider_external and privacy_level in private_levels:
            return False, text, "external_provider_blocked_for_sensitive_content"
        if provider_external and privacy_level in private_levels and protected_mode_policy != "explicit_sensitive_indexing":
            return False, text, "external_provider_blocked_for_sensitive_content"
        if protected_mode_policy == "index_redacted_sensitive" and privacy_level in private_levels:
            return True, "[REDACTED]", None
        return True, text, None

    def _semantic_target_privacy_level(self, *, target_id: str, target_type: str) -> str:
        privacy_order = {"public": 0, "personal": 1, "private": 2, "sensitive": 2, "secret": 3}
        if target_type == "evidence":
            row = self.store.connection.execute(
                "SELECT privacy_level FROM evidence_events WHERE id = ?",
                (target_id,),
            ).fetchone()
            return row["privacy_level"] if row else "personal"
        if target_type == "candidate_claims":
            row = self.store.connection.execute(
                "SELECT privacy_level FROM candidate_claims WHERE id = ?",
                (target_id,),
            ).fetchone()
            return row["privacy_level"] if row else "personal"
        if target_type == "claims":
            rows = self.store.connection.execute(
                """
                SELECT ee.privacy_level
                FROM claim_evidence_links cel
                JOIN evidence_events ee ON ee.id = cel.evidence_id
                WHERE cel.claim_id = ?
                """,
                (target_id,),
            ).fetchall()
        elif target_type == "source_documents":
            rows = self.store.connection.execute(
                """
                SELECT ee.privacy_level
                FROM source_documents sd
                JOIN ingestion_batch_evidence_links ibel ON ibel.batch_id = sd.batch_id
                JOIN evidence_events ee ON ee.id = ibel.evidence_id
                WHERE sd.id = ?
                """,
                (target_id,),
            ).fetchall()
        else:
            rows = []
        if not rows:
            return "personal"
        return max((row["privacy_level"] for row in rows), key=lambda level: privacy_order.get(level, 1))

    def _semantic_targets(
        self,
        *,
        namespace: str,
        target_type: str,
        target_ids: list[str] | None,
    ) -> list[tuple[str, str]]:
        params: list[object] = [namespace]
        id_clause = ""
        if target_ids:
            id_clause = f" AND id IN ({','.join('?' for _ in target_ids)})"
            params.extend(target_ids)
        if target_type == "claims":
            rows = self.store.connection.execute(
                f"""
                SELECT *
                FROM claims
                WHERE namespace = ?
                  AND status NOT IN ('rejected', 'archived', 'superseded')
                  {id_clause}
                ORDER BY created_at ASC
                """,
                params,
            ).fetchall()
            return [
                (row["id"], claim_text(row["subject"], row["predicate"], row["object"]))
                for row in rows
            ]
        if target_type == "evidence":
            rows = self.store.connection.execute(
                f"""
                SELECT id, content
                FROM evidence_events
                WHERE namespace = ?
                  {id_clause}
                ORDER BY created_at ASC
                """,
                params,
            ).fetchall()
            return [(row["id"], row["content"]) for row in rows]
        if target_type == "candidate_claims":
            rows = self.store.connection.execute(
                f"""
                SELECT *
                FROM candidate_claims
                WHERE namespace = ?
                  AND candidate_status NOT IN ('rejected', 'invalid')
                  {id_clause}
                ORDER BY created_at ASC
                """,
                params,
            ).fetchall()
            return [
                (row["id"], claim_text(row["subject"], row["predicate"], row["object"]))
                for row in rows
            ]
        if target_type == "source_documents":
            source_id_clause = ""
            source_params: list[object] = [namespace]
            if target_ids:
                source_id_clause = f" AND sd.id IN ({','.join('?' for _ in target_ids)})"
                source_params.extend(target_ids)
            rows = self.store.connection.execute(
                f"""
                SELECT sd.id, ee.content
                FROM source_documents sd
                JOIN ingestion_batch_evidence_links ibel ON ibel.batch_id = sd.batch_id
                JOIN evidence_events ee ON ee.id = ibel.evidence_id
                WHERE sd.namespace = ?
                  {source_id_clause}
                ORDER BY sd.created_at ASC
                """,
                source_params,
            ).fetchall()
            return [(row["id"], row["content"]) for row in rows]
        return []

    def _semantic_scores_for_query(
        self,
        *,
        namespace: str,
        query: str,
        target_type: str,
        provider: str | None = None,
        target_ids: list[str] | None = None,
    ) -> dict[str, float]:
        if target_ids is not None and not target_ids:
            return {}
        engine = provider_for_name(provider)
        latest = self.store.connection.execute(
            """
            SELECT index_version, model, dimension
            FROM embeddings
            WHERE namespace = ?
              AND target_type = ?
              AND provider = ?
              AND model = ?
              AND COALESCE(status, 'indexed') = 'indexed'
              AND index_version IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (namespace, target_type, engine.name, engine.model),
        ).fetchone()
        if not latest:
            return {}
        engine = provider_for_name(provider, model=latest["model"], dimension=latest["dimension"])
        query_vector = engine.embed_texts(
            [query],
            namespace=namespace,
            privacy_level="personal",
            purpose="semantic_query",
            metadata={"target_type": target_type},
        )[0]
        results = SQLiteVectorStore(self.store.connection).search(
            namespace=namespace,
            query_vector=query_vector,
            target_type=target_type,
            provider=engine.name,
            model=engine.model,
            index_version=latest["index_version"],
            limit=len(target_ids) if target_ids is not None else 1000,
            filters={"target_ids": target_ids} if target_ids is not None else None,
        )
        return {result.target_id: result.score for result in results}

    def _retrieve_semantic_or_hybrid(
        self,
        *,
        namespace: str,
        query: str,
        mode: str,
        filters: dict,
        limit: int,
        provider: str | None = None,
    ) -> list[RetrievalResult]:
        limit = max(1, int(limit))
        candidate_limit = max(limit, min(max(limit * 20, 100), 1000))
        rows = self._governed_claim_rows(
            namespace=namespace,
            filters=filters,
            limit=candidate_limit,
        )
        semantic_scores = self._semantic_scores_for_query(
            namespace=namespace,
            query=query,
            target_type="claims",
            provider=provider,
            target_ids=[row["id"] for row in rows],
        )
        claim_ids = [row["id"] for row in rows]
        project_ids_by_claim = self._project_ids_for_claims(claim_ids)
        conflict_ids_by_claim = self._conflict_ids_for_claims(claim_ids)
        evidence_ids_by_claim = self._evidence_ids_for_claims(claim_ids)
        unresolved_conflict_claim_ids = self._claim_ids_with_unresolved_conflicts(claim_ids)
        duplicate_claim_ids = self._claim_ids_with_duplicate_relationships(claim_ids)
        scope_rows_by_claim = self._scope_rows_by_claim(claim_ids)
        results: list[RetrievalResult] = []
        for row in rows:
            project_ids = project_ids_by_claim.get(row["id"], [])
            project_id = filters.get("project_id")
            session_id = filters.get("session_id")
            if not self._scope_rows_match(
                scope_rows_by_claim.get(row["id"], []),
                query=query,
                project_id=project_id,
                session_id=session_id,
            ):
                continue
            lexical = lexical_score(
                query,
                [
                    row["subject"],
                    row["predicate"],
                    row["object"],
                    row["memory_type"],
                    claim_text(row["subject"], row["predicate"], row["object"]),
                ],
            )
            if not query.strip():
                lexical = 0.0
            semantic = semantic_scores.get(row["id"], 0.0)
            if mode == "semantic" and semantic_scores and semantic <= 0.0:
                continue
            score = self._hybrid_score_for_row(
                row=row,
                lexical=0.0 if mode == "semantic" and semantic_scores else lexical,
                semantic=semantic,
                project_relevance=1.0 if project_id and project_id in project_ids else 0.0,
                conflict_ids=conflict_ids_by_claim.get(row["id"], []),
                has_unresolved_conflict=row["id"] in unresolved_conflict_claim_ids,
                has_duplicate_relationship=row["id"] in duplicate_claim_ids,
            )
            if mode == "semantic" and not semantic_scores:
                score = lexical
            results.append(
                RetrievalResult(
                    claim_id=row["id"],
                    namespace=row["namespace"],
                    text=claim_text(row["subject"], row["predicate"], row["object"]),
                    subject=row["subject"],
                    predicate=row["predicate"],
                    object=row["object"],
                    memory_type=row["memory_type"],
                    status=row["status"],
                    score=score,
                    lexical_score=lexical,
                    confidence_base=row["confidence_base"],
                    confidence_effective=row["confidence_effective"],
                    importance=row["importance"],
                    created_at=row["created_at"],
                    last_verified_at=row["last_verified_at"],
                    evidence_ids=evidence_ids_by_claim.get(row["id"], []),
                    conflict_ids=conflict_ids_by_claim.get(row["id"], []),
                    project_ids=project_ids,
                    semantic_score=semantic,
                    retrieval_mode=mode,
                )
            )
        results.sort(
            key=lambda result: (
                -result.score,
                -result.semantic_score,
                -result.lexical_score,
                -result.confidence_effective,
                result.claim_id,
            )
        )
        return results[:limit]

    def _governed_claim_rows(
        self,
        *,
        namespace: str,
        filters: dict,
        limit: int | None = None,
    ) -> list[Any]:
        clauses, params = governed_claim_filter(namespace, filters, alias="c")
        if limit is not None:
            params.append(max(1, int(limit)))
            limit_clause = "LIMIT ?"
        else:
            limit_clause = ""
        rows = self.store.connection.execute(
            f"""
            SELECT c.*
            FROM claims c
            WHERE {' AND '.join(clauses)}
            ORDER BY c.created_at DESC, c.id ASC
            {limit_clause}
            """,
            params,
        ).fetchall()
        return rows

    def _hybrid_score_for_row(
        self,
        *,
        row,
        lexical: float,
        semantic: float,
        project_relevance: float,
        conflict_ids: list[str],
        has_unresolved_conflict: bool,
        has_duplicate_relationship: bool,
    ) -> float:
        unresolved_conflict = 1.0 if has_unresolved_conflict else 0.0
        duplicate_penalty = 1.0 if has_duplicate_relationship else 0.0
        return (
            0.25 * lexical
            + 0.25 * semantic
            + 0.15 * float(row["confidence_effective"])
            + 0.10 * float(row["importance"])
            + 0.08 * MEMORY_TYPE_PRIORITY.get(row["memory_type"], 0.50)
            + 0.07 * project_relevance
            + 0.05 * STATUS_PRIORITY.get(row["status"], 0.20)
            + 0.05 * recency_score(row["created_at"])
            - 0.20 * unresolved_conflict
            - 0.10 * duplicate_penalty
            - (0.05 if conflict_ids and row["status"] != "active" else 0.0)
        )

    def _has_duplicate_relationship(self, claim_id: str) -> bool:
        row = self.store.connection.execute(
            """
            SELECT 1
            FROM claim_relationships
            WHERE relationship_type = 'duplicate_of'
              AND (source_claim_id = ? OR target_claim_id = ?)
            LIMIT 1
            """,
            (claim_id, claim_id),
        ).fetchone()
        return row is not None

    def _project_ids_for_claim(self, claim_id: str) -> list[str]:
        rows = self.store.connection.execute(
            """
            SELECT project_id
            FROM project_claim_links
            WHERE claim_id = ?
            ORDER BY project_id
            """,
            (claim_id,),
        ).fetchall()
        return [row["project_id"] for row in rows]

    def _project_ids_for_claims(self, claim_ids: list[str]) -> dict[str, list[str]]:
        if not claim_ids:
            return {}
        rows = self.store.connection.execute(
            f"""
            SELECT claim_id, project_id
            FROM project_claim_links
            WHERE claim_id IN ({','.join('?' for _ in claim_ids)})
            ORDER BY claim_id, project_id
            """,
            claim_ids,
        ).fetchall()
        return self._group_row_values(rows, "claim_id", "project_id")

    def _conflict_ids_for_claim(self, claim_id: str) -> list[str]:
        rows = self.store.connection.execute(
            """
            SELECT conflict_id
            FROM conflict_family_claims
            WHERE claim_id = ?
            UNION
            SELECT conflict_id
            FROM conflict_claim_links
            WHERE claim_id = ?
            ORDER BY conflict_id
            """,
            (claim_id, claim_id),
        ).fetchall()
        return [row["conflict_id"] for row in rows]

    def _conflict_ids_for_claims(self, claim_ids: list[str]) -> dict[str, list[str]]:
        if not claim_ids:
            return {}
        placeholders = ",".join("?" for _ in claim_ids)
        rows = self.store.connection.execute(
            f"""
            SELECT claim_id, conflict_id
            FROM conflict_family_claims
            WHERE claim_id IN ({placeholders})
            UNION
            SELECT claim_id, conflict_id
            FROM conflict_claim_links
            WHERE claim_id IN ({placeholders})
            ORDER BY claim_id, conflict_id
            """,
            [*claim_ids, *claim_ids],
        ).fetchall()
        return self._group_row_values(rows, "claim_id", "conflict_id")

    def _claim_ids_with_unresolved_conflicts(self, claim_ids: list[str]) -> set[str]:
        if not claim_ids:
            return set()
        rows = self.store.connection.execute(
            f"""
            SELECT DISTINCT cfc.claim_id
            FROM conflict_family_claims cfc
            JOIN conflict_families cf ON cf.id = cfc.conflict_id
            WHERE cfc.claim_id IN ({','.join('?' for _ in claim_ids)})
              AND cf.status = 'unresolved'
            """,
            claim_ids,
        ).fetchall()
        return {row["claim_id"] for row in rows}

    def _claim_ids_with_duplicate_relationships(self, claim_ids: list[str]) -> set[str]:
        if not claim_ids:
            return set()
        placeholders = ",".join("?" for _ in claim_ids)
        rows = self.store.connection.execute(
            f"""
            SELECT DISTINCT source_claim_id AS claim_id
            FROM claim_relationships
            WHERE relationship_type = 'duplicate_of'
              AND source_claim_id IN ({placeholders})
            UNION
            SELECT DISTINCT target_claim_id AS claim_id
            FROM claim_relationships
            WHERE relationship_type = 'duplicate_of'
              AND target_claim_id IN ({placeholders})
            """,
            [*claim_ids, *claim_ids],
        ).fetchall()
        return {row["claim_id"] for row in rows}

    def _session_continuity_results(
        self,
        *,
        namespace: str,
        session_id: str,
        project_id: str | None,
    ) -> list[RetrievalResult]:
        try:
            session = self.get_session(session_id)
        except NotFoundError:
            return []
        continuity_project_id = project_id or session.project_id
        if not continuity_project_id:
            return []
        return self.retrieve(
            namespace=namespace,
            query="",
            limit=10,
            memory_types=["session_summary"],
            project_id=continuity_project_id,
            recompute_confidence=False,
        )

    def _estimate_tokens(self, text: str) -> int:
        return max(1, math.ceil(len(text) / 4))

    def _estimate_warning_tokens(self, warnings: list[ContextWarning]) -> int:
        return sum(self._estimate_tokens(warning.text) for warning in warnings)

    def _write_retrieval_log(
        self,
        *,
        namespace: str,
        query: str,
        session_id: str | None,
        project_id: str | None,
        result_count: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.store.connection.execute(
            """
            INSERT INTO retrieval_log (
                id, namespace, query, session_id, project_id, result_count,
                created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("ret"),
                namespace,
                query,
                session_id,
                project_id,
                result_count,
                utc_now_iso(),
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )

    def _write_context_pack_log(
        self,
        *,
        context_pack_id: str | None = None,
        namespace: str,
        query: str,
        session_id: str | None,
        project_id: str | None,
        token_budget: int,
        item_count: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.store.connection.execute(
            """
            INSERT INTO context_pack_log (
                id, namespace, query, session_id, project_id, token_budget,
                item_count, created_at, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                context_pack_id or new_id("ctx"),
                namespace,
                query,
                session_id,
                project_id,
                token_budget,
                item_count,
                utc_now_iso(),
                json.dumps(metadata or {}, sort_keys=True),
            ),
        )

    def _link_claim_to_project(
        self,
        *,
        namespace: str,
        project_id: str,
        claim_id: str,
        relation: str,
    ) -> None:
        self.store.connection.execute(
            """
            INSERT OR IGNORE INTO project_claim_links (
                namespace, project_id, claim_id, relation, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (namespace, project_id, claim_id, relation, utc_now_iso()),
        )

    def _link_claim_to_session(
        self,
        *,
        session_id: str,
        claim_id: str,
        relation: str,
    ) -> None:
        self.store.connection.execute(
            """
            INSERT OR IGNORE INTO session_claim_links (
                session_id, claim_id, relation, created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (session_id, claim_id, relation, utc_now_iso()),
        )

    def _claim_ids_for_project(self, namespace: str, project_id: str) -> list[str]:
        rows = self.store.connection.execute(
            """
            SELECT claim_id
            FROM project_claim_links
            WHERE namespace = ? AND project_id = ?
            ORDER BY claim_id
            """,
            (namespace, project_id),
        ).fetchall()
        return [row["claim_id"] for row in rows]

    def _infer_project_id(self, subject: str) -> str | None:
        if subject.startswith("project:") and len(subject) > len("project:"):
            return subject.split(":", 1)[1]
        return None

    def _validate_claim_input(self, **values: str) -> None:
        for key, value in values.items():
            if key == "status":
                if value not in CLAIM_STATUSES:
                    raise ValidationError(f"Unknown claim status: {value}")
                continue
            self._require_text(value, key)

    def _require_text(self, value: str, name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"{name} must be a non-empty string.")

    def _index_claim(
        self,
        *,
        claim_id: str,
        namespace: str,
        subject: str,
        predicate: str,
        object: str,
        memory_type: str,
    ) -> None:
        if production.should_skip_claim_index(self, namespace=namespace, claim_id=claim_id):
            return
        self.store.connection.execute(
            """
            INSERT INTO claims_fts (
                claim_id, namespace, subject, predicate, object, memory_type, content
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                claim_id,
                namespace,
                subject,
                predicate,
                object,
                memory_type,
                claim_text(subject, predicate, object),
            ),
        )

    def _write_audit(
        self,
        *,
        namespace: str,
        target_type: str,
        target_id: str,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.store.connection.execute(
            """
            INSERT INTO audit_log (id, namespace, target_type, target_id, action, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("aud"),
                namespace,
                target_type,
                target_id,
                action,
                json.dumps(details or {}, sort_keys=True),
                utc_now_iso(),
            ),
        )

    def _evidence_ids_for_claim(self, claim_id: str) -> list[str]:
        rows = self.store.connection.execute(
            """
            SELECT evidence_id
            FROM claim_evidence_links
            WHERE claim_id = ?
            ORDER BY evidence_id
            """,
            (claim_id,),
        ).fetchall()
        return [row["evidence_id"] for row in rows]

    def _evidence_ids_for_claims(self, claim_ids: list[str]) -> dict[str, list[str]]:
        if not claim_ids:
            return {}
        rows = self.store.connection.execute(
            f"""
            SELECT claim_id, evidence_id
            FROM claim_evidence_links
            WHERE claim_id IN ({','.join('?' for _ in claim_ids)})
            ORDER BY claim_id, evidence_id
            """,
            claim_ids,
        ).fetchall()
        return self._group_row_values(rows, "claim_id", "evidence_id")

    @staticmethod
    def _group_row_values(rows, key_field: str, value_field: str) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for row in rows:
            grouped.setdefault(row[key_field], []).append(row[value_field])
        return grouped

    def _claim_ids_for_conflict(self, conflict_id: str) -> list[str]:
        rows = self.store.connection.execute(
            """
            SELECT claim_id
            FROM conflict_claim_links
            WHERE conflict_id = ?
            ORDER BY claim_id
            """,
            (conflict_id,),
        ).fetchall()
        return [row["claim_id"] for row in rows]

    def _claim_ids_for_conflict_family(self, conflict_id: str) -> list[str]:
        rows = self.store.connection.execute(
            """
            SELECT claim_id
            FROM conflict_family_claims
            WHERE conflict_id = ?
            ORDER BY claim_id
            """,
            (conflict_id,),
        ).fetchall()
        if rows:
            return [row["claim_id"] for row in rows]
        return self._claim_ids_for_conflict(conflict_id)

    def _create_or_update_conflict(
        self,
        *,
        namespace: str,
        subject: str,
        predicate: str,
        claim_ids: list[str],
        conflict_type: str = "direct_value_conflict",
        mark_disputed: bool = True,
    ) -> Conflict:
        row = self.store.connection.execute(
            """
            SELECT *
            FROM conflict_families
            WHERE namespace = ?
              AND subject = ?
              AND predicate = ?
              AND conflict_type = ?
              AND status = 'unresolved'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (namespace, subject, predicate, conflict_type),
        ).fetchone()
        now = utc_now_iso()
        with self.store.transaction():
            if row:
                conflict_id = row["id"]
            else:
                conflict_id = new_id("conf")
                self.store.connection.execute(
                    """
                    INSERT INTO conflicts (
                        id, namespace, subject, predicate, status, active_claim_id,
                        resolution_note, created_at, resolved_at
                    )
                    VALUES (?, ?, ?, ?, 'unresolved', NULL, NULL, ?, NULL)
                    """,
                    (conflict_id, namespace, subject, predicate, now),
                )
                self.store.connection.execute(
                    """
                    INSERT INTO conflict_families (
                        id, namespace, subject, predicate, conflict_type, status,
                        active_claim_id, resolution_strategy, resolution_note,
                        created_at, updated_at, resolved_at
                    )
                    VALUES (?, ?, ?, ?, ?, 'unresolved', NULL, NULL, NULL, ?, ?, NULL)
                    """,
                    (conflict_id, namespace, subject, predicate, conflict_type, now, now),
                )
            for linked_claim_id in claim_ids:
                self.store.connection.execute(
                    """
                    INSERT OR IGNORE INTO conflict_claim_links (conflict_id, claim_id)
                    VALUES (?, ?)
                    """,
                    (conflict_id, linked_claim_id),
                )
                self.store.connection.execute(
                    """
                    INSERT OR IGNORE INTO conflict_family_claims (
                        conflict_id, claim_id, role, created_at
                    )
                    VALUES (?, ?, 'member', ?)
                    """,
                    (conflict_id, linked_claim_id, now),
                )
                if mark_disputed:
                    linked_claim = self.read_claim(linked_claim_id)
                    if linked_claim.status == "core":
                        self._write_audit(
                            namespace=namespace,
                            target_type="claim",
                            target_id=linked_claim_id,
                            action="conflict.detect.core_preserved",
                            details={
                                "conflict_id": conflict_id,
                                "conflict_type": conflict_type,
                            },
                        )
                    else:
                        self._set_claim_status(
                            claim_id=linked_claim_id,
                            status="disputed",
                            action="conflict.detect",
                            details={
                                "conflict_id": conflict_id,
                                "conflict_type": conflict_type,
                            },
                        )
                self._write_audit(
                    namespace=namespace,
                    target_type="claim",
                    target_id=linked_claim_id,
                    action="conflict.detect",
                    details={"conflict_id": conflict_id, "conflict_type": conflict_type},
                )
            self._write_audit(
                namespace=namespace,
                target_type="conflict",
                target_id=conflict_id,
                action="conflict.detect",
                details={"claim_ids": claim_ids, "conflict_type": conflict_type},
            )
        return self.read_conflict(conflict_id)

    def _set_claim_status(
        self,
        *,
        claim_id: str,
        status: str,
        action: str,
        details: dict[str, Any],
    ) -> None:
        claim = self.read_claim(claim_id)
        self.store.connection.execute(
            "UPDATE claims SET status = ? WHERE id = ?",
            (status, claim_id),
        )
        if claim.status != status:
            self._write_status_history(
                namespace=claim.namespace,
                claim_id=claim_id,
                old_status=claim.status,
                new_status=status,
                reason=str(details.get("reason") or action),
                actor=str(details.get("actor") or "system"),
            )
        self._write_audit(
            namespace=claim.namespace,
            target_type="claim",
            target_id=claim_id,
            action=action,
            details=details,
        )
        if claim.status != status and status in {"rejected", "superseded", "archived"}:
            self.invalidate_derived(
                namespace=claim.namespace,
                source_id=claim_id,
                source_type="claim",
                reason=str(details.get("reason") or f"claim status changed to {status}"),
                mode="mark_stale",
            )

    def _write_status_history(
        self,
        *,
        namespace: str,
        claim_id: str,
        old_status: str | None,
        new_status: str,
        reason: str,
        actor: str,
    ) -> None:
        self.store.connection.execute(
            """
            INSERT INTO claim_status_history (
                id, namespace, claim_id, old_status, new_status, reason, changed_by, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("hist"),
                namespace,
                claim_id,
                old_status,
                new_status,
                reason,
                actor,
                utc_now_iso(),
            ),
        )

    def _apply_feedback_to_claim(
        self,
        claim_id: str,
        signal: str,
        source: str,
        evidence_id: str | None,
        strength: float,
    ) -> None:
        claim = self.read_claim(claim_id)
        now = utc_now_iso()
        new_confidence = claim.confidence_base
        new_status = claim.status
        last_verified_at = claim.last_verified_at
        if signal in {"confirmed", "verified"}:
            amount = 0.12 if signal == "verified" else 0.08
            new_confidence = min(claim.confidence_base + amount * strength, 1.0)
            if source != "assistant" or evidence_id:
                last_verified_at = now
            if claim.status == "candidate" and new_confidence >= 0.65:
                new_status = "active"
        elif signal in {"wrong"}:
            new_confidence = max(claim.confidence_base - 0.50 * strength, 0.0)
            new_status = "rejected" if strength >= 0.5 else "disputed"
        elif signal in {"contradicted"}:
            new_confidence = max(claim.confidence_base - 0.25 * strength, 0.0)
            new_status = "disputed"
        elif signal in {"stale"}:
            new_confidence = max(claim.confidence_base - 0.12 * strength, 0.0)
        elif signal == "important":
            new_confidence = min(claim.confidence_base + 0.03 * strength, 1.0)
        elif signal == "unimportant":
            new_confidence = max(claim.confidence_base - 0.03 * strength, 0.0)
        self.store.connection.execute(
            """
            UPDATE claims
            SET confidence_base = ?,
                status = ?,
                last_verified_at = ?
            WHERE id = ?
            """,
            (new_confidence, new_status, last_verified_at, claim_id),
        )
        if claim.status != new_status:
            self._write_status_history(
                namespace=claim.namespace,
                claim_id=claim_id,
                old_status=claim.status,
                new_status=new_status,
                reason=f"feedback.{signal}",
                actor=source,
            )

    def _promotion_failures(
        self,
        claim: Claim,
        snapshot: ConfidenceSnapshot,
        target_status: str,
    ) -> list[str]:
        failures: list[str] = []
        if claim.status in {"rejected", "superseded"}:
            failures.append(f"claim is {claim.status}")
        if claim.status == "disputed" and self._has_unresolved_conflicts(claim.id):
            failures.append("claim is disputed in an unresolved conflict")
        if not claim.evidence_ids:
            failures.append("claim has no evidence")
        if self._has_unresolved_conflicts(claim.id):
            failures.append("claim belongs to an unresolved conflict")
        if target_status == "active":
            if snapshot.effective_confidence < 0.65:
                failures.append("effective confidence is below 0.65")
            if claim.importance < 0.30:
                failures.append("importance is below 0.30")
        if target_status == "core":
            if snapshot.effective_confidence < 0.85:
                failures.append("effective confidence is below 0.85")
            if claim.importance < 0.70:
                failures.append("importance is below 0.70")
            if claim.memory_type in {"current_task", "task", "temporary_preference", "inference"}:
                failures.append("memory type is not durable enough for core")
        return failures

    def _has_unresolved_conflicts(self, claim_id: str) -> bool:
        row = self.store.connection.execute(
            """
            SELECT 1
            FROM conflict_family_claims cfc
            JOIN conflict_families cf ON cf.id = cfc.conflict_id
            WHERE cfc.claim_id = ?
              AND cf.status = 'unresolved'
            LIMIT 1
            """,
            (claim_id,),
        ).fetchone()
        return row is not None

    def _coerce_time(self, value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return parse_iso(value.isoformat())
        return parse_iso(value)

    def _time_arg_to_text(self, value: datetime | str | None) -> str | None:
        if value is None:
            return None
        parsed = self._coerce_time(value)
        return parsed.isoformat() if parsed else str(value)

    def _half_life_for_claim(self, claim: Claim) -> float:
        row = self.store.connection.execute(
            """
            SELECT *
            FROM half_life_policies
            WHERE (namespace = ? OR namespace IS NULL)
              AND (memory_type = ? OR memory_type IS NULL)
              AND (predicate = ? OR predicate IS NULL)
            ORDER BY
              namespace IS NULL ASC,
              predicate IS NULL ASC,
              memory_type IS NULL ASC,
              updated_at DESC
            LIMIT 1
            """,
            (claim.namespace, claim.memory_type, claim.predicate),
        ).fetchone()
        default_half_life = float(DEFAULT_HALF_LIVES.get(claim.memory_type, 180.0))
        if row and not str(row["id"]).startswith("hlp_default_"):
            return float(row["half_life_days"])
        if claim.half_life_days and float(claim.half_life_days) != default_half_life:
            return float(claim.half_life_days)
        if row:
            return float(row["half_life_days"])
        return default_half_life

    def _source_reliability_factor(self, claim: Claim) -> float:
        rows = self.store.connection.execute(
            """
            SELECT e.trust_level, e.source_type
            FROM claim_evidence_links l
            JOIN evidence_events e ON e.id = l.evidence_id
            WHERE l.claim_id = ?
            """,
            (claim.id,),
        ).fetchall()
        if not rows:
            return 0.85
        factors = []
        for row in rows:
            trust_level = row["trust_level"] or "unknown"
            source_type = row["source_type"] or "unknown"
            factor = {
                "tool_verified": 1.08,
                "user_confirmed": 1.05,
                "user_asserted": 1.00,
                "external_verified": 1.10,
                "imported": 0.90,
                "model_generated": 0.75,
                "unknown": 0.90,
            }.get(trust_level, 0.90)
            if source_type in {"assistant", "model"}:
                factor = min(factor, 0.80)
            factors.append(factor)
        return max(0.50, min(sum(factors) / len(factors), 1.15))

    def _feedback_factor(self, claim_id: str) -> float:
        rows = self.store.connection.execute(
            "SELECT * FROM feedback WHERE target_type = 'claim' AND target_id = ?",
            (claim_id,),
        ).fetchall()
        factor = 1.0
        for row in rows:
            strength = float(row["strength"] or 1.0)
            signal = row["signal"]
            if signal == "confirmed":
                factor += 0.08 * strength
            elif signal == "verified":
                factor += 0.14 * strength
            elif signal == "wrong":
                factor *= max(0.05, 1.0 - 0.85 * strength)
            elif signal == "contradicted":
                factor *= max(0.20, 1.0 - 0.35 * strength)
            elif signal == "stale":
                factor *= max(0.50, 1.0 - 0.18 * strength)
            elif signal == "important":
                factor += 0.04 * strength
            elif signal == "unimportant":
                factor *= max(0.70, 1.0 - 0.10 * strength)
        return max(0.05, min(factor, 1.40))

    def _usefulness_factor(self, claim_id: str) -> float:
        rows = self.store.connection.execute(
            "SELECT signal, strength FROM feedback WHERE target_type = 'claim' AND target_id = ?",
            (claim_id,),
        ).fetchall()
        factor = 1.0
        for row in rows:
            strength = float(row["strength"] or 1.0)
            signal = row["signal"]
            if signal == "useful":
                factor += 0.25 * strength
            elif signal == "not_useful":
                factor *= max(0.30, 1.0 - 0.35 * strength)
            elif signal == "irrelevant":
                factor *= max(0.20, 1.0 - 0.50 * strength)
            elif signal == "important":
                factor += 0.35 * strength
            elif signal == "unimportant":
                factor *= max(0.30, 1.0 - 0.35 * strength)
            elif signal == "stale":
                factor *= max(0.40, 1.0 - 0.30 * strength)
        return max(0.05, min(factor, 1.60))

    def _contradiction_factor(self, claim: Claim) -> float:
        if claim.status == "rejected":
            return 0.05
        if claim.status == "superseded":
            return 0.10
        if claim.status == "archived":
            return 0.25
        rows = self.store.connection.execute(
            """
            SELECT cf.*
            FROM conflict_families cf
            JOIN conflict_family_claims cfc ON cfc.conflict_id = cf.id
            WHERE cfc.claim_id = ?
            """,
            (claim.id,),
        ).fetchall()
        if any(row["status"] == "unresolved" for row in rows):
            return 0.40
        if claim.status == "disputed":
            return 0.65
        if any(row["active_claim_id"] == claim.id for row in rows):
            return 1.0
        if any(row["status"] in {"context_scoped", "time_scoped"} for row in rows):
            return 1.0 if self.list_claim_scopes(claim.id) else 0.65
        return 1.0

    def _verification_factor(self, claim: Claim) -> float:
        factor = 1.05 if claim.last_verified_at else 1.0
        rows = self.store.connection.execute(
            """
            SELECT strength
            FROM feedback
            WHERE target_type = 'claim'
              AND target_id = ?
              AND signal = 'verified'
            """,
            (claim.id,),
        ).fetchall()
        for row in rows:
            factor += 0.05 * float(row["strength"] or 1.0)
        return max(1.0, min(factor, 1.20))

    def _retrieval_salience(
        self,
        *,
        claim: Claim,
        age_days: float,
        usefulness_factor: float,
    ) -> float:
        recency_salience = 1 / (1 + age_days / 30.0)
        status_factor = {
            "core": 1.0,
            "active": 0.80,
            "candidate": 0.30,
            "disputed": 0.10,
            "archived": 0.05,
            "superseded": 0.0,
            "rejected": 0.0,
        }.get(claim.status, 0.20)
        scope_factor = 0.65 if self.list_claim_scopes(claim.id) else 1.0
        return self._clamp(
            claim.importance
            * recency_salience
            * usefulness_factor
            * status_factor
            * scope_factor
        )

    def _persist_confidence_snapshot(
        self,
        *,
        namespace: str,
        snapshot: ConfidenceSnapshot,
        old_truth_confidence: float | None,
        old_retrieval_salience: float | None,
        event_type: str,
        reason: str,
    ) -> None:
        self.store.connection.execute(
            """
            UPDATE claims
            SET confidence_effective = ?,
                half_life_days = ?
            WHERE id = ?
            """,
            (snapshot.effective_confidence, snapshot.half_life_days, snapshot.claim_id),
        )
        snapshot_id = new_id("snap")
        self.store.connection.execute(
            """
            INSERT INTO confidence_snapshots (
                id, namespace, claim_id, truth_confidence, retrieval_salience,
                base_confidence, effective_confidence, decay_factor,
                source_reliability_factor, feedback_factor, contradiction_factor,
                verification_factor, half_life_days, age_days, explanation, computed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                namespace,
                snapshot.claim_id,
                snapshot.truth_confidence,
                snapshot.retrieval_salience,
                snapshot.base_confidence,
                snapshot.effective_confidence,
                snapshot.decay_factor,
                snapshot.source_reliability_factor,
                snapshot.feedback_factor,
                snapshot.contradiction_factor,
                snapshot.verification_factor,
                snapshot.half_life_days,
                snapshot.age_days,
                snapshot.explanation,
                snapshot.computed_at,
            ),
        )
        self.store.connection.execute(
            """
            INSERT INTO confidence_events (
                id, namespace, claim_id, event_type, old_truth_confidence,
                new_truth_confidence, old_retrieval_salience, new_retrieval_salience,
                reason, metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("cevt"),
                namespace,
                snapshot.claim_id,
                event_type,
                old_truth_confidence,
                snapshot.truth_confidence,
                old_retrieval_salience,
                snapshot.retrieval_salience,
                reason,
                json.dumps({"snapshot_id": snapshot_id}, sort_keys=True),
                utc_now_iso(),
            ),
        )

    def _create_relationship(
        self,
        *,
        source_claim_id: str,
        target_claim_id: str,
        relationship_type: str,
        reason: str | None,
        confidence: float = 1.0,
    ) -> ClaimRelationship:
        if relationship_type not in RELATIONSHIP_TYPES:
            raise ValidationError(f"Unknown relationship type: {relationship_type}")
        source = self.read_claim(source_claim_id)
        target = self.read_claim(target_claim_id)
        if source.namespace != target.namespace:
            raise ValidationError("Related claims must share a namespace.")
        relationship_id = new_id("rel")
        now = utc_now_iso()
        self.store.connection.execute(
            """
            INSERT OR IGNORE INTO claim_relationships (
                id, namespace, source_claim_id, target_claim_id, relationship_type,
                confidence, reason, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relationship_id,
                source.namespace,
                source_claim_id,
                target_claim_id,
                relationship_type,
                confidence,
                reason,
                now,
            ),
        )
        row = self.store.connection.execute(
            """
            SELECT *
            FROM claim_relationships
            WHERE source_claim_id = ?
              AND target_claim_id = ?
              AND relationship_type = ?
            """,
            (source_claim_id, target_claim_id, relationship_type),
        ).fetchone()
        return ClaimRelationship.from_row(row)

    def _scope_claim_in_transaction(
        self,
        *,
        claim_id: str,
        scope_type: str,
        applies_when: str | None,
        valid_from: str | None,
        valid_to: str | None,
        reason: str,
        activate: bool,
    ) -> ClaimScope:
        claim = self.read_claim(claim_id)
        scope_id = new_id("scope")
        now = utc_now_iso()
        self.store.connection.execute(
            """
            INSERT INTO claim_scopes (
                id, namespace, claim_id, scope_type, applies_when,
                valid_from, valid_to, reason, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scope_id,
                claim.namespace,
                claim_id,
                scope_type,
                applies_when,
                valid_from,
                valid_to,
                reason,
                now,
            ),
        )
        if activate and claim.status == "disputed" and not self._has_unresolved_conflicts(claim_id):
            self._set_claim_status(
                claim_id=claim_id,
                status="active",
                action="claim.scope",
                details={"reason": reason, "scope_type": scope_type, "applies_when": applies_when},
            )
        self._write_audit(
            namespace=claim.namespace,
            target_type="claim",
            target_id=claim_id,
            action="claim.scope",
            details={
                "scope_type": scope_type,
                "applies_when": applies_when,
                "valid_from": valid_from,
                "valid_to": valid_to,
                "reason": reason,
            },
        )
        return ClaimScope(
            id=scope_id,
            namespace=claim.namespace,
            claim_id=claim_id,
            scope_type=scope_type,
            applies_when=applies_when,
            valid_from=valid_from,
            valid_to=valid_to,
            reason=reason,
            created_at=now,
        )

    def _scope_matches_claim(
        self,
        claim_id: str,
        *,
        query: str,
        project_id: str | None,
        session_id: str | None,
    ) -> bool:
        scopes = self.list_claim_scopes(claim_id)
        return self._scope_rows_match(
            scopes,
            query=query,
            project_id=project_id,
            session_id=session_id,
        )

    def _filter_results_by_scope(
        self,
        results: list[RetrievalResult],
        *,
        query: str,
        project_id: str | None,
        session_id: str | None,
    ) -> list[RetrievalResult]:
        scope_rows_by_claim = self._scope_rows_by_claim([result.claim_id for result in results])
        return [
            result
            for result in results
            if self._scope_rows_match(
                scope_rows_by_claim.get(result.claim_id, []),
                query=query,
                project_id=project_id,
                session_id=session_id,
            )
        ]

    def _scope_rows_by_claim(self, claim_ids: list[str]) -> dict[str, list[ClaimScope]]:
        if not claim_ids:
            return {}
        rows = self.store.connection.execute(
            f"""
            SELECT *
            FROM claim_scopes
            WHERE claim_id IN ({','.join('?' for _ in claim_ids)})
            ORDER BY claim_id, created_at ASC
            """,
            claim_ids,
        ).fetchall()
        scopes_by_claim: dict[str, list[ClaimScope]] = {}
        for row in rows:
            scopes_by_claim.setdefault(row["claim_id"], []).append(ClaimScope.from_row(row))
        return scopes_by_claim

    def _scope_rows_match(
        self,
        scopes: list[ClaimScope],
        *,
        query: str,
        project_id: str | None,
        session_id: str | None,
    ) -> bool:
        if not scopes:
            return True
        now = utc_now()
        for scope in scopes:
            if scope.valid_from and (parse_iso(scope.valid_from) or now) > now:
                continue
            if scope.valid_to and (parse_iso(scope.valid_to) or now) < now:
                continue
            if scope.scope_type == "project":
                if scope.applies_when in {None, project_id}:
                    return True
                continue
            if scope.scope_type == "session":
                if scope.applies_when in {None, session_id}:
                    return True
                continue
            if self._scope_matches_text(scope.applies_when, query):
                return True
        return False

    def _scope_matches_text(self, applies_when: str | None, query: str) -> bool:
        if not applies_when:
            return True
        normalized_query = query.lower().replace("-", "_")
        normalized_scope = applies_when.lower()
        if normalized_scope in normalized_query:
            return True
        query_terms = set(normalized_query.replace("/", "_").split())
        scope_terms = set(normalized_scope.replace("/", "_").split("_"))
        if scope_terms & query_terms:
            return True
        aliases = {
            "architecture_or_design_request": {
                "architecture",
                "design",
                "contract",
                "plan",
                "spec",
                "system",
                "implementation",
            },
            "progress_update": {"progress", "update", "status", "brief", "milestone"},
            "architecture_contract": {
                "architecture",
                "architectural",
                "design",
                "contract",
                "contracts",
                "spec",
                "specification",
            },
        }
        return bool(aliases.get(normalized_scope, set()) & query_terms)

    def _scope_label(self, claim_id: str) -> str | None:
        scopes = self.list_claim_scopes(claim_id)
        if not scopes:
            return None
        return ", ".join(scope.applies_when or scope.scope_type for scope in scopes)

    def _select_active_claim_for_strategy(
        self,
        family: ConflictFamily,
        strategy: str,
    ) -> str | None:
        claims = [self.read_claim(claim_id) for claim_id in family.claim_ids]
        if not claims:
            return None
        if strategy in {"context_scope", "time_scope", "mark_unresolved"}:
            return family.active_claim_id
        if strategy == "latest_wins":
            return max(claims, key=lambda claim: claim.created_at).id
        if strategy in {"highest_confidence_wins", "merge_duplicates", "reject_weak_claims"}:
            return max(claims, key=lambda claim: self.compute_confidence(claim.id).effective_confidence).id
        if strategy == "user_correction_wins":
            correction = [claim for claim in claims if claim.memory_type == "correction"]
            return max(correction or claims, key=lambda claim: claim.created_at).id
        if strategy == "verified_source_wins":
            return max(claims, key=self._source_reliability_factor).id
        return family.active_claim_id

    def _conflict_type_for_claims(self, claims: list[Claim]) -> str:
        if any(claim.memory_type == "correction" for claim in claims):
            return "user_correction_conflict"
        if any(self._source_reliability_factor(claim) >= 1.05 for claim in claims):
            return "verified_fact_conflict"
        if any(claim.memory_type in {"project_state", "current_task", "task"} for claim in claims):
            return "temporal_state_conflict"
        if all(claim.memory_type == "preference" for claim in claims):
            return "contextual_preference_conflict"
        return "direct_value_conflict"

    def _link_duplicate_claims(self, claims: list[Claim]) -> None:
        ordered = sorted(claims, key=lambda claim: (claim.created_at, claim.id))
        canonical = ordered[0]
        for duplicate in ordered[1:]:
            self._create_relationship(
                source_claim_id=duplicate.id,
                target_claim_id=canonical.id,
                relationship_type="duplicate_of",
                reason="M2 duplicate detection.",
            )

    def _write_curation_decision(
        self,
        *,
        namespace: str,
        claim_id: str | None,
        decision_type: str,
        target_status: str | None,
        reason: str,
        confidence_before: float | None,
        confidence_after: float | None,
        dry_run: bool,
        applied: bool,
        force: bool,
        metadata: dict[str, Any],
        persist: bool = True,
    ) -> CurationDecision:
        decision_id = new_id("cur")
        now = utc_now_iso()
        decision = CurationDecision(
            id=decision_id,
            namespace=namespace,
            claim_id=claim_id,
            decision_type=decision_type,
            target_status=target_status,
            reason=reason,
            confidence_before=confidence_before,
            confidence_after=confidence_after,
            dry_run=dry_run,
            applied=applied,
            force=force,
            metadata=metadata,
            created_at=now,
        )
        old_status = metadata.get("old_status")
        if old_status is None and claim_id:
            try:
                old_status = self.read_claim(claim_id).status
            except NotFoundError:
                old_status = None
        if persist:
            self.store.connection.execute(
                """
                INSERT INTO curation_decisions (
                    id, namespace, claim_id, decision_type, old_status,
                    proposed_status, target_status, reason,
                    confidence_before, confidence_after, dry_run, applied, force,
                    metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.id,
                    decision.namespace,
                    decision.claim_id,
                    decision.decision_type,
                    old_status,
                    decision.target_status,
                    decision.target_status,
                    decision.reason,
                    decision.confidence_before,
                    decision.confidence_after,
                    int(decision.dry_run),
                    int(decision.applied),
                    int(decision.force),
                    json.dumps(decision.metadata, sort_keys=True),
                    decision.created_at,
                ),
            )
        return decision

    def _clamp(self, value: float) -> float:
        if math.isnan(value):
            raise ValidationError("Confidence cannot be NaN.")
        return max(0.0, min(float(value), 1.0))
