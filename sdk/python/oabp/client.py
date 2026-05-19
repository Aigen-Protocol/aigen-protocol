"""OABP client implementation. AIP-1 + AIP-2 + AIP-3 compliant."""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass, field
from typing import Optional


# AIP-2 §3.9 — verification method compatibility per mission type.
# Keys: mission_type → verification_method → compat level.
VERIFICATION_COMPAT: dict[str, dict[str, str]] = {
    "code_review": {
        "creator_judges": "RECOMMENDED",
        "first_valid_match": "NOT_RECOMMENDED",
        "oracle": "OPTIONAL",
        "peer_vote": "OPTIONAL",
    },
    "token_scan": {
        "creator_judges": "OPTIONAL",
        "first_valid_match": "NOT_RECOMMENDED",
        "oracle": "RECOMMENDED",
        "peer_vote": "OPTIONAL",
    },
    "doc_write": {
        "creator_judges": "RECOMMENDED",
        "first_valid_match": "NOT_RECOMMENDED",
        "oracle": "NOT_APPLICABLE",
        "peer_vote": "OPTIONAL",
    },
    "test_create": {
        "creator_judges": "RECOMMENDED",
        "first_valid_match": "OPTIONAL",
        "oracle": "RECOMMENDED",
        "peer_vote": "OPTIONAL",
    },
    "data_label": {
        "creator_judges": "OPTIONAL",
        "first_valid_match": "NOT_RECOMMENDED",
        "oracle": "RECOMMENDED",
        "peer_vote": "RECOMMENDED",
    },
    "translation": {
        "creator_judges": "OPTIONAL",
        "first_valid_match": "NOT_RECOMMENDED",
        "oracle": "OPTIONAL",
        "peer_vote": "RECOMMENDED",
    },
    "research": {
        "creator_judges": "RECOMMENDED",
        "first_valid_match": "NOT_RECOMMENDED",
        "oracle": "OPTIONAL",
        "peer_vote": "OPTIONAL",
    },
    "freeform": {
        "creator_judges": "RECOMMENDED",
        "first_valid_match": "OPTIONAL",
        "oracle": "OPTIONAL",
        "peer_vote": "RECOMMENDED",
    },
}


def check_verification_compat(mission_type: str, verification_method: str) -> tuple[str, bool]:
    """AIP-2 §3.9 — return (compat_level, is_warning) for a type + method pair.

    ``compat_level`` is one of: RECOMMENDED, OPTIONAL, NOT_RECOMMENDED, NOT_APPLICABLE, UNKNOWN.
    ``is_warning`` is True when the level is NOT_RECOMMENDED or NOT_APPLICABLE.

    Unknown types (custom types) always return (UNKNOWN, False) — custom types
    are implementation-defined and carry no compatibility guarantee from this table.
    """
    type_row = VERIFICATION_COMPAT.get(mission_type)
    if type_row is None:
        return "UNKNOWN", False
    level = type_row.get(verification_method, "UNKNOWN")
    return level, level in ("NOT_RECOMMENDED", "NOT_APPLICABLE")


class OABPError(Exception):
    """Raised on protocol errors (HTTP non-2xx, malformed responses, missing fields)."""

    def __init__(self, message: str, status: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.body = body


class OABPTransportError(OABPError):
    """Raised on transport-layer rejections: 400 Bad Request, 405 Method Not Allowed,
    406 Not Acceptable.  Parses the AIP-1 §7.2.1 structured JSON-RPC error body so
    callers can inspect ``error_code`` without re-parsing ``body`` themselves.
    """

    def __init__(self, message: str, status: int, body: Optional[str] = None,
                 error_code: Optional[int] = None):
        super().__init__(message, status=status, body=body)
        self.error_code = error_code

    @classmethod
    def _from_http(cls, status: int, path: str, raw: bytes) -> "OABPTransportError":
        body = raw.decode("utf-8", errors="ignore")
        error_code: Optional[int] = None
        detail = ""
        try:
            data = json.loads(body)
            err = data.get("error", {})
            error_code = err.get("code")
            detail = err.get("message", "")
        except (json.JSONDecodeError, AttributeError):
            detail = body[:120]
        msg = f"HTTP {status} on {path}"
        if detail:
            msg += f": {detail}"
        return cls(msg, status=status, body=body, error_code=error_code)


@dataclass
class MissionType:
    """AIP-2 §1 — mission type record from the shared type registry."""
    type_id: str
    display_name: str = ""
    description: str = ""
    required_params: list = field(default_factory=list)
    registry_version: str = ""
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d) -> "MissionType":
        if isinstance(d, str):
            return cls(type_id=d)
        known = {"type_id", "id", "display_name", "description", "required_params", "registry_version"}
        return cls(
            type_id=d.get("type_id") or d.get("id", ""),
            display_name=d.get("display_name", ""),
            description=d.get("description", ""),
            required_params=d.get("required_params", []),
            registry_version=d.get("registry_version", ""),
            extra={k: v for k, v in d.items() if k not in known},
        )

    def __str__(self) -> str:
        return self.type_id


