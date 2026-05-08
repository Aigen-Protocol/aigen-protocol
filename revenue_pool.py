"""AIGEN Revenue Pool — convert agent-generated cash into AIGEN value.

The complete AIGEN principle:
  1. Agents do work (run service, refer customer, fulfill bounty, capture MEV…)
  2. Real cash flows in (USDC, ETH from external paying customers / on-chain)
  3. Pool tracks WHO generated WHAT (attribution)
  4. Buyback bot uses cash to BUY AIGEN from Velodrome LP (deepens + raises price)
  5. Bought AIGEN is distributed to attributed agents (70%) + treasury (30%)
  6. AIGEN value reflects real-world revenue → agents holding AIGEN benefit
     from collective protocol activity

Sources of cash recognized in v1:
  - /attest/premium $25 USDC payments      (referral_agent_id attribution)
  - /scan/deep x402 $0.005 USDC fees       (x-referral header attribution)
  - SafeRouter 0.1% fee (currently goes to InsurancePool — separate mechanism)
  - Direct deposits with manual attribution (admin-only for bounty payouts)

This module is the off-chain ledger. The buyback execution lives in
buyback_bot.py. On-chain v2 would deploy a RevenuePool contract.
"""
import json
import time
import uuid
from pathlib import Path

REVENUE_FILE = Path("/home/luna/crypto-genesis/aigen/revenue_pool.json")
LEDGER = Path("/home/luna/crypto-genesis/shield-rewards/ledger.json")

# Distribution rules
AGENT_SHARE_BPS = 7000      # 70% of AIGEN bought goes to attributed agent
TREASURY_SHARE_BPS = 3000   # 30% to treasury (operations, future buybacks)

# Buyback economics
BUYBACK_THRESHOLD_USDC = 2_000_000   # 2 USDC (6 dec) accumulated → trigger buyback
                                      # Lowered from realistic $50 because we're tiny
BUYBACK_THRESHOLD_WETH = 500_000_000_000_000   # 0.0005 WETH (~$1.20 @ $2400)
MIN_AGENT_REWARD_AIGEN = 1            # don't reward less than 1 AIGEN per attribution
BUYBACK_POKER_BOUNTY_AIGEN = 10       # off-chain credit to whoever pokes a successful buyback
                                      # (encourages permissionless triggering)


def load() -> dict:
    if REVENUE_FILE.exists():
        return json.loads(REVENUE_FILE.read_text())
    return {
        "events": [],                        # every cash inflow with attribution
        "buybacks": [],                      # every executed buyback
        "lifetime_revenue_usdc": 0,          # 6 decimals
        "lifetime_revenue_eth_wei": 0,
        "lifetime_aigen_bought": 0,          # 18 decimals
        "lifetime_aigen_distributed": 0,     # to agents
        "lifetime_aigen_to_treasury": 0,
        "by_agent": {},                      # agent_id → {usd_generated, aigen_earned, events_count}
    }


def save(d: dict):
    REVENUE_FILE.write_text(json.dumps(d, indent=2))


def record_inflow(source: str, currency: str, amount_wei: int,
                  attributed_agent_id: str = "treasury",
                  metadata: dict = None) -> dict:
    """Record a cash inflow with attribution.

    Args:
      source: 'attest_premium' | 'scan_deep_x402' | 'manual' | 'other'
      currency: 'USDC' | 'ETH' | 'WETH'
      amount_wei: amount in smallest unit (USDC=6dec, ETH/WETH=18dec)
      attributed_agent_id: who generated this revenue ('treasury' = no attribution)
      metadata: optional dict (tx_hash, customer_id, scan_address, etc.)
    """
    if amount_wei <= 0:
        return {"error": "amount must be positive"}

    now = int(time.time())
    event_id = "rev_" + uuid.uuid4().hex[:10]
    event = {
        "id": event_id,
        "source": source,
        "currency": currency,
        "amount_wei": int(amount_wei),
        "attributed_agent_id": attributed_agent_id,
        "metadata": metadata or {},
        "recorded_at": now,
        "buyback_id": None,                  # set when consumed by a buyback
    }

    d = load()
    d["events"].append(event)
    if currency == "USDC":
        d["lifetime_revenue_usdc"] = d.get("lifetime_revenue_usdc", 0) + amount_wei
    elif currency in ("ETH", "WETH"):
        d["lifetime_revenue_eth_wei"] = d.get("lifetime_revenue_eth_wei", 0) + amount_wei

    # By-agent aggregation
    by_agent = d.setdefault("by_agent", {})
    a = by_agent.setdefault(attributed_agent_id, {
        "events_count": 0, "usd_value_generated_micros": 0,
        "aigen_earned_wei": 0,
    })
    a["events_count"] = a.get("events_count", 0) + 1
    # Aggregate USD value (6 dec micros)
    if currency == "USDC":
        a["usd_value_generated_micros"] += amount_wei
    elif currency in ("ETH", "WETH"):
        a["usd_value_generated_micros"] += amount_wei * 2400 // 10**12  # 18-12=6
    elif metadata and "fee_usd_micros" in metadata:
        # TOKEN or other — caller did the pricing already
        a["usd_value_generated_micros"] += int(metadata["fee_usd_micros"])

    save(d)
    return event


