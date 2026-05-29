"""AIGEN Reputation System — Trust built through work."""
import json
import time as _time_mod
from pathlib import Path

# Module-level cache: {path_str: (loaded_at, data)} — 60s TTL
# Prevents parsing missions.json (6.3MB) 170× per leaderboard call (85 agents × 2 reads each).
_FILE_CACHE: dict = {}
_CACHE_TTL = 60


def _load_cached(path: str) -> dict:
    now = _time_mod.time()
    entry = _FILE_CACHE.get(path)
    if entry and now - entry[0] < _CACHE_TTL:
        return entry[1]
    p = Path(path)
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    _FILE_CACHE[path] = (now, data)
    return data

REP_FILE = Path("/home/luna/crypto-genesis/aigen/reputation.json")

RANKS = [
    (0, "Newcomer", 1.0),
    (100, "Contributor", 1.2),
    (500, "Trusted", 1.5),
    (1000, "Expert", 2.0),
    (5000, "Senior", 3.0),
    (10000, "Elder", 5.0),
    (50000, "Founder", 10.0),
]

def load():
    if REP_FILE.exists():
        return json.loads(REP_FILE.read_text())
    return {}

def save(data):
    REP_FILE.write_text(json.dumps(data, indent=2))

def get_rank(points):
    rank_name = "Newcomer"
    multiplier = 1.0
    for threshold, name, mult in RANKS:
        if points >= threshold:
            rank_name = name
            multiplier = mult
    return rank_name, multiplier

def add_reputation(agent_id, points, reason=""):
    data = load()
    if agent_id not in data:
        data[agent_id] = {"points": 0, "history": []}
    data[agent_id]["points"] += points
    data[agent_id]["history"].append({"points": points, "reason": reason, "ts": __import__('time').time()})
    save(data)
    rank, mult = get_rank(data[agent_id]["points"])
    return {"total": data[agent_id]["points"], "rank": rank, "multiplier": mult}

def get_reputation(agent_id):
    data = load()
    if agent_id not in data:
        return {"total": 0, "rank": "Newcomer", "multiplier": 1.0}
    pts = data[agent_id]["points"]
    rank, mult = get_rank(pts)
    return {"total": pts, "rank": rank, "multiplier": mult}


# =====================================================================
# AUTO-DERIVED REPUTATION (from on-chain agent history — pure data)
# =====================================================================

import time

# ELO-ish point values — deterministic from agent's track record
POINTS = {
    "prediction_won":     50,   # correctly predicted token outcome
    "prediction_lost":   -25,
    "prediction_void":     0,
    "pattern_validated":  100,  # submitter of validated pattern
    "pattern_yes_correct": 30,  # voted YES, pattern got validated
    "pattern_no_correct":  30,  # voted NO, pattern got rejected
    "pattern_yes_wrong":  -20,
    "pattern_no_wrong":   -20,
    "approved_contribution": 25,
    "mission_won_first_valid_match": 1,
    "mission_won_oracle": 3,
    "mission_won_creator_judges": 5,
    "mission_won_peer_vote": 10,
    "premium_attestation_referral": 15,  # referred a paying customer (premium attestation)
    "saferouter_route_volume_log_bps": 5,  # 5 pts per "log10(USD micros)"
}


