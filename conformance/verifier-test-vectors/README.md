<!--
  OABP / AIGEN — Verifier test vectors
  Install target: <your-project-dir>/verifier-test-vectors.json
  Category: test-conformance
  Reference deployment: https://cryptogenesis.duckdns.org
-->

# Verifier test vectors (`first_valid_match` + JCS/ES256 card)

A **language-neutral, frozen** set of test vectors that any OABP / AIGEN
verification implementation can run to prove it is correct. There are two
families of verifier in the protocol, and this file pins golden inputs/outputs
for both:

1. **Content-addressed verification** (`first_valid_match`) — the resolver
   decides whether a submitted `proof` wins a mission by matching it against the
   mission's published **regex**. The `first_valid_match` section gives regex /
   proof / expected-boolean triples a correct verifier (and any regex sampler or
   fuzzer used to cross-check it) **must** agree on.
2. **Agent-card signature verification** (AIP-3 discovery) — the card served at
   `/.well-known/agent-card.json` is integrity-protected by a **detached
   ES256/JWS** computed over the **RFC 8785 (JCS)** canonical form of the card.
   The `agent_card_signature` section pins a sample card, its exact canonical
   bytes, a P-256 public JWK, a **valid** signature, and a battery of
   **malformed** cases that must all be rejected — plus standalone JCS
   canonicalization sub-vectors.

Everything here is deterministic and reproducible. ECDSA verification is
deterministic, so the valid signature validates byte-for-byte on every machine,
in every language; JCS is a pure function, so the canonical strings are fixed;
regex full-matching is a pure function of `(regex, proof)`. **A conformant
implementation produces exactly the `expected_*` value for every case.**

> `AIGEN` is an uncapped off-chain reputation/points token; nothing in these
> vectors moves real value. They test cryptographic and matching **correctness**
> only.

---

## Files

| File | What it is |
|---|---|
| [`verifier-test-vectors.json`](./verifier-test-vectors.json) | The vectors. The single source of truth; load this from your test suite. |
| [`run_vectors.py`](./run_vectors.py) | A self-contained **reference runner** (Python stdlib + `cryptography`). Proves the vectors run and shows exactly how each check is performed; port it to your language. |
| `README.md` | This document. |

---

## File layout (`verifier-test-vectors.json`)

```
{
  "first_valid_match": {
    "match_semantics": "fullmatch",          // proof wins iff the WHOLE string matches
    "cases": [ { id, group, regex, proof, expected_match, note, requires? }, … ]
  },
  "agent_card_signature": {
    "signing_input_convention": "BASE64URL(protected) + '.' + BASE64URL(JCS(card_without_signatures))",
    "allowed_algorithms": ["ES256"],
    "jwks":      { "document": { "keys": [ <P-256 public JWK> ] } },
    "payload":   { "card_without_signatures": {…}, "full_served_card": {…} },
    "canonical": { "jcs_string", "jcs_hex", "jcs_byte_length", "payload_b64url" },
    "valid":     { protected, signature, signing_input_ascii, expected_verify: true },
    "malformed": { "cases": [ { id, attack, protected, payload_b64url, signature,
                                verify_with, verification_jwk?, expected_verify: false }, … ] },
    "jcs_conformance": { "cases": [ { id, property, input, expected_jcs, expected_jcs_hex }, … ] }
  }
}
```

---

## Section 1 — `first_valid_match` (content-addressed)

### The contract under test

The OABP resolver treats `verification_params.regex` as the **complete**
predicate on a submission's `proof`: a proof is valid **iff the entire proof
string matches the regex** (anchored / full-string match). There is no substring
acceptance, no length heuristic, no semantic parsing — just the boolean
`fullmatch(regex, proof)`. (Which submission *wins* is then "first valid match in
arrival order"; these vectors test the per-proof boolean that decision is built
on.)

