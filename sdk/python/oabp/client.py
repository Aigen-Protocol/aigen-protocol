"""OABP client implementation. AIP-1 v0.1 compliant."""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass, field
from typing import Optional


class OABPError(Exception):
    """Raised on protocol errors (HTTP non-2xx, malformed responses, missing fields)."""

    def __init__(self, message: str, status: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.body = body


@dataclass
class Mission:
    """AIP-1 §2 mission record."""
    id: str
    creator: str
    title: str
    description: str
    reward_asset: str
    reward_amount: int
    verification_type: str  # creator_judges | first_valid_match | peer_vote | oracle
    verification_params: dict
    deadline: str  # ISO 8601 UTC
    status: str  # open | escrowed | resolved | voided
    created_at: str
    extra: dict = field(default_factory=dict)  # forward-compat: unknown fields preserved here

    @classmethod
    def from_dict(cls, d: dict) -> "Mission":
        known = {"id", "creator", "title", "description", "reward",
                 "verification", "deadline", "status", "created_at"}
        reward = d.get("reward", {})
        verification = d.get("verification", {})
        return cls(
            id=d["id"], creator=d["creator"],
            title=d.get("title", ""), description=d.get("description", ""),
            reward_asset=reward.get("asset", "AIGEN"),
            reward_amount=int(reward.get("amount", 0)),
            verification_type=verification.get("type", "creator_judges"),
            verification_params=verification.get("params", {}),
            deadline=d.get("deadline", ""), status=d.get("status", "open"),
            created_at=d.get("created_at", ""),
            extra={k: v for k, v in d.items() if k not in known},
        )


@dataclass
class Submission:
    """AIP-1 §3 submission record."""
    submission_id: str
    mission_id: str
    submitter: str
    content_uri: str
    content_hash: str
    submitted_at: str
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "Submission":
        return cls(
            submission_id=d["submission_id"], mission_id=d["mission_id"],
            submitter=d["submitter"], content_uri=d.get("content_uri", ""),
            content_hash=d.get("content_hash", ""),
            submitted_at=d.get("submitted_at", ""),
            metadata=d.get("metadata", {}),
        )


@dataclass
class AgentReputation:
    """AIP-1 §5 reputation record. Portable across OABP-compliant implementations."""
    agent_id: str
    rating: int  # ELO; starts at 1400
    completed: int
    missions_won: int
    missions_lost: int
    last_activity_ts: Optional[str] = None
    badge_url: Optional[str] = None  # SVG embeddable badge
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentReputation":
        known = {"agent_id", "rating", "completed", "missions_won",
                 "missions_lost", "last_activity_ts", "badge_url"}
        return cls(
            agent_id=d.get("agent_id") or d.get("id", ""),
            rating=int(d.get("rating", 1400)),
            completed=int(d.get("completed", 0)),
            missions_won=int(d.get("missions_won", 0)),
            missions_lost=int(d.get("missions_lost", 0)),
            last_activity_ts=d.get("last_activity_ts"),
            badge_url=d.get("badge_url"),
            extra={k: v for k, v in d.items() if k not in known},
        )


class OABPClient:
    """Read+write client for an OABP-compliant implementation.

    The client autodiscovers endpoints from `/.well-known/oabp.json` if present,
    otherwise falls back to AIP-1 default paths.
    """

    DEFAULT_TIMEOUT = 15

    def __init__(self, base_url: str, timeout: int = DEFAULT_TIMEOUT, user_agent: str = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent or f"oabp-python/{__import__('oabp').__version__}"
        self._endpoints: Optional[dict] = None

    # ---- Discovery ----

    @classmethod
    def discover(cls, base_url: str, timeout: int = 10) -> dict:
        """AIP-1 §9 — fetch /.well-known/oabp.json. Returns the raw manifest."""
        url = f"{base_url.rstrip('/')}/.well-known/oabp.json"
        req = urllib.request.Request(url, headers={"User-Agent": "oabp-python-discover/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def endpoints(self) -> dict:
        """Returns the implementation's endpoint map. Cached after first call."""
        if self._endpoints is not None:
            return self._endpoints
        try:
            info = self.discover(self.base_url, timeout=self.timeout)
            self._endpoints = info.get("endpoints", {})
        except Exception:
            # Fall back to AIP-1 defaults
            self._endpoints = {
                "missions": "/missions",
                "missions_active": "/missions/active",
                "missions_stats": "/missions/stats",
                "agents": "/api/agents",
                "agent_badge": "/api/agents/{id}/badge.svg",
                "leaderboard": "/api/leaderboard",
                "submissions": "/api/submissions",
                "feed": "/feed.xml",
            }
        return self._endpoints

    # ---- Low-level HTTP ----

    def _get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise OABPError(f"GET {path} failed", status=e.code, body=e.read().decode("utf-8", errors="ignore"))

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method="POST", headers={
            "User-Agent": self.user_agent,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise OABPError(f"POST {path} failed", status=e.code, body=e.read().decode("utf-8", errors="ignore"))

    # ---- Mission operations ----

    def list_missions(self, status: str = "open", limit: int = 50) -> list[Mission]:
        ep = self.endpoints().get("missions_active" if status == "open" else "missions", "/missions")
        params = urllib.parse.urlencode({"status": status, "limit": limit})
        data = self._get(f"{ep}?{params}")
        items = data if isinstance(data, list) else (data.get("missions") or data.get("items") or [])
        return [Mission.from_dict(m) for m in items]

    def get_mission(self, mission_id: str) -> Mission:
        ep = self.endpoints().get("missions", "/missions")
        data = self._get(f"{ep}/{mission_id}")
        return Mission.from_dict(data)

    def submit(self, mission_id: str, agent_id: str, content_uri: str, content_hash: str,
               metadata: Optional[dict] = None) -> Submission:
        """AIP-1 §3 — submit a candidate solution to a mission."""
        ep = self.endpoints().get("missions", "/missions")
        body = {
            "submitter": agent_id,
            "content_uri": content_uri,
            "content_hash": content_hash,
            "metadata": metadata or {},
        }
        data = self._post(f"{ep}/{mission_id}/submit", body)
        return Submission.from_dict(data)

    def get_submission(self, mission_id: str, submission_id: str) -> Submission:
        ep = self.endpoints().get("submissions", "/api/submissions")
        data = self._get(f"{ep}/{submission_id}")
        return Submission.from_dict(data)

    # ---- Agent / reputation ----

    def agent(self, agent_id: str) -> AgentReputation:
        ep = self.endpoints().get("agents", "/api/agents")
        data = self._get(f"{ep}/{agent_id}")
        return AgentReputation.from_dict(data)

    def agent_badge_url(self, agent_id: str) -> str:
        """AIP-1 §5 mandatory — embeddable badge SVG URL."""
        ep = self.endpoints().get("agent_badge", "/api/agents/{id}/badge.svg")
        return f"{self.base_url}{ep.replace('{id}', agent_id)}"

    def leaderboard(self, limit: int = 50) -> list[AgentReputation]:
        ep = self.endpoints().get("leaderboard", "/api/leaderboard")
        data = self._get(f"{ep}?limit={limit}")
        items = data if isinstance(data, list) else (data.get("agents") or data.get("items") or [])
        return [AgentReputation.from_dict(a) for a in items]

    # ---- Convenience ----

    def __repr__(self):
        return f"OABPClient(base_url={self.base_url!r})"
