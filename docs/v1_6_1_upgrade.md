# Memory 1.6.1 beta upgrade

1.6.1 repairs the independently verified findings in the 1.6.0 code review.
The API remains v1 and storage remains 1.3.1. This is a release candidate until
GitHub and PyPI publication completes.

Keep a verified encrypted backup and the previous binary before upgrading.
Install the reviewed wheel in a separate environment and validate it with
synthetic data. After publication, the equivalent pinned install is
`python -m pip install aletheia-memory==1.6.1`.

## Changes that require caller updates

- Active agent creation accepts only active or candidate status. Core promotion
  remains an explicitly reviewed operation. Ingest enforces the credential's
  privacy ceiling.
- Namespace administrators cannot operate on foreign targets or selectors.
  Physical backups, restores, global migrations, keys and encryption settings
  require a wildcard namespace grant. Raw exports require full secret privacy
  access. Reports require administrative capability and full privacy access;
  notification mutations require administration.
- Archives use exclusive 0600 output creation. Choose a new output name when
  a destination already exists. Use `--passphrase-stdin` or the existing backup
  passphrase environment variable instead of process arguments.
- Imports require an explicit destination namespace. Plain archives and legacy
  encrypted archives whose manifests are unauthenticated require explicit
  `trust_unauthenticated=True` / `--trust-unauthenticated` after independent trust
  verification. Newly created encrypted manifests are authenticated. Imports
  refuse instance-local ciphertext; use an encrypted portable logical export.
- Object IDs unavailable under current authority receive the same generic 403
  error as absent IDs. Public route/type errors still use 404. CSRF and missing
  capability diagnostics remain explicit.
- Federation mutations require exact IDs, rather than remote-controlled names;
  unique-name lookup remains available for inspection.
- Repeated inference/proposal decisions cannot reopen terminal state. Editing a
  validated candidate still requires renewed review by design.
- Interrupted file operations retain uncertain idempotency reservations rather
  than being repeated after five minutes; inspect the output before recovery.
- Provider and SDK response bodies are bounded at 8 MiB; ZIPs are bounded at 256 MiB decompressed
  size and 10,000 members.
- Crashed jobs with a proven exited local owner are recovered with retry backoff.
  Unknown historical ownership requires explicit operator confirmation through
  `POST /v1/jobs/{job_id}/recover` or `Memory.recover_job`. Known live owners are always
  refused, including when confirmation is supplied. On non-POSIX platforms,
  foreign process liveness remains unknown and no process is signaled.
- Automatic migration refuses schemas older than the published 1.3.0 minimum.
  Preserve older databases for manual recovery rather than experimenting on
  the sole copy.

Backup verification records are retained for audit; failed verifications do
not establish readiness. A prior bug may already have disclosed or destroyed
data, which an upgrade cannot reverse. Revoke unintended federation recipients
and rotate affected sharing credentials when prior exposure is established.

See [review resolution](v1_6_0_review_resolution.md) for issue mappings and
[release verification](v1_6_1_release_verification.md) for publication gates.
