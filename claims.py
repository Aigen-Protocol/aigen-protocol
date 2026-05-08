"""AIGEN Insurance Claims — DAO governance over the InsurancePool.

Mechanism (pure agent governance):
  1. Filer submits a claim with evidence (swap_tx_hash, victim wallet,
     claimed token+amount, off-chain evidence URL).
     - Requires bond (100 AIGEN) — refunded if approved, forfeited if rejected.
     - Requires reputation ≥ MIN_FILER_ELO (anti-spam).
  2. AIGEN holders vote YES (pay the claim) or NO (reject).
     - Min vote: 10 AIGEN. Vote weight = stake (1 AIGEN = 1 vote).
  3. After voting period (48h), DETERMINISTIC tally:
     - Need quorum: total votes ≥ 200 AIGEN
     - If yes_total > no_total AND quorum met → APPROVED
     - Else → REJECTED
  4. Operator executes on-chain: calls InsurancePool.payClaim(victim, ...)
     via /claims/{id}/execute endpoint. The on-chain contract still
     enforces per-claim caps (10% of pool max).
  5. Reward distribution:
     - Approved: filer gets bond back + 5% fee. YES voters split NO stakes
       proportional to their stake. 0.5% of NO pool to insurance pool refresh.
     - Rejected: filer loses bond to NO voters. NO voters split YES + bond.

This makes InsurancePool claim authority truly distributed. A single
operator can no longer unilaterally pay (or refuse) claims — the DAO
decides, operator just executes the deterministic outcome.

v1 = operator-executed (we still call payClaim on-chain after vote).
v2 = on-chain governance contract verifies DAO sig before payout.
"""
import json
import re
import time
import uuid
from pathlib import Path

CLAIMS_FILE = Path("/home/luna/crypto-genesis/aigen/claims.json")
LEDGER = Path("/home/luna/crypto-genesis/shield-rewards/ledger.json")

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")

MIN_FILER_BOND = 100              # AIGEN
MIN_FILER_ELO = 1500              # base ELO; effectively any rep agent qualifies
MIN_VOTE = 10                     # AIGEN per vote
QUORUM_AIGEN = 200                # total YES + NO needed for valid resolution
DEFAULT_VOTING_HOURS = 48
APPROVAL_FEE_BPS = 500            # 5% of approved amount → filer (paid in claimed token by operator post-execute)
INSURANCE_REFRESH_BPS = 50        # 0.5% of loser pool → refresh fund (off-chain marker for now)


def load() -> dict:
    if CLAIMS_FILE.exists():
        return json.loads(CLAIMS_FILE.read_text())
    return {
        "claims": [], "total": 0,
        "approved": 0, "rejected": 0, "voided": 0,
        "lifetime_volume_aigen": 0,
    }


def save(d: dict):
    CLAIMS_FILE.write_text(json.dumps(d, indent=2))


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
# Filer reputation gate
# =====================================================================

def _filer_eligible(agent_id: str) -> tuple[bool, str]:
    """Filer must have reputation ≥ MIN_FILER_ELO."""
    try:
        from reputation import derive_reputation
        rep = derive_reputation(agent_id)
        if rep["elo"] < MIN_FILER_ELO:
            return False, f"reputation ELO {rep['elo']} below required {MIN_FILER_ELO}"
        return True, "ok"
    except Exception:
        # If reputation system fails, conservatively allow (fail-open for filer)
        return True, "rep system unavailable"


# =====================================================================
# Public API
# =====================================================================

