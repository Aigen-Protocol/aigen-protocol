#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OABP / AIGEN oracle mission verifier: *a required on-chain action occurred*.

What this is
============
A new **oracle** mission-type verifier for the OABP / AIGEN agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``. It resolves missions whose
deliverable is an **on-chain transaction** — e.g. "send >= 0.01 ETH to
``0xRecipient`` on Base", "make an ERC-20 ``Transfer`` of >= 1_000_000 USDC units
to ``0xTreasury`` on Optimism", or "deploy a contract on Ethereum". The submitter
proves the work by handing over a **transaction hash**; the verifier confirms it
against the chain.

The protocol already ships oracle backends — **GoPlus** (token-security for
safety-review missions) and the **GitHub REST API** (repo deliverables). This
module adds an **on-chain settlement oracle** in the same spirit:

* **Content-addressed** — anyone can re-run it and get the same verdict from a
  public, read-only source: the chain itself, via a JSON-RPC endpoint. The truth
  is the mined transaction, not the submitter's prose.
* **Read-only, zero authority** — it only issues *read* RPC calls
  (``eth_getTransactionByHash`` / ``eth_getTransactionReceipt`` /
  ``eth_blockNumber`` on EVM; ``getTransaction`` / ``getSlot`` on Solana). It
  **never signs, never broadcasts, and holds no key material**. There is no
  private key, mnemonic, or signing path anywhere in this file.
* **Fail-closed** — anything it cannot affirmatively confirm (tx missing,
  unmined, reverted, wrong recipient, wrong amount, wrong Transfer log) is
  ``verified=False`` with a precise, human-readable reason.

It depends on the **Python standard library only** (``urllib``), so it runs in a
resolver with zero third-party packages installed. The RPC URL for each chain is
**injectable** (constructor / params / env / CLI) — no endpoint is hard-required,
and a stub transport is used by the bundled offline self-test.

Settlement chains (protocol mapping)
====================================
The protocol settles on four chains; each maps to a public read-only JSON-RPC
endpoint. The defaults below are well-known *public* endpoints, but every one is
overridable (``rpc_urls`` arg, ``verification_params.rpc_url``, the
``OABP_RPC_<CHAIN>`` env var, or ``--rpc-url`` on the CLI) so an operator can
point at their own node / paid provider:

    chain      | family | default public JSON-RPC endpoint
    -----------+--------+-------------------------------------------------
    base       | EVM    | https://mainnet.base.org
    optimism   | EVM    | https://mainnet.optimism.io
    ethereum   | EVM    | https://eth.llamarpc.com
    solana     | SVM    | https://api.mainnet-beta.solana.com

Aliases accepted for ``chain``: ``base``; ``optimism|op|op-mainnet``;
``ethereum|eth|mainnet|l1``; ``solana|sol``.

Mission kinds
=============
``verification_params.kind`` selects what "the required action" is:

* ``tx_to``          — a plain value transfer / call whose **recipient** is
                       ``to`` and whose native value is ``>= min_value`` (wei on
                       EVM, lamports on Solana). Use for "send N native units to
                       address A".
* ``erc20_transfer`` — the transaction emitted an **ERC-20 ``Transfer`` log**
                       from the ``token`` contract, to recipient ``to``, for
                       ``>= min_value`` token base-units. Matched by the canonical
                       Transfer event topic (below). EVM only.
* ``contract_deploy``— the transaction **created a contract** (``to`` is null in
                       the tx and the receipt carries a ``contractAddress``). If
                       ``to`` is supplied for this kind it is interpreted as the
                       *expected deployed address* and must match the receipt's
                       ``contractAddress``.

Optionally, every kind may also require the sender: ``from`` (the tx ``from`` must
equal it). Addresses are compared **case-insensitively** (EVM is checksum-cased
but consensus is lowercase-hex; Solana is base58 and compared verbatim/trimmed).

The ERC-20 Transfer topic this verifier matches
-----------------------------------------------
ERC-20 ``Transfer(address indexed from, address indexed to, uint256 value)`` is
emitted as a log whose ``topics[0]`` is the Keccak-256 hash of the event
signature string ``"Transfer(address,address,uint256)"``::

    TRANSFER_TOPIC0 =
        0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef

For a standard ERC-20 this log has exactly **3 topics**: ``topics[0]`` = the hash
above, ``topics[1]`` = ``from`` (left-zero-padded to 32 bytes), ``topics[2]`` =
``to`` (left-zero-padded to 32 bytes); the **value** is the 32-byte ``data``
field (uint256, big-endian). The verifier scans the receipt's ``logs`` for a log
emitted by ``token`` with this ``topics[0]``, decodes ``topics[2]`` -> recipient
and ``data`` -> amount, and accepts iff recipient == ``to`` and amount >=
``min_value``. (This is exactly the on-chain shape produced by every compliant
ERC-20 ``transfer`` / ``transferFrom``; tokens that don't emit the standard
event — a handful of non-compliant ones — cannot be verified this way, which is
the safe default.)

What the verifier checks (all must hold for ``verified=True``)
--------------------------------------------------------------
1. **PROOF PARSES** — the proof yields a transaction hash of the right shape for
   the chain (EVM: ``0x`` + 64 hex; Solana: base58, ~64–90 chars). The proof may
   be a bare hash, ``chain:hash``, an explorer URL, or a JSON object.
2. **TX FOUND** — the node returns the transaction (EVM
   ``eth_getTransactionByHash`` non-null; Solana ``getTransaction`` non-null). A
   missing tx ⇒ never happened (or wrong chain) ⇒ reject.
3. **MINED (>= 1 confirmation)** — the tx is in a block: EVM
   ``blockNumber``/``blockHash`` are non-null and ``head - blockNumber + 1 >=
   min_confirmations`` (default 1); Solana has a non-null ``slot`` and a
   ``confirmationStatus``/``commitment`` of confirmed|finalized. A pending /
   dropped tx ⇒ reject.
4. **SUCCEEDED** — EVM receipt ``status == 0x1`` (post-Byzantium); Solana
   ``meta.err is null``. A reverted/failed tx ⇒ reject. (EVM status ``0x0`` is a
   revert.)
5. **MATCHES CONSTRAINTS** — per ``kind`` as described above (recipient / value /
   ERC-20 Transfer topic+amount / contract creation), plus the optional ``from``.

Each failing check sets ``verified=False`` and a ``detail`` naming the first
failure; the full structured trace (raw RPC fields used, decoded values, the
confirmation maths) is returned in ``VerifyResult.evidence`` so a creator/auditor
can re-derive the verdict.

The proof format
----------------
``proof`` is the transaction hash. Accepted forms (all normalise to one hash):

  * ``"0xabc…"`` (EVM) or ``"5xY…"`` (Solana base58)                  (bare hash)
  * ``"base:0xabc…"`` / ``"solana:5xY…"``                              (chain-tagged)
  * an explorer URL: ``https://basescan.org/tx/0xabc…``,
    ``https://optimistic.etherscan.io/tx/0x…``, ``https://etherscan.io/tx/0x…``,
    ``https://solscan.io/tx/5xY…`` (or ``…/tx/…?cluster=…``)            (URL)
  * ``'{"chain":"base","tx_hash":"0xabc…"}'``                          (JSON)

A ``chain`` found in the proof must be consistent with the mission's ``chain``
(mismatch ⇒ reject) but is otherwise advisory — the mission's chain is canonical.

verification_params schema
==========================
The mission's ``verification_params`` object (the ``oracle`` arm of the protocol)
for this mission-type is::

    {
      # REQUIRED — which settlement chain to read.
      "chain": "base",            # base | optimism | ethereum | solana (aliases ok)

      # REQUIRED — what the on-chain action is.
      "kind": "tx_to",            # tx_to | erc20_transfer | contract_deploy

      # CONSTRAINTS (which apply depends on kind):
      "to": "0xRecipient…",       # tx_to: required recipient.
                                  # erc20_transfer: required Transfer recipient.
                                  # contract_deploy: OPTIONAL expected deployed addr.
      "token": "0xToken…",        # erc20_transfer: REQUIRED ERC-20 contract addr.
      "min_value": "10000000000000000",  # tx_to: min native value (wei/lamports).
                                  # erc20_transfer: min token base-units.
                                  # string|int; default 0 (any positive/zero amount).
      "from": "0xSender…",        # OPTIONAL; if set, tx sender must equal this.

      # OPTIONAL — knobs.
      "min_confirmations": 1,     # int >=1; EVM depth required (default 1).
      "rpc_url": "https://…",     # override the endpoint for this chain.

      # human-readable spec; surfaced to solvers, not parsed by the oracle.
      "oracle_description":
          "Send >= 0.01 ETH to 0xRecipient… on Base; submit the tx hash."
    }

``chain`` and ``kind`` are mandatory. ``token`` is mandatory for
``erc20_transfer``; ``to`` is mandatory for ``tx_to`` and ``erc20_transfer`` and
optional (= expected address) for ``contract_deploy``. ``oracle_description`` is
free text for humans/solvers; the machine truth is the typed fields above.

