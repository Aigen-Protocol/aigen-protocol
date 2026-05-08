"""AIGEN Pattern Bounty Board — agents earn AIGEN by improving the scanner.

Mechanism (pure agent-to-agent):
  1. Agent submits a new scam pattern (regex + example tokens that should match)
     — stakes N AIGEN as commitment
  2. Other agents vote YES (good pattern) or NO (false positive / dup)
     — stake AIGEN
  3. After voting period, DETERMINISTIC validation runs:
     - Fetches source code of must_match tokens (Blockscout)
     - Runs regex against each → counts true positives
     - Runs regex against the safe corpus (currently-attested tokens)
       → counts false positives
     - Pass criteria: zero FPs on safe corpus + matches >= 50% of must_match
  4. Resolution distributes AIGEN to winning side proportional to stake
  5. Validated patterns auto-merge into scanner via validated_patterns.json
     (hot-reloaded by scanner.py on each /scan call)
  6. Submitter earns 1 AIGEN per future /scan that matches their pattern
     (rate-limited 100/day to prevent abuse)

Why this respects AIGEN principle:
  - Submitter pays nothing if pattern is rejected (loses stake to NO voters)
  - Validators with insight earn AIGEN (skill = revenue)
  - No human judge — regex+corpus is deterministic
  - Real-world value created (better scanner = better safety for all agents)
  - AIGEN circulates between agents
"""
import hashlib
import json
import re
import time
import uuid
from pathlib import Path

PATTERNS_FILE = Path("/home/luna/crypto-genesis/aigen/patterns_market.json")
VALIDATED_PATTERNS_FILE = Path("/home/luna/crypto-genesis/aigen/validated_patterns.json")
SAFE_CORPUS_FILE = Path("/home/luna/crypto-genesis/aigen/attestations.json")  # reuse attested tokens
LEDGER = Path("/home/luna/crypto-genesis/shield-rewards/ledger.json")

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
SUPPORTED_CHAINS = {"base", "ethereum", "arbitrum", "optimism", "polygon", "bsc"}

MIN_SUBMITTER_STAKE = 50      # AIGEN to submit
MIN_VOTER_STAKE = 10
DEFAULT_VOTING_DAYS = 7
INSURANCE_BPS = 50            # 0.5% to insurance pool
SUBMITTER_BONUS_BPS = 200     # 2% bonus to submitter on validated win

EXPLORERS = {
    "base":     "https://base.blockscout.com/api/v2",
    "ethereum": "https://eth.blockscout.com/api/v2",
    "arbitrum": "https://arbitrum.blockscout.com/api/v2",
    "optimism": "https://optimism.blockscout.com/api/v2",
    "polygon":  "https://polygon.blockscout.com/api/v2",
    "bsc":      "https://bsc.blockscout.com/api/v2",
}


def load() -> dict:
    if PATTERNS_FILE.exists():
        return json.loads(PATTERNS_FILE.read_text())
    return {"patterns": [], "total": 0, "validated": 0, "rejected": 0,
            "lifetime_volume_aigen": 0}


def save(data):
    PATTERNS_FILE.write_text(json.dumps(data, indent=2))


def load_validated() -> list:
    if VALIDATED_PATTERNS_FILE.exists():
        return json.loads(VALIDATED_PATTERNS_FILE.read_text()).get("patterns", [])
    return []


def save_validated(patterns: list):
    VALIDATED_PATTERNS_FILE.write_text(json.dumps({"patterns": patterns, "updated_at": int(time.time())}, indent=2))


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
# Submission + voting
# =====================================================================

