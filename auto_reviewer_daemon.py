#!/usr/bin/env python3
"""AIGEN Auto-Reviewer — submits deterministic safety reviews to radar missions.

Bridges the supply gap: radar creates missions, but no submitters yet exist.
This daemon submits a templated review using our own /scan endpoint output
(EVM) or /scan/solana (Solana). No LLM, no external cost.

Strategy:
  Every 5 min, scan open radar missions that:
    - Have 0 submissions
    - Are at least 30 min old (give external submitters first crack)
    - Aren't already covered by us
  For each, run /scan{,/solana}, format the result as a 50-200 word
  review, submit as agent `aigen-auto-reviewer`.

If a human/LLM submitter writes a BETTER review, peer-vote picks them
(template losing to crafted is the right outcome). If nobody else
shows up, the auto-reviewer wins → AIGEN cycles → RSS feed gets real
entries → public consumers see active output.

Modes:
  python3 auto_reviewer_daemon.py once
  python3 auto_reviewer_daemon.py daemon
"""
import argparse
import json
import logging
import re
import sys
import time
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("auto-reviewer")

BASE_URL = "http://127.0.0.1:4444"
INTERVAL_SECONDS = 300       # 5 min
GRACE_SECONDS = 1800         # don't submit until mission is 30 min old
REVIEWER_AGENT = "aigen-auto-reviewer"
SEEN_FILE = Path("/home/luna/crypto-genesis/aigen/auto_reviewer_seen.json")
LEDGER_PATH = Path("/home/luna/crypto-genesis/shield-rewards/ledger.json")


