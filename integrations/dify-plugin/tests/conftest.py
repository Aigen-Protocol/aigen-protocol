"""Pytest bootstrap for the OABP / AIGEN Dify plugin tests.

The plugin's tool modules import ``dify_plugin`` (the Dify plugin SDK, which is
only present inside the Dify runtime). To keep the suite fully offline we install
a **minimal fake ``dify_plugin`` package** into ``sys.modules`` *before* the
plugin modules are imported. The fake mirrors exactly the surface the plugin
uses:

* ``dify_plugin.Tool``            — base class with ``create_text_message`` /
                                    ``create_json_message`` factories and a public
                                    ``invoke`` that drains ``_invoke``;
* ``dify_plugin.ToolProvider``    — base class for the provider;
* ``dify_plugin.Plugin`` / ``DifyPluginEnv`` — used by ``main.py``;
* ``dify_plugin.entities.tool.ToolInvokeMessage`` — the message type the tools
                                    yield (text or json);
* ``dify_plugin.errors.tool.ToolProviderCredentialValidationError``.

HTTP is stubbed at the ``requests.Session`` level via ``RoutingFakeSession``, so
no real network call is ever made.
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
# Minimal fake ``dify_plugin`` package
# --------------------------------------------------------------------------- #
class ToolInvokeMessage:
    """Stand-in for ``dify_plugin.entities.tool.ToolInvokeMessage``.

    Carries a ``type`` ("text" | "json" | "link" | ...) and a ``message``
    payload, matching the shape the real SDK exposes closely enough for tests to
    assert on (``.type`` and ``.message``).
    """

    def __init__(self, type: str, message: Any) -> None:
        self.type = type
        self.message = message

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"ToolInvokeMessage(type={self.type!r}, message={self.message!r})"


class _TextMessage:
    def __init__(self, text: str) -> None:
        self.text = text


class _JsonMessage:
    def __init__(self, data: Any) -> None:
        self.json_object = data


class Tool:
    """Fake ``dify_plugin.Tool`` base class.

    The real base is constructed by the runtime with a ``runtime`` (credentials)
    and a ``session``; here we accept and store them, and provide the two message
    factories and an ``invoke`` driver the tests use.
    """

    def __init__(self, runtime: Any = None, session: Any = None) -> None:
        self.runtime = runtime
        self.session = session

    # message factories (mirror the real SDK names) ------------------------
    def create_text_message(self, text: str) -> ToolInvokeMessage:
        return ToolInvokeMessage("text", _TextMessage(text))

    def create_json_message(self, json_object: Any) -> ToolInvokeMessage:
        return ToolInvokeMessage("json", _JsonMessage(json_object))

    def create_link_message(self, link: str) -> ToolInvokeMessage:  # pragma: no cover
        return ToolInvokeMessage("link", link)

    # public driver -------------------------------------------------------
    def invoke(self, tool_parameters: Dict[str, Any]) -> List[ToolInvokeMessage]:
        return list(self._invoke(tool_parameters))

    def _invoke(self, tool_parameters: Dict[str, Any]):  # pragma: no cover
        raise NotImplementedError


class ToolProvider:
    """Fake ``dify_plugin.ToolProvider`` base class."""

    def validate_credentials(self, credentials: Dict[str, Any]) -> None:
        self._validate_credentials(credentials)

    def _validate_credentials(self, credentials: Dict[str, Any]) -> None:  # pragma: no cover
        raise NotImplementedError


class DifyPluginEnv:  # pragma: no cover - only constructed in main.py
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class Plugin:  # pragma: no cover - only constructed in main.py
    def __init__(self, env: Any = None) -> None:
        self.env = env

    def run(self) -> None:
        raise RuntimeError("the fake Plugin.run() must not be called in tests")


class ToolProviderCredentialValidationError(Exception):
    """Stand-in for the SDK's credential-validation error."""


def _install_fake_dify_plugin() -> None:
    """Register the fake ``dify_plugin`` package tree in ``sys.modules``."""
    if "dify_plugin" in sys.modules:
        return

    pkg = types.ModuleType("dify_plugin")
    pkg.Tool = Tool
    pkg.ToolProvider = ToolProvider
    pkg.Plugin = Plugin
    pkg.DifyPluginEnv = DifyPluginEnv
    pkg.__path__ = []  # mark as a package so submodules can be registered

    entities = types.ModuleType("dify_plugin.entities")
    entities.__path__ = []
    entities_tool = types.ModuleType("dify_plugin.entities.tool")
    entities_tool.ToolInvokeMessage = ToolInvokeMessage

    errors = types.ModuleType("dify_plugin.errors")
    errors.__path__ = []
    errors_tool = types.ModuleType("dify_plugin.errors.tool")
    errors_tool.ToolProviderCredentialValidationError = (
        ToolProviderCredentialValidationError
    )

    sys.modules["dify_plugin"] = pkg
    sys.modules["dify_plugin.entities"] = entities
    sys.modules["dify_plugin.entities.tool"] = entities_tool
    sys.modules["dify_plugin.errors"] = errors
    sys.modules["dify_plugin.errors.tool"] = errors_tool


_install_fake_dify_plugin()


# --------------------------------------------------------------------------- #
# Fake HTTP transport
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

    A route value may be a callable ``(method, url, kwargs) -> FakeResponse`` so
    a test can assert on the exact request body the tool sends.
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


# --------------------------------------------------------------------------- #
# Shared sample payloads (live API shapes)
# --------------------------------------------------------------------------- #
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

SAMPLE_STATS = {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000}


class _Runtime:
    """Mimics the Dify ``ToolRuntime`` object: carries ``.credentials``."""

    def __init__(self, credentials: Dict[str, Any]) -> None:
        self.credentials = credentials


@pytest.fixture
def make_tool():
    """Factory: instantiate a tool class wired to a RoutingFakeSession.

    Returns ``(tool, session)``. The tool's ``runtime.credentials`` carry the
    configured agent id / base url, and the tool's HTTP client is forced onto the
    fake session via ``_session_override``.
    """

    def _make(tool_cls, routes: Dict[tuple, Any], **credentials: Any):
        session = RoutingFakeSession(routes)
        runtime = _Runtime(credentials)
        tool = tool_cls(runtime=runtime, session=None)
        tool._session_override = session
        return tool, session

    return _make
