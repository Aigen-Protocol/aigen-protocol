#!/usr/bin/env python3
"""Register AIGEN slash commands globally with Discord. Run once per bot setup
(or after editing the command schema). Re-running is idempotent.

Requires env vars:
  DISCORD_APPLICATION_ID
  DISCORD_BOT_TOKEN
"""
import json
import os
import sys
import urllib.request

APP_ID = os.environ.get("DISCORD_APPLICATION_ID", "").strip()
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()

if not APP_ID or not BOT_TOKEN:
    print("ERROR: set DISCORD_APPLICATION_ID and DISCORD_BOT_TOKEN env vars", file=sys.stderr)
    sys.exit(1)

# Slash command definition: /aigen with 6 subcommands
COMMAND = {
    "name": "aigen",
    "description": "AIGEN Open Bounty Protocol — scan tokens, browse missions, check reputation",
    "type": 1,  # CHAT_INPUT
    "options": [
        {
            "name": "scan",
            "description": "Free token safety scan (0-100 score)",
            "type": 1,  # SUB_COMMAND
            "options": [
                {"name": "address", "description": "Token address (0x...)", "type": 3, "required": True},
                {"name": "chain", "description": "Chain (default: base)", "type": 3, "required": False,
                 "choices": [
                     {"name": "Base", "value": "base"},
                     {"name": "Ethereum", "value": "ethereum"},
                     {"name": "Optimism", "value": "optimism"},
                     {"name": "Arbitrum", "value": "arbitrum"},
                     {"name": "Polygon", "value": "polygon"},
                     {"name": "BSC", "value": "bsc"},
                 ]},
            ],
        },
        {
            "name": "missions",
            "description": "List open paid bounties",
            "type": 1,
            "options": [
                {"name": "limit", "description": "Max missions to show (default 5)", "type": 4, "required": False},
            ],
        },
        {
            "name": "mission",
            "description": "Get details on one mission",
            "type": 1,
            "options": [
                {"name": "id", "description": "Mission ID (mis_...)", "type": 3, "required": True},
            ],
        },
        {
            "name": "rep",
            "description": "Get agent reputation (ELO + rank)",
            "type": 1,
            "options": [
                {"name": "agent_id", "description": "Agent ID", "type": 3, "required": True},
            ],
        },
        {
            "name": "leaderboard",
            "description": "Top 10 agents by ELO",
            "type": 1,
        },
        {
            "name": "live",
            "description": "Live AIGEN protocol stats",
            "type": 1,
        },
    ],
}


def main():
    url = f"https://discord.com/api/v10/applications/{APP_ID}/commands"
    data = json.dumps(COMMAND).encode()
    req = urllib.request.Request(url, method="POST", data=data,
                                 headers={"Authorization": f"Bot {BOT_TOKEN}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"OK ({r.status})")
            print(json.dumps(json.loads(r.read()), indent=2))
    except urllib.error.HTTPError as e:
        print(f"FAILED ({e.code}): {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
