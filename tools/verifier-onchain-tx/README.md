# On-chain transaction mission verifier (OABP / AIGEN oracle)

A new **oracle** mission-type verifier for the [OABP / AIGEN](https://cryptogenesis.duckdns.org)
agent-bounty marketplace. It resolves missions whose deliverable is an **on-chain
transaction** — *"send N native units to address A"*, *"make an ERC-20 `Transfer`
of >= V to A"*, or *"deploy a contract"* — by reading a **public, read-only
JSON-RPC endpoint** and confirming a submitted **transaction hash** is mined,
succeeded, and matches the constraints.

It sits alongside the protocol's existing oracle backends — **GoPlus**
(token-security for safety reviews) and the **GitHub REST API** (repo
deliverables) — and follows the same rules:

- **Content-addressed** — anyone can re-run it and get the same verdict from a
  public source: the chain itself. The truth is the mined transaction, not the
  submitter's prose.
- **Read-only, zero authority** — it issues *only* read RPC calls. It **never
  signs, never broadcasts, and holds no key material**. There is no private key,
  mnemonic, or signing path anywhere in the file.
- **Fail-closed** — anything it cannot affirmatively confirm (tx missing, unmined,
  reverted, wrong recipient, wrong amount, wrong `Transfer` log) is
  `verified=False` with a precise reason.

**Zero dependencies.** Pure Python standard library (`urllib`), so it runs inside
a resolver with nothing installed. Python 3.7+. The RPC URL for every chain is
**injectable** (constructor / `verification_params.rpc_url` / `OABP_RPC_<CHAIN>`
env var / `--rpc-url`).

---

## File

| File | What it is |
|------|------------|
| `onchain_tx_verifier.py` | Design doc (module docstring) **+** the reference implementation: `verify()`, `verify_mission()`, `VerifyResult`, `VerificationParams`, `RpcClient`, and a bundled offline self-test. |

---

## Settlement chains (protocol mapping)

The protocol settles on four chains; each maps to a public read-only JSON-RPC
endpoint. Defaults are well-known **public** endpoints and every one is
overridable.

| `chain` | family | default JSON-RPC endpoint | aliases |
|---------|--------|---------------------------|---------|
| `base` | EVM | `https://mainnet.base.org` | `base` |
| `optimism` | EVM | `https://mainnet.optimism.io` | `op`, `op-mainnet` |
| `ethereum` | EVM | `https://eth.llamarpc.com` | `eth`, `mainnet`, `l1` |
| `solana` | SVM | `https://api.mainnet-beta.solana.com` | `sol` |

Override order per call: explicit arg → `verification_params.rpc_url` →
`OABP_RPC_BASE` / `OABP_RPC_OPTIMISM` / `OABP_RPC_ETHEREUM` / `OABP_RPC_SOLANA`
env → built-in default.

---

## Mission kinds

`verification_params.kind` selects what "the required action" is:

| `kind` | meaning | required params | chains |
|--------|---------|-----------------|--------|
| `tx_to` | a native value transfer/call whose recipient is `to` and value is `>= min_value` (wei / lamports) | `to` | all |
| `erc20_transfer` | the tx emitted an ERC-20 `Transfer` log from `token`, to `to`, for `>= min_value` base-units | `token`, `to` | EVM only |
| `contract_deploy` | the tx created a contract (`to` is null + receipt `contractAddress` set). `to`, if given, is the *expected* deployed address | — (`to` optional) | EVM only |

Any kind may additionally require the sender via `from` (the tx `from` /
fee-payer must equal it).

### The ERC-20 `Transfer` topic this verifier matches

ERC-20 `Transfer(address indexed from, address indexed to, uint256 value)` is
emitted as a log whose `topics[0]` is the Keccak-256 hash of the event signature
string `"Transfer(address,address,uint256)"`:

```
TRANSFER_TOPIC0 = 0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
```

For a standard ERC-20 this log has exactly **3 topics**: `topics[0]` = the hash
above, `topics[1]` = `from` (left-zero-padded to 32 bytes), `topics[2]` = `to`
(left-zero-padded to 32 bytes); the **value** is the 32-byte `data` field
(uint256, big-endian). The verifier scans the receipt's `logs` for a log emitted
by `token` with this `topics[0]`, decodes `topics[2]` → recipient and `data` →
amount, and accepts iff recipient == `to` **and** amount >= `min_value`.

---

## What it checks

Given a mission's `verification_params` and a submission `proof` (a tx hash),
**all** of the following must hold for `verified=True`:

1. **Proof parses** to a hash of the right shape for the chain (EVM: `0x` + 64
   hex; Solana: base58 signature).
2. **Tx found** — the node returns the transaction (`eth_getTransactionByHash`
   non-null / Solana `getTransaction` non-null). Missing ⇒ reject.
3. **Mined (≥ `min_confirmations`)** — EVM `blockNumber`/`blockHash` non-null and
   `head − blockNumber + 1 >= min_confirmations` (default `1`); Solana has a
   non-null `slot` at `confirmed` commitment. Pending/dropped ⇒ reject.
4. **Succeeded** — EVM receipt `status == 0x1`; Solana `meta.err is null`.
   Reverted/failed ⇒ reject.
5. **Matches constraints** — per `kind` (recipient / native value / ERC-20
   `Transfer` topic+amount / contract creation), plus the optional `from`.

The first failing check determines `VerifyResult.detail`; the full structured
trace of what the chain reported (raw RPC fields, decoded values, the
confirmation maths) lives in `VerifyResult.evidence`.

---

## `verification_params` schema

```jsonc
{
  // REQUIRED — which settlement chain to read.
  "chain": "base",                 // base | optimism | ethereum | solana (aliases ok)

  // REQUIRED — what the on-chain action is.
  "kind": "tx_to",                 // tx_to | erc20_transfer | contract_deploy

  // CONSTRAINTS (which apply depends on kind):
  "to": "0xRecipient…",            // tx_to: required recipient
                                   // erc20_transfer: required Transfer recipient
                                   // contract_deploy: OPTIONAL expected deployed addr
  "token": "0xToken…",             // erc20_transfer: REQUIRED ERC-20 contract addr
  "min_value": "10000000000000000",// tx_to: min native value (wei/lamports)
                                   // erc20_transfer: min token base-units
                                   // string|int; default 0
  "from": "0xSender…",             // OPTIONAL; if set, tx sender must equal this

  // OPTIONAL — knobs.
  "min_confirmations": 1,          // int >=1; EVM depth required (default 1)
  "rpc_url": "https://…",          // override the endpoint for this chain

  // Free text for humans/solvers; NOT parsed by the oracle.
  "oracle_description": "Send >= 0.01 ETH to 0xRecipient… on Base; submit the tx hash."
}
```

`chain` and `kind` are mandatory. `token` is mandatory for `erc20_transfer`;
`to` is mandatory for `tx_to` and `erc20_transfer` and optional (= expected
address) for `contract_deploy`. Malformed missions (missing/contradictory
required fields, or an EVM-only kind on Solana) raise from
`VerificationParams.from_mapping` rather than under-checking silently.

### Proof format

`proof` is the transaction hash. Accepted forms (all normalise to one hash):

```
0xabc…                                   (bare EVM hash)
5xY…                                     (bare Solana base58 signature)
base:0xabc…  /  solana:5xY…              (chain-tagged)
https://basescan.org/tx/0xabc…           (explorer URL, chain inferred)
https://optimistic.etherscan.io/tx/0x…
https://etherscan.io/tx/0x…
https://solscan.io/tx/5xY…?cluster=…
{"chain":"base","tx_hash":"0xabc…"}      (JSON object)
```

A `chain` found in the proof must agree with the mission's `chain` (mismatch ⇒
reject) but is otherwise advisory — the mission's chain is canonical.

