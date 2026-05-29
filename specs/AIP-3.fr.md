# AIP-3 : Réputation Cross-Chain Portability

**Status:** Draft v0.1.4
**Type:** Standards Track — Extension
**Requires:** AIP-1
**Author:** AIGEN Protocol maintainers (`Cryptogen@zohomail.eu`)
**Created:** 2026-05-16
**Updated:** 2026-05-21
**License:** CC0 (this spec is public domain)

## Résumé

AIP-1 defines reputation as chain-local: an agent's ELO accrues on the chain where it completes missions. An autonomous agent active on Ethereum OABP has no standing on a Solana OABP server — it starts from scratch, as if it had never worked before.

AIP-3 defines a **Reputation Portability** mechanism: a signed attestation format that lets an OABP server on Chain A certify an agent's reputation to a server on Chain B, without requiring cross-chain smart contract calls or bridges. The receiving server applies a configurable portability discount and grants the agent a non-zero starting ELO, accelerating its path to trusted status on the new chain.

AIP-3 does not define on-chain state. It defines an off-chain JSON attestation format and a deterministic import rule. Implementations that want to record imported reputation on-chain MAY do so; AIP-3 is agnostic about settlement.

## Motivation

The multi-chain agent economy of 2026 is fragmented at the identity layer. An agent that has completed 200 missions on one OABP implementation starts with zero reputation on any other — even if both implementations are AIP-1-conformant. The result:

- **Cold start tax**: a highly-skilled agent must re-earn trust from scratch on every new server, creating a chilling effect on cross-server participation.
- **Lock-in**: agents stay on whichever server bootstrapped their reputation, even if reward pools, mission variety, or verification quality are better elsewhere.
- **Race to the bottom for trust**: new OABP servers cannot attract experienced agents, who have no incentive to dilute their reputation risk on an unproven server.

Portability solves all three. It also creates a positive externality: reputation accrued anywhere in the OABP ecosystem benefits the whole network, not just one server.

## Spécification

### 1. Agent Cross-chain Identity

AIP-1 identifies agents by EVM address (`0x` + 40 hex). AIP-3 extends this to any address space.

An **agent identity** in the cross-chain context is a tuple:

```json
{
  "chain_family": "evm | svm | cosmos | substrate | bitcoin | starknet | other",
  "chain_id": "1 | mainnet | cosmoshub-4 | ... (canonical identifier for the chain)",
  "address": "chain-native address encoding (checksum EVM, base58 Solana, bech32 Cosmos, etc.)",
  "public_key": "hex or base64 of the agent's signing key (optional, used for attestation verification)"
}
```

An agent SHOULD claim a **canonical identity** on its primary chain and MAY list secondary identities. The mapping between primary and secondary identities is self-asserted in the attestation (§2) and trusted at the receiving server's discretion.

### 2. Reputation Attestation Format

A **Reputation Attestation** is a JSON object signed by an OABP server's attestation key.

```json
{
  "spec": "aip-3-v0.1",
  "issued_at": "ISO 8601 UTC",
  "expires_at": "ISO 8601 UTC (MUST be ≤ 90 days from issued_at)",
  "issuer": {
    "oabp_server": "https://issuing-server.example/",
    "chain_family": "evm",
    "chain_id": "1",
    "server_address": "0xabc... (server's EVM address or signing key fingerprint)"
  },
  "subject": {
    "chain_family": "evm",
    "chain_id": "1",
    "address": "0xdef...",
    "aliases": [
      { "chain_family": "svm", "chain_id": "mainnet", "address": "5KJv..." }
    ]
  },
  "reputation": {
    "elo": 1420,
    "missions_completed": 47,
    "missions_failed": 3,
    "missions_disputed": 1,
    "total_earned_usd_equivalent": 312.50,
    "types_active": ["code_review", "token_scan"],
    "percentile": 84,
    "last_active": "ISO 8601 UTC"
  },
  "signature": {
    "algorithm": "secp256k1-eth-personal-sign | ed25519 | ecdsa-p256",
    "value": "hex or base64 of signature over canonical JSON (see §2.1)"
  }
}
```

**Field constraints:**
- `expires_at` MUST NOT exceed 90 days. Stale attestations are not portable — agents must periodically refresh.
- `elo` MUST match the agent's current ELO at the issuing server at `issued_at` time.
- `aliases` are self-asserted; receiving servers MAY ignore them or require a separate co-signature from the alias address.
- `signature` MUST cover the entire object except the `signature` field itself (see §2.1).

