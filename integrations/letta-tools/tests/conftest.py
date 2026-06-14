"""Pytest bootstrap for the letta_oabp test-suite.

Adds the project root to ``sys.path`` so tests import the local ``letta_oabp``
package without an install. Provides:

* a ``fake_marketplace`` fixture that monkey-patches ``urllib.request.urlopen``
  with an in-memory OABP marketplace, so the four source tools run fully offline
  and deterministically (they build a ``urllib.request.Request`` and call
  ``urlopen`` inside their own bodies — patching ``urlopen`` is all it takes);
* a ``fake_letta`` fixture that installs a minimal fake ``letta_client`` module so
  the ``register_tools`` / ``create_oabp_agent`` wiring can be exercised without
  the optional ``letta-client`` dependency, recording every upsert / attach /
  create call.
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


SAMPLE_MISSIONS = [
    {
        "id": "mis_a1b2c3",
        "title": "GoPlus safety review of 0xABC",
        "description": "GoPlus token-security review for token 0xABC",
        "reward": {"amount": 500, "currency": "AIGEN"},
        "verification_type": "oracle",
        "verification_params": {"oracle_description": "safety review of 0xABC"},
        "deadline": 1893456000,
        "status": "open",
        "submissions": [],
    },
    {
        "id": "mis_d4e5f6",
        "title": "Ship a Go SDK example",
        "description": "Public GitHub repo with a runnable Go example",
        "reward": {"amount": 50, "currency": "USDC"},
        "verification_type": "first_valid_match",
        "verification_params": {"regex": "github\\.com/.+"},
        "deadline": 1893456000,
        "status": "open",
        "submissions": [
            {"submitter_agent_id": "agent-9", "proof": "github.com/me/repo"}
        ],
    },
]

SAMPLE_STATS = {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000}


class _FakeHTTPResponse:
    """Minimal context-manager stand-in for urllib's HTTP response object."""

    def __init__(self, payload: Any) -> None:
        self._data = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


class _Marketplace:
    """Records requests and routes them to canned OABP responses."""

    def __init__(self, missions: List[Dict[str, Any]], stats: Dict[str, Any]) -> None:
        self.missions = [dict(m) for m in missions]
        self.stats = dict(stats)
        self.calls: List[Dict[str, Any]] = []
        # Tests can register error overrides keyed by (METHOD, url-suffix).
        self.errors: Dict[Any, Any] = {}

    def urlopen(self, req: Any, timeout: int = 15) -> _FakeHTTPResponse:
        method = req.get_method()
        url = req.full_url
        body = None
        if getattr(req, "data", None):
            body = json.loads(req.data.decode("utf-8"))
        self.calls.append({"method": method, "url": url, "body": body})

        # Optional injected error (a urllib error instance) for a route.
        for (m, suffix), exc in self.errors.items():
            if method == m and url.rstrip("/").endswith(suffix.rstrip("/")):
                raise exc

        tail = url.rstrip("/")
        # Drop a query string for suffix matching.
        path = tail.split("?", 1)[0]
        if method == "GET" and path.endswith("/api/missions"):
            return _FakeHTTPResponse(self.missions)
        if method == "GET" and path.endswith("/api/stats"):
            return _FakeHTTPResponse(self.stats)
        if method == "POST" and path.endswith("/api/missions"):
            mission = {
                "id": "mis_new001",
                "title": body["title"],
                "description": body["description"],
                "reward": {
                    "amount": body["reward_amount"],
                    "currency": body["reward_currency"],
                },
                "verification_type": body["verification_type"],
                "verification_params": body.get("verification_params", {}),
                "deadline": 1893456000,
                "status": "open",
                "submissions": [],
            }
            self.missions.append(mission)
            return _FakeHTTPResponse({"mission": mission})
        if method == "POST" and "/submit" in path:
            return _FakeHTTPResponse(
                {
                    "accepted": True,
                    "resolution": {
                        "winner_agent_id": body["submitter_agent_id"],
                        "verified": True,
                        "reward_paid": 497.5,
                    },
                }
            )
        raise AssertionError("unexpected request: %s %s" % (method, url))


