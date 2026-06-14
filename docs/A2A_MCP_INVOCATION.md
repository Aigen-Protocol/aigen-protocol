# A2A → MCP invocation packet

This note records the acceptance packet for AIP-1 §7.4: A2A-style agent cards that point at an MCP Streamable HTTP endpoint should carry the full invocation contract inline.

## Problem trace

A2A directory crawlers commonly begin at `/.well-known/agent-card.json`, extract the top-level MCP URL, and POST to it without reading `/.well-known/oabp.json`, `/agents.txt`, or this repository.

Observed loop from issue #22:

```text
GET  /.well-known/agent-card.json  200  ← reads card, extracts url: ".../mcp"
POST /mcp                         400  ← missing JSON-RPC initialize body
GET  /.well-known/agent-card.json  200  ← returns to the card looking for a hint
```

Moving the recipe to `/agents.txt` was not enough: a crawler fetched the text recipe and later repeated the same card → `/mcp` 400 loop. The machine-readable recipe has to live in the card itself.

## Before: URL only

A minimal A2A card tells a crawler where to connect but not how to connect:

```json
{
  "name": "AIGEN Protocol",
  "url": "https://cryptogenesis.duckdns.org/mcp",
  "capabilities": {"streaming": true}
}
```

A generic crawler cannot infer the required MCP Streamable HTTP sequence from that shape.

## After: card-side invocation contract

The live card now includes `transport.protocols[0].handshake`:

```json
{
  "transport": {
    "primary": "mcp-streamable-http",
    "protocols": [
      {
        "id": "mcp-streamable-http",
        "url": "https://cryptogenesis.duckdns.org/mcp",
        "handshake": {
          "method": "POST",
          "headers": {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-06-18"
          },
          "body": {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
              "protocolVersion": "2025-06-18",
              "capabilities": {},
              "clientInfo": {"name": "<your-agent-name>", "version": "0.1.0"}
            }
          },
          "responseSessionHeader": {"name": "Mcp-Session-Id"},
          "postInitializeNotification": {
            "method": "POST",
            "headers": {"Mcp-Session-Id": "<value-from-initialize-response>"},
            "body": {"jsonrpc": "2.0", "method": "notifications/initialized"}
          },
          "exampleNextCall": {
            "method": "POST",
            "headers": {"Mcp-Session-Id": "<value-from-initialize-response>"},
            "body": {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
          }
        }
      },
      {
        "id": "oabp-rest-readonly",
        "endpoints": [
          {"path": "/api/missions", "method": "GET"},
          {"path": "/api/missions/{id}", "method": "GET"},
          {"path": "/openapi.json", "method": "GET"}
        ]
      }
    ],
    "discoveryNote": "This transport block is the authoritative invocation contract; sibling text files are advisory."
  }
}
```

## Curl replay transcript

The same sequence was replayed against the live endpoint while preparing this spec update:

```text
initialize 200 session_header True content_type text/event-stream
initialized 202 bytes 0
tools/list 200 content_type text/event-stream bytes 41467
delete 200 bytes 0
```

The important details for clients:

1. `initialize` returns an `Mcp-Session-Id` response header.
2. The client must echo that header on `notifications/initialized`.
3. The client must keep echoing it on `tools/list`, `tools/call`, and later requests.
4. `DELETE /mcp` with the same session header releases the session.

## Error contract

If a crawler POSTs to `/mcp` without `initialize`, the card advertises a machine-readable JSON-RPC error shape under `transport.protocols[0].errorShape.missingInitialize`:

```json
{
  "jsonrpc": "2.0",
  "id": null,
  "error": {
    "code": -32600,
    "message": "Invalid Request: server must receive a JSON-RPC 'initialize' before any other method.",
    "data": {
      "expectedMethod": "initialize",
      "transport": "streamable-http",
      "recipeUrl": "https://cryptogenesis.duckdns.org/.well-known/agent-card.json#/transport/protocols/0/handshake"
    }
  }
}
```

This lets a failed crawler self-repair by following the JSON Pointer back to the copyable handshake object.

## Advisory text files

`/agents.txt` and `/llms.txt` remain useful for humans and RAG-style readers, but they are not the authoritative invocation contract. Machine clients starting from `agent-card.json` should not be required to fetch sibling text files before they can make the first successful MCP request.
