#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single-file OABP / AIGEN ``oracle`` (GitHub-repo) deliverable agent.

What this is
============
A self-contained autonomous agent for the **OABP / AIGEN** agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``. It targets the
``oracle`` missions whose deliverable is a **code repository in a specific
language** — the live "Implement OABP AIP-1 client in <language>" bounties —
and submits *its own already-published GitHub repo* as the proof.

The live target missions (real ids, verified on the marketplace)
----------------------------------------------------------------
The marketplace currently carries a family of repo-deliverable bounties asking
for an OABP **AIP-1 client** implemented in a named language. The three this
agent was written against are::

    mis_2bbc63696ffd   "Implement OABP AIP-1 client in Golang"   -> language: Go
    mis_4d7f00fac5f8   "Implement OABP AIP-1 client in Ruby"     -> language: Ruby
    mis_ab37cc7aab37   "Implement OABP AIP-1 client in PHP"      -> language: PHP

Each is ``verification_type == "oracle"`` with an
``verification_params.oracle_description`` that says, in words, "deliver a
public GitHub repository implementing the client in <language>". The protocol's
**GitHub oracle** then resolves the submission with *purely structural* REST
checks — no code is cloned, built, or executed.

What the protocol's GitHub oracle actually checks (and what this agent mirrors)
------------------------------------------------------------------------------
The oracle is *content-addressed*: anyone can re-run it and get the same answer.
For a repo-deliverable mission it performs exactly three checks against the
public GitHub REST API, and **nothing else** (in particular it never runs the
code):

1. **EXISTS** — ``GET https://api.github.com/repos/{owner}/{repo}`` returns
   HTTP 200 (the repository is public and resolvable).
2. **NON-EMPTY** — the repo has actual content. The repo object's ``size`` is
   greater than 0 *and* ``GET /repos/{owner}/{repo}/languages`` is a non-empty
   object (a brand-new repo with only a README and no code has an empty
   ``languages`` map; an utterly empty repo has ``size == 0``).
3. **RIGHT LANGUAGE** — the language required by the mission (inferred from its
   title / ``oracle_description``) appears in the repo's ``/languages`` map.
   GitHub reports languages by bytes-of-code, so a Go deliverable must have a
   ``"Go"`` key with a positive byte count.

This agent re-implements those *same* checks locally before it submits, so it
only ever posts a proof the oracle will accept — it is **fail-closed**: a repo
that is missing, empty, or in the wrong language is reported and **not**
submitted. Submitting junk would simply waste the attempt (and, on
first-valid-match-style races, hand the win to a competitor), so verifying
first is both honest and optimal.

The proof
---------
The submitted ``proof`` is the canonical repository URL,
``https://github.com/{owner}/{repo}``. That is the exact string the GitHub
oracle parses ``{owner}/{repo}`` out of, so it is the natural content-address
for a repo deliverable.

How AIGEN missions pay out (the economics)
------------------------------------------
A mission carries a **reward** in ``AIGEN`` or ``USDC``.

* **AIGEN** is the protocol's *uncapped, off-chain reputation / points token* —
  not a tradable on-chain asset, just a score of how much useful, verified work
  an agent has delivered. Treat it as reputation, not money. **USDC** rewards
  (when present) carry real economic value.
* A flat **0.5% protocol fee** (50 basis points) is taken from every payout, so
  the solver nets ``reward * (1 - 0.005)``. A 200-AIGEN mission pays 199 AIGEN
  net; the 1 AIGEN fee accrues to the protocol. This tool prints the
  net-after-fee figure alongside each candidate.

Safety / ethics note
--------------------
This agent submits a repository **you** point it at (``--repo owner/name``) — it
is meant for delivering *your own* work to a matching bounty, not for laundering
someone else's repo. It defaults to ``--dry-run``: it runs the three structural
checks, prints the verdict and the proof it *would* submit, and posts nothing.
You must pass an explicit ``--agent-id`` and ``--no-dry-run`` to actually
submit.

Dependencies: Python 3.8+ standard library **plus** the ubiquitous ``requests``
package. No OABP SDK import — this file is intentionally copy-pasteable.
Set ``GITHUB_TOKEN`` in the environment to raise GitHub's unauthenticated
rate limit (60 req/h) to 5000 req/h; it is optional and never required.

Exit codes
----------
* ``0`` — ran cleanly: at least one matching mission had a verified repo
          (and, outside dry-run, was submitted without error).
* ``1`` — no actionable repo-deliverable ``oracle`` mission matched (none of
          the requested language / id, or none open).
* ``2`` — a mission matched but the supplied ``--repo`` FAILED the structural
          checks (missing / empty / wrong language) — nothing was submitted.
* ``3`` — a configuration / usage error (e.g. real submit without ``--agent-id``,
          or ``--repo`` not in ``owner/name`` form).
* ``4`` — a network / API error that aborted the run.

Run
---
    # default: verify my Go repo against the live Golang mission, submit nothing
    python3 github_repo_deliverer.py --repo myorg/oabp-go

    # auto-match by language (infers "Go" from the repo's own /languages) and
    # actually submit
    python3 github_repo_deliverer.py --repo myorg/oabp-go \\
        --agent-id my-bot --no-dry-run

    # target a specific mission id explicitly
    python3 github_repo_deliverer.py --mission-id mis_ab37cc7aab37 \\
        --repo myorg/oabp-php --agent-id my-bot --no-dry-run

    # run the built-in offline self-test (stubs GitHub) and exit
    python3 github_repo_deliverer.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
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
GITHUB_API = "https://api.github.com"
PROTOCOL_FEE_BPS = 50  # 0.50% — taken from every payout
TARGET_VERIFICATION_TYPE = "oracle"
HTTP_TIMEOUT = 30.0
USER_AGENT = "oabp-github-repo-deliverer/1.0 (+https://cryptogenesis.duckdns.org)"

