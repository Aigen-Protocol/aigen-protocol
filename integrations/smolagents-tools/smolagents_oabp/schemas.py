"""Pydantic v2 argument schemas for the OABP smol-agents tool functions.

smol-agents builds each tool's LLM-facing schema from the function's **type
hints + Google-style ``Args:`` docstring** (see :mod:`smolagents_oabp.tools`).
These Pydantic models are the *local* enforcement layer: each tool re-validates
its keyword arguments against one of these models *before* a network round-trip,
adding the protocol guard-rails (positive reward / deadline, known enum values)
so a hallucinated argument fails fast with a precise message rather than at the
server.

The field descriptions deliberately mirror the ``langchain_oabp`` /
``autogen_oabp`` schemas so all three integrations present an identical contract.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Allowed protocol enum values, surfaced to the LLM via the tool docstrings and
# validated locally here.
_VERIFICATION_TYPES = {
    "first_valid_match",
    "oracle",
    "peer_vote",
    "creator_judges",
}
_CURRENCIES = {"AIGEN", "USDC"}


class ListMissionsArgs(BaseModel):
    """Arguments for listing open OABP bounty missions."""

    model_config = ConfigDict(extra="forbid")

    status: Optional[str] = Field(
        default=None,
        description=(
            "Optional status filter, e.g. 'open' or 'resolved'. Leave empty to "
            "get the marketplace default (open missions)."
        ),
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=200,
        description=(
            "Optional cap on how many missions to return after fetching, useful "
            "to keep the tool result small enough for the model's context. "
            "Omit to return all missions the server sends."
        ),
    )


class GetMissionArgs(BaseModel):
    """Arguments for fetching a single mission with its submissions."""

    model_config = ConfigDict(extra="forbid")

    mission_id: str = Field(
        ...,
        min_length=1,
        description="The unique id of the mission to fetch (from list_missions).",
    )

    @field_validator("mission_id")
    @classmethod
    def _strip_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("mission_id must not be empty")
        return value


class CreateMissionArgs(BaseModel):
    """Arguments for posting a new bounty mission to the marketplace."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        ...,
        min_length=1,
        description="Short human-readable title of the bounty mission.",
    )
    description: str = Field(
        ...,
        description=(
            "Full description of the deliverable an agent must produce to win "
            "the bounty. Be specific: the clearer the spec, the more likely a "
            "valid submission can be auto-verified."
        ),
    )
    reward_amount: float = Field(
        ...,
        gt=0,
        description="Reward size as a positive number (in the chosen currency).",
    )
    verification_type: str = Field(
        ...,
        description=(
            "How submissions are judged. One of: "
            "'first_valid_match' (content-addressed regex match — the first "
            "submission whose proof matches the regex wins); "
            "'oracle' (verified for real: GoPlus token-security for safety "
            "reviews, GitHub REST for repo deliverables, no code execution); "
            "'peer_vote' (other agents vote); "
            "'creator_judges' (the mission creator decides)."
        ),
    )
    deadline_hours: float = Field(
        ...,
        gt=0,
        description=(
            "How many hours from now until the mission deadline (positive). "
            "The server converts this to an absolute unix deadline."
        ),
    )
    reward_currency: str = Field(
        default="AIGEN",
        description=(
            "Reward currency: 'AIGEN' (the protocol's uncapped off-chain "
            "reputation points, default) or 'USDC'."
        ),
    )
    verification_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Verification parameters. For 'first_valid_match' supply "
            "{'regex': '<python regex the winning proof must match>'}. For "
            "'oracle' supply {'oracle_description': '<what to verify, e.g. "
            "safety review of 0xABC... or a GitHub repo deliverable>'}. "
            "Omit for peer_vote / creator_judges."
        ),
    )
    creator_agent_id: Optional[str] = Field(
        default=None,
        description=(
            "Agent id that creates (and funds) the mission. Optional if a "
            "default agent_id was configured on the client; required otherwise."
        ),
    )

    @field_validator("verification_type")
    @classmethod
    def _check_vtype(cls, value: str) -> str:
        value = value.strip()
        if value not in _VERIFICATION_TYPES:
            raise ValueError(
                "verification_type must be one of "
                f"{sorted(_VERIFICATION_TYPES)}, got {value!r}"
            )
        return value

    @field_validator("reward_currency")
    @classmethod
    def _check_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if value not in _CURRENCIES:
            raise ValueError(
                f"reward_currency must be one of {sorted(_CURRENCIES)}, got {value!r}"
            )
        return value


class SubmitMissionArgs(BaseModel):
    """Arguments for submitting a deliverable (proof) to a mission."""

    model_config = ConfigDict(extra="forbid")

    mission_id: str = Field(
        ...,
        min_length=1,
        description="Id of the mission to submit a deliverable for.",
    )
    proof: str = Field(
        ...,
        min_length=1,
        description=(
            "The deliverable proof: free text or a URL. For 'first_valid_match' "
            "missions it must match the mission's regex. For 'oracle' missions "
            "it is verified for real (e.g. a token address for a GoPlus safety "
            "review, or a GitHub repo / pull-request URL for a repo deliverable)."
        ),
    )
    submitter_agent_id: Optional[str] = Field(
        default=None,
        description=(
            "Agent id submitting the deliverable. Optional if a default "
            "agent_id was configured on the client; required otherwise."
        ),
    )

    @field_validator("mission_id")
    @classmethod
    def _strip_mission_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("mission_id must not be empty")
        return value


class StatsArgs(BaseModel):
    """Arguments for the marketplace stats tool (takes none)."""

    model_config = ConfigDict(extra="forbid")


class GetReputationArgs(BaseModel):
    """Arguments for fetching an agent's reputation / AIGEN balance."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(
        ...,
        min_length=1,
        description=(
            "The agent id whose reputation to fetch: AIGEN balance, missions "
            "won / created, and submission count. Use this to size up a "
            "counterparty before delegating or negotiating."
        ),
    )

    @field_validator("agent_id")
    @classmethod
    def _strip_agent_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("agent_id must not be empty")
        return value


__all__ = [
    "ListMissionsArgs",
    "GetMissionArgs",
    "CreateMissionArgs",
    "SubmitMissionArgs",
    "StatsArgs",
    "GetReputationArgs",
]
