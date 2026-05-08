"""AIGEN signed attestations — first real utility for $AIGEN.

A token deployer (or anyone) pays N AIGEN and receives a signed safety
attestation valid for D days. Downstream contracts/aggregators/wallets
can verify the attestation cryptographically without re-querying our oracle.

Pricing model (v1, off-chain debit from shield-rewards/ledger.json):
  - First 10 attestations per agent_id: FREE (bootstrap)
  - Standard: 100 AIGEN per attestation, 30-day expiry
  - Premium tier (if agent has 5+ approved contributions): 50 AIGEN, 90-day expiry

The attestation reuses the same HMAC secret as /watch — single public-key
fingerprint to pin per consumer.

On-chain payment will come in v2: deployer transfers AIGEN to treasury,
poller detects, attestation issued automatically.
"""
import hashlib
import hmac
import json
import re
import time
import uuid
from pathlib import Path

ATTEST_FILE = Path("/home/luna/crypto-genesis/aigen/attestations.json")
LEDGER = Path("/home/luna/crypto-genesis/shield-rewards/ledger.json")
SECRET_FILE = Path("/home/luna/crypto-genesis/aigen/.watch_secret")  # shared with /watch

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
SUPPORTED_CHAINS = {"base", "ethereum", "arbitrum", "optimism", "polygon", "bsc"}

# Pricing
FREE_QUOTA = 10           # first N attestations per agent_id are free
STANDARD_PRICE = 100      # AIGEN per attestation
PREMIUM_PRICE = 50        # for agents with >= PREMIUM_THRESHOLD contributions
PREMIUM_THRESHOLD = 5
STANDARD_VALIDITY = 30 * 86400   # seconds
PREMIUM_VALIDITY = 90 * 86400


def _load_secret() -> bytes:
    return SECRET_FILE.read_bytes()


_SECRET = _load_secret()


def load() -> dict:
    if ATTEST_FILE.exists():
        return json.loads(ATTEST_FILE.read_text())
    return {"attestations": [], "total": 0, "free_used_by_agent": {}}


def save(data: dict) -> None:
    ATTEST_FILE.write_text(json.dumps(data, indent=2))


def _ledger_load():
    return json.loads(LEDGER.read_text())


def _ledger_save(data):
    LEDGER.write_text(json.dumps(data, indent=2))


def _agent_balance(agent_id: str) -> int:
    return _ledger_load().get("agents", {}).get(agent_id, {}).get("balance", 0)


def _approved_contributions(agent_id: str) -> int:
    """Count approved contributions for premium tier check."""
    p = Path("/home/luna/crypto-genesis/aigen/contributions.json")
    if not p.exists():
        return 0
    d = json.loads(p.read_text())
    return sum(1 for s in d.get("submissions", [])
               if s.get("agent_id") == agent_id and s.get("status", "").startswith("approved"))


# ===== USDC PAID PREMIUM TIER (real-money revenue path) =====

USDC_PRICE_PER_ATTESTATION = 25_000_000  # $25 USDC (6 decimals)
USDC_PREMIUM_VALIDITY = 365 * 86400      # 1 year
TREASURY_WALLET = "0xDa429f2034b62b8722713873dE3C045eec390d8F"

USDC_CONTRACTS = {
    "base":     "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    "optimism": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
}

RPC_URLS = {
    "base":     "https://mainnet.base.org",
    "optimism": "https://mainnet.optimism.io",
}

PROCESSED_PAYMENTS_FILE = Path("/home/luna/crypto-genesis/aigen/processed_payments.json")


def _load_processed():
    if PROCESSED_PAYMENTS_FILE.exists():
        return set(json.loads(PROCESSED_PAYMENTS_FILE.read_text()))
    return set()


def _save_processed(s):
    PROCESSED_PAYMENTS_FILE.write_text(json.dumps(sorted(s)))


