"""Aletheia exception types."""


class AletheiaError(Exception):
    """Base exception for Aletheia."""


class NotFoundError(AletheiaError):
    """Raised when a requested memory object does not exist."""


class ValidationError(AletheiaError):
    """Raised when input cannot be safely accepted."""

