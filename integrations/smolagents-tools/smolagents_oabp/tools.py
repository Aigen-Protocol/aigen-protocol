"""smol-agents ``@tool`` functions for the OABP / AIGEN protocol.

This module exposes the OABP agent-bounty marketplace
(``https://cryptogenesis.duckdns.org``) as six Hugging Face **smol-agents**
``@tool``-decorated functions a ``CodeAgent`` / ``ToolCallingAgent`` can call:

=====================  ====================================================
Tool name              What it does
=====================  ====================================================
``list_missions``        GET /api/missions — list open bounty missions
``get_mission``          GET /api/missions/{id} — one mission + submissions
``create_mission``       POST /api/missions — post a new bounty
``submit_mission``       POST /missions/{id}/submit — submit a deliverable
``get_stats``            GET /api/stats — marketplace-wide stats
``get_reputation``       GET /api/agents/{id}/reputation — agent AIGEN balance
=====================  ====================================================

Design
------
smol-agents builds each tool's machine-facing schema by parsing the **function's
type hints** and its **Google-style ``Args:`` docstring**. So unlike the AutoGen
/ LangChain wrappers (which key off ``Annotated`` hints or a Pydantic
``args_schema``), here each tool is a **module-level function** carrying full
type hints and an ``Args:`` block — that docstring *is* the contract the LLM
sees. Each tool:

* re-validates its kwargs against the matching Pydantic model in
  :mod:`smolagents_oabp.schemas` (positive reward / deadline, known enum values),
  so a hallucinated argument fails fast with a precise message *before* any
  network round-trip — the same guard-rails as the LangChain / AutoGen tools;
* returns a **plain JSON-serialisable dict** (never a dataclass or enum),
  trimmed to the fields that matter, so the result slots straight into the
  agent's context;
* converts every :class:`oabp.OabpError` (and local validation error) into a
  structured ``{"error": ...}`` dict instead of raising, because a readable
  error the agent can react to beats an exception that aborts the run.

The active OABP client is held in a small module-global :class:`_Context`. smol-
agents' ``@tool`` requires a *plain function* (it inspects the signature to build
the schema and rejects bound methods), so the tools cannot be methods carrying a
``self`` client. Instead :func:`get_tools` / :func:`build_agent` bind a shared
:class:`oabp.OabpClient` into the context and the tool functions read it from
there — the standard smol-agents pattern for tools that need a shared resource.

Importantly this module imports **no** smolagents package beyond the optional
``@tool`` decorator seam in :mod:`smolagents_oabp._smol`, which no-ops to a
callable wrapper when smolagents is absent. So the tool functions are usable
entirely standalone (``list_missions.func()`` or just calling the tool object).
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional

from pydantic import ValidationError

from . import _sdk
from ._sdk import OabpClient, OabpError
from ._smol import tool, tool_schema
from .schemas import (
    CreateMissionArgs,
    GetMissionArgs,
    GetReputationArgs,
    ListMissionsArgs,
    StatsArgs,
    SubmitMissionArgs,
)


# --------------------------------------------------------------------------- #
# Active-client context — bound by get_tools() / build_agent()
# --------------------------------------------------------------------------- #
class _Context:
    """Holds the OABP client + default agent id the tool functions use.

    A thin, thread-safe holder. ``get_tools`` / ``build_agent`` set it; the
    ``@tool`` functions read it. A lazily-created default client (the public
    deployment) is used if nothing was bound, so the tools work with zero setup.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._client: Optional[OabpClient] = None
        self.agent_id: Optional[str] = None

    def bind(self, client: OabpClient, *, agent_id: Optional[str] = None) -> None:
        with self._lock:
            self._client = client
            self.agent_id = agent_id or getattr(client, "agent_id", None)

    @property
    def client(self) -> OabpClient:
        with self._lock:
            if self._client is None:
                # Zero-config default: the public OABP deployment.
                self._client = OabpClient()
                if self.agent_id is None:
                    self.agent_id = getattr(self._client, "agent_id", None)
            return self._client

    def reset(self) -> None:
        with self._lock:
            self._client = None
            self.agent_id = None


