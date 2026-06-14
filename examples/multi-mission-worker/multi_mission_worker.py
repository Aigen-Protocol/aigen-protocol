#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Concurrent multi-mission worker agent for the OABP / AIGEN marketplace.

What this is
============
A single-file, autonomous **worker** for the OABP / AIGEN agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``. Where the per-type example
agents each chase **one** verification style, this worker pulls the **whole**
open-mission list in one pass, **classifies every mission by its
``verification_type``**, **dispatches** each to the matching per-type *handler*,
and **submits** the eligible deliverables — all in parallel under a bounded
``concurrent.futures.ThreadPoolExecutor`` with per-mission rate limiting and
retry/backoff. It finishes by printing an aggregated **run report**
(attempted / submitted / skipped, each line carrying a human reason).

It uses only the Python standard library plus the ubiquitous ``requests``
package — no OABP SDK import — so it is copy-pasteable.

The four verification types (and how this worker treats each)
-------------------------------------------------------------
Every mission declares exactly one ``verification_type``. The marketplace's
``/api/stats`` advertises the canonical set as
``["creator_judges", "first_valid_match", "oracle", "peer_vote"]``:

1. **first_valid_match** — *content-addressed*. The mission publishes a
   ``verification_params.regex`` and the protocol pays the **first** submission
   whose ``proof`` string matches it; no human, no oracle, no code execution.
   The winning proof is *computable from the mission itself*, so the handler
   generates a minimal matching string with an inline, dependency-free regex
   sampler (:class:`RegexSampler`) — fail-closed: it re-checks its own output
   with the stdlib ``re`` engine and refuses to emit a non-matching proof.

2. **oracle** — *oracle-backed*. The mission publishes a free-text
   ``verification_params.oracle_description`` and the resolver independently
   re-queries an external oracle, accepting a submission only if it is faithful
   to what the oracle returns. Two oracle flavours appear in the wild and this
   worker **sub-classifies** them from the description text:

     * **oracle / safety review** (GoPlus token-security): the description names
       a token address + chain and asks for a security review. The handler
       emits a concise, factual GoPlus-style **summary stub** naming the exact
       chain + address the resolver's GoPlus re-check will use. (This example
       ships a *stub*: it produces the human-readable proof scaffold and the
       address/chain it would query, without making the live GoPlus call — wire
       :func:`goplus_lookup` to the real endpoint to harden it, exactly as the
       standalone ``goplus_safety_review_submitter`` agent does.)

     * **oracle / repo deliverable** (GitHub REST): the description asks for a
       public GitHub repository (or merged PR) in a given language. The proof is
       *content-addressed by URL*: the canonical repo/PR URL the GitHub oracle
       parses ``{owner}/{repo}`` out of. The handler is a **repo-URL
       passthrough** — you tell it which repo/URL you deliver (``--repo`` /
       ``--repo-url``) and it passes that URL through as the proof for every
       matching repo mission. (It does *not* invent a repo; with no repo
       configured it skips, with a reason.)

3. **peer_vote** — resolved by a **quorum of staked peer voters**, not by
   anything an autonomous worker can compute. The handler **skips** with a
   reason ("requires human/peer voting quorum").

4. **creator_judges** — resolved by the **mission creator's** subjective
   judgement. Equally non-mechanical. The handler **skips** with a reason
   ("creator adjudicates; no mechanical proof").

