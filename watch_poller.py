#!/usr/bin/env python3
"""AIGEN watch poller — long-running daemon.

Every cycle (60s tick):
- Find watches whose next_poll_at <= now
- For each, fetch wallet token balances via Blockscout
- For each held token, get safety score (calls our /scan, which is cached)
- Diff vs known_holdings → list of alerts
- POST signed webhook to callback_url for each alert
- Update known_holdings + reschedule next_poll_at

Resilience:
- Per-watch error increments consecutive_failures with exponential backoff
- 10 consecutive failures → status=suspended
- Webhook delivery: HTTP 2xx = success; anything else = failed delivery (logged)
"""
import asyncio
import json
import logging
import os
import sys
import time

import aiohttp

sys.path.insert(0, "/home/luna/crypto-genesis/aigen")
from watches import (  # noqa: E402
    watches_due_for_poll,
    update_after_poll,
    diff_holdings,
    build_webhook_envelope,
    log_alert,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("watch_poller")

SCANNER = "http://127.0.0.1:4444"
TICK_SECONDS = 60  # how often we wake to look for due watches

BLOCKSCOUT = {
    "base": "https://base.blockscout.com/api/v2",
    "ethereum": "https://eth.blockscout.com/api/v2",
    "arbitrum": "https://arbitrum.blockscout.com/api/v2",
    "optimism": "https://optimism.blockscout.com/api/v2",
    "polygon": "https://polygon.blockscout.com/api/v2",
    "bsc": "https://bsc.blockscout.com/api/v2",
}


async def fetch_holdings(session, chain, wallet, max_tokens):
    """Return list of ERC-20 token addresses held by `wallet` on `chain`."""
    api = BLOCKSCOUT.get(chain)
    if not api:
        return []
    url = f"{api}/addresses/{wallet}/token-balances"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                log.warning("Blockscout %s returned %s for %s", chain, r.status, wallet)
                return []
            data = await r.json()
    except Exception as e:
        log.warning("Blockscout fetch error %s/%s: %s", chain, wallet, e)
        return []

    out = []
    items = data if isinstance(data, list) else data.get("items", [])
    for item in items:
        token = item.get("token") or {}
        if token.get("type") not in ("ERC-20", "ERC20", None):
            continue
        addr = token.get("address_hash") or token.get("address")
        if not addr:
            continue
        # Skip dust (zero balance)
        try:
            balance = int(item.get("value", "0") or "0")
            if balance == 0:
                continue
        except (TypeError, ValueError):
            pass
        out.append(addr.lower())
        if len(out) >= max_tokens:
            break
    return out


async def fetch_score(session, chain, address):
    """Call our own /scan endpoint (which uses internal cache + RPC)."""
    try:
        async with session.get(
            f"{SCANNER}/scan",
            params={"address": address, "chain": chain},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as r:
            if r.status != 200:
                return None
            d = await r.json()
            tok = d.get("token", {})
            return {
                "score": d.get("safety_score", d.get("score", 100)),
                "verdict": d.get("verdict", "?"),
                "symbol": tok.get("symbol", "?"),
                "name": tok.get("name", "?"),
                "decimals": tok.get("decimals", 18),
                "risks": d.get("risks", []),
            }
    except Exception as e:
        log.warning("Scan error %s/%s: %s", chain, address, e)
        return None


async def deliver_webhook(session, callback_url, payload):
    """POST signed payload. Return (ok, status, body_excerpt)."""
    try:
        async with session.post(
            callback_url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=10),
            headers={"Content-Type": "application/json", "User-Agent": "AIGEN-Watch/1.0"},
        ) as r:
            body = (await r.text())[:200]
            return (200 <= r.status < 300), r.status, body
    except Exception as e:
        return False, 0, str(e)[:200]


async def poll_one(session, watch):
    """Run one full poll cycle for a single watch."""
    log.info("Polling watch %s agent=%s wallet=%s chain=%s",
             watch["id"], watch["agent_id"], watch["wallet"], watch["chain"])

    holdings = await fetch_holdings(session, watch["chain"], watch["wallet"], watch.get("max_tokens_tracked", 20))
    if not holdings:
        # Empty wallet OR Blockscout transient error. Treat as no-op (no alerts, no error backoff).
        log.info("  no holdings (or fetch failed) for %s", watch["id"])
        update_after_poll(watch["id"], new_holdings={}, alerts_count=0)
        return

    # Score all held tokens (concurrency limited)
    sem = asyncio.Semaphore(4)

    async def scored(addr):
        async with sem:
            s = await fetch_score(session, watch["chain"], addr)
            return addr, s

    pairs = await asyncio.gather(*[scored(a) for a in holdings])
    new_scan = {addr: s for addr, s in pairs if s is not None}

    # Detect alerts
    known = watch.get("known_holdings", {})
    # Custom thresholds per watch
    min_drop = watch.get("min_score_drop", 20)
    min_alert = watch.get("min_alert_score", 50)
    alerts = []
    for addr, fresh in new_scan.items():
        prev = known.get(addr.lower(), {})
        prev_score = prev.get("score")
        new_score = fresh.get("score", 100)
        if prev_score is None:
            if new_score < min_alert:
                alerts.append({
                    "event": "risky_new_holding",
                    "token": {"address": addr, "symbol": fresh.get("symbol"), "name": fresh.get("name")},
                    "previous_score": None,
                    "current_score": new_score,
                    "delta": None,
                    "verdict": fresh.get("verdict"),
                    "risks": fresh.get("risks", [])[:5],
                })
        else:
            delta = new_score - prev_score
            if delta <= -min_drop:
                alerts.append({
                    "event": "score_drop",
                    "token": {"address": addr, "symbol": fresh.get("symbol"), "name": fresh.get("name")},
                    "previous_score": prev_score,
                    "current_score": new_score,
                    "delta": delta,
                    "verdict": fresh.get("verdict"),
                    "risks": fresh.get("risks", [])[:5],
                })

    # Deliver webhooks
    delivered = 0
    for alert in alerts:
        envelope = build_webhook_envelope(watch, alert)
        ok, status, body = await deliver_webhook(session, watch["callback_url"], envelope)
        log_alert(watch["id"], alert, {"ok": ok, "http_status": status, "response_excerpt": body})
        if ok:
            delivered += 1
            log.info("  alert delivered: %s %s prev=%s curr=%s",
                     alert["event"], alert["token"]["symbol"], alert.get("previous_score"), alert.get("current_score"))
        else:
            log.warning("  alert delivery FAILED: status=%s body=%s", status, body)

    # Persist
    update_after_poll(
        watch["id"],
        new_holdings={a: {"score": s["score"], "symbol": s.get("symbol"), "name": s.get("name"), "verdict": s.get("verdict"), "decimals": s.get("decimals", 18)} for a, s in new_scan.items()},
        alerts_count=delivered,
    )


async def main():
    log.info("watch_poller starting (tick=%ss)", TICK_SECONDS)
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                due = watches_due_for_poll()
                if due:
                    log.info("%d watch(es) due for poll", len(due))
                    # Process up to 8 in parallel; rest wait next tick
                    sem = asyncio.Semaphore(8)
                    async def run(w):
                        async with sem:
                            try:
                                await poll_one(session, w)
                            except Exception as e:
                                log.exception("poll_one failed for %s: %s", w["id"], e)
                                update_after_poll(w["id"], new_holdings={}, alerts_count=0, error=str(e)[:200])
                    await asyncio.gather(*[run(w) for w in due])
            except Exception as e:
                log.exception("tick error: %s", e)
            await asyncio.sleep(TICK_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
