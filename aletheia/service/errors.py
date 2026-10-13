"""Service-layer errors with HTTP/MCP error codes."""

from __future__ import annotations


class ServiceError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def unauthorized(message: str = "Authentication required.") -> ServiceError:
    return ServiceError("unauthorized", message, status_code=401)


def forbidden(message: str = "Forbidden.", details: dict | None = None) -> ServiceError:
    return ServiceError("forbidden", message, status_code=403, details=details)


def validation_error(message: str, details: dict | None = None) -> ServiceError:
    return ServiceError("validation_error", message, status_code=400, details=details)


def not_found(message: str) -> ServiceError:
    return ServiceError("not_found", message, status_code=404)


def rate_limited(message: str = "Rate limit exceeded.") -> ServiceError:
    return ServiceError("rate_limited", message, status_code=429)


def idempotency_conflict(message: str = "Idempotency key reused with a different payload.") -> ServiceError:
    return ServiceError("idempotency_conflict", message, status_code=409)


def stale_schema(message: str) -> ServiceError:
    return ServiceError("stale_schema", message, status_code=503)


ERROR_CODES = ['database_busy', 'forbidden', 'idempotency_conflict', 'internal_error', 'invalid_cursor', 'not_found', 'pairing_failed', 'pairing_unavailable', 'payload_too_large', 'precondition_required', 'provider_input_changed', 'rate_limited', 'replay_result_changed', 'request_timeout', 'review_conflict', 'review_scan_limit', 'service_closed', 'stale_cursor', 'stale_revision', 'stale_schema', 'unauthorized', 'unsupported_contract', 'validation_error']