# Real, live repo-deliverable missions this agent was written against. Used as a
# fallback "known target" list when the marketplace listing cannot be reached,
# and so the offline self-test exercises the real ids. (See module docstring.)
KNOWN_REPO_MISSIONS: Dict[str, str] = {
    "mis_2bbc63696ffd": "Go",    # Implement OABP AIP-1 client in Golang
    "mis_4d7f00fac5f8": "Ruby",  # Implement OABP AIP-1 client in Ruby
    "mis_ab37cc7aab37": "PHP",   # Implement OABP AIP-1 client in PHP
}


# --------------------------------------------------------------------------- #
# Language inference
# --------------------------------------------------------------------------- #
#
# GitHub's /languages endpoint reports the *canonical* language name (Linguist
# names: "Go", "Ruby", "PHP", "Python", "Rust", "TypeScript", ...). A mission
# title/description, by contrast, uses human phrasing ("Golang", "in PHP",
# "a Ruby gem"). We map the latter to the former so the "right language" check
# compares like with like.

# Ordered (longest / most specific alias first) so "golang" wins over a bare
# "go", and "typescript" / "ts" map before any accidental substring hit.
_LANGUAGE_ALIASES: List[Tuple[str, str]] = [
    # --- Go --- (specific aliases first; bare "go" is whole-word only)
    ("golang", "Go"),
    ("go-lang", "Go"),
    ("go", "Go"),
    # --- Ruby --- ("ruby on rails" before bare "ruby")
    ("ruby on rails", "Ruby"),
    ("rubygem", "Ruby"),
    ("ruby", "Ruby"),
    # --- PHP ---
    ("php", "PHP"),
    # --- Python --- (specific aliases first; bare "py" is whole-word only)
    ("python3", "Python"),
    ("python", "Python"),
    ("py", "Python"),
    # --- Rust ---
    ("rustlang", "Rust"),
    ("rust", "Rust"),
    # --- TypeScript --- (bare "ts" is whole-word only)
    ("typescript", "TypeScript"),
    ("type-script", "TypeScript"),
    ("ts", "TypeScript"),
]

# Short/ambiguous tokens that must match as a *whole word* (surrounded by
# non-word chars or string ends), so a bare "go" does not fire inside
# "algorithm", "ts" inside "facts", or "py" inside "occupy".
_WHOLE_WORD_ONLY = {"go", "ts", "py"}

# Canonical language names we understand, used to validate explicit --language
# and to recognise a /languages key as a "known" language.
CANONICAL_LANGUAGES = {"Go", "Ruby", "PHP", "Python", "Rust", "TypeScript"}


def infer_language(text: str) -> Optional[str]:
    """Infer the canonical GitHub language name required by a mission.

    ``text`` is the mission title (optionally concatenated with its
    description / oracle_description). Returns one of
    :data:`CANONICAL_LANGUAGES` or ``None`` if no known language is mentioned.

    The match is alias-aware ("Golang" -> "Go") and uses whole-word matching
    for the short/ambiguous tokens in :data:`_WHOLE_WORD_ONLY` so it does not
    fire on incidental substrings (e.g. "go" inside "algorithm").
    """
    if not text:
        return None
    low = text.lower()
    for alias, canonical in _LANGUAGE_ALIASES:
        if alias in _WHOLE_WORD_ONLY:
            # whole-word: alias surrounded by non-word chars / string ends
            if re.search(r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(alias), low):
                return canonical
        else:
            if alias in low:
                return canonical
    return None


def canonicalize_language(name: str) -> Optional[str]:
    """Map a user-supplied --language value to a canonical name (or None)."""
    direct = {c.lower(): c for c in CANONICAL_LANGUAGES}
    if name.lower() in direct:
        return direct[name.lower()]
    return infer_language(name)


# --------------------------------------------------------------------------- #
# OABP API client (plain HTTP, no SDK)
# --------------------------------------------------------------------------- #


class APIError(Exception):
    """Network or HTTP-level failure talking to the OABP API."""


class OABPClient:
    """Thin synchronous client for the handful of OABP endpoints we use."""

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
        """``GET /api/missions/{id}`` -> full mission dict (with params)."""
        data = self._get("/api/missions/%s" % mission_id)
        if not isinstance(data, dict):
            raise APIError("unexpected mission-detail shape for %s" % mission_id)
        return data

    def submit(
        self, mission_id: str, submitter_agent_id: str, proof: str
    ) -> Tuple[int, Any]:
        """``POST /missions/{id}/submit`` with the repo-URL proof."""
        return self._post(
            "/missions/%s/submit" % mission_id,
            {"submitter_agent_id": submitter_agent_id, "proof": proof},
        )


# --------------------------------------------------------------------------- #
# GitHub REST client — the structural oracle, re-implemented locally
# --------------------------------------------------------------------------- #


class GitHubError(Exception):
    """Network / HTTP failure talking to the GitHub REST API."""


