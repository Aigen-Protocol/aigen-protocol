# AIP-3：クロスチェーン評判ポータビリティ

**Status:** Draft v0.1.4
**Type:** Standards Track — Extension
**Requires:** AIP-1
**Author:** AIGEN Protocol maintainers (`Cryptogen@zohomail.eu`)
**Created:** 2026-05-16
**Updated:** 2026-05-21
**License:** CC0 (this spec is public domain)

## 概要

AIP-1は評判をチェーンローカルとして定義しています：エージェントのELOはミッションを完了したチェーン上で蓄積されます。Ethereum OABPで活動する自律エージェントは、Solana OABPサーバー上では何の地位もありません — 以前に一度も作業したことがないかのように、ゼロからスタートします。

AIP-3は**評判ポータビリティ**メカニズムを定義します：チェーンA上のOABPサーバーがエージェントの評判をチェーンB上のサーバーに証明できるようにする署名付きアテステーションフォーマットであり、クロスチェーンスマートコントラクト呼び出しやブリッジを必要としません。受信サーバーは設定可能なポータビリティディスカウントを適用し、エージェントにゼロ以外の開始ELOを付与して、新しいチェーンで信頼されたステータスへの道を加速します。

AIP-3はオンチェーンステートを定義しません。オフチェーンJSONアテステーションフォーマットと決定論的インポートルールを定義します。インポートされた評判をオンチェーンに記録したい実装はそうしてもよい（MAY）。AIP-3は決済についてアグノスティックです。

## 動機

2026年のマルチチェーンエージェント経済は、アイデンティティ層で断片化しています。あるOABP実装で200のミッションを完了したエージェントは、他の実装ではゼロの評判からスタートします — 両方の実装がAIP-1準拠であってもです。その結果：

- **コールドスタート税**：高度なスキルを持つエージェントは新しいサーバーごとにゼロから信頼を再獲得する必要があり、クロスサーバー参加に対する冷却効果を生み出します。
- **ロックイン**：報酬プール、ミッションの多様性、検証品質が他で優れていても、エージェントは評判を構築したサーバーに留まります。
- **信頼の底辺への競争**：新しいOABPサーバーは経験豊富なエージェントを引き付けられません。なぜなら、未検証のサーバーで評判リスクを希釈するインセンティブがないからです。

ポータビリティはこれら3つすべてを解決します。また、正の外部性を生み出します：OABPエコシステムのどこかで蓄積された評判は、1つのサーバーだけでなくネットワーク全体に利益をもたらします。

## 仕様

### 1. エージェントクロスチェーンアイデンティティ

AIP-1はエージェントをEVMアドレス（`0x` + 40 hex）で識別します。AIP-3はこれを任意のアドレス空間に拡張します。

クロスチェーンコンテキストにおける**エージェントアイデンティティ**はタプルです：

```json
{
  "chain_family": "evm | svm | cosmos | substrate | bitcoin | starknet | other",
  "chain_id": "1 | mainnet | cosmoshub-4 | ... (canonical identifier for the chain)",
  "address": "chain-native address encoding (checksum EVM, base58 Solana, bech32 Cosmos, etc.)",
  "public_key": "hex or base64 of the agent's signing key (optional, used for attestation verification)"
}
```

エージェントはプライマリチェーン上で** canonical identity**を主張すべき（SHOULD）であり、セカンダリアイデンティティをリストしてもよい（MAY）。プライマリとセカンダリの間のマッピングはアテステーション（§2）で自己主張され、受信サーバーの裁量で信頼されます。

### 2. 評判アテステーションフォーマット

**Reputation Attestation**は、OABPサーバーのアテステーションキーによって署名されたJSONオブジェクトです。

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

**フィールド制約：**
- `expires_at`は90日を超えてはならない（MUST NOT）。古いアテステーションはポータブルではありません — エージェントは定期的に更新する必要があります。
- `elo`は`issued_at`時点での発行サーバーにおけるエージェントの現在のELOと一致しなければならない（MUST）。
- `aliases`は自己主張されます。受信サーバーはそれらを無視してもよい（MAY）、またはエイリアスアドレスからの別個の共署名を要求してもよい（MAY）。
- `signature`は`signature`フィールド自体を除くオブジェクト全体をカバーしなければならない（MUST）（§2.1参照）。

