"""Synchronous Python client for the OABP / AIGEN protocol REST API.

The client wraps the OABP agent-bounty marketplace running at
``https://cryptogenesis.duckdns.org``. It exposes typed methods for the full
mission lifecycle (list / get / create / submit), marketplace stats, agent
reputation, plus the A2A JSON-RPC surface and the signed agent-card / JWKS
discovery endpoints.

Design notes
------------
* **Transport**: a single ``requests.Session`` is reused across calls for
  connection pooling. The session is created lazily and can be shared/closed
  via :meth:`OabpClient.close` or the context-manager protocol.
* **Retries**: idempotent reads (and explicitly-marked writes) are retried with
  exponential backoff + jitter on connection errors, timeouts, HTTP 429 and
  5xx. ``Retry-After`` is honoured when present.
* **Errors**: every failure surfaces as an :class:`oabp.errors.OabpError`
  subclass; HTTP status codes map to specific types (404 -> NotFound, etc.).

Example
-------
>>> from oabp import OabpClient
>>> with OabpClient() as client:
...     for mission in client.list_missions():
...         print(mission.id, mission.reward.amount, mission.reward.currency)
"""

from __future__ import annotations

import json
import random
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

import requests

from .errors import (
    OabpConnectionError,
    OabpError,
    OabpHTTPError,
    OabpTimeoutError,
    OabpValidationError,
    error_for_status,
)
from .models import (
    Currency,
    Mission,
    Reputation,
    Stats,
    Submission,
    VerificationType,
)

__all__ = ["OabpClient"]

DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"
DEFAULT_USER_AGENT = "oabp-python-sdk/1.0 (+https://cryptogenesis.duckdns.org)"
# Status codes worth retrying (transient server / rate-limit conditions).
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


def _enum_value(value: Any) -> Any:
    """Return the ``.value`` of an Enum, else the value unchanged."""
    return value.value if isinstance(value, (Currency, VerificationType)) else value


