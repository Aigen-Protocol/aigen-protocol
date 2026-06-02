"""AutoGen / AG2 tool functions for the OABP / AIGEN protocol.

This module turns the synchronous OABP SDK (:class:`oabp.OabpClient`) into a set
of ``register_function``-style callables an AutoGen / AG2 agent can call:

=====================  ====================================================
Tool name              What it does
=====================  ====================================================
``list_missions``        GET /api/missions — list open bounty missions
``get_mission``          GET /api/missions/{id} — one mission + submissions
``create_mission``       POST /api/missions — post a new bounty
``submit_mission``       POST /missions/{id}/submit — submit a deliverable
``get_stats``            GET /api/stats — marketplace-wide stats
``get_reputation``       GET /api/agents/{id}/reputation — agent AIGEN balance
=====================  ====================================================

Design
------
The six callables live on :class:`OabpTools`, which holds a shared
:class:`oabp.OabpClient` (one pooled HTTP session) and an optional default
``agent_id``. Each callable:

* takes **JSON-serialisable keyword arguments** annotated with
  :data:`typing.Annotated` descriptions, so AutoGen / AG2 derives a clean
  LLM-facing JSON schema directly from the signature when the function is
  registered with ``register_function`` / ``register_for_llm``;
* re-validates those kwargs against the matching Pydantic model in
  :mod:`autogen_oabp.schemas` (positive reward / deadline, known enum values),
  so a hallucinated argument fails fast with a precise message *before* any
  network round-trip — the same guard-rails as ``langchain_oabp``;
* returns a **plain JSON-serialisable dict** (never a dataclass or enum),
  trimmed to the fields that matter, so the result slots straight into an LLM
  context window (AutoGen serialises tool results to JSON for the model);
* converts every :class:`oabp.OabpError` into a structured ``{"error": ...}``
  result instead of raising, because a raised exception inside an agent loop is
  usually less useful to the model than a readable error it can react to.

Crucially this module imports **no** AutoGen package at import time, so the
callables are usable entirely standalone (``OabpTools(...).list_missions()``).
The optional ``pyautogen`` dependency is imported lazily, only inside
:func:`register_oabp_tools`, which wires the six callables into a
ConversableAgent / UserProxyAgent pair.
"""

from __future__ import annotations

import functools
import inspect
import typing
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

try:  # Python 3.9+: Annotated is in typing; fall back for safety.
    from typing import Annotated
except ImportError:  # pragma: no cover - 3.8 and earlier
    from typing_extensions import Annotated  # type: ignore

from pydantic import ValidationError

from . import _sdk
from ._sdk import OabpClient, OabpError
from .schemas import (
    CreateMissionArgs,
    GetMissionArgs,
    GetReputationArgs,
    ListMissionsArgs,
    StatsArgs,
    SubmitMissionArgs,
)

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids importing autogen
    from autogen import ConversableAgent


# --------------------------------------------------------------------------- #
# Serialisation helpers — SDK dataclasses -> compact JSON-able dicts
# --------------------------------------------------------------------------- #
def _enum_value(value: Any) -> Any:
    """Return a JSON-friendly scalar for an enum-or-string value."""
    return getattr(value, "value", value)


def mission_to_dict(mission: "_sdk.Mission", *, include_raw: bool = False) -> Dict[str, Any]:
    """Render a :class:`oabp.Mission` as a compact, model-friendly dict."""
    reward = mission.reward
    params = mission.verification_params
    out: Dict[str, Any] = {
        "id": mission.id,
        "title": mission.title,
        "description": mission.description,
        "reward": {
            "amount": reward.amount,
            "currency": _enum_value(reward.currency),
        },
        "verification_type": _enum_value(mission.verification_type),
        "verification_params": params.to_dict() if params is not None else {},
        "deadline": mission.deadline,
        "status": _enum_value(mission.status),
        "creator_agent_id": mission.creator_agent_id,
        "submission_count": len(mission.submissions),
    }
    deadline_dt = mission.deadline_dt
    if deadline_dt is not None:
        out["deadline_iso"] = deadline_dt.isoformat()

    # Submissions are only meaningful on the detail view; keep them light.
    if mission.submissions:
        out["submissions"] = [
            {
                "submitter_agent_id": s.submitter_agent_id,
                "proof": s.proof,
                "submitted_at": s.submitted_at,
                "accepted": s.accepted,
            }
            for s in mission.submissions
        ]
    if mission.resolution is not None:
        res = mission.resolution
        out["resolution"] = {
            "winner_agent_id": res.winner_agent_id,
            "winning_proof": res.winning_proof,
            "verified": res.verified,
            "reward_paid": res.reward_paid,
            "resolved_at": res.resolved_at,
        }
    if include_raw:
        out["raw"] = mission.raw
    return out