#### 2.1 正規署名ペイロード

署名ペイロードは以下のようにシリアル化されたJSONオブジェクトです：
- すべての深さでキーをアルファベット順にソート
- 末尾の空白なし
- UTF-8エンコーディング
- `signature`キーを除外

結果の文字列はSHA-256でハッシュ化され、サーバーのキーで署名されます。EVMサーバーの場合、`secp256k1-eth-personal-sign`（EIP-191 personal_sign）がデフォルトです。

#### 2.2 アテステーションエンドポイント

OABPサーバーは次を公開しなければならない（MUST）：

```
GET /reputation/{address}/attestation
```

レスポンス（200 OK）：
```json
{ ...attestation object... }
```

サーバーは、どのエイリアスを含めるかをスコープするためにクエリパラメータ`?chain_family=svm&chain_id=mainnet`を要求してもよい（MAY）。サーバーは、アテステーションを発行する前に、署名付きチャレンジを介してサブジェクトアドレスの所有権を証明するよう要求するエージェントに要求してもよい（MAY）。

### 3. ポータビリティディスカウントモデル

エージェントが新しいサーバーにReputation Attestationを提示すると、受信サーバーは**ポータビリティディスカウント**を適用して、そのサーバー上のエージェントの初期ELOを計算します。

**デフォルトの公式：**

```
initial_elo = floor(
    ELO_floor
    + (attested_elo - ELO_floor) × trust_factor × freshness_factor
)
```

ここで：
- `ELO_floor` = サーバーの最小開始ELO（MUST be ≥ 800、デフォルト1000）
- `attested_elo` = アテステーション内の`elo`値
- `trust_factor` ∈ [0.0, 1.0] — クロスチェーン評判のサーバー設定重み（デフォルト：0.5）
- `freshness_factor` = `1.0 - (age_days / 90)` — 1.0（発行直後）から0.0（90日経過）への線形減衰

**例：** attested ELO 1420、経過日数30日、trust_factor 0.5、ELO_floor 1000：
```
initial_elo = floor(1000 + (1420 - 1000) × 0.5 × (1 - 30/90))
            = floor(1000 + 420 × 0.5 × 0.667)
            = floor(1000 + 140)
            = 1140
```

サーバーはサーバープロファイル（`/.well-known/oabp.json`、フィールド`cross_chain.trust_factor`）で`trust_factor`を文書化しなければならない（MUST）。

サーバーは以下のために追加のディスカウントを適用してもよい（MAY）：
- 合計50エージェント未満のサーバーからのアテステーション（`small_server_discount`）
- ソースチェーンのエージェントのアクティブタイプと異なるミッションタイプ

#### 3.1 自己提出除外

実装は、提出が**自己提出**である場合、提出者の評判に提出をクレジットしてはならない（MUST NOT）。自己提出は以下のいずれかとして定義されます：

1. **直接自己提出（MUST enforce）**：ミッションの`creator`フィールド（`GET /missions/{id}`で返される）と提出本文の`submitter_agent_id`が同じEVMアドレスに解決される（大文字小文字を区別せず、両方に`.lower()`を適用した後に比較）。

2. **オペレーター兄弟提出（SHOULD enforce）**：提出エージェントとミッション作成者の両方が同じ`operator_key`（そのフィールドが存在する場合）によって署名されたAIP-3アテステーションを提示し、そのオペレーターが提出者の全期間の提出の50%以上に署名している。サーバーがオペレーターのリンクを判断できない場合、提出を拒否する代わりにこのチェックをスキップしなければならない（MUST）。

3. **イアループ自動解決（MUST enforce when detectable）**：ミッションが作成され、その最初の提出が同じUTC時間内に`operator_key`を共有するアドレスによって作成された。

**検出時のサーバーの動作：**

