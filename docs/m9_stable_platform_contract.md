Aletheia M9 Contract

Milestone: Stable Platform, Plugin Ecosystem, Conformance, and v1.0 General Availability

⸻

1. Milestone Summary

M0 proved that Aletheia can remember.
M1 proved that Aletheia can recall across sessions and projects.
M2 proved that Aletheia can maintain trust through confidence, contradiction, decay, and curation.
M3 proved that Aletheia can ingest raw material and form candidate memories.
M4 proved that Aletheia can reason, infer, reflect, and preserve derivation lineage.
M5 proved that Aletheia can evaluate and improve itself safely.
M6 proved that Aletheia can serve local agents through HTTP and MCP.
M7 proved that Aletheia can be operated and governed through a local console.
M8 proved that Aletheia can survive production realities: backup, restore, encryption, migration, redaction, retention, integrity, and release hardening.
M9 must prove that Aletheia is a stable local memory platform others can build on.

M9 is where Aletheia becomes v1.0-ready.

M0 = Remember
M1 = Recall
M2 = Trust
M3 = Understand
M4 = Reason
M5 = Improve
M6 = Connect
M7 = Operate
M8 = Harden
M9 = Stabilize

The core M9 promise:

Aletheia exposes stable public APIs, SDKs, protocols, plugin interfaces, adapter contracts, conformance suites, documentation, examples, and compatibility guarantees so any local AI agent, tool, or extension can integrate with it safely.

M9 is not about adding new memory intelligence.
M9 is about making Aletheia a stable platform.

A memory system becomes real when other systems can trust it, extend it, test against it, and upgrade it without fear.

⸻

2. M9 Name

M9 — Stable Platform

Fuller name:

M9 — Stable Platform, Plugin Ecosystem, Conformance, and v1.0 General Availability

Recommended short name:

M9 — Stable Platform

⸻

3. M9 Contract Status

milestone: M9
name: Stable Platform
depends_on: M8
version_target: 1.0.0
stability: general-availability
breaking_changes_allowed: no_for_v1_public_contracts
storage_migration_required: yes
daemon_required: yes
console_required: yes
plugin_system_required: yes
conformance_suite_required: yes
public_docs_required: yes
sdk_stability_required: yes
cloud_required: no
external_telemetry_required: no
enterprise_acl_required: no
primary_theme: stable_platform_and_ecosystem

Important clarification:

M9 must establish v1 public contracts.
M9 must not introduce unstable behavior into the core.
M9 must not require cloud services.
M9 must not require external telemetry.
M9 must not allow plugins to bypass Aletheia governance.
M9 must not break M0–M8 behavior.

⸻

4. M8 Assumptions

M9 assumes M8 already provides:

- Durable memory kernel
- Evidence ledger
- Claim store
- Candidate memory system
- Confidence, contradiction, decay, and curation
- Sessions and projects
- Ingestion and extraction
- Entity and category registry
- Semantic retrieval interface
- Inference, reflection, abstraction, and derivation
- Evaluation and learning
- Local job queue
- HTTP API
- MCP server
- Python client
- Local console
- Backup and restore
- Encryption and protected mode
- Redaction and forget workflows
- Retention policies
- Integrity checks
- Migration hardening
- Import/export
- Support bundles
- Benchmarks
- Production readiness checks

M9 should not replace any of this.
M9 should stabilize it, document it, expose it cleanly, and allow external extensions to integrate without corrupting it.

⸻

5. M9 Primary Objective

M9 must make this flow work reliably:

pip install aletheia-memory

Then:

aletheia init --db ./aletheia.db
aletheia readiness check --db ./aletheia.db
aletheia serve --db ./aletheia.db --with-console

Then a developer can install a local plugin:

aletheia plugins install ./plugins/local-embedding-provider
aletheia plugins enable local-embedding-provider
aletheia conformance run --plugin local-embedding-provider

Then an agent developer can generate an integration scaffold:

aletheia adapters scaffold \
  --type generic-http \
  --name local-research-agent \
  --output ./examples/local-research-agent

Then run the conformance suite:

aletheia conformance run \
  --suite agent-adapter \
  --target ./examples/local-research-agent

Expected behavior:

- Aletheia installs cleanly.
- Public APIs are stable.
- HTTP and MCP contracts are versioned.
- SDKs follow the same contracts.
- Plugins declare capabilities.
- Plugins cannot bypass memory integrity rules.
- Adapters can be tested against conformance suites.
- Documentation and examples match real behavior.
- Migration from 0.9.x to 1.0.0 is safe.
- v1 compatibility rules are explicit.

⸻

6. M9 Non-Negotiable Principles

6.1 v1 means public contract discipline

After M9, public APIs must follow semantic versioning.

Public contracts include:

Python SDK
HTTP API v1
MCP tools
CLI commands
plugin interfaces
backup/archive format
database migration contract
configuration file format
context-pack schema
retrieval result schema
audit schema
conformance suite behavior

Aletheia must clearly distinguish:

public stable API
experimental API
internal API
deprecated API

No ambiguity.

⸻

6.2 Plugins must not bypass memory governance

Plugins may provide:

embedding providers
vector backends
extractors
importers
exporters
key providers
inference engines
agent adapters
console panels
report generators

But plugins must not directly mutate canonical memory unless they go through the approved Aletheia kernel APIs.

A plugin must not bypass:

evidence requirements
confidence gates
conflict gates
candidate review
privacy labels
protected indexing policy
audit logging
namespace isolation
capability enforcement
deletion/redaction propagation

⸻

6.3 Plugin permissions must be explicit

Every plugin must declare:

what it does
what APIs it uses
what capabilities it needs
what namespaces it can access
whether it reads memory content
whether it writes memory
whether it calls external services
whether it stores data
whether it executes code

No hidden behavior.

⸻

6.4 Local-first remains non-negotiable

M9 must not quietly pivot Aletheia into a cloud product.

Allowed:

optional plugins that call external APIs
optional remote adapters
optional external vector stores

Not allowed by default:

external telemetry
cloud sync
remote plugin registry calls
uploading memories
external training
remote diagnostics

Aletheia v1 must remain useful completely offline.

⸻

6.5 Documentation must be executable where possible

M9 docs must not be aspirational fiction.

Examples should run.

API examples should be tested.

CLI examples should be validated.

OpenAPI should match the actual server.

MCP tool schemas should match the actual MCP server.

If documentation says a behavior exists, tests should prove it.

⸻

6.6 Conformance beats vibes

M9 must include conformance suites for:

memory kernel
HTTP API
MCP tools
plugin interfaces
agent adapters
backup/restore archives
protected-mode behavior
context-pack schema

Integrations should not claim “Aletheia compatible” unless they pass relevant conformance tests.

⸻

6.7 Backward compatibility must be explicit

M9 must define:

what is stable
what may change
what is deprecated
how long deprecations last
how migrations work
how clients detect compatibility

A breaking change after 1.0 must require a major version bump or a new API version.

⸻

6.8 Deprecation must be humane

When a public feature is deprecated, Aletheia must provide:

warning
replacement
migration path
minimum support window
documentation
test coverage

Do not break users suddenly.

⸻

6.9 Extension failures must be contained

A failing plugin must not corrupt the memory store.

