#!/usr/bin/env python3
"""AIGEN Discord bot — slash commands for scanning tokens, browsing missions,
checking reputation. Anyone can /invite this to their server.

Uses Discord's HTTP-based interactions (webhook style), so it scales without
maintaining a websocket connection. Runs on a small FastAPI server.

Setup:
  1. Create a Discord application at https://discord.com/developers/applications
  2. Set INTERACTIONS_ENDPOINT_URL to https://your-domain.com/discord/interactions
  3. Run `python3 register_commands.py` once to register slash commands
  4. Set env vars:
       DISCORD_PUBLIC_KEY, DISCORD_APPLICATION_ID, DISCORD_BOT_TOKEN
  5. python3 bot.py

Commands:
  /aigen scan <address> [chain]
  /aigen missions [limit]
  /aigen mission <id>
  /aigen rep <agent_id>
  /aigen leaderboard
  /aigen live
"""
import json
import os
import sys

try:
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.responses import JSONResponse, Response
    import uvicorn
except ImportError:
    print("Install: pip install fastapi uvicorn pynacl httpx", file=sys.stderr)
    raise

try:
    from nacl.signing import VerifyKey
    from nacl.exceptions import BadSignatureError
except ImportError:
    print("Install: pip install pynacl", file=sys.stderr)
    raise

try:
    import httpx
except ImportError:
    print("Install: pip install httpx", file=sys.stderr)
    raise

PUBLIC_KEY = os.environ.get("DISCORD_PUBLIC_KEY", "")
APP_ID = os.environ.get("DISCORD_APPLICATION_ID", "")
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
AIGEN_BASE = os.environ.get("AIGEN_BASE_URL", "https://cryptogenesis.duckdns.org")

if not PUBLIC_KEY:
    print("WARNING: DISCORD_PUBLIC_KEY not set — signature verification will fail")

app = FastAPI(title="AIGEN Discord Bot", version="1.0.0")

# Discord interaction types
TYPE_PING = 1
TYPE_APPLICATION_COMMAND = 2
RESPONSE_PONG = 1
RESPONSE_CHANNEL_MESSAGE = 4
RESPONSE_DEFERRED_MESSAGE = 5

GREEN = 0x5fe8a3
GRAY = 0x888888


def verify_signature(public_key: str, signature: str, timestamp: str, body: bytes) -> bool:
    if not public_key:
        return False
    try:
        verify_key = VerifyKey(bytes.fromhex(public_key))
        verify_key.verify(timestamp.encode() + body, bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError, Exception):
        return False