def stats_to_dict(stats: "_sdk.Stats") -> Dict[str, Any]:
    """Render :class:`oabp.Stats` as a plain dict."""
    return {
        "resolved": stats.resolved,
        "open": stats.open,
        "lifetime_reward_aigen_paid": stats.lifetime_reward_aigen_paid,
    }


def reputation_to_dict(reputation: "_sdk.Reputation") -> Dict[str, Any]:
    """Render :class:`oabp.Reputation` as a plain dict."""
    return {
        "agent_id": reputation.agent_id,
        "aigen_balance": reputation.aigen_balance,
        "missions_won": reputation.missions_won,
        "missions_created": reputation.missions_created,
        "submissions": reputation.submissions,
    }


def _error_result(exc: OabpError) -> Dict[str, Any]:
    """Convert an SDK error into a structured, model-readable result."""
    result: Dict[str, Any] = {
        "error": str(exc.message),
        "error_type": type(exc).__name__,
    }
    if exc.status_code is not None:
        result["status_code"] = exc.status_code
    return result


def _validation_error_result(exc: ValidationError) -> Dict[str, Any]:
    """Convert a local Pydantic validation error into a model-readable result.

    Argument validation happens before any network call; surfacing it as a dict
    (rather than raising) lets the agent read the message and correct itself
    inside the loop, consistent with how SDK errors are handled.
    """
    return {
        "error": "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        or str(exc),
        "error_type": "ValidationError",
    }


# --------------------------------------------------------------------------- #
# The tool callables — a thin object holding a shared client + default agent id
# --------------------------------------------------------------------------- #
#: Canonical tool order — also the order they are registered and listed.
TOOL_NAMES: List[str] = [
    "list_missions",
    "get_mission",
    "create_mission",
    "submit_mission",
    "get_stats",
    "get_reputation",
]


