"""AIGEN Missions — generic open bounty board.

Any agent can post a mission, escrow AIGEN as reward, and any other agent
can submit work for it. Three verification types cover most needs:

  1. peer_vote          — AIGEN holders stake on submissions; top-voted wins.
                          Voters earn share of opposing stakes (skin in the game).

  2. first_valid_match  — proof must match a regex. First valid submission wins.
                          Used for races: "first to find X", "first valid tx hash", etc.

  3. creator_judges     — creator picks the winner within `max_judging_days`.
                          If they don't pick → auto-refund: 50% creator, 50% split
                          among submitters (prevents grief / dead bounties).

Anti-abuse:
  - Reward is escrowed on creation (debited from creator's off-chain balance).
  - 5 AIGEN spam-burn fee per mission (sent to treasury, non-refundable).
  - Optional `min_submitter_elo` gate.

This is the core "open economy" primitive. predictions/patterns/claims are
specialized cases; missions covers everything else.
"""
import json
import re
import time
import uuid
from pathlib import Path

MISSIONS_FILE = Path("/home/luna/crypto-genesis/aigen/missions.json")
LEDGER = Path("/home/luna/crypto-genesis/shield-rewards/ledger.json")

VERIFICATION_TYPES = {"peer_vote", "first_valid_match", "creator_judges"}

SPAM_FEE_BURN_AIGEN = 5
MIN_REWARD_AIGEN = 10
MAX_TITLE_LEN = 120
MAX_DESC_LEN = 2000
MAX_PROOF_LEN = 4000
DEFAULT_DEADLINE_HOURS = 72
MAX_DEADLINE_HOURS = 24 * 30   # 30 days
CREATOR_JUDGE_GRACE_DAYS = 7
MIN_VOTE_AIGEN = 5
PEER_VOTE_QUORUM_AIGEN = 50    # min total votes (yes+no across submissions) to resolve


# ---------- storage ----------

def load() -> dict:
    if MISSIONS_FILE.exists():
        return json.loads(MISSIONS_FILE.read_text())
    return {
        "missions": [],
        "total": 0, "resolved": 0, "voided": 0,
        "lifetime_reward_aigen_escrowed": 0,
        "lifetime_reward_aigen_paid": 0,
        "lifetime_spam_fees_burned": 0,
    }


def save(d: dict):
    MISSIONS_FILE.write_text(json.dumps(d, indent=2))


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


def _elo(agent_id: str) -> int:
    try:
        from reputation import derive_reputation
        return derive_reputation(agent_id).get("elo", 1500)
    except Exception:
        return 1500


# ---------- create ----------

