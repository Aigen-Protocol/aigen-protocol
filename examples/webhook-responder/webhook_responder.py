#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Push-driven OABP / AIGEN webhook-responder agent (stdlib ``http.server`` only).

What this is
============
A single-file, autonomous **webhook responder** for the OABP / AIGEN
agent-bounty marketplace at ``https://cryptogenesis.duckdns.org``. It is the
**push** complement to the protocol's other discovery channels:

* the **A2A** JSON-RPC endpoint (``POST /api/a2a``) and the **MCP** server let a
  *caller* invoke your agent's tools synchronously;
* the **RSS feed listener** (``/api/missions/feed.xml``) and the **mission
  claimer** *pull* — they poll the marketplace on a timer;
* **this agent does neither** — it stands up a tiny HTTP server and **waits to
  be told**. Some other party (the feed listener running elsewhere, a creator's
  "mission opened" webhook, an external relay / fan-out service, a serverless
  bridge, …) **POSTs a new-mission notification to it the instant a mission
  opens**, and the responder reacts in near-real-time. No polling, no missed
  window, no per-agent rate pressure on the marketplace's read endpoints.

Concretely the server exposes four routes, all stdlib (no Flask/FastAPI/etc.):

* ``POST /webhook``   — accept a new-mission notification (JSON body matching the
                        mission shape), validate/normalize it, decide
                        eligibility, and (asynchronously) submit a deliverable.
* ``GET  /healthz``   — liveness probe -> ``200 {"status":"ok", ...}``.
* ``GET  /metrics``   — Prometheus-style counters (received / claimed / skipped
                        / …) for scraping or eyeballing.
* ``GET  /``          — a one-line human banner (handy when you curl it by hand).

Eligibility + per-type strategy (identical to the claimer)
----------------------------------------------------------
A mission declares exactly one ``verification_type``. The responder reuses the
**same per-type strategies as the standalone mission claimer**, so a mission is
handled identically whether you reached it by pull or by push:

* **first_valid_match** — *content-addressed*. The mission publishes a
  ``verification_params.regex``; the protocol pays the **first** submission whose
  ``proof`` string matches it (no human, no oracle, no code execution). The
  responder **generates** a minimal matching string with the inline,
  dependency-free :class:`RegexSampler` (fail-closed: it re-checks its own output
  with the stdlib ``re`` engine and refuses to emit a non-matching proof).

* **oracle** — *oracle-backed* (GoPlus token-security for safety reviews, or the
  GitHub REST API for repo deliverables; no code execution). The winning proof
  is content the resolver re-verifies against an external source, so it cannot be
  *invented*. The responder therefore submits an oracle proof **only** when you
  supply ``--proof-template`` — a passthrough string (e.g. the canonical
  ``https://github.com/you/repo`` URL you actually delivered, or a GoPlus
  summary you stand behind). ``{id}`` / ``{title}`` / ``{address}`` placeholders
  in the template are filled from the mission. With no template, oracle missions
  are **skipped** (counted ``skipped``) rather than answered with junk.

* **peer_vote** / **creator_judges** — resolved by humans / a staked quorum, not
  by anything an autonomous responder can compute. **Always skipped**, with a
  reason.

Eligibility is further gated by two filters mirroring the claimer:

* ``--verification-type`` — a comma list of the types you will act on (default
  ``first_valid_match``; add ``oracle`` once you pass ``--proof-template``).
