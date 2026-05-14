# Uniswap Foundation — Security Track Grant Application

**Submit at:** https://www.uniswapfoundation.org/grants

**Track:** Security

**Funding ask:** $30,000 USDC (audit-only)

---

## Project: STELLA — A reference implementation for Terra-resistant stablecoins

### Why this is a Security-track project, not Ecosystem-track

We're not asking funding to build a competitor to USDC or DAI. We're asking
funding to **audit a public reference implementation** of a stablecoin
designed explicitly to refuse every Terra/Luna failure mode, so that any
future builder can fork it instead of repeating the same mistakes that
vaporized $60B in 2022.

The artifact is the audit + the audited code. The funding goes to the auditors,
not to operations.

### Context

When Terra/UST collapsed in May 2022:
- $60B in user value vaporized in 4 days
- LUNA went from $80 → fractions of a cent (hyperinflation to defend the peg)
- Ripple effects took out 3AC, Voyager, Celsius, Genesis (~$30B more)
- Uniswap LPs in UST/USDC pools held the bag at the worst moment

The mechanism failures were knowable in advance — algorithmic-only backing,
subsidized 20% yield (Anchor), 75% concentration in one protocol, no circuit
breakers, opaque reserves, founder centralization. They were knowable but the
design space lacked a publicly-audited "do this instead" reference.

### What STELLA is

A 250-line Solidity contract on Base that enforces every counter-design choice
in code:

| Terra failure mode | STELLA mitigation, in code |
|---|---|
| Algorithmic-only backing | `mint()` requires USDC transferIn 1:1; `backingUSDC()` reads contract balance |
| Anchor 20% subsidy → ponzi | No native yield. Yield is opt-in separate contracts only |
| 75% concentration in one protocol | `supplyCap = 100_000e18` initially. Raised only via 48h-timelocked vote |
| No circuit breakers | `pokePause()` callable by anyone; auto-pauses if ratio < 110% or peg < $0.97 |
| Opaque reserves | `backingUSDC()` and `collateralRatioBps()` are public view functions |
| Founder centralization (Do Kwon mints) | NO admin function exists for mint, burn, or freeze. Governor can ONLY queue 48h-delayed parameter changes |
| Cross-chain bridge attack surface | Single-chain (Base only). No bridge code in this contract |
| Forced de-peg via DEX liquidity drain | `redeem()` pulls from contract custody — never depends on DEX liquidity |

### Why this matters to Uniswap specifically

Uniswap LPs are the first casualty when a stablecoin de-pegs (UST/USDC pool on
Curve being the prime example). A safer stablecoin design ecosystem reduces
LP risk system-wide. Specifically:

- **Reference implementations get forked.** OpenZeppelin contracts power most
  ERC20s. A widely-respected, audited "safe stablecoin" pattern would similarly
  propagate.
- **Security research compounds.** Trail of Bits / Spearbit reports on novel
  patterns become the basis for future best-practice. Funding our audit
  produces a public artifact other auditors learn from.
- **Aligned with UF's stated security investment thesis** (24M USDC committed
  to security in 2025).

### Status

- ✅ Code complete: [Stella.sol](https://github.com/Aigen-Protocol/aigen-protocol/blob/main/contracts/src/Stella.sol)
- ✅ 15 Foundry tests, all passing
- ✅ Internal audit complete — 5 findings (1C, 2H, 1M, 1L) all fixed in v0.2
- ✅ Spec published: [STELLA_PROTOCOL.md](https://cryptogenesis.duckdns.org/STELLA_PROTOCOL.md)
- ✅ Live status page: [cryptogenesis.duckdns.org/stella](https://cryptogenesis.duckdns.org/stella)
- ✅ Live RPC reads from Base mainnet: [/api/stella/reserves](https://cryptogenesis.duckdns.org/api/stella/reserves)

Block on mainnet: external audit. Internal audit is necessary but not
sufficient for a stablecoin where bug = total loss.

### Budget — $30,000 single-line item

100% of the ask goes to a single audit firm. Suggested firms (we'll defer to
UF's preferred partners):

- Trail of Bits — typically $35-50k for ~250 LOC pure Solidity (high end)
- Spearbit — competitive pricing, distributed team, ~$25-40k
- OpenZeppelin Audits — $30-45k typical
- Code4rena public audit contest — $20-30k for prize pool, more eyes

We'd recommend **Spearbit or Code4rena** for cost-effectiveness on a contract
this size. Final decision deferred to UF.

### Deliverables

1. **Public audit report** published in our repo + linked from [/stella](https://cryptogenesis.duckdns.org/stella)
2. **All findings addressed** in code, with diff commits referenced in audit response
3. **Public retrospective post** comparing STELLA's design choices vs Terra's failure modes, written for other stablecoin builders
4. **Forking license: MIT** (already)
5. **Public commitment**: any future stablecoin we build on this base goes
   through the same audit process; we don't deploy variations without audit

### What we're NOT asking

- Not asking for ongoing operational funding
- Not asking for liquidity bootstrapping (we'll seed from AIGEN protocol fees)
- Not asking for marketing budget
- Not asking for team salary

Audit only. Single deliverable. Then back off.

### About us

Solo + AI collaboration. We've built the broader AIGEN ecosystem — open bounty
protocol, 22 MCP tools published on the official Model Context Protocol Registry,
multiple integrations with major AI agent frameworks. Public-good orientation
throughout.

GitHub: [github.com/Aigen-Protocol/aigen-protocol](https://github.com/Aigen-Protocol/aigen-protocol)
Wallet: `0xDa429f2034b62b8722713873dE3C045eec390d8F`
Contact: Cryptogen@zohomail.eu
