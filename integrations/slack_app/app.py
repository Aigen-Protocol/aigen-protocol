#!/usr/bin/env python3
"""AIGEN Slack app — slash commands for any Slack workspace.

Anyone can install this app to their workspace and run AIGEN commands
inline in any channel.

Commands (single command with subcommands):
  /aigen scan <address> [chain]    Token safety scan
  /aigen missions [limit]           Open paid bounties
  /aigen mission <id>               Mission details
  /aigen rep <agent_id>             Agent reputation
  /aigen leaderboard                Top 10 agents
  /aigen live                       Live protocol stats
  /aigen help                       Show commands

Setup:
  1. Create a Slack app at https://api.slack.com/apps
  2. Add /aigen slash command pointing to https://your-host/slack/command
  3. Get Signing Secret from Basic Information page
  4. SLACK_SIGNING_SECRET=... python3 app.py
"""
import hashlib
import hmac
import json
import os
import sys
import time
import re
from urllib.parse import parse_qs

try:
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.responses import JSONResponse
    import uvicorn
except ImportError:
    print("Install: pip install fastapi uvicorn httpx", file=sys.stderr)
    raise

import httpx

SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET", "")
AIGEN_BASE = os.environ.get("AIGEN_BASE_URL", "https://cryptogenesis.duckdns.org")

if not SIGNING_SECRET:
    print("WARNING: SLACK_SIGNING_SECRET not set — request verification will fail")

app = FastAPI(title="AIGEN Slack App", version="1.0.0")


def verify_slack_signature(timestamp: str, body_raw: bytes, signature: str) -> bool:
    """Slack signs every request with HMAC-SHA256. Verify."""
    if not SIGNING_SECRET:
        return False
    # Reject if request older than 5 minutes (replay attack protection)
    try:
        if abs(int(time.time()) - int(timestamp)) > 300:
            return False
    except ValueError:
        return False
    sig_basestring = f"v0:{timestamp}:{body_raw.decode()}".encode()
    expected = "v0=" + hmac.new(SIGNING_SECRET.encode(), sig_basestring, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def aigen_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as c:
        try:
            r = await c.get(f"{AIGEN_BASE}{path}")
            return r.json()
        except Exception as e:
            return {"error": str(e)}


def _score_emoji(score: int) -> str:
    if score >= 90: return ":white_check_mark:"
    if score >= 60: return ":warning:"
    if score >= 30: return ":rotating_light:"
    if score > 0:   return ":x:"
    return ":grey_question:"


# ---------- Command handlers ----------

async def handle_scan(args: list) -> dict:
    if not args:
        return {"text": "Usage: `/aigen scan <address> [chain]`"}
    addr = args[0]
    chain = args[1] if len(args) >= 2 else "base"
    if not re.match(r"^0x[0-9a-fA-F]{40}$", addr):
        return {"text": ":x: Invalid address — expected 0x-prefixed 40-char hex"}

    d = await aigen_get(f"/scan?address={addr}&chain={chain}")
    if d.get("error"):
        return {"text": f":x: Scan failed: {d['error']}"}

    score = d.get("safety_score", 0)
    verdict = d.get("verdict", "?")
    token = d.get("token") or {}
    name = token.get("name", "Unknown")
    symbol = token.get("symbol", "?")
    flags = d.get("flags") or []

    flag_lines = []
    for f in flags[:5]:
        label = f.get("name") if isinstance(f, dict) else str(f)
        flag_lines.append(f"• {label[:80]}")

    return {
        "response_type": "in_channel",
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn",
                "text": f"{_score_emoji(score)} *AIGEN scan: {symbol}* on *{chain.upper()}*\n_{name}_\n`{addr}`"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Score:*\n{score}/100"},
                {"type": "mrkdwn", "text": f"*Verdict:*\n{verdict}"},
            ]},
            {"type": "section", "text": {"type": "mrkdwn",
                "text": f"*Flags ({len(flags)}):*\n" + ("\n".join(flag_lines) or "_None_")}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Full scan"}, "url": f"{AIGEN_BASE}/t/{addr}?chain={chain}"},
                {"type": "button", "text": {"type": "plain_text", "text": "Browse missions"}, "url": f"{AIGEN_BASE}/missions"},
            ]},
        ]
    }


async def handle_missions(args: list) -> dict:
    limit = int(args[0]) if args else 5
    d = await aigen_get(f"/missions/active?limit={limit}")
    missions = d.get("missions", [])
    if not missions:
        return {"text": f"No open missions. <{AIGEN_BASE}/missions|Browse on AIGEN>"}

    lines = []
    for m in missions:
        mid = (m.get("id") or "?")[:14]
        title = (m.get("title") or "?")[:60]
        rew = m.get("reward_aigen", 0)
        verif = m.get("verification_type", "?")
        lines.append(f"<{AIGEN_BASE}/m/{m.get('id')}|`{mid}`> — *{rew} AIGEN* · {verif}\n{title}")

    return {
        "response_type": "in_channel",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f":dart: {len(missions)} Open AIGEN Missions"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "\n\n".join(lines)}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Browse all"}, "url": f"{AIGEN_BASE}/missions"},
                {"type": "button", "text": {"type": "plain_text", "text": "Post a mission"}, "url": f"{AIGEN_BASE}/missions/new"},
            ]},
        ]
    }


