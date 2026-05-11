# NFT Safety MCP Tool

`nft_safety.py` adds a dependency-free NFT collection safety analyzer and wires
it into MCP as `check_nft_safety(collection, chain)`.

## What It Checks

- Address has deployed contract bytecode.
- Explorer source is verified.
- Contract advertises ERC-721 or ERC-1155 via ERC-165.
- Contract advertises ERC-2981 royalties.
- Explorer does not mark the contract as scam.
- Owner/admin is visible via `owner()` or `ownerAddress()`.

## Supported Chains

- Base
- Optimism
- Ethereum

## Output

The tool returns a plain-text report with:

- 0-100 score
- verdict
- weighted signal list
- risk flags
- explorer URL

## Verification

```bash
python3 nft_safety.py
python3 -m py_compile nft_safety.py mcp_server.py
git diff --check
```

The self-test validates scoring, verdict thresholds, address validation, and
report formatting without calling external services.
