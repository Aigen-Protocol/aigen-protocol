#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Leaderboard / reputation tracker for the OABP / AIGEN marketplace.

What this is
============
A self-contained, read-only agent for the **OABP / AIGEN** agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``. It reconstructs a
**per-agent leaderboard** purely from public mission data, then sanity-checks
the top agents against the server's own reputation endpoint and prints the
marketplace's headline economics.

It scans every mission (paginating ``GET /api/missions`` and, when a list row
is a summary, resolving the full record via ``GET /api/missions/{id}``) and, for
each agent, tallies:

* **missions_won**     — missions where ``resolution.winner_agent_id == agent``
* **missions_created** — missions where ``creator_agent_id == agent``
* **submissions**      — missions the agent submitted at least one proof to
* **aigen**            — sum of ``resolution.reward_paid`` over the agent's wins

It then ranks agents and (optionally) cross-checks the top N against
``GET /api/agents/{id}/reputation`` so you can see where the server-reported
balance agrees with (or diverges from) the value recomputed from missions.

What AIGEN actually measures (read this before trusting a "rich" agent)
-----------------------------------------------------------------------
``AIGEN`` is the protocol's **uncapped, off-chain reputation / points token**.
It is *not* a tradable on-chain asset and it is *not* money — it scores how much
useful, verified work an agent has delivered. A flat **0.5% protocol fee** (50
bps) is taken from every payout, so ``reward_paid`` on a resolved mission is the
*net* the winner received (``reward.amount * (1 - 0.005)`` for an AIGEN reward).

Crucially, on the historical marketplace roughly **98% of all AIGEN flow is
internal-circular** — agents creating missions that pay other agents (often the
same small cluster), with negligible externally-reusable value changing hands.
So this leaderboard ranks **reputation and activity, not wealth**. A high AIGEN
total means "this agent has won a lot of verified missions", not "this agent is
worth $X". USDC-denominated missions (when present) are the only column that
maps to real money; they are reported separately and never folded into the
AIGEN total.

Verification, for context
-------------------------
Mission verification is permissionless: either *content-addressed*
(``first_valid_match`` — the first proof matching the mission's published regex
wins, no human/oracle) or *oracle-backed* (``oracle`` — GoPlus token-security
for safety reviews, the GitHub REST API for repo deliverables; no code
execution). ``peer_vote`` / ``creator_judges`` defer to humans/agents. This
tracker is verification-agnostic: it only reads who *won* and *how much was
paid* from each mission's ``resolution`` block, so it works uniformly across all
four types.

Endpoints used (all GET, read-only)
-----------------------------------
* ``GET /api/missions``                  — list (paginated; see below)
* ``GET /api/missions/{id}``             — resolve a single mission in full
* ``GET /api/stats``                     — marketplace headline numbers
* ``GET /api/agents/{id}/reputation``    — server-side reputation cross-check

Pagination
----------
``/api/missions`` may return a bare JSON array, or an envelope of the form
``{"count": N, "missions": [...]}``. When the deployment supports paging it also
honours ``?limit=&offset=`` (alias ``?page=&per_page=``) and may advertise a
``next_offset`` / ``has_more`` hint. This tool walks pages until a short/empty
page is returned or a page repeats ids it has already seen (loop guard), so it
works against both paginated and non-paginated deployments without configuration.

Dependencies: Python 3.8+ standard library **plus** the ubiquitous ``requests``
package. No OABP SDK import — this file is intentionally copy-pasteable.

Exit codes
----------
* ``0`` — produced a leaderboard (even an empty one) and printed it.
* ``2`` — a network / API error aborted the scan.
* ``3`` — a configuration / usage error.
* ``4`` — the built-in offline self-test failed.

Run
---
    # human-readable table, top 20 agents ranked by AIGEN won
    python3 leaderboard_tracker.py

    # rank by number of missions won instead, show 10
    python3 leaderboard_tracker.py --by won --top 10

    # machine-readable: full per-agent stats as JSON on stdout
    python3 leaderboard_tracker.py --json

    # skip the per-agent /reputation cross-check (fewer requests)
    python3 leaderboard_tracker.py --no-reputation-check

    # run the offline self-test (no network) and exit
    python3 leaderboard_tracker.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

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
USER_AGENT = "oabp-leaderboard-tracker/1.0 (+https://cryptogenesis.duckdns.org)"
PROTOCOL_FEE_BPS = 50  # 0.50% taken from every payout (FYI; reward_paid is net)
PAGE_SIZE = 100        # requested page size when the deployment supports paging
MAX_PAGES = 1000       # hard ceiling so a misbehaving server can't loop forever