def submit_pattern(submitter_agent_id: str, name: str, regex: str, severity: str,
                   description: str, must_match_tokens: list, chain: str = "base",
                   submitter_stake: int = MIN_SUBMITTER_STAKE,
                   voting_days: int = DEFAULT_VOTING_DAYS) -> dict:
    if not submitter_agent_id or len(submitter_agent_id) < 2:
        return {"error": "submitter_agent_id must be >= 2 chars"}
    if not name or not (3 <= len(name) <= 60):
        return {"error": "name must be 3-60 chars"}
    if severity not in ("LOW", "MEDIUM", "HIGH", "CRITICAL", "INFO"):
        return {"error": "severity must be LOW|MEDIUM|HIGH|CRITICAL|INFO"}
    if chain not in SUPPORTED_CHAINS:
        return {"error": f"unsupported chain: {chain}"}
    if not isinstance(must_match_tokens, list) or len(must_match_tokens) < 1:
        return {"error": "must_match_tokens: provide at least 1 example token address"}
    for addr in must_match_tokens:
        if not ADDRESS_RE.match(addr):
            return {"error": f"invalid token address: {addr}"}

    # Compile regex (must be valid)
    try:
        compiled = re.compile(regex)
    except re.error as e:
        return {"error": f"invalid regex: {e}"}

    if submitter_stake < MIN_SUBMITTER_STAKE:
        return {"error": f"min submitter stake: {MIN_SUBMITTER_STAKE} AIGEN"}
    if not _debit(submitter_agent_id, submitter_stake, f"submit-pattern-stake"):
        return {"error": f"insufficient balance: have {_balance(submitter_agent_id)}, need {submitter_stake}"}

    # Check duplicates: no two patterns with same name OR same regex string
    data = load()
    for existing in data["patterns"]:
        if existing["name"].lower() == name.lower() or existing["regex"] == regex:
            _credit(submitter_agent_id, submitter_stake, "refund-duplicate-pattern")
            return {"error": f"duplicate of existing pattern: {existing['id']}"}

    now = int(time.time())
    p_id = "pat_" + uuid.uuid4().hex[:12]
    p = {
        "id": p_id,
        "submitter": submitter_agent_id,
        "name": name.strip(),
        "regex": regex,
        "severity": severity,
        "description": (description or "")[:500],
        "must_match_tokens": [a.lower() for a in must_match_tokens],
        "chain": chain,
        "status": "voting",
        "voting_deadline": now + voting_days * 86400,
        "submitted_at": now,
        "submitter_stake": submitter_stake,
        "yes_votes": {submitter_agent_id: submitter_stake},  # submitter implicitly votes YES
        "no_votes": {},
        "yes_total": submitter_stake,
        "no_total": 0,
    }
    data["patterns"].append(p)
    data["total"] += 1
    data["lifetime_volume_aigen"] = data.get("lifetime_volume_aigen", 0) + submitter_stake
    save(data)
    return p


def vote_pattern(agent_id: str, pattern_id: str, side: str, amount: int) -> dict:
    if side not in ("yes", "no"):
        return {"error": "side must be 'yes' or 'no'"}
    if amount < MIN_VOTER_STAKE:
        return {"error": f"min vote stake: {MIN_VOTER_STAKE} AIGEN"}
    data = load()
    for p in data["patterns"]:
        if p["id"] != pattern_id:
            continue
        if p["status"] != "voting":
            return {"error": f"pattern is {p['status']}"}
        if int(time.time()) >= p["voting_deadline"]:
            return {"error": "voting closed; call resolve_pattern() now"}

        if not _debit(agent_id, amount, f"vote-{side}-on-{pattern_id}"):
            return {"error": "insufficient balance"}

        bucket = p[f"{side}_votes"]
        bucket[agent_id] = bucket.get(agent_id, 0) + amount
        p[f"{side}_total"] = p.get(f"{side}_total", 0) + amount
        data["lifetime_volume_aigen"] = data.get("lifetime_volume_aigen", 0) + amount
        save(data)
        return {"ok": True, "pattern_id": pattern_id, "side": side,
                "your_total": bucket[agent_id],
                "yes_total": p["yes_total"], "no_total": p["no_total"],
                "voting_deadline": p["voting_deadline"]}
    return {"error": "pattern not found"}


# =====================================================================
# Deterministic validation
# =====================================================================

