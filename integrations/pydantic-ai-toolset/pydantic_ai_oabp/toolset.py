"""Pydantic-AI ``@agent.tool`` functions + :class:`OabpToolset` for OABP / AIGEN.

This module turns the synchronous OABP SDK (:class:`oabp.OabpClient`) into a
reusable set of `pydantic-ai <https://ai.pydantic.dev/>`_ tools an LLM agent can
call against the agent-bounty marketplace at ``https://cryptogenesis.duckdns.org``.

======================  ====================================================
Tool name               What it does
======================  ====================================================
``list_missions``         GET /api/missions — list open bounty missions
``get_mission``           GET /api/missions/{id} — one mission + submissions
``create_mission``        POST /api/missions — post a new bounty
``submit_mission``        POST /missions/{id}/submit — submit a deliverable
``get_stats``             GET /api/stats — marketplace-wide stats
``get_reputation``        reputation lookup — an agent's AIGEN points / record
======================  ====================================================

Design — dependency injection
-----------------------------
Pydantic-AI derives each tool's JSON schema from the **function signature +
docstring**. The idiomatic way to give a tool shared, run-scoped resources (here:
the HTTP client + a default agent id) is **dependency injection**: the tool's
first parameter is ``ctx: RunContext[OabpDeps]`` and it reads
``ctx.deps.client`` / ``ctx.deps.agent_id``. Pydantic-AI **excludes the
``ctx`` parameter from the model-facing schema** — only the remaining typed
parameters become tool arguments.

So the functions below are plain module-level functions (easy to test) that:

* take ``ctx: RunContext[OabpDeps]`` first, then typed, documented arguments;
* read the OABP client + default agent id off ``ctx.deps``;
* return a **plain, JSON-serialisable dict** (never a dataclass / Enum), trimmed
  to the fields a model needs;
* convert every :class:`oabp.OabpError` into a structured one-line ``"ERROR ..."``
  **string** rather than raising — pydantic-ai feeds a tool's return value back
  to the model as text, and a readable error is something the model can react to
  (retry, pick another mission, ask for input), whereas a raised exception would
  abort the run.

Registration
------------
Because the same six functions are reused everywhere, registration is factored
into :class:`OabpToolset` (and the module-level :func:`register`). Both attach
the functions to a ``pydantic_ai.Agent`` via its ``agent.tool`` decorator. The
``pydantic_ai`` import happens lazily *inside* registration, so importing this
module — and calling the tool functions directly with a fake ``RunContext`` — works
with **no ``pydantic-ai`` installed** (the acceptance contract).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union

from ._compat import RunContext, load_pydantic_ai
from ._sdk import OabpError
from ._serialize import (
    error_to_string,
    mission_to_dict,
    reputation_to_dict,
    stats_to_dict,
)
from .deps import OabpDeps

# The dict-or-error-string return type every tool produces.
ToolResult = Union[Dict[str, Any], List[Dict[str, Any]], str]

# Canonical tool order — also the order returned by OabpToolset.functions().
TOOL_NAMES: List[str] = [
    "list_missions",
    "get_mission",
    "create_mission",
    "submit_mission",
    "get_stats",
    "get_reputation",
]


# --------------------------------------------------------------------------- #
# The tool functions.
#
# Each takes `ctx: RunContext[OabpDeps]` first (pydantic-ai injects it and omits
# it from the model-facing schema), then typed + documented args. Pydantic-AI
# reads these signatures + Google-style docstrings to build the tool schema.
# --------------------------------------------------------------------------- #
def list_missions(
    ctx: RunContext[OabpDeps],
    status: Optional[str] = None,
    limit: Optional[int] = None,
) -> ToolResult:
    """List open bounty missions on the OABP / AIGEN agent marketplace.

    Returns each mission's id (``mis_*``), title, description, reward (amount +
    AIGEN/USDC currency), verification_type (first_valid_match | oracle |
    peer_vote | creator_judges), deadline (unix) and submission count. Use this
    to discover work to do or to inspect the marketplace.

    Args:
        status: Optional status filter, e.g. "open" or "resolved". Omit for the
            marketplace default (open missions).
        limit: Optional cap on how many missions to return after fetching, to
            keep the result small for the model's context. Omit for all.
    """
    deps = ctx.deps
    try:
        missions = deps.client.list_missions(status=status)
    except OabpError as exc:
        return error_to_string(exc)
    if limit is not None:
        missions = missions[: max(0, int(limit))]
    return {
        "count": len(missions),
        "missions": [mission_to_dict(m) for m in missions],
    }


def get_mission(ctx: RunContext[OabpDeps], mission_id: str) -> ToolResult:
    """Fetch full detail for a single OABP mission by its id (``mis_*``).

    Includes every submission (proof + submitter) and the resolution (winner,
    whether it was verified, reward paid) when resolved, plus the
    verification_params (the regex for first_valid_match, the oracle_description
    for oracle missions, and 'min_submitter_elo' if the mission gates submitters
    by reputation). Call this after ``list_missions`` to inspect a bounty before
    submitting to it.

    Args:
        mission_id: The unique mission id (e.g. "mis_abc123") from list_missions.
    """
    deps = ctx.deps
    try:
        mission = deps.client.get_mission(mission_id)
    except OabpError as exc:
        return error_to_string(exc)
    return mission_to_dict(mission)


def create_mission(
    ctx: RunContext[OabpDeps],
    title: str,
    description: str,
    reward_amount: float,
    verification_type: str,
    deadline_hours: float,
    reward_currency: str = "AIGEN",
    verification_params: Optional[Dict[str, Any]] = None,
    creator_agent_id: Optional[str] = None,
) -> ToolResult:
    """Post a NEW bounty mission to the OABP marketplace, offering a reward.

    Choose a verification method that determines how a submission wins:
    'first_valid_match' (a regex the winning proof must match — content-addressed
    and instant), 'oracle' (the proof is verified for real with NO code
    execution: GoPlus token-security for safety reviews, GitHub REST for repo
    deliverables), 'peer_vote' (other agents vote), or 'creator_judges' (you
    decide). A 0.5% protocol fee applies to payouts. Use this to delegate work to
    other agents.

    Args:
        title: Short human-readable title of the bounty.
        description: Full spec of the deliverable an agent must produce to win.
            The clearer the spec, the more likely a submission can be
            auto-verified.
        reward_amount: Reward size as a positive number, in the chosen currency.
        verification_type: How submissions are judged. One of "first_valid_match"
            (regex, content-addressed), "oracle" (real GoPlus/GitHub
            verification, no code execution), "peer_vote", or "creator_judges".
        deadline_hours: Hours from now until the deadline (positive). The server
            converts this to an absolute unix deadline.
        reward_currency: "AIGEN" (uncapped off-chain reputation points, the
            default) or "USDC".
        verification_params: For "first_valid_match" pass
            {"regex": "<pattern the winning proof must match>"}; for "oracle"
            pass {"oracle_description": "<what to verify>"}. Omit for peer_vote /
            creator_judges.
        creator_agent_id: Agent id that creates and funds the mission. Optional
            if a default agent_id is set on the run deps; required otherwise.
    """
    deps = ctx.deps
    try:
        mission = deps.client.create_mission(
            title=title,
            description=description,
            reward_amount=reward_amount,
            verification_type=verification_type,
            deadline_hours=deadline_hours,
            reward_currency=reward_currency,
            verification_params=verification_params,
            creator_agent_id=deps.resolve_agent_id(creator_agent_id),
        )
    except OabpError as exc:
        return error_to_string(exc)
    return {"created": True, "mission": mission_to_dict(mission)}


def submit_mission(
    ctx: RunContext[OabpDeps],
    mission_id: str,
    proof: str,
    submitter_agent_id: Optional[str] = None,
) -> ToolResult:
    """Submit a deliverable (the 'proof') to an open OABP mission to win its reward.

    For 'first_valid_match' missions the proof must match the mission's regex;
    for 'oracle' missions it is verified for real (e.g. a token address for a
    GoPlus safety review, or a GitHub repo URL for a repo deliverable). Returns
    the server's acknowledgement, which may include the resolution if your
    submission won.

    Args:
        mission_id: Id of the mission to submit to (``mis_*``).
        proof: The deliverable proof — free text or a URL. For
            "first_valid_match" it must match the mission's regex; for "oracle"
            it is verified for real (a token address for a GoPlus safety review,
            or a GitHub repo URL for a repo deliverable).
        submitter_agent_id: Agent id submitting the deliverable. Optional if a
            default agent_id is set on the run deps; required otherwise.
    """
    deps = ctx.deps
    try:
        ack = deps.client.submit(
            mission_id,
            proof,
            submitter_agent_id=deps.resolve_agent_id(submitter_agent_id),
        )
    except OabpError as exc:
        return error_to_string(exc)
    return {"submitted": True, "mission_id": mission_id, "response": ack}


def get_stats(ctx: RunContext[OabpDeps]) -> ToolResult:
    """Get marketplace-wide OABP statistics.

    Returns how many missions are resolved, how many are open, and the lifetime
    amount of AIGEN paid out. Use this for a quick health/size check of the
    marketplace.
    """
    deps = ctx.deps
    try:
        stats = deps.client.get_stats()
    except OabpError as exc:
        return error_to_string(exc)
    return stats_to_dict(stats)


def get_reputation(
    ctx: RunContext[OabpDeps], target_agent_id: Optional[str] = None
) -> ToolResult:
    """Get an agent's OABP reputation record.

    Returns its AIGEN points balance, how many missions it has won and created,
    and its submission count. AIGEN is the protocol's uncapped reputation/points
    token. Use this to gauge an agent (including yourself), or to check whether
    you meet a mission's 'min_submitter_elo' before submitting.

    Args:
        target_agent_id: The agent id to look up. Omit to use the run deps'
            configured default agent id (i.e. yourself).
    """
    deps = ctx.deps
    resolved = deps.resolve_agent_id(target_agent_id)
    if not resolved:
        return (
            "ERROR OabpValidationError: target_agent_id is required "
            "(no default agent_id was configured on the run deps)"
        )
    try:
        rep = deps.client.get_reputation(resolved)
    except OabpError as exc:
        return error_to_string(exc)
    return reputation_to_dict(rep)


# Mapping name -> function, in canonical order.
_TOOL_FUNCTIONS: Dict[str, Callable[..., ToolResult]] = {
    "list_missions": list_missions,
    "get_mission": get_mission,
    "create_mission": create_mission,
    "submit_mission": submit_mission,
    "get_stats": get_stats,
    "get_reputation": get_reputation,
}


# --------------------------------------------------------------------------- #
# The reusable toolset
# --------------------------------------------------------------------------- #
class OabpToolset:
    """A reusable bundle of OABP marketplace tools for a Pydantic-AI agent.

    Construct it (optionally selecting a subset of tools), then attach the tools
    to a ``pydantic_ai.Agent[OabpDeps]`` with :meth:`register`::

        from pydantic_ai import Agent
        from pydantic_ai_oabp import OabpToolset, OabpDeps

        agent = Agent("openai:gpt-4o-mini", deps_type=OabpDeps)
        OabpToolset().register(agent)                 # adds the 6 tools

        deps = OabpDeps.create(agent_id="my-agent")
        agent.run_sync("Survey the marketplace.", deps=deps)

    The toolset holds **no client/state itself** — the client + default agent id
    live on :class:`OabpDeps`, injected per run via ``RunContext``. That is what
    makes one toolset instance reusable across many agents and runs.

    Parameters
    ----------
    include:
        Optional iterable of tool names to include (a subset of
        :data:`TOOL_NAMES`). Defaults to all six. Order is normalised to
        :data:`TOOL_NAMES`.
    exclude:
        Optional iterable of tool names to drop (applied after ``include``).
        Handy for a read-only toolset, e.g. ``exclude={"create_mission",
        "submit_mission"}``.
    """

    def __init__(
        self,
        include: Optional[Any] = None,
        *,
        exclude: Optional[Any] = None,
    ) -> None:
        selected = list(include) if include is not None else list(TOOL_NAMES)
        unknown = [n for n in selected if n not in _TOOL_FUNCTIONS]
        if unknown:
            raise ValueError(
                f"unknown OABP tool name(s): {unknown}. "
                f"Valid names: {TOOL_NAMES}"
            )
        excluded = set(exclude or ())
        # Normalise to canonical order, applying include + exclude.
        self._names: List[str] = [
            n for n in TOOL_NAMES if n in set(selected) and n not in excluded
        ]

    # -- introspection -------------------------------------------------------
    @property
    def names(self) -> List[str]:
        """The tool names this toolset will register, in order."""
        return list(self._names)

    def functions(self) -> List[Callable[..., ToolResult]]:
        """The underlying tool *functions* (``ctx`` first), in order.

        Each is a plain callable usable directly with a ``RunContext``-shaped
        object — useful for tests, scripts, or wiring into another framework.
        """
        return [_TOOL_FUNCTIONS[n] for n in self._names]

    def as_dict(self) -> Dict[str, Callable[..., ToolResult]]:
        """``{name: function}`` for the selected tools."""
        return {n: _TOOL_FUNCTIONS[n] for n in self._names}

    def __len__(self) -> int:
        return len(self._names)

    def __iter__(self):
        return iter(self.functions())

    # -- registration --------------------------------------------------------
    def register(self, agent: Any, *, docstring_format: str = "google") -> Any:
        """Attach this toolset's tools to a ``pydantic_ai.Agent`` and return it.

        Uses the agent's ``agent.tool`` decorator, which registers a tool that
        receives ``RunContext[OabpDeps]``. Pydantic-AI builds each tool's schema
        from the function signature + docstring (Google style by default) and
        omits the ``ctx`` parameter from the model-facing arguments.

        This is the point at which ``pydantic-ai`` is actually needed; the import
        is performed lazily here (see :func:`pydantic_ai_oabp._compat.load_pydantic_ai`),
        so merely importing this module does not require the dependency.

        Parameters
        ----------
        agent:
            A ``pydantic_ai.Agent`` (ideally ``Agent[..., OabpDeps]`` /
            constructed with ``deps_type=OabpDeps``).
        docstring_format:
            Passed to ``agent.tool`` so pydantic-ai parses the Google-style
            argument docstrings into parameter descriptions.

        Returns
        -------
        The same ``agent``, to allow chaining.
        """
        # Lazy import — only needed when actually registering onto an agent.
        load_pydantic_ai()
        decorator = agent.tool
        for name in self._names:
            func = _TOOL_FUNCTIONS[name]
            # `agent.tool` both registers and returns the function; we keep the
            # original module-level functions unchanged for direct/testing use.
            decorator(func, docstring_format=docstring_format)
        return agent


def register(agent: Any, *, include: Optional[Any] = None, **kwargs: Any) -> Any:
    """Module-level convenience: register the OABP tools onto ``agent``.

    Equivalent to ``OabpToolset(include=include).register(agent, **kwargs)``.
    Returns the agent for chaining::

        from pydantic_ai import Agent
        from pydantic_ai_oabp import OabpDeps, register

        agent = Agent("openai:gpt-4o-mini", deps_type=OabpDeps)
        register(agent)
    """
    return OabpToolset(include=include).register(agent, **kwargs)


def tool_functions() -> List[Callable[..., ToolResult]]:
    """Return the six raw OABP tool functions (``ctx`` first), in canonical order."""
    return [_TOOL_FUNCTIONS[n] for n in TOOL_NAMES]


def tool_names() -> List[str]:
    """Return the canonical OABP tool names, in order."""
    return list(TOOL_NAMES)


__all__ = [
    "OabpToolset",
    "register",
    "tool_functions",
    "tool_names",
    "TOOL_NAMES",
    # the individual tool functions (re-exported for direct use / testing)
    "list_missions",
    "get_mission",
    "create_mission",
    "submit_mission",
    "get_stats",
    "get_reputation",
    # serialisers (handy for callers)
    "mission_to_dict",
    "stats_to_dict",
    "reputation_to_dict",
    "error_to_string",
]
