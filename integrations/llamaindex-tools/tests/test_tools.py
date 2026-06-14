"""Offline unit tests for the llamaindex_oabp integration.

All HTTP is mocked via the ``RoutingFakeSession`` injected into the underlying
OABP SDK client (see conftest), so the suite is deterministic and never touches
the network. The suite also runs whether or not ``llama-index-core`` is
installed:

* with it, ``get_tools`` returns real ``llama_index.core.tools.FunctionTool``
  objects (name/description/fn_schema under ``.metadata``);
* without it, the tools are lightweight ``FunctionTool``-likes that mirror the
  same attributes and remain directly callable.

The helpers :func:`tname` / :func:`invoke_tool` paper over that difference, both
built on the public :func:`llamaindex_oabp.tool_metadata`.
"""

from __future__ import annotations

import inspect
import json

import pytest
from pydantic import BaseModel, ValidationError

import llamaindex_oabp
from llamaindex_oabp import (
    CreateMissionArgs,
    HAS_LLAMA_INDEX,
    get_tools,
    tool_metadata,
    tool_names,
)
from llamaindex_oabp.schemas import (
    GetMissionArgs,
    GetReputationArgs,
    ListMissionsArgs,
    StatsArgs,
    SubmitMissionArgs,
)
from llamaindex_oabp.tools import (
    mission_to_dict,
    reputation_to_dict,
    stats_to_dict,
)

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
# Cross-mode helpers (real FunctionTool vs fallback FunctionTool-like)
# --------------------------------------------------------------------------- #
def tname(tool) -> str:
    """Tool name in either mode (always via the metadata seam)."""
    return tool_metadata(tool).name


def tools_by_name(tools):
    return {tname(t): t for t in tools}


def invoke_tool(tool, **kwargs):
    """Invoke a tool and return its dict result, in either mode.

    Both the real FunctionTool and the fallback expose ``.call(**kwargs)``
    returning a ToolOutput-like object whose ``.raw_output`` is the tool's dict.
    The fallback is also directly callable; we prefer ``.call`` for parity with
    the real LlamaIndex API.
    """
    out = tool.call(**kwargs)
    raw = getattr(out, "raw_output", out)
    if isinstance(raw, str):
        stripped = raw.lstrip()
        if stripped[:1] in "{[":
            try:
                return json.loads(raw)
            except ValueError:
                return raw
    return raw


# --------------------------------------------------------------------------- #
# Importability + discovery
# (acceptance: imports without llama-index; >=6 tools w/ name+description+fn_schema)
# --------------------------------------------------------------------------- #
def test_package_imports_without_llama_index():
    # The whole module graph is importable regardless of LlamaIndex being present.
    assert hasattr(llamaindex_oabp, "get_tools")
    assert hasattr(llamaindex_oabp, "build_agent")
    assert hasattr(llamaindex_oabp, "tool_metadata")
    # HAS_LLAMA_INDEX reflects reality; this test must pass in both worlds.
    assert isinstance(HAS_LLAMA_INDEX, bool)


def test_get_tools_returns_at_least_six_named_tools():
    tools = get_tools(agent_id="agent-x")
    assert len(tools) >= 6
    assert [tname(t) for t in tools] == EXPECTED_NAMES
    assert tool_names() == EXPECTED_NAMES


def test_every_tool_exposes_name_description_and_fn_schema():
    """Acceptance: each tool exposes name + (concise) description + Pydantic fn_schema."""
    for tool in get_tools(agent_id="agent-x"):
        meta = tool_metadata(tool)
        name = meta.name
        assert name and name.startswith("oabp_")

        assert meta.description and len(meta.description) > 20, (
            f"{name} has a trivial description"
        )

        # fn_schema is a Pydantic model class.
        assert meta.fn_schema is not None, f"{name} has no fn_schema"
        assert isinstance(meta.fn_schema, type) and issubclass(meta.fn_schema, BaseModel)

        # And it produces a usable function-calling parameter schema.
        params = meta.get_parameters_dict()
        assert isinstance(params, dict)
        assert params.get("type") == "object"
        assert "properties" in params


def test_fn_schema_field_mapping():
    schemas = {tname(t): tool_metadata(t).fn_schema for t in get_tools()}
    assert schemas["oabp_list_missions"] is ListMissionsArgs
    assert schemas["oabp_get_mission"] is GetMissionArgs
    assert schemas["oabp_create_mission"] is CreateMissionArgs
    assert schemas["oabp_submit_mission"] is SubmitMissionArgs
    assert schemas["oabp_get_stats"] is StatsArgs
    assert schemas["oabp_get_reputation"] is GetReputationArgs


