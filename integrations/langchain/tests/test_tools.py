"""Offline unit tests for the langchain_oabp integration.

All HTTP is mocked via the ``RoutingFakeSession`` injected into the underlying
OABP SDK client (see conftest), so the suite is deterministic and never touches
the network. The LLM is a real ``langchain_core.BaseChatModel`` subclass that
supports ``bind_tools`` but emits scripted tool calls.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ValidationError

import langchain_oabp
from langchain_oabp import (
    CreateMissionArgs,
    OabpToolkit,
    get_tools,
    tool_names,
)
from langchain_oabp.schemas import (
    GetMissionArgs,
    ListMissionsArgs,
    StatsArgs,
    SubmitMissionArgs,
)
from langchain_oabp.tools import mission_to_dict, stats_to_dict

from conftest import (
    FakeResponse,
    SAMPLE_MISSION,
    SAMPLE_MISSION_DETAIL,
    SAMPLE_STATS,
)

EXPECTED_NAMES = [
    "oabp_list_missions",
    "oabp_get_mission",
    "oabp_create_mission",
    "oabp_submit_mission",
    "oabp_get_stats",
]


# --------------------------------------------------------------------------- #
# Discovery / wiring
# --------------------------------------------------------------------------- #
def test_get_tools_importable_and_named():
    tools = get_tools(agent_id="agent-x")
    assert [t.name for t in tools] == EXPECTED_NAMES
    assert tool_names() == EXPECTED_NAMES


def test_every_tool_has_args_schema():
    """Acceptance: each tool exposes a Pydantic args_schema."""
    for tool in get_tools(agent_id="agent-x"):
        assert tool.args_schema is not None, f"{tool.name} has no args_schema"
        assert issubclass(tool.args_schema, BaseModel)
        # description is non-trivial so the LLM understands the tool
        assert tool.description and len(tool.description) > 20


def test_args_schema_field_mapping():
    schemas = {t.name: t.args_schema for t in get_tools()}
    assert schemas["oabp_list_missions"] is ListMissionsArgs
    assert schemas["oabp_get_mission"] is GetMissionArgs
    assert schemas["oabp_create_mission"] is CreateMissionArgs
    assert schemas["oabp_submit_mission"] is SubmitMissionArgs
    assert schemas["oabp_get_stats"] is StatsArgs
    # stats takes no args
    assert get_tools()[-1].args == {}


def test_toolkit_get_tools_matches_function(make_client):
    client, _ = make_client({})
    tk = OabpToolkit(client=client)
    assert [t.name for t in tk.get_tools()] == EXPECTED_NAMES
    # from_credentials builds its own client
    tk2 = OabpToolkit.from_credentials(agent_id="a")
    assert [t.name for t in tk2.get_tools()] == EXPECTED_NAMES


def test_toolkit_context_manager_closes(make_client):
    # The SDK client only closes sessions it *owns*; an injected session is left
    # alone by design. So verify the toolkit propagates close() to the client.
    client, _ = make_client({})
    closed = {"n": 0}
    original_close = client.close

    def spy_close():
        closed["n"] += 1
        original_close()

    client.close = spy_close  # type: ignore[method-assign]
    with OabpToolkit(client=client) as tk:
        assert len(tk.get_tools()) == 5
    assert closed["n"] == 1


# --------------------------------------------------------------------------- #
# Read tools
# --------------------------------------------------------------------------- #
def test_list_missions_tool(make_client):
    routes = {("GET", "/api/missions"): FakeResponse(200, [SAMPLE_MISSION])}
    client, session = make_client(routes, agent_id="agent-x")
    tool = {t.name: t for t in get_tools(client=client)}["oabp_list_missions"]

    out = tool.invoke({})
    assert out["count"] == 1
    m = out["missions"][0]
    assert m["id"] == "m-001"
    assert m["reward"] == {"amount": 500.0, "currency": "AIGEN"}
    assert m["verification_type"] == "oracle"
    assert m["status"] == "open"
    # result must be JSON-serialisable (no dataclasses/enums leaking)
    json.dumps(out)


def test_list_missions_limit(make_client):
    many = [dict(SAMPLE_MISSION, id=f"m-{i}") for i in range(5)]
    routes = {("GET", "/api/missions"): FakeResponse(200, many)}
    client, _ = make_client(routes)
    tool = {t.name: t for t in get_tools(client=client)}["oabp_list_missions"]
    out = tool.invoke({"limit": 2})
    assert out["count"] == 2
    assert [m["id"] for m in out["missions"]] == ["m-0", "m-1"]


def test_get_mission_tool_with_submissions_and_resolution(make_client):
    routes = {("GET", "/api/missions/m-001"): FakeResponse(200, SAMPLE_MISSION_DETAIL)}
    client, _ = make_client(routes)
    tool = {t.name: t for t in get_tools(client=client)}["oabp_get_mission"]
    out = tool.invoke({"mission_id": "m-001"})
    assert out["id"] == "m-001"
    assert out["submission_count"] == 1
    assert out["submissions"][0]["submitter_agent_id"] == "agent-9"
    assert out["resolution"]["winner_agent_id"] == "agent-9"
    assert out["resolution"]["reward_paid"] == 497.5
    json.dumps(out)


def test_get_stats_tool(make_client):
    routes = {("GET", "/api/stats"): FakeResponse(200, SAMPLE_STATS)}
    client, _ = make_client(routes)
    tool = {t.name: t for t in get_tools(client=client)}["oabp_get_stats"]
    out = tool.invoke({})
    assert out == {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000.0}


# --------------------------------------------------------------------------- #
# Write tools — assert the body the SDK sends to the server
# --------------------------------------------------------------------------- #
def test_create_mission_tool_sends_correct_body(make_client):
    captured = {}

    def handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        # echo back a created mission
        return FakeResponse(200, dict(SAMPLE_MISSION, id="m-new"))

    routes = {("POST", "/api/missions"): handler}
    client, _ = make_client(routes, agent_id="creator-1")
    tool = {t.name: t for t in get_tools(client=client)}["oabp_create_mission"]

    out = tool.invoke(
        {
            "title": "Audit MyToken",
            "description": "GoPlus safety review for 0xDEF",
            "reward_amount": 250,
            "verification_type": "oracle",
            "deadline_hours": 48,
            "verification_params": {"oracle_description": "safety review of 0xDEF"},
        }
    )
    assert out["created"] is True
    assert out["mission"]["id"] == "m-new"

    body = captured["body"]
    assert body["creator_agent_id"] == "creator-1"  # default agent_id used
    assert body["title"] == "Audit MyToken"
    assert body["reward_amount"] == 250.0
    assert body["reward_currency"] == "AIGEN"
    assert body["verification_type"] == "oracle"
    assert body["deadline_hours"] == 48.0
    assert body["verification_params"] == {"oracle_description": "safety review of 0xDEF"}


def test_submit_mission_tool_sends_correct_body(make_client):
    captured = {}

    def handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        return FakeResponse(200, {"accepted": True, "resolution": {"winner_agent_id": "sub-1"}})

    routes = {("POST", "/missions/m-001/submit"): handler}
    client, _ = make_client(routes, agent_id="sub-1")
    tool = {t.name: t for t in get_tools(client=client)}["oabp_submit_mission"]

    out = tool.invoke({"mission_id": "m-001", "proof": "https://github.com/me/repo"})
    assert out["submitted"] is True
    assert out["mission_id"] == "m-001"
    assert out["response"]["accepted"] is True

    body = captured["body"]
    assert body["submitter_agent_id"] == "sub-1"
    assert body["proof"] == "https://github.com/me/repo"


# --------------------------------------------------------------------------- #
# Error handling — SDK errors become structured results, not exceptions
# --------------------------------------------------------------------------- #
def test_get_mission_404_returns_error_dict(make_client):
    routes = {("GET", "/api/missions/nope"): FakeResponse(404, {"error": "not found"})}
    client, _ = make_client(routes, max_retries=0)
    tool = {t.name: t for t in get_tools(client=client)}["oabp_get_mission"]
    out = tool.invoke({"mission_id": "nope"})
    assert out["error_type"] == "OabpNotFoundError"
    assert out["status_code"] == 404
    json.dumps(out)


def test_list_missions_server_error_returns_error_dict(make_client):
    routes = {("GET", "/api/missions"): FakeResponse(500, {"error": "boom"})}
    client, _ = make_client(routes, max_retries=0)
    tool = {t.name: t for t in get_tools(client=client)}["oabp_list_missions"]
    out = tool.invoke({})
    assert out["error_type"] == "OabpServerError"
    assert out["status_code"] == 500


# --------------------------------------------------------------------------- #
# Schema-level validation (these fire before any network call)
# --------------------------------------------------------------------------- #
def test_create_schema_rejects_bad_verification_type():
    with pytest.raises(ValidationError):
        CreateMissionArgs(
            title="x",
            description="d",
            reward_amount=10,
            verification_type="telepathy",
            deadline_hours=1,
        )


def test_create_schema_rejects_nonpositive_reward():
    with pytest.raises(ValidationError):
        CreateMissionArgs(
            title="x",
            description="d",
            reward_amount=0,
            verification_type="oracle",
            deadline_hours=1,
        )


def test_create_schema_normalises_currency_case():
    args = CreateMissionArgs(
        title="x",
        description="d",
        reward_amount=10,
        verification_type="first_valid_match",
        deadline_hours=1,
        reward_currency="usdc",
    )
    assert args.reward_currency == "USDC"


def test_submit_schema_requires_nonempty_proof():
    with pytest.raises(ValidationError):
        SubmitMissionArgs(mission_id="m-1", proof="")


def test_get_schema_strips_and_requires_id():
    assert GetMissionArgs(mission_id="  m-1 ").mission_id == "m-1"
    with pytest.raises(ValidationError):
        GetMissionArgs(mission_id="   ")


def test_stats_schema_takes_no_args():
    StatsArgs()  # ok
    with pytest.raises(ValidationError):
        StatsArgs(unexpected=1)


# --------------------------------------------------------------------------- #
# Serialiser helpers
# --------------------------------------------------------------------------- #
def test_mission_to_dict_is_json_serialisable():
    from langchain_oabp import Mission

    d = mission_to_dict(Mission.from_dict(SAMPLE_MISSION_DETAIL))
    json.dumps(d)  # must not raise
    assert d["verification_type"] == "oracle"  # enum -> str
    assert d["reward"]["currency"] == "AIGEN"


def test_stats_to_dict():
    from langchain_oabp import Stats

    d = stats_to_dict(Stats.from_dict(SAMPLE_STATS))
    assert d == {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000.0}


# --------------------------------------------------------------------------- #
# THE smoke test — bind tools to a fake LLM and invoke list_missions
# --------------------------------------------------------------------------- #
def test_smoke_bind_to_fake_llm_and_invoke_list_missions(
    make_client, fake_tool_calling_llm
):
    routes = {("GET", "/api/missions"): FakeResponse(200, [SAMPLE_MISSION])}
    client, _ = make_client(routes, agent_id="agent-x")
    tools = get_tools(client=client)
    tools_by_name = {t.name: t for t in tools}

    # 1) bind the real StructuredTools to the fake LLM (exercises tool->schema
    #    conversion inside bind_tools)
    llm = fake_tool_calling_llm(
        emit=[{"name": "oabp_list_missions", "args": {}, "id": "call_1", "type": "tool_call"}]
    )
    bound = llm.bind_tools(tools)
    assert llm.bound_names == EXPECTED_NAMES

    # 2) the (fake) model decides to call list_missions
    ai = bound.invoke("Show me the open bounty missions")
    assert ai.tool_calls, "model should have emitted a tool call"
    call = ai.tool_calls[0]
    assert call["name"] == "oabp_list_missions"

    # 3) execute that tool call exactly as an agent executor would
    tool_msg = tools_by_name[call["name"]].invoke(call)
    assert tool_msg.name == "oabp_list_missions"
    assert tool_msg.tool_call_id == "call_1"
    payload = (
        json.loads(tool_msg.content)
        if isinstance(tool_msg.content, str)
        else tool_msg.content
    )
    assert payload["count"] == 1
    assert payload["missions"][0]["id"] == "m-001"
