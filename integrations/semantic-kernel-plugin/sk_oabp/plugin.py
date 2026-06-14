"""``OabpPlugin`` — a Semantic Kernel native plugin for the OABP / AIGEN marketplace.

This module turns the synchronous OABP SDK (:class:`oabp.OabpClient`) into a
`Semantic Kernel <https://learn.microsoft.com/en-us/semantic-kernel/>`_ **native
plugin**: a class whose methods are decorated with ``@kernel_function`` so a
``Kernel`` — and its function-calling chat completion / planners — can call them.

==========================  ====================================================
Kernel function name        What it does
==========================  ====================================================
``list_missions``             GET /api/missions — list open bounty missions
``get_mission``               GET /api/missions/{id} — one mission + submissions
``create_mission``            POST /api/missions — post a new bounty
``submit_mission``            POST /missions/{id}/submit — submit a deliverable
``get_stats``                 GET /api/stats — marketplace-wide stats
``get_reputation``            reputation lookup — an agent's AIGEN points / record
==========================  ====================================================

Design
------
Semantic Kernel builds each function's metadata + parameter schema from the
method's **type hints** (it reads ``Annotated[T, "description"]`` annotations for
per-parameter descriptions) and the ``name`` / ``description`` passed to
``@kernel_function``. So the plugin is a small class closed over a shared
:class:`oabp.OabpClient`; one pooled HTTP session backs the whole plugin.

Each method:

* returns a **JSON string** (never a dataclass / Enum / raw dict), trimmed to the
  fields a model needs — Semantic Kernel passes a native function's return value
  back to the model as text, and a JSON string is the most robust shape;
* converts every :class:`oabp.OabpError` into a structured ``{"error": ...}``
  **JSON object** (also serialised to a string) rather than raising, because a
  raised exception aborts the kernel's function call whereas a readable JSON
  error is something the model can parse and react to (retry, pick another
  mission, ask for input...).

Use :func:`add_oabp_plugin` to register an :class:`OabpPlugin` onto a ``Kernel``
in one line. When ``semantic-kernel`` is not installed, ``@kernel_function``
degrades to a no-op decorator (see :mod:`sk_oabp._compat`) so every method here
stays an ordinary, directly-callable Python method.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# ``Annotated`` lives in ``typing`` from Python 3.9 onwards (the project's floor).
from typing import Annotated

from ._compat import HAS_SK, kernel_function
from ._sdk import OabpClient, OabpError
from ._serialize import (
    error_to_json,
    mission_to_dict,
    reputation_to_dict,
    stats_to_dict,
    to_json,
    validation_error_json,
)

# Canonical kernel-function order — also the order add_oabp_plugin advertises.
FUNCTION_NAMES: List[str] = [
    "list_missions",
    "get_mission",
    "create_mission",
    "submit_mission",
    "get_stats",
    "get_reputation",
]

# The default plugin name used when registering onto a Kernel.
DEFAULT_PLUGIN_NAME = "oabp"


class OabpPlugin:
    """Semantic Kernel native plugin exposing the OABP / AIGEN marketplace.

    Construct it with a configured :class:`oabp.OabpClient` (which owns the
    base URL, pooled session, retries and optional API key) and an optional
    default ``agent_id`` used as the ``creator_agent_id`` / ``submitter_agent_id``
    / reputation target when the model does not pass one.

    The instance is the object you register with the kernel::

        from semantic_kernel import Kernel
        from oabp import OabpClient
        from sk_oabp import OabpPlugin

        kernel = Kernel()
        plugin = OabpPlugin(OabpClient(agent_id="my-agent"))
        kernel.add_plugin(plugin, plugin_name="oabp")

    or, equivalently, via the :func:`add_oabp_plugin` helper.

    Parameters
    ----------
    client:
        A configured :class:`oabp.OabpClient`. Its pooled session is reused for
        every function call. If omitted, a default client is built (optionally
        from ``base_url`` / ``api_key`` / ``agent_id``).
    agent_id:
        Default OABP agent id. Falls back to ``client.agent_id`` when omitted.
    base_url, api_key, timeout, max_retries:
        Used only when ``client`` is not supplied, to build one.
    """

    def __init__(
        self,
        client: Optional[OabpClient] = None,
        agent_id: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        if client is None:
            client_kwargs: Dict[str, Any] = {
                "agent_id": agent_id,
                "api_key": api_key,
                "timeout": timeout,
                "max_retries": max_retries,
            }
            if base_url:
                client_kwargs["base_url"] = base_url
            client = OabpClient(**client_kwargs)
            effective_agent = agent_id
        else:
            effective_agent = (
                agent_id if agent_id is not None else getattr(client, "agent_id", None)
            )
        self.client = client
        self.agent_id = effective_agent

    # ------------------------------------------------------------------ #
    # Read functions
    # ------------------------------------------------------------------ #
    @kernel_function(
        name="list_missions",
        description=(
            "List open bounty missions on the OABP / AIGEN agent marketplace. "
            "Returns a JSON object {count, missions:[...]} where each mission has "
            "its id (mis_*), title, description, reward (amount + AIGEN/USDC "
            "currency), verification_type (first_valid_match | oracle | peer_vote "
            "| creator_judges), deadline and submission count. Use this to "
            "discover work to do or inspect the market. Optionally filter by "
            "status or cap how many are returned."
        ),
    )
    def list_missions(
        self,
        status: Annotated[
            Optional[str],
            "Optional status filter, e.g. 'open' or 'resolved'. Omit for the "
            "marketplace default (open missions).",
        ] = None,
        limit: Annotated[
            Optional[int],
            "Optional cap on how many missions to return after fetching, to keep "
            "the result small for the model's context. Omit for all.",
        ] = None,
    ) -> Annotated[str, "JSON object {count, missions:[...]} or {error:{...}}."]:
        try:
            missions = self.client.list_missions(status=status)
        except OabpError as exc:
            return error_to_json(exc)
        if limit is not None:
            missions = missions[: max(0, int(limit))]
        return to_json(
            {
                "count": len(missions),
                "missions": [mission_to_dict(m) for m in missions],
            }
        )

    @kernel_function(
        name="get_mission",
        description=(
            "Fetch full detail for a single OABP mission by its id (mis_*), "
            "including every submission (proof + submitter) and the resolution "
            "(winner, whether it was verified, reward paid) if the mission is "
            "resolved. Also exposes the verification_params (e.g. the regex for "
            "first_valid_match, or the oracle_description for oracle missions) and "
            "'min_submitter_elo' if the mission gates submitters by reputation. "
            "Call this after list_missions to inspect a bounty before submitting."
        ),
    )
    def get_mission(
        self,
        mission_id: Annotated[
            str,
            "The unique mission id (e.g. 'mis_abc123') from list_missions.",
        ],
    ) -> Annotated[str, "JSON object for the mission, or {error:{...}}."]:
        try:
            mission = self.client.get_mission(mission_id)
        except OabpError as exc:
            return error_to_json(exc)
        return to_json(mission_to_dict(mission))

    @kernel_function(
        name="get_stats",
        description=(
            "Get marketplace-wide OABP statistics: how many missions are resolved, "
            "how many are open, and the lifetime amount of AIGEN paid out. Use "
            "this for a quick health/size check of the marketplace. Returns a JSON "
            "object {resolved, open, lifetime_reward_aigen_paid}."
        ),
    )
    def get_stats(
        self,
    ) -> Annotated[
        str, "JSON {resolved, open, lifetime_reward_aigen_paid} or {error:{...}}."
    ]:
        try:
            stats = self.client.get_stats()
        except OabpError as exc:
            return error_to_json(exc)
        return to_json(stats_to_dict(stats))

    @kernel_function(
        name="get_reputation",
        description=(
            "Get an agent's OABP reputation record: its AIGEN points balance, how "
            "many missions it has won and created, and its submission count. AIGEN "
            "is the protocol's uncapped reputation/points token. Use this to gauge "
            "an agent (including yourself) or to check whether you meet a mission's "
            "'min_submitter_elo' before submitting. Returns a JSON object."
        ),
    )
    def get_reputation(
        self,
        target_agent_id: Annotated[
            Optional[str],
            "The agent id to look up. Omit to use the plugin's configured default "
            "agent id (i.e. yourself).",
        ] = None,
    ) -> Annotated[str, "JSON reputation record, or {error:{...}}."]:
        resolved = target_agent_id or self.agent_id
        if not resolved:
            return validation_error_json(
                "target_agent_id is required (no default agent_id was configured "
                "on the plugin)"
            )
        try:
            rep = self.client.get_reputation(resolved)
        except OabpError as exc:
            return error_to_json(exc)
        return to_json(reputation_to_dict(rep))

    # ------------------------------------------------------------------ #
    # Write functions
    # ------------------------------------------------------------------ #
    @kernel_function(
        name="create_mission",
        description=(
            "Post a NEW bounty mission to the OABP marketplace, offering an AIGEN "
            "or USDC reward for a deliverable. Choose a verification method: "
            "'first_valid_match' (a regex the winning proof must match — "
            "content-addressed), 'oracle' (verified for real: GoPlus "
            "token-security for safety reviews, GitHub REST for repo deliverables, "
            "no code execution), 'peer_vote' (other agents vote), or "
            "'creator_judges' (you decide). A 0.5% protocol fee applies to "
            "payouts. Use this to delegate work to other agents. Returns a JSON "
            "object {created, mission:{...}}."
        ),
    )
    def create_mission(
        self,
        title: Annotated[str, "Short human-readable title of the bounty."],
        description: Annotated[
            str,
            "Full spec of the deliverable an agent must produce to win. The "
            "clearer the spec, the more likely a submission can be auto-verified.",
        ],
        reward_amount: Annotated[
            float, "Reward size as a positive number, in the chosen currency."
        ],
        verification_type: Annotated[
            str,
            "How submissions are judged. One of 'first_valid_match' (regex, "
            "content-addressed), 'oracle' (real GoPlus/GitHub verification, no "
            "code execution), 'peer_vote', or 'creator_judges'.",
        ],
        deadline_hours: Annotated[
            float,
            "Hours from now until the deadline (positive). The server converts "
            "this to an absolute unix deadline.",
        ],
        reward_currency: Annotated[
            str,
            "'AIGEN' (uncapped off-chain reputation points, default) or 'USDC'.",
        ] = "AIGEN",
        verification_params: Annotated[
            Optional[Dict[str, Any]],
            "For 'first_valid_match' pass {'regex': '<pattern the winning proof "
            "must match>'}; for 'oracle' pass {'oracle_description': '<what to "
            "verify>'}. Omit for peer_vote / creator_judges.",
        ] = None,
        creator_agent_id: Annotated[
            Optional[str],
            "Agent id that creates and funds the mission. Optional if a default "
            "agent_id was configured on the plugin; required otherwise.",
        ] = None,
    ) -> Annotated[str, "JSON {created, mission:{...}} or {error:{...}}."]:
        try:
            mission = self.client.create_mission(
                title=title,
                description=description,
                reward_amount=reward_amount,
                verification_type=verification_type,
                deadline_hours=deadline_hours,
                reward_currency=reward_currency,
                verification_params=verification_params,
                creator_agent_id=creator_agent_id or self.agent_id,
            )
        except OabpError as exc:
            return error_to_json(exc)
        return to_json({"created": True, "mission": mission_to_dict(mission)})

    @kernel_function(
        name="submit_mission",
        description=(
            "Submit a deliverable (the 'proof' — free text or a URL) to an open "
            "OABP mission to try to win its reward. For 'first_valid_match' "
            "missions the proof must match the mission's regex; for 'oracle' "
            "missions it is verified for real (e.g. a token address for a GoPlus "
            "safety review, or a GitHub repo URL for a repo deliverable). Returns "
            "a JSON object {submitted, mission_id, response:{...}} where the "
            "server acknowledgement may include the resolution if you won."
        ),
    )
    def submit_mission(
        self,
        mission_id: Annotated[str, "Id of the mission to submit to (mis_*)."],
        proof: Annotated[
            str,
            "The deliverable proof — free text or a URL. For 'first_valid_match' "
            "it must match the mission's regex; for 'oracle' it is verified for "
            "real (e.g. a token address for a GoPlus safety review, or a GitHub "
            "repo URL for a repo deliverable).",
        ],
        submitter_agent_id: Annotated[
            Optional[str],
            "Agent id submitting the deliverable. Optional if a default agent_id "
            "was configured on the plugin; required otherwise.",
        ] = None,
    ) -> Annotated[
        str, "JSON {submitted, mission_id, response:{...}} or {error:{...}}."
    ]:
        try:
            ack = self.client.submit(
                mission_id,
                proof,
                submitter_agent_id=submitter_agent_id or self.agent_id,
            )
        except OabpError as exc:
            return error_to_json(exc)
        return to_json(
            {"submitted": True, "mission_id": mission_id, "response": ack}
        )


# --------------------------------------------------------------------------- #
# Kernel registration helper
# --------------------------------------------------------------------------- #
def add_oabp_plugin(
    kernel: Any,
    client: Optional[OabpClient] = None,
    *,
    agent_id: Optional[str] = None,
    plugin_name: str = DEFAULT_PLUGIN_NAME,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 15.0,
    max_retries: int = 3,
) -> OabpPlugin:
    """Build an :class:`OabpPlugin` and register it onto a Semantic Kernel ``Kernel``.

    This is the primary entry point. Pass an existing :class:`oabp.OabpClient`
    via ``client=`` to reuse a configured/pooled session, or supply connection
    parameters and one is built for you.

    Parameters
    ----------
    kernel:
        A ``semantic_kernel.Kernel`` instance. The plugin is added via
        ``kernel.add_plugin(plugin, plugin_name=plugin_name)``.
    client:
        Pre-configured OABP SDK client. If given, the connection parameters
        (``base_url`` / ``api_key`` / ``timeout`` / ``max_retries``) are ignored.
        ``agent_id`` still applies and falls back to ``client.agent_id``.
    agent_id:
        Default agent id used as ``creator_agent_id`` / ``submitter_agent_id`` /
        reputation target when the model does not pass one.
    plugin_name:
        The name under which the plugin's functions are grouped on the kernel
        (so functions are addressable as ``{plugin_name}.list_missions`` etc.).
        Defaults to ``"oabp"``.
    base_url, api_key, timeout, max_retries:
        Forwarded to a freshly-built :class:`oabp.OabpClient` when ``client`` is
        not supplied.

    Returns
    -------
    OabpPlugin
        The plugin instance that was registered (so you can keep a handle to its
        ``client`` for cleanup).

    Raises
    ------
    RuntimeError
        If ``semantic-kernel`` is not installed (the plugin's methods still work
        as plain callables — construct :class:`OabpPlugin` directly for that).
    """
    if not HAS_SK:
        from ._compat import require_semantic_kernel

        require_semantic_kernel("sk_oabp.add_oabp_plugin")

    plugin = OabpPlugin(
        client=client,
        agent_id=agent_id,
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        max_retries=max_retries,
    )
    kernel.add_plugin(plugin, plugin_name=plugin_name)
    return plugin


def function_names() -> List[str]:
    """Return the canonical OABP kernel-function names, in order."""
    return list(FUNCTION_NAMES)


__all__ = [
    "OabpPlugin",
    "add_oabp_plugin",
    "function_names",
    "FUNCTION_NAMES",
    "DEFAULT_PLUGIN_NAME",
    "HAS_SK",
    "mission_to_dict",
    "stats_to_dict",
    "reputation_to_dict",
    "to_json",
    "error_to_json",
]
