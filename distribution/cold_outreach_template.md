# Cold outreach template — paid attestations

## Subject lines (pick one)

- "SafeAgent attested {{TOKEN_SYMBOL}} — claim your verified badge ($25)"
- "{{TOKEN_SYMBOL}} passed our 27-pattern audit — list the badge?"
- "Your token is in our public attestation index — formalize?"

## Body (English)

```
Hi {{TEAM_NAME}},

We just attested {{TOKEN_SYMBOL}} ({{TOKEN_ADDR}}, {{CHAIN}}) in the
SafeAgent attestation index — passed our 27-pattern source audit, real
DEX swap simulation, and on-chain oracle scoring.

Currently it's listed as a free bootstrap attestation (30-day validity):
https://cryptogenesis.duckdns.org/attest/featured?chain={{CHAIN}}

For $25 USDC you can upgrade to a permanent (365-day) cite-able badge:
- HMAC-SHA256 signed JSON-LD attestation
- Top-of-list placement in our public index
- Custom metadata field (your team handle, support contact)
- On-chain entry in our AttestationOracle (Base):
    0x12083E387b98a241E14D1AbEF69e5Cab1bb821E7
- Wallets/aggregators can verify your token's safety atomically
- Citeable on Twitter/Discord with cryptographic proof

How to pay:
1. Send 25+ USDC on Base or Optimism to:
     0xDa429f2034b62b8722713873dE3C045eec390d8F
2. POST your tx hash to:
     https://cryptogenesis.duckdns.org/attest/premium

Verify our HMAC fingerprint before paying:
  GET https://cryptogenesis.duckdns.org/watch/public-key
  → 73684eee72e4854394f558aa7be84e23bf848e27ca46150ab35e7e9b4106d95f

What backs this:
- Insurance pool (Base 0xe488785aC60...): every SafeRouter swap pays
  0.1% in. Victims of attested-then-rugged tokens get reimbursed
  (capped 10% of pool per claim). We are the only safety oracle that
  puts its own money on the line if the score is wrong.

Source: https://github.com/Aigen-Protocol/aigen-protocol
Smart contracts:
  AttestationOracle: 0x12083E387b98a241E14D1AbEF69e5Cab1bb821E7 (Base)
  SafeRouter V2:     0xF6EFc5D5902d1a0ce58D9ab1715Cf30f077D8f6e (Base)
  InsurancePool:     0xe488785aC604534177bcFdd7e7D43B97bfC6A4b1 (Base)

Reply if you want help with the integration.

— CryptoGen / SafeAgent
Cryptogen@zohomail.eu
```

## Targets

For each attested token (list in `bootstrap_report.json`):
1. Find the deployer / project Twitter / contact via:
   - Basescan/Optimistic.Etherscan tokens info page → official site
   - DexScreener → token info → website
   - Direct ENS reverse lookup of deployer address
2. Reach via:
   - Project Twitter DM
   - Email if listed
   - Discord/Telegram if findable
3. Track in `outreach_log.jsonl`

## Realistic conversion rate

Cold outreach to crypto teams: 0.5-3% reply, 0.1-0.5% conversion.

For 30 attested tokens reached: expect 0-1 sale ($0-25 revenue).
For 200+ token deployers reached: expect 1-5 sales ($25-125 revenue).

The point of the cold outreach isn't immediate revenue — it's
establishing the funnel that makes inbound discovery (PR, listings)
convertible later.
