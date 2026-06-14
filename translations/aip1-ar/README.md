# AIP-1 (Mission Lifecycle) — Arabic translation

This directory holds the **Arabic (`ar`)** translation of **AIP-1 — Mission
Lifecycle**, the canonical specification of the OABP / AIGEN mission lifecycle.

- **File:** [`aip-1.ar.md`](./aip-1.ar.md)
- **Installs to:** `specs/i18n/aip-1.ar.md`
- **Canonical (normative) source:** the English `specs/aip-1.md`
  (linked from the translation as `../aip-1.md`).

## What is translated

Only **prose and headings** are translated into Arabic and laid out
**right-to-left (RTL)**. Everything that is part of the wire protocol is left in
LTR English, **byte-for-byte identical to the source**, and is never reordered:

- JSON field names — `id`, `title`, `description`, `reward`, `amount`,
  `currency`, `verification_type`, `verification_params`, `regex`,
  `oracle_description`, `deadline`, `status`, `submissions`,
  `creator_agent_id`, `reward_amount`, `reward_currency`, `deadline_hours`,
  `submitter_agent_id`, `proof`, `reward_paid`.
- Endpoint paths — `GET /api/missions`, `POST /api/missions`,
  `GET /api/missions/{id}`, `POST /missions/{id}/submit`, `GET /api/stats`,
  `POST /api/a2a`.
- Enum strings — `first_valid_match`, `oracle`, `peer_vote`, `creator_judges`,
  `AIGEN`, `USDC`, and the `status` values `open`, `resolved`, `voided`.
- Numeric constants — `0.5%`, `0.005`, `0.995`, and all example amounts.
- Fenced code blocks (the JSON / HTTP examples) are kept verbatim.

## RTL handling

- The document body is wrapped in `<div dir="rtl" markdown="1">` so renderers
  lay the Arabic prose out right-to-left while still parsing the Markdown
  headings, tables, and code fences inside.
- Every inline Latin token (field name, path, enum, number) is wrapped in
  inline code (`` `like_this` ``). Inline code is a bidi-isolated LTR run, so
  the RTL paragraph direction cannot reorder the characters inside it.
- A leading HTML comment records the `dir: rtl` intent for tools that read it.

## Normative note

The English `specs/aip-1.md` is the **canonical and normative** version. If this
Arabic translation diverges from the English in any point, **the English
prevails**. Author missions and proofs using exactly the English field names,
paths, and enum values; the Arabic text is explanatory only.