def _http_get(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "aigen-auto-reviewer/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        log.warning("GET %s → %s", url, e)
        return None


def _http_post(path: str, body: dict) -> dict:
    url = BASE_URL + path
    req = urllib.request.Request(
        url, method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "aigen-auto-reviewer/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def _ensure_reviewer_aigen():
    """Make sure auto-reviewer can pay submission spam fees (none for AIGEN)."""
    try:
        d = json.loads(LEDGER_PATH.read_text())
    except Exception:
        return
    a = d.setdefault("agents", {}).setdefault(REVIEWER_AGENT, {
        "balance": 0, "total_earned": 0, "actions": 0, "first_seen": int(time.time()),
    })
    if a.get("balance", 0) >= 100:
        return
    a["balance"] = a.get("balance", 0) + 500
    a.setdefault("credits", []).append({"ts": int(time.time()), "amount": 500,
                                         "reason": "auto-reviewer-bootstrap"})
    LEDGER_PATH.write_text(json.dumps(d, indent=2))
    log.info("auto-reviewer balance bootstrapped to %d", a["balance"])


def _load_seen() -> set:
    if not SEEN_FILE.exists():
        return set()
    try:
        return set(json.loads(SEEN_FILE.read_text()))
    except Exception:
        return set()


def _save_seen(seen: set):
    SEEN_FILE.write_text(json.dumps(sorted(seen)[-2000:]))


def _parse_radar_title(title: str) -> tuple[str, str] | None:
    """Extract (chain_lower, address) from a radar mission title.
    Format: 'Safety review: SOLANA token 4SGD4RzT7i…9PMp'
    Note: ellipsis means we need to look in the description.
    """
    m = re.match(r"Safety review:\s+(\w+)\s+token\s+(.+?)(?:[…\s]|$)", title)
    if m:
        return m.group(1).lower(), m.group(2).strip()
    return None


def _parse_radar_description(desc: str) -> tuple[str, str] | None:
    """Extract (chain, address) from radar mission description.
    Description contains: 'Newly-listed token on {chain}: `{address}`'
    """
    m = re.search(r"Newly-listed token on (\w+):\s*`([A-Za-z0-9]{32,44}|0x[a-fA-F0-9]{40})`", desc)
    if m:
        return m.group(1).lower(), m.group(2).strip()
    return None


def _format_review(scan: dict, chain: str, address: str) -> str:
    """Turn raw /scan response into a 50-200 word review string."""
    if not scan or scan.get("error"):
        return None
    score = scan.get("safety_score", 0)
    verdict = scan.get("verdict", "?")
    token = scan.get("token") or {}
    name = token.get("name", "Unknown")
    symbol = token.get("symbol", "?")
    flags = scan.get("flags") or []

    # Bucket
    if score >= 90:
        verdict_label = "SAFE"
    elif score >= 60:
        verdict_label = "MODERATE"
    elif score >= 30:
        verdict_label = "DANGER"
    elif score > 0:
        verdict_label = "DANGER"
    else:
        verdict_label = "UNKNOWN"

    flag_summary = []
    for f in flags[:5]:
        if isinstance(f, dict):
            sev = f.get("severity", "?")
            nm = f.get("name", "?")
            flag_summary.append(f"  - [{sev}] {nm}")
        else:
            flag_summary.append(f"  - {f}")
    flag_text = "\n".join(flag_summary) if flag_summary else "  - None notable"

    review = (
        f"Verdict: {verdict_label} (AIGEN safety score: {score}/100)\n\n"
        f"Token: {symbol} ({name}) on {chain.upper()}\n"
        f"Address: {address}\n\n"
        f"Findings:\n{flag_text}\n\n"
        f"Source: deterministic on-chain scan via AIGEN scanner. "
        f"Cross-check this verdict on a 24h follow-up before trading."
    )
    return review


def cycle() -> int:
    """Submit reviews to eligible radar missions. Returns count submitted."""
    _ensure_reviewer_aigen()

    # List open radar missions
    d = _http_get(f"{BASE_URL}/api/missions?limit=200")
    if not d or "missions" not in d:
        return 0
    candidates = [m for m in d["missions"]
                  if m.get("creator") == "aigen-radar"
                  and (m.get("submission_count", 0) == 0 or len(m.get("submissions", []) or []) == 0)]

    seen = _load_seen()
    submitted = 0
    now = int(time.time())

    # Need full mission details (description, age) — use /api/missions/{id}
    for m in candidates:
        mid = m.get("id")
        if mid in seen:
            continue
        # Get full mission with description
        full = _http_get(f"{BASE_URL}/api/missions/{mid}")
        if not full or full.get("error"):
            continue
        if full.get("submissions"):
            seen.add(mid)
            continue
        created = full.get("created_at", 0)
        if now - created < GRACE_SECONDS:
            continue  # too young — give external submitters a shot

        # Parse chain + address
        parsed = _parse_radar_description(full.get("description", "")) or _parse_radar_title(full.get("title", ""))
        if not parsed:
            log.warning("could not parse mission %s", mid)
            seen.add(mid)
            continue
        chain, address = parsed

        # Run scan
        if chain == "solana":
            scan = _http_get(f"{BASE_URL}/scan/solana?address={address}")
        elif chain in ("base", "ethereum", "optimism", "arbitrum", "polygon", "bsc"):
            scan = _http_get(f"{BASE_URL}/scan?address={address}&chain={chain}")
        else:
            log.info("unsupported chain %s for %s", chain, mid)
            seen.add(mid)
            continue

        review = _format_review(scan, chain, address)
        if not review:
            log.warning("scan failed for %s/%s — skipping", chain, address)
            seen.add(mid)
            continue

        # Submit
        body = {
            "submitter_agent_id": REVIEWER_AGENT,
            "proof": review,
            "metadata": {"source": "auto-reviewer", "scan_chain": chain, "scan_addr": address},
        }
        r = _http_post(f"/missions/{mid}/submit", body)
        if r.get("ok"):
            log.info("submitted to %s [%s/%s] verdict=%s",
                     mid, chain, address[:10], scan.get("verdict"))
            seen.add(mid)
            submitted += 1
        else:
            log.warning("submit failed for %s: %s", mid, r.get("error"))
            # Don't add to seen — retry next cycle in case of transient error
            if "already" in (r.get("error") or "").lower():
                seen.add(mid)

    _save_seen(seen)
    return submitted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["once", "daemon"], default="daemon", nargs="?")
    args = ap.parse_args()

    if args.mode == "once":
        n = cycle()
        log.info("done — submitted %d", n)
        return

    log.info("auto-reviewer daemon starting (interval=%ds, grace=%ds)",
             INTERVAL_SECONDS, GRACE_SECONDS)
    while True:
        try:
            n = cycle()
            if n:
                log.info("cycle done — submitted %d", n)
        except Exception as e:
            log.exception("cycle failed: %s", e)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