@dataclass
class Mission:
    """AIP-1 §2 + AIP-2 mission record."""
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
    mission_type: str = "freeform"  # AIP-2 §1 — "freeform" when untyped
    type_params: dict = field(default_factory=dict)  # AIP-2 §1 — type-specific required fields
    extra: dict = field(default_factory=dict)  # forward-compat: unknown fields preserved here

    @classmethod
    def from_dict(cls, d: dict) -> "Mission":
        known = {"id", "creator", "title", "description", "reward",
                 "verification", "deadline", "status", "created_at",
                 "mission_type", "type_params"}
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
            mission_type=d.get("mission_type", "freeform"),
            type_params=d.get("type_params", {}),
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
class MissionTypeAffinity:
    """AIP-3 §5.2 — per-mission-type reputation slot.

    Only present in the response when the agent has at least one completion
    of that type (``completions >= 1``).
    """
    elo: int
    completions: int
    last_active: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "MissionTypeAffinity":
        return cls(
            elo=int(d.get("elo", 1400)),
            completions=int(d.get("completions", 0)),
            last_active=d.get("last_active"),
        )


@dataclass
class AgentReputation:
    """AIP-1 §5 + AIP-3 §5 reputation record. Portable across OABP-compliant implementations."""
    agent_id: str
    rating: int  # global ELO per AIP-3 §5.1; starts at 1400
    completed: int
    missions_won: int
    missions_lost: int
    last_activity_ts: Optional[str] = None
    badge_url: Optional[str] = None  # SVG embeddable badge
    mission_type_affinity: dict = field(default_factory=dict)  # AIP-3 §5.2
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentReputation":
        known = {"agent_id", "rating", "completed", "missions_won",
                 "missions_lost", "last_activity_ts", "badge_url",
                 "mission_type_affinity", "elo"}
        raw_affinity = d.get("mission_type_affinity") or {}
        affinity = {
            type_id: MissionTypeAffinity.from_dict(v) if isinstance(v, dict)
            else MissionTypeAffinity(elo=int(v), completions=0)
            for type_id, v in raw_affinity.items()
        }
        return cls(
            agent_id=d.get("agent_id") or d.get("id", ""),
            rating=int(d.get("rating") or d.get("elo", 1400)),
            completed=int(d.get("completed", 0)),
            missions_won=int(d.get("missions_won", 0)),
            missions_lost=int(d.get("missions_lost", 0)),
            last_activity_ts=d.get("last_activity_ts"),
            badge_url=d.get("badge_url"),
            mission_type_affinity=affinity,
            extra={k: v for k, v in d.items() if k not in known},
        )


