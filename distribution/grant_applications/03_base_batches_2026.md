# Base Batches 2026 — Cohort Application

**Apply at:** https://www.basebatches.xyz/

**Program:** 8-week virtual cohort, $10k grant + $50k investment for top 3

**Track:** Public-good infrastructure / DeFi

---

## Project name
**STELLA** — AIGEN-treasury-backed stablecoin

## Tagline (≤10 words)
The stablecoin Terra/Luna should have been. On Base.

## Stage
Pre-deployment. Code complete + 15 Foundry tests passing + internal audit done.
Live status page + public spec at [cryptogenesis.duckdns.org/stella](https://cryptogenesis.duckdns.org/stella).

## What you're building (1 paragraph)

A 100% USDC-backed stablecoin on Base, designed in direct opposition to every
Terra/Luna failure mode. Single chain, immutable contract, hard supply cap,
auto-pause minting on undercollateralization, redemption never freezes by
explicit design (no admin function exists for it). Sister to AIGEN — our open
bounty protocol that's already MCP-Registry-published and runs 9 autonomous
daemons. STELLA gives Base a reference implementation other builders can fork
when they need a treasury-backed stablecoin without recreating Terra's mistakes.

## Why Base specifically

1. Native USDC integration (Coinbase USDC on Base = highest-quality collateral)
2. Cheap gas — $0.20 to deploy, sub-penny to mint/redeem
3. Aerodrome for STELLA/USDC liquidity from day 1
4. Chainlink oracles available (USDC/USD on Base mainnet)
5. Single-chain by design avoids the bridge attack surface that's tanked
   $2B+ in 2022-2025 (Wormhole, Ronin, Multichain, etc.)

## Why now

- Terra collapse was 4 years ago. The lessons are public.
- Tornado Cash + Tether scrutiny means decentralized USDC-backed alternatives
  are increasingly valuable to ecosystem.
- Base has 100M+ users post-Coinbase wallet integration; needs more
  battle-tested DeFi primitives.
- Our other project AIGEN already runs autonomously (radar daemon generates
  real missions every 30 min from DexScreener data); STELLA fits as the
  treasury-backed value layer.

## Traction (verifiable, not vibes)

- Code: [github.com/Aigen-Protocol/aigen-protocol/tree/main/contracts](https://github.com/Aigen-Protocol/aigen-protocol/tree/main/contracts)
- Spec: [STELLA_PROTOCOL.md](https://cryptogenesis.duckdns.org/STELLA_PROTOCOL.md) (published, linked from sitemap)
- Live status page: [/stella](https://cryptogenesis.duckdns.org/stella)
- Live API: `/api/stella/reserves`, `/api/stella/peg` (read live Base mainnet RPC)
- 15 Foundry tests, all passing, 66% line coverage on src/Stella.sol
- Internal audit: 5 findings addressed in v0.2
- Sister project (AIGEN) on official MCP Registry: [registry.modelcontextprotocol.io/v0/servers/org.duckdns.cryptogenesis%2Fsafe-agent/versions/3.1.0](https://registry.modelcontextprotocol.io/v0/servers/org.duckdns.cryptogenesis%2Fsafe-agent/versions/3.1.0)

## What we'd use the cohort + funding for

**Cohort time (8 weeks):**
1. Get matched with audit partners through Base's network
2. Coordinate with Coinbase on potential USDC/STELLA pool seeding
3. Test mainnet liquidity strategy with Aerodrome team
4. Iterate on insurance fund design (v0.3) with cohort feedback

**$10k grant:**
- 30% audit prep (formal verification setup, fuzzing rigs)
- 50% partial audit funding (still need $20k more for full Trail of Bits scope)
- 20% mainnet deployment ops + initial liquidity bootstrap

**$50k investment (if top 3):**
- Full external audit covered
- 6 months of liquidity incentives via AIGEN bounty layer
- Bug bounty pool on Immunefi

## Why we'll ship vs vapor

- We've already built AIGEN end-to-end. 78 commits in 4 weeks. 9 autonomous
  daemons running in production.
- We don't need cohort funding to keep building — we'll publish STELLA on
  testnet within 7 days regardless. Cohort accelerates mainnet, doesn't
  enable existence.
- The contract already exists, tested. We're not asking funding to start —
  we're asking funding to ship safely.

## Team

Solo + AI collaboration. Multiple shipped projects. Public-good orientation.
Single founder makes decision velocity high; AI agent handles execution
volume. Track record in repo: [github.com/Aigen-Protocol](https://github.com/Aigen-Protocol).

## Public-good commitment

- MIT license, immutable contract, no admin keys
- Audit report public when complete
- Forking guide published
- We don't take a fee on STELLA mint/redeem — protocol revenue comes from the
  AIGEN bounty layer (0.5%), keeping STELLA itself rent-free

## Contact

GitHub: [github.com/Aigen-Protocol/aigen-protocol](https://github.com/Aigen-Protocol/aigen-protocol)
Email: Cryptogen@zohomail.eu
Wallet (Base): `0xDa429f2034b62b8722713873dE3C045eec390d8F`
