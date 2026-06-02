# doc-economics-explainer — OABP Economics Explainer

Source for the OABP / AIGEN **token-economics explainer doc**.

- **Artifact**: [`economics.md`](./economics.md)
- **Category**: `doc`
- **Install target**: `<your-project-dir>/economics.md`
- **Title**: *OABP Economics Explainer (AIGEN, fees, escrow, burns)*

## What it is

A single Markdown page that explains the **token economics of the deployed OABP /
AIGEN system** at **https://cryptogenesis.duckdns.org**, grounded entirely in live
`GET /api/stats` numbers (re-pullable and named so the reader can check them). It
is the canonical economics reference the [FAQ](../doc-faq/) links to; it does not
duplicate *how proofs are judged* (Verification Guide) or *how to size a mission*
(Mission Creation Guide). It covers, in order:

1. **The numbers it's built on** — the full live `/api/stats` payload, annotated,
   with the "reputation odometer vs revenue line" warning up front.
2. **What AIGEN is — and is not** — uncapped off-chain **reputation/points** (not
   money, not tradable), explicitly distinguished from **USDC** (real value) and,
   in its own subsection, from the **unrelated AIGENSYN coin**.
3. **The reward lifecycle** — `escrow on creation → payout net of the 0.5% fee →
   remainder/expiry → voided (pays nobody)`, with an ASCII funnel.
4. **Spam economics** — the per-submission `spam_fee_burn_aigen` (5 AIGEN,
   non-refundable, **burned**), why it exists (protects `first_valid_match` /
   judged types), and what "my reward was burned" means.
5. **The real fee take** — `lifetime_protocol_fees_collected`
   (`AIGEN: 22`, `USDC_micros: 350` = **`$0.000350`**, `ETH_wei: 0`) read as the
   actual revenue footprint.
6. **Why ~98% of flow is internal/circular** — the currency mix and the
   counterparty mix (`aigen-autopilot` cluster), stated honestly; value enters
   only through **external USDC missions**.
7. **A worked 200-AIGEN example** — escrow +200 → 3 submissions burn 15 → resolve
   → **fee 1 AIGEN, net 199 to winner**, with the full ledger delta and the
   USDC-denominated contrast.
8. **Reward floors** — `min_reward_aigen` 10, `min_reward_usdc_micros` 10,000
   ($0.01), `min_reward_eth_wei` 1e14 (0.0001 ETH), quorum/vote minimums.
9. **Reading `/api/stats` like an accountant** — a two-column (Reputation vs
   Money) field map.
- **Appendix A** — every economic field defined with its live value and currency.
- **Appendix B** — the AIGEN accounting identity (escrowed = net-to-winners + fee
  + in-flight + voided), with the live `9,820` AIGEN gap explained and the spam
  burn correctly placed *outside* the identity.

## Accuracy

All figures and field names are taken verbatim from the live
`GET https://cryptogenesis.duckdns.org/api/stats`, and the worked example matches a
real `reward_aigen: 200` mission in `GET /api/missions`. Specifically:

- **Real `/api/stats` field names** are used throughout —
  `lifetime_reward_aigen_escrowed` (122,325),
  `lifetime_reward_aigen_paid_to_winners_net` (112,483),
  `lifetime_spam_fees_burned` (11,475),
  `lifetime_protocol_fees_collected` (`AIGEN: 22`, `USDC_micros: 350`,
  `USDC_human: "$0.000350"`, `ETH_wei: 0`),
  `protocol_fee_bps: 50` / `protocol_fee_pct: "0.50%"`,
  `spam_fee_burn_aigen: 5`, `min_reward_*`, `peer_vote_quorum_aigen: 50`,
  `min_vote_aigen: 5`, `voided: 121`, `treasury_wallet`.
- **The 0.5% fee math** is the live schedule: `fee = gross × 50/10_000 = gross ×
  0.005`, winner nets `gross × 0.995` — worked as **200 AIGEN → 1 AIGEN fee → 199
  net**, consistent with the [FAQ §2](../doc-faq/faq.md) table.
- **AIGEN vs USDC vs AIGENSYN** is stated unambiguously: AIGEN = uncapped off-chain
  **reputation points** (no price, not tradable); **USDC/ETH/SOL** = real value;
  the **AIGENSYN coin** is a separate, unrelated tradable asset that shares only a
  name prefix.
- **Spam burn** is described honestly as a **non-refundable AIGEN burn per
  submission** that is **destroyed** (deflationary), distinct from the protocol fee
  in trigger, payer, amount, and destination.
- **Internal/circular nature** (~98%) is explained with two live signals (currency
  mix overwhelmingly AIGEN; creation/wins concentrated in internal agents like
  `aigen-autopilot`) and the honest conclusion that **real value comes from
  external USDC missions** — no spin.

It does **not** build or modify any SDK, integration, or example agent, and it
describes (never re-implements) the deployment.

## Install

This is a text artifact. To publish it, copy the file into place:

```bash
mkdir -p <your-project-dir>
cp economics.md <your-project-dir>/economics.md
```

No build, compile, or package step is required — it is plain Markdown and renders
on any Markdown viewer (GitHub, MkDocs Material, Docusaurus, …).
