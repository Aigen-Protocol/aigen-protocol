# AIGEN — Distribution Progress (Live Tracker)

> Auto-updated weekly. This is the visible momentum file. Updated by `cron @weekly`.
> If you're returning after a break, read this first to see where we are.

## Latest snapshot — 2026-05-13

### MCP Registry Submissions (in flight)

| Registry | Stars | PR # | Status |
|---|---|---|---|
| punkpeye/awesome-mcp-servers | 86k | [#6288](https://github.com/punkpeye/awesome-mcp-servers/pull/6288) | open |
| e2b-dev/awesome-ai-agents | 28k | [#942](https://github.com/e2b-dev/awesome-ai-agents/pull/942) | open ⭐ |
| yzfly/Awesome-MCP-ZH | 7k | [#223](https://github.com/yzfly/Awesome-MCP-ZH/pull/223) | open ⭐ |
| jaw9c/awesome-remote-mcp-servers | 1k | [#320](https://github.com/jaw9c/awesome-remote-mcp-servers/pull/320) | open |
| MobinX/awesome-mcp-list | 879 | [#263](https://github.com/MobinX/awesome-mcp-list/pull/263) | open ⭐ |
| badkk/awesome-crypto-mcp-servers | 134 | [#73](https://github.com/badkk/awesome-crypto-mcp-servers/pull/73) | open |

### Framework Integration Issues Opened
- mastra-ai/mastra [#16546](https://github.com/mastra-ai/mastra/issues/16546) — community integration review request
- crewAIInc/crewAI [#5790](https://github.com/crewAIInc/crewAI/issues/5790) — community tool inclusion ask

### Framework SDKs Published (in repo, not yet on registries)
- `@aigen-protocol/mastra` (TypeScript, ~23k stars audience) — `integrations/mastra/`
- `aigen-langchain` (Python, ~90k stars audience) — `integrations/langchain/`
- `aigen-crewai` (Python, ~51k stars audience) — `integrations/crewai/`
- Total framework audience cumulative: ~164k stars

### Distribution / Discoverability Pages
- `/proof` — narrative case-study with live on-chain data
- `/llms.txt` — LLM-agent discoverability (llmstxt.org standard)
- `/badge/token/{addr}.svg` — viral SVG safety badges for any project's README
- `/badge/protocol-fee.svg` — marketing badge (0.5% fee)

### Real Revenue (lifetime)
- USDC fees collected: **$0.000250** (250 micros from end-to-end test mission)
- AIGEN fees collected: **1 AIGEN** (test)
- Real external paying mission creators: **0**

### External Contributors
- **worjs** (Jaegun Cho) — 1 PR merged (manifesto translations) + 5 contributions = 4300 AIGEN paid
- **nicbstme** (Nicolas Bustamante, Microsoft AGI) — 3 PRs merged + 1 declined = 9000 AIGEN paid

Total paid to externals: **13,300 AIGEN** (≈$1.33 at current AIGEN price)

### Code shipped
- Protocol fee mechanism (0.5%) — commit `dc066e5`
- Brand reposition "Open Bounty Protocol" — commit `8c79116`  
- 10 new task domains — commit `ee8952e`
- Manifesto translations 5 langues — commit (worjs)
- 3 nicbstme PRs merged — Telegram bot, Glama inspector, NFT safety MCP

### Treasury (Base mainnet)
- ETH: 0.0000284 (~$0.07)
- USDC: $0.078

### Treasury (Optimism)
- ETH: 0.000433 (~$1.04)
- USDC: 0
- AIGEN: 990M (off-chain calc; on-chain LP $1.39 each side)

### What's next (rolling 30-day plan)
1. ⏳ Wait for PR review on 3 awesome lists (88k+ stars audience)
2. 🔥 **Submit Birdeye BIP Competition Sprint 4 — 500 USDC potential ($500 if top-1)**
   - Submission writeup: `distribution/birdeye_bip_submission.md`
   - Need: BIRDEYE_API_KEY (free with competition entry) + 5min user clicks
   - Deadline: May 16
3. 🔜 Submit to mcpservers.org (wong2's web form)
4. 🔜 Apply for Optimism RetroPGF Round 6 (draft ready)
5. 🔜 Build ElizaOS plugin (existing PR pending merge)
6. 🔜 Setup @aigen Farcaster/Twitter (needs user action — phone verify)
7. 🔜 Cold pitch top 5 from `outreach_targets_2026_05_13.json` for $25 attestation
8. 🔜 Build LangChain / OpenAI Agents SDK examples (next framework integrations)

### Daily automated jobs
- `0 8 * * *` — bounty radar scans Superteam Earn / Gitcoin / Replit
- `0 9 * * *` — contributor activity check on github
- `*/5 * * * *` — autopilot: resolve due missions, execute claims, poke buyback, daily mission

### New strategy: AIGEN as bounty hunter for AIGEN treasury
Inversion: instead of waiting for users to post on AIGEN, AIGEN's autopilot
hunts external bounties (Superteam, Replit, Gitcoin), wins USDC, deposits
to treasury. Treasury cash funds REAL AIGEN missions ($25-500), which
attract real bounty hunters → network effect kicks in.

Top current opportunity: Birdeye BIP Sprint 4, 500 USDC.
