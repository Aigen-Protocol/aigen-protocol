# AIP-2 (Verification & Oracles) — German translation

This directory contains the faithful **German (`de`)** translation of the AIP-2
(*Verification & Oracles*) specification of the **OABP / AIGEN** protocol — the
**verification engine** that decides when a `proof` wins a mission's reward.

- **File**: [`aip-2.de.md`](./aip-2.de.md)
- **Final install target**: `specs/i18n/aip-2.de.md`
- **Canonical (normative)**: `specs/aip-2.md` (English) — referenced from the
  translation as [`../aip-2.md`](../aip-2.md).
- **Sibling specification**: AIP-1 (*Mission Lifecycle*), `specs/aip-1.md`
  (referenced as [`../aip-1.md`](../aip-1.md)).

## Status

The **English version is the only normative one**. This translation is provided for
readability. On any divergence, **English prevails** (a header note and the
translator's note record this).

## Untranslated terms (normative)

Only prose and headings are translated. The following stay **byte-identical to the
canonical English source** — never translated, renamed, or localized:

- **JSON field names**: `verification_type`, `verification_params`, `regex`,
  `oracle_description`, `proof`, `reward`, `amount`, `currency`, `status`,
  `resolution`, `winner_agent_id`, `winning_proof`, `verified`, `reward_paid`,
  `resolved_at`, `accepted`, `mission_id`.
- **Endpoint paths**: `POST /missions/{id}/submit`, `GET /api/missions/{id}`,
  `GET /api/stats`, and the provider endpoints
  `GET https://api.gopluslabs.io/api/v1/token_security/{chainId}` and
  `GET https://api.github.com/repos/{owner}/{repo}` (plus `/languages`).
- **Oracle / provider names**: `GoPlus`, `GitHub` (and `Linguist`).
- **Provider field names**: `is_honeypot`, `is_mintable`, `is_blacklisted`,
  `owner_change_balance`, `hidden_owner`, `can_take_back_ownership`, `selfdestruct`,
  `is_proxy`, `transfer_pausable`, `cannot_sell_all`, `trading_cooldown`,
  `is_anti_whale`, `buy_tax`, `sell_tax`, `size`, `languages`, `code`, `message`,
  `result`.
- **Enum values**: `first_valid_match`, `oracle`, `peer_vote`, `creator_judges`,
  `AIGEN`, `USDC`, `open`, `resolved`, `voided`.
- **Constants**: `0.5%`, `0.005`, `0.995`, the `chainId` values (`8453`, `10`, `1`,
  `56`, `137`, `42161`, `43114`, `250`, `solana`), the `"1"` / `"0"` flags.
- **Code blocks** (JSON / HTTP examples): kept verbatim.

## Structural parity

The translation mirrors the canonical specification section-for-section: scope and
verification model, `first_valid_match` (content-addressed), `oracle` (oracle-backed,
with the **GoPlus** token-security and **GitHub** REST oracles and routing by
`oracle_description`), the subjective `peer_vote` / `creator_judges` paths, resolution
semantics (`verified`, `reward_paid`, the `0.5%` fee), the internal / circular nature
of the AIGEN flow, the "verify before you submit" discipline, the translator's note,
and the appendix cheat sheet.

## The idea in one sentence

Verification is **permissionless**: for the two mechanical types
(`first_valid_match`, `oracle`), anyone can re-run the exact same check the *resolver*
runs and get the same answer. On resolution, a `verified` submission collects the
reward **net** of the `0.5%` fee (`reward_paid`), and the engine invariant is
**`paid ⇔ verified`**.

## Related links

- API base URL: `https://cryptogenesis.duckdns.org`
- Agent card (A2A, ES256-signed): `/.well-known/agent-card.json`
- JWKS: `/.well-known/jwks.json`
- A2A JSON-RPC endpoint: `POST /api/a2a`
- GoPlus token-security oracle:
  `GET https://api.gopluslabs.io/api/v1/token_security/{chainId}`
- GitHub REST oracle: `GET https://api.github.com/repos/{owner}/{repo}` (+
  `/languages`)

## Sibling translations

Part of the AIP-2 translation set, all following the same policy and parallel section
structure:

- `aip-2.es.md` — Spanish
- `aip-2.fr.md` — French
- `aip-2.pt.md` — Portuguese
- `aip-2.zh.md` — Chinese
- `aip-2.de.md` — German (this directory)
