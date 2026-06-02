"""``submit_mission`` tool — submit a deliverable (POST /missions/{id}/submit)."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any, Mapping

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools._base import OabpToolBase, _opt_str
from tools.oabp_api import OabpError


class SubmitMissionTool(Tool, OabpToolBase):
    def _invoke(
        self, tool_parameters: Mapping[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        mission_id = _opt_str(tool_parameters.get("mission_id"))
        proof = tool_parameters.get("proof")

        if not mission_id:
            yield from self._validation_error("mission_id is required")
            return
        if proof is None or str(proof) == "":
            yield from self._validation_error("proof must not be empty")
            return

        try:
            response = self.client.submit(
                mission_id,
                str(proof),
                submitter_agent_id=_opt_str(tool_parameters.get("submitter_agent_id")),
            )
        except OabpError as exc:
            payload = self.error_payload(exc)
            yield self.create_json_message(payload)
            yield self.create_text_message(f"OABP error: {payload['error']}")
            return

        result = {
            "submitted": True,
            "mission_id": mission_id,
            "response": response,
        }
        yield self.create_json_message(result)
        yield self.create_text_message(self._render(mission_id, response))

    def _validation_error(
        self, message: str
    ) -> Generator[ToolInvokeMessage, None, None]:
        payload = {"error": message, "error_type": "ValidationError"}
        yield self.create_json_message(payload)
        yield self.create_text_message(message)

    @staticmethod
    def _render(mission_id: str, response: Mapping[str, Any]) -> str:
        accepted = response.get("accepted")
        resolution = response.get("resolution") if isinstance(response, Mapping) else None
        head = f"Submitted to {mission_id}"
        if accepted is not None:
            head += f" (accepted={accepted})"
        if isinstance(resolution, Mapping):
            return (
                head
                + f"\n  resolution: winner {resolution.get('winner_agent_id')}, "
                f"verified={resolution.get('verified')}, "
                f"reward_paid={resolution.get('reward_paid')}"
            )
        return head + "."
