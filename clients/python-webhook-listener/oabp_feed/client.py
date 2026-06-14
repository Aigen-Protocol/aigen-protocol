"""HTTP fetcher for the missions feed (stdlib ``urllib`` only).

:class:`FeedClient` performs *conditional* GETs against the feed URL. It
remembers the ``ETag`` / ``Last-Modified`` returned by the server and sends
them back as ``If-None-Match`` / ``If-Modified-Since`` on the next poll, so an
unchanged feed costs a cheap ``304 Not Modified`` instead of a full transfer.

This module deliberately knows nothing about parsing or dedup -- it only turns
"go fetch the feed" into a :class:`HttpResult`. That separation keeps it
trivially swappable (e.g. for tests, or to route through an MCP/A2A proxy).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import urllib.error
import urllib.request

__all__ = ["FeedClient", "HttpResult", "FeedHttpError"]


class FeedHttpError(Exception):
    """Raised on a non-retryable-from-here HTTP/network failure.

    ``status`` is the HTTP status code when available (e.g. 500), else ``None``
    for transport errors (DNS, refused connection, timeout).
    """

    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


@dataclass
class HttpResult:
    """Outcome of one conditional fetch.

    * ``not_modified=True``  -> server returned 304; ``body`` is ``None``.
    * ``not_modified=False`` -> ``body`` holds the fresh feed bytes.
    """

    not_modified: bool
    body: Optional[bytes]
    status: int
    etag: Optional[str] = None
    last_modified: Optional[str] = None


class FeedClient:
    """Minimal conditional-GET client for a single feed URL."""

    def __init__(
        self,
        url: str,
        *,
        timeout: float = 15.0,
        user_agent: str = "oabp-feed-listener/1.0 (+https://cryptogenesis.duckdns.org)",
        extra_headers: Optional[dict] = None,
    ):
        self.url = url
        self.timeout = timeout
        self.user_agent = user_agent
        self.extra_headers = dict(extra_headers or {})
        self._etag: Optional[str] = None
        self._last_modified: Optional[str] = None

    # Allow seeding/restoring cache validators (e.g. after a restart).
    @property
    def etag(self) -> Optional[str]:
        return self._etag

    @etag.setter
    def etag(self, value: Optional[str]) -> None:
        self._etag = value

    @property
    def last_modified(self) -> Optional[str]:
        return self._last_modified

    @last_modified.setter
    def last_modified(self, value: Optional[str]) -> None:
        self._last_modified = value

    def fetch(self) -> HttpResult:
        """Perform one conditional GET. Updates stored ETag/Last-Modified.

        :raises FeedHttpError: on 4xx/5xx (other than 304) or transport errors.
        """
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
        }
        headers.update(self.extra_headers)
        if self._etag:
            headers["If-None-Match"] = self._etag
        if self._last_modified:
            headers["If-Modified-Since"] = self._last_modified

        req = urllib.request.Request(self.url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.getcode()
                body = resp.read()
                etag = resp.headers.get("ETag")
                last_mod = resp.headers.get("Last-Modified")
                if etag:
                    self._etag = etag
                if last_mod:
                    self._last_modified = last_mod
                return HttpResult(
                    not_modified=False,
                    body=body,
                    status=status,
                    etag=self._etag,
                    last_modified=self._last_modified,
                )
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                # Not modified: keep validators, no body to parse.
                return HttpResult(
                    not_modified=True,
                    body=None,
                    status=304,
                    etag=self._etag,
                    last_modified=self._last_modified,
                )
            raise FeedHttpError(
                f"feed fetch failed: HTTP {exc.code} {exc.reason}", status=exc.code
            ) from exc
        except urllib.error.URLError as exc:
            raise FeedHttpError(f"feed fetch failed: {exc.reason}") from exc
        except (TimeoutError, OSError) as exc:  # pragma: no cover - env dependent
            raise FeedHttpError(f"feed fetch failed: {exc}") from exc
