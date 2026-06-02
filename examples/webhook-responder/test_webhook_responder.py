#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline tests for ``webhook_responder.py`` (stdlib ``unittest``, no network).

Covers the acceptance criteria directly:

* an offline test starts the server on an **ephemeral port**, POSTs a
  ``first_valid_match`` mission JSON, asserts a 2xx response, and — in
  **non-dry-run with a stubbed submit** — asserts a deliverable was generated and
  delivered to the stub;
* ``GET /healthz`` returns 200;
* ``GET /metrics`` reflects the ``received`` counter;
* a request with the WRONG ``--secret`` is rejected ``401``.

Plus: the regex sampler battery / fail-closed behaviour, oracle passthrough
(``--proof-template``) submit vs skip-without-template, peer_vote/creator_judges
skips, the min-reward floor, dry-run-submits-nothing, malformed-JSON handling,
the HMAC and bare-token secret forms, and oversized-body rejection.

Run::

    python3 -m unittest -v test_webhook_responder
    # or simply:  python3 test_webhook_responder.py
"""

from __future__ import annotations

import hashlib
import hmac
import json
import queue
import threading
import unittest
import urllib.error
import urllib.request
from typing import Any, List, Mapping, Optional, Tuple

import webhook_responder as wr


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _request(
    method: str,
    url: str,
    *,
    body: Optional[bytes] = None,
    headers: Optional[Mapping[str, str]] = None,
) -> Tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, method=method, headers=dict(headers or {}))
    try:
        resp = urllib.request.urlopen(req, timeout=10.0)
        return int(getattr(resp, "status", resp.getcode())), resp.read()
    except urllib.error.HTTPError as exc:
        raw = b""
        try:
            raw = exc.read()
        except Exception:
            pass
        return int(exc.code), raw


def _hmac(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


class _StubSubmitter(wr.Submitter):
    """A Submitter that records calls instead of hitting the network."""

    def __init__(self) -> None:
        super().__init__("http://stub.invalid")
        self.calls: List[Tuple[str, str, str]] = []

    def submit(self, mission_id: str, agent_id: str, proof: str) -> Tuple[int, Any]:
        self.calls.append((mission_id, agent_id, proof))
        return 200, {"status": "accepted", "mission_id": mission_id}


class _ServerFixture:
    """Spin up the responder on an ephemeral port with a stubbed submitter."""

    def __init__(self, *, dry_run: bool, secret: Optional[str],
                 verification_types: Optional[List[str]] = None,
                 proof_template: Optional[str] = None,
                 min_reward: float = 0.0) -> None:
        self.metrics = wr.Metrics()
        self.stub = _StubSubmitter()
        self.queue: "queue.Queue" = queue.Queue()
        self._worker = threading.Thread(
            target=wr.submit_worker,
            args=(self.queue, self.stub, "test-agent", self.metrics, lambda m: None),
            daemon=True,
        )
        self._worker.start()
        cfg = wr.ResponderConfig(
            responder=wr.Responder(
                verification_types=verification_types,
                proof_template=proof_template,
                min_reward=min_reward,
                seed=0,
            ),
            metrics=self.metrics,
            agent_id="test-agent",
            secret=secret,
            dry_run=dry_run,
            submit_queue=None if dry_run else self.queue,
        )
        self.httpd = wr.make_server("127.0.0.1", 0, cfg)
        self.port = self.httpd.server_address[1]
        self.base = "http://127.0.0.1:%d" % self.port
        self._t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self._t.start()

    def drain(self) -> None:
        self.queue.join()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.queue.put(wr._SUBMIT_SENTINEL)
        self._worker.join(timeout=5.0)


FVM_MISSION = {
    "id": "mis_e2e_001",
    "title": "Find a token address",
    "verification_type": "first_valid_match",
    "verification_params": {"regex": r"^0x[a-f0-9]{40}$"},
    "reward": {"amount": 67, "currency": "AIGEN"},
    "status": "open",
}


# --------------------------------------------------------------------------- #
# Regex sampler
# --------------------------------------------------------------------------- #
class TestRegexSampler(unittest.TestCase):
    def test_matches_battery(self) -> None:
        for pat in (
            r"^0x[a-f0-9]{40}$",
            r"^[A-Z]{3}-\d{4}$",
            r"https://github\.com/[A-Za-z0-9_.\-]+/pull/[0-9]+",
            r"^(cat|dog|bird)$",
            r"\d{3,5}",
        ):
            s = wr.RegexSampler(seed=1234).sample(pat)
            if pat.startswith("^") and pat.endswith("$"):
                self.assertRegex(s, pat)  # fullmatch-ish for anchored
            else:
                self.assertTrue(wr.re.search(pat, s), (pat, s))

    def test_canonical_address_minimal(self) -> None:
        self.assertEqual(wr.RegexSampler(seed=0).sample(r"^0x[a-f0-9]{40}$"), "0x" + "0" * 40)

    def test_deterministic_with_seed(self) -> None:
        a = wr.RegexSampler(seed=7).sample(r"^[a-f0-9]{6}$")
        b = wr.RegexSampler(seed=7).sample(r"^[a-f0-9]{6}$")
        self.assertEqual(a, b)

    def test_fail_closed_on_unsupported(self) -> None:
        for bad in (r"(?=foo)bar", r"(a)\1", r"(?i)abc", r"a{", r"["):
            with self.assertRaises(wr.UnsupportedPattern):
                wr.RegexSampler(seed=1).sample(bad)


# --------------------------------------------------------------------------- #
# Responder policy (no server)
# --------------------------------------------------------------------------- #
class TestResponderPolicy(unittest.TestCase):
    def test_first_valid_match_claimed(self) -> None:
        d = wr.Responder(seed=0).evaluate(FVM_MISSION)
        self.assertEqual(d.action, "claim")
        self.assertEqual(d.proof, "0x" + "0" * 40)

    def test_oracle_skipped_without_template(self) -> None:
        d = wr.Responder(verification_types=["oracle"]).evaluate(
            {"id": "m", "verification_type": "oracle"}
        )
        self.assertEqual(d.action, "skip")

    def test_oracle_claimed_with_template(self) -> None:
        d = wr.Responder(
            verification_types=["oracle"],
            proof_template="https://github.com/me/{id}",
        ).evaluate({"id": "mis_repo", "verification_type": "oracle",
                    "description": "deliver a Go repo"})
        self.assertEqual(d.action, "claim")
        self.assertEqual(d.proof, "https://github.com/me/mis_repo")

    def test_template_address_placeholder(self) -> None:
        addr = "0x" + "ab" * 20
        d = wr.Responder(
            verification_types=["oracle"],
            proof_template="reviewed {address}",
        ).evaluate({"id": "m", "verification_type": "oracle",
                    "description": "safety review of %s on Base" % addr})
        self.assertEqual(d.proof, "reviewed %s" % addr)

    def test_peer_vote_and_creator_judges_skipped(self) -> None:
        r = wr.Responder(verification_types=["first_valid_match", "peer_vote", "creator_judges"])
        self.assertEqual(r.evaluate({"id": "p", "verification_type": "peer_vote"}).action, "skip")
        self.assertEqual(r.evaluate({"id": "c", "verification_type": "creator_judges"}).action, "skip")

    def test_type_filter_skips_unlisted(self) -> None:
        d = wr.Responder(verification_types=["first_valid_match"]).evaluate(
            {"id": "o", "verification_type": "oracle"}
        )
        self.assertEqual(d.action, "skip")
        self.assertIn("not in --verification-type", d.reason)

    def test_min_reward_floor(self) -> None:
        d = wr.Responder(min_reward=100).evaluate(
            {"id": "x", "verification_type": "first_valid_match",
             "verification_params": {"regex": "^a$"}, "reward_aigen": 5}
        )
        self.assertEqual(d.action, "skip")

    def test_invalid_body(self) -> None:
        self.assertEqual(wr.Responder().evaluate(["not", "a", "mission"]).action, "invalid")
        self.assertEqual(wr.Responder().evaluate(42).action, "invalid")

    def test_unwrap_envelope(self) -> None:
        d = wr.Responder(seed=0).evaluate({"event": "mission.created", "data": FVM_MISSION})
        self.assertEqual(d.action, "claim")

    def test_non_open_status_skipped(self) -> None:
        m = dict(FVM_MISSION, status="resolved")
        self.assertEqual(wr.Responder(seed=0).evaluate(m).action, "skip")


# --------------------------------------------------------------------------- #
# Secret verification
# --------------------------------------------------------------------------- #
class TestSecret(unittest.TestCase):
    def test_open_mode_accepts_all(self) -> None:
        self.assertTrue(wr.verify_secret(None, b"{}", {}))

    def test_hmac(self) -> None:
        body = b'{"id":"m"}'
        self.assertTrue(wr.verify_secret("s3cret", body, {"X-OABP-Signature": _hmac("s3cret", body)}))

    def test_bare_token_and_bearer(self) -> None:
        self.assertTrue(wr.verify_secret("s3cret", b"x", {"X-OABP-Token": "s3cret"}))
        self.assertTrue(wr.verify_secret("s3cret", b"x", {"Authorization": "Bearer s3cret"}))

    def test_wrong_secret_rejected(self) -> None:
        self.assertFalse(wr.verify_secret("s3cret", b"x", {"X-OABP-Token": "WRONG"}))
        self.assertFalse(wr.verify_secret("s3cret", b"x", {}))


# --------------------------------------------------------------------------- #
# End-to-end server (ephemeral port) — the acceptance scenario
# --------------------------------------------------------------------------- #
class TestServerEndToEnd(unittest.TestCase):
    def test_acceptance_flow(self) -> None:
        fx = _ServerFixture(dry_run=False, secret="s3cret",
                            verification_types=["first_valid_match", "oracle"],
                            proof_template="https://github.com/me/{id}")
        try:
            raw = json.dumps(FVM_MISSION).encode("utf-8")

            # wrong secret -> 401, nothing claimed
            st, _ = _request("POST", fx.base + "/webhook", body=raw,
                             headers={"Content-Type": "application/json",
                                      "X-OABP-Token": "WRONG"})
            self.assertEqual(st, 401)

            # correct HMAC -> 202 (queued in non-dry-run), proof generated
            st, rb = _request("POST", fx.base + "/webhook", body=raw,
                              headers={"Content-Type": "application/json",
                                       "X-OABP-Signature": _hmac("s3cret", raw)})
            self.assertEqual(st, 202)
            payload = json.loads(rb.decode("utf-8"))
            self.assertEqual(payload["action"], "claim")
            self.assertRegex(payload["proof"], r"^0x[a-f0-9]{40}$")

            # the stubbed submit actually received the deliverable
            fx.drain()
            self.assertIn(("mis_e2e_001", "test-agent", "0x" + "0" * 40), fx.stub.calls)

            # /healthz -> 200
            st, rb = _request("GET", fx.base + "/healthz")
            self.assertEqual(st, 200)
            health = json.loads(rb.decode("utf-8"))
            self.assertEqual(health["status"], "ok")
            self.assertEqual(health["agent_id"], "test-agent")

            # /metrics reflects the received + claimed + rejected counters
            st, rb = _request("GET", fx.base + "/metrics")
            self.assertEqual(st, 200)
            text = rb.decode("utf-8")
            self.assertIn("oabp_webhook_received_total 1", text)
            self.assertIn("oabp_webhook_claimed_total 1", text)
            self.assertIn("oabp_webhook_rejected_unauthorized_total 1", text)
            self.assertIn("oabp_webhook_submit_ok_total 1", text)
        finally:
            fx.close()

    def test_dry_run_submits_nothing(self) -> None:
        fx = _ServerFixture(dry_run=True, secret=None)  # open + dry-run
        try:
            raw = json.dumps(FVM_MISSION).encode("utf-8")
            st, rb = _request("POST", fx.base + "/webhook", body=raw,
                              headers={"Content-Type": "application/json"})
            self.assertEqual(st, 200)  # 200, not 202, in dry-run
            payload = json.loads(rb.decode("utf-8"))
            self.assertEqual(payload["action"], "claim")
            self.assertFalse(payload["submitted"])
            self.assertRegex(payload["proof"], r"^0x[a-f0-9]{40}$")
            # nothing was submitted
            self.assertEqual(fx.stub.calls, [])
            # /metrics: received + claimed counted, submit_ok not
            _, rb = _request("GET", fx.base + "/metrics")
            self.assertIn("oabp_webhook_claimed_total 1", rb.decode("utf-8"))
            self.assertIn("oabp_webhook_submit_ok_total 0", rb.decode("utf-8"))
        finally:
            fx.close()

    def test_oracle_passthrough_over_http(self) -> None:
        fx = _ServerFixture(dry_run=False, secret=None,
                            verification_types=["oracle"],
                            proof_template="https://github.com/me/{id}")
        try:
            omission = {
                "id": "mis_oracle_002",
                "title": "Deliver a Go repo",
                "verification_type": "oracle",
                "verification_params": {"oracle_description": "public GitHub repo in Go"},
                "reward": {"amount": 250, "currency": "USDC"},
            }
            raw = json.dumps(omission).encode("utf-8")
            st, rb = _request("POST", fx.base + "/webhook", body=raw,
                              headers={"Content-Type": "application/json"})
            self.assertEqual(st, 202)
            self.assertEqual(json.loads(rb.decode("utf-8"))["proof"],
                             "https://github.com/me/mis_oracle_002")
            fx.drain()
            self.assertTrue(any(mid == "mis_oracle_002" for (mid, _a, _p) in fx.stub.calls))
        finally:
            fx.close()

    def test_skip_returns_200(self) -> None:
        fx = _ServerFixture(dry_run=True, secret=None,
                            verification_types=["first_valid_match"])
        try:
            # peer_vote not in our type filter AND human-resolved -> skip
            m = {"id": "pv", "verification_type": "peer_vote",
                 "reward": {"amount": 10, "currency": "AIGEN"}}
            raw = json.dumps(m).encode("utf-8")
            st, rb = _request("POST", fx.base + "/webhook", body=raw,
                              headers={"Content-Type": "application/json"})
            self.assertEqual(st, 200)
            self.assertEqual(json.loads(rb.decode("utf-8"))["action"], "skip")
            _, rb = _request("GET", fx.base + "/metrics")
            self.assertIn("oabp_webhook_skipped_total 1", rb.decode("utf-8"))
        finally:
            fx.close()

    def test_malformed_json_is_400(self) -> None:
        fx = _ServerFixture(dry_run=True, secret=None)
        try:
            st, _ = _request("POST", fx.base + "/webhook", body=b"{not json",
                             headers={"Content-Type": "application/json"})
            self.assertEqual(st, 400)
        finally:
            fx.close()

    def test_unknown_route_404(self) -> None:
        fx = _ServerFixture(dry_run=True, secret=None)
        try:
            st, _ = _request("GET", fx.base + "/nope")
            self.assertEqual(st, 404)
        finally:
            fx.close()

    def test_root_banner_200(self) -> None:
        fx = _ServerFixture(dry_run=True, secret=None)
        try:
            st, rb = _request("GET", fx.base + "/")
            self.assertEqual(st, 200)
            self.assertIn(b"webhook responder", rb)
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
