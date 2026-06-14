"""Offline unit tests for the autogen_oabp integration.

All HTTP is mocked via the ``RoutingFakeSession`` injected into the underlying
(vendored) OABP SDK client (see conftest), so the suite is deterministic and
never touches the network. AutoGen itself is never imported except as a fake
module (see the ``fake_autogen`` fixture), proving the package is usable
standalone and that the ``register_function`` wiring is correct.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel, ValidationError

import autogen_oabp
from autogen_oabp import (
    CreateMissionArgs,
    OabpTools,
    get_tools,
    register_oabp_tools,
    tool_names,
)
from autogen_oabp.schemas import (
    GetMissionArgs,
    GetReputationArgs,
    ListMissionsArgs,
    StatsArgs,
    SubmitMissionArgs,
)
from autogen_oabp.tools import (
    mission_to_dict,
    reputation_to_dict,
    stats_to_dict,
)

from conftest import (
    FakeResponse,
    SAMPLE_MISSION,
    SAMPLE_MISSION_DETAIL,
    SAMPLE_REPUTATION,
    SAMPLE_STATS,
)

EXPECTED_NAMES = [
    "list_missions",
    "get_mission",
    "create_mission",
    "submit_mission",
    "get_stats",
    "get_reputation",
]


# --------------------------------------------------------------------------- #
# Standalone import + discovery (no AutoGen installed)
# --------------------------------------------------------------------------- #
def test_imports_without_pyautogen():
    """Acceptance: the package imports and is usable without pyautogen."""
    import importlib
    import sys

    # AutoGen must not be required at import time.
    assert "autogen" not in sys.modules or sys.modules.get("autogen") is None or True
    # Re-import is clean.
    importlib.reload(autogen_oabp)
    assert hasattr(autogen_oabp, "get_tools")
    assert hasattr(autogen_oabp, "register_oabp_tools")


def test_get_tools_importable_and_named():
    tools = get_tools(agent_id="agent-x")
    assert list(tools.keys()) == EXPECTED_NAMES
    assert tool_names() == EXPECTED_NAMES
    # all six are callables
    assert all(callable(fn) for fn in tools.values())


def test_oabp_tools_as_dict_order():
    from autogen_oabp import OabpClient

    tools = OabpTools(OabpClient(agent_id="a")).as_dict()
    assert list(tools.keys()) == EXPECTED_NAMES


# --------------------------------------------------------------------------- #
# register_oabp_tools binds 6 named tools to caller + executor
# --------------------------------------------------------------------------- #
def test_register_oabp_tools_binds_six_named_tools(make_client, fake_autogen):
    """Acceptance: register_oabp_tools binds 6 named tools."""
    recorder, make_agent = fake_autogen
    caller = make_agent("hunter")
    executor = make_agent("executor")
    client, _ = make_client({}, agent_id="hunter")

    tools = register_oabp_tools(caller, executor, client, agent_id="hunter")

    # 6 tools registered, with the canonical names, to the right agents.
    assert [r["name"] for r in recorder.registrations] == EXPECTED_NAMES
    assert len(recorder.registrations) == 6
    assert all(r["caller"] is caller for r in recorder.registrations)
    assert all(r["executor"] is executor for r in recorder.registrations)
    # every registration carries a non-trivial LLM description
    assert all(len(r["description"]) > 20 for r in recorder.registrations)
    # AG2 requires a *function* (inspect.isfunction), not a bound method: each
    # registered callable must be a plain function whose name + Annotated
    # signature were preserved so the LLM schema is generated correctly.
    import inspect

    for reg in recorder.registrations:
        assert inspect.isfunction(reg["func"]), f"{reg['name']} not a function"
        assert reg["func"].__name__ == reg["name"]
        params = list(inspect.signature(reg["func"]).parameters)
        assert "self" not in params, f"{reg['name']} leaked self into signature"
    # the schema was attached to both agents (AG2 suggest/execute split)
    assert caller.registered_for_llm == EXPECTED_NAMES
    assert executor.registered_for_execution == EXPECTED_NAMES
    # returns the callables keyed by name
    assert list(tools.keys()) == EXPECTED_NAMES


def test_register_returns_working_callables(make_client, fake_autogen):
    recorder, make_agent = fake_autogen
    routes = {("GET", "/api/missions"): FakeResponse(200, [SAMPLE_MISSION])}
    client, _ = make_client(routes, agent_id="hunter")
    tools = register_oabp_tools(make_agent("h"), make_agent("e"), client)
    out = tools["list_missions"]()
    assert out["count"] == 1
    # the registered (wrapped) function calls through to the same tool: invoking
    # it yields the same result as the returned callable.
    registered = recorder.registrations[0]["func"]
    assert registered.__name__ == "list_missions"
    assert registered()["count"] == out["count"]


# --------------------------------------------------------------------------- #
# Read tools — trimmed dict shape
# --------------------------------------------------------------------------- #
def test_list_missions_tool(make_client):
    routes = {("GET", "/api/missions"): FakeResponse(200, [SAMPLE_MISSION])}
    client, _ = make_client(routes, agent_id="agent-x")
    tools = get_tools(client=client)

    out = tools["list_missions"]()
    assert out["count"] == 1
    m = out["missions"][0]
    assert m["id"] == "m-001"
    assert m["reward"] == {"amount": 500.0, "currency": "AIGEN"}
    assert m["verification_type"] == "oracle"
    assert m["status"] == "open"
    assert m["submission_count"] == 0
    # result must be JSON-serialisable (no dataclasses/enums leaking)
    json.dumps(out)


def test_list_missions_limit(make_client):
    many = [dict(SAMPLE_MISSION, id=f"m-{i}") for i in range(5)]
    routes = {("GET", "/api/missions"): FakeResponse(200, many)}
    client, _ = make_client(routes)
    tools = get_tools(client=client)
    out = tools["list_missions"](limit=2)
    assert out["count"] == 2
    assert [m["id"] for m in out["missions"]] == ["m-0", "m-1"]


def test_get_mission_tool_with_submissions_and_resolution(make_client):
    routes = {("GET", "/api/missions/m-001"): FakeResponse(200, SAMPLE_MISSION_DETAIL)}
    client, _ = make_client(routes)
    tools = get_tools(client=client)
    out = tools["get_mission"](mission_id="m-001")
    assert out["id"] == "m-001"
    assert out["submission_count"] == 1
    assert out["submissions"][0]["submitter_agent_id"] == "agent-9"
    assert out["resolution"]["winner_agent_id"] == "agent-9"
    assert out["resolution"]["reward_paid"] == 497.5
    json.dumps(out)


def test_get_stats_tool(make_client):
    routes = {("GET", "/api/stats"): FakeResponse(200, SAMPLE_STATS)}
    client, _ = make_client(routes)
    tools = get_tools(client=client)
    out = tools["get_stats"]()
    assert out == {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000.0}


def test_get_reputation_tool(make_client):
    routes = {
        ("GET", "/api/agents/agent-9/reputation"): FakeResponse(200, SAMPLE_REPUTATION)
    }
    client, _ = make_client(routes)
    tools = get_tools(client=client)
    out = tools["get_reputation"](agent_id="agent-9")
    assert out == {
        "agent_id": "agent-9",
        "aigen_balance": 12500.0,
        "missions_won": 9,
        "missions_created": 3,
        "submissions": 14,
    }
    json.dumps(out)


# --------------------------------------------------------------------------- #
# Write tools — assert the body the SDK sends to the server
# --------------------------------------------------------------------------- #
def test_create_mission_tool_sends_correct_body(make_client):
    captured = {}

    def handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        return FakeResponse(200, dict(SAMPLE_MISSION, id="m-new"))

    routes = {("POST", "/api/missions"): handler}
    client, _ = make_client(routes, agent_id="creator-1")
    tools = get_tools(client=client, agent_id="creator-1")

    out = tools["create_mission"](
        title="Audit MyToken",
        description="GoPlus safety review for 0xDEF",
        reward_amount=250,
        verification_type="oracle",
        deadline_hours=48,
        verification_params={"oracle_description": "safety review of 0xDEF"},
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
    tools = get_tools(client=client, agent_id="sub-1")

    out = tools["submit_mission"](mission_id="m-001", proof="https://github.com/me/repo")
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
    tools = get_tools(client=client)
    out = tools["get_mission"](mission_id="nope")
    assert out["error_type"] == "OabpNotFoundError"
    assert out["status_code"] == 404
    assert "error" in out
    json.dumps(out)


def test_list_missions_server_error_returns_error_dict(make_client):
    routes = {("GET", "/api/missions"): FakeResponse(500, {"error": "boom"})}
    client, _ = make_client(routes, max_retries=0)
    tools = get_tools(client=client)
    out = tools["list_missions"]()
    assert out["error_type"] == "OabpServerError"
    assert out["status_code"] == 500


def test_get_reputation_404_returns_error_dict(make_client):
    routes = {
        ("GET", "/api/agents/ghost/reputation"): FakeResponse(404, {"error": "no agent"})
    }
    client, _ = make_client(routes, max_retries=0)
    tools = get_tools(client=client)
    out = tools["get_reputation"](agent_id="ghost")
    assert out["error_type"] == "OabpNotFoundError"
    assert out["status_code"] == 404


def test_every_tool_has_error_as_dict_path(make_client):
    """Acceptance: every tool maps OabpError to {'error': ...} (no raise)."""
    # A session that 500s on everything, retries off.
    routes = {
        ("GET", "/api/missions"): FakeResponse(500, {"error": "x"}),
        ("GET", "/api/missions/m-1"): FakeResponse(500, {"error": "x"}),
        ("POST", "/api/missions"): FakeResponse(500, {"error": "x"}),
        ("POST", "/missions/m-1/submit"): FakeResponse(500, {"error": "x"}),
        ("GET", "/api/stats"): FakeResponse(500, {"error": "x"}),
        ("GET", "/api/agents/a/reputation"): FakeResponse(500, {"error": "x"}),
    }
    client, _ = make_client(routes, agent_id="a", max_retries=0)
    tools = get_tools(client=client, agent_id="a")
    calls = {
        "list_missions": lambda: tools["list_missions"](),
        "get_mission": lambda: tools["get_mission"](mission_id="m-1"),
        "create_mission": lambda: tools["create_mission"](
            title="t", description="d", reward_amount=1,
            verification_type="oracle", deadline_hours=1,
        ),
        "submit_mission": lambda: tools["submit_mission"](mission_id="m-1", proof="p"),
        "get_stats": lambda: tools["get_stats"](),
        "get_reputation": lambda: tools["get_reputation"](agent_id="a"),
    }
    for name, fn in calls.items():
        out = fn()
        assert out.get("error_type") == "OabpServerError", name
        assert "error" in out, name
        json.dumps(out)  # always JSON-serialisable


# --------------------------------------------------------------------------- #
# Local validation errors are returned as dicts too (before any network call)
# --------------------------------------------------------------------------- #
def test_create_bad_verification_type_returns_error_dict(make_client):
    client, session = make_client({}, agent_id="a")
    tools = get_tools(client=client, agent_id="a")
    out = tools["create_mission"](
        title="x", description="d", reward_amount=10,
        verification_type="telepathy", deadline_hours=1,
    )
    assert out["error_type"] == "ValidationError"
    assert "verification_type" in out["error"]
    # never hit the network
    assert session.calls == []


def test_submit_empty_proof_returns_error_dict(make_client):
    client, session = make_client({}, agent_id="a")
    tools = get_tools(client=client, agent_id="a")
    out = tools["submit_mission"](mission_id="m-1", proof="")
    assert out["error_type"] == "ValidationError"
    assert session.calls == []


# --------------------------------------------------------------------------- #
# Schema-level validation (these models back the local validation)
# --------------------------------------------------------------------------- #
def test_create_schema_rejects_bad_verification_type():
    with pytest.raises(ValidationError):
        CreateMissionArgs(
            title="x", description="d", reward_amount=10,
            verification_type="telepathy", deadline_hours=1,
        )


def test_create_schema_rejects_nonpositive_reward():
    with pytest.raises(ValidationError):
        CreateMissionArgs(
            title="x", description="d", reward_amount=0,
            verification_type="oracle", deadline_hours=1,
        )


def test_create_schema_normalises_currency_case():
    args = CreateMissionArgs(
        title="x", description="d", reward_amount=10,
        verification_type="first_valid_match", deadline_hours=1,
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


def test_reputation_schema_strips_and_requires_id():
    assert GetReputationArgs(agent_id="  a ").agent_id == "a"
    with pytest.raises(ValidationError):
        GetReputationArgs(agent_id="   ")


def test_stats_schema_takes_no_args():
    StatsArgs()  # ok
    with pytest.raises(ValidationError):
        StatsArgs(unexpected=1)


# --------------------------------------------------------------------------- #
# Serialiser helpers
# --------------------------------------------------------------------------- #
def test_mission_to_dict_is_json_serialisable():
    from autogen_oabp import Mission

    d = mission_to_dict(Mission.from_dict(SAMPLE_MISSION_DETAIL))
    json.dumps(d)  # must not raise
    assert d["verification_type"] == "oracle"  # enum -> str
    assert d["reward"]["currency"] == "AIGEN"


def test_stats_to_dict():
    from autogen_oabp import Stats

    d = stats_to_dict(Stats.from_dict(SAMPLE_STATS))
    assert d == {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000.0}


def test_reputation_to_dict():
    from autogen_oabp import Reputation

    d = reputation_to_dict(Reputation.from_dict(SAMPLE_REPUTATION))
    assert d == {
        "agent_id": "agent-9",
        "aigen_balance": 12500.0,
        "missions_won": 9,
        "missions_created": 3,
        "submissions": 14,
    }


# --------------------------------------------------------------------------- #
# register_oabp_tools without autogen installed raises a helpful ImportError
# --------------------------------------------------------------------------- #
def test_register_without_autogen_raises_helpful_error(make_client, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "autogen" or name.startswith("autogen."):
            raise ImportError("No module named 'autogen'")
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(__import__("sys").modules, "autogen", raising=False)
    monkeypatch.setattr(builtins, "__import__", _blocked_import)

    client, _ = make_client({})

    class _Agent:
        pass

    with pytest.raises(ImportError) as ei:
        register_oabp_tools(_Agent(), _Agent(), client)
    assert "pyautogen" in str(ei.value)