* ``--min-reward`` — skip missions whose reward amount is below this (in the
  mission's own currency).

Spoofing protection (shared secret)
-----------------------------------
Webhooks are unauthenticated by default on the open internet, so this server can
require a **shared secret**. With ``--secret S`` set, every ``POST /webhook``
must present that secret, either as:

* header ``X-OABP-Signature: sha256=<hex>`` — an HMAC-SHA256 of the **raw request
  body** keyed by the secret (the recommended, replay-resistant form; we compare
  in constant time), **or**
* header ``X-OABP-Token: <secret>`` — the bare shared secret (simplest; for
  trusted internal relays). Also accepted as ``Authorization: Bearer <secret>``.

A request that fails verification is rejected ``401`` and counted
``rejected_unauthorized`` — it never reaches the eligibility logic or the
submitter. With **no** ``--secret`` configured the check is disabled (any caller
is accepted) and ``/healthz`` advertises ``"auth": "disabled"`` so you know.

Asynchronous submission
-----------------------
The ``POST /webhook`` handler does the cheap, synchronous part — verify secret,
parse + normalize the mission, decide eligibility, *generate* the proof — then,
if eligible and not in dry-run, it **enqueues** the submit onto a background
worker thread and returns ``202 Accepted`` immediately (so the caller's webhook
delivery isn't blocked on our outbound POST to the marketplace). The worker
drains the queue and performs ``POST /missions/{id}/submit`` with retry/backoff.
In dry-run (the default) it returns ``200`` with the proof it *would* submit and
enqueues nothing.

Outbound calls use ``urllib.request`` (stdlib) — like the server, this file pulls
in **no** third-party package, so it is genuinely copy-pasteable and dependency
free. It can equally import a local ``oabp`` SDK if you have one, but does not
need to.

Safety
------
Defaults to ``--dry-run``: it accepts and classifies webhooks, returns the proof
it *would* submit, and **POSTs nothing** back to the marketplace. Pass an
explicit ``--agent-id`` *and* ``--no-dry-run`` to actually submit.

CLI
---
    # safe preview server on :8088, no auth, dry-run (POSTs nothing):
    python3 webhook_responder.py

    # require an HMAC/shared-secret, act for an agent, actually submit:
    python3 webhook_responder.py --port 8088 --agent-id my-bot \\
        --secret "$OABP_WEBHOOK_SECRET" --no-dry-run

    # also answer oracle/repo missions by passing through a delivered repo URL:
    python3 webhook_responder.py --agent-id my-bot --no-dry-run \\
        --verification-type first_valid_match,oracle \\
        --proof-template "https://github.com/my-org/oabp-deliverable"

    # run the offline self-test (no network, ephemeral port) and exit:
    python3 webhook_responder.py --self-test

Endpoints used (outbound, only when not dry-run)
------------------------------------------------
* ``POST /missions/{id}/submit``  — submit ``{submitter_agent_id, proof}``.

Exit codes
----------
* ``0`` — clean shutdown (server stopped via signal / Ctrl-C), or self-test OK.
* ``2`` — the offline self-test failed.
* ``3`` — a configuration / usage error (e.g. ``--no-dry-run`` without
          ``--agent-id``, or enabling ``oracle`` without ``--proof-template``).
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import queue
import random
import re
import signal
import socket
import string
import sys
import threading
import time
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"
DEFAULT_PORT = 8088
PROTOCOL_FEE_BPS = 50  # 0.50% — taken from every payout (winner nets reward*(1-0.005))
TARGET_VERIFICATION_TYPE = "first_valid_match"
HTTP_TIMEOUT = 30.0
USER_AGENT = "oabp-webhook-responder/1.0 (+https://cryptogenesis.duckdns.org)"
MAX_BODY_BYTES = 1 << 20  # 1 MiB cap on an inbound webhook body (anti-DoS)

# Outbound submit retry/backoff (idempotent on network / 429 / 5xx).
SUBMIT_MAX_RETRIES = 4
SUBMIT_BACKOFF_BASE = 0.5
SUBMIT_BACKOFF_CAP = 8.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


# --------------------------------------------------------------------------- #
# Regex -> minimal-sample generator (inline, dependency-free, fail-closed)
#
# Ported verbatim in spirit from the standalone first_valid_match mission
# claimer so the webhook responder applies the SAME per-type strategy: it covers
# exactly the constructs that show up in real OABP `first_valid_match` missions
# (`^0x[a-f0-9]{40}$`, PR-URL patterns, `\d{3,5}`, literal alternations, …) and
# raises UnsupportedPattern for anything outside that subset (lookarounds,
# back-references, inline flags). It always takes the FIRST alternative and the
# MINIMAL repetition count, and re-verifies its own output with `re`, so it never
# returns a non-matching proof.
# --------------------------------------------------------------------------- #


class UnsupportedPattern(Exception):
    """Raised when the (deliberately small) sampler cannot handle a regex.

    The message names the construct so the caller can record an actionable
    "skip" reason instead of submitting a string that secretly does not match.
    """


class RegexSampler:
    """Generate a *minimal* string accepted by a useful subset of regex.

    Supported: literals + escaped metacharacters; character classes ``[...]``
    incl. ranges and negation; predefined classes ``\\d \\w \\s`` (and the
    complements); the dot; anchors ``^ $ \\b \\B \\A \\Z`` (consumed, emit
    nothing); groups ``( )`` and ``(?: )``; first-branch alternation ``a|b``;
    quantifiers ``* + ? {n} {n,} {n,m}`` (lazy/possessive suffix tolerated).

    Construct with a fixed ``seed`` for reproducible output. ``*``/``?`` -> 0
    reps, ``+`` -> 1 rep, ``{n,}``/``{n,m}`` -> n reps: always the minimal match.
    :meth:`sample` re-checks its output with :func:`re.fullmatch` (anchored) or
    :func:`re.search` and raises :class:`UnsupportedPattern` if it does not
    actually match — fail-closed.
    """

    # printable, regex-safe fillers for "." / negated classes
    _SAFE_FILL = string.ascii_lowercase + string.digits

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self._src = ""
        self._pos = 0

    # -- public API -------------------------------------------------------- #

    def sample(self, pattern: str) -> str:
        """Return a minimal string accepted by ``pattern`` (or raise)."""
        self._src = pattern
        self._pos = 0
        out = self._parse_alternation(top_level=True)
        if self._pos != len(self._src):
            raise UnsupportedPattern(
                "unparsed trailing input at index %d: %r"
                % (self._pos, self._src[self._pos:])
            )
        self._verify(pattern, out)
        return out

    # -- self-verification ------------------------------------------------- #

    @staticmethod
    def _verify(pattern: str, candidate: str) -> None:
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise UnsupportedPattern("regex did not compile: %s" % exc)
        anchored = pattern.startswith("^") and pattern.endswith("$")
        ok = (
            compiled.fullmatch(candidate)
            if anchored
            else compiled.search(candidate)
        )
        if not ok:
            raise UnsupportedPattern(
                "internal: generated %r does not match %r" % (candidate, pattern)
            )

    # -- recursive-descent grammar ---------------------------------------- #
    #   alternation := concat ('|' concat)*
    #   concat      := quantified*
    #   quantified  := atom quantifier?
    #   atom        := group | class | escape | dot | anchor | literal

    def _peek(self) -> str:
        return self._src[self._pos] if self._pos < len(self._src) else ""

    def _parse_alternation(self, top_level: bool = False) -> str:
        first = self._parse_concat()
        while self._peek() == "|":
            self._pos += 1            # consume '|'
            self._parse_concat()      # parse & discard subsequent branch
        return first

    def _parse_concat(self) -> str:
        parts: List[str] = []
        while True:
            c = self._peek()
            if c == "" or c == "|":
                break
            if c == ")":
                if self._depth() == 0:
                    raise UnsupportedPattern("unbalanced ')' in pattern")
                break
            parts.append(self._parse_quantified())
        return "".join(parts)

    def _depth(self) -> int:
        depth = 0
        i = 0
        s = self._src
        while i < self._pos:
            ch = s[i]
            if ch == "\\":
                i += 2
                continue
            if ch == "[":
                j = i + 1
                if j < len(s) and s[j] == "^":
                    j += 1
                if j < len(s) and s[j] == "]":
                    j += 1
                while j < len(s) and s[j] != "]":
                    if s[j] == "\\":
                        j += 1
                    j += 1
                i = j + 1
                continue
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        return depth

    def _parse_quantified(self) -> str:
        atom, repeatable = self._parse_atom()
        q = self._peek()
        if q in ("*", "+", "?"):
            self._pos += 1
            if self._peek() in ("?", "+"):   # tolerate lazy/possessive suffix
                self._pos += 1
            if not repeatable:
                raise UnsupportedPattern("quantifier applied to a non-repeatable token")
            if q == "*":
                return ""        # minimal: zero copies
            if q == "+":
                return atom      # minimal: one copy
            return ""            # '?' minimal: zero copies
        if q == "{":
            n, _m = self._parse_brace_quantifier()
            if not repeatable:
                raise UnsupportedPattern("quantifier applied to a non-repeatable token")
            return atom * n      # minimal: exactly n copies
        return atom

    def _parse_brace_quantifier(self) -> Tuple[int, Optional[int]]:
        end = self._src.find("}", self._pos)
        if end == -1:
            raise UnsupportedPattern("unterminated '{' quantifier")
        body = self._src[self._pos + 1:end]
        self._pos = end + 1
        if self._peek() == "?":          # tolerate lazy suffix {n,m}?
            self._pos += 1
        body = body.strip()
        if not body:
            raise UnsupportedPattern("empty '{}' quantifier")
        if "," in body:
            lo_s, hi_s = body.split(",", 1)
            lo = int(lo_s) if lo_s.strip() else 0
            hi = int(hi_s) if hi_s.strip() else None
            return lo, hi
        n = int(body)
        return n, n

    def _parse_atom(self) -> Tuple[str, bool]:
        c = self._peek()
        if c == "(":
            return self._parse_group(), True
        if c == "[":
            return self._parse_class(), True
        if c == "\\":
            return self._parse_escape()
        if c == ".":
            self._pos += 1
            return self._rng.choice(self._SAFE_FILL), True
        if c in ("^", "$"):
            self._pos += 1
            return "", False     # anchor: contributes nothing, not repeatable
        if c in ("*", "+", "?", "{"):
            raise UnsupportedPattern("dangling quantifier %r (nothing to repeat)" % c)
        if c == ")":
            raise UnsupportedPattern("unexpected ')'")
        self._pos += 1
        return c, True           # plain literal

    def _parse_group(self) -> str:
        self._pos += 1           # consume '('
        if self._peek() == "?":
            self._pos += 1
            nxt = self._peek()
            if nxt == ":":
                self._pos += 1   # non-capturing, treat like a normal group
            elif nxt in ("=", "!", "<"):
                raise UnsupportedPattern("look-around / special group is unsupported")
            else:
                raise UnsupportedPattern("inline-flag group '(?%s...)' is unsupported" % nxt)
        inner = self._parse_alternation()
        if self._peek() != ")":
            raise UnsupportedPattern("unterminated group '('")
        self._pos += 1           # consume ')'
        return inner

    def _parse_class(self) -> str:
        start = self._pos
        self._pos += 1
        negated = False
        if self._peek() == "^":
            negated = True
            self._pos += 1
        members: List[str] = []
        ranges: List[Tuple[int, int]] = []
        first = True
        while True:
            c = self._peek()
            if c == "":
                raise UnsupportedPattern("unterminated character class '['")
            if c == "]" and not first:
                self._pos += 1
                break
            first = False
            if c == "\\":
                self._pos += 1
                esc = self._peek()
                self._pos += 1
                members.extend(self._class_escape(esc))
                continue
            if (
                self._pos + 2 < len(self._src)
                and self._src[self._pos + 1] == "-"
                and self._src[self._pos + 2] != "]"
            ):
                lo = c
                hi = self._src[self._pos + 2]
                ranges.append((ord(lo), ord(hi)))
                self._pos += 3
                continue
            members.append(c)
            self._pos += 1

        if not negated:
            choices: List[str] = list(members)
            for lo, hi in ranges:
                if lo <= hi:
                    choices.append(chr(lo))
            if not choices:
                raise UnsupportedPattern(
                    "empty character class %r" % self._src[start:self._pos]
                )
            return min(choices)
        excluded = set(members)
        for lo, hi in ranges:
            for o in range(lo, hi + 1):
                excluded.add(chr(o))
        for ch in self._SAFE_FILL:
            if ch not in excluded:
                return ch
        raise UnsupportedPattern("negated class excludes all safe fillers")

    @staticmethod
    def _class_escape(esc: str) -> List[str]:
        mapping = {
            "d": [chr(o) for o in range(ord("0"), ord("9") + 1)],
            "w": ["a", "A", "0", "_"],
            "s": [" "],
            "t": ["\t"],
            "n": ["\n"],
            "r": ["\r"],
        }
        if esc in mapping:
            return mapping[esc]
        if esc in ("D", "W", "S"):
            raise UnsupportedPattern("negated class-escape \\%s inside [] is unsupported" % esc)
        return [esc]             # escaped literal (\. \- \] \\ etc.)

    def _parse_escape(self) -> Tuple[str, bool]:
        self._pos += 1           # consume '\'
        esc = self._peek()
        if esc == "":
            raise UnsupportedPattern("trailing backslash")
        self._pos += 1
        if esc == "d":
            return "0", True
        if esc == "w":
            return "a", True
        if esc == "s":
            return " ", True
        if esc in ("D", "W", "S"):
            if esc == "D":
                return "a", True
            if esc == "W":
                return " ", True
            return "a", True     # \S -> non-space
        if esc in ("b", "B", "A", "Z"):
            return "", False     # word-boundary / string anchors: emit nothing
        if esc == "t":
            return "\t", True
        if esc == "n":
            return "\n", True
        if esc == "r":
            return "\r", True
        return esc, True         # escaped literal metacharacter


# --------------------------------------------------------------------------- #
# Mission-field helpers (tolerant to the summary vs detail vs webhook shapes)
#
# A webhook body may carry the compact summary shape (`reward_aigen`,
# `verification_type`), the rich detail shape (`reward:{amount,currency}`,
# `verification_params`), or be wrapped in an envelope (`{"mission": {...}}` /
# `{"event": "...", "data": {...}}`). These accessors read whichever is present.
# --------------------------------------------------------------------------- #

_EVM_ADDR_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")


def unwrap_mission(payload: Any) -> Optional[Dict[str, Any]]:
    """Pull the mission object out of an arbitrary webhook JSON body.

    Accepts the bare mission dict, or an envelope nesting it under one of
    ``mission`` / ``data`` / ``result`` / ``payload``. Returns ``None`` when no
    mission-shaped dict can be found.
    """
    if isinstance(payload, Mapping):
        if _mission_id(payload) is not None or "verification_type" in payload:
            return dict(payload)
        for key in ("mission", "data", "result", "payload"):
            inner = payload.get(key)
            if isinstance(inner, Mapping):
                got = unwrap_mission(inner)
                if got is not None:
                    return got
    return None


def _mission_id(m: Mapping[str, Any]) -> Optional[str]:
    if not isinstance(m, Mapping):
        return None
    mid = m.get("id")
    if mid is None:
        mid = m.get("mission_id")
    return str(mid) if mid is not None else None


def mission_verification_type(m: Mapping[str, Any]) -> str:
    return str(m.get("verification_type") or "").strip()


def mission_verification_params(m: Mapping[str, Any]) -> Dict[str, Any]:
    vp = m.get("verification_params")
    return dict(vp) if isinstance(vp, Mapping) else {}


def mission_regex(m: Mapping[str, Any]) -> Optional[str]:
    vp = mission_verification_params(m)
    rx = vp.get("regex")
    if isinstance(rx, str) and rx:
        return rx
    rx = m.get("regex")  # some deployments hoist regex to the top level
    return rx if isinstance(rx, str) and rx else None


def mission_oracle_description(m: Mapping[str, Any]) -> Optional[str]:
    vp = mission_verification_params(m)
    od = vp.get("oracle_description")
    return od if isinstance(od, str) and od else None


def mission_reward_amount(m: Mapping[str, Any]) -> Optional[float]:
    reward = m.get("reward")
    if isinstance(reward, Mapping):
        amt = reward.get("amount")
        if isinstance(amt, (int, float)):
            return float(amt)
    for key in ("reward_amount", "reward_aigen"):
        amt = m.get(key)
        if isinstance(amt, (int, float)):
            return float(amt)
    return None


def mission_reward_currency(m: Mapping[str, Any]) -> str:
    reward = m.get("reward")
    if isinstance(reward, Mapping) and reward.get("currency"):
        return str(reward["currency"])
    cur = m.get("reward_currency")
    if cur:
        return str(cur)
    if isinstance(m.get("reward_aigen"), (int, float)):
        return "AIGEN"
    return "AIGEN"


def mission_text(m: Mapping[str, Any]) -> str:
    """Concatenate human-readable mission fields for placeholder/address use."""
    parts = [str(m.get("title") or ""), str(m.get("description") or "")]
    od = mission_oracle_description(m)
    if od:
        parts.append(od)
    return "\n".join(p for p in parts if p)


def extract_token_address(text: str) -> Optional[str]:
    mm = _EVM_ADDR_RE.search(text or "")
    return mm.group(0) if mm else None


def net_after_fee(amount: float) -> float:
    """Apply the flat 0.5% protocol fee."""
    return round(amount * (1.0 - PROTOCOL_FEE_BPS / 10_000.0), 6)


# --------------------------------------------------------------------------- #
# Eligibility decision + per-type proof generation
# --------------------------------------------------------------------------- #


class Decision:
    """The outcome of evaluating one inbound mission webhook.

    ``action`` is one of:
      * ``"claim"``  — eligible; ``proof`` holds the deliverable to submit.
      * ``"skip"``   — ineligible / not mechanically answerable; ``reason`` says why.
      * ``"invalid"``— the body was not a usable mission; ``reason`` says why.
    """

    __slots__ = ("action", "reason", "proof", "mission_id", "verification_type",
                 "reward_amount", "reward_currency")

    def __init__(
        self,
        action: str,
        reason: str,
        *,
        proof: Optional[str] = None,
        mission_id: Optional[str] = None,
        verification_type: str = "",
        reward_amount: Optional[float] = None,
        reward_currency: str = "",
    ) -> None:
        self.action = action
        self.reason = reason
        self.proof = proof
        self.mission_id = mission_id
        self.verification_type = verification_type
        self.reward_amount = reward_amount
        self.reward_currency = reward_currency

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "action": self.action,
            "reason": self.reason,
            "mission_id": self.mission_id,
            "verification_type": self.verification_type,
        }
        if self.reward_amount is not None:
            d["reward_amount"] = self.reward_amount
            d["reward_currency"] = self.reward_currency
            d["reward_net_after_fee"] = net_after_fee(self.reward_amount)
        if self.proof is not None:
            d["proof"] = self.proof
        return d


def render_proof_template(template: str, mission: Mapping[str, Any]) -> str:
    """Fill ``{id}`` / ``{title}`` / ``{address}`` placeholders in a template.

    Unknown placeholders are left intact (so an accidental ``{}`` does not crash
    the responder). The address comes from the mission text when present.
    """
    fields = {
        "id": _mission_id(mission) or "",
        "title": str(mission.get("title") or ""),
        "address": extract_token_address(mission_text(mission)) or "",
    }

    class _Safe(dict):
        def __missing__(self, key: str) -> str:  # leave unknown {placeholders}
            return "{" + key + "}"

    try:
        return string.Formatter().vformat(template, (), _Safe(fields))
    except (ValueError, IndexError):
        # Malformed format spec — fall back to the literal template unchanged.
        return template


class Responder:
    """Stateless policy object: decide + (when eligible) generate a proof.

    Holds the immutable configuration (which verification types to act on, the
    min-reward floor, the oracle proof-template, the sampler seed) and turns a
    parsed mission into a :class:`Decision`. It performs **no** network I/O — the
    server enqueues submission for the worker — so it is trivially testable.
    """

    def __init__(
        self,
        *,
        verification_types: Optional[List[str]] = None,
        min_reward: float = 0.0,
        proof_template: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.verification_types = (
            list(verification_types) if verification_types else [TARGET_VERIFICATION_TYPE]
        )
        self.min_reward = float(min_reward)
        self.proof_template = proof_template
        self.seed = seed

    def evaluate(self, payload: Any) -> Decision:
        mission = unwrap_mission(payload)
        if mission is None:
            return Decision("invalid", "body is not a mission-shaped object")

        mid = _mission_id(mission)
        vt = mission_verification_type(mission)
        amount = mission_reward_amount(mission)
        currency = mission_reward_currency(mission)

        common = dict(
            mission_id=mid,
            verification_type=vt,
            reward_amount=amount,
            reward_currency=currency,
        )

        if not mid:
            return Decision("invalid", "mission has no id", **common)

        # Respect an explicit non-open status if the webhook carries one.
        status = mission.get("status")
        if isinstance(status, str) and status and status != "open":
            return Decision("skip", "mission status is %r (not open)" % status, **common)

        if not vt:
            return Decision("skip", "mission has no verification_type", **common)

        if vt not in self.verification_types:
            return Decision(
                "skip",
                "verification_type %r not in --verification-type %s"
                % (vt, ",".join(self.verification_types)),
                **common,
            )

        if amount is not None and amount < self.min_reward:
            return Decision(
                "skip",
                "reward %g %s < --min-reward %g" % (amount, currency, self.min_reward),
                **common,
            )

        # --- per-type strategy (identical to the standalone claimer) ---
        if vt == "first_valid_match":
            return self._handle_first_valid_match(mission, common)
        if vt == "oracle":
            return self._handle_oracle(mission, common)
        if vt in ("peer_vote", "creator_judges"):
            human = (
                "a staked peer-voting quorum"
                if vt == "peer_vote"
                else "the mission creator's subjective judgement"
            )
            return Decision(
                "skip",
                "%s is resolved by %s — no mechanically computable proof" % (vt, human),
                **common,
            )
        return Decision("skip", "unsupported verification_type %r" % vt, **common)

    # -- per-type handlers ------------------------------------------------- #

    def _handle_first_valid_match(
        self, mission: Mapping[str, Any], common: Mapping[str, Any]
    ) -> Decision:
        rx = mission_regex(mission)
        if not rx:
            return Decision(
                "skip",
                "first_valid_match mission has no verification_params.regex",
                **common,
            )
        try:
            proof = RegexSampler(seed=self.seed).sample(rx)
        except UnsupportedPattern as exc:
            return Decision(
                "skip",
                "regex not satisfiable by the inline sampler (%s): %s" % (exc, rx),
                **common,
            )
        return Decision(
            "claim",
            "generated a minimal string matching regex %r" % rx,
            proof=proof,
            **common,
        )

    def _handle_oracle(
        self, mission: Mapping[str, Any], common: Mapping[str, Any]
    ) -> Decision:
        # An oracle proof is content the resolver re-verifies against GoPlus /
        # GitHub — it cannot be invented. Only act when given a passthrough
        # template the operator stands behind (same policy as the claimer).
        if not self.proof_template:
            return Decision(
                "skip",
                "oracle mission requires --proof-template (passthrough proof, e.g. a "
                "delivered repo URL or GoPlus summary) — none configured",
                **common,
            )
        proof = render_proof_template(self.proof_template, mission)
        return Decision(
            "claim",
            "passing through --proof-template as the oracle proof",
            proof=proof,
            **common,
        )


# --------------------------------------------------------------------------- #
# Outbound submitter (urllib, stdlib) with retry/backoff
# --------------------------------------------------------------------------- #


class SubmitError(Exception):
    """A submission could not be delivered after retries."""


class Submitter:
    """POST ``/missions/{id}/submit`` with retry/backoff, using ``urllib``.

    Pulled out so the test-suite can substitute a stub (``submit_func``) and
    assert a deliverable *would* be generated/sent without touching the network.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = HTTP_TIMEOUT,
        max_retries: int = SUBMIT_MAX_RETRIES,
        sleep_func: Callable[[float], None] = time.sleep,
        opener: Optional[Callable[[urllib.request.Request, float], Any]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._sleep = sleep_func
        # opener(req, timeout) -> response-like (has .status / .getcode(), .read())
        self._opener = opener or (lambda req, t: urllib.request.urlopen(req, timeout=t))

    def _backoff(self, attempt: int) -> float:
        delay = min(SUBMIT_BACKOFF_CAP, SUBMIT_BACKOFF_BASE * (2 ** attempt))
        return delay + random.uniform(0.0, delay / 2.0)

    def submit(self, mission_id: str, agent_id: str, proof: str) -> Tuple[int, Any]:
        """Return ``(status, body)``. Raises :class:`SubmitError` on give-up."""
        url = "%s/missions/%s/submit" % (self.base_url, mission_id)
        data = json.dumps(
            {"submitter_agent_id": agent_id, "proof": proof}
        ).encode("utf-8")
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            req = urllib.request.Request(
                url,
                data=data,
                method="POST",
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            try:
                resp = self._opener(req, self.timeout)
                status = getattr(resp, "status", None)
                if status is None and hasattr(resp, "getcode"):
                    status = resp.getcode()
                raw = resp.read()
                body = _maybe_json(raw)
                return int(status or 0), body
            except urllib.error.HTTPError as exc:
                status = exc.code
                raw = b""
                try:
                    raw = exc.read()
                except Exception:
                    pass
                if status in RETRY_STATUSES and attempt < self.max_retries - 1:
                    self._sleep(self._backoff(attempt))
                    last_exc = exc
                    continue
                return int(status), _maybe_json(raw)
            except (urllib.error.URLError, OSError) as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    self._sleep(self._backoff(attempt))
                    continue
        raise SubmitError(
            "POST %s failed after %d attempts: %s" % (url, self.max_retries, last_exc)
        )


def _maybe_json(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        try:
            return raw.decode("utf-8", "replace")
        except Exception:
            return None


# --------------------------------------------------------------------------- #
# Metrics (thread-safe counters)
# --------------------------------------------------------------------------- #


class Metrics:
    """A tiny thread-safe set of monotonically-increasing counters.

    Rendered for ``GET /metrics`` in Prometheus text-exposition format and as a
    plain dict for ``GET /healthz`` / the self-test.
    """

    _FIELDS = (
        "received",               # webhook bodies accepted past auth
        "claimed",                # missions we submitted (or would, in dry-run)
        "skipped",                # ineligible / not mechanically answerable
        "invalid",                # body was not a usable mission
        "rejected_unauthorized",  # failed shared-secret verification (401)
        "submit_ok",              # outbound submit returned a non-error status
        "submit_failed",          # outbound submit gave up / was rejected
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._c: Dict[str, int] = {k: 0 for k in self._FIELDS}
        self.started_at = time.time()

    def inc(self, field: str, by: int = 1) -> None:
        with self._lock:
            self._c[field] = self._c.get(field, 0) + by

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._c)

    def render_prometheus(self) -> str:
        snap = self.snapshot()
        lines: List[str] = []
        for field in self._FIELDS:
            metric = "oabp_webhook_%s_total" % field
            lines.append("# HELP %s OABP webhook responder counter: %s." % (metric, field))
            lines.append("# TYPE %s counter" % metric)
            lines.append("%s %d" % (metric, snap.get(field, 0)))
        uptime = max(0.0, time.time() - self.started_at)
        lines.append("# HELP oabp_webhook_uptime_seconds Process uptime in seconds.")
        lines.append("# TYPE oabp_webhook_uptime_seconds gauge")
        lines.append("oabp_webhook_uptime_seconds %.3f" % uptime)
        return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Shared-secret verification
# --------------------------------------------------------------------------- #


def verify_secret(
    secret: Optional[str],
    raw_body: bytes,
    headers: Mapping[str, str],
) -> bool:
    """Return True if the request is authorized for the configured ``secret``.

    With no secret configured, every request is authorized (open mode). With a
    secret, accept either an HMAC-SHA256 of the raw body (``X-OABP-Signature:
    sha256=<hex>``, constant-time compared) or the bare shared secret
    (``X-OABP-Token`` or ``Authorization: Bearer``). All header lookups are
    case-insensitive.
    """
    if not secret:
        return True
    lower = {str(k).lower(): str(v) for k, v in headers.items()}

    sig = lower.get("x-oabp-signature")
    if sig:
        provided = sig.split("=", 1)[1].strip() if "=" in sig else sig.strip()
        expected = hmac.new(
            secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        if hmac.compare_digest(provided, expected):
            return True

    token = lower.get("x-oabp-token")
    if token and hmac.compare_digest(token.strip(), secret):
        return True

    auth = lower.get("authorization", "")
    if auth.lower().startswith("bearer "):
        bearer = auth[len("bearer "):].strip()
        if hmac.compare_digest(bearer, secret):
            return True

    return False


# --------------------------------------------------------------------------- #
# HTTP server
# --------------------------------------------------------------------------- #


class ResponderConfig:
    """Everything the request handler needs, attached to the server instance."""

    def __init__(
        self,
        *,
        responder: Responder,
        metrics: Metrics,
        agent_id: Optional[str],
        secret: Optional[str],
        dry_run: bool,
        submit_queue: Optional["queue.Queue"],
        webhook_path: str = "/webhook",
        log: Callable[[str], None] = lambda msg: None,
    ) -> None:
        self.responder = responder
        self.metrics = metrics
        self.agent_id = agent_id
        self.secret = secret
        self.dry_run = dry_run
        self.submit_queue = submit_queue
        self.webhook_path = webhook_path
        self.log = log


class _Handler(BaseHTTPRequestHandler):
    """stdlib request handler dispatching the four routes. No framework."""

    server_version = "oabp-webhook-responder/1.0"
    protocol_version = "HTTP/1.1"

    # -- helpers ----------------------------------------------------------- #

    @property
    def cfg(self) -> ResponderConfig:
        return self.server.cfg  # type: ignore[attr-defined]

    def _send_json(self, status: int, obj: Any) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_text(self, status: int, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _read_body(self) -> Optional[bytes]:
        """Read up to MAX_BODY_BYTES of request body, or None if too large."""
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except (TypeError, ValueError):
            length = 0
        if length < 0:
            return b""
        if length > MAX_BODY_BYTES:
            return None
        if length == 0:
            return b""
        return self.rfile.read(length)

    def log_message(self, fmt: str, *args: Any) -> None:  # silence default stderr spam
        self.cfg.log("%s - %s" % (self.address_string(), fmt % args))

    # -- routes ------------------------------------------------------------ #

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/healthz":
            self._handle_healthz()
        elif path == "/metrics":
            self._send_text(
                HTTPStatus.OK,
                self.cfg.metrics.render_prometheus(),
                content_type="text/plain; version=0.0.4; charset=utf-8",
            )
        elif path == "/":
            self._send_text(
                HTTPStatus.OK,
                "OABP/AIGEN webhook responder — POST a new-mission notification to %s ; "
                "GET /healthz ; GET /metrics\n" % self.cfg.webhook_path,
            )
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found", "path": path})

    def do_HEAD(self) -> None:
        # Reuse GET routing for headers-only probes.
        self.do_GET()

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path != self.cfg.webhook_path.rstrip("/"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found", "path": path})
            return
        self._handle_webhook()

    # -- route impls ------------------------------------------------------- #

    def _handle_healthz(self) -> None:
        m = self.cfg.metrics
        self._send_json(
            HTTPStatus.OK,
            {
                "status": "ok",
                "agent_id": self.cfg.agent_id,
                "dry_run": self.cfg.dry_run,
                "auth": "shared-secret" if self.cfg.secret else "disabled",
                "verification_types": self.cfg.responder.verification_types,
                "uptime_seconds": round(max(0.0, time.time() - m.started_at), 3),
                "counters": m.snapshot(),
            },
        )

    def _handle_webhook(self) -> None:
        raw = self._read_body()
        if raw is None:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": "request body exceeds %d bytes" % MAX_BODY_BYTES},
            )
            return

        # 1) Spoof check FIRST — before parsing or any work.
        if not verify_secret(self.cfg.secret, raw, self.headers):
            self.cfg.metrics.inc("rejected_unauthorized")
            self._send_json(
                HTTPStatus.UNAUTHORIZED,
                {"error": "unauthorized: missing or invalid shared-secret"},
            )
            return

        # 2) Parse JSON.
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else None
        except (ValueError, UnicodeDecodeError) as exc:
            self.cfg.metrics.inc("invalid")
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid JSON body: %s" % exc},
            )
            return

        # Counted as received only once it is authorized and well-formed JSON.
        self.cfg.metrics.inc("received")

        # 3) Decide eligibility + (maybe) generate proof.
        decision = self.cfg.responder.evaluate(payload)
        result = decision.to_dict()

        if decision.action == "invalid":
            self.cfg.metrics.inc("invalid")
            self._send_json(HTTPStatus.BAD_REQUEST, result)
            return

        if decision.action == "skip":
            self.cfg.metrics.inc("skipped")
            result["dry_run"] = self.cfg.dry_run
            self._send_json(HTTPStatus.OK, result)
            return

        # decision.action == "claim"
        self.cfg.metrics.inc("claimed")
        result["dry_run"] = self.cfg.dry_run

        if self.cfg.dry_run or self.cfg.submit_queue is None:
            result["submitted"] = False
            result["note"] = (
                "dry-run: proof generated but NOT submitted; "
                "re-run with --no-dry-run --agent-id <id> to submit"
            )
            self._send_json(HTTPStatus.OK, result)
            return

        # Real submit: enqueue for the async worker, return 202 immediately.
        assert decision.mission_id is not None and decision.proof is not None
        self.cfg.submit_queue.put((decision.mission_id, decision.proof))
        result["submitted"] = "queued"
        result["note"] = "enqueued for asynchronous submission"
        self._send_json(HTTPStatus.ACCEPTED, result)


def make_server(
    host: str,
    port: int,
    cfg: ResponderConfig,
) -> ThreadingHTTPServer:
    """Build (but do not start) a threaded HTTP server with ``cfg`` attached."""
    httpd = ThreadingHTTPServer((host, port), _Handler)
    httpd.daemon_threads = True
    httpd.cfg = cfg  # type: ignore[attr-defined]
    return httpd


# --------------------------------------------------------------------------- #
# Async submit worker
# --------------------------------------------------------------------------- #

_SUBMIT_SENTINEL = object()


def submit_worker(
    submit_queue: "queue.Queue",
    submitter: Submitter,
    agent_id: str,
    metrics: Metrics,
    log: Callable[[str], None],
) -> None:
    """Drain ``submit_queue`` and POST each ``(mission_id, proof)`` deliverable.

    Runs on a background daemon thread so the webhook handler can ACK fast. The
    sentinel object pushed at shutdown breaks the loop cleanly.
    """
    while True:
        item = submit_queue.get()
        try:
            if item is _SUBMIT_SENTINEL:
                return
            mission_id, proof = item
            try:
                status, body = submitter.submit(mission_id, agent_id, proof)
            except SubmitError as exc:
                metrics.inc("submit_failed")
                log("submit %s FAILED: %s" % (mission_id, exc))
                continue
            # The API returns HTTP 200 with an {"error": ...} on logical failure.
            if isinstance(body, Mapping) and body.get("error"):
                metrics.inc("submit_failed")
                log("submit %s rejected: %s" % (mission_id, body.get("error")))
            elif status >= 400:
                metrics.inc("submit_failed")
                log("submit %s HTTP %d: %s" % (mission_id, status, body))
            else:
                metrics.inc("submit_ok")
                log("submit %s OK (HTTP %d)" % (mission_id, status))
        finally:
            submit_queue.task_done()


# --------------------------------------------------------------------------- #
# Offline self-test (no network, ephemeral port)
# --------------------------------------------------------------------------- #


def _http_request(
    method: str,
    url: str,
    *,
    body: Optional[bytes] = None,
    headers: Optional[Mapping[str, str]] = None,
) -> Tuple[int, bytes]:
    """Minimal urllib round-trip returning ``(status, raw_body)``."""
    req = urllib.request.Request(url, data=body, method=method, headers=dict(headers or {}))
    try:
        resp = urllib.request.urlopen(req, timeout=10.0)
        return int(getattr(resp, "status", resp.getcode())), resp.read()
    except urllib.error.HTTPError as exc:
        raw = b""
        try:
            raw = exc.read()
        except Exception:
            pass
        return int(exc.code), raw


def _self_test() -> None:
    """End-to-end offline test on an ephemeral port — the acceptance scenario.

    Proves, with no external network:
      * the regex sampler matches a battery of patterns (and fails closed);
      * a ``first_valid_match`` webhook returns 200 and, with a STUBBED submit in
        non-dry-run, a deliverable is generated *and* the stub receives it;
      * ``GET /healthz`` returns 200 and ``/metrics`` reflects the received counter;
      * a ``POST`` with the WRONG secret is rejected 401 (and never claimed);
      * an oracle mission without ``--proof-template`` is skipped, and *with* one
        the rendered passthrough proof is submitted.
    """
    # ---- 1) sampler battery (same cases as the claimer) ----
    for pat in (
        r"^0x[a-f0-9]{40}$",
        r"^[A-Z]{3}-\d{4}$",
        r"https://github\.com/[A-Za-z0-9_.\-]+/pull/[0-9]+",
        r"^(cat|dog|bird)$",
        r"\d{3,5}",
    ):
        s = RegexSampler(seed=1234).sample(pat)
        if pat.startswith("^") and pat.endswith("$"):
            assert re.fullmatch(pat, s), (pat, s)
        else:
            assert re.search(pat, s), (pat, s)
    assert RegexSampler(seed=0).sample(r"^0x[a-f0-9]{40}$") == "0x" + "0" * 40
    for bad in (r"(?=foo)bar", r"(a)\1", r"(?i)abc", r"a{", r"["):
        try:
            RegexSampler(seed=1).sample(bad)
        except UnsupportedPattern:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected UnsupportedPattern for %r" % bad)

    # ---- 2) Responder policy unit checks (no server) ----
    r_fvm = Responder()  # default: first_valid_match only
    d = r_fvm.evaluate(
        {
            "id": "mis_unit",
            "verification_type": "first_valid_match",
            "verification_params": {"regex": r"^[A-Z]{3}-\d{4}$"},
            "reward_aigen": 50,
        }
    )
    assert d.action == "claim" and re.fullmatch(r"^[A-Z]{3}-\d{4}$", d.proof or ""), d.to_dict()
    # oracle skipped without a template ...
    d2 = r_fvm.evaluate({"id": "m", "verification_type": "oracle"})
    assert d2.action == "skip", d2.to_dict()
    # ... and claimed (passthrough) with one + the right type enabled
    r_oracle = Responder(
        verification_types=["first_valid_match", "oracle"],
        proof_template="https://github.com/me/{id}",
    )
    d3 = r_oracle.evaluate({"id": "mis_repo", "verification_type": "oracle",
                            "description": "deliver a Go repo"})
    assert d3.action == "claim" and d3.proof == "https://github.com/me/mis_repo", d3.to_dict()
    # peer_vote / creator_judges always skipped
    assert r_oracle.evaluate({"id": "p", "verification_type": "peer_vote"}).action == "skip"
    assert r_oracle.evaluate({"id": "c", "verification_type": "creator_judges"}).action == "skip"
    # min-reward floor
    assert Responder(min_reward=100).evaluate(
        {"id": "x", "verification_type": "first_valid_match",
         "verification_params": {"regex": "^a$"}, "reward_aigen": 5}
    ).action == "skip"
    # secret verification primitives
    body = b'{"id":"m"}'
    sig = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert verify_secret("s3cret", body, {"X-OABP-Signature": sig})
    assert verify_secret("s3cret", body, {"X-OABP-Token": "s3cret"})
    assert verify_secret("s3cret", body, {"Authorization": "Bearer s3cret"})
    assert not verify_secret("s3cret", body, {"X-OABP-Token": "WRONG"})
    assert verify_secret(None, body, {})  # open mode

    # ---- 3) live server on an ephemeral port with a STUBBED submitter ----
    metrics = Metrics()
    submitted: List[Tuple[str, str, str]] = []

    class StubSubmitter(Submitter):
        def __init__(self) -> None:
            super().__init__("http://stub.invalid")

        def submit(self, mission_id: str, agent_id: str, proof: str) -> Tuple[int, Any]:
            submitted.append((mission_id, agent_id, proof))
            return 200, {"status": "accepted", "mission_id": mission_id}

    q: "queue.Queue" = queue.Queue()
    submitter = StubSubmitter()
    worker = threading.Thread(
        target=submit_worker,
        args=(q, submitter, "test-agent", metrics, lambda m: None),
        daemon=True,
    )
    worker.start()

    cfg = ResponderConfig(
        responder=Responder(verification_types=["first_valid_match", "oracle"],
                            proof_template="https://github.com/me/{id}"),
        metrics=metrics,
        agent_id="test-agent",
        secret="s3cret",
        dry_run=False,          # non-dry-run, but submit is STUBBED
        submit_queue=q,
    )
    httpd = make_server("127.0.0.1", 0, cfg)
    port = httpd.server_address[1]
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    base = "http://127.0.0.1:%d" % port
    try:
        mission = {
            "id": "mis_e2e_001",
            "title": "Find a token address",
            "verification_type": "first_valid_match",
            "verification_params": {"regex": r"^0x[a-f0-9]{40}$"},
            "reward": {"amount": 67, "currency": "AIGEN"},
            "status": "open",
        }
        raw = json.dumps(mission).encode("utf-8")
        good_sig = "sha256=" + hmac.new(b"s3cret", raw, hashlib.sha256).hexdigest()

        # (a) wrong secret -> 401, nothing claimed
        st, _ = _http_request(
            "POST", base + "/webhook", body=raw,
            headers={"Content-Type": "application/json", "X-OABP-Token": "WRONG"},
        )
        assert st == 401, "wrong secret must be 401, got %s" % st

        # (b) correct HMAC -> 202 (queued), deliverable generated
        st, rb = _http_request(
            "POST", base + "/webhook", body=raw,
            headers={"Content-Type": "application/json", "X-OABP-Signature": good_sig},
        )
        assert st == 202, "valid first_valid_match webhook must be 202, got %s" % st
        payload = json.loads(rb.decode("utf-8"))
        assert payload["action"] == "claim", payload
        assert re.fullmatch(r"^0x[a-f0-9]{40}$", payload["proof"]), payload

        # (c) oracle mission with template -> 202, passthrough proof
        omission = {
            "id": "mis_oracle_002",
            "title": "Deliver a Go repo",
            "verification_type": "oracle",
            "verification_params": {"oracle_description": "public GitHub repo in Go"},
            "reward": {"amount": 250, "currency": "USDC"},
        }
        oraw = json.dumps(omission).encode("utf-8")
        osig = "sha256=" + hmac.new(b"s3cret", oraw, hashlib.sha256).hexdigest()
        st, rb = _http_request(
            "POST", base + "/webhook", body=oraw,
            headers={"Content-Type": "application/json", "X-OABP-Signature": osig},
        )
        assert st == 202, "oracle+template webhook must be 202, got %s" % st
        assert json.loads(rb.decode("utf-8"))["proof"] == "https://github.com/me/mis_oracle_002"

        # drain the async submit queue and assert the stub received BOTH
        q.join()
        assert ("mis_e2e_001", "test-agent",
                "0x" + "0" * 40) in submitted, submitted
        assert any(mid == "mis_oracle_002" for (mid, _a, _p) in submitted), submitted

        # (d) /healthz -> 200
        st, rb = _http_request("GET", base + "/healthz")
        assert st == 200, "healthz must be 200, got %s" % st
        health = json.loads(rb.decode("utf-8"))
        assert health["status"] == "ok" and health["agent_id"] == "test-agent", health

        # (e) /metrics reflects the received counter (2 authorized bodies)
        st, rb = _http_request("GET", base + "/metrics")
        assert st == 200, "metrics must be 200, got %s" % st
        text = rb.decode("utf-8")
        assert "oabp_webhook_received_total 2" in text, text
        assert "oabp_webhook_claimed_total 2" in text, text
        assert "oabp_webhook_rejected_unauthorized_total 1" in text, text

        # (f) a malformed-JSON body (authorized) -> 400 invalid
        st, _ = _http_request(
            "POST", base + "/webhook", body=b"{not json",
            headers={"Content-Type": "application/json",
                     "X-OABP-Token": "s3cret"},
        )
        assert st == 400, "malformed JSON must be 400, got %s" % st
    finally:
        httpd.shutdown()
        httpd.server_close()
        q.put(_SUBMIT_SENTINEL)


# --------------------------------------------------------------------------- #
# CLI / main
# --------------------------------------------------------------------------- #


def parse_verification_types(spec: str) -> List[str]:
    out: List[str] = []
    for piece in spec.split(","):
        piece = piece.strip()
        if piece and piece not in out:
            out.append(piece)
    return out or [TARGET_VERIFICATION_TYPE]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="webhook_responder",
        description=(
            "Push-driven OABP/AIGEN webhook responder (stdlib http.server). "
            "Stands up a tiny HTTP server that accepts POSTed new-mission "
            "notifications, decides eligibility, and asynchronously submits a "
            "deliverable using the same per-type strategies as the claimer. "
            "Defaults to a safe DRY-RUN (generates proofs, submits nothing)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "This is the PUSH complement to the A2A JSON-RPC / MCP server and the "
            "pull-based feed listener: instead of polling, it waits for a relay to "
            "POST a mission the instant it opens. AIGEN is the protocol's uncapped "
            "reputation/points token; a 0.5%% fee is taken from every payout."
        ),
    )
    parser.add_argument("--host", default="0.0.0.0", help="Interface to bind.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="TCP port to listen on.")
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL,
        help="OABP API base URL for outbound submissions.",
    )
    parser.add_argument(
        "--agent-id", default=None,
        help="Your submitter_agent_id. REQUIRED before any real (non-dry-run) submit.",
    )
    parser.add_argument(
        "--secret", default=os.environ.get("OABP_WEBHOOK_SECRET"),
        help=(
            "Shared secret for verifying inbound webhooks (also read from "
            "$OABP_WEBHOOK_SECRET). When set, a POST must carry an HMAC "
            "(X-OABP-Signature: sha256=<hex of raw body>) OR the bare secret "
            "(X-OABP-Token / Authorization: Bearer). Unset = open (no auth)."
        ),
    )
    parser.add_argument(
        "--verification-type", default=TARGET_VERIFICATION_TYPE,
        help=(
            "Comma list of verification_types to act on. 'oracle' additionally "
            "requires --proof-template; 'peer_vote'/'creator_judges' are always "
            "skipped (human-resolved)."
        ),
    )
    parser.add_argument(
        "--min-reward", type=float, default=0.0,
        help="Skip missions whose reward amount is below this (mission's currency).",
    )
    parser.add_argument(
        "--proof-template", default=None,
        help=(
            "Passthrough proof for 'oracle' missions (content the resolver "
            "re-verifies via GoPlus/GitHub — cannot be invented). Placeholders "
            "{id} {title} {address} are filled from the mission. E.g. "
            "'https://github.com/you/repo'."
        ),
    )
    parser.add_argument(
        "--webhook-path", default="/webhook",
        help="URL path that accepts POSTed mission notifications.",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Seed for the regex sampler (deterministic first_valid_match proofs).",
    )
    dry = parser.add_mutually_exclusive_group()
    dry.add_argument(
        "--dry-run", dest="dry_run", action="store_true",
        help="Generate proofs and submit NOTHING (default).",
    )
    dry.add_argument(
        "--no-dry-run", dest="dry_run", action="store_false",
        help="Actually POST submissions (requires --agent-id).",
    )
    parser.set_defaults(dry_run=True)
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-request logging to stderr.",
    )
    parser.add_argument(
        "--self-test", action="store_true",
        help="Run the offline end-to-end self-test (no network) and exit.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.self_test:
        try:
            _self_test()
        except AssertionError as exc:
            sys.stderr.write("SELF-TEST FAILED: %s\n" % (exc,))
            return 2
        except Exception as exc:  # pragma: no cover - unexpected
            sys.stderr.write("SELF-TEST ERROR: %s\n" % (exc,))
            return 2
        print("webhook responder self-test: OK")
        return 0

    verification_types = parse_verification_types(args.verification_type)

    # Config validation (usage errors -> exit 3, send nothing).
    if not args.dry_run and not args.agent_id:
        sys.stderr.write("ERROR: --agent-id is required for a real (non-dry-run) submit.\n")
        return 3
    if "oracle" in verification_types and not args.proof_template:
        sys.stderr.write(
            "ERROR: acting on 'oracle' missions requires --proof-template "
            "(an oracle proof cannot be invented; supply the content you deliver).\n"
        )
        return 3

    def log(msg: str) -> None:
        if not args.quiet:
            sys.stderr.write("[webhook-responder] %s\n" % msg)
            sys.stderr.flush()

    metrics = Metrics()
    responder = Responder(
        verification_types=verification_types,
        min_reward=args.min_reward,
        proof_template=args.proof_template,
        seed=args.seed,
    )

    # Wire the async submit worker only when we will really submit.
    submit_queue: Optional["queue.Queue"] = None
    worker: Optional[threading.Thread] = None
    if not args.dry_run:
        submit_queue = queue.Queue()
        submitter = Submitter(args.base_url)
        worker = threading.Thread(
            target=submit_worker,
            args=(submit_queue, submitter, args.agent_id, metrics, log),
            daemon=True,
        )
        worker.start()

    cfg = ResponderConfig(
        responder=responder,
        metrics=metrics,
        agent_id=args.agent_id,
        secret=args.secret,
        dry_run=args.dry_run,
        submit_queue=submit_queue,
        webhook_path=args.webhook_path,
        log=log,
    )

    try:
        httpd = make_server(args.host, args.port, cfg)
    except OSError as exc:
        sys.stderr.write("ERROR: could not bind %s:%d: %s\n" % (args.host, args.port, exc))
        return 3

    bound_host, bound_port = httpd.server_address[:2]
    print(
        "OABP/AIGEN webhook responder listening on http://%s:%d%s\n"
        "  auth        : %s\n"
        "  dry_run     : %s\n"
        "  agent_id    : %s\n"
        "  act on      : %s\n"
        "  base_url    : %s\n"
        "  routes      : POST %s | GET /healthz | GET /metrics\n"
        "  (Ctrl-C to stop)"
        % (
            bound_host, bound_port, args.webhook_path,
            "shared-secret" if args.secret else "DISABLED (open)",
            args.dry_run, args.agent_id or "(none)",
            ",".join(verification_types), args.base_url, args.webhook_path,
        ),
        flush=True,
    )

    stop = threading.Event()

    def _on_signal(signum: int, _frame: Any) -> None:
        log("signal %d received, shutting down" % signum)
        stop.set()

    try:
        signal.signal(signal.SIGINT, _on_signal)
        signal.signal(signal.SIGTERM, _on_signal)
    except ValueError:
        # Not on the main thread (e.g. embedded) — rely on KeyboardInterrupt.
        pass

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    try:
        while not stop.is_set():
            stop.wait(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        httpd.server_close()
        if submit_queue is not None and worker is not None:
            # let in-flight submissions drain, then stop the worker
            try:
                submit_queue.join()
            except Exception:
                pass
            submit_queue.put(_SUBMIT_SENTINEL)
            worker.join(timeout=5.0)
    print("\nstopped.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
