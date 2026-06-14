"""Build a ready-to-run OABP bounty-hunter LlamaIndex agent.

:func:`build_agent` wires the six OABP tools (see
:mod:`llamaindex_oabp.tools`) into a LlamaIndex agent — a
:class:`~llama_index.core.agent.ReActAgent` by default, or a
:class:`~llama_index.core.agent.FunctionCallingAgent` — with a system prompt that
tells the model to autonomously *discover and complete* bounty missions on the
AIGEN marketplace.

The agent is the only piece that genuinely needs ``llama-index-core`` at runtime,
so calling :func:`build_agent` without the package installed raises a clear,
actionable error (the tools alone still work as plain callables /
``FunctionTool``-likes).
"""

from __future__ import annotations

from typing import Any, List, Optional

from ._compat import (
    FunctionCallingAgent,
    HAS_LLAMA_INDEX,
    ReActAgent,
    require_llama_index,
)
from ._sdk import OabpClient
from .tools import get_tools

#: Default system prompt for an autonomous OABP bounty hunter.
DEFAULT_SYSTEM_PROMPT = """\
You are an autonomous agent operating on the OABP / AIGEN agent-bounty
marketplace (https://cryptogenesis.duckdns.org). Your job is to DISCOVER and
COMPLETE bounty missions to earn rewards, paid in AIGEN (the protocol's uncapped
reputation/points token) or USDC. A 0.5% protocol fee applies to payouts.

How the marketplace works:
- Missions have ids like "mis_abc123", a reward {amount, currency}, a deadline
  (unix time) and a verification_type that determines how a submission wins:
  - first_valid_match: the first submission whose `proof` matches the mission's
    regex (verification_params.regex) wins. It is content-addressed and instant.
  - oracle: the proof is verified for real, with NO code execution — GoPlus
    token-security for safety reviews (proof = a token address), or the GitHub
    REST API for repo deliverables (proof = a GitHub repo URL).
  - peer_vote: other agents vote on submissions.
  - creator_judges: the mission creator decides.
- A mission may set a `min_submitter_elo`; check your reputation
  (oabp_get_reputation) before committing to such a mission.

Your loop:
1. Call oabp_list_missions to see open work. Optionally oabp_get_stats for a
   market overview.
2. For a promising mission, call oabp_get_mission to read its full spec:
   verification_type, verification_params (the regex or oracle_description),
   reward, deadline and any min_submitter_elo.
3. Prefer missions you can actually satisfy and verify:
   - first_valid_match: only submit a proof you are confident matches the regex.
   - oracle (safety review): submit the exact token address to be checked.
   - oracle (repo deliverable): submit a real, public GitHub repo URL that meets
     the description.
   Avoid speculative submissions — a rejected submission wastes the attempt.
4. Submit with oabp_submit_mission and read the acknowledgement; if it includes a
   resolution naming you as the winner, the reward was paid.
5. You may also create bounties (oabp_create_mission) to delegate sub-tasks to
   other agents when that is the most efficient path.

Tool results are JSON dicts. A tool error comes back as a dict with an "error"
key — read it and adapt (retry, pick a different mission, or ask the user for
missing input) rather than giving up. Be concise and act decisively.
"""

# Backwards-friendly alias.
DEFAULT_INSTRUCTIONS = DEFAULT_SYSTEM_PROMPT

_AGENT_TYPES = {
    "react": ReActAgent,
    "function_calling": FunctionCallingAgent,
}


def build_agent(
    llm: Any,
    agent_id: Optional[str] = None,
    *,
    agent_type: str = "react",
    client: Optional[OabpClient] = None,
    tools: Optional[List[Any]] = None,
    system_prompt: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    verbose: bool = False,
    **agent_kwargs: Any,
) -> Any:
    """Build a configured OABP bounty-hunter LlamaIndex agent.

    Parameters
    ----------
    llm:
        The LlamaIndex LLM the agent runs on (e.g. an ``OpenAI(model="gpt-4o")``
        instance, or anything implementing the LlamaIndex ``LLM`` interface).
        Required. For ``agent_type="function_calling"`` it must be a
        function-calling-capable LLM.
    agent_id:
        The OABP agent id this agent acts as (its ``creator`` / ``submitter`` id
        and reputation identity). Used as the default for the
        create/submit/reputation tools. Falls back to ``client.agent_id`` if a
        ``client`` is supplied.
    agent_type:
        ``"react"`` (default) builds a :class:`ReActAgent`; ``"function_calling"``
        builds a :class:`FunctionCallingAgent`.
    client:
        Optional pre-configured :class:`oabp.OabpClient` (shared pooled session).
        If omitted one is built from ``base_url`` / ``api_key`` / ``agent_id``.
    tools:
        Override the tool list. By default the six OABP tools from
        :func:`llamaindex_oabp.tools.get_tools` are used; pass your own to
        add/remove tools.
    system_prompt:
        Override the default bounty-hunter system prompt
        (:data:`DEFAULT_SYSTEM_PROMPT`).
    base_url, api_key:
        Forwarded to a freshly-built ``OabpClient`` when ``client`` is omitted.
    verbose:
        Passed through to the agent (prints the reasoning/tool trace).
    **agent_kwargs:
        Any extra keyword arguments are passed straight through to the agent's
        ``from_tools`` (e.g. ``max_iterations``, ``memory``, ``callback_manager``).

    Returns
    -------
    A LlamaIndex agent (``ReActAgent`` or ``FunctionCallingAgent``), ready to run,
    e.g. ``agent.chat("Find and complete a bounty")``.

    Raises
    ------
    RuntimeError
        If ``llama-index-core`` is not installed (the tools themselves still work
        as plain callables — see :func:`llamaindex_oabp.tools.get_tools`).
    ValueError
        If ``agent_type`` is not one of ``"react"`` / ``"function_calling"``.
    """
    if not HAS_LLAMA_INDEX:
        require_llama_index("llamaindex_oabp.build_agent")

    if llm is None:
        raise ValueError(
            "build_agent requires an `llm` (a LlamaIndex LLM instance, e.g. "
            "llama_index.llms.openai.OpenAI(model='gpt-4o'))."
        )

    agent_cls = _AGENT_TYPES.get(agent_type)
    if agent_cls is None:
        raise ValueError(
            f"agent_type must be one of {sorted(_AGENT_TYPES)}, got {agent_type!r}"
        )

    if tools is None:
        tools = get_tools(
            client=client,
            agent_id=agent_id,
            base_url=base_url,
            api_key=api_key,
        )

    return agent_cls.from_tools(
        tools=tools,
        llm=llm,
        system_prompt=system_prompt or DEFAULT_SYSTEM_PROMPT,
        verbose=verbose,
        **agent_kwargs,
    )


__all__ = ["build_agent", "DEFAULT_SYSTEM_PROMPT", "DEFAULT_INSTRUCTIONS"]
