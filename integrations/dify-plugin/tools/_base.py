"""Shared base for the OABP / AIGEN Dify tools.

Each concrete tool is a tiny class that subclasses both :class:`dify_plugin.Tool`
and :class:`OabpToolBase`; the base provides ``self.client`` (built from the
runtime credentials) and ``error_message`` (turn an :class:`OabpError` into a
human-readable ``ToolInvokeMessage`` text payload). Keeping this in a mixin —
rather than the ``Tool`` subclass itself — lets the offline tests construct a
tool with a stubbed ``requests.Session`` without booting the full Dify runtime.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Mapping, Optional

import requests

# Make the sibling modules importable regardless of how Dify loads the plugin.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.oabp_api import OabpClient, OabpError  # noqa: E402


def _opt_str(value: Any) -> Optional[str]:
    """Normalise an optional string parameter: blank/whitespace -> None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _opt_float(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return float(value)


class OabpToolBase:
    """Mixin giving OABP tools a credential-built client + error formatting.

    ``self.runtime.credentials`` is populated by Dify. A ``_session_override``
    attribute (set only by the tests) lets the underlying HTTP transport be
    stubbed so the suite never hits the network.
    """

    _session_override: Optional[requests.Session] = None

    @property
    def credentials(self) -> Mapping[str, Any]:
        runtime = getattr(self, "runtime", None)
        creds = getattr(runtime, "credentials", None) if runtime is not None else None
        return creds or {}

    @property
    def client(self) -> OabpClient:
        return OabpClient.from_credentials(
            self.credentials, session=self._session_override
        )

    @staticmethod
    def error_payload(exc: OabpError) -> dict:
        """A structured, JSON-serialisable error an agent can read and react to."""
        payload = {"error": str(exc), "error_type": type(exc).__name__}
        if getattr(exc, "status_code", None) is not None:
            payload["status_code"] = exc.status_code
        return payload
