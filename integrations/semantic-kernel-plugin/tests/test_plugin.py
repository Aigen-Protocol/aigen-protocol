"""Offline unit tests for the sk_oabp Semantic Kernel plugin.

All HTTP is mocked via the ``RoutingFakeSession`` injected into the underlying
OABP SDK client (see conftest), so the suite is deterministic and never touches
the network. The suite also runs whether or not ``semantic-kernel`` is installed:

* the ``OabpPlugin`` methods are decorated with ``@kernel_function``; with the
  real SDK that records ``__kernel_function__`` metadata, and without it the
  fallback records the same attributes while leaving the method directly
  callable — so the tests call the bound methods directly in both worlds and
  read metadata off the underlying functions.

The acceptance checks are explicitly exercised:
* the package imports with or without ``semantic-kernel``;
* ``OabpPlugin`` exposes >= 6 ``@kernel_function`` methods, each with a name +
  description;
* ``submit_mission`` over a mock session returns a JSON **ack string**.
"""

from __future__ import annotations

import json

import pytest

import sk_oabp
from sk_oabp import HAS_SK, OabpPlugin, add_oabp_plugin, function_names
from sk_oabp.plugin import mission_to_dict, reputation_to_dict, stats_to_dict

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
# Metadata helpers (real semantic-kernel vs no-op fallback)
# --------------------------------------------------------------------------- #
def _unwrap(method):
    """Return the underlying function carrying the @kernel_function metadata.

    Semantic Kernel records metadata on the function object; a bound method
    proxies attribute access to ``__func__``, so reading off the bound method
    works in both modes, but we normalise to the function for clarity.
    """
    return getattr(method, "__func__", method)


def kf_name(method) -> str:
    """The kernel-function name recorded by @kernel_function, in either mode."""
    fn = _unwrap(method)
    return getattr(fn, "__kernel_function_name__", None) or getattr(
        fn, "oabp_function_name", fn.__name__
    )


def kf_description(method):
    fn = _unwrap(method)
    return getattr(fn, "__kernel_function_description__", None) or getattr(
        fn, "oabp_function_description", None
    )


def is_kernel_function(method) -> bool:
    return bool(getattr(_unwrap(method), "__kernel_function__", False))


def kernel_methods(plugin):
    """All bound methods on ``plugin`` marked as kernel functions, in name order."""
    found = {}
    for attr in dir(plugin):
        if attr.startswith("_"):
            continue
        member = getattr(plugin, attr)
        if callable(member) and is_kernel_function(member):
            found[kf_name(member)] = member
    return found


def new_plugin(make_client, routes, **kw):
    client, session = make_client(routes, **kw)
    return OabpPlugin(client=client, agent_id=kw.get("agent_id")), session


# --------------------------------------------------------------------------- #
# Importability (acceptance: importable without semantic-kernel)
# --------------------------------------------------------------------------- #
def test_package_imports_without_semantic_kernel():
    # The whole module graph is importable regardless of the SDK being present.
    assert hasattr(sk_oabp, "OabpPlugin")
    assert hasattr(sk_oabp, "add_oabp_plugin")
    # HAS_SK reflects reality; this test must pass in both worlds.
    assert isinstance(HAS_SK, bool)
    assert sk_oabp.USING_SEMANTIC_KERNEL == HAS_SK


def test_methods_are_callable_without_semantic_kernel():
    """Acceptance: @kernel_function degrades to a no-op so methods stay callable."""
    plugin = OabpPlugin(agent_id="agent-x")  # builds a default client; no network used here
    # The decorated attributes are still ordinary bound methods.
    assert callable(plugin.list_missions)
    assert callable(plugin.submit_mission)
    # And they are marked as kernel functions in both modes.
    assert is_kernel_function(plugin.list_missions)
    assert is_kernel_function(plugin.submit_mission)


# --------------------------------------------------------------------------- #
# >= 6 @kernel_function methods, each with name + description
# --------------------------------------------------------------------------- #
def test_plugin_exposes_at_least_six_kernel_functions():
    plugin = OabpPlugin(agent_id="agent-x")
    methods = kernel_methods(plugin)
    assert len(methods) >= 6
    assert sorted(methods) == sorted(EXPECTED_NAMES)
    assert function_names() == EXPECTED_NAMES


def test_every_kernel_function_has_name_and_description():
    """Acceptance: each @kernel_function carries a name + a real description."""
    plugin = OabpPlugin(agent_id="agent-x")
    for name, method in kernel_methods(plugin).items():
        assert name in EXPECTED_NAMES
        desc = kf_description(method)
        assert desc and len(desc) > 20, f"{name} has a trivial description"


