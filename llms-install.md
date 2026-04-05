# AIGEN Protocol — MCP Server Installation

## Remote Server (No Installation Required)

AIGEN Protocol runs as a remote MCP server. No local installation needed.

### Configuration

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "aigen": {
      "url": "https://cryptogenesis.duckdns.org/mcp",
      "transport": "streamable-http"
    }
  }
}
```

### SSE Transport (Alternative)

```json
{
  "mcpServers": {
    "aigen": {
      "url": "https://cryptogenesis.duckdns.org/mcp/sse",
      "transport": "sse"
    }
  }
}
```

### No API Key Required

The server is free and open. No authentication needed.

### Verify Installation

After connecting, call the `explore()` tool to see all 38 available tools.

### Available Tools

- `shield(action, token, chain)` — Token safety check with GO/BLOCK decision
- `test_honeypot(token, chain)` — Real DEX swap simulation
- `check_token_safety(token, chain)` — Quick safety score (0-100)
- `defi_yields()` — Top DeFi yield opportunities
- `gas_prices()` — Real-time gas across chains
- `explore()` — Discover all tools and features
