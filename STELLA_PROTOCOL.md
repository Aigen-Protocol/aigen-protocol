# STELLA Protocol — Spec

> An AIGEN-treasury-backed stablecoin on Base. The stablecoin Terra/Luna should
> have been: 100% collateralized by USDC, single chain, hard supply cap,
> auto-pause on under-collateralization, redemption never freezes.

---

## Why STELLA

Terra/Luna pioneered the right vision (decentralized stablecoin, permissionless
monetary policy, DeFi-native rails) but coupled it to fatal mechanics:
algorithmic-only backing, subsidized 20% yield, founder centralization,
cross-chain attack surface, no circuit breakers.

The vision is still right. The execution wasn't.

STELLA is what happens when you keep the vision and remove every failure mode
that killed Luna, in code, on day one.

## Core principles

1. **Backing is real and on-chain visible.** Every STELLA is backed by ≥150% USDC
   in the AIGEN treasury wallet. Anyone can read `collateralRatioBps()` on-chain.
2. **Mint pauses, redemption never does.** If treasury collateral drops below
   110% or peg drops below $0.97, anyone calls `pokePause()` and minting halts.
   Redemption stays open forever — even paused, you get your USDC back at $1.
3. **No founder, no admin, no upgrade proxy.** The contract is immutable. The
   governor (multisig) can only queue 48-hour-timelocked changes to: supply
   cap, governor address, unpause flag. Nothing else.
4. **Hard supply cap.** Starts at $100k. Raised by governor with 48h timelock.
   Caps the blast radius of any single integration or attack.
5. **No yield in the base contract.** Terra's Anchor was the death blow.
   STELLA itself just mints and redeems. Yield products are separate, opt-in
   contracts that holders choose. Yield must come from real revenue.
6. **Single chain.** Base only at launch. No cross-chain bridges = no
   Wormhole/Ronin-class vulnerabilities.
7. **AIGEN-aligned**. The same treasury that earns 0.5% on every AIGEN bounty
   resolution backs STELLA. As AIGEN protocol revenue grows, STELLA's backing
   grows automatically. The two flywheels reinforce.

## Mechanism

### Mint
```
caller → 100 USDC → Treasury wallet
Treasury → 100 STELLA → caller
```
Reverts if:
- Mint paused
- Supply cap would be breached
- Treasury collateral ratio is below 150% before, or would drop below 110% after
- Peg (USDC/USD via Chainlink) is below $0.97 or oracle stale (>1h)

### Redeem
```
caller → 100 STELLA → burned
Treasury → 100 USDC → caller
```
Reverts only if:
- Caller balance insufficient
- Treasury hasn't approved the contract (deployment-time setup)

That's the entire surface. No special cases.

### Auto-pause (`pokePause`)
Anyone can call. Cheap (no state writes if conditions OK). Sets `mintPaused = true`
if collateral_ratio_bps < 11000 OR peg < 97_000_000.

Once paused:
- Minting blocked
- Redemption unaffected
- Only governor can unpause, and only when both ratio AND peg recovered.

### Governance (timelocked)
- `queueGovernorChange(addr)` → 48h wait → `executeGovernorChange()`
- `queueSupplyCap(amount)` → 48h wait → `executeSupplyCap()`
- `unpause()` — instant, but only if both ratio + peg currently healthy

That's the entire governance surface. Cannot mint, burn, freeze, or touch user funds.

## Numerics

| Parameter | Value | Why |
|---|---|---|
| `MIN_COLLATERAL_RATIO_BPS` | 15000 (150%) | Mint requires this. Buffer absorbs USDC depeg events. |
| `PAUSE_RATIO_BPS` | 11000 (110%) | Auto-pause triggers below this. Still over-collateralized. |
| `PEG_FLOOR` | $0.97 | Minting halts if USDC/USD itself depegs (defends STELLA from upstream collapse). |
| `ORACLE_STALE_AFTER` | 1 hour | Reject stale Chainlink reads. |
| `INITIAL_SUPPLY_CAP` | $100,000 | Caps initial blast radius. Raise via 48h-timelocked vote. |
| `TIMELOCK` | 48 hours | All governance changes wait 2 days. |
| `STELLA_DECIMALS` | 18 | ERC20 standard. |
| `USDC_DECIMALS` | 6 | Native to Base USDC. Conversion = ×1e12. |

