#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for ``oracle_watcher.py`` (stdlib ``unittest``, no network).

Covers the acceptance criteria:

* ``--demo`` replays two fixtures and prints exactly one ``NEW ORACLE MISSION``
  line (dedup proven, no network);
* a user-callback exception is caught and does **not** kill the loop;
* the state file round-trips seen ids across a simulated restart;

plus the three event kinds (open / submission / resolved), the
non-oracle/malformed-record filtering, conditional-GET 304 idling, and backoff.

Run::

    python3 -m unittest -v test_oracle_watcher
    # or simply:  python3 test_oracle_watcher.py
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from typing import Any, Dict, List, Optional

import oracle_watcher as ow


# --------------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------------- #
class FakeClient:
    """A MissionsClient-shaped fake that returns scripted poll outcomes.

    ``script`` is a list whose entries are one of:
      * a dict / list  -> served as a fresh JSON body (200);
      * the string "304" -> served as a 304 Not Modified;
      * an Exception instance -> raised as if the fetch failed.
    Past the end of the script it serves 304 (idle).
    """

    def __init__(self, script: List[Any]) -> None:
        self.url = "memory://test/api/missions"
        self._script = list(script)
        self._i = 0
        self.etag: Optional[str] = None
        self.last_modified: Optional[str] = None
        self.fetch_calls = 0

    def fetch(self) -> ow.HttpResult:
        self.fetch_calls += 1
        if self._i >= len(self._script):
            return ow.HttpResult(not_modified=True, body=None, status=304)
        item = self._script[self._i]
        self._i += 1
        if isinstance(item, ow.MissionsHttpError):
            raise item
        if isinstance(item, Exception):
            raise item
        if item == "304":
            return ow.HttpResult(not_modified=True, body=None, status=304)
        body = json.dumps(item).encode("utf-8")
        return ow.HttpResult(not_modified=False, body=body, status=200)


def oracle_mission(
    mid: str,
    *,
    status: str = "open",
    submissions: Optional[List[Dict[str, Any]]] = None,
    resolution: Optional[Dict[str, Any]] = None,
    amount: float = 100,
    currency: str = "AIGEN",
    oracle_description: str = "safety review of 0x" + "ab" * 20 + " on base",
) -> Dict[str, Any]:
    m: Dict[str, Any] = {
        "id": mid,
        "title": "Oracle mission %s" % mid,
        "reward": {"amount": amount, "currency": currency},
        "verification_type": "oracle",
        "verification_params": {"oracle_description": oracle_description},
        "deadline": 4102444800,
        "status": status,
        "submissions": submissions if submissions is not None else [],
    }
    if resolution is not None:
        m["resolution"] = resolution
    return m


def board(missions: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"count": len(missions), "missions": missions}


def ids(events: List[tuple]) -> List[tuple]:
    """Normalise ``poll_once`` output ``[(kind, Mission), ...]`` to ``[(kind, id)]``."""
    return [(kind, m.id) for (kind, m) in events]


class Recorder:
    """Collects (kind, mission_id) events; can be told to raise once."""

    def __init__(self, raise_on_first: bool = False) -> None:
        self.events: List[tuple] = []
        self.calls = 0
        self._raise_on_first = raise_on_first

    def __call__(self, kind: str, mission: ow.Mission) -> None:
        self.calls += 1
        if self._raise_on_first and self.calls == 1:
            raise RuntimeError("boom from user callback")
        self.events.append((kind, mission.id))


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
class DemoTest(unittest.TestCase):
    def test_demo_prints_exactly_one_new_oracle_mission_line(self) -> None:
        buf = io.StringIO()
        rc = ow.run_demo(out=buf)
        self.assertEqual(rc, 0, buf.getvalue())
        text = buf.getvalue()
        new_lines = [
            ln for ln in text.splitlines() if ln.startswith("[NEW ORACLE MISSION]")
        ]
        self.assertEqual(len(new_lines), 1, text)
        self.assertIn("mis_demo_repo_0003", new_lines[0])

    def test_main_demo_returns_zero(self) -> None:
        self.assertEqual(ow.main(["--demo"]), 0)