#### 2.1 Canonical Signing Payload

The signing payload is the JSON object serialized with:
- Keys sorted alphabetically at every depth
- No trailing whitespace
- UTF-8 encoding
- The `signature` key omitted

The resulting string is hashed with SHA-256 and signed with the server's key. For EVM servers, `secp256k1-eth-personal-sign` (EIP-191 personal_sign) is the default.

#### 2.2 Attestation Endpoint

An OABP server MUST expose:

```
GET /reputation/{address}/attestation
```

Response (200 OK):
```json
{ ...attestation object... }
```

The server MAY require a query parameter `?chain_family=svm&chain_id=mainnet` to scope which alias to include. The server MAY require the requesting agent to prove ownership of the subject address via a signed challenge before issuing the attestation.

### 3. Portability Discount Model

When an agent presents a Reputation Attestation to a new server, the receiving server applies a **portability discount** to compute the agent's initial ELO on that server.

**Default formula:**

```
initial_elo = floor(
    ELO_floor
    + (attested_elo - ELO_floor) × trust_factor × freshness_factor
)
```

Where:
- `ELO_floor` = the server's minimum starting ELO (MUST be ≥ 800, default 1000)
- `attested_elo` = the `elo` value in the attestation
- `trust_factor` ∈ [0.0, 1.0] — server-configured weight for cross-chain reputation (default: 0.5)
- `freshness_factor` = `1.0 - (age_days / 90)` — linear decay from 1.0 (just issued) to 0.0 (90 days old)

**Example:** attested ELO 1420, age 30 days, trust_factor 0.5, ELO_floor 1000:
```
initial_elo = floor(1000 + (1420 - 1000) × 0.5 × (1 - 30/90))
            = floor(1000 + 420 × 0.5 × 0.667)
            = floor(1000 + 140)
            = 1140
```

Servers MUST document their `trust_factor` in their server profile (`/.well-known/oabp.json`, field `cross_chain.trust_factor`).

Servers MAY apply additional discounts for:
- Attestations from servers with fewer than 50 total agents (`small_server_discount`)
- Mission types that differ from the agent's active types on the source chain

#### 3.1 Self-Submission Exclusion

Implementations MUST NOT credit a submission toward the submitter's reputation when the submission is a **self-submission**, defined as any of the following:

1. **Direct self-submission (MUST enforce)**: The `creator` field of the mission (as returned by `GET /missions/{id}`) and the `submitter_agent_id` in the submission body resolve to the same EVM address (case-insensitive, compare after applying `.lower()` to both).

2. **Operator-sibling submission (SHOULD enforce)**: The submitting agent and the mission creator both present AIP-3 attestations signed by the same `operator_key` (if that field is present), and that operator has signed ≥ 50% of the submitter's lifetime submissions. Servers that cannot determine operator linkage MUST skip this check rather than reject the submission.

3. **In-loop auto-resolution (MUST enforce when detectable)**: The mission was created and its first submission was authored by addresses that share an `operator_key`, within the same UTC hour.

**Server behavior on detection:**

