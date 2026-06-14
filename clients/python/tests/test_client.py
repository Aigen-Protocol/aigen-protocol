"""Unit tests for the OABP Python SDK.

All HTTP traffic is mocked at the ``requests.Session.request`` level via a tiny
fake session, so the suite runs fully offline and deterministically. Backoff
sleeps are stubbed out so retry paths execute instantly.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import pytest
import requests

from oabp import (
    Currency,
    Mission,
    MissionStatus,
    OabpClient,
    OabpConnectionError,
    OabpError,
    OabpNotFoundError,
    OabpRateLimitError,
    OabpServerError,
    OabpTimeoutError,
    OabpValidationError,
    Reputation,
    Stats,
    VerificationType,
)


# --------------------------------------------------------------------------- #
# Test doubles
# --------------------------------------------------------------------------- #
class FakeResponse:
    """Minimal stand-in for ``requests.Response``."""

    def __init__(
        self,
        status_code: int = 200,
        json_data: Any = None,
        *,
        text: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        reason: str = "OK",
    ) -> None:
        self.status_code = status_code
        self._json = json_data
        self.reason = reason
        self.headers = headers or {}
        if text is not None:
            self.text = text
            self.content = text.encode()
        elif json_data is not None:
            self.text = json.dumps(json_data)
            self.content = self.text.encode()
            self.headers.setdefault("Content-Type", "application/json")
        else:
            self.text = ""
            self.content = b""

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("no json")
        return self._json


class FakeSession:
    """Records requests and replays a scripted sequence of responses.

    ``responses`` may contain :class:`FakeResponse` objects or exception
    instances (which will be raised to simulate transport failures).
    """

    def __init__(self, responses: List[Any]) -> None:
        self._responses = list(responses)
        self.calls: List[Dict[str, Any]] = []
        self.closed = False

    def request(self, method, url, **kwargs):  # noqa: D401 - mimics requests API
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise AssertionError(f"unexpected extra request: {method} {url}")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    def close(self):
        self.closed = True


def make_client(responses: List[Any], **kwargs) -> OabpClient:
    session = FakeSession(responses)
    client = OabpClient(session=session, backoff_factor=0.0, **kwargs)
    # Make retries instantaneous regardless of jitter.
    client._sleep = lambda _seconds: None
    return client


# --------------------------------------------------------------------------- #
# Sample payloads
# --------------------------------------------------------------------------- #
MISSION_PAYLOAD = {
    "id": "m-001",
    "title": "Audit MyToken",
    "description": "GoPlus safety review for 0xabc",
    "reward": {"amount": 500, "currency": "AIGEN"},
    "verification_type": "oracle",
    "verification_params": {"oracle_description": "safety review of 0xabc"},
    "deadline": 4102444800,  # 2100-01-01, comfortably in the future
    "status": "open",
    "submissions": [],
}


# --------------------------------------------------------------------------- #
# list_missions
# --------------------------------------------------------------------------- #
def test_list_missions_array():
    client = make_client([FakeResponse(200, [MISSION_PAYLOAD])])
    missions = client.list_missions()
    assert len(missions) == 1
    m = missions[0]
    assert isinstance(m, Mission)
    assert m.id == "m-001"
    assert m.reward.amount == 500.0
    assert m.reward.currency is Currency.AIGEN
    assert m.verification_type is VerificationType.ORACLE
    assert m.verification_params.oracle_description == "safety review of 0xabc"
    assert m.is_open is True
    assert m.is_expired() is False
    # Correct endpoint hit.
    call = client._session.calls[0]
    assert call["method"] == "GET"
    assert call["url"].endswith("/api/missions")


def test_list_missions_envelope_and_status_filter():
    client = make_client([FakeResponse(200, {"missions": [MISSION_PAYLOAD]})])
    missions = client.list_missions(status="open")
    assert [m.id for m in missions] == ["m-001"]
    assert client._session.calls[0]["params"] == {"status": "open"}


def test_list_missions_bad_shape_raises():
    client = make_client([FakeResponse(200, 12345)])
    with pytest.raises(OabpError):
        client.list_missions()


# --------------------------------------------------------------------------- #
# get_mission
# --------------------------------------------------------------------------- #
def test_get_mission_with_resolution():
    payload = dict(MISSION_PAYLOAD)
    payload["status"] = "resolved"
    payload["submissions"] = [
        {"submitter_agent_id": "agent-x", "proof": "0xabc clean", "accepted": True}
    ]
    payload["resolution"] = {
        "winner_agent_id": "agent-x",
        "verified": True,
        "reward_paid": 497.5,
    }
    client = make_client([FakeResponse(200, payload)])
    m = client.get_mission("m-001")
    assert m.status is MissionStatus.RESOLVED
    assert m.submissions[0].submitter_agent_id == "agent-x"
    assert m.submissions[0].accepted is True
    assert m.resolution is not None
    assert m.resolution.verified is True
    assert m.resolution.reward_paid == 497.5
    assert client._session.calls[0]["url"].endswith("/api/missions/m-001")


def test_get_mission_not_found():
    client = make_client(
        [FakeResponse(404, {"error": "mission not found"}, reason="Not Found")]
    )
    with pytest.raises(OabpNotFoundError) as exc:
        client.get_mission("nope")
    assert exc.value.status_code == 404
    assert "not found" in str(exc.value).lower()


def test_get_mission_empty_id_validation():
    client = make_client([])  # no request should be made
    with pytest.raises(OabpValidationError):
        client.get_mission("  ")
    assert client._session.calls == []


# --------------------------------------------------------------------------- #
# create_mission
# --------------------------------------------------------------------------- #
def test_create_mission_builds_correct_body():
    created = dict(MISSION_PAYLOAD)
    created["id"] = "m-777"
    client = make_client([FakeResponse(201, created)], agent_id="creator-1")
    m = client.create_mission(
        title="Audit MyToken",
        description="desc",
        reward_amount=500,
        verification_type=VerificationType.ORACLE,
        deadline_hours=48,
        verification_params={"oracle_description": "safety review of 0xabc"},
    )
    assert m.id == "m-777"
    call = client._session.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/api/missions")
    body = call["json"]
    assert body["creator_agent_id"] == "creator-1"
    assert body["reward_currency"] == "AIGEN"  # enum serialised to value
    assert body["verification_type"] == "oracle"
    assert body["reward_amount"] == 500.0
    assert body["deadline_hours"] == 48.0
    assert body["verification_params"] == {"oracle_description": "safety review of 0xabc"}


def test_create_mission_unwraps_envelope():
    client = make_client(
        [FakeResponse(201, {"mission": {"id": "m-9", "reward": {"amount": 10}}})],
        agent_id="creator-1",
    )
    m = client.create_mission(
        title="t",
        description="d",
        reward_amount=10,
        verification_type="first_valid_match",
        deadline_hours=1,
    )
    assert m.id == "m-9"


def test_create_mission_requires_creator():
    client = make_client([])
    with pytest.raises(OabpValidationError):
        client.create_mission(
            title="t",
            description="d",
            reward_amount=10,
            verification_type="oracle",
            deadline_hours=1,
        )
    assert client._session.calls == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"reward_amount": 0},
        {"reward_amount": -5},
        {"deadline_hours": 0},
        {"title": ""},
    ],
)
def test_create_mission_argument_validation(kwargs):
    base = dict(
        title="t",
        description="d",
        reward_amount=10,
        verification_type="oracle",
        deadline_hours=1,
        creator_agent_id="c",
    )
    base.update(kwargs)
    client = make_client([])
    with pytest.raises(OabpValidationError):
        client.create_mission(**base)
    assert client._session.calls == []


def test_create_mission_not_retried():
    # Two 503s scripted, but create must NOT retry → first 503 surfaces.
    client = make_client(
        [FakeResponse(503, {"error": "down"}), FakeResponse(503, {"error": "down"})],
        agent_id="c",
    )
    with pytest.raises(OabpServerError):
        client.create_mission(
            title="t",
            description="d",
            reward_amount=10,
            verification_type="oracle",
            deadline_hours=1,
        )
    assert len(client._session.calls) == 1


# --------------------------------------------------------------------------- #
# submit
# --------------------------------------------------------------------------- #
def test_submit_first_valid_match():
    client = make_client(
        [FakeResponse(200, {"accepted": True, "matched": True})],
        agent_id="agent-x",
    )
    result = client.submit("m-001", proof="ANSWER-42")
    assert result == {"accepted": True, "matched": True}
    call = client._session.calls[0]
    assert call["url"].endswith("/missions/m-001/submit")
    assert call["json"] == {"submitter_agent_id": "agent-x", "proof": "ANSWER-42"}


def test_submit_explicit_agent_overrides_default():
    client = make_client([FakeResponse(200, {"accepted": False})], agent_id="default")
    client.submit("m-1", proof="x", submitter_agent_id="explicit")
    assert client._session.calls[0]["json"]["submitter_agent_id"] == "explicit"


def test_submit_requires_proof():
    client = make_client([], agent_id="a")
    with pytest.raises(OabpValidationError):
        client.submit("m-1", proof="")
    assert client._session.calls == []


def test_submit_requires_agent():
    client = make_client([])
    with pytest.raises(OabpValidationError):
        client.submit("m-1", proof="x")


def test_submit_non_dict_response_wrapped():
    client = make_client([FakeResponse(200, "queued")], agent_id="a")
    assert client.submit("m-1", proof="x") == {"result": "queued"}


# --------------------------------------------------------------------------- #
# stats & reputation
# --------------------------------------------------------------------------- #
def test_get_stats():
    client = make_client(
        [FakeResponse(200, {"resolved": 12, "open": 3, "lifetime_reward_aigen_paid": 108000})]
    )
    stats = client.get_stats()
    assert isinstance(stats, Stats)
    assert stats.resolved == 12
    assert stats.open == 3
    assert stats.lifetime_reward_aigen_paid == 108000.0


def test_get_reputation():
    client = make_client(
        [
            FakeResponse(
                200,
                {
                    "agent_id": "agent-x",
                    "aigen_balance": 1500,
                    "missions_won": 4,
                    "missions_created": 2,
                    "submissions": 9,
                },
            )
        ]
    )
    rep = client.get_reputation("agent-x")
    assert isinstance(rep, Reputation)
    assert rep.agent_id == "agent-x"
    assert rep.aigen_balance == 1500.0
    assert rep.missions_won == 4
    assert client._session.calls[0]["url"].endswith("/api/agents/agent-x/reputation")


def test_get_reputation_infers_agent_id_when_missing():
    client = make_client([FakeResponse(200, {"aigen_balance": 7})])
    rep = client.get_reputation("agent-y")
    assert rep.agent_id == "agent-y"
    assert rep.aigen_balance == 7.0


# --------------------------------------------------------------------------- #
# A2A + discovery
# --------------------------------------------------------------------------- #
def test_a2a_returns_result():
    client = make_client(
        [FakeResponse(200, {"jsonrpc": "2.0", "id": "1", "result": {"tasks": []}})]
    )
    result = client.a2a("tasks/list")
    assert result == {"tasks": []}
    body = client._session.calls[0]["json"]
    assert body["jsonrpc"] == "2.0"
    assert body["method"] == "tasks/list"
    assert client._session.calls[0]["url"].endswith("/api/a2a")


def test_a2a_send_message_shapes_payload():
    client = make_client(
        [FakeResponse(200, {"jsonrpc": "2.0", "id": "1", "result": {"taskId": "t1"}})]
    )
    out = client.a2a_send_message("hello", request_id="req-1")
    assert out == {"taskId": "t1"}
    body = client._session.calls[0]["json"]
    assert body["id"] == "req-1"
    assert body["method"] == "message/send"
    assert body["params"]["message"]["parts"][0]["text"] == "hello"
    assert body["params"]["message"]["role"] == "user"


def test_a2a_error_envelope_raises():
    client = make_client(
        [
            FakeResponse(
                200,
                {"jsonrpc": "2.0", "id": "1", "error": {"code": -32601, "message": "no method"}},
            )
        ]
    )
    with pytest.raises(OabpError) as exc:
        client.a2a("bogus/method")
    assert "no method" in str(exc.value)


def test_get_agent_card_and_jwks():
    client = make_client(
        [
            FakeResponse(200, {"name": "AIGEN Agent", "url": "https://x/api/a2a"}),
            FakeResponse(200, {"keys": [{"kty": "EC", "crv": "P-256"}]}),
        ]
    )
    card = client.get_agent_card()
    assert card["name"] == "AIGEN Agent"
    jwks = client.get_jwks()
    assert jwks["keys"][0]["crv"] == "P-256"
    assert client._session.calls[0]["url"].endswith("/.well-known/agent-card.json")
    assert client._session.calls[1]["url"].endswith("/.well-known/jwks.json")


# --------------------------------------------------------------------------- #
# Retry / backoff behaviour
# --------------------------------------------------------------------------- #
def test_retry_on_503_then_success():
    client = make_client(
        [
            FakeResponse(503, {"error": "starting"}),
            FakeResponse(503, {"error": "starting"}),
            FakeResponse(200, [MISSION_PAYLOAD]),
        ]
    )
    missions = client.list_missions()
    assert len(missions) == 1
    assert len(client._session.calls) == 3  # 2 retries + final success


def test_retry_exhausted_raises_server_error():
    client = make_client(
        [FakeResponse(503), FakeResponse(503), FakeResponse(503), FakeResponse(503)],
        max_retries=3,
    )
    with pytest.raises(OabpServerError) as exc:
        client.list_missions()
    assert exc.value.status_code == 503
    assert len(client._session.calls) == 4  # initial + 3 retries


def test_retry_on_connection_error_then_success():
    client = make_client(
        [
            requests.exceptions.ConnectionError("conn reset"),
            FakeResponse(200, {"resolved": 1, "open": 0, "lifetime_reward_aigen_paid": 0}),
        ]
    )
    stats = client.get_stats()
    assert stats.resolved == 1
    assert len(client._session.calls) == 2


def test_timeout_exhausted_raises_timeout_error():
    client = make_client(
        [requests.exceptions.Timeout(), requests.exceptions.Timeout()],
        max_retries=1,
    )
    with pytest.raises(OabpTimeoutError):
        client.get_stats()
    assert len(client._session.calls) == 2


def test_connection_error_exhausted_raises():
    client = make_client(
        [requests.exceptions.ConnectionError("x")], max_retries=0
    )
    with pytest.raises(OabpConnectionError):
        client.get_stats()


def test_rate_limit_honours_retry_after_then_succeeds(monkeypatch):
    slept: List[float] = []
    client = make_client(
        [
            FakeResponse(429, {"error": "slow down"}, headers={"Retry-After": "2"}),
            FakeResponse(200, {"resolved": 0, "open": 0, "lifetime_reward_aigen_paid": 0}),
        ]
    )
    client._sleep = lambda s: slept.append(s)
    client.get_stats()
    assert slept == [2.0]  # honoured Retry-After exactly


def test_rate_limit_exhausted_raises():
    client = make_client([FakeResponse(429), FakeResponse(429)], max_retries=1)
    with pytest.raises(OabpRateLimitError):
        client.get_stats()


def test_4xx_not_retried():
    # A 400 should surface immediately without consuming a second response.
    client = make_client([FakeResponse(400, {"error": "bad request"})])
    with pytest.raises(OabpError) as exc:
        client.list_missions()
    assert exc.value.status_code == 400
    assert len(client._session.calls) == 1


# --------------------------------------------------------------------------- #
# Client construction / lifecycle
# --------------------------------------------------------------------------- #
def test_base_url_trailing_slash_stripped():
    client = OabpClient(base_url="https://example.com/", session=FakeSession([]))
    assert client.base_url == "https://example.com"


def test_empty_base_url_rejected():
    with pytest.raises(OabpValidationError):
        OabpClient(base_url="")


def test_api_key_sets_auth_header():
    client = make_client([FakeResponse(200, [])], api_key="secret-token")
    client.list_missions()
    headers = client._session.calls[0]["headers"]
    assert headers["Authorization"] == "Bearer secret-token"
    assert headers["User-Agent"].startswith("oabp-python-sdk")


def test_context_manager_closes_owned_session():
    session = FakeSession([FakeResponse(200, [])])
    with OabpClient(session=session) as client:
        # externally-provided session is NOT owned, so it stays open
        client.list_missions()
    assert session.closed is False

    owned = OabpClient()
    real_session = owned._session
    owned.close()
    assert real_session is not None  # sanity: a real session existed


def test_error_str_and_attributes():
    err = OabpNotFoundError(
        "missing", status_code=404, request_url="https://x/api/missions/zz"
    )
    s = str(err)
    assert "missing" in s and "404" in s and "api/missions/zz" in s
    assert err.status_code == 404


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
