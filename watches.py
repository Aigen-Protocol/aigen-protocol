"""AIGEN /watch — wallet monitoring with signed webhook alerts.

Storage layer: CRUD for watch entries, holdings diff, signed receipt generation.
The poller (watch_poller.py) and REST endpoints (scanner.py) call into here.
"""
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from pathlib import Path

WATCHES_FILE = Path("/home/luna/crypto-genesis/aigen/watches.json")
ALERTS_LOG = Path("/home/luna/crypto-genesis/aigen/alerts.jsonl")
SECRET_FILE = Path("/home/luna/crypto-genesis/aigen/.watch_secret")

SUPPORTED_CHAINS = {"base", "ethereum", "arbitrum", "optimism", "polygon", "bsc"}
TIERS = {
    "free":    {"poll_interval": 3600, "max_watches": 3, "max_tokens_tracked": 20},
    "premium": {"poll_interval": 600,  "max_watches": 25, "max_tokens_tracked": 100},
}

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
URL_RE = re.compile(r"^https?://[^\s]+$")

# Significant change thresholds (server defaults; per-watch overrides allowed)
DEFAULT_MIN_SCORE_DROP = 20
DEFAULT_RISKY_SCORE = 50


def _load_secret() -> bytes:
    """HMAC secret for signing webhook payloads. Generated once, reused."""
    if SECRET_FILE.exists():
        return SECRET_FILE.read_bytes()
    secret = os.urandom(32)
    SECRET_FILE.write_bytes(secret)
    SECRET_FILE.chmod(0o600)
    return secret


_SECRET = _load_secret()


def load() -> dict:
    if WATCHES_FILE.exists():
        return json.loads(WATCHES_FILE.read_text())
    return {"watches": [], "total": 0, "alerts_sent_total": 0}


def save(data: dict) -> None:
    WATCHES_FILE.write_text(json.dumps(data, indent=2))


# ===== Public API =====

def add_watch(agent_id, wallet, callback_url, chain="base", tier="free",
              min_score_drop=None, min_alert_score=None):
    """Register a new wallet watch. Returns the watch dict or {'error': ...}."""
    if not agent_id or len(agent_id.strip()) < 2:
        return {"error": "agent_id must be >= 2 chars"}
    if not ADDRESS_RE.match(wallet or ""):
        return {"error": "wallet must be a valid 0x-prefixed 40-char hex address"}
    if not URL_RE.match(callback_url or ""):
        return {"error": "callback_url must be a valid http(s):// URL"}
    if chain not in SUPPORTED_CHAINS:
        return {"error": f"unsupported chain: {chain}", "supported": sorted(SUPPORTED_CHAINS)}
    if tier not in TIERS:
        return {"error": f"unknown tier: {tier}", "available": sorted(TIERS)}

    data = load()

    # Per-agent quota
    agent_watches = [w for w in data["watches"] if w.get("agent_id") == agent_id and w.get("status") == "active"]
    if len(agent_watches) >= TIERS[tier]["max_watches"]:
        return {"error": f"agent already has {len(agent_watches)} active watches; tier {tier} max is {TIERS[tier]['max_watches']}"}

    # Idempotency: same agent + wallet + chain → return existing
    for w in agent_watches:
        if w.get("wallet", "").lower() == wallet.lower() and w.get("chain") == chain:
            return {"existing": True, **w}

    now = int(time.time())
    watch_id = str(uuid.uuid4())[:12]
    watch = {
        "id": watch_id,
        "agent_id": agent_id.strip(),
        "wallet": wallet.lower(),
        "chain": chain,
        "callback_url": callback_url,
        "tier": tier,
        "poll_interval": TIERS[tier]["poll_interval"],
        "max_tokens_tracked": TIERS[tier]["max_tokens_tracked"],
        "min_score_drop": int(min_score_drop) if min_score_drop is not None else DEFAULT_MIN_SCORE_DROP,
        "min_alert_score": int(min_alert_score) if min_alert_score is not None else DEFAULT_RISKY_SCORE,
        "status": "active",
        "created_at": now,
        "last_poll_at": 0,
        "next_poll_at": now,
        "consecutive_failures": 0,
        "alerts_sent": 0,
        "known_holdings": {},  # token_addr -> {"symbol","name","score","verdict","first_seen","last_score_at"}
    }
    data["watches"].append(watch)
    data["total"] += 1
    save(data)
    return watch


def get_watch(watch_id):
    data = load()
    for w in data["watches"]:
        if w["id"] == watch_id:
            return w
    return None


def remove_watch(watch_id, agent_id=None):
    """Mark watch as deleted. If agent_id provided, must match (auth check)."""
    data = load()
    for w in data["watches"]:
        if w["id"] == watch_id:
            if agent_id and w["agent_id"] != agent_id:
                return {"error": "agent_id mismatch"}
            w["status"] = "deleted"
            w["deleted_at"] = int(time.time())
            save(data)
            return {"deleted": True, "id": watch_id}
    return {"error": "not found"}


def list_watches(agent_id=None, include_deleted=False):
    data = load()
    out = []
    for w in data["watches"]:
        if not include_deleted and w.get("status") != "active":
            continue
        if agent_id and w.get("agent_id") != agent_id:
            continue
        out.append(w)
    return out