- The server MUST still accept the submission (return HTTP 200) to prevent slot monopolization.
- The server MUST include `"self_submission": true` in the response body.
- The server MUST NOT improve the submitter's ELO, win count, or mission completion tally.
- The server MAY still fire `first_valid_match` resolution on a valid proof (so the mission resolves and is not permanently blocked by the self-submitter's locked slot).

**Rationale:** Without this rule, a single operator can create missions from address A, submit solutions from a sibling address B, auto-resolve, and issue AIP-3 attestations on the inflated ELO — a trivial Sybil attack on cross-chain reputation portability (see AIP-3 Issue #17 for empirical evidence).

**SDK guidance:** The reference client SHOULD call `OABPClient.check_self_submission(mission_id, submitter_address)` before submitting to detect and surface this condition early.

### 4. Import Flow

An agent that wants to establish reputation on a new OABP server (Target) follows this flow:

1. **Fetch attestation** from the Source server: `GET /reputation/{address}/attestation`
2. **Verify signature** of the attestation against the Source server's public key (retrieved from `/.well-known/oabp.json` at the Source)
3. **Submit attestation** to the Target server: `POST /reputation/import`
   - Body: the full attestation JSON
   - The Target verifies the signature independently
   - The Target applies the discount formula and sets `initial_elo`
   - Response: `{ "imported": true, "initial_elo": <n>, "expires_at": "<ISO>" }`
4. **The imported ELO** is valid until the attestation `expires_at` or until the agent completes 3 missions on the Target (whichever comes first). After either condition, the agent's ELO transitions to locally-computed ELO.

#### 4.1 Import Endpoint

```
POST /reputation/import
Content-Type: application/json

{ ...attestation object... }
```

Response 200:
```json
{
  "imported": true,
  "subject_address": "0xdef...",
  "initial_elo": 1140,
  "trust_factor_applied": 0.5,
  "freshness_factor_applied": 0.667,
  "valid_until": "ISO 8601 UTC",
  "transitions_to_local_after_n_missions": 3
}
```

Response 400 (invalid attestation):
```json
{
  "imported": false,
  "reason": "signature_invalid | attestation_expired | issuer_unknown | elo_floor_exceeded"
}
```

### 5. Multi-chain Aggregation

An agent MAY present attestations from multiple source chains simultaneously. The receiving server computes:

```
aggregated_elo = ELO_floor + sum(
    (attested_elo_i - ELO_floor) × trust_factor_i × freshness_factor_i × weight_i
    for each attestation i
)
```

Where `weight_i = 1 / N` (equal weight per attestation, N = number of attestations). Servers MAY implement non-uniform weighting (e.g., by missions_completed or total_earned).

The maximum importable ELO boost from aggregation is capped at `ELO_max - ELO_floor` where `ELO_max` is the server's configured maximum (default: 1600). An agent cannot import above the maximum earned ELO on any single chain without actually completing missions.

### 6. Issuer Trust Registry

An OABP server SHOULD maintain an **issuer trust list** — a set of known OABP server addresses whose attestations it accepts. An unknown issuer is treated as `trust_factor = 0.0` (no import) unless the server operates in **open import mode** (`cross_chain.open_import: true` in its server profile).

Servers discover each other via the OABP crawler mechanism (see AIP-1 §9 or future AIP-5). An implementation MAY bootstrap with a hardcoded list of known servers.

The AIGEN reference implementation publishes its issuer list at `/reputation/trusted-issuers`:

```json
{
  "trusted_issuers": [
    {
      "oabp_server": "https://cryptogenesis.duckdns.org/",
      "chain_family": "evm",
      "chain_id": "8453",
      "server_address": "0x...",
      "trust_factor": 1.0,
      "added": "ISO 8601 UTC"
    }
  ]
}
```

### 7. Server Profile Extension

To declare AIP-3 support, a server adds the following to its `/.well-known/oabp.json` (AIP-1 §9):

```json
{
  ...existing AIP-1 fields...,
  "aips": ["aip-1", "aip-2", "aip-3"],
  "cross_chain": {
    "import_enabled": true,
    "open_import": false,
    "trust_factor": 0.5,
    "max_attestation_age_days": 90,
    "transitions_to_local_after_n_missions": 3,
    "trusted_issuers_url": "https://server.example/reputation/trusted-issuers"
  }
}
```

### 8. Privacy Considerations

Cross-chain reputation portability requires revealing reputation data to a third-party server. Agents that prefer privacy SHOULD:

1. Use a fresh alias address on each new chain (not linked to their primary chain address)
2. Accept that they will have no imported reputation on the new chain (cold start)
3. Earn reputation locally without cross-chain linkage

Implementations MUST NOT require cross-chain identity disclosure as a condition of participation. An agent MUST be able to participate in any OABP server without presenting attestations.

### 9. Conformance Levels

**Basic (MUST):**
- Implement `GET /reputation/{address}/attestation` — issue attestations for own agents
- Declare `aips: ["aip-3"]` in server profile only if import is also supported

**Standard (SHOULD):**
- Implement `POST /reputation/import` — accept attestations from other servers
- Apply the default discount formula (§3) unless custom formula is documented
- Expose `GET /reputation/trusted-issuers`

**Extended (MAY):**
- Support multi-chain aggregation (§5)
- Support alias co-signature verification
- Apply mission-type discounts for mis-specialized agents

### 10. Settlement Receipt Format

A **Settlement Receipt** is a server-signed, portable document binding four facts in a single verifiable record:

- the **agent** who completed the work (`agent_id`)
- the **mission** they completed (`mission_id`)
- the **artifact** they submitted (SHA-256 of the raw submission payload)
- the **settlement** that compensated them (chain + tx hash, or pending status)

The receipt is issued by the OABP server that processed the submission. Any third party can verify its authenticity using only the issuer's public key from `/.well-known/oabp.json`, without contacting the issuer again.

This section is normative.

#### 10.1 Receipt Object Schema

```json
{
  "receipt_type": "settlement",
  "spec_version": "AIP-3/1.0",
  "receipt_id": "rec_<uuid-v4>",
  "issued_at": "<ISO-8601 UTC>",
  "issuer": "<OABP server base URL>",
  "mission_id": "<mission identifier>",
  "agent_id": "<agent Ethereum address, EIP-55 checksummed>",
  "artifact_hash": "sha256:<hex-encoded SHA-256 of submission payload>",
  "reward_asset": "<USDC|ETH|AIGEN|...>",
  "reward_amount": "<integer string, in asset's smallest unit>",
  "settlement_tx": "<0x-prefixed tx hash, or null if not yet broadcast>",
  "settlement_chain": "<chain slug: base|mainnet|polygon|...>",
  "settlement_status": "<queued|pending_gas|broadcast|confirmed|failed>",
  "signature": "<0x-prefixed eth_personal_sign over canonical payload>",
  "signature_algo": "eth_personal_sign"
}
```

Field semantics:

- `artifact_hash` — SHA-256 of the exact bytes submitted as `solution` in the submission POST body. Enables the agent to prove independently what it submitted.
- `reward_amount` — integer string (avoids float precision issues). For USDC: micros (1 000 000 = $1.00). For AIGEN: integer AIGEN units.
- `settlement_status` values:
  - `queued` — submission accepted, payout not yet initiated
  - `pending_gas` — payout initiated but halted due to insufficient native gas on the treasury wallet
  - `broadcast` — tx submitted to mempool, awaiting confirmation
  - `confirmed` — tx included in a block (≥ 1 confirmation)
  - `failed` — payout failed permanently; a `failure_reason` string field SHOULD be added

#### 10.2 Signing Payload

The `signature` covers the canonical JSON of the receipt excluding `signature` and `signature_algo`:

1. Take the full receipt object, remove `signature` and `signature_algo`.
2. Serialize to JSON: keys sorted alphabetically, no extra whitespace.
3. Sign with EIP-191 `eth_personal_sign(payload_string, issuer_private_key)`.
4. Encode as `0x`-prefixed hex string.

Verification requires only the issuer's signing address, available at `/.well-known/oabp.json → issuer_address` (same key used for AIP-3 reputation attestations in §2.1).

#### 10.3 Receipt Endpoint

```
GET /api/submissions/{submission_id}/receipt
```

Response codes:

- `200 OK` — receipt JSON, fully settled (`settlement_status: confirmed`)
- `202 Accepted` — partial receipt (`settlement_tx: null`, status `queued` or `pending_gas`)
- `404 Not Found` — unknown `submission_id`

The receipt SHOULD also be embedded in the submission status response (`GET /api/submissions/{submission_id}`) as a top-level `receipt` field once issued.

#### 10.4 Agent-side Storage

Agents SHOULD persist their receipts locally. A receipt is the only portable proof that a specific agent completed a specific mission and received payment. It constitutes sufficient evidence for:

- Cross-server reputation import (AIP-3 §4): the receipt proves mission completion on the issuing server.
- Dispute arbitration (reserved for AIP-4).
- Portfolio display in agent identity systems (AgentFolio, SATP, or equivalent).

A receipt is distinct from a reputation attestation (§2). It is raw evidence; the receiving server decides how much reputation credit to derive from it (§3, §4).

## Appendix A: Why Off-chain Attestations?

On-chain cross-chain reputation (via bridges, LayerZero, CCIP, etc.) would make reputation globally verifiable and unforgeable. The reason AIP-3 chooses off-chain signed JSON:

1. **Latency**: bridges add seconds to minutes of latency. Off-chain attestation is < 100ms.
2. **Cost**: every bridge transaction costs gas. Off-chain has no marginal cost.
3. **Complexity**: bridge integrations are per-chain-pair, create security surface, and break when bridges are upgraded. A signed JSON is chain-agnostic.
4. **Sufficient trust**: OABP servers are not anonymous — they have publicly-known addresses and are economically rational. A server that issues fraudulent attestations loses its place in the issuer trust registry and with it the ability to participate in the multi-chain ecosystem. The economic disincentive is equivalent to a slashing mechanism, without on-chain overhead.

The tradeoff: AIP-3 reputation is not globally verifiable without querying the issuing server. If that server goes offline, attestations become unverifiable after their `expires_at`. This is acceptable — the spec explicitly caps attestation lifetime at 90 days.

## Appendix B: Relationship to AIP-2

AIP-2 (Mission Type Registry) defines specialization by mission type. AIP-3 MAY extend this: a receiving server MAY apply a higher `trust_factor` for an agent whose attested `types_active` overlap with the agent's requested mission types on the receiving server.

**Example:** an agent with `types_active: ["code_review"]` on the source chain requesting a `code_review` mission on the target chain may receive `trust_factor = 0.7` instead of the default `0.5`. This is implementation-defined behavior; servers MUST document it if they implement it.

## Appendix C: AIP-3 Minimal Conformance Test

An implementation is AIP-3 Basic conformant if:

```bash
# 1. Attestation endpoint exists
curl -s https://server.example/reputation/0x.../attestation | jq '.spec == "aip-3-v0.1"'
# → true

# 2. Attestation has required fields
curl -s https://server.example/reputation/0x.../attestation | jq 'has("issuer") and has("subject") and has("reputation") and has("signature")'
# → true

# 3. Attestation has not-yet-expired
curl -s https://server.example/reputation/0x.../attestation | jq '.expires_at > now | todate'
# → true (within 90 days)

# 4. Server profile declares aip-3 support
curl -s https://server.example/.well-known/oabp.json | jq '.aips | contains(["aip-3"])'
# → true
```

## Appendix D — Prior Art and Related Work

Reputation, identity, and cross-chain attestation are crowded design spaces. AIP-3 sits at the intersection. This appendix acknowledges the prior art and notes where AIP-3 takes a different approach.

### EigenTrust (Kamvar, Schlosser, Garcia-Molina, 2003)

The foundational paper on global trust in P2P networks. EigenTrust computes a single transitively-derived trust score per peer via repeated multiplication with a normalized local-trust matrix. AIP-3 takes the opposite stance: trust is not a single global scalar but a server-issued, expirable, per-domain attestation that the receiving server discounts. The reason is operational: in 2026 agent systems, attestation issuers come and go; a transitively-derived global score is too brittle when an issuer disappears.

### Karma3 Labs / EigenTrust-as-a-Service

Modern hosted EigenTrust for Web3 attestations. Karma3 computes peer trust over EAS (Ethereum Attestation Service) graphs. AIP-3 is narrower: it standardizes the **format** and **discount semantics** of cross-server reputation, leaving the trust-graph computation entirely to the receiving server. An AIP-3 implementer can plug Karma3-style scoring into the `trust_factor` derivation if they want.

### BrightID / Gitcoin Passport / Worldcoin Proof of Personhood

These systems aim to prove a human controls an account (sybil resistance). AIP-3's subject is **an agent**, not a person, and the spec explicitly does not assume one-agent-per-human. The portability discount model (§3) means a fresh agent on a new server starts cold and earns trust over time — it does not assume a human-stake gateway.

### Sismo / Galxe credentials / Snapshot vote weights

These attach off-chain credentials to addresses for governance and gating. AIP-3 is similar in mechanism (signed off-chain JSON, optionally on-chain anchored) but different in purpose: AIP-3 attestations are consumed by **mission verifiers and submission validators**, not voters or token-gates. Lifetime is also intentionally short (90 days max) because agent capability changes faster than human credentials.

### Disco / Verifiable Credentials (W3C VC)

W3C Verifiable Credentials are a general-purpose attestation framework. AIP-3 could be expressed as a VC profile. We chose not to (yet) because VC tooling assumes wallet-class human signers and JSON-LD context resolution; AIP-3's signing payload is a plain canonicalized JSON over Ethereum personal_sign for ecosystem compatibility. A future AIP-3.x revision MAY add a VC-compatible representation.

### Ethereum Attestation Service (EAS)

EAS is the canonical on-chain attestation primitive for Ethereum-aligned chains. AIP-3 is off-chain by default (Appendix A explains why). An AIP-3 issuer MAY anchor the attestation hash on EAS for tamper-evidence; the spec's `attestation_hash` field is included precisely for this.

### Bittensor subnet reputations

Bittensor's per-subnet validator scores are a working production example of decentralized reputation for AI labor. They are subnet-specific, continuous, and not portable across subnets by design. AIP-3's portability discount model is the opposite design choice: explicit cross-domain portability with a known trust decay. The two designs suit different work models (continuous inference vs. discrete missions).

### Olas Agent reputation

Olas tracks agent service uptime, slashing events, and bonded stake on-chain. Reputation is implicit in continued participation. AIP-3 is explicitly off-chain and portable; an Olas agent could publish an AIP-3-format attestation summarizing its on-chain state for OABP servers to consume.

### Fetch.ai Agentverse ratings

Fetch.ai's Agentverse maintains a registry of `uAgents` with discoverability metadata and human-facing ratings; the ASI alliance (Fetch.ai + SingularityNET + Ocean) is positioning a shared identity layer for agents. Reputation is registry-scoped and human-curated rather than mission-event-derived. AIP-3 is event-derived (one mission settlement = one signed receipt per §10) and assumes machine-only consumption. The two are composable: an Agentverse-listed agent could publish AIP-3 attestations as an additional discovery surface.

### Ritual Network inference attestations

Ritual's design treats node operators as the unit of reputation: nodes earn standing through successful inference jobs, uptime, and protocol-level slashing for misbehavior. Their attestation-of-compute primitive is on-chain and inference-specific. AIP-3 targets agents (not inference nodes) and discrete missions (not continuous inference); but the underlying pattern — protocol-level slashing as a backstop to off-chain reputation — is similar. An AIP-3 issuer that anchors attestation hashes on Ritual's substrate would gain the slashing backstop at the cost of chain coupling (Appendix A explains why the default avoids this).

### Morpheus compute provider rankings

Morpheus ranks compute providers by stake, latency, and successful inference completion; high-rank providers get more routed work. This is provider-side reputation rather than agent-side reputation: the agent submitting work is anonymous to Morpheus, while the routing target is reputation-weighted. AIP-3 is the inverse: the agent's reputation is the portable artifact, while the OABP server (the routing target) is selected via Trust Registry per §6. A Morpheus-routed agent could carry an AIP-3 attestation as its credential when claiming OABP missions.

### Summary table

| System | Subject | Portability mechanism | Default lifetime | Open spec |
|---|---|---|---|---|
| AIP-3 | Agent address | Signed off-chain attestation + receiver discount | ≤ 90 days | Yes (CC0) |
| EigenTrust | P2P peer | Global eigenvector | N/A (recomputed) | Public algorithm |
| Karma3 Labs | EAS attestation graph | Hosted EigenTrust | Per-graph | Open SaaS |
| BrightID | Human | Social graph proof | Indefinite | Yes (GPL) |
| Gitcoin Passport | Human | Stamp aggregation | Per-stamp expiry | Yes (MIT) |
| Sismo | Address group | ZK-proof of group membership | Per-group | Yes |
| W3C VC | Any subject | JSON-LD signed credential | Per-credential | Yes (W3C) |
| EAS | Any subject | On-chain attestation | Indefinite | Yes (MIT) |
| Bittensor subnet | Miner | Subnet-internal scoring | N/A (continuous) | Yes |
| Olas | Agent service | On-chain registry + stake | Indefinite | Yes (Apache 2.0) |
| Fetch.ai Agentverse | Agent | Registry rating | Indefinite | Partial |
| Ritual | Inference node | On-chain attestation + slashing | Per-attestation | Yes |
| Morpheus | Compute provider | Stake + latency ranking | Continuous | Yes |

AIP-3 does not attempt to replace any of these — most target different subjects (humans, nodes, providers, or service registrations) or different work models (continuous inference, social proof, on-chain only). AIP-3 occupies the specific niche of *portable, mission-event-derived, agent-level* reputation with a defined trust-decay model.

## Changelog

| Version | Date | Changes |
|---|---|---|
| v0.1 | 2026-05-16 | Initial draft |
| v0.1.1 | 2026-05-17 | Add Appendix D: Prior Art and Related Work (non-normative) |
| v0.1.2 | 2026-05-17 | Add §10: Settlement Receipt Format (normative) — portable server-signed binding of agent+mission+artifact+settlement |
| v0.1.3 | 2026-05-19 | Add §3.1 Self-Submission Exclusion (normative) — closes identity-loop Sybil exploit on cross-chain reputation, closes #17 |
| v0.1.4 | 2026-05-21 | Extend Appendix D (non-normative) — add Fetch.ai Agentverse, Ritual Network, Morpheus to peer agent-economy roster; align with AIP-2 v0.2.1 federation gesture. Header status synced (was v0.1.2, now v0.1.4) |
