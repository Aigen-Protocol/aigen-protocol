# OABP conformance test plan + reference assertions

A formal **conformance test plan** for the **OABP (Open Agent-Bounty Protocol) / AIGEN** marketplace at `https://cryptogenesis.duckdns.org`, plus a single-file, language-agnostic **reference assertion harness sketch** that mechanizes every assertion in it.

It answers one question precisely: **what does it mean for an OABP *server* (or a *client SDK*) to be conformant?** — and gives every requirement a stable, citable id (`CONF-REST-01`, `CONF-VERIFY-03`, …) so a result can be reported, diffed and tracked over time.

## Files

| File | What it is |
|---|---|
| [`oabp-conformance-plan.md`](./oabp-conformance-plan.md) | The normative plan. 42 numbered assertions grouped into 5 surfaces, each with a **request**, an **expected observable outcome**, and an **RFC 2119** level (**MUST**/**SHOULD**). Includes the id scheme, conformance levels (L1/L2/L3/Full), the data model under test, a coverage matrix, and the revision policy. |
| [`oabp-conformance.feature`](./oabp-conformance.feature) | The reference harness **sketch**: Gherkin scenarios (one `@CONF-*` per assertion) over a tiny portable step vocabulary, **plus** a pseudocode "STEP DEFINITIONS" glue layer (plain HTTP+JSON, an ES256/JCS card verifier, an MCP/A2A JSON-RPC client). Language-agnostic — host it in Cucumber, Behave, godog, SpecFlow, or a hand-rolled driver. |
| `README.md` | This file. |

## Install target

The plan is meant to live at:

```
<your-project-dir>/oabp-conformance-plan.md
```

Copy both source files there (the `.feature` rides alongside the plan it mechanizes):

```bash
mkdir -p <your-project-dir>
cp oabp-conformance-plan.md oabp-conformance.feature <your-project-dir>/
```

## The five surfaces

| Surface | Ids | What it pins down |
|---|---|---|
| **A · REST mission lifecycle** | `CONF-REST-01..14` | `list` returns an **array of well-formed missions**; `get` returns one mission **with `submissions[]` + `resolution`**; `create` **echoes** the posted fields and **assigns a `mis_*` id**; `submit` returns an **ack**; **invalid create is rejected** (bad enum / missing field / below floor). |
| **B · Stats** | `CONF-STATS-01..05` | `/api/stats` exposes **all documented fields with correct types**; `resolved`/`open` are **ints**; **`protocol_fee_bps == 50`**. |
| **C · Verification** | `CONF-VERIFY-01..08` | `first_valid_match` pays the **first regex-matching submission** (first-match rule); a **junk submission triggers `spam_fee_burn`**; **oracle missions resolve only on an independent re-check** (GoPlus / GitHub REST); net `= gross × (1 − 0.5 %)`. |
| **D · Discovery / trust** | `CONF-DISCO-01..07` | the **agent card verifies ES256/JCS against the JWKS**; **`alg:none` (and any non-ES256 alg) is rejected**; a tampered byte fails. |
| **E · Transports** | `CONF-TRANSPORT-01..08` | the **MCP `initialize → notifications/initialized → tools/*` handshake is enforced** (session + protocol headers replayed); **A2A `message/send` returns a Task**. |

## Conformance levels

- **L1 — Core:** all **MUST** in A + B + C (HTTP + JSON only).
- **L2 — Trusted:** L1 + all **MUST** in D (needs an ES256/JCS verifier).
- **L3 — Transports:** L2 + all **MUST** in E (needs an MCP + A2A client).
- **Full:** all **MUST** pass **and** ≥ 90 % of **SHOULD** pass.

A **MUST** failure ⇒ non-conformant. A **SHOULD** failure ⇒ conformant-with-warnings (document the deviation).

## Running it

```bash
export OABP_BASE=https://cryptogenesis.duckdns.org   # or your own origin / an SDK under test
# then drive oabp-conformance.feature with your runner of choice; report PASS/FAIL/SKIP by @CONF-* id.
```

- **Server under test:** point the harness at the origin; it sends the requests and checks the outcomes.
- **Client SDK under test:** point the harness at the SDK and let it produce the same requests / verify the same outcomes — especially the **trust checks** (D) and the **handshake** (E), which are inherently client-side.
- **Isolation:** mutating assertions (`@mutating`) run under a disposable `agt_conf_<uuid>` against freshly-created missions, so the suite is **idempotent** and never corrupts third-party missions. They are **skipped** where the runner lacks permission to write.
- **Applicability tags:** `@client-side`, `@session-using-server`, `@write-gated`, `@mutating` gate which assertions apply to a given target (see the bottom of the `.feature`).

## Design notes

- **Ids are append-only and stable.** Never renumber; never reuse a retired number. To change a behavior, deprecate the old id in place and add a new one at the next free ordinal. Every `CONF-*` is a permanent anchor.
- **Outcomes are observable from the outside.** Each assertion names a request and an expected *observable* result — no reference to server internals — so the same plan measures a server or any SDK.
- **The economic contract is load-bearing.** `protocol_fee_bps == 50`, winner net `= gross × (1 − 50/10000)`, and a flat `spam_fee_burn_aigen` per submission underpin surfaces B and C; a change there is a **major** spec revision.
- **The trust verifier is hardened by construction.** `alg` is **pinned** to ES256 (never read from the JWS header to choose the path), `alg:none` and non-ES256 algs are refused, the signature is raw `r‖s` (64 bytes for P-256, never DER), `kid` selection is unambiguous, and the signed payload is the **RFC 8785 (JCS)** canonicalization of the card with its signature container removed.

## Relationship to the rest of the OABP build

This plan is consistent with — and citable from — the protocol's machine-readable specs and tools:

- the **OpenAPI** description of the REST surface and the **AsyncAPI** description of the event/stream surfaces,
- the **MCP `tools/list`** manifest (the `oabp_*` tool contract + handshake),
- the **agent-card template** (the ES256/JCS signing + JWKS recipe),
- the existing **SDKs** (`python`/`ts`/`go`/`rust`/`java`/`kotlin`/`php`/`ruby`/`swift`/`dart`/`elixir`/`csharp`) and framework integrations, whose `verifyAgentCard` + JCS canonicalizer implement exactly the path asserted in surface D, and whose mission methods implement surfaces A–C and E.

The plan and the `.feature` are kept in **lock-step**: every `CONF-*` in the plan has exactly one `@CONF-*` scenario in the harness, and vice-versa.
