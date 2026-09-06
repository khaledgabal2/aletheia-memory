# Local Registration And Pairing v1

Unreleased in Memory 1.5.0.dev0. This is local application pairing, independent
of federation. The existing HTTP API and 1.4.1 client contracts remain compatible.
No storage schema migration is added.

## Running And Advertising

On POSIX, `aletheia serve` automatically advertises loopback instances in
`~/.aletheia/desktop-discovery` and enables local TLS pairing when authentication
is required. Each daemon owns a UUID-named mode-0600 JSON registration in a
mode-0700 directory. Format 1 contains exactly `format_version`,
`registration_id`, `label`, `port`, `service_identity`, `expires_at_ms`.
Leases last 30 seconds and renew every 10 seconds. Normal exit and SIGTERM remove
only the daemon's record. A crash leaves an expiring hint. Other records survive.

Use `--service-name`, `--discovery-dir`, `--no-advertise`, `--identity-dir`, or
`--no-local-pairing` with `serve`. Equivalent `[local]` configuration keys are
`name`, `discovery_directory`, `advertise`, `identity_directory`, and `pairing`.
`ALETHEIA_DISCOVERY_DIR` and `ALETHEIA_IDENTITY_DIR` also select absolute roots.
Both `serve` and `console serve` load this configuration. Advertising and pairing
are disabled for remote binds/allow-remote; tokenless services cannot pair.
Programmatic `ServiceConfig` callers opt into pairing with `local_pairing_enabled=True`.
Windows local advertising/pairing requires a future ownership/ACL implementation.

Discovery is untrusted. It cannot enumerate offline databases, embedded Memory
objects, opted-out services, or installations that do not publish the format.
A stale record during port reuse never authorizes a credential. Clients compare
instance hints and reject mismatches until the hint expires or is refreshed.

## Owner Approval

Start your intended service, then explicitly choose grants when issuing a code:

```sh
aletheia pairing invite --db ./example.db --port 8765 --name 'Aletheia Desktop' --namespace user/default --capability memory:read --capability memory:audit --privacy-ceiling personal --token-ttl-seconds 86400
```

Use the same `--identity-dir` if startup used a custom root. Repeat `--namespace`
and `--capability` for additional explicit grants. Allowed capabilities are
`memory:read`, `memory:audit`, `memory:review`; administrative capabilities are
not available. Credential lifetime is 5 minutes to 30 days; default 24 hours.
Each code lasts 5 minutes and can be consumed once. Keep it private. The app
shows the approved namespaces, capabilities, privacy ceiling, and duration for
confirmation. Its client cannot request broader grants during completion.

The CLI verifies the private service descriptor through pinned TLS before writing
an owner-only invitation. It does not open or migrate the database or create an
API token. The service creates the client and token atomically only on successful
completion; token creation and self-revocation leave secret-free audit events in
`system/local-pairing`. The database stores only bearer hashes through AuthService.

## Protocol And Trust Boundary

The code is `aletheia-local-v1.` followed by unpadded base64url JSON containing
`protocol=aletheia-local-pairing-v1`, public/TLS ports, certificate SHA-256,
transient service identity, UUID invitation ID, 32-byte secret, and expiry in ms.
Do not treat the encoding as encryption. Invite files store only the secret hash.
Five incorrect guesses invalidate the invitation. Outstanding owner-created
invitations and request/file sizes are bounded.

A private ECDSA P-256 identity is bound to the canonical database path and its
device/inode. Certificate and key are one atomic owner-only PEM file. Certificate
lifetime is 10 years; expired or changed keys are never trusted automatically.
A separate loopback TLS listener uses an OS-assigned port, TLS 1.2 or newer, and
a certificate for the literal IP 127.0.0.1. Slow handshakes run outside the accept
loop with timeouts and a 32-worker ceiling.

| Operation | Transport and result |
| --- | --- |
| GET `/v1/pairing/info` | Public certificate material, ports, and transient instance hint; no trust established |
| POST `/v1/pairing/inspect` | Pinned TLS and `{invitation_id, secret}`; authoritative grant summary |
| POST `/v1/pairing/complete` | Pinned TLS, same request; single-use exchange returning expiring bearer only to credential host |
| POST `/v1/pairing/cancel` | Pinned TLS, same request; invalidate the invitation |
| DELETE `/v1/pairing/current` | Pinned TLS and current paired bearer; revoke only that credential |
| GET `/v1/auth/me` | Pinned TLS and paired bearer; existing scoped principal contract |

Match public certificate material against the code fingerprint **before sending
any secret**. Clients use only that certificate as their TLS trust root, retain
hostname verification, and refuse redirects, ambient proxies, and plaintext
fallback. Pairing-issued credentials are rejected on the public HTTP API and on
a different TLS identity. A public port/label/instance ID is never ownership proof.
All responses are no-store; request IDs and errors never echo pairing input.

Restart preserves the certificate and existing unexpired credentials, while
invalidating unused codes tied to the previous running instance. Database
replacement/relocation or identity-directory loss requires fresh pairing. After
key rotation, revoke old credentials through owner administration; do not copy an
old identity onto an unrelated database. Expired/used codes cannot be renewed.
Create a fresh code. If completion loses its response, its credential may remain
until expiry or owner revocation; there is no token-recovery or replay endpoint.

Desktop native clients keep credentials in the OS store; local browser hosts keep
them in process memory. This protocol does not define remote browser sessions,
LAN discovery, enterprise identity, OS service supervision, or signed packaging.

## Validation

`tests/test_v1_5_local_pairing.py` covers multi-instance leases, shutdown/crash,
opt-out, restarts/database replacement, permissions/grants, replay races,
cancel/expiry/guess limits, TLS-only authorization, wrong certificate rejection,
audit redaction, bounded slow handshakes, and OpenAPI profile conformance. The
complete Memory suite passes 329 tests on macOS/Python 3.13.13. Desktop consumer
and real Keychain tests are recorded in the sibling Desktop pairing decision.