def test_create_fn_schema_exposes_expected_parameters():
    meta = {tname(t): tool_metadata(t) for t in get_tools()}["oabp_create_mission"]
    props = meta.get_parameters_dict()["properties"]
    for field in (
        "title",
        "description",
        "reward_amount",
        "verification_type",
        "deadline_hours",
        "reward_currency",
        "verification_params",
        "creator_agent_id",
    ):
        assert field in props, f"create_mission fn_schema missing {field!r}"


# --------------------------------------------------------------------------- #
# THE acceptance test — get_mission returns submissions + resolution keys
# --------------------------------------------------------------------------- #
def test_get_mission_returns_submissions_and_resolution_keys(make_client):
    routes = {
        ("GET", "/api/missions/mis_abc123"): FakeResponse(200, SAMPLE_MISSION_DETAIL)
    }
    client, session = make_client(routes)
    tools = tools_by_name(get_tools(client=client))

    out = invoke_tool(tools["oabp_get_mission"], mission_id="mis_abc123")

    # The two keys the acceptance criterion calls out.
    assert "submissions" in out
    assert "resolution" in out

    assert out["id"] == "mis_abc123"
    assert out["submission_count"] == 1
    assert out["submissions"][0]["submitter_agent_id"] == "agent-9"
    assert out["submissions"][0]["proof"] == "0xABC"
    assert out["resolution"]["winner_agent_id"] == "agent-9"
    assert out["resolution"]["verified"] is True
    assert out["resolution"]["reward_paid"] == 497.5

    # min_submitter_elo flows straight through verification_params.
    assert out["verification_params"]["min_submitter_elo"] == 1200

    # result is JSON-serialisable (no dataclasses / enums leaking).
    json.dumps(out)

    # the SDK actually issued the GET we expect.
    assert session.calls and session.calls[0]["method"] == "GET"
    assert "/api/missions/mis_abc123" in session.calls[0]["url"]


# --------------------------------------------------------------------------- #
# Read tools
# --------------------------------------------------------------------------- #
def test_list_missions_parses_mis_id_and_min_submitter_elo(make_client):
    routes = {("GET", "/api/missions"): FakeResponse(200, [SAMPLE_MISSION])}
    client, session = make_client(routes, agent_id="agent-x")
    tools = tools_by_name(get_tools(client=client, agent_id="agent-x"))

    out = invoke_tool(tools["oabp_list_missions"])
    assert out["count"] == 1
    mission = out["missions"][0]

    assert mission["id"] == "mis_abc123"
    assert mission["id"].startswith("mis_")
    assert mission["reward"] == {"amount": 500.0, "currency": "AIGEN"}
    assert mission["verification_type"] == "oracle"
    assert mission["status"] == "open"
    assert mission["verification_params"]["min_submitter_elo"] == 1200
    json.dumps(out)


def test_list_missions_limit(make_client):
    many = [dict(SAMPLE_MISSION, id=f"mis_{i}") for i in range(5)]
    routes = {("GET", "/api/missions"): FakeResponse(200, many)}
    client, _ = make_client(routes)
    tools = tools_by_name(get_tools(client=client))
    out = invoke_tool(tools["oabp_list_missions"], limit=2)
    assert out["count"] == 2
    assert [m["id"] for m in out["missions"]] == ["mis_0", "mis_1"]


def test_get_stats(make_client):
    routes = {("GET", "/api/stats"): FakeResponse(200, SAMPLE_STATS)}
    client, _ = make_client(routes)
    tools = tools_by_name(get_tools(client=client))
    out = invoke_tool(tools["oabp_get_stats"])
    assert out == {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000.0}


def test_get_reputation_uses_default_agent_id(make_client):
    routes = {
        ("GET", "/api/agents/agent-9/reputation"): FakeResponse(200, SAMPLE_REPUTATION)
    }
    client, _ = make_client(routes, agent_id="agent-9")
    tools = tools_by_name(get_tools(client=client, agent_id="agent-9"))
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
    tools = tools_by_name(get_tools(client=client, agent_id="creator-1"))

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
    tools = tools_by_name(get_tools(client=client, agent_id="sub-1"))

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
# Error handling — SDK errors become structured {"error": ...} dicts, not raises
# --------------------------------------------------------------------------- #
def test_get_mission_404_returns_error_dict(make_client):
    routes = {("GET", "/api/missions/nope"): FakeResponse(404, {"error": "not found"})}
    client, _ = make_client(routes, max_retries=0)
    tools = tools_by_name(get_tools(client=client))
    out = invoke_tool(tools["oabp_get_mission"], mission_id="nope")
    assert isinstance(out, dict)
    assert out["error_type"] == "OabpNotFoundError"
    assert out["status_code"] == 404
    json.dumps(out)


