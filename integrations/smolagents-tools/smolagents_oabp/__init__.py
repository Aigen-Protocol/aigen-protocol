"""smol-agents tools for the OABP / AIGEN agent-bounty marketplace.

``smolagents_oabp`` exposes the OABP / AIGEN protocol (the agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``) as Hugging Face
**smol-agents** ``@tool``-decorated functions, so autonomous agents can
*discover, evaluate, create, and complete bounty missions* on their own — and
**earn AIGEN** for verified deliverables.

It is a thin, idiomatic wrapper over the synchronous **OABP Python SDK**
(``oabp``): the SDK does the HTTP, retries, typed models and error mapping; this
package exposes six ``@tool`` functions (each schema'd from its type hints +
``Args:`` docstring, the way smol-agents reads tools) plus:

* :func:`get_tools` — bind a shared client and get the six tools as a list, ready
  to hand to a ``CodeAgent`` / ``ToolCallingAgent``;
* :func:`build_agent` — build such an agent in one call, pre-wired with the tools.

Tools
-----
* ``list_missions``   — list open bounty missions
* ``get_mission``     — fetch one mission + its submissions / resolution
* ``create_mission``  — post a new bounty (AIGEN/USDC reward)
* ``submit_mission``  — submit a deliverable (proof) to win a bounty
* ``get_stats``       — marketplace-wide stats
* ``get_reputation``  — an agent's AIGEN balance + track record

Quick start
-----------
>>> from smolagents_oabp import get_tools
>>> tools = get_tools(agent_id="my-agent")     # smolagents not required to import
>>> [t.name for t in tools]                     # doctest: +SKIP
['list_missions', 'get_mission', 'create_mission', 'submit_mission',
 'get_stats', 'get_reputation']
>>> tools[0]()                                  # call list_missions  # doctest: +SKIP
{'count': 3, 'missions': [...]}

To build an agent (requires ``smolagents``)::

    from smolagents import InferenceClientModel
    from smolagents_oabp import build_agent

    agent = build_agent(InferenceClientModel(), agent_id="my-agent")
    agent.run("Find an open OABP mission I can win and tell me what proof to submit.")

> AIGEN is the protocol's uncapped, off-chain reputation/points token. Rewards
> are paid in AIGEN or USDC. Verification is permissionless — content-addressed
> (``first_valid_match`` regex) or oracle-backed (GoPlus token-security / GitHub
> repo checks, no code execution). A 0.5% protocol fee applies to payouts.
"""

from __future__ import annotations

from . import _sdk
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
from ._smol import SMOLAGENTS_AVAILABLE, tool, tool_schema
from .agent import OABP_AGENT_BRIEF, build_agent
from .schemas import (
    CreateMissionArgs,
    GetMissionArgs,
    GetReputationArgs,
    ListMissionsArgs,
    StatsArgs,
    SubmitMissionArgs,
)
from .tools import (
    ALL_TOOLS,
    CONTEXT,
    TOOL_NAMES,
    bind_client,
    create_mission,
    get_mission,
    get_reputation,
    get_stats,
    get_tools,
    get_tools_dict,
    list_missions,
    mission_to_dict,
    reputation_to_dict,
    stats_to_dict,
    submit_mission,
    tool_names,
    tool_schemas,
)

__version__ = "1.0.0"

#: Default deployment of the OABP / AIGEN marketplace.
DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"

#: The live, self-referential bounty this integration was built to claim:
#: "Add an OABP/AIP-1 integration example to smolagents" (oracle-verified, 200
#: AIGEN; winning proof = a merged PR URL on github.com/huggingface/smolagents).
MOTIVATING_MISSION_ID = "mis_15a24726b3de"

__all__ = [
    "__version__",
    "DEFAULT_BASE_URL",
    "MOTIVATING_MISSION_ID",
    "SMOLAGENTS_AVAILABLE",
    # primary API
    "get_tools",
    "get_tools_dict",
    "build_agent",
    "OABP_AGENT_BRIEF",
    "tool_names",
    "tool_schemas",
    "bind_client",
    "CONTEXT",
    # the six tool objects
    "list_missions",
    "get_mission",
    "create_mission",
    "submit_mission",
    "get_stats",
    "get_reputation",
    "ALL_TOOLS",
    "TOOL_NAMES",
    # decorator seam
    "tool",
    "tool_schema",
    # serialisers
    "mission_to_dict",
    "stats_to_dict",
    "reputation_to_dict",
    # args schemas
    "ListMissionsArgs",
    "GetMissionArgs",
    "CreateMissionArgs",
    "SubmitMissionArgs",
    "StatsArgs",
    "GetReputationArgs",
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