@dataclass
class RegistryAttestation:
    """AIP-1 §1.4 — signed binding between a registry routing token and an EVM address.

    Posted by a registry operator to ``POST /attestations/registry`` to grant
    an end-user session identity inside an OABP server.  A server MUST verify
    ``signature`` against the registry's registered public key before granting
    the bound address any write access.
    """
    api_key: str                # opaque registry session token (UUID or similar)
    evm_address: str            # 0x... address that will accrue reputation
    registry_domain: str        # e.g. "smithery.ai"
    issued_at: str              # ISO 8601 UTC
    signature: str              # 0x ECDSA over keccak256(abi.encode(api_key, evm_address, issued_at))
    profile: Optional[str] = None          # opaque label+provider string (informational)
    ttl_seconds: int = 86400               # how long the binding is valid; default 24 h

    def is_valid_address(self) -> bool:
        """Return True if evm_address is syntactically a valid 20-byte EVM address."""
        import re
        return bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", self.evm_address))

    def to_dict(self) -> dict:
        d = {
            "api_key": self.api_key,
            "evm_address": self.evm_address,
            "registry_domain": self.registry_domain,
            "issued_at": self.issued_at,
            "signature": self.signature,
            "ttl_seconds": self.ttl_seconds,
        }
        if self.profile is not None:
            d["profile"] = self.profile
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "RegistryAttestation":
        return cls(
            api_key=d["api_key"],
            evm_address=d["evm_address"],
            registry_domain=d["registry_domain"],
            issued_at=d["issued_at"],
            signature=d["signature"],
            profile=d.get("profile"),
            ttl_seconds=int(d.get("ttl_seconds", 86400)),
        )


def check_registry_session(
    query_params: dict,
    authorization_header: Optional[str],
    attested_bindings: Optional[dict] = None,
) -> Optional[str]:
    """AIP-1 §1.4 — resolve the EVM address for a registry-routed request.

    Args:
        query_params: parsed query string dict (e.g. ``{"api_key": "uuid", "profile": "..."}``).
        authorization_header: value of the HTTP ``Authorization`` header, or None.
        attested_bindings: mapping from ``api_key`` → ``evm_address`` for previously
            verified registry attestations (maintained by the server).  Pass None to
            simulate a server with no active bindings.

    Returns:
        The bound EVM address string if an attestation exists for the api_key, or
        None if the session is anonymous.  A None return means the server MUST treat
        the request as anonymous (read-only) per §1.4 rule 2.
    """
    api_key = query_params.get("api_key")
    if not api_key:
        return None
    if attested_bindings and api_key in attested_bindings:
        return attested_bindings[api_key]
    return None


