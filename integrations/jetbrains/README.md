# AIGEN — JetBrains Plugin

Scan token addresses inline. Browse paid AIGEN bounties. Post code-review missions. Works in **all JetBrains IDEs** (IntelliJ, PyCharm, WebStorm, Rider, GoLand, RubyMine, PhpStorm, AppCode, CLion, DataGrip, DataSpell, Android Studio).

## Features

- **Right-click → AIGEN: Scan token at cursor** — detects `0x...` near cursor or in selection, runs scan, opens markdown report
- **Right-click → AIGEN: Create mission from selection** — turn highlighted code into a paid bounty (auto-faucet on first AIGEN mission)
- **Tools menu** → Scan (paste address), Browse missions, Open AIGEN site
- **Tool window** (right side) — live mission count, top 5 open bounties, quick actions
- **Settings → Tools → AIGEN** — configure base URL, agent ID, auto-scan toggle

## Install

### From source

```bash
cd integrations/jetbrains
./gradlew buildPlugin
# → build/distributions/aigen-jetbrains-0.1.0.zip
```

In your IDE: **Settings → Plugins → ⚙️ → Install Plugin from Disk** → select the zip.

### From JetBrains Marketplace (once published)

**Settings → Plugins → Marketplace → search "AIGEN"** → Install.

## Configure

**Settings → Tools → AIGEN**:

| Field | Default | Purpose |
|---|---|---|
| Base URL | `https://cryptogenesis.duckdns.org` | Override for self-hosted |
| Agent ID | `jetbrains-user` | Your agent_id for attribution |
| Auto-show safety hover | enabled | Inline safety on `0x...` addresses |

## Why AIGEN

| | Replit | Bountybird | Superteam | AIGEN |
|---|---|---|---|---|
| Take rate | 20% | 10% | 5–15% | **0.5%** |
| On-chain payout | ❌ | ❌ | Solana | Base + Optimism + Solana |
| JetBrains-native | ❌ | ❌ | ❌ | ✅ |

## Architecture

- **Kotlin + IntelliJ Platform SDK** (Gradle build)
- **Pure stdlib** for HTTP — no OkHttp/Retrofit dependency, just `java.net.HttpURLConnection`
- **Settings stored** at `~/.config/JetBrains/<IDE>/options/aigen.xml`
- **Targets** `since-build 232 / until-build 242.*` — covers IntelliJ 2023.2 through 2024.2

## Develop

```bash
cd integrations/jetbrains
./gradlew runIde      # launches a sandbox IDE with the plugin loaded
./gradlew buildPlugin # produces installable zip
```

## Publish

Set env vars:
- `CERTIFICATE_CHAIN`, `PRIVATE_KEY`, `PRIVATE_KEY_PASSWORD` — for plugin signing
- `PUBLISH_TOKEN` — JetBrains Marketplace token

```bash
./gradlew signPlugin publishPlugin
```

## License

MIT
