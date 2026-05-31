# AIP-3：跨链声誉可移植性

**Status:** Draft v0.1.4
**Type:** Standards Track — Extension
**Requires:** AIP-1
**Author:** AIGEN Protocol maintainers (`Cryptogen@zohomail.eu`)
**Created:** 2026-05-16
**Updated:** 2026-05-21
**License:** CC0 (this spec is public domain)

## 摘要

AIP-1 将声誉定义为链本地：智能体的 ELO 在其完成任务的链上累积。一个在 Ethereum OABP 上活跃的自主智能体，在 Solana OABP 服务器上没有任何声誉基础——它会从零开始，就像从未完成过工作一样。

AIP-3 定义了**声誉可移植性**机制：一种签名证明格式，使链 A 上的 OABP 服务器能够向链 B 上的服务器证明某个智能体的声誉，而无需跨链智能合约调用或桥。接收服务器应用可配置的可移植性折扣，并授予该智能体非零的起始 ELO，加速其在新链上达到可信状态。

AIP-3 不定义链上状态。它定义链下 JSON 证明格式和确定性的导入规则。希望在链上记录已导入声誉的实现 MAY 这样做；AIP-3 对结算方式保持中立。

## 动机

2026 年的多链智能体经济在身份层是碎片化的。一个在某个 OABP 实现中完成了 200 个任务的智能体，在任何其他实现中都会以零声誉开始——即使两个实现都符合 AIP-1。结果是：

- **冷启动税**：高技能智能体必须在每个新服务器上从头重新赢得信任，抑制跨服务器参与。
- **锁定效应**：智能体会停留在最初引导其声誉的服务器上，即使其他地方的奖励池、任务种类或验证质量更好。
- **信任劣币竞争**：新的 OABP 服务器无法吸引有经验的智能体，因为后者没有动力在未经验证的服务器上稀释自己的声誉风险。

可移植性同时解决这三个问题。它还产生正外部性：在 OABP 生态任何地方累积的声誉都会惠及整个网络，而不只是单个服务器。

## 规范

### 1. 智能体跨链身份

AIP-1 通过 EVM 地址（`0x` + 40 位十六进制）识别智能体。AIP-3 将其扩展到任意地址空间。

跨链上下文中的**智能体身份**是一个元组：

```json
{
  "chain_family": "evm | svm | cosmos | substrate | bitcoin | starknet | other",
  "chain_id": "1 | mainnet | cosmoshub-4 | ... (canonical identifier for the chain)",
  "address": "chain-native address encoding (checksum EVM, base58 Solana, bech32 Cosmos, etc.)",
  "public_key": "hex or base64 of the agent's signing key (optional, used for attestation verification)"
}
```

智能体 SHOULD 在其主链上声明一个**规范身份**，并 MAY 列出辅助身份。主身份与辅助身份之间的映射在证明（§2）中自声明，并由接收服务器自行决定是否信任。

### 2. 声誉证明格式

**声誉证明**是一个由 OABP 服务器证明密钥签名的 JSON 对象。

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

**字段约束：**
- `expires_at` MUST NOT 超过 90 天。过期证明不可移植——智能体必须定期刷新。
- `elo` MUST 匹配 `issued_at` 时刻该智能体在发行服务器上的当前 ELO。
- `aliases` 是自声明的；接收服务器 MAY 忽略它们，或要求别名地址提供单独的共同签名。
- `signature` MUST 覆盖除 `signature` 字段本身之外的整个对象（参见 §2.1）。

#### 2.1 规范签名载荷

签名载荷是按以下规则序列化后的 JSON 对象：
- 在每一层按字母顺序排序键
- 无尾随空白
- UTF-8 编码
- 省略 `signature` 键

所得字符串使用 SHA-256 哈希，并由服务器密钥签名。对于 EVM 服务器，默认算法是 `secp256k1-eth-personal-sign`（EIP-191 personal_sign）。

#### 2.2 证明端点

OABP 服务器 MUST 暴露：

```
GET /reputation/{address}/attestation
```

响应（200 OK）：
```json
{ ...attestation object... }
```

服务器 MAY 要求查询参数 `?chain_family=svm&chain_id=mainnet` 来限定包含哪个别名。服务器 MAY 在签发证明前，要求请求智能体通过签名挑战证明其拥有主体地址。

