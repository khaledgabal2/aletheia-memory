# Aletheia Memory 1.7.0 release qualification

Release date: October 17, 2026 (America/Chicago). Software 1.7.0
production/stable; Python 3.11+; API v1; storage 1.3.1. Production support is
bounded by the [release notes](v1_7_0_release_notes.md#qualification-and-limits).

The runtime accepted in [PR #69](https://github.com/khaledgabal2/aletheia-memory/pull/69)
was qualified before the version/metadata/documentation preparation. It passed
1,104 local tests, fourteen scorecards, twelve manually reviewed real-model
extraction probes and eight advisory workflows. Native Linux/macOS/Windows on
Python 3.11/3.12/3.13, installed artifacts, SDK/HTTP/MCP/TypeScript interfaces,
bounded disk/memory recovery and the 1,800-second/2,540-cycle lifecycle soak passed.
The full [step-by-step journal](production_qualification.md) retains source
revisions, previous failures, invalidations and resource-deferred checks.

Release gates are run on the final release source on main and again by the
trusted publication workflow on tag `v1.7.0`. Distribution builds are checked
with strict Twine metadata validation and embedded README equality before
publication. The immutable release assets carry actual workflow artifacts,
SHA256 checksums and postpublication verification receipts. Those receipts,
rather than this prepublication source record, establish upload/fresh-install
success. No package or tag is replaced to update a publication receipt.

An initial Windows 3.12 750ms concurrency timeout passed unchanged on repeat;
its root cause is unproven. Model review, bounded grammar, trusted Windows
ancestors, POSIX-only pairing, sampled startup budgets and the monotonic soak's
host-suspension limitation remain explicit release constraints, not waived gates.
