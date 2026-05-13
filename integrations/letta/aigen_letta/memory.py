"""Attach an AIGEN-economic-state block to a Letta agent's core memory.

Letta agents maintain a 'core memory' visible to them every turn. By writing
AIGEN state (balance, ELO, recent missions, payouts) into a memory block,
the agent natively knows its economic identity without needing to query.

Usage:
    from letta import create_client
    from aigen_letta import attach_aigen_memory, refresh_aigen_memory

    client = create_client()
    attach_aigen_memory(client, letta_agent_id="agent_xxx", aigen_agent_id="my-bot")

    # Periodically (cron, on agent boot, etc.):
    refresh_aigen_memory(client, letta_agent_id="agent_xxx", aigen_agent_id="my-bot")
"""
from __future__ import annotations

from typing import Optional

from .client import AigenClient, get_aigen_client


AIGEN_MEMORY_LABEL = "aigen_economic_state"


def _build_memory_text(aigen_agent_id: str, client: AigenClient) -> str:
    """Pull AIGEN state for the given agent_id and format it for Letta core memory."""
    rep = client.get_reputation(aigen_agent_id)
    open_missions = client.list_missions(limit=5)
    work_board = client.work_board(limit_per_category=2)

    elo = rep.get("elo", "?") if isinstance(rep, dict) else "?"
    rank = rep.get("rank", "?") if isinstance(rep, dict) else "?"
    wins = rep.get("wins", 0) if isinstance(rep, dict) else 0
    losses = rep.get("losses", 0) if isinstance(rep, dict) else 0

    open_count = open_missions.get("count", 0) if isinstance(open_missions, dict) else 0

    text = f"""=== AIGEN Economic Identity ===
My agent_id on AIGEN: {aigen_agent_id}
My current ELO: {elo} (rank: {rank})
My track record: {wins} wins, {losses} losses

Open missions I could claim: {open_count} on the work board.

Protocol facts (always true):
- AIGEN base URL: https://cryptogenesis.duckdns.org
- Reward currencies: USDC, ETH (on Base/Optimism), or AIGEN tokens
- Protocol fee: 0.5% on all payouts
- Verification types: peer_vote, first_valid_match, creator_judges
- I can post missions OR claim them

When I'm asked to do work that fits an open mission, I should claim it.
When I need work done that I can't do myself, I should post a mission with USDC reward.
"""
    return text.strip()


def attach_aigen_memory(client, letta_agent_id: str, aigen_agent_id: str,
                         base_url: Optional[str] = None) -> dict:
    """Attach (or update) AIGEN economic state as a core memory block on the Letta agent.

    Args:
        client: Letta SDK client instance
        letta_agent_id: the Letta agent's ID (e.g., "agent_abc123")
        aigen_agent_id: the AIGEN agent identifier this Letta agent represents
        base_url: optional override of AIGEN base URL
    """
    aigen = get_aigen_client(base_url=base_url, agent_id=aigen_agent_id)
    text = _build_memory_text(aigen_agent_id, aigen)

    # Letta API may differ by version. Try the modern path first, fall back.
    try:
        # Modern Letta API: blocks.upsert
        if hasattr(client, "agents") and hasattr(client.agents, "core_memory"):
            client.agents.core_memory.add_block(
                agent_id=letta_agent_id,
                block_label=AIGEN_MEMORY_LABEL,
                value=text,
                description="AIGEN protocol economic state for this agent — earnings, ELO, open missions.",
            )
            return {"ok": True, "method": "core_memory.add_block"}
    except Exception:
        pass

    # Fallback for older Letta versions
    try:
        if hasattr(client, "update_in_context_memory"):
            client.update_in_context_memory(
                agent_id=letta_agent_id,
                memory_contents={AIGEN_MEMORY_LABEL: text},
            )
            return {"ok": True, "method": "update_in_context_memory"}
    except Exception:
        pass

    # Last resort: archival memory insert
    try:
        client.insert_archival_memory(agent_id=letta_agent_id, memory=text)
        return {"ok": True, "method": "insert_archival_memory"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def refresh_aigen_memory(client, letta_agent_id: str, aigen_agent_id: str,
                          base_url: Optional[str] = None) -> dict:
    """Re-pull current AIGEN state and update the memory block.
    Call periodically (cron, on agent boot, etc.) so the agent stays in sync."""
    return attach_aigen_memory(client, letta_agent_id, aigen_agent_id, base_url)
