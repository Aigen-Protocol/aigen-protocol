"""OABP / AIGEN tool provider for Dify.

``OabpProvider._validate_credentials`` is called by Dify when a user adds or
edits the provider's credentials. It confirms the base URL is present and that
the configured OABP deployment answers ``GET /api/stats`` (optionally with the
supplied bearer token), so a misconfigured URL or a dead node is caught at
configuration time instead of on the first tool call.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Mapping

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

# Make the sibling ``tools`` package importable whether the plugin is loaded as
# a package or its directory is on sys.path (also keeps the offline tests simple).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.oabp_api import OabpClient, OabpError  # noqa: E402


class OabpProvider(ToolProvider):
    """Credential gate for the OABP / AIGEN tools."""

    def _validate_credentials(self, credentials: Mapping[str, Any]) -> None:
        base_url = (credentials or {}).get("oabp_base_url")
        if not base_url or not str(base_url).strip():
            raise ToolProviderCredentialValidationError(
                "oabp_base_url is required (e.g. https://cryptogenesis.duckdns.org)."
            )
        if not str(base_url).startswith(("http://", "https://")):
            raise ToolProviderCredentialValidationError(
                "oabp_base_url must start with http:// or https://."
            )

        client = OabpClient.from_credentials(credentials)
        try:
            # A cheap, always-available read that also exercises the bearer token.
            client.get_stats()
        except OabpError as exc:
            if exc.status_code in (401, 403):
                raise ToolProviderCredentialValidationError(
                    "OABP rejected the credentials (HTTP "
                    f"{exc.status_code}): check the API key."
                ) from exc
            raise ToolProviderCredentialValidationError(
                f"Could not reach the OABP deployment at {base_url}: {exc}"
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive catch-all
            raise ToolProviderCredentialValidationError(str(exc)) from exc
