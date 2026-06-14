"""Pure-stdlib parser for the OABP missions RSS feed.

``parse_feed(xml_bytes)`` turns the bytes of ``/api/missions/feed.xml`` into a
list of :class:`oabp_feed.model.Mission` objects (newest first, matching feed
order). It handles RSS 2.0 with the ``oabp:`` extension namespace and also
degrades gracefully on Atom 1.0 feeds.

Design rules:
* No external dependencies -- ``xml.etree.ElementTree`` only.
* One bad ``<item>`` never sinks the whole feed: per-item parse errors are
  swallowed and that item is skipped (the listener still makes progress).
* A structurally broken document (not XML / no channel) raises
  :class:`FeedParseError` so the caller's backoff logic can react.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from email.utils import parsedate_to_datetime
from typing import List, Optional, Dict
from xml.etree import ElementTree as ET

from .model import Mission, FeedItem, REWARD_CURRENCIES, VERIFICATION_TYPES

# Namespace used by the OABP server for structured mission fields on each item.
OABP_NS = "https://cryptogenesis.duckdns.org/ns/oabp"
ATOM_NS = "http://www.w3.org/2005/Atom"


class FeedParseError(ValueError):
    """Raised when the payload is not a usable RSS/Atom feed at all."""


def parse_feed(data) -> List[Mission]:
    """Parse feed bytes/str into a list of :class:`Mission` (feed order).

    :param data: ``bytes`` or ``str`` of the feed document.
    :raises FeedParseError: if the document is not parseable as XML or lacks a
        recognised channel/feed root.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    if not data or not data.strip():
        raise FeedParseError("empty feed document")

    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise FeedParseError(f"invalid XML: {exc}") from exc

    tag = _local(root.tag)

    if tag == "rss":
        channel = root.find("channel")
        if channel is None:
            raise FeedParseError("RSS root has no <channel>")
        item_elems = channel.findall("item")
    elif tag == "feed":
        # Atom: entries live directly under <feed>.
        channel = root
        item_elems = root.findall(f"{{{ATOM_NS}}}entry") or root.findall("entry")
    elif tag == "channel":
        # Some servers emit a bare <channel> without the <rss> wrapper.
        channel = root
        item_elems = root.findall("item")
    else:
        raise FeedParseError(f"unrecognised feed root <{tag}>")

    missions: List[Mission] = []
    for el in item_elems:
        try:
            item = _parse_item(el, atom=(tag == "feed"))
        except Exception:
            # Never let one malformed item abort the whole feed.
            continue
        if item is None:
            continue
        missions.append(_item_to_mission(item))
    return missions


# --------------------------------------------------------------------------- #
# item -> FeedItem
# --------------------------------------------------------------------------- #

def _parse_item(el: ET.Element, atom: bool = False) -> Optional[FeedItem]:
    if atom:
        return _parse_atom_entry(el)

    guid_el = el.find("guid")
    link = _text(el.find("link"))
    title = _text(el.find("title"))
    description = _text(el.find("description"))
    pub = _parse_rfc822(_text(el.find("pubDate")))
    categories = tuple(
        c.text.strip() for c in el.findall("category") if c.text and c.text.strip()
    )

    oabp: Dict[str, str] = {}
    for child in el:
        local = _local(child.tag)
        if child.tag.startswith(f"{{{OABP_NS}}}") or child.tag.startswith("oabp:"):
            if child.text is not None:
                oabp[local] = child.text.strip()

    guid = _text(guid_el) if guid_el is not None else ""
    # Resolve the canonical id: explicit oabp:id > guid > id-in-link > title.
    canonical = oabp.get("id") or guid or _id_from_link(link) or title
    if not canonical:
        return None

    return FeedItem(
        guid=canonical,
        title=title,
        link=link,
        description=description,
        pub_date=pub,
        categories=categories,
        oabp=oabp,
    )


def _parse_atom_entry(el: ET.Element) -> Optional[FeedItem]:
    def afind(name: str) -> Optional[ET.Element]:
        found = el.find(f"{{{ATOM_NS}}}{name}")
        return found if found is not None else el.find(name)

    id_text = _text(afind("id"))
    title = _text(afind("title"))
    summary = _text(afind("summary")) or _text(afind("content"))

    link = ""
    for link_el in (el.findall(f"{{{ATOM_NS}}}link") or el.findall("link")):
        rel = link_el.get("rel", "alternate")
        if rel == "alternate" or not link:
            link = link_el.get("href", "") or link

    pub = None
    for name in ("updated", "published"):
        raw = _text(afind(name))
        if raw:
            pub = _parse_iso8601(raw)
            if pub is not None:
                break

    oabp: Dict[str, str] = {}
    for child in el:
        if child.tag.startswith(f"{{{OABP_NS}}}") or child.tag.startswith("oabp:"):
            if child.text is not None:
                oabp[_local(child.tag)] = child.text.strip()

    canonical = oabp.get("id") or id_text or _id_from_link(link) or title
    if not canonical:
        return None

    return FeedItem(
        guid=canonical,
        title=title,
        link=link,
        description=summary,
        pub_date=pub,
        categories=(),
        oabp=oabp,
    )


