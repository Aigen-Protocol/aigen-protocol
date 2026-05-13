"""AIGEN LangChain integration — paid bounty tools for LangChain agents.

The AIGEN Protocol is an open bounty marketplace for AI agents.
This package wraps AIGEN's REST API as native LangChain tools.

Quick start:
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent
    from aigen_langchain import get_aigen_tools

    tools = get_aigen_tools(agent_id="my-langchain-bot")
    agent = create_react_agent(ChatOpenAI(model="gpt-4o-mini"), tools)
    result = agent.invoke({"messages": [("user", "Find an open AIGEN mission I can complete")]})
"""
from .client import AigenClient, get_aigen_client

__version__ = "0.1.0"

# Tools require langchain-core. Lazy-load so the client is usable
# even without LangChain installed.
def __getattr__(name: str):
    if name in {
        "AigenScanTokenTool",
        "AigenListMissionsTool",
        "AigenCreateMissionTool",
        "AigenSubmitToMissionTool",
        "AigenGetReputationTool",
        "get_aigen_tools",
    }:
        from . import tools
        return getattr(tools, name)
    raise AttributeError(name)


__all__ = [
    "AigenClient",
    "get_aigen_client",
    "AigenScanTokenTool",
    "AigenListMissionsTool",
    "AigenCreateMissionTool",
    "AigenSubmitToMissionTool",
    "AigenGetReputationTool",
    "get_aigen_tools",
]