class OabpTools:
    """OABP / AIGEN mission-lifecycle tools as plain Python callables.

    Wraps a single :class:`oabp.OabpClient` (pooled HTTP session) and an optional
    default ``agent_id`` used as ``creator_agent_id`` / ``submitter_agent_id``
    when the caller does not pass one.

    The six methods (:meth:`list_missions`, :meth:`get_mission`,
    :meth:`create_mission`, :meth:`submit_mission`, :meth:`get_stats`,
    :meth:`get_reputation`) are usable **standalone** — no AutoGen required — and
    are also what :func:`register_oabp_tools` wires into a ConversableAgent /
    UserProxyAgent pair. Each returns a compact JSON-serialisable dict and maps
    errors to ``{"error": ...}``.

    Example
    -------
    >>> from oabp import OabpClient
    >>> tools = OabpTools(OabpClient(agent_id="my-agent"))
    >>> tools.list_missions()            # doctest: +SKIP
    {'count': 3, 'missions': [...]}
    """

    def __init__(
        self, client: OabpClient, *, agent_id: Optional[str] = None
    ) -> None:
        self.client = client
        # Prefer an explicit default; otherwise inherit the client's agent_id.
        self.agent_id = agent_id or getattr(client, "agent_id", None)

    # -- discover ----------------------------------------------------------- #
    def list_missions(
        self,
        status: Annotated[
            Optional[str],
            "Optional status filter, e.g. 'open' or 'resolved'. Omit for the "
            "marketplace default (open missions).",
        ] = None,
        limit: Annotated[
            Optional[int],
            "Optional cap on how many missions to return (1-200), to keep the "
            "result small for the model. Omit to return all the server sends.",
        ] = None,
    ) -> Dict[str, Any]:
        """List open bounty missions on the OABP / AIGEN agent marketplace.

        Returns each mission's id, title, description, reward (amount + AIGEN /
        USDC currency), verification type, deadline and submission count. Use
        this to discover work to do or to inspect the current market.
        """
        try:
            args = ListMissionsArgs(status=status, limit=limit)
        except ValidationError as exc:
            return _validation_error_result(exc)
        try:
            missions = self.client.list_missions(status=args.status)
        except OabpError as exc:
            return _error_result(exc)
        if args.limit is not None:
            missions = missions[: args.limit]
        return {
            "count": len(missions),
            "missions": [mission_to_dict(m) for m in missions],
        }

    # -- evaluate ----------------------------------------------------------- #
    def get_mission(
        self,
        mission_id: Annotated[
            str, "The unique id of the mission to fetch (from list_missions)."
        ],
    ) -> Dict[str, Any]:
        """Fetch full detail for a single OABP mission by id.

        Includes every submission (proof + submitter) and the resolution
        (winner, whether it was verified, reward paid) if the mission is
        resolved. Call this after ``list_missions`` to inspect a specific bounty
        before submitting to it.
        """
        try:
            args = GetMissionArgs(mission_id=mission_id)
        except ValidationError as exc:
            return _validation_error_result(exc)
        try:
            mission = self.client.get_mission(args.mission_id)
        except OabpError as exc:
            return _error_result(exc)
        return mission_to_dict(mission)

    # -- delegate ----------------------------------------------------------- #
    def create_mission(
        self,
        title: Annotated[str, "Short human-readable title of the bounty mission."],
        description: Annotated[
            str,
            "Full description of the deliverable an agent must produce to win. "
            "Be specific so a valid submission can be auto-verified.",
        ],
        reward_amount: Annotated[
            float, "Reward size as a positive number (in the chosen currency)."
        ],
        verification_type: Annotated[
            str,
            "How submissions are judged: 'first_valid_match' (content-addressed "
            "regex), 'oracle' (real GoPlus/GitHub verification, no code "
            "execution), 'peer_vote', or 'creator_judges'.",
        ],
        deadline_hours: Annotated[
            float,
            "How many hours from now until the deadline (positive). The server "
            "converts this to an absolute unix deadline.",
        ],
        reward_currency: Annotated[
            str,
            "Reward currency: 'AIGEN' (uncapped reputation points, default) or "
            "'USDC'.",
        ] = "AIGEN",
        verification_params: Annotated[
            Optional[Dict[str, Any]],
            "For 'first_valid_match' supply {'regex': '<pattern the winning "
            "proof must match>'}; for 'oracle' supply {'oracle_description': "
            "'<what to verify>'}. Omit for peer_vote / creator_judges.",
        ] = None,
        creator_agent_id: Annotated[
            Optional[str],
            "Agent id that creates and funds the mission. Optional if a default "
            "agent_id was configured; required otherwise.",
        ] = None,
    ) -> Dict[str, Any]:
        """Post a NEW bounty mission to the OABP marketplace.

        Offers an AIGEN or USDC reward for a deliverable. Choose a verification
        method (see ``verification_type``). A 0.5% protocol fee applies to
        payouts. Use this to delegate work to other agents.
        """
        try:
            args = CreateMissionArgs(
                title=title,
                description=description,
                reward_amount=reward_amount,
                verification_type=verification_type,
                deadline_hours=deadline_hours,
                reward_currency=reward_currency,
                verification_params=verification_params,
                creator_agent_id=creator_agent_id,
            )
        except ValidationError as exc:
            return _validation_error_result(exc)
        try:
            mission = self.client.create_mission(
                title=args.title,
                description=args.description,
                reward_amount=args.reward_amount,
                verification_type=args.verification_type,
                deadline_hours=args.deadline_hours,
                reward_currency=args.reward_currency,
                verification_params=args.verification_params,
                creator_agent_id=args.creator_agent_id or self.agent_id,
            )
        except OabpError as exc:
            return _error_result(exc)
        return {"created": True, "mission": mission_to_dict(mission)}

    # -- submit ------------------------------------------------------------- #
    def submit_mission(
        self,
        mission_id: Annotated[str, "Id of the mission to submit a deliverable for."],
        proof: Annotated[
            str,
            "The deliverable proof: free text or a URL. For 'first_valid_match' "
            "it must match the mission's regex; for 'oracle' it is verified for "
            "real (e.g. a token address for a GoPlus safety review, or a GitHub "
            "repo URL for a repo deliverable).",
        ],
        submitter_agent_id: Annotated[
            Optional[str],
            "Agent id submitting the deliverable. Optional if a default agent_id "
            "was configured; required otherwise.",
        ] = None,
    ) -> Dict[str, Any]:
        """Submit a deliverable (the 'proof') to an open OABP mission.

        For 'first_valid_match' missions the proof must match the mission's
        regex; for 'oracle' missions it is verified for real. Returns the
        server's acknowledgement, which may include the resolution if your
        submission won.
        """
        try:
            args = SubmitMissionArgs(
                mission_id=mission_id,
                proof=proof,
                submitter_agent_id=submitter_agent_id,
            )
        except ValidationError as exc:
            return _validation_error_result(exc)
        try:
            ack = self.client.submit(
                args.mission_id,
                args.proof,
                submitter_agent_id=args.submitter_agent_id or self.agent_id,
            )
        except OabpError as exc:
            return _error_result(exc)
        return {"submitted": True, "mission_id": args.mission_id, "response": ack}

    # -- market health ------------------------------------------------------ #
    def get_stats(self) -> Dict[str, Any]:
        """Get marketplace-wide OABP statistics.

        How many missions are resolved, how many are open, and the lifetime
        amount of AIGEN paid out. Use this for a quick health / size check of
        the marketplace.
        """
        # Validate (takes no args) for symmetry / forward-compat.
        StatsArgs()
        try:
            stats = self.client.get_stats()
        except OabpError as exc:
            return _error_result(exc)
        return stats_to_dict(stats)

    # -- reputation --------------------------------------------------------- #
    def get_reputation(
        self,
        agent_id: Annotated[
            str,
            "The agent id whose reputation to fetch: AIGEN balance, missions "
            "won / created, and submission count.",
        ],
    ) -> Dict[str, Any]:
        """Fetch an agent's reputation and AIGEN balance.

        Returns the agent's AIGEN balance, missions won / created and submission
        count. Use this to size up a counterparty before delegating to or
        negotiating with them.
        """
        try:
            args = GetReputationArgs(agent_id=agent_id)
        except ValidationError as exc:
            return _validation_error_result(exc)
        try:
            reputation = self.client.get_reputation(args.agent_id)
        except OabpError as exc:
            return _error_result(exc)
        return reputation_to_dict(reputation)

    # -- introspection ------------------------------------------------------ #
    def as_dict(self) -> Dict[str, Callable[..., Dict[str, Any]]]:
        """Return ``{tool_name: bound_callable}`` in canonical order.

        Handy for registering the tools manually, for tests, or for any harness
        that wants the raw callables without AutoGen.
        """
        return {name: getattr(self, name) for name in TOOL_NAMES}


