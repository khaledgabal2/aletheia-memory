# Remaining production qualification

This follow-up addresses the blockers retained by the beta pressure campaign.
Results are pending until recorded below; implementation is not qualification.
No release is authorized by this document.

## Extraction contract

The model selects exact evidence and per-event scope references. The host
independently validates source identity, Unicode boundaries and text equality,
then resolves only a scope anchor belonging to that source. Blank fields, unknown
references, invented calendar boundaries and detected lost qualifiers are refused.
The bounded anchor grammar recognizes explicit English calendar boundaries and
named-project conditions; unsupported semantics remain operator review work.
Month boundaries use the first day. All model output remains untrusted and pending
review. Source instructions cannot approve, verify or promote. Human-approved
temporal boundaries survive promotion; project inclusions/exclusions match actual
project context rather than query words. Privacy gates remain in effect.

Extraction wire v2 uses `scope_ref`. At most two repair proposals may follow a
rejection; each is independently validated, with attempt status/error/output hash
recorded. Set `max_repair_attempts=0` to disable repairs. Bounded repair can make up
to three provider requests and does not establish general semantic entailment.

The six original adversarial examples must yield useful, semantically correct
pending candidates, not merely pass governance refusal. The harness now exits
unsuccessfully when its explicit quality checks fail. Exact-source anchoring is
necessary provenance, not proof that a paraphrase follows from evidence. Held-out
examples and manual review remain necessary to assess generalization.

## Windows isolation contract

The threat model is another standard local security principal. Administrators,
SYSTEM, an account sharing the owner's token, and offline disk access are outside
this ACL boundary; encryption and host administration remain separate controls.
POSIX mode bits are not Windows isolation evidence.

New database and archive files use an explicit protected native DACL at creation.
SQLite sidecars inherit from a private database directory. Existing directory
permissions are inspected, never silently tightened. A directory with grants to
other standard principals is refused before opening the database. Newly created
database directories are explicitly private. Local pairing remains POSIX-only.
Native tests must verify owner access, deny read/write and file creation under a
restricted token, inspect all database/WAL/SHM/export files, and refuse a broad
Everyone grant. These tests require actual Windows execution.

## Startup readiness targets

The supported baseline is a fresh Python process running the CLI daemon with
loopback binding, authentication enabled, no worker, advertisement or local
pairing, no provider calls, and an empty synthetic namespace. Readiness requires
an actual HTTP 200 response from `/v1/ready` with `data.ready=true`; process
creation, a listening socket or a printed startup line does not count.

| Profile | Per-run sampled p95 | Hard maximum per sample |
| --- | ---: | ---: |
| Create empty database and migrate | 45 seconds | 60 seconds |
| Reopen current database | 15 seconds | 30 seconds |

These are startup acceptance budgets for supported local SSD hosts with at least
two CPU cores and 4 GiB available memory. They are not an availability or request
latency SLA. `scripts/beta_startup_latency.py` runs five independent process
starts per profile and retains every timing, exit state and startup log. P95
uses nearest rank; with five samples it equals the observed maximum. This small
sample regression gate does not estimate population p95 with statistical
confidence. CI repeats it on each supported OS/Python combination. OS cache
purging, large-database upgrade, network filesystems, provider loading and
advertisement/pairing startup are outside this profile and require separate
qualification before promising those targets for such deployments.

Failure must remain failure; do not enlarge budgets to fit observations. First
separate process import, schema creation/current-schema checks and endpoint
readiness when investigating an exceeded target.

## Follow-up journal

1. Inspected all six retained quality failures and the exact previous CI/soak
   receipts. Kept the original campaign and its failed/invalidated/deferred runs.
2. Added schema-bound full-event anchors, independent nonblank field validation
   and qualifier/attribution guidance. Models1 passed recipe/advisories/governance
   but failed two semantic checks: omitted date and unrelated Chinese output.
3. Found escaped Unicode in model-visible evidence and unnecessary namespace
   labels. Sent readable Unicode content without namespace metadata. Models2
   retained the effective date and Chinese meaning, but copied a Spanish example
   into the unrelated attribution case. Kept the failure and removed that example.
   The harness now fails on quality failures, separately from governance.
4. Added native Windows protected creation for databases, archives and federation
   recovery files. Database parent and existing sidecar ACLs are inspected before
   SQLite opens; new database directories receive private inheritable ACLs.
   Broad directories fail closed rather than being silently re-permissioned.
