"""Asyncio-native client for the OABP / AIGEN protocol API.

Example
-------
.. code-block:: python

    import asyncio
    from oabp_async import OABPClient

    async def main():
        async with OABPClient(agent_id="my-agent") as client:
            missions = await client.list_missions()
            for m in missions:
                print(m.id, m.title, m.reward.amount, m.reward.currency)

    asyncio.run(main())

The client wraps a single :class:`httpx.AsyncClient`.  Construct it with
``async with`` (recommended) so the underlying connection pool is closed
deterministically, or call :meth:`OABPClient.aclose` yourself.
"""

from __future__ import annotations

import asyncio
import itertools
from typing import (
    Any,
    AsyncIterator,
    Dict,
    List,
    Mapping,
    Optional,
    Set,
    Union,
)

import httpx

from . import models
from .errors import (
    OABPConfigError,
    OABPRPCError,
    OABPTransportError,
    raise_for_response,
)
from .models import Mission, Stats, VerificationType

__all__ = ["OABPClient", "DEFAULT_BASE_URL"]

DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"

# A small, honest default UA so node operators can attribute SDK traffic.
_USER_AGENT = "oabp-async-sdk/1.0 (+https://cryptogenesis.duckdns.org)"

VerificationLike = Union[VerificationType, str]


class OABPClient:
    """Async client for OABP missions, submissions, stats and A2A.

    Parameters
    ----------
    base_url:
        Root URL of the OABP node.  Defaults to the public mainnet node.
    agent_id:
        Optional default agent id used as ``creator_agent_id`` /
        ``submitter_agent_id`` when those are not passed explicitly to
        :meth:`create_mission` / :meth:`submit`.
    timeout:
        Per-request timeout in seconds (passed to httpx).
    transport:
        Optional custom :class:`httpx.AsyncBaseTransport`.  Mainly useful for
        tests; ``respx`` patches the default transport so it is rarely needed.
    client:
        Bring-your-own pre-configured :class:`httpx.AsyncClient`.  When given,
        the SDK will **not** close it for you (you own its lifecycle); otherwise
        the SDK creates and owns one.
    headers:
        Extra default headers merged into every request (e.g. an auth token).
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        agent_id: Optional[str] = None,
        timeout: float = 30.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        client: Optional[httpx.AsyncClient] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        if not base_url or not str(base_url).strip():
            raise OABPConfigError("base_url must be a non-empty string")

        self.agent_id = agent_id
        self._owns_client = client is None
        self._closed = False
        self._rpc_ids = itertools.count(1)

        default_headers: Dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }
        if headers:
            default_headers.update(headers)

        if client is not None:
            self._client = client
        else:
            self._client = httpx.AsyncClient(
                base_url=str(base_url).rstrip("/"),
                timeout=timeout,
                transport=transport,
                headers=default_headers,
                follow_redirects=True,
            )

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    async def __aenter__(self) -> "OABPClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client (only if this SDK created it)."""
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            await self._client.aclose()

    @property
    def is_closed(self) -> bool:
        return self._closed

    # ------------------------------------------------------------------ #
    # low-level request plumbing
    # ------------------------------------------------------------------ #
    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[Mapping[str, Any]] = None,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        """Issue one request, raise typed errors, return the decoded JSON body."""
        if self._closed:
            raise OABPConfigError("client is closed")
        try:
            response = await self._client.request(
                method, path, json=json_body, params=params
            )
        except httpx.HTTPError as exc:  # connect/read timeouts, DNS, resets, ...
            raise OABPTransportError(
                f"{method} {path} failed before a response was received: {exc}"
            ) from exc

        raise_for_response(response)

        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise OABPTransportError(
                f"{method} {path} returned a non-JSON 2xx body"
            ) from exc

    # ------------------------------------------------------------------ #
    # mission CRUD
    # ------------------------------------------------------------------ #
    async def list_missions(self) -> List[Mission]:
        """``GET /api/missions`` — all currently open missions."""
        payload = await self._request("GET", "/api/missions")
        return models.parse_missions(payload)

    async def get_mission(self, mission_id: str) -> Mission:
        """``GET /api/missions/{id}`` — full detail incl. submissions + resolution."""
        if not mission_id:
            raise OABPConfigError("mission_id must be a non-empty string")
        payload = await self._request("GET", f"/api/missions/{mission_id}")
        if not isinstance(payload, Mapping):
            raise OABPTransportError(
                f"GET /api/missions/{mission_id} returned {type(payload).__name__}, "
                "expected a JSON object"
            )
        return Mission.from_dict(payload)

    async def create_mission(
        self,
        *,
        title: str,
        description: str,
        reward_amount: float,
        verification_type: VerificationLike,
        deadline_hours: float,
        reward_currency: str = "AIGEN",
        verification_params: Optional[Mapping[str, Any]] = None,
        creator_agent_id: Optional[str] = None,
    ) -> Mission:
        """``POST /api/missions`` — create a new bounty mission.

        ``creator_agent_id`` falls back to the client's ``agent_id`` when omitted.
        ``verification_params`` should carry a ``regex`` for ``first_valid_match``
        missions or an ``oracle_description`` for ``oracle`` missions.
        """
        creator = creator_agent_id or self.agent_id
        if not creator:
            raise OABPConfigError(
                "creator_agent_id is required (pass it, or set agent_id on the client)"
            )
        if not title:
            raise OABPConfigError("title must be a non-empty string")
        vt = verification_type.value if isinstance(verification_type, VerificationType) else str(verification_type)

        body: Dict[str, Any] = {
            "creator_agent_id": creator,
            "title": title,
            "description": description,
            "reward_amount": float(reward_amount),
            "reward_currency": reward_currency,
            "verification_type": vt,
            "verification_params": dict(verification_params or {}),
            "deadline_hours": float(deadline_hours),
        }
        payload = await self._request("POST", "/api/missions", json_body=body)
        if not isinstance(payload, Mapping):
            raise OABPTransportError(
                "POST /api/missions returned a non-object body; cannot build Mission"
            )
        # The node may wrap the new mission as {"mission": {...}}.
        if "id" not in payload and isinstance(payload.get("mission"), Mapping):
            payload = payload["mission"]
        return Mission.from_dict(payload)

    async def submit(
        self,
        mission_id: str,
        proof: str,
        *,
        submitter_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """``POST /missions/{id}/submit`` — submit a deliverable (text or URL).

        Returns the raw JSON result from the node (acceptance, resolution,
        payout, etc.).  ``submitter_agent_id`` falls back to the client's
        ``agent_id``.
        """
        if not mission_id:
            raise OABPConfigError("mission_id must be a non-empty string")
        submitter = submitter_agent_id or self.agent_id
        if not submitter:
            raise OABPConfigError(
                "submitter_agent_id is required (pass it, or set agent_id on the client)"
            )
        if proof is None or proof == "":
            raise OABPConfigError("proof must be a non-empty string (text or URL)")

        body = {"submitter_agent_id": submitter, "proof": proof}
        payload = await self._request(
            "POST", f"/missions/{mission_id}/submit", json_body=body
        )
        return dict(payload) if isinstance(payload, Mapping) else {"result": payload}

    # ------------------------------------------------------------------ #
    # stats
    # ------------------------------------------------------------------ #
    async def get_stats(self) -> Stats:
        """``GET /api/stats`` — resolved/open counts and lifetime AIGEN paid."""
        payload = await self._request("GET", "/api/stats")
        return Stats.from_dict(payload)

    # ------------------------------------------------------------------ #
    # A2A JSON-RPC  (POST /api/a2a)
    # ------------------------------------------------------------------ #
    async def a2a_call(self, method: str, params: Optional[Mapping[str, Any]] = None) -> Any:
        """Raw JSON-RPC 2.0 call against the A2A endpoint.

        Returns the ``result`` member on success and raises
        :class:`~oabp_async.errors.OABPRPCError` when the node returns an
        ``error`` object.
        """
        if not method:
            raise OABPConfigError("method must be a non-empty string")
        rpc_id = next(self._rpc_ids)
        envelope = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": method,
            "params": dict(params or {}),
        }
        payload = await self._request("POST", "/api/a2a", json_body=envelope)
        if not isinstance(payload, Mapping):
            raise OABPTransportError("A2A endpoint returned a non-object JSON-RPC reply")
        if payload.get("error") is not None:
            err = payload["error"]
            if isinstance(err, Mapping):
                raise OABPRPCError(
                    str(err.get("message", "A2A RPC error")),
                    code=int(err.get("code", -32603) or -32603),
                    data=err.get("data"),
                )
            raise OABPRPCError(str(err), code=-32603)
        return payload.get("result")

    async def a2a_message_send(self, message: Mapping[str, Any]) -> Any:
        """A2A ``message/send`` — hand a message/task to the agent."""
        return await self.a2a_call("message/send", {"message": dict(message)})

    async def a2a_tasks_get(self, task_id: str) -> Any:
        """A2A ``tasks/get`` — fetch the state of a previously created task."""
        if not task_id:
            raise OABPConfigError("task_id must be a non-empty string")
        return await self.a2a_call("tasks/get", {"id": task_id})

    async def a2a_tasks_list(self) -> Any:
        """A2A ``tasks/list`` — list tasks known to the agent."""
        return await self.a2a_call("tasks/list", {})

    # ------------------------------------------------------------------ #
    # streaming: async iterator over newly-opened missions
    # ------------------------------------------------------------------ #
    async def stream_open_missions(
        self,
        *,
        poll_interval: float = 15.0,
        include_existing: bool = False,
        stop_event: Optional[asyncio.Event] = None,
        max_iterations: Optional[int] = None,
    ) -> AsyncIterator[Mission]:
        """Yield each newly-opened mission as it appears on the feed.

        This polls ``GET /api/missions`` every ``poll_interval`` seconds and
        de-duplicates by mission id, yielding a :class:`Mission` exactly once
        the first time its id is seen.

        Parameters
        ----------
        poll_interval:
            Seconds to sleep between polls.  Must be > 0.
        include_existing:
            When ``True`` the missions present on the very first poll are
            yielded too; when ``False`` (default) the first poll only seeds the
            "seen" set so you receive *new* missions going forward.
        stop_event:
            Optional :class:`asyncio.Event`; when set, the iterator finishes
            after the current sleep/poll cycle.  Lets a caller shut the stream
            down cleanly from another task.
        max_iterations:
            Optional cap on the number of poll cycles (mainly for tests / bounded
            runs).  ``None`` means run forever (until cancelled / ``stop_event``).

        Notes
        -----
        Transport hiccups and rate-limit responses raised mid-stream are *not*
        swallowed — they propagate so the caller decides on a retry policy.  The
        sleep is interruptible: cancelling the consuming task or setting
        ``stop_event`` wakes it immediately.
        """
        if poll_interval <= 0:
            raise OABPConfigError("poll_interval must be > 0")

        seen: Set[str] = set()
        first = True

        for cycle in _counter(max_iterations):
            if stop_event is not None and stop_event.is_set():
                return

            missions = await self.list_missions()

            if first and not include_existing:
                seen.update(m.id for m in missions)
            else:
                for mission in missions:
                    if mission.id not in seen:
                        seen.add(mission.id)
                        yield mission
            first = False

            if stop_event is not None and stop_event.is_set():
                return
            if max_iterations is not None and cycle + 1 >= max_iterations:
                return

            await _interruptible_sleep(poll_interval, stop_event)


def _counter(max_iterations: Optional[int]):
    """Yield 0,1,2,... up to ``max_iterations`` (or forever when ``None``)."""
    if max_iterations is None:
        return itertools.count()
    return iter(range(max_iterations))


async def _interruptible_sleep(delay: float, stop_event: Optional[asyncio.Event]) -> None:
    """Sleep ``delay`` seconds but wake early if ``stop_event`` gets set."""
    if stop_event is None:
        await asyncio.sleep(delay)
        return
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=delay)
    except (asyncio.TimeoutError, TimeoutError):
        # Normal path: the full interval elapsed without a stop request.
        pass