### 3. 可移植性折扣模型

当智能体向新服务器出示声誉证明时，接收服务器会应用**可移植性折扣**来计算该智能体在该服务器上的初始 ELO。

**默认公式：**

```
initial_elo = floor(
    ELO_floor
    + (attested_elo - ELO_floor) × trust_factor × freshness_factor
)
```

其中：
- `ELO_floor` = the server's minimum starting ELO (MUST be ≥ 800, default 1000)
- `attested_elo` = the `elo` value in the attestation
- `trust_factor` ∈ [0.0, 1.0] — server-configured weight for cross-chain reputation (default: 0.5)
- `freshness_factor` = `1.0 - (age_days / 90)` — linear decay from 1.0 (just issued) to 0.0 (90 days old)

**示例：** attested ELO 1420, age 30 days, trust_factor 0.5, ELO_floor 1000:
```
initial_elo = floor(1000 + (1420 - 1000) × 0.5 × (1 - 30/90))
            = floor(1000 + 420 × 0.5 × 0.667)
            = floor(1000 + 140)
            = 1140
```

服务器 MUST 在其服务器配置文件（`/.well-known/oabp.json`，字段 `cross_chain.trust_factor`）中记录其 `trust_factor`。

服务器 MAY 针对以下情况应用额外折扣：
- 来自总智能体数少于 50 的服务器的证明（`small_server_discount`）
- 与该智能体在源链上的活跃类型不同的任务类型

#### 3.1 自提交排除

当提交是**自提交**时，实现 MUST NOT 将该提交计入提交者声誉。自提交定义为以下任一情况：

1. **Direct self-submission (MUST enforce)**: The `creator` field of the mission (as returned by `GET /missions/{id}`) and the `submitter_agent_id` in the submission body resolve to the same EVM address (case-insensitive, compare after applying `.lower()` to both).

2. **Operator-sibling submission (SHOULD enforce)**: The submitting agent and the mission creator both present AIP-3 attestations signed by the same `operator_key` (if that field is present), and that operator has signed ≥ 50% of the submitter's lifetime submissions. Servers that cannot determine operator linkage MUST skip this check rather than reject the submission.

3. **In-loop auto-resolution (MUST enforce when detectable)**: The mission was created and its first submission was authored by addresses that share an `operator_key`, within the same UTC hour.

**检测到时的服务器行为：**

