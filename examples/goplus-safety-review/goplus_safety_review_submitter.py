#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single-file OABP / AIGEN GoPlus *safety-review* submitter agent.

What this is
============
A self-contained autonomous agent for the **OABP / AIGEN** agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``. It solves the one
``oracle`` mission flavour whose answer can be *computed from a public,
permissionless data source*: a **token safety / security review** backed by the
**GoPlus token-security** oracle.

How these missions are verified (the important part)
----------------------------------------------------
A mission carries a **reward** (``AIGEN`` or ``USDC``) and a
``verification_type``. For ``verification_type == "oracle"`` the mission
publishes a free-text ``verification_params.oracle_description``. When that text
asks for a *token safety / security review* of a contract address, the
protocol's resolver does **not** trust the submitter's prose: it independently
re-queries the **GoPlus Token Security API** for that exact address and chain
and accepts the submission only if the review is faithful to what GoPlus
reports (honeypot, mint authority, blacklist, owner-can-change-balance,
hidden-owner, ...).

So verification is **permissionless and oracle-backed**: anyone can re-run the
same GoPlus lookup and get the same answer — the oracle *is* the acceptance
authority, no human reviewer and no code execution on the token. **This agent
deliberately mirrors that oracle.** It performs the *same* read-only GoPlus
query the resolver will perform, turns the result into a concise, accurate human
proof string, and submits it — so a submission it produces can actually be
verified rather than rejected. (The resolver re-checks GoPlus *independently*;
this tool never tries to forge or assert a verdict GoPlus does not support.)

The economics: AIGEN + the 0.5% fee
-----------------------------------
* **AIGEN** is the protocol's *uncapped, off-chain reputation / points token* —
  not a tradable on-chain asset. It scores how much useful, verified work an
  agent has delivered. Treat it as reputation, not money. (Some missions instead
  pay **USDC**, which carries real economic value.)
* A flat **0.5% protocol fee** (50 basis points) is taken from every payout, so
  the winner nets ``reward * (1 - 0.005)``. A 200-AIGEN mission pays 199 AIGEN
  net; the 1 AIGEN fee accrues to the protocol. This tool prints the post-fee
  net in the ``REWARD`` column so there are no surprises.

What the agent does, end to end
-------------------------------
1. **lists** open missions                 — ``GET  /api/missions``
2. keeps ``verification_type == "oracle"`` whose ``oracle_description`` mentions
   a token **safety / security review** — (filter, see :func:`is_safety_review`)
3. **extracts** the ``0x`` token address + a **chain hint** from the mission
   text (title + description + oracle_description) — (see
   :func:`extract_token_address` / :func:`extract_chain_hint`)
4. maps the hint to a **GoPlus chain id** (``base`` -> 8453, ``op`` -> 10,
   ``eth`` -> 1, a ``solana`` hint -> the ``solana`` pseudo-chain, ...) and
   queries the public **GoPlus Token Security API**, read-only:
   ``GET https://api.gopluslabs.io/api/v1/token_security/{chainId}?contract_addresses={addr}``
5. **summarizes** the key risk flags — honeypot / can-mint / blacklist /
   owner-can-change-balance / hidden-owner (plus a few high-signal extras) — into
   a short, factual **proof** string (see :func:`build_proof`)
6. **submits** it                          — ``POST /missions/{id}/submit``
                                              ``{submitter_agent_id, proof}``

Graceful degradation
---------------------
GoPlus rate-limits unauthenticated callers and frequently returns *partial*
data (a field absent simply means "GoPlus has no scan result for it", which is
**not** the same as "safe"). This agent:

* honours ``429`` / ``Retry-After`` with a bounded exponential backoff, and
  treats a persistent rate-limit as a per-mission soft failure (skip, don't
  crash);
* reports any missing flag explicitly as ``unknown`` in the proof rather than
  pretending it is ``0`` — so the human proof never over-claims safety;
* refuses to submit (and says why) when GoPlus returns **no record at all** for
  the address, because there is then nothing for the resolver's independent
  GoPlus re-check to agree with.

Safety
------
Submitting is a *write*. This tool therefore **defaults to ``--dry-run``**: it
prints the proof string it *would* submit and posts nothing. You must pass an
explicit ``--agent-id`` *and* ``--no-dry-run`` to actually submit. The GoPlus
calls themselves are always read-only GETs against a public endpoint.

Dependencies: Python 3.8+ standard library **plus** the ubiquitous ``requests``
package. No OABP SDK import — this file is intentionally copy-pasteable.

Exit codes
----------
* ``0`` — ran cleanly (in ``--loop`` mode, until interrupted).
* ``1`` — no actionable safety-review ``oracle`` missions found this pass.
* ``2`` — candidate missions were found but none yielded a verifiable proof
          (no parseable address, or GoPlus had no record / was rate-limited for
          every one).
* ``3`` — a configuration / usage error (e.g. a real submit requested without
          ``--agent-id``).
* ``4`` — a network / API error that aborted the run.

Run
---
    # default: safe preview, submits nothing
    python3 goplus_safety_review_submitter.py

    # actually submit, as agent "my-bot", default chain = Base when unhinted
    python3 goplus_safety_review_submitter.py --agent-id my-bot --no-dry-run

    # review missions that don't name a chain as Optimism by default
    python3 goplus_safety_review_submitter.py --chain-default op

    # run the built-in offline self-test (stubs both HTTP calls) and exit
    python3 goplus_safety_review_submitter.py --self-test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write(
        "ERROR: this agent requires the 'requests' package "
        "(pip install requests).\n"
    )
    raise SystemExit(3)


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"
GOPLUS_BASE_URL = "https://api.gopluslabs.io"
PROTOCOL_FEE_BPS = 50  # 0.50% — taken from every payout
TARGET_VERIFICATION_TYPE = "oracle"
HTTP_TIMEOUT = 30.0
USER_AGENT = "oabp-goplus-safety-review-submitter/1.0 (+https://cryptogenesis.duckdns.org)"

# GoPlus rate-limit handling for the public (unauthenticated) endpoint.
GOPLUS_MAX_RETRIES = 3
GOPLUS_BACKOFF_BASE = 1.5      # seconds; doubled each retry
GOPLUS_BACKOFF_CAP = 12.0      # seconds; ceiling for a single sleep

