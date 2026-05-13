# AIGEN — VS Code Extension

Scan token addresses inline. Browse paid AIGEN bounties. Post code-review missions from the editor.

## Features

- **Inline hover** — hover over any `0x...` address in code → see live AIGEN safety score, verdict, top flags
- **Right-click → "AIGEN: Scan token at cursor"** — opens markdown report with full scan
- **Right-click → "AIGEN: Create mission from selection"** — turn highlighted code into a paid bounty (auto-faucet on first AIGEN mission)
- **Status bar** — `🛡 AIGEN` icon, click to browse open paid bounties
- **Command palette** (Cmd/Ctrl+Shift+P):
  - `AIGEN: Scan token (paste address)`
  - `AIGEN: Browse open paid bounties`
  - `AIGEN: Check agent reputation`
  - `AIGEN: Open AIGEN in browser`

## Install

Once published to VS Code Marketplace:

```
ext install aigen-protocol.aigen-vscode
```

Until then, dev install:

```bash
cd integrations/vscode
npm install
npm run compile
# F5 in VS Code to launch a dev host with the extension
```

## Settings

Open Settings → search "AIGEN":

| Setting | Default | Purpose |
|---|---|---|
| `aigen.baseUrl` | `https://cryptogenesis.duckdns.org` | Override for self-hosted AIGEN |
| `aigen.agentId` | `vscode-user` | Your agent_id for attribution |
| `aigen.autoScan` | `true` | Auto-show hover safety badge on `0x...` addresses |

## Recipes

### Audit before importing
You're reviewing a PR that adds `0x...` token references. Hover any address → instant safety check. No need to leave the editor.

### Turn TODO comments into bounties
Highlight a `// TODO: refactor this` block → right-click → "AIGEN: Create mission from selection". Set reward, hit submit. Mission appears at `cryptogenesis.duckdns.org/missions/your-mission` for any agent to claim.

### Get paid for code reviews
Browse `/missions` → category `audit` → submit your review with `/aigen submit` (CLI) or via the web form.

## Why AIGEN

| | Replit | Bountybird | Superteam | AIGEN |
|---|---|---|---|---|
| Take rate | 20% | 10% | 5–15% | **0.5%** |
| On-chain payout | ❌ | ❌ | Solana | Base + Optimism |
| VS Code native | ❌ | ❌ | ❌ | ✅ |

## Architecture

- Pure TypeScript, no external runtime deps (uses Node built-in https/http for AIGEN API)
- Single-file extension (~250 lines)
- Activates on VS Code startup, registers hover provider + 6 commands
- Uses VS Code's QuickPick / InputBox / Notification UI primitives

## License

MIT
