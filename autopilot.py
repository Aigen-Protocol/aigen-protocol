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


def cycle():
    log.info("autopilot cycle start")
    p = cycle_resolve_predictions()
    pa = cycle_resolve_patterns()
    c = cycle_resolve_claims()
    e = cycle_execute_claims()
    b = cycle_buyback_poke()
    log.info("cycle done: predictions=%d patterns=%d claims_resolved=%d claims_executed=%d buyback_poked=%d",
             p, pa, c, e, b)


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
