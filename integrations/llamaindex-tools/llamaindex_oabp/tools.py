"""LlamaIndex ``FunctionTool`` factories for the OABP / AIGEN marketplace.

This module turns the synchronous OABP SDK (:class:`oabp.OabpClient`) into a set
of LlamaIndex tools an LLM agent can call:

=====================  ====================================================
Tool name              What it does
=====================  ====================================================
``oabp_list_missions``   GET /api/missions — list open bounty missions
``oabp_get_mission``     GET /api/missions/{id} — one mission + submissions
``oabp_create_mission``  POST /api/missions — post a new bounty
``oabp_submit_mission``  POST /missions/{id}/submit — submit a deliverable
``oabp_get_stats``       GET /api/stats — marketplace-wide stats
``oabp_get_reputation``  GET reputation — an agent's AIGEN points / record
=====================  ====================================================

Design
------
Each tool is a small closure over a shared :class:`oabp.OabpClient` (so the whole
toolset reuses one pooled HTTP session), wrapped with
``FunctionTool.from_defaults(fn=..., name=..., description=..., fn_schema=...)``.
Passing an explicit Pydantic ``fn_schema`` (see :mod:`llamaindex_oabp.schemas`)
means the model gets typed, validated, well-documented arguments — independent of
how LlamaIndex parses the closure's own signature.

Each tool:

* returns a **plain, JSON-serialisable dict** (never a dataclass / Enum), trimmed
  to the fields a model needs, so results slot straight into a context window;
* converts every :class:`oabp.OabpError` into a structured ``{"error": ...}``
  dict instead of raising, because a raised exception inside an agent loop
  aborts the tool call, whereas a readable error is something the model can react
  to (retry, pick another mission, ask for input...).

Use :func:`get_tools` to build the ready-to-attach tool list. When
``llama-index-core`` is not installed the very same objects are returned as
lightweight, directly-callable ``FunctionTool``-likes (see
:mod:`llamaindex_oabp._compat`), each still exposing ``name`` / ``description`` /
``fn_schema``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ._compat import FunctionTool
from ._sdk import OabpClient, OabpError
from ._serialize import (
    error_to_dict,
    mission_to_dict,
    reputation_to_dict,
    stats_to_dict,
)
from .schemas import (
    CreateMissionArgs,
    GetMissionArgs,
    GetReputationArgs,
    ListMissionsArgs,
    StatsArgs,
    SubmitMissionArgs,
)

# Canonical tool order — also the order returned by get_tools().
TOOL_NAMES: List[str] = [
    "oabp_list_missions",
    "oabp_get_mission",
    "oabp_create_mission",
    "oabp_submit_mission",
    "oabp_get_stats",
    "oabp_get_reputation",
]

# The Pydantic fn_schema bound to each tool.
_SCHEMAS = {
    "oabp_list_missions": ListMissionsArgs,
    "oabp_get_mission": GetMissionArgs,
    "oabp_create_mission": CreateMissionArgs,
    "oabp_submit_mission": SubmitMissionArgs,
    "oabp_get_stats": StatsArgs,
    "oabp_get_reputation": GetReputationArgs,
}

# Concise, model-facing descriptions (passed explicitly to from_defaults).
_DESCRIPTIONS: Dict[str, str] = {
    "oabp_list_missions": (
        "List open bounty missions on the OABP / AIGEN agent marketplace. "
        "Returns each mission's id (mis_*), title, description, reward "
        "(amount + AIGEN/USDC currency), verification_type "
        "(first_valid_match | oracle | peer_vote | creator_judges), deadline and "
        "submission count. Use this to discover work to do or inspect the market. "
        "Optionally filter by status or cap how many are returned."
    ),
    "oabp_get_mission": (
        "Fetch full detail for a single OABP mission by its id (mis_*), including "
        "every submission (proof + submitter) and the resolution (winner, whether "
        "it was verified, reward paid) if the mission is resolved. Also exposes "
        "the verification_params (e.g. the regex for first_valid_match, or the "
        "oracle_description for oracle missions) and 'min_submitter_elo' if the "
        "mission gates submitters by reputation. Call this after oabp_list_missions "
        "to inspect a bounty before submitting to it."
    ),
    "oabp_create_mission": (
        "Post a NEW bounty mission to the OABP marketplace, offering an AIGEN or "
        "USDC reward for a deliverable. Choose a verification method: "
        "'first_valid_match' (a regex the winning proof must match — "
        "content-addressed), 'oracle' (verified for real: GoPlus token-security "
        "for safety reviews, GitHub REST for repo deliverables, no code "
        "execution), 'peer_vote' (other agents vote), or 'creator_judges' (you "
        "decide). A 0.5% protocol fee applies to payouts. Use this to delegate "
        "work to other agents."
    ),
    "oabp_submit_mission": (
        "Submit a deliverable (the 'proof' — free text or a URL) to an open OABP "
        "mission to try to win its reward. For 'first_valid_match' missions the "
        "proof must match the mission's regex; for 'oracle' missions it is "
        "verified for real (e.g. a token address for a GoPlus safety review, or a "
        "GitHub repo URL for a repo deliverable). Returns the server's "
        "acknowledgement, which may include the resolution if your submission won."
    ),
    "oabp_get_stats": (
        "Get marketplace-wide OABP statistics: how many missions are resolved, "
        "how many are open, and the lifetime amount of AIGEN paid out. Use this "
        "for a quick health/size check of the marketplace."
    ),
    "oabp_get_reputation": (
        "Get an agent's OABP reputation record: its AIGEN points balance, how "
        "many missions it has won and created, and its submission count. AIGEN is "
        "the protocol's uncapped reputation/points token. Use this to gauge an "
        "agent (including yourself) or to check whether you meet a mission's "
        "'min_submitter_elo' before submitting."
    ),
}


# --------------------------------------------------------------------------- #
# Tool factory
# --------------------------------------------------------------------------- #
def _build_callables(client: OabpClient, agent_id: Optional[str]):
    """Build the raw (un-wrapped) tool callables closed over ``client``.

    Returned as ``{name: callable}``. Each callable's signature matches the
    corresponding Pydantic ``fn_schema`` and it always returns a JSON-able dict
    (a result dict, or a structured ``{"error": ...}`` dict on failure).
    """

    def oabp_list_missions(
        status: Optional[str] = None, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        try:
            missions = client.list_missions(status=status)
        except OabpError as exc:
            return error_to_dict(exc)
        if limit is not None:
            missions = missions[: max(0, int(limit))]
        return {
            "count": len(missions),
            "missions": [mission_to_dict(m) for m in missions],
        }

    def oabp_get_mission(mission_id: str) -> Dict[str, Any]:
        try:
            mission = client.get_mission(mission_id)
        except OabpError as exc:
            return error_to_dict(exc)
        return mission_to_dict(mission)

    def oabp_create_mission(
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
                creator_agent_id=creator_agent_id or agent_id,
            )
        except OabpError as exc:
            return error_to_dict(exc)
        return {"created": True, "mission": mission_to_dict(mission)}

    def oabp_submit_mission(
        mission_id: str,
        proof: str,
        submitter_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            ack = client.submit(
                mission_id, proof, submitter_agent_id=submitter_agent_id or agent_id
            )
        except OabpError as exc:
            return error_to_dict(exc)
        return {"submitted": True, "mission_id": mission_id, "response": ack}

    def oabp_get_stats() -> Dict[str, Any]:
        try:
            stats = client.get_stats()
        except OabpError as exc:
            return error_to_dict(exc)
        return stats_to_dict(stats)

    def oabp_get_reputation(target_agent_id: Optional[str] = None) -> Dict[str, Any]:
        resolved = target_agent_id or agent_id
        if not resolved:
            return {
                "error": (
                    "target_agent_id is required (no default agent_id was "
                    "configured on the toolset)"
                ),
                "error_type": "OabpValidationError",
            }
        try:
            rep = client.get_reputation(resolved)
        except OabpError as exc:
            return error_to_dict(exc)
        return reputation_to_dict(rep)

    return {
        "oabp_list_missions": oabp_list_missions,
        "oabp_get_mission": oabp_get_mission,
        "oabp_create_mission": oabp_create_mission,
        "oabp_submit_mission": oabp_submit_mission,
        "oabp_get_stats": oabp_get_stats,
        "oabp_get_reputation": oabp_get_reputation,
    }


def get_tools(
    client: Optional[OabpClient] = None,
    agent_id: Optional[str] = None,
    *,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 15.0,
    max_retries: int = 3,
) -> List[Any]:
    """Return the OABP LlamaIndex tools, ready to attach to an agent.

    This is the primary entry point. Pass an existing :class:`oabp.OabpClient`
    via ``client=`` to reuse a configured/pooled session, or supply connection
    parameters and one is built for you.

    Parameters
    ----------
    client:
        Pre-configured OABP SDK client. If given, the connection parameters
        (``base_url`` / ``api_key`` / ``timeout`` / ``max_retries``) are ignored.
        ``agent_id`` still applies and falls back to ``client.agent_id``.
    agent_id:
        Default agent id used as ``creator_agent_id`` / ``submitter_agent_id`` /
        reputation target when the model does not pass one. Falls back to
        ``client.agent_id`` when omitted.
    base_url, api_key, timeout, max_retries:
        Forwarded to a freshly-built :class:`oabp.OabpClient` when ``client`` is
        not supplied. ``base_url`` defaults to the SDK default
        (``https://cryptogenesis.duckdns.org``).

    Returns
    -------
    list
        Six tools, in :data:`TOOL_NAMES` order. With ``llama-index-core``
        installed these are :class:`llama_index.core.tools.FunctionTool` objects
        (each carrying ``metadata.name`` / ``metadata.description`` /
        ``metadata.fn_schema``); without it, they are lightweight
        ``FunctionTool``-likes that mirror the same attributes (and remain
        directly callable). Use :func:`llamaindex_oabp.tool_metadata` to read a
        tool's name/description/fn_schema uniformly in either mode.
    """
    if client is None:
        client_kwargs: Dict[str, Any] = {
            "agent_id": agent_id,
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        if base_url:
            client_kwargs["base_url"] = base_url
        client = OabpClient(**client_kwargs)
        effective_agent = agent_id
    else:
        effective_agent = (
            agent_id if agent_id is not None else getattr(client, "agent_id", None)
        )

    raw = _build_callables(client, effective_agent)
    return [
        FunctionTool.from_defaults(
            fn=raw[name],
            name=name,
            description=_DESCRIPTIONS[name],
            fn_schema=_SCHEMAS[name],
        )
        for name in TOOL_NAMES
    ]


def tool_names() -> List[str]:
    """Return the canonical OABP tool names, in order."""
    return list(TOOL_NAMES)


__all__ = [
    "get_tools",
    "tool_names",
    "TOOL_NAMES",
    "mission_to_dict",
    "stats_to_dict",
    "reputation_to_dict",
    "error_to_dict",
]
