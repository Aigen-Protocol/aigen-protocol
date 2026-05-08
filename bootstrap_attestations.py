#!/usr/bin/env python3
"""Bootstrap demand: proactively attest top trending tokens.

Pulls top pools from GeckoTerminal + our seed list, scans each, issues a
free-tier attestation. Splits across 3 service agent_ids to stay within
the 10-free-quota each. Output is a queryable attestation index that
makes /attest immediately useful for aggregators / wallets.

Usage:
  python3 bootstrap_attestations.py
"""
import json
import requests
import sys
import time
from collections import defaultdict

API = "http://127.0.0.1:4444"  # local scanner

# Service agent IDs (each gets 10 free attestations)
SERVICE_AGENTS = {
    "base": "aigen-bootstrap-base",
    "ethereum": "aigen-bootstrap-eth",
    "optimism": "aigen-bootstrap-op",
}

# Curated seed list (top blue-chips per chain)
SEED = {
    "base": [
        ("USDC",    "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"),
        ("WETH",    "0x4200000000000000000000000000000000000006"),
        ("DEGEN",   "0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed"),
        ("AERO",    "0x940181a94A35A4569E4529A3CDfB74e38FD98631"),
        ("BRETT",   "0x532f27101965dd16442E59d40670FaF5eBB142E4"),
        ("TOSHI",   "0xAC1Bd2486aAf3B5C0fc3Fd868558b082a531B2B4"),
        ("HIGHER",  "0x0578d8A44db98B23BF096A382e016e29a5Ce0ffe"),
        ("VIRTUAL", "0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b"),
        ("WELL",    "0xA88594D404727625A9437C3f886C7643872296AE"),
        ("MORPHO",  "0xBAa5CC21fd487B8Fcc2F632f3F4E8D37262a0842"),
    ],
    "ethereum": [
        ("USDT",  "0xdAC17F958D2eE523a2206206994597C13D831ec7"),
        ("USDC",  "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
        ("WETH",  "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
        ("DAI",   "0x6B175474E89094C44Da98b954EedeAC495271d0F"),
        ("LINK",  "0x514910771AF9Ca656af840dff83E8264EcF986CA"),
        ("UNI",   "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"),
        ("AAVE",  "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9"),
        ("PEPE",  "0x6982508145454Ce325dDbE47a25d4ec3d2311933"),
        ("SHIB",  "0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE"),
    ],
    "optimism": [
        ("USDC",  "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85"),
        ("USDT",  "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58"),
        ("WETH",  "0x4200000000000000000000000000000000000006"),
        ("OP",    "0x4200000000000000000000000000000000000042"),
        ("VELO",  "0x9560e827aF36c94D2Ac33a39bCE1Fe78631088Db"),
    ],
}


def fetch_geckoterminal_top(chain: str, pages: int = 2):
    """Pull top pools, extract unique base tokens."""
    api_chain = {"base": "base", "ethereum": "eth", "optimism": "optimism"}.get(chain, chain)
    tokens = set()
    for page in range(1, pages + 1):
        try:
            r = requests.get(f"https://api.geckoterminal.com/api/v2/networks/{api_chain}/pools",
                             params={"page": page}, timeout=10)
            data = r.json()
            for p in data.get("data", []):
                base_addr = p.get("relationships", {}).get("base_token", {}).get("data", {}).get("id", "")
                addr = base_addr.split("_", 1)[-1].lower()
                if addr.startswith("0x") and len(addr) == 42:
                    tokens.add(addr)
        except Exception as e:
            print(f"  geckoterminal {chain} p{page} err: {e}", file=sys.stderr)
        time.sleep(1)  # be nice to free API
    return tokens


def attest(agent_id: str, token: str, chain: str) -> dict:
    try:
        r = requests.post(f"{API}/attest", json={
            "agent_id": agent_id, "token": token, "chain": chain,
        }, timeout=30)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def main():
    started = time.time()
    results = defaultdict(list)

    for chain in ("base", "ethereum", "optimism"):
        agent = SERVICE_AGENTS[chain]
        print(f"\n=== {chain} (agent={agent}) ===")

        # Combine seed + trending
        seed_addrs = {addr.lower() for _, addr in SEED.get(chain, [])}
        trending = fetch_geckoterminal_top(chain, pages=2)
        all_tokens = seed_addrs | trending
        print(f"  seed={len(seed_addrs)} trending={len(trending)} total={len(all_tokens)}")

        # Stay under 10-free quota (1 per agent for now; we can rotate later)
        # Actually free quota is 10 per agent — we have ~10-30 tokens per chain
        # If we exceed 10, the rest will go to "standard" (100 AIGEN debit)
        # since service agents have no balance, those will fail with "insufficient"
        # Solution: limit to 10 per chain in the bootstrap
        target = list(all_tokens)[:10]

        for i, token in enumerate(target, 1):
            r = attest(agent, token, chain)
            if "error" in r:
                results["failed"].append({"chain": chain, "token": token, "error": r["error"]})
                print(f"  [{i:2d}/{len(target)}] {token[:14]}... FAIL: {r['error'][:60]}")
            else:
                results["issued"].append({
                    "chain": chain, "token": token, "id": r["id"],
                    "score": r["score"], "verdict": r["verdict"],
                })
                print(f"  [{i:2d}/{len(target)}] {token[:14]}... OK id={r['id']} score={r['score']} {r['verdict']}")
            time.sleep(0.3)

    elapsed = time.time() - started
    print(f"\n=== DONE in {elapsed:.1f}s ===")
    print(f"  issued:  {len(results['issued'])}")
    print(f"  failed:  {len(results['failed'])}")

    # Save report
    out = {
        "ran_at": int(time.time()),
        "issued": results["issued"],
        "failed": results["failed"],
    }
    open("/home/luna/crypto-genesis/aigen/bootstrap_report.json", "w").write(json.dumps(out, indent=2))
    print(f"\nReport: /home/luna/crypto-genesis/aigen/bootstrap_report.json")


if __name__ == "__main__":
    main()
