"""Offline unit tests for the letta_oabp integration.

All HTTP is mocked by patching ``urllib.request.urlopen`` (see the
``fake_marketplace`` fixture in conftest), so the four source tools run
deterministically and never touch the network. ``letta-client`` is never imported
except as a fake module (the ``fake_letta`` fixture), proving the package imports
and the tool functions are usable standalone, and that the registration wiring is
correct.

The suite also enforces the Letta-specific contract: each tool is **self-contained**
(its source string imports its own dependencies, carries a Google-style docstring,
and references no module-level name) and its source is extractable via
``inspect.getsource`` — which is exactly what Letta requires to register a tool.
"""

from __future__ import annotations

import ast
import inspect
import json
import os

import pytest

import letta_oabp
from letta_oabp import (
    TOOL_FUNCTIONS,
    TOOL_NAMES,
    build_tool_exec_environment,
    create_oabp_agent,
    load_agent_config,
    oabp_create_mission,
    oabp_get_stats,
    oabp_list_missions,
    oabp_submit_mission,
    register_tools,
    tool_names,
    upsert_tools,
)

EXPECTED_NAMES = [
    "oabp_list_missions",
    "oabp_create_mission",
    "oabp_submit_mission",
    "oabp_get_stats",
]


# --------------------------------------------------------------------------- #
# Package imports without letta-client; tool names are stable
# --------------------------------------------------------------------------- #
def test_imports_without_letta_client():
    """Acceptance: the package imports without the optional letta-client."""
    import importlib
    import sys

    # letta_client must NOT be required at import time.
    assert "letta_client" not in sys.modules or sys.modules.get("letta_client")
    importlib.reload(letta_oabp)
    assert hasattr(letta_oabp, "register_tools")
    assert hasattr(letta_oabp, "create_oabp_agent")


def test_tool_names_are_canonical():
    assert tool_names() == EXPECTED_NAMES
    assert TOOL_NAMES == EXPECTED_NAMES
    assert [fn.__name__ for fn in TOOL_FUNCTIONS] == EXPECTED_NAMES
    assert all(callable(fn) for fn in TOOL_FUNCTIONS)


# --------------------------------------------------------------------------- #
# Letta source-tool contract: self-contained + extractable + compiles
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("fn", TOOL_FUNCTIONS, ids=lambda f: f.__name__)
def test_each_tool_source_extractable_and_compiles(fn):
    """Acceptance: each tool's source is extractable and py_compiles."""
    src = inspect.getsource(fn)
    assert src.strip(), f"{fn.__name__} has empty source"
    # The source string Letta stores must be independently compilable.
    compile(src, f"<{fn.__name__}>", "exec")


@pytest.mark.parametrize("fn", TOOL_FUNCTIONS, ids=lambda f: f.__name__)
def test_each_tool_source_execs_in_bare_namespace(fn):
    """Definitive Letta check: the extracted source runs with zero imports.

    Letta registers a tool from ``inspect.getsource(fn)`` — which does NOT include
    the module's imports or any ``from __future__`` line — and re-executes that
    extracted source in a sandbox. So the ``def`` itself (signature annotations and
    defaults included) must execute in a bare namespace. This is why the tools are
    annotated with builtins only: a ``typing`` symbol in a signature would raise
    ``NameError`` here (and in Letta's sandbox).
    """
    src = inspect.getsource(fn)
    namespace: dict = {}
    # Compile WITHOUT inheriting this test module's __future__ flags, so the
    # exec mirrors Letta running the raw extracted source on its own.
    exec(compile(src, f"<{fn.__name__}>", "exec", dont_inherit=True), namespace)  # noqa: S102
    assert fn.__name__ in namespace
    # Only builtins may appear in the (now-evaluated) annotations — the type
    # object (e.g. ``dict``) or, under PEP 563, its name string (e.g. "dict").
    builtin_types = (str, int, float, bool, list, dict)
    builtin_type_names = {t.__name__ for t in builtin_types}
    for ann in namespace[fn.__name__].__annotations__.values():
        ok = ann in builtin_types or ann in builtin_type_names
        assert ok, f"{fn.__name__} has a non-builtin annotation {ann!r}"


@pytest.mark.parametrize("fn", TOOL_FUNCTIONS, ids=lambda f: f.__name__)
def test_each_tool_has_google_style_docstring(fn):
    """Acceptance: complete Google-style docstring (Letta derives the schema)."""
    doc = inspect.getdoc(fn)
    assert doc and len(doc) > 40, f"{fn.__name__} docstring too short"
    assert "Returns:" in doc, f"{fn.__name__} missing Returns: section"
    # Any tool that takes arguments must document them under an Args: section.
    params = [p for p in inspect.signature(fn).parameters]
    if params:
        assert "Args:" in doc, f"{fn.__name__} missing Args: section"
        for name in params:
            assert name in doc, f"{fn.__name__} docstring omits arg {name!r}"


