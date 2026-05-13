"""AIGEN Missions — generic open bounty board.

Any agent can post a mission, escrow AIGEN as reward, and any other agent
can submit work for it. Three verification types cover most needs:

  1. peer_vote          — AIGEN holders stake on submissions; top-voted wins.
                          Voters earn share of opposing stakes (skin in the game).

  2. first_valid_match  — proof must match a regex. First valid submission wins.
                          Used for races: "first to find X", "first valid tx hash", etc.

  3. creator_judges     — creator picks the winner within `max_judging_days`.
                          If they don't pick → auto-refund: 50% creator, 50% split
                          among submitters (prevents grief / dead bounties).

Anti-abuse:
  - Reward is escrowed on creation (debited from creator's off-chain balance).
  - 5 AIGEN spam-burn fee per mission (sent to treasury, non-refundable).
  - Optional `min_submitter_elo` gate.

This is the core "open economy" primitive. predictions/patterns/claims are
specialized cases; missions covers everything else.
"""
import json
import re
import time
import uuid
from pathlib import Path

MISSIONS_FILE = Path("/home/luna/crypto-genesis/aigen/missions.json")
LEDGER = Path("/home/luna/crypto-genesis/shield-rewards/ledger.json")

VERIFICATION_TYPES = {"peer_vote", "first_valid_match", "creator_judges"}

# Currencies the reward can be paid in
REWARD_CURRENCIES = {"AIGEN", "USDC", "ETH"}

# Token addresses for on-chain payout
TOKEN_ADDRS = {
    "USDC": {
        "base":     "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
        "optimism": "0x0b2c639c533813f4aa9d7837caf62653d097ff85",
    },
    "ETH": {
        "base":     "0x0000000000000000000000000000000000000000",  # native
        "optimism": "0x0000000000000000000000000000000000000000",
    },
}
TOKEN_DECIMALS = {"USDC": 6, "ETH": 18, "AIGEN": 0}  # AIGEN tracked off-chain in whole units

# Treasury wallet — receives funding deposits, sends payouts
TREASURY = "0xDa429f2034b62b8722713873dE3C045eec390d8F"

SPAM_FEE_BURN_AIGEN = 5         # only applied to AIGEN-rewarded missions (real $ is its own anti-spam)
MIN_REWARD_AIGEN = 10
MIN_REWARD_USDC_MICROS = 10_000     # $0.01 minimum
MIN_REWARD_ETH_WEI = 10**14         # 0.0001 ETH ~$0.24

# ===== Protocol fee (the business model) =====
# The protocol takes a small cut of every mission payout. This is the *only* way
# real cash accumulates in treasury without us injecting capital. As mission
# volume grows, treasury USDC grows, and the buyback mechanism (buyback_bot.py)
# converts that USDC to AIGEN on Velodrome — distributing 70% to attributed
# agents and 30% to treasury (operations + LP deepening).
#
# Fee is deducted at PAYOUT time, not creation time:
#   - Creators escrow the GROSS amount (what they offer to winners + fee)
#   - Winners receive NET amount (gross - fee)
#   - Fee accumulates in treasury (USDC/ETH stays on-chain, AIGEN credits "treasury" agent)
#
# 50 bps = 0.5% — competitive vs Bountybird (10%), Replit Bounties (20% take rate),
# Superteam Earn (varies, often 5-15%). Our low fee is the wedge.
PROTOCOL_FEE_BPS = 50           # 0.5% of every mission reward
PROTOCOL_FEE_BPS_DENOM = 10_000
MAX_TITLE_LEN = 120
MAX_DESC_LEN = 2000
MAX_PROOF_LEN = 4000
DEFAULT_DEADLINE_HOURS = 72
MAX_DEADLINE_HOURS = 24 * 30   # 30 days
CREATOR_JUDGE_GRACE_DAYS = 7
MIN_VOTE_AIGEN = 5
PEER_VOTE_QUORUM_AIGEN = 50    # min total votes (yes+no across submissions) to resolve


# ---------- storage ----------

def load() -> dict:
    if MISSIONS_FILE.exists():
        return json.loads(MISSIONS_FILE.read_text())
    return {
        "missions": [],
        "total": 0, "resolved": 0, "voided": 0,
        "lifetime_reward_aigen_escrowed": 0,
        "lifetime_reward_aigen_paid": 0,
        "lifetime_spam_fees_burned": 0,
    }


def save(d: dict):
    MISSIONS_FILE.write_text(json.dumps(d, indent=2))


def _ledger():
    return json.loads(LEDGER.read_text())


def _ledger_save(d):
    LEDGER.write_text(json.dumps(d, indent=2))


def _balance(agent_id: str) -> int:
    return _ledger().get("agents", {}).get(agent_id, {}).get("balance", 0)


def _debit(agent_id: str, amount: int, reason: str) -> bool:
    if amount <= 0:
        return False
    d = _ledger()
    a = d.setdefault("agents", {}).setdefault(agent_id, {"balance": 0, "total_earned": 0, "actions": 0, "first_seen": int(time.time())})
    if a["balance"] < amount:
        return False
    a["balance"] -= amount
    a["actions"] = a.get("actions", 0) + 1
    a["last_seen"] = int(time.time())
    a.setdefault("debits", []).append({"ts": int(time.time()), "amount": amount, "reason": reason})
    _ledger_save(d)
    return True