All `regex` values in this section are written **already anchored** with `^…$`,
so "full match" and "anchored search" coincide and the vectors are unambiguous
across engines.

### How to evaluate a case in your language

For each case, compute `is_match` and assert `is_match == expected_match`:

| Language / engine | Full-string match expression |
|---|---|
| Python | `re.fullmatch(regex, proof) is not None` |
| JavaScript / TypeScript | `new RegExp('^(?:' + regex + ')$').test(proof)` *(regex is already anchored; the extra `^(?:…)$` is harmless and makes intent explicit)* — or `new RegExp(regex).test(proof)` since the patterns carry their own anchors |
| Go (RE2) | `regexp.MustCompile(regex).MatchString(proof)` *(patterns are anchored; for an unanchored regex you would wrap as `^(?:…)$`)* |
| Rust (`regex` crate) | `Regex::new(regex)?.is_match(proof)` |
| Java | `Pattern.compile(regex).matcher(proof).matches()` |
| PCRE / PHP | `preg_match('/^(?:' . $regex . ')$/u', $proof) === 1` |

### Coverage (≥ 12 cases; this file ships 31)

`anchors`, `char-class` (incl. negated `[^…]`), `shorthand-class`
(`\d` / `\w` / `\s`), `quantifier` (`?` `*` `+` `{m,n}`), `alternation`,
`empty-string` edges (`^$`, `\d+` vs empty, `.*` vs empty), realistic OABP proof
shapes (EVM address, 32-byte tx hash, GitHub repo URL, ISO date, reward
currency), and three intentionally **unsatisfiable** patterns:

- `^a$ and ^b$` — reads like a contradiction, and as a regex it is: the literal
  `" and "` (with interior anchors) means **no** string can full-match it →
  `false`. A correct content-addressed verifier and a regex *sampler* (which
  tries to generate a satisfying string and fails) agree.
- `^a^` — after consuming `a`, the second `^` re-asserts start-of-string, which
  can never hold → never matches.
- `^(?!x)x$` — a negative lookahead forbids the very `x` the pattern then
  requires → unsatisfiable.

### Engine portability

Every case carries an `engines_safe` list. **All but one** case use a portable
subset (POSIX-ish + `\d\w\s` + `{m,n}`) that compiles identically on PCRE,
ECMAScript, Python, **and RE2** (Go `regexp`, Rust `regex`). The single
exception, `fvm-unsat-empty-required-char`, uses **lookaround** and is tagged:

```json
"requires": ["lookahead"]
```

RE2-based runners (Go, Rust) **cannot compile** lookaround and **MUST SKIP** any
case whose `requires` they do not support — *skip, do not fail*. PCRE / ECMAScript
/ Python runners run it. (The reference runner probes its own engine and skips
automatically.)

---

## Section 2 — `agent_card_signature` (JCS + ES256)

### The contract under test

A served agent card carries one or more **detached JWS** signatures in
`signatures[]`. The signing input is the A2A / RFC 7515 detached-JWS convention:

```
signing_input = BASE64URL(protected) + '.' + BASE64URL( JCS( card \ {signatures} ) )
```

i.e. take the card **with its `signatures` field removed**, canonicalize it with
**RFC 8785 (JCS)**, base64url that as the JWS payload, and ECDSA-P256/SHA-256
verify each signature against the public key from the JWKS. A card is
**verified** iff **at least one** signature verifies **and** its protected `alg`
is in the allow-list `["ES256"]`.

The JWS **signature is the raw 64-byte `r‖s`**, base64url (no padding) — **not**
ASN.1/DER. (If your crypto library hands you DER, convert: split into the two
32-byte big-endian integers `r`, `s`.)

### Verifying the **valid** vector — step by step

1. Take `agent_card_signature.payload.card_without_signatures`.
2. JCS-canonicalize it. The result **must** equal
   `agent_card_signature.canonical.jcs_string` (and its UTF-8 hex must equal
   `canonical.jcs_hex`, length `canonical.jcs_byte_length` = 169). If it does
   not, your JCS is wrong — fix that first.
