# Beta pressure findings — October 16, 2026

This is the original diagnosis. Implemented corrections and subsequent evidence
are recorded in `beta_pressure_resolution.md`.

Baseline: `4ad75a8a98b86d1606a4f2cead7f0cdfe63c3826`, source version 1.6.3.
Product implementation was not changed. Evidence is synthetic and retained under
`output/beta-pressure-2026-10-16-*`. This is a qualification report, not a release
approval. Severity reflects the reproduced impact and current interface boundary.

## BETA-001 — Zero-strength feedback is applied as full-strength feedback

**Confirmed, medium; feedback correctness.** Reproduction:
`beta_pressure_cases.py`, case `zero_strength_feedback_is_inert`.

On a fresh active claim, record each signal with `strength=0`. The feedback row
correctly stores zero, but confidence recomputation treats it as one:
`_feedback_factor` and `_usefulness_factor` in `aletheia/core/memory.py` use
`float(row["strength"] or 1.0)`. Confirmed changed feedback factor from 1 to
1.08; verified to 1.14; wrong to 0.15. Wrong and contradicted also move the claim
to disputed through `_apply_feedback_to_claim` despite zero strength.

Expected: reject zero explicitly or make zero inert consistently. Actual:
accepted zero changes confidence, salience, status and potentially verification
time. This can affect later recall. Fix the distinction between missing and zero
and make state transitions respect the same effective strength. Add assertions
for every feedback signal, including verification time and both confidence and
salience. The existing 846-test suite did not catch this.

## BETA-002 — Embedded context budgeting accepts NaN

**Confirmed, medium; trusted embedded API validation.** Reproduction:
`beta_pressure_cases.py`, case `invalid_context_budgets`.

`Memory.context_pack(..., token_budget=float("nan"))` returns a pack containing
memory. The comparisons at the inclusion loops in `aletheia/core/memory.py`
cannot exceed NaN, so budget enforcement is bypassed. The entry point accepts
the argument without validating a finite nonnegative integer.

Expected: a clear validation error before retrieval or persistent usage changes.
Validate the budget once at the kernel boundary. HTTP has stricter numeric
parsing; this receipt does not establish a remote security bypass. Extend the
regression to infinity, booleans, negative values and numeric strings, and verify
side effects are absent on rejection.

## BETA-003 — Scope resolution can close a conflict before any scope exists

**Confirmed workflow deficiency, medium; not a newly introduced regression.**
Reproduction: `beta_pressure_cases.py`,
`context_resolution_without_scopes`.

Create incompatible editor preferences, then call
`resolve_conflict(id, strategy="context_scope", note=...)` without scoped claims.
The conflict becomes resolved and the family context-scoped, while no scopes
were provided. The resolution implementation records resolved state before
iterating the optional empty `scoped_claims` list.

The existing test `test_context_scope_resolution_controls_context_pack`
deliberately follows this with a separate `scope_claim` call. Thus this is an
existing staged workflow, with a non-atomic gap that can remain indefinitely if
the second operation fails or is forgotten. It is not evidence that contradictory
claims automatically become trusted: disputed claim status still applies.

Prefer supplying/validating scopes atomically, or an explicit pending-scoping
state that remains visible in unresolved work until scoping is complete. Cover
CLI and HTTP behavior and failure between the two current actions.

## BETA-004 — Real LLM advisory outputs can be empty or wrong-shaped yet completed

**Confirmed with the documented local model, high functional impact on optional
LLM workflows.** Evidence: extended run `live-workflows/cases.json`.

With the documented Llama 3.1 8B setup, query expansion returned only `query` and
run ID, without `expanded_terms`. Named-entity and category tasks echoed source
metadata and returned empty suggestion lists. Summarization returned no summary.
Reflection generated the literal placeholder “LLM reflection draft requires
review.” rather than a summary of the explicit SQLite source fact.

`expand_query` sends a schema with required keys but no property definitions.
`_llm_source_task` uses only `{"type":"object"}` and a generic draft instruction.
The task type is present in metadata, but task-specific output requirements are
not explained. Valid JSON is stored as a completed invocation without validating
the task result shape. Some methods fill defaults, masking the missing output.
`draft_reflection_with_llm` substitutes a placeholder and stores a candidate.

The governance boundary held: these outputs did not create active claims.
That safety success does not establish functional quality. Use explicit typed
schemas, task-specific prompts and post-response validation. Distinguish provider
completion from a usable validated result. Test all advisory tasks against real
providers as well as malformed deterministic fixtures; do not promote defaults
or placeholders to a successful quality score.

Read-only inspection of stored `output_keys` also confirmed the apparent scope
and merge successes came from API defaults, not model-generated suggestions.
All eight advisory tasks lacked their expected substantive output field in this
sample. See `live-workflows/quality-review.json`; do not replace the original
case receipt with the corrected interpretation.

The six adversarial extraction samples also showed a quality limitation:
four produced no candidates because generated source spans were invalid, one
correctly attributed a third-party statement, and the Chinese source produced
an invalid whitespace candidate. These are not successful extraction-quality
results. Provenance rejection was correct and must remain strict.

## BETA-005 — Advertised MCP stdio does not implement the MCP handshake

**Confirmed interoperability gap, high for standard MCP clients.** The CLI
emits an unsolicited custom `type: ready` object, expects `tool`/`arguments`, and
answers a standard JSON-RPC `initialize` request with `{"ok":false,"error":"'tool'"}`.
`McpToolRegistry.serve_stdio` implements this custom protocol. No initialize,
tools/list or tools/call JSON-RPC handling exists there.