class RepoCheckResult:
    """Outcome of the three structural checks for one repo + required language."""

    __slots__ = (
        "owner",
        "repo",
        "required_language",
        "exists",
        "non_empty",
        "language_ok",
        "detected_languages",
        "reason",
    )

    def __init__(
        self,
        owner: str,
        repo: str,
        required_language: Optional[str],
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.required_language = required_language
        self.exists = False
        self.non_empty = False
        self.language_ok = False
        self.detected_languages: List[str] = []
        self.reason = ""

    @property
    def ok(self) -> bool:
        """True only if all three structural checks pass."""
        return bool(self.exists and self.non_empty and self.language_ok)

    @property
    def url(self) -> str:
        return "https://github.com/%s/%s" % (self.owner, self.repo)

    def summary(self) -> str:
        flag = lambda b: "PASS" if b else "FAIL"  # noqa: E731
        langs = ", ".join(self.detected_languages) or "-"
        return (
            "exists=%s non-empty=%s language(%s in {%s})=%s"
            % (
                flag(self.exists),
                flag(self.non_empty),
                self.required_language or "?",
                langs,
                flag(self.language_ok),
            )
        )


class GitHubVerifier:
    """Run EXISTS / NON-EMPTY / RIGHT-LANGUAGE against the GitHub REST API.

    This is a faithful local re-implementation of what the OABP GitHub oracle
    does to resolve a repo-deliverable mission. It performs **no code
    execution**: it only reads ``/repos/{owner}/{repo}`` (existence + size) and
    ``/repos/{owner}/{repo}/languages`` (the language byte-map).
    """

    def __init__(
        self,
        token: Optional[str] = None,
        timeout: float = HTTP_TIMEOUT,
        session: Optional["requests.Session"] = None,
    ) -> None:
        self.timeout = timeout
        self._session = session or requests.Session()
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = "Bearer %s" % token
        self._session.headers.update(headers)

    # -- raw GETs ---------------------------------------------------------- #

    def _get(self, path: str) -> Tuple[int, Any]:
        url = GITHUB_API + path
        try:
            resp = self._session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            raise GitHubError("GET %s failed: %s" % (url, exc)) from exc
        body: Any
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
        return resp.status_code, body

    def get_repo(self, owner: str, repo: str) -> Tuple[int, Any]:
        return self._get("/repos/%s/%s" % (owner, repo))

    def get_languages(self, owner: str, repo: str) -> Tuple[int, Any]:
        return self._get("/repos/%s/%s/languages" % (owner, repo))

    # -- the oracle -------------------------------------------------------- #

    def verify(
        self, owner: str, repo: str, required_language: Optional[str]
    ) -> RepoCheckResult:
        """Run the three structural checks; return a :class:`RepoCheckResult`.

        Fail-closed: any check that does not affirmatively pass leaves ``ok``
        False with a human-readable ``reason``.
        """
        res = RepoCheckResult(owner, repo, required_language)

        # --- 1) EXISTS ---------------------------------------------------- #
        status, repo_obj = self.get_repo(owner, repo)
        if status == 404:
            res.reason = "repository %s/%s does not exist (HTTP 404)" % (owner, repo)
            return res
        if status == 403:
            # Most commonly rate-limiting on unauthenticated calls.
            res.reason = (
                "GitHub returned 403 for %s/%s (rate-limited? set GITHUB_TOKEN). "
                "Body: %s" % (owner, repo, _short(repo_obj))
            )
            return res
        if status != 200 or not isinstance(repo_obj, dict):
            res.reason = "unexpected GitHub status %d for repo %s/%s: %s" % (
                status,
                owner,
                repo,
                _short(repo_obj),
            )
            return res
        res.exists = True

        # --- 2) NON-EMPTY ------------------------------------------------- #
        # A repo with no commits has size == 0. We also require a non-empty
        # languages map below; together these reject "README-only" repos.
        size = repo_obj.get("size")
        size_nonzero = isinstance(size, (int, float)) and size > 0

        lang_status, lang_obj = self.get_languages(owner, repo)
        if lang_status != 200 or not isinstance(lang_obj, dict):
            res.reason = "could not read /languages for %s/%s (HTTP %d): %s" % (
                owner,
                repo,
                lang_status,
                _short(lang_obj),
            )
            return res
        # Keep only languages with a positive byte count (GitHub maps language
        # name -> bytes of code). An empty map == no code == empty repo.
        languages = [
            str(name)
            for name, nbytes in lang_obj.items()
            if isinstance(nbytes, (int, float)) and nbytes > 0
        ]
        res.detected_languages = languages

        if not languages:
            res.reason = (
                "repository %s/%s has no detectable source code "
                "(empty /languages map) — looks empty / docs-only" % (owner, repo)
            )
            return res
        if not size_nonzero:
            # /languages found code but size==0 would be contradictory; treat a
            # populated languages map as authoritative evidence of content, but
            # flag the oddity for transparency.
            res.reason = (
                "note: repo 'size' field is %r though /languages is non-empty; "
                "treating as non-empty on language evidence" % (size,)
            )
        res.non_empty = True

        # --- 3) RIGHT LANGUAGE -------------------------------------------- #
        if required_language is None:
            # No language constraint to satisfy: existence + non-empty suffice.
            res.language_ok = True
            return res
        # Case-insensitive containment against the canonical key set GitHub
        # returns (which are already canonical Linguist names).
        wanted = required_language.lower()
        present = {l.lower() for l in languages}
        if wanted in present:
            res.language_ok = True
        else:
            res.language_ok = False
            res.reason = (
                "required language %r not present in repo languages {%s}"
                % (required_language, ", ".join(languages))
            )
        return res


def _short(obj: Any, n: int = 200) -> str:
    try:
        s = obj if isinstance(obj, str) else json.dumps(obj)
    except (TypeError, ValueError):
        s = repr(obj)
    return s if len(s) <= n else s[: n - 1] + "…"


# --------------------------------------------------------------------------- #
# Mission-field helpers (tolerant to summary vs detail shapes)
# --------------------------------------------------------------------------- #


def mission_text(m: Dict[str, Any]) -> str:
    """Concatenate the title, description and oracle_description for inference."""
    parts = [str(m.get("title", "")), str(m.get("description", ""))]
    vp = m.get("verification_params")
    if isinstance(vp, dict):
        od = vp.get("oracle_description")
        if isinstance(od, str):
            parts.append(od)
    return " \n ".join(p for p in parts if p)


def mission_reward_amount(m: Dict[str, Any]) -> Optional[float]:
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


def mission_oracle_description(m: Dict[str, Any]) -> Optional[str]:
    vp = m.get("verification_params")
    if isinstance(vp, dict):
        od = vp.get("oracle_description")
        if isinstance(od, str) and od:
            return od
    return None


def looks_like_repo_mission(m: Dict[str, Any]) -> bool:
    """Heuristic: is this an oracle mission whose deliverable is a code repo?

    True when the verification type is ``oracle`` AND the text mentions a
    repository/GitHub deliverable in a recognisable language. This is the same
    surface the GitHub oracle keys off, and it deliberately *excludes* the
    GoPlus token-security ``oracle`` missions (which talk about token addresses
    / safety reviews, not repositories).
    """
    if m.get("verification_type") != TARGET_VERIFICATION_TYPE:
        return False
    text = mission_text(m).lower()
    mentions_repo = (
        "github" in text
        or "repo" in text
        or "repository" in text
        or "implement" in text
        or "client" in text
    )
    return bool(mentions_repo and infer_language(text) is not None)


def net_after_fee(amount: float) -> float:
    """Apply the 0.5% protocol fee."""
    return amount * (1.0 - PROTOCOL_FEE_BPS / 10000.0)


def parse_owner_repo(spec: str) -> Tuple[str, str]:
    """Parse ``owner/name`` (or a full GitHub URL) into ``(owner, repo)``.

    Raises ``ValueError`` if it is not a well-formed ``owner/name`` reference.
    """
    s = spec.strip()
    # tolerate a pasted URL
    m = re.match(
        r"^(?:https?://)?(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+?)(?:\.git)?/?$",
        s,
    )
    if m:
        return m.group(1), m.group(2)
    if "/" not in s:
        raise ValueError(
            "repo must be in 'owner/name' form (or a github.com URL); got %r" % spec
        )
    owner, _, repo = s.partition("/")
    owner = owner.strip()
    repo = repo.strip().removesuffix(".git").rstrip("/")
    if not owner or not repo or "/" in repo:
        raise ValueError(
            "repo must be in 'owner/name' form (or a github.com URL); got %r" % spec
        )
    # basic GitHub name sanity (owners/repos: alnum, '-', '_', '.')
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+", repo
    ):
        raise ValueError("invalid GitHub owner/name characters in %r" % spec)
    return owner, repo


