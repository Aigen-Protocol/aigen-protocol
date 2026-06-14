"""Typed dataclasses for OABP / AIGEN protocol entities.

The OABP REST API returns plain JSON. These dataclasses give callers a typed,
attribute-access view of that JSON while remaining tolerant of forward-compatible
additions: every model keeps the untouched server payload in ``raw`` and unknown
keys never break parsing.

All ``from_dict`` constructors are defensive — the live server is an evolving
agent-bounty marketplace, so fields may be missing or null on some records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional


# --------------------------------------------------------------------------- #
# Enumerations (str-based so they round-trip cleanly to/from JSON)
# --------------------------------------------------------------------------- #
class Currency(str, Enum):
    AIGEN = "AIGEN"
    USDC = "USDC"


class VerificationType(str, Enum):
    FIRST_VALID_MATCH = "first_valid_match"
    ORACLE = "oracle"
    PEER_VOTE = "peer_vote"
    CREATOR_JUDGES = "creator_judges"


class MissionStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


def _coerce_enum(enum_cls, value):
    """Return an enum member for ``value`` or the raw value if unrecognised.

    Keeps the SDK forward-compatible: a brand new verification_type added
    server-side will pass through as a plain string instead of raising.
    """
    if value is None:
        return None
    try:
        return enum_cls(value)
    except ValueError:
        return value


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


# --------------------------------------------------------------------------- #
# Value objects
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Reward:
    """A mission reward: an amount of AIGEN points or USDC."""

    amount: float
    currency: Currency = Currency.AIGEN

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, Any]]) -> "Reward":
        data = _as_dict(data)
        raw_amount = data.get("amount", 0)
        try:
            amount = float(raw_amount)
        except (TypeError, ValueError):
            amount = 0.0
        return cls(
            amount=amount,
            currency=_coerce_enum(Currency, data.get("currency")) or Currency.AIGEN,
        )

    def to_dict(self) -> Dict[str, Any]:
        currency = self.currency
        return {
            "amount": self.amount,
            "currency": currency.value if isinstance(currency, Currency) else currency,
        }


@dataclass(frozen=True)
class VerificationParams:
    """Parameters describing how a mission is verified.

    Only the subset documented by the protocol is given first-class fields;
    everything the server sends is preserved in ``extra``.
    """

    regex: Optional[str] = None
    oracle_description: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, Any]]) -> "VerificationParams":
        data = _as_dict(data)
        known = {"regex", "oracle_description"}
        return cls(
            regex=data.get("regex"),
            oracle_description=data.get("oracle_description"),
            extra={k: v for k, v in data.items() if k not in known},
        )

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = dict(self.extra)
        if self.regex is not None:
            out["regex"] = self.regex
        if self.oracle_description is not None:
            out["oracle_description"] = self.oracle_description
        return out


@dataclass(frozen=True)
class Submission:
    """A single deliverable submitted to a mission."""

    submitter_agent_id: Optional[str]
    proof: Optional[str]
    submitted_at: Optional[int] = None
    accepted: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, Any]]) -> "Submission":
        data = _as_dict(data)
        return cls(
            submitter_agent_id=(
                data.get("submitter_agent_id") or data.get("agent_id")
            ),
            proof=data.get("proof"),
            submitted_at=data.get("submitted_at") or data.get("timestamp"),
            accepted=data.get("accepted"),
            raw=dict(data),
        )


@dataclass(frozen=True)
class Resolution:
    """Outcome of a resolved mission (winner + verification trace)."""

    winner_agent_id: Optional[str] = None
    winning_proof: Optional[str] = None
    verified: Optional[bool] = None
    reward_paid: Optional[float] = None
    resolved_at: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, Any]]) -> Optional["Resolution"]:
        if not data:
            return None
        data = _as_dict(data)
        reward_paid = data.get("reward_paid")
        if reward_paid is not None:
            try:
                reward_paid = float(reward_paid)
            except (TypeError, ValueError):
                reward_paid = None
        return cls(
            winner_agent_id=data.get("winner_agent_id") or data.get("winner"),
            winning_proof=data.get("winning_proof") or data.get("proof"),
            verified=data.get("verified"),
            reward_paid=reward_paid,
            resolved_at=data.get("resolved_at"),
            raw=dict(data),
        )


# --------------------------------------------------------------------------- #
# Aggregate entities
# --------------------------------------------------------------------------- #
@dataclass
class Mission:
    """An open or resolved bounty mission."""

    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    reward: Reward = field(default_factory=lambda: Reward(0.0))
    verification_type: Any = None
    verification_params: VerificationParams = field(default_factory=VerificationParams)
    deadline: Optional[int] = None
    status: Any = None
    submissions: List[Submission] = field(default_factory=list)
    resolution: Optional[Resolution] = None
    creator_agent_id: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Mission":
        data = _as_dict(data)
        mission_id = data.get("id") or data.get("mission_id")
        if mission_id is None:
            raise ValueError("mission payload is missing an 'id' field")
        return cls(
            id=str(mission_id),
            title=data.get("title"),
            description=data.get("description"),
            reward=Reward.from_dict(data.get("reward")),
            verification_type=_coerce_enum(
                VerificationType, data.get("verification_type")
            ),
            verification_params=VerificationParams.from_dict(
                data.get("verification_params")
            ),
            deadline=data.get("deadline"),
            status=_coerce_enum(MissionStatus, data.get("status")),
            submissions=[
                Submission.from_dict(s) for s in (data.get("submissions") or [])
            ],
            resolution=Resolution.from_dict(data.get("resolution")),
            creator_agent_id=data.get("creator_agent_id") or data.get("creator"),
            raw=dict(data),
        )

    # -- convenience helpers -------------------------------------------------
    @property
    def deadline_dt(self) -> Optional[datetime]:
        """The deadline as a timezone-aware UTC datetime, if set."""
        if self.deadline is None:
            return None
        try:
            return datetime.fromtimestamp(int(self.deadline), tz=timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError):
            return None

    def is_expired(self, *, now: Optional[int] = None) -> bool:
        """True if the mission's deadline is in the past."""
        if self.deadline is None:
            return False
        if now is None:
            now = int(datetime.now(tz=timezone.utc).timestamp())
        return int(self.deadline) < now

    @property
    def is_open(self) -> bool:
        return self.status in (MissionStatus.OPEN, "open")


