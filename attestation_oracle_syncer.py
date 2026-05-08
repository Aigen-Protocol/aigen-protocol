#!/usr/bin/env python3
"""Sync off-chain attestations.json → on-chain AttestationOracle.

For each attestation in our local store that:
  - is on a chain where the AttestationOracle is deployed (currently: Base)
  - has higher score OR newer issued_at than the on-chain version
  - is non-expired

…push setAttestation() so any contract on that chain can query
hasValidAttestation() / isAttestedSafe() / getAttestation() atomically.

Cost per write: ~50k gas at 0.006 gwei = ~$0.0007. For 30 attestations
in one batch: ~$0.02 total.

Modes:
  python3 attestation_oracle_syncer.py once       # one cycle
  python3 attestation_oracle_syncer.py daemon     # cycle every 30 min
  python3 attestation_oracle_syncer.py batch      # one big setAttestationsBatch tx
"""
import argparse, json, logging, sys, time
from pathlib import Path
from web3 import Web3
from eth_account import Account

WALLET = Path("/home/luna/crypto-genesis/.wallet.json")
ATTEST_FILE = Path("/home/luna/crypto-genesis/aigen/attestations.json")
DEPLOY_FILE = Path("/home/luna/crypto-genesis/contracts/attestation_oracle_deployment_base.json")
ABI_FILE = Path("/home/luna/crypto-genesis/contracts/AttestationOracle_abi.json")