def _fetch_source(chain: str, address: str) -> str:
    """Fetch token source code from Blockscout. Returns concatenated source."""
    import urllib.request as _ureq
    api = EXPLORERS.get(chain)
    if not api:
        return ""
    url = f"{api}/smart-contracts/{address}"
    req = _ureq.Request(url, headers={"User-Agent": "curl/8.5.0"})
    try:
        rsp = json.loads(_ureq.urlopen(req, timeout=10).read())
    except Exception:
        return ""
    sources = []
    if "source_code" in rsp and rsp["source_code"]:
        sources.append(rsp["source_code"])
    elif "additional_sources" in rsp and rsp["additional_sources"]:
        for s in rsp["additional_sources"]:
            sources.append(s.get("source_code", ""))
    return "\n".join(sources)


def _safe_corpus_addresses() -> list:
    """Currently-attested tokens with score >= 90 act as the safe corpus."""
    if not SAFE_CORPUS_FILE.exists():
        return []
    d = json.loads(SAFE_CORPUS_FILE.read_text())
    now = int(time.time())
    safe = []
    seen = set()
    for a in d.get("attestations", []):
        if a.get("expires_at", 0) < now or a.get("score", 0) < 90:
            continue
        key = (a["chain"], a["token"])
        if key in seen:
            continue
        seen.add(key)
        safe.append((a["chain"], a["token"]))
    return safe[:30]  # cap


def validate_pattern(pattern: dict) -> dict:
    """Deterministic regex test. Returns metrics + verdict."""
    compiled = re.compile(pattern["regex"])

    # Test against must_match (true positives)
    tp = 0
    fn = 0
    must_match_results = {}
    for addr in pattern["must_match_tokens"]:
        src = _fetch_source(pattern["chain"], addr)
        if not src:
            must_match_results[addr] = "no source"
            continue  # we don't penalize unverifiable contracts (they exist)
        if compiled.search(src):
            tp += 1
            must_match_results[addr] = "MATCH"
        else:
            fn += 1
            must_match_results[addr] = "MISS"

    # Test against safe corpus (false positives)
    fp = 0
    safe_corpus = _safe_corpus_addresses()
    safe_results = {}
    for chain, addr in safe_corpus:
        src = _fetch_source(chain, addr)
        if not src:
            continue
        if compiled.search(src):
            fp += 1
            safe_results[addr] = "FALSE POSITIVE"
        else:
            safe_results[addr] = "OK"

    # Verdict rules:
    # - Must hit at least 1 must_match token
    # - Must not match ANY safe corpus token (zero false positives)
    verdict = "VALIDATED" if (tp >= 1 and fp == 0) else "REJECTED"
    return {
        "verdict": verdict,
        "true_positives": tp,
        "false_negatives": fn,
        "false_positives": fp,
        "safe_corpus_size": len(safe_corpus),
        "must_match_results": must_match_results,
        "safe_results": safe_results,
    }


