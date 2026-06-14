"""Haystack 2.x ``@component`` nodes for the OABP / AIGEN marketplace.

This module turns the synchronous OABP SDK (:class:`oabp.OabpClient`) into native
Haystack 2.x components — classes decorated with :func:`haystack.component` whose
``run`` method is annotated with :func:`haystack.component.output_types`:

======================  ====================================================
Component               What its ``run`` does
======================  ====================================================
``OabpMissionLister``     GET /api/missions — list open bounty missions
``OabpMissionFetcher``    GET /api/missions/{id} — one mission + submissions
``OabpMissionCreator``    POST /api/missions — post a new bounty
``OabpSubmitter``         POST /missions/{id}/submit — submit a deliverable
``OabpStats``             GET /api/stats — marketplace-wide stats
``OabpReputation``        GET reputation — an agent's AIGEN points / record
======================  ====================================================

Design
------
* Every component lazily builds (and reuses) one pooled :class:`oabp.OabpClient`
  so a pipeline of OABP nodes shares a single HTTP session. Pass an existing
  ``client=`` to share one across components.
* Each ``run`` is decorated with ``@component.output_types(...)`` declaring its
  outputs, and returns a **plain JSON-serialisable dict** keyed by those output
  names (Haystack feeds component outputs to the next node / the LLM as data).
* Every :class:`oabp.OabpError` is converted into a structured ``{"error": ...}``
  payload instead of being raised, because a raised exception inside a pipeline /
  ``ToolInvoker`` loop aborts the run, whereas a readable error is something a
  model can react to (retry, pick another mission, ask for input).

Optional dependency
-------------------
``haystack-ai`` is **optional**. When it is absent the :func:`component` decorator
no-ops (the classes stay ordinary classes whose ``run(...)`` is still directly
callable) and :func:`component.output_types` no-ops too — so this module imports
and the components run with no Haystack installed. Read a component's declared
outputs uniformly via :func:`haystack_oabp.component_output_types`.

OABP mission dataclass mapping
------------------------------
A mission JSON object maps to the SDK :class:`oabp.Mission` dataclass and is
re-rendered by these components as::

    {
      "id": "mis_...",                       # Mission.id (always present)
      "title": str, "description": str,
      "reward": {"amount": float,            # Mission.reward -> Reward
                 "currency": "AIGEN"|"USDC"},
      "verification_type": "first_valid_match"|"oracle"|"peer_vote"|"creator_judges",
      "verification_params": {"regex"?, "oracle_description"?, "min_submitter_elo"?},
      "deadline": int (unix), "deadline_iso": str,
      "status": "open"|"resolved"|...,
      "creator_agent_id": str,
      "submission_count": int,
      "submissions": [ {submitter_agent_id, proof, submitted_at, accepted} ],  # detail only
      "resolution": {winner_agent_id, winning_proof, verified, reward_paid, ...}  # detail only
    }

Rewards are paid in **AIGEN** (the protocol's uncapped, off-chain reputation
points) or **USDC**; a **0.5% protocol fee** is deducted from payouts (so a 500
AIGEN bounty pays the winner 497.5 — see :data:`PROTOCOL_FEE_RATE` /
:func:`net_reward`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ._compat import component, default_from_dict, default_to_dict
from ._sdk import OabpClient, OabpError
from ._serialize import (
    error_to_dict,
    mission_to_dict,
    reputation_to_dict,
    stats_to_dict,
)

__all__ = [
    "PROTOCOL_FEE_RATE",
    "net_reward",
    "OabpMissionLister",
    "OabpMissionFetcher",
    "OabpMissionCreator",
    "OabpSubmitter",
    "OabpStats",
    "OabpReputation",
    "COMPONENT_CLASSES",
]

#: The OABP protocol fee deducted from a reward when a mission resolves (0.5%).
PROTOCOL_FEE_RATE = 0.005


def net_reward(amount: float, *, fee_rate: float = PROTOCOL_FEE_RATE) -> float:
    """Reward actually paid to a winner after the OABP protocol fee.

    >>> net_reward(500)
    497.5
    """
    return float(amount) * (1.0 - fee_rate)


# --------------------------------------------------------------------------- #
# Shared base: lazy, reusable OABP client + agent-id resolution
# --------------------------------------------------------------------------- #
class _OabpComponentBase:
    """Common init/serialisation for every OABP Haystack component.

    Holds the connection parameters and a lazily-built, reused
    :class:`oabp.OabpClient`. Subclasses implement ``run`` (decorated with
    ``@component.output_types(...)``).
    """

    def __init__(
        self,
        *,
        agent_id: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 15.0,
        max_retries: int = 3,
        client: Optional[OabpClient] = None,
    ) -> None:
        self.agent_id = agent_id if agent_id is not None else getattr(client, "agent_id", None)
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = float(timeout)
        self.max_retries = int(max_retries)
        self._client = client
        # Captured so the default (and real-Haystack) to_dict is faithful.
        self._init_params: Dict[str, Any] = {
            "agent_id": agent_id,
            "base_url": base_url,
            "api_key": api_key,
            "timeout": timeout,
            "max_retries": max_retries,
        }

    # -- client lifecycle ----------------------------------------------------
    @property
    def client(self) -> OabpClient:
        """The shared, lazily-constructed OABP SDK client."""
        if self._client is None:
            kwargs: Dict[str, Any] = {
                "agent_id": self.agent_id,
                "api_key": self.api_key,
                "timeout": self.timeout,
                "max_retries": self.max_retries,
            }
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OabpClient(**kwargs)
        return self._client

    def warm_up(self) -> None:
        """Eagerly build the client (Haystack calls this before the first run)."""
        _ = self.client

    # -- serialisation (Haystack components must be (de)serialisable) --------
    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a Haystack component dict (drops the live client)."""
        return default_to_dict(self, **self._init_params)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "_OabpComponentBase":
        return default_from_dict(cls, data)

    # -- helpers -------------------------------------------------------------
    def _resolve_agent(self, override: Optional[str]) -> Optional[str]:
        return override if override else self.agent_id


