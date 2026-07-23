from __future__ import annotations

import hashlib

import pytest

from aletheia.core.crypto import (
    AES_GCM_PASSPHRASE_ALGORITHM,
    decrypt_bytes_with_passphrase,
    encrypt_bytes_with_passphrase,
    hash_secret,
    verify_secret_hash,
)
from aletheia.core.errors import ValidationError


def test_secret_hashing_is_versioned_salted_and_legacy_compatible():
    stored = hash_secret("correct horse battery staple")
    assert stored.startswith("pbkdf2_sha256$")
    assert verify_secret_hash("correct horse battery staple", stored)
    assert not verify_secret_hash("wrong secret", stored)

    legacy = hashlib.sha256("legacy-token".encode("utf-8")).hexdigest()
    assert verify_secret_hash("legacy-token", legacy)
    assert not verify_secret_hash("wrong-token", legacy)


def test_passphrase_aes_gcm_envelope_detects_tampering():
    cipher, metadata = encrypt_bytes_with_passphrase(
        b"backup bytes",
        "shared passphrase",
        key_id="key_test",
    )
    assert metadata["algorithm"] == AES_GCM_PASSPHRASE_ALGORITHM
    assert decrypt_bytes_with_passphrase(cipher, "shared passphrase", metadata) == b"backup bytes"

    tampered = bytearray(cipher)
    tampered[-1] ^= 1
    with pytest.raises(ValidationError):
        decrypt_bytes_with_passphrase(bytes(tampered), "shared passphrase", metadata)

