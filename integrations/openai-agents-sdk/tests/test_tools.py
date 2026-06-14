"""Offline unit tests for the openai_agents_oabp integration.

All HTTP is mocked via the ``RoutingFakeSession`` injected into the underlying
OABP SDK client (see conftest), so the suite is deterministic and never touches
the network. The suite also runs whether or not ``openai-agents`` is installed:

* with it, ``get_oabp_tools`` returns real ``agents.FunctionTool`` objects and the
  tests invoke them through ``on_invoke_tool``;
* without it, the tools are plain callables and the tests call them directly.

The helper :func:`invoke_tool` papers over that difference.
"""

from __future__ import annotations

import asyncio
import inspect
import json

import pytest

import openai_agents_oabp
from openai_agents_oabp import HAS_AGENTS, get_oabp_tools, tool_names
from openai_agents_oabp.tools import mission_to_dict, reputation_to_dict, stats_to_dict

from conftest import (
    SAMPLE_MISSION,
    SAMPLE_MISSION_DETAIL,
    SAMPLE_REPUTATION,
    SAMPLE_STATS,
    FakeResponse,
)

EXPECTED_NAMES = [
    "oabp_list_missions",
    "oabp_get_mission",
    "oabp_create_mission",
    "oabp_submit_mission",
    "oabp_get_stats",
    "oabp_get_reputation",
]


# --------------------------------------------------------------------------- #
# Cross-mode helpers (FunctionTool vs plain callable)
# --------------------------------------------------------------------------- #
def tool_name(tool) -> str:
    """Tool name whether it's a FunctionTool or an annotated plain callable."""
    return getattr(tool, "name", None) or getattr(tool, "oabp_tool_name")


def tools_by_name(tools):
    return {tool_name(t): t for t in tools}


def invoke_tool(tool, **kwargs):
    """Invoke a tool and return its (parsed) result, in either mode."""
    if HAS_AGENTS and hasattr(tool, "on_invoke_tool"):
        # Real openai-agents FunctionTool: async on_invoke_tool(ctx, json_args).
        out = asyncio.get_event_loop().run_until_complete(
            tool.on_invoke_tool(None, json.dumps(kwargs))
        )
    else:
        # Fallback: the tool *is* the plain callable.
        out = tool(**kwargs)
    # Tools return dicts; FunctionTool may stringify — normalise to an object.
    if isinstance(out, str):
        stripped = out.lstrip()
        if stripped[:1] in "{[":
            try:
                return json.loads(out)
            except ValueError:
                return out
    return out


# --------------------------------------------------------------------------- #
# Importability + discovery (acceptance: importable without openai-agents)
# --------------------------------------------------------------------------- #
def test_package_imports_without_openai_agents():
    # The whole module graph is importable regardless of the SDK being present.
    assert hasattr(openai_agents_oabp, "get_oabp_tools")
    assert hasattr(openai_agents_oabp, "build_agent")
    # HAS_AGENTS reflects reality; this test must pass in both worlds.
    assert isinstance(HAS_AGENTS, bool)


def test_get_oabp_tools_returns_at_least_six_named_tools():
    tools = get_oabp_tools(agent_id="agent-x")
    assert len(tools) >= 6
    assert [tool_name(t) for t in tools] == EXPECTED_NAMES
    assert tool_names() == EXPECTED_NAMES


def test_every_tool_exposes_name_description_and_params_schema():
    """Acceptance: each tool has name + description + a params schema."""
    for tool in get_oabp_tools(agent_id="agent-x"):
        name = tool_name(tool)
        assert name and name.startswith("oabp_")

        desc = getattr(tool, "description", None) or getattr(
            tool, "oabp_tool_description", None
        )
        assert desc and len(desc) > 20, f"{name} has a trivial description"

        # A params JSON schema is present. With openai-agents that's
        # `params_json_schema`; in the fallback we reconstruct one from the
        # callable's signature so the contract still holds.
        schema = _params_schema(tool)
        assert isinstance(schema, dict)
        assert schema.get("type") == "object"
        assert "properties" in schema


def _params_schema(tool) -> dict:
    """Return a params JSON schema for a tool in either mode."""
    schema = getattr(tool, "params_json_schema", None)
    if isinstance(schema, dict):
        return schema
    # Fallback: derive a minimal object schema from the plain callable's params.
    fn = tool  # the callable itself
    props = {}
    sig = inspect.signature(fn)
    for pname in sig.parameters:
        props[pname] = {}
    return {"type": "object", "properties": props}


