#!/usr/bin/env python3
"""SafeRouter event indexer.

Listens to SafeSwap and SwapBlocked events on the deployed SafeRouter,
appends to swaps.jsonl. Replaces a subgraph: lighter, faster, no Graph
hosted service dependency.

Polls eth_getLogs every 30s from last_block forward. Idempotent — safe
to restart any time. Stores progress in indexer_state.json.

Exposed via the scanner's /saferouter/swaps and /saferouter/swaps/recent
endpoints (added separately to scanner.py).
"""
import asyncio
import json
import logging
import os
import time
from pathlib import Path

import aiohttp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("saferouter_indexer")

ROOT = Path("/home/luna/crypto-genesis/aigen")
SWAPS = ROOT / "swaps.jsonl"
STATE = ROOT / "indexer_state.json"

CONFIG = {
    "base": {
        "rpc": "https://mainnet.base.org",
        "rpc_fallbacks": ["https://base-rpc.publicnode.com", "https://base.llamarpc.com"],
        "router": "0xF6EFc5D5902d1a0ce58D9ab1715Cf30f077D8f6e",  # V2
        "router_v1": "0xb200357a35C7e96A81190C53631BC5Beca84A8FA",  # also indexed (see addresses array)
        "addresses": [
            "0xF6EFc5D5902d1a0ce58D9ab1715Cf30f077D8f6e",  # V2
            "0xb200357a35C7e96A81190C53631BC5Beca84A8FA",  # v1
        ],
        "deploy_block": 45680000,  # before first known SafeSwap on v1 (45686499)
        "events": {
            # v1 SafeSwap(address indexed user, address tokenIn, address tokenOut, uint256 amountIn, uint8 safetyScore)
            "0x8c05da6a4f2bef6d01aad57094fab3ea93e5571f8dd36d3e7e6cf80c7b993591": "SafeSwap",
            # v2 SafeSwap (added amountOut)
            "0x697be5be799981b1414402c0dfeb0a63035a65ce971838f370b2e2d6b5fa4d69": "SafeSwapV2",
            # v2 SwapPreflight(address indexed user, address tokenOut, uint8 score, bool allowed)
            "0xb372fa47a5acaa903865f746443ade8668cf2fe3969e79e3b3b9d21f53b892be": "SwapPreflight",
            # v1 SwapBlocked
            "0xace773ad80d904f35b2f2d7e96ae3ac2622d18d49ad6408e5ac703ef7497267f": "SwapBlocked",
            # v1 ScamPrevented
            "0xe62f4b652f76e78e6cc9891d41ac53544b4c3d83082846b1c7be1e62c26830cb": "ScamPrevented",
        },
    },
}

POLL_INTERVAL = 30
LOG_RANGE = 9999  # mainnet.base.org caps at 10000


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {}


def save_state(state):
    STATE.write_text(json.dumps(state, indent=2))


def append_swap(entry):
    with SWAPS.open("a") as f:
        f.write(json.dumps(entry) + "\n")