@pytest.fixture
def fake_marketplace(monkeypatch):
    """Patch urllib.request.urlopen with an in-memory OABP marketplace.

    Yields the :class:`_Marketplace` so a test can assert on ``.calls`` (the exact
    requests the tools sent) or inject errors via ``.errors[(METHOD, suffix)]``.
    Also sets ``OABP_AGENT_ID`` / ``OABP_BASE_URL`` so the tools have a default
    agent id and a deterministic base URL.
    """
    import urllib.request

    market = _Marketplace(SAMPLE_MISSIONS, SAMPLE_STATS)
    monkeypatch.setattr(urllib.request, "urlopen", market.urlopen)
    monkeypatch.setenv("OABP_BASE_URL", "https://cryptogenesis.duckdns.org")
    monkeypatch.setenv("OABP_AGENT_ID", "test-agent")
    monkeypatch.delenv("OABP_API_KEY", raising=False)
    return market


# --------------------------------------------------------------------------- #
# Minimal fake ``letta_client`` so register_tools / create_oabp_agent can be
# tested without the optional dependency. Records every call.
# --------------------------------------------------------------------------- #
class _FakeTool:
    def __init__(self, name: str, source_code: str) -> None:
        self.id = "tool-" + name
        self.name = name
        self.source_code = source_code


class _FakeAgentState:
    def __init__(self, **kwargs: Any) -> None:
        self.id = "agent-001"
        self.name = kwargs.get("name", "oabp-agent")
        self.tools = list(kwargs.get("tools", []) or [])
        self.kwargs = kwargs


class _FakeToolsAPI:
    def __init__(self, recorder: Dict[str, List[Any]]) -> None:
        self._rec = recorder

    def upsert_from_function(self, *, func: Any, args_schema: Any = None) -> _FakeTool:
        import inspect

        # Mirror Letta: read the function's source (must be extractable).
        source = inspect.getsource(func)
        tool = _FakeTool(func.__name__, source)
        self._rec["upserts"].append({"name": func.__name__, "source": source})
        return tool


class _FakeAgentToolsAPI:
    def __init__(self, recorder: Dict[str, List[Any]]) -> None:
        self._rec = recorder

    def attach(self, *, agent_id: str, tool_id: str) -> None:
        self._rec["attaches"].append({"agent_id": agent_id, "tool_id": tool_id})


class _FakeMessagesAPI:
    def __init__(self, recorder: Dict[str, List[Any]]) -> None:
        self._rec = recorder

    def create(self, *, agent_id: str, messages: Any) -> Any:
        self._rec["messages"].append({"agent_id": agent_id, "messages": messages})
        return types.SimpleNamespace(messages=[])


class _FakeAgentsAPI:
    def __init__(self, recorder: Dict[str, List[Any]]) -> None:
        self._rec = recorder
        self.tools = _FakeAgentToolsAPI(recorder)
        self.messages = _FakeMessagesAPI(recorder)

    def create(self, **kwargs: Any) -> _FakeAgentState:
        self._rec["creates"].append(kwargs)
        return _FakeAgentState(**kwargs)

    def modify(self, *, agent_id: str, **kwargs: Any) -> None:
        self._rec["modifies"].append({"agent_id": agent_id, **kwargs})


class _FakeLetta:
    """Stand-in for ``letta_client.Letta`` that records all calls."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.init_args = {"args": args, "kwargs": kwargs}
        self.recorder: Dict[str, List[Any]] = {
            "upserts": [],
            "attaches": [],
            "creates": [],
            "modifies": [],
            "messages": [],
        }
        self.tools = _FakeToolsAPI(self.recorder)
        self.agents = _FakeAgentsAPI(self.recorder)


@pytest.fixture
def fake_letta(monkeypatch):
    """Install a fake ``letta_client`` module and return a fresh client.

    Returns the ``_FakeLetta`` instance; ``client.recorder`` exposes the recorded
    ``upserts`` / ``attaches`` / ``creates`` / ``modifies`` / ``messages``.
    """
    module = types.ModuleType("letta_client")
    module.Letta = _FakeLetta  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "letta_client", module)
    return _FakeLetta()
