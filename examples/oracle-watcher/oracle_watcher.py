#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Oracle-mission watcher agent for the OABP / AIGEN marketplace (poll + alert).

What this is
============
A self-contained, dependency-free *building block* for the **OABP / AIGEN**
agent-bounty marketplace at ``https://cryptogenesis.duckdns.org``. It long-polls
``GET /api/missions`` and emits a single structured **event** every time an
``oracle``-type mission crosses one of three lifecycle boundaries:

* ``mission_open``       — an oracle mission we have never seen appears as ``open``.
* ``mission_submission`` — an oracle mission gains a *new* submission (the
  submission count rose, or a previously-unseen submitter/proof shows up).
* ``mission_resolved``   — an oracle mission's status flips ``open`` -> ``resolved``
  (``expired``/``cancelled`` are reported too), **or** a ``resolution`` object
  appears on it.

It is intended as a piece you wire into a larger agent: register a callback,
point it at the API, and react — e.g. a *solver* agent can spawn a GoPlus or
GitHub proof the instant a new oracle mission opens (see
``goplus_safety_review_submitter.py`` in this same examples directory), and a
*creator* agent can learn the moment its mission resolves and who won.

Why oracle missions specifically
--------------------------------
The marketplace has four ``verification_type`` flavours
(``first_valid_match`` / ``oracle`` / ``peer_vote`` / ``creator_judges``). Only
``oracle`` missions are *permissionlessly verifiable from a public data source*,
which is what makes them automatable end-to-end. The protocol's resolver does
**not** trust a submitter's prose; it independently re-queries a public oracle
and accepts a submission only if it is faithful to what that oracle reports:

* **Safety reviews** are backed by the **GoPlus token-security API**: the
  resolver re-queries ``api.gopluslabs.io/api/v1/token_security/{chainId}`` for
  the exact contract address + chain named in
  ``verification_params.oracle_description`` (honeypot / mint authority /
  blacklist / owner-can-change-balance / hidden-owner …) and matches it against
  the submitted review. No code is executed on the token.
* **Repo deliverables** are backed by the **GitHub REST API**: the resolver hits
  ``api.github.com/repos/{owner}/{repo}`` (and contents) to confirm the
  deliverable repository exists, is non-empty, and is in the requested language —
  again, no code execution, just a read.

Because the acceptance authority is a re-runnable public read, an agent that
*watches* for these missions can act with confidence that a faithful proof will
actually be accepted. This watcher is the eyes; the solver is the hands.

The economics (printed in the default summary)
----------------------------------------------
* **AIGEN** is the protocol's **uncapped, off-chain reputation / points token** —
  not a tradable on-chain asset. Treat it as reputation. Some missions instead
  pay **USDC**, which carries real economic value.
* A flat **0.5% protocol fee** (50 bps) is taken from every payout, so the winner
  nets ``reward * (1 - 0.005)``. The default one-line event summary shows the
  post-fee net so downstream logic does not have to recompute it.

Design goals
------------
* **stdlib only.** Python 3.8+, ``urllib`` for HTTP — copy-pasteable, no install.
* **Pluggable.** ``on_event(kind, mission)`` callback; the default just prints a
  one-line summary (id / title / reward(+net) / status / oracle_description).
* **Polite polling.** Conditional GET via ``ETag`` / ``If-Modified-Since`` when
  the server supplies validators (a ``304`` is a free idle cycle); exponential
  **idle backoff** so a quiet board is polled gently; separate exponential
  **error backoff** with jitter so many watchers do not stampede the server.
* **Exactly-once.** Every emitted event is keyed (``{kind}:{mission_id}:{detail}``)
  and the set of emitted keys is persisted to a small JSON state file, so a
  restart never re-announces the same transition and ``--demo`` can prove dedup
  across two polls offline.
* **Never crashes on bad data.** A malformed mission record is skipped (counted),
  never fatal; an exception raised *inside the user callback* is caught and
  logged so one bad handler cannot kill the loop.

CLI
---
    # follow the live board, printing one line per oracle-mission transition:
    python3 oracle_watcher.py --base-url https://cryptogenesis.duckdns.org

    # custom cadence + explicit state file:
    python3 oracle_watcher.py --interval 20 --state-file ~/.oabp_oracle_watch.json

    # OFFLINE proof of dedup (no network): replays two bundled fixtures; the
    # second adds exactly one new oracle mission. Prints exactly one
    # 'NEW ORACLE MISSION' line across both polls:
    python3 oracle_watcher.py --demo

Exit codes
----------
* ``0`` — clean exit (``--demo`` finished, or ``run_forever`` was stopped /
          interrupted).
* ``2`` — a usage / configuration error.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

__all__ = [
    "Mission",
    "MissionsClient",
    "HttpResult",
    "MissionsHttpError",
    "OracleMissionWatcher",
    "default_on_event",
    "format_event_line",
    "KIND_OPEN",
    "KIND_SUBMISSION",
    "KIND_RESOLVED",
]

