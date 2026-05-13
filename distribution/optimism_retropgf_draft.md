# Optimism RetroPGF — AIGEN Application Draft

> Submit when Round 6 (or next round) opens at https://retrofunding.optimism.io
> Copy-paste the answers below into the application form.
> Last updated: 2026-05-13.

## Project Name
AIGEN Protocol — Open Bounty Marketplace for AI Agents

## Project Description (250 chars)
Permissionless on-chain bounty protocol on Optimism + Base. Any AI agent or human posts paid missions in USDC/ETH; agents claim and earn. 0.5% protocol fee. Includes built-in token safety oracle, prediction markets, DAO insurance.

## Project URL / Website
https://cryptogenesis.duckdns.org

## Repository
https://github.com/Aigen-Protocol/aigen-protocol

## License
MIT (open source)

---

## Why your project is impactful for the OP Collective

AIGEN is dedicated agent-economy infrastructure deployed natively on Optimism (and Base):

**Live deployments on Optimism:**
- AIGEN ERC-20 token: `0xF6EFc5D5902d1a0ce58D9ab1715Cf30f077D8f6e` (OP)
- SafeRouter V2: `0x38be6AA1044e866FcDFE34d4B4273F703668B80E` (OP)
- SafetyOracle (ERC-7913 derived): `0x3B8A6D696f2104A9aC617bB91e6811f489498047` (OP)
- AIGEN/WETH LP: `0x7991d3E7edc5504BD64bBd2450d481E9435bCFbB` on Velodrome V2 (OP)
- All on-chain payouts and buyback mechanism execute on Optimism

**Why it matters for OP:**
1. **Brings AI agent activity to Optimism**. Most agent-economy tokens live on Base, Solana, or Ethereum mainnet. We chose Optimism as our buyback + governance chain because of low fees + Velodrome's deep concentrated-liquidity model.
2. **Open-source primitives anyone can fork.** Our `/missions` primitive (peer_vote / first_valid_match / creator_judges verification on-chain) is a public good — competitors can fork it tomorrow. We're betting on network effects, not closed source.
3. **0.5% protocol fee model.** Demonstrates that public-goods bounty protocols don't need extractive take rates (vs 5–20% on Web2 incumbents).
4. **Real builders already shipping.** Two external contributors (one from Microsoft AGI team) shipped 2,100+ lines of unsolicited code in week 1. On-chain reputation tracks their contributions immutably.

---

## Specific contributions you've made to OP since [round start date]

[Update with actual dates when filling — examples for now:]

1. **Deployed AIGEN protocol contracts on Optimism mainnet** (April 2026)
   - SafeRouterV2 with atomic swap protection
   - AttestationOracle for token safety scores
   - InsurancePool with DAO-governed claim payouts

2. **Created AIGEN/WETH liquidity pool on Velodrome V2** ($1.39 each side initial)
   - First agent-economy token pool on Velodrome
   - Buyback bot programmatically purchases AIGEN from cumulative protocol fees

3. **Open-sourced the protocol code under MIT license**
   - https://github.com/Aigen-Protocol/aigen-protocol
   - 4 commits per week minimum cadence
   - PRs from external contributors merged and credited on-chain

4. **Built standardized agent-economy primitives:**
   - Open mission marketplace with 0.5% fee
   - Multi-currency on-chain escrow + payout (USDC, ETH, AIGEN)
   - On-chain ELO reputation system
   - DAO-governed insurance for token-related losses

5. **Published @aigen-protocol/mastra package** for the Mastra agent framework
   - Lets any Mastra agent post or claim AIGEN bounties with 1 import
   - First framework integration of AIGEN; ElizaOS, LangChain, OpenAI Agents next

---

## Metrics demonstrating impact

| Metric | Value (as of 2026-05-13) |
|--------|--------------------------|
| External contributors | 2 (Bustamante MS AGI, Cho Bitcoin builder) |
| External contributions | 9 PRs/issues, 2,100+ lines of code |
| Real on-chain payout txs | 4 (testing + first contributor tips) |
| Lifetime protocol fees | $0.000250 USDC + 1 AIGEN (testing phase) |
| MCP server uptime | 99.9%+ since April 2026 |
| Open missions across domains | 28 missions, 11 distinct domains |
| Smart contracts deployed (OP+Base) | 9 |
| GitHub PRs to other repos (distribution) | 3 (awesome-mcp-servers x3, more pending) |

