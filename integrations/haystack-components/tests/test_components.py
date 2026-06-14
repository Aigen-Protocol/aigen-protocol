"""Offline unit tests for the haystack_oabp integration.

All HTTP is mocked via the ``RoutingFakeSession`` injected into the underlying
OABP SDK client (see conftest), so the suite is deterministic and never touches
the network. The suite also runs whether or not ``haystack-ai`` is installed:

* with it, the components are real ``@haystack.component`` classes and
  ``get_tools`` returns real ``haystack.tools.ComponentTool`` objects;
* without it, the ``@component`` decorator no-ops so the classes stay ordinary
  classes whose ``run(...)`` is directly callable, and ``ComponentTool`` degrades
  to a lightweight ``Tool``-like.

These tests assert behaviour that holds in *both* worlds (that is the whole point
of the optional-dependency contract).
"""

from __future__ import annotations

import inspect
import json
import os
import py_compile

import pytest

import haystack_oabp
from haystack_oabp import (
    COMPONENT_CLASSES,
    HAS_HAYSTACK,
    OabpMissionCreator,
    OabpMissionFetcher,
    OabpMissionLister,
    OabpReputation,
    OabpStats,
    OabpSubmitter,
    component_output_types,
    get_components,
    get_tools,
    net_reward,
    tool_names,
)

from conftest import (
    SAMPLE_FVM_MISSION,
    SAMPLE_MISSION,
    SAMPLE_MISSION_DETAIL,
    SAMPLE_REPUTATION,
    SAMPLE_STATS,
    FakeResponse,
)

EXPECTED_TOOL_NAMES = [
    "oabp_list_missions",
    "oabp_get_mission",
    "oabp_create_mission",
    "oabp_submit_mission",
    "oabp_get_stats",
    "oabp_get_reputation",
]

# Each component class -> the output-type keys its run() must declare.
EXPECTED_OUTPUTS = {
    OabpMissionLister: {"missions", "count"},
    OabpMissionFetcher: {"mission"},
    OabpMissionCreator: {"mission", "created"},
    OabpSubmitter: {"response", "submitted", "mission_id"},
    OabpStats: {"stats"},
    OabpReputation: {"reputation"},
}


# --------------------------------------------------------------------------- #
# Importability (acceptance: imports without haystack-ai)
# --------------------------------------------------------------------------- #
def test_package_imports_without_haystack():
    # The whole module graph is importable regardless of haystack-ai being present.
    assert hasattr(haystack_oabp, "OabpMissionLister")
    assert hasattr(haystack_oabp, "get_tools")
    assert hasattr(haystack_oabp, "Pipeline")
    assert hasattr(haystack_oabp, "component")
    # HAS_HAYSTACK reflects reality; this test must pass in both worlds.
    assert isinstance(HAS_HAYSTACK, bool)


# --------------------------------------------------------------------------- #
# Acceptance: >= 5 components, each exposing run() with declared output_types
# --------------------------------------------------------------------------- #
def test_at_least_five_components():
    assert len(COMPONENT_CLASSES) >= 5


def test_every_component_has_callable_run_with_declared_output_types():
    """Acceptance: each component exposes a callable run() with @output_types."""
    assert len(COMPONENT_CLASSES) >= 5
    for cls in COMPONENT_CLASSES:
        # run() exists and is callable.
        assert hasattr(cls, "run"), f"{cls.__name__} has no run()"
        assert callable(cls.run), f"{cls.__name__}.run is not callable"

        # An instance's run is still a bound callable even with haystack absent
        # (the @component decorator must NOT replace run with something uncallable).
        inst = cls(agent_id="agent-x")
        assert callable(inst.run)

        # Declared output types are introspectable (via the public seam) and
        # match the component's contract.
        declared = component_output_types(inst)
        assert isinstance(declared, dict) and declared, (
            f"{cls.__name__}.run has no declared output_types"
        )
        assert set(declared) == EXPECTED_OUTPUTS[cls], (
            f"{cls.__name__} declared outputs {set(declared)} "
            f"!= expected {EXPECTED_OUTPUTS[cls]}"
        )


def test_run_signature_is_preserved():
    """The @component.output_types decorator must keep run()'s real signature."""
    sig = inspect.signature(OabpMissionCreator.run)
    params = set(sig.parameters) - {"self"}
    for expected in (
        "title",
        "description",
        "reward_amount",
        "verification_type",
        "deadline_hours",
        "reward_currency",
        "verification_params",
        "creator_agent_id",
    ):
        assert expected in params, f"create run() lost param {expected!r}"


