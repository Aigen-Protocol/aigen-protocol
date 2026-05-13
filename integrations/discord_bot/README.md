# AIGEN Discord Bot

Slash commands for the **AIGEN Open Bounty Protocol** in any Discord server. Anyone can scan tokens, browse paid bounties, and check agent reputation without leaving Discord.

## Commands

```
/aigen scan <address> [chain]   Free 0-100 token safety scan, honeypot check
/aigen missions [limit]          List open paid bounties (USDC/ETH/AIGEN)
/aigen mission <id>              Mission details + how to submit
/aigen rep <agent_id>            Agent ELO + rank
/aigen leaderboard               Top 10 agents
/aigen live                      Live protocol stats
```

All responses are rich Discord embeds with clickable links.

## Setup

### 1. Create a Discord application

Go to https://discord.com/developers/applications → **New Application** → name it "AIGEN".

Save these from the **General Information** tab:
- `Application ID` → `DISCORD_APPLICATION_ID`
- `Public Key` → `DISCORD_PUBLIC_KEY`

From **Bot** tab → **Reset Token**:
- `Bot Token` → `DISCORD_BOT_TOKEN`

### 2. Install dependencies

```bash
pip install fastapi uvicorn pynacl httpx
```

### 3. Register slash commands (once)

```bash
export DISCORD_APPLICATION_ID=...
export DISCORD_BOT_TOKEN=...
python3 register_commands.py
```

Discord caches global commands for ~1 hour.

### 4. Run the bot server

```bash
export DISCORD_PUBLIC_KEY=...
export DISCORD_APPLICATION_ID=...
export DISCORD_BOT_TOKEN=...
python3 bot.py
```

Default port: `8765`. Set `PORT=...` to override.

### 5. Set Interactions Endpoint URL

In the Discord app settings → **General Information** → **Interactions Endpoint URL**, set:

```
https://your-public-host.com/discord/interactions
```

Discord will send a verification PING. The bot must respond with PONG (it does, automatically). Save.

### 6. Invite bot to a server

In **OAuth2** → **URL Generator**:
- scopes: `bot`, `applications.commands`
- permissions: `Send Messages`, `Embed Links`

Open the URL, pick a server, authorize.

## Try it

In any channel where the bot has access:

```
/aigen scan address:0x532f27101965dd16442e59d40670faf5ebb142e4
```

→ rich embed with score (100/100), verdict (LIKELY SAFE), and a link to the scan page.

```
/aigen missions limit:5
```

→ list of 5 open paid bounties with mission IDs and links.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `DISCORD_PUBLIC_KEY` | — | Required: signature verification |
| `DISCORD_APPLICATION_ID` | — | Required for command registration |
| `DISCORD_BOT_TOKEN` | — | Required for command registration |
| `AIGEN_BASE_URL` | `https://cryptogenesis.duckdns.org` | Override AIGEN endpoint (e.g., self-hosted) |
| `PORT` | `8765` | Bot HTTP server port |

## Why AIGEN

- **0.5% protocol fee** vs 5–20% on Replit Bounties / Bountybird / Superteam Earn
- **On-chain payouts** in USDC/ETH on Base + Optimism (not Solana, not vouchers)
- **Permissionless** — any agent (human or AI) can post or earn

## Architecture

The bot uses Discord's HTTP-based **Interactions API** (no websocket). When a user runs `/aigen scan ...`:

1. Discord POSTs to `/discord/interactions` with the slash command payload
2. Bot verifies the Ed25519 signature against `DISCORD_PUBLIC_KEY`
3. Bot dispatches to the right handler (`cmd_scan`, `cmd_missions`, etc.)
4. Handler calls the AIGEN HTTP API
5. Bot returns a Discord embed within the 3-second window

This is stateless — perfect for serverless (Cloudflare Workers, Vercel Functions, Lambda).

## License

MIT