def file_claim(filer_agent_id: str, victim_wallet: str, token_address: str,
               amount_wei: int, swap_tx_hash: str, chain: str = "base",
               evidence_url: str = "", voting_hours: int = DEFAULT_VOTING_HOURS) -> dict:
    """Open a new insurance claim for DAO vote."""
    if not filer_agent_id or len(filer_agent_id.strip()) < 2:
        return {"error": "filer_agent_id must be >= 2 chars"}
    if not ADDRESS_RE.match(victim_wallet or ""):
        return {"error": "victim_wallet must be 0x-prefixed 40-char hex"}
    if not ADDRESS_RE.match(token_address or "") and token_address.lower() != "0x0000000000000000000000000000000000000000":
        return {"error": "token_address must be 0x-prefixed (or 0x000…0 for native ETH)"}
    if amount_wei <= 0:
        return {"error": "amount_wei must be positive"}
    if not TX_HASH_RE.match(swap_tx_hash or ""):
        return {"error": "swap_tx_hash must be 0x-prefixed 64-char hex"}

    eligible, reason = _filer_eligible(filer_agent_id)
    if not eligible:
        return {"error": f"filer not eligible: {reason}", "min_elo_required": MIN_FILER_ELO}

    if _balance(filer_agent_id) < MIN_FILER_BOND:
        return {"error": f"insufficient AIGEN for bond: have {_balance(filer_agent_id)}, need {MIN_FILER_BOND}"}
    if not _debit(filer_agent_id, MIN_FILER_BOND, f"file-claim-bond"):
        return {"error": "bond debit failed"}

    now = int(time.time())
    claim_id = "claim_" + uuid.uuid4().hex[:12]
    c = {
        "id": claim_id,
        "filer": filer_agent_id,
        "victim_wallet": victim_wallet.lower(),
        "token_address": token_address.lower(),
        "amount_wei": int(amount_wei),
        "swap_tx_hash": swap_tx_hash.lower(),
        "chain": chain,
        "evidence_url": (evidence_url or "")[:500],
        "filed_at": now,
        "voting_deadline": now + voting_hours * 3600,
        "status": "voting",                 # voting | approved | rejected | voided | executed
        "filer_bond_aigen": MIN_FILER_BOND,
        "yes_votes": {},                    # agent_id → AIGEN
        "no_votes": {},
        "yes_total": 0,
        "no_total": 0,
        "execution_tx": None,                # set when /claims/{id}/execute on-chain succeeds
    }
    d = load()
    d["claims"].append(c)
    d["total"] += 1
    d["lifetime_volume_aigen"] = d.get("lifetime_volume_aigen", 0) + MIN_FILER_BOND
    save(d)
    return c


def vote(agent_id: str, claim_id: str, side: str, amount: int) -> dict:
    if side not in ("yes", "no"):
        return {"error": "side must be 'yes' or 'no'"}
    if amount < MIN_VOTE:
        return {"error": f"min vote: {MIN_VOTE} AIGEN"}
    d = load()
    for c in d["claims"]:
        if c["id"] != claim_id:
            continue
        if c["status"] != "voting":
            return {"error": f"claim is {c['status']}"}
        if int(time.time()) >= c["voting_deadline"]:
            return {"error": "voting closed; call resolve_claim()"}
        if not _debit(agent_id, amount, f"vote-{side}-claim-{claim_id}"):
            return {"error": "insufficient balance"}
        bucket = c[f"{side}_votes"]
        bucket[agent_id] = bucket.get(agent_id, 0) + amount
        c[f"{side}_total"] = c.get(f"{side}_total", 0) + amount
        d["lifetime_volume_aigen"] = d.get("lifetime_volume_aigen", 0) + amount
        save(d)
        return {"ok": True, "claim_id": claim_id, "side": side,
                "your_total": bucket[agent_id],
                "yes_total": c["yes_total"], "no_total": c["no_total"],
                "voting_deadline": c["voting_deadline"]}
    return {"error": "claim not found"}