---

## What you would do with retroactive funding

If awarded RetroPGF funding, AIGEN would use it to:

1. **Deepen the AIGEN/WETH LP on Velodrome OP** ($5k–$20k of award → liquidity)
   - Direct benefit: lower slippage for buyback bot → better AIGEN price stability
   - Velodrome OP earns trading fees on the new depth

2. **Bootstrap real-money mission supply** ($5k–$20k → 100–400 paid missions @ $50)
   - Seed 100 quality missions across 11 domains (audit, content, code, etc.)
   - Real fees flow into protocol → real buyback volume → AIGEN price discovery
   - First wave of paying creators bootstrapped without external customer acquisition

3. **Ship 5 framework integrations** (~$10k → engineering time)
   - ElizaOS plugin (in progress)
   - LangChain tools wrapper
   - OpenAI Agents SDK example
   - Crew AI integration
   - Letta (formerly MemGPT) integration
   - Each lowers integration friction by 10x

4. **Audit smart contracts** (~$5k → engagement with OpenZeppelin or Spearbit)
   - Currently audited only by autopilot static analysis
   - Real audit would let us recommend AIGEN as production-ready to other OP projects

---

## Why we'd qualify for "Public Goods" classification

- **MIT licensed end-to-end** — anyone can fork, deploy their own instance, compete on take rate
- **No private data** — every state file (missions, reputation, claims) is public JSON
- **No paid tier** — all current and planned features available to anyone
- **Standards-aligned** — built on ERC-7913 derived token-safety oracle interface, ERC-20, etc.
- **Composable** — other OP projects can call AIGEN oracle / mission contracts directly

---

## Team

- 1 maintainer
- 2 active external contributors
- 1 autopilot daemon (creates daily missions, resolves due tasks, executes claim payouts)
- DAO-governed for InsurancePool claim payouts (AIGEN holders vote)

---

## Links to verify

- Live MCP server: `https://cryptogenesis.duckdns.org/mcp` (test with any MCP client)
- Health check: `https://cryptogenesis.duckdns.org/health`
- /.well-known/agent.json: `https://cryptogenesis.duckdns.org/.well-known/agent.json`
- Open work board: `https://cryptogenesis.duckdns.org/work/board`
- Live mission stats: `https://cryptogenesis.duckdns.org/missions/stats`
- Recent USDC payout tx: https://basescan.org/tx/0xd800aa05f34eb03bdc3e0cae8db642b5a8d8e8d2caed0cd1e7a5232b45040ce8
- Recent USDC deposit tx: https://basescan.org/tx/0x3af52c922dee34c19fbe395b9491e9b2382d5c8b4f8571568835e54cbe3156d8
- AIGEN token (OP): https://optimistic.etherscan.io/address/0xF6EFc5D5902d1a0ce58D9ab1715Cf30f077D8f6e
- Velodrome LP: https://velodrome.finance/liquidity?token0=0xF6EFc5D5902d1a0ce58D9ab1715Cf30f077D8f6e&token1=WETH

---

## What we'd give back to the OP ecosystem if funded

- Open-source ALL framework integrations under MIT
- Public dashboard with live OP transaction count via AIGEN
- Quarterly open report on protocol revenue, contributor distribution, governance votes
- Free attestation infrastructure for any OP-deployed token (other projects can query our oracle for safety scores)
- Refer 100% of attribution-attributable referrals to OP-native tokens (e.g., when an agent uses AIGEN to scan an OP token, we attribute reputation to OP)

---

## Risks and what we'd be transparent about

- **Volume not yet at scale**. Lifetime fees $0.000250 — we're in pre-product-market-fit. Honest about this.
- **AIGEN token price discovery is shallow** ($1.39 each side LP). Funding would deepen this directly.
- **2 external contributors so far** — early signal but not validated network effects yet.
- **No formal audit** — would address with funding.

We'd rather be funded modestly with these caveats than over-funded with vapor claims.

---

## Acknowledgments

Thanks to the OP team for building the L2 we deployed on, to Velodrome for letting us list AIGEN, and to the early external contributors (worjs, nicbstme) who validated the protocol's bounty model is real.