5. Added native restricted-token read/write denial tests, broad-parent refusal,
   owner access and database/WAL/SHM/archive checks. Per-test Windows temporary
   directories are explicitly private; real Windows execution is still pending.
6. Defined separate new/current database startup budgets and a reusable CLI-to-
   HTTP-ready harness, with five samples/profile and all samples/logs retained.
   Added it to every native OS/Python CI combination.
7. Initial focused local regression run exposed a test-fixture mistake: Memory
   does not implement a context manager. Corrected the test to close explicitly;
   all failed receipts are retained. Started the production phase with the shared
   resource lock and no active external Ollama client observed.
8. Local1 passed 83 tests (two Windows-only skips); five startup samples/profile
   observed maxima 0.188 seconds new and 0.151 seconds current. This is local
   evidence only. A model admission retry was resource-deferred, not an attempt.
9. Native initial revision `96d8714`: Windows/Python 3.13 passed 1,076 tests
   (17 POSIX skips), both native ACL cases including the restricted-token readable
   positive control, and startup targets (maxima 1.165s new / 0.550s current).
   Linux combinations passed. macOS 3.13 passed 1,091 tests with two Windows skips,
   but current-database startup timed out at the unchanged 30-second hard limit;
   fresh database startup was about 35 seconds. This is a qualification failure.
10. Inspected the inherited HTTPServer.server_bind: it synchronously calls
    socket.getfqdn on the bound host. A deterministic regression reproduced that
    dependency with reverse DNS unavailable. The first reproducer also called a
    nonexistent test cleanup method; corrected it to shutdown. Removed reverse
    DNS from the daemon bind path; retain the numeric bound address as server_name.
    Local2 passed 84 tests with two Windows skips and ten startup samples. Hosted
    repeats are required to establish whether this explains the macOS delay.
11. Added six held-out extraction probes before inspecting their model outputs:
    a different negated beverage, dated warehouse move, another scoped project,
    deletion instruction attack, different reported third party, and Spanish.
    Models4 tests all twelve with real local providers; source is frozen for it.
12. Models4 retained useful candidates for all twelve inputs; nine machine quality
    checks passed. Two genuine failures omitted effective dates (office and
    held-out warehouse). The attribution fixture also failed an overly strict
    oracle that prohibited even a negative current-user statement; inspected
    output correctly attributed coffee to Bob and explicitly denied a user
    preference. Corrected the oracle to forbid affirmative user attribution,
    matching the stated expectation, rather than forbidding all user mentions.
13. Found a contract gap: suggested_scope was not exposed in the extraction
    schema, and promotion discarded suggested temporal boundaries. Added typed
    scope output and independent scope/time validation; carry approved date
    boundaries into the resulting claim and its temporal scope. Added promotion
    regressions for both lower and upper boundaries. Prompt v6 requests scope
    rather than relying on a paraphrased object to carry every qualifier.
14. Local3 was resource-deferred before any test executed: another owner's
    PID 92833 held the existing shared lock and had an actual Ollama connection.
    New temporal changes remain unverified until local/native repeats complete.

15. Native `9010319` exposed three related mock/conformance failures: the bundled
    mock extractor still emitted the obsolete `{type: review_required}` scope.
    Corrected unqualified mock output to null without relaxing the scope validator.
    Local4 passed 86 tests with two native-Windows skips and ten startup samples,
    including lower/upper boundary promotion regressions. Models5 is running
    prompt v6 against all twelve semantic cases; no quality pass is inferred yet.
16. Models5 completed with stable source identical to the Python files committed
    in `12ba6ed` (started from `9010319` plus the recorded mock correction).
    Seven of twelve quality checks passed; five were refused because model scopes
    contained empty objects or string "null" dates. Governance remained intact;
    this is a quality failure, not a pass. Replaced ambiguous nullable fields with
    disjoint unqualified/temporal/context branches. Temporal scopes require a date
    boundary; conditions require text; unused fields are omitted. Host validation
    still rejects malformed dates and intervals. Added branch-shape regressions.
17. Native `12ba6ed` passed all Linux/macOS matrix jobs and macOS startup budgets.
    macOS 3.13 maxima were 0.611s new / 0.327s current after the DNS fix, against
    unchanged targets. Build/recovery failed a 15-second restored-service start.
    Inspection found a second inherited reverse-DNS path in the TLS pairing
    listener; removed it and extended the deterministic DNS regression to pairing.
    Added the child status/startup log to recovery timeout errors without changing
    its deadline. The causal explanation for that build failure awaits a repeat.
