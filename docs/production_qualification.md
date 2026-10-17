# Remaining production qualification

This follow-up addresses the blockers retained by the beta pressure campaign.
Results are pending until recorded below; implementation is not qualification.
No release is authorized by this document.

## Extraction contract

The model selects a complete, exact evidence event from schema-bound anchors.
The host independently validates its identifier, Unicode character boundaries
and byte-for-byte text equality. Blank subject, predicate, object and memory type
are rejected. Full-event evidence retains cross-sentence qualifiers; candidate
objects must preserve negation, attribution, temporal boundaries and exceptions.
All output remains untrusted and pending review. Source instructions cannot
approve, verify or promote candidates. Private/external and secret-source gates
remain in effect.

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