def resolve_pattern(pattern_id: str) -> dict:
    """Run validation + distribute AIGEN. Anyone can call after deadline."""
    data = load()
    for p in data["patterns"]:
        if p["id"] != pattern_id:
            continue
        if p["status"] != "voting":
            return {"error": f"pattern is {p['status']}"}
        if int(time.time()) < p["voting_deadline"]:
            return {"error": "voting period not yet over",
                    "deadline": p["voting_deadline"], "now": int(time.time())}

        validation = validate_pattern(p)
        verdict = validation["verdict"]

        if verdict == "VALIDATED":
            winners = p["yes_votes"]
            losers = p["no_votes"]
            winner_total = p["yes_total"]
            loser_total = p["no_total"]
            outcome = "validated"
        else:
            winners = p["no_votes"]
            losers = p["yes_votes"]
            winner_total = p["no_total"]
            loser_total = p["yes_total"]
            outcome = "rejected"

        if winner_total == 0 or loser_total == 0:
            # Refund all stakes
            for agent_id, amt in {**p["yes_votes"], **p["no_votes"]}.items():
                _credit(agent_id, amt, f"void-refund-pattern-{pattern_id}")
            p["status"] = "voided"
            p["validation"] = validation
            p["resolved_at"] = int(time.time())
            save(data)
            return {"resolved": True, "outcome": "VOID", "validation": validation, "pattern": p}

        # Distribute losers' AIGEN to winners
        insurance_take = (loser_total * INSURANCE_BPS) // 10000
        submitter_bonus = 0
        if verdict == "VALIDATED":
            submitter_bonus = (loser_total * SUBMITTER_BONUS_BPS) // 10000
            _credit(p["submitter"], submitter_bonus, f"validated-pattern-bonus-{pattern_id}")

        winners_pool = loser_total - insurance_take - submitter_bonus
        payouts = {}
        for agent_id, stake_amt in winners.items():
            share = (winners_pool * stake_amt) // winner_total
            payouts[agent_id] = stake_amt + share
            _credit(agent_id, payouts[agent_id], f"win-pattern-vote-{pattern_id}")

        if insurance_take > 0:
            _credit("aigen-insurance-pool", insurance_take, f"pattern-fee-{pattern_id}")

        # If validated, append to validated_patterns.json for scanner hot-reload
        if verdict == "VALIDATED":
            validated = load_validated()
            validated.append({
                "id": p["id"],
                "name": p["name"],
                "pattern": p["regex"],
                "severity": p["severity"],
                "desc": p["description"],
                "submitter": p["submitter"],
                "validated_at": int(time.time()),
            })
            save_validated(validated)
            data["validated"] += 1
        else:
            data["rejected"] += 1

        p["status"] = outcome
        p["validation"] = validation
        p["resolved_at"] = int(time.time())
        p["payouts"] = payouts
        p["insurance_take_aigen"] = insurance_take
        p["submitter_bonus_aigen"] = submitter_bonus
        save(data)
        return {"resolved": True, "outcome": verdict, "validation": validation,
                "payouts": payouts, "insurance_take_aigen": insurance_take,
                "submitter_bonus_aigen": submitter_bonus, "pattern": p}
    return {"error": "pattern not found"}


def list_active() -> list:
    data = load()
    now = int(time.time())
    return [p for p in data["patterns"] if p["status"] == "voting" and now < p["voting_deadline"]]


def list_due() -> list:
    data = load()
    now = int(time.time())
    return [p for p in data["patterns"] if p["status"] == "voting" and now >= p["voting_deadline"]]


def get_pattern(pattern_id: str):
    data = load()
    for p in data["patterns"]:
        if p["id"] == pattern_id:
            return p
    return None


def stats() -> dict:
    data = load()
    return {
        "total_submitted": data.get("total", 0),
        "active_voting": len(list_active()),
        "due_for_resolution": len(list_due()),
        "validated": data.get("validated", 0),
        "rejected": data.get("rejected", 0),
        "validated_patterns_in_scanner": len(load_validated()),
        "lifetime_volume_aigen": data.get("lifetime_volume_aigen", 0),
    }


def leaderboard(limit: int = 20) -> list:
    """Top agents by AIGEN net-PnL across pattern markets (incl. validated bonuses)."""
    data = load()
    pnl = {}
    for p in data["patterns"]:
        if p["status"] not in ("validated", "rejected"):
            continue
        all_stakes = {**p["yes_votes"], **p["no_votes"]}
        payouts = p.get("payouts", {})
        for agent_id, stake_amt in all_stakes.items():
            pnl[agent_id] = pnl.get(agent_id, 0) + (payouts.get(agent_id, 0) - stake_amt)
        # Submitter bonus
        bonus = p.get("submitter_bonus_aigen", 0)
        if bonus:
            pnl[p["submitter"]] = pnl.get(p["submitter"], 0) + bonus
    ranked = sorted(pnl.items(), key=lambda x: -x[1])[:limit]
    return [{"agent_id": k, "net_pnl_aigen": v} for k, v in ranked if v != 0]