class TransitionTest(unittest.TestCase):
    def test_open_fires_once_then_dedups(self) -> None:
        rec = Recorder()
        client = FakeClient(
            [
                board([oracle_mission("m1")]),  # appears -> OPEN
                board([oracle_mission("m1")]),  # unchanged -> nothing
                "304",                            # idle
            ]
        )
        w = ow.OracleMissionWatcher(
            on_event=rec, client=client, emit_initial=True, jitter=0.0
        )
        e1 = w.poll_once()
        e2 = w.poll_once()
        e3 = w.poll_once()
        self.assertEqual([(ow.KIND_OPEN, "m1")], ids(e1))
        self.assertEqual([], e2)
        self.assertEqual([], e3)
        self.assertEqual(rec.events, [(ow.KIND_OPEN, "m1")])

    def test_cold_start_suppresses_initial_when_emit_initial_false(self) -> None:
        rec = Recorder()
        client = FakeClient([board([oracle_mission("m1"), oracle_mission("m2")])])
        w = ow.OracleMissionWatcher(
            on_event=rec, client=client, emit_initial=False, jitter=0.0
        )
        e1 = w.poll_once()
        self.assertEqual([], e1, "cold first poll must be silent")
        # state was still seeded: a later resolution fires, an old open does not.
        client._script.append(board([oracle_mission("m1", status="resolved")]))
        e2 = w.poll_once()
        self.assertEqual([(ow.KIND_RESOLVED, "m1")], ids(e2))

    def test_new_submission_fires_on_count_increase(self) -> None:
        rec = Recorder()
        client = FakeClient(
            [
                board([oracle_mission("m1")]),  # 0 submissions (seed, emit)
                board([oracle_mission("m1", submissions=[{"submitter_agent_id": "a", "proof": "p1"}])]),
                board(  # second, distinct submission
                    [
                        oracle_mission(
                            "m1",
                            submissions=[
                                {"submitter_agent_id": "a", "proof": "p1"},
                                {"submitter_agent_id": "b", "proof": "p2"},
                            ],
                        )
                    ]
                ),
                board(  # re-poll identical -> no new event
                    [
                        oracle_mission(
                            "m1",
                            submissions=[
                                {"submitter_agent_id": "a", "proof": "p1"},
                                {"submitter_agent_id": "b", "proof": "p2"},
                            ],
                        )
                    ]
                ),
            ]
        )
        w = ow.OracleMissionWatcher(
            on_event=rec, client=client, emit_initial=True, jitter=0.0
        )
        w.poll_once()  # OPEN
        e2 = w.poll_once()
        e3 = w.poll_once()
        e4 = w.poll_once()
        self.assertEqual([(ow.KIND_SUBMISSION, "m1")], ids(e2))
        self.assertEqual([(ow.KIND_SUBMISSION, "m1")], ids(e3))
        self.assertEqual([], e4)
        self.assertEqual(
            [k for (k, _) in rec.events].count(ow.KIND_SUBMISSION), 2
        )

    def test_resolved_fires_on_status_flip(self) -> None:
        rec = Recorder()
        client = FakeClient(
            [
                board([oracle_mission("m1")]),
                board([oracle_mission("m1", status="resolved",
                                      resolution={"winner_agent_id": "winner-bot",
                                                  "verified": True})]),
                board([oracle_mission("m1", status="resolved",
                                      resolution={"winner_agent_id": "winner-bot"})]),
            ]
        )
        w = ow.OracleMissionWatcher(
            on_event=rec, client=client, emit_initial=True, jitter=0.0
        )
        w.poll_once()
        e2 = w.poll_once()
        e3 = w.poll_once()
        self.assertEqual([(ow.KIND_RESOLVED, "m1")], ids(e2))
        self.assertEqual([], e3, "resolution must not re-fire")

    def test_resolution_object_without_status_change_fires(self) -> None:
        # Some deployments attach a resolution while leaving status as-is.
        rec = Recorder()
        client = FakeClient(
            [
                board([oracle_mission("m1")]),
                board([oracle_mission("m1", resolution={"winner_agent_id": "w"})]),
            ]
        )
        w = ow.OracleMissionWatcher(
            on_event=rec, client=client, emit_initial=True, jitter=0.0
        )
        w.poll_once()
        e2 = w.poll_once()
        self.assertEqual([(ow.KIND_RESOLVED, "m1")], ids(e2))

    def test_non_oracle_missions_ignored(self) -> None:
        rec = Recorder()
        regex_mission = {
            "id": "r1",
            "verification_type": "first_valid_match",
            "verification_params": {"regex": "^x"},
            "reward": {"amount": 1, "currency": "AIGEN"},
            "status": "open",
            "submissions": [],
        }
        client = FakeClient([board([regex_mission])])
        w = ow.OracleMissionWatcher(
            on_event=rec, client=client, emit_initial=True, jitter=0.0
        )
        self.assertEqual([], w.poll_once())
        self.assertEqual(rec.events, [])