Plugin failures should be:

logged
reported
audited when state-changing
isolated when possible
recoverable
disableable

The kernel must remain stable even when an extension misbehaves.

⸻

6.10 v1 release must be boring

This is important.

M9 should not chase more intelligence.
It should ship the platform cleanly.

The goal is not to impress with new features.
The goal is to make Aletheia dependable enough that people can build serious agents on top of it.

⸻

7. M9 Scope

In Scope

M9 includes:

1. Public API stability policy
2. Semantic versioning policy
3. Deprecation policy
4. Compatibility matrix
5. Plugin architecture v1
6. Plugin manifest format
7. Plugin capability model
8. Plugin installation and validation
9. Plugin enable/disable lifecycle
10. Plugin execution logging
11. Plugin conformance tests
12. Adapter conformance tests
13. HTTP API conformance suite
14. MCP conformance suite
15. Backup/archive conformance suite
16. Context-pack schema conformance
17. Stable Python SDK v1
18. Stable async Python SDK v1
19. Optional TypeScript SDK v1
20. Agent adapter scaffolding
21. Example local agents
22. Integration templates
23. Documentation site
24. API reference generation
25. CLI reference generation
26. Plugin developer guide
27. Adapter developer guide
28. Migration guide from 0.9.x to 1.0.0
29. Release notes and changelog discipline
30. Compatibility report command
31. Doctor command for v1 installs
32. Extension safety review
33. v1 release candidate gates
34. Migration from M8 to M9
35. Golden platform tests

⸻

Out of Scope

M9 explicitly excludes:

Cloud plugin marketplace
Cloud sync
Hosted registry
Enterprise SSO
Multi-user cloud collaboration
Remote telemetry
Automatic fine-tuning
Distributed multi-node deployment
Browser extension marketplace
Commercial licensing enforcement
Managed hosted Aletheia

M9 may define future hooks for these, but v1 should stay local-first and stable.

⸻

8. M9 Deliverables

8.1 Platform Deliverables

- PublicContractRegistry
- ApiStabilityPolicy
- DeprecationPolicy
- CompatibilityMatrix
- CompatibilityReport
- PluginManager
- PluginManifest model
- PluginInstallation model
- PluginCapabilityGrant model
- PluginRuntime
- PluginValidator
- PluginSandboxPolicy
- PluginExecutionLogger
- ConformanceSuite model
- ConformanceCase model
- ConformanceRun model
- ConformanceResult model
- AdapterScaffoldGenerator
- DocumentationBuilder
- ExampleProjectRegistry
- DoctorService
- V1ReleaseGate

⸻

8.2 Plugin Deliverables

Required plugin interfaces:

ExtractorPlugin
EmbeddingProviderPlugin
VectorIndexPlugin
ImporterPlugin
ExporterPlugin
InferenceEnginePlugin
KeyProviderPlugin
ReportGeneratorPlugin
AgentAdapterPlugin

Optional plugin interfaces:

ConsolePanelPlugin
StorageBackendPlugin
PolicyOptimizerPlugin
RedactionDetectorPlugin
RiskScannerPlugin

Storage backend plugins are high-risk and should remain advanced/explicit.

⸻

8.3 SDK Deliverables

- Python SDK v1
- Async Python SDK v1
- Typed error model
- Stable request/response models
- SDK compatibility tests
- SDK migration guide
- Optional TypeScript SDK v1

⸻

8.4 Documentation Deliverables

- Documentation site
- Quickstart
- Concepts guide
- Architecture guide
- Memory model guide
- CLI reference
- Python SDK reference
- HTTP API reference
- MCP guide
- Plugin developer guide
- Adapter developer guide
- Security and privacy guide
- Backup/restore guide
- Protected mode guide
- Migration guide
- Troubleshooting guide
- Production readiness guide
- Example gallery

⸻

8.5 Storage Deliverables

M9 adds:

- public_contracts
- api_contract_versions
- deprecation_notices
- compatibility_matrix_entries
- plugin_manifests
- plugin_installations
- plugin_capability_grants
- plugin_execution_log
- plugin_settings
- plugin_trust_records
- conformance_suites
- conformance_cases
- conformance_runs
- conformance_results
- adapter_certifications
- sdk_release_records
- documentation_builds
- example_projects
- doctor_runs
- v1_release_gate_runs

⸻

8.6 CLI Deliverables

M9 adds or improves:

aletheia doctor
aletheia compatibility
aletheia plugins
aletheia conformance
aletheia adapters
aletheia docs
aletheia examples
aletheia contracts
aletheia deprecations
aletheia v1-gate

Existing M0–M8 CLI commands must remain valid.

⸻

8.7 Console Deliverables

M9 adds console pages or panels for:

Plugins
Plugin Permissions
Conformance Runs
Compatibility Matrix
API Contracts
Deprecation Notices
SDK Versions
Documentation Status
Example Projects
Doctor Reports
v1 Release Gate

⸻

9. Public Contract Stability

9.1 PublicContract model

@dataclass
class PublicContract:
    id: str
    contract_type: str
    name: str
    version: str
    stability: str
    introduced_in: str
    deprecated_in: str | None
    removed_in: str | None
    schema_ref: str | None
    documentation_ref: str | None
    created_at: datetime
    metadata: dict

Allowed contract_type:

python_api
http_api
mcp_tool
cli_command
plugin_interface
config_schema
archive_format
context_pack_schema
retrieval_result_schema
audit_schema
database_migration_contract

Allowed stability levels:

stable
experimental
internal
deprecated
removed

⸻

9.2 Stability rules

For v1:

Stable public contracts cannot break without major version bump.
Experimental contracts may change with warning.
Internal contracts are not guaranteed.
Deprecated contracts must remain available for the deprecation window.
Removed contracts require migration documentation.

⸻

9.3 DeprecationPolicy

Minimum recommended deprecation window:

2 minor releases

Example:

Deprecated in 1.2
Warn in 1.2 and 1.3
Removed no earlier than 1.4

Critical or security-driven removals may be faster, but must be documented.

⸻

9.4 memory.register_public_contract()

def register_public_contract(
    self,
    *,
    contract_type: str,
    name: str,
    version: str,
    stability: str,
    schema_ref: str | None = None,
    documentation_ref: str | None = None,
    metadata: dict | None = None,
) -> PublicContract:
    ...

⸻

9.5 CLI

aletheia contracts list
aletheia contracts show context_pack_schema_v1
aletheia deprecations list

⸻

10. Plugin Architecture Contract

10.1 Plugin principle

Plugins extend Aletheia.
They do not own Aletheia.

A plugin may provide new capabilities, but the core memory governance remains in the kernel.

⸻

10.2 Plugin types

M9 must support these plugin types.

Plugin Type	Purpose
extractor	Extract candidate memories from evidence
embedding_provider	Generate embeddings
vector_index	Store/search vectors
importer	Import external data
exporter	Export data
inference_engine	Produce inference candidates or relations
key_provider	Provide encryption keys
report_generator	Generate local reports
agent_adapter	Connect Aletheia to an agent framework

Optional:

Plugin Type	Purpose
console_panel	Add local console panels
storage_backend	Provide alternate storage backend
policy_optimizer	Propose optimization policies
risk_scanner	Detect prompt injection/secrets/memory poisoning

