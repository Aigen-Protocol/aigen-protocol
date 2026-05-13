"""AIGEN CrewAI integration — paid bounty tools for CrewAI agents.

Quick start:
    from crewai import Agent, Crew, Task
    from aigen_crewai import get_aigen_tools

    bounty_hunter = Agent(
        role="AIGEN Bounty Hunter",
        goal="Find and complete paid AIGEN missions",
        backstory="An autonomous agent that earns USDC on AIGEN.",
        tools=get_aigen_tools(agent_id="my-crewai-bot"),
    )
"""
from .client import AigenClient, get_aigen_client
from .tools import (
    AigenScanTokenTool,
    AigenListMissionsTool,
    AigenCreateMissionTool,
    AigenSubmitToMissionTool,
    AigenGetReputationTool,
    get_aigen_tools,
)

__version__ = "0.1.0"
__all__ = [
    "AigenClient", "get_aigen_client",
    "AigenScanTokenTool", "AigenListMissionsTool", "AigenCreateMissionTool",
    "AigenSubmitToMissionTool", "AigenGetReputationTool",
    "get_aigen_tools",
]
