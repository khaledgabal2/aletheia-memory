# Published 1.3.1 compatibility baseline

`client.py` is an unmodified copy from the published `aletheia-memory==1.3.1`
distribution. Source, retrieval date, MIT license and SHA-256 are recorded in
`provenance.json`. It is deliberately independent of the live SDK module.
Never change this fixture to make a new service pass a compatibility check.

`openapi.json` contains the selected existing profile paths and original envelope
schemas, extracted from a real `/v1/openapi.json` response. It is historical,
not an authoritative schema for the new service. Summary counts and a hash of
the complete baseline schema are in `summary.json`.

`responses.json` contains 26 synthetic actual-HTTP observations, including
successes and denial/error responses. Detailed security reproductions are kept
private outside the repository according to SECURITY.md. It contains
no user data, credentials, authorization headers or token hashes. Generated
IDs and timestamps are retained to preserve the response shapes. These are not
byte-for-byte golden expectations and do not replace negative authorization tests.

Reproduce on the unchanged 1.3.1 runtime from the Phase 0 checkout:

```sh
python scripts/v1_4_phase0.py --output /tmp/new-phase0-capture
```

The output directory must not exist. Runtime module hashes are checked against
the published package before capture; a modified/new runtime is rejected rather
than mislabeled as historical evidence. Test credentials/databases are generated
in temporary directories and removed after the harness shuts down its loopback
service. Capture is an explicit local-network test, not part of normal startup.