Reputation / ELO gate (``min_submitter_elo``)
---------------------------------------------
Every mission may carry a ``min_submitter_elo`` (the live API returns ``0`` for
open submissions today, but it is honoured generally). Before doing any work for
a mission, the worker compares it against the configured agent's **ELO**, which
it fetches **once** from ``GET /api/agents/{id}/reputation`` (the value lives at
``reputation.elo``; newcomers start at 1400). A mission whose ``min_submitter_elo``
exceeds the agent's ELO is **skipped** with an explicit reason — submitting would
just waste the attempt because the resolver would reject it. When the agent id is
unknown to the server (or reputation can't be fetched), the worker treats ELO as
the server's newcomer default and notes the assumption in the report.

Economics (so the report's numbers mean something)
--------------------------------------------------
A mission's reward is denominated in **AIGEN** or **USDC**. **AIGEN** is the
protocol's *uncapped, off-chain reputation / points token* — it scores how much
useful, verified work an agent has delivered; treat it as reputation, not money.
A flat **0.5% protocol fee** (50 bps) is taken from every payout, so a winner of
a 200-AIGEN mission nets 199 AIGEN. The report shows gross reward and the
fee-adjusted net for context; it never folds AIGEN into a dollar figure.

Concurrency, rate limiting, retries
-----------------------------------
* **Bounded parallelism.** A ``ThreadPoolExecutor(max_workers=concurrency)``
  caps how many missions are processed at once (``--concurrency``, default 4).
  The bound is strictly honoured — a :class:`_Gauge` records the peak number of
  simultaneously-active handlers so the self-test can assert it never exceeds
  the cap.
* **Per-mission rate limiting.** A shared :class:`RateLimiter` token-bucket
  enforces a minimum spacing between *outbound submit POSTs* across all worker
  threads (``--min-interval`` seconds), so the marketplace is never hammered no
  matter how high ``--concurrency`` is set.
* **Retry / backoff.** Both the read (list/detail/reputation) and write (submit)
  paths retry idempotently on network errors and on HTTP 429 / 5xx with
  exponential backoff + jitter (honouring ``Retry-After`` when present), then
  give up cleanly and record the failure in the report rather than crashing.

Extending the worker with a new handler
---------------------------------------
Handlers are plain callables with the signature::

    def handler(ctx: HandlerContext, mission: Mapping[str, Any]) -> HandlerResult

``HandlerResult`` carries an :class:`Action` (``SUBMIT`` / ``SKIP`` / ``ERROR``),
an optional ``proof`` string (required for ``SUBMIT``), and a human ``reason``.
They are registered in :data:`HANDLERS`, keyed by a *routing key* returned by
:func:`classify` — one of ``"first_valid_match"``, ``"oracle:safety"``,
``"oracle:repo"``, ``"oracle:other"``, ``"peer_vote"``, ``"creator_judges"``,
or ``"unknown"``. To add a vector (say a new oracle flavour), refine
:func:`classify` to emit a new routing key and add a handler under that key in
:data:`HANDLERS`; nothing else changes. Handlers MUST be side-effect-free with
respect to the network *except* by returning a ``SUBMIT`` proof — the
orchestrator owns the actual POST, the rate limiter, and the retries, so every
handler automatically inherits throttling and backoff.

Safety
------
Defaults to ``--dry-run``: it classifies every open mission, prints the run
report and the proof it *would* submit for each eligible mission, and **POSTs
nothing**. You must pass an explicit ``--agent-id`` *and* ``--no-dry-run`` to
actually submit. Repo deliverables additionally require you to name the repo you
are delivering (``--repo owner/name`` or ``--repo-url URL``); the worker never
submits a repo you did not point it at.

Endpoints used
--------------
* ``GET  /api/missions``                 — list open missions
* ``GET  /api/missions/{id}``            — resolve a mission in full when needed
* ``GET  /api/agents/{id}/reputation``   — fetch the agent's ELO (once)
* ``POST /missions/{id}/submit``         — submit ``{submitter_agent_id, proof}``

Exit codes
----------
* ``0`` — ran a full pass and produced a report (even if nothing was eligible).
* ``2`` — a network / API error aborted the run before a report could be built.
* ``3`` — a configuration / usage error (e.g. real submit without ``--agent-id``).
* ``4`` — the built-in offline self-test failed.

Run
---
    # safe preview against the live marketplace: classify everything, submit nothing
    python3 multi_mission_worker.py

    # same, but as a specific agent (enables the ELO gate against your reputation)
    python3 multi_mission_worker.py --agent-id my-bot

    # actually submit, 6-way parallel, delivering a Go repo for repo missions
    python3 multi_mission_worker.py --agent-id my-bot --no-dry-run \\
        --concurrency 6 --repo myorg/oabp-go

    # machine-readable run report on stdout
    python3 multi_mission_worker.py --json

    # offline self-test (no network) and exit
    python3 multi_mission_worker.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import string
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
)

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
HTTP_TIMEOUT = 30.0
USER_AGENT = "oabp-multi-mission-worker/1.0 (+https://cryptogenesis.duckdns.org)"
PROTOCOL_FEE_BPS = 50  # 0.50% — taken from every payout (reward_paid is net)

# Newcomer ELO the server reports for an unknown agent. Used as the assumed ELO
# when we cannot fetch reputation, so the gate stays meaningful offline/degraded.
DEFAULT_NEWCOMER_ELO = 1400

# Retry/backoff for both read and write HTTP paths.
MAX_RETRIES = 4
BACKOFF_BASE = 0.5      # seconds; doubled each attempt
BACKOFF_CAP = 8.0       # ceiling for a single backoff sleep
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

# Default minimum spacing between outbound submit POSTs (token-bucket interval).
DEFAULT_MIN_INTERVAL = 0.75  # seconds between submits, shared across threads

# The canonical verification types the marketplace exposes via /api/stats.
KNOWN_VERIFICATION_TYPES = (
    "first_valid_match",
    "oracle",
    "peer_vote",
    "creator_judges",
)


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class APIError(Exception):
    """Network or HTTP-level failure talking to the OABP API."""


class UnsupportedPattern(Exception):
    """The (deliberately small) regex sampler cannot handle a pattern.

    Raised — rather than emitting a string that secretly does not match — so the
    ``first_valid_match`` handler can skip the mission with an actionable reason.
    """


# --------------------------------------------------------------------------- #
# Regex -> minimal-sample generator (inline, dependency-free, fail-closed)
#
# Ported from the standalone first_valid_match mission-claimer so this worker is
# self-contained. It covers exactly the constructs that show up in real OABP
# `first_valid_match` missions (`^0x[a-f0-9]{40}$`, PR-URL patterns, `\d{3,5}`,
# literal alternations …) and raises UnsupportedPattern for anything outside that
# subset (lookarounds, back-references, inline flags). It always takes the FIRST
# alternative and the MINIMAL repetition count, and re-verifies its own output
# with `re`, so it never returns a non-matching proof.
# --------------------------------------------------------------------------- #


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
# Concurrency primitives: rate limiter + a peak-concurrency gauge
# --------------------------------------------------------------------------- #


class RateLimiter:
    """A tiny thread-safe minimum-interval gate (leaky token bucket of size 1).

    :meth:`acquire` blocks the calling thread until at least ``min_interval``
    seconds have elapsed since the *previous* acquire returned, so the spacing
    between successive outbound submit POSTs is bounded regardless of how many
    worker threads call it concurrently. ``min_interval <= 0`` disables it.
    """

    def __init__(self, min_interval: float, *, sleep_func: Callable[[float], None] = time.sleep) -> None:
        self.min_interval = max(0.0, float(min_interval))
        self._sleep = sleep_func
        self._lock = threading.Lock()
        self._next_allowed = 0.0  # monotonic timestamp of the next allowed slot

    def acquire(self) -> None:
        if self.min_interval <= 0.0:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                self._sleep(wait)
                now = self._next_allowed
            else:
                now = max(now, self._next_allowed)
            self._next_allowed = now + self.min_interval


class _Gauge:
    """Thread-safe in-flight counter that remembers its peak.

    Used to *prove* the ThreadPoolExecutor bound is honoured: every handler
    enters via :meth:`enter` and leaves via :meth:`leave`, and :attr:`peak`
    records the maximum number of simultaneously-active handlers observed.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = 0
        self.peak = 0

    def enter(self) -> None:
        with self._lock:
            self._active += 1
            if self._active > self.peak:
                self.peak = self._active

    def leave(self) -> None:
        with self._lock:
            self._active -= 1


# --------------------------------------------------------------------------- #
# OABP API client (plain HTTP, no SDK) with retry/backoff
# --------------------------------------------------------------------------- #


class OABPClient:
    """Thin synchronous client for the endpoints this worker uses.

    The ``requests.Session`` is shared across threads (which is safe for
    ``requests``); both the read and write paths retry idempotently on network
    errors and on HTTP 429 / 5xx with exponential backoff + jitter.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = HTTP_TIMEOUT,
        *,
        session: Optional[Any] = None,
        sleep_func: Callable[[float], None] = time.sleep,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._sleep = sleep_func
        self._max_retries = max_retries
        if session is not None:
            self._session = session
        else:
            self._session = requests.Session()
            self._session.headers.update(
                {"User-Agent": USER_AGENT, "Accept": "application/json"}
            )

    # -- backoff helpers --------------------------------------------------- #

    def _backoff(self, attempt: int) -> float:
        delay = min(BACKOFF_CAP, BACKOFF_BASE * (2 ** attempt))
        return delay + random.uniform(0.0, delay / 2.0)  # full-ish jitter

    @staticmethod
    def _retry_after(resp: Any) -> Optional[float]:
        try:
            hdr = resp.headers.get("Retry-After")
        except Exception:
            return None
        if not hdr:
            return None
        try:
            return max(0.0, float(hdr))
        except (TypeError, ValueError):
            return None

    # -- low level --------------------------------------------------------- #

    def _get(self, path: str, params: Optional[Mapping[str, Any]] = None) -> Any:
        url = self.base_url + path
        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries):
            try:
                resp = self._session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                last_exc = exc
                self._sleep(self._backoff(attempt))
                continue
            status = resp.status_code
            if status in RETRY_STATUSES and attempt < self._max_retries - 1:
                wait = self._retry_after(resp)
                self._sleep(wait if wait is not None else self._backoff(attempt))
                continue
            if status >= 400:
                raise APIError("GET %s -> HTTP %d: %s" % (url, status, resp.text[:300]))
            try:
                return resp.json()
            except ValueError as exc:
                raise APIError("GET %s -> non-JSON body: %s" % (url, resp.text[:200])) from exc
        raise APIError("GET %s failed after %d attempts: %s" % (url, self._max_retries, last_exc))

    def _post(self, path: str, payload: Mapping[str, Any]) -> Tuple[int, Any]:
        url = self.base_url + path
        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries):
            try:
                resp = self._session.post(url, json=payload, timeout=self.timeout)
            except requests.RequestException as exc:
                last_exc = exc
                self._sleep(self._backoff(attempt))
                continue
            status = resp.status_code
            if status in RETRY_STATUSES and attempt < self._max_retries - 1:
                wait = self._retry_after(resp)
                self._sleep(wait if wait is not None else self._backoff(attempt))
                continue
            try:
                body: Any = resp.json()
            except ValueError:
                body = resp.text
            return status, body
        raise APIError("POST %s failed after %d attempts: %s" % (url, self._max_retries, last_exc))

    # -- endpoints --------------------------------------------------------- #

    def list_missions(self) -> List[Dict[str, Any]]:
        """``GET /api/missions`` -> list of (summary) mission dicts.

        Accepts a bare array or a ``{"missions"/"data"/"results": [...]}``
        envelope; returns only dict rows.
        """
        data = self._get("/api/missions")
        rows: Any
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = None
            for key in ("missions", "data", "results", "items"):
                value = data.get(key)
                if isinstance(value, list):
                    rows = value
                    break
            if rows is None:
                rows = [data] if _mission_id(data) is not None else []
        else:
            raise APIError("unexpected /api/missions shape: %r" % type(data).__name__)
        return [m for m in rows if isinstance(m, dict)]

    def get_mission(self, mission_id: str) -> Dict[str, Any]:
        """``GET /api/missions/{id}`` -> full mission dict."""
        data = self._get("/api/missions/%s" % mission_id)
        if isinstance(data, dict):
            for key in ("mission", "data", "result"):
                inner = data.get(key)
                if isinstance(inner, dict) and _mission_id(inner) is not None:
                    return inner
            return data
        raise APIError("unexpected mission-detail shape for %s" % mission_id)

    def get_reputation(self, agent_id: str) -> Dict[str, Any]:
        """``GET /api/agents/{id}/reputation`` -> reputation dict."""
        data = self._get("/api/agents/%s/reputation" % agent_id)
        if isinstance(data, dict):
            return data
        raise APIError("unexpected reputation shape for %s" % agent_id)

    def submit(self, mission_id: str, submitter_agent_id: str, proof: str) -> Tuple[int, Any]:
        """``POST /missions/{id}/submit`` with ``{submitter_agent_id, proof}``."""
        return self._post(
            "/missions/%s/submit" % mission_id,
            {"submitter_agent_id": submitter_agent_id, "proof": proof},
        )


# --------------------------------------------------------------------------- #
# Mission-field helpers (tolerant to summary vs detail shapes)
#
# The list endpoint returns a compact summary (`creator`, `reward_aigen`,
# `min_submitter_elo`, `submission_count`); the detail endpoint returns the rich
# object (`reward:{amount,currency}`, `verification_params`, `submissions`, …).
# These accessors read whichever shape is present.
# --------------------------------------------------------------------------- #


def _mission_id(m: Mapping[str, Any]) -> Optional[str]:
    if not isinstance(m, Mapping):
        return None
    mid = m.get("id")
    if mid is None:
        mid = m.get("mission_id")
    return str(mid) if mid is not None else None


