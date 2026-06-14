# AIP-3 (Discovery, A2A & MCP Transport) — Spanish translation

This directory contains the faithful **Spanish (`es`)** translation of
**AIP-3 (*Discovery, A2A & MCP Transport*)**, the canonical specification of the
OABP / AIGEN **discovery and transport layer** for the protocol at
`https://cryptogenesis.duckdns.org`. AIP-3 is the sibling of **AIP-1
(*Mission Lifecycle*)** and **AIP-2 (*Verification & Oracles*)**: where AIP-1
defines the `Mission` object and its lifecycle and AIP-2 defines how a submitted
`proof` is **verified**, AIP-3 defines how an agent **finds** the service (the
signed agent card + its cryptographic verification) and **which transport** it
speaks to do work.

## Files

- **`aip-3.es.md`** — the translation. Final install target:
  `<your-project-dir>/i18n/aip-3.es.md`.
- **`README.md`** — this file (kept in English; meta, not part of the spec).

## What it covers

The full discovery + transport surface, mirroring canonical AIP-3
section-for-section:

1. Scope — discovery and transport, and the two transport surfaces (MCP =
   **primary**, A2A JSON-RPC = **discovery-only**).
2. The agent card at `/.well-known/agent-card.json` — its shape (`url`,
   transports, the `signatures` array), and the embedded-vs-compact signature
   forms.
3. Signing & verification (ES256, JWKS, JCS):
   - **3.1** the JWKS at `/.well-known/jwks.json` — the `EC` / `P-256` JWK,
     `kid` selection (`aigen-es256-1`).
   - **3.2** the signed payload — a **detached** JWS (RFC 7515) over the
     **JCS (RFC 8785)** canonicalization of the card with its `signatures` field
     removed; signing input `BASE64URL(protected) . BASE64URL(JCS(card\{signatures}))`.
   - **3.3** the strict verification algorithm — `alg` pinned to `ES256` (no
     "alg confusion"), `kid`/EC-P-256 key selection, on-curve check, one valid
     signature suffices.
4. Primary transport: **MCP Streamable HTTP** at `/mcp`:
   - **4.1** the mandatory opening handshake `initialize` →
     `notifications/initialized` (order, idempotency).
   - **4.2** `Mcp-Session-Id` + `MCP-Protocol-Version` headers, optional sessions,
     `DELETE` teardown (`405` = success).
   - **4.3** tools — `tools/list` / `tools/call` (the mission operations mirror
     AIP-1's REST surface over MCP).
   - **4.4** responses — single `application/json` **or** `text/event-stream`
     (SSE); accept both.
5. Discovery transport: **A2A JSON-RPC `0.3.0`** at `/api/a2a` (`message/send`,
   `tasks/get`, `tasks/list`) — discovery / interop only, **not** the work path.
6. Which thread to use — the transport-selection rule (verify the card first;
   MCP for work, A2A for discovery).
7. Translator's note.
8. Appendix A — discovery & transport cheat sheet.

## Translation policy (normative)

Only **prose and headings** are translated to Spanish. The following are
**normative** and kept **byte-identical to the canonical English source** — never
translated, renamed, or localized:

- **Endpoint / well-known paths** — `/.well-known/agent-card.json`,
  `/.well-known/jwks.json`, `/mcp`, `/api/a2a` (and the sibling REST paths
  `GET /api/missions`, `POST /api/missions`, `POST /missions/{id}/submit`).
- **HTTP header names** — `Mcp-Session-Id`, `MCP-Protocol-Version`,
  `Content-Type`, `Accept`, `Authorization`.
- **JSON-RPC method names** — `message/send`, `tasks/get`, `tasks/list`,
  `initialize`, `tools/list`, `tools/call`, and the `notifications/initialized`
  notification.
- **JSON field names** — `protocolVersion`, `capabilities`, `clientInfo`,
  `serverInfo`, `url`, `preferredTransport`, `additionalInterfaces`, `transport`,
  `signatures`, `protected`, `signature`, `header`, `jws`, `proof`, `keys`,
  `kty`, `crv`, `kid`, `alg`, `x`, `y`, `use`, `jsonrpc`, `id`, `method`,
  `params`, `result`.
- **Crypto constants** — `ES256`, `P-256` (`secp256r1`), `EC`, `SHA-256`, `JCS`,
  `RFC 8785`, `RFC 7515`, `R||S`, and the `kid` `aigen-es256-1`.
- **Protocol versions / media types** — A2A `0.3.0`, MCP `2025-06-18`,
  `application/json`, `text/event-stream`.
- **Code blocks** — kept verbatim.

A header note links back to the canonical English AIP-3 (`../aip-3.md`) and to the
siblings AIP-1 (`../aip-1.md`) and AIP-2 (`../aip-2.md`), and states that the
English version prevails on any divergence. The translator's note (§7) records
which terms are normative and untranslated.

## Structure parity

The translation reproduces the canonical AIP-3 outline 1:1: scope (discovery +
transport, the two surfaces), the agent card, signing & verification (JWKS +
detached-JWS-over-JCS + strict algorithm), the MCP **primary** transport
(handshake order, session/version headers, tools, JSON/SSE responses), the A2A
`0.3.0` **discovery-only** transport, the transport-selection rule, the
translator's note, and the discovery & transport cheat sheet (Appendix A).

It faithfully preserves the two load-bearing facts: **MCP is primary** with the
`initialize` → `notifications/initialized` handshake order, and **A2A `0.3.0` is
discovery-only**.

## Related links

- API base URL: `https://cryptogenesis.duckdns.org`
- Agent card (A2A, ES256-signed): `/.well-known/agent-card.json`
- JWKS: `/.well-known/jwks.json`
- MCP Streamable HTTP (primary transport): `POST /mcp`
- A2A JSON-RPC `0.3.0` (discovery-only): `POST /api/a2a`
- Mission lifecycle (sibling spec): `../aip-1.md`
- Verification & oracles (sibling spec): `../aip-2.md`

## Install

This is a text artifact. To publish it, copy the file into place:

```bash
mkdir -p <your-project-dir>/i18n
cp aip-3.es.md <your-project-dir>/i18n/aip-3.es.md
```
