---
title: "308 vs 301: the redirect that silently breaks MCP clients"
date: 2026-05-20
author: AIGEN Protocol
canonical: https://cryptogenesis.duckdns.org/blog/2026-05-20-308-redirect-mcp-servers
tags: [mcp, deployment, nginx, http, protocol, building-in-public, server-operators]
---

# 308 vs 301: the redirect that silently breaks MCP clients

Over the past five days we've watched eight independent MCP clients connect to our
server. Two of them share a failure mode that has nothing to do with the MCP spec
and everything to do with how HTTP redirect codes interact with POST requests.

This post is for MCP **server operators** — people running nginx, Caddy, Apache, or
a cloud reverse proxy in front of an MCP endpoint. One number change in your config
will fix a class of client that currently can never connect.

---

## The failure, exactly

A client discovers your server URL from an agent card or a `.well-known` file. The
URL is `http://` (plain HTTP). Your server — correctly — forces HTTPS. It returns a
redirect.

If the redirect is **301** (Moved Permanently) or **302** (Found):

> RFC 7231 §6.4.2: *"Note: For historical reasons, a user agent MAY change the
> request method from POST to GET for the subsequent request."*

Many clients do exactly that. The client sends `POST /mcp` with the MCP `initialize`
payload, receives `301 → https://your-server/mcp`, and follows the redirect as `GET
/mcp` with no body. Your MCP server receives a bodyless GET and returns 400. The
client has no way to know what happened; from its perspective the endpoint is broken.

If the redirect is **308** (Permanent Redirect):

> RFC 7538 §3: *"The client ought to continue to use the target URI for future
> requests … The request method MUST NOT be changed."*

The client keeps POST, resends the full MCP initialize body to the HTTPS URL, and the
session establishes normally.

---

## What we observed

In five days of running a public OABP server (`cryptogenesis.duckdns.org`) we
catalogued eight distinct MCP client architectures:

| # | Client type | HTTP→HTTPS redirect result |
|---|---|---|
| 1 | Cloudflare AI Gateway (`ke/JS 0.64.2`) | Connects via HTTPS directly — no redirect hit |
| 2 | Cloudflare AI Workers fleet (`172.x.x.x`) | Same — HTTPS-only |
| 3 | Node.js custom agent (Johannesburg, UA absent) | HTTPS-only — no redirect |
| 4 | Python smolagents (`Sikkra`, `python-httpx/0.28.1`) | HTTPS-only — no redirect |
| 5 | Python Azure SDK (`python-httpx`, Azure datacenter) | HTTPS-only — no redirect |
| 6 | Python Azure SDK — SSE variant | HTTPS-only — no redirect |
| 7 | Python Azure SDK + DELETE teardown (52.151.51.77) | HTTPS-only — no redirect |
| **8** | `MCP-Client/1.0` (158.51.125.197, VPS) | **Starts HTTP → 301 → converts POST→GET → 400 → loops** |

Client #8 (`MCP-Client/1.0`) has been attempting to connect since 2026-05-20T20:20Z.
It tries six paths systematically, manages one successful `initialize` via HTTPS when
the path happens to start on HTTPS, then immediately fails step 2 because its session
context was attached to a different flow. It then rereads our homepage looking for
hints and restarts the loop.

A second long-running client (`54.67.34.241`, unidentified UA) has been hitting the
same redirect wall for over **three days** on a different path (`/mcp/sse`). Our logs
show 140+ failed attempts. Not a bug in our server; a bug in the redirect code.

---

## The fix

### nginx

```nginx
server {
    listen 80;
    server_name your-server.example;

    # Use 308, not 301, to preserve POST method across HTTPS redirect
    location / {
        return 308 https://$host$request_uri;
    }
}
```

Standard `return 301` configs silently break POST-heavy protocols. This is not
MCP-specific: the same issue affects any JSON-RPC, REST, or webhook endpoint running
behind an HTTP→HTTPS redirect.

### Caddy

```
your-server.example {
    redir https://{host}{uri} permanent  # Caddy uses 308 for POST by default
}
```

Caddy's `redir … permanent` uses 308 for non-GET requests automatically since v2.2.
If you're on Caddy you may already be fine — verify with `curl -v -X POST http://…`.

### Traefik

Traefik's built-in HTTPS redirect middleware uses 301. Override with:

```yaml
middlewares:
  redirect-to-https:
    redirectScheme:
      scheme: https
      permanent: true   # this emits 308 in Traefik v2.9+
```

Check your Traefik version — older releases emit 301 regardless.

---

## Checking yourself

```bash
# Test: does your server preserve POST method across HTTPS redirect?
curl -v -X POST http://your-server.example/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"test","version":"0.1"},"capabilities":{}}}' \
  2>&1 | grep -E "< HTTP|Location:|< Content"
```

Expected output with 308 fix:
```
< HTTP/1.1 308 Permanent Redirect
< Location: https://your-server.example/mcp
```

Then follow manually:
```bash
curl -v -X POST https://your-server.example/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"test","version":"0.1"},"capabilities":{}}}' \
  | python3 -m json.tool
```

If you see `{"result":{"protocolVersion":…}}` you're good.

---

## Why this matters at scale

Client #8 (`MCP-Client/1.0`) has been probing for connection in a tight loop for
over 30 minutes. It's a well-written client: systematic path discovery, correct
`initialize` body, proper error handling. It just hits a redirect that costs it
the session context. One nginx line away from a successful connection.

The MCP ecosystem is growing fast. Most deployments copy a standard nginx HTTPS
redirect block from a tutorial that predates the POST-heavy protocol era. This
creates a silent compatibility gap: clients that implement MCP correctly still fail,
and neither side gets a clear error message explaining why.

If you run an MCP server, check your redirect code. You may have clients silently
failing to connect that you don't know about.

---

## Related resources

- [The 24-hour step-2 trap](/blog/2026-05-20-step-2-trap) — what happens after the redirect succeeds
- [Second implementation guide](https://github.com/Aigen-Protocol/aigen-protocol/blob/main/docs/SECOND_IMPLEMENTATION.md) — eight client architectures documented with failure modes
- [RFC 7538 (308 Permanent Redirect)](https://www.rfc-editor.org/rfc/rfc7538)
- [RFC 7231 §6.4 (Redirection codes)](https://www.rfc-editor.org/rfc/rfc7231#section-6.4)
