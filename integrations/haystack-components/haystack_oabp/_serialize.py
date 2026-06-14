"""Serialisation helpers: OABP SDK dataclasses -> compact JSON-able dicts.

The Haystack OABP components return **plain, JSON-serialisable dicts** (never a
dataclass, never an Enum) from ``run`` so their outputs slot straight into a
prompt/agent context and survive Haystack's pipeline serialisation. These helpers
do that mapping and are shared by every component in :mod:`haystack_oabp.components`.

Errors are likewise turned into a structured ``{"error": ...}`` **dict** rather
than raised: inside an agent/``ToolInvoker`` loop a readable error the model can
react to (retry, pick another mission, ask the user for input) is more useful than
an exception that aborts the whole tool call.
"""

from __future__ import annotations

from typing import Any, Dict

from ._sdk import OabpError


def enum_value(value: Any) -> Any:
    """Return a JSON-friendly scalar for an enum-or-string value."""
    return getattr(value, "value", value)


def mission_to_dict(mission: Any, *, include_raw: bool = False) -> Dict[str, Any]:
    """Render a :class:`oabp.Mission` as a compact, model-friendly dict.

    Only the model-relevant fields are kept. Submissions and resolution are
    included only when present (i.e. on the detail view), to keep list results
    small enough for a context window.
    """
    reward = mission.reward
    params = mission.verification_params
    out: Dict[str, Any] = {
        "id": mission.id,
        "title": mission.title,
        "description": mission.description,
        "reward": {
            "amount": reward.amount,
            "currency": enum_value(reward.currency),
        },
        "verification_type": enum_value(mission.verification_type),
        "verification_params": params.to_dict() if params is not None else {},
        "deadline": mission.deadline,
        "status": enum_value(mission.status),
        "creator_agent_id": mission.creator_agent_id,
        "submission_count": len(mission.submissions),
    }
    deadline_dt = mission.deadline_dt
    if deadline_dt is not None:
        out["deadline_iso"] = deadline_dt.isoformat()

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


def stats_to_dict(stats: Any) -> Dict[str, Any]:
    """Render :class:`oabp.Stats` as a plain dict."""
    return {
        "resolved": stats.resolved,
        "open": stats.open,
        "lifetime_reward_aigen_paid": stats.lifetime_reward_aigen_paid,
    }


def reputation_to_dict(rep: Any) -> Dict[str, Any]:
    """Render :class:`oabp.Reputation` as a plain dict."""
    return {
        "agent_id": rep.agent_id,
        "aigen_balance": rep.aigen_balance,
        "missions_won": rep.missions_won,
        "missions_created": rep.missions_created,
        "submissions": rep.submissions,
    }


def error_to_dict(exc: OabpError) -> Dict[str, Any]:
    """Convert an SDK error into a structured, model-readable ``{"error": ...}``.

    Returning a dict with an ``error`` key (rather than raising) lets a model /
    ``ToolInvoker`` read the failure and adapt instead of having the run aborted.
    """
    result: Dict[str, Any] = {
        "error": str(exc.message),
        "error_type": type(exc).__name__,
    }
    if getattr(exc, "status_code", None) is not None:
        result["status_code"] = exc.status_code
    return result


__all__ = [
    "enum_value",
    "mission_to_dict",
    "stats_to_dict",
    "reputation_to_dict",
    "error_to_dict",
]
