# Aletheia Memory 1.8.0 — predicate semantics and conflict governance

Release date: October 18, 2026 (America/Chicago). Python 3.11+, API v1 and
storage marker 1.3.1 remain supported. This release adds public APIs and stricter
conflict validation. Existing databases need an additive schema migration.

## Highlights

- Declare namespace-scoped predicate cardinality: `multiple` uses set membership;
  `single` uses exclusive values and remains the default for undeclared predicates.
  Declarations govern conflict detection, candidate screening, inference promotion
  and receiving-side federation reconciliation.
- Configure declarations through Python `Memory.set_predicate_semantics`, HTTP
  `GET/POST /v1/predicate-semantics`, `aletheia predicates get/set` and sync/async
  SDKs. Remote writes require admin access; namespace authorization applies.
- Close project/privacy authorization bypasses before conflict mutation, keep
  subsequent single-valued assertions disputed, and preserve approved unchanged
  contextual and temporal scopes on rescans.
- Reject malformed, overlapping or incomplete conflict outcomes atomically;
  support explicit multivalue `coexist` reconciliation and consistent comparisons.
- Complete OpenAPI URI parameter declarations and typed conflict contracts;
  validate the entire document and ship matching TypeScript starter declarations.

## Upgrade guidance

See the [upgrade guide](v1_8_0_upgrade.md). Back up before opening existing data
with automatic migration. Services using `auto_migrate=False` must explicitly
apply migration before startup. Roll back by restoring the matching older backup
with its older binary; an unchanged storage marker does not imply downgrade safety.
Declaring a predicate does not automatically resolve historical disputes.

## Qualification and limits

The predicate implementation and seven review fixes were merged in PR #72 after
all 16 CI checks passed, including nine native OS/Python combinations, installed
wheel/source recovery and TypeScript contracts. Release-specific evidence is in
the [verification record](v1_8_0_release_verification.md); publication receipts
and file hashes are attached to the GitHub release after publication.

The [1.7.0 production support boundaries](v1_7_0_release_notes.md#qualification-and-limits)
continue to apply. This release does not repeat or expand those measured live-model
or soak claims. Predicate declarations express application policy; they do not
infer cardinality from arbitrary language or automatically repair old disputes.