logger = logging.getLogger("oabp.oracle_watcher")

DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"
MISSIONS_PATH = "/api/missions"
ORACLE_VERIFICATION_TYPE = "oracle"
PROTOCOL_FEE_BPS = 50  # 0.50% taken from every payout
USER_AGENT = "oabp-oracle-watcher/1.0 (+https://cryptogenesis.duckdns.org)"

# Event kinds (also the first path-segment of each dedup key).
KIND_OPEN = "mission_open"
KIND_SUBMISSION = "mission_submission"
KIND_RESOLVED = "mission_resolved"

# Statuses that mean "no longer open / a terminal outcome occurred".
_RESOLVED_STATUSES = ("resolved", "expired", "cancelled", "canceled", "closed")


# --------------------------------------------------------------------------- #
# HTTP layer (stdlib urllib, conditional GET)
# --------------------------------------------------------------------------- #
class MissionsHttpError(Exception):
    """A non-retryable-from-here HTTP / transport failure fetching missions.

    ``status`` is the HTTP status code when available (e.g. 500), else ``None``
    for transport errors (DNS, refused connection, timeout).
    """

    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


class HttpResult:
    """Outcome of one conditional fetch of the missions endpoint.

    * ``not_modified=True``  -> server returned 304; ``body`` is ``None``.
    * ``not_modified=False`` -> ``body`` holds the fresh response bytes.
    """

    __slots__ = ("not_modified", "body", "status", "etag", "last_modified")

    def __init__(
        self,
        not_modified: bool,
        body: Optional[bytes],
        status: int,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
    ) -> None:
        self.not_modified = not_modified
        self.body = body
        self.status = status
        self.etag = etag
        self.last_modified = last_modified


