"""Offline unit tests for the pydantic_ai_oabp integration.

All HTTP is mocked via the ``RoutingFakeSession`` injected into the underlying
OABP SDK client (see conftest), so the suite is deterministic and never touches
the network. The suite also runs **whether or not ``pydantic-ai`` is installed**:

* the tool *functions* are plain callables that take ``ctx: RunContext[OabpDeps]``
  first; tests call them directly with a ``RunContext`` (the real one if
  pydantic-ai is present, else the structural shim from ``_compat``);
* registration mechanics are tested against a tiny ``FakeAgent`` (so they do not
  require pydantic-ai), and the lazy-import gate is tested separately.
"""

from __future__ import annotations

import inspect
import json
import typing

import pytest

import pydantic_ai_oabp
from pydantic_ai_oabp import (
    HAS_PYDANTIC_AI,
    OabpDeps,
    OabpToolset,
    RunContext,
    build_agent,
    register,
    tool_functions,
    tool_names,
)
from pydantic_ai_oabp.toolset import (
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
    "list_missions",
    "get_mission",
    "create_mission",
    "submit_mission",
    "get_stats",
    "get_reputation",
]


# --------------------------------------------------------------------------- #
# A tiny stand-in for pydantic_ai.Agent so registration is testable offline.
# --------------------------------------------------------------------------- #
class FakeAgent:
    """Records ``@agent.tool``-registered functions, like pydantic_ai.Agent.tool."""

    def __init__(self):
        self.registered = []  # list of (func, kwargs)

    def tool(self, func=None, **kwargs):
        # Mirror pydantic-ai's agent.tool: usable as @agent.tool and
        # agent.tool(func, ...); returns the function unchanged.
        if func is None:
            def _decorate(f):
                self.registered.append((f, kwargs))
                return f
            return _decorate
        self.registered.append((func, kwargs))
        return func


@pytest.fixture
def patch_pydantic_ai(monkeypatch):
    """Make ``load_pydantic_ai()`` a no-op so register() works without the dep."""
    import pydantic_ai_oabp._compat as compat
    import pydantic_ai_oabp.toolset as toolset_mod

    monkeypatch.setattr(compat, "load_pydantic_ai", lambda: None)
    monkeypatch.setattr(toolset_mod, "load_pydantic_ai", lambda: None)
    return monkeypatch


# --------------------------------------------------------------------------- #
# Importability + discovery (acceptance: importable without pydantic-ai)
# --------------------------------------------------------------------------- #
def test_package_imports_without_pydantic_ai():
    # The whole module graph is importable regardless of pydantic-ai presence.
    assert hasattr(pydantic_ai_oabp, "OabpToolset")
    assert hasattr(pydantic_ai_oabp, "OabpDeps")
    assert hasattr(pydantic_ai_oabp, "register")
    assert hasattr(pydantic_ai_oabp, "build_agent")
    # HAS_PYDANTIC_AI reflects reality; this test must pass in both worlds.
    assert isinstance(HAS_PYDANTIC_AI, bool)


def test_toolset_registers_at_least_six_named_tools():
    ts = OabpToolset()
    assert len(ts) >= 6
    assert ts.names == EXPECTED_NAMES
    assert tool_names() == EXPECTED_NAMES
    assert len(tool_functions()) >= 6


def test_tool_functions_have_typed_args_and_docstrings():
    """Acceptance: each tool fn uses RunContext + typed args + a docstring.

    Pydantic-AI derives a tool's JSON schema from exactly these — the signature
    (type hints) and the (Google-style) docstring — so we assert their presence
    directly, which holds with or without pydantic-ai installed.
    """
    for func in tool_functions():
        name = func.__name__
        sig = inspect.signature(func)
        params = list(sig.parameters.values())

        # First param is the injected RunContext[OabpDeps] (excluded from schema).
        assert params, f"{name} has no parameters"
        assert params[0].name == "ctx", f"{name} first param must be ctx"
        hints = typing.get_type_hints(func)
        assert "ctx" in hints, f"{name} ctx is not annotated"

        # A non-trivial docstring (parsed into tool + arg descriptions).
        doc = inspect.getdoc(func) or ""
        assert len(doc) > 40, f"{name} has a trivial docstring"

        # Every *model-facing* parameter (all but ctx) is type-annotated. This is
        # what lets pydantic-ai build a correct argument schema from hints.
        for p in params[1:]:
            assert p.annotation is not inspect.Parameter.empty, (
                f"{name} arg {p.name!r} is missing a type hint"
            )

        # A documented return annotation exists too.
        assert "return" in hints, f"{name} missing a return annotation"


