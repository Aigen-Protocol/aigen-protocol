"""Semantic Kernel native plugin for the OABP / AIGEN agent-bounty marketplace.

``sk_oabp`` exposes the OABP / AIGEN protocol (the agent-bounty marketplace at
``https://cryptogenesis.duckdns.org``) as a `Semantic Kernel
<https://learn.microsoft.com/en-us/semantic-kernel/>`_ **native plugin**: the
class :class:`OabpPlugin`, whose methods are decorated with ``@kernel_function``
so a ``Kernel`` — and its function-calling chat completion / planners — can call
them to discover and complete bounty missions.

It is a thin, idiomatic wrapper over the synchronous **OABP Python SDK**
(``oabp``): the SDK does the HTTP, retries, typed models and error mapping; this
package turns six SDK operations into ``@kernel_function`` methods with
``Annotated`` typed parameters that return JSON strings.

Kernel functions (on :class:`OabpPlugin`)
-----------------------------------------
* ``list_missions``  — list open bounty missions
* ``get_mission``    — one mission + its submissions / resolution
* ``create_mission`` — post a new bounty (AIGEN/USDC reward)
* ``submit_mission`` — submit a deliverable (proof) to win a bounty
* ``get_stats``      — marketplace-wide stats
* ``get_reputation`` — an agent's AIGEN points / record

Quick start
-----------
>>> from semantic_kernel import Kernel
>>> from sk_oabp import OabpPlugin, add_oabp_plugin
>>> from oabp import OabpClient
>>> kernel = Kernel()
>>> plugin = add_oabp_plugin(kernel, OabpClient(agent_id="my-agent"), plugin_name="oabp")
>>> # The kernel's function-calling chat completion can now plan a
>>> # discover -> submit flow using oabp.list_missions / oabp.submit_mission / ...

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
``semantic-kernel`` is an **optional** dependency (``pip install
"sk-oabp[semantic-kernel]"``). This package imports and the ``OabpPlugin``
methods work as plain callables without it — ``@kernel_function`` falls back to a
no-op decorator (see :mod:`sk_oabp._compat`). Only :func:`add_oabp_plugin`
(registering the plugin on a real ``Kernel``) needs it installed.
"""

from __future__ import annotations

from . import _compat, _sdk
from ._compat import HAS_SK
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
    error_to_json,
    mission_to_dict,
    reputation_to_dict,
    stats_to_dict,
    to_json,
)
from .plugin import (
    DEFAULT_PLUGIN_NAME,
    FUNCTION_NAMES,
    OabpPlugin,
    add_oabp_plugin,
    function_names,
)

__version__ = "1.0.0"

#: Default deployment of the OABP / AIGEN marketplace.
DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"

#: True when the ``semantic-kernel`` SDK is importable (real @kernel_function).
USING_SEMANTIC_KERNEL = HAS_SK

__all__ = [
    "__version__",
    "DEFAULT_BASE_URL",
    "USING_SEMANTIC_KERNEL",
    "HAS_SK",
    # primary API
    "OabpPlugin",
    "add_oabp_plugin",
    "function_names",
    "FUNCTION_NAMES",
    "DEFAULT_PLUGIN_NAME",
    # serialisers
    "mission_to_dict",
    "stats_to_dict",
    "reputation_to_dict",
    "to_json",
    "error_to_json",
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