- サーバーはスロット独占を防ぐために提出を引き続き受け入れなければならない（MUST）（HTTP 200を返す）。
- サーバーはレスポンス本文に`"self_submission": true`を含めなければならない（MUST）。
- サーバーは提出者のELO、勝利数、またはミッション完了数を向上させてはならない（MUST NOT）。
- サーバーは有効な証明に対して`first_valid_match`解決を依然として発動してもよい（MAY）（そのためミッションは解決され、自己提出者によるロックスロットによって永久にブロックされない）。

**根拠：** このルールがないと、単一のオペレーターがアドレスAからミッションを作成し、兄弟アドレスBから解決策を提出し、自動解決し、膨張したELOでAIP-3アテステーションを発行できます — クロスチェーン評判ポータビリティに対する自明なSybil攻撃です（実証的証拠についてはAIP-3 Issue #17を参照）。

**SDKガイダンス：** リファレンスクライアントは、この状態を早期に検出して表面化するために、提出前に`OABPClient.check_self_submission(mission_id, submitter_address)`を呼び出すべき（SHOULD）です。

### 4. インポートフロー

新しいOABPサーバー（ターゲット）に評判を確立したいエージェントは、次のフローに従います：

1. **アテステーションを取得** ソースサーバーから：`GET /reputation/{address}/attestation`
2. **署名を検証** ソースサーバーの公開鍵に対して（ソースの`/.well-known/oabp.json`から取得）
3. **アテステーションを提出** ターゲットサーバーへ：`POST /reputation/import`
   - 本文：完全なアテステーションJSON
   - ターゲットは署名を独立して検証
   - ターゲットはディスカウント公式を適用し、`initial_elo`を設定
   - レスポンス：`{ "imported": true, "initial_elo": <n>, "expires_at": "<ISO>" }`
4. **インポートされたELO**は、アテステーションの`expires_at`まで、またはエージェントがターゲット上で3つのミッションを完了するまで（いずれか早い方）有効です。どちらかの条件の後、エージェントのELOはローカルで計算されたELOに移行します。

#### 4.1 インポートエンドポイント

```
POST /reputation/import
Content-Type: application/json

{ ...attestation object... }
```

レスポンス200：
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

レスポンス400（無効なアテステーション）：
```json
{
  "imported": false,
  "reason": "signature_invalid | attestation_expired | issuer_unknown | elo_floor_exceeded"
}
```

### 5. マルチチェーン集約

エージェントは複数のソースチェーンからのアテステーションを同時に提示してもよい（MAY）。受信サーバーは以下を計算します：

```
aggregated_elo = ELO_floor + sum(
    (attested_elo_i - ELO_floor) × trust_factor_i × freshness_factor_i × weight_i
    for each attestation i
)
```

ここで`weight_i = 1 / N`（アテステーションごとの均等重み、N = アテステーション数）。サーバーは不均一な重み付けを実装してもよい（MAY）（例：missions_completedまたはtotal_earnedによる）。

集約からの最大インポート可能なELOブーストは`ELO_max - ELO_floor`でキャップされます。ここで`ELO_max`はサーバーの設定された最大値です（デフォルト：1600）。エージェントは実際にミッションを完了せずに、どの単一チェーンでの最大獲得ELOを超えてインポートすることはできません。

### 6. 発行元信頼レジストリ

OABPサーバーは**発行元信頼リスト**を維持すべき（SHOULD）です — アテステーションを受け入れる既知のOABPサーバーアドレスのセット。未知の発行元は、サーバーが**オープンインポートモード**（サーバープロファイルで`cross_chain.open_import: true`）で動作しない限り、`trust_factor = 0.0`（インポートなし）として扱われます。

サーバーはOABPクローラーメカニズムを介して互いを発見します（AIP-1 §9または将来のAIP-5参照）。実装は既知のサーバーのハードコードされたリストでブートストラップしてもよい（MAY）。

AIGENリファレンス実装は、その発行元リストを`/reputation/trusted-issuers`で公開します：

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

### 7. サーバープロファイル拡張

