# Aave Grants DAO — STELLA application

**Submit at:** https://aavegrants.org/

**Apply for:** Smart Contract Audit Funding ($30,000–50,000 USDC)

**Category:** Stablecoin infrastructure / Public goods

---

## Project: STELLA — AIGEN-Treasury-Backed Stablecoin

### One-line description
A 100% USDC-backed, immutable, single-chain stablecoin on Base, designed in
direct opposition to every Terra/Luna failure mode. Open-source MIT.

### Why this matters for the Aave ecosystem

Aave runs GHO and integrates dozens of stablecoins. The 2022 Terra collapse
($60B vaporized) exposed how algorithmic + reflexive backing fails under stress.
STELLA is the explicit "what should have been" — a reference implementation of
a stablecoin that cannot enter a death spiral:

- **100% USDC custody in contract** (not algorithmic, not partner-token absorbed)
- **Hard supply cap** raised only via 48h-timelocked vote
- **Auto-pause minting** if collateral ratio < 110% or peg < $0.97
- **Redemption never freezes** (no admin function exists for it)
- **48h timelock + emergency cancel** on all governance changes
- **No upgrade proxy** — code is immutable

Useful to Aave specifically:
- Could be listed as collateral in Aave V3 once audited (low-risk profile)
- Reference implementation other stablecoin builders can fork
- Reduces ecosystem-wide risk of another Terra event

### Problem we solve

When users deposit funds into a stablecoin, they're trusting:
1. The backing exists (collateral risk)
2. Redemption will work (counterparty risk)
3. The peg holds (mechanism risk)
4. No admin can rug them (governance risk)

Terra failed all four simultaneously. Most "stablecoins" today still fail at
least one. STELLA's contract enforces all four mechanically:

| Risk | STELLA mechanism |
|---|---|
| Collateral | `backingUSDC()` is a public view that reads the contract's own USDC balance |
| Counterparty | `redeem()` pulls from contract custody, no external approval needed |
| Mechanism | `pokePause()` + `MIN_RATIO_BPS = 15000` enforced in `mint()` |
| Governance | 48h timelock on every state change, emergency-cancel for malicious raises |

### What's already done (verifiable)

- ✅ Contract code complete: [Stella.sol](https://github.com/Aigen-Protocol/aigen-protocol/blob/main/contracts/src/Stella.sol)
  (~250 lines, no external dependencies, Solidity 0.8.24)
- ✅ Internal audit complete: 5 findings (1 critical, 2 high, 1 medium, 1 low)
  all fixed in v0.2 ([commit 8d033a6](https://github.com/Aigen-Protocol/aigen-protocol/commit/8d033a6))
- ✅ Test suite: **15 Foundry tests, all passing.** Coverage 66% on src/Stella.sol
- ✅ Public spec: [STELLA_PROTOCOL.md](https://cryptogenesis.duckdns.org/STELLA_PROTOCOL.md)
- ✅ Live status page: [cryptogenesis.duckdns.org/stella](https://cryptogenesis.duckdns.org/stella)
- ✅ Live API endpoints: `/api/stella/reserves`, `/api/stella/peg` (read live Base mainnet)

### What this grant unlocks

**Audit by Trail of Bits / Spearbit / OpenZeppelin / Code4rena.**

We've done what we can internally. External audit is the gating requirement
before mainnet. Without it, deployment would be irresponsible — a single bug
could vaporize all backing.

### Budget breakdown ($30,000 – $50,000)

| Line | Amount | Notes |
|---|---|---|
| External audit (1 firm, 2-3 weeks) | $25,000 – $40,000 | Trail of Bits estimate for ~250 LOC pure Solidity |
| Bug bounty bootstrap (Immunefi) | $5,000 | Initial bounty pool to attract whitehat reviews post-deploy |
| Multisig setup + governance docs | $0 | We'll do this in-kind |
| Testnet deployment + monitoring | $0 | Already running infrastructure (cryptogenesis.duckdns.org) |
| Mainnet deployment gas | < $1 | Base mainnet, ~$0.20 typical |
| Initial liquidity bootstrap (post-audit) | $0 | We'll seed from AIGEN protocol fees as they accrue |

**Total ask:** $30,000 minimum, $50,000 if you're feeling generous.

### Deliverables (within 3 months of grant)

1. **Audit report published** publicly + all findings addressed in code
2. **Mainnet deployment** on Base with multisig governor
3. **Open public dashboard** at `/stella` showing live reserves, ratio, peg
4. **Public retrospective** documenting the design choices vs Terra/Luna
5. **Forking guide** so other teams can deploy Stella variants for their treasury
6. **Aave V3 listing application** if the grant DAO sees fit

### Team

This is built by a single human + AI agent collaboration (Cryptogen / AIGEN
Protocol). We've built and shipped the broader [AIGEN ecosystem](https://cryptogenesis.duckdns.org)
— an open bounty protocol with 9 autonomous daemons, MCP server published on
the official [Model Context Protocol Registry](https://registry.modelcontextprotocol.io/v0/servers/org.duckdns.cryptogenesis%2Fsafe-agent/versions/3.1.0),
22 MCP tools, integrations with 8 frameworks (Mastra, LangChain, CrewAI, Letta,
OpenAI Agents, Vercel AI SDK, Cloudflare Workers AI + universal SDK), VS Code
+ JetBrains plugins, Discord/Telegram/Slack bots.

### What happens if we DON'T get this grant

STELLA stays as a public reference implementation on GitHub. Anyone can fork,
audit, deploy. We don't take it to mainnet because mainnet without audit is
malpractice. The world keeps running with Tether, Circle USDC, and DAI.
Nothing terrible happens — but the design space loses an iteration.

### Contact

- GitHub: [github.com/Aigen-Protocol/aigen-protocol](https://github.com/Aigen-Protocol/aigen-protocol)
- Email: Cryptogen@zohomail.eu
- Wallet for grant disbursement: `0xDa429f2034b62b8722713873dE3C045eec390d8F` (Base, also Optimism)

We're public-good infrastructure. The grant agreement can require milestones,
public reporting, full code transparency. We'll honor any reasonable terms.