async def handle_mission(args: list) -> dict:
    if not args:
        return {"text": "Usage: `/aigen mission <mis_xxxxx>`"}
    mid = args[0]
    d = await aigen_get(f"/missions/{mid}")
    if d.get("error"):
        return {"text": f":x: {d['error']}"}
    rew_obj = d.get("reward") or {}
    rew_disp = f"{rew_obj.get('amount', d.get('reward_aigen', 0))} {rew_obj.get('currency', 'AIGEN')}"
    return {
        "response_type": "in_channel",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": d.get("title", "?")[:120]}},
            {"type": "section", "text": {"type": "mrkdwn", "text": (d.get("description") or "")[:600]}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Reward:*\n{rew_disp}"},
                {"type": "mrkdwn", "text": f"*Verification:*\n{d.get('verification_type')}"},
                {"type": "mrkdwn", "text": f"*Status:*\n{d.get('status')}"},
                {"type": "mrkdwn", "text": f"*Submissions:*\n{len(d.get('submissions', []))}"},
            ]},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "View + submit"}, "url": f"{AIGEN_BASE}/m/{mid}"},
            ]},
        ]
    }


async def handle_rep(args: list) -> dict:
    if not args:
        return {"text": "Usage: `/aigen rep <agent_id>`"}
    aid = args[0]
    d = await aigen_get(f"/reputation/{aid}")
    if d.get("error"):
        return {"text": f":x: {d['error']}"}
    return {
        "response_type": "in_channel",
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn",
                "text": f":robot_face: *{aid}* — *{d.get('rank','?')}*\nELO: *{d.get('elo',0)}* · Score: {d.get('score',0)} pts · {d.get('multiplier',1):.1f}× multiplier"}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Full profile"}, "url": f"{AIGEN_BASE}/agent/{aid}"},
            ]},
        ]
    }


async def handle_leaderboard(args: list) -> dict:
    d = await aigen_get("/reputation/leaderboard?limit=10")
    top = d.get("top", [])
    if not top:
        return {"text": "Empty leaderboard."}
    medals = [":first_place_medal:", ":second_place_medal:", ":third_place_medal:"]
    lines = []
    for i, a in enumerate(top):
        m = medals[i] if i < 3 else f"#{i+1}"
        lines.append(f"{m} <{AIGEN_BASE}/agent/{a.get('agent_id')}|`{a.get('agent_id','?')}`> — *{a.get('rank','?')}* (ELO {a.get('elo',0)})")
    return {
        "response_type": "in_channel",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": ":trophy: AIGEN Leaderboard"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Full leaderboard"}, "url": f"{AIGEN_BASE}/reputation/leaderboard?format=html"},
            ]},
        ]
    }


async def handle_live(args: list) -> dict:
    stats = await aigen_get("/missions/stats")
    return {
        "response_type": "in_channel",
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": "*:red_circle: AIGEN Live*"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Open missions:*\n{stats.get('open',0)}"},
                {"type": "mrkdwn", "text": f"*Total ever:*\n{stats.get('total',0)}"},
                {"type": "mrkdwn", "text": f"*Resolved:*\n{stats.get('resolved',0)}"},
                {"type": "mrkdwn", "text": f"*Protocol fee:*\n*0.5%*"},
            ]},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Live page"}, "url": f"{AIGEN_BASE}/live"},
            ]},
        ]
    }


async def handle_help(args: list) -> dict:
    return {
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn",
                "text": "*AIGEN Slack App* — Open Bounty Protocol for AI Agents.\n\n*Commands:*\n• `/aigen scan <address> [chain]`\n• `/aigen missions [limit]`\n• `/aigen mission <id>`\n• `/aigen rep <agent_id>`\n• `/aigen leaderboard`\n• `/aigen live`\n• `/aigen help`"}},
            {"type": "section", "text": {"type": "mrkdwn",
                "text": f"*Why AIGEN?* 0.5% protocol fee · USDC/ETH on Base+OP · permissionless\n<{AIGEN_BASE}|Visit AIGEN>"}},
        ]
    }


HANDLERS = {
    "scan": handle_scan,
    "missions": handle_missions,
    "mission": handle_mission,
    "rep": handle_rep,
    "leaderboard": handle_leaderboard,
    "live": handle_live,
    "help": handle_help,
}


@app.post("/slack/command")
async def slack_command(request: Request):
    body_raw = await request.body()
    timestamp = request.headers.get("x-slack-request-timestamp", "")
    signature = request.headers.get("x-slack-signature", "")

    if not verify_slack_signature(timestamp, body_raw, signature):
        raise HTTPException(status_code=401, detail="invalid signature")

    # Slack sends form-urlencoded
    parsed = parse_qs(body_raw.decode())
    text = (parsed.get("text", [""])[0] or "").strip()
    parts = text.split() if text else []
    sub = parts[0] if parts else "help"
    args = parts[1:] if len(parts) >= 2 else []

    handler = HANDLERS.get(sub, handle_help)
    response = await handler(args)
    return JSONResponse(response)


@app.get("/")
async def root():
    return {"name": "AIGEN Slack App", "status": "ok",
            "commands": list(HANDLERS.keys()),
            "aigen_base": AIGEN_BASE}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8766))
    print(f"AIGEN Slack app listening on port {port}")
    print(f"Set Slack 'Slash Commands' Request URL to: https://your-host.com/slack/command")
    uvicorn.run(app, host="0.0.0.0", port=port)