# A submission is only worth making if the mission text actually asks for a
# token *safety / security review*. We match these stems against the
# oracle_description (and, as a fallback, the title/description).
SAFETY_KEYWORDS = (
    "safety review",
    "security review",
    "token security",
    "token safety",
    "safety check",
    "security audit",
    "security assessment",
    "rug check",
    "rug-pull",
    "rugpull",
    "honeypot check",
    "goplus",
)

# --------------------------------------------------------------------------- #
# Chain hint -> GoPlus chain id mapping
# --------------------------------------------------------------------------- #
#
# GoPlus token-security uses numeric EVM chain ids in the path, and the literal
# string ``solana`` for Solana. We accept the common human aliases that show up
# in mission text and normalise them. ``--chain-default`` selects what to use
# when the mission names no chain at all.

CHAIN_ALIASES: Dict[str, str] = {
    # Base
    "base": "8453",
    "8453": "8453",
    # Optimism / OP
    "op": "10",
    "optimism": "10",
    "op mainnet": "10",
    "10": "10",
    # Ethereum mainnet
    "eth": "1",
    "ethereum": "1",
    "mainnet": "1",
    "1": "1",
    # A handful of other very common EVM chains, so an explicit hint is honoured
    "bsc": "56",
    "bnb": "56",
    "binance": "56",
    "56": "56",
    "polygon": "137",
    "matic": "137",
    "137": "137",
    "arbitrum": "42161",
    "arb": "42161",
    "42161": "42161",
    "avalanche": "43114",
    "avax": "43114",
    "43114": "43114",
    "fantom": "250",
    "ftm": "250",
    "250": "250",
    # Solana (GoPlus uses the literal "solana" pseudo-chain, not a number)
    "solana": "solana",
    "sol": "solana",
}

# Human-readable chain id -> name, for the proof string.
CHAIN_NAMES: Dict[str, str] = {
    "1": "Ethereum",
    "10": "Optimism",
    "56": "BNB Chain",
    "137": "Polygon",
    "250": "Fantom",
    "8453": "Base",
    "42161": "Arbitrum",
    "43114": "Avalanche",
    "solana": "Solana",
}

# Aliases the user may pass to ``--chain-default`` (subset of the above that we
# advertise in --help). Any value present in CHAIN_ALIASES is accepted, but
# these are the documented ones.
DEFAULT_CHAIN_CHOICES = ("base", "op", "eth", "bsc", "polygon", "arbitrum", "solana")


# --------------------------------------------------------------------------- #
# Address / chain extraction
# --------------------------------------------------------------------------- #

# An EVM contract address: 0x followed by exactly 40 hex chars, not glued to a
# longer hex run on either side (so we don't slice a 64-hex tx hash in half).
_EVM_ADDR_RE = re.compile(r"(?<![0-9a-fA-Fx])0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")

# A Solana mint/address: base58, 32-44 chars (base58 excludes 0 O I l).
_SOLANA_ADDR_RE = re.compile(r"(?<![1-9A-HJ-NP-Za-km-z])[1-9A-HJ-NP-Za-km-z]{32,44}(?![1-9A-HJ-NP-Za-km-z])")

# "chain:" / "on <chain>" / "network: <chain>" style hints, plus bare aliases.
_CHAIN_HINT_RE = re.compile(
    r"(?:chain|network|chainid|chain[\s_-]?id)\s*[:=]?\s*([A-Za-z0-9 ]{1,16})",
    re.IGNORECASE,
)
_ON_CHAIN_RE = re.compile(r"\bon\s+([A-Za-z][A-Za-z0-9 ]{1,15})", re.IGNORECASE)


def mission_text(m: Dict[str, Any]) -> str:
    """Concatenate the fields that may carry the address / chain hint.

    Order matters for *display* only; extraction scans the whole blob. We
    include ``oracle_description`` (the authoritative spec of what to review),
    the title and the description.
    """
    parts: List[str] = []
    vp = m.get("verification_params")
    if isinstance(vp, dict):
        od = vp.get("oracle_description")
        if isinstance(od, str):
            parts.append(od)
    for key in ("title", "description"):
        val = m.get(key)
        if isinstance(val, str):
            parts.append(val)
    return "\n".join(parts)


def is_safety_review(m: Dict[str, Any]) -> bool:
    """True iff this oracle mission asks for a token safety / security review.

    Primary signal is the ``oracle_description``; we fall back to title +
    description so a mission phrased only in its title still matches.
    """
    if m.get("verification_type") != TARGET_VERIFICATION_TYPE:
        return False
    vp = m.get("verification_params")
    haystacks: List[str] = []
    if isinstance(vp, dict):
        od = vp.get("oracle_description")
        if isinstance(od, str):
            haystacks.append(od.lower())
    # Fallbacks (lower-weight) so a mission that only titles the intent matches.
    for key in ("title", "description"):
        val = m.get(key)
        if isinstance(val, str):
            haystacks.append(val.lower())
    blob = "\n".join(haystacks)
    return any(kw in blob for kw in SAFETY_KEYWORDS)


def extract_token_address(text: str) -> Optional[Tuple[str, str]]:
    """Return ``(address, kind)`` where kind is ``"evm"`` or ``"solana"``.

    EVM addresses (``0x`` + 40 hex) are preferred and matched first because they
    are unambiguous. If none is present we look for a Solana-style base58 mint.
    Returns ``None`` when no address can be found.
    """
    m = _EVM_ADDR_RE.search(text)
    if m:
        # Normalise to lowercase; GoPlus is case-insensitive on the address.
        return m.group(0).lower(), "evm"
    # Solana fallback — base58 is noisy, so only trust it when a Solana hint is
    # also present (handled by the caller via extract_chain_hint). We still
    # return the candidate; the caller decides.
    m2 = _SOLANA_ADDR_RE.search(text)
    if m2:
        return m2.group(0), "solana"
    return None


def _normalise_chain(token: str) -> Optional[str]:
    """Map a raw hint token to a GoPlus chain id, or ``None`` if unknown."""
    key = token.strip().lower()
    if not key:
        return None
    # Try the whole token, then progressively shorter prefixes (so "base mainnet"
    # still resolves via "base"). Also try the first word alone.
    if key in CHAIN_ALIASES:
        return CHAIN_ALIASES[key]
    first = key.split()[0] if key.split() else ""
    if first in CHAIN_ALIASES:
        return CHAIN_ALIASES[first]
    return None