3. `payload_b64 = base64url(utf8(jcs_string))` — must equal
   `canonical.payload_b64url`.
4. Build `signing_input = valid.protected + "." + payload_b64` (this is also
   pinned verbatim as `valid.signing_input_ascii`).
5. Resolve the key from `jwks.document.keys[…]` by the `kid` in the decoded
   protected header (`{"alg":"ES256","kid":"vSEx1EvN-…"}`).
6. ECDSA-P256/SHA-256 verify `valid.signature` (raw `r‖s`) over `signing_input`.
   → **`expected_verify: true`**.

### The **malformed** cases (all `expected_verify: false`)

Each isolates one failure mode; a conformant verifier rejects every one. Note
that two of them are *not* signature-math failures — they are **policy**
rejections your verifier must make **before** trusting any bytes:

| `id` | `attack` | Why it must be rejected |
|---|---|---|
| `card-malformed-tampered-payload` | `tampered-byte` | One canonical-payload byte changed (`AIGEN`→`BIGEN`); ECDSA over the altered input fails. |
| `card-malformed-tampered-signature` | `tampered-byte` | Last byte of `r‖s` flipped; ECDSA fails. |
| `card-malformed-alg-none` | `alg-none-downgrade` | Protected header claims `{"alg":"none"}` with an empty signature. **Pin the algorithm allow-list** — never accept `none` as "signed". |
| `card-malformed-wrong-key` | `wrong-key` | A well-formed but **unrelated** P-256 key (e.g. wrong/rotated JWKS, `kid` mismatch); the genuine signature does not verify under it. |
| `card-malformed-wrong-curve` | `wrong-curve` | A well-formed **P-384/ES384** JWK presented while the header claims ES256. **Pin curve+alg** and reject the mismatch regardless of bytes. |
| `card-malformed-non-canonical-json` | `non-canonical-payload` | The signature is presented over **pretty-printed, reordered** JSON instead of JCS. Because the verifier recomputes `JCS(card)`, a signature over any non-canonical encoding fails. This proves your verifier actually **canonicalizes**, rather than hashing whatever bytes it was handed. |

Each malformed case names how to key the verification:
- `verify_with: "jwks"` → use the public key in `jwks.document`.
- `verify_with: "inline_jwk"` → use the case's own `verification_jwk`.

### `jcs_conformance` sub-vectors

Standalone RFC 8785 checks (independent of any signature). For each,
`JCS(input)` must equal `expected_jcs` byte-for-byte (`expected_jcs_hex` is its
UTF-8 hex). They pin the three properties an agent-card verifier depends on:

- **number** — ECMAScript `Number::toString`: `-0` → `0`, `1e21` → `1e+21`,
  `2e-3` → `0.002`, `1e-27` → `1e-27`, integers stay bare.
- **unicode** — keys sorted by **UTF-16 code unit** (so `A` < `z` < `é` < `€`),
  printable non-ASCII emitted as literal UTF-8, control chars as short escapes
  (`\n`).
- **key-order** — insertion order is irrelevant; digit-string keys sort
  lexicographically (`"1" < "10" < "A" < "a"`), not numerically; recursion
  sorts nested objects while **preserving array order**.

---

## How to run these vectors against *any* implementation

The pattern is identical in every language: **load the JSON, loop the cases,
call your implementation, assert the boolean.** No build step is required to read
the file.

### 1. Reference runner (proves the vectors, and is a worked example)

```bash
python3 run_vectors.py                 # uses ./verifier-test-vectors.json
python3 run_vectors.py /path/to/verifier-test-vectors.json
echo $?                                # 0 = all vectors passed
```

It runs all three suites and prints a per-case PASS/FAIL line. (The
`agent_card_signature` suite needs the `cryptography` package; if it is absent
the runner skips that suite and still checks regex + JCS. The
`first_valid_match` and `jcs_conformance` suites are pure stdlib.)