class OABPClient:
    """Read+write client for an OABP-compliant implementation.

    The client autodiscovers endpoints and transport type from
    ``/.well-known/oabp.json`` (AIP-1 §9) if present, otherwise falls back to
    AIP-1 default paths.  Check ``client.transport`` before probing ``/mcp``
    directly — a ``streamable_http`` transport requires session negotiation and
    will return a structured 400 on unauthenticated GET /mcp (AIP-1 §7.2.1).
    """

    DEFAULT_TIMEOUT = 15

    #: Transport values from the discovery manifest (AIP-1 §9).
    TRANSPORT_STREAMABLE_HTTP = "streamable_http"
    TRANSPORT_SSE = "sse"

    _TRANSPORT_ERRORS = {400, 405, 406}

    def __init__(self, base_url: str, timeout: int = DEFAULT_TIMEOUT, user_agent: str = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.user_agent = user_agent or f"oabp-python/{__import__('oabp').__version__}"
        self._endpoints: Optional[dict] = None
        self._transport: Optional[str] = None

    # ---- Discovery ----

    @classmethod
    def discover(cls, base_url: str, timeout: int = 10) -> dict:
        """AIP-1 §9 — fetch /.well-known/oabp.json. Returns the raw manifest."""
        url = f"{base_url.rstrip('/')}/.well-known/oabp.json"
        req = urllib.request.Request(url, headers={"User-Agent": "oabp-python-discover/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def endpoints(self) -> dict:
        """Returns the implementation's endpoint map. Cached after first call.

        Also populates ``self.transport`` from the discovery manifest so callers
        know the MCP transport type before making any requests (AIP-1 §7, §9).
        """
        if self._endpoints is not None:
            return self._endpoints
        try:
            info = self.discover(self.base_url, timeout=self.timeout)
            self._endpoints = info.get("endpoints", {})
            # AIP-1 §9: read transport field first, before attempting any /mcp call
            self._transport = info.get("transport")
        except Exception:
            # Fall back to AIP-1/AIP-2 defaults
            self._endpoints = {
                "missions": "/missions",
                "missions_active": "/missions/active",
                "missions_stats": "/missions/stats",
                "missions_types": "/missions/types",
                "agents": "/api/agents",
                "agent_badge": "/api/agents/{id}/badge.svg",
                "leaderboard": "/api/leaderboard",
                "submissions": "/api/submissions",
                "feed": "/feed.xml",
            }
        # Ensure AIP-2 endpoint has a default even when server-provided endpoints omit it
        self._endpoints.setdefault("missions_types", "/missions/types")
        return self._endpoints

    @property
    def transport(self) -> Optional[str]:
        """AIP-1 §7/§9 — MCP transport type declared by the server
        (``"streamable_http"``, ``"sse"``, or ``None`` when unknown).

        Resolved from ``/.well-known/oabp.json`` on first access.  Use this
        before probing ``/mcp`` directly: ``streamable_http`` requires a
        session-ID handshake and returns a structured 400 on plain GET.
        """
        if self._transport is None and self._endpoints is None:
            self.endpoints()  # triggers discovery and sets self._transport
        return self._transport

    # ---- Low-level HTTP ----

    def _get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raw = e.read()
            if e.code in self._TRANSPORT_ERRORS:
                raise OABPTransportError._from_http(e.code, path, raw)
            raise OABPError(f"GET {path} failed", status=e.code,
                            body=raw.decode("utf-8", errors="ignore"))

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
            raw = e.read()
            if e.code in self._TRANSPORT_ERRORS:
                raise OABPTransportError._from_http(e.code, path, raw)
            raise OABPError(f"POST {path} failed", status=e.code,
                            body=raw.decode("utf-8", errors="ignore"))

    # ---- Mission operations ----

    def list_missions(self, status: str = "open", limit: int = 50,
                      mission_type: Optional[str] = None) -> list[Mission]:
        """AIP-1 §2 + AIP-2 — list missions, optionally filtered by AIP-2 mission_type."""
        ep = self.endpoints().get("missions_active" if status == "open" else "missions", "/missions")
        qs: dict = {"status": status, "limit": limit}
        if mission_type is not None:
            qs["mission_type"] = mission_type
        data = self._get(f"{ep}?{urllib.parse.urlencode(qs)}")
        items = data if isinstance(data, list) else (data.get("missions") or data.get("items") or [])
        return [Mission.from_dict(m) for m in items]

    def list_mission_types(self) -> list[MissionType]:
        """AIP-2 §2 — return all mission types supported by this implementation.

        Combines registered types (from the shared AIP-2 registry) and any
        implementation-specific custom types. Returns an empty list when the
        server returns 404 (implementation doesn't declare AIP-2 support).
        """
        ep = self.endpoints().get("missions_types", "/missions/types")
        try:
            data = self._get(ep)
        except OABPError as e:
            if e.status == 404:
                return []
            raise

        result: list[MissionType] = []
        if isinstance(data, list):
            return [MissionType.from_dict(t) for t in data]

        rv = data.get("registry_version", "")
        for t in data.get("supported_types", []):
            mt = MissionType.from_dict(t)
            if not mt.registry_version:
                mt.registry_version = rv
            result.append(mt)
        for t in data.get("custom_types", []):
            result.append(MissionType.from_dict(t))
        return result

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
        """AIP-1 §5 + AIP-3 §5 — fetch agent reputation.

        Returns global ELO (``rep.rating``) and, when the server implements
        AIP-3 §5.2, per-mission-type affinity (``rep.mission_type_affinity``).
        Types with zero completions are omitted by compliant servers.
        """
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

    # ---- AIP-3 §3.1 Self-Submission Detection ----

    def check_self_submission(self, mission_id: str, submitter_address: str) -> bool:
        """AIP-3 §3.1 — return True if submitter is the mission creator (self-submission).

        Compares mission creator against submitter_address using case-insensitive EVM
        address equality.  Servers MUST NOT credit self-submissions to reputation; this
        helper lets the client surface the condition before wasting a submission slot.
        """
        try:
            mission = self.mission(mission_id)
        except Exception:
            return False
        creator = getattr(mission, "creator", None) or ""
        return creator.lower() == submitter_address.lower()

    # ---- Convenience ----

    def __repr__(self):
        return f"OABPClient(base_url={self.base_url!r})"