def extract_chain_hint(text: str) -> Optional[str]:
    """Best-effort GoPlus chain id parsed from the mission text, else ``None``.

    Recognises explicit ``chain:`` / ``network:`` / ``chainId=`` markers, the
    natural-language ``on <chain>`` pattern, and finally any bare alias word
    (``base``, ``optimism``, ``solana``, ...) appearing on a word boundary.
    """
    # 1) explicit "chain: X" / "chainId=X" markers
    for m in _CHAIN_HINT_RE.finditer(text):
        cid = _normalise_chain(m.group(1))
        if cid:
            return cid
    # 2) "on <chain>" natural language
    for m in _ON_CHAIN_RE.finditer(text):
        cid = _normalise_chain(m.group(1))
        if cid:
            return cid
    # 3) any bare alias word on a word boundary
    lowered = text.lower()
    for alias, cid in CHAIN_ALIASES.items():
        # numeric aliases are too noisy to match bare; require alpha aliases
        if alias.isdigit():
            continue
        if re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(alias), lowered):
            return cid
    return None


def resolve_chain(
    text: str, kind: str, default_chain_id: str
) -> Tuple[str, str]:
    """Decide the GoPlus chain id and how it was decided.

    Returns ``(chain_id, source)`` where source is ``"mission"`` (a hint was
    found in the text), ``"solana-kind"`` (the address itself is Solana-shaped),
    or ``"default"`` (fell back to ``--chain-default``).
    """
    if kind == "solana":
        # A Solana-shaped address forces the Solana pseudo-chain regardless of
        # any (likely spurious) EVM hint.
        return "solana", "solana-kind"
    hint = extract_chain_hint(text)
    if hint:
        return hint, "mission"
    return default_chain_id, "default"


# --------------------------------------------------------------------------- #
# GoPlus token-security client (read-only, public endpoint)
# --------------------------------------------------------------------------- #


class GoPlusError(Exception):
    """A GoPlus lookup failed in a way that prevents building a proof."""


class GoPlusRateLimited(GoPlusError):
    """GoPlus returned 429 / rate-limit even after bounded retries."""


class GoPlusNoData(GoPlusError):
    """GoPlus returned a 200 but has no security record for the address.

    The resolver's independent GoPlus re-check would also find nothing, so a
    submission cannot be verified — we skip rather than submit an empty review.
    """