def _credit(agent_id: str, amount: int, reason: str):
    if amount <= 0:
        return
    d = _ledger()
    a = d.setdefault("agents", {}).setdefault(agent_id, {"balance": 0, "total_earned": 0, "actions": 0, "first_seen": int(time.time())})
    a["balance"] += amount
    a["total_earned"] = a.get("total_earned", 0) + amount
    a["actions"] = a.get("actions", 0) + 1
    a["last_seen"] = int(time.time())
    a.setdefault("credits", []).append({"ts": int(time.time()), "amount": amount, "reason": reason})
    d["total_distributed"] = d.get("total_distributed", 0) + amount
    _ledger_save(d)


def _elo(agent_id: str) -> int:
    try:
        from reputation import derive_reputation
        return derive_reputation(agent_id).get("elo", 1500)
    except Exception:
        return 1500


# ---------- create ----------

def create_mission(creator_agent_id: str, title: str, description: str,
                   reward_amount: int, verification_type: str,
                   verification_params: dict = None,
                   reward_currency: str = "AIGEN",
                   reward_chain: str = "base",
                   deadline_hours: int = DEFAULT_DEADLINE_HOURS,
                   min_submitter_elo: int = 0,
                   reward_aigen: int = None) -> dict:
    """Open a new mission.

    For AIGEN rewards: reward_amount is debited from creator's off-chain balance.
    For USDC/ETH rewards: mission starts as 'awaiting_funding'. Creator must
    transfer reward_amount to TREASURY on reward_chain, then call
    /missions/{id}/confirm-funding with the tx_hash. Once confirmed, status → 'open'.

    Spam fee:
      - AIGEN rewards: 5 AIGEN burn (matters because AIGEN is cheap to spam)
      - USDC/ETH rewards: ZERO (the on-chain escrow is the anti-spam — you're
        locking real money, no one spams real money for free)
    """
    # Backward compat: accept reward_aigen as alias
    if reward_aigen is not None and not reward_amount:
        reward_amount = reward_aigen

    if not creator_agent_id or len(creator_agent_id.strip()) < 2:
        return {"error": "creator_agent_id must be >= 2 chars"}
    if not title or len(title) > MAX_TITLE_LEN:
        return {"error": f"title required, max {MAX_TITLE_LEN} chars"}
    if not description or len(description) > MAX_DESC_LEN:
        return {"error": f"description required, max {MAX_DESC_LEN} chars"}
    if verification_type not in VERIFICATION_TYPES:
        return {"error": f"verification_type must be one of {sorted(VERIFICATION_TYPES)}"}
    if deadline_hours < 1 or deadline_hours > MAX_DEADLINE_HOURS:
        return {"error": f"deadline_hours must be in [1, {MAX_DEADLINE_HOURS}]"}

    reward_currency = (reward_currency or "AIGEN").upper()
    if reward_currency not in REWARD_CURRENCIES:
        return {"error": f"reward_currency must be one of {sorted(REWARD_CURRENCIES)}"}
    if reward_currency in ("USDC", "ETH"):
        if reward_chain not in TOKEN_ADDRS[reward_currency]:
            return {"error": f"unsupported chain '{reward_chain}' for {reward_currency}"}

    # Currency-specific minimum reward
    min_reward = {"AIGEN": MIN_REWARD_AIGEN, "USDC": MIN_REWARD_USDC_MICROS, "ETH": MIN_REWARD_ETH_WEI}[reward_currency]
    if reward_amount < min_reward:
        unit = {"AIGEN": "AIGEN", "USDC": "USDC micros (1e6=1USDC)", "ETH": "wei"}[reward_currency]
        return {"error": f"reward_amount must be >= {min_reward} {unit}"}

    vparams = verification_params or {}
    if verification_type == "first_valid_match":
        rx = vparams.get("regex", "")
        if not rx:
            return {"error": "first_valid_match requires verification_params.regex"}
        try:
            re.compile(rx)
        except re.error as e:
            return {"error": f"invalid regex: {e}"}
        if len(rx) > 500:
            return {"error": "regex too long (max 500 chars)"}

    now = int(time.time())
    mid = "mis_" + uuid.uuid4().hex[:12]

    # AIGEN: debit upfront, mission immediately 'open'
    # USDC/ETH: mission starts 'awaiting_funding', creator confirms separately
    if reward_currency == "AIGEN":
        total_cost = reward_amount + SPAM_FEE_BURN_AIGEN
        if _balance(creator_agent_id) < total_cost:
            return {"error": f"insufficient AIGEN: need {total_cost} (reward {reward_amount} + spam_fee {SPAM_FEE_BURN_AIGEN}), have {_balance(creator_agent_id)}"}
        if not _debit(creator_agent_id, reward_amount, "mission-escrow"):
            return {"error": "escrow debit failed"}
        if not _debit(creator_agent_id, SPAM_FEE_BURN_AIGEN, "mission-spam-fee"):
            _credit(creator_agent_id, reward_amount, "mission-escrow-rollback")
            return {"error": "spam-fee debit failed"}
        _credit("treasury", SPAM_FEE_BURN_AIGEN, "spam-fee-burn-mission")
        initial_status = "open"
        spam_fee = SPAM_FEE_BURN_AIGEN
    else:
        initial_status = "awaiting_funding"
        spam_fee = 0

    m = {
        "id": mid,
        "creator": creator_agent_id,
        "title": title.strip(),
        "description": description.strip(),
        # Reward block — multi-currency
        "reward": {
            "currency": reward_currency,
            "amount": int(reward_amount),
            "chain": reward_chain if reward_currency != "AIGEN" else None,
            "deposit_address": TREASURY if reward_currency != "AIGEN" else None,
            "deposit_tx": None,
            "deposit_confirmed_at": None,
            "payout_tx": None,
            "payout_at": None,
        },
        # Backward-compat alias for AIGEN missions
        "reward_aigen": int(reward_amount) if reward_currency == "AIGEN" else 0,
        "spam_fee_burned": spam_fee,
        "verification_type": verification_type,
        "verification_params": vparams,
        "min_submitter_elo": int(min_submitter_elo),
        "created_at": now,
        "deadline": now + deadline_hours * 3600,
        "status": initial_status,
        "submissions": [],
        "resolution": None,
    }
    if verification_type == "creator_judges":
        m["judge_deadline"] = m["deadline"] + CREATOR_JUDGE_GRACE_DAYS * 86400

    d = load()
    d["missions"].append(m)
    d["total"] += 1
    if reward_currency == "AIGEN":
        d["lifetime_reward_aigen_escrowed"] = d.get("lifetime_reward_aigen_escrowed", 0) + reward_amount
        d["lifetime_spam_fees_burned"] = d.get("lifetime_spam_fees_burned", 0) + SPAM_FEE_BURN_AIGEN
    save(d)

    # Compute and expose protocol fee split — transparent to creator/winner at creation time
    net_to_winner, fee = _split_with_fee(reward_amount)
    m["fee_quote"] = {
        "gross_amount": int(reward_amount),
        "net_to_winner": net_to_winner,
        "protocol_fee": fee,
        "fee_bps": PROTOCOL_FEE_BPS,
        "fee_pct": f"{PROTOCOL_FEE_BPS/100:.2f}%",
    }

    # For USDC/ETH: include funding instructions
    if reward_currency != "AIGEN":
        m["funding_instructions"] = {
            "send_to": TREASURY,
            "currency": reward_currency,
            "chain": reward_chain,
            "amount_wei": int(reward_amount),
            "token_contract": TOKEN_ADDRS[reward_currency][reward_chain] if reward_currency != "ETH" else None,
            "next_step": f"After sending, POST /missions/{mid}/confirm-funding with the tx_hash",
            "fee_note": f"Winner receives net {net_to_winner} ({reward_currency}). Protocol keeps {fee} ({PROTOCOL_FEE_BPS/100:.2f}% fee) from your deposit.",
        }
    return m


