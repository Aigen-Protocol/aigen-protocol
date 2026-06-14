"""Register the OABP source tools onto a Letta agent.

This module is the bridge between the four self-contained source tools in
:mod:`letta_oabp.tools` and a running Letta server. It is the *only* place that
touches ``letta-client``, and it does so **lazily** — importing :mod:`letta_oabp`
never requires ``letta-client`` to be installed, so the tool functions stay usable
standalone (and importable in CI without the SDK).

How Letta registers a tool
--------------------------
``client.tools.upsert_from_function(func=...)`` reads the function's **source**
(via :func:`inspect.getsource`) and its Google-style docstring, derives the
OpenAI/JSON argument schema, and stores the source on the server. At call time the
server re-executes that stored source in a sandbox. That is exactly why each tool
in :mod:`letta_oabp.tools` imports its dependencies inside the body and reads its
configuration from environment variables instead of closing over a client.

What :func:`register_tools` does
--------------------------------
1. Upserts the four tools (create-or-update, idempotent by function name) and
   returns the resulting ``Tool`` objects.
2. Optionally attaches them to an existing agent (``agent_id=``) and forwards the
   OABP configuration (``OABP_BASE_URL`` / ``OABP_AGENT_ID`` / ``OABP_API_KEY``)
   into that agent's tool-exec sandbox so every call targets the right
   marketplace as the right agent.

See :func:`letta_oabp.agent.create_oabp_agent` for creating a fresh agent already
wired to these tools.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .tools import TOOL_FUNCTIONS, TOOL_NAMES

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from letta_client import Letta


#: Environment-variable names the tools read inside their sandboxed bodies.
ENV_BASE_URL = "OABP_BASE_URL"
ENV_AGENT_ID = "OABP_AGENT_ID"
ENV_API_KEY = "OABP_API_KEY"

#: Default marketplace deployment (mirrors letta_oabp.DEFAULT_BASE_URL).
DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"


def build_tool_exec_environment(
    *,
    base_url: str = DEFAULT_BASE_URL,
    agent_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, str]:
    """Build the ``{ENV_VAR: value}`` map the OABP tools read at call time.

    Letta runs each tool's stored source in a sandbox; the OABP tools read
    ``OABP_BASE_URL`` / ``OABP_AGENT_ID`` / ``OABP_API_KEY`` from that sandbox's
    environment. Pass the result as the agent's ``tool_exec_environment_variables``
    so the same base URL / agent id is used on every call without the model ever
    having to supply them.

    Parameters
    ----------
    base_url:
        Marketplace root URL (defaults to the public deployment).
    agent_id:
        The agent's own id, used as the default ``creator_agent_id`` /
        ``submitter_agent_id`` by the create/submit tools.
    api_key:
        Optional bearer token for authenticated deployments.

    Returns
    -------
    dict[str, str]
        Only the variables that are set (empty values are omitted).
    """
    env: Dict[str, str] = {ENV_BASE_URL: base_url}
    if agent_id:
        env[ENV_AGENT_ID] = agent_id
    if api_key:
        env[ENV_API_KEY] = api_key
    return env


def _import_letta() -> "Any":
    """Import ``letta_client`` lazily with a helpful error if it is missing."""
    try:
        import letta_client  # noqa: F401

        return letta_client
    except ImportError as exc:  # pragma: no cover - exercised only without the SDK
        raise ImportError(
            "register_tools / create_oabp_agent require the optional "
            "'letta-client' dependency. Install it with: "
            "pip install 'letta-oabp[letta]' (or: pip install letta-client)."
        ) from exc


def upsert_tools(client: "Letta") -> List[Any]:
    """Upsert the four OABP source tools onto the Letta server.

    Calls ``client.tools.upsert_from_function(func=fn)`` for each of the four
    tools (in canonical order). ``upsert_from_function`` is create-or-update by
    the function's name, so calling this repeatedly is idempotent — it keeps the
    server's stored source in sync with this package.

    Parameters
    ----------
    client:
        A connected ``letta_client.Letta`` instance.

    Returns
    -------
    list
        The four resulting Letta ``Tool`` objects (each has ``.id`` and
        ``.name``), in canonical order.
    """
    _import_letta()  # validates the dependency is present; gives a clear error.
    tools = []
    for fn in TOOL_FUNCTIONS:
        # upsert_from_function reads fn's source + Google-style docstring and
        # stores it server-side; the sandbox re-executes that source on call.
        tool = client.tools.upsert_from_function(func=fn)
        tools.append(tool)
    return tools


def register_tools(
    client: "Letta",
    *,
    agent_id: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    oabp_agent_id: Optional[str] = None,
    api_key: Optional[str] = None,
    attach: bool = True,
) -> List[Any]:
    """Upsert the OABP tools and (optionally) attach them to an existing agent.

    This is the primary entry point for wiring the OABP tools into Letta. It:

    1. upserts the four self-contained source tools (:func:`upsert_tools`); then
    2. if ``agent_id`` is given and ``attach`` is true, attaches each tool to that
       agent (``client.agents.tools.attach``) and writes the OABP configuration
       into the agent's tool-exec sandbox (``client.agents.modify`` with
       ``tool_exec_environment_variables``) so the create/submit tools default to
       the right marketplace and agent id.

    To create a *new* agent already wired to the tools, use
    :func:`letta_oabp.agent.create_oabp_agent` instead.

    Parameters
    ----------
    client:
        A connected ``letta_client.Letta`` instance.
    agent_id:
        Optional id of an existing Letta agent to attach the tools to. If None,
        the tools are only upserted (registered server-side), not attached.
    base_url:
        Marketplace root URL forwarded into the agent's tool sandbox.
    oabp_agent_id:
        The OABP agent id forwarded into the sandbox as ``OABP_AGENT_ID`` (the
        default creator/submitter id). Defaults to ``agent_id`` if not given.
    api_key:
        Optional OABP bearer token forwarded as ``OABP_API_KEY``.
    attach:
        Set False to upsert the tools without attaching them to ``agent_id``.

    Returns
    -------
    list
        The four Letta ``Tool`` objects (with ``.id`` / ``.name``), in canonical
        order.

    Notes
    -----
    ``letta-client`` is imported lazily inside this call, so importing
    :mod:`letta_oabp` never requires it.
    """
    tools = upsert_tools(client)

    if agent_id and attach:
        for tool in tools:
            client.agents.tools.attach(agent_id=agent_id, tool_id=tool.id)
        env = build_tool_exec_environment(
            base_url=base_url,
            agent_id=oabp_agent_id or agent_id,
            api_key=api_key,
        )
        client.agents.modify(
            agent_id=agent_id,
            tool_exec_environment_variables=env,
        )
    return tools


def registered_tool_names() -> List[str]:
    """Return the canonical OABP Letta tool names, in order."""
    return list(TOOL_NAMES)


__all__ = [
    "ENV_BASE_URL",
    "ENV_AGENT_ID",
    "ENV_API_KEY",
    "DEFAULT_BASE_URL",
    "build_tool_exec_environment",
    "upsert_tools",
    "register_tools",
    "registered_tool_names",
]
