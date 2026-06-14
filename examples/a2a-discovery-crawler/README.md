# OABP / AIGEN — A2A discovery crawler (fetch + verify agent cards)

A single-file agent that performs **A2A agent discovery with cryptographic
trust** against the [OABP / AIGEN](https://cryptogenesis.duckdns.org)
marketplace (or any other A2A endpoint). For each base URL it fetches the
well-known **agent card** and **JWKS**, then **cryptographically verifies the
card's ES256 / JWS signature** before printing what the agent advertises.

Dependencies: [`requests`](https://pypi.org/project/requests/) and
[`cryptography`](https://pypi.org/project/cryptography/). No OABP SDK import —
`a2a_discovery_crawler.py` is intentionally copy-pasteable.

---

## What it does

For every `--url` (default the OABP deployment) it:

1. `GET <origin>/.well-known/agent-card.json` — the A2A discovery card.
2. `GET <origin>/.well-known/jwks.json` — the signing public keys.
3. **Verifies** the card's ES256 / JWS signature against the JWKS
   (EC **P-256**, `kid` **`aigen-es256-1`** on the reference deployment).
4. Prints, per agent:

   | field | source |
   |-------|--------|
   | `name`, `version`, `url` | card identity / service URL |
   | `capabilities` | card transport capabilities |
   | `protocolVersion` | the A2A protocol version (`0.3.0`) |
   | `preferredTransport` | the primary A2A transport (`JSONRPC`) |
   | **MCP transport** | the declared MCP interface (`/mcp`) |
   | `skills` | number of advertised skills |
   | verdict | **`VERIFIED`** / **`INVALID`** / `SKIPPED` / `ERROR` |

---

## Discovery + trust model

A2A agents publish a self-describing **agent card** at
`<origin>/.well-known/agent-card.json` (identity, service URL, capabilities,
`protocolVersion`, the interfaces it exposes — A2A JSON-RPC at `/api/a2a` and an
**MCP** server at `/mcp` — and its skills). Discovery is **permissionless**:
anyone can fetch a card.

Because a card is just JSON over HTTP, its **authenticity** has to be proven
cryptographically rather than trusted on faith. The OABP card is signed with
**ES256** (ECDSA / NIST **P-256** / SHA-256); the *public* half of the signing
key is published as a **JWK** in the JWKS at `<origin>/.well-known/jwks.json`
(`kid` `aigen-es256-1`). The verifier reconstructs the exact bytes the signer
hashed, checks the ECDSA signature with the published public key, and only then
trusts the card.

The signed bytes are the **RFC 8785 (JCS)** canonicalization of the card
payload. JSON canonicalization removes every serialization degree of freedom
(key order, number formatting, whitespace, string escaping) so an independent
verifier reproduces the signer's bytes exactly. This file ships a **tiny in-file
JCS canonicalizer** (no external JCS dependency), validated against the RFC 8785
Appendix B vector in the self-test — and byte-for-byte equal to the reference
`oabp_a2a.jcs`, so a card signed by the OABP signer (`sign_card.py`) verifies
here unchanged.

### Card signature shapes accepted

| shape | wire form | signed payload |
|-------|-----------|----------------|
| **embedded detached JWS** | `signature` (or `jws`/`proof`) field = `BASE64URL(header)..BASE64URL(sig)` | `JCS(card)` minus the signature field (OABP `sign_card.py` form) |
| **full compact JWS** | the whole body is `header.payload.signature` | the decoded `payload` is the card JSON |
| **A2A `signatures[]`** | a `signatures` array of `{protected, signature, header?}` | `JCS(card)` minus the `signatures` field; VERIFIED if **any** entry verifies |

### Hardening (what the verifier refuses)

- **`alg` is pinned to ES256.** The algorithm is *never* read from the JWS
  header to decide how to verify — the classic **alg-confusion** attack. A
  header advertising `RS256`/`HS256`/anything-but-`ES256` is rejected.
- **`alg: none`** (the unsigned-token downgrade) is rejected.
- The JWK must be `kty=EC` / `crv=P-256`; coordinates must lie on the curve.
- A header `kid` MUST select a matching JWK; a missing `kid` only resolves when
  the JWKS holds exactly one EC key (an ambiguous set is rejected, never
  guessed).
- If a signer **inlines** the payload it MUST byte-equal our JCS of the stripped
  card; inlined bytes are never trusted blindly.
- The ECDSA signature must be the raw `R || S` (64 bytes for P-256); any other
  length is rejected before any curve math.

---

## Usage

```bash
# crawl the default OABP deployment, fetch + verify its card
python3 a2a_discovery_crawler.py

# crawl several agents (repeat --url)
python3 a2a_discovery_crawler.py \
    --url https://cryptogenesis.duckdns.org \
    --url https://another-a2a-agent.example

# machine-readable output
python3 a2a_discovery_crawler.py --json

# fetch + print WITHOUT verifying the signature (debugging an untrusted endpoint)
python3 a2a_discovery_crawler.py --insecure-skip-verify

# offline self-test (no network), then exit
python3 a2a_discovery_crawler.py --self-test
```

### CLI flags

| flag | default | description |
|------|---------|-------------|
| `--url BASE_URL` | `https://cryptogenesis.duckdns.org` | agent base URL to crawl (**repeatable**) |
| `--insecure-skip-verify` | **off** | fetch + print the card without verifying its signature (debug only; verdict `SKIPPED`) |
| `--json` | off | emit machine-readable JSON instead of a table |
| `--self-test` | — | run the offline self-test and exit |

---

## Example output

```
== A2A discovery crawl ==

[ VERIFIED ]  https://cryptogenesis.duckdns.org
    name             : AIGEN Protocol
    version          : 1.0.0
    url              : https://cryptogenesis.duckdns.org/api/a2a
    protocolVersion  : 0.3.0
    preferredTransport: JSONRPC
    MCP transport    : https://cryptogenesis.duckdns.org/mcp
    capabilities     : streaming, pushNotifications
    skills           : 3
    signed by kid    : aigen-es256-1

1/1 agent(s) trusted (VERIFIED, or SKIPPED with --insecure-skip-verify).
```

JSON (`--json`):

```json
[
  {
    "base_url": "https://cryptogenesis.duckdns.org",
    "name": "AIGEN Protocol",
    "version": "1.0.0",
    "url": "https://cryptogenesis.duckdns.org/api/a2a",
    "protocolVersion": "0.3.0",
    "preferredTransport": "JSONRPC",
    "mcpTransport": "https://cryptogenesis.duckdns.org/mcp",
    "capabilities": { "streaming": true, "pushNotifications": false },
    "skillsCount": 3,
    "kid": "aigen-es256-1",
    "verdict": "VERIFIED"
  }
]
```

---

## Exit codes

| code | meaning |
|------|---------|
| `0` | every crawled agent was `VERIFIED` (or `SKIPPED` with `--insecure-skip-verify`) |
| `1` | at least one agent was `INVALID` or could not be fetched (`ERROR`), but the crawl printed |
| `2` | usage / configuration error (e.g. a missing dependency) |
| `4` | the offline self-test failed |

---

## Self-test

`--self-test` runs a real-crypto, no-network check that mints an ephemeral
P-256 key (`kid` `aigen-es256-1`), signs a fixture card in the OABP embedded
detached-JWS form, and asserts:

- a clean card **VERIFIES** and surfaces `name='AIGEN Protocol'`, its `version`,
  and the MCP transport (`/mcp`);
- **tampering one byte** of the signed card flips the verdict to **`INVALID`**;
- an **`alg: none`** signature is rejected with a clear `alg` error;
- a non-ES256 **`alg` (alg-confusion)** header is rejected;
- the A2A **`signatures[]`** array shape also verifies;
- the in-file **JCS** canonicalizer matches the RFC 8785 Appendix B vector.

This makes the agent fail-closed: it cannot ship with a broken verifier or a
JCS canonicalizer that diverges from the signer.

---

## How it talks to the network

Two `GET` requests per agent, both read-only:

| call | purpose |
|------|---------|
| `GET /.well-known/agent-card.json` | the A2A discovery card (object or compact-JWS string) |
| `GET /.well-known/jwks.json` | the ES256 public keys used to verify the card |

The crawler never creates, submits, or mutates anything — it is pure discovery
and verification.