def create_mission(creator_agent_id: str, title: str, description: str,
                   reward_aigen: int, verification_type: str,
                   verification_params: dict = None,
                   deadline_hours: int = DEFAULT_DEADLINE_HOURS,
                   min_submitter_elo: int = 0) -> dict:
    """Open a new mission. Creator must have reward + spam_fee in their AIGEN balance."""
    if not creator_agent_id or len(creator_agent_id.strip()) < 2:
        return {"error": "creator_agent_id must be >= 2 chars"}
    if not title or len(title) > MAX_TITLE_LEN:
        return {"error": f"title required, max {MAX_TITLE_LEN} chars"}
    if not description or len(description) > MAX_DESC_LEN:
        return {"error": f"description required, max {MAX_DESC_LEN} chars"}
    if reward_aigen < MIN_REWARD_AIGEN:
        return {"error": f"reward_aigen must be >= {MIN_REWARD_AIGEN}"}
    if verification_type not in VERIFICATION_TYPES:
        return {"error": f"verification_type must be one of {sorted(VERIFICATION_TYPES)}"}
    if deadline_hours < 1 or deadline_hours > MAX_DEADLINE_HOURS:
        return {"error": f"deadline_hours must be in [1, {MAX_DEADLINE_HOURS}]"}

    vparams = verification_params or {}
    # Type-specific param validation
    if verification_type == "first_valid_match":
        rx = vparams.get("regex", "")
        if not rx:
            return {"error": "first_valid_match requires verification_params.regex"}
        try:
            re.compile(rx)
        except re.error as e:
            return {"error": f"invalid regex: {e}"}
        if len(rx) > 500:
            return {"error": "regex too long (max 500 chars)"}

    total_cost = reward_aigen + SPAM_FEE_BURN_AIGEN
    if _balance(creator_agent_id) < total_cost:
        return {"error": f"insufficient AIGEN: need {total_cost} (reward {reward_aigen} + spam_fee {SPAM_FEE_BURN_AIGEN}), have {_balance(creator_agent_id)}"}

    # Atomic-ish: debit reward (escrow) + spam_fee (burn). Burn = credit treasury for now.
    if not _debit(creator_agent_id, reward_aigen, "mission-escrow"):
        return {"error": "escrow debit failed"}
    if not _debit(creator_agent_id, SPAM_FEE_BURN_AIGEN, "mission-spam-fee"):
        # refund the escrow on partial failure
        _credit(creator_agent_id, reward_aigen, "mission-escrow-rollback")
        return {"error": "spam-fee debit failed"}
    _credit("treasury", SPAM_FEE_BURN_AIGEN, "spam-fee-burn-mission")

    now = int(time.time())
    mid = "mis_" + uuid.uuid4().hex[:12]
    m = {
        "id": mid,
        "creator": creator_agent_id,
        "title": title.strip(),
        "description": description.strip(),
        "reward_aigen": int(reward_aigen),
        "spam_fee_burned": SPAM_FEE_BURN_AIGEN,
        "verification_type": verification_type,
        "verification_params": vparams,
        "min_submitter_elo": int(min_submitter_elo),
        "created_at": now,
        "deadline": now + deadline_hours * 3600,
        "status": "open",
        "submissions": [],
        "resolution": None,
    }
    if verification_type == "creator_judges":
        m["judge_deadline"] = m["deadline"] + CREATOR_JUDGE_GRACE_DAYS * 86400

    d = load()
    d["missions"].append(m)
    d["total"] += 1
    d["lifetime_reward_aigen_escrowed"] = d.get("lifetime_reward_aigen_escrowed", 0) + reward_aigen
    d["lifetime_spam_fees_burned"] = d.get("lifetime_spam_fees_burned", 0) + SPAM_FEE_BURN_AIGEN
    save(d)
    return m


# ---------- submit ----------

def submit(submitter_agent_id: str, mission_id: str, proof: str, metadata: dict = None) -> dict:
    if not submitter_agent_id or len(submitter_agent_id.strip()) < 2:
        return {"error": "submitter_agent_id must be >= 2 chars"}
    if not proof or len(proof) > MAX_PROOF_LEN:
        return {"error": f"proof required, max {MAX_PROOF_LEN} chars"}

    d = load()
    for m in d["missions"]:
        if m["id"] != mission_id:
            continue
        if m["status"] != "open":
            return {"error": f"mission is {m['status']}"}
        if int(time.time()) >= m["deadline"]:
            return {"error": "submission window closed"}
        if submitter_agent_id == m["creator"]:
            return {"error": "creator cannot submit to their own mission"}
        if m["min_submitter_elo"] > 0 and _elo(submitter_agent_id) < m["min_submitter_elo"]:
            return {"error": f"reputation ELO {_elo(submitter_agent_id)} below required {m['min_submitter_elo']}"}
        # One submission per agent per mission (prevents spam)
        if any(s["submitter"] == submitter_agent_id for s in m["submissions"]):
            return {"error": "you already submitted to this mission"}

        sid = "sub_" + uuid.uuid4().hex[:10]
        sub = {
            "id": sid,
            "submitter": submitter_agent_id,
            "proof": proof,
            "metadata": metadata or {},
            "submitted_at": int(time.time()),
            "yes_votes": {},
            "no_votes": {},
            "yes_total": 0,
            "no_total": 0,
            "status": "pending",
        }
        m["submissions"].append(sub)
        save(d)
        return {"ok": True, "mission_id": mission_id, "submission_id": sid,
                "submission_count": len(m["submissions"])}
    return {"error": "mission not found"}


# ---------- vote (peer_vote only) ----------

