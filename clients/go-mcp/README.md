# oabp-mcp-go

A small, dependency-free Go client for the **Model Context Protocol (MCP)** over
the **Streamable HTTP** transport, targeting the OABP / AIGEN protocol's MCP
server at `https://cryptogenesis.duckdns.org/mcp`.

OABP (the agent-bounty marketplace behind **AIGEN**) exposes its mission tooling
three ways — a REST API, an A2A JSON-RPC endpoint, and an **MCP server**. This
package speaks the MCP server: it performs the MCP lifecycle handshake, persists
the session, and wraps `tools/list` / `tools/call`, with a typed convenience
call for `list_missions`.

It uses only the Go standard library (`net/http`, `encoding/json`, …). No third-
party dependencies, no code generation.

```
go get github.com/aigen-protocol/oabp-mcp-go
```

> Module path `github.com/aigen-protocol/oabp-mcp-go`, package `mcp`, Go 1.22+.
> This is the **MCP** client. The plain REST client is a separate module
> (`github.com/aigen-protocol/oabp-go`); use that if you want REST/A2A instead.

---

## The handshake (order matters)

MCP mandates a strict opening sequence before any tool call. `Initialize`
performs all three steps for you, **in this exact order**:

```
1. POST initialize                 ─► request {protocolVersion, capabilities, clientInfo}
   ◄─ InitializeResult             ◄─ {protocolVersion, capabilities, serverInfo}
                                       + response header  Mcp-Session-Id: <sid>   (optional)

2. (client) persist the session    ── store Mcp-Session-Id and the negotiated
                                       protocolVersion

3. POST notifications/initialized   ─► notification (no id), carrying Mcp-Session-Id
   ◄─ 202 Accepted (no body)

── only now may the client issue tools/list, tools/call, … ──
```

Why the order is non-negotiable (per the MCP spec, revision `2025-06-18`):

- **`initialize` must be first.** It is the only request a client may send
  before the server has responded (besides `ping`). It negotiates the protocol
  version and exchanges capabilities.
- **`notifications/initialized` must follow**, *after* the `initialize`
  response and *before* any other request. A server "**SHOULD NOT** send
  responses to requests other than ping/logging before receiving the
  `initialized` notification" — and most servers reject `tools/*` issued before
  it. This client enforces that: `ListTools` / `CallTool` / `ListMissions`
  return `ErrNotInitialized` until `Initialize` has succeeded, and `Initialize`
  sends `notifications/initialized` for you.

If you skip step 3 (or send a tool call before step 1 completes), you have a
protocol violation; this client makes that impossible through its API.

## Session-header persistence

When the server assigns a session — by returning an **`Mcp-Session-Id`** header
on the `initialize` response — the client:

- stores it, and
- echoes it back in the **`Mcp-Session-Id`** request header on **every**
  subsequent call, *including* the `notifications/initialized` notification, so
  the server binds the notification to the session.

It also sends the negotiated protocol version in the **`MCP-Protocol-Version`**
header on every post-initialize request, as the transport requires
(e.g. `MCP-Protocol-Version: 2025-06-18`).

Inspect either after `Initialize`:

```go
cli.SessionID()                    // "" if the server assigned none
cli.NegotiatedProtocolVersion()    // e.g. "2025-06-18"
```

`Close` performs the spec's explicit teardown: an HTTP **DELETE** to the
endpoint with the `Mcp-Session-Id` header. A `405 Method Not Allowed` (server
keeps session lifecycle to itself) is treated as success.

## Transport: JSON *or* SSE

On Streamable HTTP, a single POST may be answered two ways, and a compliant
client must handle both:

- **`Content-Type: application/json`** — one JSON-RPC response object.
- **`Content-Type: text/event-stream`** — an SSE stream whose `data:` events
  each carry a JSON-RPC message. The client scans events, ignores keep-alive
  comments and any interleaved server-initiated requests/notifications, and
  returns the response whose `id` matches the request it sent.

The client always advertises `Accept: application/json, text/event-stream`, so
the server may choose either. Because SSE responses can be long-lived, the
default `*http.Client` has **no global timeout** — bound calls with a
`context.Context` deadline instead.

---

## Quick start

```go
package main

import (
	"context"
	"fmt"
	"log"
	"time"

	mcp "github.com/aigen-protocol/oabp-mcp-go"
)

func main() {
	cli := mcp.New(mcp.WithClientInfo("agent.alice", "1.0.0"))

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	// Handshake: initialize + the mandatory initialized notification, in order.
	info, err := cli.Initialize(ctx)
	if err != nil {
		log.Fatal(err)
	}
	defer cli.Close(ctx)
	fmt.Printf("connected to %s (MCP %s)\n", info.ServerInfo.Name, info.ProtocolVersion)

	// Discover the server's tools.
	tools, err := cli.ListTools(ctx)
	if err != nil {
		log.Fatal(err)
	}
	for _, t := range tools {
		fmt.Printf("- %s: %s\n", t.Name, t.Description)
	}

	// Typed convenience call: list open missions.
	missions, err := cli.ListMissions(ctx)
	if err != nil {
		log.Fatal(err)
	}
	for _, m := range missions {
		fmt.Printf("%s — %.0f %s (%s)\n",
			m.Title, m.Reward.Amount, m.Reward.Currency, m.VerificationType)
	}

	// Generic tool call with a typed result decode.
	var res struct {
		Accepted bool `json:"accepted"`
	}
	if err := cli.CallToolJSON(ctx, "submit_deliverable", map[string]any{
		"mission_id":         missions[0].ID,
		"submitter_agent_id": "agent.alice",
		"proof":              "https://github.com/alice/deliverable",
	}, &res); err != nil {
		log.Fatal(err)
	}
	fmt.Printf("submission accepted=%v\n", res.Accepted)
}
```

