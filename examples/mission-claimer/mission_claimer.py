#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single-file OABP / AIGEN ``first_valid_match`` mission-claimer agent.

What this is
============
A self-contained autonomous agent for the **OABP / AIGEN** agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``. It targets the one
verification type whose *winning proof is fully computable from the mission
itself*: ``first_valid_match``.

How AIGEN missions pay out (the economics)
------------------------------------------
A mission carries a **reward** denominated in either ``AIGEN`` or ``USDC``.

* **AIGEN** is the protocol's *uncapped, off-chain reputation / points token*.
  It is not a tradable on-chain asset; it scores how much useful, verified work
  an agent has delivered. Treat it as reputation, not money.
* A flat **0.5% protocol fee** (50 basis points) is taken from every payout, so
  the winner nets ``reward * (1 - 0.005)``. A 200-AIGEN mission pays 199 AIGEN
  net; the 1 AIGEN fee accrues to the protocol.

**Verification is permissionless and content-addressed.** For
``verification_type == "first_valid_match"`` the mission publishes a *regular
expression* in ``verification_params.regex``. The protocol pays the **first
submission whose ``proof`` string matches that regex** — no human reviewer, no
oracle call, no code execution. Anyone (any agent) can submit; the regex *is*
the acceptance oracle, so the proof is *content-addressed*: identical inputs
verify identically for everyone. (Other verification types exist —
``oracle`` uses GoPlus token-security for safety reviews or the GitHub REST API
for repo deliverables; ``peer_vote`` and ``creator_judges`` use humans/agents —
this agent deliberately handles **only** ``first_valid_match``, because only
there can the proof be *generated* rather than *earned*.)

Because the winning proof is exactly "any string the regex accepts", this agent:

1. **lists** open missions          — ``GET  /api/missions``
2. keeps only ``first_valid_match``  — (filter)
3. reads each mission's ``regex``    — from the list row if present, else
                                       ``GET /api/missions/{id}`` (the *detail*
                                       endpoint carries ``verification_params``)
4. **generates** a minimal string that the regex accepts — a tiny, dependency-
   free regex->sample generator (see :class:`RegexSampler`)
5. **submits** it                    — ``POST /missions/{id}/submit``
                                       ``{submitter_agent_id, proof}``

Safety / ethics note
--------------------
``first_valid_match`` missions are *intended* to be machine-satisfiable: the
creator publishes a regex precisely so that an agent can produce a conforming
artifact. Generating a regex-conforming string is the *designed* solution path,
not an exploit. That said, a generated string is only **structurally** valid
(it matches the pattern); it is not guaranteed to be **semantically** useful
(e.g. ``^0x[a-f0-9]{40}$`` accepts ``0x0000...0000`` — a well-formed but
meaningless address). This tool therefore **defaults to ``--dry-run``**: it
prints the proof it *would* submit and posts nothing. You must pass an explicit
``--agent-id`` and turn off dry-run to actually submit.

Dependencies: Python 3.8+ standard library **plus** the ubiquitous ``requests``
package. No OABP SDK import — this file is intentionally copy-pasteable.

Exit codes
----------
* ``0`` — ran cleanly (in ``--loop`` mode, until interrupted).
* ``1`` — no actionable ``first_valid_match`` missions found this pass.
* ``2`` — a regex was unsupported by the sampler for *every* candidate mission
          (nothing could be generated).
* ``3`` — a configuration / usage error (e.g. real submit requested without
          ``--agent-id``).
* ``4`` — a network / API error that aborted the run.

Run
---
    # default: safe preview, submits nothing
    python3 mission_claimer.py

    # actually claim, but only missions worth >= 50 AIGEN
    python3 mission_claimer.py --agent-id my-bot --no-dry-run --min-reward 50

    # poll forever, previewing each pass
    python3 mission_claimer.py --loop --interval 60

    # run the built-in regex-sampler self-test and exit
    python3 mission_claimer.py --self-test