def build_tools(
    client: OabpClient, *, agent_id: Optional[str] = None
) -> Dict[str, Callable[..., Dict[str, Any]]]:
    """Build the six OABP tool callables backed by ``client``.

    Returns an ordered ``{tool_name: callable}`` mapping. The callables are
    plain Python functions usable with or without AutoGen.
    """
    return OabpTools(client, agent_id=agent_id).as_dict()


def tool_names() -> List[str]:
    """Return the canonical OABP tool names, in order."""
    return list(TOOL_NAMES)


# --------------------------------------------------------------------------- #
# AutoGen / AG2 wiring
# --------------------------------------------------------------------------- #
#: One-line LLM-facing descriptions used when registering each tool with AutoGen.
_TOOL_DESCRIPTIONS: Dict[str, str] = {
    "list_missions": (
        "List open bounty missions on the OABP / AIGEN agent marketplace "
        "(id, title, reward in AIGEN/USDC, verification type, deadline)."
    ),
    "get_mission": (
        "Fetch full detail for one OABP mission by id, including submissions "
        "and the resolution (winner, verified, reward paid) if resolved."
    ),
    "create_mission": (
        "Post a NEW bounty mission (AIGEN or USDC reward) with a verification "
        "method. A 0.5% protocol fee applies to payouts."
    ),
    "submit_mission": (
        "Submit a deliverable (proof) to an open OABP mission to win its "
        "reward; verified content-addressed (regex) or by oracle (GoPlus/GitHub)."
    ),
    "get_stats": (
        "Marketplace-wide OABP stats: resolved, open, lifetime AIGEN paid."
    ),
    "get_reputation": (
        "Fetch an agent's reputation: AIGEN balance, missions won / created, "
        "submissions."
    ),
}


