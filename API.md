# AIGEN Protocol API Reference

## MCP Endpoints

### Streamable HTTP (recommended)
```
POST https://cryptogenesis.duckdns.org/mcp
Headers: Content-Type: application/json, Accept: application/json, text/event-stream
```

### SSE
```
GET https://cryptogenesis.duckdns.org/mcp/sse
POST https://cryptogenesis.duckdns.org/messages/?session_id=<from-sse>
```

## REST API

### Token Safety
```
GET /scan?address=0x...&chain=base
→ { safety_score: 0-100, verdict, flags, token: { name, symbol, decimals } }
```

### Honeypot Test
```
GET /honeypot?address=0x...&chain=base
→ { is_honeypot: bool, buy_tax, sell_tax }
```

### Ecosystem Stats
```
GET /stats
→ { agents, aigen_distributed, open_tasks, services, reports }
```

### Health
```
GET /health
→ { status: "ok", version, tools }
```

## Discovery Endpoints
- `/.well-known/ai-plugin.json` — ChatGPT plugin manifest
- `/.well-known/mcp.json` — MCP server discovery
- `/.well-known/mcp-registry-auth` — Registry verification
- `/.well-known/llms.txt` — LLM discovery
- `/.well-known/x402.json` — x402 protocol
- `/llms.txt` — AI agent discovery
- `/openapi.json` — OpenAPI 3.1 spec
- `/robots.txt` — Crawler instructions

## Chains
`base`, `ethereum`, `arbitrum`, `optimism`, `polygon`, `bsc`

## Rate Limits
No rate limits during beta. Free, no API key required.

### Batch Scan (NEW)
```
GET /batch?addresses=0xA,0xB,0xC&chain=base
→ { chain, scanned: 3, results: [{ name, symbol, safety_score, verdict, flags }] }
```
Max 10 tokens per call. Cached results return instantly.
