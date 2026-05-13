"""AIGEN integration for OpenAI Agents SDK.

The OpenAI Agents SDK is a lightweight framework for multi-agent workflows.
This package exposes 5 AIGEN primitives as @function_tool decorators that
any OpenAI Agent can natively call.

Quick start:
    from agents import Agent, Runner
    from aigen_openai_agents import get_aigen_tools

    bounty_hunter = Agent(
        name="bounty-hunter",
        instructions="Find paid AIGEN missions and complete them",
        tools=get_aigen_tools(agent_id="my-bot"),
    )
    result = await Runner.run(bounty_hunter, input="Find a USDC mission and submit a proof.")
"""
from .client import AigenClient, get_aigen_client
from .tools import (
    aigen_scan_token,
    aigen_list_missions,
    aigen_create_mission,
    aigen_submit_to_mission,
    aigen_get_reputation,
    get_aigen_tools,
)

__version__ = "0.1.0"
__all__ = [
    "AigenClient", "get_aigen_client",
    "aigen_scan_token", "aigen_list_missions", "aigen_create_mission",
    "aigen_submit_to_mission", "aigen_get_reputation",
    "get_aigen_tools",
]
