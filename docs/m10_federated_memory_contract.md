Aletheia M10 Contract

Milestone: Federated Memory, Multi-Agent Governance, and Secure Sync

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
M8 proved that Aletheia can survive production realities.
M9 proved that Aletheia is a stable v1 platform with plugins, conformance, SDKs, and public contracts.
M10 must prove that Aletheia can share memory safely across agents, devices, users, and organizations without losing local control.

M10 is where Aletheia becomes federated.

M0  = Remember
M1  = Recall
M2  = Trust
M3  = Understand
M4  = Reason
M5  = Improve
M6  = Connect
M7  = Operate
M8  = Harden
M9  = Stabilize
M10 = Federate

The core M10 promise:

Aletheia can synchronize selected memory across local instances, agents, devices, and trusted peers using explicit sharing grants, encrypted exchange, provenance-preserving imports, conflict-aware merge policies, revocation records, and human-governed trust boundaries.

M10 is not “cloud Aletheia.”
M10 is not “everyone shares all memory.”
M10 is not “one global truth store.”

M10 is local-first federation.

Aletheia remains sovereign on each machine. Federation is explicit, scoped, auditable, encrypted, and reversible where possible.

⸻

2. M10 Name

M10 — Federated Memory

Fuller name:

M10 — Federated Memory, Multi-Agent Governance, and Secure Sync

Recommended short name:

M10 — Federated Memory

⸻

3. M10 Contract Status

milestone: M10
name: Federated Memory
depends_on: M9
version_target: 1.1.0
stability: federation-beta
breaking_changes_allowed: no_for_v1_public_contracts
storage_migration_required: yes
federation_required: yes
sync_required: yes
encrypted_exchange_required: yes
multi_agent_governance_required: yes
cloud_required: no
external_relay_required: no
external_telemetry_required: no
enterprise_sso_required: no
primary_theme: local_first_federation_and_governed_sync

Important clarification:

M10 must support local-first sync.
M10 must support encrypted share bundles.
M10 must support peer-to-peer or file-based exchange.
M10 may support optional relay transports later.
M10 must not require cloud infrastructure.
M10 must not send memory to any peer without explicit sharing grants.
M10 must not allow remote peers to bypass Aletheia governance.

⸻

4. M9 Assumptions

M10 assumes M9 already provides:

- Stable v1 public contracts
- Plugin system
- Conformance suites
- HTTP API v1
- MCP tools
- Python SDK v1
- Optional TypeScript SDK
- Local daemon
- Local console
- Backup/restore
- Protected mode
- Encryption support
- Redaction/forget workflows
- Integrity checks
- Import/export archive format
- Agent adapters
- Compatibility reports
- Doctor diagnostics
- v1 release gate

M10 builds on this by adding:

- federation identities
- trusted peers
- share grants
- sync collections
- encrypted share packages
- bidirectional sync
- multi-agent governance
- remote memory trust domains
- sync conflict detection
- sync conflict resolution
- revocation and consent records
- federation conformance tests

⸻

5. M10 Primary Objective

M10 must make this flow work reliably.

On machine A:

aletheia federation init \
  --db ./aletheia-a.db \
  --name default-laptop

Create a share:

aletheia shares create \
  --db ./aletheia-a.db \
  --namespace user/default/projects/aletheia \
  --name aletheia-project-share \
  --permissions read,candidate_write,feedback \
  --privacy-ceiling personal \
  --recipient default-workstation

Export encrypted share bundle:

aletheia shares export \
  --db ./aletheia-a.db \
  --share share_001 \
  --output ./aletheia-project-share.aletsync \
  --encrypt

On machine B:

aletheia shares import \
  --db ./aletheia-b.db \
  --input ./aletheia-project-share.aletsync \
  --trust-policy trusted_device

Then:

aletheia sync run \
  --db ./aletheia-b.db \
  --peer default-laptop \
  --collection aletheia-project-share

Expected behavior:

- Only explicitly shared namespace content is included.
- Secret content is excluded unless explicitly allowed.
- Share bundle is encrypted.
- Imported records preserve source provenance.
- Imported active claims remain active only if trust policy permits.
- Otherwise imported claims become candidates or remote claims.
- Conflicts are detected, not overwritten.
- Deletions and redactions propagate through tombstones.
- Both sides retain audit records.

⸻

6. M10 Non-Negotiable Principles

6.1 Nothing leaves without an explicit share grant

Federation must be opt-in.

Aletheia must not sync:

all memory
all namespaces
all projects
all evidence
secret content
auth tokens
private keys
local-only audit records

unless the user explicitly grants it.

A share grant defines exactly what can leave.

⸻

6.2 Local sovereignty remains intact

Every Aletheia instance is authoritative for its own local store.

Remote memory is never automatically “the truth.”

Imported memory must carry:

origin instance
origin namespace
origin claim ID
origin evidence ID
trust domain
import time
sync run ID
source peer

Local Aletheia decides how to treat it.

⸻

6.3 Federation must preserve provenance

A synced memory must answer:

Where was this originally created?
Who or what created it?
What evidence supports it?
Was it direct, candidate, inferred, reflected, or imported?
Which peer sent it?
Which share grant allowed it?
Which sync run imported it?

No provenance means no federation.

⸻

6.4 Imported memory is not automatically trusted

Default import policy:

remote active claim → local candidate or remote_claim

unless the peer is explicitly trusted for that namespace and memory type.

Trust policies may allow:

trusted_device imports active project state
trusted_team imports active shared decisions
untrusted_import imports candidates only

The default should be conservative.

⸻

6.5 Sync conflicts are first-class objects

A sync conflict must not be resolved by silent last-write-wins unless a policy explicitly says so.

Sync conflicts include:

same claim edited differently
same subject/predicate incompatible across peers
local redaction vs remote update
local deletion vs remote active claim
different scopes
different confidence values
different privacy labels
different policy versions

Aletheia must preserve both sides and ask for resolution or apply an approved merge policy.

⸻

6.6 Deletion and redaction must propagate

If a shared evidence item is redacted on its origin instance, receivers must get a tombstone/redaction notice during sync.

Receivers must then:

redact local imported content
invalidate derived records
update indexes
record audit event
surface review task if needed

M10 must also be honest:

Revocation prevents future access.
It cannot guarantee the peer forgets data already received unless that peer cooperates.

⸻

6.7 Remote write access is candidate-first by default

A remote peer may suggest memory.

It should not be able to directly mutate canonical local truth unless explicitly granted.

Default remote write mode:

candidate_write

Not:

active_write
core_promotion
policy_application
deletion

⸻

6.8 Federation identities must be cryptographic

Peers must have stable identities backed by key material.

Each instance should have:

instance_id
public key
local display name
fingerprint
created_at
trust status

The private key must be protected and never exported accidentally.

⸻

6.9 Remote sync must be encrypted

Any share bundle or remote sync payload containing memory content must be encrypted unless explicitly exported in redacted or public mode.

Protected-mode databases must require encrypted sync packages by default.

⸻

6.10 Federation must be auditable

Every federation action must be auditable:

identity created
peer added
peer trusted
share grant created
share exported
share imported
sync run started
sync run completed
remote change applied
conflict detected
conflict resolved
share revoked
peer revoked
redaction propagated

⸻

7. M10 Scope

In Scope

M10 includes:

1. Federation identity
2. Peer registration
3. Peer trust model
4. Share grants
5. Share recipients
6. Sync collections
7. Encrypted share bundles
8. File-based sync
9. Local peer-to-peer sync over HTTP
10. Federation protocol v1
11. Sync changesets
12. Replication cursors
13. Sync conflict model
14. Sync conflict resolution
15. Remote memory source tracking
16. Remote trust domains
17. Import trust policies
18. Candidate-first remote writes
19. Redaction/deletion propagation
20. Revocation records
21. Consent records
22. Workspace/team namespace model
23. Agent group governance
24. Federation audit log
25. Federation conformance suite
26. CLI support
27. HTTP API extensions
28. Console support
29. SDK support
30. Migration from M9 to M10
31. Golden federation tests

⸻

Out of Scope

M10 explicitly excludes:

Hosted cloud sync service
Managed relay service
Enterprise SSO
Global identity provider
Public plugin marketplace
Multi-node distributed database
Consensus protocol
Real-time collaborative editing
Legal compliance automation
Guaranteed remote erasure from untrusted peers
Commercial licensing enforcement

M10 may define interfaces for future relay/cloud options, but the milestone must work without them.

⸻

8. M10 Deliverables

8.1 Library Deliverables

- FederationIdentity model
- PeerDevice model
- TrustDomain model
- ShareGrant model
- ShareRecipient model
- SyncCollection model
- SyncChangeSet model
- SyncChangeItem model
- SyncRun model
- ReplicationCursor model
- RemoteMemorySource model
- ImportTrustPolicy model
- SyncConflict model
- SyncConflictResolution model
- FederationAuditEvent model
- ConsentRecord model
- RevocationRecord model
- SyncTombstone model
- Workspace model
- WorkspaceMember model
- AgentGroup model
- FederationService
- PeerService
- ShareService
- SyncService
- SyncConflictResolver
- FederationCryptoService
- FederationConformanceSuite

⸻

8.2 Protocol Deliverables

- Federation protocol v1
- Share bundle format .aletsync
- Sync changeset schema
- Peer identity schema
- Share grant schema
- Revocation notice schema
- Sync tombstone schema
- Federation conformance tests

⸻

8.3 Storage Deliverables

M10 adds:

- federation_identities
- peer_devices
- trust_domains
- share_grants
- share_recipients
- sync_collections
- sync_changesets
- sync_change_items
- sync_runs
- replication_cursors
- remote_memory_sources
- import_trust_policies
- sync_conflicts
- sync_conflict_resolutions
- federation_audit_events
- consent_records
- revocation_records
- sync_tombstones
- workspaces
- workspace_members
- agent_groups
- agent_group_members

⸻

8.4 CLI Deliverables

M10 adds:

aletheia federation
aletheia peers
aletheia shares
aletheia sync
aletheia workspaces
aletheia grants
aletheia revocations
aletheia federation-conformance

Existing M0–M9 CLI commands must remain valid.

⸻

8.5 Console Deliverables

M10 adds console pages for:

Federation Overview
Local Identity
Peers
Share Grants
Sync Collections
Sync Runs
Sync Conflicts
Remote Sources
Trust Domains
Revocations
Workspaces
Agent Groups
Federation Audit

⸻

8.6 SDK Deliverables

- Python SDK federation methods
- Async Python SDK federation methods
- HTTP API federation endpoints
- Optional TypeScript SDK federation methods
- Adapter support for shared namespaces

⸻

8.7 Test Deliverables

- Federation identity tests
- Peer trust tests
- Share grant tests
- Share bundle tests
- Encrypted sync tests
- File-based sync tests
- HTTP peer sync tests
- Candidate-first remote write tests
- Trust policy tests
- Sync conflict tests
- Redaction propagation tests
- Revocation tests
- Workspace tests
- Console/API tests
- SDK tests
- Migration tests
- Golden federation tests

⸻

9. Federation Identity Contract

9.1 FederationIdentity model

@dataclass
class FederationIdentity:
    id: str
    instance_id: str
    display_name: str
    public_key: str
    key_fingerprint: str
    key_algorithm: str
    created_at: datetime
    rotated_at: datetime | None
    status: str
    metadata: dict

Allowed statuses:

active
rotated
revoked
disabled

⸻

9.2 memory.create_federation_identity()

def create_federation_identity(
    self,
    *,
    display_name: str,
    key_algorithm: str = "default",
    protected: bool = True,
) -> FederationIdentity:
    ...

Required behavior:

- Generate stable instance ID.
- Generate or register public/private key pair.
- Store public identity.
- Protect private key.
- Write audit event.
- Refuse to overwrite existing active identity unless rotation is requested.

⸻

9.3 Key rotation

def rotate_federation_key(
    self,
    *,
    reason: str,
    actor: str = "user",
) -> FederationIdentity:
    ...

Required behavior:

- Create new key pair.
- Mark previous key as rotated.
- Create revocation/update notice for peers.
- Preserve old key metadata for verifying old signed records.
- Write audit event.

⸻

10. Peer Management Contract

10.1 PeerDevice model

@dataclass
class PeerDevice:
    id: str
    peer_instance_id: str
    display_name: str
    public_key: str
    key_fingerprint: str
    trust_status: str
    trust_domain_id: str | None
    added_at: datetime
    trusted_at: datetime | None
    revoked_at: datetime | None
    metadata: dict

Allowed trust statuses:

unknown
untrusted
trusted_device
trusted_user
trusted_team
revoked
blocked

⸻

10.2 memory.add_peer()

def add_peer(
    self,
    *,
    peer_identity_file: str | None = None,
    peer_identity: dict | None = None,
    display_name: str | None = None,
    trust_status: str = "unknown",
    reason: str,
) -> PeerDevice:
    ...