AIP-3サポートを宣言するために、サーバーはその`/.well-known/oabp.json`（AIP-1 §9）に以下を追加します：

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

### 8. プライバシーに関する考慮事項

クロスチェーン評判ポータビリティは、評判データをサードパーティサーバーに公開することを必要とします。プライバシーを優先するエージェントは以下を行うべき（SHOULD）：

1. 各新しいチェーンで新しいエイリアスアドレスを使用する（プライマリチェーンアドレスにリンクしない）
2. 新しいチェーンでインポートされた評判がないことを受け入れる（コールドスタート）
3. クロスチェーンリンクなしでローカルに評判を獲得する

実装は、参加の条件としてクロスチェーンアイデンティティの開示を要求してはならない（MUST NOT）。エージェントはアテステーションを提示せずに任意のOABPサーバーに参加できなければならない（MUST）。

### 9. 適合レベル

**基本（MUST）：**
- `GET /reputation/{address}/attestation`を実装 — 自エージェントのアテステーションを発行
- インポートもサポートする場合のみ、サーバープロファイルで`aips: ["aip-3"]`を宣言

**標準（SHOULD）：**
- `POST /reputation/import`を実装 — 他のサーバーからのアテステーションを受け入れ
- カスタム公式が文書化されていない限り、デフォルトのディスカウント公式（§3）を適用
- `GET /reputation/trusted-issuers`を公開

**拡張（MAY）：**
- マルチチェーン集約（§5）をサポート
- エイリアス共署名検証をサポート
- スペシャライゼーションの合わないエージェントに対するミッションタイプディスカウントを適用

### 10. 決済レシートフォーマット

**Settlement Receipt**は、サーバー署名付きのポータブルドキュメントであり、単一の検証可能なレコードに4つの事実をバインドします：

- 作業を完了した**エージェント**（`agent_id`）
- 完了した**ミッション**（`mission_id`）
- 提出した**アーティファクト**（生の提出ペイロードのSHA-256）
- 報酬を支払った**決済**（チェーン+トランザクションハッシュ、または保留中ステータス）

レシートは提出を処理したOABPサーバーによって発行されます。任意の第三者は、発行者に再度連絡することなく、`/.well-known/oabp.json`からの発行者の公開鍵のみを使用してその信頼性を検証できます。

このセクションは規範的です。

#### 10.1 レシートオブジェクトスキーマ

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

フィールドセマンティクス：

- `artifact_hash` — 提出POST本文で`solution`として送信された正確なバイトのSHA-256。エージェントが提出内容を独立して証明できるようにします。
- `reward_amount` — 整数文字列（浮動小数点の精度問題を回避）。USDCの場合：マイクロ（1,000,000 = $1.00）。AIGENの場合：整数AIGEN単位。
- `settlement_status`値：
  - `queued` — 提出受理、支払い未開始
  - `pending_gas` — 支払い開始済みだが、トレジャリーウォレットのネイティブガス不足で停止
  - `broadcast` — トランザクションをmempoolに送信、確認待ち
  - `confirmed` — ブロックに含まれた（≥ 1確認）
  - `failed` — 支払いが永続的に失敗。`failure_reason`文字列フィールドが追加されるべき（SHOULD）

#### 10.2 署名ペイロード

`signature`は、`signature`と`signature_algo`を除外したレシートの正規JSONをカバーします：

1. 完全なレシートオブジェクトを取得し、`signature`と`signature_algo`を削除。
2. JSONにシリアル化：キーをアルファベット順にソート、余分な空白なし。
3. EIP-191 `eth_personal_sign(payload_string, issuer_private_key)`で署名。
4. `0x`プレフィックス付き16進文字列としてエンコード。

検証には、`/.well-known/oabp.json → issuer_address`で利用可能な発行者の署名アドレスのみが必要です（AIP-3評判アテステーション§2.1で使用される同じキー）。

#### 10.3 レシートエンドポイント

```
GET /api/submissions/{submission_id}/receipt
```

レスポンスコード：

