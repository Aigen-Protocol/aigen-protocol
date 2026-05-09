#!/usr/bin/env python3
"""AIGEN Autopilot — keeps the network alive without human intervention.

Cycle every 5 minutes:
  1. /predict/{id}/resolve     for any market past deadline (on-chain oracle decides)
  2. /patterns/{id}/resolve    for any pattern past voting deadline
  3. /claims/{id}/resolve      for any claim past voting deadline (DAO tally)
  4. /claims/{id}/execute      for any approved claim awaiting on-chain payClaim
  5. /buyback/poke             when revenue threshold is met

The autopilot is itself a registered agent (`aigen-autopilot`) that earns the
permissionless poker bounties — keeping it self-funding even if no humans poke.

Modes:
  python3 autopilot.py once       # one cycle, exit
  python3 autopilot.py daemon     # cycle every 5 min
"""
import argparse
import json
import logging
import sys
import time
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("autopilot")

BASE_URL = "http://127.0.0.1:4444"   # local scanner — bypasses proxy auth
AUTOPILOT_AGENT = "aigen-autopilot"
INTERVAL_SECONDS = 300

# Daily mission generator — autopilot autonomously creates a peer_vote mission
# from the day's most-scanned token, so the network always has fresh work
# without any human input.
DAILY_STATE_FILE = "/home/luna/crypto-genesis/aigen/autopilot_daily_state.json"
DAILY_MISSION_REWARD_AIGEN = 50
DAILY_MISSION_DEADLINE_HOURS = 23
AUTOPILOT_AIGEN_REFILL_THRESHOLD = 100
AUTOPILOT_AIGEN_REFILL_AMOUNT = 10_000   # 10k AIGEN per refill (good for ~180 missions)
LEDGER_PATH = "/home/luna/crypto-genesis/shield-rewards/ledger.json"


def _http(method: str, path: str, body: dict | None = None, timeout: int = 60) -> dict:
    url = BASE_URL + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, data=data,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "aigen-autopilot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e), "url": url}


def cycle_resolve_predictions() -> int:
    """Resolve any prediction markets past deadline. Returns count resolved."""
    sys.path.insert(0, "/home/luna/crypto-genesis/aigen")
    from predictions import list_due_for_resolution
    due = list_due_for_resolution()
    n = 0
    for m in due:
        r = _http("POST", f"/predict/{m['id']}/resolve")
        if r.get("resolved"):
            log.info("  predictions: %s → %s", m["id"], r.get("outcome"))
            n += 1
        else:
            log.warning("  predictions: %s skipped: %s", m["id"], r.get("error"))
    return n


def cycle_resolve_patterns() -> int:
    sys.path.insert(0, "/home/luna/crypto-genesis/aigen")
    from patterns_market import list_due
    due = list_due()
    n = 0
    for p in due:
        r = _http("POST", f"/patterns/{p['id']}/resolve")
        if "error" not in r:
            log.info("  patterns: %s → %s", p["id"], r.get("outcome", "resolved"))
            n += 1
        else:
            log.warning("  patterns: %s skipped: %s", p["id"], r.get("error"))
    return n


def cycle_resolve_missions() -> int:
    sys.path.insert(0, "/home/luna/crypto-genesis/aigen")
    from missions import list_due_for_resolution
    due = list_due_for_resolution()
    n = 0
    for m in due:
        r = _http("POST", f"/missions/{m['id']}/resolve")
        if r.get("ok"):
            log.info("  missions: %s → %s", m["id"], r.get("outcome") or r.get("winner"))
            n += 1
        else:
            log.warning("  missions: %s skipped: %s", m["id"], r.get("error"))
    return n


def cycle_resolve_claims() -> int:
    sys.path.insert(0, "/home/luna/crypto-genesis/aigen")
    from claims import list_due
    due = list_due()
    n = 0
    for c in due:
        r = _http("POST", f"/claims/{c['id']}/resolve")
        if r.get("resolved"):
            log.info("  claims: %s → %s", c["id"], r.get("outcome"))
            n += 1
        else:
            log.warning("  claims: %s skipped: %s", c["id"], r.get("error"))
    return n


def cycle_execute_claims() -> int:
    """Execute approved claims that haven't been on-chain paid yet."""
    sys.path.insert(0, "/home/luna/crypto-genesis/aigen")
    from claims import list_pending_execution
    pending = list_pending_execution()
    n = 0
    for c in pending:
        r = _http("POST", f"/claims/{c['id']}/execute?executor_agent_id={AUTOPILOT_AGENT}", timeout=240)
        if r.get("ok"):
            log.info("  claims-execute: %s tx=%s", c["id"], r.get("execution_tx"))
            n += 1
        else:
            log.warning("  claims-execute: %s skipped: %s", c["id"], r.get("error"))
    return n


def cycle_buyback_poke() -> int:
    """Poke buyback if threshold met."""
    r = _http("POST", f"/buyback/poke?poker_agent_id={AUTOPILOT_AGENT}")
    if r.get("ok") and r.get("queued"):
        log.info("  buyback: queued (pending=%s)", r.get("pending_at_trigger"))
        return 1
    return 0


