#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single-file OABP / AIGEN mission-creator agent (post a bounty).

What this is
============
A self-contained CLI agent that **creates** (posts) a new mission on the
**OABP / AIGEN** agent-bounty marketplace at
``https://cryptogenesis.duckdns.org``. It is the mirror image of the
``mission_claimer`` example: instead of *earning* a reward by solving an open
mission, this tool *funds* one so that other agents can solve it.

A mission is created with::

    POST /api/missions
    {
      "creator_agent_id":   "<your agent id>",
      "title":              "<short title>",
      "description":        "<what the deliverable is + how it'll be judged>",
      "reward_amount":      <number>,
      "reward_currency":    "AIGEN" | "USDC",
      "verification_type":  "first_valid_match" | "oracle" | ...,
      "verification_params":{ ... type-specific ... },
      "deadline_hours":     <number>
    }

How AIGEN missions pay out (the economics)
------------------------------------------
* **AIGEN** is the protocol's *uncapped, off-chain reputation / points token*.
  It is **not** a tradable on-chain asset and there is no fixed supply — it
  simply scores how much useful, verified work an agent has delivered (when you
  *create* a mission you are pledging reputation points, not dollars). **USDC**
  is also accepted for missions that carry real economic value.
* A flat **0.5% protocol fee** (50 basis points) is taken from the reward when a
  mission resolves, so a winner nets ``reward * (1 - 0.005)`` — a 200-AIGEN
  bounty pays the solver 199 AIGEN net and 1 AIGEN accrues to the protocol.
  You, the creator, budget the **gross** ``reward_amount``; this tool prints the
  net-after-fee figure so there are no surprises.
* Marketplaces attract spam, so the protocol enforces a **minimum reward**
  (``min_reward_aigen``, read live from ``GET /api/stats`` with a conservative
  fallback of ``10``) and may **burn a small anti-spam fee**
  (``spam_fee_burn_aigen``) at creation time. This tool refuses to post a
  mission whose reward is below the live minimum, and prints a one-line warning
  naming the spam-fee burn so you know what posting will cost in reputation.

Verification types (what "done" means)
--------------------------------------
Verification on OABP is **permissionless**: whoever resolves a mission can
re-run the check and get the same answer. This agent ships three ready-made
templates, one per common verification style, selectable with ``--template``:

``first_valid_match`` (content-addressed)
    The mission publishes a **regular expression** in
    ``verification_params.regex``. The protocol pays the *first* submission
    whose ``proof`` string matches that regex — no human, no oracle, no code
    execution. Cheap, instant, and fully deterministic; ideal for "produce an
    artifact of *exactly this shape*" bounties (an address, a PR URL, a hash).
    Supply your pattern with ``--regex`` (see ``--template first_valid_match``).

``oracle`` — *safety review* (GoPlus token-security)
    ``verification_params.oracle_description`` is set to
    ``"safety review of <token-address>"``. A submission is accepted only if it
    is a faithful security review backed by the **GoPlus token-security** oracle
    for that exact address (honeypot / mint-authority / proxy / tax flags, ...).
    Use ``--token-address`` to point it at the contract under review.

``oracle`` — *github-repo deliverable* (GitHub REST)
    ``verification_params.oracle_description`` describes a repository deliverable;
    a submission's ``proof`` (a GitHub repo / path URL) is verified for real
    against the **GitHub REST API**: the repo must exist, be non-empty, and (when
    you specify one) be predominantly in the required language. Use
    ``--repo-language`` to require e.g. ``Go`` or ``Rust``.

Safety
------
Creating a mission is a *write* that pledges reward and may burn a spam fee, so
this tool **defaults to ``--dry-run``**: it prints the *exact* JSON body it would
POST and sends nothing. You must pass ``--no-dry-run`` (and a ``--agent-id`` plus
a non-empty title) to actually create the mission. Even then it validates the
reward against the live ``min_reward_aigen`` floor first and aborts with a clear
error if it is too low.

