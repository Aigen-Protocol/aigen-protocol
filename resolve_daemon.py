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
    if not due:
        return 0

    n_ok = 0
    for m in due:
        r = _http_post(f"/missions/{m['id']}/resolve")
        if r.get("ok"):
            outcome = r.get("outcome") or r.get("winner") or "resolved"
            log.info("resolved %s [%s] → %s", m["id"], m.get("verification_type"), outcome)
            n_ok += 1
        elif r.get("resolution"):
            # Already resolved — no-op
            pass
        else:
            log.warning("could not resolve %s: %s", m["id"], r.get("error"))
    return n_ok


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