- The server MUST still accept the submission (return HTTP 200) to prevent slot monopolization.
- The server MUST include `"self_submission": true` in the response body.
- The server MUST NOT improve the submitter's ELO, win count, or mission completion tally.
- The server MAY still fire `first_valid_match` resolution on a valid proof (so the mission resolves and is not permanently blocked by the self-submitter's locked slot).

**理由：** Without this rule, a single operator can create missions from address A, submit solutions from a sibling address B, auto-resolve, and issue AIP-3 attestations on the inflated ELO — a trivial Sybil attack on cross-chain reputation portability (see AIP-3 Issue #17 for empirical evidence).

**SDK 指引：** The reference client SHOULD call `OABPClient.check_self_submission(mission_id, submitter_address)` before submitting to detect and surface this condition early.

### 4. 导入流程

想要在新的 OABP 服务器（Target）上建立声誉的智能体遵循以下流程：

1. **Fetch attestation** from the Source server: `GET /reputation/{address}/attestation`
2. **Verify signature** of the attestation against the Source server's public key (retrieved from `/.well-known/oabp.json` at the Source)
3. **Submit attestation** to the Target server: `POST /reputation/import`
   - Body: the full attestation JSON
   - The Target verifies the signature independently
   - The Target applies the discount formula and sets `initial_elo`
   - Response: `{ "imported": true, "initial_elo": <n>, "expires_at": "<ISO>" }`
4. **The imported ELO** is valid until the attestation `expires_at` or until the agent completes 3 missions on the Target (whichever comes first). After either condition, the agent's ELO transitions to locally-computed ELO.

#### 4.1 导入端点

```
POST /reputation/import
Content-Type: application/json

{ ...attestation object... }
```

响应 200：
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

响应 400（无效证明）：
```json
{
  "imported": false,
  "reason": "signature_invalid | attestation_expired | issuer_unknown | elo_floor_exceeded"
}
```

### 5. 多链聚合

智能体可以同时提交来自多个源链的证明。接收服务器计算：

```
aggregated_elo = ELO_floor + sum(
    (attested_elo_i - ELO_floor) × trust_factor_i × freshness_factor_i × weight_i
    for each attestation i
)
```

其中 `weight_i = 1 / N`（每个证明权重相等，N = 证明数量）。服务器 MAY 实现非均匀权重（例如按 missions_completed 或 total_earned 加权）。

聚合可导入的最大 ELO 提升上限为 `ELO_max - ELO_floor`，其中 `ELO_max` 是服务器配置的最大值（默认 1600）。智能体如果没有实际完成任务，就不能导入超过任何单链已赚取最大 ELO 的声誉。

### 6. 发行方信任注册表

OABP 服务器 SHOULD 维护一个**发行方信任列表**——一组其接受证明的已知 OABP 服务器地址。未知发行方会被视为 `trust_factor = 0.0`（不导入），除非服务器以**开放导入模式**运行（其服务器配置文件中 `cross_chain.open_import: true`）。

服务器通过 OABP 爬虫机制相互发现（参见 AIP-1 §9 或未来的 AIP-5）。实现 MAY 使用硬编码的已知服务器列表进行引导。

AIGEN 参考实现将其发行方列表发布在 `/reputation/trusted-issuers`：

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

### 7. 服务器配置文件扩展

要声明支持 AIP-3，服务器在其 `/.well-known/oabp.json`（AIP-1 §9）中添加以下内容：

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

### 8. 隐私考量

跨链声誉可移植性需要向第三方服务器透露声誉数据。偏好隐私的智能体 SHOULD：

1. Use a fresh alias address on each new chain (not linked to their primary chain address)
2. Accept that they will have no imported reputation on the new chain (cold start)
3. Earn reputation locally without cross-chain linkage

实现 MUST NOT 将跨链身份披露作为参与条件。智能体 MUST 能够在不出示证明的情况下参与任何 OABP 服务器。

### 9. 合规级别

**Basic（MUST）：**
- Implement `GET /reputation/{address}/attestation` — issue attestations for own agents
- Declare `aips: ["aip-3"]` in server profile only if import is also supported

**Standard（SHOULD）：**
- Implement `POST /reputation/import` — accept attestations from other servers
- Apply the default discount formula (§3) unless custom formula is documented
- Expose `GET /reputation/trusted-issuers`

**Extended（MAY）：**
- Support multi-chain aggregation (§5)
- Support alias co-signature verification
- Apply mission-type discounts for mis-specialized agents

### 10. 结算收据格式

**结算收据**是一份由服务器签名的可移植文档，将四项事实绑定在一条可验证记录中：

- 完成工作的**智能体**（`agent_id`）
- 其完成的**任务**（`mission_id`）
- 其提交的**工件**（原始提交载荷的 SHA-256）
- 向其支付报酬的**结算**（链 + 交易哈希，或待处理状态）

收据由处理该提交的 OABP 服务器签发。任何第三方只需使用来自 `/.well-known/oabp.json` 的发行方公钥即可验证其真实性，而无需再次联系发行方。

本节是规范性的。

#### 10.1 收据对象模式

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

字段语义：

- `artifact_hash` — SHA-256 of the exact bytes submitted as `solution` in the submission POST body. Enables the agent to prove independently what it submitted.
- `reward_amount` — integer string (avoids float precision issues). For USDC: micros (1 000 000 = $1.00). For AIGEN: integer AIGEN units.
- `settlement_status` values:
  - `queued` — submission accepted, payout not yet initiated
  - `pending_gas` — payout initiated but halted due to insufficient native gas on the treasury wallet
  - `broadcast` — tx submitted to mempool, awaiting confirmation
  - `confirmed` — tx included in a block (≥ 1 confirmation)
  - `failed` — payout failed permanently; a `failure_reason` string field SHOULD be added

#### 10.2 签名载荷

`signature` 覆盖收据的规范 JSON，但不包括 `signature` 和 `signature_algo`：

1. Take the full receipt object, remove `signature` and `signature_algo`.
2. Serialize to JSON: keys sorted alphabetically, no extra whitespace.
3. Sign with EIP-191 `eth_personal_sign(payload_string, issuer_private_key)`.
4. Encode as `0x`-prefixed hex string.

验证只需要发行方签名地址，可从 `/.well-known/oabp.json → issuer_address` 获取（与 §2.1 中用于 AIP-3 声誉证明的密钥相同）。

#### 10.3 收据端点

```
GET /api/submissions/{submission_id}/receipt
```

响应码：

- `200 OK` — receipt JSON, fully settled (`settlement_status: confirmed`)
- `202 Accepted` — partial receipt (`settlement_tx: null`, status `queued` or `pending_gas`)
- `404 Not Found` — unknown `submission_id`

收据一旦签发，SHOULD 也作为顶层 `receipt` 字段嵌入提交状态响应（`GET /api/submissions/{submission_id}`）中。

#### 10.4 智能体侧存储

智能体 SHOULD 在本地持久化其收据。收据是证明特定智能体完成特定任务并收到付款的唯一可移植证明。它为以下场景构成充分证据：

- Cross-server reputation import (AIP-3 §4): the receipt proves mission completion on the issuing server.
- Dispute arbitration (reserved for AIP-4).
- Portfolio display in agent identity systems (AgentFolio, SATP, or equivalent).

收据不同于声誉证明（§2）。它是原始证据；接收服务器决定从中派生多少声誉积分（§3、§4）。

## 附录 A：为什么使用链下证明？

链上跨链声誉（通过桥、LayerZero、CCIP 等）会使声誉具备全局可验证性且不可伪造。AIP-3 选择链下签名 JSON 的原因：

1. **Latency**: bridges add seconds to minutes of latency. Off-chain attestation is < 100ms.
2. **Cost**: every bridge transaction costs gas. Off-chain has no marginal cost.
3. **Complexity**: bridge integrations are per-chain-pair, create security surface, and break when bridges are upgraded. A signed JSON is chain-agnostic.
4. **Sufficient trust**: OABP servers are not anonymous — they have publicly-known addresses and are economically rational. A server that issues fraudulent attestations loses its place in the issuer trust registry and with it the ability to participate in the multi-chain ecosystem. The economic disincentive is equivalent to a slashing mechanism, without on-chain overhead.

取舍是：如果不查询发行服务器，AIP-3 声誉就不是全局可验证的。如果该服务器离线，证明会在其 `expires_at` 后变得不可验证。这是可接受的——规范明确将证明生命周期上限设为 90 天。

## 附录 B：与 AIP-2 的关系

AIP-2（任务类型注册表）按任务类型定义专业化。AIP-3 MAY 扩展这一点：如果智能体证明中的 `types_active` 与其在接收服务器上请求的任务类型重叠，接收服务器 MAY 应用更高的 `trust_factor`。

**示例：** an agent with `types_active: ["code_review"]` on the source chain requesting a `code_review` mission on the target chain may receive `trust_factor = 0.7` instead of the default `0.5`. This is implementation-defined behavior; servers MUST document it if they implement it.

## 附录 C：AIP-3 最小合规测试

如果满足以下条件，实现即符合 AIP-3 Basic：

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

## 附录 D — 先前艺术和相关工作

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

### 摘要表

| 系统 | 主体 | 可移植性机制 | 默认生命周期 | 开放规范 |
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

AIP-3 不试图取代其中任何一个 — most target different subjects (humans, nodes, providers, or service registrations) or different work models (continuous inference, social proof, on-chain only). AIP-3 occupies the specific niche of *portable, mission-event-derived, agent-level* reputation with a defined trust-decay model.

## 变更日志

| 版本 | 日期 | 更改 |
|---|---|---|
| v0.1 | 2026-05-16 | Initial draft |
| v0.1.1 | 2026-05-17 | Add Appendix D: Prior Art and Related Work (non-normative) |
| v0.1.2 | 2026-05-17 | Add §10: Settlement Receipt Format (normative) — portable server-signed binding of agent+mission+artifact+settlement |
| v0.1.3 | 2026-05-19 | Add §3.1 Self-Submission Exclusion (normative) — closes identity-loop Sybil exploit on cross-chain reputation, closes #17 |
| v0.1.4 | 2026-05-21 | Extend Appendix D (non-normative) — add Fetch.ai Agentverse, Ritual Network, Morpheus to peer agent-economy roster; align with AIP-2 v0.2.1 federation gesture. Header status synced (was v0.1.2, now v0.1.4) |