# --------------------------------------------------------------------------- #
# Table rendering
# --------------------------------------------------------------------------- #


def _truncate(text: str, width: int) -> str:
    text = str(text).replace("\n", " ").strip()
    return text if len(text) <= width else text[: width - 1] + "…"


def render_table(rows: List[Dict[str, Any]]) -> str:
    """ASCII table of id / title / language / reward / verdict."""
    headers = ["MISSION ID", "TITLE", "LANG", "REWARD", "REPO VERDICT"]
    widths = [16, 30, 6, 18, 40]
    lines = []
    sep = "+".join("-" * (w + 2) for w in widths)
    lines.append(sep)
    lines.append(
        "|".join(" %-*s " % (w, _truncate(h, w)) for w, h in zip(widths, headers))
    )
    lines.append(sep)
    for r in rows:
        cells = [
            _truncate(r.get("id", ""), widths[0]),
            _truncate(r.get("title", ""), widths[1]),
            _truncate(r.get("language", ""), widths[2]),
            _truncate(r.get("reward", ""), widths[3]),
            _truncate(r.get("verdict", ""), widths[4]),
        ]
        lines.append("|".join(" %-*s " % (w, c) for w, c in zip(widths, cells)))
    lines.append(sep)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Candidate discovery + matching
# --------------------------------------------------------------------------- #


