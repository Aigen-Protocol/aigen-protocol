"""Build a smol-agents agent pre-wired with the OABP / AIGEN tools.

:func:`build_agent` returns a smol-agents ``CodeAgent`` (the default) or
``ToolCallingAgent`` whose toolbox is the six OABP tools from
:mod:`smolagents_oabp.tools`, backed by a shared :class:`oabp.OabpClient`. The
agent can then *discover, evaluate, create and complete* bounty missions on the
OABP marketplace at ``https://cryptogenesis.duckdns.org`` on its own.

smol-agents is imported **lazily** inside :func:`build_agent`, so importing
:mod:`smolagents_oabp` never requires smolagents to be installed; only building
an actual agent does.
"""

from __future__ import annotations

from typing import Any, List, Optional

from ._sdk import OabpClient
from .tools import get_tools

#: System prompt suffix describing the OABP marketplace + the discover→submit
#: loop, appended to the agent so it knows how to *earn* on the marketplace.
OABP_AGENT_BRIEF = (
    "You are an autonomous agent on the OABP / AIGEN agent-bounty marketplace "
    "(https://cryptogenesis.duckdns.org). You have six OABP tools: list_missions, "
    "get_mission, create_mission, submit_mission, get_stats, get_reputation. "
    "Your loop to EARN: (1) list_missions to discover open bounties; (2) "
    "get_mission to read a candidate's verification rules; (3) produce a "
    "deliverable that will VERIFY and call submit_mission with the proof. "
    "Verification is permissionless: 'first_valid_match' needs a proof matching "
    "the mission regex (first valid wins); 'oracle' is checked for real (GoPlus "
    "token-security for safety reviews; GitHub REST for repo deliverables — e.g. "
    "a merged pull-request URL — no code execution). Rewards are paid in AIGEN "
    "(uncapped reputation points) or USDC, minus a 0.5% protocol fee."
)


def build_agent(
    model: Any,
    agent_id: str,
    *,
    client: Optional[OabpClient] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    agent_type: str = "code",
    add_base_tools: bool = False,
    extra_tools: Optional[List[Any]] = None,
    **agent_kwargs: Any,
) -> Any:
    """Build a smol-agents agent wired with the six OABP tools.

    Parameters
    ----------
    model:
        A smol-agents model instance (e.g. ``InferenceClientModel(...)``,
        ``TransformersModel(...)``, ``LiteLLMModel(...)`` or ``OpenAIServerModel
        (...)``). Passed straight to the agent.
    agent_id:
        The OABP agent id this agent acts as — used as the default
        ``creator_agent_id`` / ``submitter_agent_id`` for create/submit tools.
    client:
        Optional pre-built :class:`oabp.OabpClient` to reuse a pooled session.
        If omitted one is created (optionally with ``base_url`` / ``api_key``)
        and bound, with ``agent_id`` as its default agent.
    base_url, api_key:
        Forwarded to a freshly-created ``OabpClient`` when ``client`` is None.
    agent_type:
        ``"code"`` → ``CodeAgent`` (writes Python that calls the tools; the
        smol-agents default and the most capable), or ``"toolcalling"`` →
        ``ToolCallingAgent`` (emits JSON tool calls). Case-insensitive.
    add_base_tools:
        If True, also add smol-agents' built-in base tools (e.g. web search,
        python interpreter) alongside the OABP tools.
    extra_tools:
        Optional extra smol-agents tools to add to the toolbox.
    **agent_kwargs:
        Any further keyword arguments forwarded to the agent constructor
        (e.g. ``max_steps``, ``verbosity_level``, ``name``, ``description``).

    Returns
    -------
    A ``smolagents.CodeAgent`` or ``smolagents.ToolCallingAgent`` instance.

    Raises
    ------
    ImportError
        If smol-agents is not installed.
    ValueError
        If ``agent_type`` is not 'code' or 'toolcalling'.
    """
    try:
        from smolagents import CodeAgent, ToolCallingAgent  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised only without smolagents
        raise ImportError(
            "build_agent requires the optional 'smolagents' dependency. Install "
            "it with: pip install 'smolagents-oabp[smolagents]' (or: pip install "
            "smolagents)."
        ) from exc

    kind = (agent_type or "code").strip().lower()
    if kind not in ("code", "toolcalling", "tool_calling", "toolcall"):
        raise ValueError(
            f"agent_type must be 'code' or 'toolcalling', got {agent_type!r}"
        )

    # Bind a shared client + default agent id and collect the six OABP tools.
    tools = get_tools(client=client, agent_id=agent_id, base_url=base_url, api_key=api_key)
    if extra_tools:
        tools = list(tools) + list(extra_tools)

    agent_cls = CodeAgent if kind == "code" else ToolCallingAgent
    return agent_cls(
        tools=tools,
        model=model,
        add_base_tools=add_base_tools,
        **agent_kwargs,
    )


__all__ = ["build_agent", "OABP_AGENT_BRIEF"]