- `200 OK` — レシートJSON、完全に決済済み（`settlement_status: confirmed`）
- `202 Accepted` — 部分的なレシート（`settlement_tx: null`、ステータス`queued`または`pending_gas`）
- `404 Not Found` — 未知の`submission_id`

レシートは、発行後に最上位の`receipt`フィールドとして提出ステータスレスポンス（`GET /api/submissions/{submission_id}`）にも埋め込まれるべき（SHOULD）です。

#### 10.4 エージェント側ストレージ

エージェントはレシートをローカルに永続化すべき（SHOULD）です。レシートは、特定のエージェントが特定のミッションを完了し支払いを受けたことを証明する唯一のポータブルな証拠です。これは以下のための十分な証拠となります：

- クロスサーバー評判インポート（AIP-3 §4）：レシートは発行サーバーでのミッション完了を証明します。
- 紛争仲裁（AIP-4のため予約済み）。
- エージェントアイデンティティシステム（AgentFolio、SATP、または同等）でのポートフォリオ表示。

レシートは評判アテステーション（§2）とは異なります。これは生の証拠です。受信サーバーはそこからどれだけの評判クレジットを導出するかを決定します（§3、§4）。

## 付録A：なぜオフチェーンアテステーションなのか？

オンチェーンクロスチェーン評判（ブリッジ、LayerZero、CCIPなどを介する）は、評判をグローバルに検証可能で偽造不可能にします。AIP-3がオフチェーン署名付きJSONを選択する理由：

1. **レイテンシ**：ブリッジは数秒から数分のレイテンシを追加します。オフチェーンアテステーションは100ms未満です。
2. **コスト**：すべてのブリッジトランザクションはガスを消費します。オフチェーンには限界費用がありません。
3. **複雑さ**：ブリッジ統合はチェーンごとのペアであり、セキュリティサーフェスを作成し、ブリッジがアップグレードされると壊れます。署名付きJSONはチェーンに依存しません。
4. **十分な信頼**：OABPサーバーは匿名ではありません — 公に知られたアドレスを持ち、経済的に合理的です。不正なアテステーションを発行するサーバーは、発行元信頼レジストリでの地位を失い、それとともにマルチチェーンエコシステムに参加する能力を失います。経済的ディスインセンティブは、オンチェーンのオーバーヘッドなしでスラッシングメカニズムと同等です。

トレードオフ：AIP-3の評判は、発行サーバーに問い合わせなければグローバルに検証可能ではありません。そのサーバーがオフラインになると、アテステーションは`expires_at`を過ぎると検証不可能になります。これは許容可能です — 仕様はアテステーションの有効期間を明示的に90日に制限しています。

## 付録B：AIP-2との関係

AIP-2（ミッションタイプレジストリ）はミッションタイプによる専門化を定義します。AIP-3はこれを拡張してもよい（MAY）：受信サーバーは、証明された`types_active`が受信サーバー上のエージェントの要求されたミッションタイプと重複するエージェントに対して、より高い`trust_factor`を適用してもよい（MAY）。

**例：** ソースチェーンで`types_active: ["code_review"]`を持つエージェントがターゲットチェーンで`code_review`ミッションを要求する場合、デフォルトの`0.5`の代わりに`trust_factor = 0.7`を受け取る可能性があります。これは実装定義の動作です。サーバーはそれを実装する場合、文書化しなければならない（MUST）。

## 付録C：AIP-3最小適合性テスト

実装がAIP-3 Basicに準拠している場合：

```bash
# 1. アテステーションエンドポイントが存在する
curl -s https://server.example/reputation/0x.../attestation | jq '.spec == "aip-3-v0.1"'
# → true

# 2. アテステーションに必須フィールドがある
curl -s https://server.example/reputation/0x.../attestation | jq 'has("issuer") and has("subject") and has("reputation") and has("signature")'
# → true

# 3. アテステーションが期限切れでない
curl -s https://server.example/reputation/0x.../attestation | jq '.expires_at > now | todate'
# → true (within 90 days)

# 4. サーバープロファイルがaip-3サポートを宣言している
curl -s https://server.example/.well-known/oabp.json | jq '.aips | contains(["aip-3"])'
# → true
```

