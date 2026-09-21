# Policy execution, sync decisions, and certification

Policy versions now control reads, sync decisions change governed objects, and
certification distinguishes structural inventory from observed behavior.

## Ranking and context policies

Retrieval loads one immutable ranking version before selecting candidates. All
three modes use its weights for lexical/semantic relevance, confidence,
importance, type/status priority, project relevance, recency, and conflict,
duplicate, and staleness penalties. A feature unavailable in a mode contributes
zero (for example, semantic similarity in lexical mode). Project membership and
all penalty features participate before bounding candidates. Retrieval remains
bounded top-N selection, not exhaustive enumeration.

Omitting a version selects the active `rpol_default` or `cpol_default` version.
Python retrieval, HTTP retrieval, and context accept `policy_version_id`;
context additionally accepts `context_policy_version_id`. A version owned by
another namespace is rejected. Context subqueries and evaluation cases pin the
selected versions, and their records identify the versions actually used.

Context budget, reflection/inference inclusion, and derivation metadata default
to the selected context configuration. Explicit request options override those
defaults. The initial policy still uses 1,500 tokens, includes reflections, and
excludes inferences and derivation metadata. CLI `context` and `context-pack`
also inherit policy defaults when flags are omitted. Context traces through
Python, HTTP, and CLI inherit the same budget and record the effective budget;
an explicit trace budget still overrides the policy.

Applying a proposal merges supported partial configuration into its current
version. Unknown fields, invalid weights/budgets, and attempts to disable
default status/validity safeguards fail validation. Evaluation thresholds may
tighten the built-in governance limits. With evaluation required, application
reruns the referenced evaluation set using the proposed version; an earlier
baseline pass alone is insufficient. Activation, evaluation, history, and audit
records commit together or roll back. Ranking and context rollback restore the
selected version's behavior. Other policy types are not executable through this
application path and return an error.

HTTP application of a global default requires a literal `*` namespace grant
and `memory:policy`. Review existing active configurations during upgrade:
supported configurations now affect results; invalid legacy configurations
produce validation errors instead of silently falling back to hardcoded scores.

## Sync conflict decisions

Resolution reads the current local claim, imported remote object, mapping, and
all supporting evidence inside one write transaction. Missing, changed,
already reviewed, cross-namespace, or deleted sources are rejected. It does not
recreate deleted data from an old bundle snapshot.

The console's ordinary conflict-family resolution uses the same current-source
authorization as the ordinary HTTP route. Embedded resolution also rejects
nonmember targets before any mutation. Redaction scrubs federation conflict
snapshots as well as their source objects. HTTP conflict listings reveal
snapshots only when both current sources remain accessible and match them;
otherwise they return structural conflict state with empty metadata.

| Strategy | Verified effect |
| --- | --- |
| `keep_local`, `reject_remote` | Keep the local choice active and reject the remote candidate or imported claim. |
| `accept_remote_as_candidate` | Keep the local choice active and retain a reviewable remote candidate; an already active remote claim is archived and copied into the candidate path with its evidence. |
| `accept_remote_active` | Use normal governed promotion if needed, resolve the two-claim conflict family, supersede the local claim, and retain remote evidence and the supersession relationship. |
| `defer` | Leave memory objects unchanged, mark the decision deferred, and leave `resolved_at` empty. A later decision remains possible. |

Successful receipts include the resulting local/remote identities and statuses.
Source mappings follow a promoted or demoted remote object, so another import
does not undo the decision. Review tasks and receipts update only after the
effects are verified. Failures roll back all effects. Repeating a terminal
resolution is rejected.

`merge_as_conflict_family`, `scope_both`, `time_scope`, and `manual_merge` are
unsupported without explicit merge/scope inputs and return validation errors.
Families containing additional claims require separate family review.

HTTP resolution requires `memory:sync`, `memory:review`, and access to both
objects' current provenance. Changing active claims also requires
`memory:write_active`; accepting remote active memory additionally requires
`memory:remote_active_write`.

## Evidence and certification

Adapter certification checks the manifest, regular files, and Python
compilation. Invalid Python fails. Custom Python with valid syntax receives
structural evidence only and is `not_certified`; it is never imported or run.

The executable `bundled-sdk-loop-v1` contract is limited to the bundled loop's
AST (module documentation and formatting may differ). Its probes use disposable
synthetic memory, the real Python SDK methods, and an in-process HTTP service.
They verify returned context, privacy exclusions, one candidate with evidence,
zero active writes, denied writes without mutation, namespace denial, and SDK
error propagation. Only passing behavioral evidence can issue `certified`.
Certificates record the source hash, contract, adapter type, and probe results.
The `generic-http` and `mcp-client` scaffold labels currently use this same SDK
loop; its certificate does not certify their network or MCP transport.

Legacy certificates without behavioral evidence appear as `not_certified` and
require recertification. The standalone federation conformance command also
labels its table/contract inventory `structural_passed`.

Other conformance suites currently provide structural inventory and/or report
missing probes. They return `structural_passed` or `incomplete`, not a behavioral
pass. Empty suites and unknown/skipped cases cannot pass. Caller metadata cannot
promote structural evidence into a behavioral result. The in-database v1 gate
requires current behavioral results; old passes and target-specific adapter
checks cannot satisfy built-in suite requirements. Unit/integration attestations
also default to missing, rather than passed. This gate therefore remains failed
until its missing behavioral suites and other required checks are implemented
and verified. The separate `scripts/release_gate.py` checks generic repository
packaging boundaries and does not certify runtime behavior.

Normal regression coverage is in `tests/test_policy_execution.py`,
`tests/test_sync_resolution_effects.py`, and `tests/test_certification_evidence.py`.
