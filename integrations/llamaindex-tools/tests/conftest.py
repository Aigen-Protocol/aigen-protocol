"""Pytest bootstrap for the llamaindex_oabp test-suite.

Adds the project root to ``sys.path`` so tests import the local
``llamaindex_oabp`` package (which in turn falls back to its vendored ``oabp``
SDK) without an install. Provides a shared fake HTTP transport so the whole suite
runs fully offline — no network, and crucially no dependency on the
``llama-index-core`` package (the package must work without it).
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

    A response may also be a callable ``(method, url, kwargs) -> FakeResponse`` so
    tests can assert on the request body the SDK sends.
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
# Fixtures — note the mis_* ids and the min_submitter_elo gate
# --------------------------------------------------------------------------- #
SAMPLE_MISSION = {
    "id": "mis_abc123",
    "title": "GoPlus safety review of 0xABC",
    "description": "GoPlus token-security review for token 0xABC",
    "reward": {"amount": 500, "currency": "AIGEN"},
    "verification_type": "oracle",
    # A mission that gates submitters by reputation — the integration must surface
    # min_submitter_elo straight through verification_params.
    "verification_params": {
        "oracle_description": "safety review of 0xABC",
        "min_submitter_elo": 1200,
    },
    "deadline": 1893456000,
    "status": "open",
    "submissions": [],
}

SAMPLE_MISSION_DETAIL = {
    **SAMPLE_MISSION,
    "submissions": [
        {"submitter_agent_id": "agent-9", "proof": "0xABC", "accepted": True}
    ],
    "resolution": {
        "winner_agent_id": "agent-9",
        "winning_proof": "0xABC",
        "verified": True,
        "reward_paid": 497.5,
    },
}

SAMPLE_STATS = {"resolved": 7, "open": 3, "lifetime_reward_aigen_paid": 108000}

SAMPLE_REPUTATION = {
    "agent_id": "agent-9",
    "aigen_balance": 1500,
    "missions_won": 4,
    "missions_created": 2,
    "submissions": 11,
}


@pytest.fixture
def make_client():
    """Factory: build an OabpClient wired to a RoutingFakeSession."""
    from llamaindex_oabp import OabpClient

    def _make(routes: Dict[tuple, Any], **client_kwargs: Any):
        session = RoutingFakeSession(routes)
        client = OabpClient(session=session, **client_kwargs)
        return client, session

    return _make
