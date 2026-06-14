"""Typed exceptions for the OABP A2A client.

Callers can catch the broad :class:`OABPError` or narrow to a specific failure
mode (HTTP, JSON-RPC, signature verification, mission resolution).
"""

from __future__ import annotations

from typing import Any, Optional

__all__ = [
    "OABPError",
    "TransportError",
    "HTTPError",
    "JSONRPCError",
    "SignatureError",
    "MissionError",
]


class OABPError(Exception):
    """Base class for every error raised by this SDK."""


class TransportError(OABPError):
    """A network-level failure (connection refused, timeout, DNS, ...)."""


class HTTPError(OABPError):
    """A non-2xx HTTP response from the OABP server."""

    def __init__(self, status_code: int, url: str, body: Optional[str] = None):
        self.status_code = status_code
        self.url = url
        self.body = body
        snippet = ""
        if body:
            snippet = body if len(body) <= 300 else body[:297] + "..."
            snippet = f": {snippet}"
        super().__init__(f"HTTP {status_code} for {url}{snippet}")


class JSONRPCError(OABPError):
    """The A2A endpoint returned a JSON-RPC 2.0 error object."""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"JSON-RPC error {code}: {message}")


class SignatureError(OABPError):
    """The agent-card signature failed to verify against the JWKS."""


class MissionError(OABPError):
    """A mission operation could not be completed (bad params, not found, ...)."""
