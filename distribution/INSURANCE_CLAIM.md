# SafeAgent Insurance — Claim Process

The InsurancePool contract `0xe488785aC604534177bcFdd7e7D43B97bfC6A4b1` (Base) automatically receives 0.1% of every swap routed through SafeRouter V2 (`0xF6EFc5D5902d1a0ce58D9ab1715Cf30f077D8f6e`). This pool reimburses victims of "attested-then-rugged" tokens, capped at 10% of the pool's balance per single claim (so no single rug drains the fund).

## When you can claim

You're eligible if **all four** are true:

1. You routed a swap into a token through **SafeRouter V2** on Base (cite the swap tx hash).
2. At the time of the swap, the token had a **passing safety score** (>= 40 on the on-chain oracle, or a current attestation in the AttestationOracle `0x12083E387b98a241E14D1AbEF69e5Cab1bb821E7`).
3. The token has since become **demonstrably unsafe** — current safety score < 20, OR liquidity removed, OR honeypot now triggers when sold.
4. You **still hold** the rugged token in the wallet that did the swap (you didn't already exit at a loss).

## How to file

Open an issue at <https://github.com/Aigen-Protocol/aigen-protocol/issues/new> with title:

```
[INSURANCE CLAIM] <token symbol> <chain> — <your wallet>
```

Body must include:

```
- Original SafeRouter swap tx hash:   0x...
- Your wallet (the original swap signer):   0x...
- Rugged token address:   0x...
- Chain:   base
- Amount you swapped IN (in tokenIn wei):   ...
- Amount you received OUT (in tokenOut wei, the now-rugged token):   ...
- Current safety score (per /scan):   ...
- Evidence URL(s) showing rug (basescan tx removing LP / DEX showing 0 liquidity / honeypot.is screenshot):
  - ...

Bundle hash (compute keccak256 of the JSON of all the above, hex-encoded):
  0x...
```

## Operator review

Within 72h, the operator (founder wallet `0xDa429f2034b62b8722713873dE3C045eec390d8F`) verifies on-chain:

1. The cited swap tx is a real SafeRouter V2 call by your wallet
2. The token's current state is genuinely rugged
3. You still hold the proceeds
4. The bundle hash matches the keccak256 of your evidence JSON

If verified, the operator calls:

```solidity
InsurancePool.payClaim(
    victim,           // your wallet
    token,            // address(0) for native ETH, else the ERC-20 to pay
    amount,           // <= maxClaimToken(token) which is poolBalance / 10
    swapTxHash,       // your original SafeRouter swap
    evidenceHash      // your bundle hash
)
```

The pool transfers funds to your wallet directly. The on-chain `ClaimPaid` event documents the full record forever.

## What you receive

- Currency: matched to what's in the pool — usually the same token you swapped IN (since SafeRouter forwards 0.1% in tokenIn). If you'd prefer ETH or a stable, the operator can convert and pay with discretion.
- Cap: `min(your_loss, poolBalance(token) / 10)`. As the pool grows from cumulative swaps, individual cap rises.
- No co-pay, no deductible.

## Disputes

If the claim is rejected or undervalued, you can:

1. Reply on the issue with additional evidence (oracle dispute, alternative score source, fork tx history)
2. Escalate to community review — DM `@AIGEN_Protocol` or post in the public chat at <https://cryptogenesis.duckdns.org/feed>

## Pool transparency

- Live pool ETH balance: `cast call 0xe488785aC604534177bcFdd7e7D43B97bfC6A4b1 'ethBalance() (uint256)' --rpc-url https://mainnet.base.org`
- Live pool token balance: `cast call ... 'tokenBalance(address) (uint256)' <token_addr>`
- All claims paid: `cast call ... 'claimsCount() (uint256)'` then iterate `claims(uint256)`
- Or query the public ClaimPaid events on Basescan: <https://basescan.org/address/0xe488785aC604534177bcFdd7e7D43B97bfC6A4b1#events>

## Why this exists

Most "safety oracles" (GoPlus, De.Fi, Honeypot.is) give you a SCORE. None of them put their own money on the line. SafeAgent does: every swap routed through us pays into a fund that backstops users when the score was wrong. This is a hard, expensive promise — and the only honest one in the category.

## Limitations (read carefully)

- The pool does NOT cover swaps routed through other DEXes/aggregators. Use SafeRouter V2 for the protection to apply.
- The pool does NOT cover MEV, gas inflation, normal price impact, or sandwich attacks — only post-attestation rugs.
- The 10% per-claim cap means early claims (when pool is small) will pay symbolically. That's the trade-off of a self-funded model — pool grows with usage.
- Operator authority is currently a single key (founder wallet). v2 plan: 3-of-5 multisig governance.

## Source

- InsurancePool source: `contracts/InsurancePool.sol`
- Deploy artifact: `contracts/insurance_pool_deployment_base.json`
- Deploy tx: <https://basescan.org/tx/0x06dba7a497fff47c535230c450245250753c100f2c8be575d1351e1bfc05d3d1>
- Treasury redirect tx: <https://basescan.org/tx/0x25e7f39edb32b5d99507ab1686a33c886e5d3aa787d5b9144ce74d542ac22f11>
