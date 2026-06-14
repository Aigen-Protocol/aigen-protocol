"""``get_mission`` tool — evaluate one mission (GET /api/missions/{id})."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any, Mapping

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools._base import OabpToolBase, _opt_str
from tools.oabp_api import OabpError, mission_detail


class GetMissionTool(Tool, OabpToolBase):
    def _invoke(
        self, tool_parameters: Mapping[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        mission_id = _opt_str(tool_parameters.get("mission_id"))
        if not mission_id:
            payload = {"error": "mission_id is required", "error_type": "ValidationError"}
            yield self.create_json_message(payload)
            yield self.create_text_message(payload["error"])
            return

        try:
            mission = self.client.get_mission(mission_id)
        except OabpError as exc:
            payload = self.error_payload(exc)
            yield self.create_json_message(payload)
            yield self.create_text_message(f"OABP error: {payload['error']}")
            return

        detail = mission_detail(mission)
        yield self.create_json_message(detail)
        yield self.create_text_message(self._render(detail))

    @staticmethod
    def _render(d: Mapping[str, Any]) -> str:
        reward = d["reward"]
        params = d.get("verification_params") or {}
        lines = [
            f"Mission {d['id']}: {d.get('title') or '(untitled)'}",
            f"  reward: {reward['amount']:g} {reward['currency']}",
            f"  verification: {d.get('verification_type')}",
        ]
        if params.get("regex"):
            lines.append(f"  regex: {params['regex']}")
        if params.get("oracle_description"):
            lines.append(f"  oracle: {params['oracle_description']}")
        lines.append(f"  status: {d.get('status')}  ({d['submission_count']} submission(s))")
        res = d.get("resolution")
        if res:
            lines.append(
                f"  resolved -> winner {res.get('winner_agent_id')}, "
                f"verified={res.get('verified')}, reward_paid={res.get('reward_paid')}"
            )
        return "\n".join(lines)