def watches_due_for_poll(now=None):
    """Active watches whose next_poll_at <= now."""
    now = now or int(time.time())
    data = load()
    return [w for w in data["watches"]
            if w.get("status") == "active" and w.get("next_poll_at", 0) <= now]


def update_after_poll(watch_id, new_holdings, alerts_count=0, error=None):
    """Update known_holdings + scheduling after a poll cycle.

    new_holdings: dict {token_addr -> {"symbol","name","score","verdict","decimals"}}
    """
    data = load()
    now = int(time.time())
    for w in data["watches"]:
        if w["id"] != watch_id:
            continue
        if error:
            w["consecutive_failures"] = w.get("consecutive_failures", 0) + 1
            w["last_error"] = error
            w["last_error_at"] = now
            # Exponential backoff on repeated failures (cap at 6h)
            backoff = min(w["poll_interval"] * (2 ** min(w["consecutive_failures"], 6)), 21600)
            w["next_poll_at"] = now + backoff
            if w["consecutive_failures"] >= 10:
                w["status"] = "suspended"
                w["suspended_reason"] = f"10+ consecutive poll failures: {error[:100]}"
        else:
            w["consecutive_failures"] = 0
            w.pop("last_error", None)
            # Merge new holdings into known
            kh = w.setdefault("known_holdings", {})
            for addr, info in new_holdings.items():
                addr_l = addr.lower()
                prev = kh.get(addr_l, {})
                kh[addr_l] = {
                    **prev,
                    **info,
                    "first_seen": prev.get("first_seen", now),
                    "last_score_at": now,
                }
            # Drop tokens no longer held
            for addr in list(kh.keys()):
                if addr not in {a.lower() for a in new_holdings}:
                    kh[addr]["last_seen_holding"] = kh[addr].get("last_seen_holding", now)
                    if now - kh[addr].get("last_score_at", 0) > 7 * 86400:
                        del kh[addr]
            w["last_poll_at"] = now
            w["next_poll_at"] = now + w["poll_interval"]
            w["alerts_sent"] = w.get("alerts_sent", 0) + alerts_count
        break

    if alerts_count:
        data["alerts_sent_total"] = data.get("alerts_sent_total", 0) + alerts_count
    save(data)


# ===== Alert generation =====

def diff_holdings(known, new_scan):
    """Compare known state vs fresh scan; produce alert events.

    known: {addr -> {"score","symbol",...}} from previous poll
    new_scan: {addr -> {"score","symbol","name","decimals","verdict","risks"}}

    Returns list of alert dicts (event, token, previous, current, delta, verdict, risks).
    """
    alerts = []
    for addr_raw, fresh in new_scan.items():
        addr = addr_raw.lower()
        new_score = fresh.get("score", 100)
        prev = known.get(addr, {})
        prev_score = prev.get("score")

        if prev_score is None:
            # New holding
            if new_score < DEFAULT_RISKY_SCORE:
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
            if delta <= -DEFAULT_MIN_SCORE_DROP:
                alerts.append({
                    "event": "score_drop",
                    "token": {"address": addr, "symbol": fresh.get("symbol"), "name": fresh.get("name")},
                    "previous_score": prev_score,
                    "current_score": new_score,
                    "delta": delta,
                    "verdict": fresh.get("verdict"),
                    "risks": fresh.get("risks", [])[:5],
                })
    return alerts


# ===== Signed webhook payload =====

def sign_payload(payload: dict) -> str:
    """HMAC-SHA256 signature over canonical JSON. Hex digest."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_SECRET, canonical, hashlib.sha256).hexdigest()


def build_webhook_envelope(watch, alert):
    """Build the full webhook payload, signed, ready to POST.

    The envelope contains: watch metadata, alert details, scan_url for verification,
    timestamp, signature. Agents can verify the signature with our public_key endpoint.
    """
    now = int(time.time())
    body = {
        "schema": "aigen.watch.v1",
        "watch_id": watch["id"],
        "agent_id": watch["agent_id"],
        "wallet": watch["wallet"],
        "chain": watch["chain"],
        "alert": alert,
        "scan_url": f"https://cryptogenesis.duckdns.org/scan?address={alert['token']['address']}&chain={watch['chain']}",
        "issued_at": now,
        "issuer": "aigen-watch.cryptogenesis.duckdns.org",
    }
    body["signature"] = sign_payload(body)
    return body


def verify_signature(payload: dict, signature: str) -> bool:
    """For self-verification / docs. Agents will call /watch/public-key + verify themselves."""
    expected = sign_payload({k: v for k, v in payload.items() if k != "signature"})
    return hmac.compare_digest(expected, signature)


def public_key_fingerprint() -> str:
    """SHA256 fingerprint of the HMAC secret (so agents can confirm they're verifying against the right server key)."""
    return hashlib.sha256(_SECRET).hexdigest()


def log_alert(watch_id, alert, delivery_status):
    """Append-only audit log of every alert sent."""
    entry = {
        "ts": int(time.time()),
        "watch_id": watch_id,
        "event": alert.get("event"),
        "token": alert.get("token", {}).get("address"),
        "previous_score": alert.get("previous_score"),
        "current_score": alert.get("current_score"),
        "delivery": delivery_status,
    }
    with ALERTS_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")