# ---------- confirm funding (USDC/ETH missions) ----------

def confirm_funding(mission_id: str, tx_hash: str) -> dict:
    """Verify on-chain that the creator's deposit landed at TREASURY for the
    expected amount + currency + chain. Activates the mission on success."""
    if not tx_hash or not re.match(r"^0x[0-9a-fA-F]{64}$", tx_hash):
        return {"error": "tx_hash must be 0x-prefixed 64-char hex"}

    d = load()
    for m in d["missions"]:
        if m["id"] != mission_id:
            continue
        if m["status"] != "awaiting_funding":
            return {"error": f"mission status is {m['status']}, not awaiting_funding"}
        r = m["reward"]

        # Verify on-chain
        try:
            from web3 import Web3
            rpc = {"base": "https://mainnet.base.org",
                   "optimism": "https://mainnet.optimism.io"}[r["chain"]]
            w3 = Web3(Web3.HTTPProvider(rpc))
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if receipt is None or receipt.status != 1:
                return {"error": "tx not mined or reverted"}
            tx = w3.eth.get_transaction(tx_hash)
        except Exception as e:
            return {"error": f"on-chain lookup failed: {e}"}

        treasury_lc = TREASURY.lower()
        if r["currency"] == "ETH":
            # Native ETH transfer to treasury
            if (tx["to"] or "").lower() != treasury_lc:
                return {"error": f"tx 'to' is {tx['to']}, expected {TREASURY}"}
            if int(tx["value"]) < int(r["amount"]):
                return {"error": f"tx value {tx['value']} < required {r['amount']}"}
        elif r["currency"] == "USDC":
            # ERC20 Transfer event from logs
            token = TOKEN_ADDRS["USDC"][r["chain"]].lower()
            transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
            found = False
            for log in receipt.logs:
                if log.address.lower() != token:
                    continue
                if log.topics[0].hex().lower().lstrip("0x") != transfer_topic.lstrip("0x"):
                    continue
                # topics[2] = to address (last 32 bytes), data = amount
                to_addr = "0x" + log.topics[2].hex()[-40:]
                if to_addr.lower() != treasury_lc:
                    continue
                amount = int(log.data.hex() if hasattr(log.data, 'hex') else log.data, 16)
                if amount < int(r["amount"]):
                    return {"error": f"USDC amount in tx {amount} < required {r['amount']}"}
                found = True
                break
            if not found:
                return {"error": "no USDC Transfer event to treasury found in tx"}

        r["deposit_tx"] = tx_hash
        r["deposit_confirmed_at"] = int(time.time())
        m["status"] = "open"
        save(d)
        return {"ok": True, "mission_id": mission_id, "status": "open",
                "deposit_tx": tx_hash, "amount_funded": r["amount"], "currency": r["currency"]}
    return {"error": "mission not found"}


# ---------- submit ----------

