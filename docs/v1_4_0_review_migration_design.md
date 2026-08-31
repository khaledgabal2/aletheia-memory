# Phase 4 review storage and protocol design

The accepted Phase 0 D5/D6 decisions require durable conservative invalidation,
atomic compare-and-review, replay before stale-state checking, and bound keyset
pagination. This design was recorded before implementation in [design issue #4](https://github.com/khaledgabal2/aletheia-memory/issues/4). No merge or release
is authorized. The implementation branch starts at Phase 3 `b4ca771`.

## Storage and migration

Use independent storage version **1.3.1** (previous storage: 1.3.0). This is not a
software release number; software becomes 1.4.0 only in the release-candidate
phase. Add `review_state` (singleton generation nonce and monotonically increasing
epoch), `review_replays` (credential-bound successful operations) and a candidate
keyset index. Keep existing public resource fields and legacy unconditioned calls.

Install INSERT/UPDATE/DELETE triggers on every table in the dependency inventory
below. Conservative extra invalidations are accepted: unrelated domain changes
can require re-review. Derived FTS tables are excluded because authoritative
claim changes already advance the epoch. Every user table must be classified;
tests fail if future schema additions lack a decision. Request/rate/diagnostic
logs and replay storage must not advance it.

Migration applies under one SQLite write transaction, including schema creation,
backfills, triggers and version marker. Failure rolls everything back. Inventory
and trigger integrity are checked on reopen. Existing explicit backup-before
migration remains available; no silent downgrade is provided. Default older
binaries refuse the newer schema. An older binary must use a pre-upgrade backup,
not a downgraded marker or an unsupported no-migration bypass.

## Transaction and protocol

Negotiation uses `X-Aletheia-Contract: memory-review-v1`. Candidate detail/list
include an opaque revision. Mutations require `expected_revision` and an
`Idempotency-Key`; a supplied precondition is never silently ignored. Document
legacy requests separately. Acquire BEGIN IMMEDIATE before reauthorization,
replay lookup, revision comparison or governance input reads. Nested domain work
uses savepoints, without committing the outer operation. Wrap embedded promotion
and review too, so claim/decision/link/scope/audit changes are atomic.

Return 428 for a missing negotiated revision, 412 for stale state, 400 for a
missing key/invalid request, 409 for a changed payload under the same key or a
terminal-state conflict. Scope/privacy/auth errors never reveal the stored
outcome. Never automatically re-review or force a stale decision.

Successful replay is credential-, method-, target- and namespace-bound and
includes the original precondition in its fingerprint. Reauthorize inside the
same transaction before returning it. Store a content-free operation receipt
with original operation/decision/claim identifiers, not a stale copy of evidence
or claim text. Replay retains the operation ID and returns a fresh transport
request ID without another governance decision. Retain successful keys for 24
hours. Expired keys do not bypass terminal-state or revision checks.

Candidate list uses created_at DESC/id ASC, applied limits 1-200, and an opaque
continuation bound to filters, current scope, service identity and review epoch.
Changing these requires a fresh list. Select one extra authorized result to
establish continuation; do not silently skip hidden rows or encode their data.
Service restart invalidates revisions/cursors. The profile is not advertised
until actual-service, generated-client and concurrency gates pass.

## Restore and recovery

Use SQLite-aware copying, including live WAL data, rather than copying only the
main database file. Restoring creates a new review generation and clears replay
receipts so pre-restore decisions cannot be replayed against rolled-back state.
A running service must change its cache identity when it detects a new database
generation. Test upgrade preservation, failed-migration rollback, encrypted
backup/restore, cross-connection invalidation and rejection of old review tokens.

## Dependency inventory

The domain call graph begins with candidate reads/edits/review/promotion, evidence
and span access, trust-adjusted confidence, write_claim, scopes and labels/entities.
It extends through risk/conflict policy, protected data/redaction/retention,
background processing and federation import. Extra domain tables are included
conservatively instead of assuming they can never affect a reviewed decision.
Operational exclusions are non-authoritative bookkeeping; their corresponding
domain/policy writes still trigger invalidation. Authentication metadata is read
again in the transaction; bearer token/grant changes are also classified below.

### Invalidating tables (124)

`abstraction_records`, `abstraction_sources`, `agent_group_members`, `agent_groups`, `agent_registrations`, `api_clients`, `api_tokens`, `candidate_claim_links`, `candidate_claims`, `candidate_entity_links`, `candidate_evidence_links`, `capability_grants`, `category_registry`, `claim_entity_links`, `claim_evidence_links`, `claim_relationships`, `claim_scopes`, `claim_status_history`, `claims`, `confidence_events`, `confidence_snapshots`, `conflict_claim_links`, `conflict_families`, `conflict_family_claims`, `conflict_resolutions`, `conflicts`, `consent_records`, `content_risk_flags`, `context_pack_policies`, `context_pack_policy_versions`, `context_usage_events`, `curation_decisions`, `curation_queue`, `deletion_tombstones`, `derivation_edges`, `derived_claim_links`, `embeddings`, `encryption_key_records`, `entities`, `entity_aliases`, `entity_mentions`, `evaluation_cases`, `evaluation_metrics`, `evaluation_results`, `evaluation_runs`, `evaluation_sets`, `evidence_events`, `evidence_spans`, `extraction_decisions`, `extraction_run_evidence_links`, `extraction_runs`, `federation_audit_events`, `federation_identities`, `feedback`, `half_life_policies`, `import_trust_policies`, `inference_candidates`, `inference_decisions`, `inference_explanations`, `inference_rules`, `inference_runs`, `ingestion_batch_evidence_links`, `ingestion_batches`, `invalidation_events`, `key_rotation_events`, `learning_gate_results`, `learning_runs`, `llm_outputs`, `llm_prompt_versions`, `llm_prompts`, `llm_runs`, `llm_safety_flags`, `memory_category_labels`, `memory_usage_events`, `namespace_access_grants`, `optimization_runs`, `peer_devices`, `plugin_capability_grants`, `plugin_installations`, `plugin_manifests`, `plugin_settings`, `plugin_trust_records`, `policy_application_history`, `policy_proposals`, `procedure_update_proposals`, `procedure_versions`, `project_claim_links`, `projects`, `protected_mode_config`, `ranking_policies`, `ranking_policy_versions`, `redaction_events`, `reflection_sources`, `reflections`, `refresh_queue`, `remote_memory_sources`, `replication_cursors`, `retention_policies`, `retrieval_judgments`, `review_task_events`, `review_tasks`, `revocation_records`, `rollback_records`, `rule_execution_log`, `semantic_cluster_members`, `semantic_clusters`, `semantic_index_records`, `semantic_relations`, `session_claim_links`, `sessions`, `share_grants`, `share_recipients`, `source_documents`, `sync_change_items`, `sync_changesets`, `sync_collections`, `sync_conflict_resolutions`, `sync_conflicts`, `sync_runs`, `sync_tombstones`, `task_outcomes`, `trust_domains`, `workspace_members`, `workspaces`.

### Operational/excluded tables (56)

`adapter_certifications`, `api_contract_versions`, `audit_log`, `backup_items`, `backup_manifests`, `backup_verification_runs`, `benchmark_results`, `benchmark_runs`, `compaction_runs`, `compatibility_matrix_entries`, `conformance_cases`, `conformance_results`, `conformance_runs`, `conformance_suites`, `console_action_confirmations`, `console_sessions`, `context_pack_log`, `context_trace_items`, `dashboard_preferences`, `dashboard_saved_views`, `deprecation_notices`, `doctor_runs`, `documentation_builds`, `example_projects`, `export_manifests`, `idempotency_records`, `import_runs`, `index_consistency_runs`, `integrity_check_runs`, `integrity_findings`, `local_jobs`, `mcp_tool_invocation_log`, `memory_health_snapshots`, `metric_snapshots`, `migration_plans`, `migration_runs`, `notification_events`, `plugin_execution_log`, `production_readiness_checks`, `public_contracts`, `rate_limit_records`, `release_manifests`, `report_exports`, `restore_runs`, `retention_runs`, `retrieval_log`, `retrieval_trace_items`, `schema_version`, `sdk_release_records`, `service_config_history`, `service_instance_log`, `service_request_log`, `support_bundles`, `trace_events`, `trace_runs`, `v1_release_gate_runs`.

`review_state` and `review_replays` are protocol infrastructure and do not receive recursive epoch triggers.