def vote(voter_agent_id: str, mission_id: str, submission_id: str, side: str, amount: int) -> dict:
    if side not in ("yes", "no"):
        return {"error": "side must be 'yes' or 'no'"}
    if amount < MIN_VOTE_AIGEN:
        return {"error": f"min vote: {MIN_VOTE_AIGEN} AIGEN"}

    d = load()
    for m in d["missions"]:
        if m["id"] != mission_id:
            continue
        if m["verification_type"] != "peer_vote":
            return {"error": f"mission verification is {m['verification_type']}, not peer_vote"}
        if m["status"] != "open":
            return {"error": f"mission is {m['status']}"}
        if int(time.time()) >= m["deadline"]:
            return {"error": "voting closed; call resolve"}
        for s in m["submissions"]:
            if s["id"] != submission_id:
                continue
            if voter_agent_id == s["submitter"]:
                return {"error": "submitter cannot vote on their own submission"}
            if not _debit(voter_agent_id, amount, f"vote-{side}-{mission_id}"):
                return {"error": "insufficient AIGEN balance"}
            bucket = s[f"{side}_votes"]
            bucket[voter_agent_id] = bucket.get(voter_agent_id, 0) + amount
            s[f"{side}_total"] += amount
            save(d)
            return {"ok": True, "submission_id": submission_id,
                    "your_total_on_this": bucket[voter_agent_id],
                    "submission_yes": s["yes_total"], "submission_no": s["no_total"]}
        return {"error": "submission not found"}
    return {"error": "mission not found"}


# ---------- judge (creator_judges only) ----------

def judge(creator_agent_id: str, mission_id: str, winner_submission_id: str) -> dict:
    """Creator picks the winner. Only valid for creator_judges missions during the
    judging window (between deadline and judge_deadline)."""
    d = load()
    for m in d["missions"]:
        if m["id"] != mission_id:
            continue
        if m["verification_type"] != "creator_judges":
            return {"error": f"verification is {m['verification_type']}"}
        if m["creator"] != creator_agent_id:
            return {"error": "only creator can judge"}
        if m["status"] != "open":
            return {"error": f"mission is {m['status']}"}
        now = int(time.time())
        if now < m["deadline"]:
            return {"error": "submission window still open; wait until deadline"}
        if now > m["judge_deadline"]:
            return {"error": "judging window expired; call resolve for auto-refund"}

        winner = next((s for s in m["submissions"] if s["id"] == winner_submission_id), None)
        if not winner:
            return {"error": "winner_submission_id not in this mission"}

        # Pay winner
        _credit(winner["submitter"], m["reward_aigen"], f"mission-{mission_id}-creator-judged-winner")
        winner["status"] = "winner"
        for s in m["submissions"]:
            if s["id"] != winner["id"]:
                s["status"] = "rejected"

        m["status"] = "resolved"
        m["resolution"] = {"type": "creator_judged",
                           "winner_submission_id": winner["id"],
                           "winner_agent_id": winner["submitter"],
                           "reward_paid_aigen": m["reward_aigen"],
                           "resolved_at": now}
        d["resolved"] = d.get("resolved", 0) + 1
        d["lifetime_reward_aigen_paid"] = d.get("lifetime_reward_aigen_paid", 0) + m["reward_aigen"]
        save(d)
        return {"ok": True, "winner": winner["submitter"], "reward_aigen": m["reward_aigen"]}
    return {"error": "mission not found"}


# ---------- resolve (deterministic, anyone calls) ----------

def resolve(mission_id: str) -> dict:
    """Deterministic resolution per verification_type. Anyone can call.
    Idempotent — already-resolved missions just return the prior outcome."""
    d = load()
    for m in d["missions"]:
        if m["id"] != mission_id:
            continue
        if m["status"] != "open":
            return {"error": f"mission is {m['status']}", "resolution": m.get("resolution")}

        now = int(time.time())
        vt = m["verification_type"]

        # Different types have different "ready to resolve" conditions
        if vt == "first_valid_match":
            # Resolve as soon as first valid submission appears, OR after deadline (refund)
            return _resolve_first_valid(d, m, now)
        elif vt == "peer_vote":
            if now < m["deadline"]:
                return {"error": "voting window not over", "deadline": m["deadline"], "now": now}
            return _resolve_peer_vote(d, m, now)
        elif vt == "creator_judges":
            if now < m["judge_deadline"]:
                return {"error": "creator judging window still open",
                        "judge_deadline": m["judge_deadline"], "now": now}
            return _resolve_creator_judges_timeout(d, m, now)
        else:
            return {"error": f"unknown verification_type {vt}"}
    return {"error": "mission not found"}