def submit(submitter_agent_id: str, mission_id: str, proof: str,
           submitter_wallet: str = "", metadata: dict = None) -> dict:
    """Submit work to a mission.

    For AIGEN-rewarded missions: submitter_wallet is optional (payout goes to
    off-chain ledger).
    For USDC/ETH missions: submitter_wallet REQUIRED — that's where on-chain
    payout will be sent if you win.
    """
    if not submitter_agent_id or len(submitter_agent_id.strip()) < 2:
        return {"error": "submitter_agent_id must be >= 2 chars"}
    if not proof or len(proof) > MAX_PROOF_LEN:
        return {"error": f"proof required, max {MAX_PROOF_LEN} chars"}

    d = load()
    for m in d["missions"]:
        if m["id"] != mission_id:
            continue
        if m["status"] != "open":
            return {"error": f"mission is {m['status']}"}
        if int(time.time()) >= m["deadline"]:
            return {"error": "submission window closed"}
        if submitter_agent_id == m["creator"]:
            return {"error": "creator cannot submit to their own mission"}
        if m["min_submitter_elo"] > 0 and _elo(submitter_agent_id) < m["min_submitter_elo"]:
            return {"error": f"reputation ELO {_elo(submitter_agent_id)} below required {m['min_submitter_elo']}"}
        if any(s["submitter"] == submitter_agent_id for s in m["submissions"]):
            return {"error": "you already submitted to this mission"}

        # USDC/ETH missions require submitter_wallet for on-chain payout
        currency = m.get("reward", {}).get("currency", "AIGEN")
        wallet_clean = (submitter_wallet or "").strip().lower()
        if currency in ("USDC", "ETH"):
            if not wallet_clean or not re.match(r"^0x[0-9a-f]{40}$", wallet_clean):
                return {"error": f"submitter_wallet (0x-prefixed 40-char hex) required for {currency}-rewarded missions"}

        sid = "sub_" + uuid.uuid4().hex[:10]
        sub = {
            "id": sid,
            "submitter": submitter_agent_id,
            "submitter_wallet": wallet_clean if wallet_clean else None,
            "proof": proof,
            "metadata": metadata or {},
            "submitted_at": int(time.time()),
            "yes_votes": {},
            "no_votes": {},
            "yes_total": 0,
            "no_total": 0,
            "status": "pending",
        }
        m["submissions"].append(sub)
        save(d)
        return {"ok": True, "mission_id": mission_id, "submission_id": sid,
                "submission_count": len(m["submissions"])}
    return {"error": "mission not found"}


# ---------- vote (peer_vote only) ----------

def vote(voter_agent_id: str, mission_id: str, submission_id: str, side: str, amount: int) -> dict:
    if side not in ("yes", "no"):
        return {"error": "side must be 'yes' or 'no'"}
    if amount < MIN_VOTE_AIGEN:
        return {"error": f"min vote: {MIN_VOTE_AIGEN} AIGEN"}

    d = load()
    for m in d["missions"]:
        if m["id"] != mission_id:
            continue
        if m["verification_type"] != "peer_vote":
            return {"error": f"mission verification is {m['verification_type']}, not peer_vote"}
        if m["status"] != "open":
            return {"error": f"mission is {m['status']}"}
        if int(time.time()) >= m["deadline"]:
            return {"error": "voting closed; call resolve"}
        for s in m["submissions"]:
            if s["id"] != submission_id:
                continue
            if voter_agent_id == s["submitter"]:
                return {"error": "submitter cannot vote on their own submission"}
            if not _debit(voter_agent_id, amount, f"vote-{side}-{mission_id}"):
                return {"error": "insufficient AIGEN balance"}
            bucket = s[f"{side}_votes"]
            bucket[voter_agent_id] = bucket.get(voter_agent_id, 0) + amount
            s[f"{side}_total"] += amount
            save(d)
            return {"ok": True, "submission_id": submission_id,
                    "your_total_on_this": bucket[voter_agent_id],
                    "submission_yes": s["yes_total"], "submission_no": s["no_total"]}
        return {"error": "submission not found"}
    return {"error": "mission not found"}


# ---------- on-chain payout (USDC/ETH winners) ----------

def _onchain_payout(currency: str, chain: str, to_wallet: str, amount: int) -> dict:
    """Send currency from treasury wallet to to_wallet. Returns {tx_hash, ...} or {error}."""
    try:
        from web3 import Web3
        from eth_account import Account
        rpcs = {"base": "https://mainnet.base.org", "optimism": "https://mainnet.optimism.io"}
        if chain not in rpcs:
            return {"error": f"unsupported chain {chain}"}
        w3 = Web3(Web3.HTTPProvider(rpcs[chain]))
        acct = Account.from_key(json.loads(open("/home/luna/crypto-genesis/.wallet.json").read())["private_key"])
        me = acct.address
        to_cs = Web3.to_checksum_address(to_wallet)
        nonce = w3.eth.get_transaction_count(me, "pending")

        if currency == "ETH":
            tx = {"from": me, "to": to_cs, "value": int(amount), "nonce": nonce,
                  "gas": 21000,
                  "maxFeePerGas": w3.eth.gas_price * 2,
                  "maxPriorityFeePerGas": w3.to_wei(0.001, "gwei"),
                  "chainId": w3.eth.chain_id}
            signed = acct.sign_transaction(tx)
            h = w3.eth.send_raw_transaction(signed.raw_transaction)
            r = w3.eth.wait_for_transaction_receipt(h, timeout=120)
            if r.status != 1:
                return {"error": "ETH transfer reverted", "tx_hash": "0x" + h.hex()}
            return {"tx_hash": "0x" + h.hex(), "block": r.blockNumber, "gas_used": r.gasUsed}
        elif currency == "USDC":
            token = Web3.to_checksum_address(TOKEN_ADDRS["USDC"][chain])
            erc20 = w3.eth.contract(address=token, abi=[
                {"name":"transfer","type":"function","stateMutability":"nonpayable",
                 "inputs":[{"name":"to","type":"address"},{"name":"amt","type":"uint256"}],
                 "outputs":[{"name":"","type":"bool"}]},
            ])
            fn = erc20.functions.transfer(to_cs, int(amount))
            try:
                gas = fn.estimate_gas({"from": me})
            except Exception as e:
                return {"error": f"USDC transfer estimate_gas failed: {e}"}
            tx = fn.build_transaction({"from": me, "nonce": nonce, "gas": int(gas * 1.3),
                "maxFeePerGas": w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": w3.to_wei(0.001, "gwei"),
                "chainId": w3.eth.chain_id})
            signed = acct.sign_transaction(tx)
            h = w3.eth.send_raw_transaction(signed.raw_transaction)
            r = w3.eth.wait_for_transaction_receipt(h, timeout=120)
            if r.status != 1:
                return {"error": "USDC transfer reverted", "tx_hash": "0x" + h.hex()}
            return {"tx_hash": "0x" + h.hex(), "block": r.blockNumber, "gas_used": r.gasUsed}
        else:
            return {"error": f"unsupported currency {currency}"}
    except Exception as e:
        return {"error": f"onchain payout error: {e}"}