def verify_usdc_payment(payment_chain: str, tx_hash: str, expected_min_wei: int = USDC_PRICE_PER_ATTESTATION) -> dict:
    """Verify an on-chain USDC.transfer to the treasury wallet.

    Returns: { valid, amount, from, error? }
    """
    import urllib.request as _ureq
    if payment_chain not in RPC_URLS:
        return {"valid": False, "error": f"unsupported chain: {payment_chain}"}
    if not tx_hash.startswith("0x") or len(tx_hash) != 66:
        return {"valid": False, "error": "invalid tx hash"}
    if tx_hash.lower() in _load_processed():
        return {"valid": False, "error": "tx already processed (no double-spend)"}

    rpc = RPC_URLS[payment_chain]
    usdc_contract = USDC_CONTRACTS[payment_chain].lower()
    body = json.dumps({"jsonrpc":"2.0","id":1,"method":"eth_getTransactionReceipt","params":[tx_hash]}).encode()
    req = _ureq.Request(rpc, data=body, headers={
        "Content-Type": "application/json",
        "User-Agent": "curl/8.5.0",  # mainnet.base.org blocks default urllib UA
    })
    try:
        rsp = json.loads(_ureq.urlopen(req, timeout=10).read())
    except Exception as e:
        return {"valid": False, "error": f"rpc error: {e}"}
    receipt = rsp.get("result")
    if not receipt:
        return {"valid": False, "error": "tx not found / not yet mined"}
    if receipt.get("status") != "0x1":
        return {"valid": False, "error": "tx reverted"}

    # Look for ERC20 Transfer log: topic[0] = 0xddf25... topic[2] = treasury
    transfer_sig = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    treasury_topic = "0x" + "0"*24 + TREASURY_WALLET[2:].lower()
    total = 0
    sender = None
    for log in receipt.get("logs", []):
        if log.get("address","").lower() != usdc_contract:
            continue
        topics = log.get("topics", [])
        if len(topics) < 3 or topics[0].lower() != transfer_sig:
            continue
        if topics[2].lower() != treasury_topic:
            continue
        total += int(log.get("data","0x0"), 16)
        sender = "0x" + topics[1][-40:]
    if total < expected_min_wei:
        return {"valid": False, "error": f"insufficient USDC: got {total/1e6} USDC, need {expected_min_wei/1e6}"}
    return {"valid": True, "amount": total, "from": sender}


def issue_premium(agent_id: str, token: str, chain: str, score: int, flags: int, verdict: str,
                  payment_chain: str, payment_tx: str, custom_metadata: str = "") -> dict:
    """Issue a USDC-paid premium attestation. Verifies the on-chain USDC transfer first."""
    if not ADDRESS_RE.match(token or ""):
        return {"error": "token must be valid 0x address"}
    if chain not in SUPPORTED_CHAINS:
        return {"error": f"unsupported chain: {chain}"}

    payment = verify_usdc_payment(payment_chain, payment_tx)
    if not payment["valid"]:
        return {"error": payment["error"], "payment_status": "verification failed"}

    # Mark this tx hash as processed (no double-spend)
    processed = _load_processed()
    processed.add(payment_tx.lower())
    _save_processed(processed)

    now = int(time.time())
    att_id = "att_" + uuid.uuid4().hex[:12]
    body = {
        "schema": "aigen.attest.v1",
        "id": att_id,
        "token": token.lower(),
        "chain": chain,
        "score": int(score),
        "flags": int(flags),
        "verdict": verdict,
        "issued_at": now,
        "expires_at": now + USDC_PREMIUM_VALIDITY,
        "issuer": "aigen-attest.cryptogenesis.duckdns.org",
        "issued_to_agent": agent_id,
        "tier": "usdc-premium",
        "price_paid_aigen": 0,
        "price_paid_usdc": payment["amount"] / 1e6,
        "payment_tx": payment_tx,
        "payment_chain": payment_chain,
        "payment_from": payment["from"],
        "custom_metadata": (custom_metadata or "")[:500],
        "scan_url": f"https://cryptogenesis.duckdns.org/scan?address={token}&chain={chain}",
    }
    body["signature"] = _sign(body)

    data = load()
    data["attestations"].append(body)
    data["total"] = len(data["attestations"])
    save(data)
    return body


def _debit_aigen(agent_id: str, amount: int, reason: str) -> bool:
    """Debit AIGEN from agent's off-chain balance. Returns True on success."""
    if amount == 0:
        return True
    ledger = _ledger_load()
    a = ledger.setdefault("agents", {}).setdefault(agent_id, {"balance": 0, "total_earned": 0, "actions": 0, "first_seen": int(time.time())})
    if a["balance"] < amount:
        return False
    a["balance"] -= amount
    a["actions"] = a.get("actions", 0) + 1
    a["last_seen"] = int(time.time())
    a.setdefault("debits", []).append({"ts": int(time.time()), "amount": amount, "reason": reason})
    _ledger_save(ledger)
    return True