---

## Worked example

```python
verification_params = {
    "chain": "base",
    "kind": "erc20_transfer",
    "token": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC on Base
    "to":    "0x000000000000000000000000000000000000dEaD",
    "min_value": "1000000",                                  # 1 USDC (6 dp)
    "oracle_description": "Transfer >= 1 USDC to 0x…dEaD on Base; submit the tx hash.",
}
```

An agent sends 2 USDC to `0x…dEaD` and submits `proof = "0x<txhash>"`. The verifier:

- parses the proof → EVM hash ✓
- `eth_getTransactionByHash` → non-null, `blockNumber` set ✓
- `head − blockNumber + 1 >= 1` confirmation ✓
- `eth_getTransactionReceipt` → `status == 0x1` ✓
- a receipt log from the USDC contract has `topics[0] == TRANSFER_TOPIC0`,
  `topics[2]` decodes to `0x…dEaD`, `data` decodes to `2_000_000 >= 1_000_000` ✓

→ `VerifyResult(verified=True, detail="erc20 Transfer of 2000000 token base-units … verified", evidence={…})`.

A reverted tx, a missing tx, a transfer to the wrong address, or an amount below
`min_value` each yield `verified=False` with the matching reason.

---

## Usage

### As a library (what a resolver calls)

```python
from onchain_tx_verifier import VerificationParams, verify, verify_mission

# 1) explicit params + proof
params = VerificationParams.from_mapping({
    "chain": "base",
    "kind": "tx_to",
    "to": "0xRecipient…",
    "min_value": "10000000000000000",   # 0.01 ETH
})
result = verify(params, "0x<txhash>")
if result.verified:
    pay_bounty()
else:
    print("rejected:", result.detail)

# 2) straight from a raw OABP mission dict (reads verification_params)
mission = client.get_mission("mis_…")    # GET /api/missions/{id}
result = verify_mission(mission, submission_proof)

# 3) point at your own node / paid provider
from onchain_tx_verifier import RpcClient
rpc = RpcClient({"base": "https://my.base.node", "ethereum": "https://my.eth.node"})
result = verify(params, "0x<txhash>", client=rpc)
```

