# Upgrade to Aletheia Memory 1.7.0

Version 1.7.0 is production/stable within the [release boundaries](v1_7_0_release_notes.md#qualification-and-limits).
Python remains 3.11+, API v1 and storage 1.3.1. Install the pinned release:

```sh
python -m pip install --upgrade aletheia-memory==1.7.0
aletheia --help
```

Before replacing an important installation, stop writers, create an authenticated
backup using the existing [backup/recovery procedures](operations_guide.md), and
verify restore into a separate private location. Preserve the old binary, backup
and identity directory. Do not open upgraded data with older software merely to
roll back: restore its matching backup instead. From storage 1.3.0 use the
[migration guide](v1_4_0_migration_guide.md); 1.6.x storage 1.3.1 needs no schema bump.
Normal restarts preserve pairing credentials; restored/relocated databases require
fresh pairing because the TLS identity binds to the database file.

## Caller changes

- Zero-strength feedback and evidence-free assistant repetition are inert.
- Context token budgets must be nonnegative integers. Conflict scope resolutions
  must include a complete, atomic scope for every conflicting claim.
- Advisory LLM outputs must satisfy task-specific contracts. Invalid outputs fail
  rather than yielding placeholder advice. Candidate extraction schema metadata
  is `candidate_claim_draft.v2`; the model chooses source `scope_ref` keys and
  the public candidate exposes resolved `suggested_scope`. Raw provider-schema
  integrations need to adopt that wire format. At most two repair attempts may
  follow rejection, and all proposals still require explicit human review.
- Approved temporal dates survive promotion. `project=NAME` and `project!=NAME`
  use actual project context/namespace-local titles, not words in a query.
- MCP stdio supports the standard initialization/tools JSON-RPC lifecycle; no
  unsolicited ready line is emitted. The legacy tool/arguments request remains
  supported before standard initialization. Use an official MCP client for new
  integrations and preserve mode/namespace authorization.

## Windows and operation

Choose a private database directory with trusted ancestors. Shared grants are
refused before writes and are never silently tightened. Owner-provisioned private
DACLs protect files, sidecars and internal scratch artifacts against other standard
principals; administrator/SYSTEM and offline disk access are outside this boundary.
Local pairing remains POSIX-only. Configure semantic/LLM providers explicitly and
retain the index model/dimension/prefix recipe; defaults are not quality evidence.
See [security](security_privacy_guide.md), [release notes](v1_7_0_release_notes.md)
and [qualification](v1_7_0_release_verification.md) for measured limits.
