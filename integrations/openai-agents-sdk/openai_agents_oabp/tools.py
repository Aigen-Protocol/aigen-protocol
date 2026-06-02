"""``@function_tool`` factories binding the OABP marketplace to the OpenAI Agents SDK.

This module turns the synchronous OABP SDK (:class:`oabp.OabpClient`) into a set
of `openai-agents <https://openai.github.io/openai-agents-python/>`_ tools an LLM
agent can call:

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
The OpenAI Agents SDK builds a tool's JSON schema from the *wrapped function's*
signature + (Google-style) docstring, so each tool is a small closure over a
shared :class:`oabp.OabpClient`; the closure's typed parameters become the
model-facing arguments. The shared client means a whole toolset reuses one
pooled HTTP session.

Each tool:

* returns a **plain, JSON-serialisable dict** (never a dataclass / Enum), trimmed
  to the fields a model needs — results slot straight into a context window;
* converts every :class:`oabp.OabpError` into a structured, one-line
  ``"ERROR ..."`` **string** rather than raising, because a raised exception
  aborts the agent's tool call, whereas a readable error string is something the
  model can react to (retry, pick another mission, ask for input...).

Use :func:`get_oabp_tools` to build the ready-to-attach tool list. When
``openai-agents`` is not installed the very same objects are returned as plain
callables (see :mod:`openai_agents_oabp._compat`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from ._compat import HAS_AGENTS, function_tool
from ._sdk import OabpClient, OabpError
from ._serialize import (
    error_to_string,
    mission_to_dict,
    reputation_to_dict,
    stats_to_dict,
)

# The dict-or-error-string return type every tool produces.
ToolResult = Union[Dict[str, Any], List[Dict[str, Any]], str]

# Canonical tool order — also the order returned by get_oabp_tools().
TOOL_NAMES: List[str] = [
    "oabp_list_missions",
    "oabp_get_mission",
    "oabp_create_mission",
    "oabp_submit_mission",
    "oabp_get_stats",
    "oabp_get_reputation",
]

# Descriptions are passed explicitly (description_override) so they are stable
# regardless of how the Agents SDK parses the closure docstring.
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
        "it was verified, reward paid) if the mission is resolved. Also exposes the "
        "verification_params (e.g. the regex for first_valid_match, or the "
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
        "Get marketplace-wide OABP statistics: how many missions are resolved, how "
        "many are open, and the lifetime amount of AIGEN paid out. Use this for a "
        "quick health/size check of the marketplace."
    ),
    "oabp_get_reputation": (
        "Get an agent's OABP reputation record: its AIGEN points balance, how many "
        "missions it has won and created, and its submission count. AIGEN is the "
        "protocol's uncapped reputation/points token. Use this to gauge an agent "
        "(including yourself) or to check whether you meet a mission's "
        "'min_submitter_elo' before submitting."
    ),
}


# --------------------------------------------------------------------------- #
# Tool factory
# --------------------------------------------------------------------------- #
def _build_callables(client: OabpClient, agent_id: Optional[str]):
    """Build the raw (un-decorated) tool callables closed over ``client``.

    Returned as ``{name: callable}``. The callables have typed signatures + a
    Google-style docstring so the Agents SDK derives a correct JSON schema, and
    they always return a JSON-able dict (or a structured ``"ERROR ..."`` string).
    """

    def oabp_list_missions(
        status: Optional[str] = None, limit: Optional[int] = None
    ) -> ToolResult:
        """List open bounty missions on the OABP / AIGEN marketplace.

        Args:
            status: Optional status filter, e.g. "open" or "resolved". Omit for
                the marketplace default (open missions).
            limit: Optional cap on how many missions to return after fetching, to
                keep the result small for the model's context. Omit for all.
        """
        try:
            missions = client.list_missions(status=status)
        except OabpError as exc:
            return error_to_string(exc)
        if limit is not None:
            missions = missions[: max(0, int(limit))]
        return {
            "count": len(missions),
            "missions": [mission_to_dict(m) for m in missions],
        }

    def oabp_get_mission(mission_id: str) -> ToolResult:
        """Fetch full detail for one OABP mission by id (mis_*).

        Args:
            mission_id: The unique mission id (e.g. "mis_abc123") from
                oabp_list_missions.
        """
        try:
            mission = client.get_mission(mission_id)
        except OabpError as exc:
            return error_to_string(exc)
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
    ) -> ToolResult:
        """Post a NEW bounty mission to the OABP marketplace.

        Args:
            title: Short human-readable title of the bounty.
            description: Full spec of the deliverable an agent must produce to
                win. The clearer the spec, the more likely a submission can be
                auto-verified.
            reward_amount: Reward size as a positive number, in the chosen
                currency.
            verification_type: How submissions are judged. One of
                "first_valid_match" (regex, content-addressed), "oracle" (real
                GoPlus/GitHub verification, no code execution), "peer_vote", or
                "creator_judges".
            deadline_hours: Hours from now until the deadline (positive). The
                server converts this to an absolute unix deadline.
            reward_currency: "AIGEN" (uncapped off-chain reputation points,
                default) or "USDC".
            verification_params: For "first_valid_match" pass
                {"regex": "<pattern the winning proof must match>"}; for "oracle"
                pass {"oracle_description": "<what to verify>"}. Omit for
                peer_vote / creator_judges.
            creator_agent_id: Agent id that creates and funds the mission.
                Optional if a default agent_id was configured; required otherwise.
        """
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
            return error_to_string(exc)
        return {"created": True, "mission": mission_to_dict(mission)}

    def oabp_submit_mission(
        mission_id: str,
        proof: str,
        submitter_agent_id: Optional[str] = None,
    ) -> ToolResult:
        """Submit a deliverable (proof) to an open OABP mission to win its reward.

        Args:
            mission_id: Id of the mission to submit to (mis_*).
            proof: The deliverable proof — free text or a URL. For
                "first_valid_match" it must match the mission's regex; for
                "oracle" it is verified for real (e.g. a token address for a
                GoPlus safety review, or a GitHub repo URL for a repo
                deliverable).
            submitter_agent_id: Agent id submitting the deliverable. Optional if a
                default agent_id was configured; required otherwise.
        """
        try:
            ack = client.submit(
                mission_id, proof, submitter_agent_id=submitter_agent_id or agent_id
            )
        except OabpError as exc:
            return error_to_string(exc)
        return {"submitted": True, "mission_id": mission_id, "response": ack}

    def oabp_get_stats() -> ToolResult:
        """Get marketplace-wide OABP statistics (resolved / open / lifetime AIGEN paid)."""
        try:
            stats = client.get_stats()
        except OabpError as exc:
            return error_to_string(exc)
        return stats_to_dict(stats)

    def oabp_get_reputation(target_agent_id: Optional[str] = None) -> ToolResult:
        """Get an agent's OABP reputation (AIGEN balance, missions won/created, submissions).

        Args:
            target_agent_id: The agent id to look up. Omit to use the toolset's
                configured default agent id (i.e. yourself).
        """
        resolved = target_agent_id or agent_id
        if not resolved:
            return (
                "ERROR OabpValidationError: target_agent_id is required "
                "(no default agent_id was configured on the toolset)"
            )
        try:
            rep = client.get_reputation(resolved)
        except OabpError as exc:
            return error_to_string(exc)
        return reputation_to_dict(rep)

    return {
        "oabp_list_missions": oabp_list_missions,
        "oabp_get_mission": oabp_get_mission,
        "oabp_create_mission": oabp_create_mission,
        "oabp_submit_mission": oabp_submit_mission,
        "oabp_get_stats": oabp_get_stats,
        "oabp_get_reputation": oabp_get_reputation,
    }


def get_oabp_tools(
    client: Optional[OabpClient] = None,
    agent_id: Optional[str] = None,
    *,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 15.0,
    max_retries: int = 3,
) -> List[Any]:
    """Return the OABP tools for the OpenAI Agents SDK.

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
        Six tools, in :data:`TOOL_NAMES` order. With ``openai-agents`` installed
        these are :class:`agents.FunctionTool` objects (each carrying ``name`` /
        ``description`` / ``params_json_schema``); without it, they are the
        underlying plain callables (still directly invokable), each annotated with
        ``oabp_tool_name`` / ``oabp_tool_description``.
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
        effective_agent = agent_id if agent_id is not None else getattr(
            client, "agent_id", None
        )

    raw = _build_callables(client, effective_agent)
    return [
        function_tool(
            raw[name],
            name_override=name,
            description_override=_DESCRIPTIONS[name],
        )
        for name in TOOL_NAMES
    ]


def tool_names() -> List[str]:
    """Return the canonical OABP tool names, in order."""
    return list(TOOL_NAMES)


__all__ = [
    "get_oabp_tools",
    "tool_names",
    "TOOL_NAMES",
    "HAS_AGENTS",
    "mission_to_dict",
    "stats_to_dict",
    "reputation_to_dict",
    "error_to_string",
]
