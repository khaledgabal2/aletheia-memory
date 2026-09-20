# Federation key recovery

Use this procedure when a federation signing or encryption key may have been
exposed. It replaces both key pairs, preserves a separate encrypted copy of the
old decryption key, and requires fresh operator approval on every peer. It does
not run automatically, recall previously shared data, or prove that historical
data was authentic. Ordinary memory remains in the database.

## Prepare

Pause federation transfers on the affected instances and install the repaired
software on each one. Identify their databases, peer IDs, current fingerprints,
and any outstanding encrypted bundles. Preserve restricted recovery copies of
the databases using independently verified backup tooling.

Create a private directory for recovery files. On POSIX systems, for example:

```bash
mkdir -m 700 ./private-recovery
aletheia federation status --db ./device.db
```

Provide a strong, independently generated recovery secret through the operator's
protected environment as `ALETHEIA_FEDERATION_RECOVERY_KEY`. Keep a secure copy
separate from the recovery files. Do not put it in a command argument, transcript,
repository, or shared bundle. For a protected identity, its existing
`ALETHEIA_FEDERATION_KEY` (or `ALETHEIA_PROTECTED_KEY`) is also needed to read the
current private key. Recovery and current-key protection are separate purposes.

Recovery files use authenticated AES-256-GCM encryption with the existing
PBKDF2-SHA256 implementation. Each file is created exclusively, flushed, and
decrypted again to verify it before the database changes. Existing files and
symlinks are refused. Files are created with mode `0600` on POSIX; on Windows,
restrict the containing directory with appropriate ACLs.

## Rotate the local identity

Record the current fingerprint as `LOCAL_OLD_FINGERPRINT`, then run:

```bash
aletheia federation rotate-key --db ./device.db \
  --expected-fingerprint "$LOCAL_OLD_FINGERPRINT" \
  --recovery-output ./private-recovery/device-old.key \
  --reason "Recovery after possible federation key exposure"

aletheia federation export-identity --db ./device.db \
  --output ./device-new.identity.json
```

Rotation preserves the instance ID and generates new signing and encryption
keys. It revokes all existing local share grants, their collections, and their
recipients, including imported grants. Recreate only the grants that are still
needed. CLI and HTTP identity responses contain public information only.

The recovery file contains the old X25519 private decryption key and the public
identity needed to check it. It contains no old signing private key and no new
private keys. The normal import path never reads recovery files or falls back to
retired keys. Older calls without an expected fingerprint and a recovery output
now fail before rotation instead of silently discarding decryption capability.

Rotation and its revocations/audit records share one database transaction. A
stale fingerprint, missing secret, unavailable output, or failed verification
leaves the database unchanged. If a database failure occurs after the encrypted
file is written, that file is retained. Inspect the current fingerprint before
retrying, and choose a new output path. Never assume a returned connection error
means the rotation did not commit.

## Approve the replacement on each peer

Exchange `device-new.identity.json` and verify the new fingerprint through an
independent trusted channel. A message signed only by the potentially compromised
old key is not sufficient authorization. Confirm the full old and new
fingerprints, not just a shortened display prefix.

On each peer that knows the affected instance:

```bash
aletheia peers replace-key PEER_ID --db ./peer.db \
  --identity ./device-new.identity.json \
  --expected-fingerprint "$PEER_OLD_FINGERPRINT" \
  --confirmed-fingerprint "$VERIFIED_NEW_FINGERPRINT" \
  --reason "Replacement fingerprints verified independently"
```

This works for a previously trusted, blocked, or revoked peer. It requires the
same instance ID and new material for both key pairs. It permanently records the
retired public keys, rejects their reuse, sets the replacement to `unknown`,
clears its old trust domain, and revokes its existing shares. Ordinary `peers add`
cannot replace a pinned key; old bundles and old grants remain rejected.
An approval already in progress fails if replacement or revocation changed its
peer before the trust update, so it cannot restore trust using an outdated key.

Make any subsequent trust decision separately, for example:

```bash
aletheia peers trust PEER_ID --db ./peer.db \
  --status trusted_device --reason "Explicit approval of verified replacement"
```

Create fresh scoped share grants as needed. Default imports remain
`candidate_only`; active imports still require an explicit active policy and
the corresponding authorization. Verify a fresh bundle works before resuming
normal transfers. Rotate/re-approve each affected instance independently.

## Recover pending historical bundles for review

An old encrypted bundle addressed to the retired local key will fail ordinary
import. Recover its contents to a separate encrypted review file instead:

```bash
aletheia federation recover-bundle --db ./device.db \
  --input ./pending.aletsync \
  --recovery-key ./private-recovery/device-old.key \
  --expected-fingerprint "$LOCAL_OLD_FINGERPRINT" \
  --output ./private-recovery/pending.review \
  --reason "Review outstanding data after key replacement"
```

Use the recovery secret that protected that particular key file. The operation
checks the archive's identity and decryption key, bundle checksums, signature,
and encryption authentication. It changes no database rows. The result is always
marked `requires_review`, is encrypted under the recovery secret, and is not a
sync package that normal import can accept. Identity metadata from legacy
bundles, including leaked private-key records, is excluded from the review file.

The embedded API can decrypt that file for a local review tool:

```python
review = memory.read_federation_recovery_review(
    input_path="./private-recovery/pending.review"
)
assert review["requires_review"] is True
# Inspect review["payloads"] in a private review workflow.
# Any later ingestion must preserve provenance/privacy and use normal review.
```

Recovery does not authorize a sender or establish the authenticity of content
signed while a key may have been compromised. Review it independently. There is
no HTTP endpoint for decrypting recovery artifacts. If an older rotation already
discarded a key and no restricted copy exists, this feature cannot reconstruct
that lost key.

## Embedded and HTTP interfaces

Embedded callers use `rotate_federation_key(expected_fingerprint=...,
recovery_path=..., reason=...)`, `replace_peer_key(peer_id, peer_identity=...,
expected_fingerprint=..., confirmed_fingerprint=..., reason=...)`, and
`recover_share_bundle_for_review(...)`. The rotation/recovery methods can take
an explicit `recovery_passphrase`; omission uses the protected environment.

`POST /v1/federation/identity/rotate` now requires `memory:admin`, a reason,
`expected_fingerprint`, and `recovery_path`. The path is on the server and must
be a new file under an admin safe root. The recovery secret must be configured
on that server; it is not accepted from the request body. The response contains
only the public identity.

`POST /v1/peers/{peer_id}/replace-key` requires `memory:admin`, `peer_identity`,
`expected_fingerprint`, `confirmed_fingerprint`, and a reason. It returns the
replacement peer in `unknown` trust state. Both Python SDKs expose these guarded
operations. Requesting ordinary `memory:federation` or `memory:peers` capability
does not grant key-replacement authority.

## Completion evidence

Keep a record of affected instances, full retired/replacement fingerprints,
peer approvals, fresh grant IDs, and validation outcomes, without private keys
or recovery secrets. Verify after restart that retired keys/grants are rejected,
fresh approved peers work, and any required pending data can be recovered for
review. Retain recovery files only as long as they are needed, under restricted
storage. Old bundles and database copies remain sensitive: rotation does not
erase private material from prior exports, backups, or database storage remnants.