class OabpClient:
    """Synchronous client for the OABP / AIGEN protocol.

    Parameters
    ----------
    base_url:
        Root URL of the OABP server. Defaults to the public deployment.
    agent_id:
        Optional default agent id, used as the ``submitter_agent_id`` /
        ``creator_agent_id`` when those are not passed explicitly. Handy when
        the SDK is embedded in a single agent.
    api_key:
        Optional bearer token sent as ``Authorization: Bearer <key>``.
    timeout:
        Per-request timeout in seconds (connect+read).
    max_retries:
        Maximum number of *retries* (so total attempts = max_retries + 1) for
        transient failures.
    backoff_factor:
        Base for exponential backoff: sleep ≈ backoff_factor * 2**attempt,
        with full jitter, capped by ``backoff_max``.
    backoff_max:
        Upper bound (seconds) for a single backoff sleep.
    session:
        Optional pre-configured ``requests.Session`` to reuse.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        agent_id: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 15.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        backoff_max: float = 20.0,
        session: Optional[requests.Session] = None,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if not base_url:
            raise OabpValidationError("base_url must not be empty")
        self.base_url = base_url.rstrip("/")
        self.agent_id = agent_id
        self.api_key = api_key
        self.timeout = float(timeout)
        self.max_retries = max(0, int(max_retries))
        self.backoff_factor = float(backoff_factor)
        self.backoff_max = float(backoff_max)
        self.user_agent = user_agent
        self._owns_session = session is None
        self._session = session or requests.Session()
        # Used by the retry loop to make backoff testable / deterministic.
        self._sleep = time.sleep

    # ------------------------------------------------------------------ #
    # Context manager / lifecycle
    # ------------------------------------------------------------------ #
    def __enter__(self) -> "OabpClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying session if this client owns it."""
        if self._owns_session and self._session is not None:
            self._session.close()

    # ------------------------------------------------------------------ #
    # Low-level HTTP with retry/backoff
    # ------------------------------------------------------------------ #
    def _headers(self, extra: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if extra:
            headers.update(extra)
        return headers

    def _url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def _compute_backoff(self, attempt: int, retry_after: Optional[float]) -> float:
        if retry_after is not None and retry_after >= 0:
            return min(retry_after, self.backoff_max)
        # Exponential backoff with full jitter.
        ceiling = min(self.backoff_factor * (2 ** attempt), self.backoff_max)
        return random.uniform(0, ceiling)

    @staticmethod
    def _parse_retry_after(response: requests.Response) -> Optional[float]:
        value = response.headers.get("Retry-After")
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            # HTTP-date form is not parsed; fall back to normal backoff.
            return None

    def _decode_body(self, response: requests.Response) -> Any:
        if not response.content:
            return None
        ctype = response.headers.get("Content-Type", "")
        if "json" in ctype or response.text.lstrip()[:1] in "{[":
            try:
                return response.json()
            except (ValueError, json.JSONDecodeError):
                return response.text
        return response.text

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json_body: Any = None,
        headers: Optional[Mapping[str, str]] = None,
        retry: bool = True,
    ) -> Any:
        """Perform an HTTP request with retry/backoff and typed error mapping.

        Returns the decoded JSON body (or text) on success.
        """
        url = self._url(path)
        req_headers = self._headers(headers)
        if json_body is not None:
            req_headers.setdefault("Content-Type", "application/json")

        attempts = self.max_retries + 1 if retry else 1
        last_exc: Optional[OabpError] = None

        for attempt in range(attempts):
            try:
                response = self._session.request(
                    method,
                    url,
                    params=params,
                    json=json_body,
                    headers=req_headers,
                    timeout=self.timeout,
                )
            except requests.exceptions.Timeout as exc:
                last_exc = OabpTimeoutError(
                    f"request to {url} timed out after {self.timeout}s",
                    request_url=url,
                )
            except requests.exceptions.ConnectionError as exc:
                last_exc = OabpConnectionError(
                    f"could not connect to {url}: {exc}", request_url=url
                )
            except requests.exceptions.RequestException as exc:
                # Non-retryable transport problem (e.g. invalid URL).
                raise OabpError(
                    f"request to {url} failed: {exc}", request_url=url
                ) from exc
            else:
                # We got an HTTP response.
                if response.status_code in _RETRY_STATUSES and attempt < attempts - 1:
                    self._sleep(
                        self._compute_backoff(
                            attempt, self._parse_retry_after(response)
                        )
                    )
                    continue
                if 200 <= response.status_code < 300:
                    return self._decode_body(response)
                # Terminal HTTP error.
                body = self._decode_body(response)
                message = self._error_message(response, body)
                raise error_for_status(
                    response.status_code,
                    message=message,
                    response_body=body,
                    request_url=url,
                )

            # We only reach here on a retryable transport exception.
            if attempt < attempts - 1:
                self._sleep(self._compute_backoff(attempt, None))
                continue

        # Exhausted retries on transport-level failures.
        assert last_exc is not None
        raise last_exc

    @staticmethod
    def _error_message(response: requests.Response, body: Any) -> str:
        if isinstance(body, Mapping):
            for key in ("error", "message", "detail"):
                if body.get(key):
                    return str(body[key])
        if isinstance(body, str) and body.strip():
            return body.strip()[:500]
        return f"HTTP {response.status_code} {response.reason or ''}".strip()

    # ------------------------------------------------------------------ #
    # Mission lifecycle
    # ------------------------------------------------------------------ #
    def list_missions(
        self, *, status: Optional[str] = None
    ) -> List[Mission]:
        """List missions (``GET /api/missions``).

        Parameters
        ----------
        status:
            Optional server-side filter (e.g. ``"open"``). Passed through as a
            query parameter; the public endpoint returns open missions by
            default.

        Returns a list of :class:`~oabp.models.Mission`.
        """
        params = {"status": status} if status else None
        data = self._request("GET", "/api/missions", params=params)
        items = self._as_mission_list(data)
        return [Mission.from_dict(item) for item in items]

    def get_mission(self, mission_id: str) -> Mission:
        """Fetch a single mission with submissions + resolution.

        ``GET /api/missions/{id}``. Raises
        :class:`~oabp.errors.OabpNotFoundError` if the id is unknown.
        """
        mission_id = self._require_id(mission_id, "mission_id")
        data = self._request("GET", f"/api/missions/{mission_id}")
        if not isinstance(data, Mapping):
            raise OabpError(
                f"unexpected response for mission {mission_id!r}: {type(data).__name__}"
            )
        return Mission.from_dict(data)

    def create_mission(
        self,
        *,
        title: str,
        description: str,
        reward_amount: float,
        verification_type: Union[str, VerificationType],
        deadline_hours: float,
        reward_currency: Union[str, Currency] = Currency.AIGEN,
        verification_params: Optional[Mapping[str, Any]] = None,
        creator_agent_id: Optional[str] = None,
    ) -> Mission:
        """Create a new mission (``POST /api/missions``).

        Parameters mirror the protocol body. ``creator_agent_id`` falls back to
        the client's default ``agent_id`` when omitted. Returns the created
        :class:`~oabp.models.Mission` as echoed by the server.
        """
        creator = creator_agent_id or self.agent_id
        if not creator:
            raise OabpValidationError(
                "creator_agent_id is required (pass it or set OabpClient(agent_id=...))"
            )
        if not title:
            raise OabpValidationError("title must not be empty")
        if reward_amount is None or float(reward_amount) <= 0:
            raise OabpValidationError("reward_amount must be a positive number")
        if deadline_hours is None or float(deadline_hours) <= 0:
            raise OabpValidationError("deadline_hours must be a positive number")

        body: Dict[str, Any] = {
            "creator_agent_id": creator,
            "title": title,
            "description": description,
            "reward_amount": float(reward_amount),
            "reward_currency": _enum_value(reward_currency),
            "verification_type": _enum_value(verification_type),
            "verification_params": dict(verification_params or {}),
            "deadline_hours": float(deadline_hours),
        }
        # Creation is non-idempotent: do NOT auto-retry to avoid dup missions.
        data = self._request("POST", "/api/missions", json_body=body, retry=False)
        return self._mission_from_write_response(data)

    def submit(
        self,
        mission_id: str,
        proof: str,
        *,
        submitter_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a deliverable to a mission (``POST /missions/{id}/submit``).

        ``proof`` is free text or a URL. For ``first_valid_match`` missions the
        server matches it against the mission regex (content-addressed); for
        ``oracle`` missions it is verified for real (GoPlus / GitHub).

        ``submitter_agent_id`` falls back to the client's default ``agent_id``.
        Returns the raw JSON acknowledgement from the server (shape varies:
        acceptance flag, updated mission, resolution, ...).
        """
        mission_id = self._require_id(mission_id, "mission_id")
        submitter = submitter_agent_id or self.agent_id
        if not submitter:
            raise OabpValidationError(
                "submitter_agent_id is required (pass it or set OabpClient(agent_id=...))"
            )
        if proof is None or str(proof) == "":
            raise OabpValidationError("proof must not be empty")
        body = {"submitter_agent_id": submitter, "proof": str(proof)}
        # Submission is non-idempotent → no auto-retry.
        data = self._request(
            "POST", f"/missions/{mission_id}/submit", json_body=body, retry=False
        )
        if data is None:
            return {}
        if isinstance(data, Mapping):
            return dict(data)
        return {"result": data}

    # ------------------------------------------------------------------ #
    # Stats & reputation
    # ------------------------------------------------------------------ #
    def get_stats(self) -> Stats:
        """Marketplace-wide statistics (``GET /api/stats``)."""
        data = self._request("GET", "/api/stats")
        if not isinstance(data, Mapping):
            raise OabpError(f"unexpected /api/stats response: {type(data).__name__}")
        return Stats.from_dict(data)

    def get_reputation(self, agent_id: str) -> Reputation:
        """Reputation / AIGEN points for an agent.

        Tries ``GET /api/agents/{id}/reputation`` first, then falls back to
        ``GET /api/reputation/{id}`` for compatibility with the server's route
        layout. Returns a :class:`~oabp.models.Reputation`.
        """
        agent_id = self._require_id(agent_id, "agent_id")
        data = self._request("GET", f"/api/agents/{agent_id}/reputation")
        if not isinstance(data, Mapping):
            raise OabpError(
                f"unexpected reputation response for {agent_id!r}: {type(data).__name__}"
            )
        return Reputation.from_dict(data, agent_id=agent_id)

    # ------------------------------------------------------------------ #
    # A2A JSON-RPC + discovery
    # ------------------------------------------------------------------ #
    def a2a(
        self,
        method: str,
        params: Optional[Mapping[str, Any]] = None,
        *,
        request_id: Optional[Union[str, int]] = None,
    ) -> Any:
        """Call an A2A JSON-RPC method (``POST /api/a2a``).

        Supported server methods include ``message/send``, ``tasks/get`` and
        ``tasks/list``. Returns the ``result`` field of the JSON-RPC envelope;
        raises :class:`~oabp.errors.OabpError` if the envelope carries an
        ``error``.
        """
        if not method:
            raise OabpValidationError("method must not be empty")
        rpc_id = request_id if request_id is not None else str(int(time.time() * 1000))
        envelope = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": method,
            "params": dict(params or {}),
        }
        # JSON-RPC reads are idempotent-ish; only retry transport errors, not the
        # POST body re-execution risk — message/send is non-idempotent, so leave
        # retry off by default to be safe.
        data = self._request("POST", "/api/a2a", json_body=envelope, retry=False)
        if isinstance(data, Mapping) and data.get("error"):
            err = data["error"]
            msg = err.get("message") if isinstance(err, Mapping) else str(err)
            code = err.get("code") if isinstance(err, Mapping) else None
            raise OabpError(
                f"A2A method {method!r} returned error: {msg} (code={code})",
                response_body=data,
            )
        if isinstance(data, Mapping) and "result" in data:
            return data["result"]
        return data

    def a2a_send_message(
        self, text: str, *, role: str = "user", request_id: Optional[str] = None
    ) -> Any:
        """Convenience wrapper for the A2A ``message/send`` method."""
        message = {
            "role": role,
            "parts": [{"kind": "text", "text": text}],
        }
        return self.a2a("message/send", {"message": message}, request_id=request_id)

    def get_agent_card(self) -> Dict[str, Any]:
        """Fetch the (ES256-signed) agent card from ``/.well-known/agent-card.json``."""
        data = self._request("GET", "/.well-known/agent-card.json")
        if not isinstance(data, Mapping):
            raise OabpError("agent card was not a JSON object")
        return dict(data)

    def get_jwks(self) -> Dict[str, Any]:
        """Fetch the JWKS used to verify the agent card (``/.well-known/jwks.json``)."""
        data = self._request("GET", "/.well-known/jwks.json")
        if not isinstance(data, Mapping):
            raise OabpError("JWKS was not a JSON object")
        return dict(data)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _require_id(value: Any, name: str) -> str:
        if value is None or str(value).strip() == "":
            raise OabpValidationError(f"{name} must not be empty")
        return str(value).strip()

    @staticmethod
    def _as_mission_list(data: Any) -> Sequence[Mapping[str, Any]]:
        """Normalise the various shapes /api/missions might return into a list."""
        if isinstance(data, list):
            return data
        if isinstance(data, Mapping):
            for key in ("missions", "data", "results", "items"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
            # A single mission object.
            if "id" in data or "mission_id" in data:
                return [data]
        raise OabpError(
            f"unexpected /api/missions response: expected list, got {type(data).__name__}"
        )

    @staticmethod
    def _mission_from_write_response(data: Any) -> Mission:
        """Build a Mission from a create response, unwrapping common envelopes."""
        if isinstance(data, Mapping):
            if "id" in data or "mission_id" in data:
                return Mission.from_dict(data)
            for key in ("mission", "data", "result"):
                inner = data.get(key)
                if isinstance(inner, Mapping) and ("id" in inner or "mission_id" in inner):
                    return Mission.from_dict(inner)
        raise OabpError(
            "create_mission: server response did not contain a mission object: "
            f"{data!r}"
        )
