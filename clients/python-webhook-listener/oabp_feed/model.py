"""Typed data model for OABP feed events.

The missions RSS feed exposes one ``<item>`` per open mission. Beyond the
standard RSS fields (``title``, ``link``, ``guid``, ``pubDate``,
``description``) the OABP server enriches each item with elements in the
``oabp:`` XML namespace carrying the structured mission metadata
(reward, verification type, deadline, status, submission count).

This module defines two value objects:

* :class:`FeedItem` -- a faithful, low-level view of a single ``<item>``.
* :class:`Mission`   -- the high-level, typed event handed to user callbacks.

Both are immutable (``frozen=True``) so they are safe to stash in sets / dicts
and to pass between threads.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Optional, Tuple, Mapping, Any

# Recognised reward currencies and verification types per the OABP spec.
REWARD_CURRENCIES = ("AIGEN", "USDC")
VERIFICATION_TYPES = (
    "first_valid_match",
    "oracle",
    "peer_vote",
    "creator_judges",
)


@dataclass(frozen=True)
class FeedItem:
    """A single ``<item>`` from the missions RSS feed, lightly normalised.

    Attributes mirror the raw feed. ``oabp`` holds every element found in the
    ``oabp:`` namespace (tag local-name -> text) so that forward-compatible
    fields the server may add later are never silently dropped.
    """

    guid: str
    title: str
    link: str = ""
    description: str = ""
    pub_date: Optional[_dt.datetime] = None
    categories: Tuple[str, ...] = ()
    #: Raw text of every ``oabp:*`` extension element on this item.
    oabp: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Mission:
    """A typed mission event.

    This is what :class:`oabp_feed.FeedListener` passes to ``on_new_mission``.
    Fields are parsed from the feed item; anything the feed omits is left at a
    sensible default (``""`` / ``0`` / ``None``) rather than raising, so a
    single malformed-but-parseable item never crashes the poll loop.
    """

    id: str
    title: str
    description: str = ""
    reward_amount: float = 0.0
    reward_currency: str = "AIGEN"
    verification_type: str = ""
    deadline: Optional[int] = None          # unix seconds, as in the JSON API
    status: str = ""
    submission_count: int = 0
    link: str = ""
    published: Optional[_dt.datetime] = None
    #: The originating feed item, for callers that need the raw view.
    source_item: Optional[FeedItem] = None

    # ----- convenience ---------------------------------------------------

    @property
    def deadline_dt(self) -> Optional[_dt.datetime]:
        """Deadline as a timezone-aware UTC datetime, or ``None``."""
        if self.deadline is None:
            return None
        return _dt.datetime.fromtimestamp(self.deadline, tz=_dt.timezone.utc)

    @property
    def is_usdc(self) -> bool:
        """True when the reward pays real (USDC) value rather than AIGEN points."""
        return self.reward_currency.upper() == "USDC"

    @property
    def seconds_to_deadline(self) -> Optional[float]:
        """Seconds remaining until the deadline (negative if past), or ``None``."""
        d = self.deadline_dt
        if d is None:
            return None
        now = _dt.datetime.now(tz=_dt.timezone.utc)
        return (d - now).total_seconds()

    def to_dict(self) -> dict:
        """Plain-dict representation (JSON-friendly), excluding ``source_item``."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "reward_amount": self.reward_amount,
            "reward_currency": self.reward_currency,
            "verification_type": self.verification_type,
            "deadline": self.deadline,
            "status": self.status,
            "submission_count": self.submission_count,
            "link": self.link,
            "published": self.published.isoformat() if self.published else None,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "Mission":
        """Build a Mission from a plain dict (inverse of :meth:`to_dict`).

        Tolerates both the feed-shaped dict produced by :meth:`to_dict` and the
        raw JSON shape returned by ``GET /api/missions`` (nested ``reward``).
        """
        reward = d.get("reward")
        if isinstance(reward, Mapping):
            amount = _to_float(reward.get("amount"))
            currency = str(reward.get("currency") or "AIGEN")
        else:
            amount = _to_float(d.get("reward_amount"))
            currency = str(d.get("reward_currency") or "AIGEN")

        published = d.get("published")
        if isinstance(published, str) and published:
            try:
                published = _dt.datetime.fromisoformat(published)
            except ValueError:
                published = None
        elif not isinstance(published, _dt.datetime):
            published = None

        submissions = d.get("submissions")
        if isinstance(submissions, (list, tuple)):
            sub_count = len(submissions)
        else:
            sub_count = int(d.get("submission_count") or 0)

        return cls(
            id=str(d.get("id", "")),
            title=str(d.get("title", "")),
            description=str(d.get("description", "")),
            reward_amount=amount,
            reward_currency=currency,
            verification_type=str(d.get("verification_type", "")),
            deadline=_to_int_or_none(d.get("deadline")),
            status=str(d.get("status", "")),
            submission_count=sub_count,
            link=str(d.get("link", "")),
            published=published,
        )


def _to_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int_or_none(value: Any) -> Optional[int]:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None