The [MCP lifecycle](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle)
requires client initialization and a matching JSON-RPC server response; the
[stdio transport](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
requires MCP messages on stdout. Some local docs carefully say “MCP-style”; the
README advertises it for an MCP host. Qualify that promise or implement the real
protocol and test it with an actual MCP client. Direct registry tests cannot
certify wire interoperability. Evidence: `interfaces/stdio-jsonrpc.log`.

## BETA-006 — CLI MCP namespace option does not configure tokenless authorization

**Confirmed, medium; normal nondefault-namespace operation fails.** The corrected
custom stdio probe invokes `memory_search` in `read_only` mode with namespace
`pressure/stdio`. The response is “Object is unavailable under the current access
policy.” `_run_mcp` configures `mcp_default_namespace`, but constructs
`Memory.open(config.db_path)` without that namespace. Tokenless authorization in
`AletheiaService` grants `self.memory.namespace`, which remains `user/default`.
The registry checks the requested namespace, then HTTP authorization rejects it.

Expected: selecting an isolated namespace lets the local configured tool read
that namespace, while other namespaces remain denied. Align service memory
namespace and tokenless grants with the explicitly selected MCP namespace; keep
the negative namespace-escape tests. Evidence: `interfaces/stdio-custom.log`;
a separate default-namespace control passed in targeted3 with the same tool and
mode, isolating the namespace setup defect.

## BETA-007 — Console logout retains previously displayed results

**Confirmed, medium; client-side privacy/UX.** In the real browser, log in,
refresh the dashboard and load a retrieval trace, integrity report, contracts and
federation status. Click Log Out. “Logged out” appears, but all those results
remain rendered. The logout handler in `aletheia/service/http.py` clears CSRF
state and session status only; it does not clear protected result panels or
input values. This does not show a server authorization bypass.

Clear result panels and credential inputs on logout and authentication loss,
and test visibility after logout/revocation. Evidence:
`browser1/console-logged-out.png` and `console-logged-out-state.txt`.

## Evaluation infrastructure observations

- The historical milestone scorecards are not all current qualification gates.
  Many expect storage schema 1.3.0, while current storage is 1.3.1. Old migration
  fixtures predate the supported 1.3.0 floor. Newer hardening behavior refuses
  overwriting archives or importing metadata-only content that old scripts
  expected to accept. Preserve these failures; classify/update their fixtures
  without removing the current security invariants.
- Initial M10 and M11 runs lacked explicit synthetic protected/federation key
  setup. Those failures are setup failures, not product crypto failures. The
  reusable runner now provides disposable synthetic keys; reruns are distinct
  receipts and must not erase initial results.
- Development installed metadata reports 1.6.0, whereas the checkout declares
  1.6.3. Fresh wheel verification subsequently passed: clean site-packages import,
  runtime metadata and distribution metadata all report 1.6.3, and README content
  matches in wheel and sdist. The old development environment was not changed.
- M7 does correctly exit nonzero through its reporting function. An initial
  source-reading suspicion to the contrary was withdrawn.
- The 100-event assistant-confirmation probe reached base and truth confidence
  1.0 without new evidence despite per-event strength being capped at 0.05. This
  is a stress observation about cumulative reinforcement, not a claim that
  single-event attenuation is absent. Decide whether the policy should bound
  cumulative support per independent source before production.
- The first browser fixture mixed console setup with a previously captured
  read-only baseline and seeded a duplicate claim. These harness errors were
  corrected; browser2 passed seven read and six governed-review checks. The
  initial fixture failures were not counted as product bugs.
- The first README comparison used email parser text decoding instead of UTF-8
  bytes. Correct decoding verified equality. That initial failure is a harness
  bug, not mismatched package documentation.

## Source locations

| Finding | Relevant implementation |
| --- | --- |
| BETA-001 | `core/memory.py`: `feedback`, `_apply_feedback_to_claim`, `_feedback_factor`, `_usefulness_factor` |
| BETA-002 | `core/memory.py`: `context_pack`, inclusion-loop budget comparisons |
| BETA-003 | `core/memory.py`: `resolve_conflict`, family-status update and optional `scoped_claims` loop |
| BETA-004 | `core/memory.py`: `expand_query`, `_llm_source_task`, `draft_reflection_with_llm`; `llm.py`: `HTTPLLMProvider._payload` |
| BETA-005 | `service/mcp.py`: `McpToolRegistry.serve_stdio` |
| BETA-006 | `cli/main.py`: `_run_mcp`; `service/http.py`: `_authenticate`; `service/mcp.py`: `invoke` |
| BETA-007 | `service/http.py`: console JavaScript logout handler |

Paths above are relative to `aletheia/`. Exact product source hashes are in every
campaign receipt. The focused cases and interface failures were repeated with
retained disposable databases; no product repair was applied during diagnosis.

## Release decision

Retain beta. Resolve and retest the confirmed feedback/context defects and
qualify LLM task output quality before a production claim covering these
features. Installed artifact, browser and TypeScript evidence now passes within
the documented scope; MCP and logout failures remain. Finish behavioral
conformance and the supported platform/load envelope. Passing the generic
repository release gate alone does not answer those questions. See the companion
evaluation journal for completed checks, historical-failure classification and
unverified combinations.
