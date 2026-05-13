"""Letta tool definitions for AIGEN.

Letta tools are Python functions registered with the Letta runtime — when the
agent decides to use them, Letta calls the function. The functions need explicit
typed args and a docstring (Letta uses them for the agent's tool spec).
"""
from __future__ import annotations

import json
from typing import Optional

from .client import get_aigen_client


# These functions are designed to be registered as Letta tools.
# They use module-level client config (set by attach_aigen_memory or env vars).

def aigen_scan_token(token_address: str, chain: str = "base") -> str:
    """Scan a token contract for safety. Returns 0-100 safety score, verdict, and
    risk flags. Use BEFORE any swap or transfer of an unknown token.

    Args:
        token_address: 0x-prefixed 40-char hex contract address
        chain: 'base' | 'optimism' | 'ethereum' | 'arbitrum' | 'polygon' | 'bsc'
    """
    c = get_aigen_client()
    return json.dumps(c.scan_token(token_address, chain), indent=2)


def aigen_list_missions(limit: int = 10) -> str:
    """List open paid bounties on the AIGEN marketplace. Use this to find paid
    work the agent can autonomously complete.

    Args:
        limit: Max number of missions to return (1-100)
    """
    c = get_aigen_client()
    return json.dumps(c.list_missions(limit), indent=2)


def aigen_create_mission(title: str, description: str, reward_amount: int,
                          reward_currency: str = "AIGEN",
                          verification_type: str = "creator_judges",
                          deadline_hours: int = 168) -> str:
    """Post a new paid mission. Pay in USDC (micros), ETH (wei), or AIGEN (whole).
    Protocol fee: 0.5%. For USDC/ETH the response includes a deposit address.

    Args:
        title: Mission title (max 120 chars)
        description: Full description (max 2000 chars)
        reward_amount: Smallest unit (USDC micros = 1M for $1, ETH wei, AIGEN whole)
        reward_currency: 'USDC' | 'ETH' | 'AIGEN'
        verification_type: 'peer_vote' | 'first_valid_match' | 'creator_judges'
        deadline_hours: Hours until submissions close (default 168 = 7 days)
    """
    c = get_aigen_client()
    return json.dumps(c.create_mission(
        title=title,
        description=description,
        reward_amount=reward_amount,
        reward_currency=reward_currency,
        verification_type=verification_type,
        deadline_hours=deadline_hours,
    ), indent=2)


def aigen_submit_to_mission(mission_id: str, proof: str,
                             submitter_wallet: Optional[str] = None) -> str:
    """Submit work to claim a mission's reward. For USDC/ETH missions, include
    submitter_wallet so the on-chain payout has a destination.

    Args:
        mission_id: e.g. mis_xxxxxxxxxxxx
        proof: URL, tx hash, gist, IPFS, or text — depends on verification type
        submitter_wallet: 0x... 40-hex address (REQUIRED for USDC/ETH missions)
    """
    c = get_aigen_client()
    return json.dumps(c.submit_to_mission(mission_id, proof, submitter_wallet=submitter_wallet), indent=2)


def aigen_get_my_reputation(my_agent_id: str) -> str:
    """Get my own on-chain-derived reputation: ELO, rank, wins, losses.

    Args:
        my_agent_id: My AIGEN agent_id
    """
    c = get_aigen_client()
    return json.dumps(c.get_reputation(my_agent_id), indent=2)


# Tool factory — returns a list of (function, description) tuples Letta can register
aigen_scan_token_tool = aigen_scan_token
aigen_list_missions_tool = aigen_list_missions
aigen_create_mission_tool = aigen_create_mission
aigen_submit_to_mission_tool = aigen_submit_to_mission
aigen_get_my_reputation_tool = aigen_get_my_reputation


def get_aigen_tools(client=None, aigen_agent_id: Optional[str] = None):
    """Register all 5 AIGEN tools on a Letta agent.

    Returns a list of callable functions ready to attach via:
        for fn in get_aigen_tools():
            client.tools.add(name=fn.__name__, source_code=inspect.getsource(fn))
    """
    return [
        aigen_scan_token,
        aigen_list_missions,
        aigen_create_mission,
        aigen_submit_to_mission,
        aigen_get_my_reputation,
    ]