# --------------------------------------------------------------------------- #
# THE acceptance test — list_missions parses a mis_* fixture w/ min_submitter_elo
# --------------------------------------------------------------------------- #
def test_list_missions_parses_mis_id_and_min_submitter_elo(make_client):
    routes = {("GET", "/api/missions"): FakeResponse(200, [SAMPLE_MISSION])}
    client, session = make_client(routes, agent_id="agent-x")
    tools = tools_by_name(get_oabp_tools(client=client, agent_id="agent-x"))

    out = invoke_tool(tools["oabp_list_missions"])
    assert out["count"] == 1
    mission = out["missions"][0]

    # mis_* id is parsed and surfaced.
    assert mission["id"] == "mis_abc123"
    assert mission["id"].startswith("mis_")

    # reward + verification_type are trimmed/serialised correctly.
    assert mission["reward"] == {"amount": 500.0, "currency": "AIGEN"}
    assert mission["verification_type"] == "oracle"
    assert mission["status"] == "open"

    # min_submitter_elo flows straight through verification_params.
    assert mission["verification_params"]["min_submitter_elo"] == 1200
    assert mission["verification_params"]["oracle_description"] == "safety review of 0xABC"

    # result is JSON-serialisable (no dataclasses / enums leaking).
    json.dumps(out)

    # the SDK actually issued the GET we expect.
    assert session.calls and session.calls[0]["method"] == "GET"
    assert "/api/missions" in session.calls[0]["url"]


def test_list_missions_limit(make_client):
    many = [dict(SAMPLE_MISSION, id=f"mis_{i}") for i in range(5)]
    routes = {("GET", "/api/missions"): FakeResponse(200, many)}
    client, _ = make_client(routes)
    tools = tools_by_name(get_oabp_tools(client=client))
    out = invoke_tool(tools["oabp_list_missions"], limit=2)
    assert out["count"] == 2
    assert [m["id"] for m in out["missions"]] == ["mis_0", "mis_1"]


# --------------------------------------------------------------------------- #
# Read tools
# --------------------------------------------------------------------------- #
def test_get_mission_with_submissions_and_resolution(make_client):
    routes = {
        ("GET", "/api/missions/mis_abc123"): FakeResponse(200, SAMPLE_MISSION_DETAIL)
    }
    client, _ = make_client(routes)
    tools = tools_by_name(get_oabp_tools(client=client))
    out = invoke_tool(tools["oabp_get_mission"], mission_id="mis_abc123")
    assert out["id"] == "mis_abc123"
    assert out["submission_count"] == 1
    assert out["submissions"][0]["submitter_agent_id"] == "agent-9"
    assert out["resolution"]["winner_agent_id"] == "agent-9"
    assert out["resolution"]["reward_paid"] == 497.5
    json.dumps(out)


def test_get_stats(make_client):
    routes = {("GET", "/api/stats"): FakeResponse(200, SAMPLE_STATS)}
    client, _ = make_client(routes)
    tools = tools_by_name(get_oabp_tools(client=client))
    out = invoke_tool(tools["oabp_get_stats"])
    assert out == {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000.0}


def test_get_reputation_uses_default_agent_id(make_client):
    routes = {
        ("GET", "/api/agents/agent-9/reputation"): FakeResponse(200, SAMPLE_REPUTATION)
    }
    client, _ = make_client(routes, agent_id="agent-9")
    tools = tools_by_name(get_oabp_tools(client=client, agent_id="agent-9"))
    out = invoke_tool(tools["oabp_get_reputation"])
    assert out["agent_id"] == "agent-9"
    assert out["aigen_balance"] == 1500.0
    assert out["missions_won"] == 4


# --------------------------------------------------------------------------- #
# Write tools — assert the exact body the SDK sends to the server
# --------------------------------------------------------------------------- #
def test_create_mission_sends_correct_body(make_client):
    captured = {}

    def handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        return FakeResponse(200, dict(SAMPLE_MISSION, id="mis_new"))

    routes = {("POST", "/api/missions"): handler}
    client, _ = make_client(routes, agent_id="creator-1")
    tools = tools_by_name(get_oabp_tools(client=client, agent_id="creator-1"))

    out = invoke_tool(
        tools["oabp_create_mission"],
        title="Audit MyToken",
        description="GoPlus safety review for 0xDEF",
        reward_amount=250,
        verification_type="oracle",
        deadline_hours=48,
        verification_params={"oracle_description": "safety review of 0xDEF"},
    )
    assert out["created"] is True
    assert out["mission"]["id"] == "mis_new"

    body = captured["body"]
    assert body["creator_agent_id"] == "creator-1"  # default agent_id used
    assert body["title"] == "Audit MyToken"
    assert body["reward_amount"] == 250.0
    assert body["reward_currency"] == "AIGEN"
    assert body["verification_type"] == "oracle"
    assert body["deadline_hours"] == 48.0
    assert body["verification_params"] == {"oracle_description": "safety review of 0xDEF"}