def _ensure_autopilot_aigen():
    """Make sure the autopilot agent has enough AIGEN to escrow at least one
    mission. Treasury is the source of truth for new ledger AIGEN — we mint
    from the protocol's bootstrap supply (mirroring the on-chain 990M supply
    we hold). Refill is silent and idempotent."""
    try:
        d = json.load(open(LEDGER_PATH))
    except Exception as e:
        log.warning("ledger load failed: %s", e)
        return False
    a = d.setdefault("agents", {}).setdefault(AUTOPILOT_AGENT, {
        "balance": 0, "total_earned": 0, "actions": 0, "first_seen": int(time.time()),
    })
    if a.get("balance", 0) >= AUTOPILOT_AIGEN_REFILL_THRESHOLD:
        return True
    a["balance"] = a.get("balance", 0) + AUTOPILOT_AIGEN_REFILL_AMOUNT
    a["total_earned"] = a.get("total_earned", 0) + AUTOPILOT_AIGEN_REFILL_AMOUNT
    a.setdefault("credits", []).append({
        "ts": int(time.time()),
        "amount": AUTOPILOT_AIGEN_REFILL_AMOUNT,
        "reason": "autopilot-refill-from-bootstrap-supply",
    })
    d["total_distributed"] = d.get("total_distributed", 0) + AUTOPILOT_AIGEN_REFILL_AMOUNT
    json.dump(d, open(LEDGER_PATH, "w"), indent=2)
    log.info("autopilot AIGEN refilled +%d (new balance=%d)", AUTOPILOT_AIGEN_REFILL_AMOUNT, a["balance"])
    return True


def cycle_auto_create_daily_mission() -> int:
    """Once per UTC day: pick the most-scanned token from /trending and post
    a peer_vote mission asking agents to describe it. Generates content,
    accumulates ELO history, and demonstrates the protocol is alive even
    without external creators.

    Treasury (autopilot agent) escrows AIGEN. If no one submits/votes within
    23h, mission voids and autopilot is refunded (loses only 5 AIGEN spam fee).
    """
    today = time.strftime("%Y-%m-%d", time.gmtime())
    try:
        state = json.load(open(DAILY_STATE_FILE))
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    if state.get("last_mission_day") == today:
        return 0  # already created today

    # Make sure autopilot can escrow
    _ensure_autopilot_aigen()

    # Pick token from trending. Skip system tokens and very low-info entries.
    trending_resp = _http("GET", "/trending")
    if not trending_resp or "trending" not in trending_resp:
        log.info("  daily-mission: trending unavailable, skipping")
        return 0
    candidates = [t for t in trending_resp["trending"]
                  if t.get("verdict") != "SYSTEM TOKEN"
                  and t.get("symbol") not in ("???", "")
                  and t.get("name") not in ("Unknown", "")]
    if not candidates:
        log.info("  daily-mission: no usable trending candidates")
        return 0
    pick = candidates[0]

    sym = pick["symbol"]
    addr = pick["address"]
    chain = pick["chain"]
    name = pick.get("name", sym)
    score = pick.get("safety_score", "?")
    verdict = pick.get("verdict", "?")

    title = f"Best 1-line summary of {name} ({sym}) on {chain}"
    description = (
        f"Token: {name} ({sym}) — {addr} on {chain}. "
        f"Current AIGEN safety score: {score} ({verdict}). "
        f"Submit one concise sentence describing what this token does, who's behind it, "
        f"and what makes it interesting (or not). Best peer-voted submission wins "
        f"{DAILY_MISSION_REWARD_AIGEN} AIGEN."
    )

    r = _http("POST", "/missions/create", {
        "creator_agent_id": AUTOPILOT_AGENT,
        "title": title[:120],
        "description": description[:2000],
        "reward_amount": DAILY_MISSION_REWARD_AIGEN,
        "reward_currency": "AIGEN",
        "verification_type": "peer_vote",
        "deadline_hours": DAILY_MISSION_DEADLINE_HOURS,
    })
    if r.get("id"):
        log.info("  daily-mission CREATED: %s for %s/%s (chain=%s)",
                 r["id"], sym, addr[:10], chain)
        state["last_mission_day"] = today
        state["last_mission_id"] = r["id"]
        state["last_mission_token"] = f"{sym}@{chain}"
        state["created_at"] = int(time.time())
        try:
            json.dump(state, open(DAILY_STATE_FILE, "w"), indent=2)
        except Exception as e:
            log.warning("  daily-state save failed: %s", e)
        return 1
    log.warning("  daily-mission FAILED: %s", r)
    return 0


def cycle():
    log.info("autopilot cycle start")
    p = cycle_resolve_predictions()
    pa = cycle_resolve_patterns()
    c = cycle_resolve_claims()
    e = cycle_execute_claims()
    mi = cycle_resolve_missions()
    b = cycle_buyback_poke()
    dm = cycle_auto_create_daily_mission()
    log.info("cycle done: predictions=%d patterns=%d claims_resolved=%d claims_executed=%d missions_resolved=%d buyback_poked=%d daily_mission=%d",
             p, pa, c, e, mi, b, dm)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["once", "daemon"])
    ap.add_argument("--interval", type=int, default=INTERVAL_SECONDS)
    args = ap.parse_args()
    if args.mode == "once":
        cycle()
    else:
        log.info("autopilot daemon starting (interval=%ds)", args.interval)
        while True:
            try:
                cycle()
            except Exception:
                log.exception("cycle err")
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