def discover_missions(
    client: OABPClient,
    mission_id: Optional[str],
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """Return the list of candidate repo-deliverable missions (detail dicts).

    * If ``mission_id`` is given, fetch exactly that mission's detail.
    * Otherwise list the marketplace and keep the repo-deliverable oracle
      missions (see :func:`looks_like_repo_mission`).

    Each returned dict is annotated with ``_language`` = the inferred canonical
    language for that mission (may be ``None`` for an explicit id whose language
    we could not infer — the caller then relies on the repo's own language /
    the ``--language`` override).
    """
    missions: List[Dict[str, Any]] = []

    if mission_id:
        detail = client.get_mission(mission_id)
        detail["_language"] = infer_language(mission_text(detail))
        missions.append(detail)
        return missions

    listing = client.list_missions()
    repo_missions = [m for m in listing if looks_like_repo_mission(m)]
    if verbose:
        sys.stderr.write(
            "Discovered %d mission(s); %d are repo-deliverable '%s' missions.\n"
            % (len(listing), len(repo_missions), TARGET_VERIFICATION_TYPE)
        )
    for summary in repo_missions:
        mid = summary.get("id")
        if not mid:
            continue
        # The summary row usually carries verification_params already; only
        # fetch detail if the oracle_description (and thus language) is missing.
        detail = summary
        if infer_language(mission_text(summary)) is None or not mission_oracle_description(
            summary
        ):
            try:
                detail = client.get_mission(mid)
            except APIError as exc:
                if verbose:
                    sys.stderr.write(
                        "  warn: could not fetch detail for %s: %s\n" % (mid, exc)
                    )
                detail = summary
        detail["_language"] = infer_language(mission_text(detail))
        missions.append(detail)
    return missions


def select_missions(
    missions: List[Dict[str, Any]],
    required_language: Optional[str],
    repo_language: Optional[str],
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Pick the missions to act on and the language to verify the repo against.

    Returns ``(selected_missions, effective_language)``.

    Auto-match logic when no explicit ``--mission-id`` was used:
      * If ``--language`` was given, keep missions requiring that language.
      * Else if the repo's own dominant language is known, keep missions
        requiring it (this is the "auto-match by language" path: the agent's
        delivered repo *is* the language declaration).
      * Else keep all repo missions (the verifier will reject mismatches).

    ``effective_language`` is the language the verifier should require:
    ``--language`` if set, else the unanimous mission language if the selected
    missions all need the same one, else the repo's own language.
    """
    effective = required_language or repo_language

    if required_language:
        sel = [m for m in missions if (m.get("_language") or "").lower() == required_language.lower()]
        # An explicitly id-fetched mission with unknown language is still kept.
        if not sel:
            sel = [m for m in missions if m.get("_language") is None]
        return sel, required_language

    if repo_language:
        sel = [m for m in missions if (m.get("_language") or "").lower() == repo_language.lower()]
        if sel:
            return sel, repo_language

    # No language hints at all: keep everything, require each mission's own.
    return missions, effective


# --------------------------------------------------------------------------- #
# Core run
# --------------------------------------------------------------------------- #


def run_once(
    client: OABPClient,
    verifier: GitHubVerifier,
    args: argparse.Namespace,
) -> int:
    """One discover -> verify -> (maybe) submit pass. Returns an exit code."""
    # --repo is mandatory for any real work (the agent submits *a* repo).
    try:
        owner, repo = parse_owner_repo(args.repo)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 3

    # Resolve the language the user explicitly asked for (if any).
    required_language: Optional[str] = None
    if args.language:
        required_language = canonicalize_language(args.language)
        if required_language is None:
            sys.stderr.write(
                "ERROR: --language %r is not a recognised language "
                "(known: %s).\n" % (args.language, ", ".join(sorted(CANONICAL_LANGUAGES)))
            )
            return 3

    # Pre-compute the repo's own dominant language once, so we can auto-match
    # missions by it and report it. (Cheap: one extra /languages read, reused.)
    repo_language: Optional[str] = None
    repo_langs: List[str] = []
    try:
        lang_status, lang_obj = verifier.get_languages(owner, repo)
        if lang_status == 200 and isinstance(lang_obj, dict):
            # dominant = the language with the most bytes
            ranked = sorted(
                (
                    (str(k), float(v))
                    for k, v in lang_obj.items()
                    if isinstance(v, (int, float)) and v > 0
                ),
                key=lambda kv: kv[1],
                reverse=True,
            )
            repo_langs = [k for k, _ in ranked]
            for name, _ in ranked:
                canon = canonicalize_language(name)
                if canon in CANONICAL_LANGUAGES:
                    repo_language = canon
                    break
    except GitHubError as exc:
        sys.stderr.write("warn: could not pre-read repo languages: %s\n" % exc)

    # Discover candidate missions.
    try:
        missions = discover_missions(client, args.mission_id, verbose=True)
    except APIError as exc:
        sys.stderr.write("API error discovering missions: %s\n" % exc)
        return 4

    if not missions:
        print(
            "No repo-deliverable '%s' missions found%s."
            % (
                TARGET_VERIFICATION_TYPE,
                (" for id %s" % args.mission_id) if args.mission_id else "",
            )
        )
        return 1

    selected, effective_language = select_missions(
        missions, required_language, repo_language
    )
    if not selected:
        langhint = required_language or repo_language or "?"
        print(
            "No open repo-deliverable mission matches language %r. "
            "Candidates: %s"
            % (
                langhint,
                ", ".join(
                    "%s(%s)" % (m.get("id"), m.get("_language") or "?") for m in missions
                ),
            )
        )
        return 1

    print(
        "Repo %s/%s — detected languages: %s; will verify against language: %s\n"
        % (owner, repo, ", ".join(repo_langs) or "(none/unknown)", effective_language or "(none)")
    )

    rows: List[Dict[str, Any]] = []
    submittable: List[Tuple[Dict[str, Any], RepoCheckResult]] = []

    for m in selected:
        mid = m.get("id", "")
        # Per-mission required language: prefer the mission's own inferred
        # language, then the effective/explicit one.
        req = m.get("_language") or effective_language
        amount = mission_reward_amount(m)
        currency = mission_reward_currency(m)
        reward_str = (
            "%g %s (net %g)" % (amount, currency, round(net_after_fee(amount), 4))
            if amount is not None
            else "?"
        )
        # Verify ONCE per mission and cache the result on the row (so the
        # detail lines below reuse it rather than re-hitting GitHub).
        try:
            result = verifier.verify(owner, repo, req)
        except GitHubError as exc:
            rows.append(
                {
                    "id": mid,
                    "title": m.get("title", ""),
                    "language": req or "?",
                    "reward": reward_str,
                    "verdict": "github-error: %s" % exc,
                    "_detail": "github-error: %s" % exc,
                }
            )
            continue

        verdict = ("OK -> %s" % result.url) if result.ok else ("REJECT: %s" % result.reason)
        rows.append(
            {
                "id": mid,
                "title": m.get("title", ""),
                "language": req or "?",
                "reward": reward_str,
                "verdict": verdict,
                "_detail": result.summary(),
            }
        )
        if result.ok:
            submittable.append((m, result))

    print(render_table(rows))
    print()
    # Detail lines: show each mission's per-check structural verdict (cached
    # from the single verification above — no extra GitHub calls).
    for r in rows:
        print("  %s [%s]: %s" % (r["id"], r.get("language", "?"), r.get("_detail", "")))
    print()

    if not submittable:
        print(
            "No mission passed the structural checks for repo %s/%s. "
            "Nothing was submitted (the GitHub oracle would reject it too)."
            % (owner, repo)
        )
        return 2

    proof = submittable[0][1].url  # canonical repo URL; identical for all rows

    if args.dry_run:
        print(
            "DRY-RUN: %d mission(s) would receive proof %r. No submissions were "
            "sent. Re-run with --no-dry-run --agent-id <id> to deliver."
            % (len(submittable), proof)
        )
        return 0

    # Real submission path — requires an agent id.
    if not args.agent_id:
        sys.stderr.write(
            "ERROR: --agent-id is required for a real (non-dry-run) submit.\n"
        )
        return 3

    any_error = False
    for m, result in submittable:
        mid = m["id"]
        print(
            "Submitting proof=%r to %s as agent %r ..." % (result.url, mid, args.agent_id)
        )
        try:
            code, body = client.submit(mid, args.agent_id, result.url)
        except APIError as exc:
            any_error = True
            print("  network error: %s" % exc)
            continue
        # The API returns HTTP 200 with an {"error": ...} field on logical
        # failures (bad agent id, already-resolved, etc.); surface that.
        if isinstance(body, dict) and body.get("error"):
            print("  rejected: %s" % body["error"])
            any_error = True
        elif code >= 400:
            print("  HTTP %d: %s" % (code, _short(body)))
            any_error = True
        else:
            print(
                "  accepted: %s"
                % (json.dumps(body) if not isinstance(body, str) else body)
            )
    return 4 if any_error else 0


# --------------------------------------------------------------------------- #
# Offline self-test (stubs GitHub + OABP; runs under --self-test and on import)
# --------------------------------------------------------------------------- #


class _StubSession:
    """Minimal stand-in for ``requests.Session`` returning canned responses.

    ``routes`` maps a URL suffix -> ``(status_code, json_body)``. The longest
    matching suffix wins, so ``/languages`` is matched before the bare repo URL.
    """

    class _Resp:
        def __init__(self, status: int, payload: Any) -> None:
            self.status_code = status
            self._payload = payload
            self.text = payload if isinstance(payload, str) else json.dumps(payload)

        def json(self) -> Any:
            if isinstance(self._payload, str):
                raise ValueError("not json")
            return self._payload

    def __init__(self, routes: Dict[str, Tuple[int, Any]]) -> None:
        self.routes = routes
        self.headers: Dict[str, str] = {}
        self.posted: List[Tuple[str, Dict[str, Any]]] = []

    def get(self, url: str, timeout: float = 0.0) -> "_StubSession._Resp":
        best: Optional[str] = None
        for suffix in self.routes:
            if url.endswith(suffix) and (best is None or len(suffix) > len(best)):
                best = suffix
        if best is None:
            return self._Resp(404, {"message": "Not Found", "url": url})
        status, payload = self.routes[best]
        return self._Resp(status, payload)

    def post(self, url: str, json: Any = None, timeout: float = 0.0):  # noqa: A002
        self.posted.append((url, json or {}))
        return self._Resp(200, {"status": "accepted", "resolved": True})


def _make_verifier(routes: Dict[str, Tuple[int, Any]]) -> GitHubVerifier:
    return GitHubVerifier(session=_StubSession(routes))


def _run_quiet(fn, *a, **k):
    """Call ``fn(*a, **k)`` with stdout/stderr suppressed; return its result.

    Used so the import-time self-test can exercise the full ``run_once`` flow
    (which prints tables) without polluting normal program output.
    """
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        return fn(*a, **k)


def _self_test(verbose: bool = False) -> None:
    """Offline assertions: stub GitHub and prove accept/reject behaviour.

    Covers (per the acceptance criteria):
      * a matching-language, non-empty repo is ACCEPTED;
      * an empty repo is REJECTED;
      * a wrong-language repo is REJECTED;
      * language inference covers Go / Ruby / PHP / Python / Rust / TypeScript;
      * --dry-run posts nothing (the OABP stub records zero POSTs);
      * the real mis_* ids round-trip through discovery + verification.

    ``verbose`` lets the ``--self-test`` CLI path show the full ``run_once``
    output; the import-time invocation keeps it quiet.
    """
    _runner = run_once if verbose else (lambda *a, **k: _run_quiet(run_once, *a, **k))

    # ---- language inference (Go / Ruby / PHP / Python / Rust / TypeScript) -- #
    assert infer_language("Implement OABP AIP-1 client in Golang") == "Go"
    assert infer_language("Implement OABP AIP-1 client in Ruby") == "Ruby"
    assert infer_language("Implement OABP AIP-1 client in PHP") == "PHP"
    assert infer_language("Build a Python SDK for OABP") == "Python"
    assert infer_language("a Rust implementation of the client") == "Rust"
    assert infer_language("write it in TypeScript please") == "TypeScript"
    # whole-word guard: a bare "go" inside a word must NOT fire as Go
    assert infer_language("a great algorithm, no language named") is None
    assert infer_language("targets the go runtime") == "Go"  # standalone "go"
    # canonicalization of explicit --language values
    assert canonicalize_language("golang") == "Go"
    assert canonicalize_language("PHP") == "PHP"
    assert canonicalize_language("klingon") is None

    # ---- owner/name parsing ------------------------------------------------ #
    assert parse_owner_repo("myorg/oabp-go") == ("myorg", "oabp-go")
    assert parse_owner_repo("https://github.com/myorg/oabp-go") == ("myorg", "oabp-go")
    assert parse_owner_repo("https://github.com/myorg/oabp-go.git") == ("myorg", "oabp-go")
    for bad in ["noslash", "a/b/c", "", "  /x", "x/  "]:
        try:
            parse_owner_repo(bad)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected ValueError for %r" % bad)

    # ---- ACCEPT: matching-language, non-empty repo ------------------------- #
    accept_routes = {
        "/repos/myorg/oabp-go": (200, {"size": 142, "full_name": "myorg/oabp-go"}),
        "/repos/myorg/oabp-go/languages": (200, {"Go": 18234, "Makefile": 312}),
    }
    v = _make_verifier(accept_routes)
    r = v.verify("myorg", "oabp-go", "Go")
    assert r.exists and r.non_empty and r.language_ok, r.summary()
    assert r.ok, r.summary()
    assert r.url == "https://github.com/myorg/oabp-go"
    assert "Go" in r.detected_languages

    # ---- REJECT: wrong-language repo --------------------------------------- #
    wrong = _make_verifier(
        {
            "/repos/myorg/oabp-go": (200, {"size": 80}),
            "/repos/myorg/oabp-go/languages": (200, {"Python": 5000}),
        }
    )
    r2 = wrong.verify("myorg", "oabp-go", "Go")
    assert r2.exists and r2.non_empty and not r2.language_ok, r2.summary()
    assert not r2.ok
    assert "not present" in r2.reason

    # ---- REJECT: empty repo (no languages) --------------------------------- #
    empty = _make_verifier(
        {
            "/repos/myorg/empty": (200, {"size": 0}),
            "/repos/myorg/empty/languages": (200, {}),
        }
    )
    r3 = empty.verify("myorg", "empty", "Go")
    assert r3.exists and not r3.non_empty and not r3.ok, r3.summary()
    assert "empty" in r3.reason.lower()

    # ---- REJECT: README-only repo (size>0 but no code languages) ----------- #
    readme_only = _make_verifier(
        {
            "/repos/myorg/docs": (200, {"size": 7}),
            "/repos/myorg/docs/languages": (200, {}),
        }
    )
    r4 = readme_only.verify("myorg", "docs", "Ruby")
    assert not r4.non_empty and not r4.ok

    # ---- REJECT: missing repo (404) ---------------------------------------- #
    missing = _make_verifier({})  # every GET 404s
    r5 = missing.verify("ghost", "nope", "PHP")
    assert not r5.exists and not r5.ok
    assert "does not exist" in r5.reason

    # ---- end-to-end via stubbed OABP + GitHub, real mis_* ids, DRY-RUN ----- #
    # Two real live missions: Go (mis_2bbc63696ffd) and PHP (mis_ab37cc7aab37).
    oabp_routes = {
        "/api/missions": (
            200,
            {
                "count": 2,
                "missions": [
                    {
                        "id": "mis_2bbc63696ffd",
                        "title": "Implement OABP AIP-1 client in Golang",
                        "description": "Deliver a public GitHub repository.",
                        "verification_type": "oracle",
                        "verification_params": {
                            "oracle_description": "GitHub repo implementing the AIP-1 client in Go"
                        },
                        "reward": {"amount": 250, "currency": "AIGEN"},
                        "status": "open",
                    },
                    {
                        "id": "mis_ab37cc7aab37",
                        "title": "Implement OABP AIP-1 client in PHP",
                        "description": "Deliver a public GitHub repository.",
                        "verification_type": "oracle",
                        "verification_params": {
                            "oracle_description": "GitHub repo implementing the AIP-1 client in PHP"
                        },
                        "reward": {"amount": 250, "currency": "AIGEN"},
                        "status": "open",
                    },
                ],
            },
        ),
        "/api/missions/mis_2bbc63696ffd": (
            200,
            {
                "id": "mis_2bbc63696ffd",
                "title": "Implement OABP AIP-1 client in Golang",
                "verification_type": "oracle",
                "verification_params": {
                    "oracle_description": "GitHub repo implementing the AIP-1 client in Go"
                },
                "reward": {"amount": 250, "currency": "AIGEN"},
                "status": "open",
            },
        ),
    }
    oabp_stub = _StubSession(oabp_routes)
    oabp = OABPClient(DEFAULT_BASE_URL)
    oabp._session = oabp_stub  # inject the stub

    missions = discover_missions(oabp, None, verbose=False)
    ids = {m["id"] for m in missions}
    assert "mis_2bbc63696ffd" in ids and "mis_ab37cc7aab37" in ids, ids
    by_id = {m["id"]: m for m in missions}
    assert by_id["mis_2bbc63696ffd"]["_language"] == "Go"
    assert by_id["mis_ab37cc7aab37"]["_language"] == "PHP"

    # Repo is a Go repo -> auto-match should select ONLY the Go mission.
    sel, eff = select_missions(missions, None, "Go")
    assert [m["id"] for m in sel] == ["mis_2bbc63696ffd"], [m["id"] for m in sel]
    assert eff == "Go"

    # DRY-RUN end-to-end: nothing must be POSTed.
    gh = _make_verifier(accept_routes)
    args = argparse.Namespace(
        repo="myorg/oabp-go",
        mission_id=None,
        agent_id=None,
        language=None,
        dry_run=True,
    )
    rc = _runner(oabp, gh, args)
    assert rc == 0, rc
    assert oabp_stub.posted == [], "dry-run must not POST anything"

    # Wrong-language repo against the same Go mission -> exit 2, still no POST.
    gh_wrong = _make_verifier(
        {
            "/repos/myorg/oabp-go": (200, {"size": 80}),
            "/repos/myorg/oabp-go/languages": (200, {"Python": 5000}),
        }
    )
    args_wrong = argparse.Namespace(
        repo="myorg/oabp-go",
        mission_id="mis_2bbc63696ffd",
        agent_id="bot",
        language=None,
        dry_run=False,
    )
    rc2 = _runner(oabp, gh_wrong, args_wrong)
    assert rc2 == 2, rc2
    assert oabp_stub.posted == [], "rejected repo must not POST anything"


# Run the self-test at import time so the file can never ship broken. It is
# cheap, pure, and fully offline. Disable by setting the env var below.
if os.environ.get("REPO_DELIVERER_SKIP_SELFTEST") != "1":
    _self_test()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="github_repo_deliverer",
        description=(
            "Autonomous OABP/AIGEN agent that delivers a GitHub repo to a "
            "matching 'oracle' (repo-deliverable) mission. It runs the SAME "
            "structural checks as the protocol's GitHub oracle "
            "(exists / non-empty / right-language, no code execution) and "
            "submits the repo URL as proof. Defaults to a safe DRY-RUN."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "Live target missions: mis_2bbc63696ffd (Go), mis_4d7f00fac5f8 "
            "(Ruby), mis_ab37cc7aab37 (PHP). AIGEN is the protocol's uncapped "
            "reputation/points token; a 0.5%% fee is taken from every payout. "
            "Set GITHUB_TOKEN to raise GitHub's rate limit."
        ),
    )
    parser.add_argument(
        "--repo",
        default=None,
        help=(
            "Your delivered repo as 'owner/name' (or a github.com URL). "
            "Required for every action except --self-test."
        ),
    )
    parser.add_argument(
        "--mission-id",
        default=None,
        help="Target this mission id explicitly. If omitted, auto-match by language.",
    )
    parser.add_argument(
        "--agent-id",
        default=None,
        help="Your submitter_agent_id. REQUIRED before any real submit.",
    )
    parser.add_argument(
        "--language",
        default=None,
        help=(
            "Override the required language (Go/Ruby/PHP/Python/Rust/TypeScript). "
            "If omitted, it is inferred from the mission and/or the repo's own "
            "dominant language."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="OABP API base URL.",
    )
    parser.add_argument(
        "--github-token",
        default=None,
        help="GitHub token (else read from $GITHUB_TOKEN). Optional; raises rate limit.",
    )
    dry = parser.add_mutually_exclusive_group()
    dry.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Verify and print the intended proof; submit NOTHING (default).",
    )
    dry.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Actually POST the submission (requires --agent-id).",
    )
    parser.set_defaults(dry_run=True)

    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the offline self-test (stubs GitHub + OABP) and exit.",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        try:
            _self_test(verbose=True)
        except AssertionError as exc:  # pragma: no cover
            sys.stderr.write("SELF-TEST FAILED: %s\n" % (exc,))
            return 2
        print("\ngithub-repo-deliverer self-test: OK")
        return 0

    if not args.repo:
        sys.stderr.write(
            "ERROR: --repo owner/name is required (or pass --self-test).\n"
        )
        return 3

    token = args.github_token or os.environ.get("GITHUB_TOKEN")
    client = OABPClient(args.base_url)
    verifier = GitHubVerifier(token=token)

    try:
        return run_once(client, verifier, args)
    except APIError as exc:
        sys.stderr.write("API error: %s\n" % exc)
        return 4
    except GitHubError as exc:
        sys.stderr.write("GitHub error: %s\n" % exc)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
