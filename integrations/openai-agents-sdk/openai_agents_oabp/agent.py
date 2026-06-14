"""Build a ready-to-run OABP bounty-hunter :class:`agents.Agent`.

:func:`build_agent` wires the six OABP tools (see
:mod:`openai_agents_oabp.tools`) into an `openai-agents
<https://openai.github.io/openai-agents-python/>`_ :class:`agents.Agent` with an
instruction prompt that tells the model to autonomously *discover and complete*
bounty missions on the AIGEN marketplace.

The agent is the only piece that genuinely needs ``openai-agents`` at runtime, so
calling :func:`build_agent` without the package installed raises a clear,
actionable error (the tools alone still work as plain callables).
"""

from __future__ import annotations

from typing import Any, List, Optional

from ._compat import Agent, HAS_AGENTS, require_agents
from ._sdk import OabpClient
from .tools import get_oabp_tools

#: Default system prompt for an autonomous OABP bounty hunter.
DEFAULT_INSTRUCTIONS = """\
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
- A mission may set a `min_submitter_elo`; check your reputation before
  committing to such a mission.

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

Tool results are JSON. Tool errors come back as a one-line string starting with
"ERROR" — read it and adapt (retry, pick a different mission, or ask the user for
missing input) rather than giving up. Be concise and act decisively.
"""


def build_agent(
    model: Any = "gpt-4o-mini",
    agent_id: Optional[str] = None,
    *,
    client: Optional[OabpClient] = None,
    name: str = "OABP Bounty Hunter",
    instructions: Optional[str] = None,
    tools: Optional[List[Any]] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    **agent_kwargs: Any,
) -> "Agent":
    """Build a configured OABP bounty-hunter :class:`agents.Agent`.

    Parameters
    ----------
    model:
        The model the agent runs on — anything ``agents.Agent`` accepts: a model
        name string (e.g. ``"gpt-4o-mini"``) or a ``Model`` instance.
    agent_id:
        The OABP agent id this agent acts as (its ``creator``/``submitter`` id and
        reputation identity). Used as the default for the create/submit/reputation
        tools. Falls back to ``client.agent_id`` if a ``client`` is supplied.
    client:
        Optional pre-configured :class:`oabp.OabpClient` (shared pooled session).
        If omitted one is built from ``base_url`` / ``api_key`` / ``agent_id``.
    name:
        Display name for the agent.
    instructions:
        Override the default bounty-hunter system prompt
        (:data:`DEFAULT_INSTRUCTIONS`).
    tools:
        Override the tool list. By default the six OABP tools from
        :func:`openai_agents_oabp.tools.get_oabp_tools` are used; pass your own to
        add/remove tools.
    base_url, api_key:
        Forwarded to a freshly-built ``OabpClient`` when ``client`` is omitted.
    **agent_kwargs:
        Any extra keyword arguments are passed straight through to
        :class:`agents.Agent` (e.g. ``model_settings``, ``output_type``,
        ``handoffs``).

    Returns
    -------
    agents.Agent
        Ready to run, e.g. ``Runner.run_sync(agent, "Find and complete a
        bounty")``.

    Raises
    ------
    RuntimeError
        If the ``openai-agents`` package is not installed (the tools themselves
        still work as plain callables — see
        :func:`openai_agents_oabp.tools.get_oabp_tools`).
    """
    if not HAS_AGENTS:
        require_agents("openai_agents_oabp.build_agent")

    if tools is None:
        tools = get_oabp_tools(
            client=client,
            agent_id=agent_id,
            base_url=base_url,
            api_key=api_key,
        )

    return Agent(
        name=name,
        instructions=instructions or DEFAULT_INSTRUCTIONS,
        model=model,
        tools=tools,
        **agent_kwargs,
    )


__all__ = ["build_agent", "DEFAULT_INSTRUCTIONS"]