class RobustnessTest(unittest.TestCase):
    def test_callback_exception_does_not_kill_loop(self) -> None:
        # The FIRST emitted event raises inside the user callback; subsequent
        # polls must still run and still emit.
        rec = Recorder(raise_on_first=True)
        client = FakeClient(
            [
                board([oracle_mission("m1")]),                 # OPEN (callback raises)
                board([oracle_mission("m1", status="resolved")]),  # RESOLVED (must still fire)
            ]
        )
        w = ow.OracleMissionWatcher(
            on_event=rec, client=client, emit_initial=True, jitter=0.0
        )
        # poll_once itself must not raise even though the callback did.
        w.poll_once()
        w.poll_once()
        # The first (open) event was swallowed; the resolved event recorded.
        self.assertIn((ow.KIND_RESOLVED, "m1"), rec.events)
        # event_count only counts successful emits (the raising one didn't count).
        self.assertEqual(w.event_count, 1)

    def test_run_forever_survives_callback_exception(self) -> None:
        # Drive the real loop (bounded) with a handler that always raises.
        def boom(kind: str, mission: ow.Mission) -> None:
            raise ValueError("always boom")

        client = FakeClient(
            [
                board([oracle_mission("m1")]),
                board([oracle_mission("m2")]),
            ]
        )
        w = ow.OracleMissionWatcher(
            on_event=boom, client=client, emit_initial=True, interval=0.001, jitter=0.0
        )
        # If a callback exception killed the loop, this would raise.
        w.run_forever(max_cycles=3)
        self.assertGreaterEqual(client.fetch_calls, 3)

    def test_malformed_record_skipped_not_fatal(self) -> None:
        rec = Recorder()
        client = FakeClient(
            [
                board(
                    [
                        {"title": "no id here", "verification_type": "oracle"},  # bad
                        oracle_mission("good1"),                                  # good
                        {"id": "", "verification_type": "oracle"},               # blank id
                        "not a dict",                                            # not a mapping
                    ]
                )
            ]
        )
        w = ow.OracleMissionWatcher(
            on_event=rec, client=client, emit_initial=True, jitter=0.0
        )
        e1 = w.poll_once()
        self.assertEqual([(ow.KIND_OPEN, "good1")], ids(e1))
        self.assertEqual(w.malformed_count, 3)

    def test_invalid_json_triggers_error_backoff_not_crash(self) -> None:
        rec = Recorder()

        class BadBodyClient(FakeClient):
            def fetch(self) -> ow.HttpResult:
                self.fetch_calls += 1
                return ow.HttpResult(
                    not_modified=False, body=b"<<<not json>>>", status=200
                )

        client = BadBodyClient([])
        w = ow.OracleMissionWatcher(
            on_event=rec, client=client, interval=10.0, jitter=0.0
        )
        out = w.poll_once()  # must NOT raise
        self.assertEqual(out, [])
        self.assertEqual(w._failures, 1)
        # next interval reflects one failure (error backoff): 10 * 2**1 = 20.
        self.assertAlmostEqual(w.next_interval(), 20.0, places=6)

    def test_http_error_triggers_error_backoff(self) -> None:
        rec = Recorder()
        client = FakeClient(
            [ow.MissionsHttpError("boom", status=500), board([oracle_mission("m1")])]
        )
        w = ow.OracleMissionWatcher(
            on_event=rec, client=client, interval=5.0, emit_initial=True, jitter=0.0
        )
        self.assertEqual([], w.poll_once())  # failure #1
        self.assertEqual(w._failures, 1)
        # a subsequent success resets failures and emits.
        e = w.poll_once()
        self.assertEqual([(ow.KIND_OPEN, "m1")], ids(e))
        self.assertEqual(w._failures, 0)


class BackoffTest(unittest.TestCase):
    def test_idle_backoff_grows_then_new_event_resets(self) -> None:
        client = FakeClient(
            [
                board([oracle_mission("m1")]),  # seeds (cold-suppressed)
                "304",                            # idle 1
                "304",                            # idle 2
                board([oracle_mission("m2")]),  # new -> resets idle
            ]
        )
        w = ow.OracleMissionWatcher(
            on_event=Recorder(), client=client, interval=10.0,
            max_idle_interval=10000.0, emit_initial=False, jitter=0.0,
        )
        w.poll_once()
        self.assertEqual(w._idle_steps, 1)
        w.poll_once()
        self.assertEqual(w._idle_steps, 2)
        w.poll_once()
        self.assertEqual(w._idle_steps, 3)
        w.poll_once()  # new mission -> reset
        self.assertEqual(w._idle_steps, 0)

    def test_304_not_modified_is_idle_not_error(self) -> None:
        w = ow.OracleMissionWatcher(
            on_event=Recorder(), client=FakeClient(["304"]),
            interval=10.0, jitter=0.0,
        )
        self.assertEqual([], w.poll_once())
        self.assertEqual(w._failures, 0)
        self.assertEqual(w._idle_steps, 1)


