"""The polling feed listener.

:class:`FeedListener` ties the pieces together:

* fetch the feed (conditional GET via :class:`oabp_feed.client.FeedClient`),
* parse it into :class:`~oabp_feed.model.Mission` objects,
* deduplicate against missions already seen (optionally persisted to disk), and
* invoke ``on_new_mission`` once per genuinely new mission.

Polling cadence is adaptive:

* **Error backoff** -- on a fetch/parse failure the wait grows exponentially
  (``base_interval * factor**n``, capped at ``max_interval``) with jitter,
  and ``on_error`` is called. A success resets it.
* **Idle backoff** -- if a poll yields no new missions, the wait grows (up to
  ``max_idle_interval``) so a quiet feed is polled gently. Any new mission
  snaps the cadence straight back to ``base_interval``.

The class exposes :meth:`poll_once` (a single, side-effecting poll returning the
new missions) so it can be driven deterministically from tests, and
:meth:`run_forever` for production use.
"""

from __future__ import annotations

import json
import logging
import os
import random
import tempfile
import threading
import time
from collections import OrderedDict
from typing import Callable, Iterable, List, Optional, Sequence

from .client import FeedClient, FeedHttpError, HttpResult
from .model import Mission
from .parser import parse_feed, FeedParseError

logger = logging.getLogger("oabp_feed")

OnMission = Callable[[Mission], None]
OnError = Callable[[BaseException, int], None]

DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"
DEFAULT_FEED_PATH = "/api/missions/feed.xml"


