"""Acceptance tests for the plugin's YAML wiring.

Verifies that every YAML parses, the manifest lists all five tools and points at
the provider, the provider lists the five tool YAMLs and the credential schema
(``oabp_base_url`` + optional ``api_key`` + ``agent_id``), and that each
``tools/<name>.yaml`` is consistent with its ``tools/<name>.py``:

* ``identity.name`` == the file stem and the provider's tool list entry;
* every declared parameter name is actually read by the tool's ``_invoke``
  (via ``tool_parameters.get("<name>")`` / ``["<name>"]``), and every parameter
  the code reads that is user-facing is declared in the YAML.
"""

from __future__ import annotations

import os
import re

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS_DIR = os.path.join(ROOT, "tools")
PROVIDER_DIR = os.path.join(ROOT, "provider")

EXPECTED_TOOLS = [
    "list_missions",
    "get_mission",
    "create_mission",
    "submit_mission",
    "get_stats",
]

# Parameters each tool YAML must declare (the user/LLM-facing inputs).
EXPECTED_PARAMS = {
    "list_missions": {"status", "limit"},
    "get_mission": {"mission_id"},
    "create_mission": {
        "title",
        "description",
        "reward_amount",
        "reward_currency",
        "verification_type",
        "deadline_hours",
        "verification_params",
        "creator_agent_id",
    },
    "submit_mission": {"mission_id", "proof", "submitter_agent_id"},
    "get_stats": set(),
}


def _load_yaml(path):
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_all_yaml_files_parse():
    yaml_files = [os.path.join(ROOT, "manifest.yaml"), os.path.join(PROVIDER_DIR, "oabp.yaml")]
    yaml_files += [os.path.join(TOOLS_DIR, f"{n}.yaml") for n in EXPECTED_TOOLS]
    for path in yaml_files:
        assert os.path.exists(path), path
        data = _load_yaml(path)
        assert isinstance(data, dict) and data, f"{path} parsed empty"


def test_manifest_lists_provider_and_meta():
    manifest = _load_yaml(os.path.join(ROOT, "manifest.yaml"))
    assert manifest["name"] == "dify_oabp"
    assert manifest["type"] == "plugin"
    assert manifest["plugins"]["tools"] == ["provider/oabp.yaml"]
    assert manifest["meta"]["runner"]["language"] == "python"
    assert manifest["meta"]["runner"]["entrypoint"] == "main"


def test_provider_yaml_lists_five_tools_and_credentials():
    provider = _load_yaml(os.path.join(PROVIDER_DIR, "oabp.yaml"))
    assert provider["identity"]["name"] == "oabp"
    listed = [os.path.basename(p).replace(".yaml", "") for p in provider["tools"]]
    assert listed == EXPECTED_TOOLS

    creds = provider["credentials_for_provider"]
    assert set(creds) == {"oabp_base_url", "api_key", "agent_id"}
    assert creds["oabp_base_url"]["required"] is True
    assert creds["api_key"].get("required", False) is False
    assert creds["agent_id"].get("required", False) is False
    assert creds["api_key"]["type"] == "secret-input"
    assert provider["extra"]["python"]["source"] == "provider/oabp.py"


def test_manifest_lists_all_five_tools_via_provider():
    """The manifest references the provider, which enumerates all five tools."""
    provider = _load_yaml(os.path.join(PROVIDER_DIR, "oabp.yaml"))
    listed = [os.path.basename(p).replace(".yaml", "") for p in provider["tools"]]
    assert sorted(listed) == sorted(EXPECTED_TOOLS)
    assert len(listed) == 5


def test_each_tool_yaml_identity_and_params_match_py():
    for name in EXPECTED_TOOLS:
        ydoc = _load_yaml(os.path.join(TOOLS_DIR, f"{name}.yaml"))

        # identity.name == file stem
        assert ydoc["identity"]["name"] == name, name

        # the python source points back at the matching .py
        assert ydoc["extra"]["python"]["source"] == f"tools/{name}.py", name

        # declared params == expected, and each has type + descriptions + form
        params = ydoc.get("parameters") or []
        declared = {p["name"] for p in params}
        assert declared == EXPECTED_PARAMS[name], (name, declared)
        for p in params:
            assert "type" in p, (name, p.get("name"))
            assert "label" in p, (name, p.get("name"))
            assert "llm_description" in p, (name, p.get("name"))
            assert p["form"] in ("llm", "form"), (name, p.get("name"))

        # every declared param is read by the tool's _invoke
        py_src = open(os.path.join(TOOLS_DIR, f"{name}.py"), encoding="utf-8").read()
        read = set(re.findall(r"tool_parameters(?:\.get\(|\[)\s*[\"']([a-z_]+)[\"']", py_src))
        for pname in declared:
            assert pname in read, f"{name}.py does not read parameter {pname!r}"
        # and the tool reads no undeclared user parameter
        assert read <= declared, (name, read - declared)


def test_each_tool_yaml_select_options_are_valid():
    """select-type params must enumerate options with values."""
    create = _load_yaml(os.path.join(TOOLS_DIR, "create_mission.yaml"))
    by_name = {p["name"]: p for p in create["parameters"]}

    vt = by_name["verification_type"]
    assert vt["type"] == "select"
    vt_values = {o["value"] for o in vt["options"]}
    assert vt_values == {"first_valid_match", "oracle", "peer_vote", "creator_judges"}

    cur = by_name["reward_currency"]
    assert cur["type"] == "select"
    assert {o["value"] for o in cur["options"]} == {"AIGEN", "USDC"}