Worked example
==============
Mission::

    verification_params = {
        "chain": "base",
        "kind": "erc20_transfer",
        "token": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC on Base
        "to":    "0x000000000000000000000000000000000000dEaD",
        "min_value": "1000000",                                  # 1 USDC (6 dp)
        "oracle_description":
            "Transfer >= 1 USDC to 0x…dEaD on Base; submit the tx hash.",
    }

An agent sends 2 USDC to ``0x…dEaD`` and submits ``proof =
"0x<txhash>"``. The verifier:

* parses the proof -> EVM hash; ✓
* ``eth_getTransactionByHash`` -> non-null, ``blockNumber`` set; ✓
* head - blockNumber + 1 >= 1 confirmation; ✓
* ``eth_getTransactionReceipt`` -> ``status == 0x1``; ✓
* a receipt log from the USDC contract has ``topics[0] == TRANSFER_TOPIC0``,
  ``topics[2]`` decodes to ``0x…dEaD``, ``data`` decodes to 2_000_000 >=
  1_000_000; ✓

=> ``VerifyResult(verified=True, detail="erc20 Transfer of 2000000 USDC-units to
0x…dEaD on base confirmed in tx 0x… …", evidence={…})``. A reverted tx, a missing
tx, a transfer to the wrong address, or an amount below ``min_value`` each yield
``verified=False`` with the matching reason.

CLI
===
    # verify a live submission against a public Base RPC:
    python3 onchain_tx_verifier.py \
        --chain base --kind tx_to --to 0xRecipient \
        --min-value 10000000000000000 --proof 0x<txhash>

    # ERC-20 transfer on Optimism, with a custom RPC:
    python3 onchain_tx_verifier.py \
        --chain optimism --kind erc20_transfer \
        --token 0xToken --to 0xTreasury --min-value 1000000 \
        --rpc-url https://my.op.node --proof 0x<txhash>

    # run the bundled OFFLINE self-test (stubs the RPC; no network) and exit:
    python3 onchain_tx_verifier.py --self-test

Exit codes (CLI):
* ``0`` — verified True (or, under --self-test, all assertions passed).
* ``1`` — verified False (the submission does not satisfy the mission).
* ``2`` — usage / configuration error.
* ``3`` — an RPC / network error prevented a verdict.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

__all__ = [
    "VerifyResult",
    "VerificationParams",
    "RpcClient",
    "RpcError",
    "verify",
    "verify_mission",
    "normalize_chain",
    "parse_proof",
    "TRANSFER_TOPIC0",
    "DEFAULT_RPC_URLS",
]

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
HTTP_TIMEOUT = 25.0
USER_AGENT = "oabp-onchain-tx-verifier/1.0 (+https://cryptogenesis.duckdns.org)"

# ERC-20 Transfer(address,address,uint256) event signature topic0:
#   keccak256("Transfer(address,address,uint256)")
# This is a fixed, well-known constant of the ERC-20 standard.
TRANSFER_TOPIC0 = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)

# Canonical chain id -> family.
_EVM_CHAINS = ("base", "optimism", "ethereum")
_SVM_CHAINS = ("solana",)

# chain aliases -> canonical id.
_CHAIN_ALIASES = {
    "base": "base",
    "base-mainnet": "base",
    "optimism": "optimism",
    "op": "optimism",
    "op-mainnet": "optimism",
    "optimism-mainnet": "optimism",
    "ethereum": "ethereum",
    "eth": "ethereum",
    "mainnet": "ethereum",
    "l1": "ethereum",
    "homestead": "ethereum",
    "solana": "solana",
    "sol": "solana",
    "solana-mainnet": "solana",
    "mainnet-beta": "solana",
}

# Default PUBLIC read-only JSON-RPC endpoints (all overridable; see module doc).
DEFAULT_RPC_URLS: Dict[str, str] = {
    "base": "https://mainnet.base.org",
    "optimism": "https://mainnet.optimism.io",
    "ethereum": "https://eth.llamarpc.com",
    "solana": "https://api.mainnet-beta.solana.com",
}

_EVM_TX_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
# base58 alphabet (Bitcoin/Solana) — excludes 0 O I l.
_BASE58_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{43,90}$")
_ALL_KINDS = ("tx_to", "erc20_transfer", "contract_deploy")


# --------------------------------------------------------------------------- #
# Result + params dataclasses
# --------------------------------------------------------------------------- #
@dataclass
class VerifyResult:
    """Typed outcome of an oracle verification.

    Attributes
    ----------
    verified:
        ``True`` only if every required check passed. The protocol pays the
        bounty iff this is ``True``.
    detail:
        Human-readable one-line explanation (the accept reason, or the FIRST
        failing check and why). Safe to log / surface to the creator.
    evidence:
        Structured, content-addressed trace of what the chain reported and which
        checks ran. Lets anyone re-derive the verdict without re-querying.
        Always JSON-serialisable.
    """

    verified: bool
    detail: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verified": self.verified,
            "detail": self.detail,
            "evidence": self.evidence,
        }

    def __bool__(self) -> bool:  # truthy == verified, convenient in callers
        return self.verified


@dataclass(frozen=True)
class VerificationParams:
    """Parsed, validated view of an on-chain-tx mission's ``verification_params``.

    See the module docstring for the JSON schema. ``from_mapping`` is tolerant of
    unknown keys and lenient typing, but enforces the *required* fields per kind
    (so a malformed mission fails loudly rather than silently under-checking).
    """

    chain: str
    kind: str
    to: Optional[str] = None
    token: Optional[str] = None
    min_value: int = 0
    from_addr: Optional[str] = None
    min_confirmations: int = 1
    rpc_url: Optional[str] = None
    oracle_description: Optional[str] = None

    @property
    def family(self) -> str:
        return "evm" if self.chain in _EVM_CHAINS else "svm"

    @classmethod
    def from_mapping(
        cls, data: Optional[Mapping[str, Any]]
    ) -> "VerificationParams":
        if not isinstance(data, Mapping):
            raise ValueError("verification_params must be an object")

        raw_chain = data.get("chain")
        if not isinstance(raw_chain, str) or not raw_chain.strip():
            raise ValueError(
                "verification_params.chain is required "
                "(base|optimism|ethereum|solana)"
            )
        chain = normalize_chain(raw_chain)

        raw_kind = data.get("kind")
        if not isinstance(raw_kind, str) or raw_kind.strip().lower() not in _ALL_KINDS:
            raise ValueError(
                "verification_params.kind is required and must be one of %s"
                % (", ".join(_ALL_KINDS),)
            )
        kind = raw_kind.strip().lower()

        def _opt_addr(*keys: str) -> Optional[str]:
            for k in keys:
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return None

        to = _opt_addr("to", "recipient", "to_address")
        token = _opt_addr("token", "token_address", "contract")
        from_addr = _opt_addr("from", "from_address", "sender")
        rpc_url = _opt_addr("rpc_url", "rpc", "endpoint")
        oracle_description = _opt_addr("oracle_description")

        min_value = _coerce_int(data.get("min_value"), default=0)
        if min_value < 0:
            raise ValueError("verification_params.min_value must be >= 0")

        min_conf = _coerce_int(data.get("min_confirmations"), default=1)
        if min_conf < 1:
            min_conf = 1

        # Per-kind required-field enforcement (fail-closed on malformed missions).
        if kind == "tx_to":
            if not to:
                raise ValueError("kind 'tx_to' requires 'to' (recipient address)")
        elif kind == "erc20_transfer":
            if chain not in _EVM_CHAINS:
                raise ValueError(
                    "kind 'erc20_transfer' is EVM-only; chain %r is not EVM"
                    % (chain,)
                )
            if not token:
                raise ValueError(
                    "kind 'erc20_transfer' requires 'token' (ERC-20 contract)"
                )
            if not to:
                raise ValueError(
                    "kind 'erc20_transfer' requires 'to' (transfer recipient)"
                )
        elif kind == "contract_deploy":
            if chain not in _EVM_CHAINS:
                raise ValueError(
                    "kind 'contract_deploy' is EVM-only; chain %r is not EVM"
                    % (chain,)
                )
            # 'to' is OPTIONAL here (= expected deployed address).

        return cls(
            chain=chain,
            kind=kind,
            to=to,
            token=token,
            min_value=min_value,
            from_addr=from_addr,
            min_confirmations=min_conf,
            rpc_url=rpc_url,
            oracle_description=oracle_description,
        )


def _coerce_int(value: Any, default: int = 0) -> int:
    """Tolerant int coercion accepting int, decimal str, or 0x-hex str."""
    if value is None:
        return default
    if isinstance(value, bool):  # avoid True==1 surprises
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return default
        try:
            if s.lower().startswith("0x"):
                return int(s, 16)
            return int(s, 10)
        except ValueError:
            return default
    return default


# --------------------------------------------------------------------------- #
# Chain normalisation
# --------------------------------------------------------------------------- #
def normalize_chain(chain: str) -> str:
    """Map a chain string (with aliases) to a canonical id, or raise ValueError.

    ``op`` -> ``optimism``; ``eth``/``mainnet`` -> ``ethereum``; ``sol`` ->
    ``solana``; ``base`` -> ``base``.
    """
    key = (chain or "").strip().lower()
    if key in _CHAIN_ALIASES:
        return _CHAIN_ALIASES[key]
    raise ValueError(
        "unknown chain %r; expected one of base|optimism|ethereum|solana "
        "(or an alias)" % (chain,)
    )


