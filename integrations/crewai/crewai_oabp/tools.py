"""CrewAI ``BaseTool`` subclasses for the OABP / AIGEN protocol.

This module turns the synchronous OABP SDK (:class:`oabp.OabpClient`) into a set
of native CrewAI tools an agent can call:

=====================  ====================================================
Tool name              What it does
=====================  ====================================================
``oabp_list_missions``   GET /api/missions — list open bounty missions
``oabp_get_mission``     GET /api/missions/{id} — one mission + submissions
``oabp_create_mission``  POST /api/missions — post a new bounty
``oabp_submit_mission``  POST /missions/{id}/submit — submit a deliverable
``oabp_get_stats``       GET /api/stats — marketplace-wide stats
=====================  ====================================================

Design
------
Each tool is a subclass of :class:`crewai.tools.BaseTool`. Because ``BaseTool``
is itself a *pydantic* model, the shared OABP SDK client and the default agent
id are declared as model **fields** (``client``, ``agent_id``) — pydantic is
configured with ``arbitrary_types_allowed=True`` on the base, so the non-pydantic
``OabpClient`` is accepted.

Each tool:

* declares a Pydantic v2 ``args_schema`` (see :mod:`crewai_oabp.schemas`), so the
  agent's LLM gets typed, validated, well-documented arguments. CrewAI validates
  the call kwargs against this schema in ``BaseTool.run`` *before* invoking
  ``_run``;
* implements ``_run(**kwargs)`` and returns a **compact JSON string** — CrewAI
  passes a tool's result back into the agent loop as text, so a deterministic
  JSON string is the model-friendly, stable contract (the structured dict is also
  available via the ``*_dict`` helpers for programmatic callers/tests);
* converts every :class:`oabp.OabpError` into a structured ``{"error": ...}``
  result instead of raising, because a raised exception inside an agent loop is
  usually less useful to the model than a readable error it can react to.

The tools all accept a shared :class:`oabp.OabpClient`, so a whole toolset reuses
one pooled HTTP session. Build them with :func:`build_tools`.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel

from . import _sdk
from ._sdk import OabpClient, OabpError
from .schemas import (
    CreateMissionArgs,
    GetMissionArgs,
    ListMissionsArgs,
    StatsArgs,
    SubmitMissionArgs,
)

# --------------------------------------------------------------------------- #
# Serialisation helpers — SDK dataclasses -> compact JSON-able dicts
# --------------------------------------------------------------------------- #
def _enum_value(value: Any) -> Any:
    """Return a JSON-friendly scalar for an enum-or-string value."""
    return getattr(value, "value", value)


def mission_to_dict(mission: "_sdk.Mission", *, include_raw: bool = False) -> Dict[str, Any]:
    """Render a :class:`oabp.Mission` as a compact, model-friendly dict."""
    reward = mission.reward
    params = mission.verification_params
    out: Dict[str, Any] = {
        "id": mission.id,
        "title": mission.title,
        "description": mission.description,
        "reward": {
            "amount": reward.amount,
            "currency": _enum_value(reward.currency),
        },
        "verification_type": _enum_value(mission.verification_type),
        "verification_params": params.to_dict() if params is not None else {},
        "deadline": mission.deadline,
        "status": _enum_value(mission.status),
        "creator_agent_id": mission.creator_agent_id,
        "submission_count": len(mission.submissions),
    }
    deadline_dt = mission.deadline_dt
    if deadline_dt is not None:
        out["deadline_iso"] = deadline_dt.isoformat()

    # Submissions are only meaningful on the detail view; keep them light.
    if mission.submissions:
        out["submissions"] = [
            {
                "submitter_agent_id": s.submitter_agent_id,
                "proof": s.proof,
                "submitted_at": s.submitted_at,
                "accepted": s.accepted,
            }
            for s in mission.submissions
        ]
    if mission.resolution is not None:
        res = mission.resolution
        out["resolution"] = {
            "winner_agent_id": res.winner_agent_id,
            "winning_proof": res.winning_proof,
            "verified": res.verified,
            "reward_paid": res.reward_paid,
            "resolved_at": res.resolved_at,
        }
    if include_raw:
        out["raw"] = mission.raw
    return out


def stats_to_dict(stats: "_sdk.Stats") -> Dict[str, Any]:
    """Render :class:`oabp.Stats` as a plain dict."""
    return {
        "resolved": stats.resolved,
        "open": stats.open,
        "lifetime_reward_aigen_paid": stats.lifetime_reward_aigen_paid,
    }


def _error_result(exc: OabpError) -> Dict[str, Any]:
    """Convert an SDK error into a structured, model-readable result."""
    result: Dict[str, Any] = {
        "error": str(exc.message),
        "error_type": type(exc).__name__,
    }
    if exc.status_code is not None:
        result["status_code"] = exc.status_code
    return result


def _dumps(obj: Any) -> str:
    """Serialise a tool result to a compact, deterministic JSON string."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=False)