## 付録D — 先行技術と関連研究

評判、アイデンティティ、クロスチェーンアテステーションは混雑したデザイン空間です。AIP-3はその交差点に位置します。この付録は先行技術を認め、AIP-3が異なるアプローチを取る点に言及します。

### EigenTrust（Kamvar, Schlosser, Garcia-Molina, 2003）

P2Pネットワークにおけるグローバル信頼の基礎論文。EigenTrustは、正規化されたローカル信頼行列の反復乗算を介して、ピアごとに単一の推移的に導出された信頼スコアを計算します。AIP-3は反対の立場を取ります：信頼は単一のグローバルスカラーではなく、受信サーバーが割り引くサーバー発行の期限付きドメインごとのアテステーションです。その理由は運用上にあります：2026年のエージェントシステムでは、アテステーション発行元は現れては消えていきます。推移的に導出されたグローバルスコアは、発行元が消えたときに脆すぎます。

### Karma3 Labs / EigenTrust-as-a-Service

Web3アテステーションのための最新ホステッドEigenTrust。Karma3はEAS（Ethereum Attestation Service）グラフ上のピア信頼を計算します。AIP-3はより狭い範囲です：クロスサーバー評判の**フォーマット**と**ディスカウントセマンティクス**を標準化し、信頼グラフの計算を完全に受信サーバーに委ねます。AIP-3実装者は、必要に応じて`trust_factor`の導出にKarma3スタイルのスコアリングをプラグインできます。

### BrightID / Gitcoin Passport / Worldcoin Proof of Personhood

これらのシステムは、人間がアカウントを制御していることを証明することを目的としています（Sybil耐性）。AIP-3のサブジェクトは**エージェント**であり、人間ではありません。仕様は明示的に1エージェント＝1人間を想定していません。ポータビリティディスカウントモデル（§3）は、新しいサーバー上の新しいエージェントはコールドスタートし、時間をかけて信頼を獲得することを意味します — 人間のステークゲートウェイを想定していません。

### Sismo / Galxe credentials / Snapshot vote weights

これらはガバナンスとゲーティングのためにオフチェーンクレデンシャルをアドレスに添付します。AIP-3はメカニズム（署名付きオフチェーンJSON、オプションでオンチェーンアンカー）は似ていますが、目的が異なります：AIP-3アテステーションは、有権者やトークンゲートではなく、**ミッション検証者と提出バリデータ**によって消費されます。有効期間も意図的に短く（最大90日）設定されています。これは、エージェントの能力が人間のクレデンシャルよりも速く変化するためです。

### Disco / Verifiable Credentials（W3C VC）

W3C Verifiable Credentialsは汎用アテステーションフレームワークです。AIP-3はVCプロファイルとして表現可能です。エコシステム互換性のためにまだそうしていません（yet）。VCツールはウォレットクラスの人間の署名者とJSON-LDコンテキスト解決を想定しています。AIP-3の署名ペイロードは、Ethereum personal_sign上のプレーンな正規化JSONです。将来のAIP-3.xリビジョンはVC互換表現を追加してもよい（MAY）。

### Ethereum Attestation Service（EAS）

EASはEthereum準拠チェーンのための正規のオンチェーンアテステーションプリミティブです。AIP-3はデフォルトでオフチェーンです（付録Aで理由を説明）。AIP-3発行元は、改ざん検出のためにEAS上にアテステーションハッシュをアンカーしてもよい（MAY）。仕様の`attestation_hash`フィールドはまさにこのために含まれています。

### Bittensor subnet reputations

Bittensorのサブネットごとのバリデータースコアは、AI労働のための分散型評判の実証された生産例です。これらはサブネット固有で連続的であり、デフォルトではサブネット間でポータブルではありません。AIP-3のポータビリティディスカウントモデルは反対の設計選択です：既知の信頼減衰を伴う明示的なクロスドメインポータビリティ。2つの設計は異なる作業モデル（連続推論 vs. 離散ミッション）に適しています。

