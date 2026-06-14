"""Lightweight typed views over OABP/A2A JSON payloads.

These dataclasses are convenience wrappers: they parse the JSON the server
returns into attribute-accessible objects while *retaining* the original
``raw`` mapping so no server field is ever lost. They intentionally do not
enforce a rigid schema (the protocol evolves), they just surface the common
fields described in the OABP API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional

__all__ = [
    "Reward",
    "Mission",
    "Submission",
    "Stats",
    "Task",
    "Message",
    "TextPart",
]


@dataclass(frozen=True)
class Reward:
    amount: float
    currency: str
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_json(cls, data: Optional[Mapping[str, Any]]) -> "Reward":
        data = data or {}
        return cls(
            amount=_as_float(data.get("amount", 0)),
            currency=str(data.get("currency", "AIGEN")),
            raw=data,
        )


@dataclass(frozen=True)
class Submission:
    submitter_agent_id: Optional[str]
    proof: Optional[str]
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "Submission":
        return cls(
            submitter_agent_id=data.get("submitter_agent_id") or data.get("agent_id"),
            proof=data.get("proof"),
            raw=data,
        )


@dataclass(frozen=True)
class Mission:
    id: str
    title: Optional[str]
    description: Optional[str]
    reward: Reward
    verification_type: Optional[str]
    verification_params: Mapping[str, Any]
    deadline: Optional[int]
    status: Optional[str]
    submissions: List[Submission]
    resolution: Optional[Mapping[str, Any]]
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "Mission":
        return cls(
            id=str(data.get("id")),
            title=data.get("title"),
            description=data.get("description"),
            reward=Reward.from_json(data.get("reward")),
            verification_type=data.get("verification_type"),
            verification_params=data.get("verification_params") or {},
            deadline=_as_optional_int(data.get("deadline")),
            status=data.get("status"),
            submissions=[
                Submission.from_json(s) for s in (data.get("submissions") or [])
            ],
            resolution=data.get("resolution"),
            raw=data,
        )

    @property
    def regex(self) -> Optional[str]:
        """The ``first_valid_match`` regex, if this mission uses one."""
        return self.verification_params.get("regex")

    @property
    def oracle_description(self) -> Optional[str]:
        return self.verification_params.get("oracle_description")


@dataclass(frozen=True)
class Stats:
    resolved: int
    open: int
    lifetime_reward_aigen_paid: float
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "Stats":
        return cls(
            resolved=_as_optional_int(data.get("resolved")) or 0,
            open=_as_optional_int(data.get("open")) or 0,
            lifetime_reward_aigen_paid=_as_float(
                data.get("lifetime_reward_aigen_paid", 0)
            ),
            raw=data,
        )


@dataclass(frozen=True)
class TextPart:
    """An A2A message part carrying text."""

    text: str

    def to_json(self) -> Mapping[str, Any]:
        # A2A message parts are typed; "text" is the universally supported kind.
        return {"kind": "text", "text": self.text}


@dataclass(frozen=True)
class Message:
    """An A2A message (a turn in a task)."""

    role: Optional[str]
    parts: List[Mapping[str, Any]]
    message_id: Optional[str]
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "Message":
        return cls(
            role=data.get("role"),
            parts=list(data.get("parts") or []),
            message_id=data.get("messageId") or data.get("message_id"),
            raw=data,
        )

    @property
    def text(self) -> str:
        """Concatenate the text of every text part (handy for simple replies)."""
        chunks = []
        for part in self.parts:
            if part.get("kind") == "text" or "text" in part:
                chunks.append(str(part.get("text", "")))
        return "".join(chunks)


@dataclass(frozen=True)
class Task:
    """An A2A task as returned by ``message/send``, ``tasks/get`` etc."""

    id: Optional[str]
    context_id: Optional[str]
    status_state: Optional[str]
    history: List[Message]
    artifacts: List[Mapping[str, Any]]
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "Task":
        status = data.get("status") or {}
        if isinstance(status, str):
            status_state = status
        else:
            status_state = status.get("state")
        return cls(
            id=data.get("id"),
            context_id=data.get("contextId") or data.get("context_id"),
            status_state=status_state,
            history=[Message.from_json(m) for m in (data.get("history") or [])],
            artifacts=list(data.get("artifacts") or []),
            raw=data,
        )


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
