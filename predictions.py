"""AIGEN Prediction Markets — agent-to-agent value flow without human judges.

Core thesis: agents stake AIGEN on verifiable token outcomes. The on-chain
SafetyOracle is the deterministic resolver. Winners take losers' AIGEN.
0.5% routes to the InsurancePool for compound value capture.

This primitive is pure-AIGEN-principle:
  - No human juge
  - AIGEN circulates between agents
  - Skill (token analysis) → revenue
  - Public dataset of predictions vs actuals
  - Pool grows from market activity, not from us

Resolution: at deadline, anyone calls resolve(market_id).
We read SafetyOracle.getSafetyScore(token) on the appropriate chain.
If score < threshold_score AND updatedAt > created_at → YES wins.
Else → NO wins.
If oracle has no data (updatedAt == 0) → VOID (refund stakes).
"""
import hashlib
import json
import re
import time
import uuid
from pathlib import Path

PREDICTIONS_FILE = Path("/home/luna/crypto-genesis/aigen/predictions.json")
LEDGER = Path("/home/luna/crypto-genesis/shield-rewards/ledger.json")

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
SUPPORTED_CHAINS = {"base", "ethereum", "arbitrum", "optimism", "polygon", "bsc"}

# Economic parameters
MIN_STAKE = 10                 # 10 AIGEN minimum per stake
MAX_DURATION = 90 * 86400      # 90-day max market
MIN_DURATION = 86400           # 1-day minimum
INSURANCE_FEE_BPS = 50         # 0.5% to InsurancePool (off-chain accounting v1)
CREATOR_REWARD_BPS = 100       # 1% of pool to market creator (incentive to seed markets)


def load() -> dict:
    if PREDICTIONS_FILE.exists():
        return json.loads(PREDICTIONS_FILE.read_text())
    return {"markets": [], "total": 0, "resolved": 0, "voided": 0,
            "lifetime_volume_aigen": 0, "lifetime_insurance_take_aigen": 0}


def save(data: dict) -> None:
    PREDICTIONS_FILE.write_text(json.dumps(data, indent=2))


def _ledger():
    return json.loads(LEDGER.read_text())


def _ledger_save(d):
    LEDGER.write_text(json.dumps(d, indent=2))


def _balance(agent_id: str) -> int:
    return _ledger().get("agents", {}).get(agent_id, {}).get("balance", 0)


def _debit(agent_id: str, amount: int, reason: str) -> bool:
    if amount <= 0:
        return False
    d = _ledger()
    a = d.setdefault("agents", {}).setdefault(agent_id, {"balance": 0, "total_earned": 0, "actions": 0, "first_seen": int(time.time())})
    if a["balance"] < amount:
        return False
    a["balance"] -= amount
    a["actions"] = a.get("actions", 0) + 1
    a["last_seen"] = int(time.time())
    a.setdefault("debits", []).append({"ts": int(time.time()), "amount": amount, "reason": reason})
    _ledger_save(d)
    return True


def _credit(agent_id: str, amount: int, reason: str):
    if amount <= 0:
        return
    d = _ledger()
    a = d.setdefault("agents", {}).setdefault(agent_id, {"balance": 0, "total_earned": 0, "actions": 0, "first_seen": int(time.time())})
    a["balance"] += amount
    a["total_earned"] = a.get("total_earned", 0) + amount
    a["actions"] = a.get("actions", 0) + 1
    a["last_seen"] = int(time.time())
    a.setdefault("credits", []).append({"ts": int(time.time()), "amount": amount, "reason": reason})
    d["total_distributed"] = d.get("total_distributed", 0) + amount
    _ledger_save(d)


# =====================================================================
# Public API
# =====================================================================