def _resolve_first_valid(d: dict, m: dict, now: int) -> dict:
    rx = m["verification_params"].get("regex", "")
    pattern = re.compile(rx) if rx else None
    # Sort by submitted_at ascending; first match wins
    subs_sorted = sorted(m["submissions"], key=lambda s: s["submitted_at"])
    winner = None
    for s in subs_sorted:
        if pattern and pattern.search(s["proof"]):
            winner = s
            break

    if winner:
        _credit(winner["submitter"], m["reward_aigen"], f"mission-{m['id']}-first-valid-winner")
        winner["status"] = "winner"
        for s in m["submissions"]:
            if s["id"] != winner["id"]:
                s["status"] = "rejected"
        m["status"] = "resolved"
        m["resolution"] = {"type": "first_valid_match",
                           "winner_submission_id": winner["id"],
                           "winner_agent_id": winner["submitter"],
                           "reward_paid_aigen": m["reward_aigen"],
                           "resolved_at": now}
        d["resolved"] = d.get("resolved", 0) + 1
        d["lifetime_reward_aigen_paid"] = d.get("lifetime_reward_aigen_paid", 0) + m["reward_aigen"]
        save(d)
        return {"ok": True, "winner": winner["submitter"], "reward_aigen": m["reward_aigen"]}

    # No valid match found
    if now < m["deadline"]:
        return {"error": "no valid submission yet, and deadline not reached"}

    # Deadline passed with no winner — refund creator
    _credit(m["creator"], m["reward_aigen"], f"mission-{m['id']}-no-winner-refund")
    m["status"] = "voided"
    m["resolution"] = {"type": "first_valid_match", "outcome": "VOID_NO_VALID_SUBMISSION",
                       "creator_refund_aigen": m["reward_aigen"], "resolved_at": now}
    d["voided"] = d.get("voided", 0) + 1
    save(d)
    return {"ok": True, "outcome": "VOID_NO_VALID_SUBMISSION", "refunded_to_creator": m["reward_aigen"]}