Expected summary:

```
first_valid_match            -> 31 passed, 0 failed, 0 skipped
jcs_conformance (RFC 8785)   -> 6 passed, 0 failed
agent_card_signature …       -> 7 passed, 0 failed
TOTAL: 44 passed, 0 failed, 0 skipped
```

### 2. Wiring your own implementation in (pseudocode, any language)

```text
doc = JSON.parse(read("verifier-test-vectors.json"))

# --- content-addressed ---
for c in doc.first_valid_match.cases:
    if c.requires contains a feature your engine lacks: continue   # e.g. "lookahead" on RE2
    got = YOUR_VERIFIER.matches(c.regex, c.proof)        # full-string match
    assert got == c.expected_match,  c.id

# --- JCS ---
for c in doc.agent_card_signature.jcs_conformance.cases:
    assert YOUR_JCS.canonicalize(c.input) == c.expected_jcs,  c.id

# --- agent-card signature ---
A = doc.agent_card_signature
payload_b64 = base64url(utf8( YOUR_JCS.canonicalize(A.payload.card_without_signatures) ))
assert payload_b64 == A.canonical.payload_b64url            # cross-check JCS

v = A.valid
assert YOUR_VERIFIER.verify_card(                            # must be TRUE
          protected = v.protected,
          payload_b64 = payload_b64,
          signature = v.signature,
          jwks = A.jwks.document) == true

for c in A.malformed.cases:
    key = (c.verify_with == "jwks") ? A.jwks.document : { keys: [ c.verification_jwk ] }
    assert YOUR_VERIFIER.verify_card(                        # must be FALSE
              protected = c.protected,
              payload_b64 = c.payload_b64url,
              signature = c.signature,
              jwks = key) == false,   c.id
```

If you consume an OABP SDK, use its public surface instead of plain crypto:
e.g. the TypeScript A2A client's `canonicalize()` (RFC 8785) and
`verifyAgentCard(card, { jwks })`, or the equivalent helpers in the python / go /
rust / java / kotlin / php / ruby / swift / dart / elixir / csharp clients. The
vectors are SDK-agnostic — they assert *behaviour*, not any one library.

### 3. Pass / fail criterion

An implementation is **conformant** against this file when, for the suites it
supports:

- **every** `first_valid_match` case it does **not** skip yields
  `expected_match`;
- **every** `jcs_conformance` case yields `expected_jcs` byte-for-byte;
- the **valid** card vector verifies (`true`) **and every** `malformed` card
  vector is rejected (`false`).

Any single deviation means non-conformant — most often a JCS bug (key ordering,
number formatting, Unicode escaping) or a missing **policy** check (accepting
`alg:none`, or not pinning the curve), which the malformed cases are designed to
catch.

---

## Provenance & regeneration

- The **valid** signature, the P-256 JWK, and the JWKS are a frozen ES256 vector:
  minted once with a standard JOSE/`jose` toolchain and pinned, then
  independently re-verified with a separate P-256 implementation, so the bytes
  the verifier sees are not produced by the verifier itself.
- The **canonical** `jcs_string` / `jcs_hex` / `payload_b64url`, the tampered and
  non-canonical payloads, the unrelated-key and wrong-curve JWKs, and every
  `jcs_conformance` expectation were **computed**, not hand-written, and the
  whole file is self-consistent: running `run_vectors.py` recomputes the
  canonical payload from the card and re-derives every boolean. If you ever edit
  the sample card, re-run the runner — the valid signature is bound to the exact
  canonical bytes above and will (correctly) stop verifying if the payload
  changes.
- JCS follows **RFC 8785**; the JWS conventions follow **RFC 7515** (detached) +
  the A2A agent-card signature profile; regex semantics are full-string match as
  specified by the OABP verification model.

CC0-1.0. Reuse freely.
