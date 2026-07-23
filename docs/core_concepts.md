# Core Concepts

This guide explains the vocabulary Aletheia uses across the Python kernel,
CLI, HTTP service, MCP tools, plugins, and operational console.

## Local-First Memory

Aletheia stores durable state in a SQLite database that you choose with
`--db`. The default service is local. Binding the HTTP service beyond loopback
requires explicit authentication and external transport protection.

The database contains memory content, provenance, confidence records, conflicts,
review decisions, logs, service auth records, operational reports, backups,
federation metadata, and platform state.

## Namespace

A namespace is the primary isolation boundary for memory, for example
`user/default` or `team/research`. Most user-facing commands require
`--namespace`.

Namespaces are used for:

- Claim and evidence separation.
- API token grants.
- Privacy ceilings.
- Federation share grants.
- Console and report filtering.

Use one namespace when a user or agent should see one memory corpus. Use
separate namespaces when recall, writes, or permissions should be isolated.

## Evidence

Evidence is the raw observed source material. It is stored in
`evidence_events` with source type, source URI, content hash, trust level,
privacy level, retention policy, and optional session link.

Evidence is not automatically truth. It is the source from which candidates,
claims, reflections, and summaries can be derived.

Common evidence sources:

- Manual memories written through `remember`.
- Text or file ingestion through `ingest`.
- Agent observations written as candidate evidence through HTTP, MCP, or SDKs.
- Imported archives or sync bundles.

## Candidate Memory

A candidate is a proposed memory awaiting review. It lives separately from
trusted claims and usually comes from extraction, plugins, LLM tasks, service
writes, or MCP tools.

Candidate-first writes are the safe default for agents. They let tools record
possible memory without silently changing what future agents will trust.

Review actions include:

- Promote a candidate to a claim.
- Reject a candidate.
- Edit a candidate before promotion.
- Leave it pending for later review.

## Claim

A claim is a structured assertion:

```text
subject -> predicate -> object
```

Every claim has:

- `memory_type`
- `status`
- base and effective confidence
- importance
- half-life policy
- evidence links
- audit records

`write_claim()` rejects evidence-free claims. `remember()` is the convenience
path that writes evidence and then writes a claim backed by that evidence.

## Claim Status

Common claim statuses are:

- `active`: normal trusted memory.
- `core`: high-importance memory intended to appear early in context.
- `disputed`: memory involved in unresolved conflict.
- `superseded`: memory replaced by a newer or better-scoped claim.
- `rejected`: memory that should not be used.
- `archived`: memory retained but normally excluded from recall.

Status affects retrieval, context pack placement, conflict handling, and
curation.

## Memory Type

`memory_type` describes the role of a claim. The implementation accepts string
types rather than a fixed closed enum. Common types include:

- `preference`
- `fact`
- `project`
- `procedure`
- `session`
- `reflection`

Use stable, low-cardinality type names. Filters, half-life policies, retrieval
ranking, and docs examples assume memory types are meaningful.

## Confidence And Salience

Aletheia tracks truth confidence separately from retrieval salience.

Effective confidence is computed from:

- base confidence
- age and half-life decay
- source reliability
- feedback
- contradiction pressure
- verification factors

Salience is about whether a memory should be retrieved for a query. A memory
can be true but not useful for a given query, or useful but low-confidence
enough to require warnings.

## Conflicts

A conflict is not treated as noise. When active claims disagree, Aletheia can
create conflict families and mark claims as disputed.

Resolution options include:

- Select an active claim.
- Supersede older claims.
- Reject unsupported claims.
- Scope claims to different contexts.
- Keep the conflict unresolved with warnings.

Use conflict resolution when memories are genuinely incompatible. Use claim
scoping when multiple statements can be true under different conditions.

## Scope

Scope narrows where a claim applies. A scoped claim can have:

- scope type
- applies-when text
- validity dates
- project ID
- session ID
- agent ID
- reason

Scope is important for personal preferences, project-specific procedures, and
memories that change across time or contexts.

## Context Pack

A context pack is the agent-ready recall product. It groups memory into:

- core memory
- project memory
- session memory
- procedural memory
- reflections
- relevant memory
- warnings
- omitted items

Context packs retain claim IDs, confidence, evidence IDs, policy version IDs,
generation time, and optional usage records. Agents should prefer context packs
over raw search when preparing prompts.

## Retrieval

Aletheia supports lexical, semantic, and hybrid retrieval modes.

Lexical retrieval uses SQLite FTS. Semantic and hybrid retrieval use governed
embedding providers and a local vector store. Retrieval still applies namespace,
status, privacy, conflict, scope, and policy gates before results enter a
context pack.

## Projects And Sessions

Projects and sessions make recall less generic.

Projects represent durable areas of work. Sessions represent bounded agent or
user interactions. Claims can be linked to projects or sessions, and context
packs can prioritize matching memory.

## Reflections, Inferences, And Abstractions

Reasoned memory creates higher-level material while preserving derivation:

- Inferences are reviewable outputs from rules or engines.
- Reflections combine source-backed claims into concise summaries.
- Abstractions preserve links to lower-level records.
- Derivation traces explain where a derived item came from.
- Invalidations propagate when source material changes.

These records do not erase underlying evidence.

## LLM Tasks

LLM support is optional and governed. LLM tasks can propose:

- candidate memories
- query expansions
- entity/category suggestions
- scope suggestions
- duplicate-merge suggestions
- summaries
- reflection drafts
- conflict explanations

LLM output does not become trusted memory automatically. Persistent LLM output
records store metadata and hashes by default.

## Audit

Important mutations write audit records. Use audit when you need to answer:

- Where did this memory come from?
- Which evidence supports it?
- Who promoted, rejected, scoped, or superseded it?
- What confidence or conflict decisions affected it?

CLI entry point:

```bash
aletheia audit clm_... --db ./aletheia.db
```

## Operational State

Aletheia also stores operational state:

- API clients and tokens.
- Service request logs, idempotency records, and rate limits.
- Console sessions and CSRF-protected state changes.
- Review tasks, notifications, metrics, traces, and reports.
- Backups, restores, protected-mode metadata, redactions, tombstones, retention runs, integrity findings, release manifests, and readiness checks.
- Plugin manifests, compatibility records, conformance runs, docs builds, examples, and doctor runs.

This state is local and auditable like memory state.

## Encryption Layer

Aletheia has a local encryption layer for protected memory content and exported
payloads.

Protected mode can encrypt secret-tier evidence content before storage. It also
requires encrypted backups, uses metadata-only request logging, and applies a
secret-safe indexing policy by default.

Backup, namespace export, and support-bundle encryption are separate archive
payload paths. They use passphrases or configured key material and are verified
before restore.

Read `docs/encryption_layer.md` for the full model.
