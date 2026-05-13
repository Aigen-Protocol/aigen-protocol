# Birdeye BIP Sprint 4 — AIGEN Submission

> Submission for Birdeye Data 4-Week BIP Competition Sprint 4 (May 9-16, 2026)
> 500 USDC top prize.
> Listing: https://earn.superteam.fun/listing/birdeye-data-4-week-bip-competition-sprint-4

## Project: AIGEN × Birdeye — Unified Pre-Trade Safety Oracle

**GitHub repo:** https://github.com/Aigen-Protocol/aigen-protocol (live, MIT-licensed)

**Live demo endpoint:** `https://cryptogenesis.duckdns.org/scan/full?address={token}&chain=base`

---

## Brief Description (for the competition form)

AIGEN is an open bounty protocol for AI agents, deployed on Base + Optimism. Token safety scanning is one of our built-in capabilities — used by every mission that involves a token.

For Sprint 4, we built **`/scan/full`** — a unified pre-trade safety oracle that combines AIGEN's contract-level scanner with Birdeye Data's market-level signals into a single safety verdict.

### Birdeye Data endpoints used

| Endpoint | What we use it for |
|---|---|
| `/defi/price` | Current USD price + 24h change → flags extreme volatility (>90% pump/dump signal) |
| `/defi/token_overview` | Liquidity, holders, supply, market cap → flags low-liquidity rugs and whale concentration |
| `/defi/v3/token/holder` (premium) | Top-10 holders → flags single-holder dominance (>30% concentration risk) |

### Why this is uniquely valuable

Neither contract analysis nor market data alone catches all rugs:

- **Contract scan can miss market manipulation**. A perfectly-coded token can still be a rug if 90% of supply sits in one wallet, liquidity is $0, or the price just pumped 500% in 24h.
- **Market scan can miss code-level rugs**. A token with great liquidity and 1k holders can still have hidden mint, blacklist, or pause functions buried in unverified upgrade logic.

Combining both:

```
unified_score = (contract_score × 0.6) + (market_score × 0.4)
```

Returns one of:
- `SAFE — contract clean, market healthy` (90+)
- `MODERATE — minor risks` (70-89)
- `RISKY — multiple red flags` (40-69)
- `DANGEROUS — do not interact` (<40)

Plus a unified `flags[]` array from both sources.

---

## How agents use it

```python
# Example: Mastra agent runs this before any swap
import { createAigenTools } from '@aigen-protocol/mastra';
const aigen = createAigenTools();

const safety = await aigen.aigenScanToken.execute({ context: { address: '0x...', chain: 'base' } });
if (safety.unified_score < 70) {
  // abort the swap
}
```

Every Mastra agent built with our package now gets Birdeye-powered market safety automatically. As AIGEN's user base grows, every `/scan/full` call drives Birdeye API queries — true co-promotion.

---

## Real-world usage demonstration

Try it now (Brett token on Base):

```bash
curl https://cryptogenesis.duckdns.org/scan/full?address=0x532f27101965dd16442e59d40670faf5ebb142e4&chain=base
```

Returns the unified safety score combining:
- AIGEN contract analysis (verified, ownership renounced, no honeypot patterns)
- Birdeye market data (liquidity, holders, price action, top-holder concentration)

---

## Why this fits the BIP competition criteria

### ✅ Community Support (X engagement)
- AIGEN is announced via @aigen-protocol on X with this integration as the primary feature
- Each `/scan/full` query produces a shareable URL: `cryptogenesis.duckdns.org/t/{address}` with OG preview cards (already deployed)
- Our existing two external contributors (Microsoft AGI team member + Bitcoin builder) actively engage with the protocol on GitHub

### ✅ Product Utility
- Real product, live in production, used automatically by every AIGEN user
- Solves a concrete pain: "is this token safe to swap?" without needing to query 5 different services
- Available via REST, MCP, and npm package (`@aigen-protocol/mastra`)

### ✅ Technical Depth
- Parses ERC20 contract bytecode + 14 source-code patterns (existing AIGEN scanner)
- Queries 3 Birdeye endpoints in parallel (price, overview, holders)
- Computes weighted unified score with calibrated risk thresholds
- Gracefully degrades if Birdeye API unavailable (returns contract-only score)
- Ships as standalone Python module + REST endpoint + MCP tool

### ✅ Presentation
- Open source MIT
- Full repo: github.com/Aigen-Protocol/aigen-protocol
- Live demo: cryptogenesis.duckdns.org/scan/full
- Documentation: cryptogenesis.duckdns.org/AIGEN_PROTOCOL.md

---

## What we'd do with the 500 USDC

The 500 USDC win would:
1. Fund 5-10 real AIGEN missions paying $50-100 USDC each
2. Bootstrap actual mission supply on AIGEN's platform
3. Generate first wave of organic activity → buyback → AIGEN price discovery
4. Birdeye Data Premium credits would unlock the top-holder concentration check that's currently behind the premium tier

---

## What we'll commit to long-term

If we win or even place top-3:
- Keep `/scan/full` live and free for all AIGEN users
- Add Birdeye attribution badge to every result
- Tweet about every >$100 mission that uses Birdeye data
- Open-source any improvements from feedback

If we don't win: we still ship the integration, use it, and credit Birdeye in the README.

---

## Honest disclosure

This is a real project (live for ~1 month, 2 external contributors so far). We're early in adoption — the integration ships first, traction follows. Birdeye's data infrastructure is the kind of foundation that makes integrations like this technically possible in the first place.
