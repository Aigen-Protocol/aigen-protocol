#!/usr/bin/env python3
"""OABP mission validator / linter.

A standalone, single-file linter for **OABP / AIGEN protocol** mission
definitions. It inspects a mission *before* it is posted (or audits one that is
already live) and flags problems that would make it **unresolvable** (no agent
can ever satisfy it / it can never pay out) or **spammy** (trivially matched,
mis-priced, junk metadata).

The OABP marketplace runs at ``https://cryptogenesis.duckdns.org``. Missions are
verified permissionlessly: either content-addressed (``first_valid_match`` — a
submission's proof is matched against a regex server-side) or oracle-backed
(``oracle`` — GoPlus token-security for safety reviews, GitHub REST for repo
deliverables). The other two verification modes (``peer_vote``,
``creator_judges``) are social/subjective. This linter encodes the rules that
keep each mode actually resolvable.

Design goals
------------
* **Zero third-party dependencies.** Standard library only (``json``, ``re``,
  ``urllib``, ``argparse`` ...). It runs anywhere Python 3.8+ runs, including
  inside an agent sandbox with no ``pip install``.
* **Three input sources.** A local JSON ``--file``, ``--stdin``, or a live
  ``--mission-id`` fetched from ``GET /api/missions/{id}`` (the live shape is
  normalised to the create-body shape before linting).
* **Findings, not exceptions.** Every problem is a structured
  :class:`Finding` with a severity, a stable ``code``, a human ``message``, a
  ``field`` pointer (dotted path), and — when the input is a JSON file — a
  best-effort source ``line`` number. The process exits non-zero iff there is
  at least one ``ERROR``.

Mission shape (create body)
---------------------------
``POST /api/missions`` accepts::

    {
      "creator_agent_id": "agent-123",
      "title": "...",
      "description": "...",
      "reward_amount": 100,
      "reward_currency": "AIGEN" | "USDC",
      "verification_type": "first_valid_match" | "oracle"
                           | "peer_vote" | "creator_judges",
      "verification_params": { "regex": "...", "oracle_description": "..." },
      "deadline_hours": 48
    }

``GET /api/missions/{id}`` returns a richer object (nested ``reward`` object,
absolute unix ``deadline`` instead of ``deadline_hours``, plus ``status`` /
``submissions``). :func:`normalize_mission` converts the latter into the
former so a single rule set covers both.

CLI
---
::

    oabp_mission_lint.py --file mission.json
    cat mission.json | oabp_mission_lint.py --stdin --format json
    oabp_mission_lint.py --mission-id 42 --base-url https://cryptogenesis.duckdns.org

Exit codes: ``0`` clean (no ERROR), ``1`` at least one ERROR, ``2`` usage /
input error (bad flags, unreadable file, malformed JSON, fetch failure).
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
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

__version__ = "1.0.0"

# --------------------------------------------------------------------------- #
# Protocol constants
# --------------------------------------------------------------------------- #
DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"
DEFAULT_USER_AGENT = f"oabp-mission-lint/{__version__} (+{DEFAULT_BASE_URL})"

ALLOWED_CURRENCIES = ("AIGEN", "USDC")
ALLOWED_VERIFICATION_TYPES = (
    "first_valid_match",
    "oracle",
    "peer_vote",
    "creator_judges",
)
# Verification modes whose resolution is automated (and therefore lintable for
# *unresolvability*). The other two are human/social and only get soft checks.
AUTOMATED_VERIFICATION_TYPES = ("first_valid_match", "oracle")

# Fallback floor used when /api/stats is unavailable or omits the field. The
# protocol's documented default minimum reward is 10 AIGEN.
FALLBACK_MIN_REWARD_AIGEN = 10.0

# Soft sanity bounds (tunable). These drive WARN/INFO, never ERROR on their own.
TITLE_MIN_LEN = 8
TITLE_MAX_LEN = 140
DESCRIPTION_MIN_LEN = 20
DESCRIPTION_MAX_LEN = 8000
DEADLINE_HOURS_WARN_SHORT = 1.0          # < 1h: agents may not see it in time
DEADLINE_HOURS_WARN_LONG = 24.0 * 90     # > 90 days: capital locked too long
REGEX_LEN_WARN = 2000                    # absurdly long patterns = likely junk

# A 0x EVM address (used to detect a named token in oracle safety reviews).
_EVM_ADDRESS_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
# Chains an OABP safety-review oracle (GoPlus) commonly understands. Matched
# case-insensitively as whole words inside the oracle_description.
_KNOWN_CHAINS = (
    "ethereum", "eth", "mainnet", "bsc", "bnb", "binance", "polygon", "matic",
    "arbitrum", "optimism", "base", "avalanche", "avax", "fantom", "ftm",
    "cronos", "gnosis", "celo", "moonbeam", "moonriver", "harmony", "zksync",
    "linea", "scroll", "mantle", "blast", "solana", "sol", "sui", "aptos",
    "tron", "ton",
)
# Programming languages a repo-deliverable oracle (GitHub) might assert on.
_KNOWN_LANGUAGES = (
    "python", "py", "javascript", "js", "typescript", "ts", "go", "golang",
    "rust", "rs", "java", "kotlin", "kt", "swift", "c", "c++", "cpp", "c#",
    "csharp", "dotnet", "ruby", "rb", "php", "dart", "elixir", "ex", "scala",
    "haskell", "ocaml", "clojure", "solidity", "sol", "move", "cairo", "zig",
    "lua", "perl", "r", "julia", "shell", "bash", "node", "react",
)


# --------------------------------------------------------------------------- #
# Findings
# --------------------------------------------------------------------------- #
class Severity(str, Enum):
    """Ordered severity. ``ERROR`` is the only level that fails the lint."""

    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"

    @property
    def rank(self) -> int:
        return {"ERROR": 3, "WARN": 2, "INFO": 1}[self.value]


@dataclass
class Finding:
    """One linter result.

    Attributes
    ----------
    severity:
        :class:`Severity` of the finding.
    code:
        Stable, greppable identifier (e.g. ``"reward.currency.invalid"``).
    message:
        Human-readable explanation.
    field:
        Dotted path into the mission the finding refers to (``None`` for
        whole-document findings).
    line:
        1-based source line in the input JSON, when it could be located.
    """

    severity: Severity
    code: str
    message: str
    field: Optional[str] = None
    line: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "line": self.line,
        }

    def format_text(self) -> str:
        loc = self.field or "<mission>"
        if self.line is not None:
            loc = f"{loc} (line {self.line})"
        return f"{self.severity.value:5s} [{self.code}] {loc}: {self.message}"


class LintError(Exception):
    """Raised for usage / input problems (maps to exit code 2)."""


# --------------------------------------------------------------------------- #
# Source line mapping (best-effort, stdlib only — no external JSON parser)
# --------------------------------------------------------------------------- #
def build_line_index(source: Optional[str]) -> Dict[str, int]:
    """Map top-level and one-level-nested JSON keys to 1-based line numbers.

    This is a lightweight, regex-based locator — it does not fully parse JSON,
    it just scans for ``"key"`` tokens that appear as object keys (immediately
    followed by a colon). The first occurrence of each key name wins. Nested
    keys are recorded both bare (``regex``) and, for the params we care about,
    dotted (``verification_params.regex``) when the parent key is seen first.

    Returns an empty map when ``source`` is ``None`` (e.g. a live fetch), in
    which case findings simply carry no line number.
    """
    index: Dict[str, int] = {}
    if not source:
        return index

    key_re = re.compile(r'"((?:[^"\\]|\\.)*)"\s*:')
    parent_for_param = {"regex", "oracle_description"}
    last_parent: Optional[str] = None

    for lineno, raw in enumerate(source.splitlines(), start=1):
        for m in key_re.finditer(raw):
            try:
                key = json.loads(f'"{m.group(1)}"')
            except json.JSONDecodeError:
                key = m.group(1)
            if key not in index:
                index[key] = lineno
            if key == "verification_params":
                last_parent = key
            elif key in parent_for_param and last_parent == "verification_params":
                dotted = f"verification_params.{key}"
                if dotted not in index:
                    index[dotted] = lineno
    return index


def _line_for(index: Mapping[str, int], field: Optional[str]) -> Optional[int]:
    if not field or not index:
        return None
    if field in index:
        return index[field]
    # Fall back to the leaf key for dotted paths we did not record dotted.
    leaf = field.rsplit(".", 1)[-1]
    return index.get(leaf)


# --------------------------------------------------------------------------- #
# Input loading + normalisation
# --------------------------------------------------------------------------- #
def load_from_file(path: str) -> Tuple[Dict[str, Any], str]:
    """Load a mission from a JSON file. Returns ``(mission, raw_source)``."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            source = fh.read()
    except OSError as exc:
        raise LintError(f"could not read --file {path!r}: {exc}") from exc
    return _parse_json_object(source, origin=path), source


