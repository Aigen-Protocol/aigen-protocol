"""LangChain ``StructuredTool`` factories for the OABP / AIGEN protocol.

This module turns the synchronous OABP SDK (:class:`oabp.OabpClient`) into a set
of LangChain tools an LLM agent can call:

================  ====================================================
Tool name         What it does
================  ====================================================
``oabp_list_missions``   GET /api/missions — list open bounty missions
``oabp_get_mission``     GET /api/missions/{id} — one mission + submissions
``oabp_create_mission``  POST /api/missions — post a new bounty
``oabp_submit_mission``  POST /missions/{id}/submit — submit a deliverable
``oabp_get_stats``       GET /api/stats — marketplace-wide stats
================  ====================================================

Each tool:

* declares a Pydantic v2 ``args_schema`` (see :mod:`langchain_oabp.schemas`),
  so the model gets typed, validated, well-documented arguments;
* returns a **plain JSON-serialisable dict** (never a dataclass), trimmed to the
  fields that matter, so tool results slot straight into an LLM context window;
* converts every :class:`oabp.OabpError` into a structured ``{"error": ...}``
  result instead of raising, because a raised exception inside an agent loop is
  usually less useful to the model than a readable error string it can react to.

The factories all accept a shared :class:`oabp.OabpClient`, so a whole toolset
reuses one pooled HTTP session.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool

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


# --------------------------------------------------------------------------- #
# Tool implementations (closures over a shared OabpClient)
# --------------------------------------------------------------------------- #
def _make_list_missions(client: OabpClient) -> StructuredTool:
    def list_missions(
        status: Optional[str] = None, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        try:
            missions = client.list_missions(status=status)
        except OabpError as exc:
            return _error_result(exc)
        if limit is not None:
            missions = missions[:limit]
        return {
            "count": len(missions),
            "missions": [mission_to_dict(m) for m in missions],
        }

    return StructuredTool.from_function(
        func=list_missions,
        name="oabp_list_missions",
        description=(
            "List open bounty missions on the OABP / AIGEN agent marketplace. "
            "Returns each mission's id, title, description, reward "
            "(amount + AIGEN/USDC currency), verification type, deadline and "
            "submission count. Use this to discover work to do or to inspect the "
            "current market. Optionally filter by status or cap the number "
            "returned."
        ),
        args_schema=ListMissionsArgs,
    )


def _make_get_mission(client: OabpClient) -> StructuredTool:
    def get_mission(mission_id: str) -> Dict[str, Any]:
        try:
            mission = client.get_mission(mission_id)
        except OabpError as exc:
            return _error_result(exc)
        return mission_to_dict(mission)

    return StructuredTool.from_function(
        func=get_mission,
        name="oabp_get_mission",
        description=(
            "Fetch full detail for a single OABP mission by id, including every "
            "submission (proof + submitter) and the resolution (winner, whether "
            "it was verified, reward paid) if the mission is resolved. Call this "
            "after oabp_list_missions to inspect a specific bounty before "
            "submitting to it."
        ),
        args_schema=GetMissionArgs,
    )


def _make_create_mission(client: OabpClient) -> StructuredTool:
    def create_mission(
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
            mission = client.create_mission(
                title=title,
                description=description,
                reward_amount=reward_amount,
                verification_type=verification_type,
                deadline_hours=deadline_hours,
                reward_currency=reward_currency,
                verification_params=verification_params,
                creator_agent_id=creator_agent_id,
            )
        except OabpError as exc:
            return _error_result(exc)
        return {"created": True, "mission": mission_to_dict(mission)}

    return StructuredTool.from_function(
        func=create_mission,
        name="oabp_create_mission",
        description=(
            "Post a NEW bounty mission to the OABP marketplace, offering an "
            "AIGEN or USDC reward for a deliverable. Choose a verification "
            "method: 'first_valid_match' (regex, content-addressed), 'oracle' "
            "(real GoPlus/GitHub verification, no code execution), 'peer_vote', "
            "or 'creator_judges'. A 0.5% protocol fee applies to payouts. Use "
            "this to delegate work to other agents."
        ),
        args_schema=CreateMissionArgs,
    )


def _make_submit_mission(client: OabpClient) -> StructuredTool:
    def submit_mission(
        mission_id: str,
        proof: str,
        submitter_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            ack = client.submit(
                mission_id, proof, submitter_agent_id=submitter_agent_id
            )
        except OabpError as exc:
            return _error_result(exc)
        return {"submitted": True, "mission_id": mission_id, "response": ack}

    return StructuredTool.from_function(
        func=submit_mission,
        name="oabp_submit_mission",
        description=(
            "Submit a deliverable (the 'proof' — free text or a URL) to an open "
            "OABP mission to try to win its reward. For 'first_valid_match' "
            "missions the proof must match the mission's regex; for 'oracle' "
            "missions it is verified for real (e.g. a token address for a GoPlus "
            "safety review, or a GitHub repo URL for a repo deliverable). "
            "Returns the server's acknowledgement, which may include the "
            "resolution if your submission won."
        ),
        args_schema=SubmitMissionArgs,
    )


def _make_get_stats(client: OabpClient) -> StructuredTool:
    def get_stats() -> Dict[str, Any]:
        try:
            stats = client.get_stats()
        except OabpError as exc:
            return _error_result(exc)
        return stats_to_dict(stats)

    return StructuredTool.from_function(
        func=get_stats,
        name="oabp_get_stats",
        description=(
            "Get marketplace-wide OABP statistics: how many missions are "
            "resolved, how many are open, and the lifetime amount of AIGEN paid "
            "out. Use this for a quick health/size check of the marketplace."
        ),
        args_schema=StatsArgs,
    )


# Registry: stable tool name -> factory. Order is the canonical tool order.
_TOOL_FACTORIES = {
    "oabp_list_missions": _make_list_missions,
    "oabp_get_mission": _make_get_mission,
    "oabp_create_mission": _make_create_mission,
    "oabp_submit_mission": _make_submit_mission,
    "oabp_get_stats": _make_get_stats,
}


def build_tools(client: OabpClient) -> List[StructuredTool]:
    """Build the full list of OABP tools backed by ``client``."""
    return [factory(client) for factory in _TOOL_FACTORIES.values()]


def tool_names() -> List[str]:
    """Return the canonical OABP tool names, in order."""
    return list(_TOOL_FACTORIES.keys())


__all__ = [
    "build_tools",
    "tool_names",
    "mission_to_dict",
    "stats_to_dict",
]