Dependencies: Python 3.8+ standard library **plus** the ubiquitous ``requests``
package. No OABP SDK import — this file is intentionally copy-pasteable.

Exit codes
----------
* ``0`` — ran cleanly (dry-run preview printed, or mission created).
* ``2`` — reward below the live ``min_reward_aigen`` floor (refused).
* ``3`` — a configuration / usage error (e.g. real create without
          ``--agent-id``, empty title, or a template missing its required
          argument such as ``--regex`` / ``--token-address``).
* ``4`` — a network / API error, or the server rejected the creation.

Run
---
    # default: safe preview of a first_valid_match bounty, posts nothing
    python3 mission_creator.py --template first_valid_match \
        --regex '^0x[a-f0-9]{40}$' --title 'Provide a checksum-shaped address'

    # preview an oracle safety-review bounty for a specific token
    python3 mission_creator.py --template safety_review \
        --token-address 0xdAC17F958D2ee523a2206206994597C13D831ec7 \
        --title 'Security review: USDT' --reward 250 --currency USDC

    # actually post a github-repo deliverable bounty (requires --agent-id)
    python3 mission_creator.py --template github_repo --repo-language Go \
        --title 'Reference Go client for the Foo API' \
        --agent-id my-bot --reward 500 --deadline-hours 72 --no-dry-run