Required behavior:

- Validate peer identity.
- Store public key and fingerprint.
- Default to unknown trust.
- Require explicit trust upgrade.
- Write audit event.

⸻

10.3 memory.trust_peer()

def trust_peer(
    self,
    peer_id: str,
    *,
    trust_status: str,
    trust_domain_id: str | None = None,
    reason: str,
    actor: str = "user",
) -> PeerDevice:
    ...

Required behavior:

- Require explicit reason.
- Update trust status.
- Write federation audit event.
- Create review task if high-trust permission is granted.

⸻

10.4 Peer revocation

def revoke_peer(
    peer_id: str,
    *,
    reason: str,
    actor: str = "user",
    revoke_shares: bool = True,
) -> RevocationRecord:
    ...

Required behavior:

- Mark peer revoked.
- Optionally revoke active shares.
- Generate revocation notice.
- Prevent future sync with peer.
- Write audit event.

⸻

11. Trust Domain Contract

11.1 Purpose

Trust domains define how imported memories from a peer should be treated.

Examples:

personal_trusted_devices
team_shared_project
untrusted_imports
public_reference_data

⸻

11.2 TrustDomain model

@dataclass
class TrustDomain:
    id: str
    name: str
    description: str
    default_import_policy: str
    allowed_memory_types: list[str]
    max_privacy_level: str
    allow_active_import: bool
    allow_candidate_import: bool
    allow_feedback_import: bool
    allow_remote_redaction: bool
    created_at: datetime
    updated_at: datetime
    metadata: dict

Allowed import policies:

candidate_only
remote_claim_only
active_if_trusted
active_for_project_state
manual_review
reject_by_default

Recommended default:

candidate_only

⸻

12. Share Grant Contract

12.1 Purpose

A share grant defines what memory may be shared with whom.

It is the core privacy and governance object in M10.

⸻

12.2 ShareGrant model

@dataclass
class ShareGrant:
    id: str
    name: str
    namespace: str
    project_id: str | None
    grant_type: str
    permissions: list[str]
    memory_types: list[str] | None
    statuses: list[str] | None
    privacy_ceiling: str
    include_evidence: bool
    include_reflections: bool
    include_inferences: bool
    include_audit: bool
    candidate_write_allowed: bool
    active_write_allowed: bool
    expires_at: datetime | None
    status: str
    created_at: datetime
    revoked_at: datetime | None
    reason: str
    metadata: dict

Allowed grant types:

read_only
read_write_candidate
read_write_active
feedback_only
sync_bidirectional
export_only

Allowed permissions:

read_claims
read_evidence
read_reflections
read_inferences
read_audit
write_candidate
write_feedback
write_active
sync_pull
sync_push
receive_redactions

Allowed statuses:

active
paused
revoked
expired
disabled

⸻

12.3 memory.create_share_grant()

def create_share_grant(
    self,
    *,
    name: str,
    namespace: str,
    recipient_peer_ids: list[str],
    grant_type: str = "read_write_candidate",
    permissions: list[str],
    privacy_ceiling: str = "personal",
    memory_types: list[str] | None = None,
    include_evidence: bool = True,
    include_reflections: bool = True,
    include_inferences: bool = False,
    expires_at: datetime | None = None,
    reason: str,
) -> ShareGrant:
    ...

Required behavior:

- Validate namespace.
- Validate recipient peers.
- Enforce protected-mode restrictions.
- Refuse secret sharing unless explicitly allowed.
- Create share recipients.
- Write audit event.
- Create consent record if required.

⸻

12.4 ShareRecipient model

@dataclass
class ShareRecipient:
    id: str
    share_grant_id: str
    peer_id: str
    recipient_public_key: str
    status: str
    created_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    metadata: dict

Allowed statuses:

pending
accepted
active
revoked
expired
rejected

⸻

13. Sync Collection Contract

13.1 Purpose

A sync collection is the actual stream of memory objects shared under a grant.

One share grant may define access.
A sync collection tracks synchronization state.

⸻

13.2 SyncCollection model

@dataclass
class SyncCollection:
    id: str
    share_grant_id: str
    namespace: str
    project_id: str | None
    name: str
    direction: str
    transport: str
    status: str
    created_at: datetime
    updated_at: datetime
    metadata: dict

Allowed directions:

push
pull
bidirectional

Allowed transports:

file_bundle
local_http
manual_import
plugin_transport

Allowed statuses:

active
paused
revoked
failed
disabled

⸻

13.3 ReplicationCursor model

@dataclass
class ReplicationCursor:
    id: str
    collection_id: str
    peer_id: str
    last_change_id: str | None
    last_synced_at: datetime | None
    status: str
    metadata: dict

⸻

14. Sync Change Contract

14.1 SyncChangeSet model

@dataclass
class SyncChangeSet:
    id: str
    collection_id: str
    origin_instance_id: str
    target_peer_id: str | None
    sequence_number: int
    signed: bool
    signature: str | None
    encrypted: bool
    created_at: datetime
    item_count: int
    metadata: dict

⸻

14.2 SyncChangeItem model

@dataclass
class SyncChangeItem:
    id: str
    changeset_id: str
    object_id: str
    object_type: str
    operation: str
    object_hash: str
    previous_hash: str | None
    payload_ref: str | None
    privacy_level: str
    created_at: datetime
    metadata: dict

Allowed object types:

evidence_event
claim
candidate_claim
reflection
inference
entity
category
conflict
confidence_snapshot
audit_event
redaction_event
tombstone
policy
procedure

Allowed operations:

create
update
status_change
scope_change
confidence_update
redact
tombstone
delete_marker
relationship_add
relationship_remove

⸻

14.3 Change requirements

Every sync change item must include:

object type
object ID
operation
hash
origin instance
created_at
privacy level
provenance reference

State-changing objects must also include:

audit reference

⸻

15. Share Bundle Contract

15.1 File extension

M10 defines a sync/share archive:

.aletsync

Example:

aletheia-project-share.aletsync

⸻

15.2 Bundle contents

Unencrypted structure:

manifest.json
peer_identity.json
share_grant.json
changesets/
payloads/
checksums.sha256
signature.json

Encrypted structure:

manifest.json
encrypted_payload.bin
encryption_metadata.json
checksums.sha256
signature.json

⸻

15.3 Required manifest fields

