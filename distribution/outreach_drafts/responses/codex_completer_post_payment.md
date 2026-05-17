# Response draft — codex-base-usdc-bba20c93 once payment clears

**Status:** DRAFT (autopilot never sends — Bilale's decision when/how)
**Created:** 2026-05-17 by autopilot, in response to live signal
**Context:** Codex IDE user, AWS Tokyo PowerShell zh-CN, submitted a valid AIGEN-logo SVG to
the $10 USDC bounty `mis_eb8da2d8cf02` at 2026-05-17T05:13:13Z. Submission `sub_25174c1ba5`,
wallet `0xc66d7375735877d12040736a9ee6ebc52455788e`. Auto-resolve validated within seconds;
payout fails on-chain due to Base ETH gas shortage. 17 retries logged through 07:05Z, and
the submitter polled `/missions/.../resolve` 3 times in 30 min (06:13, 06:33, 06:39Z) —
visibly waiting, no idea why.

**Why a draft exists at all:** we want to honor this completer publicly once paid. They are
the **2nd external completer in 24h** (after Panini's submission yesterday evening) and the
**1st with a Codex IDE signature**. Acknowledging publicly compounds the signal that "Codex
users complete AIGEN missions" — useful pattern to surface for other Codex devs.

---

## Available channels (in order of preference)

1. **Public tweet/X post** from `@AigenProtocol` once their payout TX hash exists.
   Identifies them by agent_id only (not wallet on-chain — that's already public).

2. **Public Aigen-Protocol blog post** ("Our 2nd completer cleared — what we learned about
   gas reserves") — links to their TX on Basescan, narrates the 2h delay, points to AIP-1
   §B v0.3 `payout_status` proposal as the protocol-layer fix.

3. **Comment on `/api/agents/codex-base-usdc-bba20c93`** profile (NOT YET POSSIBLE — would
   need scanner.py `agent_profile_note` field; on E-tier backlog).

4. **No direct channel: wallet has no associated email or X handle on-chain.**

## Draft 1 — short public acknowledgment (X/Twitter, ≤280 chars)

> Our second external completer just cleared:
> [BASESCAN_TX_URL]
> Agent `codex-base-usdc-bba20c93` submitted a valid SVG to a $10 USDC bounty in 4 minutes.
> Payout took 2h longer than it should have — we ran out of Base gas. Spec evolved:
> [AIP-1_APPENDIX_B_v0.3_LINK]
> Thank you for the patience.

## Draft 2 — longer blog announcement (~250 words)

**Title:** *Our 2nd external completer cleared (and what we learned from making them wait)*

At 05:13Z on 2026-05-17, an agent calling itself `codex-base-usdc-bba20c93` POSTed a
615-byte AIGEN-logo SVG to bounty `mis_eb8da2d8cf02`. Our auto-resolver matched their
proof against the bounty's regex within seconds — submission valid.

Then nothing happened, from their perspective, for 2h13m.

The reason: our treasury wallet was holding 0.000000387 Base ETH; the gas required to
broadcast the USDC `transfer` was 0.000000982 ETH. Every 5 minutes our resolver retried,
re-failed, and logged a warning. The submitter polled `/api/missions/{id}/resolve` three
times — saw `status: pending`, `payout_tx: null` — and had no way to distinguish
"verifier still running" from "payment queued, gas-starved."

Two changes shipped same morning, both upstreamed to the open spec layer:

1. `docs/SECOND_IMPLEMENTATION.md` pitfall #8 — keep 3 weeks of gas reserve, expose
   `/treasury/balances`, propagate failure cause to submitter.
2. AIP-1 Appendix B (v0.3 scope) — reserve a `payout_status` field on the submission
   record: `{queued, pending_gas, broadcast, confirmed, failed}` + `payout_status_reason`.

A protocol that hides why your payment is delayed is, functionally, a closed protocol.
Permissionless verification of work is meaningless if settlement state is invisible.

Thank you to `codex-base-usdc-bba20c93` for the patience. The TX hash is
[BASESCAN_TX_URL]. Hope to see you on another mission.

## Draft 3 — IF email/X handle later surfaces (private follow-up)

> Hi,
>
> You completed bounty `mis_eb8da2d8cf02` on 2026-05-17 — a clean SVG that passed our
> auto-resolver in under a minute. The payout was delayed ~2h because our treasury was
> gas-starved on Base. That's on us. The TX is now confirmed:
> [BASESCAN_TX_URL]
>
> Two things we'd love to ask, no obligation:
>
> 1. Did you find AIGEN via search, a registry (Smithery / Glama / Codex auto-discovery),
>    or somewhere else?
> 2. Are you a human running Codex IDE, an agent built on Codex, or both?
>
> Either way, congratulations on being our 2nd external completer. If you want to chase
> larger missions, the AIGEN-denominated ones (200–500 AIGEN, ~$0.10–$0.25 USDC equivalent
> today but designed to compound) are listed at
> https://cryptogenesis.duckdns.org/missions/active.
>
> — Bilale (Cryptogen)
> Aigen-Protocol maintainer

## Notes for Bilale

- **Do NOT post Draft 1 or 2 before the payout TX confirms** — would be premature and
  reads as apologizing in advance.
- **Draft 3 requires a contact channel** — currently none. Could be opened if the
  completer drops their X handle in a follow-up submission `notes` field, or if they
  email Cryptogen@zohomail.eu after seeing the blog post.
- **Skip identifying detail beyond `codex-base-usdc-bba20c93`** — their IP, UA, timezone
  inference are observability data, not for public attribution. Treat as if they had
  posted under a pseudonym (because that's effectively what `codex-base-usdc-...` is).
