"""Exception hierarchy for the OABP async SDK.

All errors raised by :class:`oabp_async.client.OABPClient` derive from
:class:`OABPError`, so callers can catch the whole family with a single
``except OABPError``.  HTTP-level failures additionally carry the offending
:class:`httpx.Response` (when one was received) so the caller can inspect the
status code, body and headers.
"""

from __future__ import annotations

from typing import Optional

import httpx

__all__ = [
    "OABPError",
    "OABPConfigError",
    "OABPTransportError",
    "OABPAPIError",
    "OABPNotFoundError",
    "OABPBadRequestError",
    "OABPRateLimitError",
    "OABPServerError",
    "OABPRPCError",
    "raise_for_response",
]


class OABPError(Exception):
    """Base class for every error raised by the SDK."""


class OABPConfigError(OABPError, ValueError):
    """Raised when the client is constructed or called with invalid arguments."""


class OABPTransportError(OABPError):
    """Raised when the request never produced an HTTP response.

    Wraps connect timeouts, DNS failures, read timeouts, connection resets,
    etc.  The originating ``httpx`` exception is available as ``__cause__``.
    """


class OABPAPIError(OABPError):
    """Raised for a non-2xx HTTP response from the OABP API.

    Attributes
    ----------
    status_code:
        The HTTP status code of the response.
    response:
        The raw :class:`httpx.Response`, for callers that need headers or the
        full body.
    payload:
        The decoded JSON body when the server returned JSON, else ``None``.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response: Optional[httpx.Response] = None,
        payload: object = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response
        self.payload = payload


class OABPBadRequestError(OABPAPIError):
    """HTTP 4xx other than 404/429 — typically a malformed mission or proof."""


class OABPNotFoundError(OABPAPIError):
    """HTTP 404 — the mission id (or endpoint) does not exist."""


class OABPRateLimitError(OABPAPIError):
    """HTTP 429 — the feed/poller is being throttled.

    ``retry_after`` is the parsed ``Retry-After`` header in seconds when the
    server supplied one, else ``None``.
    """

    def __init__(self, *args: object, retry_after: Optional[float] = None, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.retry_after = retry_after


class OABPServerError(OABPAPIError):
    """HTTP 5xx — the OABP node failed to process the request."""


class OABPRPCError(OABPError):
    """Raised when an A2A JSON-RPC call returns an ``error`` object.

    Mirrors the JSON-RPC 2.0 error shape.
    """

    def __init__(self, message: str, *, code: int, data: object = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


def _parse_retry_after(response: httpx.Response) -> Optional[float]:
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        # HTTP-date form is allowed by the spec but rare for this API; we do not
        # attempt to parse it and simply signal "unknown".
        return None


def raise_for_response(response: httpx.Response) -> None:
    """Raise the most specific :class:`OABPAPIError` subclass for ``response``.

    A no-op for 2xx responses.  The decoded JSON body (if any) is attached to
    the exception and, when the server provides a human-readable ``error`` or
    ``message`` field, it is used as the exception text.
    """
    if response.is_success:
        return

    payload: object = None
    detail: Optional[str] = None
    try:
        payload = response.json()
    except (ValueError, httpx.DecodingError):
        text = response.text.strip()
        detail = text[:300] if text else None
    else:
        if isinstance(payload, dict):
            for key in ("error", "message", "detail"):
                value = payload.get(key)
                if isinstance(value, str) and value:
                    detail = value
                    break

    status = response.status_code
    base = f"{response.request.method} {response.request.url} -> HTTP {status}"
    message = f"{base}: {detail}" if detail else base

    common = dict(status_code=status, response=response, payload=payload)
    if status == 404:
        raise OABPNotFoundError(message, **common)  # type: ignore[arg-type]
    if status == 429:
        raise OABPRateLimitError(
            message, retry_after=_parse_retry_after(response), **common  # type: ignore[arg-type]
        )
    if 400 <= status < 500:
        raise OABPBadRequestError(message, **common)  # type: ignore[arg-type]
    raise OABPServerError(message, **common)  # type: ignore[arg-type]