def test_toolset_register_adds_tools_to_agent(patch_pydantic_ai):
    """register() attaches all six tools via agent.tool (Google docstrings)."""
    agent = FakeAgent()
    returned = OabpToolset().register(agent)
    assert returned is agent
    assert [f.__name__ for f, _ in agent.registered] == EXPECTED_NAMES
    # Google docstring format is requested so arg docs become param descriptions.
    assert all(kw.get("docstring_format") == "google" for _, kw in agent.registered)


def test_module_level_register_and_subset(patch_pydantic_ai):
    agent = FakeAgent()
    out = register(agent, include=["list_missions", "get_stats"])
    assert out is agent
    assert [f.__name__ for f, _ in agent.registered] == ["list_missions", "get_stats"]


def test_toolset_include_exclude_normalises_order():
    # exclude drops write tools -> a read-only toolset, canonical order kept.
    ro = OabpToolset(exclude={"create_mission", "submit_mission"})
    assert ro.names == ["list_missions", "get_mission", "get_stats", "get_reputation"]
    # include is order-normalised to TOOL_NAMES regardless of input order.
    sub = OabpToolset(include=["get_stats", "list_missions"])
    assert sub.names == ["list_missions", "get_stats"]
    # unknown name -> ValueError.
    with pytest.raises(ValueError):
        OabpToolset(include=["nope"])


# --------------------------------------------------------------------------- #
# THE acceptance test — get_stats over a fake RunContext/deps
# --------------------------------------------------------------------------- #
def test_get_stats_over_fake_ctx_returns_resolved_open_lifetime(make_ctx):
    """Acceptance: build the toolset against a fake RunContext/deps and assert
    get_stats returns resolved / open / lifetime fields."""
    routes = {("GET", "/api/stats"): FakeResponse(200, SAMPLE_STATS)}
    ctx, session = make_ctx(routes)

    tools = OabpToolset().as_dict()
    out = tools["get_stats"](ctx)

    assert out == {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000.0}
    # the three required fields are present and typed.
    assert set(out) >= {"resolved", "open", "lifetime_reward_aigen_paid"}
    assert isinstance(out["resolved"], int)
    assert isinstance(out["open"], int)
    assert isinstance(out["lifetime_reward_aigen_paid"], float)
    json.dumps(out)  # JSON-serialisable

    # the SDK actually issued the GET we expect.
    assert session.calls and session.calls[0]["method"] == "GET"
    assert "/api/stats" in session.calls[0]["url"]


# --------------------------------------------------------------------------- #
# list_missions parses a mis_* fixture carrying min_submitter_elo
# --------------------------------------------------------------------------- #
def test_list_missions_parses_mis_id_and_min_submitter_elo(make_ctx):
    routes = {("GET", "/api/missions"): FakeResponse(200, [SAMPLE_MISSION])}
    ctx, session = make_ctx(routes, agent_id="agent-x")
    tools = OabpToolset().as_dict()

    out = tools["list_missions"](ctx)
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

    json.dumps(out)  # no dataclasses / enums leaking
    assert "/api/missions" in session.calls[0]["url"]


def test_list_missions_limit(make_ctx):
    many = [dict(SAMPLE_MISSION, id=f"mis_{i}") for i in range(5)]
    routes = {("GET", "/api/missions"): FakeResponse(200, many)}
    ctx, _ = make_ctx(routes)
    tools = OabpToolset().as_dict()
    out = tools["list_missions"](ctx, limit=2)
    assert out["count"] == 2
    assert [m["id"] for m in out["missions"]] == ["mis_0", "mis_1"]


