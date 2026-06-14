"""The OABP A2A JSON-RPC + REST client.

:class:`A2AClient` is a thin, dependency-light wrapper over the OABP protocol
served at ``https://cryptogenesis.duckdns.org``:

* **A2A JSON-RPC** (``POST /api/a2a``): ``message/send``, ``tasks/get``,
  ``tasks/list``.
* **Agent card**: fetch ``/.well-known/agent-card.json`` and verify its ES256
  signature against ``/.well-known/jwks.json``.
* **Missions REST**: list / create / get missions, submit deliverables, stats.

The only third-party runtime dependency is :mod:`requests`; signature
verification uses :mod:`cryptography` (via :mod:`oabp_a2a.signing`). The HTTP
layer is injectable (``session=``) so it can be mocked in tests without any
network access.
"""

from __future__ import annotations

import itertools
import json
import uuid
from typing import Any, Dict, List, Mapping, Optional, Union

import requests

from . import signing
from .errors import (
    HTTPError,
    JSONRPCError,
    MissionError,
    OABPError,
    TransportError,
)
from .models import Mission, Stats, Task

__all__ = ["A2AClient", "DEFAULT_BASE_URL"]

DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"

_AGENT_CARD_PATH = "/.well-known/agent-card.json"
_JWKS_PATH = "/.well-known/jwks.json"
_A2A_PATH = "/api/a2a"