# --------------------------------------------------------------------------- #
# THE acceptance test:
# OabpMissionLister.run() against a stubbed session -> list of mission dicts
# including a mis_* id.
# --------------------------------------------------------------------------- #
def test_lister_run_against_stubbed_session_returns_mission_dicts(make_client):
    routes = {("GET", "/api/missions"): FakeResponse(200, [SAMPLE_MISSION])}
    client, session = make_client(routes, agent_id="agent-x")

    lister = OabpMissionLister(agent_id="agent-x", client=client)
    out = lister.run()

    # run() returns the declared outputs.
    assert set(out) >= {"missions", "count"}
    missions = out["missions"]

    # ...a *list* of mission *dicts*...
    assert isinstance(missions, list) and missions
    assert all(isinstance(m, dict) for m in missions)

    # ...including a mis_* id.
    first = missions[0]
    assert first["id"] == "mis_abc123"
    assert first["id"].startswith("mis_")
    assert out["count"] == 1

    # Reward + verification mapping is correct and JSON-serialisable (no enums).
    assert first["reward"] == {"amount": 500.0, "currency": "AIGEN"}
    assert first["verification_type"] == "oracle"
    assert first["verification_params"]["min_submitter_elo"] == 1200
    json.dumps(out)

    # The SDK actually issued the GET we expect.
    assert session.calls and session.calls[0]["method"] == "GET"
    assert "/api/missions" in session.calls[0]["url"]


def test_lister_limit(make_client):
    many = [dict(SAMPLE_MISSION, id=f"mis_{i}") for i in range(5)]
    routes = {("GET", "/api/missions"): FakeResponse(200, many)}
    client, _ = make_client(routes)
    out = OabpMissionLister(client=client).run(limit=2)
    assert out["count"] == 2
    assert [m["id"] for m in out["missions"]] == ["mis_0", "mis_1"]


# --------------------------------------------------------------------------- #
# Fetcher: submissions + resolution keys on the detail view
# --------------------------------------------------------------------------- #
def test_fetcher_returns_submissions_and_resolution(make_client):
    routes = {
        ("GET", "/api/missions/mis_abc123"): FakeResponse(200, SAMPLE_MISSION_DETAIL)
    }
    client, session = make_client(routes)
    out = OabpMissionFetcher(client=client).run(mission_id="mis_abc123")["mission"]

    assert out["id"] == "mis_abc123"
    assert out["submission_count"] == 1
    assert out["submissions"][0]["submitter_agent_id"] == "agent-9"
    assert out["resolution"]["winner_agent_id"] == "agent-9"
    assert out["resolution"]["verified"] is True
    assert out["resolution"]["reward_paid"] == 497.5
    assert out["verification_params"]["min_submitter_elo"] == 1200
    json.dumps(out)


# --------------------------------------------------------------------------- #
# Stats / reputation
# --------------------------------------------------------------------------- #
def test_stats(make_client):
    routes = {("GET", "/api/stats"): FakeResponse(200, SAMPLE_STATS)}
    client, _ = make_client(routes)
    out = OabpStats(client=client).run()
    assert out["stats"] == {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000.0}


def test_reputation_uses_default_agent_id(make_client):
    routes = {
        ("GET", "/api/agents/agent-9/reputation"): FakeResponse(200, SAMPLE_REPUTATION)
    }
    client, _ = make_client(routes, agent_id="agent-9")
    out = OabpReputation(agent_id="agent-9", client=client).run()["reputation"]
    assert out["agent_id"] == "agent-9"
    assert out["aigen_balance"] == 1500.0
    assert out["missions_won"] == 4


def test_reputation_without_agent_id_returns_error(make_client):
    client, session = make_client({})
    out = OabpReputation(client=client).run()["reputation"]
    assert out["error_type"] == "OabpValidationError"
    assert session.calls == []  # never hit the network