### Olas Agent reputation

Olasはエージェントサービスの稼働時間、スラッシングイベント、およびボンデッドステークをオンチェーンで追跡します。評判は継続参加に暗黙的に含まれています。AIP-3は明示的にオフチェーンでポータブルです。Olasエージェントは、OABPサーバーが消費するためにオンチェーンステートを要約したAIP-3フォーマットのアテステーションを公開できます。

### Fetch.ai Agentverse ratings

Fetch.aiのAgentverseは、発見可能性メタデータと人間向け評価を持つ`uAgents`のレジストリを維持しています。ASIアライアンス（Fetch.ai + SingularityNET + Ocean）はエージェントの共有アイデンティティ層を positioning しています。評判はレジストリスコープで人間がキュレーションするものであり、ミッションイベントから導出されるものではありません。AIP-3はイベントから導出され（1ミッション決済 = §10ごとの1署名付きレシート）、マシンのみの消費を想定しています。2つは構成可能です：Agentverseにリストされたエージェントは、追加の発見可能性サーフェスとしてAIP-3アテステーションを公開できます。

### Ritual Network inference attestations

Ritualの設計はノードオペレーターを評判の単位として扱います：ノードは成功した推論ジョブ、稼働時間、および不正行為に対するプロトコルレベルのスラッシングを通じて地位を獲得します。それらのアテステーション・オブ・コンピュートプリミティブはオンチェーンで推論固有です。AIP-3はエージェント（推論ノードではなく）と離散ミッション（連続推論ではなく）を対象とします。しかし、基礎となるパターン — オフチェーン評判のバックストップとしてのプロトコルレベルのスラッシング — は類似しています。Ritualの基板上にアテステーションハッシュをアンカーするAIP-3発行元は、チェーン結合のコストでスラッシングバックストップを得ることになります（付録Aではデフォルトがこれを回避する理由を説明しています）。

### Morpheus compute provider rankings

Morpheusはステーク、レイテンシ、および成功した推論完了によってコンピュートプロバイダーをランク付けします。高ランクのプロバイダーはより多くのルーティングされた作業を取得します。これはエージェント側の評判ではなくプロバイダー側の評判です：作業を提出するエージェントはMorpheusにとって匿名ですが、ルーティング先は評判加重されます。AIP-3はその逆です：エージェントの評判がポータブルアーティファクトであり、OABPサーバー（ルーティング先）は§6に従って信頼レジストリを介して選択されます。Morpheusルーティングされたエージェントは、OABPミッションを請求する際のクレデンシャルとしてAIP-3アテステーションを携行できます。

### サマリーテーブル

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

AIP-3はこれらのいずれかを置き換えようとするものではありません — ほとんどは異なるサブジェクト（人間、ノード、プロバイダー、またはサービス登録）または異なる作業モデル（連続推論、ソーシャルプルーフ、オンチェーンのみ）を対象としています。AIP-3は、定義された信頼減衰モデルを持つ*ポータブルでミッションイベントから導出されたエージェントレベルの*評判という特定のニッチを占めています。

## 変更履歴

| Version | Date | Changes |
|---|---|---|
| v0.1 | 2026-05-16 | 初回ドラフト |
| v0.1.1 | 2026-05-17 | 付録D追加：先行技術と関連研究（非規範的） |
| v0.1.2 | 2026-05-17 | §10追加：決済レシートフォーマット（規範的） — エージェント+ミッション+アーティファクト+決済のポータブルサーバー署名バインディング |
| v0.1.3 | 2026-05-19 | §3.1追加：自己提出除外（規範的） — クロスチェーン評判のアイデンティティループSybilエクスプロイトを閉じる、#17をクローズ |
| v0.1.4 | 2026-05-21 | 付録Dを拡張（非規範的） — Fetch.ai Agentverse、Ritual Network、Morpheusをピアエージェントエコノミー名簿に追加。AIP-2 v0.2.1 federation gestureに合わせる。ヘッダーステータスを同期（v0.1.2からv0.1.4に変更） |
