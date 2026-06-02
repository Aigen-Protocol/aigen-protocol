"""``get_stats`` tool — marketplace-wide statistics (GET /api/stats)."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any, Mapping

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools._base import OabpToolBase
from tools.oabp_api import OabpError, stats_to_dict


class GetStatsTool(Tool, OabpToolBase):
    def _invoke(
        self, tool_parameters: Mapping[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        try:
            stats = self.client.get_stats()
        except OabpError as exc:
            payload = self.error_payload(exc)
            yield self.create_json_message(payload)
            yield self.create_text_message(f"OABP error: {payload['error']}")
            return

        result = stats_to_dict(stats)
        yield self.create_json_message(result)
        yield self.create_text_message(
            f"OABP marketplace: {result['resolved']} resolved, "
            f"{result['open']} open, "
            f"{result['lifetime_reward_aigen_paid']:g} AIGEN paid lifetime."
        )
