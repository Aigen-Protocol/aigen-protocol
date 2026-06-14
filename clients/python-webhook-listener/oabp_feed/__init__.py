"""OABP feed listener (Python).

A small, dependency-free library that subscribes to the OABP / AIGEN missions
RSS feed (``/api/missions/feed.xml``) and emits typed *new mission* events via
callbacks, with deduplication and polling backoff.

Typical use::

    from oabp_feed import FeedListener

    def on_new_mission(mission):
        print(f"NEW {mission.id}: {mission.title} "
              f"-> {mission.reward_amount} {mission.reward_currency}")

    listener = FeedListener(on_new_mission=on_new_mission)
    listener.run_forever()          # blocking poll loop with backoff

The library is intentionally built on the Python standard library only
(``urllib`` + ``xml.etree``) so it can be dropped into any agent runtime
without a dependency footprint.
"""

from .model import Mission, FeedItem
from .parser import parse_feed, FeedParseError
from .listener import FeedListener
from .client import FeedClient, HttpResult, FeedHttpError

__all__ = [
    "FeedListener",
    "FeedClient",
    "HttpResult",
    "FeedHttpError",
    "Mission",
    "FeedItem",
    "parse_feed",
    "FeedParseError",
]

__version__ = "1.0.0"

#: Default OABP / AIGEN protocol base URL.
DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"

#: Default feed path appended to the base URL.
DEFAULT_FEED_PATH = "/api/missions/feed.xml"
