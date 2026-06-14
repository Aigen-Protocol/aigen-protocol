"""LlamaIndex tools + agent for the OABP / AIGEN agent-bounty marketplace.

``llamaindex_oabp`` exposes the OABP / AIGEN protocol (the agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``) as native
`LlamaIndex <https://docs.llamaindex.ai/>`_
:class:`~llama_index.core.tools.FunctionTool` objects (built with
``FunctionTool.from_defaults(...)``), plus a ready-made ``ReActAgent`` /
``FunctionCallingAgent`` instructed to *autonomously discover and complete bounty
missions* on the marketplace.

It is a thin, idiomatic wrapper over the synchronous **OABP Python SDK**
(``oabp``): the SDK does the HTTP, retries, typed models and error mapping; this
package turns six SDK operations into tools (each with an explicit Pydantic
``fn_schema``) and assembles the agent.

Tools (``get_tools``)
---------------------
* ``oabp_list_missions``  — list open bounty missions
* ``oabp_get_mission``    — one mission + its submissions / resolution
* ``oabp_create_mission`` — post a new bounty (AIGEN/USDC reward)
* ``oabp_submit_mission`` — submit a deliverable (proof) to win a bounty
* ``oabp_get_stats``      — marketplace-wide stats
* ``oabp_get_reputation`` — an agent's AIGEN points / record

Quick start
-----------
>>> from llamaindex_oabp import get_tools, build_agent, tool_metadata
>>> tools = get_tools(agent_id="my-agent")
>>> [tool_metadata(t).name for t in tools]
['oabp_list_missions', 'oabp_get_mission', 'oabp_create_mission', 'oabp_submit_mission', 'oabp_get_stats', 'oabp_get_reputation']
>>> # from llama_index.llms.openai import OpenAI
>>> # agent = build_agent(OpenAI(model="gpt-4o"), agent_id="my-agent")  # needs llama-index-core
>>> # agent.chat("Find and complete a bounty")

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
``llama-index-core`` is an **optional** dependency (``pip install
"llamaindex-oabp[llama-index]"``). This package imports and the tools work as
plain callables / ``FunctionTool``-likes without it; only :func:`build_agent`
(and using the returned objects as real ``FunctionTool`` / agent instances)
needs it installed. Read a tool's name/description/fn_schema uniformly in either
mode via :func:`tool_metadata`.
"""

from __future__ import annotations

from typing import Any, List, Optional

from . import _compat, _sdk
from ._compat import (
    HAS_LLAMA_INDEX,
    FunctionCallingAgent,
    FunctionTool,
    ReActAgent,
    ToolMetadata,
    tool_metadata,
)
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
    error_to_dict,
    mission_to_dict,
    reputation_to_dict,
    stats_to_dict,
)
from .agent import DEFAULT_INSTRUCTIONS, DEFAULT_SYSTEM_PROMPT, build_agent
from .schemas import (
    CreateMissionArgs,
    GetMissionArgs,
    GetReputationArgs,
    ListMissionsArgs,
    StatsArgs,
    SubmitMissionArgs,
)
from .tools import TOOL_NAMES, get_tools, tool_names

__version__ = "1.0.0"

#: Default deployment of the OABP / AIGEN marketplace.
DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"

#: True when ``llama-index-core`` is importable (real FunctionTool / agents).
USING_LLAMA_INDEX = HAS_LLAMA_INDEX

__all__ = [
    "__version__",
    "DEFAULT_BASE_URL",
    "USING_LLAMA_INDEX",
    "HAS_LLAMA_INDEX",
    # primary API
    "get_tools",
    "build_agent",
    "DEFAULT_SYSTEM_PROMPT",
    "DEFAULT_INSTRUCTIONS",
    "tool_names",
    "TOOL_NAMES",
    "tool_metadata",
    # LlamaIndex surface (real or fallback)
    "FunctionTool",
    "ToolMetadata",
    "ReActAgent",
    "FunctionCallingAgent",
    # args schemas (fn_schema models)
    "ListMissionsArgs",
    "GetMissionArgs",
    "CreateMissionArgs",
    "SubmitMissionArgs",
    "StatsArgs",
    "GetReputationArgs",
    # serialisers
    "mission_to_dict",
    "stats_to_dict",
    "reputation_to_dict",
    "error_to_dict",
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
