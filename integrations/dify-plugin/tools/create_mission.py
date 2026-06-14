"""``create_mission`` tool — post a new bounty (POST /api/missions)."""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any, Dict, Mapping, Optional

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools._base import OabpToolBase, _opt_float, _opt_str
from tools.oabp_api import (
    CURRENCIES,
    VERIFICATION_TYPES,
    OabpError,
    mission_summary,
)


def _parse_params(value: Any) -> Optional[Dict[str, Any]]:
    """Accept verification_params as a dict or a JSON string; '' -> None."""
    if value is None:
        return None
    if isinstance(value, Mapping):
        return dict(value)
    text = str(value).strip()
    if not text:
        return None
    parsed = json.loads(text)  # raises ValueError on bad JSON
    if not isinstance(parsed, Mapping):
        raise ValueError("verification_params must be a JSON object")
    return dict(parsed)


class CreateMissionTool(Tool, OabpToolBase):
    def _invoke(
        self, tool_parameters: Mapping[str, Any]
    ) -> Generator[ToolInvokeMessage, None, None]:
        # ---- local validation (return structured errors, never raise) ----
        error = self._validate(tool_parameters)
        if error is not None:
            payload = {"error": error, "error_type": "ValidationError"}
            yield self.create_json_message(payload)
            yield self.create_text_message(error)
            return

        try:
            params = _parse_params(tool_parameters.get("verification_params"))
        except ValueError as exc:
            payload = {
                "error": f"verification_params is not valid JSON: {exc}",
                "error_type": "ValidationError",
            }
            yield self.create_json_message(payload)
            yield self.create_text_message(payload["error"])
            return

        try:
            mission = self.client.create_mission(
                title=str(tool_parameters["title"]),
                description=str(tool_parameters.get("description") or ""),
                reward_amount=float(tool_parameters["reward_amount"]),
                verification_type=str(tool_parameters["verification_type"]),
                deadline_hours=float(tool_parameters["deadline_hours"]),
                reward_currency=str(tool_parameters.get("reward_currency") or "AIGEN"),
                verification_params=params,
                creator_agent_id=_opt_str(tool_parameters.get("creator_agent_id")),
            )
        except OabpError as exc:
            payload = self.error_payload(exc)
            yield self.create_json_message(payload)
            yield self.create_text_message(f"OABP error: {payload['error']}")
            return

        summary = mission_summary(mission)
        result = {"created": True, "mission": summary}
        yield self.create_json_message(result)
        reward = summary["reward"]
        yield self.create_text_message(
            f"Created mission {summary['id']}: {summary.get('title')} "
            f"({reward['amount']:g} {reward['currency']}, "
            f"{summary.get('verification_type')})."
        )

    @staticmethod
    def _validate(p: Mapping[str, Any]) -> Optional[str]:
        if not _opt_str(p.get("title")):
            return "title must not be empty"
        vt = _opt_str(p.get("verification_type"))
        if vt not in VERIFICATION_TYPES:
            return (
                "verification_type must be one of "
                + ", ".join(VERIFICATION_TYPES)
                + f" (got {vt!r})"
            )
        currency = _opt_str(p.get("reward_currency")) or "AIGEN"
        if currency not in CURRENCIES:
            return "reward_currency must be one of " + ", ".join(CURRENCIES)
        try:
            reward = _opt_float(p.get("reward_amount"))
        except (TypeError, ValueError):
            return "reward_amount must be a number"
        if reward is None or reward <= 0:
            return "reward_amount must be a positive number"
        try:
            deadline = _opt_float(p.get("deadline_hours"))
        except (TypeError, ValueError):
            return "deadline_hours must be a number"
        if deadline is None or deadline <= 0:
            return "deadline_hours must be a positive number"
        return None
