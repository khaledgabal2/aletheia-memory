PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_events (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    session_id TEXT,
    source_type TEXT NOT NULL,
    source_uri TEXT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    observed_at TEXT,
    trust_level TEXT DEFAULT 'unknown',
    privacy_level TEXT DEFAULT 'personal',
    retention_policy TEXT DEFAULT 'default'
);

CREATE INDEX IF NOT EXISTS idx_evidence_namespace
ON evidence_events(namespace);

CREATE INDEX IF NOT EXISTS idx_evidence_content_hash
ON evidence_events(namespace, content_hash);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence_base REAL NOT NULL,
    confidence_effective REAL NOT NULL,
    half_life_days REAL NOT NULL,
    importance REAL DEFAULT 0.5,
    volatility TEXT DEFAULT 'medium',
    created_at TEXT NOT NULL,
    last_verified_at TEXT,
    last_accessed_at TEXT,
    valid_from TEXT,
    valid_to TEXT
);

CREATE INDEX IF NOT EXISTS idx_claims_namespace
ON claims(namespace);

CREATE INDEX IF NOT EXISTS idx_claims_subject_predicate
ON claims(namespace, subject, predicate);

CREATE INDEX IF NOT EXISTS idx_claims_status
ON claims(namespace, status);

CREATE TABLE IF NOT EXISTS claim_evidence_links (
    claim_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    PRIMARY KEY (claim_id, evidence_id),
    FOREIGN KEY (claim_id) REFERENCES claims(id),
    FOREIGN KEY (evidence_id) REFERENCES evidence_events(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_target
ON audit_log(target_type, target_id);

CREATE TABLE IF NOT EXISTS conflicts (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    status TEXT NOT NULL,
    active_claim_id TEXT,
    resolution_note TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_conflicts_namespace
ON conflicts(namespace, status);

CREATE TABLE IF NOT EXISTS conflict_claim_links (
    conflict_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    PRIMARY KEY (conflict_id, claim_id),
    FOREIGN KEY (conflict_id) REFERENCES conflicts(id),
    FOREIGN KEY (claim_id) REFERENCES claims(id)
);

CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    signal TEXT NOT NULL,
    source TEXT DEFAULT 'user',
    note TEXT,
    evidence_id TEXT,
    strength REAL DEFAULT 1.0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS confidence_events (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    old_truth_confidence REAL,
    new_truth_confidence REAL,
    old_retrieval_salience REAL,
    new_retrieval_salience REAL,
    reason TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(id)
);

CREATE INDEX IF NOT EXISTS idx_confidence_events_claim
ON confidence_events(claim_id, created_at);

CREATE TABLE IF NOT EXISTS confidence_snapshots (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    truth_confidence REAL NOT NULL,
    retrieval_salience REAL NOT NULL,
    base_confidence REAL NOT NULL,
    effective_confidence REAL NOT NULL,
    decay_factor REAL NOT NULL,
    source_reliability_factor REAL NOT NULL,
    feedback_factor REAL NOT NULL,
    contradiction_factor REAL NOT NULL,
    verification_factor REAL NOT NULL,
    half_life_days REAL NOT NULL,
    age_days REAL NOT NULL,
    explanation TEXT,
    computed_at TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(id)
);

CREATE INDEX IF NOT EXISTS idx_confidence_snapshots_claim
ON confidence_snapshots(claim_id, computed_at);

CREATE TABLE IF NOT EXISTS half_life_policies (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    memory_type TEXT,
    predicate TEXT,
    half_life_days REAL NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_half_life_policies_lookup
ON half_life_policies(namespace, memory_type, predicate);

CREATE TABLE IF NOT EXISTS claim_relationships (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    source_claim_id TEXT NOT NULL,
    target_claim_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    reason TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (source_claim_id) REFERENCES claims(id),
    FOREIGN KEY (target_claim_id) REFERENCES claims(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_claim_relationship_unique
ON claim_relationships(source_claim_id, target_claim_id, relationship_type);

CREATE TABLE IF NOT EXISTS claim_status_history (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    reason TEXT,
    changed_by TEXT DEFAULT 'system',
    created_at TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(id)
);

CREATE INDEX IF NOT EXISTS idx_claim_status_history_claim
ON claim_status_history(claim_id, created_at);

CREATE TABLE IF NOT EXISTS conflict_families (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    subject TEXT,
    predicate TEXT,
    conflict_type TEXT NOT NULL,
    status TEXT NOT NULL,
    active_claim_id TEXT,
    resolution_id TEXT,
    resolution_strategy TEXT,
    resolution_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_conflict_families_namespace
ON conflict_families(namespace, status);

CREATE TABLE IF NOT EXISTS conflict_family_claims (
    conflict_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    role TEXT DEFAULT 'member',
    created_at TEXT NOT NULL,
    PRIMARY KEY (conflict_id, claim_id),
    FOREIGN KEY (conflict_id) REFERENCES conflict_families(id),
    FOREIGN KEY (claim_id) REFERENCES claims(id)
);

CREATE TABLE IF NOT EXISTS conflict_resolutions (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    conflict_id TEXT NOT NULL,
    strategy TEXT NOT NULL,
    active_claim_id TEXT,
    superseded_claim_ids_json TEXT,
    rejected_claim_ids_json TEXT,
    scoped_claims_json TEXT,
    metadata_json TEXT,
    note TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conflict_id) REFERENCES conflict_families(id)
);

CREATE INDEX IF NOT EXISTS idx_conflict_resolutions_conflict
ON conflict_resolutions(conflict_id, created_at);

CREATE TABLE IF NOT EXISTS claim_scopes (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    applies_when TEXT,
    valid_from TEXT,
    valid_to TEXT,
    project_id TEXT,
    session_id TEXT,
    agent_id TEXT,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(id)
);

CREATE INDEX IF NOT EXISTS idx_claim_scopes_claim
ON claim_scopes(claim_id);

CREATE TABLE IF NOT EXISTS curation_decisions (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    claim_id TEXT,
    decision_type TEXT NOT NULL,
    old_status TEXT,
    proposed_status TEXT,
    target_status TEXT,
    reason TEXT NOT NULL,
    confidence_before REAL,
    confidence_after REAL,
    dry_run INTEGER NOT NULL DEFAULT 0,
    applied INTEGER NOT NULL DEFAULT 0,
    force INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(id)
);

CREATE INDEX IF NOT EXISTS idx_curation_decisions_claim
ON curation_decisions(claim_id, created_at);

CREATE TABLE IF NOT EXISTS curation_queue (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    task_type TEXT NOT NULL DEFAULT 'review',
    queue_reason TEXT NOT NULL,
    reason TEXT,
    priority REAL DEFAULT 0.5,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS claims_fts USING fts5(
    claim_id UNINDEXED,
    namespace UNINDEXED,
    subject,
    predicate,
    object,
    memory_type UNINDEXED,
    content
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    agent_id TEXT,
    project_id TEXT,
    title TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_namespace
ON sessions(namespace);

CREATE INDEX IF NOT EXISTS idx_sessions_project
ON sessions(namespace, project_id);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT,
    PRIMARY KEY (namespace, id)
);

CREATE INDEX IF NOT EXISTS idx_projects_namespace
ON projects(namespace, status);

CREATE TABLE IF NOT EXISTS project_claim_links (
    namespace TEXT NOT NULL,
    project_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT 'related',
    created_at TEXT NOT NULL,
    PRIMARY KEY (namespace, project_id, claim_id),
    FOREIGN KEY (claim_id) REFERENCES claims(id)
);

CREATE INDEX IF NOT EXISTS idx_project_claim_links_claim
ON project_claim_links(claim_id);

CREATE TABLE IF NOT EXISTS session_claim_links (
    session_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT 'created_in_session',
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, claim_id),
    FOREIGN KEY (claim_id) REFERENCES claims(id)
);

CREATE INDEX IF NOT EXISTS idx_session_claim_links_claim
ON session_claim_links(claim_id);

CREATE TABLE IF NOT EXISTS retrieval_log (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    query TEXT NOT NULL,
    session_id TEXT,
    project_id TEXT,
    result_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_retrieval_log_namespace
ON retrieval_log(namespace, created_at);

CREATE TABLE IF NOT EXISTS context_pack_log (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    query TEXT NOT NULL,
    session_id TEXT,
    project_id TEXT,
    token_budget INTEGER NOT NULL,
    item_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_context_pack_log_namespace
ON context_pack_log(namespace, created_at);

CREATE TABLE IF NOT EXISTS ingestion_batches (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_uri TEXT,
    title TEXT,
    project_id TEXT,
    session_id TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_ingestion_batches_namespace
ON ingestion_batches(namespace, created_at);

CREATE TABLE IF NOT EXISTS ingestion_batch_evidence_links (
    batch_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    PRIMARY KEY (batch_id, evidence_id),
    FOREIGN KEY (batch_id) REFERENCES ingestion_batches(id),
    FOREIGN KEY (evidence_id) REFERENCES evidence_events(id)
);

CREATE TABLE IF NOT EXISTS source_documents (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    title TEXT,
    source_type TEXT NOT NULL,
    source_uri TEXT,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (batch_id) REFERENCES ingestion_batches(id)
);

CREATE INDEX IF NOT EXISTS idx_source_documents_batch
ON source_documents(batch_id);

CREATE TABLE IF NOT EXISTS evidence_spans (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    span_text TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (evidence_id) REFERENCES evidence_events(id)
);

CREATE INDEX IF NOT EXISTS idx_evidence_spans_evidence
ON evidence_spans(evidence_id);

CREATE TABLE IF NOT EXISTS extraction_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    batch_id TEXT,
    extractor_name TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    policy_json TEXT,
    candidate_count INTEGER NOT NULL,
    stored_candidate_count INTEGER NOT NULL,
    dry_run INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    warnings_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_extraction_runs_namespace
ON extraction_runs(namespace, created_at);

CREATE TABLE IF NOT EXISTS extraction_run_evidence_links (
    extraction_run_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    PRIMARY KEY (extraction_run_id, evidence_id),
    FOREIGN KEY (extraction_run_id) REFERENCES extraction_runs(id),
    FOREIGN KEY (evidence_id) REFERENCES evidence_events(id)
);

CREATE TABLE IF NOT EXISTS candidate_claims (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    extraction_run_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    candidate_status TEXT NOT NULL,
    suggested_confidence REAL NOT NULL,
    suggested_importance REAL DEFAULT 0.5,
    suggested_half_life_days REAL,
    suggested_scope_json TEXT,
    contradiction_risk REAL DEFAULT 0.0,
    duplicate_risk REAL DEFAULT 0.0,
    privacy_level TEXT DEFAULT 'personal',
    created_at TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (extraction_run_id) REFERENCES extraction_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_candidate_claims_review
ON candidate_claims(namespace, candidate_status, created_at);

CREATE TABLE IF NOT EXISTS candidate_evidence_links (
    candidate_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    evidence_span_id TEXT,
    role TEXT NOT NULL DEFAULT 'supporting',
    PRIMARY KEY (candidate_id, evidence_id, evidence_span_id),
    FOREIGN KEY (candidate_id) REFERENCES candidate_claims(id),
    FOREIGN KEY (evidence_id) REFERENCES evidence_events(id),
    FOREIGN KEY (evidence_span_id) REFERENCES evidence_spans(id)
);

CREATE TABLE IF NOT EXISTS extraction_decisions (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    edits_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidate_claims(id)
);

CREATE INDEX IF NOT EXISTS idx_extraction_decisions_candidate
ON extraction_decisions(candidate_id, created_at);

CREATE TABLE IF NOT EXISTS candidate_claim_links (
    candidate_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT 'promoted_to',
    created_at TEXT NOT NULL,
    PRIMARY KEY (candidate_id, claim_id),
    FOREIGN KEY (candidate_id) REFERENCES candidate_claims(id),
    FOREIGN KEY (claim_id) REFERENCES claims(id)
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_entities_namespace
ON entities(namespace, lower(canonical_name));

CREATE TABLE IF NOT EXISTS entity_aliases (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_alias_unique
ON entity_aliases(namespace, lower(alias));

CREATE TABLE IF NOT EXISTS entity_mentions (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    entity_id TEXT,
    evidence_id TEXT NOT NULL,
    mention_text TEXT NOT NULL,
    start_char INTEGER,
    end_char INTEGER,
    confidence REAL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities(id),
    FOREIGN KEY (evidence_id) REFERENCES evidence_events(id)
);

CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity
ON entity_mentions(entity_id, evidence_id);

CREATE TABLE IF NOT EXISTS claim_entity_links (
    claim_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (claim_id, entity_id, role),
    FOREIGN KEY (claim_id) REFERENCES claims(id),
    FOREIGN KEY (entity_id) REFERENCES entities(id)
);

CREATE TABLE IF NOT EXISTS candidate_entity_links (
    candidate_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (candidate_id, entity_id, role),
    FOREIGN KEY (candidate_id) REFERENCES candidate_claims(id),
    FOREIGN KEY (entity_id) REFERENCES entities(id)
);

CREATE TABLE IF NOT EXISTS category_registry (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    label TEXT NOT NULL,
    parent_label TEXT,
    description TEXT,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_category_registry_label
ON category_registry(COALESCE(namespace, ''), label);

CREATE TABLE IF NOT EXISTS memory_category_labels (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    label TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    reason TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_category_labels_target
ON memory_category_labels(namespace, target_type, target_id);

CREATE TABLE IF NOT EXISTS embeddings (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    vector_ref TEXT,
    vector_blob BLOB,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT,
    provider_type TEXT DEFAULT 'mock',
    provider_version TEXT DEFAULT 'm3',
    input_hash TEXT,
    privacy_level TEXT DEFAULT 'personal',
    index_version TEXT,
    chunk_id TEXT DEFAULT 'default',
    chunk_text_hash TEXT,
    vector_store TEXT DEFAULT 'sqlite_local',
    vector_id TEXT,
    status TEXT DEFAULT 'indexed',
    stale_reason TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_embeddings_target_provider
ON embeddings(namespace, target_type, target_id, provider, model, COALESCE(index_version, ''));

CREATE TABLE IF NOT EXISTS semantic_index_records (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    indexed_at TEXT NOT NULL,
    status TEXT NOT NULL,
    metadata_json TEXT,
    model TEXT,
    dimension INTEGER,
    provider_type TEXT DEFAULT 'mock',
    vector_store TEXT DEFAULT 'sqlite_local',
    index_version TEXT,
    content_hash TEXT,
    stale_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_semantic_index_records_target
ON semantic_index_records(namespace, target_type, target_id);

CREATE TABLE IF NOT EXISTS content_risk_flags (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    risk_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    span_text TEXT,
    start_char INTEGER,
    end_char INTEGER,
    note TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (evidence_id) REFERENCES evidence_events(id)
);

CREATE INDEX IF NOT EXISTS idx_content_risk_flags_evidence
ON content_risk_flags(evidence_id, severity);

CREATE TABLE IF NOT EXISTS llm_prompts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS llm_prompt_versions (
    id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL,
    version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    template_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (prompt_id) REFERENCES llm_prompts(id)
);

CREATE TABLE IF NOT EXISTS llm_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    task_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_template_id TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    temperature REAL NOT NULL,
    schema_version TEXT NOT NULL,
    input_evidence_ids_json TEXT,
    input_hash TEXT NOT NULL,
    output_hash TEXT,
    status TEXT NOT NULL,
    warnings_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_runs_namespace
ON llm_runs(namespace, task_type, created_at);

CREATE TABLE IF NOT EXISTS llm_outputs (
    id TEXT PRIMARY KEY,
    llm_run_id TEXT NOT NULL,
    output_type TEXT NOT NULL,
    target_id TEXT,
    status TEXT NOT NULL,
    output_hash TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (llm_run_id) REFERENCES llm_runs(id)
);

CREATE TABLE IF NOT EXISTS llm_safety_flags (
    id TEXT PRIMARY KEY,
    llm_run_id TEXT NOT NULL,
    evidence_id TEXT,
    risk_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (llm_run_id) REFERENCES llm_runs(id)
);

CREATE TABLE IF NOT EXISTS inference_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    engines_json TEXT NOT NULL,
    project_id TEXT,
    session_id TEXT,
    target_claim_ids_json TEXT,
    target_evidence_ids_json TEXT,
    rule_ids_json TEXT,
    dry_run INTEGER NOT NULL DEFAULT 1,
    inference_count INTEGER NOT NULL,
    persisted_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    warnings_json TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_inference_runs_namespace
ON inference_runs(namespace, created_at);

CREATE TABLE IF NOT EXISTS inference_candidates (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    inference_run_id TEXT NOT NULL,
    inference_type TEXT NOT NULL,
    subject TEXT,
    predicate TEXT,
    object TEXT,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    engine TEXT NOT NULL,
    rule_id TEXT,
    derivation_confidence REAL NOT NULL,
    suggested_truth_confidence REAL NOT NULL,
    suggested_retrieval_salience REAL NOT NULL,
    inference_strength TEXT NOT NULL,
    abstraction_level INTEGER NOT NULL DEFAULT 1,
    invalidation_policy TEXT NOT NULL DEFAULT 'mark_stale',
    created_at TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (inference_run_id) REFERENCES inference_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_inference_candidates_review
ON inference_candidates(namespace, status, inference_type, engine);

CREATE TABLE IF NOT EXISTS inference_decisions (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    inference_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    edits_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (inference_id) REFERENCES inference_candidates(id)
);

CREATE INDEX IF NOT EXISTS idx_inference_decisions_inference
ON inference_decisions(inference_id, created_at);

CREATE TABLE IF NOT EXISTS inference_rules (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    name TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    description TEXT NOT NULL,
    condition_json TEXT NOT NULL,
    conclusion_json TEXT NOT NULL,
    confidence_policy_json TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_inference_rules_name
ON inference_rules(COALESCE(namespace, ''), name);

CREATE TABLE IF NOT EXISTS rule_execution_log (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    inference_run_id TEXT,
    matched_count INTEGER NOT NULL,
    inference_count INTEGER NOT NULL,
    dry_run INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    warnings_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_rule_execution_log_rule
ON rule_execution_log(rule_id, created_at);

CREATE TABLE IF NOT EXISTS derivation_edges (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    relationship TEXT NOT NULL,
    rule_id TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_derivation_edges_source
ON derivation_edges(namespace, source_type, source_id);

CREATE INDEX IF NOT EXISTS idx_derivation_edges_target
ON derivation_edges(namespace, target_type, target_id);

CREATE TABLE IF NOT EXISTS derived_claim_links (
    inference_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT 'promoted_to_claim',
    created_at TEXT NOT NULL,
    PRIMARY KEY (inference_id, claim_id),
    FOREIGN KEY (inference_id) REFERENCES inference_candidates(id),
    FOREIGN KEY (claim_id) REFERENCES claims(id)
);

CREATE TABLE IF NOT EXISTS reflections (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    abstraction_level INTEGER NOT NULL,
    project_id TEXT,
    status TEXT NOT NULL,
    confidence_effective REAL NOT NULL,
    retrieval_salience REAL NOT NULL,
    builder TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_reflections_namespace
ON reflections(namespace, status, project_id);

CREATE TABLE IF NOT EXISTS reflection_sources (
    reflection_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    relation TEXT NOT NULL DEFAULT 'source',
    created_at TEXT NOT NULL,
    PRIMARY KEY (reflection_id, source_id, source_type),
    FOREIGN KEY (reflection_id) REFERENCES reflections(id)
);

CREATE TABLE IF NOT EXISTS abstraction_records (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    abstraction_text TEXT NOT NULL,
    abstraction_level INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    information_loss_policy TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_abstraction_records_namespace
ON abstraction_records(namespace, status, abstraction_level);

CREATE TABLE IF NOT EXISTS abstraction_sources (
    abstraction_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (abstraction_id, source_id, source_type),
    FOREIGN KEY (abstraction_id) REFERENCES abstraction_records(id)
);

CREATE TABLE IF NOT EXISTS semantic_clusters (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    label TEXT,
    cluster_type TEXT NOT NULL,
    created_by TEXT NOT NULL,
    confidence REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_semantic_clusters_namespace
ON semantic_clusters(namespace, cluster_type);

CREATE TABLE IF NOT EXISTS semantic_cluster_members (
    cluster_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    member_type TEXT NOT NULL,
    membership_confidence REAL NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (cluster_id, member_id, member_type),
    FOREIGN KEY (cluster_id) REFERENCES semantic_clusters(id)
);

CREATE TABLE IF NOT EXISTS semantic_relations (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_semantic_relations_unique
ON semantic_relations(namespace, source_id, source_type, target_id, target_type, relation_type);

CREATE TABLE IF NOT EXISTS invalidation_events (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    affected_id TEXT NOT NULL,
    affected_type TEXT NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_invalidation_events_source
ON invalidation_events(namespace, source_type, source_id);

CREATE TABLE IF NOT EXISTS refresh_queue (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    priority REAL NOT NULL DEFAULT 0.5,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_refresh_queue_status
ON refresh_queue(namespace, status, priority);

CREATE TABLE IF NOT EXISTS inference_explanations (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    inference_id TEXT NOT NULL,
    explanation_text TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (inference_id) REFERENCES inference_candidates(id)
);

CREATE TABLE IF NOT EXISTS memory_usage_events (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    usage_type TEXT NOT NULL,
    query TEXT,
    session_id TEXT,
    project_id TEXT,
    context_pack_id TEXT,
    rank INTEGER,
    score REAL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_memory_usage_events_target
ON memory_usage_events(namespace, target_type, target_id);

CREATE INDEX IF NOT EXISTS idx_memory_usage_events_context
ON memory_usage_events(context_pack_id);

CREATE TABLE IF NOT EXISTS context_usage_events (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    context_pack_id TEXT NOT NULL,
    query TEXT NOT NULL,
    session_id TEXT,
    project_id TEXT,
    item_count INTEGER,
    token_estimate INTEGER,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_context_usage_events_namespace
ON context_usage_events(namespace, created_at);

CREATE TABLE IF NOT EXISTS task_outcomes (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    task_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    used_context_pack_id TEXT,
    session_id TEXT,
    project_id TEXT,
    user_feedback TEXT,
    score REAL,
    note TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_task_outcomes_namespace
ON task_outcomes(namespace, task_id, created_at);

CREATE TABLE IF NOT EXISTS retrieval_judgments (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    query TEXT NOT NULL,
    result_id TEXT NOT NULL,
    result_type TEXT NOT NULL,
    judgment TEXT NOT NULL,
    judge TEXT NOT NULL,
    reason TEXT,
    expected_rank INTEGER,
    session_id TEXT,
    project_id TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_retrieval_judgments_result
ON retrieval_judgments(namespace, result_type, result_id);

CREATE TABLE IF NOT EXISTS evaluation_sets (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    project_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_evaluation_sets_name
ON evaluation_sets(namespace, name);

CREATE TABLE IF NOT EXISTS evaluation_cases (
    id TEXT PRIMARY KEY,
    eval_set_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    query TEXT NOT NULL,
    expected_claim_ids_json TEXT,
    expected_reflection_ids_json TEXT,
    forbidden_claim_ids_json TEXT,
    expected_sections_json TEXT,
    project_id TEXT,
    session_id TEXT,
    tags_json TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (eval_set_id) REFERENCES evaluation_sets(id)
);

CREATE INDEX IF NOT EXISTS idx_evaluation_cases_set
ON evaluation_cases(eval_set_id, created_at);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    eval_set_id TEXT NOT NULL,
    policy_version_id TEXT,
    retrieval_mode TEXT NOT NULL,
    case_count INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (eval_set_id) REFERENCES evaluation_sets(id)
);

CREATE INDEX IF NOT EXISTS idx_evaluation_runs_set
ON evaluation_runs(eval_set_id, created_at);

CREATE TABLE IF NOT EXISTS evaluation_results (
    id TEXT PRIMARY KEY,
    evaluation_run_id TEXT NOT NULL,
    evaluation_case_id TEXT NOT NULL,
    passed INTEGER NOT NULL,
    retrieved_ids_json TEXT,
    context_pack_id TEXT,
    metrics_json TEXT NOT NULL,
    failure_reasons_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (evaluation_run_id) REFERENCES evaluation_runs(id),
    FOREIGN KEY (evaluation_case_id) REFERENCES evaluation_cases(id)
);

CREATE TABLE IF NOT EXISTS evaluation_metrics (
    id TEXT PRIMARY KEY,
    evaluation_run_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    threshold REAL,
    passed INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (evaluation_run_id) REFERENCES evaluation_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_evaluation_metrics_run
ON evaluation_metrics(evaluation_run_id, metric_name);

CREATE TABLE IF NOT EXISTS ranking_policies (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    name TEXT NOT NULL,
    active_version_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ranking_policies_name
ON ranking_policies(COALESCE(namespace, ''), name);

CREATE TABLE IF NOT EXISTS ranking_policy_versions (
    id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    weights_json TEXT NOT NULL,
    filters_json TEXT,
    thresholds_json TEXT,
    created_by TEXT NOT NULL,
    status TEXT NOT NULL,
    evaluation_summary_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (policy_id) REFERENCES ranking_policies(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ranking_policy_versions_version
ON ranking_policy_versions(policy_id, version);

CREATE TABLE IF NOT EXISTS context_pack_policies (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    name TEXT NOT NULL,
    active_version_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_context_pack_policies_name
ON context_pack_policies(COALESCE(namespace, ''), name);

CREATE TABLE IF NOT EXISTS context_pack_policy_versions (
    id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    filters_json TEXT,
    thresholds_json TEXT,
    created_by TEXT NOT NULL,
    status TEXT NOT NULL,
    evaluation_summary_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (policy_id) REFERENCES context_pack_policies(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_context_pack_policy_versions_version
ON context_pack_policy_versions(policy_id, version);

CREATE TABLE IF NOT EXISTS policy_proposals (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    policy_type TEXT NOT NULL,
    target_policy_id TEXT,
    proposed_config_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    source_run_id TEXT,
    evaluation_run_id TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewer TEXT,
    review_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_policy_proposals_namespace
ON policy_proposals(namespace, status, policy_type);

CREATE TABLE IF NOT EXISTS policy_application_history (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    policy_type TEXT NOT NULL,
    old_version_id TEXT,
    new_version_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    applied_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (proposal_id) REFERENCES policy_proposals(id)
);

CREATE TABLE IF NOT EXISTS procedure_versions (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    procedure_claim_id TEXT,
    version INTEGER NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    source_proposal_id TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_procedure_versions_claim
ON procedure_versions(namespace, procedure_claim_id, version);

CREATE TABLE IF NOT EXISTS procedure_update_proposals (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    procedure_claim_id TEXT,
    title TEXT NOT NULL,
    proposed_text TEXT NOT NULL,
    reason TEXT NOT NULL,
    source_ids_json TEXT,
    source_type TEXT,
    evaluation_run_id TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewer TEXT,
    review_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_procedure_update_proposals_namespace
ON procedure_update_proposals(namespace, status);

CREATE TABLE IF NOT EXISTS learning_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    project_id TEXT,
    learning_targets_json TEXT NOT NULL,
    eval_set_id TEXT,
    dry_run INTEGER NOT NULL,
    proposals_created_json TEXT,
    warnings_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS optimization_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    optimization_type TEXT NOT NULL,
    objective TEXT NOT NULL,
    baseline_policy_version_id TEXT,
    eval_set_id TEXT,
    trial_count INTEGER NOT NULL,
    best_metrics_json TEXT,
    proposal_id TEXT,
    dry_run INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS learning_gate_results (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    gate_type TEXT NOT NULL,
    passed INTEGER NOT NULL,
    metrics_json TEXT,
    failure_reasons_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_learning_gate_results_proposal
ON learning_gate_results(proposal_id, gate_type);

CREATE TABLE IF NOT EXISTS local_jobs (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    job_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    priority REAL NOT NULL DEFAULT 0.5,
    status TEXT NOT NULL DEFAULT 'pending',
    run_after TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_local_jobs_pending
ON local_jobs(namespace, status, run_after, priority);

CREATE TABLE IF NOT EXISTS memory_health_snapshots (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    project_id TEXT,
    metrics_json TEXT NOT NULL,
    warnings_json TEXT,
    recommendations_json TEXT,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rollback_records (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    from_version_id TEXT,
    to_version_id TEXT,
    reason TEXT NOT NULL,
    rolled_back_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_rollback_records_target
ON rollback_records(namespace, target_type, target_id);

CREATE TABLE IF NOT EXISTS api_clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    client_type TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_api_clients_status
ON api_clients(status, client_type);

CREATE TABLE IF NOT EXISTS api_tokens (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    token_prefix TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    privacy_ceiling TEXT NOT NULL DEFAULT 'personal',
    expires_at TEXT,
    created_at TEXT NOT NULL,
    revoked_at TEXT,
    metadata_json TEXT,
    FOREIGN KEY (client_id) REFERENCES api_clients(id)
);

CREATE INDEX IF NOT EXISTS idx_api_tokens_prefix
ON api_tokens(token_prefix);

CREATE TABLE IF NOT EXISTS capability_grants (
    id TEXT PRIMARY KEY,
    token_id TEXT NOT NULL,
    capability TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (token_id) REFERENCES api_tokens(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_capability_grants_unique
ON capability_grants(token_id, capability);

CREATE TABLE IF NOT EXISTS namespace_access_grants (
    id TEXT PRIMARY KEY,
    token_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    access_level TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (token_id) REFERENCES api_tokens(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_namespace_access_grants_unique
ON namespace_access_grants(token_id, namespace, access_level);

CREATE TABLE IF NOT EXISTS agent_registrations (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    name TEXT NOT NULL,
    agent_type TEXT,
    client_id TEXT,
    default_project_id TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (client_id) REFERENCES api_clients(id)
);

CREATE INDEX IF NOT EXISTS idx_agent_registrations_namespace
ON agent_registrations(namespace, status);

CREATE TABLE IF NOT EXISTS service_request_log (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    client_id TEXT,
    agent_id TEXT,
    namespace TEXT,
    method TEXT NOT NULL,
    path TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    duration_ms INTEGER,
    request_hash TEXT,
    response_hash TEXT,
    log_mode TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_service_request_log_created
ON service_request_log(created_at);

CREATE INDEX IF NOT EXISTS idx_service_request_log_request
ON service_request_log(request_id);

CREATE TABLE IF NOT EXISTS mcp_tool_invocation_log (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    client_id TEXT,
    tool_name TEXT NOT NULL,
    namespace TEXT,
    status TEXT NOT NULL,
    duration_ms INTEGER,
    input_hash TEXT,
    output_hash TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_mcp_tool_invocation_log_created
ON mcp_tool_invocation_log(created_at);

CREATE TABLE IF NOT EXISTS idempotency_records (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    client_id TEXT,
    idempotency_key TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    response_json TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_idempotency_records_unique
ON idempotency_records(client_id, idempotency_key, endpoint);

CREATE TABLE IF NOT EXISTS rate_limit_records (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    request_count INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_rate_limit_records_window
ON rate_limit_records(client_id, window_start);

CREATE TABLE IF NOT EXISTS service_config_history (
    id TEXT PRIMARY KEY,
    config_hash TEXT NOT NULL,
    config_redacted_json TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS service_instance_log (
    id TEXT PRIMARY KEY,
    instance_id TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER,
    db_path TEXT NOT NULL,
    started_at TEXT NOT NULL,
    stopped_at TEXT,
    status TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_service_instance_log_started
ON service_instance_log(started_at);

CREATE TABLE IF NOT EXISTS console_sessions (
    id TEXT PRIMARY KEY,
    client_id TEXT,
    token_id TEXT,
    namespace_grants_json TEXT NOT NULL,
    capabilities_json TEXT NOT NULL,
    privacy_ceiling TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_console_sessions_expires
ON console_sessions(expires_at, revoked_at);

CREATE TABLE IF NOT EXISTS console_action_confirmations (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    action_type TEXT NOT NULL,
    target_id TEXT,
    target_type TEXT,
    confirmation_text TEXT,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_console_action_confirmations_target
ON console_action_confirmations(namespace, target_type, target_id);

CREATE TABLE IF NOT EXISTS review_tasks (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    task_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    priority REAL NOT NULL DEFAULT 0.5,
    severity TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'open',
    recommended_action TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    due_at TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_review_tasks_queue
ON review_tasks(namespace, status, severity, priority);

CREATE UNIQUE INDEX IF NOT EXISTS idx_review_tasks_open_target
ON review_tasks(namespace, task_type, target_id, target_type, status);

CREATE TABLE IF NOT EXISTS review_task_events (
    id TEXT PRIMARY KEY,
    review_task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (review_task_id) REFERENCES review_tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_review_task_events_task
ON review_task_events(review_task_id, created_at);

CREATE TABLE IF NOT EXISTS notification_events (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unread',
    target_id TEXT,
    target_type TEXT,
    created_at TEXT NOT NULL,
    dismissed_at TEXT,
    snoozed_until TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_notification_events_queue
ON notification_events(namespace, status, severity, created_at);

CREATE TABLE IF NOT EXISTS dashboard_saved_views (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    name TEXT NOT NULL,
    view_type TEXT NOT NULL,
    filters_json TEXT NOT NULL,
    sort_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_dashboard_saved_views_namespace
ON dashboard_saved_views(namespace, view_type);

CREATE TABLE IF NOT EXISTS dashboard_preferences (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    preference_key TEXT NOT NULL,
    preference_value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dashboard_preferences_unique
ON dashboard_preferences(namespace, preference_key);

CREATE TABLE IF NOT EXISTS metric_snapshots (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    project_id TEXT,
    metrics_json TEXT NOT NULL,
    source TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_metric_snapshots_latest
ON metric_snapshots(namespace, project_id, generated_at);

CREATE TABLE IF NOT EXISTS trace_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    trace_type TEXT NOT NULL,
    query TEXT,
    project_id TEXT,
    session_id TEXT,
    retrieval_mode TEXT,
    policy_version_id TEXT,
    duration_ms INTEGER,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_trace_runs_namespace
ON trace_runs(namespace, trace_type, created_at);

CREATE TABLE IF NOT EXISTS trace_events (
    id TEXT PRIMARY KEY,
    trace_run_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (trace_run_id) REFERENCES trace_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_trace_events_run
ON trace_events(trace_run_id, created_at);

CREATE TABLE IF NOT EXISTS retrieval_trace_items (
    id TEXT PRIMARY KEY,
    trace_run_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    final_score REAL,
    lexical_score REAL,
    semantic_score REAL,
    confidence_score REAL,
    salience_score REAL,
    included INTEGER NOT NULL,
    omission_reason TEXT,
    rank INTEGER,
    metadata_json TEXT,
    FOREIGN KEY (trace_run_id) REFERENCES trace_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_retrieval_trace_items_run
ON retrieval_trace_items(trace_run_id, included, rank);

CREATE TABLE IF NOT EXISTS context_trace_items (
    id TEXT PRIMARY KEY,
    trace_run_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    section TEXT,
    included INTEGER NOT NULL,
    omission_reason TEXT,
    token_estimate INTEGER,
    rank INTEGER,
    metadata_json TEXT,
    FOREIGN KEY (trace_run_id) REFERENCES trace_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_context_trace_items_run
ON context_trace_items(trace_run_id, included, rank);

CREATE TABLE IF NOT EXISTS report_exports (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    report_type TEXT NOT NULL,
    format TEXT NOT NULL,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_report_exports_namespace
ON report_exports(namespace, report_type, created_at);

CREATE TABLE IF NOT EXISTS backup_manifests (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    backup_type TEXT NOT NULL,
    format_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    archive_path TEXT NOT NULL,
    encrypted INTEGER NOT NULL,
    encryption_key_id TEXT,
    privacy_mode TEXT NOT NULL,
    includes_auth_metadata INTEGER NOT NULL DEFAULT 1,
    includes_raw_content INTEGER NOT NULL DEFAULT 1,
    item_counts_json TEXT,
    checksums_json TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_backup_manifests_created
ON backup_manifests(created_at);

CREATE TABLE IF NOT EXISTS backup_items (
    id TEXT PRIMARY KEY,
    backup_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    item_id TEXT,
    checksum TEXT,
    size_bytes INTEGER,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_backup_items_backup
ON backup_items(backup_id, item_type);

CREATE TABLE IF NOT EXISTS backup_verification_runs (
    id TEXT PRIMARY KEY,
    backup_id TEXT,
    backup_path TEXT NOT NULL,
    status TEXT NOT NULL,
    deep INTEGER NOT NULL DEFAULT 1,
    finding_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    warnings_json TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS restore_runs (
    id TEXT PRIMARY KEY,
    backup_manifest_id TEXT,
    backup_path TEXT NOT NULL,
    target_db_path TEXT NOT NULL,
    mode TEXT NOT NULL,
    dry_run INTEGER NOT NULL DEFAULT 1,
    verified_before_restore INTEGER NOT NULL DEFAULT 0,
    restored_item_counts_json TEXT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    warnings_json TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS encryption_key_records (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL,
    algorithm TEXT,
    kdf TEXT,
    key_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    rotated_at TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS key_rotation_events (
    id TEXT PRIMARY KEY,
    old_key_id TEXT NOT NULL,
    new_key_id TEXT NOT NULL,
    target TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    affected_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS protected_mode_config (
    id TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL,
    content_encryption_enabled INTEGER NOT NULL,
    backup_encryption_required INTEGER NOT NULL,
    indexing_policy TEXT NOT NULL,
    request_logging_policy TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS redaction_events (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    replacement_text TEXT,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    affected_counts_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_redaction_events_target
ON redaction_events(target_type, target_id);

CREATE TABLE IF NOT EXISTS deletion_tombstones (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    deletion_mode TEXT NOT NULL,
    reason TEXT NOT NULL,
    deleted_by TEXT NOT NULL,
    affected_derived_count INTEGER NOT NULL DEFAULT 0,
    backup_warning TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_deletion_tombstones_target
ON deletion_tombstones(target_type, target_id);

CREATE TABLE IF NOT EXISTS retention_policies (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    memory_type TEXT,
    privacy_level TEXT,
    source_type TEXT,
    action TEXT NOT NULL,
    after_days INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS retention_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    dry_run INTEGER NOT NULL,
    matched_count INTEGER NOT NULL,
    applied_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    warnings_json TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS integrity_check_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    scope TEXT NOT NULL,
    status TEXT NOT NULL,
    finding_count INTEGER NOT NULL,
    critical_count INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS integrity_findings (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    finding_type TEXT NOT NULL,
    target_id TEXT,
    target_type TEXT,
    message TEXT NOT NULL,
    repairable INTEGER NOT NULL DEFAULT 0,
    recommended_action TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_integrity_findings_run
ON integrity_findings(run_id, severity);

CREATE TABLE IF NOT EXISTS index_consistency_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    index_type TEXT NOT NULL,
    status TEXT NOT NULL,
    checked_count INTEGER NOT NULL,
    drift_count INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS migration_plans (
    id TEXT PRIMARY KEY,
    from_version TEXT NOT NULL,
    to_version TEXT NOT NULL,
    steps_json TEXT NOT NULL,
    irreversible INTEGER NOT NULL,
    backup_required INTEGER NOT NULL,
    warnings_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS migration_runs (
    id TEXT PRIMARY KEY,
    plan_id TEXT,
    from_version TEXT NOT NULL,
    to_version TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    backup_manifest_id TEXT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    warnings_json TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS compaction_runs (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    dry_run INTEGER NOT NULL,
    backup_manifest_id TEXT,
    size_before_bytes INTEGER,
    size_after_bytes INTEGER,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    warnings_json TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS export_manifests (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    export_type TEXT NOT NULL,
    format TEXT NOT NULL,
    file_path TEXT NOT NULL,
    encrypted INTEGER NOT NULL,
    privacy_mode TEXT NOT NULL,
    item_counts_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS import_runs (
    id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    target_namespace TEXT,
    dry_run INTEGER NOT NULL,
    imported_counts_json TEXT,
    skipped_counts_json TEXT,
    conflict_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    warnings_json TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS support_bundles (
    id TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    privacy_mode TEXT NOT NULL,
    encrypted INTEGER NOT NULL,
    includes_raw_content INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS benchmark_runs (
    id TEXT PRIMARY KEY,
    profile TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS benchmark_results (
    id TEXT PRIMARY KEY,
    benchmark_run_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    item_count INTEGER,
    duration_ms INTEGER NOT NULL,
    p50_ms REAL,
    p95_ms REAL,
    p99_ms REAL,
    memory_mb REAL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_benchmark_results_run
ON benchmark_results(benchmark_run_id, operation);

CREATE TABLE IF NOT EXISTS release_manifests (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    git_commit TEXT,
    build_time TEXT NOT NULL,
    python_versions_json TEXT,
    platform_targets_json TEXT,
    package_files_json TEXT,
    dependency_lock_hash TEXT,
    migration_range TEXT,
    test_summary_json TEXT,
    benchmark_summary_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS production_readiness_checks (
    id TEXT PRIMARY KEY,
    namespace TEXT,
    profile TEXT NOT NULL,
    status TEXT NOT NULL,
    checks_json TEXT NOT NULL,
    warnings_json TEXT,
    recommendations_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS public_contracts (
    id TEXT PRIMARY KEY,
    contract_type TEXT NOT NULL,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    stability TEXT NOT NULL,
    introduced_in TEXT NOT NULL,
    deprecated_in TEXT,
    removed_in TEXT,
    schema_ref TEXT,
    documentation_ref TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_public_contracts_type
ON public_contracts(contract_type, stability);

CREATE TABLE IF NOT EXISTS api_contract_versions (
    id TEXT PRIMARY KEY,
    api_type TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL,
    schema_hash TEXT,
    introduced_in TEXT NOT NULL,
    deprecated_in TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS deprecation_notices (
    id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_name TEXT NOT NULL,
    deprecated_in TEXT NOT NULL,
    removal_not_before TEXT,
    replacement TEXT,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS compatibility_matrix_entries (
    id TEXT PRIMARY KEY,
    component_type TEXT NOT NULL,
    component_name TEXT NOT NULL,
    component_version TEXT NOT NULL,
    aletheia_min_version TEXT NOT NULL,
    aletheia_max_version TEXT,
    status TEXT NOT NULL,
    tested_at TEXT,
    notes TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS plugin_manifests (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    version TEXT NOT NULL,
    plugin_type TEXT NOT NULL,
    entrypoint TEXT NOT NULL,
    description TEXT NOT NULL,
    author TEXT,
    license TEXT,
    aletheia_min_version TEXT NOT NULL,
    aletheia_max_version TEXT,
    api_contract_version TEXT NOT NULL,
    capabilities_required_json TEXT,
    permissions_required_json TEXT,
    external_network_access INTEGER NOT NULL,
    reads_memory_content INTEGER NOT NULL,
    writes_memory INTEGER NOT NULL,
    stores_data INTEGER NOT NULL,
    config_schema_json TEXT,
    checksum TEXT,
    signature TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_plugin_manifests_name_version
ON plugin_manifests(name, version);

CREATE TABLE IF NOT EXISTS plugin_installations (
    id TEXT PRIMARY KEY,
    plugin_manifest_id TEXT NOT NULL,
    install_path TEXT NOT NULL,
    status TEXT NOT NULL,
    trust_level TEXT NOT NULL,
    installed_at TEXT NOT NULL,
    enabled_at TEXT,
    disabled_at TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_plugin_installations_manifest
ON plugin_installations(plugin_manifest_id, status);

CREATE TABLE IF NOT EXISTS plugin_capability_grants (
    id TEXT PRIMARY KEY,
    plugin_installation_id TEXT NOT NULL,
    permission TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS plugin_execution_log (
    id TEXT PRIMARY KEY,
    plugin_installation_id TEXT NOT NULL,
    plugin_type TEXT NOT NULL,
    operation TEXT NOT NULL,
    namespace TEXT,
    status TEXT NOT NULL,
    duration_ms INTEGER,
    input_hash TEXT,
    output_hash TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_plugin_execution_log_plugin
ON plugin_execution_log(plugin_installation_id, created_at);

CREATE TABLE IF NOT EXISTS plugin_settings (
    id TEXT PRIMARY KEY,
    plugin_installation_id TEXT NOT NULL,
    setting_key TEXT NOT NULL,
    setting_value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plugin_trust_records (
    id TEXT PRIMARY KEY,
    plugin_installation_id TEXT NOT NULL,
    trust_level TEXT NOT NULL,
    reason TEXT NOT NULL,
    reviewed_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS conformance_suites (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    suite_type TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT NOT NULL,
    required_for_v1 INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_conformance_suites_name
ON conformance_suites(name, version);

CREATE TABLE IF NOT EXISTS conformance_cases (
    id TEXT PRIMARY KEY,
    suite_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 1,
    test_ref TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS conformance_runs (
    id TEXT PRIMARY KEY,
    suite_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    target_name TEXT NOT NULL,
    status TEXT NOT NULL,
    passed_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS conformance_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    duration_ms INTEGER,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_conformance_results_run
ON conformance_results(run_id, status);

CREATE TABLE IF NOT EXISTS adapter_certifications (
    id TEXT PRIMARY KEY,
    adapter_name TEXT NOT NULL,
    adapter_type TEXT NOT NULL,
    adapter_version TEXT NOT NULL,
    conformance_run_id TEXT NOT NULL,
    status TEXT NOT NULL,
    certified_at TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS sdk_release_records (
    id TEXT PRIMARY KEY,
    sdk_name TEXT NOT NULL,
    sdk_version TEXT NOT NULL,
    language TEXT NOT NULL,
    api_contract_version TEXT NOT NULL,
    status TEXT NOT NULL,
    released_at TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS documentation_builds (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    output_path TEXT NOT NULL,
    status TEXT NOT NULL,
    examples_validated INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS example_projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    example_type TEXT NOT NULL,
    path TEXT NOT NULL,
    status TEXT NOT NULL,
    tested_at TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS doctor_runs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    checks_json TEXT NOT NULL,
    warnings_json TEXT,
    recommendations_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS v1_release_gate_runs (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    status TEXT NOT NULL,
    checks_json TEXT NOT NULL,
    critical_failures_json TEXT,
    warnings_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS federation_identities (
    id TEXT PRIMARY KEY,
    instance_id TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    public_key TEXT NOT NULL,
    key_fingerprint TEXT NOT NULL,
    key_algorithm TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    rotated_at TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS peer_devices (
    id TEXT PRIMARY KEY,
    peer_instance_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    public_key TEXT NOT NULL,
    key_fingerprint TEXT NOT NULL,
    trust_status TEXT NOT NULL,
    trust_domain_id TEXT,
    added_at TEXT NOT NULL,
    trusted_at TEXT,
    revoked_at TEXT,
    metadata_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_peer_devices_instance
ON peer_devices(peer_instance_id);

CREATE TABLE IF NOT EXISTS trust_domains (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    default_import_policy TEXT NOT NULL,
    allowed_memory_types_json TEXT,
    max_privacy_level TEXT NOT NULL,
    allow_active_import INTEGER NOT NULL DEFAULT 0,
    allow_candidate_import INTEGER NOT NULL DEFAULT 1,
    allow_feedback_import INTEGER NOT NULL DEFAULT 1,
    allow_remote_redaction INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_trust_domains_name
ON trust_domains(name);

CREATE TABLE IF NOT EXISTS share_grants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    namespace TEXT NOT NULL,
    project_id TEXT,
    grant_type TEXT NOT NULL,
    permissions_json TEXT NOT NULL,
    memory_types_json TEXT,
    statuses_json TEXT,
    privacy_ceiling TEXT NOT NULL,
    include_evidence INTEGER NOT NULL DEFAULT 1,
    include_reflections INTEGER NOT NULL DEFAULT 1,
    include_inferences INTEGER NOT NULL DEFAULT 0,
    include_audit INTEGER NOT NULL DEFAULT 0,
    candidate_write_allowed INTEGER NOT NULL DEFAULT 1,
    active_write_allowed INTEGER NOT NULL DEFAULT 0,
    expires_at TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    revoked_at TEXT,
    reason TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_share_grants_namespace
ON share_grants(namespace, status);

CREATE TABLE IF NOT EXISTS share_recipients (
    id TEXT PRIMARY KEY,
    share_grant_id TEXT NOT NULL,
    peer_id TEXT NOT NULL,
    recipient_public_key TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    accepted_at TEXT,
    revoked_at TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_share_recipients_share
ON share_recipients(share_grant_id, peer_id, status);

CREATE TABLE IF NOT EXISTS sync_collections (
    id TEXT PRIMARY KEY,
    share_grant_id TEXT NOT NULL,
    namespace TEXT NOT NULL,
    project_id TEXT,
    name TEXT NOT NULL,
    direction TEXT NOT NULL,
    transport TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_sync_collections_share
ON sync_collections(share_grant_id, status);

CREATE TABLE IF NOT EXISTS sync_changesets (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    origin_instance_id TEXT NOT NULL,
    target_peer_id TEXT,
    sequence_number INTEGER NOT NULL,
    signed INTEGER NOT NULL,
    signature TEXT,
    encrypted INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    item_count INTEGER NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_sync_changesets_collection
ON sync_changesets(collection_id, sequence_number);

CREATE TABLE IF NOT EXISTS sync_change_items (
    id TEXT PRIMARY KEY,
    changeset_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    operation TEXT NOT NULL,
    object_hash TEXT NOT NULL,
    previous_hash TEXT,
    payload_ref TEXT,
    privacy_level TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    peer_id TEXT,
    direction TEXT NOT NULL,
    transport TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    sent_count INTEGER NOT NULL DEFAULT 0,
    received_count INTEGER NOT NULL DEFAULT 0,
    applied_count INTEGER NOT NULL DEFAULT 0,
    conflict_count INTEGER NOT NULL DEFAULT 0,
    redaction_count INTEGER NOT NULL DEFAULT 0,
    warnings_json TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_sync_runs_collection
ON sync_runs(collection_id, started_at);

CREATE TABLE IF NOT EXISTS replication_cursors (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    peer_id TEXT NOT NULL,
    last_change_id TEXT,
    last_synced_at TEXT,
    status TEXT NOT NULL,
    metadata_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_replication_cursors_collection_peer
ON replication_cursors(collection_id, peer_id);

CREATE TABLE IF NOT EXISTS remote_memory_sources (
    id TEXT PRIMARY KEY,
    local_object_id TEXT NOT NULL,
    local_object_type TEXT NOT NULL,
    remote_object_id TEXT NOT NULL,
    remote_object_type TEXT NOT NULL,
    origin_instance_id TEXT NOT NULL,
    peer_id TEXT NOT NULL,
    share_grant_id TEXT NOT NULL,
    sync_run_id TEXT NOT NULL,
    trust_domain_id TEXT,
    imported_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_remote_memory_sources_local
ON remote_memory_sources(local_object_type, local_object_id);

CREATE TABLE IF NOT EXISTS import_trust_policies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    trust_domain_id TEXT,
    peer_id TEXT,
    namespace TEXT,
    import_mode TEXT NOT NULL,
    allow_active_claims INTEGER NOT NULL DEFAULT 0,
    allow_candidates INTEGER NOT NULL DEFAULT 1,
    allow_evidence INTEGER NOT NULL DEFAULT 1,
    allow_reflections INTEGER NOT NULL DEFAULT 1,
    allow_inferences INTEGER NOT NULL DEFAULT 0,
    require_review_for_conflicts INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_import_trust_policies_scope
ON import_trust_policies(peer_id, namespace, trust_domain_id);

CREATE TABLE IF NOT EXISTS sync_conflicts (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    collection_id TEXT NOT NULL,
    sync_run_id TEXT NOT NULL,
    conflict_type TEXT NOT NULL,
    local_object_id TEXT,
    local_object_type TEXT,
    remote_object_id TEXT,
    remote_object_type TEXT,
    origin_instance_id TEXT NOT NULL,
    status TEXT NOT NULL,
    severity TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_sync_conflicts_status
ON sync_conflicts(namespace, status, created_at);

CREATE TABLE IF NOT EXISTS sync_conflict_resolutions (
    id TEXT PRIMARY KEY,
    sync_conflict_id TEXT NOT NULL,
    strategy TEXT NOT NULL,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS federation_audit_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    namespace TEXT,
    peer_id TEXT,
    share_grant_id TEXT,
    sync_run_id TEXT,
    target_id TEXT,
    target_type TEXT,
    actor TEXT,
    reason TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_federation_audit_events_target
ON federation_audit_events(target_type, target_id, created_at);

CREATE TABLE IF NOT EXISTS consent_records (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    consent_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    granted_by TEXT NOT NULL,
    granted_to_peer_id TEXT,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    revoked_at TEXT,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS revocation_records (
    id TEXT PRIMARY KEY,
    revocation_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    peer_id TEXT,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL,
    propagated_at TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_revocation_records_target
ON revocation_records(target_type, target_id, peer_id);

CREATE TABLE IF NOT EXISTS sync_tombstones (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    origin_instance_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    tombstone_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    owner_identity_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_workspaces_namespace
ON workspaces(namespace, status);

CREATE TABLE IF NOT EXISTS workspace_members (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    member_type TEXT NOT NULL,
    member_id TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    joined_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_members_unique
ON workspace_members(workspace_id, member_type, member_id);

CREATE TABLE IF NOT EXISTS agent_groups (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    default_capabilities_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_groups_namespace
ON agent_groups(namespace, name);

CREATE TABLE IF NOT EXISTS agent_group_members (
    id TEXT PRIMARY KEY,
    agent_group_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    joined_at TEXT NOT NULL,
    metadata_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_group_members_unique
ON agent_group_members(agent_group_id, agent_id);
