"""Serialisation helpers: OABP SDK dataclasses -> compact JSON **strings**.

Semantic Kernel native functions hand their result back to the model as text, and
the most robust, framework-agnostic shape is a JSON **string**. So every
:class:`sk_oabp.OabpPlugin` method returns a ``str`` produced by :func:`to_json`
over a plain dict trimmed to the fields a model actually needs — never a
dataclass, never an Enum.

These helpers do that mapping and are shared by all the methods in
:mod:`sk_oabp.plugin`. Errors are likewise returned as a JSON string carrying a
structured ``{"error": ...}`` object (see :func:`error_to_json`) rather than
raised, because a raised exception aborts the kernel's function call whereas a
readable JSON error is something the model can parse and react to.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from ._sdk import OabpError


def enum_value(value: Any) -> Any:
    """Return a JSON-friendly scalar for an enum-or-string value."""
    return getattr(value, "value", value)


def to_json(obj: Any) -> str:
    """Serialise ``obj`` to a compact, stable JSON string.

    Uses ``ensure_ascii=False`` so token addresses / unicode survive intact, and
    ``sort_keys=False`` to preserve the insertion order the dict-builders use.
    """
    return json.dumps(obj, ensure_ascii=False, default=str)


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


def error_to_json(exc: OabpError) -> str:
    """Convert an SDK error into a structured, model-readable **JSON string**.

    Semantic Kernel surfaces a function's return value to the model as text, so
    instead of raising (which aborts the function call) we return a JSON object
    of the shape ``{"error": {"type", "message", "status_code"}}`` the model can
    parse and react to (retry, pick another mission, ask for input...).
    """
    err: Dict[str, Any] = {
        "type": type(exc).__name__,
        "message": getattr(exc, "message", str(exc)),
    }
    status = getattr(exc, "status_code", None)
    if status is not None:
        err["status_code"] = status
    return to_json({"error": err})


def validation_error_json(message: str) -> str:
    """A JSON error object for a client-side validation failure (no network)."""
    return to_json({"error": {"type": "OabpValidationError", "message": message}})


__all__ = [
    "enum_value",
    "to_json",
    "mission_to_dict",
    "stats_to_dict",
    "reputation_to_dict",
    "error_to_json",
    "validation_error_json",
]
