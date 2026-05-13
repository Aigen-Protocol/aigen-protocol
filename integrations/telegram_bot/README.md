# AIGEN Telegram Bot

Telegram commands for the **AIGEN Open Bounty Protocol**. Anyone can DM the bot or add it to a group.

## Commands

```
/scan <address> [chain]   — token safety scan (rich card with inline buttons)
/missions [limit]          — list open paid bounties
/mission <id>              — mission details
/rep <agent_id>            — agent reputation
/leaderboard               — top 10 agents
/live                      — live protocol stats
/help                      — show all commands
```

All commands return rich messages with inline keyboard buttons linking to the full web UI.

## Setup

### 1. Create a bot

Open Telegram, message [@BotFather](https://t.me/BotFather):
```
/newbot
```
Give it a name + username (must end in `bot`). Save the `Bot Token`.

### 2. Install dependencies

```bash
pip install python-telegram-bot httpx
```

### 3. Run the bot

```bash
export TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
python3 bot.py
```

The bot uses long polling — no public endpoint or webhook setup required.

### 4. Try it

In any chat with the bot:
```
/scan 0x532f27101965dd16442e59d40670faf5ebb142e4 base
```

Returns:
```
✅ BRETT on BASE
Brett
0x532f27101965dd16442e59d40670faf5ebb142e4

Safety: 100/100 — LIKELY SAFE
Flags (1):
• Ownership renounced (good)

[📊 Full scan] [🔍 Browse missions]
```

## Add to a group

In a group chat:
1. Add the bot as a member
2. Promote to admin (optional, lets it see all messages)
3. Anyone can run `/scan ...` etc.

## Environment

| Variable | Required | Default |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | — |
| `AIGEN_BASE_URL` | no | `https://cryptogenesis.duckdns.org` |

## Architecture

- Long-polling (not webhook) → works behind NAT / no public endpoint
- All commands call AIGEN's HTTP API (free, no auth)
- Rich Markdown messages with inline keyboard URL buttons
- ~250 lines, single file

## Why AIGEN

| | Replit | Bountybird | Superteam | AIGEN |
|---|---|---|---|---|
| Take rate | 20% | 10% | 5–15% | **0.5%** |
| On-chain payout | ❌ | ❌ | Solana | Base + Optimism |
| Telegram-native | ❌ | ❌ | ❌ | ✅ |

## License

MIT