{
  "format": "aletsync",
  "format_version": "1.0",
  "origin_instance_id": "inst_...",
  "share_grant_id": "share_...",
  "collection_id": "sync_...",
  "created_at": "2026-06-30T00:00:00Z",
  "encrypted": true,
  "signed": true,
  "item_counts": {},
  "privacy_ceiling": "personal",
  "schema_version": "1.1.0"
}

⸻

16. Sync Import Contract

16.1 RemoteMemorySource model

@dataclass
class RemoteMemorySource:
    id: str
    local_object_id: str
    local_object_type: str
    remote_object_id: str
    remote_object_type: str
    origin_instance_id: str
    peer_id: str
    share_grant_id: str
    sync_run_id: str
    trust_domain_id: str | None
    imported_at: datetime
    metadata: dict

⸻

16.2 ImportTrustPolicy model

@dataclass
class ImportTrustPolicy:
    id: str
    name: str
    trust_domain_id: str | None
    peer_id: str | None
    namespace: str | None
    import_mode: str
    allow_active_claims: bool
    allow_candidates: bool
    allow_evidence: bool
    allow_reflections: bool
    allow_inferences: bool
    require_review_for_conflicts: bool
    created_at: datetime
    updated_at: datetime
    metadata: dict

Allowed import modes:

candidate_only
remote_claim_only
active_if_trusted
manual_review
reject_by_default

⸻

16.3 Import behavior

When importing a remote claim:

Remote object	Default local treatment
active claim from unknown peer	candidate
active claim from trusted device	active if policy allows
core memory from any peer	active or candidate, never core by default
remote inference	inference candidate
remote reflection	reflection candidate or active if policy allows
remote evidence	evidence with remote source marker
remote deletion/redaction	tombstone/redaction notice
remote policy	candidate/policy proposal only

Core memories must not sync as local core by default.

⸻

17. Sync Run Contract

17.1 SyncRun model

@dataclass
class SyncRun:
    id: str
    collection_id: str
    peer_id: str | None
    direction: str
    transport: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    sent_count: int
    received_count: int
    applied_count: int
    conflict_count: int
    redaction_count: int
    warnings: list[str]
    metadata: dict

Allowed statuses:

planned
running
completed
completed_with_conflicts
failed
cancelled
blocked

⸻

17.2 memory.sync()

def sync(
    self,
    *,
    collection_id: str,
    peer_id: str | None = None,
    direction: str = "bidirectional",
    transport: str = "file_bundle",
    input_path: str | None = None,
    output_path: str | None = None,
    dry_run: bool = False,
) -> SyncRun:
    ...

Required behavior:

- Validate share grant.
- Validate peer trust.
- Enforce privacy ceiling.
- Encrypt exported payloads.
- Verify signatures on import.
- Apply import trust policy.
- Detect conflicts.
- Apply non-conflicting changes.
- Create review tasks for conflicts.
- Write federation audit events.

⸻

18. Sync Conflict Contract

18.1 SyncConflict model

@dataclass
class SyncConflict:
    id: str
    namespace: str
    collection_id: str
    sync_run_id: str
    conflict_type: str
    local_object_id: str | None
    local_object_type: str | None
    remote_object_id: str | None
    remote_object_type: str | None
    origin_instance_id: str
    status: str
    severity: str
    created_at: datetime
    resolved_at: datetime | None
    metadata: dict

Allowed conflict types:

claim_value_conflict
status_conflict
scope_conflict
privacy_label_conflict
delete_update_conflict
redaction_update_conflict
confidence_conflict
policy_conflict
duplicate_remote_object
missing_dependency
unsupported_object_type

Allowed statuses:

unresolved
resolved
ignored
deferred
blocked

⸻

18.2 SyncConflictResolution model

@dataclass
class SyncConflictResolution:
    id: str
    sync_conflict_id: str
    strategy: str
    reason: str
    actor: str
    applied_at: datetime
    metadata: dict

Allowed strategies:

keep_local
accept_remote_as_candidate
accept_remote_active
merge_as_conflict_family
scope_both
time_scope
reject_remote
defer
manual_merge

Recommended default:

accept_remote_as_candidate

or:

merge_as_conflict_family

depending on conflict type.

⸻

19. Revocation and Consent Contract

19.1 ConsentRecord model

@dataclass
class ConsentRecord:
    id: str
    namespace: str
    consent_type: str
    target_id: str
    target_type: str
    granted_by: str
    granted_to_peer_id: str | None
    reason: str
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    metadata: dict

Allowed consent types:

share_namespace
share_project
share_evidence
share_sensitive
allow_remote_candidate_write
allow_remote_active_write
allow_redaction_propagation

⸻

19.2 RevocationRecord model

@dataclass
class RevocationRecord:
    id: str
    revocation_type: str
    target_id: str
    target_type: str
    peer_id: str | None
    reason: str
    actor: str
    created_at: datetime
    propagated_at: datetime | None
    metadata: dict

Allowed revocation types:

peer_revocation
share_revocation
consent_revocation
key_revocation
object_revocation
redaction_notice

⸻

19.3 Revocation behavior

Revoking a share must:

- Mark share grant revoked.
- Prevent future exports.
- Prevent future imports under that grant.
- Emit revocation notice for peer.
- Record audit event.
- Create warning that already-received data cannot be forcibly erased on untrusted peers.

⸻

20. Workspaces and Agent Groups

20.1 Workspace model

@dataclass
class Workspace:
    id: str
    namespace: str
    name: str
    description: str | None
    owner_identity_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    metadata: dict

Allowed statuses:

active
archived
disabled

⸻

20.2 WorkspaceMember model

@dataclass
class WorkspaceMember:
    id: str
    workspace_id: str
    member_type: str
    member_id: str
    role: str
    status: str
    joined_at: datetime
    metadata: dict

Allowed member types:

local_user
peer_device
agent
api_client

Allowed roles:

owner
admin
curator
contributor
reader
agent

⸻

20.3 AgentGroup model

@dataclass
class AgentGroup:
    id: str
    namespace: str
    name: str
    description: str | None
    default_capabilities: list[str]
    created_at: datetime
    updated_at: datetime
    metadata: dict

Agent groups allow local multi-agent governance without giving every agent full memory access.

⸻

21. HTTP API Additions

M10 extends HTTP API under:

/v1

⸻

21.1 Federation identity endpoints

GET  /v1/federation/identity
POST /v1/federation/identity
POST /v1/federation/identity/rotate
GET  /v1/federation/status

⸻

21.2 Peer endpoints