⸻

10.3 PluginManifest model

@dataclass
class PluginManifest:
    id: str
    name: str
    display_name: str
    version: str
    plugin_type: str
    entrypoint: str
    description: str
    author: str | None
    license: str | None
    aletheia_min_version: str
    aletheia_max_version: str | None
    api_contract_version: str
    capabilities_required: list[str]
    permissions_required: list[str]
    external_network_access: bool
    reads_memory_content: bool
    writes_memory: bool
    stores_data: bool
    config_schema: dict | None
    checksum: str | None
    signature: str | None
    created_at: datetime
    metadata: dict

⸻

10.4 Plugin manifest file

A plugin must provide:

aletheia-plugin.toml

Example:

[plugin]
name = "local-embedding-provider"
display_name = "Local Embedding Provider"
version = "1.0.0"
plugin_type = "embedding_provider"
entrypoint = "local_embedding_provider:Plugin"
description = "Provides local embedding generation."
author = "Example Developer"
license = "MIT"
[compatibility]
aletheia_min_version = "1.0.0"
aletheia_max_version = null
api_contract_version = "plugin.embedding_provider.v1"
[permissions]
capabilities_required = ["memory:read"]
permissions_required = ["read_claim_text"]
external_network_access = false
reads_memory_content = true
writes_memory = false
stores_data = false
[config_schema]
model_path = { type = "string", required = true }
dimension = { type = "integer", required = true }

⸻

10.5 Plugin permission model

Allowed plugin permissions:

read_metadata
read_claim_text
read_evidence_text
write_candidate
write_index
write_report
write_external_cache
use_network
use_filesystem_read
use_filesystem_write
use_subprocess
use_key_provider
admin_storage

High-risk permissions:

read_evidence_text
write_active_claim
use_network
use_subprocess
admin_storage
use_key_provider

High-risk permissions require explicit approval.

⸻

10.6 Plugin lifecycle

discovered
  → validated
  → installed
  → enabled
  → running
  → disabled
  → uninstalled

Failure states:

invalid
incompatible
blocked
failed
quarantined

⸻

10.7 memory.install_plugin()

def install_plugin(
    self,
    *,
    plugin_path: str,
    trust_level: str = "local",
    approve_permissions: bool = False,
) -> PluginInstallation:
    ...

Required behavior:

- Read manifest.
- Validate manifest schema.
- Check version compatibility.
- Check requested permissions.
- Compute checksum.
- Record installation.
- Do not enable automatically unless configured.
- Write audit event.

⸻

10.8 memory.enable_plugin()

def enable_plugin(
    self,
    plugin_id: str,
    *,
    reason: str,
    approved_permissions: list[str],
    actor: str = "user",
) -> PluginInstallation:
    ...

Required behavior:

- Require explicit permission approval.
- Refuse incompatible plugin.
- Store capability grants.
- Write audit event.
- Make plugin available to relevant registries.

⸻

10.9 memory.disable_plugin()

def disable_plugin(
    plugin_id: str,
    *,
    reason: str,
    actor: str = "user",
) -> PluginInstallation:
    ...

Required behavior:

- Stop plugin use.
- Preserve installation record.
- Preserve logs.
- Write audit event.

⸻

10.10 Plugin execution logging

Every plugin execution must record:

plugin_id
plugin_type
operation
namespace
duration
status
error if any
input hash
output hash
created_at

Do not log raw memory content by default.

⸻

11. Plugin Interface Contracts

11.1 ExtractorPlugin

class ExtractorPlugin(Protocol):
    name: str
    version: str
    def extract(
        self,
        *,
        namespace: str,
        evidence: list[EvidenceEvent],
        policy: ExtractionPolicy,
    ) -> list[CandidateClaimDraft]:
        ...

Required behavior:

- Return candidate drafts only.
- Include evidence spans.
- Never create active claims directly.
- Respect privacy and protected-mode restrictions.

⸻

11.2 EmbeddingProviderPlugin

class EmbeddingProviderPlugin(Protocol):
    name: str
    model: str
    dimension: int
    def embed_texts(
        self,
        texts: list[str],
        *,
        metadata: dict | None = None,
    ) -> list[list[float]]:
        ...

Required behavior:

- Disclose whether external network is used.
- Respect protected-mode indexing policy.
- Never receive secret text unless explicitly permitted.

⸻

11.3 VectorIndexPlugin

class VectorIndexPlugin(Protocol):
    name: str
    def upsert(
        self,
        *,
        namespace: str,
        vectors: list[VectorRecord],
    ) -> None:
        ...
    def search(
        self,
        *,
        namespace: str,
        query_vector: list[float],
        limit: int,
        filters: dict | None = None,
    ) -> list[VectorSearchResult]:
        ...
    def delete(
        self,
        *,
        namespace: str,
        target_ids: list[str],
    ) -> None:
        ...

Required behavior:

- Respect namespace.
- Support deletion/redaction propagation.
- Preserve target IDs and metadata.
- Never override Aletheia governance filters.

⸻

11.4 ImporterPlugin

class ImporterPlugin(Protocol):
    name: str
    supported_formats: list[str]
    def inspect(
        self,
        *,
        source_path: str,
    ) -> ImportInspection:
        ...
    def import_data(
        self,
        *,
        source_path: str,
        namespace: str,
        dry_run: bool = True,
        policy: dict | None = None,
    ) -> ImportResult:
        ...

Required behavior:

- Dry-run by default.
- Create evidence/candidates through kernel APIs.
- Preserve provenance.
- Avoid direct active writes by default.

⸻

11.5 ExporterPlugin

class ExporterPlugin(Protocol):
    name: str
    supported_formats: list[str]
    def export_data(
        self,
        *,
        namespace: str | None,
        output_path: str,
        privacy_mode: str,
        filters: dict | None = None,
    ) -> ExportResult:
        ...

Required behavior:

- Respect namespace and privacy filters.
- Redact by default when privacy mode requires.
- Write export manifest.

⸻

11.6 InferenceEnginePlugin

class InferenceEnginePlugin(Protocol):
    name: str
    version: str
    def infer(
        self,
        *,
        namespace: str,
        sources: list[Claim | EvidenceEvent | Reflection],
        policy: dict,
    ) -> list[InferenceCandidateDraft | SemanticRelationDraft]:
        ...

Required behavior:

- Produce inference candidates or semantic relations only.
- Never silently promote inferred facts.
- Preserve lineage.

⸻

11.7 KeyProviderPlugin

class KeyProviderPlugin(Protocol):
    name: str
    def get_key(
        self,
        *,
        key_id: str | None = None,
    ) -> bytes:
        ...
    def create_key(
        self,
        *,
        label: str,
        metadata: dict | None = None,
    ) -> str:
        ...

Required behavior:

- Never log raw key material.
- Respect protected-mode requirements.
- Declare storage behavior.

⸻

11.8 AgentAdapterPlugin

class AgentAdapterPlugin(Protocol):
    name: str
    framework: str
    def build_context(
        self,
        *,
        query: str,
        namespace: str,
        project_id: str | None = None,
    ) -> str:
        ...
    def remember_candidate(
        self,
        *,
        namespace: str,
        subject: str,
        predicate: str,
        object: str,
        memory_type: str,
        evidence_text: str,
    ) -> str:
        ...