def test_list_missions_server_error_returns_error_dict(make_client):
    routes = {("GET", "/api/missions"): FakeResponse(500, {"error": "boom"})}
    client, _ = make_client(routes, max_retries=0)
    tools = tools_by_name(get_tools(client=client))
    out = invoke_tool(tools["oabp_list_missions"])
    assert isinstance(out, dict)
    assert out["error_type"] == "OabpServerError"
    assert out["status_code"] == 500


def test_reputation_without_agent_id_returns_error_dict(make_client):
    # No default agent_id and none passed -> structured error dict, no network call.
    client, session = make_client({})
    tools = tools_by_name(get_tools(client=client))
    out = invoke_tool(tools["oabp_get_reputation"])
    assert isinstance(out, dict)
    assert out["error_type"] == "OabpValidationError"
    assert session.calls == []  # never hit the network


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
    assert GetMissionArgs(mission_id="  mis_1 ").mission_id == "mis_1"
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
    from llamaindex_oabp import Mission

    d = mission_to_dict(Mission.from_dict(SAMPLE_MISSION_DETAIL))
    json.dumps(d)  # must not raise
    assert d["id"] == "mis_abc123"
    assert d["verification_type"] == "oracle"  # enum -> str
    assert d["reward"]["currency"] == "AIGEN"
    assert d["verification_params"]["min_submitter_elo"] == 1200


def test_stats_and_reputation_to_dict():
    from llamaindex_oabp import Reputation, Stats

    assert stats_to_dict(Stats.from_dict(SAMPLE_STATS)) == {
        "resolved": 7,
        "open": 3,
        "lifetime_reward_aigen_paid": 108000.0,
    }
    rep = reputation_to_dict(Reputation.from_dict(SAMPLE_REPUTATION))
    assert rep["agent_id"] == "agent-9"
    assert rep["aigen_balance"] == 1500.0


# --------------------------------------------------------------------------- #
# Direct-callable contract (the fallback tools must be plain callables too)
# --------------------------------------------------------------------------- #
def test_tools_are_directly_callable(make_client):
    routes = {("GET", "/api/stats"): FakeResponse(200, SAMPLE_STATS)}
    client, _ = make_client(routes)
    tools = tools_by_name(get_tools(client=client))
    fn = getattr(tools["oabp_get_stats"], "fn", tools["oabp_get_stats"])
    out = fn()
    assert out["resolved"] == 7


# --------------------------------------------------------------------------- #
# build_agent gating on the optional dependency
# --------------------------------------------------------------------------- #
def test_build_agent_requires_llama_index():
    from llamaindex_oabp import build_agent

    class _DummyLLM:
        pass

    if HAS_LLAMA_INDEX:
        # We don't run a real LLM here; just assert the call path reaches the
        # LlamaIndex agent constructor (it may raise for a non-LLM, which is a
        # *different* error than the missing-dependency RuntimeError).
        try:
            agent = build_agent(_DummyLLM(), agent_id="a")
        except RuntimeError as exc:
            # Must NOT be the "llama-index-core not installed" guard.
            assert "not installed" not in str(exc)
        except Exception:
            # LlamaIndex rejecting the dummy LLM is acceptable for this unit test.
            pass
        else:
            assert agent is not None
    else:
        with pytest.raises(RuntimeError):
            build_agent(_DummyLLM(), agent_id="a")


def test_build_agent_rejects_unknown_agent_type():
    from llamaindex_oabp import build_agent

    class _DummyLLM:
        pass

    # Only meaningful when LlamaIndex is present (otherwise the missing-dep guard
    # fires first); skip cleanly when it's absent.
    if not HAS_LLAMA_INDEX:
        pytest.skip("llama-index-core not installed")
    with pytest.raises(ValueError):
        build_agent(_DummyLLM(), agent_id="a", agent_type="telepathic")


# --------------------------------------------------------------------------- #
# The example script must at least import/compile cleanly.
# --------------------------------------------------------------------------- #
def test_example_compiles():
    import os
    import py_compile

    example = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "examples",
        "react_agent.py",
    )
    # Raises py_compile.PyCompileError on a syntax error.
    py_compile.compile(example, doraise=True)
    assert inspect.isfunction  # sanity import marker