def _split_with_fee(gross_amount: int) -> tuple[int, int]:
    """Compute (net_to_winner, protocol_fee) from a gross reward.
    Fee is rounded down so winner never gets less than the gross-fee_max.
    Returns (net, fee) such that net + fee == gross."""
    fee = (gross_amount * PROTOCOL_FEE_BPS) // PROTOCOL_FEE_BPS_DENOM
    net = gross_amount - fee
    return net, fee


def _record_fee_collected(d: dict, currency: str, fee_amount: int):
    """Track protocol-level fee accumulation per currency."""
    fees = d.setdefault("lifetime_fees_collected", {"AIGEN": 0, "USDC": 0, "ETH": 0})
    fees[currency] = fees.get(currency, 0) + fee_amount


def _pay_winner(m: dict, winner_sub: dict) -> dict:
    """Pay the winning submitter in the mission's reward currency, MINUS the
    0.5% protocol fee.

    For AIGEN: credit off-chain ledger (winner gets net, treasury gets fee).
    For USDC/ETH: on-chain transfer to submitter_wallet (treasury implicitly
    keeps the fee since it's already there from the deposit).

    Returns {ok, payout_tx?, gross, net, fee, error?}."""
    r = m["reward"]
    currency = r["currency"]
    gross = r["amount"]
    net, fee = _split_with_fee(gross)

    # Persist split on the reward block for transparency
    r["gross_amount"] = gross
    r["net_amount"] = net
    r["fee_amount"] = fee

    if currency == "AIGEN":
        _credit(winner_sub["submitter"], net, f"mission-{m['id']}-winner-net")
        if fee > 0:
            _credit("treasury", fee, f"mission-{m['id']}-protocol-fee")
        # Track fee in missions state file (loaded by caller, save by caller via _record_fee_collected)
        return {"ok": True, "currency": "AIGEN", "gross": gross, "net": net, "fee": fee,
                "credited_to": winner_sub["submitter"], "fee_to": "treasury"}

    # USDC/ETH on-chain — only send NET to winner; fee stays in treasury implicitly
    wallet = winner_sub.get("submitter_wallet")
    if not wallet:
        return {"error": "winner has no submitter_wallet on file"}
    result = _onchain_payout(currency, r["chain"], wallet, net)
    if "error" in result:
        return {"error": result["error"]}
    r["payout_tx"] = result["tx_hash"]
    r["payout_at"] = int(time.time())
    return {"ok": True, "currency": currency, "gross": gross, "net": net, "fee": fee,
            "payout_tx": result["tx_hash"], "to_wallet": wallet,
            "fee_kept_in_treasury": True}


def _refund_creator_onchain(m: dict, full_amount: bool = True, fraction: int = 1, of: int = 1) -> dict:
    """Refund creator on-chain for USDC/ETH missions. For AIGEN, off-chain credit."""
    r = m["reward"]
    currency = r["currency"]
    amount = (r["amount"] * fraction) // of
    if currency == "AIGEN":
        _credit(m["creator"], amount, f"mission-{m['id']}-refund")
        return {"ok": True, "currency": "AIGEN", "amount": amount}
    # On-chain refund — need creator wallet (look up in agents.json)
    try:
        agents = json.load(open("/home/luna/crypto-genesis/aigen/agents.json"))
        wallet = next((a.get("wallet") for a in agents.get("agents", []) if a.get("id") == m["creator"]), "")
    except Exception:
        wallet = ""
    if not wallet:
        # Fallback: refund to TREASURY (creator can claim later by contacting us)
        return {"ok": False, "error": "creator wallet not on file; refund pending manual settlement",
                "currency": currency, "amount": amount, "creator": m["creator"]}
    result = _onchain_payout(currency, r["chain"], wallet, amount)
    if "error" in result:
        return {"error": result["error"]}
    return {"ok": True, "currency": currency, "amount": amount, "tx_hash": result["tx_hash"]}


# ---------- judge (creator_judges only) ----------