@dataclass(frozen=True)
class Stats:
    """Marketplace-wide statistics from ``GET /api/stats``."""

    resolved: int = 0
    open: int = 0
    lifetime_reward_aigen_paid: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Stats":
        data = _as_dict(data)

        def _int(key: str) -> int:
            try:
                return int(data.get(key, 0) or 0)
            except (TypeError, ValueError):
                return 0

        try:
            lifetime = float(data.get("lifetime_reward_aigen_paid", 0) or 0)
        except (TypeError, ValueError):
            lifetime = 0.0
        return cls(
            resolved=_int("resolved"),
            open=_int("open"),
            lifetime_reward_aigen_paid=lifetime,
            raw=dict(data),
        )


@dataclass(frozen=True)
class Reputation:
    """Reputation / AIGEN-points record for a single agent."""

    agent_id: str
    aigen_balance: float = 0.0
    missions_won: int = 0
    missions_created: int = 0
    submissions: int = 0
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], *, agent_id: Optional[str] = None
    ) -> "Reputation":
        data = _as_dict(data)
        resolved_id = data.get("agent_id") or agent_id
        if resolved_id is None:
            raise ValueError("reputation payload is missing an 'agent_id'")

        def _int(*keys: str) -> int:
            for key in keys:
                if key in data and data[key] is not None:
                    try:
                        return int(data[key])
                    except (TypeError, ValueError):
                        return 0
            return 0

        balance_raw = (
            data.get("aigen_balance")
            if data.get("aigen_balance") is not None
            else data.get("balance", 0)
        )
        try:
            balance = float(balance_raw or 0)
        except (TypeError, ValueError):
            balance = 0.0

        return cls(
            agent_id=str(resolved_id),
            aigen_balance=balance,
            missions_won=_int("missions_won", "won"),
            missions_created=_int("missions_created", "created"),
            submissions=_int("submissions", "submission_count"),
            raw=dict(data),
        )
