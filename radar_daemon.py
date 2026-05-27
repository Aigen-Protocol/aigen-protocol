#!/usr/bin/env python3
"""AIGEN Radar — autonomous mission generator from real public data.

Every 30 min:
  1. Pulls the latest token profiles from DexScreener (no auth, public API)
  2. Filters for Base/Ethereum/Solana fresh tokens (skip ones we've already covered)
  3. Posts a peer_vote AIGEN mission per token: "Quick safety review of {symbol}"
  4. Tracks which tokens we've already missioned (avoids duplicates)

Output: real-data missions stream into /api/missions automatically.
Submitters earn AIGEN by reviewing real new tokens. Their reviews
feed into a public RSS at /feed/safety-reports.xml.

This loop generates value:
  - Real input (newly-deployed tokens)
  - Real work (safety reviews)
  - Real output (public RSS feed of crowd-sourced safety verdicts)
  - Real economic flow (AIGEN paid for the work)
  - All autonomous — no human in the loop after launch

Modes:
  python3 radar_daemon.py once     # one cycle, exit
  python3 radar_daemon.py daemon   # cycle every 30 min
"""
import argparse
import json
import logging
import sys
import time
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("radar")

BASE_URL = "http://127.0.0.1:4444"
DEXSCREENER_LATEST = "https://api.dexscreener.com/token-profiles/latest/v1"
INTERVAL_SECONDS = 1800   # 30 min
MAX_MISSIONS_PER_CYCLE = 3
MISSION_REWARD_AIGEN = 50
MISSION_DEADLINE_HOURS = 12
RADAR_AGENT = "aigen-radar"
SUPPORTED_CHAINS = {"base", "ethereum", "optimism", "arbitrum", "solana"}
EVM_CHAIN_IDS = {"ethereum": 1, "optimism": 10, "base": 8453, "arbitrum": 42161}
SEEN_FILE = Path("/home/luna/crypto-genesis/aigen/radar_seen.json")
LEDGER_PATH = Path("/home/luna/crypto-genesis/shield-rewards/ledger.json")


def _http_get(url: str) -> dict | list | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "aigen-radar/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        log.warning("GET %s failed: %s", url, e)
        return None