Required behavior:

- Use service or kernel APIs.
- Default writes to candidate.
- Support conformance tests.

⸻

12. Conformance Contract

12.1 Purpose

Conformance suites prove integrations behave correctly.

M9 must include conformance suites for:

kernel
http_api
mcp
python_sdk
plugin
agent_adapter
backup_archive
protected_mode
context_pack_schema

⸻

12.2 ConformanceSuite model

@dataclass
class ConformanceSuite:
    id: str
    name: str
    suite_type: str
    version: str
    description: str
    required_for_v1: bool
    created_at: datetime
    metadata: dict

Allowed suite types:

kernel
http_api
mcp
sdk
plugin
agent_adapter
archive
protected_mode
context_pack

⸻

12.3 ConformanceCase model

@dataclass
class ConformanceCase:
    id: str
    suite_id: str
    name: str
    description: str
    severity: str
    required: bool
    test_ref: str
    created_at: datetime
    metadata: dict

Allowed severity:

info
low
medium
high
critical

⸻

12.4 ConformanceRun model

@dataclass
class ConformanceRun:
    id: str
    suite_id: str
    target_type: str
    target_id: str | None
    target_name: str
    status: str
    passed_count: int
    failed_count: int
    skipped_count: int
    started_at: datetime
    finished_at: datetime | None
    metadata: dict

Allowed status:

passed
failed
passed_with_warnings
cancelled
error

⸻

12.5 ConformanceResult model

@dataclass
class ConformanceResult:
    id: str
    run_id: str
    case_id: str
    status: str
    message: str | None
    duration_ms: int | None
    created_at: datetime
    metadata: dict

Allowed result statuses:

passed
failed
skipped
warning
error

⸻

12.6 memory.run_conformance()

def run_conformance(
    self,
    *,
    suite: str,
    target: str | None = None,
    target_type: str | None = None,
    fail_fast: bool = False,
    metadata: dict | None = None,
) -> ConformanceRun:
    ...

⸻

12.7 CLI

aletheia conformance list
aletheia conformance run \
  --suite http-api \
  --url http://127.0.0.1:8765
aletheia conformance run \
  --suite plugin \
  --target local-embedding-provider
aletheia conformance report conf_run_001

⸻

13. Compatibility Matrix Contract

13.1 Purpose

The compatibility matrix tells users what works with what.

It must track:

Aletheia version
Python version
OS/platform
SQLite version
plugin versions
SDK versions
HTTP API version
MCP tool version
archive format version
migration range

⸻

13.2 CompatibilityMatrixEntry model

@dataclass
class CompatibilityMatrixEntry:
    id: str
    component_type: str
    component_name: str
    component_version: str
    aletheia_min_version: str
    aletheia_max_version: str | None
    status: str
    tested_at: datetime | None
    notes: str | None
    metadata: dict

Allowed statuses:

supported
experimental
deprecated
unsupported
unknown

⸻

13.3 Compatibility report

def compatibility_report(
    self,
    *,
    include_plugins: bool = True,
    include_sdks: bool = True,
    include_runtime: bool = True,
) -> CompatibilityReport:
    ...

The report must include:

current Aletheia version
schema version
API version
Python version
platform
installed plugins
plugin compatibility
SDK versions
archive format support
migration support
warnings

⸻

13.4 CLI

aletheia compatibility report --db ./aletheia.db
aletheia compatibility plugins --db ./aletheia.db

⸻

14. SDK Contract

14.1 Python SDK v1

Required guarantees:

typed request/response models
stable error classes
timeout support
idempotency support
request ID support
sync client
async client
context-pack helper
candidate remember helper
feedback/outcome helper
audit/explain helper
stream-safe error handling
version compatibility check

⸻

14.2 Required Python SDK methods

client.health()
client.version()
client.context_pack(...)
client.retrieve(...)
client.remember_candidate(...)
client.remember_active(...)
client.feedback(...)
client.record_outcome(...)
client.ingest(...)
client.list_candidates(...)
client.promote_candidate(...)
client.audit(...)
client.explain_claim(...)
client.health_report(...)
client.backup_status(...)
client.compatibility_report()

Active writes require explicit method name:

client.remember_active(...)

This is intentional. The safer default should remain:

client.remember_candidate(...)

⸻

14.3 SDK version check

client.check_compatibility()

Must return:

{
    "client_version": "1.0.0",
    "server_version": "1.0.0",
    "api_version": "v1",
    "compatible": True,
    "warnings": []
}

⸻

14.4 TypeScript SDK

M9 may ship TypeScript SDK as optional but should define the contract if included.

Required methods mirror Python client.

const client = new AletheiaClient({
  baseUrl: "http://127.0.0.1:8765",
  token: process.env.ALETHEIA_TOKEN,
});

⸻

15. Adapter Contract

15.1 Adapter principle

Adapters connect agents to Aletheia without owning memory logic.

Required adapter behavior:

read context before agent call
optionally write candidate memories after agent call
record feedback/outcomes when available
default to candidate writes
preserve namespace/project/session
support conformance tests

⸻

15.2 Adapter scaffolding

aletheia adapters scaffold \
  --type generic-http \
  --name local-research-agent \
  --output ./local-research-agent

Scaffold should include:

README
config file
example agent loop
context-pack call
candidate remember call
feedback/outcome call
conformance test hook

⸻

15.3 Supported adapter templates

Required:

generic-http
mcp-client
python-sdk

Recommended:

langgraph
llamaindex
openai-compatible-tools
ollama-local-agent
custom-cli-agent

Optional frameworks should not be core dependencies.

⸻

15.4 Adapter certification

An adapter can be marked compatible only after passing:

aletheia conformance run --suite agent-adapter --target ./adapter

⸻

16. Documentation Contract

16.1 Documentation rule

If it is public, document it.

Required documentation sections:

Quickstart
Installation
Core concepts
Memory model
Evidence and claims
Confidence and decay
Contradiction handling
Curation
Ingestion and candidates
Inference and reflection
Self-improvement and evaluation
Service mode
MCP mode
Console mode
Backup and restore
Protected mode
Plugins
Adapters
SDKs
CLI
HTTP API
Troubleshooting
Migration
Security model
Production readiness

⸻

16.2 Executable examples

M9 should support doc example validation.

aletheia docs test-examples

Required example categories:

Python SDK examples
CLI examples
HTTP curl examples
MCP tool examples
plugin examples
adapter examples
backup/restore examples
protected-mode examples

⸻

16.3 DocumentationBuilder

def build_docs(
    *,
    output_dir: str,
    include_api_reference: bool = True,
    include_cli_reference: bool = True,
    validate_examples: bool = True,
) -> DocumentationBuild:
    ...

⸻

16.4 CLI

aletheia docs build --output ./site
aletheia docs test-examples
aletheia docs open

⸻

17. Doctor Contract

17.1 Purpose

aletheia doctor should diagnose install and integration problems.

It differs from M8 readiness:

readiness = production safety
doctor = install/runtime/integration diagnosis

⸻

17.2 Doctor checks

Required checks:

