"""Pytest bootstrap for the smolagents_oabp test-suite.

Adds the project root to ``sys.path`` so tests import the local
``smolagents_oabp`` package (which in turn falls back to its vendored ``oabp``
SDK) without requiring an install. Provides a shared fake HTTP transport that
stubs the vendored SDK's ``requests.Session`` so the whole suite runs fully
offline and deterministically, plus an optional minimal fake ``smolagents``
module so the real-``@tool`` path and ``build_agent`` can be exercised without
the optional ``smolagents`` dependency installed.
"""

from __future__ import annotations

import json
import os
import sys
import types
from typing import Any, Dict, List, Optional

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# --------------------------------------------------------------------------- #
# Fake HTTP transport for the underlying (vendored) OABP SDK client
# --------------------------------------------------------------------------- #
class FakeResponse:
    """Minimal ``requests.Response`` stand-in."""

    def __init__(
        self,
        status_code: int = 200,
        json_data: Any = None,
        *,
        headers: Optional[Dict[str, str]] = None,
        reason: str = "OK",
    ) -> None:
        self.status_code = status_code
        self._json = json_data
        self.reason = reason
        self.headers = headers or {}
        if json_data is not None:
            self.text = json.dumps(json_data)
            self.content = self.text.encode()
            self.headers.setdefault("Content-Type", "application/json")
        else:
            self.text = ""
            self.content = b""

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("no json")
        return self._json


class RoutingFakeSession:
    """Routes ``(METHOD, url-substring)`` -> FakeResponse, records calls.

    A response may also be a callable ``(method, url, kwargs) -> FakeResponse``
    so tests can assert on the request body.
    """

    def __init__(self, routes: Dict[tuple, Any]) -> None:
        self.routes = routes
        self.calls: List[Dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        for (m, frag), resp in self.routes.items():
            if method == m and frag in url:
                return resp(method, url, kwargs) if callable(resp) else resp
        return FakeResponse(404, {"error": f"no route for {method} {url}"})

    def close(self) -> None:
        self.closed = True


# The live self-referential bounty this integration targets.
MOTIVATING_MISSION_ID = "mis_15a24726b3de"

SAMPLE_MISSION = {
    "id": "m-001",
    "title": "Safety review of 0xABC",
    "description": "GoPlus token-security review for token 0xABC",
    "reward": {"amount": 500, "currency": "AIGEN"},
    "verification_type": "oracle",
    "verification_params": {"oracle_description": "safety review of 0xABC"},
    "deadline": 1893456000,
    "status": "open",
    "submissions": [],
}

SAMPLE_MISSION_DETAIL = {
    **SAMPLE_MISSION,
    "submissions": [
        {"submitter_agent_id": "agent-9", "proof": "0xABC is clean", "accepted": True}
    ],
    "resolution": {
        "winner_agent_id": "agent-9",
        "winning_proof": "0xABC is clean",
        "verified": True,
        "reward_paid": 497.5,
    },
}

# The motivating smolagents bounty, in the live API's shape.
SMOLAGENTS_MISSION = {
    "id": MOTIVATING_MISSION_ID,
    "title": "Add an OABP/AIP-1 integration example to smolagents",
    "description": (
        "Submit a pull request to huggingface/smolagents that adds a working "
        "example showing how a smolagents agent can discover and complete AIGEN "
        "missions."
    ),
    "reward": {"amount": 200, "currency": "AIGEN"},
    "verification_type": "oracle",
    "verification_params": {
        "oracle_description": (
            "Submit the URL of a merged pull request on "
            "github.com/huggingface/smolagents. First valid merged PR URL wins."
        ),
        "regex": "https://github.com/huggingface/smolagents/pull/[0-9]+",
    },
    "deadline": 1781557979,
    "status": "open",
    "submissions": [],
}

SAMPLE_STATS = {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000}

SAMPLE_REPUTATION = {
    "agent_id": "agent-9",
    "aigen_balance": 12500,
    "missions_won": 9,
    "missions_created": 3,
    "submissions": 14,
}


@pytest.fixture
def make_client():
    """Factory: build an OabpClient wired to a RoutingFakeSession."""
    from smolagents_oabp import OabpClient

    def _make(routes: Dict[tuple, Any], **client_kwargs: Any):
        session = RoutingFakeSession(routes)
        client = OabpClient(session=session, **client_kwargs)
        return client, session

    return _make


@pytest.fixture(autouse=True)
def _reset_context():
    """Reset the module-global tool context between tests for isolation."""
    from smolagents_oabp.tools import CONTEXT

    CONTEXT.reset()
    yield
    CONTEXT.reset()


# --------------------------------------------------------------------------- #
# Minimal fake ``smolagents`` module so the real-@tool path + build_agent can be
# tested without the optional dependency installed. The fake ``tool`` decorator
# mirrors smolagents: it returns a Tool object that parses name/description/inputs
# and is callable.
# --------------------------------------------------------------------------- #
class _FakeSmolTool:
    """A stand-in for ``smolagents.Tool`` produced by the fake ``tool``."""

    def __init__(self, func) -> None:
        import smolagents_oabp._smol as _smol

        self.func = func
        self.name = func.__name__
        summary, arg_docs = _smol.parse_docstring(func.__doc__)
        self.description = summary or func.__name__
        self.inputs = _smol._FallbackTool._build_inputs(func, arg_docs)
        self.output_type = "object"
        self.is_fake_smolagents_tool = True

    def __call__(self, *a, **k):
        return self.func(*a, **k)


class _RecordingAgent:
    """Captures the tools/model a CodeAgent/ToolCallingAgent was built with."""

    kind = "base"

    def __init__(self, tools, model, add_base_tools=False, **kwargs) -> None:
        self.tools = list(tools)
        self.model = model
        self.add_base_tools = add_base_tools
        self.kwargs = kwargs

    def run(self, task, **kwargs):  # pragma: no cover - not exercised here
        return f"[{self.kind}] would run: {task}"


class _FakeCodeAgent(_RecordingAgent):
    kind = "code"


class _FakeToolCallingAgent(_RecordingAgent):
    kind = "toolcalling"


@pytest.fixture
def fake_smolagents(monkeypatch):
    """Install a fake ``smolagents`` module (tool + CodeAgent/ToolCallingAgent).

    Reloads ``smolagents_oabp._smol`` so its ``@tool`` seam re-detects the fake
    module, then reloads ``smolagents_oabp.tools`` so the six tools are produced
    by the fake decorator. Yields the fake module; everything is restored after.
    """
    import importlib

    module = types.ModuleType("smolagents")
    module.tool = _FakeSmolTool  # type: ignore[attr-defined]
    module.CodeAgent = _FakeCodeAgent  # type: ignore[attr-defined]
    module.ToolCallingAgent = _FakeToolCallingAgent  # type: ignore[attr-defined]
    module.Tool = _FakeSmolTool  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "smolagents", module)

    import smolagents_oabp._smol as _smol
    import smolagents_oabp.tools as _tools
    import smolagents_oabp.agent as _agent
    import smolagents_oabp as _pkg

    importlib.reload(_smol)
    importlib.reload(_tools)
    importlib.reload(_agent)
    importlib.reload(_pkg)
    try:
        yield module
    finally:
        # Restore the no-smolagents state for subsequent tests.
        monkeypatch.delitem(sys.modules, "smolagents", raising=False)
        importlib.reload(_smol)
        importlib.reload(_tools)
        importlib.reload(_agent)
        importlib.reload(_pkg)