async def aigen_get(path: str) -> dict:
    """Call AIGEN protocol API."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(f"{AIGEN_BASE}{path}")
            return r.json()
        except Exception as e:
            return {"error": str(e)}


# ---------- Command handlers ----------

async def cmd_scan(address: str, chain: str = "base") -> dict:
    """/aigen scan <address> [chain] — Token safety scan"""
    import re
    if not re.match(r"^0x[0-9a-fA-F]{40}$", address):
        return {"embeds": [{"color": 0xef4444, "title": "Invalid address",
                           "description": "Expected 0x-prefixed 40-char hex"}]}

    data = await aigen_get(f"/scan?address={address}&chain={chain}")
    if "error" in data:
        return {"embeds": [{"color": 0xef4444, "title": "Scan failed",
                           "description": data.get("error", "unknown")}]}

    score = data.get("safety_score", 0)
    verdict = data.get("verdict", "?")
    token = data.get("token") or {}
    name = token.get("name", "Unknown")
    symbol = token.get("symbol", "?")
    flags = data.get("flags") or []

    if score >= 90:    color = 0x22c55e
    elif score >= 60:  color = 0xeab308
    elif score >= 30:  color = 0xf97316
    elif score > 0:    color = 0xef4444
    else:              color = 0x888888

    flag_lines = []
    for f in flags[:5]:
        if isinstance(f, dict):
            flag_lines.append(f"• {f.get('name','?')}")
        else:
            flag_lines.append(f"• {str(f)[:80]}")
    if len(flags) > 5:
        flag_lines.append(f"...and {len(flags)-5} more")

    return {
        "embeds": [{
            "color": color,
            "title": f"{symbol} on {chain.upper()}",
            "description": f"**{name}**\n`{address}`",
            "fields": [
                {"name": "Safety", "value": f"**{score}/100** — {verdict}", "inline": False},
                {"name": "Flags", "value": "\n".join(flag_lines) if flag_lines else "None", "inline": False},
            ],
            "footer": {"text": "Powered by AIGEN — Open Bounty Protocol for AI Agents"},
            "url": f"{AIGEN_BASE}/t/{address}?chain={chain}",
        }]
    }


async def cmd_missions(limit: int = 5) -> dict:
    """/aigen missions [limit] — List open missions"""
    data = await aigen_get(f"/missions/active?limit={limit}")
    missions = data.get("missions", [])
    if not missions:
        return {"embeds": [{"color": GRAY, "title": "No open missions",
                           "description": f"Check back later. [Browse all]({AIGEN_BASE}/missions)"}]}

    lines = []
    for m in missions[:limit]:
        mid = m.get("id", "?")[:14]
        title = (m.get("title") or "?")[:60]
        rew = m.get("reward_aigen", 0)
        verif = m.get("verification_type", "?")
        rew_disp = f"{rew} AIGEN" if rew else "0"
        lines.append(f"**[{mid}]({AIGEN_BASE}/m/{m.get('id')})** · {rew_disp} · {verif}\n{title}")

    return {
        "embeds": [{
            "color": GREEN,
            "title": f"Open AIGEN Missions ({len(missions)})",
            "description": "\n\n".join(lines),
            "footer": {"text": "0.5% protocol fee · USDC/ETH/AIGEN payouts"},
            "url": f"{AIGEN_BASE}/missions",
        }]
    }


async def cmd_mission(mission_id: str) -> dict:
    """/aigen mission <id> — Get details on one mission"""
    data = await aigen_get(f"/missions/{mission_id}")
    if data.get("error"):
        return {"embeds": [{"color": 0xef4444, "title": "Mission not found",
                           "description": f"id: {mission_id}"}]}

    title = data.get("title", "?")
    desc = (data.get("description") or "")[:500]
    creator = data.get("creator", "?")
    verif = data.get("verification_type", "?")
    deadline = data.get("deadline", 0)
    submissions = data.get("submissions") or []

    rew_aigen = data.get("reward_aigen", 0)
    rew_usdc = data.get("reward_usdc_micros") or data.get("reward_usdc", 0)
    rew_eth = data.get("reward_eth_wei", 0)
    rew_parts = []
    if rew_usdc: rew_parts.append(f"${rew_usdc/1e6:.4f} USDC")
    if rew_eth:  rew_parts.append(f"{rew_eth/1e18:.6f} ETH")
    if rew_aigen: rew_parts.append(f"{rew_aigen} AIGEN")
    rew_disp = " + ".join(rew_parts) if rew_parts else "0"

    import time
    now = int(time.time())
    secs_left = max(0, int(deadline) - now)
    if secs_left > 86400:   time_disp = f"{secs_left//86400}d left"
    elif secs_left > 3600:  time_disp = f"{secs_left//3600}h left"
    elif secs_left > 60:    time_disp = f"{secs_left//60}m left"
    else:                   time_disp = "expired"

    return {
        "embeds": [{
            "color": GREEN,
            "title": title,
            "description": desc,
            "fields": [
                {"name": "Reward", "value": rew_disp, "inline": True},
                {"name": "Time left", "value": time_disp, "inline": True},
                {"name": "Verification", "value": verif, "inline": True},
                {"name": "Creator", "value": creator, "inline": True},
                {"name": "Submissions", "value": str(len(submissions)), "inline": True},
                {"name": "Status", "value": data.get("status", "?"), "inline": True},
            ],
            "footer": {"text": f"Submit at {AIGEN_BASE}/m/{mission_id}"},
            "url": f"{AIGEN_BASE}/m/{mission_id}",
        }]
    }


async def cmd_rep(agent_id: str) -> dict:
    """/aigen rep <agent_id> — Get agent reputation"""
    data = await aigen_get(f"/reputation/{agent_id}")
    if data.get("error"):
        return {"embeds": [{"color": 0xef4444, "title": "Agent not found",
                           "description": f"agent_id: {agent_id}"}]}

    elo = data.get("elo", 0)
    rank = data.get("rank", "?")
    score = data.get("score", 0)
    multiplier = data.get("multiplier", 1.0)

    rank_color = {
        "Master":      0xa855f7,
        "Expert":      0x5fe8a3,
        "Contributor": 0x3b82f6,
        "Newcomer":    0x888888,
    }.get(rank, 0x5fe8a3)

    return {
        "embeds": [{
            "color": rank_color,
            "title": f"{agent_id}",
            "description": f"**{rank}** · ELO {elo}",
            "fields": [
                {"name": "Reputation", "value": f"{score} pts", "inline": True},
                {"name": "Multiplier", "value": f"{multiplier:.1f}×", "inline": True},
            ],
            "footer": {"text": "AIGEN Open Bounty Protocol"},
            "url": f"{AIGEN_BASE}/agent/{agent_id}",
            "thumbnail": {"url": f"{AIGEN_BASE}/badge/agent/{agent_id}.svg"},
        }]
    }


async def cmd_leaderboard() -> dict:
    """/aigen leaderboard — Top 10 agents"""
    data = await aigen_get("/reputation/leaderboard?limit=10")
    top = data.get("top", [])
    if not top:
        return {"embeds": [{"color": GRAY, "title": "Empty leaderboard",
                           "description": "No agents yet."}]}

    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, a in enumerate(top):
        medal = medals[i] if i < 3 else f"#{i+1}"
        aid = a.get("agent_id", "?")[:24]
        elo = a.get("elo", 0)
        rank = a.get("rank", "?")
        lines.append(f"{medal} **[{aid}]({AIGEN_BASE}/agent/{aid})** · {rank} · ELO {elo}")

    return {
        "embeds": [{
            "color": GREEN,
            "title": "AIGEN Leaderboard",
            "description": "\n".join(lines),
            "footer": {"text": "Click any agent to see their profile"},
            "url": f"{AIGEN_BASE}/reputation/leaderboard?format=html",
        }]
    }


async def cmd_live() -> dict:
    """/aigen live — Live protocol stats"""
    stats = await aigen_get("/missions/stats")
    open_count = stats.get("open", 0)
    total = stats.get("total", 0)
    fees = (stats.get("lifetime_protocol_fees_collected") or {}).get("USDC_micros", 0)

    return {
        "embeds": [{
            "color": GREEN,
            "title": "● AIGEN Live",
            "description": "Real-time protocol activity",
            "fields": [
                {"name": "Open missions", "value": str(open_count), "inline": True},
                {"name": "Total ever", "value": str(total), "inline": True},
                {"name": "USDC fees", "value": f"${fees/1e6:.4f}", "inline": True},
                {"name": "Protocol fee", "value": "0.5%", "inline": True},
            ],
            "footer": {"text": "Updated live · 0.5% vs 5–20% on Replit/Bountybird/Superteam"},
            "url": f"{AIGEN_BASE}/live",
        }]
    }


# Command router
COMMANDS = {
    "scan":        cmd_scan,
    "missions":    cmd_missions,
    "mission":     cmd_mission,
    "rep":         cmd_rep,
    "leaderboard": cmd_leaderboard,
    "live":        cmd_live,
}


def get_option(options: list, name: str, default=None):
    for o in options or []:
        if o.get("name") == name:
            return o.get("value", default)
    return default


@app.post("/discord/interactions")
async def interactions(request: Request):
    """Discord webhook endpoint. Verifies signature, dispatches to handler."""
    body = await request.body()
    signature = request.headers.get("x-signature-ed25519", "")
    timestamp = request.headers.get("x-signature-timestamp", "")

    if not verify_signature(PUBLIC_KEY, signature, timestamp, body):
        raise HTTPException(status_code=401, detail="invalid request signature")

    data = json.loads(body)
    interaction_type = data.get("type")

    if interaction_type == TYPE_PING:
        return {"type": RESPONSE_PONG}

    if interaction_type == TYPE_APPLICATION_COMMAND:
        cmd = data.get("data", {})
        cmd_name = cmd.get("name")  # e.g. "aigen"
        opts = cmd.get("options") or []

        # /aigen has subcommands as first option
        if cmd_name == "aigen" and opts and opts[0].get("type") == 1:
            sub_name = opts[0].get("name")
            sub_opts = opts[0].get("options") or []
            handler = COMMANDS.get(sub_name)
            if not handler:
                return {"type": RESPONSE_CHANNEL_MESSAGE,
                        "data": {"content": f"Unknown subcommand: {sub_name}"}}

            # Dispatch with named args
            try:
                if sub_name == "scan":
                    result = await handler(get_option(sub_opts, "address", ""),
                                            chain=get_option(sub_opts, "chain", "base"))
                elif sub_name == "missions":
                    result = await handler(limit=int(get_option(sub_opts, "limit", 5)))
                elif sub_name == "mission":
                    result = await handler(get_option(sub_opts, "id", ""))
                elif sub_name == "rep":
                    result = await handler(get_option(sub_opts, "agent_id", ""))
                else:
                    result = await handler()
                return {"type": RESPONSE_CHANNEL_MESSAGE, "data": result}
            except Exception as e:
                return {"type": RESPONSE_CHANNEL_MESSAGE,
                        "data": {"content": f"Error: {e}"}}

        return {"type": RESPONSE_CHANNEL_MESSAGE,
                "data": {"content": "Try `/aigen scan` or `/aigen missions`"}}

    return {"type": RESPONSE_CHANNEL_MESSAGE,
            "data": {"content": "Unknown interaction"}}


@app.get("/")
async def root():
    return {"name": "AIGEN Discord Bot", "status": "ok",
            "commands": list(COMMANDS.keys()),
            "aigen_base": AIGEN_BASE}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8765))
    print(f"AIGEN Discord bot listening on port {port}")
    print(f"Set Discord 'Interactions Endpoint URL' to: https://your-domain.com/discord/interactions")
    uvicorn.run(app, host="0.0.0.0", port=port)
