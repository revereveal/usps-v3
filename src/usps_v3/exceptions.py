"""USPS v3 API exceptions."""

from __future__ import annotations


class USPSError(Exception):
    """Base exception for all USPS API errors."""

    def __init__(self, message: str, status_code: int | None = None, response_body: str | None = None):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)


class AuthError(USPSError):
    """OAuth or Payment Authorization failure."""


class ValidationError(USPSError):
    """Missing or invalid request parameters."""

    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message)


class RateLimitError(USPSError):
    """USPS returned 429 — rate limit exceeded (default: 60 req/hr)."""

    def __init__(self, message: str = "USPS rate limit exceeded (60 req/hr default)", retry_after: int | None = None):
        self.retry_after = retry_after
        super().__init__(message, status_code=429)


class APIError(USPSError):
    """USPS API returned a non-2xx response."""


class NetworkError(USPSError):
    """Connection, timeout, or DNS resolution failure."""