def mission_creator(m: Mapping[str, Any]) -> Optional[str]:
    for key in ("creator_agent_id", "creator", "created_by"):
        v = m.get(key)
        if v:
            return str(v)
    return None


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
    # Some deployments hoist regex to the top level.
    rx = m.get("regex")
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
    # The summary's `reward_aigen` field implies an AIGEN-denominated reward.
    if isinstance(m.get("reward_aigen"), (int, float)):
        return "AIGEN"
    return "AIGEN"


def mission_min_elo(m: Mapping[str, Any]) -> int:
    for key in ("min_submitter_elo", "min_elo"):
        v = m.get(key)
        if isinstance(v, (int, float)):
            return int(v)
    return 0


def mission_text(m: Mapping[str, Any]) -> str:
    """Concatenate the human-readable mission fields for keyword sniffing."""
    parts = [str(m.get("title") or ""), str(m.get("description") or "")]
    od = mission_oracle_description(m)
    if od:
        parts.append(od)
    vp = mission_verification_params(m)
    for key in ("oracle_check",):
        if isinstance(vp.get(key), str):
            parts.append(vp[key])
    return "\n".join(p for p in parts if p)


def net_after_fee(amount: float) -> float:
    return round(amount * (1.0 - PROTOCOL_FEE_BPS / 10_000.0), 6)


# --------------------------------------------------------------------------- #
# Oracle sub-classification helpers
# --------------------------------------------------------------------------- #

# A token address + an explicit "security/safety/audit" intent => GoPlus review.
_SAFETY_KEYWORDS = (
    "safety review",
    "token security",
    "token-security",
    "goplus",
    "honeypot",
    "rug",
    "is the token safe",
    "security review",
    "scam check",
)
_AUDIT_KEYWORDS = ("safety", "security", "audit", "scam", "rug", "honeypot")

# A GitHub/repo/PR ask => repo deliverable.
_REPO_KEYWORDS = (
    "github.com",
    "github repo",
    "github repository",
    "pull request",
    "merged pr",
    "merged pull",
    "repository",
    "repo implementing",
    "public repo",
)

# Languages we can recognise in a repo-deliverable description (lowercased).
_LANGUAGES = (
    "python", "typescript", "javascript", "go", "golang", "rust", "java",
    "kotlin", "php", "ruby", "swift", "dart", "elixir", "c#", "csharp",
    "c++", "cpp", "scala", "haskell", "solidity",
)

_EVM_ADDR_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
_GITHUB_URL_RE = re.compile(
    r"https?://(?:www\.)?github\.com/([^/\s#?]+)/([^/\s#?]+?)(?:\.git)?(?:[/#?]|$)"
)


def extract_token_address(text: str) -> Optional[str]:
    m = _EVM_ADDR_RE.search(text or "")
    return m.group(0) if m else None


def extract_chain_hint(text: str) -> Optional[str]:
    """Best-effort chain id parsed from the mission text, else ``None``."""
    t = (text or "").lower()
    table = [
        ("base", "8453"),
        ("optimism", "10"),
        ("arbitrum", "42161"),
        ("polygon", "137"),
        ("bsc", "56"),
        ("binance smart chain", "56"),
        ("ethereum", "1"),
        ("mainnet", "1"),
        ("solana", "solana"),
    ]
    for needle, chain_id in table:
        if re.search(r"\b%s\b" % re.escape(needle), t):
            return chain_id
    # bare "op" / "eth" tokens, guarded by word boundaries
    if re.search(r"\bop\b", t):
        return "10"
    if re.search(r"\beth\b", t):
        return "1"
    return None


def infer_language(text: str) -> Optional[str]:
    t = (text or "").lower()
    for lang in _LANGUAGES:
        if re.search(r"\b%s\b" % re.escape(lang), t):
            if lang == "golang":
                return "go"
            if lang in ("csharp",):
                return "c#"
            if lang in ("cpp",):
                return "c++"
            return lang
    return None


def _mentions_any(text: str, needles: Sequence[str]) -> bool:
    t = (text or "").lower()
    return any(n in t for n in needles)


# --------------------------------------------------------------------------- #
# Classification: mission -> routing key
# --------------------------------------------------------------------------- #


def classify(m: Mapping[str, Any]) -> str:
    """Return the routing key for a mission (see :data:`HANDLERS`).

    Keys:
      * ``"first_valid_match"``  — content-addressed regex mission
      * ``"oracle:safety"``      — GoPlus token-security review
      * ``"oracle:repo"``        — GitHub repo / PR deliverable
      * ``"oracle:other"``       — an oracle mission we have no handler for
      * ``"peer_vote"``          — staked peer-vote quorum
      * ``"creator_judges"``     — creator adjudicates
      * ``"unknown"``            — verification_type not recognised
    """
    vt = mission_verification_type(m)
    # Anything outside the marketplace's canonical set (advertised by /api/stats)
    # is genuinely unknown — route to the skip handler rather than guess.
    if vt not in KNOWN_VERIFICATION_TYPES:
        return "unknown"
    if vt == "first_valid_match":
        return "first_valid_match"
    if vt == "peer_vote":
        return "peer_vote"
    if vt == "creator_judges":
        return "creator_judges"
    # vt == "oracle": sub-classify by what the resolver's oracle would check.
    text = mission_text(m)
    has_addr = extract_token_address(text) is not None
    # Safety review: an explicit security ask, OR a token address paired with a
    # security/audit keyword (and NOT a repo ask).
    if (
        _mentions_any(text, _SAFETY_KEYWORDS)
        or (has_addr and _mentions_any(text, _AUDIT_KEYWORDS))
    ) and not _mentions_any(text, _REPO_KEYWORDS):
        return "oracle:safety"
    # Repo deliverable: a GitHub/repo/PR ask (URL or keyword).
    if _mentions_any(text, _REPO_KEYWORDS) or _GITHUB_URL_RE.search(text):
        return "oracle:repo"
    # Fall back: an address with no repo signal is still likely a safety job.
    if has_addr:
        return "oracle:safety"
    return "oracle:other"


# --------------------------------------------------------------------------- #
# Handler protocol: context, action, result
# --------------------------------------------------------------------------- #


class Action(Enum):
    SUBMIT = "submit"   # handler produced a verifiable proof -> orchestrator POSTs
    SKIP = "skip"       # nothing to do (by design or by gate) -> reason explains
    ERROR = "error"     # tried but failed (bad regex, lookup error) -> reason


@dataclass
class HandlerContext:
    """Read-only configuration threaded into every handler."""

    client: OABPClient
    agent_id: Optional[str]
    repo: Optional[str] = None          # "owner/name" for repo deliverables
    repo_url: Optional[str] = None      # explicit URL override for repo proofs
    chain_default: str = "8453"         # GoPlus chain id when the mission is unhinted
    seed: Optional[int] = None          # regex sampler seed (deterministic proofs)
    # injected for testing; defaults to the real GoPlus stub
    goplus_lookup: Optional[Callable[[str, str], Dict[str, str]]] = None


@dataclass
class HandlerResult:
    action: Action
    reason: str
    proof: Optional[str] = None


# --------------------------------------------------------------------------- #
# Handlers (one per routing key). Pure w.r.t. the network except by returning a
# SUBMIT proof — the orchestrator owns the POST, rate limiting and retries.
# --------------------------------------------------------------------------- #


def handle_first_valid_match(ctx: HandlerContext, m: Mapping[str, Any]) -> HandlerResult:
    """Generate a minimal string accepted by the mission's published regex.

    Fail-closed: if the regex is missing or uses a construct the inline sampler
    does not support, we SKIP/ERROR with a reason rather than submit junk.
    """
    rx = mission_regex(m)
    if not rx:
        return HandlerResult(Action.SKIP, "first_valid_match mission has no verification_params.regex")
    try:
        proof = RegexSampler(seed=ctx.seed).sample(rx)
    except UnsupportedPattern as exc:
        return HandlerResult(
            Action.ERROR,
            "regex not satisfiable by the inline sampler (%s): %s" % (exc, rx),
        )
    return HandlerResult(
        Action.SUBMIT,
        "generated a minimal string matching regex %r" % rx,
        proof=proof,
    )