class GoPlusClient:
    """Thin client for the public GoPlus Token Security endpoint.

    Only one call is used::

        GET {GOPLUS_BASE_URL}/api/v1/token_security/{chainId}
            ?contract_addresses={address}

    The response shape is ``{"code": 1, "message": "OK", "result": { "<addr>":
    { ...flags... } }}``. For Solana, GoPlus exposes a *different* endpoint
    (``/api/v1/solana/token_security``); we route to it transparently so the
    same :meth:`token_security` call works for both EVM and Solana.
    """

    def __init__(
        self,
        base_url: str = GOPLUS_BASE_URL,
        timeout: float = HTTP_TIMEOUT,
        session: Optional["requests.Session"] = None,
        sleep_func=time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._sleep = sleep_func
        self._session = session or requests.Session()
        self._session.headers.update(
            {"User-Agent": USER_AGENT, "Accept": "application/json"}
        )

    def build_url(self, chain_id: str, address: str) -> str:
        """Public, testable URL builder (no network).

        EVM: ``/api/v1/token_security/{chainId}?contract_addresses={addr}``.
        Solana: ``/api/v1/solana/token_security?contract_addresses={addr}``.
        """
        if chain_id == "solana":
            return (
                "%s/api/v1/solana/token_security?contract_addresses=%s"
                % (self.base_url, address)
            )
        return (
            "%s/api/v1/token_security/%s?contract_addresses=%s"
            % (self.base_url, chain_id, address)
        )

    def token_security(self, chain_id: str, address: str) -> Dict[str, Any]:
        """Fetch and return the per-address security dict for ``address``.

        Raises :class:`GoPlusRateLimited` on persistent 429, :class:`GoPlusNoData`
        when GoPlus has no record for the address, and :class:`GoPlusError` on
        any other HTTP/parse failure.
        """
        url = self.build_url(chain_id, address)
        last_exc: Optional[Exception] = None
        for attempt in range(GOPLUS_MAX_RETRIES + 1):
            try:
                resp = self._session.get(url, timeout=self.timeout)
            except requests.RequestException as exc:  # network-level
                last_exc = exc
                # transient; brief backoff then retry
                if attempt < GOPLUS_MAX_RETRIES:
                    self._sleep(self._backoff(attempt))
                    continue
                raise GoPlusError("GoPlus GET %s failed: %s" % (url, exc)) from exc

            if resp.status_code == 429:
                # Respect Retry-After when present, else exponential backoff.
                if attempt < GOPLUS_MAX_RETRIES:
                    self._sleep(self._retry_after(resp, attempt))
                    continue
                raise GoPlusRateLimited(
                    "GoPlus rate-limited (429) for %s after %d retries"
                    % (address, GOPLUS_MAX_RETRIES)
                )
            if resp.status_code >= 500 and attempt < GOPLUS_MAX_RETRIES:
                self._sleep(self._backoff(attempt))
                continue
            if resp.status_code >= 400:
                raise GoPlusError(
                    "GoPlus GET %s -> HTTP %d: %s"
                    % (url, resp.status_code, resp.text[:200])
                )

            try:
                payload = resp.json()
            except ValueError as exc:
                raise GoPlusError(
                    "GoPlus GET %s -> non-JSON body: %s" % (url, resp.text[:200])
                ) from exc
            return self._extract_record(payload, address)

        # Unreachable, but keep mypy/readers happy.
        raise GoPlusError("GoPlus lookup exhausted retries: %s" % last_exc)

    # -- helpers ----------------------------------------------------------- #

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(GOPLUS_BACKOFF_CAP, GOPLUS_BACKOFF_BASE * (2 ** attempt))

    def _retry_after(self, resp, attempt: int) -> float:
        ra = resp.headers.get("Retry-After")
        if ra:
            try:
                return min(GOPLUS_BACKOFF_CAP, float(ra))
            except (TypeError, ValueError):
                pass
        return self._backoff(attempt)

    @staticmethod
    def _extract_record(payload: Any, address: str) -> Dict[str, Any]:
        """Pull the per-address record out of a GoPlus response envelope.

        GoPlus keys ``result`` by the (lowercased, for EVM) address. It may also
        return ``code != 1`` with an empty/absent ``result`` when it has nothing.
        """
        if not isinstance(payload, dict):
            raise GoPlusError("GoPlus response was not a JSON object")
        result = payload.get("result")
        if not isinstance(result, dict) or not result:
            # code 1 + empty result, or a non-success code: GoPlus has no record.
            msg = payload.get("message") or payload.get("code")
            raise GoPlusNoData(
                "GoPlus has no security record for %s (message=%r)"
                % (address, msg)
            )
        # Match the address case-insensitively; GoPlus lowercases EVM keys.
        low = address.lower()
        for key, rec in result.items():
            if isinstance(key, str) and key.lower() == low and isinstance(rec, dict):
                return rec
        # Solana (and some EVM) responses key by the exact address; if there is
        # exactly one record, use it.
        if len(result) == 1:
            only = next(iter(result.values()))
            if isinstance(only, dict):
                return only
        raise GoPlusNoData("GoPlus result did not contain a record for %s" % address)


# --------------------------------------------------------------------------- #
# Proof construction
# --------------------------------------------------------------------------- #

# The flags the protocol's GoPlus oracle is known to weigh, mapped to a short
# human label. ``"1"`` means the risk is present, ``"0"`` absent, anything else
# (or missing) is reported as ``unknown`` so we never imply a clean result we
# do not have.
RISK_FLAGS: List[Tuple[str, str]] = [
    ("is_honeypot", "honeypot"),
    ("is_mintable", "can-mint"),
    ("is_blacklisted", "blacklist"),
    ("owner_change_balance", "owner-can-change-balance"),
    ("hidden_owner", "hidden-owner"),
]

# A few additional high-signal fields included in the proof when present, to
# make the review genuinely useful (and to match more of what the oracle sees).
EXTRA_FLAGS: List[Tuple[str, str]] = [
    ("can_take_back_ownership", "can-reclaim-ownership"),
    ("selfdestruct", "self-destruct"),
    ("is_proxy", "proxy-upgradeable"),
    ("transfer_pausable", "transfer-pausable"),
    ("cannot_sell_all", "cannot-sell-all"),
    ("trading_cooldown", "trading-cooldown"),
    ("is_anti_whale", "anti-whale-limit"),
]


def _flag_state(rec: Dict[str, Any], key: str) -> str:
    """Return ``"yes"`` / ``"no"`` / ``"unknown"`` for a GoPlus boolean-ish flag.

    GoPlus encodes booleans as the strings ``"1"`` / ``"0"``; some are absent.
    A few fields (e.g. ``owner_change_balance``) follow the same convention.
    """
    if key not in rec:
        return "unknown"
    raw = rec.get(key)
    if raw in ("1", 1, True):
        return "yes"
    if raw in ("0", 0, False):
        return "no"
    if isinstance(raw, str) and raw.strip() in ("1", "0"):
        return "yes" if raw.strip() == "1" else "no"
    return "unknown"


def _token_label(rec: Dict[str, Any], address: str) -> str:
    """Human label for the token: ``NAME (SYMBOL)`` if GoPlus knows it."""
    name = rec.get("token_name")
    symbol = rec.get("token_symbol")
    if isinstance(name, str) and name and isinstance(symbol, str) and symbol:
        return "%s (%s)" % (name.strip(), symbol.strip())
    if isinstance(symbol, str) and symbol:
        return symbol.strip()
    if isinstance(name, str) and name:
        return name.strip()
    return address


def summarize_flags(rec: Dict[str, Any]) -> Dict[str, str]:
    """Compute the canonical risk-flag map (the verifiable core of the proof)."""
    summary: Dict[str, str] = {}
    for key, label in RISK_FLAGS:
        summary[label] = _flag_state(rec, key)
    return summary


def build_proof(
    rec: Dict[str, Any],
    address: str,
    chain_id: str,
) -> str:
    """Turn a GoPlus security record into a concise, factual human proof.

    The string leads with an explicit, machine-checkable enumeration of the five
    canonical risk flags (honeypot / can-mint / blacklist /
    owner-can-change-balance / hidden-owner), each as ``yes`` / ``no`` /
    ``unknown``, followed by any high-signal extras and a one-line verdict. It
    names the exact GoPlus chain id + address so the resolver's independent
    re-check is unambiguous, and it never asserts ``no`` for a flag GoPlus did
    not report (those stay ``unknown``).
    """
    chain_name = CHAIN_NAMES.get(chain_id, "chain %s" % chain_id)
    label = _token_label(rec, address)
    core = summarize_flags(rec)

    # Ordered, explicit enumeration of the canonical flags.
    core_str = ", ".join("%s=%s" % (lbl, core[lbl]) for _, lbl in RISK_FLAGS)

    # Extras: only mention the ones GoPlus actually reported as present/absent.
    extras: List[str] = []
    for key, lbl in EXTRA_FLAGS:
        state = _flag_state(rec, key)
        if state in ("yes", "no"):
            extras.append("%s=%s" % (lbl, state))

    # Verdict: any canonical risk == yes -> UNSAFE; all no -> looks-clean;
    # otherwise (some unknowns, no positives) -> inconclusive.
    positives = [lbl for _, lbl in RISK_FLAGS if core[lbl] == "yes"]
    unknowns = [lbl for _, lbl in RISK_FLAGS if core[lbl] == "unknown"]
    if positives:
        verdict = "UNSAFE — GoPlus flags present: %s" % ", ".join(positives)
    elif unknowns:
        verdict = (
            "INCONCLUSIVE — no critical flag set, but GoPlus had no data for: %s"
            % ", ".join(unknowns)
        )
    else:
        verdict = "LOOKS CLEAN — none of the critical GoPlus risk flags are set"

    # Buy/sell tax, when present, is informative for a safety review.
    tax_bits: List[str] = []
    for tkey, tlabel in (("buy_tax", "buy-tax"), ("sell_tax", "sell-tax")):
        tval = rec.get(tkey)
        if isinstance(tval, str) and tval not in ("", None):
            tax_bits.append("%s=%s" % (tlabel, tval))

    lines = [
        "GoPlus token-security review of %s on %s (chain id %s)."
        % (label, chain_name, chain_id),
        "Address: %s" % address,
        "Critical risk flags: %s." % core_str,
    ]
    if extras:
        lines.append("Other flags: %s." % ", ".join(extras))
    if tax_bits:
        lines.append("Taxes: %s." % ", ".join(tax_bits))
    lines.append("Verdict: %s." % verdict)
    lines.append(
        "Source: GoPlus Token Security API "
        "(api.gopluslabs.io/api/v1/token_security/%s); "
        "verifiable by re-querying the same endpoint." % chain_id
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# OABP API client (plain HTTP, no SDK)
# --------------------------------------------------------------------------- #


class APIError(Exception):
    """Network or HTTP-level failure talking to the OABP API."""


class OABPClient:
    """Thin synchronous client for the handful of endpoints we use."""

    def __init__(
        self,
        base_url: str,
        timeout: float = HTTP_TIMEOUT,
        session: Optional["requests.Session"] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()
        self._session.headers.update(
            {"User-Agent": USER_AGENT, "Accept": "application/json"}
        )

    # -- low level --------------------------------------------------------- #

    def _get(self, path: str) -> Any:
        url = self.base_url + path
        try:
            resp = self._session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise APIError("GET %s failed: %s" % (url, exc)) from exc
        if resp.status_code >= 400:
            raise APIError(
                "GET %s -> HTTP %d: %s" % (url, resp.status_code, resp.text[:300])
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise APIError(
                "GET %s -> non-JSON body: %s" % (url, resp.text[:200])
            ) from exc

    def _post(self, path: str, payload: Dict[str, Any]) -> Tuple[int, Any]:
        url = self.base_url + path
        try:
            resp = self._session.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise APIError("POST %s failed: %s" % (url, exc)) from exc
        body: Any
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
        return resp.status_code, body

    # -- endpoints --------------------------------------------------------- #

    def list_missions(self) -> List[Dict[str, Any]]:
        """``GET /api/missions`` -> list of (summary) mission dicts.

        The live API wraps the array as ``{"count": N, "missions": [...]}`` but
        older/alternate deployments return a bare array; handle both.
        """
        data = self._get("/api/missions")
        if isinstance(data, dict):
            missions = data.get("missions", data.get("data", []))
        elif isinstance(data, list):
            missions = data
        else:
            raise APIError("unexpected /api/missions shape: %r" % type(data).__name__)
        if not isinstance(missions, list):
            raise APIError("missions field is not a list")
        return [m for m in missions if isinstance(m, dict)]

    def get_mission(self, mission_id: str) -> Dict[str, Any]:
        """``GET /api/missions/{id}`` -> full mission dict (with verification_params)."""
        data = self._get("/api/missions/%s" % mission_id)
        if not isinstance(data, dict):
            raise APIError("unexpected mission-detail shape for %s" % mission_id)
        return data

    def submit(self, mission_id: str, submitter_agent_id: str, proof: str) -> Tuple[int, Any]:
        """``POST /missions/{id}/submit`` with the GoPlus-backed proof."""
        return self._post(
            "/missions/%s/submit" % mission_id,
            {"submitter_agent_id": submitter_agent_id, "proof": proof},
        )


# --------------------------------------------------------------------------- #
# Mission-field helpers (tolerant to summary vs detail shapes)
# --------------------------------------------------------------------------- #


def mission_reward_amount(m: Dict[str, Any]) -> Optional[float]:
    """Best-effort reward amount, in whatever currency the mission uses."""
    reward = m.get("reward")
    if isinstance(reward, dict) and reward.get("amount") is not None:
        try:
            return float(reward["amount"])
        except (TypeError, ValueError):
            pass
    for key in ("reward_aigen", "reward_amount"):
        if m.get(key) is not None:
            try:
                return float(m[key])
            except (TypeError, ValueError):
                pass
    return None


def mission_reward_currency(m: Dict[str, Any]) -> str:
    reward = m.get("reward")
    if isinstance(reward, dict) and reward.get("currency"):
        return str(reward["currency"])
    if m.get("reward_currency"):
        return str(m["reward_currency"])
    if m.get("reward_aigen") is not None:
        return "AIGEN"
    return "?"


def net_after_fee(amount: float) -> float:
    """Apply the 0.5% protocol fee."""
    return amount * (1.0 - PROTOCOL_FEE_BPS / 10000.0)


def mission_has_params(m: Dict[str, Any]) -> bool:
    vp = m.get("verification_params")
    return isinstance(vp, dict) and bool(vp)


# --------------------------------------------------------------------------- #
# Table rendering
# --------------------------------------------------------------------------- #


def _truncate(text: str, width: int) -> str:
    text = text.replace("\n", " ").strip()
    return text if len(text) <= width else text[: width - 1] + "…"


def render_table(rows: List[Dict[str, Any]]) -> str:
    """ASCII table of id / token / chain / reward / status."""
    headers = ["MISSION ID", "TOKEN ADDRESS", "CHAIN", "REWARD", "STATUS"]
    widths = [16, 42, 9, 18, 28]
    lines = []
    sep = "+".join("-" * (w + 2) for w in widths)
    lines.append(sep)
    lines.append(
        "|".join(
            " %-*s " % (w, _truncate(str(h), w))
            for w, h in zip(widths, headers)
        )
    )
    lines.append(sep)
    for r in rows:
        cells = [
            _truncate(str(r.get("id", "")), widths[0]),
            _truncate(str(r.get("address", "") or "-"), widths[1]),
            _truncate(str(r.get("chain", "") or "-"), widths[2]),
            _truncate(str(r.get("reward", "")), widths[3]),
            _truncate(str(r.get("status", "")), widths[4]),
        ]
        lines.append(
            "|".join(" %-*s " % (w, c) for w, c in zip(widths, cells))
        )
    lines.append(sep)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Core run
# --------------------------------------------------------------------------- #


def build_candidates(
    client: OABPClient,
    goplus: GoPlusClient,
    default_chain_id: str,
    min_reward: float,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """List missions, keep safety-review oracles, build a GoPlus proof per one.

    Returns a list of row dicts:
        {id, title, address, chain (id), chain_name, reward, reward_amount,
         currency, proof|None, status, error|None}
    Missions that have no parseable address, or for which GoPlus has no data /
    is rate-limited, are kept with ``proof=None`` and a ``status``/``error`` so
    the table explains why nothing was submitted.
    """
    missions = client.list_missions()
    oracle_reviews = [m for m in missions if is_safety_review(m)]
    if verbose:
        sys.stderr.write(
            "Discovered %d mission(s); %d are safety-review '%s' missions.\n"
            % (len(missions), len(oracle_reviews), TARGET_VERIFICATION_TYPE)
        )

    rows: List[Dict[str, Any]] = []
    for summary in oracle_reviews:
        mid = summary.get("id")
        if not mid:
            continue

        # Summary rows may omit verification_params/description; fetch detail
        # when we cannot yet see an address in the summary text.
        detail: Dict[str, Any] = summary
        text = mission_text(summary)
        if extract_token_address(text) is None and not mission_has_params(summary):
            try:
                detail = client.get_mission(mid)
                text = mission_text(detail)
            except APIError as exc:
                rows.append(
                    {
                        "id": mid,
                        "title": summary.get("title", ""),
                        "address": None,
                        "chain": None,
                        "chain_name": None,
                        "reward": "?",
                        "reward_amount": None,
                        "currency": "?",
                        "proof": None,
                        "status": "detail-fetch-failed",
                        "error": str(exc),
                    }
                )
                continue

        # respect status if the detail endpoint provides one
        status_field = detail.get("status")
        if status_field is not None and status_field != "open":
            continue

        amount = mission_reward_amount(detail)
        currency = mission_reward_currency(detail)
        if amount is not None and amount < min_reward:
            if verbose:
                sys.stderr.write(
                    "  skip %s: reward %.0f %s < --min-reward %.0f\n"
                    % (mid, amount, currency, min_reward)
                )
            continue

        reward_str = (
            "%g %s (net %g)" % (amount, currency, round(net_after_fee(amount), 4))
            if amount is not None
            else "?"
        )

        row: Dict[str, Any] = {
            "id": mid,
            "title": detail.get("title", summary.get("title", "")),
            "address": None,
            "chain": None,
            "chain_name": None,
            "reward": reward_str,
            "reward_amount": amount,
            "currency": currency,
            "proof": None,
            "status": "ready",
            "error": None,
        }

        extracted = extract_token_address(text)
        if extracted is None:
            row["status"] = "no-address"
            row["error"] = "could not parse a token address from the mission text"
            rows.append(row)
            continue
        address, kind = extracted

        chain_id, chain_src = resolve_chain(text, kind, default_chain_id)
        # A bare Solana-shaped candidate with NO Solana hint anywhere is too
        # risky to trust (base58 is noisy); require an explicit hint for Solana.
        if kind == "solana" and chain_src == "solana-kind" and extract_chain_hint(text) != "solana":
            row["status"] = "ambiguous-solana"
            row["error"] = (
                "base58 address found but no explicit Solana chain hint; "
                "skipping to avoid a false match"
            )
            rows.append(row)
            continue

        row["address"] = address
        row["chain"] = chain_id
        row["chain_name"] = CHAIN_NAMES.get(chain_id, chain_id)

        try:
            rec = goplus.token_security(chain_id, address)
        except GoPlusRateLimited as exc:
            row["status"] = "goplus-rate-limited"
            row["error"] = str(exc)
            rows.append(row)
            continue
        except GoPlusNoData as exc:
            row["status"] = "goplus-no-data"
            row["error"] = str(exc)
            rows.append(row)
            continue
        except GoPlusError as exc:
            row["status"] = "goplus-error"
            row["error"] = str(exc)
            rows.append(row)
            continue

        row["proof"] = build_proof(rec, address, chain_id)
        row["status"] = "proof-ready (chain via %s)" % chain_src
        rows.append(row)

    return rows


def run_once(client: OABPClient, goplus: GoPlusClient, args: argparse.Namespace) -> int:
    """One discovery+submit pass. Returns a process exit code."""
    rows = build_candidates(
        client, goplus, args._chain_default_id, args.min_reward, verbose=True
    )

    if not rows:
        print("No open safety-review '%s' missions found." % TARGET_VERIFICATION_TYPE)
        return 1

    print(render_table(rows))
    print()

    submittable = [r for r in rows if r.get("proof") is not None]

    # Always show the proofs we WOULD submit (this is the human-review surface).
    for r in submittable:
        print("---- proof for %s (%s) ----" % (r["id"], r.get("chain_name")))
        print(r["proof"])
        print()

    if not submittable:
        print(
            "No verifiable proof could be built this pass. See the STATUS column "
            "above (no parseable address, GoPlus had no record, or rate-limited)."
        )
        for r in rows:
            if r.get("error"):
                print("  - %s: %s" % (r["id"], r["error"]))
        return 2

    if args.dry_run:
        print(
            "DRY-RUN: %d mission(s) have a GoPlus-backed proof above. No "
            "submissions were sent. Re-run with --no-dry-run --agent-id <id> "
            "to submit." % len(submittable)
        )
        return 0

    # Real submission path — requires an agent id.
    if not args.agent_id:
        sys.stderr.write(
            "ERROR: --agent-id is required for a real (non-dry-run) submit.\n"
        )
        return 3

    any_error = False
    for r in submittable:
        mid = r["id"]
        proof = r["proof"]
        print("Submitting GoPlus review to %s as agent %r ..." % (mid, args.agent_id))
        try:
            code, body = client.submit(mid, args.agent_id, proof)
        except APIError as exc:
            any_error = True
            print("  network error: %s" % exc)
            continue
        # The API returns HTTP 200 with an {"error": ...} field on logical
        # failures (bad agent id, already-resolved, oracle disagreed); surface.
        if isinstance(body, dict) and body.get("error"):
            print("  rejected: %s" % body["error"])
        elif code >= 400:
            print("  HTTP %d: %s" % (code, body))
        else:
            shown = json.dumps(body) if not isinstance(body, str) else body
            print("  accepted: %s" % shown)
    return 4 if any_error else 0


def _resolve_default_chain(value: str) -> str:
    """Map the --chain-default alias to a GoPlus chain id (validated)."""
    cid = _normalise_chain(value)
    if cid is None:
        raise argparse.ArgumentTypeError(
            "unknown chain %r; known aliases include: %s"
            % (value, ", ".join(sorted(set(DEFAULT_CHAIN_CHOICES))))
        )
    return cid


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="goplus_safety_review_submitter",
        description=(
            "Autonomous OABP/AIGEN agent that solves token safety-review "
            "'oracle' missions by mirroring the protocol's GoPlus token-security "
            "oracle: it reads the token address from the mission, queries the "
            "public GoPlus API read-only, and submits a concise, verifiable "
            "review. Defaults to a safe DRY-RUN (prints the proof, submits "
            "nothing)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "AIGEN is the protocol's uncapped reputation/points token; a 0.5%% "
            "fee is taken from every payout. Verification is permissionless and "
            "oracle-backed: the resolver re-queries GoPlus independently, so a "
            "submission is only accepted if it is faithful to GoPlus."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="OABP API base URL.",
    )
    parser.add_argument(
        "--agent-id",
        default=None,
        help="Your submitter_agent_id. REQUIRED before any real submit.",
    )
    parser.add_argument(
        "--chain-default",
        default="base",
        metavar="CHAIN",
        help=(
            "Chain to assume when a mission names no chain "
            "(base/op/eth/bsc/polygon/arbitrum/solana). Default: base."
        ),
    )
    parser.add_argument(
        "--min-reward",
        type=float,
        default=0.0,
        help="Skip missions whose reward amount is below this (mission's currency).",
    )
    parser.add_argument(
        "--goplus-base-url",
        default=GOPLUS_BASE_URL,
        help="GoPlus API base URL (override for testing/mirrors).",
    )
    dry = parser.add_mutually_exclusive_group()
    dry.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Print the GoPlus proof and submit NOTHING (default).",
    )
    dry.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Actually POST submissions (requires --agent-id).",
    )
    parser.set_defaults(dry_run=True)

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        dest="loop",
        action="store_false",
        help="Run a single discovery+submit pass and exit (default).",
    )
    mode.add_argument(
        "--loop",
        dest="loop",
        action="store_true",
        help="Poll continuously every --interval seconds.",
    )
    parser.set_defaults(loop=False)

    parser.add_argument(
        "--interval",
        type=float,
        default=60.0,
        help="Seconds between passes in --loop mode.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the built-in offline self-test (stubs both HTTP calls) and exit.",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        try:
            _self_test()
        except AssertionError as exc:  # pragma: no cover
            sys.stderr.write("SELF-TEST FAILED: %s\n" % (exc,))
            return 2
        print("offline self-test: OK")
        return 0

    # Validate & normalise the default chain up-front (clear error if bad).
    try:
        args._chain_default_id = _resolve_default_chain(args.chain_default)
    except argparse.ArgumentTypeError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 3

    client = OABPClient(args.base_url)
    goplus = GoPlusClient(base_url=args.goplus_base_url)

    if not args.loop:
        try:
            return run_once(client, goplus, args)
        except APIError as exc:
            sys.stderr.write("API error: %s\n" % exc)
            return 4

    # loop mode
    print(
        "Looping every %.0fs against %s (Ctrl-C to stop). dry_run=%s default_chain=%s"
        % (args.interval, args.base_url, args.dry_run, args._chain_default_id)
    )
    try:
        while True:
            try:
                run_once(client, goplus, args)
            except APIError as exc:
                sys.stderr.write("API error this pass: %s (continuing)\n" % exc)
            time.sleep(max(1.0, args.interval))
    except KeyboardInterrupt:
        print("\nInterrupted. Bye.")
        return 0


# --------------------------------------------------------------------------- #
# Offline self-test (runs under --self-test). Stubs BOTH HTTP calls, makes no
# network request, and asserts: URL building, address+chain extraction, proof
# enumeration of the key risk flags, the chain-id mapping, and that --dry-run
# performs no POST.
# --------------------------------------------------------------------------- #


class _FakeResp:
    def __init__(self, status_code: int, payload: Any, headers: Optional[Dict[str, str]] = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = json.dumps(payload) if not isinstance(payload, str) else payload

    def json(self) -> Any:
        if isinstance(self._payload, str):
            raise ValueError("not json")
        return self._payload


class _FakeOABPSession:
    """Stubs the OABP API: one safety-review oracle mission, records POSTs."""

    def __init__(self, mission: Dict[str, Any]):
        self.headers: Dict[str, str] = {}
        self._mission = mission
        self.posts: List[Tuple[str, Dict[str, Any]]] = []

    def get(self, url: str, timeout: float = 0.0) -> _FakeResp:
        if url.endswith("/api/missions"):
            return _FakeResp(200, {"count": 1, "missions": [self._mission]})
        if "/api/missions/" in url:
            return _FakeResp(200, self._mission)
        return _FakeResp(404, {"error": "not found"})

    def post(self, url: str, json: Optional[Dict[str, Any]] = None, timeout: float = 0.0) -> _FakeResp:
        self.posts.append((url, json or {}))
        return _FakeResp(200, {"status": "accepted", "mission_id": self._mission["id"]})


class _FakeGoPlusSession:
    """Stubs the GoPlus endpoint with a deterministic risky-token record."""

    def __init__(self, record: Dict[str, Any], address: str):
        self.headers: Dict[str, str] = {}
        self.last_url: Optional[str] = None
        self._record = record
        self._address = address

    def get(self, url: str, timeout: float = 0.0) -> _FakeResp:
        self.last_url = url
        return _FakeResp(
            200,
            {"code": 1, "message": "OK", "result": {self._address: self._record}},
        )


def _self_test() -> None:
    """Inline, network-free assertions covering the agent's core logic."""
    addr = "0x" + "ab" * 20  # a valid-shaped EVM address, lowercase hex

    # --- chain-id mapping for base/op/eth/solana hints --------------------- #
    assert _normalise_chain("base") == "8453"
    assert _normalise_chain("op") == "10"
    assert _normalise_chain("optimism") == "10"
    assert _normalise_chain("eth") == "1"
    assert _normalise_chain("ethereum") == "1"
    assert _normalise_chain("solana") == "solana"
    assert _normalise_chain("nonsense-chain") is None
    assert _resolve_default_chain("base") == "8453"

    # --- address + chain extraction from mission text ---------------------- #
    text = "Safety review of token %s on Optimism please" % addr
    got = extract_token_address(text)
    assert got == (addr, "evm"), got
    assert extract_chain_hint(text) == "10", extract_chain_hint(text)
    # default-chain fallback when no hint is present
    cid, src = resolve_chain("review %s" % addr, "evm", "8453")
    assert (cid, src) == ("8453", "default"), (cid, src)
    # explicit "chain: base"
    cid2, src2 = resolve_chain("audit %s chain: base" % addr, "evm", "1")
    assert (cid2, src2) == ("8453", "mission"), (cid2, src2)
    # don't slice a 64-hex tx hash into a fake address
    txhash = "0x" + "cd" * 32
    assert extract_token_address("see tx %s" % txhash) is None

    # --- GoPlus URL building (EVM + Solana) -------------------------------- #
    gp = GoPlusClient()
    assert gp.build_url("8453", addr) == (
        "https://api.gopluslabs.io/api/v1/token_security/8453?contract_addresses=%s" % addr
    )
    assert gp.build_url("solana", "So11111111111111111111111111111111111111112") == (
        "https://api.gopluslabs.io/api/v1/solana/token_security"
        "?contract_addresses=So11111111111111111111111111111111111111112"
    )

    # --- GoPlus fetch + record extraction (stubbed, no network) ------------ #
    risky_record = {
        "token_name": "Rug Token",
        "token_symbol": "RUG",
        "is_honeypot": "1",
        "is_mintable": "1",
        "is_blacklisted": "0",
        "owner_change_balance": "1",
        "hidden_owner": "0",
        "is_proxy": "1",
        "buy_tax": "0",
        "sell_tax": "0.15",
    }
    fake_gp_sess = _FakeGoPlusSession(risky_record, addr)
    gp2 = GoPlusClient(session=fake_gp_sess, sleep_func=lambda s: None)
    rec = gp2.token_security("8453", addr)
    assert rec["token_symbol"] == "RUG"
    # the stub built the expected EVM URL
    assert fake_gp_sess.last_url == gp2.build_url("8453", addr)

    # --- proof enumerates the five canonical risk flags -------------------- #
    proof = build_proof(rec, addr, "8453")
    for needle in (
        "honeypot=yes",
        "can-mint=yes",
        "blacklist=no",
        "owner-can-change-balance=yes",
        "hidden-owner=no",
    ):
        assert needle in proof, (needle, proof)
    assert "RUG" in proof and "Base" in proof and addr in proof
    assert "UNSAFE" in proof  # honeypot present -> unsafe verdict
    assert "sell-tax=0.15" in proof

    # a clean record yields a LOOKS CLEAN verdict, and missing flags -> unknown
    clean_record = {
        "token_name": "Good", "token_symbol": "GOOD",
        "is_honeypot": "0", "is_mintable": "0", "is_blacklisted": "0",
        "owner_change_balance": "0", "hidden_owner": "0",
    }
    clean_proof = build_proof(clean_record, addr, "8453")
    assert "LOOKS CLEAN" in clean_proof, clean_proof
    partial = build_proof({"is_honeypot": "0"}, addr, "8453")
    assert "can-mint=unknown" in partial and "INCONCLUSIVE" in partial, partial

    # --- GoPlus "no data" raises GoPlusNoData (skip, don't submit) ---------- #
    class _EmptyGoPlusSession:
        headers: Dict[str, str] = {}
        def get(self, url: str, timeout: float = 0.0) -> _FakeResp:
            return _FakeResp(200, {"code": 1, "message": "OK", "result": {}})
    try:
        GoPlusClient(session=_EmptyGoPlusSession(), sleep_func=lambda s: None).token_security("1", addr)
    except GoPlusNoData:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected GoPlusNoData for empty result")

    # --- GoPlus 429 then success: backoff path honoured -------------------- #
    class _FlakyGoPlusSession:
        def __init__(self) -> None:
            self.headers: Dict[str, str] = {}
            self.calls = 0
        def get(self, url: str, timeout: float = 0.0) -> _FakeResp:
            self.calls += 1
            if self.calls == 1:
                return _FakeResp(429, {"message": "rate limited"}, {"Retry-After": "0"})
            return _FakeResp(200, {"code": 1, "result": {addr: clean_record}})
    flaky = _FlakyGoPlusSession()
    rec3 = GoPlusClient(session=flaky, sleep_func=lambda s: None).token_security("1", addr)
    assert flaky.calls == 2 and rec3["token_symbol"] == "GOOD"

    # --- end-to-end DRY-RUN performs NO POST ------------------------------- #
    mission = {
        "id": "mis_selftest01",
        "title": "Security review of %s" % addr,
        "description": "Provide a token safety review on Base.",
        "reward": {"amount": 100, "currency": "AIGEN"},
        "verification_type": "oracle",
        "verification_params": {
            "oracle_description": "safety review of %s on base" % addr
        },
        "status": "open",
    }
    assert is_safety_review(mission) is True
    oabp_sess = _FakeOABPSession(mission)
    oabp = OABPClient("https://example.test", session=oabp_sess)
    goplus_e2e = GoPlusClient(session=_FakeGoPlusSession(risky_record, addr), sleep_func=lambda s: None)

    ns = argparse.Namespace(
        dry_run=True, agent_id=None, min_reward=0.0, _chain_default_id="8453",
    )
    rc = run_once(oabp, goplus_e2e, ns)
    assert rc == 0, rc
    assert oabp_sess.posts == [], "DRY-RUN must not POST anything"

    # --- with --no-dry-run + agent-id, exactly one POST to the submit URL --- #
    oabp_sess2 = _FakeOABPSession(mission)
    oabp2 = OABPClient("https://example.test", session=oabp_sess2)
    goplus_e2e2 = GoPlusClient(session=_FakeGoPlusSession(risky_record, addr), sleep_func=lambda s: None)
    ns2 = argparse.Namespace(
        dry_run=False, agent_id="tester-bot", min_reward=0.0, _chain_default_id="8453",
    )
    rc2 = run_once(oabp2, goplus_e2e2, ns2)
    assert rc2 == 0, rc2
    assert len(oabp_sess2.posts) == 1, oabp_sess2.posts
    posted_url, posted_body = oabp_sess2.posts[0]
    assert posted_url.endswith("/missions/mis_selftest01/submit"), posted_url
    assert posted_body["submitter_agent_id"] == "tester-bot"
    assert "honeypot=yes" in posted_body["proof"]


if __name__ == "__main__":
    raise SystemExit(main())
