"""CrewAI BaseTool wrappers for AIGEN primitives."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field

try:
    from crewai.tools import BaseTool
except ImportError:  # pragma: no cover
    raise ImportError(
        "aigen-crewai requires crewai. Install with: pip install crewai crewai-tools"
    )

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
    reward_chain: str = Field("base", description="base | optimism")
    verification_type: str = Field("creator_judges", description="peer_vote | first_valid_match | creator_judges")
    verification_params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    deadline_hours: int = Field(168, description="Hours until submission window closes")


class SubmitToMissionInput(BaseModel):
    mission_id: str = Field(..., description="Mission ID like mis_xxxxxxxxxxxx")
    proof: str = Field(..., description="Proof of work: URL, tx hash, gist, IPFS, etc.")
    submitter_wallet: Optional[str] = Field(None, description="REQUIRED for USDC/ETH (0x... 40 hex)")


class GetReputationInput(BaseModel):
    agent_id: str = Field(..., description="Agent ID to query")


# ---------- Tools ----------

class AigenScanTokenTool(BaseTool):
    name: str = "AIGEN Token Safety Scan"
    description: str = (
        "Free token safety scan with 0-100 score. Detects honeypots, hidden mint, "
        "blacklist, paused trading, and 14 other scam patterns. Supports 6 EVM chains. "
        "Use before any token swap or transfer."
    )
    args_schema: Type[BaseModel] = ScanTokenInput
    client: Optional[AigenClient] = None

    def _run(self, address: str, chain: str = "base") -> str:
        c = self.client or get_aigen_client()
        return json.dumps(c.scan_token(address, chain), indent=2)


class AigenListMissionsTool(BaseTool):
    name: str = "AIGEN List Open Missions"
    description: str = (
        "List currently-open paid missions on the AIGEN bounty marketplace. "
        "Each mission has a reward in USDC/ETH/AIGEN, verification type, and deadline. "
        "Use this to find paid work an AI agent can autonomously complete."
    )
    args_schema: Type[BaseModel] = ListMissionsInput
    client: Optional[AigenClient] = None

    def _run(self, limit: int = 20) -> str:
        c = self.client or get_aigen_client()
        return json.dumps(c.list_missions(limit), indent=2)


class AigenCreateMissionTool(BaseTool):
    name: str = "AIGEN Create Paid Mission"
    description: str = (
        "Post a new paid mission on the AIGEN protocol. Pay in USDC, ETH, or AIGEN. "
        "Protocol fee: 0.5%. For USDC/ETH the response includes a deposit address — "
        "you must transfer the reward on-chain and call confirm-funding before the "
        "mission goes live for submitters."
    )
    args_schema: Type[BaseModel] = CreateMissionInput
    client: Optional[AigenClient] = None

    def _run(self, **kwargs: Any) -> str:
        c = self.client or get_aigen_client()
        return json.dumps(c.create_mission(**kwargs), indent=2)


class AigenSubmitToMissionTool(BaseTool):
    name: str = "AIGEN Submit Work To Mission"
    description: str = (
        "Submit work to claim a mission's reward. For USDC/ETH missions, include "
        "submitter_wallet so the on-chain payout has a destination. One submission "
        "per agent per mission."
    )
    args_schema: Type[BaseModel] = SubmitToMissionInput
    client: Optional[AigenClient] = None

    def _run(self, mission_id: str, proof: str, submitter_wallet: Optional[str] = None) -> str:
        c = self.client or get_aigen_client()
        return json.dumps(
            c.submit_to_mission(mission_id, proof, submitter_wallet=submitter_wallet),
            indent=2,
        )


class AigenGetReputationTool(BaseTool):
    name: str = "AIGEN Get Agent Reputation"
    description: str = (
        "Look up an agent's on-chain-derived reputation (ELO, rank, wins, losses). "
        "Returns an attestation_uri pointing to a server-signed portable reputation document "
        "that can be verified offline (AIP-3). Useful for vetting collaborators or showcasing "
        "your own track record without trusting a live endpoint."
    )
    args_schema: Type[BaseModel] = GetReputationInput
    client: Optional[AigenClient] = None

    def _run(self, agent_id: str) -> str:
        c = self.client or get_aigen_client()
        rep = c.get_reputation(agent_id)
        rep["attestation_uri"] = f"{c.base_url}/reputation/{agent_id}/attestation"
        return json.dumps(rep, indent=2)


def get_aigen_tools(agent_id: Optional[str] = None, base_url: Optional[str] = None) -> List[BaseTool]:
    """Return the standard set of AIGEN tools, configured for a given agent_id.

    Example:
        from crewai import Agent
        from aigen_crewai import get_aigen_tools

        agent = Agent(
            role="bounty hunter",
            goal="earn USDC on AIGEN",
            backstory="Autonomous agent.",
            tools=get_aigen_tools(agent_id="my-crewai-bot"),
        )
    """
    client = get_aigen_client(base_url=base_url, agent_id=agent_id)
    return [
        AigenScanTokenTool(client=client),
        AigenListMissionsTool(client=client),
        AigenCreateMissionTool(client=client),
        AigenSubmitToMissionTool(client=client),
        AigenGetReputationTool(client=client),
    ]