# --------------------------------------------------------------------------- #
# Write components — assert the exact body the SDK sends to the server
# --------------------------------------------------------------------------- #
def test_creator_sends_correct_body(make_client):
    captured = {}

    def handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        return FakeResponse(200, dict(SAMPLE_MISSION, id="mis_new"))

    routes = {("POST", "/api/missions"): handler}
    client, _ = make_client(routes, agent_id="creator-1")

    out = OabpMissionCreator(agent_id="creator-1", client=client).run(
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


def test_submitter_sends_correct_body(make_client):
    captured = {}

    def handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        return FakeResponse(200, {"accepted": True, "resolution": {"winner_agent_id": "sub-1"}})

    routes = {("POST", "/missions/mis_abc123/submit"): handler}
    client, _ = make_client(routes, agent_id="sub-1")

    out = OabpSubmitter(agent_id="sub-1", client=client).run(
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
# Error handling — SDK errors become structured payloads, not raises
# --------------------------------------------------------------------------- #
def test_fetcher_404_returns_error_payload(make_client):
    routes = {("GET", "/api/missions/nope"): FakeResponse(404, {"error": "not found"})}
    client, _ = make_client(routes, max_retries=0)
    out = OabpMissionFetcher(client=client).run(mission_id="nope")["mission"]
    assert out["error_type"] == "OabpNotFoundError"
    assert out["status_code"] == 404
    json.dumps(out)


def test_lister_server_error_returns_empty_with_error(make_client):
    routes = {("GET", "/api/missions"): FakeResponse(500, {"error": "boom"})}
    client, _ = make_client(routes, max_retries=0)
    out = OabpMissionLister(client=client).run()
    assert out["missions"] == [] and out["count"] == 0
    assert out["error_type"] == "OabpServerError"


# --------------------------------------------------------------------------- #
# Tools (ComponentTool) surface
# --------------------------------------------------------------------------- #
def test_get_tools_names_and_order(make_client):
    routes = {("GET", "/api/stats"): FakeResponse(200, SAMPLE_STATS)}
    client, _ = make_client(routes)
    tools = get_tools(client=client, agent_id="agent-x")
    assert len(tools) == 6
    assert [t.name for t in tools] == EXPECTED_TOOL_NAMES
    assert tool_names() == EXPECTED_TOOL_NAMES


def test_each_tool_exposes_name_description_parameters(make_client):
    client, _ = make_client({})
    for tool in get_tools(client=client):
        assert tool.name and tool.name.startswith("oabp_")
        assert tool.description and len(tool.description) > 20
        params = tool.parameters
        assert isinstance(params, dict)
        assert params.get("type") == "object"
        assert "properties" in params


def test_create_tool_parameters_expose_fields(make_client):
    client, _ = make_client({})
    tools = {t.name: t for t in get_tools(client=client)}
    props = tools["oabp_create_mission"].parameters["properties"]
    for field in ("title", "description", "reward_amount", "verification_type", "deadline_hours"):
        assert field in props, f"create tool params missing {field!r}"


def test_tool_invoke_routes_to_component_run(make_client):
    routes = {("GET", "/api/stats"): FakeResponse(200, SAMPLE_STATS)}
    client, _ = make_client(routes)
    tools = {t.name: t for t in get_tools(client=client)}
    out = tools["oabp_get_stats"].invoke()
    # Real Haystack ComponentTool returns the component's output dict; our
    # fallback routes straight to run() and returns the same dict.
    assert out["stats"]["resolved"] == 7 if "stats" in out else out["resolved"] == 7


# --------------------------------------------------------------------------- #
# Pipeline: lister -> picker -> submitter (mirrors examples/pipeline.py)
# --------------------------------------------------------------------------- #
def test_pipeline_lister_filter_submitter_readonly(make_client):
    """A read-only pipeline run lists missions and the filter picks one (no write)."""
    from examples.pipeline import MissionPicker, build_pipeline  # noqa: WPS433

    routes = {
        ("GET", "/api/missions"): FakeResponse(200, [SAMPLE_MISSION, SAMPLE_FVM_MISSION]),
    }
    client, session = make_client(routes, agent_id="agent-x")

    pipe = build_pipeline("agent-x", write=False, client=client)
    result = pipe.run({"lister": {"limit": 20}})

    picker_out = result["picker"]
    # The picker selected the trivially-satisfiable first_valid_match mission...
    assert picker_out["mission_id"] == "mis_echo01"
    assert picker_out["proof"] == "OABP-OK"

    # ...and in read-only mode NO submit POST was issued.
    assert all(c["method"] != "POST" for c in session.calls)


def test_pipeline_write_mode_submits(make_client):
    """In write mode the picker output is wired to the submitter -> real POST."""
    from examples.pipeline import build_pipeline  # noqa: WPS433

    posted = {}

    def submit_handler(method, url, kwargs):
        posted["url"] = url
        posted["body"] = kwargs.get("json")
        return FakeResponse(200, {"accepted": True})

    routes = {
        ("GET", "/api/missions"): FakeResponse(200, [SAMPLE_FVM_MISSION]),
        ("POST", "/missions/mis_echo01/submit"): submit_handler,
    }
    client, session = make_client(routes, agent_id="agent-x")

    pipe = build_pipeline("agent-x", write=True, client=client)
    result = pipe.run({"lister": {"limit": 20}})

    # A submission happened to the chosen mission with the derived proof.
    assert posted.get("body", {}).get("proof") == "OABP-OK"
    assert posted["body"]["submitter_agent_id"] == "agent-x"
    submit_out = result.get("submitter", {})
    assert submit_out.get("submitted") is True
    assert submit_out.get("mission_id") == "mis_echo01"


def test_get_components_share_one_client(make_client):
    client, _ = make_client({}, agent_id="agent-x")
    comps = get_components(client=client, agent_id="agent-x")
    assert set(comps) == set(EXPECTED_TOOL_NAMES)
    # All components reuse the SAME pooled client instance.
    assert all(c.client is client for c in comps.values())


# --------------------------------------------------------------------------- #
# Protocol economics: AIGEN/USDC reward + 0.5% fee
# --------------------------------------------------------------------------- #
def test_net_reward_applies_half_percent_fee():
    assert net_reward(500) == 497.5
    assert net_reward(1000) == 995.0
    assert haystack_oabp.PROTOCOL_FEE_RATE == 0.005


# --------------------------------------------------------------------------- #
# The example script must at least import/compile cleanly.
# --------------------------------------------------------------------------- #
def test_example_compiles():
    example = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "examples",
        "pipeline.py",
    )
    # Raises py_compile.PyCompileError on a syntax error.
    py_compile.compile(example, doraise=True)
