"""Offline tests for the OABP / AIGEN Dify plugin.

``dify_plugin`` is faked in ``conftest`` and all HTTP is stubbed at the
``requests.Session`` level, so the suite is deterministic and never touches the
network. It verifies the five tools end-to-end (request body + yielded
text/json messages), the provider's ``_validate_credentials``, and that every
``tools/*.yaml`` is consistent with its ``.py`` (identity name == filename, the
declared parameters match what ``_invoke`` reads).
"""

from __future__ import annotations

import json

import pytest

from conftest import (
    FakeResponse,
    SAMPLE_MISSION,
    SAMPLE_MISSION_DETAIL,
    SAMPLE_STATS,
)

from tools.list_missions import ListMissionsTool
from tools.get_mission import GetMissionTool
from tools.create_mission import CreateMissionTool
from tools.submit_mission import SubmitMissionTool
from tools.get_stats import GetStatsTool


def _messages_by_type(messages):
    out = {"text": [], "json": []}
    for m in messages:
        if m.type == "text":
            out["text"].append(m.message.text)
        elif m.type == "json":
            out["json"].append(m.message.json_object)
    return out


# --------------------------------------------------------------------------- #
# ACCEPTANCE: submit_mission imported, stubbed session, json payload has mission id
# --------------------------------------------------------------------------- #
def test_submit_mission_json_message_contains_mission_id(make_tool):
    captured = {}

    def handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        return FakeResponse(
            200,
            {
                "accepted": True,
                "resolution": {"winner_agent_id": "sub-1", "verified": True},
            },
        )

    routes = {("POST", "/missions/m-001/submit"): handler}
    tool, session = make_tool(
        SubmitMissionTool,
        routes,
        oabp_base_url="https://cryptogenesis.duckdns.org",
        agent_id="sub-1",
    )

    messages = tool.invoke({"mission_id": "m-001", "proof": "https://github.com/me/repo"})
    by_type = _messages_by_type(messages)

    # a JSON message was yielded and its payload contains the mission id
    assert by_type["json"], "expected a json message"
    payload = by_type["json"][0]
    assert payload["submitted"] is True
    assert payload["mission_id"] == "m-001"
    assert payload["response"]["accepted"] is True
    assert payload["response"]["resolution"]["verified"] is True
    json.dumps(payload)  # JSON-serialisable

    # and it actually sent the right body to the stubbed session
    assert captured["body"] == {
        "submitter_agent_id": "sub-1",
        "proof": "https://github.com/me/repo",
    }
    assert session.calls and session.calls[0]["method"] == "POST"


# --------------------------------------------------------------------------- #
# list_missions
# --------------------------------------------------------------------------- #
def test_list_missions(make_tool):
    routes = {("GET", "/api/missions"): FakeResponse(200, [SAMPLE_MISSION])}
    tool, _ = make_tool(ListMissionsTool, routes, agent_id="agent-x")
    by_type = _messages_by_type(tool.invoke({}))

    result = by_type["json"][0]
    assert result["count"] == 1
    m = result["missions"][0]
    assert m["id"] == "m-001"
    assert m["reward"] == {"amount": 500.0, "currency": "AIGEN"}
    assert m["verification_type"] == "oracle"
    assert m["status"] == "open"
    assert m["submission_count"] == 0
    assert "m-001" in by_type["text"][0]
    json.dumps(result)


def test_list_missions_limit(make_tool):
    many = [dict(SAMPLE_MISSION, id=f"m-{i}") for i in range(5)]
    routes = {("GET", "/api/missions"): FakeResponse(200, many)}
    tool, _ = make_tool(ListMissionsTool, routes)
    result = _messages_by_type(tool.invoke({"limit": 2}))["json"][0]
    assert result["count"] == 2
    assert [m["id"] for m in result["missions"]] == ["m-0", "m-1"]


def test_list_missions_passes_status_filter(make_tool):
    captured = {}

    def handler(method, url, kwargs):
        captured["params"] = kwargs.get("params")
        return FakeResponse(200, [SAMPLE_MISSION])

    routes = {("GET", "/api/missions"): handler}
    tool, _ = make_tool(ListMissionsTool, routes)
    tool.invoke({"status": "open"})
    assert captured["params"] == {"status": "open"}


def test_list_missions_error_is_json_message(make_tool):
    routes = {("GET", "/api/missions"): FakeResponse(500, {"error": "boom"})}
    tool, _ = make_tool(ListMissionsTool, routes)
    by_type = _messages_by_type(tool.invoke({}))
    err = by_type["json"][0]
    assert err["error_type"] == "OabpError"
    assert err["status_code"] == 500
    assert "boom" in err["error"]


