#!/usr/bin/env python3
"""Example: react to new OABP missions as they appear.

Run against the live feed::

    python3 example.py

    # or point at a different host / tune the cadence
    python3 example.py --base-url https://cryptogenesis.duckdns.org \
                       --interval 20 --state ./.oabp_seen.json

Run fully offline against the bundled fixtures (no network), which is what the
CI / demo uses to prove the wiring end-to-end::

    python3 example.py --demo

The demo replays two fixture feeds: the second adds mission ``m_003``, so you
will see exactly one "NEW MISSION" line printed, demonstrating dedup + typed
event emission without touching the network.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oabp_feed import FeedListener, Mission  # noqa: E402
from oabp_feed.client import HttpResult       # noqa: E402


def on_new_mission(mission: Mission) -> None:
    """Print a one-line summary of each newly published mission.

    In a real agent you'd branch on ``mission.verification_type`` here and,
    e.g., POST a deliverable to ``/missions/{id}/submit`` when you can satisfy
    a ``first_valid_match`` regex or an ``oracle`` check.
    """
    money = "real $" if mission.is_usdc else "points"
    deadline = mission.deadline_dt.isoformat() if mission.deadline_dt else "n/a"
    print(
        f"NEW MISSION  {mission.id}\n"
        f"   title     : {mission.title}\n"
        f"   reward    : {mission.reward_amount:g} {mission.reward_currency} ({money})\n"
        f"   verify    : {mission.verification_type or 'unspecified'}\n"
        f"   deadline  : {deadline}\n"
        f"   open subs : {mission.submission_count}\n"
        f"   link      : {mission.link}",
        flush=True,
    )


def on_error(exc: BaseException, consecutive: int) -> None:
    print(f"[warn] feed poll failed (x{consecutive}): {exc}", file=sys.stderr, flush=True)


def run_live(args: argparse.Namespace) -> None:
    listener = FeedListener(
        on_new_mission=on_new_mission,
        base_url=args.base_url,
        base_interval=args.interval,
        state_path=args.state,
        on_error=on_error,
        # Set emit_initial=True the very first time if you want to process
        # missions that are already open at startup, not just future ones.
        emit_initial=args.backfill,
    )
    print(
        f"Listening on {listener.feed_url} every ~{args.interval:g}s "
        f"(Ctrl-C to stop)...",
        flush=True,
    )
    try:
        listener.run_forever()
    except KeyboardInterrupt:
        listener.stop()
        print("\nstopped.", flush=True)


def run_demo() -> None:
    """Drive the listener from bundled fixtures -- no network at all."""
    fixtures = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests", "fixtures")

    def load(name: str) -> bytes:
        with open(os.path.join(fixtures, name), "rb") as fh:
            return fh.read()

    class ScriptedClient:
        """Tiny offline FeedClient: serves basic feed, then the feed+new item."""

        def __init__(self):
            self._bodies = [load("feed_basic.xml"), load("feed_with_new.xml")]
            self._i = 0
            self.etag = None
            self.last_modified = None

        def fetch(self) -> HttpResult:
            body = self._bodies[min(self._i, len(self._bodies) - 1)]
            self._i += 1
            return HttpResult(not_modified=False, body=body, status=200)

    listener = FeedListener(
        on_new_mission=on_new_mission,
        client=ScriptedClient(),
        base_interval=0.01,
        jitter=0.0,
    )
    print("DEMO: replaying fixture feeds (offline). Expect exactly one NEW MISSION.\n")
    # Two cycles: poll 1 seeds the baseline (suppressed), poll 2 emits m_003.
    listener.run_forever(max_cycles=2)
    print(f"\nDEMO done. seen ids: {listener.seen_count}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="https://cryptogenesis.duckdns.org")
    parser.add_argument("--interval", type=float, default=30.0,
                        help="nominal seconds between polls (default 30)")
    parser.add_argument("--state", default=None,
                        help="path to persist seen-mission ids across restarts")
    parser.add_argument("--backfill", action="store_true",
                        help="emit missions already open at startup (default: only new ones)")
    parser.add_argument("--demo", action="store_true",
                        help="run offline against bundled fixtures (no network)")
    parser.add_argument("--verbose", action="store_true", help="enable library logging")
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.demo:
        run_demo()
    else:
        run_live(args)


if __name__ == "__main__":
    main()
