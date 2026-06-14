"""Offline unit tests for the smolagents_oabp integration.

All HTTP is mocked via the ``RoutingFakeSession`` injected into the underlying
(vendored) OABP SDK client (see conftest), so the suite is deterministic and
never touches the network. smolagents itself is never required: the default
suite runs with the ``@tool`` no-op fallback (proving the package is usable
standalone), and a ``fake_smolagents`` fixture exercises the real-decorator path
and ``build_agent`` without installing smolagents.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

import smolagents_oabp
from smolagents_oabp import (
    MOTIVATING_MISSION_ID,
    CreateMissionArgs,
    build_agent,
    get_tools,
    get_tools_dict,
    tool_names,
    tool_schemas,
)
from smolagents_oabp._smol import parse_docstring
from smolagents_oabp.schemas import (
    GetMissionArgs,
    GetReputationArgs,
    ListMissionsArgs,
    StatsArgs,
    SubmitMissionArgs,
)
from smolagents_oabp.tools import (
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
    SMOLAGENTS_MISSION,
)

EXPECTED_NAMES = [
    "list_missions",
    "get_mission",
    "create_mission",
    "submit_mission",
    "get_stats",
    "get_reputation",
]

# JSON-schema input names each tool must expose (parsed from its Args docstring).
EXPECTED_INPUTS = {
    "list_missions": {"status", "limit"},
    "get_mission": {"mission_id"},
    "create_mission": {
        "title",
        "description",
        "reward_amount",
        "verification_type",
        "deadline_hours",
        "reward_currency",
        "verification_params",
        "creator_agent_id",
    },
    "submit_mission": {"mission_id", "proof", "submitter_agent_id"},
    "get_stats": set(),
    "get_reputation": {"agent_id"},
}


# --------------------------------------------------------------------------- #
# Acceptance: imports without smolagents installed
# --------------------------------------------------------------------------- #
def test_imports_without_smolagents():
    """Acceptance: the package imports and is usable without smolagents.

    In this default test environment smolagents is not installed, so the @tool
    decorator must have no-op'd to a callable fallback.
    """
    import importlib
    import sys

    assert "smolagents" not in sys.modules or sys.modules.get("smolagents") is None
    assert smolagents_oabp.SMOLAGENTS_AVAILABLE is False
    importlib.reload(smolagents_oabp)
    assert hasattr(smolagents_oabp, "get_tools")
    assert hasattr(smolagents_oabp, "build_agent")
    # the six tool objects exist and are callable even without smolagents
    for name in EXPECTED_NAMES:
        t = getattr(smolagents_oabp, name)
        assert callable(t), f"{name} not callable"


# --------------------------------------------------------------------------- #
# Acceptance: get_tools returns >= 6 tools, each with name + description + inputs
# --------------------------------------------------------------------------- #
def test_get_tools_returns_six_with_schema(make_client):
    routes = {("GET", "/api/missions"): FakeResponse(200, [SAMPLE_MISSION])}
    client, _ = make_client(routes, agent_id="agent-x")
    tools = get_tools(client=client, agent_id="agent-x")

    assert isinstance(tools, list)
    assert len(tools) >= 6
    names = [t.name for t in tools]
    assert names == EXPECTED_NAMES
    for t in tools:
        # name + description + inputs schema present and well-formed
        assert isinstance(t.name, str) and t.name
        assert isinstance(t.description, str) and len(t.description) > 10
        assert isinstance(t.inputs, dict)
        assert set(t.inputs) == EXPECTED_INPUTS[t.name], t.name
        for pname, schema in t.inputs.items():
            assert "type" in schema, f"{t.name}.{pname} missing type"
            assert schema["type"] in (
                "string",
                "integer",
                "number",
                "boolean",
                "object",
                "array",
                "any",
            ), f"{t.name}.{pname} bad type {schema['type']!r}"
            assert "description" in schema
        # each tool is callable
        assert callable(t)


def test_tool_schemas_helper_matches():
    schemas = tool_schemas()
    assert [s["name"] for s in schemas] == EXPECTED_NAMES
    for s in schemas:
        assert set(s["inputs"]) == EXPECTED_INPUTS[s["name"]]
        assert s["description"]


def test_create_mission_input_types_and_nullability(make_client):
    client, _ = make_client({}, agent_id="a")
    tools = get_tools_dict(client=client, agent_id="a")
    inputs = tools["create_mission"].inputs
    assert inputs["reward_amount"]["type"] == "number"
    assert inputs["deadline_hours"]["type"] == "number"
    assert inputs["verification_params"]["type"] == "object"
    # required params (no default) are NOT marked nullable
    assert "nullable" not in inputs["title"]
    assert "nullable" not in inputs["reward_amount"]
    # optional params (default / Optional) ARE marked nullable
    assert inputs["reward_currency"]["nullable"] is True
    assert inputs["verification_params"]["nullable"] is True
    assert inputs["creator_agent_id"]["nullable"] is True


# --------------------------------------------------------------------------- #
# Read tools — trimmed dict shape
# --------------------------------------------------------------------------- #
def test_list_missions_tool(make_client):
    routes = {("GET", "/api/missions"): FakeResponse(200, [SAMPLE_MISSION])}
    client, _ = make_client(routes, agent_id="agent-x")
    tools = get_tools_dict(client=client)

    out = tools["list_missions"]()
    assert out["count"] == 1
    m = out["missions"][0]
    assert m["id"] == "m-001"
    assert m["reward"] == {"amount": 500.0, "currency": "AIGEN"}
    assert m["verification_type"] == "oracle"
    assert m["status"] == "open"
    assert m["submission_count"] == 0
    json.dumps(out)  # JSON-serialisable (no dataclasses/enums leaking)


def test_list_missions_limit(make_client):
    many = [dict(SAMPLE_MISSION, id=f"m-{i}") for i in range(5)]
    routes = {("GET", "/api/missions"): FakeResponse(200, many)}
    client, _ = make_client(routes)
    tools = get_tools_dict(client=client)
    out = tools["list_missions"](limit=2)
    assert out["count"] == 2
    assert [m["id"] for m in out["missions"]] == ["m-0", "m-1"]


def test_get_mission_tool_with_submissions_and_resolution(make_client):
    routes = {("GET", "/api/missions/m-001"): FakeResponse(200, SAMPLE_MISSION_DETAIL)}
    client, _ = make_client(routes)
    tools = get_tools_dict(client=client)
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
    tools = get_tools_dict(client=client)
    out = tools["get_stats"]()
    assert out == {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000.0}


def test_get_reputation_tool(make_client):
    routes = {
        ("GET", "/api/agents/agent-9/reputation"): FakeResponse(200, SAMPLE_REPUTATION)
    }
    client, _ = make_client(routes)
    tools = get_tools_dict(client=client)
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
    tools = get_tools_dict(client=client, agent_id="creator-1")

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


def test_submit_mission_tool_sends_correct_body_and_asserts_ack(make_client):
    """Acceptance: offline submit_mission against a stub asserts the ack."""
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
    client, _ = make_client(routes, agent_id="sub-1")
    tools = get_tools_dict(client=client, agent_id="sub-1")

    out = tools["submit_mission"](mission_id="m-001", proof="https://github.com/me/repo")
    # assert the acknowledgement
    assert out["submitted"] is True
    assert out["mission_id"] == "m-001"
    assert out["response"]["accepted"] is True
    assert out["response"]["resolution"]["verified"] is True

    body = captured["body"]
    assert body["submitter_agent_id"] == "sub-1"
    assert body["proof"] == "https://github.com/me/repo"


# --------------------------------------------------------------------------- #
# Self-referential mission: discover -> evaluate -> submit mis_15a24726b3de
# --------------------------------------------------------------------------- #
def test_self_referential_smolagents_mission_flow(make_client):
    """The motivating bounty: submit a merged smolagents PR URL, get verified."""
    pr_url = "https://github.com/huggingface/smolagents/pull/1742"
    captured = {}

    def submit_handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        return FakeResponse(
            200,
            {
                "accepted": True,
                "resolution": {
                    "winner_agent_id": "smolagents-oabp-demo",
                    "winning_proof": pr_url,
                    "verified": True,
                    "reward_paid": 199.0,  # 200 AIGEN - 0.5% fee
                },
            },
        )

    routes = {
        ("GET", "/api/missions"): FakeResponse(200, [SMOLAGENTS_MISSION]),
        (
            "GET",
            f"/api/missions/{MOTIVATING_MISSION_ID}",
        ): FakeResponse(200, SMOLAGENTS_MISSION),
        ("POST", f"/missions/{MOTIVATING_MISSION_ID}/submit"): submit_handler,
    }
    client, _ = make_client(routes, agent_id="smolagents-oabp-demo")
    tools = get_tools_dict(client=client, agent_id="smolagents-oabp-demo")

    # discover
    listing = tools["list_missions"]()
    assert any(m["id"] == MOTIVATING_MISSION_ID for m in listing["missions"])

    # evaluate
    detail = tools["get_mission"](mission_id=MOTIVATING_MISSION_ID)
    assert detail["verification_type"] == "oracle"
    assert detail["reward"] == {"amount": 200.0, "currency": "AIGEN"}
    assert (
        detail["verification_params"]["regex"]
        == "https://github.com/huggingface/smolagents/pull/[0-9]+"
    )

    # submit the merged PR and assert it verifies
    out = tools["submit_mission"](mission_id=MOTIVATING_MISSION_ID, proof=pr_url)
    assert out["submitted"] is True
    res = out["response"]["resolution"]
    assert res["verified"] is True
    assert res["reward_paid"] == 199.0
    assert captured["body"]["proof"] == pr_url


# --------------------------------------------------------------------------- #
# Error handling — SDK errors become structured results, not exceptions
# --------------------------------------------------------------------------- #
def test_get_mission_404_returns_error_dict(make_client):
    routes = {("GET", "/api/missions/nope"): FakeResponse(404, {"error": "not found"})}
    client, _ = make_client(routes, max_retries=0)
    tools = get_tools_dict(client=client)
    out = tools["get_mission"](mission_id="nope")
    assert out["error_type"] == "OabpNotFoundError"
    assert out["status_code"] == 404
    assert "error" in out
    json.dumps(out)


def test_every_tool_has_error_as_dict_path(make_client):
    """Every tool maps OabpError to {'error': ...} (no raise)."""
    routes = {
        ("GET", "/api/missions"): FakeResponse(500, {"error": "x"}),
        ("GET", "/api/missions/m-1"): FakeResponse(500, {"error": "x"}),
        ("POST", "/api/missions"): FakeResponse(500, {"error": "x"}),
        ("POST", "/missions/m-1/submit"): FakeResponse(500, {"error": "x"}),
        ("GET", "/api/stats"): FakeResponse(500, {"error": "x"}),
        ("GET", "/api/agents/a/reputation"): FakeResponse(500, {"error": "x"}),
    }
    client, _ = make_client(routes, agent_id="a", max_retries=0)
    tools = get_tools_dict(client=client, agent_id="a")
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
        json.dumps(out)


# --------------------------------------------------------------------------- #
# Local validation errors are returned as dicts too (before any network call)
# --------------------------------------------------------------------------- #
def test_create_bad_verification_type_returns_error_dict(make_client):
    client, session = make_client({}, agent_id="a")
    tools = get_tools_dict(client=client, agent_id="a")
    out = tools["create_mission"](
        title="x", description="d", reward_amount=10,
        verification_type="telepathy", deadline_hours=1,
    )
    assert out["error_type"] == "ValidationError"
    assert "verification_type" in out["error"]
    assert session.calls == []  # never hit the network


def test_submit_empty_proof_returns_error_dict(make_client):
    client, session = make_client({}, agent_id="a")
    tools = get_tools_dict(client=client, agent_id="a")
    out = tools["submit_mission"](mission_id="m-1", proof="")
    assert out["error_type"] == "ValidationError"
    assert session.calls == []


# --------------------------------------------------------------------------- #
# Zero-config: get_tools with no client uses a default public client
# --------------------------------------------------------------------------- #
def test_get_tools_without_client_binds_default():
    tools = get_tools(agent_id="z")
    assert [t.name for t in tools] == EXPECTED_NAMES
    from smolagents_oabp.tools import CONTEXT

    assert CONTEXT.agent_id == "z"
    # the default client points at the public deployment
    assert CONTEXT.client.base_url == smolagents_oabp.DEFAULT_BASE_URL


# --------------------------------------------------------------------------- #
# Docstring parsing (the source of the smolagents inputs schema)
# --------------------------------------------------------------------------- #
def test_parse_docstring_extracts_args():
    def f(a, b=None):
        """Summary line here.

        Args:
            a: the first arg, spanning
                two lines.
            b: the second arg.

        Returns:
            nothing useful.
        """

    summary, args = parse_docstring(f.__doc__)
    assert summary == "Summary line here."
    assert args["a"] == "the first arg, spanning two lines."
    assert args["b"] == "the second arg."
    assert "Returns" not in " ".join(args)


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
    StatsArgs()
    with pytest.raises(ValidationError):
        StatsArgs(unexpected=1)


def test_list_schema_limit_bounds():
    assert ListMissionsArgs(limit=1).limit == 1
    with pytest.raises(ValidationError):
        ListMissionsArgs(limit=0)
    with pytest.raises(ValidationError):
        ListMissionsArgs(limit=201)


# --------------------------------------------------------------------------- #
# Serialiser helpers
# --------------------------------------------------------------------------- #
def test_mission_to_dict_is_json_serialisable():
    from smolagents_oabp import Mission

    d = mission_to_dict(Mission.from_dict(SAMPLE_MISSION_DETAIL))
    json.dumps(d)
    assert d["verification_type"] == "oracle"  # enum -> str
    assert d["reward"]["currency"] == "AIGEN"


def test_stats_to_dict():
    from smolagents_oabp import Stats

    d = stats_to_dict(Stats.from_dict(SAMPLE_STATS))
    assert d == {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000.0}


def test_reputation_to_dict():
    from smolagents_oabp import Reputation

    d = reputation_to_dict(Reputation.from_dict(SAMPLE_REPUTATION))
    assert d == {
        "agent_id": "agent-9",
        "aigen_balance": 12500.0,
        "missions_won": 9,
        "missions_created": 3,
        "submissions": 14,
    }


# --------------------------------------------------------------------------- #
# build_agent without smolagents installed raises a helpful ImportError
# --------------------------------------------------------------------------- #
def test_build_agent_without_smolagents_raises_helpful_error():
    class _Model:
        pass

    with pytest.raises(ImportError) as ei:
        build_agent(_Model(), agent_id="x")
    assert "smolagents" in str(ei.value)


# --------------------------------------------------------------------------- #
# With a fake smolagents installed: real @tool path + build_agent both work
# --------------------------------------------------------------------------- #
def test_real_tool_decorator_path(fake_smolagents):
    """With smolagents present, @tool produces real Tool objects."""
    import smolagents_oabp as pkg

    assert pkg.SMOLAGENTS_AVAILABLE is True
    tools = pkg.get_tools(agent_id="x")
    assert [t.name for t in tools] == EXPECTED_NAMES
    # they are the fake smolagents Tool instances, still carrying the schema
    for t in tools:
        assert getattr(t, "is_fake_smolagents_tool", False) is True
        assert set(t.inputs) == EXPECTED_INPUTS[t.name]
        assert callable(t)


def test_build_code_agent_with_fake_smolagents(fake_smolagents, make_client):
    import smolagents_oabp as pkg

    routes = {("GET", "/api/missions"): FakeResponse(200, [SAMPLE_MISSION])}
    client, _ = make_client(routes, agent_id="hunter")

    model = object()
    agent = pkg.build_agent(model, agent_id="hunter", client=client, agent_type="code")
    assert agent.kind == "code"
    assert agent.model is model
    assert [t.name for t in agent.tools] == EXPECTED_NAMES
    # the bound tools actually work against the mocked marketplace
    listing = agent.tools[0]()
    assert listing["count"] == 1


def test_build_toolcalling_agent_with_fake_smolagents(fake_smolagents, make_client):
    import smolagents_oabp as pkg

    client, _ = make_client({}, agent_id="hunter")
    agent = pkg.build_agent(
        object(), agent_id="hunter", client=client, agent_type="toolcalling"
    )
    assert agent.kind == "toolcalling"
    assert [t.name for t in agent.tools] == EXPECTED_NAMES


def test_build_agent_rejects_unknown_type(fake_smolagents, make_client):
    import smolagents_oabp as pkg

    client, _ = make_client({}, agent_id="h")
    with pytest.raises(ValueError):
        pkg.build_agent(object(), agent_id="h", client=client, agent_type="psychic")