# --------------------------------------------------------------------------- #
# Read tools
# --------------------------------------------------------------------------- #
def test_get_mission_with_submissions_and_resolution(make_ctx):
    routes = {
        ("GET", "/api/missions/mis_abc123"): FakeResponse(200, SAMPLE_MISSION_DETAIL)
    }
    ctx, _ = make_ctx(routes)
    out = OabpToolset().as_dict()["get_mission"](ctx, mission_id="mis_abc123")
    assert out["id"] == "mis_abc123"
    assert out["submission_count"] == 1
    assert out["submissions"][0]["submitter_agent_id"] == "agent-9"
    assert out["resolution"]["winner_agent_id"] == "agent-9"
    assert out["resolution"]["reward_paid"] == 497.5
    json.dumps(out)


def test_get_reputation_uses_default_agent_id(make_ctx):
    routes = {
        ("GET", "/api/agents/agent-9/reputation"): FakeResponse(200, SAMPLE_REPUTATION)
    }
    ctx, _ = make_ctx(routes, agent_id="agent-9")
    out = OabpToolset().as_dict()["get_reputation"](ctx)
    assert out["agent_id"] == "agent-9"
    assert out["aigen_balance"] == 1500.0
    assert out["missions_won"] == 4


# --------------------------------------------------------------------------- #
# Write tools — assert the exact body the SDK sends to the server
# --------------------------------------------------------------------------- #
def test_create_mission_sends_correct_body(make_ctx):
    captured = {}

    def handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        return FakeResponse(200, dict(SAMPLE_MISSION, id="mis_new"))

    routes = {("POST", "/api/missions"): handler}
    ctx, _ = make_ctx(routes, agent_id="creator-1")

    out = OabpToolset().as_dict()["create_mission"](
        ctx,
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
    assert body["creator_agent_id"] == "creator-1"  # default agent_id from deps
    assert body["title"] == "Audit MyToken"
    assert body["reward_amount"] == 250.0
    assert body["reward_currency"] == "AIGEN"
    assert body["verification_type"] == "oracle"
    assert body["deadline_hours"] == 48.0
    assert body["verification_params"] == {"oracle_description": "safety review of 0xDEF"}


def test_submit_mission_sends_correct_body(make_ctx):
    captured = {}

    def handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        return FakeResponse(200, {"accepted": True, "resolution": {"winner_agent_id": "sub-1"}})

    routes = {("POST", "/missions/mis_abc123/submit"): handler}
    ctx, _ = make_ctx(routes, agent_id="sub-1")

    out = OabpToolset().as_dict()["submit_mission"](
        ctx, mission_id="mis_abc123", proof="https://github.com/me/repo"
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
def test_get_mission_404_returns_error_string(make_ctx):
    routes = {("GET", "/api/missions/nope"): FakeResponse(404, {"error": "not found"})}
    ctx, _ = make_ctx(routes, max_retries=0)
    out = OabpToolset().as_dict()["get_mission"](ctx, mission_id="nope")
    assert isinstance(out, str)
    assert out.startswith("ERROR OabpNotFoundError")
    assert "404" in out


def test_list_missions_server_error_returns_error_string(make_ctx):
    routes = {("GET", "/api/missions"): FakeResponse(500, {"error": "boom"})}
    ctx, _ = make_ctx(routes, max_retries=0)
    out = OabpToolset().as_dict()["list_missions"](ctx)
    assert isinstance(out, str)
    assert out.startswith("ERROR OabpServerError")
    assert "500" in out


def test_reputation_without_agent_id_returns_error_string(make_ctx):
    # No default agent_id and none passed -> structured error, no network call.
    ctx, session = make_ctx({})
    out = OabpToolset().as_dict()["get_reputation"](ctx)
    assert isinstance(out, str)
    assert out.startswith("ERROR OabpValidationError")
    assert session.calls == []  # never hit the network


# --------------------------------------------------------------------------- #
# Deps injection: same toolset, two identities across runs
# --------------------------------------------------------------------------- #
def test_same_toolset_two_identities_via_deps(make_ctx):
    """One toolset, swap deps -> different creator_agent_id (the DI contract)."""
    bodies = []

    def handler(method, url, kwargs):
        bodies.append(kwargs.get("json"))
        return FakeResponse(200, dict(SAMPLE_MISSION, id="mis_x"))

    create = OabpToolset().as_dict()["create_mission"]

    ctx_a, _ = make_ctx({("POST", "/api/missions"): handler}, agent_id="agent-a")
    ctx_b, _ = make_ctx({("POST", "/api/missions"): handler}, agent_id="agent-b")

    common = dict(
        title="t",
        description="d",
        reward_amount=5,
        verification_type="first_valid_match",
        deadline_hours=1,
        verification_params={"regex": "X"},
    )
    create(ctx_a, **common)
    create(ctx_b, **common)
    assert bodies[0]["creator_agent_id"] == "agent-a"
    assert bodies[1]["creator_agent_id"] == "agent-b"


def test_explicit_agent_id_overrides_deps_default(make_ctx):
    bodies = []

    def handler(method, url, kwargs):
        bodies.append(kwargs.get("json"))
        return FakeResponse(200, {"accepted": True})

    ctx, _ = make_ctx({("POST", "/missions/mis_1/submit"): handler}, agent_id="default-agent")
    OabpToolset().as_dict()["submit_mission"](
        ctx, mission_id="mis_1", proof="p", submitter_agent_id="override-agent"
    )
    assert bodies[0]["submitter_agent_id"] == "override-agent"


# --------------------------------------------------------------------------- #
# OabpDeps.create
# --------------------------------------------------------------------------- #
def test_oabp_deps_create_builds_client_and_agent_id():
    deps = OabpDeps.create(agent_id="me", base_url="https://example.test")
    assert deps.agent_id == "me"
    assert deps.client.agent_id == "me"
    assert deps.client.base_url == "https://example.test"
    assert deps.resolve_agent_id() == "me"
    assert deps.resolve_agent_id("other") == "other"


def test_oabp_deps_create_inherits_agent_id_from_client():
    from pydantic_ai_oabp import OabpClient

    client = OabpClient(agent_id="from-client")
    deps = OabpDeps.create(client=client)
    assert deps.agent_id == "from-client"


# --------------------------------------------------------------------------- #
# Serialiser helpers
# --------------------------------------------------------------------------- #
def test_mission_to_dict_is_json_serialisable():
    from pydantic_ai_oabp import Mission

    d = mission_to_dict(Mission.from_dict(SAMPLE_MISSION_DETAIL))
    json.dumps(d)  # must not raise
    assert d["id"] == "mis_abc123"
    assert d["verification_type"] == "oracle"  # enum -> str
    assert d["reward"]["currency"] == "AIGEN"
    assert d["verification_params"]["min_submitter_elo"] == 1200


def test_stats_and_reputation_to_dict():
    from pydantic_ai_oabp import Reputation, Stats

    assert stats_to_dict(Stats.from_dict(SAMPLE_STATS)) == {
        "resolved": 7,
        "open": 3,
        "lifetime_reward_aigen_paid": 108000.0,
    }
    rep = reputation_to_dict(Reputation.from_dict(SAMPLE_REPUTATION))
    assert rep["agent_id"] == "agent-9"
    assert rep["aigen_balance"] == 1500.0


# --------------------------------------------------------------------------- #
# build_agent / register gating on the optional dependency
# --------------------------------------------------------------------------- #
def test_build_agent_requires_pydantic_ai():
    if HAS_PYDANTIC_AI:
        agent = build_agent("openai:gpt-4o-mini", agent_id="a")
        # Real Agent constructed; it carries our default-id hint.
        assert getattr(agent, "oabp_default_agent_id", None) == "a"
    else:
        with pytest.raises(RuntimeError):
            build_agent("openai:gpt-4o-mini", agent_id="a")


def test_register_requires_pydantic_ai_when_absent():
    # When pydantic-ai is absent, register() onto a real-ish agent must raise the
    # clear dependency error from the lazy import (no monkeypatch here).
    if not HAS_PYDANTIC_AI:
        with pytest.raises(RuntimeError):
            OabpToolset().register(FakeAgent())


def test_runcontext_shim_or_real_carries_deps():
    # RunContext (real or shim) must expose .deps so tools can read the client.
    from pydantic_ai_oabp import OabpClient

    deps = OabpDeps(client=OabpClient(agent_id="x"), agent_id="x")
    ctx = RunContext(deps=deps)
    assert ctx.deps is deps