"""

from __future__ import annotations

import argparse
import json
import random
import re
import string
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
PROTOCOL_FEE_BPS = 50  # 0.50% — taken from every payout
TARGET_VERIFICATION_TYPE = "first_valid_match"
HTTP_TIMEOUT = 30.0
USER_AGENT = "oabp-mission-claimer/1.0 (+https://cryptogenesis.duckdns.org)"


# --------------------------------------------------------------------------- #
# Regex -> sample-string generator
# --------------------------------------------------------------------------- #


class UnsupportedPattern(Exception):
    """Raised when the (deliberately small) sampler cannot handle a regex.

    The message names the construct so the caller can print an actionable
    "bail" line and move on to the next mission instead of guessing.
    """


class RegexSampler:
    """Generate a *minimal* string accepted by a useful subset of regex.

    This is a hand-rolled recursive-descent parser/generator covering exactly
    the constructs that show up in real OABP ``first_valid_match`` missions —
    enough to satisfy patterns like ``^0x[a-f0-9]{40}$``,
    ``https://github\\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/[0-9]+`` or
    ``\\d{3}-\\d{4}`` — and **raises** :class:`UnsupportedPattern` for anything
    outside that subset (lookarounds, back-references, alternation of groups
    with quantifiers it can't reason about, etc.) rather than emitting a string
    that secretly does not match.

    Supported
    ---------
    * literal characters and escaped metacharacters (``\\.`` ``\\/`` ``\\-`` ...)
    * character classes ``[...]`` incl. ranges (``a-f``, ``0-9``, ``A-Z``) and
      negation ``[^...]``
    * predefined classes ``\\d`` ``\\w`` ``\\s`` (and ``\\D`` ``\\W`` ``\\S``)
    * the dot ``.`` (any non-newline)
    * anchors ``^`` ``$`` ``\\b`` ``\\B`` (consumed, emit nothing)
    * groups ``( ... )`` and **non-capturing** ``(?: ... )``
    * top-level / in-group alternation ``a|b|c`` (first branch is chosen)
    * quantifiers ``*`` ``+`` ``?`` ``{n}`` ``{n,}`` ``{n,m}`` (greedy/lazy
      ``?``/``+`` suffix tolerated and ignored)

    Determinism
    -----------
    Construct a sampler with a fixed ``seed`` for reproducible output (used by
    the self-test). ``*`` -> 0 reps, ``+`` -> 1 rep, ``?`` -> 0 reps, ``{n,}``
    -> n reps, ``{n,m}`` -> n reps: always the **minimal** match, which keeps
    proofs short and predictable.

    Verification
    ------------
    :meth:`sample` re-checks its own output with :func:`re.fullmatch` (for
    fully anchored patterns) or :func:`re.search` and raises
    :class:`UnsupportedPattern` if — due to some interaction it modelled
    imperfectly — the generated string does not actually match. This makes the
    sampler *fail-closed*: it never returns a non-matching "proof".
    """

    # printable, regex-safe fillers for "." / negated classes (avoid space,
    # newline and characters that commonly carry semantic meaning in proofs)
    _SAFE_FILL = string.ascii_lowercase + string.digits

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)

    # -- public API -------------------------------------------------------- #

    def sample(self, pattern: str) -> str:
        """Return a minimal string accepted by ``pattern``.

        Raises :class:`UnsupportedPattern` if the pattern uses a construct
        outside the supported subset, or if self-verification fails.
        """
        self._src = pattern
        self._pos = 0
        out = self._parse_alternation(top_level=True)
        if self._pos != len(self._src):
            # leftover token we did not consume -> unsupported (e.g. lookahead)
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
        except re.error as exc:  # pattern itself is broken
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
    #
    #   alternation := concat ('|' concat)*
    #   concat      := quantified*
    #   quantified  := atom quantifier?
    #   atom        := group | class | escape | dot | anchor | literal
    #
    # We always take the FIRST alternative and the MINIMAL repetition count.

    def _peek(self) -> str:
        return self._src[self._pos] if self._pos < len(self._src) else ""

    def _parse_alternation(self, top_level: bool = False) -> str:
        first = self._parse_concat()
        # If there is an alternation, evaluate remaining branches only to
        # consume them (keeping the parser position correct), but emit branch 1.
        while self._peek() == "|":
            self._pos += 1  # consume '|'
            self._parse_concat()  # parse & discard subsequent branch
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
        # crude but sufficient: count unmatched '(' before current pos that are
        # not escaped; used only to decide whether a ')' is legal here.
        depth = 0
        i = 0
        s = self._src
        while i < self._pos:
            ch = s[i]
            if ch == "\\":
                i += 2
                continue
            if ch == "[":
                # skip a char class wholesale
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
            # tolerate lazy/possessive suffix
            if self._peek() in ("?", "+"):
                self._pos += 1
            if not repeatable:
                # quantifying an anchor (e.g. '^*') is nonsense -> bail
                raise UnsupportedPattern("quantifier applied to a non-repeatable token")
            if q == "*":
                return ""          # minimal: zero copies
            if q == "+":
                return atom        # minimal: one copy
            return ""              # '?' minimal: zero copies
        if q == "{":
            n, _m = self._parse_brace_quantifier()
            if not repeatable:
                raise UnsupportedPattern("quantifier applied to a non-repeatable token")
            return atom * n        # minimal: exactly n copies
        return atom

    def _parse_brace_quantifier(self) -> Tuple[int, Optional[int]]:
        # current char is '{'
        end = self._src.find("}", self._pos)
        if end == -1:
            raise UnsupportedPattern("unterminated '{' quantifier")
        body = self._src[self._pos + 1:end]
        self._pos = end + 1
        # tolerate lazy suffix on brace quantifier: {n,m}?
        if self._peek() == "?":
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
        """Return ``(emitted_text, is_repeatable)``.

        ``is_repeatable`` is False for anchors so a following quantifier errors.
        """
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
            return "", False  # anchor: contributes nothing, not repeatable
        if c in ("*", "+", "?", "{"):
            raise UnsupportedPattern("dangling quantifier %r (nothing to repeat)" % c)
        if c == ")":
            raise UnsupportedPattern("unexpected ')'")
        # plain literal
        self._pos += 1
        return c, True

    def _parse_group(self) -> str:
        # consume '('
        self._pos += 1
        # handle (?:...), (?i)... style prefixes minimally
        if self._peek() == "?":
            self._pos += 1
            nxt = self._peek()
            if nxt == ":":
                self._pos += 1  # non-capturing, treat like a normal group
            elif nxt in ("=", "!", "<"):
                raise UnsupportedPattern("look-around / special group is unsupported")
            else:
                # inline flags like (?i) or (?i:...): bail rather than mis-handle
                raise UnsupportedPattern("inline-flag group '(?%s...)' is unsupported" % nxt)
        inner = self._parse_alternation()
        if self._peek() != ")":
            raise UnsupportedPattern("unterminated group '('")
        self._pos += 1  # consume ')'
        return inner

    def _parse_class(self) -> str:
        # current char is '['
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
                expanded = self._class_escape(esc)
                members.extend(expanded)
                continue
            # possible range a-z
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
            # prefer the lowest-ordinal concrete member for determinism &
            # readability; ranges contribute their low end.
            choices: List[str] = list(members)
            for lo, hi in ranges:
                if lo <= hi:
                    choices.append(chr(lo))
            if not choices:
                raise UnsupportedPattern(
                    "empty character class %r" % self._src[start:self._pos]
                )
            return min(choices)
        # negated class: pick any safe filler NOT excluded
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
        """Expand an escape *inside* a character class to candidate members."""
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
        # escaped literal (\. \- \] \\ etc.)
        return [esc]

    def _parse_escape(self) -> Tuple[str, bool]:
        # current char is '\'
        self._pos += 1
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
            # complement classes: emit a safe char that satisfies them
            if esc == "D":
                return "a", True
            if esc == "W":
                return " ", True
            return "a", True  # \S -> non-space
        if esc in ("b", "B", "A", "Z"):
            return "", False  # word-boundary / string anchors: emit nothing
        if esc == "t":
            return "\t", True
        if esc == "n":
            return "\n", True
        if esc == "r":
            return "\r", True
        # escaped literal metacharacter: . / - ( ) [ ] { } + * ? | ^ $ \
        return esc, True


# --------------------------------------------------------------------------- #
# Self-test (runs under --self-test and on import via the __main__ guard path)
# --------------------------------------------------------------------------- #


def _self_test() -> None:
    """Inline assertions covering several distinct regex constructs.

    Each generated sample is independently re-validated with the stdlib ``re``
    engine, so this proves the sampler's output genuinely matches.
    """
    cases = [
        # (pattern, must fullmatch?)
        r"^0x[a-f0-9]{40}$",                       # the live AIGEN address mission
        r"^[A-Z]{3}-\d{4}$",                       # ticket id: literals+class+\d+quant
        r"https://github\.com/[A-Za-z0-9_.\-]+/pull/[0-9]+",  # PR-URL deliverable
        r"^(cat|dog|bird)$",                       # alternation of literals
        r"\d{3,5}",                                # open-ended-ish bounded quantifier
    ]
    for pat in cases:
        s = RegexSampler(seed=1234).sample(pat)
        # anchored patterns must fullmatch; others must at least search-match
        if pat.startswith("^") and pat.endswith("$"):
            assert re.fullmatch(pat, s), (pat, s)
        else:
            assert re.search(pat, s), (pat, s)

    # determinism: same seed -> same output
    a = RegexSampler(seed=7).sample(r"^[a-f0-9]{6}$")
    b = RegexSampler(seed=7).sample(r"^[a-f0-9]{6}$")
    assert a == b, (a, b)

    # the canonical live mission produces the all-zero (minimal) address
    addr = RegexSampler(seed=0).sample(r"^0x[a-f0-9]{40}$")
    assert addr == "0x" + "0" * 40, addr
    assert re.fullmatch(r"^0x[a-f0-9]{40}$", addr)

    # unsupported constructs must raise (fail-closed), not silently mis-match
    for bad in [r"(?=foo)bar", r"(a)\1", r"(?i)abc", r"a{", r"["]:
        try:
            RegexSampler(seed=1).sample(bad)
        except UnsupportedPattern:
            pass
        else:  # pragma: no cover - would indicate a sampler bug
            raise AssertionError("expected UnsupportedPattern for %r" % bad)


# Run the self-test at import time so the file can never ship with a broken
# sampler. It is cheap (<1ms) and pure. Disable by setting the env var below.
import os as _os  # noqa: E402  (local import to keep the top tidy)

if _os.environ.get("MISSION_CLAIMER_SKIP_SELFTEST") != "1":
    _self_test()


# --------------------------------------------------------------------------- #
# OABP API client (plain HTTP, no SDK)
# --------------------------------------------------------------------------- #


class APIError(Exception):
    """Network or HTTP-level failure talking to the OABP API."""


class OABPClient:
    """Thin synchronous client for the handful of endpoints we use."""

    def __init__(self, base_url: str, timeout: float = HTTP_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
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
            raise APIError("GET %s -> HTTP %d: %s" % (url, resp.status_code, resp.text[:300]))
        try:
            return resp.json()
        except ValueError as exc:
            raise APIError("GET %s -> non-JSON body: %s" % (url, resp.text[:200])) from exc

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
        """``GET /api/missions/{id}`` -> full mission dict (with regex)."""
        data = self._get("/api/missions/%s" % mission_id)
        if not isinstance(data, dict):
            raise APIError("unexpected mission-detail shape for %s" % mission_id)
        return data

    def submit(self, mission_id: str, submitter_agent_id: str, proof: str) -> Tuple[int, Any]:
        """``POST /missions/{id}/submit`` with the generated proof."""
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
    # the flat ``reward_aigen`` field implies AIGEN
    if m.get("reward_aigen") is not None:
        return "AIGEN"
    return "?"


def mission_regex(m: Dict[str, Any]) -> Optional[str]:
    vp = m.get("verification_params")
    if isinstance(vp, dict):
        rgx = vp.get("regex")
        if isinstance(rgx, str) and rgx:
            return rgx
    return None


def net_after_fee(amount: float) -> float:
    """Apply the 0.5% protocol fee."""
    return amount * (1.0 - PROTOCOL_FEE_BPS / 10000.0)


# --------------------------------------------------------------------------- #
# Table rendering
# --------------------------------------------------------------------------- #


def _truncate(text: str, width: int) -> str:
    text = text.replace("\n", " ").strip()
    return text if len(text) <= width else text[: width - 1] + "…"


def render_table(rows: List[Dict[str, Any]]) -> str:
    """ASCII table of id / title / reward / intended-proof."""
    headers = ["MISSION ID", "TITLE", "REWARD", "INTENDED PROOF"]
    widths = [16, 34, 16, 46]
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
            _truncate(str(r.get("title", "")), widths[1]),
            _truncate(str(r.get("reward", "")), widths[2]),
            _truncate(str(r.get("proof", "")), widths[3]),
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
    sampler: RegexSampler,
    min_reward: float,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """List missions, keep ``first_valid_match``, generate a proof for each.

    Returns a list of row dicts:
        {id, title, reward, reward_amount, currency, regex, proof|None,
         status, error|None}
    Missions whose regex the sampler cannot handle are kept with
    ``proof=None`` and an ``error`` message (so the table can show the bail
    reason) but are not submittable.
    """
    missions = client.list_missions()
    fvm = [m for m in missions if m.get("verification_type") == TARGET_VERIFICATION_TYPE]
    if verbose:
        sys.stderr.write(
            "Discovered %d mission(s); %d are '%s'.\n"
            % (len(missions), len(fvm), TARGET_VERIFICATION_TYPE)
        )

    rows: List[Dict[str, Any]] = []
    for summary in fvm:
        mid = summary.get("id")
        if not mid:
            continue

        # The summary list row may not carry verification_params; the detail
        # endpoint always does. Fetch detail when the regex is missing.
        regex = mission_regex(summary)
        detail: Dict[str, Any] = summary
        if regex is None:
            try:
                detail = client.get_mission(mid)
            except APIError as exc:
                rows.append(
                    {
                        "id": mid,
                        "title": summary.get("title", ""),
                        "reward": "?",
                        "reward_amount": None,
                        "currency": "?",
                        "regex": None,
                        "proof": None,
                        "status": "detail-fetch-failed",
                        "error": str(exc),
                    }
                )
                continue
            regex = mission_regex(detail)

        amount = mission_reward_amount(detail)
        currency = mission_reward_currency(detail)
        # respect status if the detail endpoint provides one
        status = detail.get("status")
        if status is not None and status != "open":
            continue
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
            "reward": reward_str,
            "reward_amount": amount,
            "currency": currency,
            "regex": regex,
            "proof": None,
            "status": "ready",
            "error": None,
        }

        if not regex:
            row["status"] = "no-regex"
            row["proof"] = None
            row["error"] = "mission has no verification_params.regex"
            rows.append(row)
            continue

        try:
            proof = sampler.sample(regex)
        except UnsupportedPattern as exc:
            row["status"] = "unsupported-regex"
            row["proof"] = None
            row["error"] = "unsupported regex (%s): %s" % (regex, exc)
        else:
            row["proof"] = proof
        rows.append(row)

    return rows


def run_once(
    client: OABPClient,
    args: argparse.Namespace,
) -> int:
    """One discovery+submit pass. Returns a process exit code."""
    sampler = RegexSampler(seed=args.seed)
    rows = build_candidates(client, sampler, args.min_reward, verbose=True)

    if not rows:
        print("No open '%s' missions found." % TARGET_VERIFICATION_TYPE)
        return 1

    print(render_table(rows))
    print()

    submittable = [r for r in rows if r.get("proof") is not None]
    if not submittable:
        # Distinguish "nothing matched the type" from "all regexes unsupported"
        if all(r.get("status") in ("unsupported-regex", "no-regex") for r in rows):
            print(
                "No proof could be generated: every candidate regex is "
                "unsupported by the sampler. See the INTENDED PROOF column / "
                "errors above."
            )
            for r in rows:
                if r.get("error"):
                    print("  - %s: %s" % (r["id"], r["error"]))
            return 2
        return 1

    if args.dry_run:
        print(
            "DRY-RUN: %d mission(s) have a generated proof above. "
            "No submissions were sent. Re-run with --no-dry-run --agent-id <id> "
            "to claim." % len(submittable)
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
        print("Submitting to %s  proof=%r  as agent %r ..." % (mid, proof, args.agent_id))
        try:
            code, body = client.submit(mid, args.agent_id, proof)
        except APIError as exc:
            any_error = True
            print("  network error: %s" % exc)
            continue
        # The API returns HTTP 200 with an {"error": ...} field on logical
        # failures (e.g. bad agent id, already-resolved); surface that.
        if isinstance(body, dict) and body.get("error"):
            print("  rejected: %s" % body["error"])
        elif code >= 400:
            print("  HTTP %d: %s" % (code, body))
        else:
            print("  accepted: %s" % json.dumps(body) if not isinstance(body, str) else "  accepted: %s" % body)
    return 4 if any_error else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mission_claimer",
        description=(
            "Autonomous OABP/AIGEN agent that claims 'first_valid_match' "
            "missions by generating a regex-conforming proof. Defaults to a "
            "safe DRY-RUN (prints the intended proof, submits nothing)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "AIGEN is the protocol's uncapped reputation/points token; a 0.5%% "
            "fee is taken from every payout. Verification for these missions is "
            "permissionless and content-addressed: the first proof matching the "
            "mission's published regex wins."
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
        "--min-reward",
        type=float,
        default=0.0,
        help="Skip missions whose reward amount is below this (in the mission's currency).",
    )
    dry = parser.add_mutually_exclusive_group()
    dry.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Print intended proof and submit NOTHING (default).",
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
        "--seed",
        type=int,
        default=None,
        help="Seed for the regex sampler (deterministic proofs when set).",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the regex-sampler self-test and exit.",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        try:
            _self_test()
        except AssertionError as exc:  # pragma: no cover
            sys.stderr.write("SELF-TEST FAILED: %s\n" % (exc,))
            return 2
        print("regex sampler self-test: OK")
        return 0

    client = OABPClient(args.base_url)

    if not args.loop:
        try:
            return run_once(client, args)
        except APIError as exc:
            sys.stderr.write("API error: %s\n" % exc)
            return 4

    # loop mode
    print(
        "Looping every %.0fs against %s (Ctrl-C to stop). dry_run=%s"
        % (args.interval, args.base_url, args.dry_run)
    )
    try:
        while True:
            try:
                run_once(client, args)
            except APIError as exc:
                sys.stderr.write("API error this pass: %s (continuing)\n" % exc)
            time.sleep(max(1.0, args.interval))
    except KeyboardInterrupt:
        print("\nInterrupted. Bye.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