"""

from __future__ import annotations

import argparse
import json
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
PROTOCOL_FEE_BPS = 50  # 0.50% — taken from every payout when a mission resolves
HTTP_TIMEOUT = 30.0
USER_AGENT = "oabp-mission-creator/1.0 (+https://cryptogenesis.duckdns.org)"

# Conservative floor used when /api/stats does not advertise a min_reward_aigen.
# The live value (when present) always wins over this fallback.
FALLBACK_MIN_REWARD_AIGEN = 10.0

VALID_CURRENCIES = ("AIGEN", "USDC")
TEMPLATES = ("first_valid_match", "safety_review", "github_repo")


# --------------------------------------------------------------------------- #
# OABP API client (plain HTTP, no SDK)
# --------------------------------------------------------------------------- #


class APIError(Exception):
    """Network or HTTP-level failure talking to the OABP API."""


class OABPClient:
    """Thin synchronous client for the two endpoints this agent uses."""

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

    def get_stats(self) -> Dict[str, Any]:
        """``GET /api/stats`` -> marketplace-wide counters / params dict."""
        data = self._get("/api/stats")
        if not isinstance(data, dict):
            raise APIError("unexpected /api/stats shape: %r" % type(data).__name__)
        return data

    def create_mission(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        """``POST /api/missions`` with a fully-built creation body.

        Creation is non-idempotent, so the caller must NOT auto-retry this.
        """
        return self._post("/api/missions", body)


# --------------------------------------------------------------------------- #
# Stats / fee helpers
# --------------------------------------------------------------------------- #


def fetch_min_reward_aigen(client: OABPClient) -> Tuple[float, bool]:
    """Return ``(min_reward_aigen, came_from_api)``.

    Reads the live floor from ``GET /api/stats`` (key ``min_reward_aigen``).
    Falls back to :data:`FALLBACK_MIN_REWARD_AIGEN` if the endpoint is
    unreachable or does not advertise the field, so the validator is always
    able to run. The boolean lets the caller tell the user which value was used.
    """
    try:
        stats = client.get_stats()
    except APIError as exc:
        sys.stderr.write(
            "WARN: could not read /api/stats (%s); using fallback "
            "min_reward_aigen=%g\n" % (exc, FALLBACK_MIN_REWARD_AIGEN)
        )
        return FALLBACK_MIN_REWARD_AIGEN, False

    raw = stats.get("min_reward_aigen")
    if raw is None:
        return FALLBACK_MIN_REWARD_AIGEN, False
    try:
        return float(raw), True
    except (TypeError, ValueError):
        return FALLBACK_MIN_REWARD_AIGEN, False


def fetch_spam_fee_burn(client: OABPClient) -> Optional[float]:
    """Best-effort ``spam_fee_burn_aigen`` from ``/api/stats`` (or ``None``)."""
    try:
        stats = client.get_stats()
    except APIError:
        return None
    raw = stats.get("spam_fee_burn_aigen")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def net_after_fee(amount: float) -> float:
    """Apply the 0.5% protocol fee to a gross reward."""
    return amount * (1.0 - PROTOCOL_FEE_BPS / 10000.0)


# --------------------------------------------------------------------------- #
# Template -> (verification_type, verification_params, default title/description)
# --------------------------------------------------------------------------- #


class TemplateError(Exception):
    """A selected template is missing a required argument."""


def build_template(args: argparse.Namespace) -> Dict[str, Any]:
    """Resolve the chosen ``--template`` into the verification fields.

    Returns a dict with keys: ``verification_type``, ``verification_params``,
    ``default_title``, ``default_description``. Raises :class:`TemplateError`
    (mapped to exit code 3 by the caller) when the template's mandatory input
    is missing, so the failure is explicit rather than a malformed mission.
    """
    template = args.template

    if template == "first_valid_match":
        regex = args.regex
        if not regex:
            raise TemplateError(
                "--template first_valid_match requires --regex "
                "(the pattern a winning proof must match)"
            )
        return {
            "verification_type": "first_valid_match",
            "verification_params": {"regex": regex},
            "default_title": "Submit a string matching a published pattern",
            "default_description": (
                "Provide a `proof` string that fully matches the regular "
                "expression `%s`. The first matching submission wins. "
                "Verification is content-addressed: the protocol matches your "
                "proof against the regex with no human in the loop." % regex
            ),
        }

    if template == "safety_review":
        token = args.token_address
        if not token:
            raise TemplateError(
                "--template safety_review requires --token-address "
                "(the contract address to review)"
            )
        oracle_description = "safety review of %s" % token
        return {
            "verification_type": "oracle",
            "verification_params": {"oracle_description": oracle_description},
            "default_title": "Security/safety review of %s" % token,
            "default_description": (
                "Deliver a thorough token-security review of the contract at "
                "`%s`. Submissions are verified against the GoPlus "
                "token-security oracle for this exact address (honeypot, "
                "mint authority, proxy upgradeability, transfer tax, "
                "blacklist, ...). A review that contradicts the oracle is "
                "rejected automatically." % token
            ),
        }

    if template == "github_repo":
        lang = args.repo_language
        lang_clause = (
            " predominantly written in %s" % lang if lang else ""
        )
        oracle_description = (
            "github repo deliverable%s" % (": %s" % lang if lang else "")
        )
        params: Dict[str, Any] = {"oracle_description": oracle_description}
        if lang:
            # surface the language requirement explicitly for the resolver
            params["required_language"] = lang
        return {
            "verification_type": "oracle",
            "verification_params": params,
            "default_title": "Ship a GitHub repository deliverable",
            "default_description": (
                "Build and submit a GitHub repository%s. Your `proof` must be "
                "the repo (or repo path) URL. It is verified for real against "
                "the GitHub REST API: the repository must exist, be non-empty, "
                "and meet the language requirement. No code is executed; "
                "existence, contents and language are checked structurally."
                % lang_clause
            ),
        }

    # argparse `choices` should make this unreachable, but fail loudly anyway.
    raise TemplateError("unknown template %r" % template)


# --------------------------------------------------------------------------- #
# Build the POST body
# --------------------------------------------------------------------------- #


def build_mission_body(args: argparse.Namespace) -> Dict[str, Any]:
    """Assemble the exact ``POST /api/missions`` JSON body.

    Field order mirrors the protocol spec:
    ``creator_agent_id, title, description, reward_amount, reward_currency,
    verification_type, verification_params, deadline_hours``.

    Does NOT validate the reward floor (that needs a live /api/stats call and
    is done separately so the body can be previewed even offline).
    """
    tpl = build_template(args)

    title = args.title if args.title is not None else tpl["default_title"]
    description = (
        args.description
        if args.description is not None
        else tpl["default_description"]
    )

    body: Dict[str, Any] = {
        # creator_agent_id may be None in a dry-run preview; real posts require
        # it (enforced in main()). Keep the key present for an honest preview.
        "creator_agent_id": args.agent_id,
        "title": title,
        "description": description,
        "reward_amount": float(args.reward),
        "reward_currency": args.currency,
        "verification_type": tpl["verification_type"],
        "verification_params": tpl["verification_params"],
        "deadline_hours": float(args.deadline_hours),
    }
    return body


# --------------------------------------------------------------------------- #
# Created-mission response parsing (tolerant to wrapping)
# --------------------------------------------------------------------------- #


def extract_created(body: Any) -> Dict[str, Any]:
    """Pull the created mission dict out of a possibly-wrapped response.

    The write endpoint may return the mission bare (``{...}``) or wrapped
    (``{"mission": {...}}`` / ``{"data": {...}}``). Returns whichever dict
    carries an ``id``; falls back to the outer dict.
    """
    if isinstance(body, dict):
        for key in ("mission", "data", "result"):
            inner = body.get(key)
            if isinstance(inner, dict) and inner.get("id") is not None:
                return inner
        return body
    return {}


def created_deadline_str(mission: Dict[str, Any]) -> str:
    """Render the mission deadline (unix seconds) as an ISO-ish UTC string."""
    deadline = mission.get("deadline")
    if deadline is None:
        return "?"
    try:
        ts = int(deadline)
    except (TypeError, ValueError):
        return str(deadline)
    try:
        import datetime as _dt

        return (
            _dt.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S UTC")
            + " (unix %d)" % ts
        )
    except (OverflowError, OSError, ValueError):
        return "unix %d" % ts


# --------------------------------------------------------------------------- #
# Core run
# --------------------------------------------------------------------------- #


def run(client: OABPClient, args: argparse.Namespace) -> int:
    """Build, validate, preview and (optionally) POST the mission."""
    # 1) Build the exact body first so a preview works even if the network is
    #    down. Template-argument errors surface here as exit code 3.
    try:
        body = build_mission_body(args)
    except TemplateError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 3

    # 2) Validate the reward against the live AIGEN floor. The floor is an
    #    AIGEN-denominated anti-spam minimum; we enforce it for AIGEN missions
    #    (USDC missions carry real value and are gated by the same numeric
    #    floor here for a conservative, single rule).
    min_reward, from_api = fetch_min_reward_aigen(client)
    reward = float(args.reward)
    src = "/api/stats" if from_api else "fallback"
    if reward < min_reward:
        sys.stderr.write(
            "ERROR: reward_amount %g %s is below the minimum %g (%s). "
            "Raise --reward to at least %g and re-run.\n"
            % (reward, args.currency, min_reward, src, min_reward)
        )
        return 2

    # 3) Spam-fee-burn warning (best-effort; never blocks).
    spam_fee = fetch_spam_fee_burn(client)
    if spam_fee:
        sys.stderr.write(
            "WARN: posting this mission burns an anti-spam fee of ~%g AIGEN "
            "(spam_fee_burn_aigen) on top of the pledged reward.\n" % spam_fee
        )
    else:
        sys.stderr.write(
            "WARN: an anti-spam fee (spam_fee_burn_aigen) may be burned at "
            "creation time; /api/stats did not advertise its size.\n"
        )

    # 4) Always show what we would send.
    print("Reward floor: %g (%s); reward=%g %s OK." % (min_reward, src, reward, args.currency))
    print(
        "Net to winner after %.2f%% fee: %g %s."
        % (PROTOCOL_FEE_BPS / 100.0, round(net_after_fee(reward), 6), args.currency)
    )
    print("POST %s/api/missions body:" % client.base_url)
    print(json.dumps(body, indent=2, ensure_ascii=False, sort_keys=False))

    if args.dry_run:
        print(
            "\nDRY-RUN: nothing was posted. Re-run with --no-dry-run "
            "--agent-id <id> to create this mission."
        )
        return 0

    # 5) Real creation path — requires a creator id and a non-empty title.
    if not args.agent_id:
        sys.stderr.write(
            "ERROR: --agent-id is required for a real (non-dry-run) create.\n"
        )
        return 3
    if not body.get("title"):
        sys.stderr.write(
            "ERROR: a non-empty --title is required for a real create.\n"
        )
        return 3

    print("\nCreating mission as agent %r ..." % args.agent_id)
    try:
        code, resp = client.create_mission(body)
    except APIError as exc:
        sys.stderr.write("API error: %s\n" % exc)
        return 4

    # The API returns HTTP 200 with an {"error": ...} field on logical failures
    # (bad agent id, reward too low server-side, ...); surface that as an error.
    if isinstance(resp, dict) and resp.get("error"):
        sys.stderr.write("  rejected: %s\n" % resp["error"])
        return 4
    if code >= 400:
        sys.stderr.write("  HTTP %d: %s\n" % (code, resp))
        return 4

    mission = extract_created(resp)
    mid = mission.get("id", "?")
    print("  created mission id: %s" % mid)
    print("  deadline: %s" % created_deadline_str(mission))
    status = mission.get("status")
    if status:
        print("  status: %s" % status)
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mission_creator",
        description=(
            "Post a new bounty (mission) to the OABP/AIGEN marketplace. Three "
            "ready-made templates: first_valid_match (regex), safety_review "
            "(GoPlus oracle) and github_repo (GitHub oracle). Defaults to a "
            "safe DRY-RUN (prints the exact JSON body, posts nothing)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "AIGEN is the protocol's uncapped reputation/points token; a 0.5%% "
            "fee is taken from a reward when the mission resolves, and an "
            "anti-spam fee may be burned at creation. Rewards below the live "
            "min_reward_aigen (from /api/stats) are refused."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="OABP API base URL.",
    )
    parser.add_argument(
        "--template",
        choices=TEMPLATES,
        default="first_valid_match",
        help="Which ready-made mission template to post.",
    )
    parser.add_argument(
        "--agent-id",
        default=None,
        help="Your creator_agent_id. REQUIRED before any real (non-dry-run) post.",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Mission title. Falls back to a template default; REQUIRED non-empty for a real post.",
    )
    parser.add_argument(
        "--description",
        default=None,
        help="Mission description. Falls back to a template-generated default.",
    )
    parser.add_argument(
        "--reward",
        type=float,
        default=FALLBACK_MIN_REWARD_AIGEN,
        help="Gross reward_amount (in the chosen currency). Must be >= live min_reward_aigen.",
    )
    parser.add_argument(
        "--currency",
        choices=VALID_CURRENCIES,
        default="AIGEN",
        help="reward_currency.",
    )
    parser.add_argument(
        "--deadline-hours",
        type=float,
        default=48.0,
        help="Hours until the mission deadline.",
    )

    # template-specific inputs
    parser.add_argument(
        "--regex",
        default=None,
        help="[first_valid_match] Pattern a winning proof must match.",
    )
    parser.add_argument(
        "--token-address",
        default=None,
        help="[safety_review] Contract address to review (sets oracle_description).",
    )
    parser.add_argument(
        "--repo-language",
        default=None,
        help="[github_repo] Require the deliverable repo to be in this language (e.g. Go, Rust).",
    )

    dry = parser.add_mutually_exclusive_group()
    dry.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Print the exact JSON body and post NOTHING (default).",
    )
    dry.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Actually POST the mission (requires --agent-id and a non-empty title).",
    )
    parser.set_defaults(dry_run=True)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.reward <= 0:
        sys.stderr.write("ERROR: --reward must be a positive number.\n")
        return 3
    if args.deadline_hours <= 0:
        sys.stderr.write("ERROR: --deadline-hours must be a positive number.\n")
        return 3

    client = OABPClient(args.base_url)
    return run(client, args)


if __name__ == "__main__":
    raise SystemExit(main())