class FeedListener:
    """Subscribe to the OABP missions feed and emit typed new-mission events.

    :param on_new_mission: callback invoked once per new mission. Required.
    :param base_url:       protocol base URL (default the public OABP host).
    :param feed_url:       full feed URL; overrides ``base_url`` + feed path.
    :param base_interval:  nominal seconds between polls (default 30).
    :param max_interval:   ceiling for *error* backoff (default 600).
    :param max_idle_interval: ceiling for *idle* backoff (default 300).
    :param backoff_factor: multiplier per consecutive failure (default 2.0).
    :param state_path:     optional file to persist seen-mission ids across
                           restarts (atomic write). ``None`` => in-memory only.
    :param max_seen:       cap on remembered ids (LRU eviction) to bound memory.
    :param client:         inject a custom fetcher (e.g. for tests).
    :param on_error:       optional ``(exc, consecutive_failures)`` callback.
    :param emit_initial:   if False (default), missions present on the very
                           first poll are treated as already-seen and do NOT
                           fire the callback -- only missions appearing *after*
                           startup do. Set True to backfill on first run.
    """

    def __init__(
        self,
        on_new_mission: OnMission,
        *,
        base_url: str = DEFAULT_BASE_URL,
        feed_url: Optional[str] = None,
        base_interval: float = 30.0,
        max_interval: float = 600.0,
        max_idle_interval: float = 300.0,
        backoff_factor: float = 2.0,
        jitter: float = 0.1,
        state_path: Optional[str] = None,
        max_seen: int = 10000,
        client: Optional[FeedClient] = None,
        on_error: Optional[OnError] = None,
        emit_initial: bool = False,
    ):
        if on_new_mission is None or not callable(on_new_mission):
            raise TypeError("on_new_mission must be callable")
        if base_interval <= 0:
            raise ValueError("base_interval must be > 0")

        self.on_new_mission = on_new_mission
        self.on_error = on_error
        self.base_interval = float(base_interval)
        self.max_interval = float(max_interval)
        self.max_idle_interval = float(max_idle_interval)
        self.backoff_factor = float(backoff_factor)
        self.jitter = float(jitter)
        self.max_seen = int(max_seen)
        self.emit_initial = bool(emit_initial)

        url = feed_url or (base_url.rstrip("/") + DEFAULT_FEED_PATH)
        self.client = client if client is not None else FeedClient(url)
        self.feed_url = url

        self._state_path = state_path
        # OrderedDict used as an insertion-ordered LRU set of seen ids.
        self._seen: "OrderedDict[str, None]" = OrderedDict()
        self._first_poll = True

        # backoff state
        self._failures = 0
        self._idle_steps = 0

        # control
        self._stop = threading.Event()

        if state_path:
            self._load_state()

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #

    @property
    def seen_count(self) -> int:
        """How many mission ids are currently remembered."""
        return len(self._seen)

    def have_seen(self, mission_id: str) -> bool:
        """True if ``mission_id`` has already been emitted/recorded."""
        return mission_id in self._seen

    def poll_once(self) -> List[Mission]:
        """Run exactly one poll cycle.

        Fetches + parses the feed, emits ``on_new_mission`` for each new
        mission, updates dedup state, and adjusts internal backoff counters.
        Returns the list of new missions emitted this cycle.

        Never raises for *expected* feed problems (HTTP/parse errors): those
        increment the failure counter and (if provided) call ``on_error``.
        Exceptions raised *inside a user callback* propagate to the caller of
        ``poll_once`` but do not corrupt dedup state.
        """
        try:
            result = self.client.fetch()
        except FeedHttpError as exc:
            self._register_failure(exc)
            return []

        if result.not_modified:
            # Nothing changed on the server: a clean, cheap idle cycle.
            self._failures = 0
            self._note_idle(found_new=False)
            return []

        try:
            missions = parse_feed(result.body or b"")
        except FeedParseError as exc:
            self._register_failure(exc)
            return []

        self._failures = 0  # successful fetch+parse
        new_missions = self._select_new(missions)

        # On the very first poll we (by default) seed dedup state without
        # firing callbacks, so a restart doesn't re-announce the whole feed.
        suppress = self._first_poll and not self.emit_initial
        self._first_poll = False

        emitted: List[Mission] = []
        for mission in new_missions:
            self._record_seen(mission.id)
            if suppress:
                continue
            self.on_new_mission(mission)
            emitted.append(mission)

        if self._state_path and new_missions:
            self._save_state()

        self._note_idle(found_new=bool(emitted))
        return emitted

    def run_forever(self, *, max_cycles: Optional[int] = None) -> None:
        """Block, polling with adaptive backoff until :meth:`stop` is called.

        :param max_cycles: if set, return after this many poll cycles (handy
                           for tests / bounded runs). ``None`` => run until
                           stopped.
        """
        self._stop.clear()
        cycles = 0
        logger.info("FeedListener polling %s (base %.0fs)", self.feed_url, self.base_interval)
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:  # a user callback blew up; log & keep going
                logger.exception("unhandled error in poll cycle")
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                return
            wait = self.next_interval()
            # Interruptible sleep so stop() returns promptly.
            self._stop.wait(timeout=wait)

    def run_in_thread(self, **kwargs) -> threading.Thread:
        """Start :meth:`run_forever` on a daemon thread and return it."""
        t = threading.Thread(
            target=self.run_forever, kwargs=kwargs, name="oabp-feed-listener", daemon=True
        )
        t.start()
        return t

    def stop(self) -> None:
        """Signal :meth:`run_forever` to exit after the current sleep/poll."""
        self._stop.set()

    def next_interval(self) -> float:
        """Compute the wait (seconds) before the next poll, given current state.

        Error backoff dominates when failures are present; otherwise idle
        backoff applies. Both add +/- ``jitter`` proportional noise so many
        listeners don't stampede the server in lockstep.
        """
        if self._failures > 0:
            raw = self.base_interval * (self.backoff_factor ** self._failures)
            base = min(raw, self.max_interval)
        elif self._idle_steps > 0:
            raw = self.base_interval * (self.backoff_factor ** self._idle_steps)
            base = min(raw, self.max_idle_interval)
        else:
            base = self.base_interval
        return self._apply_jitter(base)

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #

    def _select_new(self, missions: Sequence[Mission]) -> List[Mission]:
        """Filter to missions not yet seen, de-duplicating within the batch too.

        Returned in chronological order (oldest first) so callbacks observe
        missions in the order they were created, even though the feed lists
        newest first.
        """
        fresh: List[Mission] = []
        batch_ids = set()
        for m in missions:
            if not m.id:
                continue
            if m.id in self._seen or m.id in batch_ids:
                continue
            batch_ids.add(m.id)
            fresh.append(m)
        fresh.reverse()  # feed is newest-first; emit oldest-first
        return fresh

    def _record_seen(self, mission_id: str) -> None:
        if mission_id in self._seen:
            self._seen.move_to_end(mission_id)
            return
        self._seen[mission_id] = None
        # LRU eviction to bound memory / state-file size.
        while len(self._seen) > self.max_seen:
            self._seen.popitem(last=False)

    def _register_failure(self, exc: BaseException) -> None:
        self._failures += 1
        logger.warning(
            "feed poll failure #%d: %s", self._failures, exc
        )
        if self.on_error is not None:
            try:
                self.on_error(exc, self._failures)
            except Exception:  # never let the error handler break the loop
                logger.exception("on_error callback raised")

    def _note_idle(self, found_new: bool) -> None:
        if found_new:
            self._idle_steps = 0
        else:
            # Cap the exponent so base * factor**n doesn't overflow uselessly.
            if self.base_interval * (self.backoff_factor ** (self._idle_steps + 1)) <= self.max_idle_interval:
                self._idle_steps += 1

    def _apply_jitter(self, base: float) -> float:
        if self.jitter <= 0:
            return base
        delta = base * self.jitter
        return max(0.0, base + random.uniform(-delta, delta))

    # ----- persistence -------------------------------------------------- #

    def _load_state(self) -> None:
        try:
            with open(self._state_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("could not load state %s: %s", self._state_path, exc)
            return
        seen = data.get("seen") if isinstance(data, dict) else None
        if isinstance(seen, list):
            for mid in seen[-self.max_seen:]:
                self._seen[str(mid)] = None
            # If we loaded prior state, this is not a fresh first poll: existing
            # missions should be treated as already-known.
            self._first_poll = False
        etag = data.get("etag") if isinstance(data, dict) else None
        last_mod = data.get("last_modified") if isinstance(data, dict) else None
        if etag:
            self.client.etag = etag
        if last_mod:
            self.client.last_modified = last_mod
        logger.info("loaded %d seen ids from %s", len(self._seen), self._state_path)

    def _save_state(self) -> None:
        payload = {
            "seen": list(self._seen.keys()),
            "etag": self.client.etag,
            "last_modified": self.client.last_modified,
            "saved_at": time.time(),
        }
        try:
            self._atomic_write_json(self._state_path, payload)
        except OSError as exc:  # pragma: no cover - fs dependent
            logger.warning("could not save state %s: %s", self._state_path, exc)

    @staticmethod
    def _atomic_write_json(path: str, payload: dict) -> None:
        directory = os.path.dirname(os.path.abspath(path)) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".oabp_state_", dir=directory)
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