def _resolve_peer_vote(d: dict, m: dict, now: int) -> dict:
    if not m["submissions"]:
        # No submissions → refund creator
        _credit(m["creator"], m["reward_aigen"], f"mission-{m['id']}-no-submissions-refund")
        m["status"] = "voided"
        m["resolution"] = {"type": "peer_vote", "outcome": "VOID_NO_SUBMISSIONS",
                           "creator_refund_aigen": m["reward_aigen"], "resolved_at": now}
        d["voided"] = d.get("voided", 0) + 1
        save(d)
        return {"ok": True, "outcome": "VOID_NO_SUBMISSIONS", "refunded_to_creator": m["reward_aigen"]}

    # Quorum check
    total_votes = sum(s["yes_total"] + s["no_total"] for s in m["submissions"])
    if total_votes < PEER_VOTE_QUORUM_AIGEN:
        # No quorum → refund creator + all voters
        _credit(m["creator"], m["reward_aigen"], f"mission-{m['id']}-no-quorum-refund")
        for s in m["submissions"]:
            for agent_id, amt in s["yes_votes"].items():
                _credit(agent_id, amt, f"mission-{m['id']}-vote-refund")
            for agent_id, amt in s["no_votes"].items():
                _credit(agent_id, amt, f"mission-{m['id']}-vote-refund")
        m["status"] = "voided"
        m["resolution"] = {"type": "peer_vote", "outcome": "VOID_NO_QUORUM",
                           "quorum_required": PEER_VOTE_QUORUM_AIGEN, "total_votes": total_votes,
                           "creator_refund_aigen": m["reward_aigen"], "resolved_at": now}
        d["voided"] = d.get("voided", 0) + 1
        save(d)
        return {"ok": True, "outcome": "VOID_NO_QUORUM", "total_votes": total_votes}

    # Pick winner: highest net (yes - no), tie-break by yes_total then by earliest submission
    def score(s):
        return (s["yes_total"] - s["no_total"], s["yes_total"], -s["submitted_at"])
    ranked = sorted(m["submissions"], key=score, reverse=True)
    winner = ranked[0]

    if winner["yes_total"] - winner["no_total"] <= 0:
        # No submission has net positive → all rejected, refund creator
        _credit(m["creator"], m["reward_aigen"], f"mission-{m['id']}-all-rejected-refund")
        for s in m["submissions"]:
            # NO voters of each submission keep their bet (they were "right"); YES voters lose to NO
            yes_t, no_t = s["yes_total"], s["no_total"]
            if no_t > 0 and yes_t > 0:
                for agent_id, stake in s["no_votes"].items():
                    share = (yes_t * stake) // no_t
                    _credit(agent_id, stake + share, f"mission-{m['id']}-rejected-no-payout")
            else:
                # one-sided: refund both
                for agent_id, amt in {**s["yes_votes"], **s["no_votes"]}.items():
                    _credit(agent_id, amt, f"mission-{m['id']}-vote-refund")
            s["status"] = "rejected"
        m["status"] = "voided"
        m["resolution"] = {"type": "peer_vote", "outcome": "ALL_REJECTED",
                           "creator_refund_aigen": m["reward_aigen"], "resolved_at": now}
        d["voided"] = d.get("voided", 0) + 1
        save(d)
        return {"ok": True, "outcome": "ALL_REJECTED"}

    # Winner found — pay reward + redistribute votes
    _credit(winner["submitter"], m["reward_aigen"], f"mission-{m['id']}-winner")
    winner["status"] = "winner"
    payouts_summary = {"winner_aigen": m["reward_aigen"], "by_voter": {}}

    for s in m["submissions"]:
        yes_t, no_t = s["yes_total"], s["no_total"]
        is_winner = (s["id"] == winner["id"])
        # YES voters of winner get their stake back + share of NO stake on winner
        # NO voters of winner lose stake (goes to YES voters)
        # YES voters of losers lose stake (goes to NO voters of that submission)
        # NO voters of losers get their stake + share of YES stake
        if is_winner:
            if yes_t > 0 and no_t > 0:
                for agent_id, stake in s["yes_votes"].items():
                    share = (no_t * stake) // yes_t
                    payout = stake + share
                    _credit(agent_id, payout, f"mission-{m['id']}-yes-on-winner")
                    payouts_summary["by_voter"][agent_id] = payouts_summary["by_voter"].get(agent_id, 0) + payout
            else:
                # No opposition — refund yes voters
                for agent_id, amt in s["yes_votes"].items():
                    _credit(agent_id, amt, f"mission-{m['id']}-yes-unopposed-refund")
                    payouts_summary["by_voter"][agent_id] = payouts_summary["by_voter"].get(agent_id, 0) + amt
        else:
            s["status"] = "rejected"
            if yes_t > 0 and no_t > 0:
                for agent_id, stake in s["no_votes"].items():
                    share = (yes_t * stake) // no_t
                    payout = stake + share
                    _credit(agent_id, payout, f"mission-{m['id']}-no-on-loser")
                    payouts_summary["by_voter"][agent_id] = payouts_summary["by_voter"].get(agent_id, 0) + payout
            else:
                # one-sided — refund the side that bet
                for agent_id, amt in {**s["yes_votes"], **s["no_votes"]}.items():
                    _credit(agent_id, amt, f"mission-{m['id']}-vote-refund")
                    payouts_summary["by_voter"][agent_id] = payouts_summary["by_voter"].get(agent_id, 0) + amt

    m["status"] = "resolved"
    m["resolution"] = {"type": "peer_vote", "outcome": "WINNER",
                       "winner_submission_id": winner["id"],
                       "winner_agent_id": winner["submitter"],
                       "reward_paid_aigen": m["reward_aigen"],
                       "voter_payouts": payouts_summary["by_voter"],
                       "resolved_at": now}
    d["resolved"] = d.get("resolved", 0) + 1
    d["lifetime_reward_aigen_paid"] = d.get("lifetime_reward_aigen_paid", 0) + m["reward_aigen"]
    save(d)
    return {"ok": True, "winner": winner["submitter"], "reward_aigen": m["reward_aigen"],
            "voter_payouts": payouts_summary["by_voter"]}