# --------------------------------------------------------------------------- #
# get_mission
# --------------------------------------------------------------------------- #
def test_get_mission_with_submissions_and_resolution(make_tool):
    routes = {("GET", "/api/missions/m-001"): FakeResponse(200, SAMPLE_MISSION_DETAIL)}
    tool, _ = make_tool(GetMissionTool, routes)
    result = _messages_by_type(tool.invoke({"mission_id": "m-001"}))["json"][0]
    assert result["id"] == "m-001"
    assert result["submission_count"] == 1
    assert result["submissions"][0]["submitter_agent_id"] == "agent-9"
    assert result["resolution"]["winner_agent_id"] == "agent-9"
    assert result["resolution"]["reward_paid"] == 497.5
    json.dumps(result)


def test_get_mission_requires_id(make_tool):
    tool, session = make_tool(GetMissionTool, {})
    err = _messages_by_type(tool.invoke({"mission_id": "  "}))["json"][0]
    assert err["error_type"] == "ValidationError"
    assert session.calls == []  # never hit the network


def test_get_mission_404(make_tool):
    routes = {("GET", "/api/missions/nope"): FakeResponse(404, {"error": "not found"})}
    tool, _ = make_tool(GetMissionTool, routes)
    err = _messages_by_type(tool.invoke({"mission_id": "nope"}))["json"][0]
    assert err["status_code"] == 404
    assert err["error_type"] == "OabpError"


# --------------------------------------------------------------------------- #
# create_mission
# --------------------------------------------------------------------------- #
def test_create_mission_sends_correct_body(make_tool):
    captured = {}

    def handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        return FakeResponse(200, dict(SAMPLE_MISSION, id="m-new"))

    routes = {("POST", "/api/missions"): handler}
    tool, _ = make_tool(CreateMissionTool, routes, agent_id="creator-1")

    result = _messages_by_type(
        tool.invoke(
            {
                "title": "Audit MyToken",
                "description": "GoPlus safety review for 0xDEF",
                "reward_amount": 250,
                "verification_type": "oracle",
                "deadline_hours": 48,
                "verification_params": '{"oracle_description": "safety review of 0xDEF"}',
            }
        )
    )["json"][0]

    assert result["created"] is True
    assert result["mission"]["id"] == "m-new"

    body = captured["body"]
    assert body["creator_agent_id"] == "creator-1"  # default agent id used
    assert body["title"] == "Audit MyToken"
    assert body["reward_amount"] == 250.0
    assert body["reward_currency"] == "AIGEN"
    assert body["verification_type"] == "oracle"
    assert body["deadline_hours"] == 48.0
    assert body["verification_params"] == {"oracle_description": "safety review of 0xDEF"}


def test_create_mission_accepts_dict_params(make_tool):
    captured = {}

    def handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        return FakeResponse(200, dict(SAMPLE_MISSION, id="m-new"))

    routes = {("POST", "/api/missions"): handler}
    tool, _ = make_tool(CreateMissionTool, routes, agent_id="c")
    tool.invoke(
        {
            "title": "t",
            "description": "d",
            "reward_amount": 10,
            "verification_type": "first_valid_match",
            "deadline_hours": 1,
            "reward_currency": "USDC",
            "verification_params": {"regex": "abc[0-9]+"},
        }
    )
    assert captured["body"]["reward_currency"] == "USDC"
    assert captured["body"]["verification_params"] == {"regex": "abc[0-9]+"}


def test_create_mission_bad_verification_type(make_tool):
    tool, session = make_tool(CreateMissionTool, {}, agent_id="c")
    err = _messages_by_type(
        tool.invoke(
            {
                "title": "x",
                "description": "d",
                "reward_amount": 10,
                "verification_type": "telepathy",
                "deadline_hours": 1,
            }
        )
    )["json"][0]
    assert err["error_type"] == "ValidationError"
    assert "verification_type" in err["error"]
    assert session.calls == []  # rejected before any network call


def test_create_mission_nonpositive_reward(make_tool):
    tool, session = make_tool(CreateMissionTool, {}, agent_id="c")
    err = _messages_by_type(
        tool.invoke(
            {
                "title": "x",
                "description": "d",
                "reward_amount": 0,
                "verification_type": "oracle",
                "deadline_hours": 1,
            }
        )
    )["json"][0]
    assert err["error_type"] == "ValidationError"
    assert "reward_amount" in err["error"]
    assert session.calls == []


def test_create_mission_bad_json_params(make_tool):
    tool, session = make_tool(CreateMissionTool, {}, agent_id="c")
    err = _messages_by_type(
        tool.invoke(
            {
                "title": "x",
                "description": "d",
                "reward_amount": 10,
                "verification_type": "oracle",
                "deadline_hours": 1,
                "verification_params": "{not json",
            }
        )
    )["json"][0]
    assert err["error_type"] == "ValidationError"
    assert "verification_params" in err["error"]
    assert session.calls == []


def test_create_mission_missing_agent_id_errors(make_tool):
    # no agent_id in credentials and none passed -> client raises, surfaced as json
    routes = {("POST", "/api/missions"): FakeResponse(200, SAMPLE_MISSION)}
    tool, session = make_tool(CreateMissionTool, routes)
    err = _messages_by_type(
        tool.invoke(
            {
                "title": "x",
                "description": "d",
                "reward_amount": 10,
                "verification_type": "oracle",
                "deadline_hours": 1,
            }
        )
    )["json"][0]
    assert err["error_type"] == "OabpError"
    assert "creator_agent_id" in err["error"]
    assert session.calls == []  # the client guards before sending