18. Local5 passed 98 tests with two Windows skips, including both HTTP/TLS DNS
    paths and scope branches; all ten startup samples passed. Models6 admission
    was resource-deferred before execution after another owner acquired the lock.
    Latest real model output, final native artifacts and full-suite repeats remain
    required. No targets, provenance checks or quality expectations were relaxed.
19. Models7 executed on `6568db4` with stable source. Ten of twelve old machine
    checks passed, but manual review caught two false positives: the previous
    Paris office had a start boundary instead of an end boundary, and Orion's
    restriction was text-only with no stored scope. Warehouse/Vega produced no
    usable candidates. Strengthened the oracle to check boundary direction and
    both stored project inclusion/exclusion conditions, not just keyword presence.
20. Added conservative source-qualifier loss checks and bounded repair. Up to two
    corrections are requested after a rejected proposal, independently revalidated
    before any candidate is returned. Attempt status, rejection reason and output
    hash are recorded in invocation metadata. The limit is configurable from zero
    to two; privacy/policy refusal cannot be bypassed. This may use up to three
    provider requests per extraction; it is not a guarantee of semantic entailment.
21. Added explicit `project=NAME` / `project!=NAME` conditions, evaluated against
    actual project context/namespace-local project title rather than query words.
    Added positive/exclusion retrieval tests including a foreign namespace with a
    misleading title, bounded-repair tests, and regressions for the oracle's two
    observed false positives. Local6 passed 102 tests with two Windows skips and
    ten startup samples. Two additional fail-closed blank-project guards were
    then added; final stable repeat remains required.
22. Models8 is running the strengthened twelve-case checks with frozen Python
    source. These changes are not yet committed or qualified by the older native
    `6568db4` run. Inspect all candidate triples and scopes before accepting its
    terminal result; then finalize and repeat appropriate full/native checks.
23. Models8 finished with stable source: nine strict machine cases passed. Tea
    and reported-attribution cases had no usable candidate after all repairs;
    Orion's optional `Project` prefix was a third machine failure, although the
    runtime explicitly supports that alias. Aligned the oracle with the runtime
    alias rather than treating equivalent project labels as different conditions.
    Manual review also found a fabricated warehouse start date in a historical
    candidate. Its source stated an end month but no start month.
24. Replaced model-authored scope objects on the wire with source-bound references
    (`candidate_claim_draft.v2`). Each event supplies a catalog of unqualified,
    explicit English calendar boundaries/intervals and named-project conditions.
    The model selects a key; the host validates event ownership of that key and
    resolves the scope. Legacy objects must equal a known source anchor. This
    prevents new dates, empty objects, string-null dates and borrowing another
    event's scope. Date-only month anchors use the documented first-day convention;
    unsupported natural-language qualifiers still require human review. This is
    not a universal semantic parser or an entailment proof.
25. Simplified the model instructions to source-only extraction/reference choice;
    removed example facts and the nested scope-generation schema. Repair history
    now retains only the base prompt and latest rejected proposal, bounding
    context growth. Added source-catalog, cross-event reference and complete-
    interval tests; replaced obsolete wire-branch tests. Local7 passed 94 tests
    with two Windows skips and ten startup samples. Models9 is now running with
    frozen source. Final full/native/artifact verification is still pending.

26. Models9 passed the configured real recipe, eight advisory tasks and all twelve
    extraction quality/governance cases with source stability true. Manual review
    confirmed attached date direction and project conditions; source-backed month
    boundaries are normalized, quoted attribution remains with Alice/Mira, and
    Chinese/Spanish meaning is retained. Unattributed imperatives can retain an
    unspecified actor; operator review is still required rather than inventing one.
27. Historical native `6568db4` passed build and Linux/macOS/Windows 3.13, but
    Windows 3.11 failed 28 cases because owned standard-library scratch directories
    inherited broad ACLs. Kept its log. Added private scratch creation with native
    DACLs at directory creation and applied it to all eight internal scratch users.
    Kept broad-directory refusal. Also centralized database-destination preflight
    for initialization, restore and SQLite copies so plaintext is not written
    before permission validation, with atomic private file/directory creation.
28. Added Windows scratch/reservation/refusal regressions and tightened the
    temporal oracle to reject invented historical starts/current ends. Local8 was
    resource-deferred behind PID98593 with an actual model client; no test attempt
    counted. Local9 is testing the final preparation; final native/full/artifact
    repeats remain pending. The source calendar parser now uses fixed English
    month names independently of the host locale.