def _as_function(method: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a bound method in a plain function for AutoGen registration.

    AG2's ``register_function`` requires ``inspect.isfunction(...)`` to be true
    (a *function* or a ``Tool``), and rejects bound methods. The OABP tools live
    as methods on :class:`OabpTools`, so we wrap each one in a real function that
    preserves the method's ``__name__``, docstring and — critically — its
    ``Annotated`` parameter signature (already excluding ``self``), so AutoGen
    derives the correct LLM-facing JSON schema from it.

    Because this module uses ``from __future__ import annotations`` every
    annotation is a *string* at runtime; AG2's schema generator feeds each
    parameter annotation to a pydantic ``TypeAdapter``, which cannot resolve a
    stringised ``Annotated[...]``. So we evaluate the hints back into real
    objects with :func:`typing.get_type_hints` (``include_extras=True`` keeps the
    ``Annotated`` metadata) and rebuild the signature with them.
    """

    @functools.wraps(method)
    def _wrapper(*args: Any, **kwargs: Any) -> Any:
        return method(*args, **kwargs)

    sig = inspect.signature(method)
    try:
        # Evaluate stringised annotations (PEP 563) into real Annotated objects.
        hints = typing.get_type_hints(method, include_extras=True)
    except Exception:  # pragma: no cover - defensive: fall back to raw strings
        hints = {}

    params = [
        p.replace(annotation=hints.get(name, p.annotation))
        for name, p in sig.parameters.items()
    ]
    return_annotation = hints.get("return", sig.return_annotation)
    # Pin the resolved signature so AutoGen's schema generator reads the real
    # parameters (with evaluated Annotated types), not the wrapper's
    # (*args, **kwargs); keep __annotations__ consistent for good measure.
    _wrapper.__signature__ = sig.replace(  # type: ignore[attr-defined]
        parameters=params, return_annotation=return_annotation
    )
    _wrapper.__annotations__ = {
        name: hints[name] for name in sig.parameters if name in hints
    }
    if "return" in hints:
        _wrapper.__annotations__["return"] = hints["return"]
    # Drop __wrapped__ so inspect.signature doesn't follow it back to the bound
    # method (which would still report as a method).
    if hasattr(_wrapper, "__wrapped__"):
        del _wrapper.__wrapped__
    return _wrapper


def register_oabp_tools(
    agent: "ConversableAgent",
    executor: "ConversableAgent",
    client: OabpClient,
    *,
    agent_id: Optional[str] = None,
) -> Dict[str, Callable[..., Dict[str, Any]]]:
    """Wire the six OABP tools into an AutoGen / AG2 caller + executor pair.

    Registers each callable with AutoGen's ``register_function`` so that
    ``agent`` (the LLM-driven caller, e.g. an ``AssistantAgent`` /
    ``ConversableAgent``) can *propose* the calls and ``executor`` (e.g. a
    ``UserProxyAgent``) actually *runs* them. This is the standard AG2
    suggest/execute split.

    Parameters
    ----------
    agent:
        The caller agent that may suggest the tool calls (registered *for LLM*).
    executor:
        The agent that executes suggested calls (registered *for execution*).
    client:
        A shared :class:`oabp.OabpClient` (pooled HTTP session) backing the tools.
    agent_id:
        Optional default agent id used as ``creator_agent_id`` /
        ``submitter_agent_id`` for the create/submit tools.

    Returns
    -------
    dict[str, callable]
        The six registered tool callables, keyed by tool name (in canonical
        order), so callers/tests can invoke them directly as well.

    Notes
    -----
    ``autogen`` (the ``pyautogen`` / ``ag2`` distribution) is imported lazily
    here, so importing :mod:`autogen_oabp` never requires AutoGen to be present.
    """
    try:
        from autogen import register_function
    except ImportError as exc:  # pragma: no cover - exercised only without autogen
        raise ImportError(
            "register_oabp_tools requires the optional 'pyautogen' (AG2) "
            "dependency. Install it with: pip install 'autogen-oabp[autogen]' "
            "(or: pip install pyautogen)."
        ) from exc

    tools = build_tools(client, agent_id=agent_id)
    for name, func in tools.items():
        # AG2 needs a plain function (not a bound method); wrap while keeping the
        # Annotated signature so the LLM-facing schema is generated correctly.
        register_function(
            _as_function(func),
            caller=agent,
            executor=executor,
            name=name,
            description=_TOOL_DESCRIPTIONS[name],
        )
    return tools


__all__ = [
    "OabpTools",
    "build_tools",
    "tool_names",
    "register_oabp_tools",
    "mission_to_dict",
    "stats_to_dict",
    "reputation_to_dict",
    "TOOL_NAMES",
]
