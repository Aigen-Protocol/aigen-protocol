"""Tiny HTTP helper shared by the OABP / AIGEN Dify tools and provider.

The plugin talks to the live OABP REST API with plain ``requests`` — no SDK
dependency, so the package stays self-contained inside a Dify plugin. This
module centralises base-URL / header handling, the request+error mapping, and
the response-shaping helpers (``mission_to_dict`` etc.) so each tool file only
contains its parameter wiring and ``_invoke`` body.

API surface used (base URL configured in the provider credentials, default
``https://cryptogenesis.duckdns.org``):

* ``GET  /api/missions``                 -> list missions
* ``GET  /api/missions/{id}``            -> one mission (+ submissions, resolution)
* ``POST /api/missions``                 -> create a mission
* ``POST /missions/{id}/submit``         -> submit a deliverable (proof)
* ``GET  /api/stats``                    -> marketplace stats
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

import requests

DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"
DEFAULT_USER_AGENT = "oabp-dify-plugin/0.1 (+https://cryptogenesis.duckdns.org)"
DEFAULT_TIMEOUT = 60.0

# The four permissionless verification methods the protocol supports.
VERIFICATION_TYPES = (
    "first_valid_match",
    "oracle",
    "peer_vote",
    "creator_judges",
)
CURRENCIES = ("AIGEN", "USDC")


class OabpError(Exception):
    """Any OABP HTTP/transport failure. Carries an HTTP ``status_code`` if known."""

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class OabpClient:
    """Minimal synchronous client for the OABP / AIGEN REST API.

    Parameters
    ----------
    base_url:
        Root URL of the deployment. Falls back to the public node.
    api_key:
        Optional bearer token (``Authorization: Bearer <key>``).
    agent_id:
        Optional default agent id used as creator/submitter when a tool does not
        receive one explicitly.
    session:
        Optional pre-built ``requests.Session`` — injected by the offline tests
        so no real network call is made.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        api_key: Optional[str] = None,
        agent_id: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key or None
        self.agent_id = agent_id or None
        self.timeout = float(timeout)
        self._session = session or requests.Session()

    # ------------------------------------------------------------------ #
    # Construction from Dify credentials
    # ------------------------------------------------------------------ #
    @classmethod
    def from_credentials(
        cls,
        credentials: Optional[Mapping[str, Any]],
        *,
        session: Optional[requests.Session] = None,
    ) -> "OabpClient":
        creds = dict(credentials or {})
        return cls(
            base_url=creds.get("oabp_base_url"),
            api_key=creds.get("api_key"),
            agent_id=creds.get("agent_id"),
            session=session,
        )

    # ------------------------------------------------------------------ #
    # Low-level request
    # ------------------------------------------------------------------ #
    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json_body: Any = None,
    ) -> Any:
        url = self._url(path)
        try:
            response = self._session.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise OabpError(f"request to {url} timed out after {self.timeout}s") from exc
        except requests.exceptions.RequestException as exc:
            raise OabpError(f"could not reach {url}: {exc}") from exc

        body = self._decode(response)
        if 200 <= response.status_code < 300:
            return body
        raise OabpError(
            self._error_message(response, body), status_code=response.status_code
        )

    @staticmethod
    def _decode(response: "requests.Response") -> Any:
        if not getattr(response, "content", b""):
            return None
        ctype = response.headers.get("Content-Type", "") if response.headers else ""
        if "json" in ctype or (response.text or "").lstrip()[:1] in "{[":
            try:
                return response.json()
            except ValueError:
                return response.text
        return response.text

    @staticmethod
    def _error_message(response: "requests.Response", body: Any) -> str:
        if isinstance(body, Mapping):
            for key in ("error", "message", "detail"):
                if body.get(key):
                    return str(body[key])
        if isinstance(body, str) and body.strip():
            return body.strip()[:500]
        reason = getattr(response, "reason", "") or ""
        return f"HTTP {response.status_code} {reason}".strip()

    # ------------------------------------------------------------------ #
    # Mission lifecycle
    # ------------------------------------------------------------------ #
    def list_missions(self, *, status: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"status": status} if status else None
        data = self._request("GET", "/api/missions", params=params)
        return _as_mission_list(data)

    def get_mission(self, mission_id: str) -> Dict[str, Any]:
        data = self._request("GET", f"/api/missions/{mission_id}")
        if not isinstance(data, Mapping):
            raise OabpError(f"unexpected response for mission {mission_id!r}")
        return dict(data)

    def create_mission(
        self,
        *,
        title: str,
        description: str,
        reward_amount: float,
        verification_type: str,
        deadline_hours: float,
        reward_currency: str = "AIGEN",
        verification_params: Optional[Mapping[str, Any]] = None,
        creator_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        creator = creator_agent_id or self.agent_id
        if not creator:
            raise OabpError(
                "creator_agent_id is required (pass it or set a default agent id "
                "in the OABP credentials)"
            )
        body: Dict[str, Any] = {
            "creator_agent_id": creator,
            "title": title,
            "description": description,
            "reward_amount": float(reward_amount),
            "reward_currency": reward_currency,
            "verification_type": verification_type,
            "verification_params": dict(verification_params or {}),
            "deadline_hours": float(deadline_hours),
        }
        data = self._request("POST", "/api/missions", json_body=body)
        return _unwrap_mission(data)

    def submit(
        self,
        mission_id: str,
        proof: str,
        *,
        submitter_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        submitter = submitter_agent_id or self.agent_id
        if not submitter:
            raise OabpError(
                "submitter_agent_id is required (pass it or set a default agent id "
                "in the OABP credentials)"
            )
        body = {"submitter_agent_id": submitter, "proof": str(proof)}
        data = self._request("POST", f"/missions/{mission_id}/submit", json_body=body)
        if data is None:
            return {}
        if isinstance(data, Mapping):
            return dict(data)
        return {"result": data}

    def get_stats(self) -> Dict[str, Any]:
        data = self._request("GET", "/api/stats")
        if not isinstance(data, Mapping):
            raise OabpError("unexpected /api/stats response")
        return dict(data)


# --------------------------------------------------------------------------- #
# Response normalisation / shaping (kept dependency-free + JSON-serialisable)
# --------------------------------------------------------------------------- #
def _as_mission_list(data: Any) -> List[Dict[str, Any]]:
    """Normalise the various shapes ``/api/missions`` might return into a list."""
    if isinstance(data, list):
        return [dict(m) for m in data if isinstance(m, Mapping)]
    if isinstance(data, Mapping):
        for key in ("missions", "data", "results", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return [dict(m) for m in value if isinstance(m, Mapping)]
        if "id" in data or "mission_id" in data:
            return [dict(data)]
    raise OabpError(
        f"unexpected /api/missions response: expected list, got {type(data).__name__}"
    )


def _unwrap_mission(data: Any) -> Dict[str, Any]:
    """Pull a mission object out of a create response, unwrapping common envelopes."""
    if isinstance(data, Mapping):
        if "id" in data or "mission_id" in data:
            return dict(data)
        for key in ("mission", "data", "result"):
            inner = data.get(key)
            if isinstance(inner, Mapping) and ("id" in inner or "mission_id" in inner):
                return dict(inner)
    raise OabpError(
        f"create_mission: server response did not contain a mission object: {data!r}"
    )


def _reward_to_dict(reward: Any) -> Dict[str, Any]:
    reward = reward if isinstance(reward, Mapping) else {}
    raw_amount = reward.get("amount", 0)
    try:
        amount = float(raw_amount)
    except (TypeError, ValueError):
        amount = 0.0
    return {"amount": amount, "currency": reward.get("currency") or "AIGEN"}


def mission_summary(mission: Mapping[str, Any]) -> Dict[str, Any]:
    """Trim a mission to the fields that matter for listing (JSON-serialisable)."""
    mission = mission if isinstance(mission, Mapping) else {}
    submissions = mission.get("submissions") or []
    return {
        "id": str(mission.get("id") or mission.get("mission_id") or ""),
        "title": mission.get("title"),
        "reward": _reward_to_dict(mission.get("reward")),
        "verification_type": mission.get("verification_type"),
        "deadline": mission.get("deadline"),
        "status": mission.get("status"),
        "submission_count": len(submissions) if isinstance(submissions, list) else 0,
    }


def mission_detail(mission: Mapping[str, Any]) -> Dict[str, Any]:
    """Full mission view: summary + description, submissions, resolution."""
    mission = mission if isinstance(mission, Mapping) else {}
    out = mission_summary(mission)
    out["description"] = mission.get("description")
    out["verification_params"] = dict(mission.get("verification_params") or {})
    out["creator_agent_id"] = mission.get("creator_agent_id") or mission.get("creator")

    submissions = mission.get("submissions") or []
    out["submissions"] = [
        {
            "submitter_agent_id": (
                s.get("submitter_agent_id") or s.get("agent_id")
            ),
            "proof": s.get("proof"),
            "accepted": s.get("accepted"),
            "submitted_at": s.get("submitted_at") or s.get("timestamp"),
        }
        for s in submissions
        if isinstance(s, Mapping)
    ]

    resolution = mission.get("resolution")
    if isinstance(resolution, Mapping):
        reward_paid = resolution.get("reward_paid")
        try:
            reward_paid = float(reward_paid) if reward_paid is not None else None
        except (TypeError, ValueError):
            reward_paid = None
        out["resolution"] = {
            "winner_agent_id": (
                resolution.get("winner_agent_id") or resolution.get("winner")
            ),
            "winning_proof": resolution.get("winning_proof") or resolution.get("proof"),
            "verified": resolution.get("verified"),
            "reward_paid": reward_paid,
            "resolved_at": resolution.get("resolved_at"),
        }
    else:
        out["resolution"] = None
    return out


def stats_to_dict(stats: Mapping[str, Any]) -> Dict[str, Any]:
    stats = stats if isinstance(stats, Mapping) else {}

    def _int(key: str) -> int:
        try:
            return int(stats.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0

    try:
        lifetime = float(stats.get("lifetime_reward_aigen_paid", 0) or 0)
    except (TypeError, ValueError):
        lifetime = 0.0
    return {
        "resolved": _int("resolved"),
        "open": _int("open"),
        "lifetime_reward_aigen_paid": lifetime,
    }
