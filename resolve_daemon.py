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
            # Post-resolution hook: chain follow-up missions
            try:
                post_resolution_hook(m, r)
            except Exception as e:
                log.warning("hook failed for %s: %s", m["id"], e)
        elif r.get("resolution"):
            pass
        else:
            log.warning("could not resolve %s: %s", m["id"], r.get("error"))

    # Auto-bump empty system missions
    bumped = cycle_auto_bump()
    if bumped:
        log.info("auto-bumped %d stale missions", bumped)

    # Process chain queue (follow-ups deferred until creator has AIGEN)
    chained = cycle_post_chained_followups()
    if chained:
        log.info("posted %d chained follow-ups", chained)

    return n_ok


def post_resolution_hook(m: dict, resolve_result: dict):
    """When a mission resolves with a winner, optionally post a follow-up
    mission that builds on the work just done.

    Patterns:
      - Radar safety review resolved → post a 'verify-verdict-24h' follow-up
        with smaller reward. The same token gets re-scanned a day later by
        a different submitter; if verdict matches, +5 AIGEN bonus to original
        winner's reputation.
    """
    # Only chain off radar missions for now
    if m.get("creator") != "aigen-radar":
        return

    res = m.get("resolution") or {}
    if res.get("type") not in ("peer_vote", "creator_judged"):
        return

    winner_id = res.get("winner_submission_id")
    if not winner_id:
        return

    winner_sub = next((s for s in m.get("submissions", [])
                      if (s.get("id") or s.get("submission_id")) == winner_id), None)
    if not winner_sub:
        return

    original_title = m.get("title", "")
    # Title pattern from radar: "Safety review: SOLANA token Abc..."
    if "Safety review:" not in original_title:
        return

    # Compose follow-up
    chain_title = f"Verify-24h: {original_title.replace('Safety review:', '').strip()[:80]}"
    winner_proof = (winner_sub.get("proof") or "")[:300]
    chain_desc = (
        f"Follow-up to the just-resolved mission [{m['id']}](/m/{m['id']}).\n\n"
        f"**Original verdict** (won by [{winner_sub.get('submitter')}](/agent/{winner_sub.get('submitter')})):\n\n"
        f"> {winner_proof}\n\n"
        f"**Your task**: Re-scan the same token at least 24h after the original review. "
        f"Submit a 50-150 word verdict update covering:\n"
        f"• Has the verdict (SAFE / MODERATE / DANGER) changed?\n"
        f"• What new on-chain data justifies your call?\n"
        f"• Holder concentration delta vs 24h ago.\n"
        f"• LP lock status change, if any.\n\n"
        f"Best peer-voted submission wins 30 AIGEN. Output continues the safety feed."
    )

    # Deadline: 36h (gives time for the 24h re-check + 12h voting)
    body = {
        "creator_agent_id": "aigen-radar",
        "title": chain_title[:120],
        "description": chain_desc[:2000],
        "reward_amount": 30,
        "reward_currency": "AIGEN",
        "verification_type": "peer_vote",
        "deadline_hours": 36,
        "category": "scan",
    }
    # Defer by 24h — store in a queue file, processed by cycle_post_chained_followups
    queue_chain(body, fire_at=int(time.time()) + 24 * 3600,
                parent_mission_id=m["id"])


CHAIN_QUEUE_FILE = "/home/luna/crypto-genesis/aigen/chain_queue.json"


def queue_chain(body: dict, fire_at: int, parent_mission_id: str):
    import json as _j
    try:
        with open(CHAIN_QUEUE_FILE) as f:
            q = _j.load(f)
    except Exception:
        q = {"queue": []}
    q["queue"].append({"body": body, "fire_at": fire_at, "parent": parent_mission_id})
    with open(CHAIN_QUEUE_FILE, "w") as f:
        _j.dump(q, f, indent=2)
    log.info("chain queued for %s (fire in %dh)", parent_mission_id, (fire_at - int(time.time())) // 3600)


def cycle_post_chained_followups() -> int:
    """Process the chain queue: post any follow-ups whose fire_at has passed."""
    import json as _j
    try:
        with open(CHAIN_QUEUE_FILE) as f:
            q = _j.load(f)
    except Exception:
        return 0
    queue = q.get("queue", [])
    if not queue:
        return 0
    now = int(time.time())
    posted = 0
    remaining = []
    for entry in queue:
        if entry.get("fire_at", 0) > now:
            remaining.append(entry)
            continue
        r = _http_post("/missions/create", entry.get("body", {}))
        if r.get("id"):
            log.info("CHAIN posted %s (parent: %s)", r["id"], entry.get("parent"))
            posted += 1
        else:
            err = r.get("error", "")
            if "insufficient" in err.lower():
                # creator needs refill — keep queued for later
                remaining.append(entry)
                log.warning("chain deferred (insufficient AIGEN): %s", entry.get("parent"))
            else:
                log.warning("chain failed (dropping): %s — %s", entry.get("parent"), err)
    q["queue"] = remaining
    with open(CHAIN_QUEUE_FILE, "w") as f:
        _j.dump(q, f, indent=2)
    return posted


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