# --------------------------------------------------------------------------- #
# FeedItem -> Mission
# --------------------------------------------------------------------------- #

def _item_to_mission(item: FeedItem) -> Mission:
    o = item.oabp

    reward_amount = _coerce_float(o.get("reward_amount") or o.get("rewardAmount"))
    reward_currency = (o.get("reward_currency") or o.get("rewardCurrency") or "").upper()
    verification_type = o.get("verification_type") or o.get("verificationType") or ""
    deadline = _coerce_int(o.get("deadline"))
    status = o.get("status") or ""
    sub_count = _coerce_int(o.get("submission_count") or o.get("submissionCount"))
    description = o.get("description") or item.description

    # If the server didn't provide structured oabp:* fields, recover what we
    # can from the human-readable description (best-effort, never fatal).
    if reward_amount == 0.0 or not reward_currency:
        amt, cur = _reward_from_text(item.description)
        if reward_amount == 0.0:
            reward_amount = amt
        if not reward_currency:
            reward_currency = cur
    if not verification_type:
        verification_type = _verification_from_text(item.description)
    if deadline is None:
        deadline = _deadline_from_text(item.description)

    if not reward_currency:
        reward_currency = "AIGEN"

    return Mission(
        id=item.guid,
        title=item.title,
        description=description,
        reward_amount=reward_amount,
        reward_currency=reward_currency,
        verification_type=verification_type,
        deadline=deadline,
        status=status,
        submission_count=sub_count if sub_count is not None else 0,
        link=item.link,
        published=item.pub_date,
        source_item=item,
    )


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

_ID_IN_LINK = re.compile(r"/missions/([^/?#]+)")
_REWARD_RE = re.compile(
    r"(\d[\d,]*\.?\d*)\s*(AIGEN|USDC)\b", re.IGNORECASE
)
_DEADLINE_TS_RE = re.compile(r"deadline[^0-9]*(\d{9,})", re.IGNORECASE)


def _local(tag: str) -> str:
    """Strip an XML namespace from a tag name."""
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    if ":" in tag:
        return tag.split(":", 1)[1]
    return tag


def _text(el: Optional[ET.Element]) -> str:
    if el is None or el.text is None:
        return ""
    return el.text.strip()


def _id_from_link(link: str) -> str:
    if not link:
        return ""
    m = _ID_IN_LINK.search(link)
    return m.group(1) if m else ""


def _coerce_float(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return 0.0


def _coerce_int(value: Optional[str]):
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except ValueError:
        return None


def _reward_from_text(text: str):
    if not text:
        return 0.0, ""
    m = _REWARD_RE.search(text)
    if not m:
        return 0.0, ""
    amount = _coerce_float(m.group(1))
    currency = m.group(2).upper()
    return amount, currency


def _verification_from_text(text: str) -> str:
    if not text:
        return ""
    low = text.lower()
    for vt in VERIFICATION_TYPES:
        if vt in low or vt.replace("_", " ") in low:
            return vt
    return ""


def _deadline_from_text(text: str):
    if not text:
        return None
    m = _DEADLINE_TS_RE.search(text)
    if m:
        return _coerce_int(m.group(1))
    return None


def _parse_rfc822(value: str) -> Optional[_dt.datetime]:
    """Parse an RSS ``pubDate`` (RFC 822 / 2822). Returns aware UTC or None."""
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt.astimezone(_dt.timezone.utc)


def _parse_iso8601(value: str) -> Optional[_dt.datetime]:
    """Parse an Atom RFC 3339 / ISO-8601 timestamp into aware UTC."""
    if not value:
        return None
    txt = value.strip()
    # Python's fromisoformat handles 'Z' only from 3.11; normalise it.
    if txt.endswith("Z"):
        txt = txt[:-1] + "+00:00"
    try:
        dt = _dt.datetime.fromisoformat(txt)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt.astimezone(_dt.timezone.utc)
