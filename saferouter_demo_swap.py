#!/usr/bin/env python3
"""SafeRouter demo: swap 0.5 BRETT → USDC on Base via 0xb200...8FA.

This is the FIRST live swap through our SafeRouter. Goal: prove the contract
works end-to-end and produce a cite-able tx with the SafeSwap event.

Safety:
- Tiny amount (0.5 BRETT, ~$0.05 at current price)
- BRETT score on-chain = 100 (won't trigger revert)
- amount_out_min = 0 (no slippage protection — it's a demo)
"""
import json
import sys
import time
from pathlib import Path
from web3 import Web3
from eth_account import Account

WALLET_FILE = Path("/home/luna/crypto-genesis/.wallet.json")
RPC = "https://base-rpc.publicnode.com"

SAFEROUTER = Web3.to_checksum_address("0xb200357a35C7e96A81190C53631BC5Beca84A8FA")
BRETT     = Web3.to_checksum_address("0x532f27101965dd16442E59d40670FaF5eBB142E4")
USDC      = Web3.to_checksum_address("0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913")

ERC20_ABI = [
    {"name": "balanceOf", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "a", "type": "address"}], "outputs": [{"name": "", "type": "uint256"}]},
    {"name": "approve", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
     "outputs": [{"name": "", "type": "bool"}]},
    {"name": "allowance", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
     "outputs": [{"name": "", "type": "uint256"}]},
]

SAFEROUTER_ABI = [
    {"name": "safeSwap", "type": "function", "stateMutability": "nonpayable",
     "inputs": [
        {"name": "tokenIn", "type": "address"},
        {"name": "tokenOut", "type": "address"},
        {"name": "amountIn", "type": "uint256"},
        {"name": "amountOutMin", "type": "uint256"},
        {"name": "stable", "type": "bool"},
        {"name": "deadline", "type": "uint256"},
     ],
     "outputs": [{"name": "amountOut", "type": "uint256"}]},
    {"name": "totalSwaps", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"name": "", "type": "uint256"}]},
    {"name": "blockedSwaps", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"name": "", "type": "uint256"}]},
]


def main():
    w3 = Web3(Web3.HTTPProvider(RPC))
    assert w3.is_connected(), "RPC not reachable"

    acct = Account.from_key(json.loads(WALLET_FILE.read_text())["private_key"])
    me = acct.address
    print(f"signer: {me}")

    brett = w3.eth.contract(address=BRETT, abi=ERC20_ABI)
    usdc  = w3.eth.contract(address=USDC,  abi=ERC20_ABI)
    router = w3.eth.contract(address=SAFEROUTER, abi=SAFEROUTER_ABI)

    bal_eth = w3.eth.get_balance(me)
    bal_brett = brett.functions.balanceOf(me).call()
    bal_usdc_before = usdc.functions.balanceOf(me).call()
    pre_total = router.functions.totalSwaps().call()
    pre_blocked = router.functions.blockedSwaps().call()

    print(f"PRE  ETH:   {bal_eth/1e18:.6f}")
    print(f"PRE  BRETT: {bal_brett/1e18:.6f}")
    print(f"PRE  USDC:  {bal_usdc_before/1e6:.6f}")
    print(f"PRE  totalSwaps={pre_total} blockedSwaps={pre_blocked}")

    AMOUNT_IN = int(0.5e18)  # 0.5 BRETT
    if bal_brett < AMOUNT_IN:
        print(f"insufficient BRETT (have {bal_brett}, need {AMOUNT_IN})")
        sys.exit(1)

    deadline = int(time.time()) + 1800
    chain_id = w3.eth.chain_id

    # === Step 1: approve SafeRouter to spend BRETT ===
    current_allowance = brett.functions.allowance(me, SAFEROUTER).call()
    if current_allowance < AMOUNT_IN:
        print(f"\n--- step 1: approve SafeRouter for {AMOUNT_IN} BRETT ---")
        nonce = w3.eth.get_transaction_count(me)
        approve_tx = brett.functions.approve(SAFEROUTER, AMOUNT_IN).build_transaction({
            "from": me, "nonce": nonce, "gas": 100000,
            "maxFeePerGas": w3.eth.gas_price * 2,
            "maxPriorityFeePerGas": w3.to_wei(0.001, "gwei"),
            "chainId": chain_id,
        })
        signed = acct.sign_transaction(approve_tx)
        h = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"approve tx: {h.hex()}")
        rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=120)
        print(f"  status={rcpt.status} gas_used={rcpt.gasUsed}")
        if rcpt.status != 1:
            print("approve failed; abort")
            sys.exit(1)
    else:
        print(f"already approved (allowance={current_allowance})")

    # === Step 2: safeSwap(BRETT, USDC, 0.5e18, 0, stable=false, deadline) ===
    print(f"\n--- step 2: safeSwap 0.5 BRETT → USDC (volatile pool, no slippage limit) ---")
    nonce = w3.eth.get_transaction_count(me)
    fn = router.functions.safeSwap(BRETT, USDC, AMOUNT_IN, 0, False, deadline)
    try:
        gas = fn.estimate_gas({"from": me})
        print(f"gas estimate: {gas}")
    except Exception as e:
        print(f"estimate_gas failed: {e}")
        # try with conservative fixed gas
        gas = 500000

    swap_tx = fn.build_transaction({
        "from": me, "nonce": nonce, "gas": int(gas * 1.3),
        "maxFeePerGas": w3.eth.gas_price * 2,
        "maxPriorityFeePerGas": w3.to_wei(0.001, "gwei"),
        "chainId": chain_id,
    })
    signed = acct.sign_transaction(swap_tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"swap tx: {h.hex()}")
    print(f"  https://basescan.org/tx/{h.hex()}")
    rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=180)
    print(f"  status={rcpt.status} gas_used={rcpt.gasUsed} block={rcpt.blockNumber}")
    if rcpt.status != 1:
        print("swap reverted")
        sys.exit(2)

    # === Step 3: verify state changes ===
    bal_brett_after = brett.functions.balanceOf(me).call()
    bal_usdc_after = usdc.functions.balanceOf(me).call()
    post_total = router.functions.totalSwaps().call()
    post_blocked = router.functions.blockedSwaps().call()

    print(f"\nPOST BRETT: {bal_brett_after/1e18:.6f}  (Δ {(bal_brett_after-bal_brett)/1e18:+.6f})")
    print(f"POST USDC:  {bal_usdc_after/1e6:.6f}    (Δ {(bal_usdc_after-bal_usdc_before)/1e6:+.6f})")
    print(f"POST totalSwaps={post_total} (Δ {post_total-pre_total:+}) blockedSwaps={post_blocked}")

    # Decode SafeSwap event from receipt
    print("\nLogs in receipt:")
    for log in rcpt.logs:
        if log.address.lower() == SAFEROUTER.lower():
            print(f"  SafeRouter event: topics={[t.hex() for t in log.topics]} data={log.data.hex()}")


if __name__ == "__main__":
    main()
