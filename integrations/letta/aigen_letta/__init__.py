"""AIGEN Letta integration — give Letta agents persistent memory of their
economic activity on AIGEN.

Letta (formerly MemGPT) provides agents with structured memory across sessions.
AIGEN agents accumulate economic state: AIGEN earnings, ELO reputation, missions
completed, on-chain wallet activity. This package surfaces all that as Letta
"core memory" or "archival memory" — so a Letta agent remembers its AIGEN
identity across runs.

Quick start:
    from letta import create_client
    from aigen_letta import attach_aigen_memory, get_aigen_tools

    client = create_client()
    agent_id = "my-letta-agent"
    attach_aigen_memory(client, agent_id, aigen_agent_id="my-letta-agent")
    tools = get_aigen_tools(client, aigen_agent_id="my-letta-agent")
"""
from .client import AigenClient, get_aigen_client
from .memory import attach_aigen_memory, refresh_aigen_memory
from .tools import (
    aigen_scan_token_tool,
    aigen_list_missions_tool,
    aigen_create_mission_tool,
    aigen_submit_to_mission_tool,
    aigen_get_my_reputation_tool,
    get_aigen_tools,
)

__version__ = "0.1.0"
__all__ = [
    "AigenClient", "get_aigen_client",
    "attach_aigen_memory", "refresh_aigen_memory",
    "aigen_scan_token_tool", "aigen_list_missions_tool",
    "aigen_create_mission_tool", "aigen_submit_to_mission_tool",
    "aigen_get_my_reputation_tool",
    "get_aigen_tools",
]