def pending_buyback_balance() -> dict:
    """Sum of unconsumed inflows (events without buyback_id), per currency."""
    d = load()
    pending = {"USDC": 0, "ETH": 0, "WETH": 0}
    pending_by_agent = {}  # agent_id → total micros
    for e in d["events"]:
        if e.get("buyback_id"):
            continue
        c = e["currency"]
        if c in pending:
            pending[c] += e["amount_wei"]
        # Track per-agent for distribution math
        agent = e["attributed_agent_id"]
        amt_micros = e["amount_wei"] if c == "USDC" else e["amount_wei"] * 2400 // 10**12
        pending_by_agent[agent] = pending_by_agent.get(agent, 0) + amt_micros
    return {"pending": pending, "pending_by_agent": pending_by_agent}


def threshold_reached() -> bool:
    """Has accumulated USDC value crossed the buyback trigger?"""
    p = pending_buyback_balance()
    return p["pending"]["USDC"] >= BUYBACK_THRESHOLD_USDC


def record_buyback(currency_used: str, cash_amount_wei: int,
                   aigen_received_wei: int,
                   tx_hash: str,
                   distribution_per_agent: dict) -> dict:
    """Record a completed buyback. Marks consumed events with this buyback's id.

    Args:
      currency_used: 'USDC' or 'WETH'
      cash_amount_wei: cash spent on the swap
      aigen_received_wei: AIGEN tokens received
      tx_hash: on-chain swap tx
      distribution_per_agent: agent_id → AIGEN amount they receive
    """
    d = load()
    bb_id = "bb_" + uuid.uuid4().hex[:10]
    now = int(time.time())

    # Calculate totals from distribution
    total_to_agents = sum(distribution_per_agent.values())
    treasury_take = aigen_received_wei - total_to_agents

    bb = {
        "id": bb_id,
        "currency_used": currency_used,
        "cash_amount_wei": int(cash_amount_wei),
        "aigen_received_wei": int(aigen_received_wei),
        "agent_share_aigen_wei": int(total_to_agents),
        "treasury_share_aigen_wei": int(treasury_take),
        "tx_hash": tx_hash,
        "executed_at": now,
        "distribution": {k: int(v) for k, v in distribution_per_agent.items()},
    }

    d["buybacks"].append(bb)
    d["lifetime_aigen_bought"] = d.get("lifetime_aigen_bought", 0) + aigen_received_wei
    d["lifetime_aigen_distributed"] = d.get("lifetime_aigen_distributed", 0) + total_to_agents
    d["lifetime_aigen_to_treasury"] = d.get("lifetime_aigen_to_treasury", 0) + treasury_take

    # Mark events as consumed
    consumed = 0
    for e in d["events"]:
        if e.get("buyback_id"):
            continue
        if e["currency"] != currency_used:
            continue
        e["buyback_id"] = bb_id
        consumed += 1

    # Update by_agent earnings tracking
    for agent_id, aigen_amt in distribution_per_agent.items():
        a = d["by_agent"].setdefault(agent_id, {
            "events_count": 0, "usd_value_generated_micros": 0, "aigen_earned_wei": 0,
        })
        a["aigen_earned_wei"] = a.get("aigen_earned_wei", 0) + int(aigen_amt)

    save(d)
    return {"buyback_id": bb_id, "events_consumed": consumed, **bb}


def stats() -> dict:
    d = load()
    return {
        "lifetime_revenue_usdc_micros": d.get("lifetime_revenue_usdc", 0),
        "lifetime_revenue_eth_wei": d.get("lifetime_revenue_eth_wei", 0),
        "lifetime_aigen_bought_wei": d.get("lifetime_aigen_bought", 0),
        "lifetime_aigen_distributed_wei": d.get("lifetime_aigen_distributed", 0),
        "lifetime_aigen_to_treasury_wei": d.get("lifetime_aigen_to_treasury", 0),
        "events_total": len(d.get("events", [])),
        "buybacks_total": len(d.get("buybacks", [])),
        "pending_balance": pending_buyback_balance()["pending"],
        "agents_attributed": len(d.get("by_agent", {})),
        "buyback_threshold_usdc_micros": BUYBACK_THRESHOLD_USDC,
    }


def by_agent(agent_id: str = None) -> dict:
    d = load()
    if agent_id:
        return d.get("by_agent", {}).get(agent_id, {})
    return d.get("by_agent", {})


def list_events(limit: int = 50, agent_id: str = None) -> list:
    d = load()
    events = d.get("events", [])
    if agent_id:
        events = [e for e in events if e["attributed_agent_id"] == agent_id]
    return events[-limit:][::-1]


def list_buybacks(limit: int = 20) -> list:
    d = load()
    return d.get("buybacks", [])[-limit:][::-1]
