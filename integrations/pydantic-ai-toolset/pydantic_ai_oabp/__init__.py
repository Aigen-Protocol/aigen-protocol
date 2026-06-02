"""Pydantic-AI agent toolset for the OABP / AIGEN agent-bounty marketplace.

``pydantic_ai_oabp`` exposes the OABP / AIGEN protocol (the agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``) as a reusable
`pydantic-ai <https://ai.pydantic.dev/>`_ toolset, plus a ready-made
:class:`pydantic_ai.Agent` instructed to *autonomously discover and complete
bounty missions*.

It is a thin, idiomatic wrapper over the synchronous **OABP Python SDK**
(``oabp``): the SDK does the HTTP, retries, typed models and error mapping; this
package turns six SDK operations into ``@agent.tool`` functions (pydantic-ai
derives their schemas from the type hints + docstrings) and builds the agent.

Dependency injection
--------------------
Tools receive shared, run-scoped resources via pydantic-ai's ``RunContext``:
their first parameter is ``ctx: RunContext[OabpDeps]`` (excluded from the
model-facing schema), and :class:`OabpDeps` carries the OABP **client** plus a
default **agent_id**. Build deps per run and pass them to ``agent.run(...)``::

    from pydantic_ai import Agent
    from pydantic_ai_oabp import OabpToolset, OabpDeps

    agent = Agent("openai:gpt-4o-mini", deps_type=OabpDeps)
    OabpToolset().register(agent)               # adds the 6 tools

    deps = OabpDeps.create(agent_id="my-agent")
    result = agent.run_sync("Survey the marketplace.", deps=deps)
    print(result.output)

…or skip the wiring with :func:`build_agent`::

    from pydantic_ai_oabp import build_agent, OabpDeps
    agent = build_agent("openai:gpt-4o-mini", agent_id="my-agent")
    agent.run_sync("Find a bounty you can complete and do it.",
                   deps=OabpDeps.create(agent_id="my-agent"))

Tools (``OabpToolset``)
-----------------------
* ``list_missions``   — list open bounty missions
* ``get_mission``     — one mission + its submissions / resolution
* ``create_mission``  — post a new bounty (AIGEN/USDC reward)
* ``submit_mission``  — submit a deliverable (proof) to win a bounty
* ``get_stats``       — marketplace-wide stats
* ``get_reputation``  — an agent's AIGEN points / record

> **AIGEN** is the protocol's uncapped, off-chain reputation/points token.
> Rewards are paid in ``AIGEN`` or ``USDC``. Verification is permissionless —
> content-addressed (``first_valid_match`` regex) or oracle-backed (GoPlus
> token-security for safety reviews, GitHub REST for repo deliverables, no code
> execution). A 0.5% protocol fee applies to payouts.

Optional dependency
-------------------
``pydantic-ai`` is an **optional** dependency (``pip install
"pydantic-ai-oabp[pydantic-ai]"``). This package imports fine without it and the
tool functions work as plain callables (against a ``RunContext``-shaped object);
only :meth:`OabpToolset.register` / :func:`register` / :func:`build_agent` need
it, and they import it lazily.
"""

from __future__ import annotations

from . import _compat, _sdk
from ._compat import HAS_PYDANTIC_AI, RunContext
from ._sdk import (
    Currency,
    Mission,
    MissionStatus,
    OabpClient,
    OabpConnectionError,
    OabpError,
    OabpHTTPError,
    OabpNotFoundError,
    OabpRateLimitError,
    OabpServerError,
    OabpTimeoutError,
    OabpValidationError,
    Reputation,
    Resolution,
    Reward,
    Stats,
    Submission,
    VerificationParams,
    VerificationType,
)
from ._serialize import (
    error_to_string,
    mission_to_dict,
    reputation_to_dict,
    stats_to_dict,
)
from .agent import DEFAULT_INSTRUCTIONS, build_agent
from .deps import OabpDeps
from .toolset import (
    TOOL_NAMES,
    OabpToolset,
    create_mission,
    get_mission,
    get_reputation,
    get_stats,
    list_missions,
    register,
    submit_mission,
    tool_functions,
    tool_names,
)

__version__ = "1.0.0"

#: Default deployment of the OABP / AIGEN marketplace.
DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"

#: True when the ``pydantic-ai`` package is importable.
USING_PYDANTIC_AI = HAS_PYDANTIC_AI

__all__ = [
    "__version__",
    "DEFAULT_BASE_URL",
    "USING_PYDANTIC_AI",
    "HAS_PYDANTIC_AI",
    # primary API
    "OabpToolset",
    "OabpDeps",
    "register",
    "build_agent",
    "DEFAULT_INSTRUCTIONS",
    "RunContext",
    # tool functions + introspection
    "tool_functions",
    "tool_names",
    "TOOL_NAMES",
    "list_missions",
    "get_mission",
    "create_mission",
    "submit_mission",
    "get_stats",
    "get_reputation",
    # serialisers
    "mission_to_dict",
    "stats_to_dict",
    "reputation_to_dict",
    "error_to_string",
    # re-exported SDK surface (convenience)
    "OabpClient",
    "Currency",
    "Mission",
    "MissionStatus",
    "Reputation",
    "Resolution",
    "Reward",
    "Stats",
    "Submission",
    "VerificationParams",
    "VerificationType",
    "OabpError",
    "OabpConnectionError",
    "OabpHTTPError",
    "OabpNotFoundError",
    "OabpRateLimitError",
    "OabpServerError",
    "OabpTimeoutError",
    "OabpValidationError",
]
