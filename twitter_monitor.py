#!/usr/bin/env python3
"""Twitter monitor for @Aigen_protocol — read-only since X Free tier doesn't
allow posting (credits required = $100/mo Basic plan).

Tracks:
  - Mentions of @Aigen_protocol from anyone
  - Engagement on tweets posted by @Aigen_protocol
  - Daily digest of activity → logged for human-in-the-loop posting

Run: python3 twitter_monitor.py once   # one cycle
     python3 twitter_monitor.py daemon # every 30 min
"""
import argparse
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

SECRETS = Path("/home/luna/.aigen-secrets/twitter.env")
LOG = Path("/home/luna/crypto-genesis/aigen/twitter_activity.jsonl")
ALERTS = Path("/home/luna/crypto-genesis/aigen/twitter_alerts.jsonl")
USER_ID = "2054568480884543489"  # @Aigen_protocol


def load_token():
    env = {}
    if SECRETS.exists():
        for line in SECRETS.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env.get("TWITTER_ACCESS_TOKEN", ""), env.get("TWITTER_REFRESH_TOKEN", "")


def refresh_access_token():
    """When access token expires (~2h), get a new one."""
    env = {}
    for line in SECRETS.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    rt = env.get("TWITTER_REFRESH_TOKEN", "")
    cid = env.get("TWITTER_OAUTH2_CLIENT_ID", "")
    csec = env.get("TWITTER_OAUTH2_CLIENT_SECRET", "")
    if not rt or not cid:
        return None

    import base64, urllib.parse
    auth = base64.b64encode(f"{cid}:{csec}".encode()).decode()
    body = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": rt}).encode()
    req = urllib.request.Request(
        "https://api.x.com/2/oauth2/token", data=body, method="POST",
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode())
        new_at = d.get("access_token", "")
        new_rt = d.get("refresh_token", "")
        if new_at and new_rt:
            # Rewrite secrets file with new tokens
            content = SECRETS.read_text()
            content = content.replace(env["TWITTER_ACCESS_TOKEN"], new_at)
            content = content.replace(env["TWITTER_REFRESH_TOKEN"], new_rt)
            SECRETS.write_text(content)
            print(f"  ✓ refreshed tokens")
            return new_at
    except Exception as e:
        print(f"  ✗ refresh err: {e}")
    return None


def api_get(path: str, token: str):
    req = urllib.request.Request(f"https://api.x.com/2{path}", headers={
        "Authorization": f"Bearer {token}",
        "User-Agent": "aigen-twitter-monitor/0.1",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        # If token expired, try to refresh
        if e.code == 401:
            new_token = refresh_access_token()
            if new_token:
                # Retry once with new token
                return api_get(path, new_token)
        try:
            return {"_err": json.loads(body)}
        except Exception:
            return {"_err": body[:200]}
    except Exception as e:
        return {"_err": str(e)}


def log_event(kind: str, data: dict):
    with open(LOG, "a") as f:
        f.write(json.dumps({"ts": int(time.time()), "kind": kind, "data": data}) + "\n")


def alert(kind: str, payload: dict):
    """Surface-able alert (visible to human, not just log)."""
    with open(ALERTS, "a") as f:
        f.write(json.dumps({"ts": int(time.time()), "kind": kind, **payload}) + "\n")


def cycle():
    token, _ = load_token()
    if not token:
        print("No token in secrets file — abort")
        return

    print(f"[{time.strftime('%Y-%m-%d %H:%M')} UTC] Twitter monitor cycle")

    # 1. Check own profile + tweet count for sanity
    me = api_get("/users/me?user.fields=public_metrics", token)
    if "_err" in me:
        if me["_err"] in (None, ""): pass
        # Try refresh
        new = refresh_access_token()
        if new:
            me = api_get("/users/me?user.fields=public_metrics", new)
    if "data" in me:
        m = me["data"].get("public_metrics", {})
        log_event("self_metrics", {"followers": m.get("followers_count"),
                                    "tweets": m.get("tweet_count"),
                                    "listed": m.get("listed_count")})
        print(f"  followers={m.get('followers_count')} tweets={m.get('tweet_count')} listed={m.get('listed_count')}")

    # 2. Search for mentions of @Aigen_protocol (recent)
    # Free tier supports /2/tweets/search/recent for the last 7 days
    mentions = api_get("/tweets/search/recent?query=%40Aigen_protocol&max_results=10&tweet.fields=author_id,created_at,public_metrics", token)
    if "data" in mentions:
        for m in mentions["data"]:
            log_event("mention", m)
            alert("mention", {
                "tweet_id": m["id"],
                "text": m["text"][:200],
                "author_id": m.get("author_id"),
                "url": f"https://x.com/i/status/{m['id']}",
            })
            print(f"  📣 mention by {m.get('author_id')}: {m['text'][:80]}")
    else:
        if "_err" in mentions:
            print(f"  mentions err: {mentions['_err']}")

    # 3. Look at our recent tweets and their engagement
    tweets = api_get(f"/users/{USER_ID}/tweets?max_results=10&tweet.fields=public_metrics,created_at", token)
    if "data" in tweets:
        for t in tweets["data"]:
            pm = t.get("public_metrics", {})
            log_event("own_tweet_metrics", {
                "tweet_id": t["id"],
                "text": t["text"][:120],
                "likes": pm.get("like_count"),
                "rts": pm.get("retweet_count"),
                "replies": pm.get("reply_count"),
                "impressions": pm.get("impression_count"),
            })
        print(f"  tracked {len(tweets['data'])} of own tweets")

    print(f"[done]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["once", "daemon"])
    ap.add_argument("--interval-min", type=int, default=30)
    args = ap.parse_args()
    if args.mode == "once":
        cycle()
    else:
        while True:
            try:
                cycle()
            except Exception:
                import traceback; traceback.print_exc()
            time.sleep(args.interval_min * 60)


if __name__ == "__main__":
    main()