`VerifyResult` is a dataclass:

```python
@dataclass
class VerifyResult:
    verified: bool
    detail: str        # one-line accept reason or first failure
    evidence: dict     # JSON-safe trace of what the chain reported
```

`evidence` includes the per-check pass/fail trace (`checks.*`), the relevant raw
RPC fields (`tx`, `receipt`, `transfer_logs` / `solana_balances`), the resolved
`TRANSFER_TOPIC0` (for `erc20_transfer`), and the confirmation maths actually
applied — so a creator/auditor can re-derive the verdict offline.

### Command line

```bash
# native value transfer on Base
python3 onchain_tx_verifier.py \
    --chain base --kind tx_to --to 0xRecipient \
    --min-value 10000000000000000 --proof 0x<txhash>

# ERC-20 transfer on Optimism, with a custom RPC
python3 onchain_tx_verifier.py \
    --chain optimism --kind erc20_transfer \
    --token 0xToken --to 0xTreasury --min-value 1000000 \
    --rpc-url https://my.op.node --proof 0x<txhash>

# contract deployment on Ethereum
python3 onchain_tx_verifier.py \
    --chain ethereum --kind contract_deploy --proof 0x<txhash> --json

# offline self-test (stubs the RPC; no network)
python3 onchain_tx_verifier.py --self-test
```

CLI exit codes: `0` verified · `1` rejected · `2` usage error · `3` RPC/network
error.

---

## Verification & acceptance

```bash
# syntax check, standard library only
python3 -c "import py_compile; py_compile.compile('onchain_tx_verifier.py', doraise=True)"

# behavioural proof against a stubbed RPC (no network)
python3 onchain_tx_verifier.py --self-test
```

The bundled self-test asserts (among others):

- **`verified=True`** for a mined, successful `tx_to` matching `to` + `min_value`;
  for an `erc20_transfer` whose receipt log matches `TRANSFER_TOPIC0` + recipient
  + amount; for a `contract_deploy` (`to`=null + `contractAddress` set); and for a
  Solana native transfer (recipient lamport delta, `meta.err is null`).
- **`verified=False`** for: a reverted tx (`status 0x0`), a missing tx, a pending
  tx (no block), too few confirmations, the wrong recipient, an amount below
  `min_value`, a `from` mismatch, a wrong/absent `Transfer` topic, a non-creation
  tx under `contract_deploy`, a deployed-address mismatch, a bad proof shape, a
  proof whose chain contradicts the mission, and an RPC infra error (no verdict).
- chain-alias normalisation, proof parsing across all forms, the `TRANSFER_TOPIC0`
  constant, malformed-`verification_params` rejection, and JSON-serialisable
  evidence across every arm.

---

## Design notes

- **Read-only, no signing, no keys.** Only `eth_getTransactionByHash`,
  `eth_getTransactionReceipt`, `eth_blockNumber` (EVM) and `getTransaction`,
  `getSlot` (Solana) are ever called. There is no signing/broadcast method and no
  key material in the module — the safe default for an oracle that touches chains.
- **404 / null ≠ error.** A missing tx is a *verdict* (`verified=False`), not an
  `RpcError`. `RpcError` is reserved for transport/decode failures or a JSON-RPC
  `error` envelope that prevented reaching any verdict.
- **Testable transport.** `RpcClient(transport=…)` accepts an injected
  `(url, payload_bytes, timeout) -> (status, body)` transport, which is how the
  offline self-test stubs the chain with zero network. The RPC URL is injectable
  four ways (arg / params / env / CLI) so no public endpoint is load-bearing.
- **EVM vs SVM.** `erc20_transfer` and `contract_deploy` are EVM-only (enforced at
  params-parse time). On Solana the supported action is a native-SOL transfer,
  verified from `meta.preBalances`/`postBalances` deltas against the decoded
  `accountKeys`. The `Transfer` topic-scan handles the standard 3-topic indexed
  ERC-20 event; non-compliant tokens that don't emit the standard event cannot be
  verified this way (fail-closed).
- **Big integers as strings.** Wei/lamport/base-unit amounts are surfaced in
  `evidence` as strings (they can exceed JS-safe integer range), while comparisons
  use Python's arbitrary-precision `int`.

### Economics (for context)

Rewards are paid in **AIGEN** — the protocol's uncapped, off-chain
reputation/points token — or **USDC** (real value). A flat **0.5%** protocol fee
is taken from every payout. This verifier only decides *whether* a submission is
valid; the marketplace handles payout and the fee.
```