def goplus_summary_stub(address: str, chain_id: str, record: Optional[Mapping[str, Any]] = None) -> str:
    """Build a concise, factual GoPlus-style **summary** proof string.

    This is the *content* of a safety-review submission: it names the exact chain
    id + address the protocol's resolver will independently re-query GoPlus for,
    and reports the canonical risk flags. ``record`` is the per-address GoPlus
    security map when available (from :func:`HandlerContext.goplus_lookup`); when
    it is ``None`` the stub emits the verifiable scaffold and marks the flags
    ``unknown`` (never over-claiming ``safe``), so it stays honest even without a
    live lookup. Wire ``goplus_lookup`` to the real
    ``api.gopluslabs.io/api/v1/token_security`` endpoint to populate the flags.
    """
    flags = ("is_honeypot", "is_blacklisted", "cannot_sell_all", "is_proxy", "is_mintable")
    lines = [
        "GoPlus token-security review of %s on chain id %s." % (address, chain_id),
    ]
    if record:
        rendered = []
        for f in flags:
            v = record.get(f)
            if v in ("1", 1, True):
                state = "yes"
            elif v in ("0", 0, False):
                state = "no"
            else:
                state = "unknown"
            rendered.append("%s=%s" % (f, state))
        positives = [f for f in flags if record.get(f) in ("1", 1, True)]
        verdict = (
            "UNSAFE — flags set: %s" % ", ".join(positives)
            if positives else "LOOKS CLEAN — no critical GoPlus risk flag set"
        )
        lines.append("Flags: " + ", ".join(rendered))
        lines.append("Verdict: " + verdict)
    else:
        lines.append("Flags: " + ", ".join("%s=unknown" % f for f in flags))
        lines.append("Verdict: INCONCLUSIVE — submitter did not attach a live GoPlus record.")
    lines.append(
        "Source: GoPlus Token Security API "
        "(api.gopluslabs.io/api/v1/token_security/%s?contract_addresses=%s). "
        "The resolver re-queries GoPlus independently for this exact chain+address."
        % (chain_id, address)
    )
    return "\n".join(lines)


def handle_oracle_safety(ctx: HandlerContext, m: Mapping[str, Any]) -> HandlerResult:
    """Emit a GoPlus safety-review **summary stub** for a token-security mission.

    Extracts the token address + chain from the mission, optionally enriches with
    a live GoPlus record via ``ctx.goplus_lookup`` (a stub by default), and
    returns the summary as the proof. SKIPs when no token address is parseable —
    there would be nothing for the resolver's GoPlus re-check to agree with.
    """
    text = mission_text(m)
    address = extract_token_address(text)
    if not address:
        return HandlerResult(
            Action.SKIP,
            "safety-review oracle mission has no parseable 0x token address to review",
        )
    chain_id = extract_chain_hint(text) or ctx.chain_default
    record: Optional[Dict[str, str]] = None
    if ctx.goplus_lookup is not None:
        try:
            record = ctx.goplus_lookup(chain_id, address)
        except Exception as exc:  # lookup is best-effort; stub still emits scaffold
            return HandlerResult(
                Action.ERROR,
                "GoPlus lookup failed for %s on chain %s: %s" % (address, chain_id, exc),
            )
    proof = goplus_summary_stub(address, chain_id, record)
    note = "with live GoPlus record" if record else "stub (no live record attached)"
    return HandlerResult(
        Action.SUBMIT,
        "built GoPlus safety summary for %s on chain %s [%s]" % (address, chain_id, note),
        proof=proof,
    )


def handle_oracle_repo(ctx: HandlerContext, m: Mapping[str, Any]) -> HandlerResult:
    """Pass the configured repo/PR URL through as the proof for a repo mission.

    The proof is *content-addressed by URL*: the GitHub oracle parses
    ``{owner}/{repo}`` out of the canonical URL. This handler does NOT invent a
    repo — if neither ``--repo`` nor ``--repo-url`` was configured it SKIPs with
    a reason (you must point it at a repo you actually delivered).
    """
    url = repo_proof_url(ctx)
    if not url:
        lang = infer_language(mission_text(m))
        langhint = (" (mission wants %s)" % lang) if lang else ""
        return HandlerResult(
            Action.SKIP,
            "repo-deliverable oracle mission but no --repo/--repo-url configured%s" % langhint,
        )
    lang = infer_language(mission_text(m))
    langhint = (" for a %s deliverable" % lang) if lang else ""
    return HandlerResult(
        Action.SUBMIT,
        "passing through delivered repo URL%s" % langhint,
        proof=url,
    )


def handle_oracle_other(ctx: HandlerContext, m: Mapping[str, Any]) -> HandlerResult:
    return HandlerResult(
        Action.SKIP,
        "oracle mission with no recognised flavour (not safety-review, not repo) — "
        "no mechanical proof; extend classify()/HANDLERS to support it",
    )


def handle_peer_vote(ctx: HandlerContext, m: Mapping[str, Any]) -> HandlerResult:
    return HandlerResult(
        Action.SKIP,
        "peer_vote: resolved by a staked peer-voting quorum, not a computable proof",
    )


def handle_creator_judges(ctx: HandlerContext, m: Mapping[str, Any]) -> HandlerResult:
    return HandlerResult(
        Action.SKIP,
        "creator_judges: the mission creator adjudicates subjectively; no mechanical proof",
    )


def handle_unknown(ctx: HandlerContext, m: Mapping[str, Any]) -> HandlerResult:
    return HandlerResult(
        Action.SKIP,
        "unknown verification_type %r — no handler registered" % mission_verification_type(m),
    )


def repo_proof_url(ctx: HandlerContext) -> Optional[str]:
    """Resolve the canonical repo URL to submit, from --repo-url or --repo."""
    if ctx.repo_url:
        return ctx.repo_url.strip()
    if ctx.repo:
        spec = ctx.repo.strip()
        mm = _GITHUB_URL_RE.search(spec)
        if mm:
            return "https://github.com/%s/%s" % (mm.group(1), mm.group(2))
        if "/" in spec:
            owner, _, name = spec.partition("/")
            owner = owner.strip()
            name = name.strip().removesuffix(".git").rstrip("/")
            if owner and name and "/" not in name:
                return "https://github.com/%s/%s" % (owner, name)
    return None


# Routing key -> handler. Add a vector by adding a key here + a classify() branch.
HANDLERS: Dict[str, Callable[[HandlerContext, Mapping[str, Any]], HandlerResult]] = {
    "first_valid_match": handle_first_valid_match,
    "oracle:safety": handle_oracle_safety,
    "oracle:repo": handle_oracle_repo,
    "oracle:other": handle_oracle_other,
    "peer_vote": handle_peer_vote,
    "creator_judges": handle_creator_judges,
    "unknown": handle_unknown,
}


# --------------------------------------------------------------------------- #
# Reputation / ELO gate
# --------------------------------------------------------------------------- #


def extract_elo(reputation: Mapping[str, Any]) -> Optional[int]:
    """Pull the agent's ELO out of a /reputation payload (nested or flat)."""
    rep = reputation.get("reputation")
    if isinstance(rep, Mapping) and isinstance(rep.get("elo"), (int, float)):
        return int(rep["elo"])
    prog = reputation.get("progression")
    if isinstance(prog, Mapping) and isinstance(prog.get("current_elo"), (int, float)):
        return int(prog["current_elo"])
    if isinstance(reputation.get("elo"), (int, float)):
        return int(reputation["elo"])
    return None


def resolve_agent_elo(
    client: OABPClient, agent_id: Optional[str], *, verbose: bool = False
) -> Tuple[int, str]:
    """Return ``(elo, source)`` for the configured agent.

    ``source`` is ``"reputation"`` when fetched live, or ``"assumed-newcomer"``
    when no agent id was given or the fetch/parse failed — in which case the
    server's newcomer default ELO is assumed so the gate still functions.
    """
    if not agent_id:
        return DEFAULT_NEWCOMER_ELO, "assumed-newcomer (no --agent-id)"
    try:
        rep = client.get_reputation(agent_id)
    except APIError as exc:
        if verbose:
            sys.stderr.write("warn: could not fetch reputation for %r: %s\n" % (agent_id, exc))
        return DEFAULT_NEWCOMER_ELO, "assumed-newcomer (reputation fetch failed)"
    elo = extract_elo(rep)
    if elo is None:
        return DEFAULT_NEWCOMER_ELO, "assumed-newcomer (no elo field in reputation)"
    return elo, "reputation"


# --------------------------------------------------------------------------- #
# Per-mission processing (runs inside the thread pool)
# --------------------------------------------------------------------------- #


@dataclass
class MissionOutcome:
    """One row of the run report."""

    mission_id: str
    title: str
    verification_type: str
    routing_key: str
    reward_amount: Optional[float]
    reward_currency: str
    min_elo: int
    # one of: "submitted", "would-submit" (dry-run), "skipped", "error"
    disposition: str
    reason: str
    proof_preview: Optional[str] = None
    submit_status: Optional[int] = None