# --------------------------------------------------------------------------- #
# Proof parsing (bare hash, chain:hash, explorer URL, or JSON)
# --------------------------------------------------------------------------- #
# Explorer host -> canonical chain (for chain inference from a URL).
_EXPLORER_HOSTS = {
    "basescan.org": "base",
    "base.blockscout.com": "base",
    "optimistic.etherscan.io": "optimism",
    "opscan.io": "optimism",
    "optimism.blockscout.com": "optimism",
    "etherscan.io": "ethereum",
    "eth.blockscout.com": "ethereum",
    "solscan.io": "solana",
    "explorer.solana.com": "solana",
    "solana.fm": "solana",
}


def parse_proof(proof: Any) -> Tuple[str, Optional[str]]:
    """Parse a submission proof into ``(tx_hash, chain_hint_or_None)``.

    Accepted forms (in priority order):
      * a mapping ``{"tx_hash"|"hash"|"txid": "...", "chain"?: "..."}``
      * a JSON object string of the same shape
      * an explorer URL ``https://<host>/tx/<hash>[?...]`` (chain inferred)
      * ``"<chain>:<hash>"``                              (chain tag + hash)
      * a bare hash ``"0x…"`` (EVM) or base58 (Solana)

    Returns the extracted hash and a chain hint (canonical id) when one could be
    inferred, else ``None``. Raises ``ValueError`` if no plausible hash is found.
    """
    # Already a mapping (e.g. proof posted as structured JSON).
    if isinstance(proof, Mapping):
        h = (
            proof.get("tx_hash")
            or proof.get("hash")
            or proof.get("txid")
            or proof.get("signature")  # Solana calls it a signature
            or proof.get("tx")
        )
        if not isinstance(h, str) or not h.strip():
            raise ValueError("proof object must carry a non-empty tx hash")
        chain_hint = proof.get("chain")
        hint = None
        if isinstance(chain_hint, str) and chain_hint.strip():
            try:
                hint = normalize_chain(chain_hint)
            except ValueError:
                hint = None
        return h.strip(), hint

    if not isinstance(proof, str) or not proof.strip():
        raise ValueError("proof must be a non-empty string (a transaction hash)")
    s = proof.strip()

    # JSON object string.
    if s.startswith("{"):
        try:
            obj = json.loads(s)
        except ValueError:
            obj = None
        if isinstance(obj, Mapping):
            return parse_proof(obj)

    # Explorer URL: scheme://host[:port]/.../tx/<hash>[?query][#frag]
    m = re.match(r"^(?:https?://)?([^/\s:]+)(?::\d+)?(/\S*)?$", s)
    if m and m.group(2) and "/tx/" in m.group(2).lower():
        host = m.group(1).lower()
        path = m.group(2)
        # take the path segment right after /tx/
        tail = re.split(r"/tx/", path, maxsplit=1, flags=re.IGNORECASE)[1]
        hash_seg = re.split(r"[/?#]", tail, maxsplit=1)[0].strip()
        if hash_seg:
            hint = _EXPLORER_HOSTS.get(host)
            return hash_seg, hint

    # "<chain>:<hash>"  — but not an EVM 0x-hash (which has no ':').
    if ":" in s and not s.lower().startswith("0x"):
        left, _, right = s.partition(":")
        left, right = left.strip(), right.strip()
        if right:
            hint = None
            try:
                hint = normalize_chain(left)
            except ValueError:
                hint = None
            if hint is not None:
                return right, hint
            # Not a chain tag (could be a URL fragment); fall through to bare.

    # Bare hash.
    return s, None


def _looks_like_evm_hash(h: str) -> bool:
    return bool(_EVM_TX_RE.match(h))


def _looks_like_solana_sig(h: str) -> bool:
    return bool(_BASE58_RE.match(h)) and not h.lower().startswith("0x")


# --------------------------------------------------------------------------- #
# Address / hex helpers
# --------------------------------------------------------------------------- #
def _eq_addr(a: Optional[str], b: Optional[str]) -> bool:
    """Case-insensitive address equality (EVM hex is consensus-lowercase)."""
    if a is None or b is None:
        return False
    return a.strip().lower() == b.strip().lower()


