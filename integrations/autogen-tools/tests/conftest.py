"""Pytest bootstrap for the autogen_oabp test-suite.

Adds the project root to ``sys.path`` so tests import the local ``autogen_oabp``
package (which in turn falls back to its vendored ``oabp`` SDK) without requiring
an install. Provides a shared fake HTTP transport that stubs the vendored SDK's
``requests.Session`` so the whole suite runs fully offline and deterministically,
plus a minimal fake ``autogen`` module so the ``register_oabp_tools`` wiring can
be exercised without the optional ``pyautogen`` dependency installed.
"""

from __future__ import annotations

import json
import os
import sys
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
    from autogen_oabp import OabpClient

    def _make(routes: Dict[tuple, Any], **client_kwargs: Any):
        session = RoutingFakeSession(routes)
        client = OabpClient(session=session, **client_kwargs)
        return client, session

    return _make


# --------------------------------------------------------------------------- #
# Minimal fake ``autogen`` module so register_oabp_tools can be tested without
# the optional pyautogen dependency. Captures every register_function call.
# --------------------------------------------------------------------------- #
class _RecordingRegisterFunction:
    """Stand-in for ``autogen.register_function`` that records registrations."""

    def __init__(self) -> None:
        self.registrations: List[Dict[str, Any]] = []

    def __call__(self, func, *, caller, executor, name, description):  # noqa: D401
        self.registrations.append(
            {
                "func": func,
                "caller": caller,
                "executor": executor,
                "name": name,
                "description": description,
            }
        )
        # Mirror AG2's behaviour of attaching the schema to both agents.
        caller.registered_for_llm.append(name)
        executor.registered_for_execution.append(name)


class _FakeAgent:
    """Tiny ConversableAgent stand-in used as caller / executor in tests."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.registered_for_llm: List[str] = []
        self.registered_for_execution: List[str] = []


@pytest.fixture
def fake_autogen(monkeypatch):
    """Install a fake ``autogen`` module exposing a recording register_function.

    Returns ``(recorder, make_agent)`` where ``recorder.registrations`` lists the
    captured calls and ``make_agent(name)`` builds a fake caller/executor agent.
    """
    import types

    recorder = _RecordingRegisterFunction()
    module = types.ModuleType("autogen")
    module.register_function = recorder  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "autogen", module)
    return recorder, _FakeAgent
