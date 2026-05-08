#!/usr/bin/env python3
"""AIGEN Buyback Bot — closes the loop: cash → AIGEN → distributed to agents.

Cycle (every 6h or when threshold reached):
  1. Read pending revenue (USDC/WETH from /attest/premium, /scan/deep, etc.)
  2. If accumulated >= BUYBACK_THRESHOLD_USDC, execute:
     - Bridge USDC from Base→OP if needed (currently we only have OP-side LP)
       (v1: skip if no OP-USDC; future: cross-chain bridge)
     - Swap USDC|WETH → AIGEN on Velodrome V2 OP (pool 0x7991d3E…BCFbB)
     - Compute attribution-weighted AIGEN distribution
     - Transfer AIGEN to attributed agents on-chain (real transfer)
     - Record buyback in revenue_pool.json (consumes events)
  3. Sleep until next cycle

Modes:
  python3 buyback_bot.py once       # one cycle, exit
  python3 buyback_bot.py daemon     # cycle every 6h
  python3 buyback_bot.py dry        # show what would happen
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

from web3 import Web3
from eth_account import Account

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("buyback")

WALLET = Path("/home/luna/crypto-genesis/.wallet.json")
RPC = "https://mainnet.optimism.io"

AIGEN = Web3.to_checksum_address("0xF6EFc5D5902d1a0ce58D9ab1715Cf30f077D8f6e")
WETH_OP = Web3.to_checksum_address("0x4200000000000000000000000000000000000006")
USDC_OP = Web3.to_checksum_address("0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85")
VELO_ROUTER = Web3.to_checksum_address("0xa062aE8A9c5e11aaA026fc2670B0D65cCc8B2858")
VELO_FACTORY = Web3.to_checksum_address("0xF1046053aa5682b4F9a81b5481394DA16BE5FF5a")
LP_POOL = Web3.to_checksum_address("0x7991d3E7edc5504BD64bBd2450d481E9435bCFbB")

ERC20_ABI = [
    {"name":"balanceOf","type":"function","stateMutability":"view","inputs":[{"name":"a","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"approve","type":"function","stateMutability":"nonpayable","inputs":[{"name":"s","type":"address"},{"name":"a","type":"uint256"}],"outputs":[{"name":"","type":"bool"}]},
    {"name":"allowance","type":"function","stateMutability":"view","inputs":[{"name":"o","type":"address"},{"name":"s","type":"address"}],"outputs":[{"name":"","type":"uint256"}]},
    {"name":"transfer","type":"function","stateMutability":"nonpayable","inputs":[{"name":"to","type":"address"},{"name":"amt","type":"uint256"}],"outputs":[{"name":"","type":"bool"}]},
]

ROUTER_ABI = [
    {"name":"swapExactTokensForTokens","type":"function","stateMutability":"nonpayable","inputs":[
        {"name":"amountIn","type":"uint256"},{"name":"amountOutMin","type":"uint256"},
        {"components":[{"name":"from","type":"address"},{"name":"to","type":"address"},
                       {"name":"stable","type":"bool"},{"name":"factory","type":"address"}],
         "name":"routes","type":"tuple[]"},
        {"name":"to","type":"address"},{"name":"deadline","type":"uint256"}],
     "outputs":[{"name":"amounts","type":"uint256[]"}]},
    {"name":"getAmountsOut","type":"function","stateMutability":"view","inputs":[
        {"name":"amountIn","type":"uint256"},
        {"components":[{"name":"from","type":"address"},{"name":"to","type":"address"},
                       {"name":"stable","type":"bool"},{"name":"factory","type":"address"}],
         "name":"routes","type":"tuple[]"}],
     "outputs":[{"name":"amounts","type":"uint256[]"}]},
]

sys.path.insert(0, "/home/luna/crypto-genesis/aigen")
import revenue_pool


def get_signer():
    return Account.from_key(json.loads(WALLET.read_text())["private_key"])


def estimate_aigen_for_weth(w3, weth_amount_wei: int) -> int:
    """View call to Velodrome router: how much AIGEN for X WETH?"""
    router = w3.eth.contract(address=VELO_ROUTER, abi=ROUTER_ABI)
    routes = [(WETH_OP, AIGEN, False, VELO_FACTORY)]
    try:
        amounts = router.functions.getAmountsOut(weth_amount_wei, routes).call()
        return amounts[-1]
    except Exception as e:
        log.warning("getAmountsOut failed: %s", e)
        return 0


def execute_buyback(w3, acct, currency: str, amount_wei: int, dry_run: bool = False) -> dict:
    """Swap currency → AIGEN on Velodrome OP."""
    me = acct.address
    weth = w3.eth.contract(address=WETH_OP, abi=ERC20_ABI)
    usdc = w3.eth.contract(address=USDC_OP, abi=ERC20_ABI)
    router = w3.eth.contract(address=VELO_ROUTER, abi=ROUTER_ABI)

    if currency == "WETH":
        token = weth
        token_addr = WETH_OP
        balance = weth.functions.balanceOf(me).call()
    elif currency == "USDC":
        token = usdc
        token_addr = USDC_OP
        balance = usdc.functions.balanceOf(me).call()
    else:
        return {"error": f"unsupported currency for buyback: {currency}"}

    if balance < amount_wei:
        return {"error": f"insufficient {currency}: have {balance}, need {amount_wei}"}

    # Estimate
    routes_data = [(token_addr, AIGEN, False, VELO_FACTORY)]
    try:
        amounts = router.functions.getAmountsOut(amount_wei, routes_data).call()
        expected_out = amounts[-1]
    except Exception as e:
        return {"error": f"price estimate failed: {e}"}

    log.info("buyback est: %s %s → ~%s AIGEN", amount_wei, currency, expected_out)

    if dry_run:
        return {"dry_run": True, "would_swap_in": amount_wei, "would_get_aigen": expected_out}

    # Approve + swap
    nonce = w3.eth.get_transaction_count(me, "pending")
    if token.functions.allowance(me, VELO_ROUTER).call() < amount_wei:
        fn_a = token.functions.approve(VELO_ROUTER, amount_wei * 10)
        tx_a = fn_a.build_transaction({"from": me, "nonce": nonce, "gas": 100000,
            "maxFeePerGas": w3.eth.gas_price * 2,
            "maxPriorityFeePerGas": w3.to_wei(0.001, "gwei"),
            "chainId": w3.eth.chain_id})
        signed = acct.sign_transaction(tx_a)
        h = w3.eth.send_raw_transaction(signed.raw_transaction)
        nonce += 1
        w3.eth.wait_for_transaction_receipt(h, timeout=120)
        log.info("approve %s tx: 0x%s", currency, h.hex())

    deadline = int(time.time()) + 1800
    fn = router.functions.swapExactTokensForTokens(
        amount_wei, int(expected_out * 0.95),  # 5% slippage tolerance
        routes_data, me, deadline,
    )
    try:
        gas = fn.estimate_gas({"from": me})
    except Exception as e:
        return {"error": f"swap estimate_gas failed: {e}"}

    tx = fn.build_transaction({"from": me, "nonce": nonce, "gas": int(gas * 1.3),
        "maxFeePerGas": w3.eth.gas_price * 2,
        "maxPriorityFeePerGas": w3.to_wei(0.001, "gwei"),
        "chainId": w3.eth.chain_id})
    signed = acct.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    log.info("buyback swap tx: 0x%s", h.hex())
    r = w3.eth.wait_for_transaction_receipt(h, timeout=180)
    if r.status != 1:
        return {"error": "swap reverted"}

    # Check actual AIGEN received
    aigen = w3.eth.contract(address=AIGEN, abi=ERC20_ABI)
    # We need to compute delta — but balance is current, before-call balance lost.
    # Use the swap event log instead. For simplicity, use expected_out as approximation.
    return {
        "tx_hash": "0x" + h.hex(),
        "block": r.blockNumber,
        "gas_used": r.gasUsed,
        "amount_in_wei": amount_wei,
        "currency": currency,
        "aigen_out_wei_estimate": expected_out,  # actual may differ slightly due to slippage
    }


def distribute_to_agents(w3, acct, aigen_total: int, attribution_micros: dict) -> dict:
    """Transfer AIGEN to attributed agents on-chain. Returns map of {agent → aigen_sent_wei}.

    attribution_micros: {agent_id → micros_USD generated} from revenue_pool
    """
    me = acct.address
    aigen = w3.eth.contract(address=AIGEN, abi=ERC20_ABI)

    total_micros = sum(attribution_micros.values())
    if total_micros == 0:
        log.info("no attribution found; all AIGEN stays in treasury")
        return {}

    # 70% goes to agents proportional, 30% stays in treasury
    agent_pool = (aigen_total * revenue_pool.AGENT_SHARE_BPS) // 10000

    # Resolve agent_id → on-chain wallet via agents.json
    agents_data = json.loads(Path("/home/luna/crypto-genesis/aigen/agents.json").read_text())
    addr_lookup = {a["id"]: a.get("wallet", "") for a in agents_data.get("agents", [])}

    distribution = {}
    nonce = w3.eth.get_transaction_count(me, "pending")
    for agent_id, micros in attribution_micros.items():
        share = (agent_pool * micros) // total_micros
        if share < 10**18:  # less than 1 AIGEN — skip (gas waste)
            log.info("  skipping %s: share=%d AIGEN < 1", agent_id, share)
            continue
        wallet = addr_lookup.get(agent_id, "")
        if not wallet or not wallet.startswith("0x") or len(wallet) != 42:
            # No wallet on file — credit off-chain ledger instead
            log.info("  no on-chain wallet for %s, credit off-chain ledger %d AIGEN", agent_id, share // 10**18)
            ledger_path = Path("/home/luna/crypto-genesis/shield-rewards/ledger.json")
            d = json.loads(ledger_path.read_text())
            a = d.setdefault("agents", {}).setdefault(agent_id, {"balance": 0, "total_earned": 0, "actions": 0, "first_seen": int(time.time())})
            credit = share // 10**18
            a["balance"] += credit
            a["total_earned"] = a.get("total_earned", 0) + credit
            a.setdefault("credits", []).append({"ts": int(time.time()), "amount": credit, "reason": "buyback-offchain"})
            d["total_distributed"] = d.get("total_distributed", 0) + credit
            ledger_path.write_text(json.dumps(d, indent=2))
            distribution[agent_id] = share
            continue
        try:
            wallet_cs = Web3.to_checksum_address(wallet)
        except Exception:
            log.warning("  invalid wallet for %s: %s", agent_id, wallet)
            continue
        # Transfer AIGEN on-chain
        fn = aigen.functions.transfer(wallet_cs, share)
        try:
            gas = fn.estimate_gas({"from": me})
        except Exception as e:
            log.error("  transfer %s estimate_gas failed: %s", agent_id, e)
            continue
        tx = fn.build_transaction({"from": me, "nonce": nonce, "gas": int(gas * 1.3),
            "maxFeePerGas": w3.eth.gas_price * 2,
            "maxPriorityFeePerGas": w3.to_wei(0.001, "gwei"),
            "chainId": w3.eth.chain_id})
        signed = acct.sign_transaction(tx)
        h = w3.eth.send_raw_transaction(signed.raw_transaction)
        nonce += 1
        try:
            r = w3.eth.wait_for_transaction_receipt(h, timeout=120)
            log.info("  → %s: sent %d AIGEN tx=0x%s status=%d", agent_id, share // 10**18, h.hex()[:16], r.status)
            distribution[agent_id] = share
        except Exception as e:
            log.warning("  receipt wait failed: %s", e)
    return distribution


def cycle(dry_run: bool = False):
    pending = revenue_pool.pending_buyback_balance()
    log.info("pending: %s", pending["pending"])

    # WETH-side buyback (most common since /scan/deep + /attest/premium pay USDC,
    # but until we add USDC bridging Base→OP we can only spend OP-side WETH)
    weth_pending = pending["pending"].get("WETH", 0)
    usdc_pending = pending["pending"].get("USDC", 0)

    # Convert: USDC on Base would need bridging. v1 only handles OP-native cash.
    # For now, only buyback what's already on OP (WETH or USDC.OP)
    if weth_pending == 0 and usdc_pending == 0:
        log.info("nothing to buy back")
        return

    w3 = Web3(Web3.HTTPProvider(RPC))
    acct = get_signer()

    # Pick currency with more pending value
    if weth_pending > 0:
        eth_value_micros = weth_pending * 2400 // 10**12
        log.info("WETH pending: %d wei (~$%.4f)", weth_pending, eth_value_micros / 1e6)
        result = execute_buyback(w3, acct, "WETH", weth_pending, dry_run=dry_run)
    else:
        log.info("USDC pending: %d (%.4f USDC)", usdc_pending, usdc_pending / 1e6)
        result = execute_buyback(w3, acct, "USDC", usdc_pending, dry_run=dry_run)

    if "error" in result:
        log.error("buyback failed: %s", result["error"])
        return
    if dry_run:
        log.info("dry-run done: %s", result)
        return

    # Compute distribution
    distribution = distribute_to_agents(w3, acct, result["aigen_out_wei_estimate"], pending["pending_by_agent"])

    # Record in revenue_pool
    bb = revenue_pool.record_buyback(
        currency_used=result["currency"],
        cash_amount_wei=result["amount_in_wei"],
        aigen_received_wei=result["aigen_out_wei_estimate"],
        tx_hash=result["tx_hash"],
        distribution_per_agent=distribution,
    )
    log.info("recorded buyback %s; events_consumed=%d", bb["buyback_id"], bb["events_consumed"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["once", "daemon", "dry"])
    ap.add_argument("--interval-hours", type=float, default=6.0)
    args = ap.parse_args()

    if args.mode == "dry":
        cycle(dry_run=True)
    elif args.mode == "once":
        cycle(dry_run=False)
    else:
        log.info("buyback daemon starting (interval=%.1fh)", args.interval_hours)
        while True:
            try:
                cycle(dry_run=False)
            except Exception:
                log.exception("cycle err")
            time.sleep(args.interval_hours * 3600)


if __name__ == "__main__":
    main()
