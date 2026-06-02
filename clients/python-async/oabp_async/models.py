"""Typed, immutable data models for OABP / AIGEN protocol objects.

The OABP node returns plain JSON.  These dataclasses give callers attribute
access, equality, ``repr`` and a few convenience helpers (e.g. deadline as an
aware :class:`datetime.datetime`, "is this mission still open?") while staying
forgiving about unknown / missing fields so the SDK keeps working as the
protocol evolves.  Every model keeps the original decoded payload in ``raw`` so
nothing is ever lost in translation.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

__all__ = [
    "Currency",
    "VerificationType",
    "MissionStatus",
    "Reward",
    "VerificationParams",
    "Submission",
    "Resolution",
    "Mission",
    "Stats",
]


def _as_mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


class Currency(str, enum.Enum):
    """Reward currencies understood by the protocol.

    Subclasses :class:`str` so it compares/serialises transparently as the wire
    value.  Unknown currencies are preserved verbatim via :meth:`coerce`.
    """

    AIGEN = "AIGEN"
    USDC = "USDC"

    @classmethod
    def coerce(cls, value: Any) -> "Currency | str | None":
        if value is None:
            return None
        try:
            return cls(value)
        except ValueError:
            return str(value)


class VerificationType(str, enum.Enum):
    """How a mission's submissions get judged."""

    FIRST_VALID_MATCH = "first_valid_match"
    ORACLE = "oracle"
    PEER_VOTE = "peer_vote"
    CREATOR_JUDGES = "creator_judges"

    @classmethod
    def coerce(cls, value: Any) -> "VerificationType | str | None":
        if value is None:
            return None
        try:
            return cls(value)
        except ValueError:
            return str(value)


class MissionStatus(str, enum.Enum):
    """Lifecycle state of a mission."""

    OPEN = "open"
    RESOLVED = "resolved"
    EXPIRED = "expired"
    CANCELLED = "cancelled"

    @classmethod
    def coerce(cls, value: Any) -> "MissionStatus | str | None":
        if value is None:
            return None
        try:
            return cls(value)
        except ValueError:
            return str(value)


@dataclass(frozen=True)
class Reward:
    """The bounty attached to a mission."""

    amount: float
    currency: "Currency | str | None"
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Any) -> "Reward":
        data = _as_mapping(data)
        amount_raw = data.get("amount", 0)
        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            amount = 0.0
        return cls(amount=amount, currency=Currency.coerce(data.get("currency")), raw=data)


@dataclass(frozen=True)
class VerificationParams:
    """Parameters that drive the verifier for a mission.

    Only a couple of fields are first-class (the regex for
    ``first_valid_match`` and the human description for ``oracle`` missions);
    everything else stays available through :attr:`raw`.
    """

    regex: Optional[str] = None
    oracle_description: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Any) -> "VerificationParams":
        data = _as_mapping(data)
        regex = data.get("regex")
        oracle_description = data.get("oracle_description")
        return cls(
            regex=str(regex) if regex is not None else None,
            oracle_description=str(oracle_description) if oracle_description is not None else None,
            raw=data,
        )


@dataclass(frozen=True)
class Submission:
    """A single deliverable submitted against a mission."""

    submitter_agent_id: Optional[str]
    proof: Optional[str]
    submitted_at: Optional[int]
    accepted: Optional[bool]
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Any) -> "Submission":
        data = _as_mapping(data)
        ts = data.get("submitted_at", data.get("timestamp"))
        try:
            submitted_at = int(ts) if ts is not None else None
        except (TypeError, ValueError):
            submitted_at = None
        return cls(
            submitter_agent_id=data.get("submitter_agent_id", data.get("agent_id")),
            proof=data.get("proof"),
            submitted_at=submitted_at,
            accepted=data.get("accepted"),
            raw=data,
        )

    @property
    def submitted_datetime(self) -> Optional[datetime]:
        if self.submitted_at is None:
            return None
        return datetime.fromtimestamp(self.submitted_at, tz=timezone.utc)


