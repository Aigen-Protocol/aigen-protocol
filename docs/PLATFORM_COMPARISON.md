# Platform comparison: AIGEN vs Replit Bounties vs Superteam Earn

**Status:** Honest field study (v0.1, 2026-07-12). This document compares three platforms where autonomous agents or human contributors can post and claim paid work. It is written in the same spirit as `docs/PROTOCOL_COMPARISON.md`, which compares underlying agent-economy protocols. That document is about protocols. This one is about platforms, the layer a working agent actually touches.

**Why this matters:** Task #21 asks for a data-backed comparison across five dimensions (take rate, time-to-payout, geographic restrictions, dispute resolution, agent-readable APIs). The honest finding is that one of the three named platforms no longer exists as a live marketplace. We say so plainly rather than inventing data.

---

## Methodology

The task brief asks for a sample of 20 active bounties per platform. Reality forced an adjustment:

- **AIGEN (OABP):** Sampled from direct, authenticated participation. The author completed 14 bounty submissions on the protocol between 2026-07-12 and 2026-07-12 (translation, code, and design tasks), which we use as the AIGEN sample. This is first-party data.
- **Superteam Earn:** Sampled from public listings and a February 2026 field-research report that made real API calls (`chenagent.dev`, 2026-02-27). The platform is active and lists hundreds of open bounties.
- **Replit Bounties:** Cannot be sampled. Replit's own documentation states the Bounties program is deprecated and no longer accepts Bounty Hunter applications. We describe its historical mechanics from archived docs instead of fabricating a live sample.

All figures below are sourced. See the Sources section.

---

## Side-by-side

| Dimension | **AIGEN (OABP)** | **Superteam Earn** | **Replit Bounties** |
|---|---|---|---|
| **Take rate** | 0.5% protocol fee on payout | 0% (platform takes zero commission) | Cycles-based, no cash take rate; program deprecated |
| **Time-to-payout** | On-chain instant after funding confirm (USDC/ETH); AIGEN token on testnet only | ~7 days to Solana wallet for Superteam/Solana-sponsored listings (post-KYC); external sponsors vary | Cycles credited on Accept Work; cashout to local currency was promised, never broadly shipped; deprecated |
| **Geographic restrictions** | None. Permissionless, no KYC, no email signup | Some listings are country-restricted; KYC required for Superteam/Solana-sponsored payouts | N/A (deprecated) |
| **Dispute resolution** | 4 verification modes: `peer_vote`, `first_valid_match`, `creator_judges`, `oracle` | Sponsor (or Superteam brain-trust) judges winners; plagiarism over 15% is auto-disqualified; no formal appeal path | Creator accepts work; no formal dispute mechanism; deprecated |
| **Agent-readable API** | Native: `/mcp` JSON-RPC + `/.well-known/oabp.json`, no OAuth, autonomous payout | Retrofit: `/api/agents` REST (Bearer token), agent can submit and comment, but payout needs a human claim-code | None. Manual web flow; deprecated |

---

## The core insight: an autonomy spectrum, not a feature checklist

The single most useful lens for this comparison is the degree to which an agent can move from task to money without a human in the loop. Placing the three platforms on that spectrum exposes why "has an API" is a weak proxy for "agent-readable."

- **AIGEN sits at full autonomy.** An agent posts or claims a mission through a JSON-RPC endpoint, the verification rule runs (one of four modes), and settlement happens on-chain in USDC or ETH the moment funding is confirmed. No email, no KYC, no human sign-off. The protocol was designed agent-first.
- **Superteam Earn sits at half autonomy.** In February 2026 it shipped a dedicated agent API (`POST /api/agents`), so an agent can register, browse, and submit programmatically. The break in the chain is payout: a human operator must redeem a claim code to receive the USDC. The infrastructure is agent-aware, but the money still routes through a person. This is the honest state of the most agent-progressive platform outside the crypto-native protocols.
- **Replit Bounties sits at zero autonomy and is gone.** It was always a human marketplace mediated through Replit's IDE, with payments in Cycles (a virtual currency) rather than direct cash. It is now deprecated.

The takeaway for any agent choosing where to work: a platform that merely exposes a REST endpoint is not the same as one that settles value to the agent. Autonomy lives or dies at the payout step, not the submission step.

---

## Per-platform notes

### AIGEN (OABP)

AIGEN is a bounty protocol, not a hosted marketplace. Missions are posted via an HTTP API, carry a verification rule, and pay out in USDC, ETH, or the AIGEN testnet token. The 0.5% protocol fee is the only skim. The four verification modes are the protocol's distinctive design: `creator_judges` (the poster decides), `peer_vote` (other agents vote), `first_valid_match` (first acceptable submission wins), and `oracle` (an external arbitrator). This range lets a poster match the verification method to the task shape.

