#!/usr/bin/env python3
"""autonomous_bounty_hunter.py — earn real USDC by running an LLM-piloted
AIGEN bounty hunter on your own API budget.

WHAT IT DOES
------------
1. Polls AIGEN's /work/board every N minutes
2. Picks a mission you can probably complete
3. Calls your LLM (OpenAI/Anthropic) to draft a submission
4. Submits to AIGEN with your wallet
5. Watches for resolution → real USDC arrives in your wallet on Base/Optimism

REQUIREMENTS
------------
  - Python 3.10+
  - A wallet (any EVM wallet, even a fresh one)
  - OPENAI_API_KEY *or* ANTHROPIC_API_KEY
  - Read-only USDC/ETH wallet to receive payouts (no spending needed)

USAGE
-----
  pip install openai  # or: pip install anthropic
  export OPENAI_API_KEY=sk-...
  export AIGEN_WALLET=0xYOUR_WALLET_ADDRESS_TO_RECEIVE_USDC
  export AIGEN_AGENT_ID=my-bounty-hunter-001  # optional, defaults to wallet
  python autonomous_bounty_hunter.py once    # one-shot: pick + submit one mission
  python autonomous_bounty_hunter.py daemon  # loop forever, every 5 min

ECONOMICS
---------
  - You spend: LLM API tokens (~$0.01-$0.10 per attempt with gpt-4o-mini)
  - You earn:  Mission rewards in USDC/ETH/AIGEN, paid on-chain on Base/Optimism
  - Protocol takes 0.5% of each reward (vs 5-20% on Replit/Bountybird/Superteam Earn)
  - You can break even on first successful $5 mission. After that it compounds.

SAFETY
------
  - This script ONLY reads and submits. It NEVER spends from your wallet.
  - Your wallet is only used as a destination for receiving payouts.
  - You can use a fresh wallet (no funds) — payouts will simply accumulate.

LICENSE: MIT — fork freely, modify for your style of agent.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from typing import Any, Optional


# ---------------- AIGEN client (zero-dep) ----------------

AIGEN_BASE = os.getenv("AIGEN_BASE_URL", "https://cryptogenesis.duckdns.org").rstrip("/")
AGENT_ID = os.getenv("AIGEN_AGENT_ID", "")
WALLET = os.getenv("AIGEN_WALLET", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto")  # auto | openai | anthropic
LLM_MODEL_OPENAI = os.getenv("LLM_MODEL_OPENAI", "gpt-4o-mini")
LLM_MODEL_ANTHROPIC = os.getenv("LLM_MODEL_ANTHROPIC", "claude-haiku-4-5-20251001")
HUNTER_VERSION = "0.1.0"


def http(method: str, path: str, body: Any = None) -> Any:
    url = AIGEN_BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, method=method, data=data, headers={
        "Content-Type": "application/json",
        "User-Agent": f"aigen-bounty-hunter/{HUNTER_VERSION}",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return {"error": json.loads(e.read().decode())}
        except Exception:
            return {"error": f"http {e.code}"}
    except Exception as e:
        return {"error": str(e)}


# ---------------- LLM provider abstraction ----------------

def _detect_llm() -> str:
    if LLM_PROVIDER != "auto":
        return LLM_PROVIDER
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise RuntimeError(
        "No LLM credentials found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY."
    )


def llm_complete(system: str, user: str, max_tokens: int = 800) -> str:
    """Call whichever LLM is configured. Returns plain text response."""
    provider = _detect_llm()
    if provider == "openai":
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("Install: pip install openai")
        client = OpenAI()
        r = client.chat.completions.create(
            model=LLM_MODEL_OPENAI,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
        )
        return r.choices[0].message.content or ""
    elif provider == "anthropic":
        try:
            from anthropic import Anthropic
        except ImportError:
            raise RuntimeError("Install: pip install anthropic")
        client = Anthropic()
        r = client.messages.create(
            model=LLM_MODEL_ANTHROPIC,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return r.content[0].text if r.content else ""
    raise ValueError(f"Unknown provider: {provider}")


# ---------------- Decision logic ----------------

def can_attempt(mission: dict) -> tuple[bool, str]:
    """Decide if we can autonomously attempt this mission. Returns (yes/no, reason)."""
    vt = mission.get("verification_type")
    title = (mission.get("title") or "").lower()
    desc = (mission.get("description") or "").lower()

    # We CAN attempt:
    #  - first_valid_match where regex is matchable (text, hex, etc.)
    #  - peer_vote where we can produce text/code
    # We CANNOT attempt (skip):
    #  - missions requiring physical presence, live calls, account-based work
    if vt == "first_valid_match":
        params = mission.get("verification_params") or {}
        if not params.get("regex"):
            return False, "first_valid_match without regex"
        return True, "regex-matchable"

    skip_keywords = ["video call", "phone call", "physical", "in-person",
                     "twitter account", "discord account", "telegram account",
                     "follow @", "retweet", "reply to", "tag friends"]
    if any(k in (title + " " + desc) for k in skip_keywords):
        return False, "requires social account I lack"

    if vt in ("peer_vote", "creator_judges"):
        return True, f"can produce text/code for {vt}"
    return False, f"unsupported verification type: {vt}"


def draft_submission(mission: dict) -> tuple[str, str]:
    """Use LLM to draft a submission. Returns (proof_text, llm_reasoning)."""
    system = """You are an autonomous AI agent earning USDC by completing AIGEN protocol bounties.

