#!/usr/bin/env python3
"""AIGEN resolve daemon — auto-resolve any expired mission every 60 seconds.

Independent of autopilot. Lower latency = faster payouts = better UX for
mission creators and submitters. Particularly important for time-sensitive
peer_vote missions where voting closed but resolution hasn't fired yet.

Modes:
  python3 resolve_daemon.py once     # one cycle, exit
  python3 resolve_daemon.py daemon   # cycle every 60 seconds
"""
import argparse
import logging
import sys
import time
import urllib.request
import json

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("resolve")

BASE_URL = "http://127.0.0.1:4444"
INTERVAL_SECONDS = 60


def _http_post(path: str, body: dict | None = None) -> dict:
    url = BASE_URL + path
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(url, method="POST", data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def cycle() -> int:
    """Resolve all due missions. Returns count resolved."""
    sys.path.insert(0, "/home/luna/crypto-genesis/aigen")
    from missions import list_due_for_resolution
    due = list_due_for_resolution(limit=50)

    n_ok = 0
    for m in due:
        r = _http_post(f"/missions/{m['id']}/resolve")
        if r.get("ok"):
            outcome = r.get("outcome") or r.get("winner") or "resolved"
            log.info("resolved %s [%s] → %s", m["id"], m.get("verification_type"), outcome)
            n_ok += 1
        elif r.get("resolution"):
            pass
        else:
            log.warning("could not resolve %s: %s", m["id"], r.get("error"))

    # Auto-bump empty system missions
    bumped = cycle_auto_bump()
    if bumped:
        log.info("auto-bumped %d stale missions", bumped)

    return n_ok


# Agents whose missions we auto-bump (system-funded, can take more escrow)
SYSTEM_CREATORS = {"aigen-radar", "aigen-autopilot", "aigen-treasury"}
MAX_BUMPS_PER_MISSION = 2
BUMP_MULTIPLIER = 1.5
MIN_INTERVAL_BETWEEN_BUMPS = 3 * 3600  # 3 hours between bumps on same mission


def cycle_auto_bump() -> int:
    """For each open system-created mission past 50% of its deadline with
    0 submissions, bump the AIGEN reward by 1.5x (max 2 bumps).

    Adaptive flywheel: missions nobody touches get progressively more
    attractive instead of just timing out into void.
    """
    sys.path.insert(0, "/home/luna/crypto-genesis/aigen")
    from missions import load, save, _balance, _debit, _credit
    d = load()
    now = int(time.time())
    bumped = 0

    for m in d.get("missions", []):
        if m.get("status") != "open":
            continue
        if m.get("creator") not in SYSTEM_CREATORS:
            continue
        # Only AIGEN missions (not USDC/ETH — those have on-chain escrow)
        if (m.get("reward") or {}).get("currency") != "AIGEN":
            continue
        if m.get("submissions"):
            continue  # has activity, leave alone
        bump_count = m.get("bump_count", 0)
        if bump_count >= MAX_BUMPS_PER_MISSION:
            continue

        created = m.get("created_at", 0)
        deadline = m.get("deadline", 0)
        if not (created and deadline):
            continue
        elapsed = now - created
        total = deadline - created
        if total <= 0 or elapsed / total < 0.5:
            continue  # not yet halfway

        # Don't bump within 1h of deadline (no time for someone to claim)
        if (deadline - now) < 3600:
            continue

        # Don't re-bump within MIN_INTERVAL_BETWEEN_BUMPS hours of last bump
        bumps = m.get("bumped_at", []) or []
        if bumps:
            last_bump_ts = bumps[-1].get("ts", 0)
            if (now - last_bump_ts) < MIN_INTERVAL_BETWEEN_BUMPS:
                continue

        # Compute bump
        old_reward = m.get("reward_aigen", 0) or m.get("reward", {}).get("amount", 0)
        new_reward = int(old_reward * BUMP_MULTIPLIER)
        delta = new_reward - old_reward
        if delta <= 0:
            continue

        # Try to escrow extra AIGEN from creator
        creator = m["creator"]
        if not _debit(creator, delta, f"mission-{m['id']}-bump-{bump_count + 1}"):
            log.warning("could not bump %s — creator %s insufficient AIGEN", m["id"], creator)
            continue

        # Update mission state
        m["reward"]["amount"] = new_reward
        m["reward_aigen"] = new_reward
        m["bump_count"] = bump_count + 1
        m["bumped_at"] = m.get("bumped_at", []) + [{"ts": now, "from": old_reward, "to": new_reward}]
        log.info("BUMP %s: %d → %d AIGEN (bump %d/%d, %.0f%% elapsed)",
                 m["id"], old_reward, new_reward,
                 bump_count + 1, MAX_BUMPS_PER_MISSION,
                 100 * elapsed / total)
        bumped += 1

    if bumped:
        save(d)
    return bumped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["once", "daemon"], default="daemon", nargs="?")
    args = ap.parse_args()

    if args.mode == "once":
        n = cycle()
        log.info("done — resolved %d", n)
        return

    log.info("resolve daemon starting (interval=%ds)", INTERVAL_SECONDS)
    while True:
        try:
            n = cycle()
            if n:
                log.info("cycle done — resolved %d", n)
        except Exception as e:
            log.exception("cycle failed: %s", e)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