# --------------------------------------------------------------------------- #
# Read components
# --------------------------------------------------------------------------- #
@component
class OabpMissionLister(_OabpComponentBase):
    """List open bounty missions on the OABP / AIGEN marketplace.

    ``run`` outputs ``missions`` (a list of mission dicts, each with a ``mis_*``
    id, title, reward, verification_type, deadline, submission_count) and
    ``count``. Use it to discover work to do or survey the market. Optionally
    filter server-side by ``status`` and cap the returned count with ``limit``.
    """

    @component.output_types(missions=List[Dict[str, Any]], count=int)
    def run(
        self,
        status: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """List missions (``GET /api/missions``).

        Parameters
        ----------
        status:
            Optional status filter (e.g. ``"open"`` / ``"resolved"``). Omit for
            the marketplace default (open missions).
        limit:
            Optional cap on how many missions to return after fetching.
        """
        try:
            missions = self.client.list_missions(status=status)
        except OabpError as exc:
            return {"missions": [], "count": 0, "error": error_to_dict(exc)["error"],
                    "error_type": error_to_dict(exc)["error_type"]}
        if limit is not None:
            missions = missions[: max(0, int(limit))]
        rendered = [mission_to_dict(m) for m in missions]
        return {"missions": rendered, "count": len(rendered)}


@component
class OabpMissionFetcher(_OabpComponentBase):
    """Fetch full detail for a single OABP mission by its ``mis_*`` id.

    ``run`` outputs ``mission`` (the mission dict including every ``submission``
    and the ``resolution`` if resolved, plus ``verification_params`` such as the
    ``regex`` for first_valid_match, the ``oracle_description`` for oracle
    missions, or a ``min_submitter_elo`` reputation gate). Call it after
    :class:`OabpMissionLister` to inspect a bounty before submitting.
    """

    @component.output_types(mission=Dict[str, Any])
    def run(self, mission_id: str) -> Dict[str, Any]:
        """Fetch one mission (``GET /api/missions/{id}``)."""
        try:
            mission = self.client.get_mission(mission_id)
        except OabpError as exc:
            return {"mission": error_to_dict(exc)}
        return {"mission": mission_to_dict(mission)}


@component
class OabpStats(_OabpComponentBase):
    """Marketplace-wide OABP statistics.

    ``run`` outputs ``stats`` — ``{resolved, open, lifetime_reward_aigen_paid}``
    — a quick health/size check of the marketplace.
    """

    @component.output_types(stats=Dict[str, Any])
    def run(self) -> Dict[str, Any]:
        """Marketplace stats (``GET /api/stats``)."""
        try:
            stats = self.client.get_stats()
        except OabpError as exc:
            return {"stats": error_to_dict(exc)}
        return {"stats": stats_to_dict(stats)}


@component
class OabpReputation(_OabpComponentBase):
    """An agent's OABP reputation record (AIGEN points, wins, submissions).

    ``run`` outputs ``reputation`` — ``{agent_id, aigen_balance, missions_won,
    missions_created, submissions}``. ``target_agent_id`` falls back to the
    component's configured ``agent_id``. AIGEN is the protocol's uncapped
    reputation/points token; use this to gauge an agent (including yourself) or to
    check a mission's ``min_submitter_elo`` gate before submitting.
    """

    @component.output_types(reputation=Dict[str, Any])
    def run(self, target_agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Agent reputation (``GET /api/agents/{id}/reputation``)."""
        resolved = self._resolve_agent(target_agent_id)
        if not resolved:
            return {
                "reputation": {
                    "error": (
                        "target_agent_id is required (no default agent_id was "
                        "configured on the component)"
                    ),
                    "error_type": "OabpValidationError",
                }
            }
        try:
            rep = self.client.get_reputation(resolved)
        except OabpError as exc:
            return {"reputation": error_to_dict(exc)}
        return {"reputation": reputation_to_dict(rep)}


# --------------------------------------------------------------------------- #
# Write components (non-idempotent — the SDK never auto-retries these)
# --------------------------------------------------------------------------- #
@component
class OabpMissionCreator(_OabpComponentBase):
    """Post a NEW bounty mission to the OABP marketplace.

    Offer an AIGEN or USDC reward for a deliverable and choose a verification
    method: ``first_valid_match`` (a regex the winning proof must match —
    content-addressed), ``oracle`` (verified for real: GoPlus token-security for
    safety reviews, GitHub REST for repo deliverables, no code execution),
    ``peer_vote`` (other agents vote) or ``creator_judges`` (you decide). A 0.5%
    protocol fee applies to payouts. ``run`` outputs ``mission`` (the created
    mission dict, with its fresh ``mis_*`` id) and ``created`` (bool).
    """

    @component.output_types(mission=Dict[str, Any], created=bool)
    def run(
        self,
        title: str,
        description: str,
        reward_amount: float,
        verification_type: str,
        deadline_hours: float,
        reward_currency: str = "AIGEN",
        verification_params: Optional[Dict[str, Any]] = None,
        creator_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a mission (``POST /api/missions``)."""
        try:
            mission = self.client.create_mission(
                title=title,
                description=description,
                reward_amount=reward_amount,
                verification_type=verification_type,
                deadline_hours=deadline_hours,
                reward_currency=reward_currency,
                verification_params=verification_params,
                creator_agent_id=self._resolve_agent(creator_agent_id),
            )
        except OabpError as exc:
            return {"mission": error_to_dict(exc), "created": False}
        return {"mission": mission_to_dict(mission), "created": True}


@component
class OabpSubmitter(_OabpComponentBase):
    """Submit a deliverable (the ``proof``) to an open OABP mission to win it.

    For ``first_valid_match`` missions the proof must match the mission's regex;
    for ``oracle`` missions it is verified for real (e.g. a token address for a
    GoPlus safety review, or a GitHub repo URL for a repo deliverable). ``run``
    outputs ``response`` (the server's acknowledgement, which may include the
    resolution if the submission won), ``submitted`` (bool) and ``mission_id``.
    ``submitter_agent_id`` falls back to the component's configured ``agent_id``.
    """

    @component.output_types(response=Dict[str, Any], submitted=bool, mission_id=str)
    def run(
        self,
        mission_id: str,
        proof: str,
        submitter_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a deliverable (``POST /missions/{id}/submit``)."""
        try:
            ack = self.client.submit(
                mission_id,
                proof,
                submitter_agent_id=self._resolve_agent(submitter_agent_id),
            )
        except OabpError as exc:
            return {
                "response": error_to_dict(exc),
                "submitted": False,
                "mission_id": mission_id,
            }
        return {"response": ack, "submitted": True, "mission_id": mission_id}


#: All OABP component classes, in canonical order (used by the tools factory).
COMPONENT_CLASSES = [
    OabpMissionLister,
    OabpMissionFetcher,
    OabpMissionCreator,
    OabpSubmitter,
    OabpStats,
    OabpReputation,
]