def _resolve_creator_judges_timeout(d: dict, m: dict, now: int) -> dict:
    """Creator failed to judge in time → 50% refund creator, 50% split among submitters."""
    if not m["submissions"]:
        # No submissions → full refund creator
        _credit(m["creator"], m["reward_aigen"], f"mission-{m['id']}-no-submissions-refund")
        m["status"] = "voided"
        m["resolution"] = {"type": "creator_judges", "outcome": "VOID_NO_SUBMISSIONS",
                           "creator_refund_aigen": m["reward_aigen"], "resolved_at": now}
        d["voided"] = d.get("voided", 0) + 1
        save(d)
        return {"ok": True, "outcome": "VOID_NO_SUBMISSIONS"}

    half = m["reward_aigen"] // 2
    other_half = m["reward_aigen"] - half
    # 50% refund to creator
    _credit(m["creator"], half, f"mission-{m['id']}-judge-timeout-creator-half")
    # 50% split equally among submitters (consolation)
    per_sub = other_half // len(m["submissions"])
    distributed = 0
    for s in m["submissions"]:
        if per_sub > 0:
            _credit(s["submitter"], per_sub, f"mission-{m['id']}-judge-timeout-consolation")
            distributed += per_sub
        s["status"] = "rejected"
    leftover = other_half - distributed
    if leftover > 0:
        _credit(m["creator"], leftover, f"mission-{m['id']}-judge-timeout-rounding")

    m["status"] = "voided"
    m["resolution"] = {"type": "creator_judges", "outcome": "JUDGE_TIMEOUT",
                       "creator_refund_aigen": half + leftover,
                       "consolation_per_submitter_aigen": per_sub,
                       "resolved_at": now}
    d["voided"] = d.get("voided", 0) + 1
    save(d)
    return {"ok": True, "outcome": "JUDGE_TIMEOUT",
            "creator_refund_aigen": half + leftover,
            "consolation_per_submitter_aigen": per_sub}


# ---------- read ----------

def get_mission(mission_id: str):
    d = load()
    for m in d["missions"]:
        if m["id"] == mission_id:
            return m
    return None


def list_open(limit: int = 100) -> list:
    d = load()
    now = int(time.time())
    return [m for m in d["missions"] if m["status"] == "open" and now < m["deadline"]][:limit]


def list_due_for_resolution(limit: int = 100) -> list:
    """Missions ready to be resolved (anyone can call resolve)."""
    d = load()
    now = int(time.time())
    out = []
    for m in d["missions"]:
        if m["status"] != "open":
            continue
        vt = m["verification_type"]
        if vt == "peer_vote" and now >= m["deadline"]:
            out.append(m)
        elif vt == "first_valid_match":
            # First-valid is "due" if there's already a valid submission, OR if deadline passed
            if now >= m["deadline"]:
                out.append(m)
            else:
                rx = m["verification_params"].get("regex", "")
                if rx:
                    try:
                        pat = re.compile(rx)
                        if any(pat.search(s["proof"]) for s in m["submissions"]):
                            out.append(m)
                    except Exception:
                        pass
        elif vt == "creator_judges" and now >= m.get("judge_deadline", 0):
            out.append(m)
    return out[:limit]


def stats() -> dict:
    d = load()
    return {
        "total": d.get("total", 0),
        "open": len(list_open(10000)),
        "due_for_resolution": len(list_due_for_resolution(10000)),
        "resolved": d.get("resolved", 0),
        "voided": d.get("voided", 0),
        "lifetime_reward_aigen_escrowed": d.get("lifetime_reward_aigen_escrowed", 0),
        "lifetime_reward_aigen_paid": d.get("lifetime_reward_aigen_paid", 0),
        "lifetime_spam_fees_burned": d.get("lifetime_spam_fees_burned", 0),
        "spam_fee_burn_aigen": SPAM_FEE_BURN_AIGEN,
        "min_reward_aigen": MIN_REWARD_AIGEN,
        "verification_types": sorted(VERIFICATION_TYPES),
        "peer_vote_quorum_aigen": PEER_VOTE_QUORUM_AIGEN,
        "min_vote_aigen": MIN_VOTE_AIGEN,
    }