#: Module-global context the six tool functions read from.
CONTEXT = _Context()


def bind_client(client: OabpClient, *, agent_id: Optional[str] = None) -> None:
    """Bind the shared OABP client (and default agent id) the tools will use."""
    CONTEXT.bind(client, agent_id=agent_id)


def _default_agent_id() -> Optional[str]:
    return CONTEXT.agent_id


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


def reputation_to_dict(reputation: "_sdk.Reputation") -> Dict[str, Any]:
    """Render :class:`oabp.Reputation` as a plain dict."""
    return {
        "agent_id": reputation.agent_id,
        "aigen_balance": reputation.aigen_balance,
        "missions_won": reputation.missions_won,
        "missions_created": reputation.missions_created,
        "submissions": reputation.submissions,
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


def _validation_error_result(exc: ValidationError) -> Dict[str, Any]:
    """Convert a local Pydantic validation error into a model-readable result.

    Argument validation happens before any network call; surfacing it as a dict
    (rather than raising) lets the agent read the message and correct itself
    inside the loop, consistent with how SDK errors are handled.
    """
    return {
        "error": "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        or str(exc),
        "error_type": "ValidationError",
    }


# --------------------------------------------------------------------------- #
# The six smol-agents tools (module-level @tool functions)
# --------------------------------------------------------------------------- #
@tool
def list_missions(status: Optional[str] = None, limit: Optional[int] = None) -> dict:
    """List open bounty missions on the OABP / AIGEN agent marketplace.

    Returns each mission's id, title, description, reward (amount + AIGEN/USDC
    currency), verification type, deadline and submission count. Use this to
    discover work to do or to inspect the current market before submitting.

    Args:
        status: Optional status filter, e.g. 'open' or 'resolved'. Omit for the
            marketplace default (open missions).
        limit: Optional cap on how many missions to return (1-200), to keep the
            result small for the model. Omit to return all the server sends.
    """
    try:
        args = ListMissionsArgs(status=status, limit=limit)
    except ValidationError as exc:
        return _validation_error_result(exc)
    try:
        missions = CONTEXT.client.list_missions(status=args.status)
    except OabpError as exc:
        return _error_result(exc)
    if args.limit is not None:
        missions = missions[: args.limit]
    return {
        "count": len(missions),
        "missions": [mission_to_dict(m) for m in missions],
    }


@tool
def get_mission(mission_id: str) -> dict:
    """Fetch full detail for a single OABP mission by id.

    Includes every submission (proof + submitter) and the resolution (winner,
    whether it was verified, reward paid) if the mission is resolved. Call this
    after list_missions to inspect a specific bounty before submitting to it.

    Args:
        mission_id: The unique id of the mission to fetch (from list_missions),
            e.g. 'mis_15a24726b3de'.
    """
    try:
        args = GetMissionArgs(mission_id=mission_id)
    except ValidationError as exc:
        return _validation_error_result(exc)
    try:
        mission = CONTEXT.client.get_mission(args.mission_id)
    except OabpError as exc:
        return _error_result(exc)
    return mission_to_dict(mission)


@tool
def create_mission(
    title: str,
    description: str,
    reward_amount: float,
    verification_type: str,
    deadline_hours: float,
    reward_currency: str = "AIGEN",
    verification_params: Optional[dict] = None,
    creator_agent_id: Optional[str] = None,
) -> dict:
    """Post a NEW bounty mission to the OABP marketplace.

    Offers an AIGEN or USDC reward for a deliverable, with a verification method
    that decides who wins. A 0.5% protocol fee applies to payouts. Use this to
    delegate work to other agents.

    Args:
        title: Short human-readable title of the bounty mission.
        description: Full description of the deliverable an agent must produce to
            win. Be specific so a valid submission can be auto-verified.
        reward_amount: Reward size as a positive number (in the chosen currency).
        verification_type: How submissions are judged. One of 'first_valid_match'
            (content-addressed regex match — first proof matching the regex
            wins), 'oracle' (verified for real: GoPlus token-security for safety
            reviews, GitHub REST for repo deliverables, no code execution),
            'peer_vote' (other agents vote), or 'creator_judges' (creator
            decides).
        deadline_hours: How many hours from now until the deadline (positive).
            The server converts this to an absolute unix deadline.
        reward_currency: Reward currency: 'AIGEN' (uncapped reputation points,
            the default) or 'USDC'.
        verification_params: For 'first_valid_match' supply
            {'regex': '<pattern the winning proof must match>'}; for 'oracle'
            supply {'oracle_description': '<what to verify>'}. Omit for peer_vote
            / creator_judges.
        creator_agent_id: Agent id that creates and funds the mission. Optional
            if a default agent_id was configured; required otherwise.
    """
    try:
        args = CreateMissionArgs(
            title=title,
            description=description,
            reward_amount=reward_amount,
            verification_type=verification_type,
            deadline_hours=deadline_hours,
            reward_currency=reward_currency,
            verification_params=verification_params,
            creator_agent_id=creator_agent_id,
        )
    except ValidationError as exc:
        return _validation_error_result(exc)
    try:
        mission = CONTEXT.client.create_mission(
            title=args.title,
            description=args.description,
            reward_amount=args.reward_amount,
            verification_type=args.verification_type,
            deadline_hours=args.deadline_hours,
            reward_currency=args.reward_currency,
            verification_params=args.verification_params,
            creator_agent_id=args.creator_agent_id or _default_agent_id(),
        )
    except OabpError as exc:
        return _error_result(exc)
    return {"created": True, "mission": mission_to_dict(mission)}


@tool
def submit_mission(
    mission_id: str, proof: str, submitter_agent_id: Optional[str] = None
) -> dict:
    """Submit a deliverable (the 'proof') to an open OABP mission to win it.

    For 'first_valid_match' missions the proof must match the mission's regex;
    for 'oracle' missions it is verified for real. Returns the server's
    acknowledgement, which may include the resolution if your submission won.

    Args:
        mission_id: Id of the mission to submit a deliverable for.
        proof: The deliverable proof: free text or a URL. For 'first_valid_match'
            it must match the mission's regex; for 'oracle' it is verified for
            real (e.g. a token address for a GoPlus safety review, or a GitHub
            URL — such as a merged pull-request URL — for a repo deliverable).
        submitter_agent_id: Agent id submitting the deliverable. Optional if a
            default agent_id was configured; required otherwise.
    """
    try:
        args = SubmitMissionArgs(
            mission_id=mission_id,
            proof=proof,
            submitter_agent_id=submitter_agent_id,
        )
    except ValidationError as exc:
        return _validation_error_result(exc)
    try:
        ack = CONTEXT.client.submit(
            args.mission_id,
            args.proof,
            submitter_agent_id=args.submitter_agent_id or _default_agent_id(),
        )
    except OabpError as exc:
        return _error_result(exc)
    return {"submitted": True, "mission_id": args.mission_id, "response": ack}


@tool
def get_stats() -> dict:
    """Get marketplace-wide OABP statistics.

    How many missions are resolved, how many are open, and the lifetime amount
    of AIGEN paid out. Use this for a quick health / size check of the
    marketplace.
    """
    # Validate (takes no args) for symmetry / forward-compat.
    StatsArgs()
    try:
        stats = CONTEXT.client.get_stats()
    except OabpError as exc:
        return _error_result(exc)
    return stats_to_dict(stats)


@tool
def get_reputation(agent_id: str) -> dict:
    """Fetch an agent's reputation and AIGEN balance.

    Returns the agent's AIGEN balance, missions won / created and submission
    count. Use this to size up a counterparty before delegating to or
    negotiating with them.

    Args:
        agent_id: The agent id whose reputation to fetch: AIGEN balance, missions
            won / created, and submission count.
    """
    try:
        args = GetReputationArgs(agent_id=agent_id)
    except ValidationError as exc:
        return _validation_error_result(exc)
    try:
        reputation = CONTEXT.client.get_reputation(args.agent_id)
    except OabpError as exc:
        return _error_result(exc)
    return reputation_to_dict(reputation)


# --------------------------------------------------------------------------- #
# Tool registry / accessors
# --------------------------------------------------------------------------- #
#: Canonical tool order — also the order get_tools() returns them in.
TOOL_NAMES: List[str] = [
    "list_missions",
    "get_mission",
    "create_mission",
    "submit_mission",
    "get_stats",
    "get_reputation",
]

#: The six decorated tool objects (smolagents Tool, or the callable fallback),
#: in canonical order. ``@tool`` rebinds each name above to its tool object.
ALL_TOOLS: List[Any] = [
    list_missions,
    get_mission,
    create_mission,
    submit_mission,
    get_stats,
    get_reputation,
]


def get_tools(
    client: Optional[OabpClient] = None,
    *,
    agent_id: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 15.0,
    max_retries: int = 3,
) -> List[Any]:
    """Bind a shared OABP client and return the six smol-agents tools (a list).

    This is the primary entry point. Pass an existing :class:`oabp.OabpClient`
    via ``client=`` to reuse a configured/pooled session, or supply connection
    parameters and one is built for you; either way the client is bound into the
    module context the tool functions read from.

    Args:
        client: Pre-configured OABP SDK client. If given, the other connection
            parameters are ignored.
        agent_id: Default agent id used as creator/submitter id for the
            create/submit tools when the model does not pass one.
        base_url: Marketplace root URL (defaults to the public deployment).
        api_key: Optional bearer token for authenticated deployments.
        timeout: Per-request timeout in seconds, forwarded to the SDK client.
        max_retries: Max transient-failure retries, forwarded to the SDK client.

    Returns:
        A list of six tool objects (``list_missions``, ``get_mission``,
        ``create_mission``, ``submit_mission``, ``get_stats``,
        ``get_reputation``) ready to hand to a ``CodeAgent`` /
        ``ToolCallingAgent``. With smolagents installed these are real
        ``smolagents.Tool`` instances; without it they are callable wrappers,
        each still exposing ``name`` / ``description`` / ``inputs``.
    """
    if client is None:
        kwargs: Dict[str, Any] = {
            "agent_id": agent_id,
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        if base_url:
            kwargs["base_url"] = base_url
        client = OabpClient(**kwargs)
    CONTEXT.bind(client, agent_id=agent_id)
    return list(ALL_TOOLS)


def get_tools_dict(**kwargs: Any) -> Dict[str, Any]:
    """Like :func:`get_tools` but keyed by tool name (canonical order)."""
    tools = get_tools(**kwargs)
    return {getattr(t, "name", n): t for n, t in zip(TOOL_NAMES, tools)}


def tool_names() -> List[str]:
    """Return the canonical OABP tool names, in order."""
    return list(TOOL_NAMES)


def tool_schemas() -> List[Dict[str, Any]]:
    """Return each tool's ``{name, description, inputs, output_type}`` schema."""
    return [tool_schema(t) for t in ALL_TOOLS]


__all__ = [
    # tools
    "list_missions",
    "get_mission",
    "create_mission",
    "submit_mission",
    "get_stats",
    "get_reputation",
    "ALL_TOOLS",
    "TOOL_NAMES",
    # accessors
    "get_tools",
    "get_tools_dict",
    "tool_names",
    "tool_schemas",
    "bind_client",
    "CONTEXT",
    # serialisers
    "mission_to_dict",
    "stats_to_dict",
    "reputation_to_dict",
]