def resolve(claim_id: str) -> dict:
    """Tally votes and resolve. Anyone can call after voting deadline.
    Distributes AIGEN between voters. The on-chain payClaim is a SEPARATE
    operator step (call /claims/{id}/execute)."""
    d = load()
    for c in d["claims"]:
        if c["id"] != claim_id:
            continue
        if c["status"] != "voting":
            return {"error": f"claim is {c['status']}"}
        if int(time.time()) < c["voting_deadline"]:
            return {"error": "voting period not yet over"}

        total_votes = c["yes_total"] + c["no_total"]
        if total_votes < QUORUM_AIGEN:
            # Quorum failed → void, refund all stakes including bond
            _credit(c["filer"], c["filer_bond_aigen"], f"void-refund-bond-{claim_id}")
            for agent_id, amt in {**c["yes_votes"], **c["no_votes"]}.items():
                _credit(agent_id, amt, f"void-refund-vote-{claim_id}")
            c["status"] = "voided"
            c["resolution"] = "VOID_NO_QUORUM"
            c["resolved_at"] = int(time.time())
            d["voided"] = d.get("voided", 0) + 1
            save(d)
            return {"resolved": True, "outcome": "VOID_NO_QUORUM",
                    "quorum_required": QUORUM_AIGEN, "total_votes": total_votes,
                    "claim": c}

        approved = c["yes_total"] > c["no_total"]
        if approved:
            outcome = "APPROVED"
            winners = c["yes_votes"]
            losers  = c["no_votes"]
            winner_total = c["yes_total"]
            loser_total  = c["no_total"]
            # Bond refunded to filer
            _credit(c["filer"], c["filer_bond_aigen"], f"approved-bond-refund-{claim_id}")
        else:
            outcome = "REJECTED"
            winners = c["no_votes"]
            losers  = c["yes_votes"]
            winner_total = c["no_total"]
            loser_total  = c["yes_total"]
            # Bond forfeited to NO voters' pool
            loser_total += c["filer_bond_aigen"]

        # Distribute losers' AIGEN to winners proportionally
        insurance_refresh = (loser_total * INSURANCE_REFRESH_BPS) // 10000
        winners_pool = loser_total - insurance_refresh

        payouts = {}
        if winner_total > 0 and winners_pool > 0:
            for agent_id, stake_amt in winners.items():
                share = (winners_pool * stake_amt) // winner_total
                payouts[agent_id] = stake_amt + share
                _credit(agent_id, payouts[agent_id], f"win-claim-vote-{outcome}-{claim_id}")
        else:
            # Edge case: one side empty — refund the other side
            for agent_id, amt in winners.items():
                _credit(agent_id, amt, f"unopposed-refund-{claim_id}")

        if insurance_refresh > 0:
            _credit("aigen-insurance-pool", insurance_refresh, f"claim-fee-{claim_id}")

        c["status"] = outcome.lower()
        c["resolution"] = outcome
        c["resolved_at"] = int(time.time())
        c["payouts"] = payouts
        c["insurance_refresh_aigen"] = insurance_refresh
        if approved:
            d["approved"] = d.get("approved", 0) + 1
        else:
            d["rejected"] = d.get("rejected", 0) + 1
        save(d)
        return {"resolved": True, "outcome": outcome, "payouts": payouts,
                "insurance_refresh_aigen": insurance_refresh, "claim": c}
    return {"error": "claim not found"}


def mark_executed(claim_id: str, execution_tx: str):
    """Operator: marks an approved claim as on-chain executed.
    Called by /claims/{id}/execute REST endpoint after payClaim succeeds."""
    d = load()
    for c in d["claims"]:
        if c["id"] == claim_id:
            c["execution_tx"] = execution_tx
            c["executed_at"] = int(time.time())
            c["status"] = "executed"
            save(d)
            return c
    return None


def get_claim(claim_id: str):
    d = load()
    for c in d["claims"]:
        if c["id"] == claim_id:
            return c
    return None


def list_active():
    d = load()
    now = int(time.time())
    return [c for c in d["claims"] if c["status"] == "voting" and now < c["voting_deadline"]]


def list_due():
    d = load()
    now = int(time.time())
    return [c for c in d["claims"] if c["status"] == "voting" and now >= c["voting_deadline"]]


def list_pending_execution():
    """Approved claims that haven't been executed on-chain yet."""
    d = load()
    return [c for c in d["claims"] if c["status"] == "approved" and not c.get("execution_tx")]


def stats() -> dict:
    d = load()
    return {
        "total": d.get("total", 0),
        "active_voting": len(list_active()),
        "due_for_resolution": len(list_due()),
        "approved": d.get("approved", 0),
        "rejected": d.get("rejected", 0),
        "voided": d.get("voided", 0),
        "pending_execution": len(list_pending_execution()),
        "lifetime_volume_aigen": d.get("lifetime_volume_aigen", 0),
        "min_filer_bond": MIN_FILER_BOND,
        "min_filer_elo": MIN_FILER_ELO,
        "quorum_aigen": QUORUM_AIGEN,
    }