GET  /v1/peers
POST /v1/peers
GET  /v1/peers/{peer_id}
POST /v1/peers/{peer_id}/trust
POST /v1/peers/{peer_id}/revoke

⸻

21.3 Share endpoints

GET  /v1/shares
POST /v1/shares
GET  /v1/shares/{share_id}
POST /v1/shares/{share_id}/export
POST /v1/shares/import
POST /v1/shares/{share_id}/revoke

⸻

21.4 Sync endpoints

GET  /v1/sync/collections
POST /v1/sync/collections
POST /v1/sync/run
GET  /v1/sync/runs
GET  /v1/sync/runs/{sync_run_id}
GET  /v1/sync/conflicts
POST /v1/sync/conflicts/{conflict_id}/resolve

⸻

21.5 Workspace endpoints

GET  /v1/workspaces
POST /v1/workspaces
GET  /v1/workspaces/{workspace_id}
POST /v1/workspaces/{workspace_id}/members
DELETE /v1/workspaces/{workspace_id}/members/{member_id}

⸻

21.6 Required capabilities

M10 adds capabilities:

memory:federation
memory:peers
memory:share
memory:sync
memory:workspace
memory:remote_write
memory:remote_admin

Dangerous capabilities:

memory:share_sensitive
memory:remote_active_write
memory:revoke_peer
memory:sync_secret

These require explicit confirmation in console and CLI.

⸻

22. CLI Contract

22.1 aletheia federation

aletheia federation init \
  --db ./aletheia.db \
  --name default-laptop
aletheia federation status \
  --db ./aletheia.db
aletheia federation export-identity \
  --db ./aletheia.db \
  --output ./default-laptop.identity.json
aletheia federation rotate-key \
  --db ./aletheia.db \
  --reason "Routine federation key rotation."

⸻

22.2 aletheia peers

aletheia peers add \
  --db ./aletheia.db \
  --identity ./default-workstation.identity.json \
  --reason "Trusted second device."
aletheia peers trust peer_001 \
  --db ./aletheia.db \
  --level trusted_device \
  --reason "Owned workstation."
aletheia peers revoke peer_001 \
  --db ./aletheia.db \
  --reason "Device retired."
aletheia peers list \
  --db ./aletheia.db

⸻

22.3 aletheia shares

aletheia shares create \
  --db ./aletheia.db \
  --namespace user/default/projects/aletheia \
  --name aletheia-project-share \
  --recipient peer_001 \
  --permissions read_claims,read_evidence,write_candidate,write_feedback \
  --privacy-ceiling personal \
  --reason "Share Aletheia project memory with workstation."
aletheia shares export \
  --db ./aletheia.db \
  --share share_001 \
  --output ./aletheia-project-share.aletsync \
  --encrypt
aletheia shares import \
  --db ./target.db \
  --input ./aletheia-project-share.aletsync \
  --trust-policy trusted_device
aletheia shares revoke share_001 \
  --db ./aletheia.db \
  --reason "No longer sharing this project."

⸻

22.4 aletheia sync

aletheia sync run \
  --db ./aletheia.db \
  --collection sync_001
aletheia sync export \
  --db ./aletheia.db \
  --collection sync_001 \
  --output ./sync-out.aletsync
aletheia sync import \
  --db ./aletheia.db \
  --input ./sync-in.aletsync
aletheia sync conflicts \
  --db ./aletheia.db
aletheia sync resolve conflict_001 \
  --db ./aletheia.db \
  --strategy accept_remote_as_candidate \
  --reason "Remote claim is useful but should be reviewed locally."

⸻

22.5 aletheia workspaces

aletheia workspaces create \
  --db ./aletheia.db \
  --namespace org/local-lab \
  --name "Local Lab Workspace"
aletheia workspaces add-member \
  --db ./aletheia.db \
  --workspace ws_001 \
  --member peer_001 \
  --role contributor

⸻

22.6 aletheia grants

aletheia grants list \
  --db ./aletheia.db
aletheia grants show share_001 \
  --db ./aletheia.db

⸻

22.7 aletheia revocations

aletheia revocations list \
  --db ./aletheia.db
aletheia revocations propagate \
  --db ./aletheia.db \
  --peer peer_001

⸻

23. Console Contract

M10 console additions must include:

Federation Overview
Identity
Peers
Share Grants
Sync Collections
Sync Runs
Sync Conflicts
Remote Sources
Trust Domains
Revocations
Workspaces
Agent Groups
Federation Audit

⸻

23.1 Federation overview

Must show:

local instance ID
display name
public key fingerprint
active peers
active shares
last sync time
sync conflicts
revocations pending propagation
federation health

⸻

23.2 Peer page

Must show:

peer display name
instance ID
fingerprint
trust status
trust domain
active shares
recent syncs
revocation status
actions

Actions:

trust
downgrade trust
revoke
export identity
view audit

⸻

23.3 Share page

Must show:

namespace
project
recipients
permissions
privacy ceiling
included memory types
evidence inclusion
expiration
status
last export
last import

High-risk sharing, such as sensitive/secret content, must require explicit confirmation.

⸻

23.4 Sync conflict page

Must show:

local object
remote object
origin peer
conflict type
evidence/provenance
confidence
privacy labels
recommended strategies
actions

Resolution actions must be audited.

⸻

24. Storage Contract

24.1 Schema version

M10 updates schema version to:

1.1.0

⸻

24.2 Required new tables

federation_identities

