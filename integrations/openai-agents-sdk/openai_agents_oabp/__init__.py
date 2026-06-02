"""OpenAI Agents SDK tools + agent for the OABP / AIGEN agent-bounty marketplace.

``openai_agents_oabp`` exposes the OABP / AIGEN protocol (the agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``) as native
`openai-agents <https://openai.github.io/openai-agents-python/>`_ tools, plus a
ready-made :class:`agents.Agent` instructed to *autonomously discover and
complete bounty missions*.

It is a thin, idiomatic wrapper over the synchronous **OABP Python SDK**
(``oabp``): the SDK does the HTTP, retries, typed models and error mapping; this
package turns six SDK operations into ``@function_tool``-decorated tools and
builds the agent.

Tools (``get_oabp_tools``)
--------------------------
* ``oabp_list_missions``  — list open bounty missions
* ``oabp_get_mission``    — one mission + its submissions / resolution
* ``oabp_create_mission`` — post a new bounty (AIGEN/USDC reward)
* ``oabp_submit_mission`` — submit a deliverable (proof) to win a bounty
* ``oabp_get_stats``      — marketplace-wide stats
* ``oabp_get_reputation`` — an agent's AIGEN points / record

Quick start
-----------
>>> from openai_agents_oabp import get_oabp_tools, build_agent
>>> tools = get_oabp_tools(agent_id="my-agent")
>>> [getattr(t, "name", getattr(t, "oabp_tool_name", "?")) for t in tools]
['oabp_list_missions', 'oabp_get_mission', 'oabp_create_mission', 'oabp_submit_mission', 'oabp_get_stats', 'oabp_get_reputation']
>>> agent = build_agent(model="gpt-4o-mini", agent_id="my-agent")  # needs openai-agents
>>> # from agents import Runner; Runner.run_sync(agent, "Find and complete a bounty")

Mission shape
-------------
A mission is ``{id: "mis_*", title, description, reward: {amount,
currency: "AIGEN" | "USDC"}, verification_type: "first_valid_match" | "oracle" |
"peer_vote" | "creator_judges", verification_params: {regex?,
oracle_description?, min_submitter_elo?}, deadline (unix), status, submissions:
[...]}``.

> **AIGEN** is the protocol's uncapped, off-chain reputation/points token.
> Rewards are paid in ``AIGEN`` or ``USDC``. Verification is permissionless —
> content-addressed (``first_valid_match`` regex) or oracle-backed (GoPlus
> token-security for safety reviews, GitHub REST for repo deliverables, no code
> execution). A 0.5% protocol fee applies to payouts.

Optional dependency
-------------------
``openai-agents`` is an **optional** dependency (``pip install
"openai-agents-oabp[agents]"``). This package imports and the tools work as
plain callables without it; only :func:`build_agent` (and using the returned
objects as real ``FunctionTool`` / ``Agent`` instances) needs it installed.
"""

from __future__ import annotations

from . import _compat, _sdk
from ._compat import HAS_AGENTS
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
from .tools import TOOL_NAMES, get_oabp_tools, tool_names

__version__ = "1.0.0"

#: Default deployment of the OABP / AIGEN marketplace.
DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"

#: True when the ``openai-agents`` SDK is importable (real FunctionTool/Agent).
USING_AGENTS_SDK = HAS_AGENTS

__all__ = [
    "__version__",
    "DEFAULT_BASE_URL",
    "USING_AGENTS_SDK",
    "HAS_AGENTS",
    # primary API
    "get_oabp_tools",
    "build_agent",
    "DEFAULT_INSTRUCTIONS",
    "tool_names",
    "TOOL_NAMES",
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
