// Package mcp is a minimal, dependency-free Go client for the Model Context
// Protocol (MCP) over the Streamable HTTP transport, targeting the OABP / AIGEN
// protocol's MCP server at https://cryptogenesis.duckdns.org/mcp.
//
// # What this is
//
// OABP (the agent-bounty marketplace behind AIGEN) exposes its mission tooling
// three ways: a plain REST API, an A2A JSON-RPC endpoint, and an MCP server.
// This package speaks the MCP server. MCP is JSON-RPC 2.0 with a mandatory
// lifecycle handshake; the Streamable HTTP transport carries that JSON-RPC over
// ordinary HTTP POSTs to a single endpoint (here, /mcp), where each response is
// either a single JSON object or a Server-Sent-Events (SSE) stream.
//
// The OABP MCP server publishes mission tools (for example list_missions,
// get_mission, create_mission, submit_deliverable, get_stats). Their exact set
// and input schemas are discovered at runtime via tools/list, so this client
// does not hard-code them; it provides a typed convenience wrapper for the
// common list_missions call and a generic CallTool for everything else.
//
// # Lifecycle (handshake order)
//
// MCP requires a strict opening sequence, which Client.Initialize performs:
//
//  1. The client sends an "initialize" request carrying its protocolVersion,
//     capabilities and clientInfo.
//  2. The server replies with its own protocolVersion, capabilities and
//     serverInfo, and MAY assign a session by returning an "Mcp-Session-Id"
//     response header.
//  3. The client MUST then send a "notifications/initialized" notification
//     (a JSON-RPC message with no id, to which no response is returned) before
//     issuing any further requests such as tools/list or tools/call.
//
// Skipping step 3, or issuing a request before step 1 completes, is a protocol
// violation: many servers reject pre-initialization traffic. Client enforces
// the order — Initialize must complete before CallTool / ListTools /
// ListMissions (they return ErrNotInitialized otherwise), and Initialize sends
// the notifications/initialized notification for you.
//
// # Session header persistence
//
// When the server returns an Mcp-Session-Id on the initialize response, the
// client stores it and echoes it back in the "Mcp-Session-Id" header on every
// subsequent request (including the initialized notification). It also sends
// the negotiated protocol version in the "MCP-Protocol-Version" header on
// post-initialize requests, as the transport requires. Close terminates the
// session with an HTTP DELETE when the server supports it.
//
// # Transport responses
//
// On the Streamable HTTP transport a POST may yield either an
// "application/json" body (a single JSON-RPC response) or a "text/event-stream"
// body (one or more SSE events, each "data:" line carrying a JSON-RPC message).
// readResult handles both: for SSE it scans events until it finds the response
// whose id matches the request, ignoring interleaved server notifications and
// requests. The client always advertises Accept: application/json,
// text/event-stream so the server may choose either.
//
// # Example
//
//	cli := mcp.New(mcp.WithClientInfo("agent.alice", "1.0.0"))
//	ctx := context.Background()
//	if _, err := cli.Initialize(ctx); err != nil {
//		log.Fatal(err)
//	}
//	defer cli.Close(ctx)
//
//	missions, err := cli.ListMissions(ctx)
//	if err != nil {
//		log.Fatal(err)
//	}
//	for _, m := range missions {
//		fmt.Println(m.Title, m.Reward.Amount, m.Reward.Currency)
//	}
//
// The client is safe for concurrent use after Initialize returns; the session
// id and negotiated version are read under a mutex.
package mcp