def _peel_optional(ann):
    """Strip an outer Optional[...] that get_type_hints adds for None-defaulted params.

    A parameter declared ``Annotated[Optional[T], "desc"] = None`` resolves under
    ``typing.get_type_hints`` to ``Optional[Annotated[Optional[T], "desc"]]`` — the
    None default makes Python add an *outer* Optional that hides ``__metadata__``.
    Semantic Kernel peels that outer Optional when reading parameter metadata; this
    helper does the same so the description is reachable for required and optional
    parameters alike.
    """
    import typing

    if typing.get_origin(ann) is typing.Union:
        non_none = [a for a in typing.get_args(ann) if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return ann


def test_kernel_function_parameters_are_annotated():
    """The methods use typing.Annotated for their typed parameters."""
    import typing

    plugin = OabpPlugin(agent_id="agent-x")
    hints = typing.get_type_hints(
        _unwrap(plugin.create_mission), include_extras=True
    )
    # Every model-facing param of create_mission must be Annotated[...] with a
    # non-empty description — including the optional ones (peel outer Optional).
    for pname in (
        "title",
        "description",
        "reward_amount",
        "verification_type",
        "deadline_hours",
        "reward_currency",
        "verification_params",
        "creator_agent_id",
    ):
        ann = _peel_optional(hints[pname])
        meta = getattr(ann, "__metadata__", ())
        assert meta, f"{pname} is not Annotated[...] with a description"
        assert isinstance(meta[0], str) and meta[0]


# --------------------------------------------------------------------------- #
# Read functions — list_missions parses a mis_* fixture w/ min_submitter_elo
# --------------------------------------------------------------------------- #
def test_list_missions_parses_mis_id_and_min_submitter_elo(make_client):
    routes = {("GET", "/api/missions"): FakeResponse(200, [SAMPLE_MISSION])}
    plugin, session = new_plugin(make_client, routes, agent_id="agent-x")

    raw = plugin.list_missions()
    assert isinstance(raw, str)  # SK-friendly JSON string
    out = json.loads(raw)
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

    # the SDK actually issued the GET we expect.
    assert session.calls and session.calls[0]["method"] == "GET"
    assert "/api/missions" in session.calls[0]["url"]


def test_list_missions_limit(make_client):
    many = [dict(SAMPLE_MISSION, id=f"mis_{i}") for i in range(5)]
    routes = {("GET", "/api/missions"): FakeResponse(200, many)}
    plugin, _ = new_plugin(make_client, routes)
    out = json.loads(plugin.list_missions(limit=2))
    assert out["count"] == 2
    assert [m["id"] for m in out["missions"]] == ["mis_0", "mis_1"]


def test_get_mission_with_submissions_and_resolution(make_client):
    routes = {
        ("GET", "/api/missions/mis_abc123"): FakeResponse(200, SAMPLE_MISSION_DETAIL)
    }
    plugin, _ = new_plugin(make_client, routes)
    out = json.loads(plugin.get_mission(mission_id="mis_abc123"))
    assert out["id"] == "mis_abc123"
    assert out["submission_count"] == 1
    assert out["submissions"][0]["submitter_agent_id"] == "agent-9"
    assert out["resolution"]["winner_agent_id"] == "agent-9"
    assert out["resolution"]["reward_paid"] == 497.5


def test_get_stats(make_client):
    routes = {("GET", "/api/stats"): FakeResponse(200, SAMPLE_STATS)}
    plugin, _ = new_plugin(make_client, routes)
    out = json.loads(plugin.get_stats())
    assert out == {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000.0}


def test_get_reputation_uses_default_agent_id(make_client):
    routes = {
        ("GET", "/api/agents/agent-9/reputation"): FakeResponse(200, SAMPLE_REPUTATION)
    }
    plugin, _ = new_plugin(make_client, routes, agent_id="agent-9")
    out = json.loads(plugin.get_reputation())
    assert out["agent_id"] == "agent-9"
    assert out["aigen_balance"] == 1500.0
    assert out["missions_won"] == 4


# --------------------------------------------------------------------------- #
# Write functions — assert the exact body the SDK sends to the server
# --------------------------------------------------------------------------- #
def test_create_mission_sends_correct_body(make_client):
    captured = {}

    def handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        return FakeResponse(200, dict(SAMPLE_MISSION, id="mis_new"))

    routes = {("POST", "/api/missions"): handler}
    plugin, _ = new_plugin(make_client, routes, agent_id="creator-1")

    out = json.loads(
        plugin.create_mission(
            title="Audit MyToken",
            description="GoPlus safety review for 0xDEF",
            reward_amount=250,
            verification_type="oracle",
            deadline_hours=48,
            verification_params={"oracle_description": "safety review of 0xDEF"},
        )
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


# --------------------------------------------------------------------------- #
# THE acceptance test — submit_mission over a mock session -> JSON ack string
# --------------------------------------------------------------------------- #
def test_submit_mission_returns_json_ack_string(make_client):
    captured = {}

    def handler(method, url, kwargs):
        captured["body"] = kwargs.get("json")
        return FakeResponse(
            200, {"accepted": True, "resolution": {"winner_agent_id": "sub-1"}}
        )

    routes = {("POST", "/missions/mis_abc123/submit"): handler}
    plugin, _ = new_plugin(make_client, routes, agent_id="sub-1")

    ack = plugin.submit_mission(
        mission_id="mis_abc123",
        proof="https://github.com/me/repo",
    )
    # The return value is a JSON *string* (SK-friendly), not a dict.
    assert isinstance(ack, str)
    out = json.loads(ack)
    assert out["submitted"] is True
    assert out["mission_id"] == "mis_abc123"
    assert out["response"]["accepted"] is True
    assert out["response"]["resolution"]["winner_agent_id"] == "sub-1"

    # The SDK sent the exact body we expect, using the default agent_id.
    body = captured["body"]
    assert body["submitter_agent_id"] == "sub-1"
    assert body["proof"] == "https://github.com/me/repo"


# --------------------------------------------------------------------------- #
# Error handling — SDK errors become a JSON {error:{...}} object string
# --------------------------------------------------------------------------- #
def test_get_mission_404_returns_json_error_object(make_client):
    routes = {("GET", "/api/missions/nope"): FakeResponse(404, {"error": "not found"})}
    plugin, _ = new_plugin(make_client, routes, max_retries=0)
    raw = plugin.get_mission(mission_id="nope")
    assert isinstance(raw, str)
    out = json.loads(raw)
    assert out["error"]["type"] == "OabpNotFoundError"
    assert out["error"]["status_code"] == 404


def test_list_missions_server_error_returns_json_error_object(make_client):
    routes = {("GET", "/api/missions"): FakeResponse(500, {"error": "boom"})}
    plugin, _ = new_plugin(make_client, routes, max_retries=0)
    out = json.loads(plugin.list_missions())
    assert out["error"]["type"] == "OabpServerError"
    assert out["error"]["status_code"] == 500


def test_reputation_without_agent_id_returns_json_error_object(make_client):
    # No default agent_id and none passed -> structured error, no network call.
    plugin, session = new_plugin(make_client, {})
    out = json.loads(plugin.get_reputation())
    assert out["error"]["type"] == "OabpValidationError"
    assert session.calls == []  # never hit the network


# --------------------------------------------------------------------------- #
# Serialiser helpers
# --------------------------------------------------------------------------- #
def test_mission_to_dict_is_json_serialisable():
    from sk_oabp import Mission

    d = mission_to_dict(Mission.from_dict(SAMPLE_MISSION_DETAIL))
    json.dumps(d)  # must not raise
    assert d["id"] == "mis_abc123"
    assert d["verification_type"] == "oracle"  # enum -> str
    assert d["reward"]["currency"] == "AIGEN"
    assert d["verification_params"]["min_submitter_elo"] == 1200


def test_stats_and_reputation_to_dict():
    from sk_oabp import Reputation, Stats

    assert stats_to_dict(Stats.from_dict(SAMPLE_STATS)) == {
        "resolved": 7,
        "open": 3,
        "lifetime_reward_aigen_paid": 108000.0,
    }
    rep = reputation_to_dict(Reputation.from_dict(SAMPLE_REPUTATION))
    assert rep["agent_id"] == "agent-9"
    assert rep["aigen_balance"] == 1500.0


# --------------------------------------------------------------------------- #
# add_oabp_plugin gating on the optional dependency
# --------------------------------------------------------------------------- #
def test_add_oabp_plugin_requires_semantic_kernel(make_client):
    client, _ = make_client({}, agent_id="a")
    if HAS_SK:
        from semantic_kernel import Kernel

        kernel = Kernel()
        plugin = add_oabp_plugin(kernel, client, agent_id="a", plugin_name="oabp")
        assert isinstance(plugin, OabpPlugin)
        # The kernel now exposes the plugin's functions under "oabp".
        funcs = kernel.get_plugin("oabp")
        names = set(getattr(funcs, "functions", funcs))
        for expected in EXPECTED_NAMES:
            assert expected in names
    else:
        class _FakeKernel:
            def __init__(self):
                self.added = []

            def add_plugin(self, plugin, plugin_name):
                self.added.append((plugin, plugin_name))

        with pytest.raises(RuntimeError):
            add_oabp_plugin(_FakeKernel(), client, agent_id="a")