@pytest.mark.parametrize("fn", TOOL_FUNCTIONS, ids=lambda f: f.__name__)
def test_each_tool_is_self_contained(fn):
    """All imports are INSIDE the body and no module-level name is referenced.

    Letta ships only the function source to a sandbox, so a tool may not depend on
    a module-level import, global, or sibling helper. We assert that (a) every
    ``import`` statement lives inside the function body, and (b) the only free
    names the body uses are builtins or names it imports/binds itself.
    """
    src = inspect.getsource(fn)
    tree = ast.parse(src)
    func_node = tree.body[0]
    assert isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef))

    # (a) No import at module scope of the snippet: all imports are within the def.
    module_level_imports = [
        n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))
    ]
    assert not module_level_imports, f"{fn.__name__}: import outside the body"
    body_imports = [
        n for n in ast.walk(func_node) if isinstance(n, (ast.Import, ast.ImportFrom))
    ]
    assert body_imports, f"{fn.__name__}: expected imports inside the body"

    # (b) Within the executable BODY (not the signature/annotations, which are
    # builtins-only and covered by the bare-exec test), every loaded name must be
    # bound locally (imported, assigned, an arg, a comprehension/with/except
    # target) or be a builtin. This proves the body references no module-level
    # import, global, or sibling helper.
    import builtins

    bound = {a.arg for a in func_node.args.args}
    bound |= {a.arg for a in getattr(func_node.args, "kwonlyargs", [])}
    body_nodes = list(func_node.body)  # the statements only — skip decorators/args
    for stmt in body_nodes:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bound.add((alias.asname or alias.name).split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    bound.add(alias.asname or alias.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    for sub in ast.walk(t):
                        if isinstance(sub, ast.Name):
                            bound.add(sub.id)
            elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                for sub in ast.walk(node.target):
                    if isinstance(sub, ast.Name):
                        bound.add(sub.id)
            elif isinstance(node, ast.withitem):
                optional_vars = node.optional_vars
                if optional_vars is not None:
                    for sub in ast.walk(optional_vars):
                        if isinstance(sub, ast.Name):
                            bound.add(sub.id)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                bound.add(node.name)

    builtin_names = set(dir(builtins)) | {"__name__"}
    loaded = set()
    for stmt in body_nodes:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                loaded.add(node.id)
    free = loaded - bound - builtin_names
    assert not free, f"{fn.__name__} body references non-local names: {sorted(free)}"


# --------------------------------------------------------------------------- #
# oabp_list_missions returns list[dict] against the stubbed transport
# --------------------------------------------------------------------------- #
def test_list_missions_returns_list_of_dicts(fake_marketplace):
    """Acceptance: oabp_list_missions returns list[dict] vs a stubbed transport."""
    out = oabp_list_missions()
    assert isinstance(out, list)
    assert out and all(isinstance(m, dict) for m in out)
    m0 = out[0]
    assert m0["id"] == "mis_a1b2c3"
    assert m0["reward"] == {"amount": 500, "currency": "AIGEN"}
    assert m0["verification_type"] == "oracle"
    assert m0["submission_count"] == 0
    # second mission already has a submission counted
    assert out[1]["submission_count"] == 1
    json.dumps(out)  # JSON-serialisable


def test_list_missions_status_and_limit(fake_marketplace):
    out = oabp_list_missions(status="open", limit=1)
    assert isinstance(out, list)
    assert len(out) == 1
    # the status filter went on the query string
    last = fake_marketplace.calls[-1]
    assert "status=open" in last["url"]
    assert last["method"] == "GET"


def test_list_missions_http_error_returns_list_with_error(fake_marketplace):
    import urllib.error

    fake_marketplace.errors[("GET", "/api/missions")] = urllib.error.HTTPError(
        "https://cryptogenesis.duckdns.org/api/missions", 500, "Server Error", {}, None
    )
    out = oabp_list_missions()
    assert isinstance(out, list) and len(out) == 1
    assert out[0]["error_type"] == "HTTPError"
    assert out[0]["status_code"] == 500
    json.dumps(out)


# --------------------------------------------------------------------------- #
# get_stats
# --------------------------------------------------------------------------- #
def test_get_stats(fake_marketplace):
    out = oabp_get_stats()
    assert out == {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000}
    json.dumps(out)


def test_get_stats_connection_error(fake_marketplace):
    import urllib.error

    fake_marketplace.errors[("GET", "/api/stats")] = urllib.error.URLError("down")
    out = oabp_get_stats()
    assert out["error_type"] == "URLError"
    assert "error" in out


# --------------------------------------------------------------------------- #
# create_mission — body + local validation
# --------------------------------------------------------------------------- #
def test_create_mission_sends_correct_body(fake_marketplace):
    out = oabp_create_mission(
        title="Audit MyToken",
        description="GoPlus safety review for 0xDEF",
        reward_amount=250,
        verification_type="oracle",
        deadline_hours=48,
        verification_params={"oracle_description": "safety review of 0xDEF"},
    )
    assert out["created"] is True
    assert out["mission"]["id"] == "mis_new001"

    body = fake_marketplace.calls[-1]["body"]
    assert body["creator_agent_id"] == "test-agent"  # from OABP_AGENT_ID env
    assert body["title"] == "Audit MyToken"
    assert body["reward_amount"] == 250.0
    assert body["reward_currency"] == "AIGEN"
    assert body["verification_type"] == "oracle"
    assert body["deadline_hours"] == 48.0
    assert body["verification_params"] == {"oracle_description": "safety review of 0xDEF"}


def test_create_mission_explicit_currency_and_agent(fake_marketplace):
    out = oabp_create_mission(
        title="x",
        description="d",
        reward_amount=10,
        verification_type="first_valid_match",
        deadline_hours=1,
        reward_currency="usdc",  # normalised to USDC
        verification_params={"regex": "0x[0-9a-f]+"},
        creator_agent_id="creator-1",
    )
    assert out["created"] is True
    body = fake_marketplace.calls[-1]["body"]
    assert body["reward_currency"] == "USDC"
    assert body["creator_agent_id"] == "creator-1"


def test_create_mission_bad_verification_type_no_network(fake_marketplace):
    out = oabp_create_mission(
        title="x", description="d", reward_amount=10,
        verification_type="telepathy", deadline_hours=1,
    )
    assert out["error_type"] == "ValueError"
    assert "verification_type" in out["error"]
    assert fake_marketplace.calls == []  # never hit the network


def test_create_mission_nonpositive_reward_no_network(fake_marketplace):
    out = oabp_create_mission(
        title="x", description="d", reward_amount=0,
        verification_type="oracle", deadline_hours=1,
    )
    assert out["error_type"] == "ValueError"
    assert fake_marketplace.calls == []


def test_create_mission_missing_agent_id(fake_marketplace, monkeypatch):
    monkeypatch.delenv("OABP_AGENT_ID", raising=False)
    out = oabp_create_mission(
        title="x", description="d", reward_amount=10,
        verification_type="oracle", deadline_hours=1,
    )
    assert out["error_type"] == "ValueError"
    assert "OABP_AGENT_ID" in out["error"]
    assert fake_marketplace.calls == []


# --------------------------------------------------------------------------- #
# submit_mission — body + validation
# --------------------------------------------------------------------------- #
def test_submit_mission_sends_correct_body(fake_marketplace):
    out = oabp_submit_mission(mission_id="mis_a1b2c3", proof="0xC0ffee")
    assert out["submitted"] is True
    assert out["mission_id"] == "mis_a1b2c3"
    assert out["response"]["accepted"] is True
    assert out["response"]["resolution"]["reward_paid"] == 497.5

    last = fake_marketplace.calls[-1]
    assert last["method"] == "POST"
    assert last["url"].endswith("/api/missions/mis_a1b2c3/submit")
    assert last["body"] == {"submitter_agent_id": "test-agent", "proof": "0xC0ffee"}


def test_submit_mission_empty_proof_no_network(fake_marketplace):
    out = oabp_submit_mission(mission_id="mis_a1b2c3", proof="")
    assert out["error_type"] == "ValueError"
    assert fake_marketplace.calls == []


def test_submit_mission_empty_id_no_network(fake_marketplace):
    out = oabp_submit_mission(mission_id="  ", proof="0xABC")
    assert out["error_type"] == "ValueError"
    assert fake_marketplace.calls == []


# --------------------------------------------------------------------------- #
# agent_config.json — valid JSON, >=4 tool names, persona + human
# --------------------------------------------------------------------------- #
def test_agent_config_is_valid_json_with_four_tools():
    """Acceptance: agent_config.json is valid JSON listing >=4 tool names."""
    cfg = load_agent_config()  # parses + validates the bundled file
    assert isinstance(cfg["tools"], list)
    assert len(cfg["tools"]) >= 4
    assert set(EXPECTED_NAMES).issubset(set(cfg["tools"]))

    labels = {b["label"] for b in cfg["memory_blocks"]}
    assert "persona" in labels and "human" in labels
    assert cfg["model"] and cfg["embedding"]


def test_agent_config_path_is_real_file():
    assert os.path.isfile(letta_oabp.AGENT_CONFIG_PATH)
    with open(letta_oabp.AGENT_CONFIG_PATH, "r", encoding="utf-8") as fh:
        json.load(fh)  # must not raise


# --------------------------------------------------------------------------- #
# build_tool_exec_environment
# --------------------------------------------------------------------------- #
def test_build_tool_exec_environment_minimal_and_full():
    env = build_tool_exec_environment(base_url="https://x", agent_id="a")
    assert env == {"OABP_BASE_URL": "https://x", "OABP_AGENT_ID": "a"}
    env2 = build_tool_exec_environment(
        base_url="https://x", agent_id="a", api_key="k"
    )
    assert env2["OABP_API_KEY"] == "k"
    # empty agent id is omitted
    assert "OABP_AGENT_ID" not in build_tool_exec_environment(base_url="https://x")


# --------------------------------------------------------------------------- #
# register_tools / create_oabp_agent — fake letta_client, lazy import
# --------------------------------------------------------------------------- #
def test_upsert_tools_ships_self_contained_sources(fake_letta):
    tools = upsert_tools(fake_letta)
    assert [t.name for t in tools] == EXPECTED_NAMES
    # Each upserted source is what inspect.getsource returned (Letta's model) and
    # imports its own deps inside the body.
    upserts = fake_letta.recorder["upserts"]
    assert [u["name"] for u in upserts] == EXPECTED_NAMES
    for u in upserts:
        assert "def %s" % u["name"] in u["source"]
        assert "import" in u["source"]


def test_register_tools_attaches_and_sets_env(fake_letta):
    tools = register_tools(
        fake_letta, agent_id="agent-001", oabp_agent_id="hunter",
        base_url="https://cryptogenesis.duckdns.org",
    )
    assert [t.name for t in tools] == EXPECTED_NAMES
    # attached all four to the agent
    attached_ids = [a["tool_id"] for a in fake_letta.recorder["attaches"]]
    assert attached_ids == [t.id for t in tools]
    assert all(a["agent_id"] == "agent-001" for a in fake_letta.recorder["attaches"])
    # wrote the OABP config into the agent's tool sandbox
    mod = fake_letta.recorder["modifies"][-1]
    env = mod["tool_exec_environment_variables"]
    assert env["OABP_AGENT_ID"] == "hunter"
    assert env["OABP_BASE_URL"] == "https://cryptogenesis.duckdns.org"


def test_register_tools_without_agent_only_upserts(fake_letta):
    register_tools(fake_letta)  # no agent_id
    assert len(fake_letta.recorder["upserts"]) == 4
    assert fake_letta.recorder["attaches"] == []
    assert fake_letta.recorder["modifies"] == []


def test_create_oabp_agent_wires_tools(fake_letta):
    agent = create_oabp_agent(fake_letta, oabp_agent_id="hunter")
    assert agent.id == "agent-001"
    # four tools upserted, agent created with the tools attached by name
    assert len(fake_letta.recorder["upserts"]) == 4
    created = fake_letta.recorder["creates"][-1]
    assert set(EXPECTED_NAMES).issubset(set(created["tools"]))
    assert created["memory_blocks"][0]["label"] in {"persona", "human"}
    env = created["tool_exec_environment_variables"]
    assert env["OABP_AGENT_ID"] == "hunter"
    assert env["OABP_BASE_URL"] == letta_oabp.DEFAULT_BASE_URL


# --------------------------------------------------------------------------- #
# register_tools references letta-client LAZILY (module imports without it)
# --------------------------------------------------------------------------- #
def test_register_imports_letta_lazily(monkeypatch):
    """Acceptance: register_tools references letta-client lazily.

    With letta_client absent, importing the module is fine; only calling
    register_tools raises a helpful ImportError.
    """
    import builtins

    real_import = builtins.__import__

    def _blocked(name, *args, **kwargs):
        if name == "letta_client" or name.startswith("letta_client."):
            raise ImportError("No module named 'letta_client'")
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(__import__("sys").modules, "letta_client", raising=False)
    monkeypatch.setattr(builtins, "__import__", _blocked)

    # Importing the package and its register module is unaffected.
    import importlib

    importlib.reload(letta_oabp)

    class _Dummy:
        pass

    with pytest.raises(ImportError) as ei:
        upsert_tools(_Dummy())
    assert "letta-client" in str(ei.value)