package version
Python version
platform
SQLite availability
schema version
database readability
migration pending
service reachable
auth configured
OpenAPI reachable
MCP available
console available
plugin compatibility
SDK compatibility
protected-mode status
backup status
integrity status
environment variables
optional dependencies

⸻

17.3 DoctorRun model

@dataclass
class DoctorRun:
    id: str
    status: str
    checks: list[dict]
    warnings: list[str]
    recommendations: list[str]
    created_at: datetime
    metadata: dict

Allowed statuses:

healthy
healthy_with_warnings
unhealthy
unknown

⸻

17.4 CLI

aletheia doctor
aletheia doctor --db ./aletheia.db --service http://127.0.0.1:8765

Expected output:

Aletheia Doctor
Status: healthy_with_warnings
Checks:
✓ Python version supported
✓ SQLite available
✓ Database schema current
✓ HTTP service reachable
! No verified backup in last 7 days
! Plugin local-embedding-provider has not run conformance
Recommendations:
- Run: aletheia backup create ...
- Run: aletheia conformance run --suite plugin --target local-embedding-provider

⸻

18. v1 Release Gate Contract

18.1 Purpose

M9 must provide a final release gate.

aletheia v1-gate run

This should aggregate all critical release checks.

⸻

18.2 Required v1 gate checks

unit tests passed
integration tests passed
migration tests passed
backup/restore tests passed
protected-mode tests passed
HTTP API conformance passed
MCP conformance passed
Python SDK conformance passed
plugin conformance base passed
CLI examples passed
docs examples passed
OpenAPI generated
MCP schema generated
release manifest generated
compatibility matrix generated
no critical integrity findings
no unrestricted default tokens
no external telemetry enabled by default
M8 readiness check passed or warnings acknowledged

⸻

18.3 V1ReleaseGateRun model

@dataclass
class V1ReleaseGateRun:
    id: str
    version: str
    status: str
    checks: list[dict]
    critical_failures: list[str]
    warnings: list[str]
    created_at: datetime
    metadata: dict

Allowed statuses:

passed
passed_with_warnings
failed
cancelled

⸻

18.4 CLI

aletheia v1-gate run
aletheia v1-gate report gate_001

⸻

19. HTTP API Additions

M9 extends the HTTP API under:

/v1

⸻

19.1 Plugin endpoints

GET  /v1/plugins
GET  /v1/plugins/{plugin_id}
POST /v1/plugins/install
POST /v1/plugins/{plugin_id}/enable
POST /v1/plugins/{plugin_id}/disable
GET  /v1/plugins/{plugin_id}/logs

Required capabilities:

memory:admin

or dedicated future capability:

memory:plugins

⸻

19.2 Conformance endpoints

GET  /v1/conformance/suites
POST /v1/conformance/run
GET  /v1/conformance/runs
GET  /v1/conformance/runs/{run_id}

⸻

19.3 Compatibility endpoints

GET /v1/compatibility/report
GET /v1/compatibility/matrix

⸻

19.4 Contract/deprecation endpoints

GET /v1/contracts
GET /v1/contracts/{contract_id}
GET /v1/deprecations

⸻

19.5 Doctor endpoints

POST /v1/doctor/run
GET  /v1/doctor/runs
GET  /v1/doctor/runs/{run_id}

⸻

19.6 Documentation endpoints

Optional but useful:

GET /v1/docs/status
POST /v1/docs/build

⸻

20. Storage Contract

20.1 Schema version

M9 updates schema version to:

1.0.0

⸻

20.2 Required new tables

public_contracts