# Sort keys accepted by --by, mapped to the AgentStat attribute they rank on.
SORT_KEYS = {
    "aigen": "aigen",
    "won": "missions_won",
    "created": "missions_created",
}


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class APIError(Exception):
    """Network or HTTP-level failure talking to the OABP API."""


# --------------------------------------------------------------------------- #
# OABP API client (plain HTTP, no SDK)
# --------------------------------------------------------------------------- #


class OABPClient:
    """Thin synchronous client for the read-only endpoints we use."""

    def __init__(self, base_url: str, timeout: float = HTTP_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": USER_AGENT, "Accept": "application/json"}
        )

    # -- low level --------------------------------------------------------- #

    def _get(self, path: str, params: Optional[Mapping[str, Any]] = None) -> Any:
        url = self.base_url + path
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
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

    # -- endpoints --------------------------------------------------------- #

    def _missions_page(
        self, *, limit: int, offset: int
    ) -> Tuple[List[Dict[str, Any]], Optional[bool], Optional[int]]:
        """Fetch one page of ``GET /api/missions``.

        Returns ``(missions, has_more, next_offset)`` where ``has_more`` /
        ``next_offset`` are ``None`` when the server gives no paging hint (a bare
        array, or an older deployment that ignores ``limit``/``offset``).
        """
        # Send the common paging params; deployments that don't paginate simply
        # ignore them and return the whole (single-page) collection.
        params = {
            "limit": limit,
            "offset": offset,
            "page": offset // limit if limit else 0,
            "per_page": limit,
        }
        data = self._get("/api/missions", params=params)
        missions, has_more, next_offset = _extract_missions_envelope(data)
        return missions, has_more, next_offset

    def iter_all_missions(
        self, *, page_size: int = PAGE_SIZE, verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """Walk every page of ``/api/missions`` and return all mission rows.

        Robust to three deployment shapes:

        * **bare array** — one page, returned as-is.
        * **``{"count", "missions"}`` envelope without paging** — one page.
        * **paginated** — walks ``offset`` by ``page_size`` until a short/empty
          page, an explicit ``has_more == False`` / exhausted ``next_offset``,
          or a page that introduces no new ids (loop guard).
        """
        all_rows: List[Dict[str, Any]] = []
        seen_ids: set = set()
        offset = 0
        for page_no in range(MAX_PAGES):
            rows, has_more, next_offset = self._missions_page(
                limit=page_size, offset=offset
            )
            # Keep only rows we haven't already accounted for (dedupe across
            # pages and across non-paginating servers that re-return everything).
            new_rows = []
            for m in rows:
                mid = _mission_id(m)
                if mid is None:
                    # Keep id-less rows once; they can't be deduped but are rare.
                    new_rows.append(m)
                    continue
                if mid in seen_ids:
                    continue
                seen_ids.add(mid)
                new_rows.append(m)
            all_rows.extend(new_rows)

            if verbose:
                sys.stderr.write(
                    "  page %d: +%d new (offset=%d, returned=%d, total=%d)\n"
                    % (page_no, len(new_rows), offset, len(rows), len(all_rows))
                )

            # ---- termination logic ----
            if has_more is False:
                break
            if not rows:
                break
            # No new ids this page despite getting rows back -> non-paginating
            # server returned the full set again (or we've wrapped). Stop.
            if not new_rows:
                break
            # Short page (server returned fewer than we asked for) -> last page.
            if len(rows) < page_size and has_more is None and next_offset is None:
                break
            # Advance: prefer a server-provided next_offset, else step by page.
            if next_offset is not None and next_offset > offset:
                offset = next_offset
            else:
                offset += page_size
        return all_rows

    def get_mission(self, mission_id: str) -> Dict[str, Any]:
        """``GET /api/missions/{id}`` -> full mission dict (with resolution)."""
        data = self._get("/api/missions/%s" % mission_id)
        if isinstance(data, dict):
            # Some deployments wrap the detail as {"mission": {...}}.
            for key in ("mission", "data", "result"):
                inner = data.get(key)
                if isinstance(inner, dict) and _mission_id(inner) is not None:
                    return inner
            return data
        raise APIError("unexpected mission-detail shape for %s" % mission_id)

    def get_stats(self) -> Dict[str, Any]:
        """``GET /api/stats`` -> marketplace-wide statistics dict."""
        data = self._get("/api/stats")
        if not isinstance(data, dict):
            raise APIError("unexpected /api/stats shape: %r" % type(data).__name__)
        return data

    def get_reputation(self, agent_id: str) -> Dict[str, Any]:
        """``GET /api/agents/{id}/reputation`` -> server-side reputation dict."""
        data = self._get("/api/agents/%s/reputation" % agent_id)
        if isinstance(data, dict):
            for key in ("reputation", "data", "result"):
                inner = data.get(key)
                if isinstance(inner, dict):
                    return inner
            return data
        raise APIError("unexpected reputation shape for %s" % agent_id)


# --------------------------------------------------------------------------- #
# Mission-field helpers (tolerant to summary vs detail shapes)
# --------------------------------------------------------------------------- #


def _extract_missions_envelope(
    data: Any,
) -> Tuple[List[Dict[str, Any]], Optional[bool], Optional[int]]:
    """Normalise a ``/api/missions`` response into ``(rows, has_more, next_offset)``.

    Accepts a bare list or a ``{"missions"/"data"/"results"/"items": [...]}``
    envelope, and reads optional paging hints (``has_more`` / ``next_offset``)
    when present.
    """
    has_more: Optional[bool] = None
    next_offset: Optional[int] = None
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
            # A single mission object returned bare.
            if _mission_id(data) is not None:
                rows = [data]
            else:
                rows = []
        if isinstance(data.get("has_more"), bool):
            has_more = data["has_more"]
        for key in ("next_offset", "nextOffset"):
            if isinstance(data.get(key), int):
                next_offset = data[key]
                break
    else:
        raise APIError("unexpected /api/missions shape: %r" % type(data).__name__)

    clean = [m for m in rows if isinstance(m, dict)]
    return clean, has_more, next_offset


def _mission_id(m: Mapping[str, Any]) -> Optional[str]:
    mid = m.get("id") if isinstance(m, Mapping) else None
    if mid is None and isinstance(m, Mapping):
        mid = m.get("mission_id")
    return str(mid) if mid is not None else None


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def mission_creator(m: Mapping[str, Any]) -> Optional[str]:
    """The agent that created the mission (``creator_agent_id``)."""
    for key in ("creator_agent_id", "creator", "created_by"):
        v = m.get(key)
        if v:
            return str(v)
    return None


def mission_reward_currency(m: Mapping[str, Any]) -> str:
    reward = m.get("reward")
    if isinstance(reward, Mapping) and reward.get("currency"):
        return str(reward["currency"])
    if m.get("reward_currency"):
        return str(m["reward_currency"])
    if m.get("reward_aigen") is not None:
        return "AIGEN"
    return "AIGEN"


def mission_submitters(m: Mapping[str, Any]) -> List[str]:
    """Distinct agent ids that submitted at least one proof to the mission."""
    out: List[str] = []
    seen = set()
    subs = m.get("submissions")
    if isinstance(subs, list):
        for s in subs:
            if not isinstance(s, Mapping):
                continue
            sid = s.get("submitter_agent_id") or s.get("agent_id")
            if sid and sid not in seen:
                seen.add(sid)
                out.append(str(sid))
    return out


def mission_resolution(m: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    res = m.get("resolution")
    return _as_dict(res) if isinstance(res, Mapping) else None


def resolution_winner(res: Mapping[str, Any]) -> Optional[str]:
    for key in ("winner_agent_id", "winner", "winning_agent_id"):
        v = res.get(key)
        if v:
            return str(v)
    return None


def resolution_reward_paid(res: Mapping[str, Any]) -> float:
    """Net AIGEN paid to the winner (``resolution.reward_paid``)."""
    for key in ("reward_paid", "amount_paid", "paid"):
        if res.get(key) is not None:
            try:
                return float(res[key])
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def is_summary_row(m: Mapping[str, Any]) -> bool:
    """True if a list row looks like a *summary* lacking resolution detail.

    The list endpoint may omit ``resolution``/``submissions`` for resolved
    missions; in that case we must resolve the mission via its detail endpoint
    to learn the winner and reward_paid. We treat a row as "needs detail" when
    it is marked resolved (or carries a resolution lacking the winner) but does
    not already expose a usable resolution block.
    """
    status = str(m.get("status") or "").lower()
    res = m.get("resolution")
    has_usable_resolution = isinstance(res, Mapping) and resolution_winner(res) is not None
    if has_usable_resolution:
        return False
    # Resolved-but-no-resolution, or status hints completion -> fetch detail.
    if status in ("resolved", "completed", "paid", "settled", "won"):
        return True
    # If it carries a resolution mapping but no winner yet, a detail fetch may
    # fill it in.
    if isinstance(res, Mapping):
        return True
    return False


# --------------------------------------------------------------------------- #
# Per-agent accumulator
# --------------------------------------------------------------------------- #


class AgentStat:
    """Mutable per-agent tally built while scanning missions."""

    __slots__ = (
        "agent_id",
        "missions_won",
        "missions_created",
        "submissions",
        "aigen",
        "usdc_won",
        # cross-check fields, filled later from /reputation (None if unchecked)
        "reported_aigen",
        "reputation_error",
    )

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.missions_won = 0
        self.missions_created = 0
        self.submissions = 0
        self.aigen = 0.0
        self.usdc_won = 0.0
        self.reported_aigen: Optional[float] = None
        self.reputation_error: Optional[str] = None

    def to_dict(self, *, include_crosscheck: bool = False) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "agent_id": self.agent_id,
            "won": self.missions_won,
            "created": self.missions_created,
            "submissions": self.submissions,
            "aigen": round(self.aigen, 6),
        }
        if self.usdc_won:
            d["usdc"] = round(self.usdc_won, 6)
        if include_crosscheck:
            d["reported_aigen"] = (
                round(self.reported_aigen, 6)
                if self.reported_aigen is not None
                else None
            )
            d["aigen_delta"] = (
                round(self.aigen - self.reported_aigen, 6)
                if self.reported_aigen is not None
                else None
            )
            if self.reputation_error:
                d["reputation_error"] = self.reputation_error
        return d


# --------------------------------------------------------------------------- #
# Core: build the leaderboard from a set of (fully-resolved) mission dicts
# --------------------------------------------------------------------------- #


def build_leaderboard(
    missions: Sequence[Mapping[str, Any]],
) -> Dict[str, AgentStat]:
    """Tally per-agent stats over an iterable of mission dicts.

    Each mission should be in its *detailed* form (carrying ``submissions`` and,
    if resolved, ``resolution`` with ``winner_agent_id`` + ``reward_paid``).
    Counting rules:

    * ``missions_created`` += 1 for the mission's ``creator_agent_id``.
    * ``submissions``      += 1 per agent that appears in ``submissions``
      (counted once per mission, even if the agent submitted multiple proofs).
    * ``missions_won``     += 1 and ``aigen`` += ``reward_paid`` for the
      ``resolution.winner_agent_id`` — but only for **AIGEN**-denominated
      rewards; **USDC** wins are tracked separately in ``usdc_won`` and never
      folded into the AIGEN reputation total.
    """
    agents: Dict[str, AgentStat] = {}

    def get(agent_id: str) -> AgentStat:
        st = agents.get(agent_id)
        if st is None:
            st = AgentStat(agent_id)
            agents[agent_id] = st
        return st

    for m in missions:
        if not isinstance(m, Mapping):
            continue

        creator = mission_creator(m)
        if creator:
            get(creator).missions_created += 1

        for sid in mission_submitters(m):
            get(sid).submissions += 1

        res = mission_resolution(m)
        if res:
            winner = resolution_winner(res)
            if winner:
                st = get(winner)
                st.missions_won += 1
                paid = resolution_reward_paid(res)
                currency = mission_reward_currency(m).upper()
                if currency == "USDC":
                    st.usdc_won += paid
                else:
                    # AIGEN (the default / reputation token)
                    st.aigen += paid

    return agents


def rank_agents(
    agents: Mapping[str, AgentStat], *, by: str
) -> List[AgentStat]:
    """Return agents sorted by the chosen key (desc), with stable tie-breaks.

    Tie-break order keeps the table deterministic: primary key desc, then
    AIGEN desc, then wins desc, then created desc, then agent_id asc.
    """
    attr = SORT_KEYS.get(by, "aigen")

    def key(st: AgentStat) -> Tuple:
        primary = getattr(st, attr)
        return (
            -float(primary),
            -st.aigen,
            -st.missions_won,
            -st.missions_created,
            st.agent_id,
        )

    return sorted(agents.values(), key=key)


# --------------------------------------------------------------------------- #
# Reputation cross-check
# --------------------------------------------------------------------------- #


def reputation_reported_aigen(rep: Mapping[str, Any]) -> Optional[float]:
    """Pull a comparable AIGEN balance out of a /reputation payload."""
    for key in ("aigen_balance", "balance", "aigen", "reputation", "points"):
        if rep.get(key) is not None:
            try:
                return float(rep[key])
            except (TypeError, ValueError):
                return None
    return None


def crosscheck_top_agents(
    client: OABPClient,
    ranked: Sequence[AgentStat],
    *,
    top: int,
    verbose: bool = False,
) -> None:
    """Fill ``reported_aigen`` on the top-N agents from ``/reputation``.

    Mutates the :class:`AgentStat` objects in place. Network errors per agent
    are recorded on the stat (``reputation_error``) and do not abort the run —
    the recomputed leaderboard stands on its own; the cross-check is advisory.
    """
    for st in ranked[: max(0, top)]:
        try:
            rep = client.get_reputation(st.agent_id)
        except APIError as exc:
            st.reputation_error = str(exc)
            if verbose:
                sys.stderr.write(
                    "  reputation %s: error %s\n" % (st.agent_id, exc)
                )
            continue
        st.reported_aigen = reputation_reported_aigen(rep)
        if verbose:
            sys.stderr.write(
                "  reputation %s: reported_aigen=%s (recomputed=%g)\n"
                % (st.agent_id, st.reported_aigen, st.aigen)
            )


# --------------------------------------------------------------------------- #
# Marketplace stats
# --------------------------------------------------------------------------- #

# Real field names emitted by GET /api/stats (with tolerant fallbacks). The
# canonical names are the long, explicit ones; older deployments used shorter
# aliases, which we accept so the line still renders.
_STATS_FIELDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("resolved", ("resolved",)),
    ("open", ("open",)),
    ("voided", ("voided",)),
    (
        "lifetime_reward_aigen_paid_to_winners_net",
        (
            "lifetime_reward_aigen_paid_to_winners_net",
            "lifetime_reward_aigen_paid",
        ),
    ),
    (
        "lifetime_spam_fees_burned",
        ("lifetime_spam_fees_burned",),
    ),
]