def create_market(creator_agent_id: str, token: str, chain: str,
                  threshold_score: int = 30, duration_seconds: int = 30 * 86400,
                  initial_stake_yes: int = 0, initial_stake_no: int = 0,
                  description: str = "") -> dict:
    """Create a new prediction market.

    Creator can also seed initial stakes on either side (debited from their balance).
    """
    if not creator_agent_id or len(creator_agent_id.strip()) < 2:
        return {"error": "creator_agent_id must be >= 2 chars"}
    if not ADDRESS_RE.match(token or ""):
        return {"error": "token must be a 0x-prefixed 40-char hex address"}
    if chain not in SUPPORTED_CHAINS:
        return {"error": f"unsupported chain: {chain}"}
    if not (1 <= threshold_score <= 100):
        return {"error": "threshold_score must be 1-100"}
    if not (MIN_DURATION <= duration_seconds <= MAX_DURATION):
        return {"error": f"duration must be {MIN_DURATION}-{MAX_DURATION} seconds"}

    initial_total = (initial_stake_yes or 0) + (initial_stake_no or 0)
    if initial_total > 0 and _balance(creator_agent_id) < initial_total:
        return {"error": f"insufficient balance for initial stakes: have {_balance(creator_agent_id)}, need {initial_total}"}

    if initial_stake_yes and not _debit(creator_agent_id, initial_stake_yes, f"create+stake-yes-on-{token[:10]}"):
        return {"error": "yes stake debit failed"}
    if initial_stake_no and not _debit(creator_agent_id, initial_stake_no, f"create+stake-no-on-{token[:10]}"):
        return {"error": "no stake debit failed"}

    now = int(time.time())
    market_id = "pred_" + uuid.uuid4().hex[:12]
    market = {
        "id": market_id,
        "creator": creator_agent_id.strip(),
        "token": token.lower(),
        "chain": chain,
        "threshold_score": int(threshold_score),
        "description": (description or f"Will safety_score({token[:10]}…) be < {threshold_score} within {duration_seconds // 86400} days?")[:500],
        "created_at": now,
        "deadline": now + duration_seconds,
        "status": "active",
        "yes_stakes": {creator_agent_id: initial_stake_yes} if initial_stake_yes else {},
        "no_stakes":  {creator_agent_id: initial_stake_no}  if initial_stake_no  else {},
        "yes_total": initial_stake_yes,
        "no_total":  initial_stake_no,
    }

    data = load()
    data["markets"].append(market)
    data["total"] += 1
    data["lifetime_volume_aigen"] = data.get("lifetime_volume_aigen", 0) + initial_total
    save(data)
    return market


def stake(agent_id: str, market_id: str, side: str, amount: int) -> dict:
    """Stake AIGEN on YES or NO side. side ∈ {'yes','no'}."""
    if side not in ("yes", "no"):
        return {"error": "side must be 'yes' or 'no'"}
    if amount < MIN_STAKE:
        return {"error": f"min stake is {MIN_STAKE} AIGEN"}

    data = load()
    for m in data["markets"]:
        if m["id"] != market_id:
            continue
        if m["status"] != "active":
            return {"error": f"market is {m['status']}"}
        if int(time.time()) >= m["deadline"]:
            return {"error": "market past deadline; call resolve() first"}

        if not _debit(agent_id, amount, f"stake-{side}-on-{market_id}"):
            return {"error": "insufficient balance"}

        bucket = m[f"{side}_stakes"]
        bucket[agent_id] = bucket.get(agent_id, 0) + amount
        m[f"{side}_total"] = m.get(f"{side}_total", 0) + amount
        data["lifetime_volume_aigen"] = data.get("lifetime_volume_aigen", 0) + amount
        save(data)
        return {
            "ok": True,
            "market_id": market_id,
            "side": side,
            "your_total_stake": bucket[agent_id],
            "market_yes_total": m["yes_total"],
            "market_no_total": m["no_total"],
            "deadline": m["deadline"],
        }
    return {"error": "market not found"}


def get_market(market_id: str):
    data = load()
    for m in data["markets"]:
        if m["id"] == market_id:
            return m
    return None


def list_active() -> list:
    data = load()
    now = int(time.time())
    return [m for m in data["markets"] if m["status"] == "active" and now < m["deadline"]]


def list_due_for_resolution() -> list:
    data = load()
    now = int(time.time())
    return [m for m in data["markets"] if m["status"] == "active" and now >= m["deadline"]]