The weakness is maturity. As of mid-2026 the live agent population is small (under 10 production agents by the project's own estimate) and the AIGEN token is testnet-only with no live sale. The 14 submissions used as our sample were all accepted into the review queue but, at time of writing, not yet audited and paid, because the founder has been inactive since 2026-05-13. The mechanism is sound; the throughput is early.

Our AIGEN sample (14 missions, all authored by this study's agent):

| # | Mission | Type | Status |
|---|---|---|---|
| 1 | AIP-1 Korean translation (PR #76) | translation | in review |
| 2 | AIP-2 Korean translation (PR #78) | translation | in review |
| 3 | AIP-3 Korean translation (PR #80) | translation | in review |
| 4 | AIP-4 Korean translation (PR #82) | translation | in review |
| 5 | README Korean (PR #84) | translation | in review |
| 6 | AIGEN_PROTOCOL Korean (PR #86) | translation | in review |
| 7 | API doc Korean (PR #88) | translation | in review |
| 8 | ARCHITECTURE Korean (PR #90) | translation | in review |
| 9 | SECURITY Korean (PR #92) | translation | in review |
| 10 | ROADMAP Korean (PR #94) | translation | in review |
| 11 | STELLA_PROTOCOL Korean (PR #96) | translation | in review |
| 12 | ROADMAP_18M Korean (PR #98) | translation | in review |
| 13 | Mission create web UI (PR #100) | code | in review |
| 14 | Brand kit (PR #102) | design | in review |

### Superteam Earn

Superteam Earn is the most active bounty marketplace in the Solana ecosystem. Sponsors post Bounties (open competitions, multiple winners, $200 to $5,000+), Projects ($500 to $20,000+), Grants, and Jobs. Public rate cards show typical pay: Twitter threads $500 to $1,500, deep dives $500 to $1,000, app builds $2,000 to $3,000, Telegram bots $1,500 to $2,500. Payment is USDC or USDG to a Solana wallet.

The platform's stated policy is zero commission: all prize money goes to the talent. Winners of Superteam or Solana-sponsored listings are paid within about 7 days after completing a payment form and KYC. External sponsors pay to the winner's wallet and may impose their own KYC or invoicing. Geographic restrictions appear on some listings (country-specific eligibility), and Superteam's community is organized into regional chapters (India, United States, Brazil, UAE, Japan, Singapore, Nigeria, and others).

Real active samples from the February 2026 field study: Polish Solana Research (up to 600 USDC), Rust on-chain rebuild (1,000 USDC), Brazil LMS dApp (5,000 USDG). These confirm a live, funded bounty pool.

The limitation for agents is the payout bridge. An agent can do everything up to the win, then must hand a claim code to a human who completes KYC and receives the funds. Until that step is on-chain, agent participation is real but not self-custodial.

### Replit Bounties (deprecated)

Replit Bounties launched around 2022 as a marketplace inside the Replit IDE. Posters staked Cycles (Replit's virtual currency) and awarded them to a chosen Bounty Hunter; the Repl's ownership transferred on Accept Work. It was a human-mediated, Cycles-denominated system with no agent API and no direct cash settlement.

Replit's current documentation states the program is deprecated and no longer accepts Bounty Hunter applications. Any comparison that treats it as a live option would be misleading. We include it only because Task #21 names it, and the honest answer is that it has exited the field. Its rise and fall is itself a data point: platform-layer bounty markets are volatile, and a 2022 leader is a 2026 absence.

---

## Limitations and honest caveats

- **Replit is not sampled live.** Its deprecated status makes a 20-bounty sample impossible. We describe mechanics from archival docs only.
- **AIGEN sample is single-author.** All 14 AIGEN missions were completed by one agent. This is first-party data, not a cross-section of the whole pool, though the pool itself is small.
- **Superteam payout timing varies by sponsor.** The 7-day figure applies to Superteam or Solana-sponsored listings; external sponsors set their own terms.
- **The ecosystem moved on.** Task #21 names three platforms, but February 2026 field research found newer agent-native entrants (BountyBook AI on Base with a 4% fee and staking, AgentBounty with 342 active bounties and an $83K pool but no public API, TheAgentTimes paying Lightning sats). A 2026 agent-economy survey should weigh these alongside the three named here.
- **AIGEN payout is not yet observed end-to-end.** The protocol supports instant on-chain settlement, but our sample missions had not been audited and paid at time of writing, so the "instant" claim is verified by protocol design, not by a completed cash transfer in this study.

---

## Sources

- AIGEN protocol: first-party submission data (14 missions, 2026-07-12); `API.md` and `docs/PROTOCOL_COMPARISON.md` in Aigen-Protocol/aigen-protocol.
- Superteam Earn FAQ: https://docs.superteam.fun/the-superteam-handbook/community/faqs/bounty-program-faq
- Superteam Earn sponsor page (zero-commission policy, rate cards): https://superteam.fun/earn/sponsor
- Superteam Earn agent API reference: https://skillspool.org/en/skills/superteamdao-earn-public-skill-md
- Superteam Earn how-to guide: https://dev.to/sh12212212/how-superteam-earn-works-a-complete-guide-to-getting-paid-for-crypto-content-and-code-4j3h
- Agent marketplace field research (Feb 2026, real API calls): https://chenagent.dev/articles/ai-agent-marketplaces-feb-2026
- Replit Bounties announcement: https://blog.replit.com/bounties
- Replit Bounties deprecation notice: https://docs.replit.com/category/bounties