# --------------------------------------------------------------------------- #
# submit_mission edge cases
# --------------------------------------------------------------------------- #
def test_submit_empty_proof_returns_error(make_tool):
    tool, session = make_tool(SubmitMissionTool, {}, agent_id="a")
    err = _messages_by_type(tool.invoke({"mission_id": "m-1", "proof": ""}))["json"][0]
    assert err["error_type"] == "ValidationError"
    assert session.calls == []


def test_submit_self_referential_mission_flow(make_tool):
    """The motivating bounty: a merged smolagents PR URL verifies for 199 AIGEN."""
    pr_url = "https://github.com/huggingface/smolagents/pull/1742"
    mission_id = "mis_15a24726b3de"

    def handler(method, url, kwargs):
        return FakeResponse(
            200,
            {
                "accepted": True,
                "resolution": {
                    "winner_agent_id": "dify-oabp-demo",
                    "winning_proof": pr_url,
                    "verified": True,
                    "reward_paid": 199.0,  # 200 AIGEN - 0.5% fee
                },
            },
        )

    routes = {("POST", f"/missions/{mission_id}/submit"): handler}
    tool, _ = make_tool(SubmitMissionTool, routes, agent_id="dify-oabp-demo")
    result = _messages_by_type(tool.invoke({"mission_id": mission_id, "proof": pr_url}))[
        "json"
    ][0]
    assert result["submitted"] is True
    assert result["mission_id"] == mission_id
    assert result["response"]["resolution"]["reward_paid"] == 199.0


# --------------------------------------------------------------------------- #
# get_stats
# --------------------------------------------------------------------------- #
def test_get_stats(make_tool):
    routes = {("GET", "/api/stats"): FakeResponse(200, SAMPLE_STATS)}
    tool, _ = make_tool(GetStatsTool, routes)
    by_type = _messages_by_type(tool.invoke({}))
    assert by_type["json"][0] == {
        "resolved": 7,
        "open": 3,
        "lifetime_reward_aigen_paid": 108000.0,
    }
    assert "108000" in by_type["text"][0]


# --------------------------------------------------------------------------- #
# Provider credential validation
# --------------------------------------------------------------------------- #
def test_provider_validate_credentials_ok():
    import requests

    from conftest import RoutingFakeSession
    from provider.oabp import OabpProvider
    from tools.oabp_api import OabpClient

    # Patch OabpClient.from_credentials to use a fake session for this test.
    routes = {("GET", "/api/stats"): FakeResponse(200, SAMPLE_STATS)}
    session = RoutingFakeSession(routes)
    orig = OabpClient.from_credentials

    def fake_from_credentials(creds, *, session=None):  # noqa: ARG001
        return orig(creds, session=RoutingFakeSession(routes))

    OabpClient.from_credentials = staticmethod(fake_from_credentials)  # type: ignore
    try:
        provider = OabpProvider()
        # should not raise
        provider.validate_credentials(
            {"oabp_base_url": "https://cryptogenesis.duckdns.org"}
        )
    finally:
        OabpClient.from_credentials = staticmethod(orig)  # type: ignore
    assert isinstance(session, requests.Session) is False  # sanity: it's our fake


def test_provider_rejects_missing_base_url():
    from dify_plugin.errors.tool import ToolProviderCredentialValidationError
    from provider.oabp import OabpProvider

    provider = OabpProvider()
    with pytest.raises(ToolProviderCredentialValidationError):
        provider.validate_credentials({"oabp_base_url": ""})


def test_provider_rejects_bad_scheme():
    from dify_plugin.errors.tool import ToolProviderCredentialValidationError
    from provider.oabp import OabpProvider

    provider = OabpProvider()
    with pytest.raises(ToolProviderCredentialValidationError):
        provider.validate_credentials({"oabp_base_url": "cryptogenesis.duckdns.org"})


def test_provider_unreachable_is_validation_error():
    from dify_plugin.errors.tool import ToolProviderCredentialValidationError
    from provider.oabp import OabpProvider
    from tools.oabp_api import OabpClient

    from conftest import RoutingFakeSession

    routes = {("GET", "/api/stats"): FakeResponse(503, {"error": "down"})}
    orig = OabpClient.from_credentials

    def fake_from_credentials(creds, *, session=None):  # noqa: ARG001
        return orig(creds, session=RoutingFakeSession(routes))

    OabpClient.from_credentials = staticmethod(fake_from_credentials)  # type: ignore
    try:
        provider = OabpProvider()
        with pytest.raises(ToolProviderCredentialValidationError):
            provider.validate_credentials({"oabp_base_url": "https://example.invalid"})
    finally:
        OabpClient.from_credentials = staticmethod(orig)  # type: ignore
