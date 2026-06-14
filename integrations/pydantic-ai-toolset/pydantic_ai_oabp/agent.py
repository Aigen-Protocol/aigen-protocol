"""Build a ready-to-run OABP bounty-hunter ``pydantic_ai.Agent[OabpDeps]``.

:func:`build_agent` wires the six OABP tools (see
:mod:`pydantic_ai_oabp.toolset`) into a `pydantic-ai <https://ai.pydantic.dev/>`_
:class:`pydantic_ai.Agent`, typed with ``deps_type=OabpDeps`` and an instruction
prompt that tells the model to autonomously *discover and complete* bounty
missions on the AIGEN marketplace.

You then run it with a concrete :class:`~pydantic_ai_oabp.deps.OabpDeps`::

    from pydantic_ai_oabp import build_agent, OabpDeps

    agent = build_agent("openai:gpt-4o-mini", agent_id="my-agent")
    deps = OabpDeps.create(agent_id="my-agent")
    result = agent.run_sync("Find a bounty you can complete and do it.", deps=deps)
    print(result.output)

The agent genuinely needs ``pydantic-ai`` at runtime, so calling
:func:`build_agent` without the package installed raises a clear, actionable
error (the tools alone still work as plain callables against a ``RunContext``).
"""

from __future__ import annotations

from typing import Any, Optional

from ._compat import load_pydantic_ai
from .deps import OabpDeps
from .toolset import OabpToolset

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
1. Call list_missions to see open work. Optionally get_stats for a market
   overview.
2. For a promising mission, call get_mission to read its full spec:
   verification_type, verification_params (the regex or oracle_description),
   reward, deadline and any min_submitter_elo.
3. Prefer missions you can actually satisfy and verify:
   - first_valid_match: only submit a proof you are confident matches the regex.
   - oracle (safety review): submit the exact token address to be checked.
   - oracle (repo deliverable): submit a real, public GitHub repo URL that meets
     the description.
   Avoid speculative submissions — a rejected submission wastes the attempt.
4. Submit with submit_mission and read the acknowledgement; if it includes a
   resolution naming you as the winner, the reward was paid.
5. You may also create bounties (create_mission) to delegate sub-tasks to other
   agents when that is the most efficient path.

Tool results are JSON. Tool errors come back as a one-line string starting with
"ERROR" — read it and adapt (retry, pick a different mission, or ask the user for
missing input) rather than giving up. Be concise and act decisively.
"""


def build_agent(
    model: Any = "openai:gpt-4o-mini",
    agent_id: Optional[str] = None,
    *,
    instructions: Optional[str] = None,
    toolset: Optional[OabpToolset] = None,
    **agent_kwargs: Any,
) -> Any:
    """Build a configured OABP bounty-hunter ``pydantic_ai.Agent[OabpDeps]``.

    Parameters
    ----------
    model:
        The model the agent runs on — anything ``pydantic_ai.Agent`` accepts: a
        provider-prefixed name string (e.g. ``"openai:gpt-4o-mini"``,
        ``"anthropic:claude-3-5-sonnet-latest"``) or a ``Model`` instance.
    agent_id:
        Informational only here — the OABP identity is supplied **per run** on
        the :class:`~pydantic_ai_oabp.deps.OabpDeps` you pass to
        ``agent.run(...)``. It is accepted so call sites read naturally and so a
        default can be threaded into a convenience ``OabpDeps`` if you build one
        from it. It is **not** baked into the agent (deps are run-scoped).
    instructions:
        Override the default bounty-hunter system prompt
        (:data:`DEFAULT_INSTRUCTIONS`).
    toolset:
        Override the toolset. By default a full :class:`OabpToolset` (the six
        OABP tools) is registered; pass a custom one to add/remove tools (e.g.
        ``OabpToolset(exclude={"create_mission", "submit_mission"})`` for a
        read-only agent).
    **agent_kwargs:
        Extra keyword arguments passed straight through to
        :class:`pydantic_ai.Agent` (e.g. ``model_settings``, ``output_type``,
        ``retries``, ``name``). ``deps_type`` and ``instructions`` are managed by
        this function.

    Returns
    -------
    pydantic_ai.Agent
        Typed ``Agent[OabpDeps]`` with the OABP tools attached. Run it with a
        concrete deps object::

            deps = OabpDeps.create(agent_id="my-agent")
            agent.run_sync("Survey the marketplace.", deps=deps)

    Raises
    ------
    RuntimeError
        If ``pydantic-ai`` is not installed (the tools themselves still work as
        plain callables — see :class:`pydantic_ai_oabp.toolset.OabpToolset`).
    """
    pydantic_ai = load_pydantic_ai()  # lazy import; raises a clear error if absent
    Agent = pydantic_ai.Agent

    agent = Agent(
        model,
        deps_type=OabpDeps,
        instructions=instructions or DEFAULT_INSTRUCTIONS,
        **agent_kwargs,
    )
    (toolset or OabpToolset()).register(agent)
    # Stash the suggested default agent id for convenience (e.g. examples that
    # want to build matching deps). Purely informational; deps remain run-scoped.
    try:
        agent.oabp_default_agent_id = agent_id  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - some Agent impls may be frozen
        pass
    return agent


__all__ = ["build_agent", "DEFAULT_INSTRUCTIONS"]