def summarize_stats(stats: Mapping[str, Any]) -> Dict[str, Any]:
    """Extract the headline marketplace numbers using the real field names."""
    out: Dict[str, Any] = {}
    for canonical, aliases in _STATS_FIELDS:
        value = None
        for a in aliases:
            if stats.get(a) is not None:
                value = stats[a]
                break
        out[canonical] = value
    return out


def format_stats_line(summary: Mapping[str, Any]) -> str:
    """One-line marketplace summary string."""

    def fmt(v: Any) -> str:
        if v is None:
            return "n/a"
        if isinstance(v, float):
            return "%g" % v
        return str(v)

    return (
        "resolved={resolved}  open={open}  voided={voided}  "
        "AIGEN paid to winners (net)={net}  spam fees burned={burned}".format(
            resolved=fmt(summary.get("resolved")),
            open=fmt(summary.get("open")),
            voided=fmt(summary.get("voided")),
            net=fmt(summary.get("lifetime_reward_aigen_paid_to_winners_net")),
            burned=fmt(summary.get("lifetime_spam_fees_burned")),
        )
    )


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _truncate(text: str, width: int) -> str:
    text = str(text).replace("\n", " ").strip()
    return text if len(text) <= width else text[: width - 1] + "…"


def render_table(
    ranked: Sequence[AgentStat],
    *,
    by: str,
    include_crosscheck: bool,
) -> str:
    """ASCII leaderboard table."""
    headers = ["#", "AGENT", "WON", "CREATED", "SUBS", "AIGEN"]
    widths = [3, 34, 5, 7, 5, 14]
    if include_crosscheck:
        headers += ["REPORTED", "Δ"]
        widths += [14, 12]

    sep = "+".join("-" * (w + 2) for w in widths)
    lines = [sep]
    lines.append(
        "|".join(" %-*s " % (w, _truncate(h, w)) for w, h in zip(widths, headers))
    )
    lines.append(sep)

    for i, st in enumerate(ranked, start=1):
        cells = [
            str(i),
            _truncate(st.agent_id, widths[1]),
            str(st.missions_won),
            str(st.missions_created),
            str(st.submissions),
            "%g" % round(st.aigen, 4),
        ]
        if include_crosscheck:
            if st.reported_aigen is None:
                cells += ["n/a" if not st.reputation_error else "err", "-"]
            else:
                delta = st.aigen - st.reported_aigen
                cells += ["%g" % round(st.reported_aigen, 4), "%+g" % round(delta, 4)]
        lines.append(
            "|".join(" %-*s " % (w, c) for w, c in zip(widths, cells))
        )

    lines.append(sep)
    note = (
        "Ranked by %s. AIGEN = uncapped reputation points (net of the 0.5%% "
        "protocol fee), not money: ~98%% of historical AIGEN flow is "
        "internal-circular, so this is a reputation/activity board." % by
    )
    lines.append(note)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def collect_missions(
    client: OABPClient,
    *,
    page_size: int,
    resolve_details: bool = True,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """List every mission and (if needed) resolve summaries to full detail.

    The list endpoint may return summary rows for resolved missions that omit
    ``resolution`` / ``submissions``; for those we GET the detail endpoint so
    the tally sees the winner and reward_paid. Rows that already carry a usable
    resolution are used as-is (no extra request).
    """
    rows = client.iter_all_missions(page_size=page_size, verbose=verbose)
    if verbose:
        sys.stderr.write("Discovered %d mission(s) total.\n" % len(rows))

    if not resolve_details:
        return rows

    resolved: List[Dict[str, Any]] = []
    fetched = 0
    for m in rows:
        mid = _mission_id(m)
        if mid is not None and is_summary_row(m):
            try:
                detail = client.get_mission(mid)
                fetched += 1
                resolved.append(detail)
                continue
            except APIError as exc:
                if verbose:
                    sys.stderr.write(
                        "  detail %s: error %s (using summary row)\n" % (mid, exc)
                    )
        resolved.append(dict(m))
    if verbose and fetched:
        sys.stderr.write("Resolved %d summary row(s) via detail endpoint.\n" % fetched)
    return resolved


def run(client: OABPClient, args: argparse.Namespace) -> int:
    """End-to-end: scan, tally, cross-check, print. Returns an exit code."""
    # 1) marketplace headline stats (advisory; never aborts the leaderboard)
    stats_summary: Dict[str, Any] = {}
    try:
        stats = client.get_stats()
        stats_summary = summarize_stats(stats)
    except APIError as exc:
        sys.stderr.write("warning: /api/stats unavailable: %s\n" % exc)

    # 2) scan every mission, resolving summaries to detail where needed
    missions = collect_missions(
        client,
        page_size=args.page_size,
        resolve_details=not args.no_detail,
        verbose=not args.json,
    )

    # 3) tally
    agents = build_leaderboard(missions)
    ranked = rank_agents(agents, by=args.by)

    # 4) cross-check the top agents against /reputation
    include_crosscheck = args.reputation_check and bool(ranked)
    if include_crosscheck:
        crosscheck_top_agents(
            client, ranked, top=args.top, verbose=not args.json
        )

    top_ranked = ranked[: args.top] if args.top and args.top > 0 else ranked

    # 5) output
    if args.json:
        payload = {
            "base_url": client.base_url,
            "by": args.by,
            "agent_count": len(agents),
            "mission_count": len(missions),
            "stats": stats_summary,
            "leaderboard": [
                st.to_dict(include_crosscheck=include_crosscheck)
                for st in top_ranked
            ],
        }
        json.dump(payload, sys.stdout, indent=2, sort_keys=False)
        sys.stdout.write("\n")
        return 0

    # human-readable
    print("== OABP / AIGEN marketplace ==")
    print("  base-url: %s" % client.base_url)
    if stats_summary:
        print("  " + format_stats_line(stats_summary))
    else:
        print("  (marketplace stats unavailable)")
    print()
    print("== leaderboard (top %d of %d agents) ==" % (len(top_ranked), len(agents)))
    if not top_ranked:
        print("  (no agents found — the marketplace has no missions yet)")
        return 0
    print(render_table(top_ranked, by=args.by, include_crosscheck=include_crosscheck))
    return 0


# --------------------------------------------------------------------------- #
# Offline self-test (no network)
# --------------------------------------------------------------------------- #


def _fixture_missions() -> List[Dict[str, Any]]:
    """A small, fully-resolved mission set used by the self-test.

    Designed so that the expected ranking is unambiguous:

    * ``did:agent:alice`` wins 2 AIGEN missions for 199 + 994.025 = 1193.025
      AIGEN  -> #1 by aigen AND #1 by wins (2 wins).
    * ``did:agent:bob``   wins 1 AIGEN mission for 497.5 AIGEN -> #2.
    * ``did:agent:carol`` wins 1 USDC mission (not counted in AIGEN) -> 0 AIGEN.
    * ``did:agent:dave``  only submits / creates, never wins -> 0 AIGEN, 0 wins.
    """
    return [
        {
            "id": "mis_001",
            "title": "GoPlus safety review of 0xABC",
            "creator_agent_id": "did:agent:dave",
            "reward": {"amount": 200, "currency": "AIGEN"},
            "verification_type": "oracle",
            "status": "resolved",
            "submissions": [
                {"submitter_agent_id": "did:agent:alice", "proof": "safe"},
                {"submitter_agent_id": "did:agent:bob", "proof": "safe"},
            ],
            "resolution": {
                "winner_agent_id": "did:agent:alice",
                "reward_paid": 199.0,  # 200 net of 0.5% fee
                "verified": True,
            },
        },
        {
            "id": "mis_002",
            "title": "Deliver a Go repo implementing X",
            "creator_agent_id": "did:agent:bob",
            "reward": {"amount": 999, "currency": "AIGEN"},
            "verification_type": "oracle",
            "status": "resolved",
            "submissions": [
                {"submitter_agent_id": "did:agent:alice", "proof": "github.com/a/x"},
            ],
            "resolution": {
                "winner_agent_id": "did:agent:alice",
                "reward_paid": 994.025,  # 999 net of 0.5% fee
            },
        },
        {
            "id": "mis_003",
            "title": "first_valid_match token",
            "creator_agent_id": "did:agent:alice",
            "reward": {"amount": 500, "currency": "AIGEN"},
            "verification_type": "first_valid_match",
            "status": "resolved",
            "submissions": [
                {"submitter_agent_id": "did:agent:bob", "proof": "TOKEN"},
                {"submitter_agent_id": "did:agent:dave", "proof": "nope"},
            ],
            "resolution": {
                "winner_agent_id": "did:agent:bob",
                "reward_paid": 497.5,  # 500 net of 0.5% fee
            },
        },
        {
            "id": "mis_004",
            "title": "USDC bounty (real money, excluded from AIGEN total)",
            "creator_agent_id": "did:agent:bob",
            "reward": {"amount": 50, "currency": "USDC"},
            "verification_type": "oracle",
            "status": "resolved",
            "submissions": [
                {"submitter_agent_id": "did:agent:carol", "proof": "done"},
            ],
            "resolution": {
                "winner_agent_id": "did:agent:carol",
                "reward_paid": 49.75,
            },
        },
        {
            "id": "mis_005",
            "title": "still open, nobody has won",
            "creator_agent_id": "did:agent:alice",
            "reward": {"amount": 10, "currency": "AIGEN"},
            "verification_type": "peer_vote",
            "status": "open",
            "submissions": [
                {"submitter_agent_id": "did:agent:dave", "proof": "wip"},
            ],
        },
    ]


def _self_test() -> None:
    """Inline assertions covering the tally, ranking, JSON and stats parsing."""
    missions = _fixture_missions()
    agents = build_leaderboard(missions)

    # ---- per-agent tallies ----
    alice = agents["did:agent:alice"]
    assert alice.missions_won == 2, alice.missions_won
    assert abs(alice.aigen - (199.0 + 994.025)) < 1e-9, alice.aigen
    # alice created mis_003 + mis_005
    assert alice.missions_created == 2, alice.missions_created
    # alice submitted to mis_001 + mis_002
    assert alice.submissions == 2, alice.submissions

    bob = agents["did:agent:bob"]
    assert bob.missions_won == 1, bob.missions_won
    assert abs(bob.aigen - 497.5) < 1e-9, bob.aigen
    # bob created mis_002 + mis_004
    assert bob.missions_created == 2, bob.missions_created
    # bob submitted to mis_001 + mis_003
    assert bob.submissions == 2, bob.submissions

    carol = agents["did:agent:carol"]
    # carol won a USDC mission -> counts as a win, but 0 AIGEN
    assert carol.missions_won == 1, carol.missions_won
    assert carol.aigen == 0.0, carol.aigen
    assert abs(carol.usdc_won - 49.75) < 1e-9, carol.usdc_won

    dave = agents["did:agent:dave"]
    assert dave.missions_won == 0, dave.missions_won
    assert dave.aigen == 0.0, dave.aigen
    assert dave.missions_created == 1, dave.missions_created  # mis_001
    # dave submitted to mis_003 + mis_005
    assert dave.submissions == 2, dave.submissions

    # ---- ranking by AIGEN: alice first, bob second ----
    by_aigen = rank_agents(agents, by="aigen")
    assert by_aigen[0].agent_id == "did:agent:alice", by_aigen[0].agent_id
    assert by_aigen[1].agent_id == "did:agent:bob", by_aigen[1].agent_id

    # ---- ranking by wins: alice (2) first, then a 1-win agent ----
    by_won = rank_agents(agents, by="won")
    assert by_won[0].agent_id == "did:agent:alice", by_won[0].agent_id
    assert by_won[0].missions_won == 2
    assert by_won[1].missions_won == 1

    # ---- ranking by created: alice & bob tie at 2; tie-break by AIGEN -> alice ----
    by_created = rank_agents(agents, by="created")
    assert by_created[0].missions_created == 2
    assert by_created[0].agent_id == "did:agent:alice", by_created[0].agent_id

    # ---- JSON shape: each entry has won/created/submissions/aigen ----
    payload_entry = alice.to_dict()
    for field in ("agent_id", "won", "created", "submissions", "aigen"):
        assert field in payload_entry, field
    blob = json.dumps([st.to_dict() for st in by_aigen])
    parsed = json.loads(blob)  # must be valid JSON
    assert parsed[0]["agent_id"] == "did:agent:alice"
    assert parsed[0]["won"] == 2
    assert abs(parsed[0]["aigen"] - 1193.025) < 1e-6

    # ---- stats parsing reads the REAL field names ----
    raw_stats = {
        "resolved": 4,
        "open": 1,
        "voided": 0,
        "lifetime_reward_aigen_paid_to_winners_net": 1690.525,
        "lifetime_spam_fees_burned": 8.5,
    }
    summary = summarize_stats(raw_stats)
    assert summary["resolved"] == 4
    assert summary["open"] == 1
    assert summary["voided"] == 0
    assert abs(summary["lifetime_reward_aigen_paid_to_winners_net"] - 1690.525) < 1e-9
    assert abs(summary["lifetime_spam_fees_burned"] - 8.5) < 1e-9
    line = format_stats_line(summary)
    assert "resolved=4" in line and "voided=0" in line
    # format_stats_line renders floats with %g (6 significant figures).
    assert "AIGEN paid to winners (net)=%g" % 1690.525 in line, line
    assert "spam fees burned=8.5" in line, line

    # ---- envelope extraction: bare list, {missions:[...]}, paging hints ----
    rows, hm, no = _extract_missions_envelope(missions)
    assert len(rows) == 5 and hm is None and no is None
    rows2, hm2, no2 = _extract_missions_envelope(
        {"count": 2, "missions": missions[:2], "has_more": True, "next_offset": 2}
    )
    assert len(rows2) == 2 and hm2 is True and no2 == 2

    # ---- summary-detection: resolved-without-resolution needs a detail fetch ----
    assert is_summary_row({"id": "x", "status": "resolved"}) is True
    assert is_summary_row(missions[0]) is False  # already has a usable resolution
    assert is_summary_row(missions[4]) is False  # open, no resolution -> nothing to fetch

    # ---- offline pagination walk via a fake client (no network) ----
    walked = _FakePagedClient(missions, page_size=2).iter_all_missions(page_size=2)
    assert len(walked) == 5, len(walked)
    ids = {_mission_id(m) for m in walked}
    assert ids == {"mis_001", "mis_002", "mis_003", "mis_004", "mis_005"}, ids


class _FakePagedClient(OABPClient):
    """An OABPClient subclass that paginates an in-memory list (for tests).

    Overrides only the single page fetch so the real ``iter_all_missions`` walk
    logic (termination, dedupe, offset stepping) is exercised without a network.
    """

    def __init__(self, missions: Sequence[Mapping[str, Any]], page_size: int = 2) -> None:
        # Deliberately do not call super().__init__ (no requests.Session needed).
        self.base_url = "https://example.invalid"
        self.timeout = 1.0
        self._missions = [dict(m) for m in missions]
        self._page_size = page_size

    def _missions_page(self, *, limit, offset):  # type: ignore[override]
        window = self._missions[offset : offset + limit]
        has_more = offset + limit < len(self._missions)
        next_offset = offset + limit if has_more else None
        return window, has_more, next_offset


# Run the self-test at import time so the file can never ship with a broken
# tally. It is cheap and pure. Disable by setting the env var below.
import os as _os  # noqa: E402

if _os.environ.get("LEADERBOARD_SKIP_SELFTEST") != "1":
    _self_test()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leaderboard_tracker",
        description=(
            "Reconstruct a per-agent leaderboard for the OABP / AIGEN "
            "marketplace from public mission data, cross-check the top agents "
            "against /reputation, and print marketplace stats. Read-only."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "AIGEN is the protocol's uncapped reputation/points token (net of "
            "the 0.5%% fee), not money: ~98%% of historical AIGEN flow is "
            "internal-circular, so this board ranks reputation/activity, not "
            "wealth. USDC wins (real money) are tracked separately."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="OABP API base URL.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Show (and cross-check) the top N agents. Use 0 for all.",
    )
    parser.add_argument(
        "--by",
        choices=sorted(SORT_KEYS.keys()),
        default="aigen",
        help="Rank agents by total AIGEN won, missions won, or missions created.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON (per-agent won/created/submissions/aigen).",
    )
    rep = parser.add_mutually_exclusive_group()
    rep.add_argument(
        "--reputation-check",
        dest="reputation_check",
        action="store_true",
        help="Cross-check the top N agents against /api/agents/{id}/reputation (default).",
    )
    rep.add_argument(
        "--no-reputation-check",
        dest="reputation_check",
        action="store_false",
        help="Skip the per-agent reputation cross-check (fewer requests).",
    )
    parser.set_defaults(reputation_check=True)
    parser.add_argument(
        "--no-detail",
        action="store_true",
        help=(
            "Do NOT resolve summary rows via /api/missions/{id}; tally only from "
            "the list payload (faster, but misses winners on deployments whose "
            "list endpoint omits resolution data)."
        ),
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=PAGE_SIZE,
        help="Page size requested from /api/missions when the server paginates.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the offline self-test (no network) and exit.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.self_test:
        try:
            _self_test()
        except AssertionError as exc:  # pragma: no cover
            sys.stderr.write("SELF-TEST FAILED: %s\n" % (exc,))
            return 4
        print("leaderboard tracker self-test: OK")
        return 0

    if args.page_size <= 0:
        sys.stderr.write("ERROR: --page-size must be a positive integer.\n")
        return 3

    client = OABPClient(args.base_url)
    try:
        return run(client, args)
    except APIError as exc:
        sys.stderr.write("API error: %s\n" % exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
