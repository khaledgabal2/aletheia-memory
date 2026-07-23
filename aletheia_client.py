"""Compatibility import module for the Aletheia Python client SDK."""

from aletheia.client import (
    AletheiaClient,
    AletheiaClientError,
    AletheiaForbiddenError,
    AletheiaIntegrityGateError,
    AletheiaRateLimitError,
    AletheiaServerError,
    AletheiaUnauthorizedError,
    AletheiaValidationError,
    AsyncAletheiaClient,
)

__all__ = [
    "AletheiaClient",
    "AletheiaClientError",
    "AletheiaForbiddenError",
    "AletheiaIntegrityGateError",
    "AletheiaRateLimitError",
    "AletheiaServerError",
    "AletheiaUnauthorizedError",
    "AletheiaValidationError",
    "AsyncAletheiaClient",
]
