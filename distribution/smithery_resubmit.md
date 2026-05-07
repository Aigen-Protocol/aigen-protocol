# Smithery resubmit — SafeAgent v2

Smithery previously bounced the registration. Resubmit with the new
manifest reflecting the watch + saferouter additions.

## smithery.yaml (updated)

```yaml
name: safeagent
qualifiedName: safeagent/token-safety
description: |
  Token safety oracle + continuous wallet monitoring + on-chain SafeRouter
  (Base/Aerodrome). Pre-trade safety checks across 6 EVM chains with 27
  scam patterns and real DEX swap simulation. Push-based alerts via
  HMAC-SHA256 signed webhooks. Free during beta.

connection:
  type: streamable-http
  url: https://cryptogenesis.duckdns.org/mcp

categories:
  - blockchain
  - security
  - devtools

tags:
  - mcp
  - crypto
  - ethereum
  - base
  - defi
  - oracle
  - safeagent
  - safety

iconUrl: https://cryptogenesis.duckdns.org/favicon.ico
homepage: https://github.com/Aigen-Protocol
docsUrl: https://github.com/Aigen-Protocol/aigen-protocol#readme
repository: https://github.com/Aigen-Protocol/aigen-protocol

config:
  schema:
    type: object
    properties: {}
```

## Submission email body (if Smithery requires manual review)

> Subject: Resubmit safeagent/token-safety — major update (watch + on-chain router)
>
> Hi Smithery team,
>
> Resubmitting SafeAgent following our previous bounce. Two material
> additions since:
>
> 1. **/watch** endpoint with HMAC-SHA256 signed webhook alerts —
>    push-based wallet monitoring, novel for the MCP space.
> 2. **SafeRouter** deployed on Base wrapping Aerodrome — agents can swap
>    with atomic safety guarantees. First live tx:
>    https://basescan.org/tx/0x60885512baac0d99270de754c1ba099205e4ae459f8468c8338e7962994ed97b
>
> Manifest: https://cryptogenesis.duckdns.org/.well-known/mcp-manifest.json
> Live: https://cryptogenesis.duckdns.org/mcp (streamable-http)
> Backup transport: https://cryptogenesis.duckdns.org/mcp/sse
>
> Stats endpoint shows 38 tools, 56 agents, 9.7K rewards distributed:
> https://cryptogenesis.duckdns.org/stats
>
> Source: https://github.com/Aigen-Protocol/aigen-protocol
>
> Cryptogen@zohomail.eu
