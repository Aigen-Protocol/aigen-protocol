# STELLA — AIGEN-Treasury-Backed Stablecoin

> The stablecoin Terra/Luna should have been. Single chain (Base). 100% backed
> by USDC in the AIGEN treasury. No algorithmic-only mechanism. Hard supply cap.
> Auto-pause on undercollateralization. Redemption never freezes.

## Status

**Pre-deployment.** Contract code complete + tested on local Foundry. Deploy
requires ~$0.50 of ETH on Base (gas) + a multisig to act as governor.

## Quick start

```bash
cd contracts
forge install foundry-rs/forge-std    # if you haven't
forge test -vv
```

Should output:
```
Running 6 tests for test/Stella.t.sol:StellaTest
[PASS] test_initial_state()
[PASS] test_mint_basic()
[PASS] test_mint_reverts_when_under_collateralized()
[PASS] test_redeem_basic()
[PASS] test_redeem_works_even_when_minting_paused()
[PASS] test_supply_cap_timelock()
[PASS] test_only_governor_can_unpause()
```

## Mechanism (vs Terra/Luna)

| Risk Terra/Luna died from | STELLA mitigation |
|---|---|
| Algorithmic-only backing → death spiral | **Every STELLA backed by USDC**. Mint requires USDC deposit. No volatility-absorbing partner token. |
| Anchor 20% subsidized yield | **No native yield mechanism in this contract**. Yield comes from real DeFi (LP fees etc) — opt-in by holders, not subsidized. |
| 75% concentration in one protocol | **Supply cap of $100k initially**, raised by 48h-timelocked governance — caps blast radius of any single integration. |
| No circuit breakers | **`pokePause()` callable by anyone** — auto-pauses minting if collateral ratio < 110% or peg < $0.97. One-way; only governor can unpause after both restored. |
| Reserve opacity | **`backingUSDC()` and `collateralRatioBps()` are public view functions**. Anyone can verify on-chain in real time. |
| Founder centralization | **No admin keys**. No mint, burn, or freeze functions for any address. Governor can ONLY: queue unpause, queue supply cap raise, queue governor change — all 48h timelocked. Cannot touch user funds. |
| Cross-chain bridges | **Single chain (Base)**. No cross-chain bridges in this contract. |
| Forced de-peg via liquidity attacks | **Redemption is always 1:1 with USDC**, gated only by treasury USDC balance and treasury approval. Cannot be paused. |

## Deployment

Constants for Base mainnet:
- USDC: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
- Chainlink USDC/USD: `0x7e860098F58bBFC8648a4311b374B1D669a2bc6B`
- AIGEN Treasury: `0xDa429f2034b62b8722713873dE3C045eec390d8F`

```bash
export PRIVATE_KEY=0x...                        # deployer key
export GOVERNOR_ADDRESS=0xMultisigAddressHere   # initial governor

forge script script/Deploy.s.sol \
  --rpc-url https://mainnet.base.org \
  --broadcast --verify \
  --etherscan-api-key $BASESCAN_KEY
```

Then **the treasury MUST approve the deployed contract** for USDC.transferFrom (so redemptions work):

```bash
cast send $USDC "approve(address,uint256)" $STELLA_ADDRESS $((2**256-1)) \
  --from $TREASURY --rpc-url https://mainnet.base.org
```

## What's NOT in this contract (intentionally)

- **No yield distribution** — that's a separate contract that holders opt into. Keeps STELLA itself unbreakable.
- **No fee on mint/redeem** — protocol fees come from AIGEN bounty layer (0.5%), not from holding STELLA.
- **No cross-chain functionality** — single-chain by design. Cross-chain in v2 maybe, with canonical bridges only.
- **No governance token** — the governor is a multisig at launch. AIGEN holders later get vote rights via a separate governance module.
- **No upgrade proxy** — code is immutable once deployed. No EIP-1967, no admin storage slots. Safer.

## License

MIT