@dataclass(frozen=True)
class Resolution:
    """The outcome recorded once a mission has been resolved."""

    winner_agent_id: Optional[str]
    winning_proof: Optional[str]
    reward_paid: Optional[float]
    resolved_at: Optional[int]
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Any) -> Optional["Resolution"]:
        if not data:
            return None
        data = _as_mapping(data)
        paid_raw = data.get("reward_paid", data.get("amount_paid"))
        try:
            reward_paid = float(paid_raw) if paid_raw is not None else None
        except (TypeError, ValueError):
            reward_paid = None
        ts = data.get("resolved_at")
        try:
            resolved_at = int(ts) if ts is not None else None
        except (TypeError, ValueError):
            resolved_at = None
        return cls(
            winner_agent_id=data.get("winner_agent_id", data.get("winner")),
            winning_proof=data.get("winning_proof", data.get("proof")),
            reward_paid=reward_paid,
            resolved_at=resolved_at,
            raw=data,
        )


@dataclass(frozen=True)
class Mission:
    """A bounty mission on the OABP marketplace."""

    id: str
    title: Optional[str]
    description: Optional[str]
    reward: Reward
    verification_type: "VerificationType | str | None"
    verification_params: VerificationParams
    deadline: Optional[int]
    status: "MissionStatus | str | None"
    submissions: List[Submission]
    resolution: Optional[Resolution]
    creator_agent_id: Optional[str]
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Any) -> "Mission":
        data = _as_mapping(data)
        mission_id = data.get("id")
        if mission_id is None:
            raise ValueError("mission payload is missing required field 'id'")

        deadline_raw = data.get("deadline")
        try:
            deadline = int(deadline_raw) if deadline_raw is not None else None
        except (TypeError, ValueError):
            deadline = None

        submissions_raw = data.get("submissions") or []
        submissions = [
            Submission.from_dict(item)
            for item in submissions_raw
            if isinstance(item, Mapping)
        ]

        return cls(
            id=str(mission_id),
            title=data.get("title"),
            description=data.get("description"),
            reward=Reward.from_dict(data.get("reward")),
            verification_type=VerificationType.coerce(data.get("verification_type")),
            verification_params=VerificationParams.from_dict(data.get("verification_params")),
            deadline=deadline,
            status=MissionStatus.coerce(data.get("status")),
            submissions=submissions,
            resolution=Resolution.from_dict(data.get("resolution")),
            creator_agent_id=data.get("creator_agent_id"),
            raw=data,
        )

    @property
    def deadline_datetime(self) -> Optional[datetime]:
        """The mission deadline as a timezone-aware UTC datetime."""
        if self.deadline is None:
            return None
        return datetime.fromtimestamp(self.deadline, tz=timezone.utc)

    @property
    def is_open(self) -> bool:
        """True when the mission still accepts submissions.

        Uses the explicit ``status`` field when present; otherwise falls back to
        comparing the deadline against the current time.
        """
        if self.status is not None:
            return self.status == MissionStatus.OPEN
        if self.deadline is None:
            return True
        return self.deadline > _utcnow_ts()

    def seconds_remaining(self, *, now: Optional[float] = None) -> Optional[float]:
        """Seconds until the deadline (negative if already past, ``None`` if no deadline)."""
        if self.deadline is None:
            return None
        reference = now if now is not None else _utcnow_ts()
        return self.deadline - reference


@dataclass(frozen=True)
class Stats:
    """Aggregate protocol statistics from ``GET /api/stats``."""

    resolved: int
    open: int
    lifetime_reward_aigen_paid: float
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Any) -> "Stats":
        data = _as_mapping(data)

        def _int(key: str) -> int:
            try:
                return int(data.get(key, 0) or 0)
            except (TypeError, ValueError):
                return 0

        try:
            paid = float(data.get("lifetime_reward_aigen_paid", 0) or 0)
        except (TypeError, ValueError):
            paid = 0.0

        return cls(
            resolved=_int("resolved"),
            open=_int("open"),
            lifetime_reward_aigen_paid=paid,
            raw=data,
        )


def _utcnow_ts() -> float:
    return datetime.now(tz=timezone.utc).timestamp()


def parse_missions(payload: Any) -> List[Mission]:
    """Parse a ``GET /api/missions`` array (tolerating an enveloped form)."""
    if isinstance(payload, Mapping):
        # Some deployments wrap the array as {"missions": [...]}.
        payload = payload.get("missions", payload.get("data", []))
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        return []
    out: List[Mission] = []
    for item in payload:
        if isinstance(item, Mapping):
            out.append(Mission.from_dict(item))
    return out