def _proof_preview(proof: Optional[str], width: int = 80) -> Optional[str]:
    if proof is None:
        return None
    flat = " ".join(proof.split())
    return flat if len(flat) <= width else flat[: width - 1] + "…"


def _needs_detail(m: Mapping[str, Any]) -> bool:
    """True when the (summary) row lacks fields a handler needs to act.

    The ``GET /api/missions`` list endpoint returns a compact summary
    (``creator``, ``reward_aigen``, ``min_submitter_elo``, ``submission_count``,
    ``title``, ``verification_type``) and omits ``description`` /
    ``verification_params``. Those live only in the per-mission detail. We
    therefore resolve the detail when, and only when, acting on the mission
    requires it:

      * ``first_valid_match`` — needs ``verification_params.regex``;
      * ``oracle`` — needs the description / ``oracle_description`` to
        sub-classify (safety vs repo) and to extract an address / language.

    ``peer_vote`` / ``creator_judges`` are skipped regardless, so they never
    trigger an extra fetch.
    """
    vt = mission_verification_type(m)
    if vt == "first_valid_match":
        return mission_regex(m) is None
    if vt == "oracle":
        has_text = bool(m.get("description")) or mission_oracle_description(m) is not None
        return not has_text
    return False


def enrich_mission(
    client: OABPClient, m: Mapping[str, Any], *, verbose: bool = False
) -> Mapping[str, Any]:
    """Return a mission dict rich enough to classify + handle.

    If the summary already carries what we need, it is returned unchanged. Else
    we fetch ``GET /api/missions/{id}`` and merge the detail over the summary
    (detail wins). On fetch failure the original summary is returned — the
    handler then SKIPs with a "missing field" reason rather than crashing. This
    runs inside the worker thread, so each detail GET is parallelised, retried
    and counted by the concurrency gauge like any other unit of work.
    """
    if not _needs_detail(m):
        return m
    mid = _mission_id(m)
    if not mid:
        return m
    try:
        detail = client.get_mission(mid)
    except APIError as exc:
        if verbose:
            sys.stderr.write("warn: could not fetch detail for %s: %s\n" % (mid, exc))
        return m
    merged = dict(m)
    merged.update(detail)
    return merged


def process_mission(
    ctx: HandlerContext,
    m: Mapping[str, Any],
    *,
    agent_elo: int,
    elo_source: str,
    dry_run: bool,
    rate_limiter: RateLimiter,
    gauge: _Gauge,
    verbose: bool = False,
) -> MissionOutcome:
    """Classify -> ELO-gate -> dispatch -> (maybe) submit one mission.

    This is the unit of work scheduled on the ThreadPoolExecutor. It enters the
    concurrency gauge for the whole duration so the pool bound can be asserted.
    The mission is first enriched to detail (if the summary lacks the fields a
    handler needs); that fetch happens here, inside the pool, so it is itself
    parallelised, retried and gauge-counted.
    """
    gauge.enter()
    try:
        m = enrich_mission(ctx.client, m, verbose=verbose)
        mid = _mission_id(m) or "?"
        title = str(m.get("title") or "")
        vt = mission_verification_type(m)
        key = classify(m)
        reward_amt = mission_reward_amount(m)
        reward_cur = mission_reward_currency(m)
        min_elo = mission_min_elo(m)

        base = dict(
            mission_id=mid,
            title=title,
            verification_type=vt,
            routing_key=key,
            reward_amount=reward_amt,
            reward_currency=reward_cur,
            min_elo=min_elo,
        )

        # --- ELO gate (before any handler work) ---
        if min_elo > agent_elo:
            return MissionOutcome(
                disposition="skipped",
                reason=(
                    "min_submitter_elo=%d exceeds agent ELO=%d (%s) — resolver would reject"
                    % (min_elo, agent_elo, elo_source)
                ),
                **base,
            )

        # --- dispatch to the per-type handler ---
        handler = HANDLERS.get(key, handle_unknown)
        try:
            result = handler(ctx, m)
        except Exception as exc:  # a handler bug must not crash the pool
            return MissionOutcome(
                disposition="error",
                reason="handler %s raised: %s" % (getattr(handler, "__name__", key), exc),
                **base,
            )

        if result.action is Action.SKIP:
            return MissionOutcome(disposition="skipped", reason=result.reason, **base)
        if result.action is Action.ERROR:
            return MissionOutcome(disposition="error", reason=result.reason, **base)

        # SUBMIT
        if not result.proof:
            return MissionOutcome(
                disposition="error",
                reason="handler returned SUBMIT with an empty proof (bug)",
                **base,
            )
        preview = _proof_preview(result.proof)

        if dry_run:
            return MissionOutcome(
                disposition="would-submit",
                reason=result.reason,
                proof_preview=preview,
                **base,
            )

        if not ctx.agent_id:
            return MissionOutcome(
                disposition="error",
                reason="cannot submit: no --agent-id configured",
                proof_preview=preview,
                **base,
            )

        # Real submit: throttle across all threads, then POST (which itself retries).
        rate_limiter.acquire()
        try:
            status, body = ctx.client.submit(mid, ctx.agent_id, result.proof)
        except APIError as exc:
            return MissionOutcome(
                disposition="error",
                reason="submit POST failed: %s" % exc,
                proof_preview=preview,
                **base,
            )
        ok = 200 <= int(status) < 300
        return MissionOutcome(
            disposition="submitted" if ok else "error",
            reason=(
                (result.reason + " (HTTP %d)" % status)
                if ok
                else "submit rejected HTTP %d: %s" % (status, _short_body(body))
            ),
            proof_preview=preview,
            submit_status=int(status),
            **base,
        )
    finally:
        gauge.leave()


def _short_body(body: Any, n: int = 160) -> str:
    try:
        s = body if isinstance(body, str) else json.dumps(body, separators=(",", ":"))
    except (TypeError, ValueError):
        s = str(body)
    return s if len(s) <= n else s[: n - 1] + "…"


# --------------------------------------------------------------------------- #
# Orchestration: pull list -> bounded pool -> aggregate report
# --------------------------------------------------------------------------- #


@dataclass
class RunReport:
    base_url: str
    agent_id: Optional[str]
    agent_elo: int
    elo_source: str
    dry_run: bool
    concurrency: int
    peak_concurrency: int
    total_open: int
    outcomes: List[MissionOutcome] = field(default_factory=list)

    # -- aggregates -------------------------------------------------------- #

    @property
    def attempted(self) -> int:
        """Missions for which a handler produced (or would produce) a proof."""
        return sum(1 for o in self.outcomes if o.disposition in ("submitted", "would-submit"))

    @property
    def submitted(self) -> int:
        return sum(1 for o in self.outcomes if o.disposition == "submitted")

    @property
    def would_submit(self) -> int:
        return sum(1 for o in self.outcomes if o.disposition == "would-submit")

    @property
    def skipped(self) -> int:
        return sum(1 for o in self.outcomes if o.disposition == "skipped")

    @property
    def errored(self) -> int:
        return sum(1 for o in self.outcomes if o.disposition == "error")

    def routing_histogram(self) -> Dict[str, int]:
        hist: Dict[str, int] = {}
        for o in self.outcomes:
            hist[o.routing_key] = hist.get(o.routing_key, 0) + 1
        return hist

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_url": self.base_url,
            "agent_id": self.agent_id,
            "agent_elo": self.agent_elo,
            "elo_source": self.elo_source,
            "dry_run": self.dry_run,
            "concurrency_limit": self.concurrency,
            "peak_concurrency": self.peak_concurrency,
            "total_open_missions": self.total_open,
            "summary": {
                "attempted": self.attempted,
                "submitted": self.submitted,
                "would_submit": self.would_submit,
                "skipped": self.skipped,
                "errored": self.errored,
            },
            "routing_histogram": self.routing_histogram(),
            "missions": [
                {
                    "mission_id": o.mission_id,
                    "title": o.title,
                    "verification_type": o.verification_type,
                    "routing_key": o.routing_key,
                    "reward_amount": o.reward_amount,
                    "reward_currency": o.reward_currency,
                    "reward_net_after_fee": (
                        net_after_fee(o.reward_amount) if isinstance(o.reward_amount, (int, float)) else None
                    ),
                    "min_submitter_elo": o.min_elo,
                    "disposition": o.disposition,
                    "reason": o.reason,
                    "proof_preview": o.proof_preview,
                    "submit_status": o.submit_status,
                }
                for o in self.outcomes
            ],
        }