def derive_reputation(agent_id: str) -> dict:
    """Compute reputation deterministically from agent's full history.
    No state mutation — pure function of the JSON ledgers."""

    score = 0
    breakdown = {}
    wins = 0
    losses = 0

    # 1. Prediction markets
    pred_path = "/home/luna/crypto-genesis/aigen/predictions.json"
    d = _load_cached(pred_path)
    if d:
        won = lost = voided = 0
        for m in d.get("markets", []):
            if m["status"] != "resolved":
                if m["status"] == "voided" and (agent_id in m.get("yes_stakes", {}) or agent_id in m.get("no_stakes", {})):
                    voided += 1
                continue
            winning_side = "yes_stakes" if m["resolution"] == "YES" else "no_stakes"
            losing_side = "no_stakes" if m["resolution"] == "YES" else "yes_stakes"
            if agent_id in m.get(winning_side, {}):
                won += 1
            if agent_id in m.get(losing_side, {}):
                lost += 1
        score += won * POINTS["prediction_won"] + lost * POINTS["prediction_lost"]
        wins += won; losses += lost
        breakdown["predictions"] = {"won": won, "lost": lost, "voided": voided,
                                    "points": won * POINTS["prediction_won"] + lost * POINTS["prediction_lost"]}

    # 2. Pattern bounty board
    pat_path = "/home/luna/crypto-genesis/aigen/patterns_market.json"
    d = _load_cached(pat_path)
    if d:
        validated_subs = 0
        yes_correct = no_correct = yes_wrong = no_wrong = 0
        for p in d.get("patterns", []):
            if p["status"] not in ("validated", "rejected"):
                continue
            is_validated = p["status"] == "validated"
            if p["submitter"] == agent_id and is_validated:
                validated_subs += 1
            voted_yes = agent_id in p.get("yes_votes", {})
            voted_no = agent_id in p.get("no_votes", {})
            if voted_yes:
                if is_validated: yes_correct += 1
                else: yes_wrong += 1
            if voted_no:
                if not is_validated: no_correct += 1
                else: no_wrong += 1
        pat_pts = (validated_subs * POINTS["pattern_validated"]
                   + yes_correct * POINTS["pattern_yes_correct"]
                   + no_correct * POINTS["pattern_no_correct"]
                   + yes_wrong * POINTS["pattern_yes_wrong"]
                   + no_wrong * POINTS["pattern_no_wrong"])
        score += pat_pts
        wins += yes_correct + no_correct
        losses += yes_wrong + no_wrong
        breakdown["patterns"] = {
            "validated_submissions": validated_subs,
            "yes_correct": yes_correct, "no_correct": no_correct,
            "yes_wrong": yes_wrong, "no_wrong": no_wrong,
            "points": pat_pts,
        }

    # 3. Approved contributions (from contributions.json)
    contrib_path = "/home/luna/crypto-genesis/aigen/contributions.json"
    d = _load_cached(contrib_path)
    if d:
        approved = sum(1 for s in d.get("submissions", [])
                       if s.get("agent_id") == agent_id and s.get("status", "").startswith("approved"))
        score += approved * POINTS["approved_contribution"]
        breakdown["contributions"] = {"approved": approved, "points": approved * POINTS["approved_contribution"]}

    # 4. Mission bounty wins
    mission_path = "/home/luna/crypto-genesis/aigen/missions.json"
    d = _load_cached(mission_path)
    if d:
        won_by_type = {
            "first_valid_match": 0,
            "oracle": 0,
            "creator_judges": 0,
            "peer_vote": 0,
        }
        rejected = 0
        for mission in d.get("missions", []):
            winner_agent_id = (mission.get("resolution") or {}).get("winner_agent_id")
            verification_type = mission.get("verification_type", "creator_judges")
            for sub in mission.get("submissions", []):
                if sub.get("submitter") != agent_id:
                    continue
                if sub.get("status") == "winner" or winner_agent_id == agent_id:
                    if verification_type in won_by_type:
                        won_by_type[verification_type] += 1
                elif sub.get("status") == "rejected":
                    rejected += 1
        bounty_pts = (
            won_by_type["first_valid_match"] * POINTS["mission_won_first_valid_match"]
            + won_by_type["oracle"] * POINTS["mission_won_oracle"]
            + won_by_type["creator_judges"] * POINTS["mission_won_creator_judges"]
            + won_by_type["peer_vote"] * POINTS["mission_won_peer_vote"]
        )
        score += bounty_pts
        wins += sum(won_by_type.values())
        losses += rejected
        breakdown["bounties"] = {**won_by_type, "rejected": rejected, "points": bounty_pts}

    # 5. Premium attestation referrals (revenue-generating work)
    rev_path = "/home/luna/crypto-genesis/aigen/revenue_pool.json"
    referrals = 0
    saferouter_volume_micros = 0
    d = _load_cached(rev_path)
    if d:
        for e in d.get("events", []):
            if e.get("attributed_agent_id") != agent_id:
                continue
            if e.get("source") == "attest_premium":
                referrals += 1
            elif e.get("source") == "saferouter_fee":
                saferouter_volume_micros += e.get("metadata", {}).get("fee_usd_micros", 0)
    score += referrals * POINTS["premium_attestation_referral"]
    # Logarithmic scoring of swap fee contribution to avoid one whale dominating
    import math
    swap_pts = 0
    if saferouter_volume_micros > 0:
        swap_pts = int(math.log10(max(1, saferouter_volume_micros)) * POINTS["saferouter_route_volume_log_bps"])
    score += swap_pts
    breakdown["revenue"] = {
        "premium_referrals": referrals, "premium_referral_points": referrals * POINTS["premium_attestation_referral"],
        "saferouter_fee_micros": saferouter_volume_micros, "saferouter_fee_points": swap_pts,
    }

    # 6. Manual reputation points (legacy)
    legacy = load().get(agent_id, {}).get("points", 0)
    score += legacy
    if legacy:
        breakdown["legacy_manual_points"] = legacy

    # Inactivity decay — 2 points per week of silence after 7-day grace period
    # Keeps the leaderboard fresh: agents who go dormant lose ground to active ones.
    raw_score = score
    last_ts = _last_activity_ts(agent_id)
    decay = 0
    if last_ts:
        now = int(time.time())
        days_inactive = max(0, (now - last_ts) // 86400 - 7)  # 7-day grace
        if days_inactive > 0:
            weeks_inactive = days_inactive // 7
            decay = min(score, weeks_inactive * 2)
            score -= decay
            breakdown["decay"] = {
                "days_inactive": int(days_inactive),
                "weeks_inactive": int(weeks_inactive),
                "points_lost": int(decay),
                "last_activity_ts": int(last_ts),
            }

    # Cap at sensible bounds
    score = max(0, score)

    rank_name, multiplier = get_rank(score)
    elo = 1500 + score - 100  # ELO-like single number for leaderboards
    return {
        "agent_id": agent_id,
        "score": score,
        "raw_score_before_decay": raw_score,
        "decay_points": int(decay),
        "elo": elo,
        "rank": rank_name,
        "multiplier": multiplier,
        "wins": wins,
        "losses": losses,
        "breakdown": breakdown,
        "computed_at": int(time.time()),
    }


def _last_activity_ts(agent_id: str) -> int | None:
    """Most recent timestamp at which agent did anything: submission, vote,
    mission creation, prediction, pattern. Returns None if never seen."""
    most_recent = 0

    # Missions: submissions, votes (vote tracked via _credit not directly, fall back to submissions),
    # mission creation
    try:
        d = _load_cached("/home/luna/crypto-genesis/aigen/missions.json")
        if d:
            for m in d.get("missions", []) or []:
                if m.get("creator") == agent_id:
                    most_recent = max(most_recent, m.get("created_at", 0))
                for s in m.get("submissions", []) or []:
                    if (s.get("submitter") or s.get("agent_id")) == agent_id:
                        most_recent = max(most_recent, s.get("submitted_at", 0))
                    # peer-vote tally tracks voters
                    for vagent in (s.get("yes_votes", {}) or {}).keys():
                        if vagent == agent_id:
                            most_recent = max(most_recent, s.get("submitted_at", 0))
                    for vagent in (s.get("no_votes", {}) or {}).keys():
                        if vagent == agent_id:
                            most_recent = max(most_recent, s.get("submitted_at", 0))
    except Exception:
        pass

    # Predictions
    try:
        d = _load_cached("/home/luna/crypto-genesis/aigen/predictions.json")
        if d:
            for m in d.get("markets", []) or []:
                if agent_id in (m.get("yes_stakes", {}) or {}) or agent_id in (m.get("no_stakes", {}) or {}):
                    most_recent = max(most_recent, m.get("created_at", 0), m.get("resolved_at", 0))
    except Exception:
        pass

    # Patterns
    try:
        d = _load_cached("/home/luna/crypto-genesis/aigen/patterns.json")
        if d:
            for s in d.get("submissions", []) or []:
                if s.get("submitter") == agent_id:
                    most_recent = max(most_recent, s.get("submitted_at", 0))
    except Exception:
        pass

    # Ledger credits (catches faucet, payouts, etc.)
    try:
        d = _load_cached("/home/luna/crypto-genesis/shield-rewards/ledger.json")
        if d:
            a = (d.get("agents") or {}).get(agent_id, {})
            for c in (a.get("credits", []) or []):
                most_recent = max(most_recent, c.get("ts", 0))
            most_recent = max(most_recent, a.get("first_seen", 0) or 0)
    except Exception:
        pass

    return most_recent if most_recent else None


def all_active_agents() -> list:
    """List all agent_ids that appear in any history file."""
    seen = set()
    for path in [
        "/home/luna/crypto-genesis/aigen/predictions.json",
        "/home/luna/crypto-genesis/aigen/patterns_market.json",
        "/home/luna/crypto-genesis/aigen/contributions.json",
        "/home/luna/crypto-genesis/aigen/missions.json",
        "/home/luna/crypto-genesis/aigen/revenue_pool.json",
        "/home/luna/crypto-genesis/aigen/agents.json",
    ]:
        d = _load_cached(path)
        if not d:
            continue
        # Collect agent ids from various structures
        for entry in d.get("agents", []):
            if isinstance(entry, dict) and "id" in entry:
                seen.add(entry["id"])
        for s in d.get("submissions", []):
            if "agent_id" in s:
                seen.add(s["agent_id"])
        for mission in d.get("missions", []):
            if "creator" in mission:
                seen.add(mission["creator"])
            for s in mission.get("submissions", []):
                if "submitter" in s:
                    seen.add(s["submitter"])
            resolution = mission.get("resolution") or {}
            if "winner_agent_id" in resolution:
                seen.add(resolution["winner_agent_id"])
        for m in d.get("markets", []):
            seen.update(m.get("yes_stakes", {}).keys())
            seen.update(m.get("no_stakes", {}).keys())
            if "creator" in m: seen.add(m["creator"])
        for p2 in d.get("patterns", []):
            seen.update(p2.get("yes_votes", {}).keys())
            seen.update(p2.get("no_votes", {}).keys())
            if "submitter" in p2: seen.add(p2["submitter"])
        for e in d.get("events", []):
            if "attributed_agent_id" in e:
                seen.add(e["attributed_agent_id"])
    seen.discard("treasury")
    seen.discard("aigen-insurance-pool")
    seen = {a for a in seen if not a.startswith("unknown_router_")}
    return sorted(seen)


def leaderboard(limit: int = 50) -> list:
    """Compute reputation for all known agents, return ranked list."""
    agents = all_active_agents()
    rows = []
    for a in agents:
        r = derive_reputation(a)
        if r["score"] == 0 and r["wins"] == 0 and r["losses"] == 0:
            continue
        rows.append(r)
    rows.sort(key=lambda x: -x["elo"])
    return rows[:limit]