CHAINS = {
    "base": {
        "rpc": "https://mainnet.base.org",
        "chain_id": 8453,
    },
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("attest_syncer")


def _short_id(att_id: str) -> bytes:
    """Convert 'att_abc123def456...' string id to 12-byte fixed."""
    return att_id.encode("ascii")[:12].ljust(12, b"\x00")


def _tier_to_int(tier: str) -> int:
    return {"free-bootstrap": 0, "standard": 1, "premium": 2}.get(tier, 0)


def load_local() -> list:
    if not ATTEST_FILE.exists():
        return []
    return json.loads(ATTEST_FILE.read_text()).get("attestations", [])


def get_oracle(chain: str = "base"):
    cfg = CHAINS[chain]
    deploy = json.loads(DEPLOY_FILE.read_text())
    abi = json.loads(ABI_FILE.read_text())
    w3 = Web3(Web3.HTTPProvider(cfg["rpc"]))
    acct = Account.from_key(json.loads(WALLET.read_text())["private_key"])
    contract = w3.eth.contract(address=Web3.to_checksum_address(deploy["contract"]), abi=abi)
    return w3, acct, contract


def needs_sync(local_att: dict, on_chain) -> bool:
    """Returns True if local has higher score OR newer issued_at OR on-chain expired."""
    if int(time.time()) >= local_att["expires_at"]:
        return False  # don't push expired
    on_chain_score, on_chain_issued, on_chain_expires = on_chain[0], on_chain[1], on_chain[2]
    if on_chain_expires == 0:
        return True
    if local_att["issued_at"] > on_chain_issued:
        return True
    return False


def diff_local_vs_chain(chain: str = "base") -> list:
    """Return list of attestations that need on-chain push."""
    w3, acct, oracle = get_oracle(chain)
    local = [a for a in load_local() if a.get("chain") == chain]
    # Group by token, pick latest per token
    by_token = {}
    for a in local:
        cur = by_token.get(a["token"])
        if cur is None or a["issued_at"] > cur["issued_at"]:
            by_token[a["token"]] = a
    needs = []
    for token, a in by_token.items():
        try:
            on_chain = oracle.functions.getAttestation(Web3.to_checksum_address(token)).call()
            # on_chain is the Attestation struct; tuple of (score, issuedAt, expiresAt, tier, idShort, flags, priceAigenPaid)
            sc = on_chain[0]
            iss = on_chain[1]
            exp = on_chain[2]
            if a["issued_at"] > iss or exp == 0:
                needs.append(a)
        except Exception as e:
            log.warning("getAttestation %s err: %s", token, e)
            needs.append(a)
        time.sleep(0.1)
    return needs


def sync_once(chain: str = "base", batch: bool = False, dry_run: bool = False):
    w3, acct, oracle = get_oracle(chain)
    me = acct.address
    bal = w3.eth.get_balance(me)
    log.info("[%s] signer=%s  balance=%.7f ETH", chain, me, bal / 1e18)

    needs = diff_local_vs_chain(chain)
    log.info("[%s] %d attestations need sync", chain, len(needs))
    if dry_run or not needs:
        for a in needs[:10]:
            log.info("  would push %s score=%d expires=%d", a["token"], a["score"], a["expires_at"])
        return

    nonce = w3.eth.get_transaction_count(me, "pending")
    gas_price = w3.eth.gas_price

    if batch and len(needs) > 1:
        # One batched tx
        tokens = [Web3.to_checksum_address(a["token"]) for a in needs]
        scores = [a["score"] for a in needs]
        flags = [a.get("flags", 0) for a in needs]
        expiries = [a["expires_at"] for a in needs]
        tiers = [_tier_to_int(a.get("tier", "free-bootstrap")) for a in needs]
        ids = [_short_id(a["id"]) for a in needs]
        prices = [a.get("price_paid_aigen", 0) for a in needs]
        fn = oracle.functions.setAttestationsBatch(tokens, scores, flags, expiries, tiers, ids, prices)
        try:
            gas = fn.estimate_gas({"from": me})
        except Exception as e:
            log.error("estimate_gas batch failed: %s", e)
            return
        tx = fn.build_transaction({
            "from": me, "nonce": nonce, "gas": int(gas * 1.3),
            "maxFeePerGas": gas_price * 2,
            "maxPriorityFeePerGas": w3.to_wei(0.001, "gwei"),
            "chainId": w3.eth.chain_id,
        })
        signed = acct.sign_transaction(tx)
        h = w3.eth.send_raw_transaction(signed.raw_transaction)
        log.info("batch tx: 0x%s  (%d attestations)", h.hex(), len(needs))
        r = w3.eth.wait_for_transaction_receipt(h, timeout=180)
        log.info("  status=%d gas=%d block=%d", r.status, r.gasUsed, r.blockNumber)
        return

    # Per-attestation
    for a in needs:
        fn = oracle.functions.setAttestation(
            Web3.to_checksum_address(a["token"]),
            a["score"],
            a.get("flags", 0),
            a["expires_at"],
            _tier_to_int(a.get("tier", "free-bootstrap")),
            _short_id(a["id"]),
            a.get("price_paid_aigen", 0),
        )
        try:
            gas = fn.estimate_gas({"from": me})
        except Exception as e:
            log.error("estimate_gas %s failed: %s", a["token"], e)
            continue
        tx = fn.build_transaction({
            "from": me, "nonce": nonce, "gas": int(gas * 1.3),
            "maxFeePerGas": gas_price * 2,
            "maxPriorityFeePerGas": w3.to_wei(0.001, "gwei"),
            "chainId": w3.eth.chain_id,
        })
        signed = acct.sign_transaction(tx)
        h = w3.eth.send_raw_transaction(signed.raw_transaction)
        nonce += 1
        try:
            r = w3.eth.wait_for_transaction_receipt(h, timeout=120)
            log.info("  %s pushed tx=0x%s status=%d gas=%d", a["token"][:14], h.hex()[:16], r.status, r.gasUsed)
        except Exception as e:
            log.warning("  %s wait err: %s", a["token"][:14], e)
        time.sleep(0.3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["once", "daemon", "batch", "dry"])
    ap.add_argument("--chain", default="base")
    ap.add_argument("--interval-min", type=int, default=30)
    args = ap.parse_args()

    if args.mode == "dry":
        sync_once(args.chain, dry_run=True)
    elif args.mode == "once":
        sync_once(args.chain, batch=False)
    elif args.mode == "batch":
        sync_once(args.chain, batch=True)
    else:  # daemon
        log.info("syncer daemon starting (interval=%dm)", args.interval_min)
        while True:
            try:
                sync_once(args.chain, batch=True)
            except Exception:
                log.exception("cycle err")
            time.sleep(args.interval_min * 60)


if __name__ == "__main__":
    main()