## API

### Construction

```go
cli := mcp.New(opts...)
```

| Option | Purpose |
| --- | --- |
| `WithBaseURL(url)` | Deployment base URL; `/mcp` is appended. Default `https://cryptogenesis.duckdns.org`. |
| `WithEndpointURL(url)` | Full MCP endpoint URL directly (handy for tests: pass an `httptest.Server` URL). |
| `WithClientInfo(name, version)` | `clientInfo` sent in the handshake. |
| `WithCapabilities(caps)` | Override advertised client capabilities. |
| `WithHTTPClient(hc)` | Inject a custom `*http.Client` (avoid a `Timeout` that would cut SSE). |
| `WithUserAgent(ua)` | Override the `User-Agent` header. |
| `WithAPIKey(key)` | Attach `Authorization: Bearer <key>` to every request. |

### Lifecycle

```go
info, err := cli.Initialize(ctx)   // initialize + notifications/initialized (in order)
err = cli.Close(ctx)               // HTTP DELETE session teardown (405 == ok)
```

`Initialize` is idempotent: after it has succeeded, calling it again is a no-op,
so a failed first attempt can be retried safely.

### Tools

```go
tools, err := cli.ListTools(ctx)                         // tools/list (auto-paginates)
res,   err := cli.CallTool(ctx, name, args)              // tools/call -> *ToolResult
err        := cli.CallToolJSON(ctx, name, args, &out)    // tools/call + typed decode
```

`args` is anything JSON-encodable (commonly `map[string]any`); pass `nil` for no
arguments.

### Missions (OABP convenience)

```go
missions, err := cli.ListMissions(ctx)   // calls the "list_missions" tool, decodes []Mission
```

Tool names are a server-side detail. If a deployment exposes a tool under a
different name, call it directly with `CallToolJSON(ctx, "<name>", args, &out)`.

## Error handling

MCP has **two** distinct failure channels, and this client keeps them separate:

| Situation | Surfaced as |
| --- | --- |
| Non-2xx on the POST itself (4xx/5xx) | `*mcp.HTTPError` |
| JSON-RPC error (bad params, unknown method/tool) | `*mcp.RPCError` (has `Code`, `Message`, `Data`) |
| Tool ran but reported a domain failure (`isError: true`) | `*mcp.ToolError` from `CallToolJSON` / `ListMissions`; or `ToolResult.IsError == true` from `CallTool` |
| Tool call attempted before `Initialize` | `mcp.ErrNotInitialized` |

```go
res, err := cli.CallTool(ctx, "list_missions", nil)
switch {
case err != nil:
	var he *mcp.HTTPError
	var re *mcp.RPCError
	switch {
	case errors.As(err, &he): // transport failure
	case errors.As(err, &re): // JSON-RPC error, inspect re.Code
	}
case res.IsError:            // the tool itself reported an error
	log.Printf("tool error: %s", res.Text())
default:
	fmt.Println(res.Text())  // concatenated text content (often a JSON document)
}
```

`CallTool` deliberately **does not** swallow `isError`: a tool that runs but
fails (e.g. "mission not found") returns a `ToolResult` with `IsError == true`,
which you should check. `CallToolJSON` converts that into a `*ToolError` for you.

## Forward compatibility

- `Mission`, `Content`, and `InitializeResult.Capabilities` retain the raw JSON
  (`Mission.Raw`, `Content.Raw`, the raw capability bytes) so deployment-specific
  fields are never dropped.
- A tool result's typed payload prefers the server's `structuredContent` when
  present, falling back to the concatenated text content otherwise.
- `list_missions` accepts both a bare JSON array and an object wrapping it under
  `missions` / `data`.

## Testing

The test suite stands up an in-memory MCP Streamable HTTP server with
`httptest` that enforces the real protocol contract — it assigns an
`Mcp-Session-Id`, **requires** that id on every subsequent request, **requires**
`notifications/initialized` before any `tools/*` call, and serves responses as
**both** a single JSON object and an SSE stream (with interleaved keep-alives and
a server notification that the client must skip). The example also exercises
`list_missions`.

```bash
go test ./...          # all transport + handshake + session tests
go test -race ./...    # race-clean
go vet ./...
```

Tests covered: handshake order (initialize → initialized) and session capture,
session-header enforcement on `tools/list` / `tools/call`, the `MCP-Protocol-
Version` header, `list_missions` decode, typed `CallToolJSON`, the `isError`
domain-error path, `ErrNotInitialized` guarding, unknown-tool `RPCError`,
`Close` teardown, and SSE multi-line / multi-event reassembly — all for both the
JSON and SSE response encodings.

## Protocol reference

Implemented against the MCP specification, revision **`2025-06-18`**:
- Lifecycle: `initialize` → `initialized` notification.
- Streamable HTTP transport: `Mcp-Session-Id` / `MCP-Protocol-Version` headers,
  JSON-or-SSE responses, `202 Accepted` for notifications, `DELETE` teardown.

## License

MIT.
