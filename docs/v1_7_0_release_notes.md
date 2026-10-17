# Aletheia Memory 1.7.0 — governed memory production release

Release date: October 17, 2026 (America/Chicago). Version 1.7.0 is the first
production/stable release within the support boundaries below. Python 3.11+,
API v1 and storage 1.3.1 remain unchanged. This minor version adds capabilities
and intentionally stricter validation without changing the stable API version.

## Highlights

- Fix zero-strength feedback and prevent evidence-free assistant repetition from
  increasing confidence. Reject invalid context budgets and incomplete conflict
  scope resolutions; commit complete resolutions atomically.
- Validate all eight advisory LLM tasks. Extraction selects source-bound scope
  references, preserves negation/attribution, refuses invented calendar boundaries
  and detected qualifier loss, and records at most two independently validated
  repair attempts. Human-approved date boundaries survive promotion. Named-project
  inclusions/exclusions use actual namespace-local project context.
- Create Windows database/archive files and internal scratch directories with
  native protected DACLs. Inspect existing directories and destination permissions
  before reserve, restore or SQLite copies write bytes; refuse broad grants.
- Remove reverse DNS from plain HTTP and TLS listener startup. Add repeatable
  HTTP-readiness regression targets to the nine-platform CI matrix.
- Add standard MCP JSON-RPC stdio and correct custom-namespace authorization.
  Clear console data after logout/auth loss, discard late responses, surface
  action errors and include selected namespaces in federation requests.
- Preserve refused legacy databases, reject dangling database paths, move HTTP
  compaction outside a transaction and preserve disk-full errors through rollback.
  Add executable conformance probes and a reusable live qualification harness.

## Upgrade guidance

Back up existing databases using the documented authenticated backup workflow and
verify recovery before upgrading an important deployment. API v1 and storage
version 1.3.1 remain unchanged. No model download or hosted credential is required;
configure the intended providers explicitly. Defaults are not a quality guarantee.

Windows deployments need a private database parent with trusted ancestors;
existing shared directories are refused rather than silently re-permissioned.
Choose a new private location or have the owner deliberately provision suitable
permissions. Local pairing remains POSIX-only. Extraction wire metadata advances
to `candidate_claim_draft.v2` with source-bound `scope_ref`; integrations inspecting
raw provider schemas must account for this. Public candidates still expose the
resolved suggested scope. Budget, advisory and scope validation is intentionally
stricter; callers must handle validation errors instead of relying on coercion.
Feedback with strength zero is inert, and repeated assistant confirmations without
independent evidence no longer raise confidence.

## Qualification and limits

Implementation `6256f35` passed 1,104 local tests, all fourteen milestone scorecards,
all nine native OS/Python combinations, fresh artifacts and installed recovery,
interface/TypeScript/official MCP checks and bounded disk/memory recovery. Real
Llama3.1:8b/Nomic checks passed eight advisory tasks and twelve extraction probes,
with manual review of every triple and scope. Ninety startup samples passed;
maxima were 1.297s new and 0.562s current. A 1,800-second measured soak passed
2,540 lifecycle cycles, integrity, cleanup and source stability.

Production support is within the documented boundaries, not a
claim of exhaustive correctness. Every model proposal remains untrusted pending
human review; English calendar/named-project anchoring is a bounded grammar.
Windows ACL isolation covers other standard principals with trusted ancestors,
not administrator/SYSTEM or offline disk access. Startup targets cover the stated
small-database baseline, five samples/profile, without provider loading, workers,
advertisement or pairing; they are not a population latency SLA. An initial
Windows 3.12 health-concurrency timeout passed unchanged on repeat; its cause is
unproven. The soak accumulated monotonic execution across host suspensions and
does not establish uninterrupted availability.

See [qualification and step-by-step journal](production_qualification.md),
[repeatable harness](beta_pressure_evaluation.md), and
[security boundaries](security_privacy_guide.md). See the [1.7.0 release qualification](v1_7_0_release_verification.md) and
[upgrade guide](v1_7_0_upgrade.md). Publication receipts and distribution hashes
are attached to the GitHub release.

## Concurrency gate interpretation

The 750ms Windows 3.12 health-concurrency timeout recurred on the prepublication
main gate. No release was tagged from that failed run. Its log did not separate
request preparation from response work, so the original timing cause remains
unproven. The regression now bounds authenticated request preparation separately,
then retains the original 750ms response deadlines and requires both operations
to finish before the deliberately paused provider is released. Delayed-authentication
cases exercise this distinction. This is provider-isolation evidence, not a
750ms end-to-end health SLA; startup acceptance budgets are unchanged.