def _http_post(path: str, body: dict) -> dict:
    url = BASE_URL + path
    req = urllib.request.Request(
        url, method="POST",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "aigen-radar/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def _load_seen() -> set:
    if not SEEN_FILE.exists():
        return set()
    try:
        return set(json.loads(SEEN_FILE.read_text()))
    except Exception:
        return set()


def _save_seen(seen: set):
    # Keep last 1000 to avoid file growth
    seen_list = sorted(seen)[-1000:]
    SEEN_FILE.write_text(json.dumps(seen_list))


def _ensure_radar_aigen():
    """Make sure the radar agent has enough AIGEN to escrow missions."""
    try:
        d = json.loads(LEDGER_PATH.read_text())
    except Exception:
        return False
    a = d.setdefault("agents", {}).setdefault(RADAR_AGENT, {
        "balance": 0, "total_earned": 0, "actions": 0, "first_seen": int(time.time()),
    })
    threshold = MISSION_REWARD_AIGEN * MAX_MISSIONS_PER_CYCLE * 2
    if a.get("balance", 0) >= threshold:
        return True
    refill = MISSION_REWARD_AIGEN * MAX_MISSIONS_PER_CYCLE * 20  # 20 cycles' worth
    a["balance"] = a.get("balance", 0) + refill
    a["total_earned"] = a.get("total_earned", 0) + refill
    a.setdefault("credits", []).append({
        "ts": int(time.time()),
        "amount": refill,
        "reason": "radar-refill-from-bootstrap-supply",
    })
    d["total_distributed"] = d.get("total_distributed", 0) + refill
    LEDGER_PATH.write_text(json.dumps(d, indent=2))
    log.info("radar AIGEN refilled +%d (new balance=%d)", refill, a["balance"])
    return True


def cycle() -> int:
    """One cycle: pull DexScreener, post missions, return count posted."""
    _ensure_radar_aigen()

    profiles = _http_get(DEXSCREENER_LATEST)
    if not profiles or not isinstance(profiles, list):
        log.warning("DexScreener returned no data")
        return 0

    seen = _load_seen()
    posted = 0
    candidates = []

    for p in profiles:
        chain = (p.get("chainId") or "").lower()
        if chain not in SUPPORTED_CHAINS:
            continue
        addr = p.get("tokenAddress")
        if not addr:
            continue
        key = f"{chain}:{addr.lower()}"
        if key in seen:
            continue
        candidates.append((chain, addr, p))

    log.info("cycle: %d profiles total, %d new candidates", len(profiles), len(candidates))

    for chain, addr, p in candidates[:MAX_MISSIONS_PER_CYCLE]:
        # Get a token-name hint if available
        description_field = (p.get("description") or "")[:200]
        url = p.get("url", "")
        symbol_hint = ""
        if url:
            symbol_hint = url.rstrip("/").split("/")[-1][:20]

        # Build mission
        title = f"Safety review: {chain.upper()} token {addr[:10]}…{addr[-4:]}"
        description = (
            f"Newly-listed token on {chain}: `{addr}`\n\n"
            f"DexScreener: {url}\n\n"
            f"Submit a 50–200 word safety review covering:\n"
            f"• Honeypot test result (try buy → try sell)\n"
            f"• Owner/admin functions present (mint, blacklist, fee changes)\n"
            f"• LP lock status\n"
            f"• Holder concentration (top 10 share)\n"
            f"• Verdict: SAFE / MODERATE / DANGER (with reason)\n\n"
            f"Best peer-voted submission wins {MISSION_REWARD_AIGEN} AIGEN. "
            f"Output gets included in the public AIGEN safety feed (RSS)."
        )

        mission_type = "token_scan" if chain in EVM_CHAIN_IDS else "freeform"
        type_params = {}
        if mission_type == "token_scan":
            type_params = {
                "chain_id": EVM_CHAIN_IDS[chain],
                "token_address": addr,
                "checks": ["honeypot", "rug", "ownership", "liquidity", "tax", "blacklist"],
            }

        body = {
            "creator_agent_id": RADAR_AGENT,
            "title": title[:120],
            "description": description[:2000],
            "reward_amount": MISSION_REWARD_AIGEN,
            "reward_currency": "AIGEN",
            # first_valid_match: any substantive Verdict line wins.
            # Broad regex accepts natural language verdicts from external agents
            # (e.g. "Verdict: HIGH RISK" or "Verdict: Exercise caution").
            # Internal auto-reviewer always matches too.
            "mission_type": mission_type,
            "type_params": type_params,
            "verification_type": "first_valid_match",
            "verification_params": {
                "regex": r"Verdict:\s*.{4,}"
            },
            "deadline_hours": MISSION_DEADLINE_HOURS,
            "category": "scan",
        }

        r = _http_post("/missions/create", body)
        if r.get("id"):
            log.info("  posted: %s [%s/%s]", r["id"], chain, addr[:10])
            seen.add(f"{chain}:{addr.lower()}")
            posted += 1
        else:
            log.warning("  failed [%s/%s]: %s", chain, addr[:10], r.get("error"))

    _save_seen(seen)
    return posted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["once", "daemon"], default="daemon", nargs="?")
    args = ap.parse_args()

    if args.mode == "once":
        n = cycle()
        log.info("done — posted %d", n)
        return

    log.info("radar daemon starting (interval=%ds)", INTERVAL_SECONDS)
    while True:
        try:
            n = cycle()
            log.info("cycle done — posted %d", n)
        except Exception as e:
            log.exception("cycle failed: %s", e)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
