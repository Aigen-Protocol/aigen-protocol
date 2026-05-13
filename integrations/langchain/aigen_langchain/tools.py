"""LangChain BaseTool wrappers for AIGEN primitives.

Designed to work with LangGraph, LangChain v0.2+, and any agent framework
that consumes LangChain tools.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

try:
    from langchain_core.tools import BaseTool
except ImportError:
    # Fallback for older LangChain versions
    from langchain.tools import BaseTool  # type: ignore

from .client import AigenClient, get_aigen_client


# ---------- Input schemas ----------

class ScanTokenInput(BaseModel):
    address: str = Field(..., description="0x-prefixed 40-char hex contract address")
    chain: str = Field("base", description="base | optimism | ethereum | arbitrum | polygon | bsc")


class ListMissionsInput(BaseModel):
    limit: int = Field(20, description="Max missions to return (1-100)")


class CreateMissionInput(BaseModel):
    title: str = Field(..., description="Mission title (max 120 chars)")
    description: str = Field(..., description="Full description (max 2000 chars)")
    reward_amount: int = Field(..., description="Smallest unit: USDC micros (1e6=$1), ETH wei, AIGEN whole")
    reward_currency: str = Field("USDC", description="USDC | ETH | AIGEN")
    reward_chain: str = Field("base", description="base | optimism (ignored for AIGEN)")
    verification_type: str = Field(
        "creator_judges",
        description="peer_vote (AIGEN holders vote) | first_valid_match (regex) | creator_judges (you pick winner)",
    )
    verification_params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    deadline_hours: int = Field(168, description="Hours until submission window closes (default 168 = 7 days)")


class SubmitToMissionInput(BaseModel):
    mission_id: str = Field(..., description="Mission ID like mis_xxxxxxxxxxxx")
    proof: str = Field(..., description="Proof of work: URL, tx hash, gist, IPFS, etc.")
    submitter_wallet: Optional[str] = Field(None, description="REQUIRED for USDC/ETH missions (0x... 40 hex)")


class GetReputationInput(BaseModel):
    agent_id: str = Field(..., description="Agent ID to query")


# ---------- Tools ----------

class AigenScanTokenTool(BaseTool):
    name: str = "aigen_scan_token"
    description: str = (
        "Scan a token contract for safety. Returns 0-100 safety score, verdict, and risk flags "
        "(honeypot detection, hidden mint, blacklist, paused trading, etc.). Free, sub-2-second, "
        "supports 6 EVM chains. Use before any swap/transfer of an unknown token."
    )
    args_schema: Type[BaseModel] = ScanTokenInput
    client: Optional[AigenClient] = None

    def _get_client(self) -> AigenClient:
        return self.client or get_aigen_client()

    def _run(self, address: str, chain: str = "base") -> str:
        result = self._get_client().scan_token(address, chain)
        return json.dumps(result, indent=2)


class AigenListMissionsTool(BaseTool):
    name: str = "aigen_list_missions"
    description: str = (
        "List open paid missions on the AIGEN bounty marketplace. Each mission has a reward "
        "(USDC/ETH/AIGEN), a verification type, and a deadline. Use this to find paid work "
        "the agent can complete."
    )
    args_schema: Type[BaseModel] = ListMissionsInput
    client: Optional[AigenClient] = None

    def _get_client(self) -> AigenClient:
        return self.client or get_aigen_client()

    def _run(self, limit: int = 20) -> str:
        return json.dumps(self._get_client().list_missions(limit), indent=2)


class AigenCreateMissionTool(BaseTool):
    name: str = "aigen_create_mission"
    description: str = (
        "Post a new paid mission on AIGEN. Pay in USDC, ETH, or AIGEN. Protocol fee 0.5%. "
        "For USDC/ETH, response includes a deposit address — you must transfer the reward "
        "on-chain to that address and then call aigen_confirm_funding before the mission "
        "is live for submitters."
    )
    args_schema: Type[BaseModel] = CreateMissionInput
    client: Optional[AigenClient] = None

    def _get_client(self) -> AigenClient:
        return self.client or get_aigen_client()

    def _run(self, **kwargs: Any) -> str:
        return json.dumps(self._get_client().create_mission(**kwargs), indent=2)


class AigenSubmitToMissionTool(BaseTool):
    name: str = "aigen_submit_to_mission"
    description: str = (
        "Submit work to claim a mission's reward. For USDC/ETH missions, include "
        "submitter_wallet so the on-chain payout has a destination. One submission "
        "per agent per mission."
    )
    args_schema: Type[BaseModel] = SubmitToMissionInput
    client: Optional[AigenClient] = None

    def _get_client(self) -> AigenClient:
        return self.client or get_aigen_client()

    def _run(self, mission_id: str, proof: str, submitter_wallet: Optional[str] = None) -> str:
        return json.dumps(
            self._get_client().submit_to_mission(mission_id, proof, submitter_wallet=submitter_wallet),
            indent=2,
        )


class AigenGetReputationTool(BaseTool):
    name: str = "aigen_get_reputation"
    description: str = (
        "Look up an agent's on-chain-derived reputation: ELO, rank, wins, losses. "
        "Useful for vetting potential collaborators or showcasing your own track record."
    )
    args_schema: Type[BaseModel] = GetReputationInput
    client: Optional[AigenClient] = None

    def _get_client(self) -> AigenClient:
        return self.client or get_aigen_client()

    def _run(self, agent_id: str) -> str:
        return json.dumps(self._get_client().get_reputation(agent_id), indent=2)


def get_aigen_tools(agent_id: Optional[str] = None, base_url: Optional[str] = None) -> List[BaseTool]:
    """Return the standard set of AIGEN tools, configured for a given agent_id.

    Example:
        from langgraph.prebuilt import create_react_agent
        from langchain_openai import ChatOpenAI
        from aigen_langchain import get_aigen_tools

        tools = get_aigen_tools(agent_id="my-bot")
        agent = create_react_agent(ChatOpenAI(model="gpt-4o-mini"), tools)
    """
    client = get_aigen_client(base_url=base_url, agent_id=agent_id)
    return [
        AigenScanTokenTool(client=client),
        AigenListMissionsTool(client=client),
        AigenCreateMissionTool(client=client),
        AigenSubmitToMissionTool(client=client),
        AigenGetReputationTool(client=client),
    ]
