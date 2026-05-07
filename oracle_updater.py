#!/usr/bin/env python3
"""SafeAgent Oracle on-chain updater.

Pulls fresh safety scores from our local /scan endpoint and pushes them
to the on-chain oracle (Base) so SafeRouter and any third-party contract
using SafeGuard sees up-to-date data.

Without this, the oracle is stale (last update Apr 4, 2026) and the
SafeRouter blocks/allows tokens based on old scores.

Usage:
  python3 oracle_updater.py once       # one-shot update of seed list
  python3 oracle_updater.py daemon     # long-running, refresh every 6h
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

import requests
from web3 import Web3
from eth_account import Account

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("oracle_updater")

WALLET_FILE = Path("/home/luna/crypto-genesis/.wallet.json")
SCANNER = "http://127.0.0.1:4444"

CONFIG = {
    "base": {
        "rpc": "https://base-rpc.publicnode.com",
        "chain_id": 8453,
        "oracle": Web3.to_checksum_address("0x37b9e9B8789181f1AaaD1cD51A5f00A887fa9b8e"),
    },
    "optimism": {
        "rpc": "https://mainnet.optimism.io",
        "chain_id": 10,
        "oracle": Web3.to_checksum_address("0x3B8A6D696f2104A9aC617bB91e6811f489498047"),
    },
}

# updateScore(address token, uint8 score, uint256 flags)
UPDATE_SELECTOR = "0x6792ad2d"

ORACLE_ABI = [
    {"name": "getSafetyScore", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "token", "type": "address"}],
     "outputs": [{"name": "score", "type": "uint8"}, {"name": "flags", "type": "uint256"}, {"name": "updatedAt", "type": "uint256"}]},
    {"name": "updateScore", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"name": "token", "type": "address"}, {"name": "score", "type": "uint8"}, {"name": "flags", "type": "uint256"}],
     "outputs": []},
    {"name": "operator", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"name": "", "type": "address"}]},
]

# Top tokens to keep current. Curated for relevance, not exhaustive.
SEED_TOKENS = {
    "base": [
        ("USDC",    "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"),
        ("WETH",    "0x4200000000000000000000000000000000000006"),
        ("USDT",    "0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2"),
        ("DAI",     "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb"),
        ("DEGEN",   "0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed"),
        ("AERO",    "0x940181a94A35A4569E4529A3CDfB74e38FD98631"),
        ("BRETT",   "0x532f27101965dd16442E59d40670FaF5eBB142E4"),
        ("TOSHI",   "0xAC1Bd2486aAf3B5C0fc3Fd868558b082a531B2B4"),
        ("HIGHER",  "0x0578d8A44db98B23BF096A382e016e29a5Ce0ffe"),
        ("VIRTUAL", "0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b"),
        ("WELL",    "0xA88594D404727625A9437C3f886C7643872296AE"),
        ("MORPHO",  "0xBAa5CC21fd487B8Fcc2F632f3F4E8D37262a0842"),
        ("KEYCAT",  "0x9a26F5433671751C3276a065f57e5a02D2817973"),
        ("NORMIE",  "0x7F12d13B34F5F4f0a9449c16Bcd42f0da47AF200"),
        ("MIGGLES", "0xB1a03EdA10342529bBF8EB700a06C60441fEf25d"),
        ("MOG",     "0x2Da56AcB9Ea78330f947bD57C54119Debda7AF71"),
        ("BENJI",   "0xBC45647eA894030a4E9801Ec03479739FA2485F0"),
        ("FAI",     "0xb33Ff54b9F7242EF1593d2C9Bcd8f9df46c77935"),
        ("GHIBLI",  "0x9C7BeBa8F6eF6643aBd725e45a4E8387eF260649"),
        ("CHOMP",   "0xebFF2dB643Cf955247339c8c6bCD8406308ca437"),
    ],
}


def load_account():
    w = json.loads(WALLET_FILE.read_text())
    return Account.from_key(w["private_key"])


def get_score_from_scanner(address: str, chain: str) -> int | None:
    try:
        r = requests.get(f"{SCANNER}/scan", params={"address": address, "chain": chain}, timeout=20)
        if r.status_code != 200:
            return None
        d = r.json()
        return int(d.get("safety_score", d.get("score", 0)))
    except Exception as e:
        log.warning("scan %s/%s failed: %s", chain, address, e)
        return None


def update_one(w3: Web3, oracle, account, token, score, flags=0, dry_run=False):
    """Push a single score update on-chain. Skip if existing score matches & is recent."""
    token_cs = Web3.to_checksum_address(token)
    try:
        existing_score, existing_flags, updated_at = oracle.functions.getSafetyScore(token_cs).call()
    except Exception as e:
        existing_score, existing_flags, updated_at = 0, 0, 0
        log.warning("oracle.getSafetyScore(%s) failed: %s", token, e)

    age_days = (int(time.time()) - updated_at) / 86400 if updated_at else 999
    if existing_score == score and existing_flags == flags and age_days < 1:
        return {"skipped": True, "reason": "score unchanged + fresh", "existing_score": existing_score}

    log.info("update %s: %d → %d (flags=%d, age=%.1fd)", token, existing_score, score, flags, age_days)
    if dry_run:
        return {"skipped": True, "reason": "dry-run"}

    nonce = w3.eth.get_transaction_count(account.address)
    fn = oracle.functions.updateScore(token_cs, score, flags)
    try:
        gas = fn.estimate_gas({"from": account.address})
    except Exception as e:
        log.error("gas estimate failed for %s: %s", token, e)
        return {"error": f"estimate_gas: {e}"}

    tx = fn.build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": int(gas * 1.2),
        "maxFeePerGas": w3.eth.gas_price * 2,
        "maxPriorityFeePerGas": w3.to_wei(0.001, "gwei"),
        "chainId": w3.eth.chain_id,
    })
    signed = account.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(h, timeout=60)
    return {
        "ok": receipt.status == 1,
        "tx_hash": h.hex(),
        "block": receipt.blockNumber,
        "gas_used": receipt.gasUsed,
        "previous_score": existing_score,
        "new_score": score,
    }


def update_chain(chain: str, dry_run: bool = False) -> dict:
    cfg = CONFIG[chain]
    w3 = Web3(Web3.HTTPProvider(cfg["rpc"]))
    if not w3.is_connected():
        return {"error": f"cannot connect to {cfg['rpc']}"}

    account = load_account()
    oracle = w3.eth.contract(address=cfg["oracle"], abi=ORACLE_ABI)

    try:
        operator = oracle.functions.operator().call()
        if operator.lower() != account.address.lower():
            return {"error": f"signer {account.address} is not operator {operator}"}
    except Exception as e:
        log.warning("operator check skipped: %s", e)

    bal = w3.eth.get_balance(account.address)
    log.info("chain=%s account=%s balance=%.6f ETH oracle=%s",
             chain, account.address, w3.from_wei(bal, "ether"), cfg["oracle"])

    results = {"chain": chain, "started_at": int(time.time()), "updates": []}
    for ticker, addr in SEED_TOKENS.get(chain, []):
        score = get_score_from_scanner(addr, chain)
        if score is None:
            log.warning("  %s: scanner unavailable, skipping", ticker)
            results["updates"].append({"ticker": ticker, "skipped": True, "reason": "no scan"})
            continue
        try:
            r = update_one(w3, oracle, account, addr, score, flags=0, dry_run=dry_run)
            r["ticker"] = ticker
            r["address"] = addr
            r["score"] = score
            results["updates"].append(r)
        except Exception as e:
            log.exception("update %s failed", ticker)
            results["updates"].append({"ticker": ticker, "address": addr, "error": str(e)})
        time.sleep(0.5)  # be gentle on RPC

    results["finished_at"] = int(time.time())
    results["success"] = sum(1 for u in results["updates"] if u.get("ok"))
    results["skipped"] = sum(1 for u in results["updates"] if u.get("skipped"))
    results["failed"] = sum(1 for u in results["updates"] if u.get("error"))
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["once", "daemon", "dry"])
    p.add_argument("--chain", default="base")
    p.add_argument("--interval-hours", type=float, default=6.0)
    args = p.parse_args()

    if args.mode == "dry":
        r = update_chain(args.chain, dry_run=True)
        print(json.dumps(r, indent=2))
        return

    if args.mode == "once":
        r = update_chain(args.chain, dry_run=False)
        print(json.dumps(r, indent=2))
        return

    # daemon
    log.info("oracle_updater daemon starting (interval=%.1fh)", args.interval_hours)
    while True:
        try:
            r = update_chain(args.chain, dry_run=False)
            log.info("cycle done: success=%d skipped=%d failed=%d", r.get("success", 0), r.get("skipped", 0), r.get("failed", 0))
        except Exception as e:
            log.exception("cycle error: %s", e)
        time.sleep(args.interval_hours * 3600)


if __name__ == "__main__":
    main()