## Deployment plan

**Phase 1 — Audit & test (current)**
- Spec written ✓
- Contract code complete ✓
- Foundry test suite (7 tests, all passing) ✓
- Public review via this repo

**Phase 2 — Testnet (Base Sepolia)**
- Deploy with mock USDC
- Bootstrap with $100 testnet USDC in treasury
- Run for 7+ days, monitor `pokePause` calls, verify redemption always works
- Fuzz testing

**Phase 3 — Mainnet (Base)**
- Set up multisig (5-of-9) as initial governor
- Deploy with `forge script Deploy.s.sol`
- Treasury approves contract for USDC.transferFrom
- Initial supply cap = $100k
- Announce, wait

**Phase 4 — Liquidity**
- Seed an Aerodrome STELLA/USDC pool with treasury funds (small, $1k–5k)
- Bounty: peg defense missions on AIGEN (paid in AIGEN for arb work)
- Wait for organic adoption

**Phase 5 — Scale (months later)**
- Raise supply cap by governance vote (48h timelock visible to all)
- Deploy yield contracts (separate, opt-in)
- Cross-chain support (canonical bridges only) when supply > $1M

## What can go wrong (and what we do about it)

| Failure | Probability | Impact | Mitigation |
|---|---|---|---|
| USDC itself depegs | Low (was 0.87 in March 2023) | High | Mint auto-pauses below $0.97; redemption continues at $1 from existing reserves; once USDC recovers, mint resumes. |
| Treasury wallet compromised | Low (multisig + cold storage) | Catastrophic | Multisig 5-of-9 minimum; redemption pulls from approved allowance, not direct treasury access; if compromised, attacker can't touch STELLA contract logic. |
| Smart contract bug | Medium pre-audit, low post | Catastrophic | No upgrade proxy by design — bugs require redeploying a new contract with migration. Forces caution in initial code. Pre-deployment audit required. |
| Coordinated short attack | Medium | Medium | 150% over-collateral provides 33% downside buffer. Auto-pause prevents inflationary spiral. Hard supply cap limits sellable size. |
| Liquidity dries up on DEX | Medium | Low | Redemption is direct-to-USDC, doesn't depend on DEX liquidity. Worst case: arb loop slow but mechanism works. |
| Chainlink oracle failure | Low | Medium | Stale-check rejects oracle reads >1h old; minting auto-pauses; redemption unaffected. |
| AIGEN treasury under-funded | Currently ~$0.08 USDC | Low while small | Mint blocked when ratio < 150%. STELLA supply can only grow as treasury grows from real AIGEN protocol fees. Mechanically tied. |

## Audit status

**Not yet audited.** Recommended before mainnet:
- Trail of Bits / OpenZeppelin / Spearbit-grade external audit ($30k–80k typical)
- Public bug bounty program (post-audit)
- Formal verification of mint/redeem invariants

Until audit completes, only deploy on testnet.

## Open questions

- Should redemption charge a tiny fee (e.g., 1bps) to discourage MEV churn? **Currently: no fee.**
- Should mint require minimum amount to prevent gas-sandwich attacks? **Currently: no minimum (only `> 0`).**
- Should governor have an emergency-shutdown function (`pause + freeze redemption`)? **Currently: no — by explicit design. Redemption never freezes.**

## Source

- Contract: `contracts/src/Stella.sol`
- Tests: `contracts/test/Stella.t.sol`
- Deploy script: `contracts/script/Deploy.s.sol`
- This spec: `STELLA_PROTOCOL.md`

## License

MIT, immutable, public-good infrastructure.