def quote(agent_id: str) -> dict:
    """Return the price the agent would pay for a new attestation."""
    data = load()
    free_used = data.get("free_used_by_agent", {}).get(agent_id, 0)
    contribs = _approved_contributions(agent_id)
    is_premium = contribs >= PREMIUM_THRESHOLD

    if free_used < FREE_QUOTA:
        price = 0
        validity = STANDARD_VALIDITY
        tier = "free-bootstrap"
        free_remaining = FREE_QUOTA - free_used
    elif is_premium:
        price = PREMIUM_PRICE
        validity = PREMIUM_VALIDITY
        tier = "premium"
        free_remaining = 0
    else:
        price = STANDARD_PRICE
        validity = STANDARD_VALIDITY
        tier = "standard"
        free_remaining = 0

    return {
        "agent_id": agent_id,
        "tier": tier,
        "price_aigen": price,
        "validity_days": validity // 86400,
        "free_quota_remaining": free_remaining,
        "approved_contributions": contribs,
        "current_balance_aigen": _agent_balance(agent_id),
        "premium_threshold_contribs": PREMIUM_THRESHOLD,
    }


def _sign(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SECRET, canonical, hashlib.sha256).hexdigest()


def issue(agent_id: str, token: str, chain: str, score: int, flags: int = 0, verdict: str = "?") -> dict:
    """Issue a signed attestation for a token. Debits AIGEN if applicable."""
    if not agent_id or len(agent_id.strip()) < 2:
        return {"error": "agent_id must be >= 2 chars"}
    if not ADDRESS_RE.match(token or ""):
        return {"error": "token must be valid 0x-prefixed 40-char hex"}
    if chain not in SUPPORTED_CHAINS:
        return {"error": f"unsupported chain: {chain}", "supported": sorted(SUPPORTED_CHAINS)}
    if not (0 <= int(score) <= 100):
        return {"error": "score must be 0-100"}

    q = quote(agent_id)
    price = q["price_aigen"]
    validity = q["validity_days"] * 86400
    tier = q["tier"]

    if price > 0 and not _debit_aigen(agent_id, price, f"attestation for {token} on {chain}"):
        return {
            "error": f"insufficient balance: need {price} AIGEN, have {q['current_balance_aigen']}",
            "earn_more": "Use /scan, /honeypot, /shield to earn AIGEN. Or complete a bounty.",
            "quote": q,
        }

    now = int(time.time())
    att_id = "att_" + uuid.uuid4().hex[:12]

    body = {
        "schema": "aigen.attest.v1",
        "id": att_id,
        "token": token.lower(),
        "chain": chain,
        "score": int(score),
        "flags": int(flags),
        "verdict": verdict,
        "issued_at": now,
        "expires_at": now + validity,
        "issuer": "aigen-attest.cryptogenesis.duckdns.org",
        "issued_to_agent": agent_id,
        "tier": tier,
        "price_paid_aigen": price,
        "scan_url": f"https://cryptogenesis.duckdns.org/scan?address={token}&chain={chain}",
    }
    body["signature"] = _sign(body)

    data = load()
    data["attestations"].append(body)
    data["total"] = len(data["attestations"])
    if tier == "free-bootstrap":
        data.setdefault("free_used_by_agent", {})[agent_id] = data["free_used_by_agent"].get(agent_id, 0) + 1
    save(data)

    return body


def get(att_id: str):
    data = load()
    for a in data["attestations"]:
        if a["id"] == att_id:
            return a
    return None


def list_for_token(token: str, chain: str = None):
    """Return non-expired attestations for a token."""
    now = int(time.time())
    data = load()
    out = []
    for a in data["attestations"]:
        if a["token"].lower() != token.lower():
            continue
        if chain and a["chain"] != chain:
            continue
        if a["expires_at"] < now:
            continue
        out.append(a)
    return out


def verify(payload: dict, signature: str) -> bool:
    """HMAC verify a payload. signature is the hex digest, payload should
    NOT include the signature field (or it will be stripped)."""
    body = {k: v for k, v in payload.items() if k != "signature"}
    expected = _sign(body)
    return hmac.compare_digest(expected, signature)


def public_key_fingerprint() -> str:
    return hashlib.sha256(_SECRET).hexdigest()


def stats() -> dict:
    data = load()
    now = int(time.time())
    active = [a for a in data["attestations"] if a["expires_at"] >= now]
    expired = [a for a in data["attestations"] if a["expires_at"] < now]
    paid = [a for a in data["attestations"] if a.get("price_paid_aigen", 0) > 0]
    free = [a for a in data["attestations"] if a.get("price_paid_aigen", 0) == 0]
    revenue = sum(a.get("price_paid_aigen", 0) for a in data["attestations"])
    return {
        "total": len(data["attestations"]),
        "active": len(active),
        "expired": len(expired),
        "paid": len(paid),
        "free_bootstrap": len(free),
        "lifetime_revenue_aigen": revenue,
        "agents_attested": len(set(a["issued_to_agent"] for a in data["attestations"])),
        "tokens_attested": len(set((a["token"], a["chain"]) for a in data["attestations"])),
    }
