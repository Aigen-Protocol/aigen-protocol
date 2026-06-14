"""Tests for the missions REST surface and the agent-card fetch+verify flow."""

from __future__ import annotations

import pytest

from oabp_a2a import A2AClient, HTTPError, MissionError, SignatureError
from tests.conftest import BASE_URL, MockResponse


def make_client(session, agent_id="agent-007"):
    return A2AClient(base_url=BASE_URL, agent_id=agent_id, session=session)


# --------------------------------------------------------------------------- #
# list / get
# --------------------------------------------------------------------------- #
def test_list_missions(session):
    session.route_json(
        "GET",
        "/api/missions",
        [
            {
                "id": "m1",
                "title": "Safety review of token 0xabc",
                "description": "Run a GoPlus safety review.",
                "reward": {"amount": 500, "currency": "AIGEN"},
                "verification_type": "oracle",
                "verification_params": {"oracle_description": "GoPlus safety review"},
                "deadline": 1893456000,
                "status": "open",
                "submissions": [],
            },
            {
                "id": "m2",
                "title": "Find the magic word",
                "reward": {"amount": 10, "currency": "USDC"},
                "verification_type": "first_valid_match",
                "verification_params": {"regex": "^alpha-[0-9]+$"},
                "status": "open",
                "submissions": [{"submitter_agent_id": "x", "proof": "alpha-1"}],
            },
        ],
    )
    client = make_client(session)
    missions = client.list_missions()
    assert [m.id for m in missions] == ["m1", "m2"]
    assert missions[0].reward.amount == 500
    assert missions[0].reward.currency == "AIGEN"
    assert missions[0].oracle_description == "GoPlus safety review"
    assert missions[1].regex == "^alpha-[0-9]+$"
    assert missions[1].submissions[0].proof == "alpha-1"


def test_list_missions_wrapped(session):
    session.route_json("GET", "/api/missions", {"missions": [{"id": "only"}]})
    client = make_client(session)
    assert client.list_missions()[0].id == "only"


def test_get_mission_detail(session):
    session.route_json(
        "GET",
        "/api/missions/m1",
        {
            "id": "m1",
            "title": "t",
            "reward": {"amount": 1, "currency": "AIGEN"},
            "verification_type": "creator_judges",
            "verification_params": {},
            "status": "resolved",
            "submissions": [{"submitter_agent_id": "w", "proof": "https://x/y"}],
            "resolution": {"winner": "w", "paid": 1},
        },
    )
    client = make_client(session)
    m = client.get_mission("m1")
    assert m.status == "resolved"
    assert m.resolution["winner"] == "w"
    assert m.submissions[0].proof == "https://x/y"


# --------------------------------------------------------------------------- #
# create
# --------------------------------------------------------------------------- #
def test_create_mission_builds_body(session):
    captured = {}

    def handler(req):
        captured["body"] = req.json
        return MockResponse(200, json_body={"id": "new-1", **req.json, "status": "open"})

    session.route("POST", "/api/missions", handler)
    client = make_client(session)

    m = client.create_mission(
        title="Repo deliverable",
        description="Ship a Go repo implementing X.",
        reward_amount=250,
        verification_type="oracle",
        verification_params={"oracle_description": "GitHub repo deliverable"},
        deadline_hours=48,
    )

    body = captured["body"]
    assert body["creator_agent_id"] == "agent-007"
    assert body["reward_currency"] == "AIGEN"
    assert body["verification_type"] == "oracle"
    assert body["deadline_hours"] == 48
    assert m.id == "new-1"


def test_create_first_valid_match_requires_regex(session):
    client = make_client(session)
    with pytest.raises(MissionError, match="regex"):
        client.create_mission(
            "t", "d", 1, "first_valid_match", verification_params={}
        )


def test_create_rejects_bad_regex(session):
    client = make_client(session)
    with pytest.raises(MissionError, match="regex"):
        client.create_mission(
            "t", "d", 1, "first_valid_match", verification_params={"regex": "("}
        )


