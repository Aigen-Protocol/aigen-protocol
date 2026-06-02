"""Exception hierarchy for the OABP Python SDK.

All errors raised by :class:`oabp.client.OabpClient` derive from
:class:`OabpError`, so callers can catch a single base type::

    from oabp import OabpClient, OabpError

    try:
        client.get_mission("does-not-exist")
    except OabpError as exc:
        print(exc.status_code, exc)
"""

from __future__ import annotations

from typing import Any, Mapping, Optional


class OabpError(Exception):
    """Base class for every error raised by the SDK.

    Attributes
    ----------
    message:
        Human readable description.
    status_code:
        HTTP status code associated with the failure, when the error
        originates from an HTTP response. ``None`` for client-side errors
        (timeouts, connection errors, bad arguments...).
    response_body:
        Decoded JSON body of the error response, when available, otherwise
        the raw text. ``None`` when there was no response.
    request_url:
        The fully-qualified URL that produced the error, when known.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        response_body: Any = None,
        request_url: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        self.request_url = request_url

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        parts = [self.message]
        if self.status_code is not None:
            parts.append(f"(HTTP {self.status_code})")
        if self.request_url:
            parts.append(f"[{self.request_url}]")
        return " ".join(parts)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"{type(self).__name__}(message={self.message!r}, "
            f"status_code={self.status_code!r}, request_url={self.request_url!r})"
        )


class OabpTimeoutError(OabpError):
    """Raised when a request times out after exhausting retries."""


class OabpConnectionError(OabpError):
    """Raised when the SDK cannot reach the OABP server (DNS, TCP, TLS...)."""


class OabpHTTPError(OabpError):
    """Raised for non-2xx HTTP responses (4xx and un-retryable 5xx)."""


class OabpNotFoundError(OabpHTTPError):
    """Raised specifically for HTTP 404 (e.g. unknown mission id)."""


class OabpRateLimitError(OabpHTTPError):
    """Raised for HTTP 429 once retries are exhausted."""


class OabpServerError(OabpHTTPError):
    """Raised for 5xx responses once retries are exhausted."""


class OabpValidationError(OabpError):
    """Raised for invalid arguments before any network call is attempted."""


def error_for_status(
    status_code: int,
    *,
    message: str,
    response_body: Any = None,
    request_url: Optional[str] = None,
) -> OabpHTTPError:
    """Map an HTTP status code to the most specific SDK exception."""
    kwargs: Mapping[str, Any] = dict(
        status_code=status_code,
        response_body=response_body,
        request_url=request_url,
    )
    if status_code == 404:
        return OabpNotFoundError(message, **kwargs)
    if status_code == 429:
        return OabpRateLimitError(message, **kwargs)
    if 500 <= status_code < 600:
        return OabpServerError(message, **kwargs)
    return OabpHTTPError(message, **kwargs)
