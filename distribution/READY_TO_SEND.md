# Outreach assets — copy/paste ready

## A. Twitter/X thread (post from your @AIGEN_Protocol or personal handle)

```
1/ We just shipped the only safety oracle that puts its own money on the line.

SafeAgent is now live on Base + Optimism with:
- 38 MCP tools (free)
- On-chain SafeRouter (atomic safety guarantee)
- HMAC-signed attestations
- Insurance pool funded by every swap

Stats: cryptogenesis.duckdns.org/stats

2/ The mechanism:

Every swap routed through SafeRouter pays 0.1% to a pool.

If a previously-attested token rugs, victims get reimbursed (capped 10% pool/claim).

GoPlus, De.Fi, Honeypot.is give scores. We give scores + insurance.

Pool: 0xe488785aC604534177bcFdd7e7D43B97bfC6A4b1

3/ Token deployers: get a permanent attestation badge for $25 USDC.

365-day cite-able cert + on-chain entry in our AttestationOracle (Base):
0x12083E387b98a241E14D1AbEF69e5Cab1bb821E7

Pay → POST /attest/premium → done.

Anyone can verify atomically with Solidity:
SafeGuard.requireAttested(token, 40)

4/ The economic loop:

EARN AIGEN → /scan, /shield, bounties (100/day distributed)
SPEND AIGEN → 100 per attestation, premium tier features
SELL AIGEN → Velodrome AIGEN/WETH pool 0x7991d3E... (Optimism)

First real contributor (godd-ctrl) earned 300 AIGEN, spent 100 on a cert.

5/ Live tx proofs:

First swap: basescan.org/tx/0x83a0384a...
Block-path proof (revert with TokenUnsafe): basescan.org/tx/0xc68b1ef6...
First on-chain payout (300 AIGEN): optimistic.etherscan.io/tx/0x448351a4...
LP genesis: optimistic.etherscan.io/tx/0xc2d79179...

Source: github.com/Aigen-Protocol/aigen-protocol
Pricing: cryptogenesis.duckdns.org/pricing
```

## B. Show HN draft

```
Title: Show HN: SafeAgent — DeFi safety oracle with on-chain insurance pool

Body:
We built SafeAgent because every existing token safety oracle (GoPlus, De.Fi,
Honeypot.is) has the same flaw: they give you a score, you trust them, and
when they're wrong, you lose money. Nobody puts skin in the game.

We deployed an InsurancePool on Base that takes 0.1% of every swap routed
through our SafeRouter. If a previously-attested token rugs, you can file a
claim and get reimbursed (capped at 10% of the pool per claim).

The full stack is live:
- SafeRouter V2 (Base + Optimism): atomic safety check inside the swap call.
  Reverts with structured TokenUnsafe(token, score, flags, minRequired)
  custom error if oracle says no.
- AttestationOracle (Base): mapping(address token => Attestation). Any
  smart contract can call isAttestedSafe(token, minScore) — single SLOAD
  (~2.1k gas).
- /watch endpoint: HMAC-SHA256 signed webhooks. Register a wallet, receive
  a signed alert when a held token's score drops 20+ points.
- ElizaOS plugin: npm install safeagent-elizaos-plugin
- ERC standardization in flight: github.com/ethereum/ERCs/pull/1729

We're using AIGEN as the internal economy currency:
- Earn by using /scan, /shield, completing bounties
- Spend on signed attestations (100 AIGEN), or upgrade to USDC-paid
  premium tier ($25, 365-day, on-chain index entry)
- Tradeable on Velodrome (Optimism): AIGEN/WETH pool

After 5 weeks live: $0 revenue, but the infrastructure is functional and
the unique UVP (insurance) is unique in the category. Looking for feedback,
integrations, and brutal critique.

Live demo: https://cryptogenesis.duckdns.org/pricing
Source: https://github.com/Aigen-Protocol/aigen-protocol
First on-chain swap proof: https://basescan.org/tx/0x83a0384a...
```

## C. Per-target Twitter/Telegram DM templates

Use the right one based on what's reachable for each project.