def test_create_rejects_unknown_verification_type(session):
    client = make_client(session)
    with pytest.raises(MissionError, match="verification_type"):
        client.create_mission("t", "d", 1, "magic")


def test_create_without_agent_id_errors(session):
    client = A2AClient(base_url=BASE_URL, session=session)  # no agent_id
    with pytest.raises(MissionError, match="creator_agent_id"):
        client.create_mission("t", "d", 1, "creator_judges")


# --------------------------------------------------------------------------- #
# submit
# --------------------------------------------------------------------------- #
def test_submit_deliverable(session):
    captured = {}

    def handler(req):
        captured["body"] = req.json
        return MockResponse(
            200,
            json_body={"accepted": True, "resolution": {"winner": "agent-007", "paid": 250}},
        )

    session.route("POST", "/missions/m1/submit", handler)
    client = make_client(session)

    res = client.submit("m1", "https://github.com/me/repo")
    assert captured["body"] == {
        "submitter_agent_id": "agent-007",
        "proof": "https://github.com/me/repo",
    }
    assert res["resolution"]["paid"] == 250


def test_submit_without_agent_id_errors(session):
    client = A2AClient(base_url=BASE_URL, session=session)
    with pytest.raises(MissionError, match="submitter_agent_id"):
        client.submit("m1", "proof")


# --------------------------------------------------------------------------- #
# stats
# --------------------------------------------------------------------------- #
def test_stats(session):
    session.route_json(
        "GET", "/api/stats", {"resolved": 42, "open": 7, "lifetime_reward_aigen_paid": 108000.5}
    )
    client = make_client(session)
    s = client.stats()
    assert s.resolved == 42
    assert s.open == 7
    assert s.lifetime_reward_aigen_paid == 108000.5


# --------------------------------------------------------------------------- #
# HTTP error surface
# --------------------------------------------------------------------------- #
def test_http_error_surfaces(session):
    session.route_json("GET", "/api/missions", {"error": "boom"}, status=500)
    client = make_client(session)
    with pytest.raises(HTTPError) as exc:
        client.list_missions()
    assert exc.value.status_code == 500


def test_404_on_get_mission(session):
    # no route registered -> FakeSession returns 404
    client = make_client(session)
    with pytest.raises(HTTPError) as exc:
        client.get_mission("ghost")
    assert exc.value.status_code == 404


# --------------------------------------------------------------------------- #
# agent card fetch + verify (end-to-end through the client + real crypto)
# --------------------------------------------------------------------------- #
def test_fetch_and_verify_agent_card(session, signer, sample_card):
    signed = signer.sign_card_embedded(sample_card)
    session.route_json("GET", "/.well-known/agent-card.json", signed)
    session.route_json("GET", "/.well-known/jwks.json", signer.jwks())

    client = make_client(session)
    verified = client.fetch_and_verify_agent_card()
    assert verified.payload["name"] == sample_card["name"]
    assert "signature" not in verified.payload


def test_fetch_agent_card_verify_true_raises_on_tamper(session, signer, sample_card):
    signed = signer.sign_card_embedded(sample_card)
    signed["url"] = "https://evil.example/api/a2a"  # tamper after signing
    session.route_json("GET", "/.well-known/agent-card.json", signed)
    session.route_json("GET", "/.well-known/jwks.json", signer.jwks())

    client = make_client(session)
    with pytest.raises(SignatureError):
        client.fetch_agent_card(verify=True)


def test_fetch_agent_card_verify_false_skips(session, signer, sample_card):
    signed = signer.sign_card_embedded(sample_card)
    signed["name"] = "unsigned-mutation"
    session.route_json("GET", "/.well-known/agent-card.json", signed)
    # Note: no JWKS route needed when verify=False.
    client = make_client(session)
    card = client.fetch_agent_card(verify=False)
    assert card["name"] == "unsigned-mutation"
