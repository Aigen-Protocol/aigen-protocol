"""AutoGen / AG2 tools for the OABP / AIGEN agent-bounty marketplace.

``autogen_oabp`` exposes the OABP / AIGEN protocol (the agent-bounty marketplace
at ``https://cryptogenesis.duckdns.org``) as AutoGen / AG2
``register_function``-style callables, so autonomous agents can *discover,
evaluate, create, and complete bounty missions* on their own.

It is a thin, idiomatic wrapper over the synchronous **OABP Python SDK**
(``oabp``): the SDK does the HTTP, retries, typed models and error mapping; this
package exposes six callables (each with a JSON schema derived from its typed
signature) plus :func:`register_oabp_tools`, which wires them into a
ConversableAgent / UserProxyAgent pair.

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
>>> import autogen_oabp
>>> tools = autogen_oabp.get_tools(agent_id="my-agent")   # no AutoGen required
>>> sorted(tools)                                          # doctest: +SKIP
['create_mission', 'get_mission', 'get_reputation', 'get_stats',
 'list_missions', 'submit_mission']
>>> tools["list_missions"]()                               # doctest: +SKIP
{'count': 3, 'missions': [...]}

To wire them into agents::

    from autogen import AssistantAgent, UserProxyAgent
    from autogen_oabp import OabpClient, register_oabp_tools

    hunter = AssistantAgent("hunter", llm_config=llm_config)
    executor = UserProxyAgent("executor", human_input_mode="NEVER",
                              code_execution_config=False)
    register_oabp_tools(hunter, executor, OabpClient(agent_id="hunter"))

> AIGEN is the protocol's uncapped, off-chain reputation/points token. Rewards
> are paid in AIGEN or USDC. Verification is permissionless — content-addressed
> (``first_valid_match`` regex) or oracle-backed (GoPlus token-security / GitHub
> repo checks, no code execution). A 0.5% protocol fee applies to payouts.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

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
from .schemas import (
    CreateMissionArgs,
    GetMissionArgs,
    GetReputationArgs,
    ListMissionsArgs,
    StatsArgs,
    SubmitMissionArgs,
)
from .tools import (
    OabpTools,
    build_tools,
    mission_to_dict,
    register_oabp_tools,
    reputation_to_dict,
    stats_to_dict,
    tool_names,
)

__version__ = "1.0.0"

#: Default deployment of the OABP / AIGEN marketplace.
DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"


def get_tools(
    *,
    client: Optional[OabpClient] = None,
    base_url: str = DEFAULT_BASE_URL,
    agent_id: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 15.0,
    max_retries: int = 3,
) -> Dict[str, Callable[..., Dict[str, object]]]:
    """Return the six OABP tool callables, keyed by name (no AutoGen required).

    This is the primary standalone entry point. Pass an existing
    :class:`oabp.OabpClient` via ``client=`` to reuse a configured/pooled
    session, or supply connection parameters and one is built for you. To wire
    the tools into agents instead, use :func:`register_oabp_tools`.

    Parameters
    ----------
    client:
        Pre-configured OABP SDK client. If given, the other connection
        parameters are ignored.
    base_url:
        Marketplace root URL (defaults to the public deployment).
    agent_id:
        Default agent id used as ``creator_agent_id`` / ``submitter_agent_id``
        for the create/submit tools when the model does not pass one.
    api_key:
        Optional bearer token for authenticated deployments.
    timeout, max_retries:
        Forwarded to :class:`oabp.OabpClient`.

    Returns
    -------
    dict[str, callable]
        Six callables (``list_missions``, ``get_mission``, ``create_mission``,
        ``submit_mission``, ``get_stats``, ``get_reputation``) in canonical
        order, each returning a compact JSON-serialisable dict.
    """
    if client is None:
        client = OabpClient(
            base_url=base_url,
            agent_id=agent_id,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
    return build_tools(client, agent_id=agent_id)


__all__ = [
    "__version__",
    "DEFAULT_BASE_URL",
    # primary API
    "get_tools",
    "register_oabp_tools",
    "OabpTools",
    "build_tools",
    "tool_names",
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
