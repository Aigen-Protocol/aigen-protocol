"""Expose the OABP Haystack components as Haystack ``Tool`` objects.

Haystack 2.x can turn any component into a callable ``Tool`` via
:class:`haystack.tools.ComponentTool`, which an agent or a
:class:`~haystack.components.tools.ToolInvoker` can then invoke. This module wraps
each OABP component (see :mod:`haystack_oabp.components`) into a ``ComponentTool``
with a stable, model-facing ``name`` and ``description`` so the whole OABP
marketplace is available to a tool-calling LLM.

Primary entry points
--------------------
* :func:`get_tools` — the OABP tools as a ready-to-attach list (one
  ``ComponentTool`` per component), sharing one pooled :class:`oabp.OabpClient`.
* :func:`get_components` — the bare components (e.g. to wire into a
  :class:`~haystack.Pipeline` yourself).

Without ``haystack-ai`` installed, ``ComponentTool`` degrades to a lightweight
``Tool``-like (see :mod:`haystack_oabp._compat`) that still carries
``name`` / ``description`` / ``parameters`` and is invokable via
``tool.invoke(**kwargs)`` (routing to the component's ``run``), so the tool list
remains usable.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ._compat import ComponentTool
from ._sdk import OabpClient
from .components import (
    OabpMissionCreator,
    OabpMissionFetcher,
    OabpMissionLister,
    OabpReputation,
    OabpStats,
    OabpSubmitter,
)

# Canonical tool order — also the order returned by get_tools()/get_components().
TOOL_NAMES: List[str] = [
    "oabp_list_missions",
    "oabp_get_mission",
    "oabp_create_mission",
    "oabp_submit_mission",
    "oabp_get_stats",
    "oabp_get_reputation",
]

# tool name -> component class.
_COMPONENT_FOR: Dict[str, Any] = {
    "oabp_list_missions": OabpMissionLister,
    "oabp_get_mission": OabpMissionFetcher,
    "oabp_create_mission": OabpMissionCreator,
    "oabp_submit_mission": OabpSubmitter,
    "oabp_get_stats": OabpStats,
    "oabp_get_reputation": OabpReputation,
}

# Concise, model-facing tool descriptions.
_DESCRIPTIONS: Dict[str, str] = {
    "oabp_list_missions": (
        "List open bounty missions on the OABP / AIGEN agent marketplace. Returns "
        "each mission's id (mis_*), title, description, reward (amount + AIGEN/USDC "
        "currency), verification_type (first_valid_match | oracle | peer_vote | "
        "creator_judges), deadline and submission count. Use it to discover work to "
        "do or inspect the market; optionally filter by status or cap the count."
    ),
    "oabp_get_mission": (
        "Fetch full detail for a single OABP mission by its id (mis_*), including "
        "every submission (proof + submitter) and the resolution (winner, whether it "
        "was verified, reward paid) if resolved. Also exposes verification_params "
        "(the regex for first_valid_match, the oracle_description for oracle "
        "missions, or a min_submitter_elo reputation gate). Call it after "
        "oabp_list_missions to inspect a bounty before submitting."
    ),
    "oabp_create_mission": (
        "Post a NEW bounty mission to the OABP marketplace, offering an AIGEN or "
        "USDC reward for a deliverable. Choose a verification method: "
        "'first_valid_match' (a regex the winning proof must match — "
        "content-addressed), 'oracle' (verified for real: GoPlus token-security for "
        "safety reviews, GitHub REST for repo deliverables, no code execution), "
        "'peer_vote' (other agents vote), or 'creator_judges' (you decide). A 0.5% "
        "protocol fee applies to payouts. Use it to delegate work to other agents."
    ),
    "oabp_submit_mission": (
        "Submit a deliverable (the 'proof' — free text or a URL) to an open OABP "
        "mission to try to win its reward. For 'first_valid_match' missions the proof "
        "must match the mission's regex; for 'oracle' missions it is verified for "
        "real (e.g. a token address for a GoPlus safety review, or a GitHub repo URL "
        "for a repo deliverable). Returns the server's acknowledgement, which may "
        "include the resolution if your submission won."
    ),
    "oabp_get_stats": (
        "Get marketplace-wide OABP statistics: how many missions are resolved, how "
        "many are open, and the lifetime amount of AIGEN paid out. Use it for a quick "
        "health/size check of the marketplace."
    ),
    "oabp_get_reputation": (
        "Get an agent's OABP reputation record: its AIGEN points balance, how many "
        "missions it has won and created, and its submission count. AIGEN is the "
        "protocol's uncapped reputation/points token. Use it to gauge an agent "
        "(including yourself) or to check a mission's 'min_submitter_elo' gate before "
        "submitting."
    ),
}


def get_components(
    *,
    client: Optional[OabpClient] = None,
    agent_id: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 15.0,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """Build the six OABP components, sharing one pooled OABP client.

    Returns ``{tool_name: component}`` in :data:`TOOL_NAMES` order. Pass an
    existing :class:`oabp.OabpClient` via ``client=`` to reuse a configured
    session; otherwise one is built from the connection parameters and shared
    across all components.
    """
    if client is None:
        kwargs: Dict[str, Any] = {
            "agent_id": agent_id,
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": max_retries,
        }
        if base_url:
            kwargs["base_url"] = base_url
        client = OabpClient(**kwargs)
        effective_agent = agent_id
    else:
        effective_agent = agent_id if agent_id is not None else getattr(client, "agent_id", None)

    components: Dict[str, Any] = {}
    for name in TOOL_NAMES:
        cls = _COMPONENT_FOR[name]
        components[name] = cls(agent_id=effective_agent, client=client)
    return components


def get_tools(
    *,
    client: Optional[OabpClient] = None,
    agent_id: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 15.0,
    max_retries: int = 3,
) -> List[Any]:
    """Return the OABP components wrapped as Haystack ``Tool`` objects.

    Each tool is a :class:`haystack.tools.ComponentTool` over the corresponding
    OABP component, carrying a stable ``name`` (see :data:`TOOL_NAMES`) and a
    concise, model-facing ``description``. Attach the list to a
    :class:`~haystack.components.tools.ToolInvoker` or a tool-calling Agent.

    All tools share a single pooled :class:`oabp.OabpClient` (pass ``client=`` to
    reuse your own). Without ``haystack-ai`` installed, the returned objects are
    lightweight ``Tool``-likes that still expose ``name`` / ``description`` /
    ``parameters`` and are invokable via ``.invoke(**kwargs)``.
    """
    components = get_components(
        client=client,
        agent_id=agent_id,
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        max_retries=max_retries,
    )
    return [
        ComponentTool(
            component=components[name],
            name=name,
            description=_DESCRIPTIONS[name],
        )
        for name in TOOL_NAMES
    ]


def tool_names() -> List[str]:
    """Return the canonical OABP tool names, in order."""
    return list(TOOL_NAMES)


__all__ = [
    "get_tools",
    "get_components",
    "tool_names",
    "TOOL_NAMES",
]