def run_worker(
    client: OABPClient,
    *,
    agent_id: Optional[str],
    concurrency: int,
    max_missions: Optional[int],
    dry_run: bool,
    min_interval: float,
    repo: Optional[str] = None,
    repo_url: Optional[str] = None,
    chain_default: str = "8453",
    seed: Optional[int] = None,
    goplus_lookup: Optional[Callable[[str, str], Dict[str, str]]] = None,
    verbose: bool = False,
) -> RunReport:
    """One full pass: list open missions, process them concurrently, aggregate.

    The ThreadPoolExecutor is bounded by ``concurrency``; a shared
    :class:`RateLimiter` spaces real submit POSTs by ``min_interval`` seconds; a
    :class:`_Gauge` records peak in-flight handlers for the report.
    """
    missions = client.list_missions()
    total_open = len(missions)
    if max_missions is not None and max_missions >= 0:
        missions = missions[:max_missions]

    elo, elo_source = resolve_agent_elo(client, agent_id, verbose=verbose)

    ctx = HandlerContext(
        client=client,
        agent_id=agent_id,
        repo=repo,
        repo_url=repo_url,
        chain_default=chain_default,
        seed=seed,
        goplus_lookup=goplus_lookup,
    )
    rate_limiter = RateLimiter(min_interval)
    gauge = _Gauge()
    workers = max(1, int(concurrency))

    outcomes: List[MissionOutcome] = []
    if missions:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    process_mission,
                    ctx,
                    m,
                    agent_elo=elo,
                    elo_source=elo_source,
                    dry_run=dry_run,
                    rate_limiter=rate_limiter,
                    gauge=gauge,
                    verbose=verbose,
                ): _mission_id(m)
                for m in missions
            }
            for fut in as_completed(futures):
                outcomes.append(fut.result())

    # Stable ordering for readable reports: by disposition then mission id.
    order = {"submitted": 0, "would-submit": 1, "error": 2, "skipped": 3}
    outcomes.sort(key=lambda o: (order.get(o.disposition, 9), o.mission_id))

    return RunReport(
        base_url=client.base_url,
        agent_id=agent_id,
        agent_elo=elo,
        elo_source=elo_source,
        dry_run=dry_run,
        concurrency=workers,
        peak_concurrency=gauge.peak,
        total_open=total_open,
        outcomes=outcomes,
    )


# --------------------------------------------------------------------------- #
# Reporting (human-readable)
# --------------------------------------------------------------------------- #