CREATE TABLE federation_identities (
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

⸻

peer_devices

CREATE TABLE peer_devices (
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

⸻

trust_domains

CREATE TABLE trust_domains (
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

⸻

share_grants

CREATE TABLE share_grants (
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

⸻

share_recipients

CREATE TABLE share_recipients (
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

⸻

sync_collections

CREATE TABLE sync_collections (
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

⸻

sync_changesets

CREATE TABLE sync_changesets (
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

⸻

sync_change_items

CREATE TABLE sync_change_items (
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

⸻

sync_runs

CREATE TABLE sync_runs (
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

⸻

replication_cursors

CREATE TABLE replication_cursors (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    peer_id TEXT NOT NULL,
    last_change_id TEXT,
    last_synced_at TEXT,
    status TEXT NOT NULL,
    metadata_json TEXT
);

⸻

remote_memory_sources

CREATE TABLE remote_memory_sources (
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

⸻

import_trust_policies

CREATE TABLE import_trust_policies (
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

⸻

sync_conflicts

CREATE TABLE sync_conflicts (
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

⸻

sync_conflict_resolutions

CREATE TABLE sync_conflict_resolutions (
    id TEXT PRIMARY KEY,
    sync_conflict_id TEXT NOT NULL,
    strategy TEXT NOT NULL,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

federation_audit_events

CREATE TABLE federation_audit_events (
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

⸻

consent_records

CREATE TABLE consent_records (
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

⸻

revocation_records

CREATE TABLE revocation_records (
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

⸻

sync_tombstones

CREATE TABLE sync_tombstones (
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

⸻

workspaces

CREATE TABLE workspaces (
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

⸻

workspace_members

CREATE TABLE workspace_members (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    member_type TEXT NOT NULL,
    member_id TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    joined_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

agent_groups

CREATE TABLE agent_groups (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    default_capabilities_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

agent_group_members

CREATE TABLE agent_group_members (
    id TEXT PRIMARY KEY,
    agent_group_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    joined_at TEXT NOT NULL,
    metadata_json TEXT
);

⸻

25. Backward Compatibility Contract

M10 must preserve M9 behavior.

The following modes must still work:

library mode
CLI mode
daemon mode
MCP mode
console mode
protected mode
backup/restore mode
plugin mode
conformance mode

The following must remain valid:

M0–M9 Python APIs
M0–M9 CLI commands
HTTP API v1
MCP tools
plugin contracts
backup/archive format
context-pack schema
public contracts
conformance suites

Allowed M10 changes:

- Add federation APIs.
- Add sync protocol.
- Add share bundle format.
- Add peer/trust/share tables.
- Add federation console pages.
- Add federation conformance suites.

Not allowed:

- Breaking v1 public contracts.
- Sharing memory without explicit grants.
- Requiring cloud services.
- Enabling sync by default.
- Treating remote memory as trusted by default.
- Importing remote core memories as local core by default.
- Allowing remote peers to bypass candidate-first write policy.
- Leaking secret memory through sync bundles.

⸻

26. Migration Contract

26.1 Migration path

M10 must support:

1.0.x → 1.1.0

⸻

26.2 Migration rules

- Existing evidence remains unchanged.
- Existing claims remain unchanged.
- Existing candidates remain unchanged.
- Existing inferences/reflections remain unchanged.
- Existing plugins remain unchanged.
- Existing public contracts remain valid.
- New federation tables are added.
- Federation identity is not created automatically unless explicitly requested.
- No peers are added automatically.
- No share grants are created automatically.
- No sync occurs automatically.
- Migration must be idempotent.

⸻

26.3 Recommended migration command

aletheia migrate plan \
  --db ./aletheia.db

Then:

aletheia backup create \
  --db ./aletheia.db \
  --output ./backups/pre-m10.alet \
  --encrypt

Then:

aletheia migrate apply \
  --db ./aletheia.db \
  --to 1.1.0 \
  --verify-after

Then:

aletheia federation init \
  --db ./aletheia.db \
  --name default-laptop

⸻

27. Test Contract

27.1 Federation identity tests

Required tests:

test_create_federation_identity
test_identity_has_public_key_and_fingerprint
test_identity_private_key_not_exported_by_default
test_rotate_federation_key
test_identity_creation_writes_audit

⸻

27.2 Peer tests

Required tests:

test_add_peer_unknown_trust_by_default
test_trust_peer_requires_reason
test_revoke_peer_blocks_future_sync
test_peer_fingerprint_mismatch_rejected
test_peer_revocation_writes_audit

⸻

27.3 Share grant tests

Required tests:

test_create_share_grant
test_share_grant_requires_namespace
test_share_grant_respects_privacy_ceiling
test_share_grant_refuses_secret_by_default
test_revoke_share_blocks_export
test_share_grant_writes_consent_record

⸻

27.4 Share bundle tests

Required tests:

test_export_share_bundle
test_share_bundle_has_manifest
test_share_bundle_encrypted_by_default_for_protected_mode
test_share_bundle_signature_verifies
test_tampered_share_bundle_rejected
test_import_share_bundle_preserves_provenance

⸻

27.5 Sync tests

Required tests:

test_sync_export_changeset
test_sync_import_changeset
test_sync_run_records_counts
test_replication_cursor_updates
test_sync_dry_run_mutates_nothing
test_sync_respects_share_permissions
test_sync_respects_memory_type_filters
test_sync_respects_privacy_ceiling

⸻

27.6 Import trust policy tests

Required tests:

test_unknown_peer_imports_active_claim_as_candidate
test_trusted_device_can_import_active_project_state_when_policy_allows
test_remote_core_memory_not_imported_as_local_core_by_default
test_remote_inference_imported_as_inference_candidate
test_remote_policy_imported_as_policy_proposal_only

⸻

27.7 Sync conflict tests

Required tests:

test_claim_value_conflict_detected
test_delete_update_conflict_detected
test_redaction_update_conflict_detected
test_privacy_label_conflict_detected
test_conflict_resolution_accept_remote_as_candidate
test_conflict_resolution_keep_local
test_conflict_resolution_merge_as_conflict_family

⸻

27.8 Redaction propagation tests

Required tests:

test_remote_redaction_creates_tombstone
test_remote_redaction_updates_imported_evidence
test_remote_redaction_invalidates_derived_reflection
test_remote_redaction_updates_indexes
test_redaction_propagation_writes_audit

⸻

27.9 Revocation tests

Required tests:

test_revoke_share_prevents_future_export
test_revoke_peer_prevents_future_import
test_revocation_notice_exported
test_revocation_warning_mentions_remote_erasure_limits

⸻

27.10 Workspace tests

Required tests:

test_create_workspace
test_add_workspace_member
test_workspace_role_limits_access
test_agent_group_default_capabilities
test_workspace_member_removal_blocks_access

⸻

27.11 Console/API tests

Required tests:

test_console_federation_page_loads
test_console_peer_page_loads
test_console_share_creation_requires_confirmation_for_sensitive
test_console_sync_conflict_resolution_writes_audit
test_http_share_create_requires_capability
test_http_sync_run_requires_capability

⸻

27.12 Migration tests

Required tests:

test_migration_from_m9_to_m10_adds_federation_tables
test_migration_preserves_existing_data
test_migration_does_not_create_identity
test_migration_does_not_create_peers
test_migration_does_not_create_shares
test_migration_does_not_sync
test_migration_is_idempotent

⸻

28. Golden M10 Tests

Golden test 1 — Explicit share only

Given:

Database contains two projects:
- user/default/projects/aletheia
- user/default/projects/private

When:

Share grant is created only for user/default/projects/aletheia.

Expected:

- Export contains Aletheia project memory only.
- Private project memory is absent.
- Manifest lists only the shared namespace.
- Integrity check passes.

⸻

Golden test 2 — Remote active claim becomes candidate by default

Given:

Peer sends active claim:
project Aletheia current milestone is M10.

When imported from unknown peer:

Expected:

- Local candidate memory is created.
- No active claim is created.
- Remote provenance is recorded.
- Review task is created.

⸻

Golden test 3 — Trusted device imports active project state

Given:

Peer is trusted_device.
Import policy allows active project state.

When peer sends:

project Aletheia current milestone is M10.

Expected:

- Local active project claim may be created.
- Remote source is recorded.
- Confidence reflects remote trust policy.
- Audit event records policy reason.

⸻

Golden test 4 — Sync conflict does not overwrite

Given:

Local claim:
M10 is Federated Memory.
Remote claim:
M10 is Cloud Sync.

Expected:

- Sync conflict is created.
- Neither claim silently overwrites the other.
- Context pack does not present both as equally true.
- Review task asks for resolution.

⸻

Golden test 5 — Redaction propagates

Given:

Evidence evt_001 was shared to peer.
Origin later redacts evt_001.

When sync runs:

Expected:

- Peer receives redaction notice.
- Imported evidence is redacted/tombstoned.
- Derived reflections are invalidated.
- Search indexes are updated.
- Audit records are written.

⸻

Golden test 6 — Secret memory is not synced by default

Given:

Secret evidence exists in shared namespace.
Share privacy ceiling is personal.

Expected:

- Secret evidence is excluded.
- Bundle does not contain secret content.
- Manifest does not reveal secret title/snippet.
- Warning is generic and non-leaking.

⸻

29. Acceptance Criteria

M10 is complete only when all of the following are true.

29.1 Federation identity acceptance

[ ] Federation identity can be created.
[ ] Identity has stable instance ID and public key fingerprint.
[ ] Private key is protected.
[ ] Identity can be exported safely.
[ ] Federation key rotation works.

⸻

29.2 Peer acceptance

[ ] Peers can be added.
[ ] Peers default to unknown trust.
[ ] Peers can be trusted explicitly.
[ ] Peers can be revoked.
[ ] Peer trust affects import behavior.

⸻

29.3 Share acceptance

[ ] Share grants can be created.
[ ] Share grants are namespace-scoped.
[ ] Share grants enforce privacy ceiling.
[ ] Share grants enforce memory type filters.
[ ] Share grants support expiration and revocation.
[ ] Secret sharing is blocked by default.

⸻

29.4 Sync acceptance

[ ] Share bundles can be exported.
[ ] Share bundles can be imported.
[ ] Encrypted share bundles work.
[ ] Sync changesets preserve provenance.
[ ] Sync runs are auditable.
[ ] Replication cursors work.
[ ] Sync dry-run works.

⸻

29.5 Trust and import acceptance

[ ] Unknown peer active claims become candidates by default.
[ ] Trusted device import policies work.
[ ] Remote core memories do not become local core by default.
[ ] Remote inferences remain inference candidates.
[ ] Remote policies become proposals only.

⸻

29.6 Conflict acceptance

[ ] Sync conflicts are detected.
[ ] Conflicts do not overwrite local memory silently.
[ ] Conflicts create review tasks.
[ ] Conflicts can be resolved with approved strategies.
[ ] Resolution writes audit records.

⸻

29.7 Redaction and revocation acceptance

[ ] Redaction notices propagate.
[ ] Imported redacted evidence is redacted/tombstoned.
[ ] Derived records are invalidated.
[ ] Share revocation blocks future sync.
[ ] Peer revocation blocks future sync.
[ ] Revocation reports explain remote erasure limits.

⸻

29.8 Workspace and agent governance acceptance

[ ] Workspaces can be created.
[ ] Workspace members can be added and removed.
[ ] Workspace roles constrain access.
[ ] Agent groups can be created.
[ ] Agent group capabilities are enforced.

⸻

29.9 Console/API/CLI acceptance

[ ] Federation console pages work.
[ ] Peer/share/sync CLI works.
[ ] HTTP federation endpoints work.
[ ] SDK federation methods work.
[ ] Capability checks are enforced.

⸻

29.10 Migration acceptance

[ ] M9 database migrates to M10.
[ ] Migration is idempotent.
[ ] Existing memory remains valid.
[ ] No identity, peer, share, or sync is created automatically.

⸻

30. M10 Demo Script

This should be the official M10 demo.

⸻

Step 1 — Migrate

aletheia migrate plan \
  --db ./aletheia-a.db
aletheia backup create \
  --db ./aletheia-a.db \
  --output ./backups/pre-m10.alet \
  --encrypt
aletheia migrate apply \
  --db ./aletheia-a.db \
  --to 1.1.0 \
  --verify-after

Expected:

Schema migrated to 1.1.0.
Federation tables created.
No identity or peers created automatically.

⸻

Step 2 — Initialize federation identity on machine A

aletheia federation init \
  --db ./aletheia-a.db \
  --name default-laptop
aletheia federation export-identity \
  --db ./aletheia-a.db \
  --output ./default-laptop.identity.json

⸻

Step 3 — Initialize federation identity on machine B

aletheia federation init \
  --db ./aletheia-b.db \
  --name default-workstation
aletheia federation export-identity \
  --db ./aletheia-b.db \
  --output ./default-workstation.identity.json

⸻

Step 4 — Add peers

On machine A:

aletheia peers add \
  --db ./aletheia-a.db \
  --identity ./default-workstation.identity.json \
  --reason "Add trusted workstation."
aletheia peers trust peer_001 \
  --db ./aletheia-a.db \
  --level trusted_device \
  --reason "Owned workstation."

On machine B:

aletheia peers add \
  --db ./aletheia-b.db \
  --identity ./default-laptop.identity.json \
  --reason "Add trusted laptop."
aletheia peers trust peer_001 \
  --db ./aletheia-b.db \
  --level trusted_device \
  --reason "Owned laptop."

⸻

Step 5 — Create share grant

On machine A:

aletheia shares create \
  --db ./aletheia-a.db \
  --namespace user/default/projects/aletheia \
  --name aletheia-project-share \
  --recipient peer_001 \
  --permissions read_claims,read_evidence,write_candidate,write_feedback,sync_pull,sync_push \
  --privacy-ceiling personal \
  --reason "Share Aletheia project memory across trusted devices."

Expected:

Share grant created.
Sync collection created.
Consent record created.

⸻

Step 6 — Export share bundle

aletheia shares export \
  --db ./aletheia-a.db \
  --share share_001 \
  --output ./aletheia-project-share.aletsync \
  --encrypt

Expected:

Encrypted share bundle created.
Manifest and signature verified.
Secret memories excluded by default.

⸻

Step 7 — Import share bundle on machine B

aletheia shares import \
  --db ./aletheia-b.db \
  --input ./aletheia-project-share.aletsync \
  --trust-policy trusted_device

Expected:

Share imported.
Remote provenance preserved.
Imported claims handled according to trust policy.

⸻

Step 8 — Create remote candidate from machine B

aletheia remember \
  --db ./aletheia-b.db \
  --namespace user/default/projects/aletheia \
  --type project \
  --subject project:aletheia \
  --predicate current_milestone \
  --object "M10 Federated Memory"

Export sync from B:

aletheia sync export \
  --db ./aletheia-b.db \
  --collection sync_001 \
  --output ./sync-b-to-a.aletsync

Import on A:

aletheia sync import \
  --db ./aletheia-a.db \
  --input ./sync-b-to-a.aletsync

Expected:

Remote change imported.
If remote write is candidate-only, candidate created on A.
Review task created.

⸻

Step 9 — Create sync conflict

On A:

aletheia remember \
  --db ./aletheia-a.db \
  --namespace user/default/projects/aletheia \
  --type project \
  --subject project:aletheia \
  --predicate current_milestone \
  --object "M10 Federated Memory"

On B:

aletheia remember \
  --db ./aletheia-b.db \
  --namespace user/default/projects/aletheia \
  --type project \
  --subject project:aletheia \
  --predicate current_milestone \
  --object "M10 Cloud Sync"

After sync:

aletheia sync conflicts \
  --db ./aletheia-a.db

Expected:

Conflict detected.
No silent overwrite.
Resolution required.

Resolve:

aletheia sync resolve conflict_001 \
  --db ./aletheia-a.db \
  --strategy keep_local \
  --reason "M10 is local-first federated memory, not cloud sync."

⸻

Step 10 — Propagate redaction

On A:

aletheia redact evidence evt_001 \
  --db ./aletheia-a.db \
  --reason "Sensitive content accidentally shared."

Export sync:

aletheia sync export \
  --db ./aletheia-a.db \
  --collection sync_001 \
  --output ./redaction-sync.aletsync

Import on B:

aletheia sync import \
  --db ./aletheia-b.db \
  --input ./redaction-sync.aletsync

Expected:

Redaction notice applied.
Imported evidence redacted/tombstoned.
Derived records invalidated.
Indexes updated.

⸻

31. M10 Implementation Checklist

Federation identity

[ ] Add FederationIdentity model
[ ] Implement federation init
[ ] Implement identity export
[ ] Implement key fingerprint
[ ] Implement key rotation
[ ] Add identity audit events

⸻

Peers and trust

[ ] Add PeerDevice model
[ ] Add TrustDomain model
[ ] Implement add_peer()
[ ] Implement trust_peer()
[ ] Implement revoke_peer()
[ ] Add peer CLI
[ ] Add trust-domain defaults

⸻

Share grants

[ ] Add ShareGrant model
[ ] Add ShareRecipient model
[ ] Implement create_share_grant()
[ ] Implement revoke_share_grant()
[ ] Enforce privacy ceiling
[ ] Enforce memory type filters
[ ] Block secret sharing by default
[ ] Add consent records

⸻

Sync protocol

[ ] Add SyncCollection model
[ ] Add SyncChangeSet model
[ ] Add SyncChangeItem model
[ ] Add ReplicationCursor model
[ ] Implement changeset generation
[ ] Implement changeset import
[ ] Implement .aletsync format
[ ] Implement signing
[ ] Implement encryption
[ ] Implement sync dry-run

⸻

Import and trust

[ ] Add RemoteMemorySource model
[ ] Add ImportTrustPolicy model
[ ] Implement candidate-only import
[ ] Implement trusted-device import
[ ] Prevent remote core auto-import as core
[ ] Track origin object IDs
[ ] Track sync run provenance

⸻

Conflict handling

[ ] Add SyncConflict model
[ ] Add SyncConflictResolution model
[ ] Detect claim conflicts
[ ] Detect delete/update conflicts
[ ] Detect privacy conflicts
[ ] Add conflict review tasks
[ ] Implement resolution strategies

⸻

Redaction and revocation

[ ] Add RevocationRecord model
[ ] Add SyncTombstone model
[ ] Propagate redactions
[ ] Apply remote tombstones
[ ] Invalidate derived records
[ ] Update indexes
[ ] Warn about remote erasure limits

⸻

Workspaces and agent groups

[ ] Add Workspace model
[ ] Add WorkspaceMember model
[ ] Add AgentGroup model
[ ] Add agent group capabilities
[ ] Enforce workspace roles

⸻

API/CLI/Console

[ ] Add federation HTTP endpoints
[ ] Add peer endpoints
[ ] Add share endpoints
[ ] Add sync endpoints
[ ] Add workspace endpoints
[ ] Add federation CLI
[ ] Add peers CLI
[ ] Add shares CLI
[ ] Add sync CLI
[ ] Add federation console pages

⸻

Conformance and tests

[ ] Add federation conformance suite
[ ] Add share bundle conformance
[ ] Add sync protocol conformance
[ ] Add migration tests
[ ] Add golden M10 tests

⸻

32. M10 Definition of Done

M10 is done when this statement is true:

Aletheia can share selected memory across trusted local instances and agents through explicit, encrypted, auditable, provenance-preserving sync without treating remote memory as automatically true or allowing remote peers to bypass governance.

More practically, M10 is complete when Aletheia can do all of this:

- Create a local federation identity.
- Add and trust peers.
- Create scoped share grants.
- Export encrypted share bundles.
- Import share bundles.
- Run sync.
- Preserve origin provenance.
- Apply import trust policies.
- Default remote writes to candidates.
- Detect sync conflicts.
- Resolve sync conflicts without data loss.
- Propagate redactions and tombstones.
- Revoke peers and shares.
- Warn honestly about remote erasure limits.
- Govern shared workspaces and agent groups.
- Expose federation through CLI, HTTP, SDK, and console.
- Preserve every M0–M9 behavior.

M10 is where Aletheia learns to share without surrendering itself.
It federates memory, but keeps truth local, governed, and accountable.