def load_from_stdin() -> Tuple[Dict[str, Any], str]:
    """Load a mission from stdin. Returns ``(mission, raw_source)``."""
    source = sys.stdin.read()
    if not source.strip():
        raise LintError("no JSON received on stdin")
    return _parse_json_object(source, origin="<stdin>"), source


def load_from_api(
    mission_id: str, base_url: str, *, timeout: float = 15.0
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Fetch a live mission via ``GET /api/missions/{id}``.

    Returns ``(mission, None)`` — there is no meaningful per-key source line
    for a fetched object, so the second element is ``None``.
    """
    url = f"{base_url.rstrip('/')}/api/missions/{_quote(mission_id)}"
    data = _http_get_json(url, timeout=timeout)
    # Some deployments wrap the object: {"mission": {...}}.
    if isinstance(data, Mapping) and isinstance(data.get("mission"), Mapping):
        data = data["mission"]
    if not isinstance(data, Mapping):
        raise LintError(
            f"GET {url} did not return a mission object (got "
            f"{type(data).__name__})"
        )
    return dict(data), None


def _parse_json_object(source: str, *, origin: str) -> Dict[str, Any]:
    try:
        obj = json.loads(source)
    except json.JSONDecodeError as exc:
        raise LintError(
            f"{origin}: invalid JSON (line {exc.lineno}, col {exc.colno}): {exc.msg}"
        ) from exc
    if not isinstance(obj, dict):
        raise LintError(
            f"{origin}: expected a JSON object (mission), got {type(obj).__name__}"
        )
    return obj


def _quote(value: str) -> str:
    from urllib.parse import quote

    return quote(str(value), safe="")


def fetch_min_reward_aigen(
    base_url: str, *, timeout: float = 10.0
) -> Tuple[float, str]:
    """Resolve the marketplace minimum AIGEN reward.

    Tries ``GET /api/stats`` and reads ``min_reward_aigen`` if present. The
    documented stats payload is ``{resolved, open, lifetime_reward_aigen_paid}``
    so the field is frequently absent; in that case (or on any network error)
    we fall back to :data:`FALLBACK_MIN_REWARD_AIGEN`.

    Returns ``(value, source)`` where ``source`` is ``"stats"`` or
    ``"fallback"`` (useful for the INFO line the linter emits).
    """
    url = f"{base_url.rstrip('/')}/api/stats"
    try:
        data = _http_get_json(url, timeout=timeout)
    except LintError:
        return FALLBACK_MIN_REWARD_AIGEN, "fallback"
    if isinstance(data, Mapping):
        for key in ("min_reward_aigen", "min_reward", "minimum_reward_aigen"):
            if data.get(key) is not None:
                try:
                    return float(data[key]), "stats"
                except (TypeError, ValueError):
                    break
    return FALLBACK_MIN_REWARD_AIGEN, "fallback"


def _http_get_json(url: str, *, timeout: float) -> Any:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": DEFAULT_USER_AGENT},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            body = resp.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        raise LintError(f"GET {url} failed: HTTP {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise LintError(f"GET {url} failed: {exc.reason}") from exc
    except (TimeoutError, OSError) as exc:  # socket timeout, connection reset
        raise LintError(f"GET {url} failed: {exc}") from exc
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise LintError(f"GET {url} returned non-JSON body: {exc.msg}") from exc


def normalize_mission(mission: Mapping[str, Any]) -> Dict[str, Any]:
    """Coerce a live ``GET /api/missions/{id}`` object to create-body shape.

    The two shapes differ in two places:

    * **reward** — live uses a nested ``{"reward": {"amount", "currency"}}``
      object; the create body uses flat ``reward_amount`` / ``reward_currency``.
    * **deadline** — live uses an absolute unix ``deadline``; the create body
      uses relative ``deadline_hours``. We do *not* invent ``deadline_hours``
      from an absolute timestamp (that would depend on "now"); instead we keep
      the absolute value under ``_deadline_unix`` so the deadline check can run
      either way.

    Inputs already in create-body shape pass through unchanged. The returned
    dict is a shallow copy; the original is never mutated.
    """
    out: Dict[str, Any] = dict(mission)

    reward = mission.get("reward")
    if isinstance(reward, Mapping):
        if "reward_amount" not in out and reward.get("amount") is not None:
            out["reward_amount"] = reward.get("amount")
        if "reward_currency" not in out and reward.get("currency") is not None:
            out["reward_currency"] = reward.get("currency")

    # Absolute deadline -> stash for the deadline check; leave deadline_hours
    # alone if the caller already supplied it.
    if "deadline_hours" not in out and mission.get("deadline") is not None:
        out["_deadline_unix"] = mission.get("deadline")

    # Pull regex / oracle_description up only for line-free convenience access;
    # the real source of truth stays verification_params.
    return out


# --------------------------------------------------------------------------- #
# Regex analysis (the heart of first_valid_match linting)
# --------------------------------------------------------------------------- #
@dataclass
class RegexAnalysis:
    """Result of reasoning about a ``first_valid_match`` regex.

    Severity mapping used by the linter:

    * ``compiles is False`` -> ERROR (server can't evaluate submissions).
    * ``provably_empty is True`` -> ERROR (no string can ever match; the only
      high-confidence, false-positive-free unsatisfiability signal).
    * ``probe_matched is False`` (and not provably empty) -> WARN
      (inconclusive: the broad probe corpus found nothing, so the pattern may
      be unsatisfiable or merely very narrow — flagged for human review, never
      blocked).
    * ``matches_empty is True`` -> WARN (accepts any/empty input → spammy).
    * ``anchored_both is False`` -> INFO (substring match; consider anchoring).
    """

    compiles: bool
    error: Optional[str] = None
    matches_empty: bool = False
    provably_empty: bool = False
    probe_matched: Optional[bool] = None  # None = not probed
    anchored_both: bool = False
    notes: List[str] = field(default_factory=list)


# Tokens that, when they constitute essentially the whole pattern, make it
# match *any* input (including empty) — i.e. it accepts every submission and so
# resolves to the first submitter regardless of content (spam magnet).
_TRIVIAL_PATTERNS = {
    "", ".*", "(.*)", "^.*$", "^(.*)$", ".*?", "(.*?)", "^$", "^.*", ".*$",
    "[\\s\\S]*", "(?s).*", "^[\\s\\S]*$",
}


def analyze_regex(pattern: str) -> RegexAnalysis:
    """Compile + reason about a ``first_valid_match`` regex.

    We determine three practically-important properties without a SAT solver:

    1. **compiles** — does :func:`re.compile` accept it? (A non-compiling regex
       can never match any submission → the mission is unresolvable → ERROR.)
    2. **satisfiable** — does *some* string match it? We can't decide this in
       general, so we split it into a **high-confidence** signal and a
       **soft** one:

       * ``provably_empty`` — structural detection of patterns that match *no*
         string (``a^`` / ``$a`` / ``(?!)`` / ``\\b\\B`` contradictions). This
         is conservative (false-positive-free) and drives an ERROR.
       * ``probe_matched`` — whether any string in a broad probe corpus matched.
         ``False`` is only *inconclusive* (the pattern may be valid but narrow),
         so it drives a WARN, never an ERROR — we must not block a
         valid-but-exotic pattern.
    3. **matches_empty** — does it match the empty string / accept anything
       (``.*`` and friends)? Such a mission pays the first submitter for *no*
       real work → WARN (spammy), not ERROR.

    The result is conservative: the only hard ERROR for an *evaluable* pattern
    is ``provably_empty``; everything else is advisory.
    """
    notes: List[str] = []
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        return RegexAnalysis(
            compiles=False,
            error=str(exc),
            notes=[f"does not compile: {exc}"],
        )

    # Empty-string / trivial-accept detection.
    stripped = pattern.strip()
    matches_empty = compiled.search("") is not None
    if stripped in _TRIVIAL_PATTERNS or matches_empty:
        matches_empty = True
        notes.append(
            "pattern matches the empty string (or any input): it accepts every "
            "submission and rewards the first submitter for no specific content"
        )

    anchored_both = _looks_anchored_both(pattern)

    provably_empty = _is_provably_empty_language(pattern)
    if provably_empty:
        notes.append(
            "pattern matches no string at all (empty language): no submission "
            "can ever satisfy it"
        )

    # Soft satisfiability probe — only meaningful when the pattern is neither
    # trivially-accepting nor provably empty.
    probe_matched: Optional[bool] = None
    if not matches_empty and not provably_empty:
        probe_matched = _probe_satisfiable(compiled)
        if not probe_matched:
            notes.append(
                "no string in the probe corpus matched this pattern; it is "
                "either very narrow or unsatisfiable — verify a real submission "
                "can match it"
            )

    return RegexAnalysis(
        compiles=True,
        error=None,
        matches_empty=matches_empty,
        provably_empty=provably_empty,
        probe_matched=probe_matched,
        anchored_both=anchored_both,
        notes=notes,
    )


def _looks_anchored_both(pattern: str) -> bool:
    """Heuristic: does the pattern anchor at both start and end?"""
    p = pattern.strip()
    # Strip a leading inline-flags group like (?i) / (?s) for the check.
    p = re.sub(r"^\(\?[aiLmsux]+\)", "", p)
    starts = p.startswith("^") or p.startswith("\\A")
    ends = p.endswith("$") or p.endswith("\\Z") or p.endswith("\\z")
    return starts and ends


# Constructs that yield the empty language regardless of input.
_EMPTY_LANG_TOKENS = (
    "(?!)",       # negative lookahead on empty -> never matches
)
# Patterns like ``a^``, ``$a``, ``^$X`` where an anchor sits mid-pattern with
# required content on the impossible side. We detect a *required* literal/class
# directly adjacent to a start anchor in the interior, or after an end anchor.
_MID_START_ANCHOR_RE = re.compile(r"(?<!\\)(?<!\[)\^(?=[^|)$])")
_AFTER_END_ANCHOR_RE = re.compile(r"(?<!\\)\$(?=[^|)\s]).")


def _is_provably_empty_language(pattern: str) -> bool:
    """Best-effort detection of patterns that match *no* string.

    This is intentionally conservative (false negatives are fine — they fall
    through to corpus probing — but false positives must be avoided so we never
    wrongly reject a valid pattern). Recognised cases:

    * an unconditional ``(?!)`` negative lookahead anywhere top-level;
    * a ``\\b\\B`` / ``\\B\\b`` contradiction (word boundary AND non-boundary
      at the same position);
    * required content after an end-anchor or before a start-anchor that is not
      itself inside an alternation (e.g. ``$x`` / ``a^b``) — i.e. the anchor is
      mid-pattern with mandatory characters on the unreachable side.
    """
    p = pattern.strip()
    for tok in _EMPTY_LANG_TOKENS:
        if tok in p and "|" not in p:
            return True
    if ("\\b\\B" in p or "\\B\\b" in p) and "|" not in p:
        return True

    # Mid-pattern anchors with mandatory content on the dead side, but only when
    # there is no alternation that could provide an escape branch.
    if "|" not in p:
        # Required char immediately after a top-level end anchor: ``$X``.
        if _AFTER_END_ANCHOR_RE.search(p):
            return True
        # Start anchor that is not the very first char and has required content
        # before it: ``a^...``. We look for ``^`` preceded by a literal token.
        m = _MID_START_ANCHOR_RE.search(p)
        if m and m.start() > 0:
            before = p[: m.start()]
            # Only "dead" if the text before the interior ^ is required content
            # (not itself an anchor / group-open / alternation boundary).
            if before and before[-1] not in "(|":
                return True
    return False


# A broad probe corpus: empty, whitespace, digits, hex, urls, repo-style and
# token-style strings, plus a few long/random ones. If a (non-empty-matching)
# pattern matches none of these, we flag it as *possibly* unsatisfiable.
_PROBE_CORPUS: Tuple[str, ...] = (
    " ", "\t", "\n",
    "0", "1", "42", "1000", "1234567890",
    "a", "z", "A", "Z", "abc", "XYZ", "Hello, world!",
    "true", "false", "yes", "no", "PASS", "FAIL", "ok", "done",
    "0x0000000000000000000000000000000000000000",
    "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    "https://github.com/octocat/Hello-World",
    "https://example.com/path?q=1#frag",
    "github.com/owner/repo",
    "owner/repo@abcdef1",
    "[email protected]",
    "QmYwAPJzv5CZsnA625s3Xf2nemtYgPpHdWEz79ojWnPbdG",  # ipfs-ish CID
    "0123456789abcdef0123456789abcdef01234567",
    "a" * 40,                                   # 40-char lowercase (sha1-ish)
    "0123456789abcdef" * 4,                     # 64-char lowercase hex (sha256)
    "0123456789ABCDEF" * 4,                     # 64-char uppercase hex
    "f" * 64,                                    # 64 lowercase hex
    "deadbeefcafebabe" * 4,                     # 64-char hex, no digits-only
    "The quick brown fox jumps over the lazy dog 1234567890 !@#$%^&*()",
    "x" * 256,
    "snake_case_value-123.json",
    "UPPER_SNAKE",
    "v1.2.3",
)


def _probe_satisfiable(compiled: "re.Pattern[str]") -> bool:
    """Return True if any probe string matches (search) the compiled pattern."""
    for probe in _PROBE_CORPUS:
        try:
            if compiled.search(probe) is not None:
                return True
        except re.error:
            # Catastrophic backtracking guard is not available stdlib-side;
            # treat a probe error as inconclusive and keep going.
            continue
    return False


# --------------------------------------------------------------------------- #
# The linter
# --------------------------------------------------------------------------- #
class MissionLinter:
    """Runs the full rule set over a normalised mission.

    Parameters
    ----------
    min_reward_aigen:
        The minimum AIGEN reward to enforce (resolved from ``/api/stats`` by the
        caller, or the documented fallback).
    min_reward_source:
        ``"stats"`` or ``"fallback"`` — only used to phrase the INFO note.
    line_index:
        Output of :func:`build_line_index` for source-line pointers (may be
        empty for fetched missions).
    """

    # Fields the create body requires. (creator_agent_id is required by the API
    # but may legitimately be injected by tooling at post time, so it is a WARN
    # when missing rather than an ERROR — see _check_required.)
    REQUIRED_FIELDS = (
        "title",
        "description",
        "reward_amount",
        "reward_currency",
        "verification_type",
        "verification_params",
        "deadline_hours",
    )

    def __init__(
        self,
        *,
        min_reward_aigen: float = FALLBACK_MIN_REWARD_AIGEN,
        min_reward_source: str = "fallback",
        line_index: Optional[Mapping[str, int]] = None,
    ) -> None:
        self.min_reward_aigen = float(min_reward_aigen)
        self.min_reward_source = min_reward_source
        self.line_index = dict(line_index or {})
        self.findings: List[Finding] = []

    # -- finding helpers ----------------------------------------------------
    def _add(
        self, severity: Severity, code: str, message: str, field: Optional[str] = None
    ) -> None:
        self.findings.append(
            Finding(
                severity=severity,
                code=code,
                message=message,
                field=field,
                line=_line_for(self.line_index, field),
            )
        )

    def error(self, code: str, message: str, field: Optional[str] = None) -> None:
        self._add(Severity.ERROR, code, message, field)

    def warn(self, code: str, message: str, field: Optional[str] = None) -> None:
        self._add(Severity.WARN, code, message, field)

    def info(self, code: str, message: str, field: Optional[str] = None) -> None:
        self._add(Severity.INFO, code, message, field)

    # -- entry point --------------------------------------------------------
    def lint(self, mission: Mapping[str, Any]) -> List[Finding]:
        """Run every rule. Returns the accumulated findings (also on ``self``)."""
        self.findings = []
        self._check_required(mission)
        self._check_currency(mission)
        vtype = self._check_verification_type(mission)
        self._check_reward_amount(mission)
        self._check_deadline(mission)
        self._check_text_bounds(mission)
        self._check_verification_params(mission, vtype)
        self._emit_summary_info()
        return self.findings

    # -- individual rules ---------------------------------------------------
    def _check_required(self, mission: Mapping[str, Any]) -> None:
        for fld in self.REQUIRED_FIELDS:
            if fld not in mission or mission.get(fld) is None:
                self.error(
                    "required.missing",
                    f"required field {fld!r} is missing",
                    field=fld,
                )
        # creator_agent_id: required by the API but tooling may inject it.
        if not mission.get("creator_agent_id"):
            self.warn(
                "creator_agent_id.missing",
                "creator_agent_id is absent — the API requires it; ensure your "
                "posting tool injects it before POST /api/missions",
                field="creator_agent_id",
            )

    def _check_currency(self, mission: Mapping[str, Any]) -> None:
        if "reward_currency" not in mission or mission.get("reward_currency") is None:
            return  # already reported by _check_required
        currency = mission.get("reward_currency")
        if not isinstance(currency, str) or currency not in ALLOWED_CURRENCIES:
            self.error(
                "reward.currency.invalid",
                f"reward_currency must be one of {ALLOWED_CURRENCIES}, "
                f"got {currency!r}",
                field="reward_currency",
            )

    def _check_verification_type(self, mission: Mapping[str, Any]) -> Optional[str]:
        vtype = mission.get("verification_type")
        if vtype is None:
            return None  # required.missing already fired
        if not isinstance(vtype, str) or vtype not in ALLOWED_VERIFICATION_TYPES:
            self.error(
                "verification.type.invalid",
                f"verification_type must be one of {ALLOWED_VERIFICATION_TYPES}, "
                f"got {vtype!r}",
                field="verification_type",
            )
            return None
        if vtype in ("peer_vote", "creator_judges"):
            self.info(
                "verification.type.subjective",
                f"verification_type {vtype!r} is resolved socially/manually, not "
                "by an automated oracle — resolution depends on voters/creator "
                "showing up; it cannot be linted for unresolvability",
                field="verification_type",
            )
        return vtype

    def _check_reward_amount(self, mission: Mapping[str, Any]) -> None:
        if "reward_amount" not in mission or mission.get("reward_amount") is None:
            return  # required.missing already fired
        raw = mission.get("reward_amount")
        try:
            amount = float(raw)
        except (TypeError, ValueError):
            self.error(
                "reward.amount.not_numeric",
                f"reward_amount must be a number, got {raw!r}",
                field="reward_amount",
            )
            return
        if amount <= 0:
            self.error(
                "reward.amount.nonpositive",
                f"reward_amount must be > 0, got {amount}",
                field="reward_amount",
            )
            return
        currency = mission.get("reward_currency")
        # The minimum floor is denominated in AIGEN. Enforce it for AIGEN
        # rewards (and, conservatively, for any non-USDC value — including an
        # invalid currency typo — since the default denomination is AIGEN). For
        # an explicit USDC reward the AIGEN floor does not apply, so we only
        # note that no FX check is performed.
        if currency == "USDC":
            self.info(
                "reward.amount.usdc",
                f"reward is {amount} USDC; the AIGEN minimum floor "
                f"({self.min_reward_aigen:g}) does not apply to USDC and no FX "
                "check is performed here — confirm it clears any USDC minimum",
                field="reward_amount",
            )
        elif amount < self.min_reward_aigen:
            denom = "AIGEN" if currency in (None, "AIGEN") else f"{currency} (treated as AIGEN)"
            self.error(
                "reward.amount.below_min",
                f"reward_amount {amount} {denom} is below the marketplace "
                f"minimum of {self.min_reward_aigen:g} AIGEN "
                f"(source: {self.min_reward_source}); the post will be "
                "rejected or ignored as dust",
                field="reward_amount",
            )

    def _check_deadline(self, mission: Mapping[str, Any]) -> None:
        # Prefer the create-body relative form; fall back to an absolute unix
        # deadline stashed by normalize_mission for live missions.
        if mission.get("deadline_hours") is not None:
            raw = mission.get("deadline_hours")
            try:
                hours = float(raw)
            except (TypeError, ValueError):
                self.error(
                    "deadline.not_numeric",
                    f"deadline_hours must be a number, got {raw!r}",
                    field="deadline_hours",
                )
                return
            if hours <= 0:
                self.error(
                    "deadline.nonpositive",
                    f"deadline_hours must be > 0, got {hours}; a non-positive "
                    "deadline makes the mission expire immediately (unresolvable)",
                    field="deadline_hours",
                )
                return
            if hours < DEADLINE_HOURS_WARN_SHORT:
                self.warn(
                    "deadline.too_short",
                    f"deadline_hours {hours} is under {DEADLINE_HOURS_WARN_SHORT}h "
                    "— agents may not discover and complete the mission in time",
                    field="deadline_hours",
                )
            if hours > DEADLINE_HOURS_WARN_LONG:
                self.warn(
                    "deadline.too_long",
                    f"deadline_hours {hours} is very large "
                    f"(> {DEADLINE_HOURS_WARN_LONG:g}h / ~90 days); any USDC "
                    "reward stays locked for that long — confirm this is intended",
                    field="deadline_hours",
                )
            return

        if mission.get("_deadline_unix") is not None:
            # Live mission: validate the absolute timestamp is in the future.
            raw = mission.get("_deadline_unix")
            try:
                deadline = int(raw)
            except (TypeError, ValueError):
                self.error(
                    "deadline.not_numeric",
                    f"deadline (unix) must be an integer, got {raw!r}",
                    field="deadline",
                )
                return
            import time

            now = int(time.time())
            if deadline <= now:
                self.warn(
                    "deadline.in_past",
                    f"mission deadline {deadline} is in the past "
                    f"(now={now}); it is already expired and cannot resolve",
                    field="deadline",
                )

    def _check_text_bounds(self, mission: Mapping[str, Any]) -> None:
        self._check_one_text(
            mission, "title", TITLE_MIN_LEN, TITLE_MAX_LEN, hard_empty=True
        )
        self._check_one_text(
            mission,
            "description",
            DESCRIPTION_MIN_LEN,
            DESCRIPTION_MAX_LEN,
            hard_empty=True,
        )

    def _check_one_text(
        self,
        mission: Mapping[str, Any],
        field_name: str,
        min_len: int,
        max_len: int,
        *,
        hard_empty: bool,
    ) -> None:
        if field_name not in mission or mission.get(field_name) is None:
            return  # required.missing already fired
        value = mission.get(field_name)
        if not isinstance(value, str):
            self.error(
                f"{field_name}.not_string",
                f"{field_name} must be a string, got {type(value).__name__}",
                field=field_name,
            )
            return
        stripped = value.strip()
        if hard_empty and not stripped:
            self.error(
                f"{field_name}.empty",
                f"{field_name} is empty (or whitespace only)",
                field=field_name,
            )
            return
        if len(stripped) < min_len:
            self.warn(
                f"{field_name}.too_short",
                f"{field_name} is only {len(stripped)} chars "
                f"(< {min_len}); too terse for agents to understand the task",
                field=field_name,
            )
        if len(stripped) > max_len:
            self.warn(
                f"{field_name}.too_long",
                f"{field_name} is {len(stripped)} chars (> {max_len}); "
                "consider trimming",
                field=field_name,
            )

    def _check_verification_params(
        self, mission: Mapping[str, Any], vtype: Optional[str]
    ) -> None:
        params = mission.get("verification_params")
        if params is None:
            return  # required.missing already fired
        if not isinstance(params, Mapping):
            self.error(
                "verification.params.not_object",
                f"verification_params must be an object, got "
                f"{type(params).__name__}",
                field="verification_params",
            )
            return

        if vtype == "first_valid_match":
            self._check_first_valid_match(params)
        elif vtype == "oracle":
            self._check_oracle(params)
        # peer_vote / creator_judges: params are free-form; nothing to enforce.

    def _check_first_valid_match(self, params: Mapping[str, Any]) -> None:
        if "regex" not in params or params.get("regex") is None:
            self.error(
                "fvm.regex.missing",
                "first_valid_match missions require verification_params.regex; "
                "without it nothing can be content-matched and the mission is "
                "unresolvable",
                field="verification_params.regex",
            )
            return
        regex = params.get("regex")
        if not isinstance(regex, str):
            self.error(
                "fvm.regex.not_string",
                f"verification_params.regex must be a string, got "
                f"{type(regex).__name__}",
                field="verification_params.regex",
            )
            return
        if regex == "":
            self.error(
                "fvm.regex.empty",
                "verification_params.regex is an empty string; an empty pattern "
                "matches every submission and pays the first submitter for no "
                "specific content",
                field="verification_params.regex",
            )
            return
        if len(regex) > REGEX_LEN_WARN:
            self.warn(
                "fvm.regex.too_long",
                f"verification_params.regex is {len(regex)} chars "
                f"(> {REGEX_LEN_WARN}); suspiciously large — verify it is not junk",
                field="verification_params.regex",
            )

        analysis = analyze_regex(regex)
        if not analysis.compiles:
            self.error(
                "fvm.regex.uncompilable",
                f"verification_params.regex does not compile: {analysis.error}; "
                "the server cannot evaluate submissions → unresolvable",
                field="verification_params.regex",
            )
            return
        if analysis.provably_empty:
            self.error(
                "fvm.regex.unsatisfiable",
                "verification_params.regex matches no string at all (empty "
                "language) — no submission can ever win, so the mission is "
                "unresolvable",
                field="verification_params.regex",
            )
            return
        if analysis.matches_empty:
            self.warn(
                "fvm.regex.matches_empty",
                "verification_params.regex matches the empty string / accepts "
                "any input — it will reward the first submitter regardless of "
                "content (spammy / trivially farmable). Anchor it and require "
                "meaningful content",
                field="verification_params.regex",
            )
        elif analysis.probe_matched is False:
            self.warn(
                "fvm.regex.no_probe_match",
                "no test string across a broad probe corpus matched "
                "verification_params.regex; it may be unsatisfiable or extremely "
                "narrow — confirm a real submission can satisfy it before posting",
                field="verification_params.regex",
            )
        if not analysis.anchored_both:
            self.info(
                "fvm.regex.unanchored",
                "verification_params.regex is not anchored at both ends "
                "(^...$); unanchored patterns match on substrings and may accept "
                "proofs that merely contain the expected token — consider "
                "anchoring for exact content-addressing",
                field="verification_params.regex",
            )

    def _check_oracle(self, params: Mapping[str, Any]) -> None:
        desc = params.get("oracle_description")
        if not desc or not isinstance(desc, str) or not desc.strip():
            self.error(
                "oracle.description.missing",
                "oracle missions require a non-empty "
                "verification_params.oracle_description telling the oracle what "
                "to verify (e.g. a 0x token + chain for a GoPlus safety review, "
                "or a language/repo for a GitHub deliverable); without it the "
                "oracle cannot resolve the mission",
                field="verification_params.oracle_description",
            )
            return

        text = desc.strip()
        lower = text.lower()
        has_token = bool(_EVM_ADDRESS_RE.search(text))
        has_chain = _contains_word(lower, _KNOWN_CHAINS)
        has_language = _contains_word(lower, _KNOWN_LANGUAGES)
        has_repo_signal = (
            "github.com" in lower
            or "repo" in lower
            or "repository" in lower
            or bool(re.search(r"\b[\w.-]+/[\w.-]+\b", text))
        )

        looks_like_safety = has_token or "goplus" in lower or "token-security" in lower \
            or "token security" in lower or "safety" in lower
        looks_like_repo = has_repo_signal or has_language or "deliverable" in lower

        if looks_like_safety:
            # GoPlus safety review: need a token address AND a chain to resolve.
            if not has_token:
                self.warn(
                    "oracle.safety.no_token",
                    "oracle_description reads like a token safety review but does "
                    "not contain a 0x token address; the GoPlus oracle needs the "
                    "exact token to verify",
                    field="verification_params.oracle_description",
                )
            if not has_chain:
                self.warn(
                    "oracle.safety.no_chain",
                    "oracle_description names a token-safety review but no chain "
                    "is identified (e.g. ethereum/bsc/base); GoPlus is chain-"
                    "scoped — specify the chain so the oracle queries the right "
                    "network",
                    field="verification_params.oracle_description",
                )
        elif looks_like_repo:
            # GitHub repo deliverable: a language assertion makes it checkable.
            if not has_language:
                self.info(
                    "oracle.repo.no_language",
                    "oracle_description looks like a GitHub repo deliverable but "
                    "does not assert a programming language; naming the expected "
                    "language lets the oracle verify the repo's content, not just "
                    "its existence",
                    field="verification_params.oracle_description",
                )
        else:
            # Neither safety nor repo signal: the automated oracle (GoPlus /
            # GitHub) likely can't resolve it.
            self.warn(
                "oracle.description.unrecognized",
                "oracle_description does not name a 0x token+chain (GoPlus safety "
                "review) nor a repo/language (GitHub deliverable); the built-in "
                "oracles only verify those two shapes, so this mission may be "
                "unresolvable by the automated oracle",
                field="verification_params.oracle_description",
            )

    # -- summary ------------------------------------------------------------
    def _emit_summary_info(self) -> None:
        if self.min_reward_source == "fallback":
            self.info(
                "stats.min_reward.fallback",
                f"using fallback minimum reward of {self.min_reward_aigen:g} "
                "AIGEN (could not read min_reward_aigen from /api/stats)",
                field=None,
            )


# --------------------------------------------------------------------------- #
# Small text helpers
# --------------------------------------------------------------------------- #
def _contains_word(haystack_lower: str, words: Tuple[str, ...]) -> bool:
    """Whole-word containment test for a lowercased haystack."""
    for w in words:
        if re.search(r"(?<![\w])" + re.escape(w) + r"(?![\w])", haystack_lower):
            return True
    return False


# --------------------------------------------------------------------------- #
# Output formatting
# --------------------------------------------------------------------------- #
def render_text(findings: List[Finding], *, source_label: str) -> str:
    counts = _severity_counts(findings)
    lines: List[str] = []
    lines.append(f"OABP mission lint: {source_label}")
    if not findings:
        lines.append("  no findings — mission looks clean")
    else:
        # Stable ordering: severity (ERROR first), then line, then code.
        for f in sorted(
            findings,
            key=lambda x: (-x.severity.rank, x.line if x.line is not None else 1 << 30, x.code),
        ):
            lines.append("  " + f.format_text())
    lines.append(
        "summary: "
        f"{counts['ERROR']} error(s), {counts['WARN']} warning(s), "
        f"{counts['INFO']} info — "
        + ("FAIL" if counts["ERROR"] else "PASS")
    )
    return "\n".join(lines)


def render_json(findings: List[Finding], *, source_label: str) -> str:
    counts = _severity_counts(findings)
    payload = {
        "source": source_label,
        "ok": counts["ERROR"] == 0,
        "counts": counts,
        "findings": [f.to_dict() for f in findings],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def _severity_counts(findings: List[Finding]) -> Dict[str, int]:
    counts = {"ERROR": 0, "WARN": 0, "INFO": 0}
    for f in findings:
        counts[f.severity.value] += 1
    return counts


def has_errors(findings: List[Finding]) -> bool:
    return any(f.severity is Severity.ERROR for f in findings)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="oabp_mission_lint",
        description=(
            "Validate / lint an OABP (AIGEN protocol) mission definition before "
            "posting it. Flags problems likely to make it unresolvable or spammy."
        ),
        epilog=(
            "Exit codes: 0 = clean (no ERROR), 1 = at least one ERROR, "
            "2 = usage/input error."
        ),
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", metavar="PATH", help="read mission JSON from a file")
    src.add_argument(
        "--stdin", action="store_true", help="read mission JSON from standard input"
    )
    src.add_argument(
        "--mission-id",
        metavar="ID",
        help="fetch a live mission via GET /api/missions/{id}",
    )
    p.add_argument(
        "--base-url",
        default=os.environ.get("OABP_BASE_URL", DEFAULT_BASE_URL),
        help=f"OABP base URL (default: {DEFAULT_BASE_URL}; env OABP_BASE_URL)",
    )
    p.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    p.add_argument(
        "--min-reward",
        type=float,
        default=None,
        metavar="AIGEN",
        help=(
            "override the minimum AIGEN reward instead of reading /api/stats "
            "(useful offline)"
        ),
    )
    p.add_argument(
        "--no-network",
        action="store_true",
        help=(
            "never make HTTP calls: skip /api/stats lookup (use fallback or "
            "--min-reward). Incompatible with --mission-id."
        ),
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        metavar="SECONDS",
        help="HTTP timeout for live fetches (default: 15)",
    )
    p.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return p


def run(argv: Optional[List[str]] = None) -> int:
    """Programmatic entry point. Returns the process exit code."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.no_network and args.mission_id:
        parser.error("--no-network cannot be combined with --mission-id")

    base_url = args.base_url

    # ---- load the mission + (optional) source for line mapping -----------
    try:
        if args.file:
            mission, source = load_from_file(args.file)
            source_label = f"file:{args.file}"
        elif args.stdin:
            mission, source = load_from_stdin()
            source_label = "stdin"
        else:  # --mission-id
            mission, source = load_from_api(
                args.mission_id, base_url, timeout=args.timeout
            )
            source_label = f"mission-id:{args.mission_id}@{base_url}"
    except LintError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    line_index = build_line_index(source)
    normalized = normalize_mission(mission)

    # ---- resolve the minimum reward --------------------------------------
    if args.min_reward is not None:
        min_reward, min_source = float(args.min_reward), "override"
    elif args.no_network:
        min_reward, min_source = FALLBACK_MIN_REWARD_AIGEN, "fallback"
    else:
        min_reward, min_source = fetch_min_reward_aigen(base_url, timeout=args.timeout)

    # ---- lint -------------------------------------------------------------
    linter = MissionLinter(
        min_reward_aigen=min_reward,
        min_reward_source=min_source,
        line_index=line_index,
    )
    findings = linter.lint(normalized)

    # ---- output -----------------------------------------------------------
    if args.format == "json":
        print(render_json(findings, source_label=source_label))
    else:
        print(render_text(findings, source_label=source_label))

    return 1 if has_errors(findings) else 0


def main() -> None:
    try:
        sys.exit(run())
    except KeyboardInterrupt:  # pragma: no cover
        print("interrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