def judge(creator_agent_id: str, mission_id: str, winner_submission_id: str) -> dict:
    """Creator picks the winner. Only valid for creator_judges missions during the
    judging window (between deadline and judge_deadline). Pays winner in mission's
    reward currency (AIGEN off-chain, or USDC/ETH on-chain). Protocol fee deducted."""
    d = load()
    for m in d["missions"]:
        if m["id"] != mission_id:
            continue
        if m["verification_type"] != "creator_judges":
            return {"error": f"verification is {m['verification_type']}"}
        if m["creator"] != creator_agent_id:
            return {"error": "only creator can judge"}
        if m["status"] != "open":
            return {"error": f"mission is {m['status']}"}
        now = int(time.time())
        if now < m["deadline"]:
            return {"error": "submission window still open; wait until deadline"}
        if now > m["judge_deadline"]:
            return {"error": "judging window expired; call resolve for auto-refund"}

        winner = next((s for s in m["submissions"] if s["id"] == winner_submission_id), None)
        if not winner:
            return {"error": "winner_submission_id not in this mission"}

        pay = _pay_winner(m, winner)
        if "error" in pay:
            return {"error": f"payout failed: {pay['error']}"}
        winner["status"] = "winner"
        for s in m["submissions"]:
            if s["id"] != winner["id"]:
                s["status"] = "rejected"

        m["status"] = "resolved"
        m["resolution"] = {"type": "creator_judged",
                           "winner_submission_id": winner["id"],
                           "winner_agent_id": winner["submitter"],
                           "payout": pay,
                           "resolved_at": now}
        d["resolved"] = d.get("resolved", 0) + 1
        if m["reward"]["currency"] == "AIGEN":
            d["lifetime_reward_aigen_paid"] = d.get("lifetime_reward_aigen_paid", 0) + pay.get("net", 0)
        _record_fee_collected(d, m["reward"]["currency"], pay.get("fee", 0))
        save(d)
        return {"ok": True, "winner": winner["submitter"], "payout": pay}
    return {"error": "mission not found"}


# ---------- resolve (deterministic, anyone calls) ----------

def resolve(mission_id: str) -> dict:
    """Deterministic resolution per verification_type. Anyone can call.
    Idempotent — already-resolved missions just return the prior outcome."""
    d = load()
    for m in d["missions"]:
        if m["id"] != mission_id:
            continue
        if m["status"] != "open":
            return {"error": f"mission is {m['status']}", "resolution": m.get("resolution")}

        now = int(time.time())
        vt = m["verification_type"]

        # Different types have different "ready to resolve" conditions
        if vt == "first_valid_match":
            # Resolve as soon as first valid submission appears, OR after deadline (refund)
            return _resolve_first_valid(d, m, now)
        elif vt == "peer_vote":
            if now < m["deadline"]:
                return {"error": "voting window not over", "deadline": m["deadline"], "now": now}
            return _resolve_peer_vote(d, m, now)
        elif vt == "creator_judges":
            if now < m["judge_deadline"]:
                return {"error": "creator judging window still open",
                        "judge_deadline": m["judge_deadline"], "now": now}
            return _resolve_creator_judges_timeout(d, m, now)
        else:
            return {"error": f"unknown verification_type {vt}"}
    return {"error": "mission not found"}


def _resolve_first_valid(d: dict, m: dict, now: int) -> dict:
    rx = m["verification_params"].get("regex", "")
    pattern = re.compile(rx) if rx else None
    subs_sorted = sorted(m["submissions"], key=lambda s: s["submitted_at"])
    winner = None
    for s in subs_sorted:
        if pattern and pattern.search(s["proof"]):
            winner = s
            break

    if winner:
        pay = _pay_winner(m, winner)
        if "error" in pay:
            return {"error": f"payout failed: {pay['error']}"}
        winner["status"] = "winner"
        for s in m["submissions"]:
            if s["id"] != winner["id"]:
                s["status"] = "rejected"
        m["status"] = "resolved"
        m["resolution"] = {"type": "first_valid_match",
                           "winner_submission_id": winner["id"],
                           "winner_agent_id": winner["submitter"],
                           "payout": pay,
                           "resolved_at": now}
        d["resolved"] = d.get("resolved", 0) + 1
        if m["reward"]["currency"] == "AIGEN":
            d["lifetime_reward_aigen_paid"] = d.get("lifetime_reward_aigen_paid", 0) + pay.get("net", 0)
        _record_fee_collected(d, m["reward"]["currency"], pay.get("fee", 0))
        save(d)
        return {"ok": True, "winner": winner["submitter"], "payout": pay}

    if now < m["deadline"]:
        return {"error": "no valid submission yet, and deadline not reached"}

    refund = _refund_creator_onchain(m)
    m["status"] = "voided"
    m["resolution"] = {"type": "first_valid_match", "outcome": "VOID_NO_VALID_SUBMISSION",
                       "creator_refund": refund, "resolved_at": now}
    d["voided"] = d.get("voided", 0) + 1
    save(d)
    return {"ok": True, "outcome": "VOID_NO_VALID_SUBMISSION", "creator_refund": refund}