def _hex_to_int(value: Any) -> Optional[int]:
    """0x-hex (or plain int) -> int; ``None`` on anything unparseable."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return int(s, 16) if s.lower().startswith("0x") else int(s, 10)
        except ValueError:
            return None
    return None


def _topic_to_address(topic: str) -> Optional[str]:
    """A 32-byte indexed-address topic -> ``0x`` + last 20 bytes (40 hex)."""
    if not isinstance(topic, str):
        return None
    h = topic.strip().lower()
    if h.startswith("0x"):
        h = h[2:]
    if len(h) < 40 or not re.match(r"^[0-9a-f]*$", h):
        return None
    return "0x" + h[-40:]


# --------------------------------------------------------------------------- #
# JSON-RPC client (stdlib urllib). Read-only. No signing. RPC URL injectable.
# --------------------------------------------------------------------------- #
class RpcError(Exception):
    """A network / transport / JSON-RPC error talking to a node.

    Distinct from "the transaction is simply absent" (which the verifier
    represents as ``verified=False``, not an exception): this is reserved for
    *infrastructure* failures (transport, non-200, malformed envelope, or an RPC
    ``error`` object) that prevented reaching a verdict at all.
    """


class RpcClient:
    """Read-only JSON-RPC 2.0 client (stdlib ``urllib`` only).

    Issues *only* read methods (``eth_*`` getters / ``getTransaction`` /
    ``getSlot``). There is no method here that signs or broadcasts anything, and
    the client holds no key material — it just POSTs a JSON-RPC envelope and reads
    the result.

    The endpoint per chain comes from (in priority order): an explicit ``url``
    passed to a call, ``rpc_urls[chain]``, the ``OABP_RPC_<CHAIN>`` env var, then
    :data:`DEFAULT_RPC_URLS`. A ``transport`` callable
    ``(url, payload_bytes, timeout) -> (status:int, body:bytes)`` may be injected
    (this is how the offline self-test stubs the chain with zero network).
    """

    def __init__(
        self,
        rpc_urls: Optional[Mapping[str, str]] = None,
        *,
        timeout: float = HTTP_TIMEOUT,
        transport: Optional[Callable[[str, bytes, float], Tuple[int, bytes]]] = None,
    ) -> None:
        self.rpc_urls: Dict[str, str] = dict(DEFAULT_RPC_URLS)
        if rpc_urls:
            for k, v in rpc_urls.items():
                if isinstance(v, str) and v.strip():
                    try:
                        self.rpc_urls[normalize_chain(k)] = v.strip()
                    except ValueError:
                        continue
        self.timeout = float(timeout)
        self._transport = transport
        self._id = 0

    # -- endpoint resolution ---------------------------------------------- #
    def url_for(self, chain: str, override: Optional[str] = None) -> str:
        if override and override.strip():
            return override.strip()
        env = os.environ.get("OABP_RPC_%s" % chain.upper())
        if env and env.strip():
            return env.strip()
        url = self.rpc_urls.get(chain)
        if not url:
            raise RpcError("no RPC URL configured for chain %r" % chain)
        return url

    # -- low level --------------------------------------------------------- #
    def call(
        self,
        chain: str,
        method: str,
        params: Sequence[Any],
        *,
        url: Optional[str] = None,
    ) -> Any:
        """One JSON-RPC call; returns the ``result`` field or raises RpcError."""
        endpoint = self.url_for(chain, url)
        self._id += 1
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": self._id, "method": method, "params": list(params)}
        ).encode("utf-8")

        if self._transport is not None:
            try:
                status, body = self._transport(endpoint, payload, self.timeout)
            except Exception as exc:  # pragma: no cover - injected transport
                raise RpcError("%s %s failed: %s" % (endpoint, method, exc)) from exc
            return self._decode(endpoint, method, status, body)

        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.getcode()
                body = resp.read()
        except urllib.error.HTTPError as exc:
            # Some nodes return the JSON-RPC error envelope with a non-200; try.
            body = exc.read() if hasattr(exc, "read") else b""
            try:
                return self._decode(endpoint, method, exc.code, body)
            except RpcError:
                raise RpcError(
                    "%s %s -> HTTP %s %s" % (endpoint, method, exc.code, exc.reason)
                ) from exc
        except urllib.error.URLError as exc:
            raise RpcError("%s %s failed: %s" % (endpoint, method, exc.reason)) from exc
        except (TimeoutError, OSError) as exc:  # pragma: no cover - env dependent
            raise RpcError("%s %s failed: %s" % (endpoint, method, exc)) from exc
        return self._decode(endpoint, method, status, body)

    @staticmethod
    def _decode(endpoint: str, method: str, status: int, body: bytes) -> Any:
        try:
            obj = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise RpcError(
                "%s %s -> non-JSON body (HTTP %s): %s" % (endpoint, method, status, exc)
            ) from exc
        if isinstance(obj, Mapping) and obj.get("error") is not None:
            raise RpcError(
                "%s %s -> RPC error: %s" % (endpoint, method, obj.get("error"))
            )
        if status != 200 and not (isinstance(obj, Mapping) and "result" in obj):
            raise RpcError("%s %s -> HTTP %s" % (endpoint, method, status))
        if isinstance(obj, Mapping):
            return obj.get("result")
        return obj

    # -- EVM endpoints ----------------------------------------------------- #
    def eth_get_transaction_by_hash(
        self, chain: str, tx_hash: str, *, url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        res = self.call(chain, "eth_getTransactionByHash", [tx_hash], url=url)
        return res if isinstance(res, dict) else None

    def eth_get_transaction_receipt(
        self, chain: str, tx_hash: str, *, url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        res = self.call(chain, "eth_getTransactionReceipt", [tx_hash], url=url)
        return res if isinstance(res, dict) else None

    def eth_block_number(self, chain: str, *, url: Optional[str] = None) -> Optional[int]:
        res = self.call(chain, "eth_blockNumber", [], url=url)
        return _hex_to_int(res)

    # -- Solana endpoints -------------------------------------------------- #
    def sol_get_transaction(
        self, chain: str, signature: str, *, url: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        res = self.call(
            chain,
            "getTransaction",
            [
                signature,
                {"encoding": "json", "maxSupportedTransactionVersion": 0,
                 "commitment": "confirmed"},
            ],
            url=url,
        )
        return res if isinstance(res, dict) else None

    def sol_get_slot(self, chain: str, *, url: Optional[str] = None) -> Optional[int]:
        res = self.call(chain, "getSlot", [{"commitment": "confirmed"}], url=url)
        return res if isinstance(res, int) else _hex_to_int(res)


# --------------------------------------------------------------------------- #
# ERC-20 Transfer log scanning
# --------------------------------------------------------------------------- #
def _scan_transfer_logs(
    logs: Sequence[Mapping[str, Any]], token: str
) -> List[Dict[str, Any]]:
    """Decode every ERC-20 ``Transfer`` log emitted by ``token`` in ``logs``.

    Returns a list of ``{"from","to","value","log_index"}`` for each log whose
    ``address`` == ``token`` and whose ``topics[0]`` == :data:`TRANSFER_TOPIC0`
    with the standard 3-topic indexed-from/indexed-to shape. ``value`` is decoded
    from the 32-byte ``data`` (uint256, big-endian).
    """
    out: List[Dict[str, Any]] = []
    for log in logs:
        if not isinstance(log, Mapping):
            continue
        addr = log.get("address")
        if not _eq_addr(addr if isinstance(addr, str) else None, token):
            continue
        topics = log.get("topics")
        if not isinstance(topics, list) or len(topics) < 3:
            continue
        t0 = topics[0]
        if not isinstance(t0, str) or t0.strip().lower() != TRANSFER_TOPIC0:
            continue
        frm = _topic_to_address(topics[1]) if isinstance(topics[1], str) else None
        to = _topic_to_address(topics[2]) if isinstance(topics[2], str) else None
        value = _hex_to_int(log.get("data"))
        out.append(
            {
                "from": frm,
                "to": to,
                "value": value,
                "log_index": _hex_to_int(log.get("logIndex")),
            }
        )
    return out


# --------------------------------------------------------------------------- #
# The oracle
# --------------------------------------------------------------------------- #
def verify(
    params: VerificationParams,
    proof: Any,
    *,
    client: Optional[RpcClient] = None,
) -> VerifyResult:
    """Resolve an on-chain-tx mission. Read-only; fail-closed.

    :param params:  the parsed :class:`VerificationParams` for the mission.
    :param proof:   the submission proof (a tx hash; see :func:`parse_proof`).
    :param client:  inject an :class:`RpcClient` (or a stub in tests). If omitted,
                    a default read-only client (public endpoints, overridable via
                    ``params.rpc_url`` / env) is created.
    :returns:       a :class:`VerifyResult` (``verified``/``detail``/``evidence``).
    """
    client = client or RpcClient()

    evidence: Dict[str, Any] = {
        "verifier": "onchain_tx",
        "params": {
            "chain": params.chain,
            "family": params.family,
            "kind": params.kind,
            "to": params.to,
            "token": params.token,
            "min_value": str(params.min_value),  # str: may exceed JS-safe int
            "from": params.from_addr,
            "min_confirmations": params.min_confirmations,
            "transfer_topic0": TRANSFER_TOPIC0
            if params.kind == "erc20_transfer"
            else None,
        },
        "checks": {},
    }
    checks: Dict[str, Any] = evidence["checks"]

    def reject(detail: str) -> VerifyResult:
        return VerifyResult(verified=False, detail=detail, evidence=evidence)

    # --- 0) PARSE PROOF --------------------------------------------------- #
    try:
        tx_hash, chain_hint = parse_proof(proof)
    except ValueError as exc:
        checks["proof_parsed"] = {"ok": False, "reason": str(exc)}
        return reject("invalid proof: %s" % exc)
    evidence["proof"] = {"raw": proof, "tx_hash": tx_hash, "chain_hint": chain_hint}

    # Shape the hash against the chain family.
    if params.family == "evm":
        shape_ok = _looks_like_evm_hash(tx_hash)
        shape_want = "0x + 64 hex"
    else:
        shape_ok = _looks_like_solana_sig(tx_hash)
        shape_want = "base58 signature"
    checks["proof_parsed"] = {
        "ok": shape_ok,
        "tx_hash": tx_hash,
        "expected_shape": shape_want,
    }
    if not shape_ok:
        return reject(
            "proof %r is not a valid %s transaction hash (expected %s)"
            % (tx_hash, params.chain, shape_want)
        )

    # Chain hint, if present, must agree with the mission chain.
    if chain_hint is not None and chain_hint != params.chain:
        checks["chain_consistent"] = {
            "ok": False,
            "proof_chain": chain_hint,
            "mission_chain": params.chain,
        }
        return reject(
            "proof names chain %r but the mission settles on %r"
            % (chain_hint, params.chain)
        )
    checks["chain_consistent"] = {"ok": True, "chain": params.chain}

    # Dispatch by family.
    if params.family == "evm":
        return _verify_evm(params, tx_hash, client, evidence, reject)
    return _verify_solana(params, tx_hash, client, evidence, reject)


def _verify_evm(
    params: VerificationParams,
    tx_hash: str,
    client: RpcClient,
    evidence: Dict[str, Any],
    reject: Callable[[str], VerifyResult],
) -> VerifyResult:
    checks: Dict[str, Any] = evidence["checks"]
    rpc = params.rpc_url

    # --- 1) TX FOUND ------------------------------------------------------ #
    try:
        tx = client.eth_get_transaction_by_hash(params.chain, tx_hash, url=rpc)
    except RpcError as exc:
        checks["tx_found"] = {"ok": False, "error": str(exc)}
        return reject("could not query %s for tx %s: %s" % (params.chain, tx_hash, exc))
    if tx is None:
        checks["tx_found"] = {"ok": False, "reason": "eth_getTransactionByHash null"}
        return reject(
            "transaction %s not found on %s (never broadcast, dropped, or wrong "
            "chain)" % (tx_hash, params.chain)
        )
    block_number = _hex_to_int(tx.get("blockNumber"))
    tx_from = tx.get("from")
    tx_to = tx.get("to")
    tx_value = _hex_to_int(tx.get("value"))
    checks["tx_found"] = {"ok": True}
    evidence["tx"] = {
        "from": tx_from,
        "to": tx_to,
        "value": str(tx_value) if tx_value is not None else None,
        "blockNumber": block_number,
        "blockHash": tx.get("blockHash"),
        "input_len": len(tx.get("input")) if isinstance(tx.get("input"), str) else None,
    }

    # --- 2) MINED (>= min_confirmations) ---------------------------------- #
    mined = block_number is not None and tx.get("blockHash") not in (None, "0x", "")
    if not mined:
        checks["mined"] = {"ok": False, "reason": "pending (no block)"}
        return reject(
            "transaction %s is pending on %s (not yet in a block)"
            % (tx_hash, params.chain)
        )
    try:
        head = client.eth_block_number(params.chain, url=rpc)
    except RpcError as exc:
        head = None
        checks.setdefault("mined", {})["head_error"] = str(exc)
    if head is not None:
        confirmations = head - block_number + 1
    else:
        confirmations = None
    enough = (
        confirmations is not None and confirmations >= params.min_confirmations
    )
    checks["mined"] = {
        "ok": bool(enough) if confirmations is not None else False,
        "block_number": block_number,
        "head": head,
        "confirmations": confirmations,
        "min_confirmations": params.min_confirmations,
    }
    if confirmations is None:
        return reject(
            "transaction %s is in block %d but the chain head could not be read to "
            "confirm depth on %s" % (tx_hash, block_number, params.chain)
        )
    if not enough:
        return reject(
            "transaction %s has %d confirmation(s) on %s; mission requires %d"
            % (tx_hash, confirmations, params.chain, params.min_confirmations)
        )

    # --- 3) SUCCEEDED (receipt status == 0x1) ----------------------------- #
    try:
        receipt = client.eth_get_transaction_receipt(params.chain, tx_hash, url=rpc)
    except RpcError as exc:
        checks["succeeded"] = {"ok": False, "error": str(exc)}
        return reject(
            "could not fetch receipt for %s on %s: %s" % (tx_hash, params.chain, exc)
        )
    if receipt is None:
        checks["succeeded"] = {"ok": False, "reason": "no receipt"}
        return reject(
            "no receipt for %s on %s (cannot confirm success)" % (tx_hash, params.chain)
        )
    status = _hex_to_int(receipt.get("status"))
    receipt_contract = receipt.get("contractAddress")
    logs = receipt.get("logs") if isinstance(receipt.get("logs"), list) else []
    succeeded = status == 1
    checks["succeeded"] = {"ok": succeeded, "status": status}
    evidence["receipt"] = {
        "status": status,
        "contractAddress": receipt_contract,
        "log_count": len(logs),
    }
    if not succeeded:
        return reject(
            "transaction %s on %s did not succeed (receipt status %s != 0x1 — "
            "reverted/failed)" % (tx_hash, params.chain, receipt.get("status"))
        )

    # --- optional: sender (from) ------------------------------------------ #
    if params.from_addr is not None:
        from_ok = _eq_addr(tx_from if isinstance(tx_from, str) else None,
                           params.from_addr)
        checks["from_matches"] = {
            "ok": from_ok,
            "expected": params.from_addr,
            "actual": tx_from,
        }
        if not from_ok:
            return reject(
                "tx sender %s does not match required from %s"
                % (tx_from, params.from_addr)
            )

    # --- 4) MATCHES CONSTRAINTS (per kind) -------------------------------- #
    if params.kind == "tx_to":
        return _check_tx_to(params, tx_hash, tx_to, tx_value, evidence, reject)
    if params.kind == "erc20_transfer":
        return _check_erc20(params, tx_hash, logs, evidence, reject)
    if params.kind == "contract_deploy":
        return _check_deploy(params, tx_hash, tx_to, receipt_contract, evidence, reject)
    return reject("unsupported kind %r" % params.kind)  # pragma: no cover


def _check_tx_to(
    params: VerificationParams,
    tx_hash: str,
    tx_to: Any,
    tx_value: Optional[int],
    evidence: Dict[str, Any],
    reject: Callable[[str], VerifyResult],
) -> VerifyResult:
    checks: Dict[str, Any] = evidence["checks"]
    to_ok = _eq_addr(tx_to if isinstance(tx_to, str) else None, params.to)
    checks["recipient_matches"] = {"ok": to_ok, "expected": params.to, "actual": tx_to}
    if not to_ok:
        return reject(
            "tx recipient %s does not match required to %s" % (tx_to, params.to)
        )
    val = tx_value if tx_value is not None else 0
    value_ok = val >= params.min_value
    checks["min_value"] = {
        "ok": value_ok,
        "value": str(val),
        "min_value": str(params.min_value),
    }
    if not value_ok:
        return reject(
            "tx native value %s is below the mission minimum %s (wei/lamports)"
            % (val, params.min_value)
        )
    detail = (
        "value transfer of %s (wei) to %s on %s confirmed in tx %s — verified"
        % (val, params.to, params.chain, tx_hash)
    )
    return VerifyResult(verified=True, detail=detail, evidence=evidence)


def _check_erc20(
    params: VerificationParams,
    tx_hash: str,
    logs: Sequence[Mapping[str, Any]],
    evidence: Dict[str, Any],
    reject: Callable[[str], VerifyResult],
) -> VerifyResult:
    checks: Dict[str, Any] = evidence["checks"]
    transfers = _scan_transfer_logs(logs, params.token or "")
    evidence["transfer_logs"] = transfers
    checks["transfer_log_present"] = {
        "ok": bool(transfers),
        "token": params.token,
        "topic0": TRANSFER_TOPIC0,
        "matched_logs": len(transfers),
    }
    if not transfers:
        return reject(
            "no ERC-20 Transfer log from token %s (topic %s) found in tx %s on %s"
            % (params.token, TRANSFER_TOPIC0, tx_hash, params.chain)
        )
    # Find a transfer to the required recipient with amount >= min_value.
    to_matches = [t for t in transfers if _eq_addr(t.get("to"), params.to)]
    checks["recipient_matches"] = {
        "ok": bool(to_matches),
        "expected": params.to,
        "recipients_seen": [t.get("to") for t in transfers],
    }
    if not to_matches:
        return reject(
            "ERC-20 Transfer(s) found from %s but none to required recipient %s "
            "in tx %s" % (params.token, params.to, tx_hash)
        )
    best = max((t.get("value") or 0) for t in to_matches)
    value_ok = best >= params.min_value
    checks["min_value"] = {
        "ok": value_ok,
        "value": str(best),
        "min_value": str(params.min_value),
    }
    if not value_ok:
        return reject(
            "ERC-20 Transfer to %s carried %s base-units, below the mission "
            "minimum %s in tx %s" % (params.to, best, params.min_value, tx_hash)
        )
    detail = (
        "erc20 Transfer of %s token base-units (token %s) to %s on %s confirmed "
        "in tx %s — verified"
        % (best, params.token, params.to, params.chain, tx_hash)
    )
    return VerifyResult(verified=True, detail=detail, evidence=evidence)


def _check_deploy(
    params: VerificationParams,
    tx_hash: str,
    tx_to: Any,
    receipt_contract: Any,
    evidence: Dict[str, Any],
    reject: Callable[[str], VerifyResult],
) -> VerifyResult:
    checks: Dict[str, Any] = evidence["checks"]
    # A creation tx has tx.to == null AND receipt.contractAddress set.
    to_is_null = tx_to in (None, "", "0x")
    has_addr = isinstance(receipt_contract, str) and bool(receipt_contract.strip())
    is_deploy = to_is_null and has_addr
    checks["is_contract_creation"] = {
        "ok": is_deploy,
        "tx_to": tx_to,
        "contractAddress": receipt_contract,
    }
    if not is_deploy:
        return reject(
            "tx %s on %s is not a contract creation (to=%r, contractAddress=%r)"
            % (tx_hash, params.chain, tx_to, receipt_contract)
        )
    # If an expected address was supplied (params.to), it must match.
    if params.to is not None:
        addr_ok = _eq_addr(receipt_contract, params.to)
        checks["deployed_address_matches"] = {
            "ok": addr_ok,
            "expected": params.to,
            "actual": receipt_contract,
        }
        if not addr_ok:
            return reject(
                "deployed contract %s does not match expected address %s in tx %s"
                % (receipt_contract, params.to, tx_hash)
            )
    detail = (
        "contract deployed at %s on %s confirmed in tx %s — verified"
        % (receipt_contract, params.chain, tx_hash)
    )
    return VerifyResult(verified=True, detail=detail, evidence=evidence)


def _verify_solana(
    params: VerificationParams,
    signature: str,
    client: RpcClient,
    evidence: Dict[str, Any],
    reject: Callable[[str], VerifyResult],
) -> VerifyResult:
    """Solana arm: supports ``tx_to`` (native SOL lamport delta to recipient).

    ``erc20_transfer`` / ``contract_deploy`` are EVM-only (enforced in
    ``VerificationParams.from_mapping``); on Solana the supported on-chain action
    is a native-SOL transfer whose recipient gained ``>= min_value`` lamports and
    whose transaction succeeded (``meta.err is null``) and is confirmed.
    """
    checks: Dict[str, Any] = evidence["checks"]
    rpc = params.rpc_url

    # --- 1) TX FOUND ------------------------------------------------------ #
    try:
        tx = client.sol_get_transaction(params.chain, signature, url=rpc)
    except RpcError as exc:
        checks["tx_found"] = {"ok": False, "error": str(exc)}
        return reject("could not query solana for tx %s: %s" % (signature, exc))
    if tx is None:
        checks["tx_found"] = {"ok": False, "reason": "getTransaction null"}
        return reject(
            "transaction %s not found on solana (unknown signature or not "
            "confirmed)" % (signature,)
        )
    checks["tx_found"] = {"ok": True}
    slot = tx.get("slot")
    meta = tx.get("meta") if isinstance(tx.get("meta"), Mapping) else {}
    err = meta.get("err")
    evidence["tx"] = {"slot": slot, "err": err}

    # --- 2) MINED (has a slot) + confirmation ----------------------------- #
    mined = isinstance(slot, int)
    checks["mined"] = {"ok": mined, "slot": slot}
    if not mined:
        return reject("transaction %s has no slot on solana (not mined)" % signature)
    # getTransaction at commitment=confirmed already implies >=1 confirmation;
    # record the head slot for the evidence trail when available.
    try:
        head_slot = client.sol_get_slot(params.chain, url=rpc)
    except RpcError:
        head_slot = None
    checks["mined"]["head_slot"] = head_slot
    if head_slot is not None:
        checks["mined"]["confirmations_slots"] = head_slot - slot + 1

    # --- 3) SUCCEEDED (meta.err is null) ---------------------------------- #
    succeeded = err is None
    checks["succeeded"] = {"ok": succeeded, "err": err}
    if not succeeded:
        return reject(
            "transaction %s on solana failed (meta.err=%r)" % (signature, err)
        )

    # --- 4) MATCHES CONSTRAINTS (tx_to: recipient lamport delta) ---------- #
    # Decode account keys + pre/post balances to compute each account's delta.
    account_keys = _solana_account_keys(tx)
    pre = meta.get("preBalances")
    post = meta.get("postBalances")
    evidence["solana_balances"] = {
        "accounts": account_keys,
        "pre": pre if isinstance(pre, list) else None,
        "post": post if isinstance(post, list) else None,
    }
    if (
        not account_keys
        or not isinstance(pre, list)
        or not isinstance(post, list)
        or len(pre) != len(account_keys)
        or len(post) != len(account_keys)
    ):
        checks["recipient_matches"] = {
            "ok": False,
            "reason": "could not decode account balances",
        }
        return reject(
            "could not decode account balances for solana tx %s to verify the "
            "transfer" % signature
        )

    # optional from
    if params.from_addr is not None:
        # fee payer / signer is account_keys[0] in legacy messages
        signer = account_keys[0] if account_keys else None
        from_ok = signer is not None and signer.strip() == params.from_addr.strip()
        checks["from_matches"] = {"ok": from_ok, "expected": params.from_addr,
                                  "actual": signer}
        if not from_ok:
            return reject(
                "solana fee-payer %s does not match required from %s"
                % (signer, params.from_addr)
            )

    try:
        idx = account_keys.index(params.to)
    except ValueError:
        idx = next(
            (i for i, k in enumerate(account_keys)
             if k.strip() == (params.to or "").strip()),
            -1,
        )
    if idx < 0:
        checks["recipient_matches"] = {
            "ok": False,
            "expected": params.to,
            "accounts_seen": account_keys,
        }
        return reject(
            "recipient %s is not an account in solana tx %s" % (params.to, signature)
        )
    delta = int(post[idx]) - int(pre[idx])
    checks["recipient_matches"] = {"ok": True, "expected": params.to, "index": idx}
    value_ok = delta >= params.min_value
    checks["min_value"] = {
        "ok": value_ok,
        "lamports_delta": str(delta),
        "min_value": str(params.min_value),
    }
    if not value_ok:
        return reject(
            "recipient %s gained %s lamports, below the mission minimum %s in tx %s"
            % (params.to, delta, params.min_value, signature)
        )
    detail = (
        "native SOL transfer of %s lamports to %s on solana confirmed in tx %s "
        "— verified" % (delta, params.to, signature)
    )
    return VerifyResult(verified=True, detail=detail, evidence=evidence)


def _solana_account_keys(tx: Mapping[str, Any]) -> List[str]:
    """Extract the ordered account-key list from a JSON-encoded Solana tx.

    Handles legacy (``message.accountKeys`` = list of base58 strings) and the
    common case where each key is a ``{"pubkey": ...}`` object. Falls back to an
    empty list if the structure is unexpected.
    """
    txn = tx.get("transaction")
    msg = None
    if isinstance(txn, Mapping):
        msg = txn.get("message")
    if not isinstance(msg, Mapping):
        return []
    keys = msg.get("accountKeys")
    out: List[str] = []
    if isinstance(keys, list):
        for k in keys:
            if isinstance(k, str):
                out.append(k)
            elif isinstance(k, Mapping) and isinstance(k.get("pubkey"), str):
                out.append(k["pubkey"])
    return out


def verify_mission(
    mission: Mapping[str, Any],
    proof: Any,
    *,
    client: Optional[RpcClient] = None,
) -> VerifyResult:
    """Convenience wrapper: verify a raw OABP mission dict + a proof.

    Reads ``verification_params`` straight off the mission object, so a resolver
    can pass the JSON it already has from ``GET /api/missions/{id}``.
    """
    if not isinstance(mission, Mapping):
        return VerifyResult(False, "mission is not an object", {})
    try:
        params = VerificationParams.from_mapping(mission.get("verification_params"))
    except ValueError as exc:
        return VerifyResult(
            False,
            "invalid verification_params: %s" % exc,
            {"error": str(exc)},
        )
    return verify(params, proof, client=client)


# =========================================================================== #
# Offline self-test (stubs the RPC; no network). Runs under --self-test.
# =========================================================================== #
def _padtopic(addr: str) -> str:
    """Left-zero-pad a 20-byte address to a 32-byte indexed topic."""
    h = addr.lower().replace("0x", "")
    return "0x" + ("0" * (64 - len(h))) + h


def _u256(n: int) -> str:
    return "0x" + format(n, "064x")


def _stub_transport(method_map: Dict[str, Any]):
    """Build an RpcClient transport returning canned results keyed by JSON-RPC method.

    ``method_map`` maps a method name (e.g. ``"eth_getTransactionByHash"``) to
    either a value (the ``result``) or a callable ``(params) -> result``. A
    method absent from the map returns ``result: null``. Returning the sentinel
    :data:`_RPC_ERR` makes the call raise (to exercise infra-error paths).
    """

    def transport(url: str, payload: bytes, timeout: float) -> Tuple[int, bytes]:
        req = json.loads(payload.decode("utf-8"))
        method = req.get("method")
        rid = req.get("id")
        params = req.get("params", [])
        if method in method_map:
            spec = method_map[method]
            result = spec(params) if callable(spec) else spec
        else:
            result = None
        if result is _RPC_ERR:
            body = json.dumps(
                {"jsonrpc": "2.0", "id": rid,
                 "error": {"code": -32000, "message": "stubbed error"}}
            ).encode("utf-8")
            return 200, body
        body = json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}).encode(
            "utf-8"
        )
        return 200, body

    return transport


_RPC_ERR = object()  # sentinel: stub returns a JSON-RPC error envelope


def _self_test(verbose: bool = False) -> None:
    """Assertions proving accept/reject behaviour against a stubbed chain."""

    def say(msg: str) -> None:
        if verbose:
            print(msg)

    # ---- chain normalisation -------------------------------------------- #
    assert normalize_chain("OP") == "optimism"
    assert normalize_chain("eth") == "ethereum"
    assert normalize_chain("Solana") == "solana"
    assert normalize_chain(" base ") == "base"
    for bad in ["", "polygon", "btc", "tron"]:
        try:
            normalize_chain(bad)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected ValueError for chain %r" % bad)

    # ---- proof parsing -------------------------------------------------- #
    H = "0x" + "ab" * 32
    assert parse_proof(H) == (H, None)
    assert parse_proof("base:" + H) == (H, "base")
    assert parse_proof("https://basescan.org/tx/" + H) == (H, "base")
    assert parse_proof("https://optimistic.etherscan.io/tx/" + H + "#eventlog") == (
        H,
        "optimism",
    )
    assert parse_proof("https://etherscan.io/tx/" + H) == (H, "ethereum")
    SIG = "5" + "K" * 60
    assert parse_proof("solana:" + SIG) == (SIG, "solana")
    assert parse_proof("https://solscan.io/tx/" + SIG + "?cluster=mainnet") == (
        SIG,
        "solana",
    )
    assert parse_proof({"chain": "base", "tx_hash": H}) == (H, "base")
    assert parse_proof('{"chain":"optimism","hash":"%s"}' % H) == (H, "optimism")
    for bad in ["", "   ", {}]:
        try:
            parse_proof(bad)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected ValueError for proof %r" % (bad,))

    # ---- transfer-topic constant ---------------------------------------- #
    assert TRANSFER_TOPIC0 == (
        "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    )
    assert len(TRANSFER_TOPIC0) == 66  # 0x + 64 hex

    TO = "0x000000000000000000000000000000000000dEaD"
    FROM = "0x1111111111111111111111111111111111111111"
    TOKEN = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"  # USDC on Base
    OTHER = "0x2222222222222222222222222222222222222222"

    # =================================================================== #
    # EVM tx_to — ACCEPT (mined, success, right recipient, value >= min)
    # =================================================================== #
    tx_ok = {
        "from": FROM,
        "to": TO,
        "value": _u256(20_000_000_000_000_000),  # 0.02 ETH
        "blockNumber": "0x10",
        "blockHash": "0x" + "cd" * 32,
        "input": "0x",
    }
    receipt_ok = {"status": "0x1", "contractAddress": None, "logs": []}
    base_methods = {
        "eth_getTransactionByHash": tx_ok,
        "eth_getTransactionReceipt": receipt_ok,
        "eth_blockNumber": "0x14",  # head 20, block 16 -> 5 confirmations
    }
    client = RpcClient(transport=_stub_transport(base_methods))
    p = VerificationParams.from_mapping(
        {
            "chain": "base",
            "kind": "tx_to",
            "to": TO,
            "min_value": "10000000000000000",  # 0.01 ETH
            "oracle_description": "send >= 0.01 ETH",
        }
    )
    r = verify(p, H, client=client)
    say("ACCEPT tx_to: " + r.detail)
    assert r.verified is True, r.detail
    assert r.evidence["checks"]["mined"]["confirmations"] == 5
    assert r.evidence["checks"]["succeeded"]["ok"] is True
    assert r.evidence["checks"]["recipient_matches"]["ok"] is True
    assert bool(r) is True
    json.dumps(r.to_dict())  # JSON-serialisable

    # tx_to ACCEPT with from constraint satisfied
    p_from = VerificationParams.from_mapping(
        {"chain": "base", "kind": "tx_to", "to": TO, "min_value": "0", "from": FROM}
    )
    assert verify(p_from, H, client=client).verified is True

    # ---- REJECT: reverted (status 0x0) ---------------------------------- #
    rev_methods = dict(base_methods)
    rev_methods["eth_getTransactionReceipt"] = {
        "status": "0x0", "contractAddress": None, "logs": []
    }
    rev_client = RpcClient(transport=_stub_transport(rev_methods))
    r_rev = verify(p, H, client=rev_client)
    say("REJECT reverted: " + r_rev.detail)
    assert r_rev.verified is False
    assert "did not succeed" in r_rev.detail
    assert r_rev.evidence["checks"]["succeeded"]["ok"] is False

    # ---- REJECT: tx missing (null) -------------------------------------- #
    miss_client = RpcClient(transport=_stub_transport({"eth_blockNumber": "0x14"}))
    r_miss = verify(p, H, client=miss_client)
    say("REJECT missing: " + r_miss.detail)
    assert r_miss.verified is False
    assert "not found" in r_miss.detail
    assert r_miss.evidence["checks"]["tx_found"]["ok"] is False

    # ---- REJECT: pending (no block) ------------------------------------- #
    pend_methods = dict(base_methods)
    pend_methods["eth_getTransactionByHash"] = {
        "from": FROM, "to": TO, "value": _u256(20_000_000_000_000_000),
        "blockNumber": None, "blockHash": None, "input": "0x",
    }
    pend_client = RpcClient(transport=_stub_transport(pend_methods))
    r_pend = verify(p, H, client=pend_client)
    say("REJECT pending: " + r_pend.detail)
    assert r_pend.verified is False
    assert "pending" in r_pend.detail
    assert r_pend.evidence["checks"]["mined"]["ok"] is False

    # ---- REJECT: too few confirmations ---------------------------------- #
    p_conf = VerificationParams.from_mapping(
        {"chain": "base", "kind": "tx_to", "to": TO, "min_confirmations": 10}
    )
    # head 0x14 (20), block 0x10 (16) -> 5 confirmations < 10
    r_conf = verify(p_conf, H, client=client)
    say("REJECT few-confs: " + r_conf.detail)
    assert r_conf.verified is False
    assert "requires 10" in r_conf.detail
    assert r_conf.evidence["checks"]["mined"]["confirmations"] == 5

    # ---- REJECT: wrong recipient ---------------------------------------- #
    p_other = VerificationParams.from_mapping(
        {"chain": "base", "kind": "tx_to", "to": OTHER, "min_value": "0"}
    )
    r_other = verify(p_other, H, client=client)
    assert r_other.verified is False
    assert "recipient" in r_other.detail
    assert r_other.evidence["checks"]["recipient_matches"]["ok"] is False

    # ---- REJECT: value below minimum ------------------------------------ #
    p_big = VerificationParams.from_mapping(
        {"chain": "base", "kind": "tx_to", "to": TO,
         "min_value": "1000000000000000000"}  # 1 ETH, tx only 0.02
    )
    r_big = verify(p_big, H, client=client)
    assert r_big.verified is False
    assert "below the mission minimum" in r_big.detail
    assert r_big.evidence["checks"]["min_value"]["ok"] is False

    # ---- REJECT: from mismatch ------------------------------------------ #
    p_wrongfrom = VerificationParams.from_mapping(
        {"chain": "base", "kind": "tx_to", "to": TO, "from": OTHER}
    )
    r_wrongfrom = verify(p_wrongfrom, H, client=client)
    assert r_wrongfrom.verified is False
    assert "sender" in r_wrongfrom.detail

    # ---- REJECT: bad proof shape for EVM -------------------------------- #
    r_badshape = verify(p, "not-a-hash", client=client)
    assert r_badshape.verified is False
    assert "not a valid" in r_badshape.detail

    # ---- REJECT: proof chain disagrees with mission chain --------------- #
    r_xchain = verify(p, "optimism:" + H, client=client)
    assert r_xchain.verified is False
    assert "settles on" in r_xchain.detail

    # ---- REJECT: RPC infra error (no verdict) --------------------------- #
    err_client = RpcClient(
        transport=_stub_transport({"eth_getTransactionByHash": _RPC_ERR,
                                   "eth_blockNumber": "0x14"})
    )
    r_err = verify(p, H, client=err_client)
    assert r_err.verified is False
    assert "could not query" in r_err.detail

    # =================================================================== #
    # EVM erc20_transfer — ACCEPT (Transfer log to TO for 2 USDC)
    # =================================================================== #
    transfer_log = {
        "address": TOKEN,
        "topics": [TRANSFER_TOPIC0, _padtopic(FROM), _padtopic(TO)],
        "data": _u256(2_000_000),  # 2 USDC (6 dp)
        "logIndex": "0x0",
    }
    erc_methods = {
        "eth_getTransactionByHash": {
            "from": FROM, "to": TOKEN,  # tx is TO the token contract
            "value": "0x0", "blockNumber": "0x10",
            "blockHash": "0x" + "cd" * 32, "input": "0xa9059cbb",
        },
        "eth_getTransactionReceipt": {
            "status": "0x1", "contractAddress": None, "logs": [transfer_log],
        },
        "eth_blockNumber": "0x20",
    }
    erc_client = RpcClient(transport=_stub_transport(erc_methods))
    p_erc = VerificationParams.from_mapping(
        {
            "chain": "base",
            "kind": "erc20_transfer",
            "token": TOKEN,
            "to": TO,
            "min_value": "1000000",  # 1 USDC
            "oracle_description": "transfer >= 1 USDC to dead address",
        }
    )
    r_erc = verify(p_erc, H, client=erc_client)
    say("ACCEPT erc20: " + r_erc.detail)
    assert r_erc.verified is True, r_erc.detail
    assert r_erc.evidence["checks"]["transfer_log_present"]["ok"] is True
    assert r_erc.evidence["checks"]["min_value"]["value"] == "2000000"
    assert r_erc.evidence["params"]["transfer_topic0"] == TRANSFER_TOPIC0

    # ---- REJECT erc20: amount below min --------------------------------- #
    p_erc_big = VerificationParams.from_mapping(
        {"chain": "base", "kind": "erc20_transfer", "token": TOKEN, "to": TO,
         "min_value": "5000000"}  # need 5 USDC, log only 2
    )
    r_erc_big = verify(p_erc_big, H, client=erc_client)
    assert r_erc_big.verified is False
    assert "below the mission minimum" in r_erc_big.detail

    # ---- REJECT erc20: transfer to a different recipient ---------------- #
    p_erc_other = VerificationParams.from_mapping(
        {"chain": "base", "kind": "erc20_transfer", "token": TOKEN, "to": OTHER}
    )
    r_erc_other = verify(p_erc_other, H, client=erc_client)
    assert r_erc_other.verified is False
    assert "none to required recipient" in r_erc_other.detail

    # ---- REJECT erc20: no Transfer log from the token ------------------- #
    no_log_methods = dict(erc_methods)
    no_log_methods["eth_getTransactionReceipt"] = {
        "status": "0x1", "contractAddress": None, "logs": [],
    }
    no_log_client = RpcClient(transport=_stub_transport(no_log_methods))
    r_nolog = verify(p_erc, H, client=no_log_client)
    assert r_nolog.verified is False
    assert "no ERC-20 Transfer log" in r_nolog.detail

    # ---- REJECT erc20: log present but WRONG topic0 (not a Transfer) ---- #
    wrong_topic_log = dict(transfer_log)
    wrong_topic_log["topics"] = ["0x" + "00" * 32, _padtopic(FROM), _padtopic(TO)]
    wrong_topic_methods = dict(erc_methods)
    wrong_topic_methods["eth_getTransactionReceipt"] = {
        "status": "0x1", "contractAddress": None, "logs": [wrong_topic_log],
    }
    wt_client = RpcClient(transport=_stub_transport(wrong_topic_methods))
    r_wt = verify(p_erc, H, client=wt_client)
    assert r_wt.verified is False
    assert "no ERC-20 Transfer log" in r_wt.detail  # topic didn't match

    # =================================================================== #
    # EVM contract_deploy — ACCEPT (to=null, contractAddress set)
    # =================================================================== #
    DEPLOYED = "0x3333333333333333333333333333333333333333"
    dep_methods = {
        "eth_getTransactionByHash": {
            "from": FROM, "to": None, "value": "0x0", "blockNumber": "0x10",
            "blockHash": "0x" + "cd" * 32, "input": "0x60806040",
        },
        "eth_getTransactionReceipt": {
            "status": "0x1", "contractAddress": DEPLOYED, "logs": [],
        },
        "eth_blockNumber": "0x20",
    }
    dep_client = RpcClient(transport=_stub_transport(dep_methods))
    p_dep = VerificationParams.from_mapping(
        {"chain": "ethereum", "kind": "contract_deploy"}
    )
    r_dep = verify(p_dep, H, client=dep_client)
    say("ACCEPT deploy: " + r_dep.detail)
    assert r_dep.verified is True, r_dep.detail
    assert r_dep.evidence["checks"]["is_contract_creation"]["ok"] is True

    # contract_deploy ACCEPT with expected address matching
    p_dep_addr = VerificationParams.from_mapping(
        {"chain": "ethereum", "kind": "contract_deploy", "to": DEPLOYED}
    )
    assert verify(p_dep_addr, H, client=dep_client).verified is True

    # ---- REJECT deploy: expected address mismatch ----------------------- #
    p_dep_wrong = VerificationParams.from_mapping(
        {"chain": "ethereum", "kind": "contract_deploy", "to": OTHER}
    )
    r_dep_wrong = verify(p_dep_wrong, H, client=dep_client)
    assert r_dep_wrong.verified is False
    assert "does not match expected address" in r_dep_wrong.detail

    # ---- REJECT deploy: not a creation (to is set) ---------------------- #
    notdep_client = RpcClient(transport=_stub_transport(base_methods))
    r_notdep = verify(p_dep, H, client=notdep_client)
    assert r_notdep.verified is False
    assert "not a contract creation" in r_notdep.detail

    # =================================================================== #
    # Params validation — malformed missions fail loudly
    # =================================================================== #
    for bad_params in [
        {},                                              # no chain
        {"chain": "base"},                               # no kind
        {"chain": "base", "kind": "frobnicate"},         # bad kind
        {"chain": "base", "kind": "tx_to"},              # tx_to needs 'to'
        {"chain": "base", "kind": "erc20_transfer", "to": TO},      # needs token
        {"chain": "base", "kind": "erc20_transfer", "token": TOKEN},  # needs to
        {"chain": "solana", "kind": "erc20_transfer", "token": TOKEN, "to": TO},  # EVM-only
        {"chain": "solana", "kind": "contract_deploy"},  # EVM-only
    ]:
        try:
            VerificationParams.from_mapping(bad_params)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected ValueError for params %r" % (bad_params,))

    # verify_mission surfaces a params error rather than raising
    bad_mission = {"verification_params": {"chain": "base"}}  # no kind
    rm_bad = verify_mission(bad_mission, H)
    assert rm_bad.verified is False
    assert "invalid verification_params" in rm_bad.detail

    # =================================================================== #
    # Solana tx_to — ACCEPT (recipient lamport delta >= min, no err)
    # =================================================================== #
    SOL_TO = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
    SOL_FROM = "4Nd1mYwHpTeJpYwYdQ5JqkVdFqZ8GqWpqXqB8wT1aaaa"
    sol_tx = {
        "slot": 1000,
        "transaction": {
            "message": {"accountKeys": [SOL_FROM, SOL_TO]},
        },
        "meta": {
            "err": None,
            "preBalances": [10_000_000_000, 1_000_000],
            "postBalances": [9_000_000_000, 1_000_000 + 50_000_000],  # +0.05 SOL
        },
    }
    sol_client = RpcClient(
        transport=_stub_transport({"getTransaction": sol_tx, "getSlot": 1005})
    )
    p_sol = VerificationParams.from_mapping(
        {"chain": "solana", "kind": "tx_to", "to": SOL_TO, "min_value": "10000000"}
    )
    r_sol = verify(p_sol, SIG, client=sol_client)
    say("ACCEPT solana: " + r_sol.detail)
    assert r_sol.verified is True, r_sol.detail
    assert r_sol.evidence["checks"]["min_value"]["lamports_delta"] == "50000000"

    # Solana ACCEPT with from (fee payer) constraint
    p_sol_from = VerificationParams.from_mapping(
        {"chain": "solana", "kind": "tx_to", "to": SOL_TO, "from": SOL_FROM}
    )
    assert verify(p_sol_from, SIG, client=sol_client).verified is True

    # ---- REJECT solana: failed tx (meta.err set) ------------------------ #
    sol_fail = dict(sol_tx)
    sol_fail = json.loads(json.dumps(sol_tx))  # deep copy
    sol_fail["meta"]["err"] = {"InstructionError": [0, "Custom"]}
    sol_fail_client = RpcClient(
        transport=_stub_transport({"getTransaction": sol_fail, "getSlot": 1005})
    )
    r_sol_fail = verify(p_sol, SIG, client=sol_fail_client)
    assert r_sol_fail.verified is False
    assert "failed" in r_sol_fail.detail

    # ---- REJECT solana: recipient gained too little --------------------- #
    p_sol_big = VerificationParams.from_mapping(
        {"chain": "solana", "kind": "tx_to", "to": SOL_TO,
         "min_value": "1000000000"}  # need 1 SOL, only got 0.05
    )
    r_sol_big = verify(p_sol_big, SIG, client=sol_client)
    assert r_sol_big.verified is False
    assert "below the mission minimum" in r_sol_big.detail

    # ---- REJECT solana: tx not found ------------------------------------ #
    sol_miss_client = RpcClient(transport=_stub_transport({"getSlot": 1005}))
    r_sol_miss = verify(p_sol, SIG, client=sol_miss_client)
    assert r_sol_miss.verified is False
    assert "not found" in r_sol_miss.detail

    # ---- REJECT solana: bad proof shape (EVM hash on solana) ------------ #
    r_sol_badshape = verify(p_sol, H, client=sol_client)  # 0x... not base58
    assert r_sol_badshape.verified is False
    assert "not a valid" in r_sol_badshape.detail

    # ---- verify_mission() happy path ------------------------------------ #
    mission = {
        "id": "mis_onchain_demo",
        "title": "Send 0.01 ETH to treasury on Base",
        "verification_type": "oracle",
        "verification_params": {
            "chain": "base",
            "kind": "tx_to",
            "to": TO,
            "min_value": "10000000000000000",
            "oracle_description": "send >= 0.01 ETH to 0x..dEaD on Base",
        },
    }
    r_mission = verify_mission(mission, H, client=client)
    assert r_mission.verified is True, r_mission.detail

    # ---- evidence is JSON-serialisable across all arms ------------------ #
    for res in (r, r_erc, r_dep, r_sol, r_rev, r_miss):
        json.dumps(res.to_dict())
        assert set(res.to_dict()) == {"verified", "detail", "evidence"}

    say("all self-test assertions passed")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="onchain_tx_verifier",
        description=(
            "OABP/AIGEN oracle verifier: confirm a required ON-CHAIN action "
            "occurred. Reads a public, read-only JSON-RPC endpoint to check a "
            "submitted tx hash is mined (>=1 confirmation), succeeded, and matches "
            "the mission constraints (recipient / native value / ERC-20 Transfer "
            "topic+amount / contract creation) on Base, Optimism, Ethereum, or "
            "Solana. Read-only; never signs; no key material; pure standard library."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--chain", help="base | optimism | ethereum | solana (aliases ok).")
    p.add_argument(
        "--kind",
        choices=_ALL_KINDS,
        help="tx_to | erc20_transfer | contract_deploy.",
    )
    p.add_argument("--proof", help="Submission proof: a tx hash (or chain:hash / URL).")
    p.add_argument("--to", default=None, help="Required recipient / expected deploy addr.")
    p.add_argument("--token", default=None, help="ERC-20 contract (erc20_transfer).")
    p.add_argument(
        "--min-value",
        default="0",
        help="Min native value (wei/lamports) or token base-units; int or 0x-hex.",
    )
    p.add_argument("--from-addr", default=None, dest="from_addr",
                   help="If set, the tx sender must equal this.")
    p.add_argument(
        "--min-confirmations", type=int, default=1,
        help="EVM confirmation depth required (>=1).",
    )
    p.add_argument(
        "--rpc-url", default=None,
        help="Override the JSON-RPC endpoint for this chain (else default/env).",
    )
    p.add_argument(
        "--json", action="store_true", help="Print the full VerifyResult as JSON."
    )
    p.add_argument(
        "--self-test", action="store_true",
        help="Run the offline self-test (stubs the RPC; no network) and exit.",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.self_test:
        try:
            _self_test(verbose=True)
        except AssertionError as exc:  # pragma: no cover
            sys.stderr.write("SELF-TEST FAILED: %s\n" % exc)
            return 2
        print("\nonchain-tx-verifier self-test: OK")
        return 0

    if not args.chain or not args.kind or not args.proof:
        sys.stderr.write(
            "ERROR: --chain, --kind and --proof are required (or use --self-test).\n"
        )
        return 2

    try:
        params = VerificationParams.from_mapping(
            {
                "chain": args.chain,
                "kind": args.kind,
                "to": args.to,
                "token": args.token,
                "min_value": args.min_value,
                "from": args.from_addr,
                "min_confirmations": args.min_confirmations,
                "rpc_url": args.rpc_url,
            }
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2

    client = RpcClient()
    try:
        result = verify(params, args.proof, client=client)
    except RpcError as exc:
        sys.stderr.write("RPC error: %s\n" % exc)
        return 3

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(("VERIFIED" if result.verified else "REJECTED") + ": " + result.detail)
    return 0 if result.verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