async def get_block_number(session, rpc):
    async with session.post(rpc, json={"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []},
                            timeout=aiohttp.ClientTimeout(total=10)) as r:
        d = await r.json()
        return int(d["result"], 16)


async def get_logs(session, rpc, addresses, from_block, to_block):
    body = {
        "jsonrpc": "2.0", "id": 1, "method": "eth_getLogs",
        "params": [{
            "fromBlock": hex(from_block),
            "toBlock": hex(to_block),
            "address": addresses if isinstance(addresses, list) else [addresses],
        }],
    }
    async with session.post(rpc, json=body, timeout=aiohttp.ClientTimeout(total=20)) as r:
        d = await r.json()
        if "error" in d:
            raise RuntimeError(f"eth_getLogs: {d['error']}")
        return d.get("result", [])


def decode_safeswap(logentry):
    # topics[0]=sig, topics[1]=user (indexed)
    # data: tokenIn(32) + tokenOut(32) + amountIn(32) + safetyScore(32)
    user = "0x" + logentry["topics"][1][-40:]
    data = logentry["data"][2:]
    token_in  = "0x" + data[24:64]
    token_out = "0x" + data[64+24:128]
    amount_in = int(data[128:192], 16)
    score     = int(data[192:256], 16)
    return {
        "event": "SafeSwap",
        "user": user.lower(),
        "token_in":  token_in.lower(),
        "token_out": token_out.lower(),
        "amount_in": amount_in,
        "safety_score": score,
    }


def decode_swapblocked(logentry):
    # event SwapBlocked(address indexed user, address tokenOut, uint8 safetyScore, uint256 flags, string reason)
    user = "0x" + logentry["topics"][1][-40:]
    data = logentry["data"][2:]
    token_out = "0x" + data[24:64]
    score = int(data[64:128], 16)
    flags = int(data[128:192], 16)
    # string reason follows: offset, length, data
    reason_off = int(data[192:256], 16) * 2
    reason_start = reason_off
    reason_len = int(data[reason_start:reason_start+64], 16) * 2
    reason_data = data[reason_start+64: reason_start+64+reason_len]
    try:
        reason = bytes.fromhex(reason_data).decode("utf-8")
    except Exception:
        reason = ""
    return {
        "event": "SwapBlocked",
        "user": user.lower(),
        "token_out": token_out.lower(),
        "safety_score": score,
        "flags": flags,
        "reason": reason,
    }


def decode_scamprevented(logentry):
    user = "0x" + logentry["topics"][1][-40:]
    data = logentry["data"][2:]
    token_out = "0x" + data[24:64]
    estimated_loss = int(data[64:128], 16)
    return {
        "event": "ScamPrevented",
        "user": user.lower(),
        "token_out": token_out.lower(),
        "estimated_loss": estimated_loss,
    }


def decode_safeswap_v2(logentry):
    user = "0x" + logentry["topics"][1][-40:]
    data = logentry["data"][2:]
    return {
        "event": "SafeSwapV2",
        "user": user.lower(),
        "token_in":  "0x" + data[24:64],
        "token_out": "0x" + data[64+24:128],
        "amount_in":  int(data[128:192], 16),
        "amount_out": int(data[192:256], 16),
        "safety_score": int(data[256:320], 16),
    }


def decode_swappreflight(logentry):
    user = "0x" + logentry["topics"][1][-40:]
    data = logentry["data"][2:]
    return {
        "event": "SwapPreflight",
        "user": user.lower(),
        "token_out": "0x" + data[24:64],
        "score": int(data[64:128], 16),
        "allowed": int(data[128:192], 16) == 1,
    }


DECODERS = {
    "SafeSwap": decode_safeswap,
    "SafeSwapV2": decode_safeswap_v2,
    "SwapPreflight": decode_swappreflight,
    "SwapBlocked": decode_swapblocked,
    "ScamPrevented": decode_scamprevented,
}


async def index_chain(chain: str):
    cfg = CONFIG[chain]
    state = load_state()
    chain_state = state.get(chain, {})
    last_block = chain_state.get("last_block")

    async with aiohttp.ClientSession() as session:
        head = await get_block_number(session, cfg["rpc"])
        if last_block is None:
            # first run: start 30 days back (~1.3M blocks at 2s blocks)
            last_block = max(cfg["deploy_block"], head - 1_300_000)
            log.info("[%s] first run, starting from block %d (head=%d)", chain, last_block, head)

        cursor = last_block + 1
        new_count = 0
        while cursor <= head:
            to_block = min(cursor + LOG_RANGE - 1, head)
            try:
                logs = await get_logs(session, cfg["rpc"], cfg.get("addresses", [cfg["router"]]), cursor, to_block)
            except Exception as e:
                log.warning("[%s] getLogs %d-%d failed: %s", chain, cursor, to_block, e)
                break

            for entry in logs:
                topic0 = entry["topics"][0] if entry.get("topics") else None
                ev_name = cfg["events"].get(topic0)
                if not ev_name:
                    continue
                decoder = DECODERS.get(ev_name)
                if not decoder:
                    continue
                try:
                    decoded = decoder(entry)
                except Exception as e:
                    log.warning("decode %s failed: %s", ev_name, e)
                    continue
                row = {
                    "chain": chain,
                    "block": int(entry["blockNumber"], 16),
                    "tx_hash": entry["transactionHash"],
                    "log_index": int(entry["logIndex"], 16),
                    "ts": int(time.time()),  # ingestion time; on-chain ts requires block fetch
                    **decoded,
                }
                append_swap(row)
                new_count += 1
                log.info("[%s] %s tx=%s user=%s", chain, ev_name, row["tx_hash"][:10], row["user"][:10])

            cursor = to_block + 1

        chain_state["last_block"] = head
        chain_state["last_run"] = int(time.time())
        chain_state["events_total"] = chain_state.get("events_total", 0) + new_count
        state[chain] = chain_state
        save_state(state)
        if new_count:
            log.info("[%s] indexed %d events up to block %d", chain, new_count, head)


async def main():
    log.info("saferouter_indexer starting (poll=%ds)", POLL_INTERVAL)
    while True:
        try:
            for chain in CONFIG:
                await index_chain(chain)
        except Exception:
            log.exception("cycle error")
        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
