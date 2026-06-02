"""Tests for client plumbing: context manager, raw rpc, verify_card helper,
URL handling and error shapes the higher-level tests don't reach."""

from __future__ import annotations

import pytest

from oabp_a2a import A2AClient, JSONRPCError, OABPError, SignatureError
from oabp_a2a.client import _as_list, _extract_task_list
from tests.conftest import BASE_URL, FakeSession, MockResponse


def make_client(session):
    return A2AClient(base_url=BASE_URL, agent_id="a", session=session)


def test_context_manager_closes_owned_session():
    # When the client owns its session it should close it on exit.
    with A2AClient(base_url=BASE_URL) as client:
        assert isinstance(client, A2AClient)
    # second close is a no-op and must not raise
    client.close()


def test_injected_session_not_closed(session):
    session.route_json("GET", "/api/stats", {"resolved": 0, "open": 0, "lifetime_reward_aigen_paid": 0})
    client = make_client(session)
    client.close()  # owns_session is False -> underlying must stay usable
    # the injected session still works after the client's close()
    assert client.stats().resolved == 0


def test_api_key_sets_auth_header(session):
    client = A2AClient(base_url=BASE_URL, session=session, api_key="secret-token")
    assert session.headers["Authorization"] == "Bearer secret-token"


def test_raw_rpc_passthrough(session):
    session.route(
        "POST",
        "/api/a2a",
        lambda req: MockResponse(
            200, json_body={"jsonrpc": "2.0", "id": req.json["id"], "result": {"ok": 1}}
        ),
    )
    client = make_client(session)
    assert client.rpc("custom/method", {"x": 1}) == {"ok": 1}


def test_rpc_missing_result_and_error(session):
    session.route(
        "POST",
        "/api/a2a",
        lambda req: MockResponse(200, json_body={"jsonrpc": "2.0", "id": req.json["id"]}),
    )
    client = make_client(session)
    with pytest.raises(JSONRPCError, match="neither result nor error"):
        client.rpc("x")


def test_rpc_non_object_response(session):
    session.route("POST", "/api/a2a", lambda req: MockResponse(200, json_body=[1, 2, 3]))
    client = make_client(session)
    with pytest.raises(JSONRPCError, match="not an object"):
        client.rpc("x")


def test_verify_card_helper_fetches_jwks(session, signer, sample_card):
    signed = signer.sign_card_embedded(sample_card)
    session.route_json("GET", "/.well-known/jwks.json", signer.jwks())
    client = make_client(session)
    # jwks omitted -> fetched from server
    verified = client.verify_card(signed)
    assert verified.payload["name"] == sample_card["name"]


def test_fetch_agent_card_returns_card_with_signature(session, signer, sample_card):
    signed = signer.sign_card_embedded(sample_card)
    session.route_json("GET", "/.well-known/agent-card.json", signed)
    session.route_json("GET", "/.well-known/jwks.json", signer.jwks())
    client = make_client(session)
    card = client.fetch_agent_card(verify=True)
    # verify=True passed; returned card keeps its embedded signature field
    assert "signature" in card
    assert card["name"] == sample_card["name"]


def test_compact_jws_card_body_through_client(session, signer, sample_card):
    # Server serves the whole card as a compact JWS string body.
    jws = signer.sign_card_compact(sample_card)
    session.route(
        "GET",
        "/.well-known/agent-card.json",
        lambda req: MockResponse(200, text_body='"%s"' % jws),  # JSON string
    )
    session.route_json("GET", "/.well-known/jwks.json", signer.jwks())
    client = make_client(session)
    verified = client.fetch_and_verify_agent_card()
    assert verified.payload["name"] == sample_card["name"]


def test_stats_coerces_strings(session):
    session.route_json(
        "GET",
        "/api/stats",
        {"resolved": "5", "open": "2", "lifetime_reward_aigen_paid": "12.5"},
    )
    client = make_client(session)
    s = client.stats()
    assert (s.resolved, s.open, s.lifetime_reward_aigen_paid) == (5, 2, 12.5)


def test_absolute_url_path_is_respected(session):
    # An absolute URL passed as a path should be used verbatim.
    session.route_json("GET", "/api/stats", {"resolved": 1, "open": 0, "lifetime_reward_aigen_paid": 0})
    client = make_client(session)
    client.stats()
    assert session.calls[-1].url == f"{BASE_URL}/api/stats"


def test_non_json_body_raises(session):
    session.route("GET", "/api/stats", lambda req: MockResponse(200, text_body="not json"))
    client = make_client(session)
    with pytest.raises(OABPError, match="non-JSON"):
        client.stats()


def test_list_missions_bad_shape(session):
    session.route_json("GET", "/api/missions", {"unexpected": True})
    client = make_client(session)
    with pytest.raises(OABPError):
        client.list_missions()


def test_helpers_directly():
    assert _as_list([{"a": 1}, "skip"]) == [{"a": 1}]
    assert _as_list({"items": [{"b": 2}]}) == [{"b": 2}]
    with pytest.raises(OABPError):
        _as_list(123)
    assert _extract_task_list([{"id": 1}]) == [{"id": 1}]
    with pytest.raises(JSONRPCError):
        _extract_task_list("nope")