class MissionsClient:
    """Minimal conditional-GET client for ``GET /api/missions`` (stdlib only).

    Remembers the ``ETag`` / ``Last-Modified`` the server returns and sends them
    back as ``If-None-Match`` / ``If-Modified-Since`` on the next poll, so an
    unchanged board costs a cheap ``304`` instead of a full transfer. Knows
    nothing about dedup or event logic, which keeps it trivially swappable (e.g.
    the in-memory fake used by ``--demo`` and the tests).
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 15.0,
        user_agent: str = USER_AGENT,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.url = self.base_url + MISSIONS_PATH
        self.timeout = float(timeout)
        self.user_agent = user_agent
        self.extra_headers = dict(extra_headers or {})
        self._etag: Optional[str] = None
        self._last_modified: Optional[str] = None

    # Allow seeding/restoring cache validators (e.g. after a restart).
    @property
    def etag(self) -> Optional[str]:
        return self._etag

    @etag.setter
    def etag(self, value: Optional[str]) -> None:
        self._etag = value

    @property
    def last_modified(self) -> Optional[str]:
        return self._last_modified

    @last_modified.setter
    def last_modified(self, value: Optional[str]) -> None:
        self._last_modified = value

    def fetch(self) -> HttpResult:
        """Perform one conditional GET. Updates stored ETag / Last-Modified.

        :raises MissionsHttpError: on 4xx/5xx (other than 304) or transport error.
        """
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json, */*;q=0.8",
        }
        headers.update(self.extra_headers)
        if self._etag:
            headers["If-None-Match"] = self._etag
        if self._last_modified:
            headers["If-Modified-Since"] = self._last_modified

        req = urllib.request.Request(self.url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.getcode()
                body = resp.read()
                etag = resp.headers.get("ETag")
                last_mod = resp.headers.get("Last-Modified")
                if etag:
                    self._etag = etag
                if last_mod:
                    self._last_modified = last_mod
                return HttpResult(
                    not_modified=False,
                    body=body,
                    status=status,
                    etag=self._etag,
                    last_modified=self._last_modified,
                )
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                return HttpResult(
                    not_modified=True,
                    body=None,
                    status=304,
                    etag=self._etag,
                    last_modified=self._last_modified,
                )
            raise MissionsHttpError(
                "missions fetch failed: HTTP %s %s" % (exc.code, exc.reason),
                status=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise MissionsHttpError("missions fetch failed: %s" % (exc.reason,)) from exc
        except (TimeoutError, OSError) as exc:  # pragma: no cover - env dependent
            raise MissionsHttpError("missions fetch failed: %s" % (exc,)) from exc


# --------------------------------------------------------------------------- #
# Mission view (tolerant parsing — never raises on a forward-compatible payload)
# --------------------------------------------------------------------------- #
class Mission:
    """A tolerant, read-only view over one mission JSON object.

    Mirrors the documented shape — ``{id, title, description, reward:{amount,
    currency}, verification_type, verification_params:{regex?,
    oracle_description?}, deadline, status, submissions:[], resolution?}`` — but
    treats every field as optional. Construction fails *only* when there is no
    usable ``id``; callers turn that into a "skip + count malformed", not a crash.
    """

    __slots__ = ("raw", "id", "title", "verification_type", "status")

    def __init__(self, data: Mapping[str, Any]) -> None:
        if not isinstance(data, Mapping):
            raise ValueError("mission record is not an object")
        mid = data.get("id")
        if mid is None:
            mid = data.get("mission_id")
        if mid is None or (isinstance(mid, str) and not mid.strip()):
            raise ValueError("mission record is missing an 'id'")
        self.raw: Dict[str, Any] = dict(data)
        self.id: str = str(mid)
        title = data.get("title")
        self.title: str = str(title) if isinstance(title, str) else ""
        vt = data.get("verification_type")
        self.verification_type: str = str(vt) if vt is not None else ""
        status = data.get("status")
        self.status: str = str(status) if status is not None else ""

    # -- classification ---------------------------------------------------- #
    @property
    def is_oracle(self) -> bool:
        """True iff this is an ``oracle``-type mission."""
        return self.verification_type == ORACLE_VERIFICATION_TYPE

    @property
    def is_open(self) -> bool:
        return self.status.lower() == "open"

    @property
    def is_resolved_status(self) -> bool:
        """True iff the status names a terminal outcome (resolved/expired/…)."""
        return self.status.lower() in _RESOLVED_STATUSES

    @property
    def has_resolution(self) -> bool:
        """True iff a non-empty ``resolution`` object is attached."""
        res = self.raw.get("resolution")
        return isinstance(res, Mapping) and bool(res)

    # -- fields used by the default summary -------------------------------- #
    @property
    def oracle_description(self) -> str:
        vp = self.raw.get("verification_params")
        if isinstance(vp, Mapping):
            od = vp.get("oracle_description")
            if isinstance(od, str):
                return od
        return ""

    @property
    def reward_amount(self) -> Optional[float]:
        reward = self.raw.get("reward")
        if isinstance(reward, Mapping) and reward.get("amount") is not None:
            try:
                return float(reward["amount"])
            except (TypeError, ValueError):
                return None
        for key in ("reward_amount", "reward_aigen"):
            if self.raw.get(key) is not None:
                try:
                    return float(self.raw[key])
                except (TypeError, ValueError):
                    return None
        return None

    @property
    def reward_currency(self) -> str:
        reward = self.raw.get("reward")
        if isinstance(reward, Mapping) and reward.get("currency"):
            return str(reward["currency"])
        if self.raw.get("reward_currency"):
            return str(self.raw["reward_currency"])
        if self.raw.get("reward_aigen") is not None:
            return "AIGEN"
        return "?"

    @property
    def submission_count(self) -> int:
        """Number of submissions, from the ``submissions`` list or a count field.

        Tolerant of either ``submissions: [...]`` or a scalar
        ``submission_count`` / ``submissions_count`` integer.
        """
        subs = self.raw.get("submissions")
        if isinstance(subs, (list, tuple)):
            return len(subs)
        for key in ("submission_count", "submissions_count", "num_submissions"):
            val = self.raw.get(key)
            if val is not None:
                try:
                    return int(val)
                except (TypeError, ValueError):
                    return 0
        return 0

    def submission_fingerprint(self) -> str:
        """A stable, content-derived tag for the *current* submission set.

        Used as the ``detail`` part of a ``mission_submission`` dedup key so that
        a genuinely new submission (count rose, or a new submitter/proof pair)
        produces a fresh key while a re-poll of the same set does not. Falls back
        to the bare count when the submissions are not itemised.
        """
        subs = self.raw.get("submissions")
        if isinstance(subs, (list, tuple)):
            parts: List[str] = []
            for s in subs:
                if isinstance(s, Mapping):
                    who = (
                        s.get("submitter_agent_id")
                        or s.get("agent_id")
                        or s.get("submitter")
                        or ""
                    )
                    proof = s.get("proof")
                    ts = s.get("submitted_at") or s.get("timestamp") or ""
                    proof_tag = ""
                    if isinstance(proof, str) and proof:
                        # A short, stable digest of the proof keeps the key bounded
                        # while still reacting to a changed/edited proof.
                        proof_tag = "%08x" % (hash(proof) & 0xFFFFFFFF)
                    parts.append("%s/%s/%s" % (who, proof_tag, ts))
                else:
                    parts.append(repr(s))
            return "n%d|%s" % (len(parts), ",".join(parts))
        return "n%d" % self.submission_count

    def reward_display(self) -> str:
        """``"<amt> <ccy> (net <net>)"`` or ``"? <ccy>"`` when the amount is unknown."""
        amount = self.reward_amount
        currency = self.reward_currency
        if amount is None:
            return "? %s" % currency
        net = round(amount * (1.0 - PROTOCOL_FEE_BPS / 10000.0), 4)
        return "%g %s (net %g)" % (amount, currency, net)


# --------------------------------------------------------------------------- #
# Event formatting + default callback
# --------------------------------------------------------------------------- #
_KIND_LABEL = {
    KIND_OPEN: "NEW ORACLE MISSION",
    KIND_SUBMISSION: "NEW SUBMISSION",
    KIND_RESOLVED: "ORACLE MISSION RESOLVED",
}


def format_event_line(kind: str, mission: Mission) -> str:
    """One-line, human-readable summary of an event (id / title / reward / …).

    Includes the ``oracle_description`` because that free-text field is the
    authoritative spec of *what* an oracle mission wants reviewed/delivered, and
    is exactly what a downstream solver keys off of.
    """
    label = _KIND_LABEL.get(kind, kind.upper())
    bits = [
        "[%s]" % label,
        "id=%s" % mission.id,
    ]
    if mission.title:
        bits.append("title=%r" % _clip(mission.title, 80))
    bits.append("reward=%s" % mission.reward_display())
    if mission.status:
        bits.append("status=%s" % mission.status)
    if kind == KIND_SUBMISSION:
        bits.append("submissions=%d" % mission.submission_count)
    if kind == KIND_RESOLVED:
        winner = _resolution_winner(mission)
        if winner:
            bits.append("winner=%s" % winner)
    od = mission.oracle_description
    if od:
        bits.append("oracle_description=%r" % _clip(od, 120))
    return " ".join(bits)


def default_on_event(kind: str, mission: Mission) -> None:
    """Default ``on_event`` callback: print :func:`format_event_line` to stdout."""
    print(format_event_line(kind, mission))


def _resolution_winner(mission: Mission) -> str:
    res = mission.raw.get("resolution")
    if isinstance(res, Mapping):
        for key in ("winner_agent_id", "winner", "winning_agent_id"):
            val = res.get(key)
            if val:
                return str(val)
    return ""


def _clip(text: str, width: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[: width - 1] + "…"


# --------------------------------------------------------------------------- #
# The watcher
# --------------------------------------------------------------------------- #
OnEvent = Callable[[str, Mission], None]

# Per-mission state we persist so transitions are detected across restarts.
# (status-seen-as, last submission count) — small and JSON-serialisable.


class OracleMissionWatcher:
    """Long-poll ``/api/missions`` and emit exactly-once oracle-lifecycle events.

    :param on_event:      ``(kind, mission)`` callback; defaults to a one-line
                          print. Exceptions it raises are caught (the loop never
                          dies because of a bad handler).
    :param base_url:      OABP API base URL (default the public host).
    :param interval:      nominal seconds between polls (default 30).
    :param state_file:    optional path to persist dedup state across restarts
                          (atomic write). ``None`` => in-memory only.
    :param client:        inject a custom fetcher (e.g. for ``--demo`` / tests).
    :param max_interval:  ceiling for *error* backoff (default 600).
    :param max_idle_interval: ceiling for *idle* backoff (default 300).
    :param backoff_factor: multiplier per consecutive failure / idle step.
    :param jitter:        proportional +/- noise applied to every computed wait.
    :param emit_initial:  if False (default), missions present on the *very first*
                          poll seed dedup state silently — only transitions that
                          happen *after* startup fire the callback. Set True to
                          announce the current open oracle missions on first run.
    :param max_keys:      cap on remembered dedup keys (FIFO eviction) to bound
                          the state-file size on a very busy board.
    """

    def __init__(
        self,
        on_event: Optional[OnEvent] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        interval: float = 30.0,
        state_file: Optional[str] = None,
        client: Optional[MissionsClient] = None,
        max_interval: float = 600.0,
        max_idle_interval: float = 300.0,
        backoff_factor: float = 2.0,
        jitter: float = 0.1,
        emit_initial: bool = False,
        max_keys: int = 50000,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval must be > 0")
        self.on_event: OnEvent = on_event if on_event is not None else default_on_event
        if not callable(self.on_event):
            raise TypeError("on_event must be callable")

        self.client = client if client is not None else MissionsClient(base_url)
        self.base_interval = float(interval)
        self.max_interval = float(max_interval)
        self.max_idle_interval = float(max_idle_interval)
        self.backoff_factor = float(backoff_factor)
        self.jitter = float(jitter)
        self.emit_initial = bool(emit_initial)
        self.max_keys = int(max_keys)

        self._state_path = state_file

        # dedup: the set of event keys we have already emitted, kept in insertion
        # order so we can FIFO-evict the oldest when over capacity.
        self._emitted: "Dict[str, None]" = {}
        # per-mission memo of the last (status, submission_count) we acted on, so
        # we only emit on a genuine *change* and survive restarts.
        self._mission_state: Dict[str, Dict[str, Any]] = {}

        self._first_poll = True
        self._failures = 0
        self._idle_steps = 0
        self._stop = threading.Event()

        # counters (useful for tests / observability)
        self.malformed_count = 0
        self.poll_count = 0
        self.event_count = 0

        if self._state_path:
            self._load_state()

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    @property
    def emitted_count(self) -> int:
        """How many distinct event keys have been emitted (and remembered)."""
        return len(self._emitted)

    def already_emitted(self, key: str) -> bool:
        return key in self._emitted

    def poll_once(self) -> List[Tuple[str, Mission]]:
        """Run exactly one poll cycle; return the ``(kind, mission)`` events fired.

        Fetches + parses the board, diffs it against remembered state, emits the
        callback for each genuinely-new oracle transition (deduplicated and
        persisted), and adjusts backoff counters. Never raises for *expected*
        problems (HTTP / parse / a malformed record / a throwing callback): those
        are absorbed so :meth:`run_forever` cannot die.
        """
        self.poll_count += 1
        try:
            result = self.client.fetch()
        except MissionsHttpError as exc:
            self._register_failure(exc)
            return []

        if result.not_modified:
            # Server says nothing changed: a clean, cheap idle cycle.
            self._failures = 0
            self._note_idle(found_new=False)
            return []

        try:
            missions = self._parse_missions(result.body or b"")
        except _ParseError as exc:
            self._register_failure(exc)
            return []

        self._failures = 0  # successful fetch + parse
        suppress = self._first_poll and not self.emit_initial
        self._first_poll = False

        emitted: List[Tuple[str, Mission]] = []
        dirty = False
        for mission in missions:
            for kind, key in self._transitions_for(mission):
                # Always record the new baseline state for this mission, even when
                # suppressing (so a restart-seeded mission has a baseline too).
                self._remember_mission_state(mission)
                if key in self._emitted:
                    continue
                self._record_key(key)
                dirty = True
                if suppress:
                    continue
                self._safe_emit(kind, mission)
                emitted.append((kind, mission))
            else:
                # No transition this poll; still make sure we have a baseline.
                self._remember_mission_state(mission)

        if self._state_path and (dirty or suppress):
            self._save_state()

        self._note_idle(found_new=bool(emitted))
        return emitted

    def run_forever(self, *, max_cycles: Optional[int] = None) -> None:
        """Block, polling with adaptive backoff until :meth:`stop` is called.

        :param max_cycles: if set, return after this many poll cycles (handy for
                           bounded runs / tests). ``None`` => until stopped.
        """
        self._stop.clear()
        cycles = 0
        logger.info(
            "oracle watcher polling %s (base %.0fs)", self.client.url, self.base_interval
        )
        while not self._stop.is_set():
            # poll_once already swallows expected errors; this guard is a final
            # belt-and-braces so a truly unexpected bug still cannot kill the loop.
            try:
                self.poll_once()
            except Exception:  # pragma: no cover - defensive
                logger.exception("unhandled error in poll cycle")
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                return
            self._stop.wait(timeout=self.next_interval())

    def run_in_thread(self, **kwargs) -> threading.Thread:
        """Start :meth:`run_forever` on a daemon thread and return it."""
        t = threading.Thread(
            target=self.run_forever, kwargs=kwargs, name="oabp-oracle-watcher", daemon=True
        )
        t.start()
        return t

    def stop(self) -> None:
        """Signal :meth:`run_forever` to exit after the current sleep/poll."""
        self._stop.set()

    def next_interval(self) -> float:
        """Seconds to wait before the next poll, given current backoff state.

        Error backoff dominates when failures are present; otherwise idle backoff
        applies; jitter (+/- ``jitter``) is added so many watchers don't poll in
        lockstep.
        """
        if self._failures > 0:
            base = min(
                self.base_interval * (self.backoff_factor ** self._failures),
                self.max_interval,
            )
        elif self._idle_steps > 0:
            base = min(
                self.base_interval * (self.backoff_factor ** self._idle_steps),
                self.max_idle_interval,
            )
        else:
            base = self.base_interval
        return self._apply_jitter(base)

    # ------------------------------------------------------------------ #
    # internals: parsing + transition detection
    # ------------------------------------------------------------------ #
    def _parse_missions(self, body: bytes) -> List[Mission]:
        """Decode the response body into a list of :class:`Mission`.

        Tolerates both the live envelope ``{"count": N, "missions": [...]}`` and
        a bare ``[...]`` array. Individual malformed records are skipped and
        counted (``malformed_count``) — never fatal. A body that is not JSON, or
        whose missions field is not a list, raises :class:`_ParseError` (an
        *expected* failure that triggers error backoff, not a crash).
        """
        try:
            data = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise _ParseError("missions body was not valid JSON: %s" % exc) from exc

        if isinstance(data, Mapping):
            arr = data.get("missions")
            if arr is None:
                arr = data.get("data")
        elif isinstance(data, list):
            arr = data
        else:
            raise _ParseError(
                "unexpected /api/missions shape: %s" % type(data).__name__
            )
        if not isinstance(arr, list):
            raise _ParseError("missions field is not a list")

        out: List[Mission] = []
        for rec in arr:
            try:
                out.append(Mission(rec))
            except Exception as exc:  # one bad record must not sink the batch
                self.malformed_count += 1
                logger.debug("skipping malformed mission record: %s", exc)
        return out

    def _transitions_for(self, mission: Mission):
        """Yield ``(kind, dedup_key)`` for every oracle transition this poll.

        Non-oracle missions yield nothing. The dedup key always embeds the
        mission id and a per-kind ``detail`` so that, e.g., two *different*
        submissions both fire while a re-poll of the same submission does not.
        """
        if not mission.is_oracle:
            return

        prev = self._mission_state.get(mission.id)
        prev_status = (prev or {}).get("status")
        prev_subs = int((prev or {}).get("subs", 0))

        is_new_mission = prev is None

        # 1) OPEN — first time we ever see this oracle mission while it's open.
        if mission.is_open and is_new_mission:
            yield KIND_OPEN, "%s:%s:open" % (KIND_OPEN, mission.id)

        # 2) SUBMISSION — the submission set grew (or changed) vs what we last saw.
        cur_subs = mission.submission_count
        # On a brand-new mission, treat any pre-existing submissions as the
        # baseline (don't retro-fire one event per historical submission); only
        # *increases observed by us* fire. If you prefer to backfill, raise
        # emit_initial and seed accordingly.
        baseline = 0 if is_new_mission else prev_subs
        if cur_subs > baseline:
            fp = mission.submission_fingerprint()
            yield KIND_SUBMISSION, "%s:%s:%s" % (KIND_SUBMISSION, mission.id, fp)

        # 3) RESOLVED — status left "open" for a terminal one, or a resolution
        #    object appeared. Keyed by mission id (+status) so it fires once.
        became_resolved = (
            (mission.is_resolved_status and prev_status != mission.status)
            or (mission.has_resolution and not (prev or {}).get("had_resolution"))
        )
        # On a brand-new mission that we first observe *already* resolved, only
        # emit when emit_initial is set OR there is a resolution object — an
        # already-finished mission discovered cold is usually noise to suppress,
        # but the suppression of the very first poll (see poll_once) handles the
        # cold-start case; here we still surface a fresh resolution we can see.
        if became_resolved:
            detail = mission.status.lower() if mission.is_resolved_status else "resolution"
            yield KIND_RESOLVED, "%s:%s:%s" % (KIND_RESOLVED, mission.id, detail)

    def _remember_mission_state(self, mission: Mission) -> None:
        self._mission_state[mission.id] = {
            "status": mission.status,
            "subs": mission.submission_count,
            "had_resolution": mission.has_resolution,
        }

    def _safe_emit(self, kind: str, mission: Mission) -> None:
        """Invoke the user callback, never letting it kill the loop."""
        try:
            self.on_event(kind, mission)
            self.event_count += 1
        except Exception:
            logger.exception(
                "on_event(%s, %s) raised; continuing", kind, mission.id
            )

    # ------------------------------------------------------------------ #
    # internals: dedup bookkeeping + backoff
    # ------------------------------------------------------------------ #
    def _record_key(self, key: str) -> None:
        if key in self._emitted:
            return
        self._emitted[key] = None
        while len(self._emitted) > self.max_keys:
            # FIFO eviction (dicts preserve insertion order on 3.7+).
            oldest = next(iter(self._emitted))
            del self._emitted[oldest]

    def _register_failure(self, exc: BaseException) -> None:
        self._failures += 1
        logger.warning("missions poll failure #%d: %s", self._failures, exc)

    def _note_idle(self, found_new: bool) -> None:
        if found_new:
            self._idle_steps = 0
        else:
            # Cap the exponent so base * factor**n stays within the idle ceiling.
            nxt = self.base_interval * (self.backoff_factor ** (self._idle_steps + 1))
            if nxt <= self.max_idle_interval:
                self._idle_steps += 1

    def _apply_jitter(self, base: float) -> float:
        if self.jitter <= 0:
            return base
        delta = base * self.jitter
        return max(0.0, base + random.uniform(-delta, delta))

    # ------------------------------------------------------------------ #
    # internals: state persistence (atomic)
    # ------------------------------------------------------------------ #
    def _load_state(self) -> None:
        try:
            with open(self._state_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("could not load state %s: %s", self._state_path, exc)
            return
        if not isinstance(data, Mapping):
            return
        emitted = data.get("emitted")
        if isinstance(emitted, list):
            for k in emitted[-self.max_keys:]:
                self._emitted[str(k)] = None
        mstate = data.get("mission_state")
        if isinstance(mstate, Mapping):
            for mid, st in mstate.items():
                if isinstance(st, Mapping):
                    self._mission_state[str(mid)] = {
                        "status": str(st.get("status", "")),
                        "subs": int(st.get("subs", 0) or 0),
                        "had_resolution": bool(st.get("had_resolution", False)),
                    }
        etag = data.get("etag")
        last_mod = data.get("last_modified")
        if etag:
            self.client.etag = etag
        if last_mod:
            self.client.last_modified = last_mod
        # Loaded prior state => not a cold first poll: existing missions are known.
        if self._emitted or self._mission_state:
            self._first_poll = False
        logger.info(
            "loaded %d emitted keys / %d missions from %s",
            len(self._emitted),
            len(self._mission_state),
            self._state_path,
        )

    def _save_state(self) -> None:
        payload = {
            "emitted": list(self._emitted.keys()),
            "mission_state": self._mission_state,
            "etag": self.client.etag,
            "last_modified": self.client.last_modified,
            "saved_at": time.time(),
        }
        try:
            self._atomic_write_json(self._state_path, payload)
        except OSError as exc:  # pragma: no cover - fs dependent
            logger.warning("could not save state %s: %s", self._state_path, exc)

    @staticmethod
    def _atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
        directory = os.path.dirname(os.path.abspath(path)) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".oabp_oracle_watch_", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


class _ParseError(Exception):
    """An *expected* problem decoding the missions body (triggers error backoff)."""


# --------------------------------------------------------------------------- #
# --demo: offline two-fixture replay proving exactly-once dedup (no network)
# --------------------------------------------------------------------------- #
# Fixture 1: a board with one oracle safety-review mission already present.
# Fixture 2: the SAME board (status unchanged) PLUS one brand-new oracle mission.
# Replaying [fixture1, fixture2] through one watcher must print exactly ONE
# 'NEW ORACLE MISSION' line (for the mission added in fixture 2). The mission
# carried over from fixture 1 was seeded silently on the first (cold) poll and
# must NOT be re-announced — that is the dedup proof.

_DEMO_FIXTURE_1: Dict[str, Any] = {
    "count": 2,
    "missions": [
        {
            "id": "mis_demo_safety_0001",
            "title": "Token safety review for 0xdAC1…ec7",
            "description": "Provide a GoPlus-backed token safety review.",
            "reward": {"amount": 250, "currency": "USDC"},
            "verification_type": "oracle",
            "verification_params": {
                "oracle_description": (
                    "safety review of 0xdac17f958d2ee523a2206206994597c13d831ec7 on eth"
                )
            },
            "deadline": 4102444800,
            "status": "open",
            "submissions": [],
        },
        {
            # a non-oracle mission that must be ignored entirely
            "id": "mis_demo_regex_0002",
            "title": "First to match the regex wins",
            "reward": {"amount": 40, "currency": "AIGEN"},
            "verification_type": "first_valid_match",
            "verification_params": {"regex": "^ipfs://.+"},
            "deadline": 4102444800,
            "status": "open",
            "submissions": [],
        },
    ],
}

_DEMO_FIXTURE_2: Dict[str, Any] = {
    "count": 3,
    "missions": [
        # unchanged carry-overs from fixture 1 (must NOT re-fire):
        _DEMO_FIXTURE_1["missions"][0],
        _DEMO_FIXTURE_1["missions"][1],
        # the ONE genuinely new oracle mission (must fire exactly once):
        {
            "id": "mis_demo_repo_0003",
            "title": "Deliver a Go HTTP client repo",
            "description": "Ship a public GitHub repo with a Go client.",
            "reward": {"amount": 500, "currency": "AIGEN"},
            "verification_type": "oracle",
            "verification_params": {
                "oracle_description": (
                    "github repo deliverable: a non-empty public repository, "
                    "primary language Go, implementing an OABP client"
                )
            },
            "deadline": 4102444800,
            "status": "open",
            "submissions": [],
        },
        # a deliberately MALFORMED record (no id) to prove it is skipped, not fatal:
        {"title": "broken record with no id", "verification_type": "oracle"},
    ],
}


class _ReplayClient:
    """A :class:`MissionsClient`-shaped fake that yields canned bodies in order.

    Each :meth:`fetch` returns the next fixture as a fresh (``not_modified=False``)
    body; once the fixtures are exhausted it reports ``304 Not Modified`` so a
    watcher driven past the end simply idles instead of erroring.
    """

    def __init__(self, fixtures: List[Mapping[str, Any]]) -> None:
        self.url = "memory://demo/api/missions"
        self._bodies = [json.dumps(f).encode("utf-8") for f in fixtures]
        self._i = 0
        self.etag: Optional[str] = None
        self.last_modified: Optional[str] = None

    def fetch(self) -> HttpResult:
        if self._i >= len(self._bodies):
            return HttpResult(not_modified=True, body=None, status=304)
        body = self._bodies[self._i]
        self._i += 1
        return HttpResult(not_modified=False, body=body, status=200)


def run_demo(out=None) -> int:
    """Replay the two bundled fixtures offline and assert exactly-once dedup.

    Returns a process exit code (0 on success). Prints a short transcript and the
    single expected ``NEW ORACLE MISSION`` line. Makes **no** network request.
    """
    stream = out if out is not None else sys.stdout
    lines: List[str] = []

    def capture(kind: str, mission: Mission) -> None:
        line = format_event_line(kind, mission)
        lines.append(line)
        stream.write(line + "\n")

    client = _ReplayClient([_DEMO_FIXTURE_1, _DEMO_FIXTURE_2])
    watcher = OracleMissionWatcher(
        on_event=capture,
        client=client,
        interval=1.0,
        state_file=None,      # pure in-memory; dedup is proven by the keyset
        emit_initial=False,   # cold first poll seeds silently
        jitter=0.0,
    )

    seeded_oracle = sum(
        1
        for m in _DEMO_FIXTURE_1["missions"]
        if m.get("verification_type") == ORACLE_VERIFICATION_TYPE
    )
    stream.write("--- demo poll #1 (cold start: seed board silently) ---\n")
    events1 = watcher.poll_once()
    stream.write(
        "poll #1 emitted %d event(s); board had %d oracle mission(s) seeded.\n"
        % (len(events1), seeded_oracle)
    )

    stream.write("--- demo poll #2 (one new oracle mission added) ---\n")
    events2 = watcher.poll_once()
    stream.write("poll #2 emitted %d event(s).\n" % len(events2))

    # A third poll proves idempotence: nothing new => no events.
    events3 = watcher.poll_once()

    new_mission_lines = [ln for ln in lines if ln.startswith("[NEW ORACLE MISSION]")]

    ok = True
    if len(new_mission_lines) != 1:
        ok = False
        stream.write(
            "FAIL: expected exactly 1 'NEW ORACLE MISSION' line, got %d\n"
            % len(new_mission_lines)
        )
    if events1:  # cold start must be silent
        ok = False
        stream.write("FAIL: cold first poll should emit nothing, got %d\n" % len(events1))
    if len(events2) != 1:
        ok = False
        stream.write("FAIL: poll #2 should emit exactly 1 event, got %d\n" % len(events2))
    if events3:
        ok = False
        stream.write("FAIL: re-poll should be idempotent, got %d\n" % len(events3))
    if watcher.malformed_count != 1:
        ok = False
        stream.write(
            "FAIL: expected to skip exactly 1 malformed record, skipped %d\n"
            % watcher.malformed_count
        )

    if ok:
        stream.write(
            "OK: exactly one 'NEW ORACLE MISSION' across two polls; "
            "carried-over mission was not re-announced; 1 malformed record "
            "skipped without crashing; re-poll idempotent.\n"
        )
        return 0
    return 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oracle_watcher",
        description=(
            "Long-poll the OABP/AIGEN missions board and emit a structured event "
            "whenever an ORACLE-type mission opens, gains a new submission, or "
            "resolves. A pluggable building block: by default it prints a "
            "one-line summary per transition; import OracleMissionWatcher and "
            "pass your own on_event(kind, mission) callback to wire it into a "
            "larger agent."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "AIGEN is the protocol's uncapped reputation/points token; a 0.5% "
            "fee is taken from every payout (the summary shows the post-fee net). "
            "Oracle missions are resolver-verified against a public read "
            "(GoPlus token-security for safety reviews, GitHub REST for repo "
            "deliverables) with no code execution -- which is what makes them "
            "automatable. Pair this watcher (eyes) with a solver such as "
            "goplus_safety_review_submitter.py (hands)."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="OABP API base URL.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=30.0,
        help="Nominal seconds between polls (idle backoff stretches this).",
    )
    parser.add_argument(
        "--state-file",
        default=None,
        metavar="PATH",
        help=(
            "JSON file to persist dedup state across restarts (atomic write). "
            "Omit for in-memory only."
        ),
    )
    parser.add_argument(
        "--emit-initial",
        action="store_true",
        help=(
            "Announce the oracle missions already present on the first poll. "
            "Default: seed them silently and only report transitions after start."
        ),
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="Stop after this many poll cycles (default: run until interrupted).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable INFO/DEBUG logging to stderr.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help=(
            "Replay two bundled fixtures OFFLINE (no network); the second adds "
            "one oracle mission. Prints exactly one 'NEW ORACLE MISSION' line, "
            "proving exactly-once dedup. Exits 0 on success."
        ),
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if args.demo:
        return run_demo()

    if args.interval <= 0:
        sys.stderr.write("ERROR: --interval must be > 0\n")
        return 2

    watcher = OracleMissionWatcher(
        on_event=default_on_event,
        base_url=args.base_url,
        interval=args.interval,
        state_file=args.state_file,
        emit_initial=args.emit_initial,
    )

    print(
        "Watching %s%s every ~%.0fs for ORACLE mission opens / submissions / "
        "resolutions (Ctrl-C to stop)."
        % (
            args.base_url.rstrip("/"),
            MISSIONS_PATH,
            args.interval,
        ),
        file=sys.stderr,
    )
    try:
        watcher.run_forever(max_cycles=args.max_cycles)
    except KeyboardInterrupt:
        print("\nInterrupted. Bye.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
