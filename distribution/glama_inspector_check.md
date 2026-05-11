# Glama Inspector Check Suite

`scripts/glama_inspector_check.py` is a CI-friendly check for the AIGEN MCP
server's Glama/registry readiness.

## What It Checks

- `server.json` has GitHub repository metadata.
- `server.json` exposes both `streamable-http` and `sse` remotes.
- Remote URLs are HTTPS.
- `glama.json` transport URLs match `server.json`.
- Every `@mcp.tool()` in `mcp_server.py` is listed in `glama.json`.
- `glama.json` does not advertise tools missing from `mcp_server.py`.
- Required core tools exist: `shield`, `test_honeypot`,
  `check_token_safety`, `explore`, `agent_register`, `task_board`.
- `mcp_server.py` serves Streamable HTTP at `/mcp`.
- README/API docs mention the public MCP endpoints.

## Run Offline

```bash
python3 scripts/glama_inspector_check.py
```

This mode is deterministic and suitable for CI. It does not call Glama or the
live SafeAgent server.

## Run Against The Live Endpoint

```bash
python3 scripts/glama_inspector_check.py --remote
```

Remote mode performs a minimal Streamable HTTP MCP handshake against
`https://cryptogenesis.duckdns.org/mcp`:

1. `initialize`
2. `notifications/initialized`
3. `tools/list`

It accepts both JSON and `text/event-stream` responses.

## Official Inspector Cross-Check

For manual browser/CLI validation with the upstream inspector:

```bash
npx @modelcontextprotocol/inspector --cli \
  https://cryptogenesis.duckdns.org/mcp \
  --transport http \
  --method tools/list
```

The local script is intentionally narrow: it catches metadata drift before a
registry or inspector run, while the official inspector remains the final
interactive debugging surface.