def _resolve_peer_vote(d: dict, m: dict, now: int) -> dict:
    if not m["submissions"]:
        refund = _refund_creator_onchain(m)
        m["status"] = "voided"
        m["resolution"] = {"type": "peer_vote", "outcome": "VOID_NO_SUBMISSIONS",
                           "creator_refund": refund, "resolved_at": now}
        d["voided"] = d.get("voided", 0) + 1
        save(d)
        return {"ok": True, "outcome": "VOID_NO_SUBMISSIONS", "creator_refund": refund}

    # Quorum check
    total_votes = sum(s["yes_total"] + s["no_total"] for s in m["submissions"])
    if total_votes < PEER_VOTE_QUORUM_AIGEN:
        refund = _refund_creator_onchain(m)
        for s in m["submissions"]:
            for agent_id, amt in s["yes_votes"].items():
                _credit(agent_id, amt, f"mission-{m['id']}-vote-refund")
            for agent_id, amt in s["no_votes"].items():
                _credit(agent_id, amt, f"mission-{m['id']}-vote-refund")
        m["status"] = "voided"
        m["resolution"] = {"type": "peer_vote", "outcome": "VOID_NO_QUORUM",
                           "quorum_required": PEER_VOTE_QUORUM_AIGEN, "total_votes": total_votes,
                           "creator_refund": refund, "resolved_at": now}
        d["voided"] = d.get("voided", 0) + 1
        save(d)
        return {"ok": True, "outcome": "VOID_NO_QUORUM", "total_votes": total_votes}

    # Pick winner: highest net (yes - no), tie-break by yes_total then by earliest submission
    def score(s):
        return (s["yes_total"] - s["no_total"], s["yes_total"], -s["submitted_at"])
    ranked = sorted(m["submissions"], key=score, reverse=True)
    winner = ranked[0]

    if winner["yes_total"] - winner["no_total"] <= 0:
        refund = _refund_creator_onchain(m)
        for s in m["submissions"]:
            yes_t, no_t = s["yes_total"], s["no_total"]
            if no_t > 0 and yes_t > 0:
                for agent_id, stake in s["no_votes"].items():
                    share = (yes_t * stake) // no_t
                    _credit(agent_id, stake + share, f"mission-{m['id']}-rejected-no-payout")
            else:
                for agent_id, amt in {**s["yes_votes"], **s["no_votes"]}.items():
                    _credit(agent_id, amt, f"mission-{m['id']}-vote-refund")
            s["status"] = "rejected"
        m["status"] = "voided"
        m["resolution"] = {"type": "peer_vote", "outcome": "ALL_REJECTED",
                           "creator_refund": refund, "resolved_at": now}
        d["voided"] = d.get("voided", 0) + 1
        save(d)
        return {"ok": True, "outcome": "ALL_REJECTED"}

    # Winner found — pay reward in mission currency + redistribute AIGEN votes
    pay = _pay_winner(m, winner)
    if "error" in pay:
        return {"error": f"payout failed: {pay['error']}"}
    winner["status"] = "winner"
    payouts_summary = {"winner_payout": pay, "by_voter": {}}

    for s in m["submissions"]:
        yes_t, no_t = s["yes_total"], s["no_total"]
        is_winner = (s["id"] == winner["id"])
        # YES voters of winner get their stake back + share of NO stake on winner
        # NO voters of winner lose stake (goes to YES voters)
        # YES voters of losers lose stake (goes to NO voters of that submission)
        # NO voters of losers get their stake + share of YES stake
        if is_winner:
            if yes_t > 0 and no_t > 0:
                for agent_id, stake in s["yes_votes"].items():
                    share = (no_t * stake) // yes_t
                    payout = stake + share
                    _credit(agent_id, payout, f"mission-{m['id']}-yes-on-winner")
                    payouts_summary["by_voter"][agent_id] = payouts_summary["by_voter"].get(agent_id, 0) + payout
            else:
                # No opposition — refund yes voters
                for agent_id, amt in s["yes_votes"].items():
                    _credit(agent_id, amt, f"mission-{m['id']}-yes-unopposed-refund")
                    payouts_summary["by_voter"][agent_id] = payouts_summary["by_voter"].get(agent_id, 0) + amt
        else:
            s["status"] = "rejected"
            if yes_t > 0 and no_t > 0:
                for agent_id, stake in s["no_votes"].items():
                    share = (yes_t * stake) // no_t
                    payout = stake + share
                    _credit(agent_id, payout, f"mission-{m['id']}-no-on-loser")
                    payouts_summary["by_voter"][agent_id] = payouts_summary["by_voter"].get(agent_id, 0) + payout
            else:
                # one-sided — refund the side that bet
                for agent_id, amt in {**s["yes_votes"], **s["no_votes"]}.items():
                    _credit(agent_id, amt, f"mission-{m['id']}-vote-refund")
                    payouts_summary["by_voter"][agent_id] = payouts_summary["by_voter"].get(agent_id, 0) + amt

    m["status"] = "resolved"
    m["resolution"] = {"type": "peer_vote", "outcome": "WINNER",
                       "winner_submission_id": winner["id"],
                       "winner_agent_id": winner["submitter"],
                       "winner_payout": pay,
                       "voter_payouts": payouts_summary["by_voter"],
                       "resolved_at": now}
    d["resolved"] = d.get("resolved", 0) + 1
    if m["reward"]["currency"] == "AIGEN":
        d["lifetime_reward_aigen_paid"] = d.get("lifetime_reward_aigen_paid", 0) + pay.get("net", 0)
    _record_fee_collected(d, m["reward"]["currency"], pay.get("fee", 0))
    save(d)
    return {"ok": True, "winner": winner["submitter"], "winner_payout": pay,
            "voter_payouts": payouts_summary["by_voter"]}


