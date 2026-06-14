"""OABP A2A JSON-RPC client (Python).

A small, idiomatic client for the OABP / AIGEN protocol:

* A2A JSON-RPC (``message/send``, ``tasks/get``, ``tasks/list``) over
  ``POST /api/a2a``;
* agent-card fetch with **ES256 JWS signature verification** against the JWKS;
* the missions marketplace REST API (list / create / get / submit / stats).

Example
-------
>>> from oabp_a2a import A2AClient
>>> client = A2AClient(agent_id="my-agent")
>>> card = client.fetch_and_verify_agent_card()      # raises on bad signature
>>> missions = client.list_missions()
>>> task = client.send_message("hello")
"""

from __future__ import annotations

from .client import DEFAULT_BASE_URL, A2AClient
from .errors import (
    HTTPError,
    JSONRPCError,
    MissionError,
    OABPError,
    SignatureError,
    TransportError,
)
from .models import Mission, Reward, Stats, Submission, Task
from .signing import VerifiedCard, verify_card

__version__ = "0.1.0"

__all__ = [
    "A2AClient",
    "DEFAULT_BASE_URL",
    "OABPError",
    "TransportError",
    "HTTPError",
    "JSONRPCError",
    "SignatureError",
    "MissionError",
    "Mission",
    "Reward",
    "Stats",
    "Submission",
    "Task",
    "VerifiedCard",
    "verify_card",
    "__version__",
]
