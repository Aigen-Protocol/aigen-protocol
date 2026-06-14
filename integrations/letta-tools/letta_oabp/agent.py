"""Create a Letta agent pre-wired to the OABP / AIGEN tools.

:func:`create_oabp_agent` upserts the four OABP source tools and creates a fresh
Letta agent that has them attached, with a persona/human drawn from
``agent_config.json`` and the OABP configuration injected into the agent's
tool-exec sandbox. It is the one-call path from "nothing" to "an agent that can
discover, create and complete OABP bounties".

``letta-client`` is imported lazily (via :mod:`letta_oabp.register`), so importing
:mod:`letta_oabp` never requires the SDK.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .register import (
    DEFAULT_BASE_URL,
    build_tool_exec_environment,
    registered_tool_names,
    upsert_tools,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from letta_client import Letta


#: Path to the bundled agent config (persona / human / tool names).
AGENT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "agent_config.json")


def load_agent_config(path: Optional[str] = None) -> Dict[str, Any]:
    """Load and lightly validate the bundled (or a custom) agent config.

    Parameters
    ----------
    path:
        Path to an ``agent_config.json``. Defaults to the one bundled with this
        package (:data:`AGENT_CONFIG_PATH`).

    Returns
    -------
    dict
        The parsed config: ``name``, ``description``, ``model``, ``embedding``,
        ``memory_blocks`` (a list of ``{"label", "value"}``), ``system`` and
        ``tools`` (the OABP tool names).

    Raises
    ------
    ValueError
        If the config is missing required keys or lists fewer than the four OABP
        tools.
    """
    cfg_path = path or AGENT_CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    for key in ("memory_blocks", "tools", "model", "embedding"):
        if key not in cfg:
            raise ValueError("agent_config is missing required key %r" % (key,))
    if not isinstance(cfg["memory_blocks"], list) or not cfg["memory_blocks"]:
        raise ValueError("agent_config 'memory_blocks' must be a non-empty list")
    if not isinstance(cfg["tools"], list) or len(cfg["tools"]) < 4:
        raise ValueError("agent_config 'tools' must list at least the 4 OABP tools")
    return cfg


def create_oabp_agent(
    client: "Letta",
    *,
    config_path: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    oabp_agent_id: Optional[str] = None,
    api_key: Optional[str] = None,
    name: Optional[str] = None,
    model: Optional[str] = None,
    embedding: Optional[str] = None,
    include_base_tools: bool = True,
) -> Any:
    """Upsert the OABP tools and create a Letta agent wired to them.

    Steps:

    1. Load the persona/human + tool list from ``agent_config.json``
       (:func:`load_agent_config`).
    2. Upsert the four self-contained OABP source tools (:func:`upsert_tools`).
    3. Create a new agent via ``client.agents.create`` with the config's
       ``memory_blocks`` / ``system`` / ``model`` / ``embedding``, the OABP tools
       attached by name, and the OABP configuration injected into the agent's
       ``tool_exec_environment_variables`` sandbox.

    Parameters
    ----------
    client:
        A connected ``letta_client.Letta`` instance.
    config_path:
        Optional path to a custom ``agent_config.json`` (defaults to bundled).
    base_url:
        Marketplace root URL injected into the agent's tool sandbox.
    oabp_agent_id:
        The OABP agent id injected as ``OABP_AGENT_ID`` (default creator/submitter
        id). Defaults to the new Letta agent's name.
    api_key:
        Optional OABP bearer token injected as ``OABP_API_KEY``.
    name, model, embedding:
        Optional overrides for the corresponding config fields.
    include_base_tools:
        Whether to also give the agent Letta's base tools (send_message, memory
        edits, etc.). Defaults to True.

    Returns
    -------
    The created Letta agent state (has ``.id``, ``.name``, ``.tools``).

    Notes
    -----
    ``letta-client`` is imported lazily by :func:`upsert_tools`, so importing
    :mod:`letta_oabp` never requires the SDK.
    """
    cfg = load_agent_config(config_path)

    agent_name = name or cfg.get("name") or "oabp-agent"
    # The default OABP creator/submitter id is the agent's name unless overridden.
    effective_oabp_id = oabp_agent_id or agent_name

    # 1) + 2) Upsert the four tools server-side (also validates letta-client).
    upsert_tools(client)

    # 3) Forward the OABP config into the agent's tool-exec sandbox.
    env = build_tool_exec_environment(
        base_url=base_url,
        agent_id=effective_oabp_id,
        api_key=api_key,
    )

    agent = client.agents.create(
        name=agent_name,
        description=cfg.get("description"),
        model=model or cfg["model"],
        embedding=embedding or cfg["embedding"],
        memory_blocks=cfg["memory_blocks"],
        system=cfg.get("system"),
        tools=list(cfg["tools"]),  # attach the OABP tools by name
        include_base_tools=include_base_tools,
        tool_exec_environment_variables=env,
    )
    return agent


def oabp_tool_names() -> List[str]:
    """Return the canonical OABP Letta tool names, in order."""
    return registered_tool_names()


__all__ = [
    "AGENT_CONFIG_PATH",
    "load_agent_config",
    "create_oabp_agent",
    "oabp_tool_names",
]
