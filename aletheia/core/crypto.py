"""Shared cryptographic helpers for Aletheia security boundaries."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from aletheia.core.errors import ValidationError


AES_GCM_PASSPHRASE_ALGORITHM = "AES-256-GCM-PBKDF2-SHA256"
LEGACY_XOR_HMAC_ALGORITHM = "xor-stream-hmac-sha256"
PBKDF2_SECRET_HASH_ALGORITHM = "pbkdf2_sha256"
PBKDF2_KEY_DERIVATION = "pbkdf2-sha256"
PBKDF2_ITERATIONS = 120_000


def random_bytes(length: int) -> bytes:
    return secrets.token_bytes(length)


def sha256_hex(data: bytes | str) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def constant_time_equal(left: bytes | str, right: bytes | str) -> bool:
    return hmac.compare_digest(left, right)


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii")


def b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


def derive_pbkdf2_key(
    secret: str,
    salt: bytes,
    *,
    iterations: int = PBKDF2_ITERATIONS,
    length: int = 32,
) -> bytes:
    if iterations <= 0:
        raise ValidationError("PBKDF2 iterations must be positive.")
    return hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations, dklen=length)


def generate_aes_key() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def aes_gcm_encrypt(key: bytes, nonce: bytes, data: bytes, associated_data: bytes | None = None) -> bytes:
    return AESGCM(key).encrypt(nonce, data, associated_data)


def aes_gcm_decrypt(key: bytes, nonce: bytes, cipher: bytes, associated_data: bytes | None = None) -> bytes:
    try:
        return AESGCM(key).decrypt(nonce, cipher, associated_data)
    except InvalidTag as exc:
        raise ValidationError("Encrypted payload authentication failed.") from exc


def encrypt_bytes_with_passphrase(
    data: bytes,
    passphrase: str,
    *,
    key_id: str | None = None,
    associated_data: bytes | None = None,
) -> tuple[bytes, dict]:
    salt = random_bytes(16)
    nonce = random_bytes(12)
    key = derive_pbkdf2_key(passphrase, salt)
    cipher = aes_gcm_encrypt(key, nonce, data, associated_data)
    return cipher, {
        "algorithm": AES_GCM_PASSPHRASE_ALGORITHM,
        "kdf": PBKDF2_KEY_DERIVATION,
        "kdf_iterations": PBKDF2_ITERATIONS,
        "salt": b64url_encode(salt),
        "nonce": b64url_encode(nonce),
        "key_id": key_id,
    }


def decrypt_bytes_with_passphrase(
    cipher: bytes,
    passphrase: str,
    metadata: dict,
    *,
    associated_data: bytes | None = None,
) -> bytes:
    if metadata.get("algorithm") != AES_GCM_PASSPHRASE_ALGORITHM:
        raise ValidationError("Unsupported encrypted payload algorithm.")
    if metadata.get("kdf", PBKDF2_KEY_DERIVATION) != PBKDF2_KEY_DERIVATION:
        raise ValidationError("Unsupported encrypted payload key derivation.")
    try:
        iterations = int(metadata.get("kdf_iterations", PBKDF2_ITERATIONS))
        salt = b64url_decode(metadata["salt"])
        nonce = b64url_decode(metadata["nonce"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Encrypted payload metadata is malformed.") from exc
    key = derive_pbkdf2_key(passphrase, salt, iterations=iterations)
    return aes_gcm_decrypt(key, nonce, cipher, associated_data)


def hash_secret(value: str) -> str:
    salt = random_bytes(16)
    digest = derive_pbkdf2_key(value, salt)
    return "$".join(
        [
            PBKDF2_SECRET_HASH_ALGORITHM,
            str(PBKDF2_ITERATIONS),
            salt.hex(),
            digest.hex(),
        ]
    )


def verify_secret_hash(value: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    parts = stored_hash.split("$")
    if len(parts) == 4 and parts[0] == PBKDF2_SECRET_HASH_ALGORITHM:
        try:
            iterations = int(parts[1])
            salt = bytes.fromhex(parts[2])
            expected = bytes.fromhex(parts[3])
            digest = derive_pbkdf2_key(value, salt, iterations=iterations)
        except (ValueError, ValidationError):
            return False
        return constant_time_equal(digest, expected)
    if len(stored_hash) == 64:
        legacy = sha256_hex(value)
        return constant_time_equal(legacy, stored_hash)
    return False


def decrypt_legacy_xor_hmac_bytes(cipher: bytes, passphrase: str, metadata: dict) -> bytes:
    try:
        salt = b64url_decode(metadata["salt"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Legacy encrypted payload metadata is malformed.") from exc
    key = derive_pbkdf2_key(passphrase, salt)
    expected = hmac.new(key, cipher, hashlib.sha256).hexdigest()
    if not constant_time_equal(expected, metadata.get("mac", "")):
        raise ValidationError("Encrypted payload authentication failed.")
    return _legacy_xor_stream(cipher, key)


def decrypt_legacy_xor_hmac_content(*, cipher: bytes, passphrase: str, salt: bytes, mac: bytes) -> bytes:
    key = derive_pbkdf2_key(passphrase, salt)
    expected = hmac.new(key, cipher, hashlib.sha256).digest()
    if not constant_time_equal(expected, mac):
        raise ValidationError("Encrypted content authentication failed.")
    return _legacy_xor_stream(cipher, key)


def _legacy_xor_stream(data: bytes, key: bytes) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < len(data):
        block = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha256).digest()
        output.extend(block)
        counter += 1
    return bytes(byte ^ output[index] for index, byte in enumerate(data))
