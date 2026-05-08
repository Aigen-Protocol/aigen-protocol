#!/usr/bin/env python3
"""SafeRouter fee attribution indexer.

For each SafeSwap event in swaps.jsonl (maintained by saferouter_indexer.py):
  - Calculate the 0.1% fee in tokenIn
  - Convert to USD value (rough)
  - Look up the routing agent by msg.sender wallet (agents.json)
  - record_inflow(source='saferouter_fee', attributed_agent_id=<agent_id or 'unknown_swap_<wallet>'>)

The actual cash sits in the InsurancePool contract until operator harvests
it via /revenue/admin/harvest. This indexer just builds the attribution
ledger — who deserves what AIGEN reward when buybacks finally execute.

Idempotent: tracks last-processed log index in indexer_state.

Modes:
  python3 saferouter_revenue_indexer.py once     # one cycle
  python3 saferouter_revenue_indexer.py daemon   # cycle every 5 min
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("revenue_indexer")

ROOT = Path("/home/luna/crypto-genesis/aigen")
SWAPS = ROOT / "swaps.jsonl"
AGENTS = ROOT / "agents.json"
STATE = ROOT / "revenue_indexer_state.json"

sys.path.insert(0, str(ROOT))
import revenue_pool

SAFEROUTER_FEE_BPS = 10  # 0.1%

# Token → (decimals, USD price approx) — for converting fee → USD micros
TOKEN_USD_HINTS = {
    # Base + Optimism
    "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": (6, 1.0),     # USDC base
    "0x4200000000000000000000000000000000000006": (18, 2400),    # WETH base+OP
    "0x0b2c639c533813f4aa9d7837caf62653d097ff85": (6, 1.0),     # USDC OP
    "0xfde4c96c8593536e31f229ea8f37b2ada2699bb2": (6, 1.0),     # USDT base
    "0xdac17f958d2ee523a2206206994597c13d831ec7": (6, 1.0),     # USDT eth
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": (6, 1.0),     # USDC eth
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": (18, 2400),    # WETH eth
    "0x4ed4e862860bed51a9570b96d89af5e1b0efefed": (18, 0.0086),  # DEGEN base
    "0x532f27101965dd16442e59d40670faf5ebb142e4": (18, 0.0085),  # BRETT base
    "0x940181a94a35a4569e4529a3cdfb74e38fd98631": (18, 1.30),    # AERO base
}


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"last_processed_index": -1, "events_recorded": 0, "fee_usd_total_micros": 0}


def save_state(s):
    STATE.write_text(json.dumps(s, indent=2))


def load_wallet_lookup() -> dict:
    """wallet (lowercase 0x) → agent_id"""
    if not AGENTS.exists():
        return {}
    d = json.loads(AGENTS.read_text())
    out = {}
    for a in d.get("agents", []):
        w = a.get("wallet", "")
        if w and w.startswith("0x") and len(w) == 42:
            out[w.lower()] = a["id"]
    return out


def usd_micros_for_fee(token_addr: str, fee_amount_raw: int) -> int:
    """Convert a fee amount (raw token wei) to USD value in micros (6 dec)."""
    info = TOKEN_USD_HINTS.get(token_addr.lower())
    if not info:
        return 0  # unknown token, can't price
    dec, usd_price = info
    # fee_amount_raw / 10**dec = whole tokens × usd_price = USD → ×1e6 = micros
    return int(fee_amount_raw * usd_price * 1_000_000) // (10 ** dec)


def cycle():
    state = load_state()
    last = state["last_processed_index"]
    wallet_to_agent = load_wallet_lookup()
    if not SWAPS.exists():
        log.info("no swaps.jsonl yet")
        return

    new_count = 0
    fee_micros_added = 0
    with SWAPS.open() as f:
        for i, line in enumerate(f):
            if i <= last:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            # Only attribute on actual SafeSwap (success), not Preflight or Block
            if ev.get("event") not in ("SafeSwap", "SafeSwapV2"):
                continue
            token_in = ev.get("token_in", "").lower()
            amount_in = int(ev.get("amount_in", 0))
            if amount_in <= 0:
                continue
            fee_raw = (amount_in * SAFEROUTER_FEE_BPS) // 10000
            usd_micros = usd_micros_for_fee(token_in, fee_raw)
            user_wallet = ev.get("user", "").lower()
            agent_id = wallet_to_agent.get(user_wallet, f"unknown_router_{user_wallet[:10]}")

            # Determine currency label for revenue_pool
            if token_in in ("0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
                            "0x0b2c639c533813f4aa9d7837caf62653d097ff85",
                            "0xfde4c96c8593536e31f229ea8f37b2ada2699bb2",
                            "0xdac17f958d2ee523a2206206994597c13d831ec7",
                            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"):
                currency = "USDC"
            elif token_in == "0x4200000000000000000000000000000000000006" or token_in == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2":
                currency = "WETH"
            else:
                currency = "TOKEN"  # generic — buyback bot will handle these later

            # Record only if we can value it (USD micros > 0)
            if usd_micros == 0 and currency == "TOKEN":
                # Token unknown to our pricing table — log but skip recording
                log.info("  skip unpriced token %s fee=%s tx=%s", token_in[:14], fee_raw, ev.get("tx_hash","?")[:14])
                state["last_processed_index"] = i
                continue

            revenue_pool.record_inflow(
                source="saferouter_fee",
                currency=currency,
                amount_wei=fee_raw,
                attributed_agent_id=agent_id,
                metadata={
                    "swap_tx_hash": ev.get("tx_hash"),
                    "swap_block": ev.get("block"),
                    "user_wallet": user_wallet,
                    "token_in": token_in,
                    "token_out": ev.get("token_out"),
                    "amount_in_wei": amount_in,
                    "fee_bps": SAFEROUTER_FEE_BPS,
                    "fee_usd_micros": usd_micros,
                    "indexer": "saferouter_revenue",
                },
            )
            new_count += 1
            fee_micros_added += usd_micros
            log.info("  +fee %s %s wei (~$%.6f) attributed=%s tx=%s",
                     currency, fee_raw, usd_micros / 1e6, agent_id, ev.get("tx_hash","?")[:14])
            state["last_processed_index"] = i

    if new_count == 0:
        log.info("no new SafeSwap events to attribute")
    else:
        state["events_recorded"] += new_count
        state["fee_usd_total_micros"] += fee_micros_added
        log.info("attributed %d new fees, total ~$%.6f", new_count, fee_micros_added / 1e6)
    save_state(state)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["once", "daemon"])
    ap.add_argument("--interval-min", type=int, default=5)
    args = ap.parse_args()

    if args.mode == "once":
        cycle()
    else:
        log.info("revenue indexer starting (interval=%dm)", args.interval_min)
        while True:
            try:
                cycle()
            except Exception:
                log.exception("cycle err")
            time.sleep(args.interval_min * 60)


if __name__ == "__main__":
    main()
