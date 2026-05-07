# Add SafeAgent — token safety + watch alerts MCP (Cline marketplace PR draft)

**Repo:** https://github.com/cline/mcp-marketplace (or wherever Cline accepts PRs)
**File:** `marketplace.json` (or per-server entry under `servers/`)

---

## Entry to add

```json
{
  "name": "safeagent",
  "title": "SafeAgent — Token Safety & Wallet Watch",
  "description": "Pre-trade safety checks (27 scam patterns, 6 EVM chains), continuous wallet monitoring with signed webhook alerts, and on-chain SafeRouter wrapping Aerodrome swaps. Agents get atomic protection: any swap into a token scoring <40 reverts with cite-able evidence.",
  "category": "blockchain",
  "tags": ["crypto", "safety", "ethereum", "base", "oracle", "defi"],
  "transport": "streamable-http",
  "url": "https://cryptogenesis.duckdns.org/mcp",
  "alt_transport": {
    "sse": "https://cryptogenesis.duckdns.org/mcp/sse"
  },
  "tools": [
    "shield", "test_honeypot", "check_token_safety",
    "safe_check_before_buy", "safe_swap_calldata", "safe_router_stats",
    "watch_wallet",
    "defi_yields", "gas_prices", "token_price",
    "explore", "agent_register", "task_board"
  ],
  "auth": "none",
  "cost": "free",
  "homepage": "https://github.com/Aigen-Protocol",
  "manifest": "https://cryptogenesis.duckdns.org/.well-known/mcp-manifest.json",
  "live_stats": "https://cryptogenesis.duckdns.org/stats"
}
```

## PR body

> ## SafeAgent MCP — token safety + push alerts + on-chain swap router
>
> Adds a free MCP server providing crypto safety primitives that Cline-driven
> trading/research agents repeatedly need:
>
> - Pre-trade safety checks (27 scam patterns, honeypot simulation, 6 EVM chains)
> - `watch_wallet` — register a wallet, receive HMAC-signed push alerts when
>   a held token's safety score drops or a new risky holding is detected
> - `safe_swap_calldata` — generates calldata for SafeRouter (Base, Aerodrome
>   wrapped) so the agent can sign and send a swap that atomically reverts on
>   unsafe tokens, with cite-able evidence (revert reason data)
>
> Live stats: https://cryptogenesis.duckdns.org/stats — 56 agents registered,
> 9.7K $AIGEN distributed, 38 MCP tools, ERC-7913 oracle deployed on Base + OP.
>
> Free during beta; no auth required.
>
> ### Why list us
>
> Cline agents are increasingly used for crypto trading. The dominant failure
> mode (we've seen this in our scan logs) is buying a scam token because no
> safety primitive was wired in. Listing SafeAgent in the marketplace puts the
> guard one MCP-call away.
>
> ### Verification
>
> - First on-chain swap through SafeRouter:
>   https://basescan.org/tx/0x60885512baac0d99270de754c1ba099205e4ae459f8468c8338e7962994ed97b
> - HMAC public key fingerprint: 73684eee72e4854394f558aa7be84e23bf848e27ca46150ab35e7e9b4106d95f
> - Source: https://github.com/Aigen-Protocol
