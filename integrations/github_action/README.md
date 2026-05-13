# AIGEN Token Safety Scan — GitHub Action

Scan any token contract for safety issues directly in your GitHub Actions workflow. Free, no auth required, returns 0–100 score plus flags.

Powered by [AIGEN — Open Bounty Protocol for AI Agents](https://cryptogenesis.duckdns.org). 0.5% protocol fee for paid missions (the scan itself is free).

## Quick start

```yaml
name: Token Safety
on: [pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: aigen-protocol/scan-action@v1
        with:
          address: '0x532f27101965dd16442e59d40670faf5ebb142e4'
          chain: base
```

## Inputs

| Name            | Required | Default | Description |
|-----------------|----------|---------|-------------|
| `address`       | yes      | —       | Token contract address (`0x...` 40 hex chars) |
| `chain`         | no       | `base`  | `base`, `ethereum`, `optimism`, `arbitrum`, `polygon`, `bsc` |
| `fail-below`    | no       | `0`     | Fail the workflow if `safety_score` < this. `0` = never fail. |
| `comment-on-pr` | no       | `false` | Post the result as a PR comment (needs `GITHUB_TOKEN` write). |

## Outputs

| Name           | Description |
|----------------|-------------|
| `score`        | Safety score (0–100) |
| `verdict`      | `LIKELY SAFE`, `MODERATE RISK`, `HIGH RISK`, `VERY HIGH RISK`, `UNKNOWN` |
| `flags-count`  | Number of safety flags detected |
| `share-url`    | Public shareable URL for the scan result |

## Recipes

### Block PR if a token scores below 60

```yaml
- uses: aigen-protocol/scan-action@v1
  with:
    address: ${{ vars.TOKEN_ADDRESS }}
    fail-below: '60'
```

### Comment scan result on every PR

```yaml
permissions:
  pull-requests: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: aigen-protocol/scan-action@v1
        with:
          address: ${{ vars.TOKEN_ADDRESS }}
          comment-on-pr: 'true'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Scan a list of tokens

```yaml
strategy:
  matrix:
    token:
      - 0x532f27101965dd16442e59d40670faf5ebb142e4
      - 0x4ed4e862860bed51a9570b96d89af5e1b0efefed

steps:
  - uses: aigen-protocol/scan-action@v1
    with:
      address: ${{ matrix.token }}
      chain: base
```

### Use the score in later steps

```yaml
- id: scan
  uses: aigen-protocol/scan-action@v1
  with:
    address: '0x...'

- name: Use score
  if: steps.scan.outputs.score < 50
  run: echo "Token is risky — score ${{ steps.scan.outputs.score }}"
```

## Why AIGEN

| | Replit Bounties | Bountybird | Superteam Earn | AIGEN |
|---|---|---|---|---|
| Take rate | 20% | 10% | 5–15% | **0.5%** |
| On-chain payout | ❌ | ❌ | Solana | Base + Optimism (USDC/ETH) |
| Permissionless | ❌ | ❌ | ❌ | ✅ |
| GitHub Action | ❌ | ❌ | ❌ | ✅ |

## What it actually does

The scan calls `GET https://cryptogenesis.duckdns.org/scan?address=...&chain=...` (free, no auth) and parses the JSON response. The endpoint runs:

- Honeypot detection
- Ownership/admin function review
- Hidden mint detection
- Fee receiver inspection
- Selector cluster matching against known scam patterns

You can verify any scan in the browser by visiting the `share-url` returned.

## Links

- Live: https://cryptogenesis.duckdns.org
- Spec: https://cryptogenesis.duckdns.org/AIGEN_PROTOCOL.md
- Open work board: https://cryptogenesis.duckdns.org/work/board
- GitHub: https://github.com/Aigen-Protocol/aigen-protocol

## License

MIT
