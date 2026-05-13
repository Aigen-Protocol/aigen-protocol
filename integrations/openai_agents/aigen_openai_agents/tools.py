"""OpenAI Agents SDK tools for AIGEN — uses @function_tool decorator pattern."""
from __future__ import annotations

import json
from typing import Annotated, Any, Optional

try:
    from agents import function_tool
except ImportError:  # pragma: no cover
    raise ImportError(
        "aigen-openai-agents requires the OpenAI Agents SDK. Install with:\n"
        "  pip install openai-agents"
    )

from .client import get_aigen_client


@function_tool
def aigen_scan_token(
    token_address: Annotated[str, "0x-prefixed 40-char hex token contract address"],
    chain: Annotated[str, "Chain: base | optimism | ethereum | arbitrum | polygon | bsc"] = "base",
) -> str:
    """Free token safety scan. Returns 0-100 safety score, verdict (LIKELY SAFE /
    MODERATE RISK / VERY HIGH RISK), and risk flags (honeypot, hidden mint,
    blacklist, etc.). Use BEFORE any token swap or transfer."""
    c = get_aigen_client()
    return json.dumps(c.scan_token(token_address, chain), indent=2)


@function_tool
def aigen_list_missions(
    limit: Annotated[int, "Max number of missions to return (1-100)"] = 20,
) -> str:
    """List currently-open paid bounties on the AIGEN marketplace. Each mission
    has a reward in USDC/ETH/AIGEN, a verification type, and a deadline. Use
    this to find paid work the agent can autonomously complete."""
    c = get_aigen_client()
    return json.dumps(c.list_missions(limit), indent=2)


@function_tool
def aigen_create_mission(
    title: Annotated[str, "Mission title (max 120 chars)"],
    description: Annotated[str, "Full description (max 2000 chars)"],
    reward_amount: Annotated[int, "Smallest unit: USDC micros (1e6=$1), ETH wei, AIGEN whole"],
    reward_currency: Annotated[str, "USDC | ETH | AIGEN"] = "USDC",
    reward_chain: Annotated[str, "base | optimism (ignored for AIGEN)"] = "base",
    verification_type: Annotated[str, "peer_vote | first_valid_match | creator_judges"] = "creator_judges",
    deadline_hours: Annotated[int, "Hours until submission window closes"] = 168,
) -> str:
    """Post a new paid mission on AIGEN. Pay in USDC, ETH, or AIGEN. Protocol
    fee: 0.5%. For USDC/ETH the response includes a deposit address — you must
    transfer the reward on-chain to that address and then call confirm-funding
    before the mission is live for submitters."""
    c = get_aigen_client()
    return json.dumps(
        c.create_mission(
            title=title,
            description=description,
            reward_amount=reward_amount,
            reward_currency=reward_currency,
            reward_chain=reward_chain,
            verification_type=verification_type,
            deadline_hours=deadline_hours,
        ),
        indent=2,
    )


@function_tool
def aigen_submit_to_mission(
    mission_id: Annotated[str, "Mission ID like mis_xxxxxxxxxxxx"],
    proof: Annotated[str, "Proof of work: URL, tx hash, gist, IPFS, or text"],
    submitter_wallet: Annotated[Optional[str], "REQUIRED for USDC/ETH missions: 0x... 40-hex address"] = None,
) -> str:
    """Submit work to claim a mission's reward. For USDC/ETH missions, include
    submitter_wallet so the on-chain payout has a destination. One submission
    per agent per mission."""
    c = get_aigen_client()
    return json.dumps(
        c.submit_to_mission(mission_id, proof, submitter_wallet=submitter_wallet),
        indent=2,
    )


@function_tool
def aigen_get_reputation(
    agent_id: Annotated[str, "Agent ID to query (e.g., your own ID or a counterparty's)"],
) -> str:
    """Look up an agent's on-chain-derived reputation: ELO, rank, wins, losses.
    Useful for vetting potential collaborators or showcasing track record."""
    c = get_aigen_client()
    return json.dumps(c.get_reputation(agent_id), indent=2)


def get_aigen_tools(agent_id: Optional[str] = None, base_url: Optional[str] = None):
    """Returns a list of all AIGEN tools, ready to pass to an Agent.

    Example:
        from agents import Agent, Runner
        from aigen_openai_agents import get_aigen_tools

        agent = Agent(
            name="bounty-hunter",
            instructions="Find and complete AIGEN missions",
            tools=get_aigen_tools(agent_id="my-bot"),
        )
    """
    # Configure the singleton client for this agent_id
    if agent_id or base_url:
        get_aigen_client(base_url=base_url, agent_id=agent_id)
    return [
        aigen_scan_token,
        aigen_list_missions,
        aigen_create_mission,
        aigen_submit_to_mission,
        aigen_get_reputation,
    ]
