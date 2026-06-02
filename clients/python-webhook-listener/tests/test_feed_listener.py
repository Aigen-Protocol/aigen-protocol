"""Tests for the OABP feed listener.

Runs under either ``python -m unittest`` or ``pytest`` -- no third-party deps.
A :class:`FakeClient` feeds fixture bytes (and synthetic errors) into the
listener so the polling/dedup/backoff logic is exercised deterministically
without any network access.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import unittest

# Make the package importable when run directly from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oabp_feed import (  # noqa: E402
    FeedListener,
    Mission,
    parse_feed,
    FeedParseError,
)
from oabp_feed.client import HttpResult, FeedHttpError  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load(name: str) -> bytes:
    with open(os.path.join(FIXTURES, name), "rb") as fh:
        return fh.read()


class FakeClient:
    """A FeedClient stand-in driven by a scripted list of responses.

    Each scripted entry is one of:
      * ``bytes``            -> a fresh 200 response with that body
      * ``"NOT_MODIFIED"``   -> a 304 response
      * an ``Exception``     -> raised from ``fetch()``
    The last entry repeats once the script is exhausted.
    """

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0
        self.etag = None
        self.last_modified = None

    def fetch(self) -> HttpResult:
        idx = min(self.calls, len(self.script) - 1)
        self.calls += 1
        step = self.script[idx]
        if isinstance(step, Exception):
            raise step
        if step == "NOT_MODIFIED":
            return HttpResult(not_modified=True, body=None, status=304)
        return HttpResult(not_modified=False, body=step, status=200)


# --------------------------------------------------------------------------- #
# Parser tests
# --------------------------------------------------------------------------- #

class TestParser(unittest.TestCase):
    def test_parses_rss_with_namespace(self):
        missions = parse_feed(load("feed_basic.xml"))
        self.assertEqual([m.id for m in missions], ["m_002", "m_001"])

        m2 = {m.id: m for m in missions}["m_002"]
        self.assertEqual(m2.title, "Safety-review the token at 0xdeadbeef on Ethereum")
        self.assertEqual(m2.reward_amount, 250.0)
        self.assertEqual(m2.reward_currency, "USDC")
        self.assertEqual(m2.verification_type, "oracle")
        self.assertEqual(m2.deadline, 1780000000)
        self.assertEqual(m2.status, "open")
        self.assertTrue(m2.is_usdc)
        self.assertEqual(m2.link, "https://cryptogenesis.duckdns.org/missions/m_002")

        m1 = {m.id: m for m in missions}["m_001"]
        self.assertEqual(m1.reward_amount, 5000.0)
        self.assertEqual(m1.reward_currency, "AIGEN")
        self.assertEqual(m1.submission_count, 2)
        self.assertFalse(m1.is_usdc)

    def test_pubdate_parsed_to_utc(self):
        missions = parse_feed(load("feed_basic.xml"))
        m2 = {m.id: m for m in missions}["m_002"]
        self.assertIsInstance(m2.published, dt.datetime)
        self.assertEqual(m2.published.tzinfo, dt.timezone.utc)
        self.assertEqual(
            m2.published,
            dt.datetime(2026, 6, 2, 8, 30, 0, tzinfo=dt.timezone.utc),
        )

    def test_deadline_helpers(self):
        m = Mission(id="x", title="t", deadline=1780000000)
        self.assertEqual(
            m.deadline_dt,
            dt.datetime.fromtimestamp(1780000000, tz=dt.timezone.utc),
        )
        self.assertIsInstance(m.seconds_to_deadline, float)
        self.assertIsNone(Mission(id="y", title="t").deadline_dt)

    def test_description_fallback_when_no_namespace(self):
        missions = parse_feed(load("feed_no_ns.xml"))
        by_id = {m.id: m for m in missions}
        self.assertIn("m_777", by_id)
        m777 = by_id["m_777"]
        self.assertEqual(m777.reward_amount, 750.0)
        self.assertEqual(m777.reward_currency, "USDC")
        self.assertEqual(m777.verification_type, "creator_judges")
        self.assertEqual(m777.deadline, 1782000000)

    def test_id_recovered_from_link_when_no_guid(self):
        missions = parse_feed(load("feed_no_ns.xml"))
        by_id = {m.id: m for m in missions}
        self.assertIn("m_888", by_id)
        self.assertEqual(by_id["m_888"].reward_currency, "AIGEN")
        self.assertEqual(by_id["m_888"].verification_type, "first_valid_match")

    def test_parses_atom(self):
        missions = parse_feed(load("feed_atom.xml"))
        self.assertEqual(len(missions), 1)
        m = missions[0]
        self.assertEqual(m.id, "m_555")
        self.assertEqual(m.reward_amount, 4200.5)
        self.assertEqual(m.verification_type, "oracle")
        self.assertEqual(m.submission_count, 3)
        self.assertEqual(m.published, dt.datetime(2026, 6, 2, 9, 30, tzinfo=dt.timezone.utc))

    def test_one_bad_item_is_skipped(self):
        missions = parse_feed(load("feed_one_bad_item.xml"))
        self.assertEqual([m.id for m in missions], ["m_good"])

    def test_malformed_feed_raises(self):
        with self.assertRaises(FeedParseError):
            parse_feed(load("feed_malformed.xml"))

    def test_empty_raises(self):
        with self.assertRaises(FeedParseError):
            parse_feed(b"")

    def test_non_feed_xml_raises(self):
        with self.assertRaises(FeedParseError):
            parse_feed(b"<html><body>not a feed</body></html>")


# --------------------------------------------------------------------------- #
# Listener: dedup / emission
# --------------------------------------------------------------------------- #

class TestListenerDedup(unittest.TestCase):
    def _listener(self, client, **kw):
        self.events = []
        kw.setdefault("jitter", 0.0)
        kw.setdefault("base_interval", 1.0)
        return FeedListener(
            on_new_mission=lambda m: self.events.append(m),
            client=client,
            **kw,
        )

    def test_first_poll_suppressed_by_default(self):
        client = FakeClient([load("feed_basic.xml")])
        listener = self._listener(client)
        emitted = listener.poll_once()
        # Seeded, not announced.
        self.assertEqual(emitted, [])
        self.assertEqual(self.events, [])
        self.assertTrue(listener.have_seen("m_001"))
        self.assertTrue(listener.have_seen("m_002"))
        self.assertEqual(listener.seen_count, 2)

    def test_emit_initial_true_backfills(self):
        client = FakeClient([load("feed_basic.xml")])
        listener = self._listener(client, emit_initial=True)
        emitted = listener.poll_once()
        self.assertEqual([m.id for m in emitted], ["m_001", "m_002"])  # oldest-first

    def test_new_mission_emitted_on_second_poll(self):
        client = FakeClient([load("feed_basic.xml"), load("feed_with_new.xml")])
        listener = self._listener(client)
        listener.poll_once()                       # seeds m_001, m_002
        emitted = listener.poll_once()             # m_003 is new
        self.assertEqual([m.id for m in emitted], ["m_003"])
        self.assertEqual([m.id for m in self.events], ["m_003"])
        self.assertEqual(self.events[0].verification_type, "peer_vote")

    def test_no_duplicate_emissions(self):
        client = FakeClient([
            load("feed_basic.xml"),
            load("feed_with_new.xml"),
            load("feed_with_new.xml"),   # same feed again -> nothing new
        ])
        listener = self._listener(client)
        listener.poll_once()
        listener.poll_once()
        emitted = listener.poll_once()
        self.assertEqual(emitted, [])
        self.assertEqual([m.id for m in self.events], ["m_003"])

    def test_emit_oldest_first_within_batch(self):
        # emit_initial -> the whole basic feed counts as new in one batch.
        client = FakeClient([load("feed_basic.xml")])
        listener = self._listener(client, emit_initial=True)
        emitted = listener.poll_once()
        # feed lists m_002 (newer) before m_001 (older); we emit oldest first.
        self.assertEqual([m.id for m in emitted], ["m_001", "m_002"])

    def test_duplicate_ids_within_one_feed_collapse(self):
        dup = (
            b'<?xml version="1.0"?>'
            b'<rss version="2.0" xmlns:oabp="https://cryptogenesis.duckdns.org/ns/oabp">'
            b"<channel><title>t</title>"
            b"<item><oabp:id>dup</oabp:id><title>a</title></item>"
            b"<item><oabp:id>dup</oabp:id><title>b</title></item>"
            b"</channel></rss>"
        )
        client = FakeClient([dup])
        listener = self._listener(client, emit_initial=True)
        emitted = listener.poll_once()
        self.assertEqual([m.id for m in emitted], ["dup"])


# --------------------------------------------------------------------------- #
# Listener: backoff
# --------------------------------------------------------------------------- #

class TestBackoff(unittest.TestCase):
    def make(self, client, **kw):
        kw.setdefault("jitter", 0.0)
        return FeedListener(
            on_new_mission=lambda m: None, client=client, **kw
        )

    def test_error_backoff_grows_then_resets(self):
        err = FeedHttpError("boom", status=503)
        client = FakeClient([err, err, load("feed_basic.xml")])
        seen_errors = []
        listener = self.make(
            client,
            base_interval=2.0,
            backoff_factor=2.0,
            max_interval=100.0,
            on_error=lambda e, n: seen_errors.append(n),
        )

        listener.poll_once()                       # failure #1
        self.assertEqual(listener.next_interval(), 4.0)   # 2 * 2**1
        listener.poll_once()                       # failure #2
        self.assertEqual(listener.next_interval(), 8.0)   # 2 * 2**2
        self.assertEqual(seen_errors, [1, 2])

        listener.poll_once()                       # success resets failures
        # idle bump may apply (no NEW missions on first successful poll because
        # first-poll is suppressed) -> idle step 1 -> 2 * 2**1 = 4.0
        self.assertEqual(listener.next_interval(), 4.0)

    def test_error_backoff_capped(self):
        err = FeedHttpError("boom", status=500)
        client = FakeClient([err] * 20)
        listener = self.make(
            client, base_interval=10.0, backoff_factor=3.0, max_interval=120.0
        )
        for _ in range(20):
            listener.poll_once()
        self.assertLessEqual(listener.next_interval(), 120.0)
        self.assertEqual(listener.next_interval(), 120.0)

    def test_idle_backoff_grows_and_new_mission_resets(self):
        client = FakeClient([
            load("feed_basic.xml"),     # first poll (suppressed) -> idle bump
            "NOT_MODIFIED",             # idle bump
            "NOT_MODIFIED",             # idle bump
            load("feed_with_new.xml"),  # new mission -> reset
        ])
        listener = self.make(
            client,
            base_interval=5.0,
            backoff_factor=2.0,
            max_idle_interval=1000.0,
        )
        listener.poll_once()
        i1 = listener.next_interval()
        listener.poll_once()
        i2 = listener.next_interval()
        listener.poll_once()
        i3 = listener.next_interval()
        self.assertLess(i1, i2)
        self.assertLess(i2, i3)

        listener.poll_once()            # emits m_003 -> reset to base
        self.assertEqual(listener.next_interval(), 5.0)

    def test_idle_backoff_capped(self):
        script = [load("feed_basic.xml")] + ["NOT_MODIFIED"] * 30
        client = FakeClient(script)
        listener = self.make(
            client, base_interval=5.0, backoff_factor=2.0, max_idle_interval=60.0
        )
        for _ in range(30):
            listener.poll_once()
        self.assertLessEqual(listener.next_interval(), 60.0)

    def test_parse_error_counts_as_failure(self):
        client = FakeClient([load("feed_malformed.xml"), load("feed_basic.xml")])
        errs = []
        listener = self.make(client, base_interval=1.0, on_error=lambda e, n: errs.append(e))
        listener.poll_once()
        self.assertEqual(len(errs), 1)
        self.assertIsInstance(errs[0], FeedParseError)


# --------------------------------------------------------------------------- #
# Listener: persistence + run loop
# --------------------------------------------------------------------------- #

class TestPersistence(unittest.TestCase):
    def test_state_survives_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "state.json")

            events_a = []
            l1 = FeedListener(
                on_new_mission=lambda m: events_a.append(m),
                client=FakeClient([load("feed_basic.xml")]),
                state_path=path,
                jitter=0.0,
            )
            l1.poll_once()                     # seeds m_001/m_002, writes file
            self.assertTrue(os.path.exists(path))

            with open(path) as fh:
                blob = json.load(fh)
            self.assertEqual(set(blob["seen"]), {"m_001", "m_002"})

            # Fresh listener, same state file, served the SAME feed: because
            # state was loaded, nothing is treated as new (no re-announce).
            events_b = []
            l2 = FeedListener(
                on_new_mission=lambda m: events_b.append(m),
                client=FakeClient([load("feed_basic.xml")]),
                state_path=path,
                jitter=0.0,
            )
            emitted = l2.poll_once()
            self.assertEqual(emitted, [])
            self.assertEqual(events_b, [])

            # ... but a genuinely new mission still fires.
            l2b = FeedListener(
                on_new_mission=lambda m: events_b.append(m),
                client=FakeClient([load("feed_with_new.xml")]),
                state_path=path,
                jitter=0.0,
            )
            emitted = l2b.poll_once()
            self.assertEqual([m.id for m in emitted], ["m_003"])

    def test_max_seen_eviction(self):
        listener = FeedListener(
            on_new_mission=lambda m: None,
            client=FakeClient([b""]),
            max_seen=3,
            jitter=0.0,
        )
        for i in range(10):
            listener._record_seen(f"id_{i}")
        self.assertEqual(listener.seen_count, 3)
        self.assertTrue(listener.have_seen("id_9"))
        self.assertFalse(listener.have_seen("id_0"))


class TestRunLoop(unittest.TestCase):
    def test_run_forever_max_cycles(self):
        client = FakeClient([
            load("feed_basic.xml"),
            load("feed_with_new.xml"),
        ])
        events = []
        listener = FeedListener(
            on_new_mission=lambda m: events.append(m),
            client=client,
            base_interval=0.001,
            jitter=0.0,
        )
        listener.run_forever(max_cycles=2)
        self.assertEqual([m.id for m in events], ["m_003"])
        self.assertEqual(client.calls, 2)

    def test_callback_exception_does_not_kill_loop(self):
        calls = {"n": 0}

        def boom(_m):
            calls["n"] += 1
            raise RuntimeError("callback failed")

        client = FakeClient([load("feed_basic.xml"), load("feed_with_new.xml")])
        listener = FeedListener(
            on_new_mission=boom,
            client=client,
            base_interval=0.001,
            jitter=0.0,
        )
        # run_forever swallows callback errors and keeps cycling.
        listener.run_forever(max_cycles=2)
        self.assertEqual(calls["n"], 1)  # m_003 attempted once
        # The id is still recorded as seen despite the callback raising.
        self.assertTrue(listener.have_seen("m_003"))

    def test_constructor_validates_callback(self):
        with self.assertRaises(TypeError):
            FeedListener(on_new_mission=None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