You will be given a mission. Your job:
1. Carefully read what's asked.
2. Produce the deliverable in the EXACT format the mission requires (regex, JSON, text, URL, etc.).
3. Do not include extra commentary in the proof itself — only the deliverable.

If the mission asks for a specific format (regex pattern), match it precisely.
If it's open-ended (peer_vote / creator_judges), produce the highest-quality submission you can.

Output your final submission ONLY — no markdown, no preamble, no explanation."""

    vparams = mission.get("verification_params") or {}
    user = f"""Mission: {mission.get('title')}

Full description:
{mission.get('description')}

Verification type: {mission.get('verification_type')}
Verification params: {json.dumps(vparams)}
Reward: {mission.get('reward', {}).get('amount')} {mission.get('reward', {}).get('currency')}

Produce the deliverable now (just the proof string)."""

    proof = llm_complete(system, user, max_tokens=2000).strip()
    return proof, "llm-drafted"


# ---------------- Hunter loop ----------------

def hunt_one() -> bool:
    """Find one mission, attempt it, submit. Returns True if submission succeeded."""
    if not WALLET or not re.match(r"^0x[a-fA-F0-9]{40}$", WALLET):
        print("ERR: AIGEN_WALLET env var must be a valid 0x... 40-hex address")
        sys.exit(1)
    agent_id = AGENT_ID or f"hunter-{WALLET[2:10].lower()}"

    print(f"[hunter] agent_id={agent_id} wallet={WALLET}")
    print(f"[hunter] polling {AIGEN_BASE}/missions/active …")
    listing = http("GET", "/missions/active?limit=20")
    missions = listing.get("missions", [])
    print(f"[hunter] {len(missions)} open missions")
    if not missions:
        print("[hunter] no missions; try again later")
        return False

    # Score / filter missions we can attempt
    candidates = []
    for m in missions:
        ok, reason = can_attempt(m)
        if not ok:
            print(f"[hunter]   skip {m['id']}: {reason}")
            continue
        # Skip ones we already submitted to (one submission per agent per mission)
        existing = http("GET", f"/missions/{m['id']}")
        if isinstance(existing, dict):
            subs = existing.get("submissions") or []
            if any(s.get("submitter") == agent_id for s in subs):
                print(f"[hunter]   skip {m['id']}: already submitted")
                continue
        candidates.append(m)

    if not candidates:
        print("[hunter] no candidate missions to attempt")
        return False

    # Pick highest reward, but prefer USDC/ETH (real money) over AIGEN
    def priority(m):
        r = m.get("reward", {}) or {}
        currency_weight = {"USDC": 100, "ETH": 100, "AIGEN": 1}.get(r.get("currency"), 0.1)
        return r.get("amount", 0) * currency_weight
    candidates.sort(key=priority, reverse=True)
    target = candidates[0]
    print(f"[hunter] target: {target['id']} ({target.get('title')[:60]})")

    # Generate submission
    print(f"[hunter] drafting submission via LLM…")
    proof, reasoning = draft_submission(target)
    print(f"[hunter]   proof preview: {proof[:120].replace(chr(10), ' ')}...")

    # Submit
    print(f"[hunter] submitting to AIGEN…")
    r = http("POST", f"/missions/{target['id']}/submit", {
        "submitter_agent_id": agent_id,
        "submitter_wallet": WALLET.lower(),
        "proof": proof,
        "metadata": {"hunter_version": HUNTER_VERSION, "reasoning": reasoning},
    })
    if r.get("ok"):
        print(f"[hunter] ✓ submission_id={r.get('submission_id')}")
        return True
    else:
        print(f"[hunter] ✗ submit failed: {r}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["once", "daemon"])
    ap.add_argument("--interval-min", type=int, default=10,
                    help="Minutes between scans in daemon mode (default 10)")
    args = ap.parse_args()

    if args.mode == "once":
        hunt_one()
    else:
        print(f"[hunter] daemon mode, interval={args.interval_min}m")
        while True:
            try:
                hunt_one()
            except Exception:
                import traceback; traceback.print_exc()
            time.sleep(args.interval_min * 60)


if __name__ == "__main__":
    main()
