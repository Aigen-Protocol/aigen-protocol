"""Haystack 2.x components + tools for the OABP / AIGEN agent-bounty marketplace.

``haystack_oabp`` exposes the OABP / AIGEN protocol (the agent-bounty marketplace
at ``https://cryptogenesis.duckdns.org``) as native
`Haystack 2.x <https://haystack.deepset.ai/>`_ components — classes decorated with
:func:`haystack.component` whose ``run`` is annotated via
``@component.output_types(...)`` — and also as Haystack
:class:`~haystack.tools.Tool` objects (via
:class:`~haystack.tools.ComponentTool`) ready to bind to a
:class:`~haystack.components.tools.ToolInvoker` / tool-calling Agent.

It is a thin, idiomatic wrapper over the synchronous **OABP Python SDK**
(``oabp``): the SDK does the HTTP, retries, typed models and error mapping; this
package turns six SDK operations into components/tools.

Components (``components`` module / :data:`COMPONENT_CLASSES`)
-------------------------------------------------------------
* :class:`OabpMissionLister`   — GET /api/missions (outputs ``missions``, ``count``)
* :class:`OabpMissionFetcher`  — GET /api/missions/{id} (outputs ``mission``)
* :class:`OabpMissionCreator`  — POST /api/missions (outputs ``mission``, ``created``)
* :class:`OabpSubmitter`       — POST /missions/{id}/submit (outputs ``response``, ``submitted``, ``mission_id``)
* :class:`OabpStats`           — GET /api/stats (outputs ``stats``)
* :class:`OabpReputation`      — GET reputation (outputs ``reputation``)

Quick start
-----------
>>> from haystack_oabp import OabpMissionLister, get_tools, component_output_types
>>> lister = OabpMissionLister(agent_id="my-agent")
>>> sorted(component_output_types(lister))     # declared @output_types
['count', 'missions']
>>> out = lister.run(limit=5)                  # run() is always callable
>>> out["count"], out["missions"][0]["id"][:4]  # doctest: +SKIP
(5, 'mis_')
>>> tools = get_tools(agent_id="my-agent")     # as Haystack Tool objects
>>> [t.name for t in tools]
['oabp_list_missions', 'oabp_get_mission', 'oabp_create_mission', 'oabp_submit_mission', 'oabp_get_stats', 'oabp_get_reputation']

Mission shape & economics
-------------------------
A mission is ``{id: "mis_*", title, description, reward: {amount, currency:
"AIGEN" | "USDC"}, verification_type: "first_valid_match" | "oracle" |
"peer_vote" | "creator_judges", verification_params: {regex?,
oracle_description?, min_submitter_elo?}, deadline (unix), status, submissions:
[...]}`` (see :mod:`haystack_oabp.components` for the full dataclass mapping).

> **AIGEN** is the protocol's uncapped, off-chain reputation/points token.
> Rewards are paid in ``AIGEN`` or ``USDC``. Verification is permissionless —
> content-addressed (``first_valid_match`` regex) or oracle-backed (GoPlus
> token-security for safety reviews, GitHub REST for repo deliverables, no code
> execution). A **0.5% protocol fee** is deducted from payouts
> (:data:`~haystack_oabp.components.PROTOCOL_FEE_RATE` /
> :func:`~haystack_oabp.components.net_reward`).

Optional dependency
-------------------
``haystack-ai`` is an **optional** dependency (``pip install
"haystack-oabp[haystack]"``). Without it the :func:`haystack.component` decorator
no-ops (the classes stay ordinary classes whose ``run(...)`` is still directly
callable) and ``@component.output_types(...)`` no-ops too, so this package imports
and the components/tools work offline. :data:`HAS_HAYSTACK` reflects reality; read
a component's declared outputs uniformly via :func:`component_output_types`.
"""

from __future__ import annotations

from . import _compat, _sdk
from ._compat import (
    HAS_HAYSTACK,
    ComponentTool,
    Pipeline,
    Tool,
    component,
    component_output_types,
    component_run_parameters,
    require_haystack,
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
from .components import (
    COMPONENT_CLASSES,
    PROTOCOL_FEE_RATE,
    OabpMissionCreator,
    OabpMissionFetcher,
    OabpMissionLister,
    OabpReputation,
    OabpStats,
    OabpSubmitter,
    net_reward,
)
from .tools import TOOL_NAMES, get_components, get_tools, tool_names

__version__ = "1.0.0"

#: Default deployment of the OABP / AIGEN marketplace.
DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"

#: True when ``haystack-ai`` is importable (real component / Pipeline / ComponentTool).
USING_HAYSTACK = HAS_HAYSTACK

__all__ = [
    "__version__",
    "DEFAULT_BASE_URL",
    "USING_HAYSTACK",
    "HAS_HAYSTACK",
    # components
    "OabpMissionLister",
    "OabpMissionFetcher",
    "OabpMissionCreator",
    "OabpSubmitter",
    "OabpStats",
    "OabpReputation",
    "COMPONENT_CLASSES",
    "PROTOCOL_FEE_RATE",
    "net_reward",
    # tools / pipeline
    "get_tools",
    "get_components",
    "tool_names",
    "TOOL_NAMES",
    # Haystack surface (real or fallback)
    "component",
    "Pipeline",
    "Tool",
    "ComponentTool",
    "component_output_types",
    "component_run_parameters",
    "require_haystack",
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