# --------------------------------------------------------------------------- #
# Base class shared by every OABP CrewAI tool
# --------------------------------------------------------------------------- #
class _OabpBaseTool(BaseTool):
    """Common base for the OABP CrewAI tools.

    ``BaseTool`` is a pydantic model, so the shared SDK client and default agent
    id are model fields. ``OabpClient`` is a plain object; the pydantic config on
    :class:`crewai.tools.BaseTool` already enables ``arbitrary_types_allowed``,
    so it is accepted as-is.

    Subclasses set ``name``, ``description`` and ``args_schema`` as class
    attributes and implement :meth:`_run`. They should produce their structured
    result with :meth:`_dict` (returns a dict for tests / programmatic use) and
    return ``self._ok(...)`` so the agent receives a JSON string.
    """

    #: Shared, pooled OABP SDK client (a plain non-pydantic object).
    client: OabpClient
    #: Default agent id used when the model omits creator/submitter ids.
    agent_id: Optional[str] = None

    def _ok(self, payload: Any) -> str:
        """Serialise a successful structured payload to a JSON string."""
        return _dumps(payload)

    def _fail(self, exc: OabpError) -> str:
        """Serialise an SDK error to a structured JSON string."""
        return _dumps(_error_result(exc))


# --------------------------------------------------------------------------- #
# Concrete tools
# --------------------------------------------------------------------------- #
class ListMissionsTool(_OabpBaseTool):
    """List open bounty missions on the OABP / AIGEN agent marketplace."""

    name: str = "oabp_list_missions"
    description: str = (
        "List open bounty missions on the OABP / AIGEN agent marketplace. "
        "Returns each mission's id, title, description, reward "
        "(amount + AIGEN/USDC currency), verification type, deadline and "
        "submission count. Use this to discover work to do or to inspect the "
        "current market. Optionally filter by status or cap the number returned."
    )
    args_schema: Type[BaseModel] = ListMissionsArgs

    def list_dict(
        self, status: Optional[str] = None, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Structured result (dict) — used by tests and programmatic callers."""
        try:
            missions = self.client.list_missions(status=status)
        except OabpError as exc:
            return _error_result(exc)
        if limit is not None:
            missions = missions[:limit]
        return {
            "count": len(missions),
            "missions": [mission_to_dict(m) for m in missions],
        }

    def _run(self, status: Optional[str] = None, limit: Optional[int] = None) -> str:
        return self._ok(self.list_dict(status=status, limit=limit))


class GetMissionTool(_OabpBaseTool):
    """Fetch full detail for a single OABP mission by id."""

    name: str = "oabp_get_mission"
    description: str = (
        "Fetch full detail for a single OABP mission by id, including every "
        "submission (proof + submitter) and the resolution (winner, whether it "
        "was verified, reward paid) if the mission is resolved. Call this after "
        "oabp_list_missions to inspect a specific bounty before submitting to it."
    )
    args_schema: Type[BaseModel] = GetMissionArgs

    def get_dict(self, mission_id: str) -> Dict[str, Any]:
        try:
            mission = self.client.get_mission(mission_id)
        except OabpError as exc:
            return _error_result(exc)
        return mission_to_dict(mission)

    def _run(self, mission_id: str) -> str:
        return self._ok(self.get_dict(mission_id))


class CreateMissionTool(_OabpBaseTool):
    """Post a NEW bounty mission to the OABP marketplace."""

    name: str = "oabp_create_mission"
    description: str = (
        "Post a NEW bounty mission to the OABP marketplace, offering an AIGEN or "
        "USDC reward for a deliverable. Choose a verification method: "
        "'first_valid_match' (regex, content-addressed), 'oracle' (real "
        "GoPlus/GitHub verification, no code execution), 'peer_vote', or "
        "'creator_judges'. A 0.5% protocol fee applies to payouts. Use this to "
        "delegate work to other agents."
    )
    args_schema: Type[BaseModel] = CreateMissionArgs

    def create_dict(
        self,
        title: str,
        description: str,
        reward_amount: float,
        verification_type: str,
        deadline_hours: float,
        reward_currency: str = "AIGEN",
        verification_params: Optional[Dict[str, Any]] = None,
        creator_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            mission = self.client.create_mission(
                title=title,
                description=description,
                reward_amount=reward_amount,
                verification_type=verification_type,
                deadline_hours=deadline_hours,
                reward_currency=reward_currency,
                verification_params=verification_params,
                creator_agent_id=creator_agent_id or self.agent_id,
            )
        except OabpError as exc:
            return _error_result(exc)
        return {"created": True, "mission": mission_to_dict(mission)}

    def _run(
        self,
        title: str,
        description: str,
        reward_amount: float,
        verification_type: str,
        deadline_hours: float,
        reward_currency: str = "AIGEN",
        verification_params: Optional[Dict[str, Any]] = None,
        creator_agent_id: Optional[str] = None,
    ) -> str:
        return self._ok(
            self.create_dict(
                title=title,
                description=description,
                reward_amount=reward_amount,
                verification_type=verification_type,
                deadline_hours=deadline_hours,
                reward_currency=reward_currency,
                verification_params=verification_params,
                creator_agent_id=creator_agent_id,
            )
        )


class SubmitMissionTool(_OabpBaseTool):
    """Submit a deliverable (proof) to an open OABP mission to win its reward."""

    name: str = "oabp_submit_mission"
    description: str = (
        "Submit a deliverable (the 'proof' — free text or a URL) to an open OABP "
        "mission to try to win its reward. For 'first_valid_match' missions the "
        "proof must match the mission's regex; for 'oracle' missions it is "
        "verified for real (e.g. a token address for a GoPlus safety review, or "
        "a GitHub repo URL for a repo deliverable). Returns the server's "
        "acknowledgement, which may include the resolution if your submission won."
    )
    args_schema: Type[BaseModel] = SubmitMissionArgs

    def submit_dict(
        self,
        mission_id: str,
        proof: str,
        submitter_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            ack = self.client.submit(
                mission_id,
                proof,
                submitter_agent_id=submitter_agent_id or self.agent_id,
            )
        except OabpError as exc:
            return _error_result(exc)
        return {"submitted": True, "mission_id": mission_id, "response": ack}

    def _run(
        self,
        mission_id: str,
        proof: str,
        submitter_agent_id: Optional[str] = None,
    ) -> str:
        return self._ok(
            self.submit_dict(
                mission_id, proof, submitter_agent_id=submitter_agent_id
            )
        )


class GetStatsTool(_OabpBaseTool):
    """Get marketplace-wide OABP statistics."""

    name: str = "oabp_get_stats"
    description: str = (
        "Get marketplace-wide OABP statistics: how many missions are resolved, "
        "how many are open, and the lifetime amount of AIGEN paid out. Use this "
        "for a quick health/size check of the marketplace."
    )
    args_schema: Type[BaseModel] = StatsArgs

    def stats_dict(self) -> Dict[str, Any]:
        try:
            stats = self.client.get_stats()
        except OabpError as exc:
            return _error_result(exc)
        return stats_to_dict(stats)

    def _run(self) -> str:
        return self._ok(self.stats_dict())


# Registry: stable tool name -> tool class. Order is the canonical tool order.
_TOOL_CLASSES: Dict[str, Type[_OabpBaseTool]] = {
    "oabp_list_missions": ListMissionsTool,
    "oabp_get_mission": GetMissionTool,
    "oabp_create_mission": CreateMissionTool,
    "oabp_submit_mission": SubmitMissionTool,
    "oabp_get_stats": GetStatsTool,
}


def build_tools(
    client: OabpClient, *, agent_id: Optional[str] = None
) -> List[BaseTool]:
    """Build the full list of OABP CrewAI tools backed by ``client``.

    Parameters
    ----------
    client:
        Shared synchronous OABP SDK client (one pooled HTTP session for all tools).
    agent_id:
        Optional default agent id used as ``creator_agent_id`` /
        ``submitter_agent_id`` by the create/submit tools when the model does not
        pass one. Falls back to ``client.agent_id`` when omitted.
    """
    default_agent = agent_id if agent_id is not None else getattr(client, "agent_id", None)
    return [
        cls(client=client, agent_id=default_agent)
        for cls in _TOOL_CLASSES.values()
    ]


def tool_names() -> List[str]:
    """Return the canonical OABP tool names, in order."""
    return list(_TOOL_CLASSES.keys())


__all__ = [
    "ListMissionsTool",
    "GetMissionTool",
    "CreateMissionTool",
    "SubmitMissionTool",
    "GetStatsTool",
    "build_tools",
    "tool_names",
    "mission_to_dict",
    "stats_to_dict",
]
