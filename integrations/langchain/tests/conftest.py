"""Pytest bootstrap for the langchain_oabp test-suite.

Adds the project root to ``sys.path`` so tests import the local
``langchain_oabp`` package (which in turn falls back to its vendored ``oabp``
SDK) without requiring an install. Also provides shared fake HTTP transport and
a fake tool-calling LLM, so the whole suite runs fully offline.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# --------------------------------------------------------------------------- #
# Fake HTTP transport for the underlying OABP SDK client
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


@pytest.fixture
def make_client():
    """Factory: build an OabpClient wired to a RoutingFakeSession."""
    from langchain_oabp import OabpClient

    def _make(routes: Dict[tuple, Any], **client_kwargs: Any):
        session = RoutingFakeSession(routes)
        client = OabpClient(session=session, **client_kwargs)
        return client, session

    return _make


# --------------------------------------------------------------------------- #
# Fake tool-calling LLM (real langchain_core BaseChatModel subclass)
# --------------------------------------------------------------------------- #
@pytest.fixture
def fake_tool_calling_llm():
    """Return a BaseChatModel subclass that supports bind_tools + emits tool calls."""
    from langchain_core.callbacks import CallbackManagerForLLMRun
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.runnables import Runnable

    class FakeToolCallingLLM(BaseChatModel):
        """Minimal fake chat model that records bound tools and emits tool calls."""

        emit: List[Dict[str, Any]] = []
        bound_names: List[str] = []

        @property
        def _llm_type(self) -> str:
            return "fake-tool-calling"

        def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Runnable:
            self.bound_names = [getattr(t, "name", str(t)) for t in tools]
            return self

        def _generate(
            self,
            messages: List[BaseMessage],
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any,
        ) -> ChatResult:
            msg = AIMessage(content="", tool_calls=list(self.emit))
            return ChatResult(generations=[ChatGeneration(message=msg)])

    return FakeToolCallingLLM
