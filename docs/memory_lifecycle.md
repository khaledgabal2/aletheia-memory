# Memory Lifecycle

This guide follows a memory from observation to governed recall and long-term
maintenance.

## 1. Initialize Storage

Create or migrate a SQLite database:

```bash
aletheia init --db ./aletheia.db
```

This applies the schema, backfills compatibility records, and prepares the
local store for evidence, claims, service state, and platform records.

## 2. Capture Evidence

Evidence is the first durable record. You can write it directly through
`remember`, or ingest raw content first.

Direct explicit memory:

```bash
aletheia remember \
  --db ./aletheia.db \
  --namespace user/default \
  --type preference \
  --subject user \
  --predicate prefers_response_style \
  --object "practical and direct"
```

Raw evidence ingestion:

```bash
aletheia ingest text \
  --db ./aletheia.db \
  --namespace user/default \
  --title "Project note" \
  "For architecture docs, prefer concrete implementation detail."
```

Ingestion records source documents, evidence spans, risk flags, and batch state.
Risk scanning can flag prompt-injection and memory-poisoning patterns.

## 3. Extract Candidates

Extraction turns evidence into candidate claims:

```bash
aletheia extract run \
  --db ./aletheia.db \
  --namespace user/default \
  --batch ing_...
```

Candidate extraction can be rule-based, mock, plugin-backed, or governed
LLM-backed. Candidates remain pending until reviewed.

List candidates:

```bash
aletheia candidates list \
  --db ./aletheia.db \
  --namespace user/default
```

## 4. Review And Promote

Promote only candidates that are supported by evidence:

```bash
aletheia candidates promote cand_... \
  --db ./aletheia.db \
  --reason "Reviewed against source evidence."
```

Reject unsupported candidates:

```bash
aletheia candidates reject cand_... \
  --db ./aletheia.db \
  --reason "Not directly supported by the source."
```

Promotion writes a claim, links evidence, records review decisions, copies
approved metadata, and writes audit events.

## 5. Retrieve Memory

Search claims directly when you need focused results:

```bash
aletheia search \
  --db ./aletheia.db \
  --namespace user/default \
  --mode lexical \
  "response style"
```

Use semantic or hybrid mode only after creating a semantic index:

```bash
aletheia index semantic \
  --db ./aletheia.db \
  --namespace user/default \
  --provider local_hash \
  --dimension 64

aletheia search \
  --db ./aletheia.db \
  --namespace user/default \
  --mode hybrid \
  --semantic-provider local_hash \
  "How detailed should docs be?"
```

Retrieval filters by namespace, status, type, subject, predicate, project,
session, category, confidence, conflict state, and scope.

## 6. Build Context Packs

Context packs are the preferred input for agents:

```bash
aletheia context-pack \
  --db ./aletheia.db \
  --namespace user/default \
  --project aletheia \
  --token-budget 1200 \
  "Write the next documentation section"
```

Context packs group memory by purpose and include warnings for disputed,
candidate, stale, or omitted material.

## 7. Record Usage And Feedback

Feedback changes confidence and future recall:

```bash
aletheia feedback clm_... \
  --db ./aletheia.db \
  --namespace user/default \
  --signal confirmed \
  --note "User explicitly confirmed this memory."
```

Task outcomes and retrieval judgments support evaluation and optimization:

```bash
aletheia outcome record \
  --db ./aletheia.db \
  --namespace user/default \
  --task task_001 \
  --outcome completed
```

## 8. Detect And Resolve Conflicts

Find conflicts:

```bash
aletheia conflicts detect \
  --db ./aletheia.db \
  --namespace user/default
```

Resolve them by choosing, superseding, rejecting, or scoping claims:

```bash
aletheia conflicts resolve conf_... \
  --db ./aletheia.db \
  --active clm_... \
  --note "The newer evidence is more specific."
```

Use claim scoping when statements apply in different contexts:

```bash
aletheia claims scope clm_... \
  --db ./aletheia.db \
  --type contextual \
  --applies-when architecture_or_design_request \
  --reason "Only applies to architecture and design work."
```

## 9. Curate And Recompute Confidence

Preview confidence decay:

```bash
aletheia decay preview \
  --db ./aletheia.db \
  --namespace user/default
```

Persist confidence recomputation:

```bash
aletheia confidence recompute \
  --db ./aletheia.db \
  --namespace user/default
```

Preview deterministic curation decisions:

```bash
aletheia curate preview \
  --db ./aletheia.db \
  --namespace user/default
```

## 10. Use Reasoned Memory

Run governed inference:

```bash
aletheia infer run \
  --db ./aletheia.db \
  --namespace user/default \
  --engines logical,semantic,factual \
  --apply
```

Build a source-backed reflection:

```bash
aletheia reflect build \
  --db ./aletheia.db \
  --namespace user/default \
  --title "Response style" \
  --claims clm_...,clm_... \
  --text "The user prefers practical answers, with more detail for architecture." \
  --reason "Combines reviewed response-style memories."
```

Trace derivation:

```bash
aletheia derivation trace ref_... \
  --db ./aletheia.db \
  --type reflection
```

## 11. Operate As A Service

Create a client and token:

```bash
aletheia clients create \
  --db ./aletheia.db \
  --name local-agent \
  --type agent

aletheia auth create-token \
  --db ./aletheia.db \
  --client local-agent \
  --namespace user/default \
  --capabilities memory:read,memory:context,memory:write_candidate,memory:feedback,memory:audit
```

Start the local service:

```bash
aletheia serve \
  --db ./aletheia.db \
  --host 127.0.0.1 \
  --port 8765
```

Normal service and MCP writes should remain candidate-first unless the caller is
trusted and explicitly authorized for active writes.

## 12. Harden And Maintain

Enable protected mode when sensitive evidence will be stored:

```bash
aletheia init --db ./aletheia.db --protected
```

Create and verify encrypted backups:

```bash
aletheia backup create \
  --db ./aletheia.db \
  --output ./aletheia.alet \
  --encrypt \
  --passphrase "change-me"

aletheia backup verify ./aletheia.alet \
  --db ./aletheia.db \
  --passphrase "change-me"
```

Run integrity and readiness checks:

```bash
aletheia integrity check --db ./aletheia.db --namespace user/default --deep
aletheia readiness check --db ./aletheia.db --namespace user/default
```

## 13. Export, Import, And Federate

Use export/import for local archives and support workflows:

```bash
aletheia export namespace --db ./aletheia.db --namespace user/default --output ./archive.alet
aletheia import apply ./archive.alet --db ./restored.db --namespace user/default
```

Use federation only when explicit identities, trust, grants, and encrypted
`.aletsync` bundles are appropriate. Federation is local-first and
grant-scoped; it is not automatic cloud sync.

## Lifecycle Rule

The central rule is:

```text
evidence -> candidate -> reviewed claim -> governed retrieval -> feedback -> maintenance
```

Every shortcut should preserve provenance, capability boundaries, auditability,
and review state.