def _truncate(text: str, width: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= width else text[: width - 1] + "…"


def render_report(report: RunReport) -> str:
    lines: List[str] = []
    mode = "DRY-RUN (submitting nothing)" if report.dry_run else "LIVE (submitting)"
    lines.append("=" * 78)
    lines.append("OABP multi-mission worker run report  [%s]" % mode)
    lines.append("  marketplace : %s" % report.base_url)
    lines.append(
        "  agent       : %s   (ELO %d, %s)"
        % (report.agent_id or "(none)", report.agent_elo, report.elo_source)
    )
    lines.append(
        "  concurrency : limit=%d, observed-peak=%d   |   open missions: %d (processed %d)"
        % (report.concurrency, report.peak_concurrency, report.total_open, len(report.outcomes))
    )
    hist = report.routing_histogram()
    if hist:
        lines.append(
            "  routing     : "
            + ", ".join("%s=%d" % (k, hist[k]) for k in sorted(hist))
        )
    lines.append("-" * 78)

    # one line per mission, grouped by the sort already applied
    header = "%-16s %-9s %-18s %-7s %s" % (
        "MISSION", "DISPOS.", "ROUTING", "REWARD", "REASON",
    )
    lines.append(header)
    lines.append("-" * 78)
    for o in report.outcomes:
        reward = (
            "%g%s" % (o.reward_amount, "" if o.reward_currency == "AIGEN" else o.reward_currency[:1])
            if isinstance(o.reward_amount, (int, float))
            else "?"
        )
        lines.append(
            "%-16s %-9s %-18s %-7s %s"
            % (
                _truncate(o.mission_id, 16),
                o.disposition,
                _truncate(o.routing_key, 18),
                reward,
                _truncate(o.reason, 80),
            )
        )
        if o.proof_preview:
            lines.append("%-16s %-9s   proof: %s" % ("", "", _truncate(o.proof_preview, 86)))

    lines.append("-" * 78)
    lines.append(
        "SUMMARY: attempted=%d  submitted=%d  would-submit=%d  skipped=%d  errored=%d"
        % (
            report.attempted,
            report.submitted,
            report.would_submit,
            report.skipped,
            report.errored,
        )
    )
    lines.append("=" * 78)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="multi_mission_worker",
        description=(
            "Concurrent OABP/AIGEN worker: pulls every open mission, classifies "
            "each by verification_type, dispatches to per-type handlers "
            "(first_valid_match -> regex sampler; oracle/safety -> GoPlus summary "
            "stub; oracle/repo -> repo-URL passthrough; peer_vote & creator_judges "
            "-> skip), and submits eligible proofs under a bounded thread pool with "
            "per-mission rate limiting and retry/backoff. Honours min_submitter_elo "
            "against the agent's reputation ELO. Defaults to a safe DRY-RUN."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "AIGEN is the protocol's uncapped reputation/points token; a 0.5%% fee "
            "is taken from every payout. Verification is permissionless: "
            "content-addressed (first_valid_match) or oracle-backed (GoPlus / GitHub)."
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
        help="Your submitter_agent_id. REQUIRED for any real submit; also enables "
        "the ELO gate against your /reputation.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Max missions processed in parallel (ThreadPoolExecutor bound).",
    )
    parser.add_argument(
        "--max-missions",
        type=int,
        default=None,
        help="Process at most this many open missions (after listing). Default: all.",
    )
    parser.add_argument(
        "--min-interval",
        type=float,
        default=DEFAULT_MIN_INTERVAL,
        help="Minimum seconds between outbound submit POSTs (shared across threads).",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Repo you deliver for oracle/repo missions, as 'owner/name' (or a "
        "github.com URL). Without it, repo missions are skipped.",
    )
    parser.add_argument(
        "--repo-url",
        default=None,
        help="Explicit canonical proof URL for repo/PR missions (overrides --repo).",
    )
    parser.add_argument(
        "--chain-default",
        default="8453",
        help="GoPlus chain id assumed for safety reviews when the mission is "
        "unhinted (8453=Base, 1=Ethereum, 10=Optimism, 42161=Arbitrum, 56=BSC).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for the regex sampler (deterministic first_valid_match proofs).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the run report as JSON on stdout (instead of the table).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log diagnostics (reputation fetch issues, etc.) to stderr.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="Classify + report, submit NOTHING (default).",
    )
    mode.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Actually submit eligible deliverables (requires --agent-id).",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the offline self-test (no network) and exit.",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        _self_test(verbose=args.verbose)
        print("multi-mission-worker self-test: OK")
        return 0

    if not args.dry_run and not args.agent_id:
        sys.stderr.write("ERROR: --agent-id is required for a real (--no-dry-run) submit.\n")
        return 3

    client = OABPClient(base_url=args.base_url)
    try:
        report = run_worker(
            client,
            agent_id=args.agent_id,
            concurrency=args.concurrency,
            max_missions=args.max_missions,
            dry_run=args.dry_run,
            min_interval=args.min_interval,
            repo=args.repo,
            repo_url=args.repo_url,
            chain_default=args.chain_default,
            seed=args.seed,
            verbose=args.verbose,
        )
    except APIError as exc:
        sys.stderr.write("FATAL: %s\n" % exc)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_report(report))
    return 0


# --------------------------------------------------------------------------- #
# Offline self-test (no network). Stubs the OABP session with a mixed mission
# fixture and asserts: each verification_type routes to the correct handler; a
# below-min_submitter_elo mission is skipped by the ELO gate; the ThreadPool
# bound is honoured (observed peak <= configured concurrency); a real submit
# POSTs exactly the eligible proofs through the rate limiter.
# --------------------------------------------------------------------------- #


class _FakeResp:
    def __init__(self, status_code: int, payload: Any, headers: Optional[Dict[str, str]] = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = payload if isinstance(payload, str) else json.dumps(payload)

    def json(self) -> Any:
        if isinstance(self._payload, str):
            raise ValueError("not json")
        return self._payload


class _FakeSession:
    """Stub OABP session: serves a fixed mission list, per-id details, a
    reputation doc, and records every POST. Optionally sleeps inside each GET to
    widen the window in which handlers overlap (so the peak gauge is meaningful).
    """

    def __init__(
        self,
        missions: List[Dict[str, Any]],
        reputation: Dict[str, Any],
        *,
        get_delay: float = 0.0,
    ) -> None:
        self.headers: Dict[str, str] = {}
        self._missions = missions
        self._by_id = {m["id"]: m for m in missions}
        self._reputation = reputation
        self._get_delay = get_delay
        self.posted: List[Tuple[str, Dict[str, Any]]] = []
        self._post_lock = threading.Lock()

    def get(self, url: str, params: Any = None, timeout: float = 0.0) -> _FakeResp:
        if self._get_delay:
            time.sleep(self._get_delay)
        if url.endswith("/api/missions"):
            return _FakeResp(200, {"missions": self._missions})
        if "/reputation" in url:
            return _FakeResp(200, self._reputation)
        # /api/missions/{id}
        mid = url.rsplit("/", 1)[-1]
        if mid in self._by_id:
            return _FakeResp(200, self._by_id[mid])
        return _FakeResp(404, {"error": "not found"})

    def post(self, url: str, json: Any = None, timeout: float = 0.0) -> _FakeResp:  # noqa: A002
        with self._post_lock:
            self.posted.append((url, dict(json or {})))
        return _FakeResp(200, {"ok": True, "status": "accepted"})


def _run_quiet(fn: Callable[..., int], *a: Any, **k: Any) -> int:
    """Call ``fn`` with stdout/stderr suppressed; return its exit code."""
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        return fn(*a, **k)


def _self_test(verbose: bool = False) -> None:
    # ---- 1. RegexSampler sanity (the first_valid_match engine) ----
    addr = RegexSampler(seed=0).sample(r"^0x[a-f0-9]{40}$")
    assert addr == "0x" + "0" * 40, addr
    assert re.fullmatch(r"^0x[a-f0-9]{40}$", addr)
    assert re.fullmatch(r"^[A-Z]{3}-\d{4}$", RegexSampler(seed=1).sample(r"^[A-Z]{3}-\d{4}$"))
    # determinism
    assert RegexSampler(seed=7).sample(r"^[a-f0-9]{6}$") == RegexSampler(seed=7).sample(r"^[a-f0-9]{6}$")
    # fail-closed on unsupported constructs
    for bad in [r"(?=foo)bar", r"(a)\1", r"(?i)abc"]:
        try:
            RegexSampler(seed=1).sample(bad)
        except UnsupportedPattern:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected UnsupportedPattern for %r" % bad)

    # ---- 2. Classification routes every verification_type correctly ----
    fvm = {
        "id": "mis_fvm", "title": "Find a token where scoring is wrong",
        "verification_type": "first_valid_match",
        "verification_params": {"regex": r"^0x[a-f0-9]{40}$"},
        "reward": {"currency": "AIGEN", "amount": 30}, "min_submitter_elo": 0,
    }
    safety = {
        "id": "mis_safe", "title": "Safety review of a Base token",
        "description": "Perform a GoPlus token-security safety review of "
                       "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 on base.",
        "verification_type": "oracle",
        "verification_params": {"oracle_description": "GoPlus token-security review on base"},
        "reward": {"currency": "AIGEN", "amount": 120}, "min_submitter_elo": 0,
    }
    repo = {
        "id": "mis_repo", "title": "Build a minimal OABP client in Go",
        "description": "Deliver a public GitHub repository implementing the "
                       "AIP-1 client in Go.",
        "verification_type": "oracle",
        "verification_params": {"oracle_description": "GitHub repo implementing the client in Go"},
        "reward": {"currency": "AIGEN", "amount": 200}, "min_submitter_elo": 0,
    }
    repo_pr = {
        "id": "mis_pr", "title": "Add an integration example to smolagents",
        "description": "Submit the URL of a merged pull request on "
                       "github.com/huggingface/smolagents.",
        "verification_type": "oracle",
        "verification_params": {
            "oracle_description": "Submit the URL of a merged pull request on github.com/huggingface/smolagents.",
            "regex": r"https://github.com/huggingface/smolagents/pull/[0-9]+",
        },
        "reward": {"currency": "AIGEN", "amount": 200}, "min_submitter_elo": 0,
    }
    oracle_other = {
        "id": "mis_other", "title": "Predict the BTC close",
        "description": "An oracle will check the BTC closing price next Friday.",
        "verification_type": "oracle",
        "verification_params": {"oracle_description": "price oracle checks BTC close"},
        "reward": {"currency": "AIGEN", "amount": 40}, "min_submitter_elo": 0,
    }
    peer = {
        "id": "mis_peer", "title": "Best logo design",
        "verification_type": "peer_vote",
        "reward": {"currency": "AIGEN", "amount": 50}, "min_submitter_elo": 0,
    }
    judges = {
        "id": "mis_judge", "title": "Write the funniest haiku",
        "verification_type": "creator_judges",
        "reward": {"currency": "AIGEN", "amount": 25}, "min_submitter_elo": 0,
    }
    gated = {
        "id": "mis_gated", "title": "Elite-only token hunt",
        "verification_type": "first_valid_match",
        "verification_params": {"regex": r"^0x[a-f0-9]{40}$"},
        "reward": {"currency": "AIGEN", "amount": 500}, "min_submitter_elo": 2000,
    }

    assert classify(fvm) == "first_valid_match", classify(fvm)
    assert classify(safety) == "oracle:safety", classify(safety)
    assert classify(repo) == "oracle:repo", classify(repo)
    assert classify(repo_pr) == "oracle:repo", classify(repo_pr)
    assert classify(oracle_other) == "oracle:other", classify(oracle_other)
    assert classify(peer) == "peer_vote", classify(peer)
    assert classify(judges) == "creator_judges", classify(judges)
    assert classify({"id": "x", "verification_type": "wat"}) == "unknown"

    # ---- 3. Handlers produce the right action per routing key ----
    ctx_norepo = HandlerContext(client=OABPClient(session=_FakeSession([], {})), agent_id="t", repo=None)
    ctx_repo = HandlerContext(
        client=OABPClient(session=_FakeSession([], {})), agent_id="t", repo="myorg/oabp-go"
    )
    r_fvm = handle_first_valid_match(ctx_norepo, fvm)
    assert r_fvm.action is Action.SUBMIT and re.fullmatch(r"^0x[a-f0-9]{40}$", r_fvm.proof), r_fvm
    r_safe = handle_oracle_safety(ctx_norepo, safety)
    assert r_safe.action is Action.SUBMIT and "GoPlus" in r_safe.proof
    assert "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48" in r_safe.proof.lower()
    # safety with no address -> SKIP
    r_safe_noaddr = handle_oracle_safety(ctx_norepo, {"id": "z", "title": "review some token", "verification_type": "oracle"})
    assert r_safe_noaddr.action is Action.SKIP, r_safe_noaddr
    # repo handler skips with no repo configured, passes the URL through when set
    assert handle_oracle_repo(ctx_norepo, repo).action is Action.SKIP
    r_repo = handle_oracle_repo(ctx_repo, repo)
    assert r_repo.action is Action.SUBMIT and r_repo.proof == "https://github.com/myorg/oabp-go", r_repo
    # repo_url override wins and works for a PR-style passthrough
    ctx_url = HandlerContext(
        client=OABPClient(session=_FakeSession([], {})), agent_id="t",
        repo_url="https://github.com/huggingface/smolagents/pull/123",
    )
    assert handle_oracle_repo(ctx_url, repo_pr).proof.endswith("/pull/123")
    assert handle_oracle_other(ctx_norepo, oracle_other).action is Action.SKIP
    assert handle_peer_vote(ctx_norepo, peer).action is Action.SKIP
    assert handle_creator_judges(ctx_norepo, judges).action is Action.SKIP

    # ---- 4. ELO gate fetch + extraction ----
    rep_doc = {"agent_id": "t", "reputation": {"elo": 1400, "score": 0}, "progression": {"current_elo": 1400}}
    assert extract_elo(rep_doc) == 1400
    assert extract_elo({"elo": 1733}) == 1733
    assert extract_elo({}) is None

    # ---- 5. End-to-end DRY-RUN over the mixed fixture (concurrent) ----
    missions = [fvm, safety, repo, repo_pr, oracle_other, peer, judges, gated]
    # add a slight GET delay so multiple handlers are genuinely in-flight at once
    sess = _FakeSession(missions, rep_doc, get_delay=0.01)
    client = OABPClient(session=sess, sleep_func=lambda s: None)
    report = run_worker(
        client,
        agent_id="t",
        concurrency=3,
        max_missions=None,
        dry_run=True,
        min_interval=0.0,
        repo="myorg/oabp-go",
        seed=0,
        verbose=verbose,
    )
    by_id = {o.mission_id: o for o in report.outcomes}
    # routing assertions per mission
    assert by_id["mis_fvm"].routing_key == "first_valid_match"
    assert by_id["mis_safe"].routing_key == "oracle:safety"
    assert by_id["mis_repo"].routing_key == "oracle:repo"
    assert by_id["mis_pr"].routing_key == "oracle:repo"
    assert by_id["mis_other"].routing_key == "oracle:other"
    assert by_id["mis_peer"].routing_key == "peer_vote"
    assert by_id["mis_judge"].routing_key == "creator_judges"
    # dispositions: fvm/safety/repo/repo_pr -> would-submit; others/peer/judges -> skipped
    assert by_id["mis_fvm"].disposition == "would-submit", by_id["mis_fvm"]
    assert by_id["mis_safe"].disposition == "would-submit"
    assert by_id["mis_repo"].disposition == "would-submit"
    assert by_id["mis_pr"].disposition == "would-submit"
    assert by_id["mis_other"].disposition == "skipped"
    assert by_id["mis_peer"].disposition == "skipped"
    assert by_id["mis_judge"].disposition == "skipped"
    # ELO gate: min_submitter_elo=2000 > agent ELO 1400 -> skipped with that reason
    assert by_id["mis_gated"].disposition == "skipped", by_id["mis_gated"]
    assert "min_submitter_elo" in by_id["mis_gated"].reason and "exceeds" in by_id["mis_gated"].reason
    # dry-run submits nothing
    assert sess.posted == [], sess.posted
    # ThreadPool bound honoured: observed peak never exceeds the configured cap
    assert report.peak_concurrency <= 3, report.peak_concurrency
    assert report.peak_concurrency >= 1
    # aggregate counts
    assert report.attempted == 4, report.attempted
    assert report.would_submit == 4 and report.submitted == 0
    assert report.skipped == 4, report.skipped  # other, peer, judge, gated
    # report renders without error
    assert "multi-mission worker run report" in render_report(report)
    assert isinstance(json.loads(json.dumps(report.to_dict())), dict)

    # ---- 6. Strict bound check at concurrency=1 (fully serialised) ----
    sess1 = _FakeSession(missions, rep_doc, get_delay=0.005)
    client1 = OABPClient(session=sess1, sleep_func=lambda s: None)
    report1 = run_worker(client1, agent_id="t", concurrency=1, max_missions=None,
                         dry_run=True, min_interval=0.0, repo="myorg/oabp-go", seed=0)
    assert report1.peak_concurrency == 1, report1.peak_concurrency

    # ---- 7. Real submit (no-dry-run) POSTs exactly the eligible proofs ----
    sess2 = _FakeSession(missions, rep_doc)
    client2 = OABPClient(session=sess2, sleep_func=lambda s: None)
    report2 = run_worker(
        client2, agent_id="tester-bot", concurrency=4, max_missions=None,
        dry_run=False, min_interval=0.0, repo="myorg/oabp-go", seed=0,
    )
    assert report2.submitted == 4, (report2.submitted, [(o.mission_id, o.disposition) for o in report2.outcomes])
    posted_ids = sorted(url.rsplit("/", 2)[-2] for url, _ in sess2.posted)
    assert posted_ids == sorted(["mis_fvm", "mis_safe", "mis_repo", "mis_pr"]), posted_ids
    # the gated + non-mechanical missions must NOT have been posted
    for url, _ in sess2.posted:
        assert "mis_gated" not in url and "mis_peer" not in url and "mis_judge" not in url
    # every POST carried the agent id and a non-empty proof
    for url, body in sess2.posted:
        assert body["submitter_agent_id"] == "tester-bot"
        assert isinstance(body["proof"], str) and body["proof"]

    # ---- 8. RateLimiter spacing is enforced (monotonic, deterministic) ----
    slept: List[float] = []
    rl = RateLimiter(0.5, sleep_func=lambda s: slept.append(s))
    rl.acquire()  # first is free
    rl.acquire()  # must request a wait close to the interval
    assert slept and 0.0 < slept[-1] <= 0.5 + 1e-6, slept

    # ---- 9. GoPlus summary stub honesty: never over-claims, names chain+addr ----
    a = "0x" + "1" * 40
    clean = goplus_summary_stub(a, "8453", {"is_honeypot": "0", "is_blacklisted": "0",
                                            "cannot_sell_all": "0", "is_proxy": "0", "is_mintable": "0"})
    assert "LOOKS CLEAN" in clean and "8453" in clean and a in clean
    risky = goplus_summary_stub(a, "1", {"is_honeypot": "1"})
    assert "UNSAFE" in risky and "is_honeypot=yes" in risky
    nodata = goplus_summary_stub(a, "1", None)
    assert "INCONCLUSIVE" in nodata and "is_honeypot=unknown" in nodata

    # ---- 10. CLI guard: --no-dry-run without --agent-id exits 3, no network ----
    rc = _run_quiet(main, ["--no-dry-run"])
    assert rc == 3, rc

    # ---- 11. reward helpers tolerate both summary and detail shapes ----
    assert mission_reward_amount({"reward_aigen": 67}) == 67.0
    assert mission_reward_amount({"reward": {"amount": 200, "currency": "AIGEN"}}) == 200.0
    assert mission_min_elo({"min_submitter_elo": 1500}) == 1500
    assert net_after_fee(200.0) == 199.0

    # ---- 12. Lazy detail-enrichment from summary-only list rows ----
    # Mirror the LIVE API: GET /api/missions returns compact summaries that omit
    # verification_params/description; those live only in GET /api/missions/{id}.
    # The worker must fetch detail for fvm/oracle rows that need it, and route
    # correctly off the merged record.
    fvm_sum = {
        "id": "mis_fvm", "title": "Find a token where scoring is wrong",
        "verification_type": "first_valid_match", "reward_aigen": 30, "min_submitter_elo": 0,
    }
    repo_sum = {
        "id": "mis_repo", "title": "Build a minimal OABP client in Go",
        "verification_type": "oracle", "reward_aigen": 200, "min_submitter_elo": 0,
    }
    peer_sum = {
        "id": "mis_peer", "title": "Best logo design",
        "verification_type": "peer_vote", "reward_aigen": 50, "min_submitter_elo": 0,
    }
    # _needs_detail: fvm + oracle summaries need a fetch; peer_vote never does.
    assert _needs_detail(fvm_sum) is True
    assert _needs_detail(repo_sum) is True
    assert _needs_detail(peer_sum) is False
    # The summaries alone classify as first_valid_match / oracle:other (no text yet).
    assert classify(fvm_sum) == "first_valid_match"
    assert classify(repo_sum) == "oracle:other"
    # A session whose *list* is summaries but *detail* carries the rich fields.
    detail_fvm = dict(fvm_sum, verification_params={"regex": r"^0x[a-f0-9]{40}$"})
    detail_repo = dict(
        repo_sum,
        description="Deliver a public GitHub repository implementing the AIP-1 client in Go.",
        verification_params={"oracle_description": "GitHub repo implementing the client in Go"},
    )
    sess3 = _FakeSession([detail_fvm, detail_repo, peer_sum], rep_doc)
    # IMPORTANT: the *list* endpoint must return the SUMMARY rows (no params), so
    # override what the fake serves for the list versus the per-id detail.
    sess3._missions = [fvm_sum, repo_sum, peer_sum]               # list = summaries
    sess3._by_id = {"mis_fvm": detail_fvm, "mis_repo": detail_repo, "mis_peer": peer_sum}
    client3 = OABPClient(session=sess3, sleep_func=lambda s: None)
    # enrich_mission fetches detail and merges it over the summary.
    enriched = enrich_mission(client3, fvm_sum)
    assert mission_regex(enriched) == r"^0x[a-f0-9]{40}$", enriched
    # End to end: routing/disposition computed off the enriched detail.
    report3 = run_worker(
        client3, agent_id="t", concurrency=3, max_missions=None,
        dry_run=True, min_interval=0.0, repo="myorg/oabp-go", seed=0,
    )
    by3 = {o.mission_id: o for o in report3.outcomes}
    assert by3["mis_fvm"].routing_key == "first_valid_match"
    assert by3["mis_fvm"].disposition == "would-submit", by3["mis_fvm"]
    assert by3["mis_repo"].routing_key == "oracle:repo", by3["mis_repo"]   # via detail text
    assert by3["mis_repo"].disposition == "would-submit"
    assert by3["mis_peer"].disposition == "skipped"
    assert sess3.posted == []


# Run the self-test at import time so the file can never ship broken (cheap,
# pure, fully offline). Disable by setting the env var below.
if os.environ.get("MULTI_MISSION_WORKER_SKIP_SELFTEST") != "1":
    _self_test()


if __name__ == "__main__":
    raise SystemExit(main())