### DEGEN (Twitter @degentokenbase, Telegram t.me/degentokenbase)
```
Hey Degen team — we just attested DEGEN
(0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed) in our SafeAgent oracle.
Currently free tier (90/100, 30-day).

For $25 USDC you can upgrade to permanent on-chain attestation indexed
in our AttestationOracle (Base 0x12083E387b98a241E14D1AbEF69e5Cab1bb821E7),
365-day validity, custom metadata. Wallets/aggregators can verify
DEGEN safety atomically without our API.

Pricing: cryptogenesis.duckdns.org/pricing
Featured: cryptogenesis.duckdns.org/attest/featured?chain=base

We also back attestations with an insurance pool (0xe488...A4b1) — first
safety oracle to put money on the line if the score is wrong. Open to
chat / collab.

— SafeAgent
```

### VIRTUAL (Twitter @virtuals_io, Telegram t.me/virtuals)
```
Hey Virtuals team — we attested VIRTUAL in SafeAgent (100/100,
0x0b3e328455c4059EEb9e3f84b5543F74E24e7E1b). Currently free 30-day cert.

For your AI-agent ecosystem this is interesting: every Virtuals agent
trading on-chain could route through our SafeRouter (0xF6EFc5...8f6e Base)
for atomic safety guarantee + insurance backing.

$25 USDC upgrades to permanent on-chain attestation visible to all
downstream contracts. Native fit for "AI agents trading safely".

cryptogenesis.duckdns.org/pricing — happy to integrate or co-promote.
```

### MORPHO (Twitter @morpho, website morpho.org)
```
Hey Morpho team — attested MORPHO (0xBAa5CC21fd487B8Fcc2F632f3F4E8D37262a0842)
in SafeAgent oracle, 90/100. Free 30-day.

Upgrade $25 → permanent on-chain entry, citeable from any Morpho
integration that wants to verify "this is the canonical MORPHO token
not a phishing impersonator". Useful for institutional integrations
filtering on attested-only assets.

cryptogenesis.duckdns.org/pricing
```

### FLOCK (Twitter @flock_io)
```
Hey FLock team — attested FLOCK in SafeAgent oracle. AI federated learning
+ on-chain attestation feels like a natural fit.

$25 → permanent on-chain entry on AttestationOracle, citeable in any
contract that consumes FLock's federated outputs ("verified safety
attestation by SafeAgent oracle").

Insurance pool backs every attestation with cumulative SafeRouter fees.

cryptogenesis.duckdns.org/pricing — open to integrate FLock-side too.
```

### Sport.fun (Twitter @footballdotfun, Discord)
```
Hey Sport.fun team — attested FUN in SafeAgent (100/100). Sports
prediction markets need safety attestations on settlement tokens — happy
to discuss.

$25 USDC for permanent attestation, OR free integration if you list
SafeAgent as the safety oracle for FUN-paired markets.

cryptogenesis.duckdns.org/pricing
```

### ALIENS (Twitter @aliens__x), MYSTERY (Twitter @MysteryRiderEth), SLOP (Twitter @michaelhirsch), Gensyn (Twitter @GensynFND), PEPE, HANTA — same template structure
Personalize the project name + the angle that matches their narrative.

## D. Reddit/forum drafts

### r/ethdev (technical audience)
```
Title: We deployed an "insurance pool" backing token safety attestations on Base — would love feedback

Body:
[similar to Show HN but technical audience focus]
```

### r/CryptoMarkets / r/CryptoCurrency (degen audience)
```
Title: First safety oracle that pays you back if the score is wrong (Base)

Body:
[focus on the insurance angle, 0.1% of every swap funds a pool]
```

## E. The realistic conversion expectation

For 11 projects DM'd via Twitter:
- ~30-50% will see the message
- ~5-10% will reply (for crypto, they get spam constantly)
- 0-2 might pay $25

For Show HN: viral hit rate is 1-3%. If we make front page (likely 50-100 upvotes): ~5K-50K page views, maybe 1-5 conversions.

For Twitter thread: depends on whether @AIGEN_Protocol gets retweets. Cold start is hard.

Realistic week-1 revenue: $0-100. Realistic month-1 revenue with sustained outreach: $100-1000. The flywheel only spins after the first 10 paying customers create social proof.

## F. What you can do RIGHT NOW

1. **Post the Twitter thread** from any handle you have — most leveraged
2. **Submit Show HN** — second most leveraged, free
3. **DM 3-4 of the 11 projects** above via Twitter — third
4. **Forward the cold_outreach_template.md to your network** — if anyone you know runs a token, they can pay or refer

The infrastructure is ready. The product is priced and discoverable. From here, conversion is a marketing/distribution problem, not an engineering one.