class A2AClient:
    """Client for the OABP A2A JSON-RPC API and mission marketplace.

    Parameters
    ----------
    base_url:
        Root URL of the OABP deployment. Defaults to the public instance.
    agent_id:
        This client's agent id, used as the default ``submitter_agent_id`` /
        ``creator_agent_id`` and as the sender on outbound A2A messages.
    session:
        An optional :class:`requests.Session` (injected for tests / custom
        transport, retries, auth headers, ...). One is created if omitted.
    timeout:
        Per-request timeout in seconds.
    api_key:
        Optional bearer token; sent as ``Authorization: Bearer <key>`` when set.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        agent_id: Optional[str] = None,
        session: Optional[requests.Session] = None,
        timeout: float = 30.0,
        api_key: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.timeout = timeout
        self._session = session or requests.Session()
        self._owns_session = session is None
        self._id_counter = itertools.count(1)
        if api_key:
            self._session.headers["Authorization"] = f"Bearer {api_key}"
        self._session.headers.setdefault("User-Agent", "oabp-a2a-python/0.1")
        self._session.headers.setdefault("Accept", "application/json")

    # ------------------------------------------------------------------ #
    # context-manager sugar
    # ------------------------------------------------------------------ #
    def __enter__(self) -> "A2AClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying session if this client created it."""
        if self._owns_session:
            self._session.close()

    # ------------------------------------------------------------------ #
    # low-level HTTP
    # ------------------------------------------------------------------ #
    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        url = self._url(path)
        try:
            resp = self._session.request(
                method,
                url,
                json=json_body,
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise TransportError(f"{method} {url} failed: {exc}") from exc

        if not (200 <= resp.status_code < 300):
            body = _safe_text(resp)
            raise HTTPError(resp.status_code, url, body)

        if resp.status_code == 204 or not (resp.content or b"").strip():
            return None
        try:
            return resp.json()
        except ValueError as exc:
            raise OABPError(
                f"{method} {url} returned non-JSON body: {_safe_text(resp)!r}"
            ) from exc

    # ------------------------------------------------------------------ #
    # agent card + JWKS
    # ------------------------------------------------------------------ #
    def fetch_jwks(self) -> Dict[str, Any]:
        """GET ``/.well-known/jwks.json``."""
        data = self._request("GET", _JWKS_PATH)
        if not isinstance(data, Mapping):
            raise OABPError("JWKS endpoint did not return a JSON object")
        return dict(data)

    def fetch_agent_card(self, verify: bool = True) -> Dict[str, Any]:
        """Fetch the agent card from ``/.well-known/agent-card.json``.

        When ``verify`` is true (the default) the card's ES256 signature is
        checked against the live JWKS before the card is returned; a bad or
        missing signature raises :class:`oabp_a2a.errors.SignatureError`.

        Returns the card object. For the embedded-signature form the returned
        dict still contains the original ``signature`` field (the *verified*
        payload, signature stripped, is available via
        :meth:`fetch_and_verify_agent_card`).
        """
        card = self._request("GET", _AGENT_CARD_PATH)
        if isinstance(card, str):
            # Server served the card as a raw JWS or JSON string body.
            pass
        elif not isinstance(card, Mapping):
            raise OABPError("agent-card endpoint did not return an object/string")
        if verify:
            jwks = self.fetch_jwks()
            signing.verify_card(card, jwks)
        return card if isinstance(card, dict) else {"_raw": card}

    def fetch_and_verify_agent_card(self) -> signing.VerifiedCard:
        """Fetch card + JWKS and return the verified result.

        The returned :class:`~oabp_a2a.signing.VerifiedCard` exposes the
        signature-stripped ``payload``, the ``kid`` and the verified ``header``.
        """
        card = self._request("GET", _AGENT_CARD_PATH)
        jwks = self.fetch_jwks()
        return signing.verify_card(card, jwks)

    def verify_card(self, card: Any, jwks: Optional[Mapping[str, Any]] = None) -> signing.VerifiedCard:
        """Verify an already-fetched ``card`` against ``jwks``.

        If ``jwks`` is omitted it is fetched from the server.
        """
        if jwks is None:
            jwks = self.fetch_jwks()
        return signing.verify_card(card, jwks)

    # ------------------------------------------------------------------ #
    # A2A JSON-RPC
    # ------------------------------------------------------------------ #
    def rpc(self, method: str, params: Any = None, *, request_id: Any = None) -> Any:
        """Invoke a raw JSON-RPC 2.0 method on ``/api/a2a``.

        Returns the ``result`` member; raises :class:`JSONRPCError` if the
        server returns an ``error`` member.
        """
        if request_id is None:
            request_id = next(self._id_counter)
        envelope = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            envelope["params"] = params

        data = self._request("POST", _A2A_PATH, json_body=envelope)
        if not isinstance(data, Mapping):
            raise JSONRPCError(-32603, "malformed JSON-RPC response (not an object)")

        if "error" in data and data["error"] is not None:
            err = data["error"]
            if isinstance(err, Mapping):
                raise JSONRPCError(
                    int(err.get("code", -32603)),
                    str(err.get("message", "unknown error")),
                    err.get("data"),
                )
            raise JSONRPCError(-32603, f"JSON-RPC error: {err!r}")

        if "result" not in data:
            raise JSONRPCError(-32603, "JSON-RPC response has neither result nor error")
        return data["result"]

    def send_message(
        self,
        text: str,
        *,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
        message_id: Optional[str] = None,
        role: str = "user",
        extra_parts: Optional[List[Mapping[str, Any]]] = None,
        configuration: Optional[Mapping[str, Any]] = None,
    ) -> Task:
        """A2A ``message/send``: send a text message and return the resulting task.

        ``task_id`` / ``context_id`` continue an existing task/conversation;
        omit them to start a new one. The sender id defaults to this client's
        :attr:`agent_id`.
        """
        parts: List[Mapping[str, Any]] = [{"kind": "text", "text": text}]
        if extra_parts:
            parts.extend(extra_parts)

        message: Dict[str, Any] = {
            "role": role,
            "parts": parts,
            "messageId": message_id or uuid.uuid4().hex,
            "kind": "message",
        }
        if task_id:
            message["taskId"] = task_id
        if context_id:
            message["contextId"] = context_id
        if self.agent_id:
            # Surfaced for servers that attribute messages to an agent id.
            message["agentId"] = self.agent_id

        params: Dict[str, Any] = {"message": message}
        if configuration:
            params["configuration"] = dict(configuration)

        result = self.rpc("message/send", params)
        return _result_to_task(result)

    def get_task(self, task_id: str, *, history_length: Optional[int] = None) -> Task:
        """A2A ``tasks/get``: fetch a task by id."""
        params: Dict[str, Any] = {"id": task_id}
        if history_length is not None:
            params["historyLength"] = history_length
        result = self.rpc("tasks/get", params)
        return _result_to_task(result)

    def list_tasks(
        self,
        *,
        length: Optional[int] = None,
        offset: Optional[int] = None,
        context_id: Optional[str] = None,
        extra_params: Optional[Mapping[str, Any]] = None,
    ) -> List[Task]:
        """A2A ``tasks/list``: list this agent's tasks.

        The OABP server returns either a bare array of tasks or an object with a
        ``tasks`` array; both are handled.
        """
        params: Dict[str, Any] = {}
        if length is not None:
            params["length"] = length
        if offset is not None:
            params["offset"] = offset
        if context_id is not None:
            params["contextId"] = context_id
        if extra_params:
            params.update(extra_params)

        result = self.rpc("tasks/list", params or None)
        items = _extract_task_list(result)
        return [Task.from_json(t) for t in items]

    # ------------------------------------------------------------------ #
    # Missions REST
    # ------------------------------------------------------------------ #
    def list_missions(self) -> List[Mission]:
        """GET ``/api/missions`` -> open missions."""
        data = self._request("GET", "/api/missions")
        items = _as_list(data, container_keys=("missions", "data", "items"))
        return [Mission.from_json(m) for m in items]

    def get_mission(self, mission_id: str) -> Mission:
        """GET ``/api/missions/{id}`` -> mission detail with submissions/resolution."""
        data = self._request("GET", f"/api/missions/{mission_id}")
        if not isinstance(data, Mapping):
            raise MissionError(f"mission {mission_id} returned a non-object body")
        # Some servers wrap the detail as {"mission": {...}}.
        if "id" not in data and isinstance(data.get("mission"), Mapping):
            data = data["mission"]
        return Mission.from_json(data)

    def create_mission(
        self,
        title: str,
        description: str,
        reward_amount: float,
        verification_type: str,
        *,
        reward_currency: str = "AIGEN",
        verification_params: Optional[Mapping[str, Any]] = None,
        deadline_hours: float = 24,
        creator_agent_id: Optional[str] = None,
    ) -> Mission:
        """POST ``/api/missions`` -> create a mission.

        ``verification_type`` is one of ``first_valid_match``, ``oracle``,
        ``peer_vote``, ``creator_judges``. For ``first_valid_match`` supply
        ``verification_params={"regex": ...}``; for ``oracle`` supply
        ``{"oracle_description": ...}``.
        """
        creator = creator_agent_id or self.agent_id
        if not creator:
            raise MissionError(
                "create_mission needs a creator_agent_id "
                "(pass it or set A2AClient(agent_id=...))"
            )
        _validate_verification(verification_type, verification_params)
        body = {
            "creator_agent_id": creator,
            "title": title,
            "description": description,
            "reward_amount": reward_amount,
            "reward_currency": reward_currency,
            "verification_type": verification_type,
            "verification_params": dict(verification_params or {}),
            "deadline_hours": deadline_hours,
        }
        data = self._request("POST", "/api/missions", json_body=body)
        if not isinstance(data, Mapping):
            raise MissionError("create_mission returned a non-object body")
        if "id" not in data and isinstance(data.get("mission"), Mapping):
            data = data["mission"]
        return Mission.from_json(data)

    def submit(
        self,
        mission_id: str,
        proof: str,
        *,
        submitter_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST ``/missions/{id}/submit`` -> submit a deliverable.

        ``proof`` is text or a URL. Returns the raw server response (which for
        an immediately-resolved mission includes the resolution).
        """
        submitter = submitter_agent_id or self.agent_id
        if not submitter:
            raise MissionError(
                "submit needs a submitter_agent_id "
                "(pass it or set A2AClient(agent_id=...))"
            )
        body = {"submitter_agent_id": submitter, "proof": proof}
        data = self._request("POST", f"/missions/{mission_id}/submit", json_body=body)
        return dict(data) if isinstance(data, Mapping) else {"result": data}

    def stats(self) -> Stats:
        """GET ``/api/stats`` -> protocol stats."""
        data = self._request("GET", "/api/stats")
        if not isinstance(data, Mapping):
            raise OABPError("stats endpoint did not return an object")
        return Stats.from_json(data)


# ---------------------------------------------------------------------- #
# module-level helpers
# ---------------------------------------------------------------------- #
def _safe_text(resp: requests.Response) -> str:
    try:
        return resp.text
    except Exception:  # pragma: no cover - defensive
        return "<unreadable body>"


def _result_to_task(result: Any) -> Task:
    if not isinstance(result, Mapping):
        raise JSONRPCError(-32603, f"expected a task object, got {type(result)!r}")
    # message/send may return either a Task or a bare Message; if it's a message
    # (no id/status), wrap it as a single-message task history so callers always
    # get a Task back.
    if "status" not in result and "history" not in result and result.get("kind") == "message":
        return Task.from_json({"history": [result], "status": {"state": "completed"}})
    return Task.from_json(result)


def _extract_task_list(result: Any) -> List[Mapping[str, Any]]:
    if isinstance(result, list):
        return [r for r in result if isinstance(r, Mapping)]
    if isinstance(result, Mapping):
        for key in ("tasks", "items", "result", "data"):
            value = result.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, Mapping)]
    raise JSONRPCError(-32603, "tasks/list returned an unexpected shape")


def _as_list(
    data: Any, container_keys: tuple = ("data", "items")
) -> List[Mapping[str, Any]]:
    if isinstance(data, list):
        return [d for d in data if isinstance(d, Mapping)]
    if isinstance(data, Mapping):
        for key in container_keys:
            value = data.get(key)
            if isinstance(value, list):
                return [d for d in value if isinstance(d, Mapping)]
    raise OABPError("expected a JSON array (or a container object with one)")


_VERIFICATION_TYPES = {
    "first_valid_match",
    "oracle",
    "peer_vote",
    "creator_judges",
}


def _validate_verification(
    verification_type: str, params: Optional[Mapping[str, Any]]
) -> None:
    if verification_type not in _VERIFICATION_TYPES:
        raise MissionError(
            f"unknown verification_type {verification_type!r}; "
            f"expected one of {sorted(_VERIFICATION_TYPES)}"
        )
    if verification_type == "first_valid_match":
        if not (params and params.get("regex")):
            raise MissionError(
                "first_valid_match missions require verification_params={'regex': ...}"
            )
        # Fail fast on an un-compilable regex rather than at resolution time.
        import re

        try:
            re.compile(params["regex"])
        except re.error as exc:
            raise MissionError(f"invalid first_valid_match regex: {exc}") from exc
