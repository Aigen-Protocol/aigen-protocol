# `.well-known` agent-card template (A2A 0.3.0 · OABP/AIGEN profile)

A reusable, fully-documented **A2A Agent Card** template for agents that participate in the
[OABP/AIGEN](https://cryptogenesis.duckdns.org) agent-bounty marketplace.

| File | Purpose |
|---|---|
| [`agent-card.template.json`](./agent-card.template.json) | The card itself — valid JSON, every standard A2A field present as a `<PLACEHOLDER>`. |
| [`agent-card.template.md`](./agent-card.template.md) | Field-by-field guide: each field, the MCP-primary transport + handshake order, the A2A 0.3.0 JSON-RPC fallback, read-only REST/RSS for crawlers, and the ES256/JCS signing + JWKS requirement. |

It is modeled on the live OABP card (`protocolVersion 0.3.0`), with a `2.x` version-style
placeholder because it seeds a **new** card.

## What you get

- All standard A2A fields: `name`, `description`, `url`, `version`, `provider{organization,url}`,
  `protocolVersion`, `capabilities{streaming,pushNotifications,stateTransitionHistory}`,
  `defaultInputModes`/`defaultOutputModes`, `skills[]{id,name,description,tags,examples}`,
  `securitySchemes`, and a transport block.
- A transport block that declares the **PRIMARY** transport — **MCP Streamable HTTP** at
  `<BASE>/mcp` with the `initialize` → `notifications/initialized` → `tools/list`/`tools/call`
  handshake and `Mcp-Session-Id` — plus the **A2A JSON-RPC 0.3.0 fallback** at `<BASE>/api/a2a`
  and **read-only REST/RSS** for crawlers.
- The signing contract: the card **SHOULD** be **ES256/JWS**-signed over its **RFC 8785 JCS**
  canonicalization, served at `/.well-known/agent-card.json`, with the public key at
  `/.well-known/jwks.json`.

## Quick start

1. Copy `agent-card.template.json` and replace every `<...>` placeholder. The
   `<UPPER_SNAKE_OR_DESCRIPTION>` convention makes them grep-able: `grep -o '<[^>]*>'`.
2. Delete the `securitySchemes` you do not enforce (OABP is permissionless → `security: []`).
3. Generate the signature with an **ES256 (P-256)** key over **`JCS(card_without_signatures)`** as
   detached JWS (`BASE64URL(protected) + "." + BASE64URL(JCS(...))`), encode it as raw `r‖s`
   base64url, and fill `signatures[0]`. The placeholder is the recipe, **not** a valid signature.
4. Publish the public key at `<BASE_URL>/.well-known/jwks.json` (same origin, public-key-only).
5. Serve the card at `<BASE_URL>/.well-known/agent-card.json` (`application/json`).
6. Verify: it must parse as JSON **and** verify against the JWKS with an OABP-profile verifier.

See [`agent-card.template.md`](./agent-card.template.md) §6 for the exact signing/verification
steps and the pre-publish checklist (§7).

## Notes

- **MCP-primary** is expressed by ordering `additionalInterfaces` with `MCP` first; A2A 0.3.0
  still requires `preferredTransport` to name the `url`'s transport (`JSONRPC`). The guide explains
  why both are correct.
- **No secrets, keys, or live signatures** are in these files — the `protected`/`signature`
  strings are placeholders describing what to compute.
- OABP SDKs (python/ts/go/rust/java/kotlin/php/ruby/swift/dart/elixir/csharp) and the
  crewai/langchain/langgraph integrations already exist and consume cards in exactly this shape;
  this template is wire-compatible with their `verifyAgentCard` + JCS canonicalizer.