def test_submit_mission_sends_correct_body(make_client):
    captured = {}

    def handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        return FakeResponse(200, {"accepted": True, "resolution": {"winner_agent_id": "sub-1"}})

    routes = {("POST", "/missions/mis_abc123/submit"): handler}
    client, _ = make_client(routes, agent_id="sub-1")
    tools = tools_by_name(get_oabp_tools(client=client, agent_id="sub-1"))

    out = invoke_tool(
        tools["oabp_submit_mission"],
        mission_id="mis_abc123",
        proof="https://github.com/me/repo",
    )
    assert out["submitted"] is True
    assert out["mission_id"] == "mis_abc123"
    assert out["response"]["accepted"] is True

    body = captured["body"]
    assert body["submitter_agent_id"] == "sub-1"
    assert body["proof"] == "https://github.com/me/repo"


# --------------------------------------------------------------------------- #
# Error handling — SDK errors become structured strings, not exceptions
# --------------------------------------------------------------------------- #
def test_get_mission_404_returns_error_string(make_client):
    routes = {("GET", "/api/missions/nope"): FakeResponse(404, {"error": "not found"})}
    client, _ = make_client(routes, max_retries=0)
    tools = tools_by_name(get_oabp_tools(client=client))
    out = invoke_tool(tools["oabp_get_mission"], mission_id="nope")
    # error is a one-line structured string the model can read.
    assert isinstance(out, str)
    assert out.startswith("ERROR OabpNotFoundError")
    assert "404" in out


def test_list_missions_server_error_returns_error_string(make_client):
    routes = {("GET", "/api/missions"): FakeResponse(500, {"error": "boom"})}
    client, _ = make_client(routes, max_retries=0)
    tools = tools_by_name(get_oabp_tools(client=client))
    out = invoke_tool(tools["oabp_list_missions"])
    assert isinstance(out, str)
    assert out.startswith("ERROR OabpServerError")
    assert "500" in out


def test_reputation_without_agent_id_returns_error_string(make_client):
    # No default agent_id and none passed -> structured error, no network call.
    client, session = make_client({})
    tools = tools_by_name(get_oabp_tools(client=client))
    out = invoke_tool(tools["oabp_get_reputation"])
    assert isinstance(out, str)
    assert out.startswith("ERROR OabpValidationError")
    assert session.calls == []  # never hit the network


# --------------------------------------------------------------------------- #
# Serialiser helpers
# --------------------------------------------------------------------------- #
def test_mission_to_dict_is_json_serialisable():
    from openai_agents_oabp import Mission

    d = mission_to_dict(Mission.from_dict(SAMPLE_MISSION_DETAIL))
    json.dumps(d)  # must not raise
    assert d["id"] == "mis_abc123"
    assert d["verification_type"] == "oracle"  # enum -> str
    assert d["reward"]["currency"] == "AIGEN"
    assert d["verification_params"]["min_submitter_elo"] == 1200


def test_stats_and_reputation_to_dict():
    from openai_agents_oabp import Reputation, Stats

    assert stats_to_dict(Stats.from_dict(SAMPLE_STATS)) == {
        "resolved": 7,
        "open": 3,
        "lifetime_reward_aigen_paid": 108000.0,
    }
    rep = reputation_to_dict(Reputation.from_dict(SAMPLE_REPUTATION))
    assert rep["agent_id"] == "agent-9"
    assert rep["aigen_balance"] == 1500.0


# --------------------------------------------------------------------------- #
# build_agent gating on the optional dependency
# --------------------------------------------------------------------------- #
def test_build_agent_requires_openai_agents():
    from openai_agents_oabp import build_agent

    if HAS_AGENTS:
        agent = build_agent(model="gpt-4o-mini", agent_id="a")
        # Real Agent carries the six tools + our instructions.
        assert getattr(agent, "name", None)
        assert len(getattr(agent, "tools", [])) >= 6
    else:
        with pytest.raises(RuntimeError):
            build_agent(model="gpt-4o-mini", agent_id="a")