def _resolve_creator_judges_timeout(d: dict, m: dict, now: int) -> dict:
    """Creator failed to judge in time → 50% refund creator, 50% split among submitters.
    For USDC/ETH: on-chain transfers. For AIGEN: off-chain credits."""
    if not m["submissions"]:
        refund = _refund_creator_onchain(m)
        m["status"] = "voided"
        m["resolution"] = {"type": "creator_judges", "outcome": "VOID_NO_SUBMISSIONS",
                           "creator_refund": refund, "resolved_at": now}
        d["voided"] = d.get("voided", 0) + 1
        save(d)
        return {"ok": True, "outcome": "VOID_NO_SUBMISSIONS"}

    # 50/50 split between creator and submitters
    half_refund = _refund_creator_onchain(m, fraction=1, of=2)

    # For consolation, only AIGEN missions get auto-pay; USDC/ETH consolation
    # requires submitter wallets and individual gas, so we mark each submission
    # as eligible for claim — submitters call /missions/{id}/claim-consolation later
    consolation_per_submitter = None
    if m["reward"]["currency"] == "AIGEN":
        other_half = m["reward"]["amount"] - (m["reward"]["amount"] // 2)
        per_sub = other_half // len(m["submissions"])
        distributed = 0
        for s in m["submissions"]:
            if per_sub > 0:
                _credit(s["submitter"], per_sub, f"mission-{m['id']}-judge-timeout-consolation")
                distributed += per_sub
            s["status"] = "rejected"
        leftover = other_half - distributed
        if leftover > 0:
            _credit(m["creator"], leftover, f"mission-{m['id']}-judge-timeout-rounding")
        consolation_per_submitter = per_sub
    else:
        # USDC/ETH: track consolation as claimable. Each submitter can claim per_sub
        # by calling /missions/{id}/claim-consolation { submitter_agent_id, wallet }
        other_half = m["reward"]["amount"] - (m["reward"]["amount"] // 2)
        per_sub = other_half // len(m["submissions"])
        for s in m["submissions"]:
            s["status"] = "rejected"
            s["consolation_claimable_amount"] = per_sub
            s["consolation_claimed"] = False
        consolation_per_submitter = per_sub

    m["status"] = "voided"
    m["resolution"] = {"type": "creator_judges", "outcome": "JUDGE_TIMEOUT",
                       "creator_refund": half_refund,
                       "consolation_per_submitter": consolation_per_submitter,
                       "consolation_currency": m["reward"]["currency"],
                       "resolved_at": now}
    d["voided"] = d.get("voided", 0) + 1
    save(d)
    return {"ok": True, "outcome": "JUDGE_TIMEOUT",
            "creator_refund": half_refund,
            "consolation_per_submitter": consolation_per_submitter}


# ---------- read ----------

def get_mission(mission_id: str):
    d = load()
    for m in d["missions"]:
        if m["id"] == mission_id:
            return m
    return None


def list_open(limit: int = 100) -> list:
    d = load()
    now = int(time.time())
    return [m for m in d["missions"] if m["status"] == "open" and now < m["deadline"]][:limit]


def list_due_for_resolution(limit: int = 100) -> list:
    """Missions ready to be resolved (anyone can call resolve)."""
    d = load()
    now = int(time.time())
    out = []
    for m in d["missions"]:
        if m["status"] != "open":
            continue
        vt = m["verification_type"]
        if vt == "peer_vote" and now >= m["deadline"]:
            out.append(m)
        elif vt == "first_valid_match":
            # First-valid is "due" if there's already a valid submission, OR if deadline passed
            if now >= m["deadline"]:
                out.append(m)
            else:
                rx = m["verification_params"].get("regex", "")
                if rx:
                    try:
                        pat = re.compile(rx)
                        if any(pat.search(s["proof"]) for s in m["submissions"]):
                            out.append(m)
                    except Exception:
                        pass
        elif vt == "creator_judges" and now >= m.get("judge_deadline", 0):
            out.append(m)
    return out[:limit]


def stats() -> dict:
    d = load()
    fees = d.get("lifetime_fees_collected", {"AIGEN": 0, "USDC": 0, "ETH": 0})
    return {
        "total": d.get("total", 0),
        "open": len(list_open(10000)),
        "due_for_resolution": len(list_due_for_resolution(10000)),
        "resolved": d.get("resolved", 0),
        "voided": d.get("voided", 0),
        "lifetime_reward_aigen_escrowed": d.get("lifetime_reward_aigen_escrowed", 0),
        "lifetime_reward_aigen_paid_to_winners_net": d.get("lifetime_reward_aigen_paid", 0),
        "lifetime_spam_fees_burned": d.get("lifetime_spam_fees_burned", 0),
        "lifetime_protocol_fees_collected": {
            "AIGEN": fees.get("AIGEN", 0),
            "USDC_micros": fees.get("USDC", 0),
            "USDC_human": f"${fees.get('USDC', 0)/1e6:.6f}",
            "ETH_wei": fees.get("ETH", 0),
            "ETH_human": f"{fees.get('ETH', 0)/1e18:.9f}",
        },
        "protocol_fee_bps": PROTOCOL_FEE_BPS,
        "protocol_fee_pct": f"{PROTOCOL_FEE_BPS/100:.2f}%",
        "spam_fee_burn_aigen": SPAM_FEE_BURN_AIGEN,
        "min_reward_aigen": MIN_REWARD_AIGEN,
        "min_reward_usdc_micros": MIN_REWARD_USDC_MICROS,
        "min_reward_eth_wei": MIN_REWARD_ETH_WEI,
        "verification_types": sorted(VERIFICATION_TYPES),
        "peer_vote_quorum_aigen": PEER_VOTE_QUORUM_AIGEN,
        "min_vote_aigen": MIN_VOTE_AIGEN,
        "treasury_wallet": TREASURY,
    }


def quote_payout(reward_currency: str, gross_amount: int) -> dict:
    """Pre-creation quote: tells creator exactly what winner will get and what
    fee the protocol takes. Useful for transparent UX in /missions/create flow."""
    if reward_currency.upper() not in REWARD_CURRENCIES:
        return {"error": f"unknown currency {reward_currency}"}
    net, fee = _split_with_fee(gross_amount)
    return {
        "currency": reward_currency.upper(),
        "gross_amount": gross_amount,
        "net_to_winner": net,
        "protocol_fee": fee,
        "fee_bps": PROTOCOL_FEE_BPS,
        "fee_pct": f"{PROTOCOL_FEE_BPS/100:.2f}%",
    }