class StatePersistenceTest(unittest.TestCase):
    def test_state_roundtrips_seen_ids_across_restart(self) -> None:
        tmpdir = tempfile.mkdtemp()
        state_path = os.path.join(tmpdir, "watch_state.json")

        # --- first process: sees m1 open, persists state ---------------- #
        rec1 = Recorder()
        client1 = FakeClient([board([oracle_mission("m1")])])
        w1 = ow.OracleMissionWatcher(
            on_event=rec1, client=client1, state_file=state_path,
            emit_initial=True, jitter=0.0,
        )
        e1 = w1.poll_once()
        self.assertEqual([(ow.KIND_OPEN, "m1")], ids(e1))
        self.assertTrue(os.path.exists(state_path))

        # the persisted file actually contains the emitted open key + baseline.
        with open(state_path, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        self.assertIn("%s:m1:open" % ow.KIND_OPEN, saved["emitted"])
        self.assertIn("m1", saved["mission_state"])

        # --- second process (simulated restart): SAME state file -------- #
        rec2 = Recorder()
        client2 = FakeClient([board([oracle_mission("m1")])])  # m1 still open
        w2 = ow.OracleMissionWatcher(
            on_event=rec2, client=client2, state_file=state_path,
            emit_initial=True, jitter=0.0,
        )
        # m1 must NOT be re-announced: its open key is remembered from disk.
        self.assertTrue(w2.already_emitted("%s:m1:open" % ow.KIND_OPEN))
        e2 = w2.poll_once()
        self.assertEqual([], e2, "restart must not re-announce known missions")

        # but a NEW transition on the same mission (resolution) DOES fire post-restart.
        client2._script.append(board([oracle_mission("m1", status="resolved")]))
        e3 = w2.poll_once()
        self.assertEqual([(ow.KIND_RESOLVED, "m1")], ids(e3))

    def test_corrupt_state_file_does_not_crash_construction(self) -> None:
        tmpdir = tempfile.mkdtemp()
        state_path = os.path.join(tmpdir, "corrupt.json")
        with open(state_path, "w", encoding="utf-8") as fh:
            fh.write("{ this is not valid json ")
        # Should log a warning and start fresh, not raise.
        w = ow.OracleMissionWatcher(
            on_event=Recorder(), client=FakeClient([]), state_file=state_path,
            jitter=0.0,
        )
        self.assertEqual(w.emitted_count, 0)

    def test_etag_validators_persist_and_restore(self) -> None:
        tmpdir = tempfile.mkdtemp()
        state_path = os.path.join(tmpdir, "etag_state.json")
        client = FakeClient([board([oracle_mission("m1")])])
        client.etag = '"abc123"'
        client.last_modified = "Wed, 21 Oct 2026 07:28:00 GMT"
        w = ow.OracleMissionWatcher(
            on_event=Recorder(), client=client, state_file=state_path,
            emit_initial=True, jitter=0.0,
        )
        w.poll_once()
        client2 = FakeClient([])
        w2 = ow.OracleMissionWatcher(
            on_event=Recorder(), client=client2, state_file=state_path, jitter=0.0,
        )
        self.assertEqual(client2.etag, '"abc123"')
        self.assertEqual(client2.last_modified, "Wed, 21 Oct 2026 07:28:00 GMT")


class ParsingAndFormatTest(unittest.TestCase):
    def test_bare_array_envelope_supported(self) -> None:
        rec = Recorder()
        client = FakeClient([[oracle_mission("m1")]])  # bare list, not wrapped
        w = ow.OracleMissionWatcher(
            on_event=rec, client=client, emit_initial=True, jitter=0.0
        )
        self.assertEqual([(ow.KIND_OPEN, "m1")], ids(w.poll_once()))

    def test_reward_net_and_currency_in_summary(self) -> None:
        m = ow.Mission(oracle_mission("m1", amount=200, currency="USDC"))
        line = ow.format_event_line(ow.KIND_OPEN, m)
        self.assertIn("[NEW ORACLE MISSION]", line)
        self.assertIn("200 USDC (net 199)", line)  # 0.5% fee
        self.assertIn("oracle_description=", line)

    def test_mission_unknown_reward_is_tolerated(self) -> None:
        m = ow.Mission({"id": "x", "verification_type": "oracle"})
        self.assertIsNone(m.reward_amount)
        self.assertEqual(m.reward_display(), "? ?")
        # formatting must not raise on a sparse record.
        ow.format_event_line(ow.KIND_OPEN, m)

    def test_mission_requires_id(self) -> None:
        with self.assertRaises(ValueError):
            ow.Mission({"verification_type": "oracle"})
        with self.assertRaises(ValueError):
            ow.Mission("not a mapping")


if __name__ == "__main__":
    unittest.main(verbosity=2)
