"""``list_missions`` tool — discover open bounty missions (GET /api/missions)."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any, Mapping

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools._base import OabpToolBase, _opt_str
from tools.oabp_api import OabpError, mission_summary


class ListMissionsTool(Tool, OabpToolBase):
    def _invoke(
        self, tool_parameters: Mapping[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        status = _opt_str(tool_parameters.get("status"))
        limit = tool_parameters.get("limit")

        try:
            missions = self.client.list_missions(status=status)
        except OabpError as exc:
            payload = self.error_payload(exc)
            yield self.create_json_message(payload)
            yield self.create_text_message(f"OABP error: {payload['error']}")
            return

        if limit is not None:
            try:
                missions = missions[: int(limit)]
            except (TypeError, ValueError):
                pass

        summaries = [mission_summary(m) for m in missions]
        result = {"count": len(summaries), "missions": summaries}
        yield self.create_json_message(result)
        yield self.create_text_message(
            self._render(summaries)
            if summaries
            else "No missions matched."
        )

    @staticmethod
    def _render(summaries: list) -> str:
        lines = [f"{len(summaries)} mission(s):"]
        for m in summaries:
            reward = m["reward"]
            lines.append(
                f"- {m['id']}: {m.get('title') or '(untitled)'} "
                f"[{reward['amount']:g} {reward['currency']}, "
                f"{m.get('verification_type')}, {m.get('status')}]"
            )
        return "\n".join(lines)