CREATE TABLE public_contracts (
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

⸻

api_contract_versions

CREATE TABLE api_contract_versions (
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

Allowed api_type:

http
mcp
python_sdk
typescript_sdk
plugin
cli
archive

⸻

deprecation_notices

CREATE TABLE deprecation_notices (
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

⸻

compatibility_matrix_entries

CREATE TABLE compatibility_matrix_entries (
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

⸻

plugin_manifests

CREATE TABLE plugin_manifests (
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

⸻

plugin_installations

CREATE TABLE plugin_installations (
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

Allowed statuses:

installed
enabled
disabled
invalid
incompatible
blocked
failed
quarantined
uninstalled

⸻

plugin_capability_grants

CREATE TABLE plugin_capability_grants (
    id TEXT PRIMARY KEY,
    plugin_installation_id TEXT NOT NULL,
    permission TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

plugin_execution_log

CREATE TABLE plugin_execution_log (
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

⸻

plugin_settings

CREATE TABLE plugin_settings (
    id TEXT PRIMARY KEY,
    plugin_installation_id TEXT NOT NULL,
    setting_key TEXT NOT NULL,
    setting_value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

⸻

plugin_trust_records

CREATE TABLE plugin_trust_records (
    id TEXT PRIMARY KEY,
    plugin_installation_id TEXT NOT NULL,
    trust_level TEXT NOT NULL,
    reason TEXT NOT NULL,
    reviewed_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

conformance_suites

CREATE TABLE conformance_suites (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    suite_type TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT NOT NULL,
    required_for_v1 INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

conformance_cases

CREATE TABLE conformance_cases (
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

⸻

conformance_runs

CREATE TABLE conformance_runs (
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

⸻

conformance_results

CREATE TABLE conformance_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    duration_ms INTEGER,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

adapter_certifications

CREATE TABLE adapter_certifications (
    id TEXT PRIMARY KEY,
    adapter_name TEXT NOT NULL,
    adapter_type TEXT NOT NULL,
    adapter_version TEXT NOT NULL,
    conformance_run_id TEXT NOT NULL,
    status TEXT NOT NULL,
    certified_at TEXT,
    metadata_json TEXT
);

⸻

sdk_release_records

CREATE TABLE sdk_release_records (
    id TEXT PRIMARY KEY,
    sdk_name TEXT NOT NULL,
    sdk_version TEXT NOT NULL,
    language TEXT NOT NULL,
    api_contract_version TEXT NOT NULL,
    status TEXT NOT NULL,
    released_at TEXT,
    metadata_json TEXT
);

⸻

documentation_builds

CREATE TABLE documentation_builds (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    output_path TEXT NOT NULL,
    status TEXT NOT NULL,
    examples_validated INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

example_projects

CREATE TABLE example_projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    example_type TEXT NOT NULL,
    path TEXT NOT NULL,
    status TEXT NOT NULL,
    tested_at TEXT,
    metadata_json TEXT
);

⸻

doctor_runs

CREATE TABLE doctor_runs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    checks_json TEXT NOT NULL,
    warnings_json TEXT,
    recommendations_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

v1_release_gate_runs

CREATE TABLE v1_release_gate_runs (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    status TEXT NOT NULL,
    checks_json TEXT NOT NULL,
    critical_failures_json TEXT,
    warnings_json TEXT,
    created_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

21. CLI Contract

21.1 aletheia doctor

aletheia doctor
aletheia doctor \
  --db ./aletheia.db \
  --service http://127.0.0.1:8765

⸻

21.2 aletheia compatibility

aletheia compatibility report \
  --db ./aletheia.db
aletheia compatibility plugins \
  --db ./aletheia.db

⸻

21.3 aletheia plugins

aletheia plugins discover ./plugins
aletheia plugins install ./plugins/local-embedding-provider \
  --db ./aletheia.db
aletheia plugins enable local-embedding-provider \
  --db ./aletheia.db \
  --approve-permission read_claim_text \
  --reason "Needed for local embedding generation."
aletheia plugins disable local-embedding-provider \
  --db ./aletheia.db \
  --reason "Testing alternate provider."
aletheia plugins list \
  --db ./aletheia.db
aletheia plugins logs local-embedding-provider \
  --db ./aletheia.db

⸻

21.4 aletheia conformance

aletheia conformance list
aletheia conformance run \
  --suite plugin \
  --target local-embedding-provider \
  --db ./aletheia.db
aletheia conformance run \
  --suite http-api \
  --url http://127.0.0.1:8765
aletheia conformance report conf_run_001

⸻

21.5 aletheia adapters

aletheia adapters scaffold \
  --type generic-http \
  --name local-research-agent \
  --output ./examples/local-research-agent
aletheia adapters test \
  --path ./examples/local-research-agent
aletheia adapters certify \
  --path ./examples/local-research-agent

⸻

21.6 aletheia docs

aletheia docs build \
  --output ./site
aletheia docs test-examples
aletheia docs open

⸻

21.7 aletheia examples

aletheia examples list
aletheia examples create \
  --template local-agent \
  --output ./my-agent
aletheia examples test

⸻

21.8 aletheia contracts

aletheia contracts list
aletheia contracts show context_pack_schema_v1

⸻

21.9 aletheia deprecations

aletheia deprecations list
aletheia deprecations check

⸻

21.10 aletheia v1-gate

aletheia v1-gate run
aletheia v1-gate report gate_001

⸻

22. Console Contract

M9 console additions must include pages for:

Plugins
Plugin Detail
Plugin Permissions
Plugin Logs
Conformance Suites
Conformance Runs
Compatibility Matrix
Public Contracts
Deprecation Notices
SDK Versions
Documentation Builds
Example Projects
Doctor Reports
v1 Release Gate

⸻

22.1 Plugin page

Must show:

installed plugins
plugin type
version
status
permissions
network access flag
reads memory content flag
writes memory flag
conformance status
recent execution logs
enable/disable actions

High-risk permissions must be visually obvious.

⸻

22.2 Conformance page

Must show:

available suites
recent runs
pass/fail counts
critical failures
target plugin/adapter/API
report details

⸻

22.3 Compatibility page

Must show:

Aletheia version
schema version
Python version
platform
HTTP API version
MCP version
SDK versions
plugin compatibility
archive format support
migration range
warnings

⸻

22.4 Public contracts page

Must show:

stable contracts
experimental contracts
deprecated contracts
removed contracts
schema references
documentation links

⸻

22.5 v1 gate page

Must show:

v1 gate status
critical failures
warnings
test summaries
conformance summaries
documentation status
release manifest status

⸻

23. Backward Compatibility Contract

M9 must preserve M8 behavior.

The following modes must still work:

library mode
CLI mode
daemon mode
MCP mode
console mode
protected mode
backup/restore mode

The following must remain valid:

M0–M8 Python APIs
M0–M8 CLI commands
M6 HTTP API v1
M6 MCP tools
M7 console behavior
M8 backup/archive format support
M8 protected-mode behavior

Allowed M9 changes:

- Add plugin system.
- Add conformance suites.
- Add compatibility reporting.
- Add documentation builder.
- Add adapter scaffolding.
- Add public contract registry.
- Add deprecation registry.
- Add v1 release gate.

Not allowed:

- Breaking existing M8 databases without migration.
- Breaking HTTP API v1.
- Breaking MCP tools without deprecation.
- Breaking Python SDK v1 after release.
- Allowing plugins to bypass memory governance.
- Requiring cloud services.
- Enabling external telemetry by default.
- Installing or enabling plugins without user approval.

⸻

24. Migration Contract

24.1 Migration path

M9 must support:

0.9.x → 1.0.0

⸻

24.2 Migration rules

- Existing evidence remains unchanged.
- Existing claims remain unchanged.
- Existing candidates remain unchanged.
- Existing inferences/reflections remain unchanged.
- Existing service/auth/console data remains unchanged.
- Existing backup/restore/encryption data remains unchanged.
- New platform/plugin/conformance tables are added.
- No plugin is installed automatically.
- No plugin is enabled automatically.
- No external registry is contacted.
- Public contracts are registered.
- Default conformance suites are registered.
- Migration must be idempotent.

⸻

24.3 Recommended migration command

aletheia migrate plan --db ./aletheia.db

Then:

aletheia backup create \
  --db ./aletheia.db \
  --output ./backups/pre-v1.alet \
  --encrypt

Then:

aletheia migrate apply \
  --db ./aletheia.db \
  --to 1.0.0 \
  --verify-after

Then:

aletheia doctor --db ./aletheia.db

⸻

25. Test Contract

25.1 Public contract tests

Required tests:

test_public_contracts_registered
test_stable_contracts_have_schema_or_docs
test_experimental_contracts_marked
test_deprecated_contracts_have_replacement_or_reason
test_deprecation_window_enforced

⸻

25.2 Plugin tests

Required tests:

test_plugin_manifest_validation
test_plugin_install_does_not_enable_by_default
test_plugin_enable_requires_permission_approval
test_plugin_high_risk_permission_requires_explicit_reason
test_plugin_disable_stops_use
test_plugin_execution_logged
test_plugin_failure_does_not_corrupt_memory
test_plugin_cannot_bypass_candidate_write_policy
test_plugin_external_network_flag_visible

⸻

25.3 Plugin interface tests

Required tests:

test_extractor_plugin_returns_candidates_only
test_embedding_plugin_respects_protected_mode
test_vector_index_plugin_respects_namespace
test_importer_plugin_dry_run_default
test_exporter_plugin_respects_privacy_mode
test_inference_plugin_outputs_candidates_or_relations
test_key_provider_plugin_does_not_log_raw_key
test_agent_adapter_defaults_to_candidate_write

⸻

25.4 Conformance tests

Required tests:

test_conformance_suite_registered
test_conformance_run_records_results
test_http_api_conformance_passes_local_server
test_mcp_conformance_passes_local_mcp
test_plugin_conformance_detects_missing_manifest_field
test_adapter_conformance_detects_active_write_by_default
test_archive_conformance_detects_invalid_manifest
test_context_pack_schema_conformance

⸻

25.5 Compatibility tests

Required tests:

test_compatibility_report_includes_runtime
test_compatibility_report_includes_plugins
test_incompatible_plugin_warns
test_unknown_component_status_unknown
test_supported_component_status_supported

⸻

25.6 SDK tests

Required tests:

test_python_sdk_check_compatibility
test_python_sdk_context_pack
test_python_sdk_remember_candidate
test_python_sdk_remember_active_explicit
test_python_sdk_typed_errors
test_python_async_sdk_context_pack
test_sdk_idempotency_support

⸻

25.7 Adapter scaffold tests

Required tests:

test_adapter_scaffold_generic_http_created
test_adapter_scaffold_contains_readme
test_adapter_scaffold_contains_context_call
test_adapter_scaffold_candidate_write_default
test_adapter_scaffold_conformance_hook

⸻

25.8 Documentation tests

Required tests:

test_docs_build
test_docs_examples_cli_validate
test_docs_examples_python_validate
test_openapi_matches_server_routes
test_mcp_schema_matches_tools
test_cli_reference_generated
test_plugin_developer_guide_exists
test_adapter_developer_guide_exists

⸻

25.9 Doctor tests

Required tests:

test_doctor_healthy_minimal_install
test_doctor_warns_missing_backup
test_doctor_warns_pending_migration
test_doctor_warns_incompatible_plugin
test_doctor_warns_service_unreachable_when_service_expected

⸻

25.10 v1 gate tests

Required tests:

test_v1_gate_fails_on_critical_test_failure
test_v1_gate_fails_on_missing_docs
test_v1_gate_fails_on_conformance_failure
test_v1_gate_fails_on_external_telemetry_default
test_v1_gate_passes_clean_release_candidate

⸻

25.11 Migration tests

Required tests:

test_migration_from_m8_to_m9_adds_platform_tables
test_migration_registers_public_contracts
test_migration_registers_default_conformance_suites
test_migration_does_not_install_plugins
test_migration_does_not_contact_external_registry
test_migration_preserves_existing_memory
test_migration_is_idempotent

⸻

26. Golden M9 Tests

Golden test 1 — Plugin cannot bypass governance

Given:

A plugin tries to create an active claim directly without memory:write_active.

Expected:

- Operation is rejected.
- No active claim is created.
- Plugin execution is logged.
- Audit or warning records the denied attempt.

⸻

Golden test 2 — Candidate-first adapter

Given:

A newly scaffolded agent adapter.

When it writes memory:

remember_candidate(...)

Expected:

- Candidate memory is created.
- Active claim is not created.
- Evidence is linked.
- Adapter passes conformance.

⸻

Golden test 3 — Protected mode blocks unsafe embedding

Given:

Protected mode is enabled.
A plugin requests secret evidence text for embedding.
The plugin lacks permission to read secret content.

Expected:

- Secret content is not passed to plugin.
- Plugin receives redacted/omitted input.
- Warning is logged.
- No plaintext secret embedding is created.

⸻

Golden test 4 — HTTP API v1 conformance

Given:

Aletheia daemon running locally.

When:

aletheia conformance run --suite http-api

Expected:

- Health endpoint passes.
- Context-pack endpoint passes.
- Standard error envelope passes.
- Auth enforcement passes.
- Idempotency behavior passes.

⸻

Golden test 5 — Documentation examples are real

Given:

Quickstart documentation contains CLI and Python examples.

When:

aletheia docs test-examples

Expected:

- Examples execute successfully or are explicitly marked non-executable.
- Broken examples fail the docs build.

⸻

Golden test 6 — v1 release gate blocks unstable release

Given:

One critical conformance failure exists.

When:

aletheia v1-gate run

Expected:

- Gate fails.
- Critical failure is listed.
- Release is not marked v1-ready.

⸻

27. Acceptance Criteria

M9 is complete only when all of the following are true.

27.1 Platform stability acceptance

[ ] Public contracts are registered.
[ ] Stable/experimental/internal/deprecated contracts are clearly marked.
[ ] Semantic versioning policy exists.
[ ] Deprecation policy exists.
[ ] Compatibility matrix exists.
[ ] Migration from 0.9.x to 1.0.0 works.

⸻

27.2 Plugin acceptance

[ ] Plugin manifest format exists.
[ ] Plugins can be discovered.
[ ] Plugins can be installed.
[ ] Plugins are not enabled by default.
[ ] Plugin permissions require approval.
[ ] High-risk permissions require explicit reason.
[ ] Plugins can be disabled.
[ ] Plugin execution is logged.
[ ] Plugins cannot bypass memory governance.

⸻

27.3 Conformance acceptance

[ ] Conformance suites exist.
[ ] HTTP API conformance works.
[ ] MCP conformance works.
[ ] Plugin conformance works.
[ ] Agent adapter conformance works.
[ ] Context-pack schema conformance works.
[ ] Conformance runs are stored and reportable.

⸻

27.4 SDK acceptance

[ ] Python SDK v1 works.
[ ] Async Python SDK v1 works.
[ ] SDK compatibility check works.
[ ] Typed errors work.
[ ] Candidate write helper exists.
[ ] Active write helper is explicit.
[ ] SDK examples pass.

⸻

27.5 Adapter acceptance

[ ] Generic HTTP adapter scaffold works.
[ ] MCP client adapter scaffold works.
[ ] Python SDK adapter scaffold works.
[ ] Adapters default to candidate writes.
[ ] Adapter conformance tests pass.

⸻

27.6 Documentation acceptance

[ ] Documentation site builds.
[ ] Quickstart exists.
[ ] Architecture guide exists.
[ ] Plugin guide exists.
[ ] Adapter guide exists.
[ ] Security/privacy guide exists.
[ ] Backup/restore guide exists.
[ ] Migration guide exists.
[ ] CLI reference generated.
[ ] HTTP API reference generated.
[ ] MCP tool reference generated.
[ ] Examples are tested.

⸻

27.7 Doctor and compatibility acceptance

[ ] aletheia doctor works.
[ ] Doctor detects missing backup.
[ ] Doctor detects pending migration.
[ ] Doctor detects incompatible plugin.
[ ] Compatibility report works.
[ ] Compatibility report includes runtime, schema, APIs, SDKs, plugins, and archive formats.

⸻

27.8 v1 release acceptance

[ ] v1 gate exists.
[ ] v1 gate runs.
[ ] v1 gate fails on critical issues.
[ ] v1 gate passes clean release candidate.
[ ] Release manifest exists.
[ ] Changelog and migration notes exist.
[ ] Package install checks pass.

⸻

27.9 Console/API acceptance

[ ] Console exposes plugin management.
[ ] Console exposes conformance runs.
[ ] Console exposes compatibility matrix.
[ ] Console exposes public contracts and deprecations.
[ ] HTTP endpoints for plugins/conformance/compatibility work.
[ ] Capability checks apply to plugin and conformance operations.

⸻

28. M9 Demo Script

This should be the official M9 demo.

⸻

Step 1 — Migrate to v1

aletheia migrate plan \
  --db ./aletheia.db

Expected:

Migration plan: 0.9.x → 1.0.0
New platform tables listed.
Backup recommended.

Then:

aletheia backup create \
  --db ./aletheia.db \
  --output ./backups/pre-v1.alet \
  --encrypt

Then:

aletheia migrate apply \
  --db ./aletheia.db \
  --to 1.0.0 \
  --verify-after

Expected:

Schema migrated to 1.0.0.
Public contracts registered.
Default conformance suites registered.
No plugins installed automatically.

⸻

Step 2 — Run doctor

aletheia doctor \
  --db ./aletheia.db

Expected:

Doctor status:
healthy or healthy_with_warnings
Warnings are actionable.

⸻

Step 3 — Start service and console

aletheia serve \
  --db ./aletheia.db \
  --host 127.0.0.1 \
  --port 8765 \
  --with-console

Expected:

HTTP API available.
Console available.
OpenAPI available.

⸻

Step 4 — Run HTTP conformance

aletheia conformance run \
  --suite http-api \
  --url http://127.0.0.1:8765

Expected:

HTTP API conformance passed.

⸻

Step 5 — Install plugin

aletheia plugins install \
  ./plugins/local-embedding-provider \
  --db ./aletheia.db

Expected:

Plugin installed but not enabled.
Permissions shown.

⸻

Step 6 — Enable plugin with explicit permission

aletheia plugins enable local-embedding-provider \
  --db ./aletheia.db \
  --approve-permission read_claim_text \
  --approve-permission write_index \
  --reason "Local embedding provider for hybrid retrieval."

Expected:

Plugin enabled.
Permission grants recorded.
Audit event written.

⸻

Step 7 — Run plugin conformance

aletheia conformance run \
  --suite plugin \
  --target local-embedding-provider \
  --db ./aletheia.db

Expected:

Plugin conformance passed.

⸻

Step 8 — Scaffold agent adapter

aletheia adapters scaffold \
  --type generic-http \
  --name local-research-agent \
  --output ./examples/local-research-agent

Expected:

Adapter scaffold created.
Candidate-first memory write included.
README generated.
Conformance hook generated.

⸻

Step 9 — Run adapter conformance

aletheia conformance run \
  --suite agent-adapter \
  --target ./examples/local-research-agent

Expected:

Adapter conformance passed.

⸻

Step 10 — Build and test docs

aletheia docs build \
  --output ./site
aletheia docs test-examples

Expected:

Docs build successful.
Examples validated.

⸻

Step 11 — Run compatibility report

aletheia compatibility report \
  --db ./aletheia.db

Expected:

Aletheia version: 1.0.0
Schema version: 1.0.0
HTTP API: v1 supported
MCP: v1 supported
Plugins: compatible
SDKs: compatible
Warnings: none or actionable

⸻

Step 12 — Run v1 gate

aletheia v1-gate run

Expected:

v1 release gate passed or passed_with_warnings.
No critical failures.

⸻

29. M9 Implementation Checklist

Public contracts

[ ] Add PublicContract model
[ ] Add public contract registry
[ ] Register HTTP API v1
[ ] Register MCP tool contracts
[ ] Register Python SDK contracts
[ ] Register plugin interface contracts
[ ] Register context-pack schema
[ ] Register archive format contract
[ ] Add deprecation policy
[ ] Add deprecation notices

⸻

Plugin system

[ ] Add PluginManifest model
[ ] Add PluginInstallation model
[ ] Add PluginManager
[ ] Add plugin discovery
[ ] Add plugin install
[ ] Add plugin enable/disable
[ ] Add permission approval
[ ] Add plugin execution logging
[ ] Add plugin validator
[ ] Add plugin trust records
[ ] Add plugin settings

⸻

Plugin interfaces

[ ] Define ExtractorPlugin
[ ] Define EmbeddingProviderPlugin
[ ] Define VectorIndexPlugin
[ ] Define ImporterPlugin
[ ] Define ExporterPlugin
[ ] Define InferenceEnginePlugin
[ ] Define KeyProviderPlugin
[ ] Define ReportGeneratorPlugin
[ ] Define AgentAdapterPlugin
[ ] Add interface conformance tests

⸻

Conformance

[ ] Add ConformanceSuite model
[ ] Add ConformanceCase model
[ ] Add ConformanceRun model
[ ] Add ConformanceResult model
[ ] Implement run_conformance()
[ ] Add HTTP API conformance suite
[ ] Add MCP conformance suite
[ ] Add plugin conformance suite
[ ] Add adapter conformance suite
[ ] Add context-pack schema conformance suite
[ ] Add archive conformance suite

⸻

Compatibility

[ ] Add CompatibilityMatrixEntry model
[ ] Add compatibility report
[ ] Add plugin compatibility checks
[ ] Add SDK compatibility checks
[ ] Add runtime compatibility checks
[ ] Add CLI commands

⸻

SDKs

[ ] Stabilize Python SDK v1
[ ] Stabilize async Python SDK v1
[ ] Add typed request/response models
[ ] Add typed errors
[ ] Add compatibility check
[ ] Add idempotency support
[ ] Add tested examples
[ ] Optional TypeScript SDK v1

⸻

Adapters

[ ] Add adapter scaffold generator
[ ] Add generic HTTP scaffold
[ ] Add MCP client scaffold
[ ] Add Python SDK scaffold
[ ] Add candidate-first write behavior
[ ] Add adapter conformance hook
[ ] Add example local agent

⸻

Documentation

[ ] Add documentation builder
[ ] Add docs site
[ ] Add quickstart
[ ] Add concepts guide
[ ] Add architecture guide
[ ] Add plugin guide
[ ] Add adapter guide
[ ] Add SDK reference
[ ] Add CLI reference
[ ] Add HTTP API reference
[ ] Add MCP guide
[ ] Add security/privacy guide
[ ] Add backup/restore guide
[ ] Add migration guide
[ ] Add troubleshooting guide
[ ] Add docs example tests

⸻

Doctor and v1 gate

[ ] Add DoctorService
[ ] Add doctor CLI
[ ] Add doctor HTTP endpoint
[ ] Add V1ReleaseGate
[ ] Add v1-gate CLI
[ ] Add gate checks
[ ] Add release gate tests

⸻

Console/API

[ ] Add plugin console page
[ ] Add plugin permissions page
[ ] Add conformance console page
[ ] Add compatibility console page
[ ] Add contracts/deprecations console page
[ ] Add doctor/v1-gate console page
[ ] Add plugin HTTP endpoints
[ ] Add conformance HTTP endpoints
[ ] Add compatibility HTTP endpoints

⸻

Migration

[ ] Add schema version 1.0.0
[ ] Add migration from 0.9.x
[ ] Add M9 tables
[ ] Register public contracts
[ ] Register default conformance suites
[ ] Ensure no plugins installed automatically
[ ] Ensure no external registry contacted
[ ] Add migration tests

⸻

Tests

[ ] Public contract tests
[ ] Plugin tests
[ ] Plugin interface tests
[ ] Conformance tests
[ ] Compatibility tests
[ ] SDK tests
[ ] Adapter tests
[ ] Documentation tests
[ ] Doctor tests
[ ] v1 gate tests
[ ] Migration tests
[ ] Golden M9 tests

⸻

30. M9 Definition of Done

M9 is done when this statement is true:

Aletheia is stable enough for other developers, agents, and plugins to build on without relying on private behavior or risking memory corruption.

More practically, M9 is complete when Aletheia can do all of this:

- Publish stable v1 public contracts.
- Enforce semantic versioning.
- Document public APIs.
- Mark experimental/internal/deprecated APIs clearly.
- Install and manage plugins safely.
- Require plugin permissions explicitly.
- Prevent plugins from bypassing governance.
- Run conformance suites.
- Certify adapters.
- Provide stable Python SDK v1.
- Provide examples and scaffolds for local agents.
- Build and validate documentation.
- Generate compatibility reports.
- Run doctor diagnostics.
- Pass the v1 release gate.
- Preserve every M0–M8 behavior.

M9 is the point where Aletheia stops being only a powerful local memory system and becomes a platform.

It is no longer just something an agent can use.
It is something an ecosystem can trust.