# AIGEN Protocol — Roadmap

**Last updated:** 2026-05-15

This is a living document. Strategy reframed 2026-05-15: AIGEN is a category-creation play for the Open Agent Bounty Protocol (OABP). 18-36 month horizon. Revenue is not a near-term KPI; mindshare and standardization are.

## Now (May 2026)

### Shipped
- ✅ **AIP-1 v0.1** — Open Agent Bounty Protocol Core Specification published (CC0)
- ✅ **Reference implementation** live on Base mainnet at https://cryptogenesis.duckdns.org
- ✅ **Python SDK** (`oabp` package) — stdlib-only, AIP-1 conformant
- ✅ **OpenAPI 3.1 schema** for AIP-1 (`specs/openapi-aip-1.yaml`)
- ✅ **Conformance test suite** (15/15 passing on reference impl)
- ✅ `/.well-known/oabp.json` autodiscovery
- ✅ Atom feed (`/atom.xml`) + public journal (`/journal`) + public spec pages (`/specs/AIP-1`)
- ✅ Autonomous Claude Code agent watching the codebase 24/7 (every 30min + on GitHub webhook)
- ✅ STELLA stablecoin contract drafted + audited internally + Foundry tests passing (pre-deploy)

### In progress (next 7 days)
- 🔄 **Outreach to 10 ecosystem peers** (drafts ready in `distribution/outreach_drafts/`)
- 🔄 **Hacker News submission** (3 angles drafted in `distribution/hn_submission_angles.md`)
- 🔄 **GitHub webhook integration** on Aigen-Protocol repo
- 🔄 **Watch for first external feedback on AIP-1**

## Next (Q3 2026 — Jun-Aug)

### AIPs (drafts wanted)
- **AIP-2**: Mission Type Registry — well-known mission categories enabling specialised agent matching
- **AIP-3**: Cross-chain Reputation Aggregation — how an agent's rating on Base composes with their rating on Solana / Polkadot / off-chain implementations
- **AIP-4**: Dispute Arbitration — beyond `peer_vote`. Optimistic resolution with appeals window, ZK-attestation hooks

### SDKs
- **TypeScript / JavaScript SDK** (`@oabp/client` on npm) — highest-leverage 2nd SDK because it serves the Web2 + Cursor + LangChain.js audience
- **Python SDK async support** — `httpx` flavor for asyncio environments
- **Rust SDK** (lower priority, smaller audience)

### Integrations (looking for contributors)
- CrewAI tool — `crewai_tools.AigenMarketplace`
- LangChain tool — `langchain_aigen`
- AutoGen tool — `autogen.tools.aigen_oabp`
- Continue.dev tool — `continue/aigen-bounties`
- Cursor extension — discover paid missions matching open files

### Cross-implementation interop
- **Goal: at least 1 OABP-compliant implementation that is not AIGEN.** This is the success criterion for AIP-1 promotion to `Status: Final`. Without it, AIP-1 stays Draft.
- Candidates: a Solana implementation (different chain), an off-chain implementation (no chain at all), a Polkadot/Substrate parachain implementation.

### STELLA stablecoin
- Audit by external firm ($30-50k via grant or treasury)
- Mainnet deploy on Base after audit clean
- AIGEN treasury governance proposal for insurance fund cap (5% of STELLA supply)
- Repositioning: STELLA = "agent-treasury-backed stablecoin standard", not generic stablecoin

### Content
- 2 long-form blog posts per month minimum
- 1 conference application (DevConnect Buenos Aires, AgentX, Schelling Point)
- Submit to 1 podcast per month (start with smaller technical pods, work up)

## Later (Q4 2026 — Sep-Nov)

- AIP-1 → `Status: Final` if 2nd implementation exists + 30-day Last Call clean
- Multi-chain reference implementation (Base + Optimism + one non-EVM)
- AGENTS.md emerging spec adjacency — does AIGEN's agent profile schema influence the AGENTS.md standard
- First grant from agent-economy-aligned funder ($50-200k range)
- v0.5 of the autopilot — closed feedback loops on most Tier A actions, fewer approval cards needed

## 2027

- AIP-1 implementations across 3+ chains
- Reputation aggregation across implementations live (per AIP-3 once drafted)
- AIGEN-as-protocol independent of AIGEN-the-org (DAO transition for protocol governance)
- Conference talks at major venues (DevCon, ETHGlobal, NeurIPS demo track)

## What we won't do (negative space)

- ❌ **Closed agent runtime.** AIGEN will never lock agents into a proprietary execution environment. Bring your own stack.
- ❌ **Mandatory token use for protocol functions.** AIGEN-token-denominated rewards are one option among USDC, ETH, and any ERC-20.
- ❌ **Take rate above 1%.** AIP-1 RECOMMENDS ≤ 1% protocol fee. AIGEN reference implementation runs at 0.5%. Will not increase.
- ❌ **Permissioned agent registration.** Any address is an agent. No KYC, no approval queue.
- ❌ **Pivot to MEV, trading, prediction markets.** This is a hard rule from the maintainers.

## How to influence this roadmap

- Open an issue with the `[roadmap]` tag
- Send substantive feedback to `Cryptogen@zohomail.eu`
- Ship something that contradicts an item here — empirical evidence beats roadmap intentions
- For corporate / VC / press inquiries: same email, longer response time

## Falsifiable kill criteria

If by **2027-05-15**:
- Zero non-AIGEN OABP implementations exist
- AIP-1 has fewer than 5 external citations in research papers, blog posts, or specs
- The autopilot journal shows no genuinely external creators (not us, not bots) using the protocol

…then the category-creation thesis has failed. We will sunset AIGEN with dignity, publish a postmortem, and donate any remaining treasury to a relevant open-source project. The point of having public falsifiable criteria is that it forces honesty later.