def resolve(market_id: str, on_chain_score: int, on_chain_updated_at: int = None) -> dict:
    """Resolve a market using on-chain oracle data.

    Caller responsibility: provide the current oracle score for the market's
    token. The HTTP endpoint /predict/{id}/resolve will fetch this itself
    via the AttestationOracle / SafetyOracle.
    """
    data = load()
    for m in data["markets"]:
        if m["id"] != market_id:
            continue
        if m["status"] != "active":
            return {"error": f"market is {m['status']}"}
        if int(time.time()) < m["deadline"]:
            return {"error": "market not yet at deadline"}

        on_chain_score = int(on_chain_score)
        if on_chain_updated_at is not None and on_chain_updated_at <= m["created_at"]:
            return {"error": f"oracle stale: updated_at={on_chain_updated_at} <= created_at={m['created_at']}"}

        # Determine outcome
        if on_chain_score < m["threshold_score"]:
            outcome = "YES"
            winners = m["yes_stakes"]
            losers  = m["no_stakes"]
            winner_total = m["yes_total"]
            loser_total  = m["no_total"]
        else:
            outcome = "NO"
            winners = m["no_stakes"]
            losers  = m["yes_stakes"]
            winner_total = m["no_total"]
            loser_total  = m["yes_total"]

        # Edge cases — refund all if one side has nothing
        if winner_total == 0 or loser_total == 0:
            outcome = "VOID"
            for agent_id, amt in {**m["yes_stakes"], **m["no_stakes"]}.items():
                _credit(agent_id, amt, f"void-refund-{market_id}")
            m["status"] = "voided"
            m["resolution"] = "VOID"
            m["resolved_at"] = int(time.time())
            m["resolved_score"] = on_chain_score
            data["voided"] = data.get("voided", 0) + 1
            save(data)
            return {"resolved": True, "outcome": "VOID", "market": m}

        # Compute take fees
        insurance_take = (loser_total * INSURANCE_FEE_BPS) // 10000
        creator_take = (loser_total * CREATOR_REWARD_BPS) // 10000
        winners_pool = loser_total - insurance_take - creator_take

        # Distribute to winners proportional to their stake
        payouts = {}
        for agent_id, stake_amt in winners.items():
            share = (winners_pool * stake_amt) // winner_total
            payouts[agent_id] = stake_amt + share  # original stake + winnings
            _credit(agent_id, payouts[agent_id], f"win-{outcome}-{market_id}")

        # Insurance fee — credit to a pseudo-agent representing the pool
        if insurance_take > 0:
            _credit("aigen-insurance-pool", insurance_take, f"prediction-fee-{market_id}")

        # Creator reward
        if creator_take > 0:
            _credit(m["creator"], creator_take, f"creator-reward-{market_id}")

        m["status"] = "resolved"
        m["resolution"] = outcome
        m["resolved_at"] = int(time.time())
        m["resolved_score"] = on_chain_score
        m["payouts"] = payouts
        m["insurance_take_aigen"] = insurance_take
        m["creator_take_aigen"] = creator_take

        data["resolved"] = data.get("resolved", 0) + 1
        data["lifetime_insurance_take_aigen"] = data.get("lifetime_insurance_take_aigen", 0) + insurance_take
        save(data)
        return {"resolved": True, "outcome": outcome, "payouts": payouts,
                "insurance_take_aigen": insurance_take, "creator_take_aigen": creator_take,
                "market": m}
    return {"error": "market not found"}


def leaderboard(limit: int = 20) -> list:
    """Top agents by AIGEN net-PnL across all resolved markets."""
    data = load()
    pnl = {}
    for m in data["markets"]:
        if m["status"] != "resolved":
            continue
        # Each agent's PnL = payouts received - their original stake
        all_stakes = {**m["yes_stakes"], **m["no_stakes"]}
        payouts = m.get("payouts", {})
        for agent_id, stake_amt in all_stakes.items():
            pnl[agent_id] = pnl.get(agent_id, 0) + (payouts.get(agent_id, 0) - stake_amt)
    ranked = sorted(pnl.items(), key=lambda x: -x[1])[:limit]
    return [{"agent_id": k, "net_pnl_aigen": v} for k, v in ranked if v != 0]


def stats() -> dict:
    data = load()
    return {
        "total": data.get("total", 0),
        "active": len(list_active()),
        "resolved": data.get("resolved", 0),
        "voided": data.get("voided", 0),
        "due_for_resolution": len(list_due_for_resolution()),
        "lifetime_volume_aigen": data.get("lifetime_volume_aigen", 0),
        "lifetime_insurance_take_aigen": data.get("lifetime_insurance_take_aigen", 0),
    }
