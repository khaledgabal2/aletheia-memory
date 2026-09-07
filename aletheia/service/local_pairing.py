"""Local pairing v1: operator-issued codes, persistent TLS identity, scoped tokens.

Discovery metadata is never a trust anchor. The owner transfers the code out of
band; clients pin its fingerprint before sending its secret over TLS.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import secrets
import ssl
import stat
import threading
import time
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .errors import ServiceError, forbidden, unauthorized, validation_error
from .local_discovery import valid_label
from .local_files import identity_directory, read_private, write_private

PROTOCOL = "aletheia-local-pairing-v1"
PAIRING_CAPABILITIES = {"memory:read", "memory:audit", "memory:review"}
PAIRING_PATHS = {"/v1/pairing/info", "/v1/pairing/inspect", "/v1/pairing/complete", "/v1/pairing/cancel", "/v1/pairing/current"}


def _identity(directory: Path) -> tuple[Path, str, str]:
    import fcntl
    lock_fd = os.open(directory / "identity.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(lock_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("Invalid local identity lock.")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        path = directory / "identity.pem"
        if not path.exists() and not path.is_symlink():
            key = ec.generate_private_key(ec.SECP256R1())
            subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Aletheia local memory")])
            now = datetime.now(timezone.utc)
            cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
                    .public_key(key.public_key()).serial_number(x509.random_serial_number())
                    .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=3650))
                    .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
                    .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                    .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                    .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                        key_encipherment=False, data_encipherment=False, key_agreement=False,
                        key_cert_sign=False, crl_sign=False, encipher_only=None, decipher_only=None), critical=True)
                    .sign(key, hashes.SHA256()))
            write_private(path, cert.public_bytes(serialization.Encoding.PEM) + key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        bundle = read_private(path)
        certificate = x509.load_pem_x509_certificate(bundle)
        pem = certificate.public_bytes(serialization.Encoding.PEM).decode("ascii")
        return path, pem, certificate.fingerprint(hashes.SHA256()).hex()
    finally:
        os.close(lock_fd)


def _grants(value: dict) -> dict:
    if set(value) != {"client_name", "namespace_grants", "capabilities", "privacy_ceiling", "token_ttl_seconds"}:
        raise validation_error("Invalid pairing grant fields.")
    capabilities = value["capabilities"]
    namespaces = value["namespace_grants"]
    ttl = value["token_ttl_seconds"]
    if (not valid_label(value["client_name"]) or not isinstance(capabilities, list)
            or not capabilities or any(not isinstance(c, str) or c not in PAIRING_CAPABILITIES for c in capabilities)
            or not isinstance(namespaces, list) or not 1 <= len(namespaces) <= 16
            or any(not isinstance(n, str) or not re.fullmatch(r"[A-Za-z0-9_/*.-]{1,128}", n) for n in namespaces)
            or value["privacy_ceiling"] not in {"public", "personal", "private", "sensitive", "secret"}
            or type(ttl) is not int or not 300 <= ttl <= 2592000):
        raise validation_error("Pairing requires explicit limited grants and an expiry from 5 minutes to 30 days.")
    return {**value, "namespace_grants": sorted(set(namespaces)), "capabilities": sorted(set(capabilities))}


class LocalPairing:
    def __init__(self, service, public_port: int):
        self.service = service
        self.public_port = public_port
        self.directory = identity_directory(service.config.db_path, service.config.identity_directory)
        self.key_path, self.certificate_pem, self.fingerprint = _identity(self.directory)
        self.tls_port = 0
        self.httpd = None
        self.thread = None
        self.failures: dict[str, int] = {}
        self.descriptor = self.directory / f"running-{public_port}.json"

    def info(self) -> dict:
        return {"protocol": PROTOCOL, "public_port": self.public_port, "tls_port": self.tls_port,
                "certificate_sha256": self.fingerprint, "certificate_pem": self.certificate_pem,
                "service_identity": self.service.service_identity}

    def start(self) -> None:
        from http.server import ThreadingHTTPServer
        from .http import AletheiaRequestHandler
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(self.key_path)

        class Handler(AletheiaRequestHandler):
            pass
        Handler.service = self.service

        class SecureServer(ThreadingHTTPServer):
            daemon_threads = True
            slots = threading.BoundedSemaphore(32)
            def process_request(self, request, address):
                if not self.slots.acquire(blocking=False):
                    request.close()
                    return
                try:
                    super().process_request(request, address)
                except BaseException:
                    self.slots.release()
                    raise
            def process_request_thread(self, request, address):
                try:
                    request.settimeout(8)
                    secure = context.wrap_socket(request, server_side=True)
                    super().process_request_thread(secure, address)
                except (ssl.SSLError, OSError):
                    request.close()
                finally:
                    self.slots.release()

        self.httpd = SecureServer(("127.0.0.1", 0), Handler)
        self.httpd.transport_identity = self.fingerprint
        self.tls_port = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, name="aletheia-local-tls", daemon=True)
        self.thread.start()
        write_private(self.descriptor, json.dumps(self.info()).encode())

    def close(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        if self.thread:
            self.thread.join(timeout=2)
        try:
            if json.loads(read_private(self.descriptor))["service_identity"] == self.service.service_identity:
                self.descriptor.unlink(missing_ok=True)
        except FileNotFoundError:
            pass
        except (OSError, ValueError, KeyError, TypeError):
            logging.getLogger(__name__).warning("Local pairing descriptor cleanup was unavailable.")

    def _ticket(self, payload: dict) -> tuple[Path, dict]:
        if set(payload) != {"invitation_id", "secret"} or not isinstance(payload["invitation_id"], str) or not isinstance(payload["secret"], str):
            raise validation_error("Invalid pairing request.")
        identifier, secret = payload["invitation_id"], payload["secret"]
        if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", identifier) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", secret):
            raise unauthorized("Pairing code is invalid, expired, or already used.")
        path = self.directory / f"invitation-{identifier}.json"
        try:
            ticket = json.loads(read_private(path, 8192))
            valid = (ticket["protocol"] == PROTOCOL and ticket["service_identity"] == self.service.service_identity
                     and ticket["certificate_sha256"] == self.fingerprint and ticket["expires_at_ms"] > int(time.time() * 1000)
                     and secrets.compare_digest(ticket["secret_sha256"], hashlib.sha256(secret.encode()).hexdigest()))
            if not valid:
                if len(self.failures) >= 128 and identifier not in self.failures:
                    self.failures.pop(next(iter(self.failures)))
                self.failures[identifier] = self.failures.get(identifier, 0) + 1
                if self.failures[identifier] >= 5:
                    path.unlink(missing_ok=True)
                    self.failures.pop(identifier, None)
                raise unauthorized("Pairing code is invalid, expired, or already used.")
            _grants(ticket["grants"])
            return path, ticket
        except (FileNotFoundError, ValueError, KeyError, TypeError):
            raise unauthorized("Pairing code is invalid, expired, or already used.") from None

    def handle(self, method: str, endpoint: str, payload: dict, headers: dict, transport_identity: str | None) -> dict:
        if method == "GET" and endpoint == "/v1/pairing/info":
            return self.info()
        if transport_identity != self.fingerprint:
            raise forbidden("Local pairing requires the pinned encrypted transport.")
        if method == "DELETE" and endpoint == "/v1/pairing/current":
            context = self.service.auth.authenticate(self.service._header(headers, "Authorization"), auth_required=True)
            if not context.token or context.token.metadata.get("local_pairing_identity") != self.fingerprint:
                raise forbidden("Only this paired credential can be revoked here.")
            with self.service.memory.store.transaction():
                self.service.auth.revoke_token(context.token.id, reason="local_pairing_sign_out")
                self._audit(context.token.id, "local_pairing.revoked", {"client_id": context.client_id})
            return {"revoked": True}
        if method != "POST" or endpoint not in {"/v1/pairing/inspect", "/v1/pairing/complete", "/v1/pairing/cancel"}:
            raise ServiceError("not_found", "Pairing operation not found.", status_code=404)
        path, ticket = self._ticket(payload)
        if endpoint == "/v1/pairing/inspect":
            return {"protocol": PROTOCOL, "certificate_sha256": self.fingerprint,
                    "service_identity": self.service.service_identity, "expires_at_ms": ticket["expires_at_ms"], **ticket["grants"]}
        # Service lock serializes validation and consumption. Tickets bind to this
        # running instance; another daemon/restart cannot consume the same ticket.
        path.unlink()
        self.failures.pop(payload["invitation_id"], None)
        if endpoint == "/v1/pairing/cancel":
            return {"canceled": True}
        grants = ticket["grants"]
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=grants["token_ttl_seconds"])).isoformat()
        with self.service.memory.store.transaction():
            client = self.service.auth.create_client(name=grants["client_name"], client_type="sdk", metadata={"local_pairing_identity": self.fingerprint})
            token, raw = self.service.auth.create_token(client_id=client.id, namespace_grants=grants["namespace_grants"],
                capabilities=grants["capabilities"], privacy_ceiling=grants["privacy_ceiling"], expires_at=expiry,
                metadata={"local_pairing_identity": self.fingerprint})
            self._audit(token.id, "local_pairing.completed", {"client_id": client.id, **grants})
        return {"protocol": PROTOCOL, "certificate_sha256": self.fingerprint,
                "service_identity": self.service.service_identity, "token": raw, "expires_at": token.expires_at}

    def _audit(self, token_id: str, action: str, details: dict) -> None:
        self.service.memory._write_audit(namespace="system/local-pairing", target_type="api_token",
            target_id=token_id, action=action, details={"certificate_sha256": self.fingerprint, **details})


def create_invitation(*, db_path: str, public_port: int, grants: dict, root: str | None = None) -> str:
    """Operator-only CLI boundary. Does not open/migrate the database or mint a token."""
    if os.name != "posix":
        raise ValueError("Local pairing currently requires a POSIX owner-only identity directory.")
    if type(public_port) is not int or not 1024 <= public_port <= 65535:
        raise ValueError("Use a non-privileged local service port.")
    approved = _grants(grants)
    directory = identity_directory(db_path, root)
    bundle = read_private(directory / "identity.pem")
    certificate = x509.load_pem_x509_certificate(bundle)
    pem = certificate.public_bytes(serialization.Encoding.PEM).decode("ascii")
    fingerprint = certificate.fingerprint(hashes.SHA256()).hex()
    descriptor = json.loads(read_private(directory / f"running-{public_port}.json"))
    tls_port = descriptor["tls_port"]
    if type(tls_port) is not int or not 1024 <= tls_port <= 65535:
        raise ValueError("Invalid running-service descriptor.")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_verify_locations(cadata=pem)
    connection = http.client.HTTPSConnection("127.0.0.1", tls_port, context=context, timeout=5)
    try:
        connection.request("GET", "/v1/pairing/info")
        response = connection.getresponse()
        raw = response.read(16385)
        if response.status != 200 or len(raw) > 16384:
            raise ValueError("The intended service could not be verified.")
        info = json.loads(raw)["data"]
        if (info["certificate_sha256"] != fingerprint or info["public_port"] != public_port
                or info["service_identity"] != descriptor["service_identity"] or info["protocol"] != PROTOCOL):
            raise ValueError("The intended service changed; retry with its current address.")
    finally:
        connection.close()
    now = int(time.time() * 1000)
    # Owner-created tickets are bounded; clean only expired invitations, never
    # an identity, descriptor, or another active service's registration.
    active = 0
    for index, entry in enumerate(directory.iterdir()):
        if index >= 256:
            raise ValueError("Local pairing directory needs operator cleanup.")
        if not re.fullmatch(r"invitation-[0-9a-f-]{36}\.json", entry.name):
            continue
        ticket = json.loads(read_private(entry, 8192))
        if ticket["expires_at_ms"] <= now:
            entry.unlink()
        else:
            active += 1
    if active >= 64:
        raise ValueError("Too many outstanding pairing codes; wait for expiry or cancel one.")
    identifier, secret = str(uuid.uuid4()), secrets.token_urlsafe(32)
    expires = now + 300000
    write_private(directory / f"invitation-{identifier}.json", json.dumps({
        "protocol": PROTOCOL, "service_identity": info["service_identity"], "certificate_sha256": fingerprint,
        "secret_sha256": hashlib.sha256(secret.encode()).hexdigest(), "expires_at_ms": expires, "grants": approved,
    }).encode())
    code = {"protocol": PROTOCOL, "public_port": public_port, "tls_port": tls_port,
            "certificate_sha256": fingerprint, "service_identity": info["service_identity"],
            "invitation_id": identifier, "secret": secret, "expires_at_ms": expires}
    return "aletheia-local-v1." + base64.urlsafe_b64encode(json.dumps(code, separators=(",", ":")).encode()).decode().rstrip("=")
