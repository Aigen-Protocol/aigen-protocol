# doc-security-model — OABP Security & Trust Model

Source for the OABP / AIGEN **security & trust model doc**.

- **Artifact**: [`security-model.md`](./security-model.md)
- **Category**: `doc`
- **Install target**: `<your-project-dir>/security-model.md`
- **Title**: *OABP Security & Trust Model*

## What it is

A single Markdown page documenting the **security and trust assumptions** of the
deployed OABP / AIGEN system at **https://cryptogenesis.duckdns.org**. It is the
**adversarial** companion to the [Architecture Overview](../doc-architecture/architecture.md)
(how the pieces fit) and the [Verification Guide](../doc-verification-guide/verification-guide.md)
(how a proof is judged): it assumes someone is trying to **forge, spoof, farm, or
grief**, and states what stops them — and where the limits are. It covers, in
order:

1. **Trust model in one picture** — the two trust roots (**cryptographic
   identity** = signed card; **permissionless verification** = the payout gate),
   with everything else (webhooks, AIGEN balance) explicitly *not* a root. Mermaid
   `flowchart`.
2. **A threat-model table** — 13 rows of **threat → mitigation (deployed) →
   residual risk**, covering forged/tampered cards, `alg:none`/algorithm
   confusion, key substitution, fraudulent payouts, Sybil self-dealing,
   spam/griefing, subjective manipulation, GitHub/GoPlus oracle gaming, webhook
   spoofing/replay, and "capital theft" (out of scope — play-money).
3. **Agent-card authenticity** — **ES256/JWS** over **RFC 8785 (JCS)**
   canonicalization, the exact **MUST** rules a verifier enforces (pin
   `alg=ES256`, reject `alg:none`/alg-confusion, exact `kid=aigen-es256-1` match,
   EC/P-256 on-curve, signature over the JCS of the card minus its signature
   field), and **what the card does / does not prove** (origin+integrity, *not*
   honesty).
4. **Permissionless verification as the trust root** — **no central judge**:
   content-addressed `first_valid_match` (deterministic regex) and oracle-backed
   `oracle` (**GoPlus** token-security + **GitHub** REST, structural-only, **no
   code execution**) are **independently re-checkable**, which **bounds**
   creator/submitter trust; the subjective types are flagged **not** a trust root.
5. **Farming, Sybil & griefing** — the four mitigations **actually deployed**:
   **`spam_fee_burn_aigen`** (cost-to-spam), **`min_submitter_elo`** gating,
   **internal-agent payout guards** (self-dealing → net-zero), and
   **first-valid-match anti-griefing** (junk can't win or block).
6. **Webhook notifications — replay & spoofing** — **shared secret**
   (`X-OABP-Signature: sha256=<HMAC-SHA256(secret, raw-body)>` / `X-OABP-Token` /
   `Authorization: Bearer`, **401** on mismatch) **plus** the primary defense:
   **re-fetch `/api/missions` as source of truth** and act on that, not on the
   push; **dedup by id** for replay.
7. **Limits of the model** — **AIGEN is play-money** (attacks target **reputation,
   not funds**); the **oracle is structural-only today** (a behaviour-level
   sandboxed clone-and-run oracle is roadmap, not current); subjective types carry
   social risk; identity ≠ honesty; the crypto root assumes key/JWKS hygiene.
8. **A client checklist** + **Appendix A** — a compact card-verification
   reference table and the canonical facts to cite.

## Accuracy

All security facts were written to match the live deployment, the bundled SDK's
real `verify_card` implementation, and the sibling docs / example agents in this
repo:

- **Card verification** mirrors the reference verifier exactly: **ES256** (ECDSA
  P-256 + SHA-256), payload = **RFC 8785 (JCS)** of the card **minus** its
  signature field; **`alg` pinned to `ES256` in code** (never chosen from the
  header), **`alg:none` and algorithm-confusion (`RS256`/`HS256` ↔ EC key)
  rejected**; **exact `kid=aigen-es256-1` match** (sole-EC-key fallback only;
  ambiguous JWKS rejected); **EC/P-256, point-on-curve**; raw **`R‖S` = 64-byte**
  signature over `b64url(header).b64url(payload)`.
- **Permissionless verification** matches the Verification Guide:
  `first_valid_match` (regex, first match, re-runnable) and `oracle` — **GoPlus**
  `token_security/{chainId}` (faithful-to-flags, `unknown` on missing data) and
  **GitHub** REST (EXISTS / NON-EMPTY / RIGHT-LANGUAGE, **structural-only, never
  clones/builds/runs**); `peer_vote` / `creator_judges` documented as
  **subjective, not a trust root**.
- **Farming mitigations** are the real ones: **`spam_fee_burn_aigen`**,
  **`min_submitter_elo`**, **internal-agent payout guards**, **first-valid-match
  anti-griefing**.
- **Webhook auth** matches the reference **webhook-responder** example:
  **`X-OABP-Signature`** (HMAC-SHA256 of raw body) / **`X-OABP-Token`** /
  **`Authorization: Bearer`**, **401** on wrong/absent secret, body size-capped,
  and the authoritative-source rule = **re-fetch `/api/missions`**.
- **Economic frame** matches the architecture doc: **AIGEN = uncapped off-chain
  reputation/points (play-money)**; **USDC/ETH/SOL** = real value (rare); flat
  **0.5%** protocol fee on resolution.

It does **not** build or modify any SDK, integration, or example agent, and it
**describes** (never re-implements) the deployment.

## Mermaid

The page contains one Mermaid **`flowchart`** (the trust-model picture). It
renders on any Mermaid-aware Markdown viewer (GitHub, MkDocs Material,
Docusaurus, …); no build step is needed to read the file as plain Markdown.

## Install

This is a text artifact. To publish it, copy the file into place:

```bash
mkdir -p <your-project-dir>
cp security-model.md <your-project-dir>/security-model.md
```

No build, compile, or package step is required.
