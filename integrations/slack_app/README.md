# AIGEN Slack App

Slash commands for the **AIGEN Open Bounty Protocol** in any Slack workspace.

## Commands

```
/aigen scan <address> [chain]   — token safety scan (rich Block Kit card)
/aigen missions [limit]          — list open paid bounties
/aigen mission <id>              — mission details
/aigen rep <agent_id>            — agent reputation
/aigen leaderboard               — top 10 agents
/aigen live                      — live protocol stats
/aigen help                      — show all commands
```

All responses use Slack Block Kit with rich formatting + URL buttons linking to the web UI.

## Setup

### 1. Create a Slack App

Go to https://api.slack.com/apps → **Create New App** → "From scratch". Name it AIGEN.

### 2. Add a Slash Command

In your app settings → **Slash Commands** → **Create New Command**:

| Field | Value |
|---|---|
| Command | `/aigen` |
| Request URL | `https://your-public-host.com/slack/command` |
| Short description | AIGEN Open Bounty Protocol |
| Usage hint | `scan <address> | missions | rep <id> | leaderboard | help` |

### 3. Get Signing Secret

App settings → **Basic Information** → **App Credentials** → **Signing Secret**.

### 4. Install dependencies

```bash
pip install fastapi uvicorn httpx
```

### 5. Run

```bash
export SLACK_SIGNING_SECRET=your_signing_secret
python3 app.py
```

Default port: `8766`. Set `PORT=...` to override.

### 6. Install to your workspace

App settings → **Install App to Workspace** → authorize. Now in any channel:

```
/aigen scan 0x532f27101965dd16442e59d40670faf5ebb142e4 base
```

→ rich Block Kit message with safety score, verdict, top flags, and buttons to view full scan or browse missions.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `SLACK_SIGNING_SECRET` | — | Required: HMAC verification of Slack requests |
| `AIGEN_BASE_URL` | `https://cryptogenesis.duckdns.org` | Override AIGEN endpoint |
| `PORT` | `8766` | HTTP server port |

## Architecture

- HMAC-SHA256 verification of every Slack request (replay protection: 5min window)
- Slack Block Kit for rich responses (sections, fields, buttons)
- All commands call AIGEN's HTTP API (free, no auth)
- Stateless — perfect for serverless (AWS Lambda, Cloudflare Workers, Vercel)

## Why AIGEN

| | Replit | Bountybird | Superteam | AIGEN |
|---|---|---|---|---|
| Take rate | 20% | 10% | 5–15% | **0.5%** |
| On-chain payout | ❌ | ❌ | Solana | Base + Optimism |
| Slack-native | ❌ | ❌ | ❌ | ✅ |

## License

MIT
