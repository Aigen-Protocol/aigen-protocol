package mcp

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
)

// mcpStub is an in-memory MCP Streamable HTTP server used by the tests. It
// honors the protocol's lifecycle: it issues a session id on initialize,
// requires that id on every subsequent request, requires that
// notifications/initialized arrive before any tools/* call, and can answer
// either as a single JSON object or as an SSE stream (selectable per stub) so
// both transport encodings are exercised.
type mcpStub struct {
	t *testing.T

	// sse selects the response encoding for request responses.
	sse bool

	mu               sync.Mutex
	sessionID        string
	initializeSeen   bool
	initializedSeen  bool
	gotProtocolVer   string // MCP-Protocol-Version seen on a post-init request
	toolCalls        []string
	deleted          bool
	sawSessionOnInit bool // session header present on the initialized notification
}

const stubSessionID = "sess-abc-123"

func newStub(t *testing.T, sse bool) *mcpStub { return &mcpStub{t: t, sse: sse} }

func (s *mcpStub) server() *httptest.Server { return httptest.NewServer(s) }

func (s *mcpStub) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodDelete:
		s.handleDelete(w, r)
		return
	case http.MethodPost:
		s.handlePost(w, r)
		return
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func (s *mcpStub) handleDelete(w http.ResponseWriter, r *http.Request) {
	if got := r.Header.Get(headerSessionID); got != stubSessionID {
		http.Error(w, "unknown session", http.StatusNotFound)
		return
	}
	s.mu.Lock()
	s.deleted = true
	s.mu.Unlock()
	w.WriteHeader(http.StatusNoContent)
}

func (s *mcpStub) handlePost(w http.ResponseWriter, r *http.Request) {
	// The client must always accept both encodings.
	if acc := r.Header.Get("Accept"); !strings.Contains(acc, "application/json") || !strings.Contains(acc, "text/event-stream") {
		s.t.Errorf("Accept header = %q; want both application/json and text/event-stream", acc)
	}
	if ct := r.Header.Get("Content-Type"); !strings.HasPrefix(ct, "application/json") {
		s.t.Errorf("Content-Type = %q; want application/json", ct)
	}

	body, _ := io.ReadAll(r.Body)

	// Distinguish a request (has id) from a notification (no id).
	var probe struct {
		JSONRPC string          `json:"jsonrpc"`
		ID      json.RawMessage `json:"id"`
		Method  string          `json:"method"`
		Params  json.RawMessage `json:"params"`
	}
	if err := json.Unmarshal(body, &probe); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	if probe.JSONRPC != "2.0" {
		s.t.Errorf("jsonrpc = %q; want 2.0", probe.JSONRPC)
	}

	isNotification := len(probe.ID) == 0

	if isNotification {
		s.handleNotification(w, r, probe.Method)
		return
	}
	s.handleRequest(w, r, probe.Method, probe.ID, probe.Params)
}

func (s *mcpStub) handleNotification(w http.ResponseWriter, r *http.Request, method string) {
	if method == "notifications/initialized" {
		s.mu.Lock()
		s.initializedSeen = true
		s.sawSessionOnInit = r.Header.Get(headerSessionID) == stubSessionID
		s.mu.Unlock()
	}
	// Notifications get a 202 with no body.
	w.WriteHeader(http.StatusAccepted)
}

func (s *mcpStub) handleRequest(w http.ResponseWriter, r *http.Request, method string, id, params json.RawMessage) {
	// initialize: assign a session, do NOT require one yet.
	if method == "initialize" {
		s.mu.Lock()
		s.initializeSeen = true
		s.sessionID = stubSessionID
		s.mu.Unlock()

		// Validate the params the client sent.
		var p initializeParams
		if err := json.Unmarshal(params, &p); err != nil {
			s.t.Errorf("initialize params decode: %v", err)
		}
		if p.ProtocolVersion == "" {
			s.t.Error("initialize: empty protocolVersion")
		}
		if p.ClientInfo.Name == "" {
			s.t.Error("initialize: empty clientInfo.name")
		}

		w.Header().Set(headerSessionID, stubSessionID)
		result := InitializeResult{
			ProtocolVersion: ProtocolVersion,
			Capabilities:    json.RawMessage(`{"tools":{"listChanged":false}}`),
			ServerInfo:      Implementation{Name: "oabp-mcp-stub", Version: "test"},
			Instructions:    "OABP mission server",
		}
		s.writeResult(w, id, mustJSON(result))
		return
	}

	// Every non-initialize request MUST carry the session id...
	if got := r.Header.Get(headerSessionID); got != stubSessionID {
		http.Error(w, "missing or wrong session id", http.StatusNotFound)
		return
	}
	// ...and the negotiated protocol version header.
	if pv := r.Header.Get(headerProtocolVersion); pv != "" {
		s.mu.Lock()
		s.gotProtocolVer = pv
		s.mu.Unlock()
	} else {
		s.t.Errorf("%s: missing %s header", method, headerProtocolVersion)
	}

	// tools/* must not precede notifications/initialized.
	s.mu.Lock()
	initd := s.initializedSeen
	s.mu.Unlock()
	if strings.HasPrefix(method, "tools/") && !initd {
		s.writeRPCError(w, id, ErrCodeInvalidRequest, "received request before initialized notification")
		return
	}

	switch method {
	case "tools/list":
		s.writeResult(w, id, mustJSON(listToolsResult{
			Tools: []Tool{
				{
					Name:        "list_missions",
					Description: "List open OABP missions",
					InputSchema: json.RawMessage(`{"type":"object","properties":{}}`),
				},
				{
					Name:        "submit_deliverable",
					Description: "Submit a deliverable to a mission",
					InputSchema: json.RawMessage(`{"type":"object","properties":{"mission_id":{"type":"string"},"proof":{"type":"string"}}}`),
				},
			},
		}))
	case "tools/call":
		s.handleToolCall(w, id, params)
	default:
		s.writeRPCError(w, id, ErrCodeMethodNotFound, "method not found: "+method)
	}
}

func (s *mcpStub) handleToolCall(w http.ResponseWriter, id, params json.RawMessage) {
	var call struct {
		Name      string          `json:"name"`
		Arguments json.RawMessage `json:"arguments"`
	}
	if err := json.Unmarshal(params, &call); err != nil {
		s.writeRPCError(w, id, ErrCodeInvalidParams, "bad params")
		return
	}
	s.mu.Lock()
	s.toolCalls = append(s.toolCalls, call.Name)
	s.mu.Unlock()

	switch call.Name {
	case "list_missions":
		missions := []map[string]any{
			{
				"id":                "m-001",
				"title":             "GoPlus safety review of 0xdead",
				"description":       "Review token security",
				"reward":            map[string]any{"amount": 500, "currency": "AIGEN"},
				"verification_type": "oracle",
				"deadline":          1893456000,
				"status":            "open",
				"submissions":       []any{},
			},
			{
				"id":                "m-002",
				"title":             "Find SHA-256 of 'aigen'",
				"description":       "lowercase hex digest",
				"reward":            map[string]any{"amount": 1000, "currency": "USDC"},
				"verification_type": "first_valid_match",
				"deadline":          1893456000,
				"status":            "open",
				"submissions":       []any{},
			},
		}
		// Return the JSON document as a text content block, the common shape.
		s.writeResult(w, id, mustJSON(ToolResult{
			Content: []Content{{Type: "text", Text: string(mustJSON(missions))}},
		}))
	case "submit_deliverable":
		s.writeResult(w, id, mustJSON(ToolResult{
			Content: []Content{{Type: "text", Text: `{"accepted":true}`}},
		}))
	case "explode":
		// A tool that runs but reports a domain error.
		s.writeResult(w, id, mustJSON(ToolResult{
			IsError: true,
			Content: []Content{{Type: "text", Text: "mission not found"}},
		}))
	default:
		s.writeRPCError(w, id, ErrCodeInvalidParams, "unknown tool: "+call.Name)
	}
}

// writeResult emits a JSON-RPC success, either as a single JSON object or as a
// one-event SSE stream, depending on the stub's mode.
func (s *mcpStub) writeResult(w http.ResponseWriter, id, result json.RawMessage) {
	env := map[string]any{"jsonrpc": "2.0", "id": rawID(id), "result": json.RawMessage(result)}
	s.writeEnvelope(w, env)
}

func (s *mcpStub) writeRPCError(w http.ResponseWriter, id json.RawMessage, code int, msg string) {
	env := map[string]any{
		"jsonrpc": "2.0",
		"id":      rawID(id),
		"error":   map[string]any{"code": code, "message": msg},
	}
	s.writeEnvelope(w, env)
}

func (s *mcpStub) writeEnvelope(w http.ResponseWriter, env map[string]any) {
	payload := mustJSON(env)
	if !s.sse {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(payload)
		return
	}
	// SSE: emit a comment keep-alive and an interleaved server-initiated
	// notification (both of which the client must ignore), then the JSON-RPC
	// response on a single data line (the real-world shape).
	w.Header().Set("Content-Type", "text/event-stream")
	w.WriteHeader(http.StatusOK)
	flusher, _ := w.(http.Flusher)
	fmt.Fprint(w, ": keep-alive\n\n")
	fmt.Fprint(w, "event: message\n")
	fmt.Fprint(w, "data: {\"jsonrpc\":\"2.0\",\"method\":\"notifications/progress\",\"params\":{\"progress\":1}}\n\n")
	fmt.Fprintf(w, "event: message\ndata: %s\n\n", payload)
	if flusher != nil {
		flusher.Flush()
	}
}

// rawID echoes the request id back into the response untouched.
func rawID(id json.RawMessage) json.RawMessage {
	if len(id) == 0 {
		return json.RawMessage("null")
	}
	return id
}

func mustJSON(v any) json.RawMessage {
	b, err := json.Marshal(v)
	if err != nil {
		panic(err)
	}
	return b
}

// newClient builds a Client pointed at the stub server.
func newClient(t *testing.T, srv *httptest.Server) *Client {
	t.Helper()
	return New(
		WithEndpointURL(srv.URL),
		WithClientInfo("agent.test", "9.9.9"),
		WithHTTPClient(srv.Client()),
	)
}

// --- Tests -------------------------------------------------------------------

func TestInitializeHandshakeOrderAndSession(t *testing.T) {
	for _, sse := range []bool{false, true} {
		name := "json"
		if sse {
			name = "sse"
		}
		t.Run(name, func(t *testing.T) {
			stub := newStub(t, sse)
			srv := stub.server()
			defer srv.Close()
			cli := newClient(t, srv)

			ctx := context.Background()
			info, err := cli.Initialize(ctx)
			if err != nil {
				t.Fatalf("Initialize: %v", err)
			}
			if info.ProtocolVersion != ProtocolVersion {
				t.Errorf("negotiated version = %q; want %q", info.ProtocolVersion, ProtocolVersion)
			}
			if info.ServerInfo.Name != "oabp-mcp-stub" {
				t.Errorf("serverInfo.name = %q; want oabp-mcp-stub", info.ServerInfo.Name)
			}
			if !info.ToolsAvailable() {
				t.Error("ToolsAvailable() = false; want true (server advertised tools)")
			}

			// Handshake order: initialize then initialized, both seen by server.
			stub.mu.Lock()
			defer stub.mu.Unlock()
			if !stub.initializeSeen {
				t.Error("server never saw initialize")
			}
			if !stub.initializedSeen {
				t.Error("server never saw notifications/initialized")
			}
			if !stub.sawSessionOnInit {
				t.Error("initialized notification did not carry the session id")
			}
			// Session persisted on the client.
			if got := cli.SessionID(); got != stubSessionID {
				t.Errorf("client SessionID() = %q; want %q", got, stubSessionID)
			}
			if got := cli.NegotiatedProtocolVersion(); got != ProtocolVersion {
				t.Errorf("client NegotiatedProtocolVersion() = %q; want %q", got, ProtocolVersion)
			}
		})
	}
}

func TestToolsListAndCallRequireSession(t *testing.T) {
	for _, sse := range []bool{false, true} {
		name := "json"
		if sse {
			name = "sse"
		}
		t.Run(name, func(t *testing.T) {
			stub := newStub(t, sse)
			srv := stub.server()
			defer srv.Close()
			cli := newClient(t, srv)

			ctx := context.Background()
			if _, err := cli.Initialize(ctx); err != nil {
				t.Fatalf("Initialize: %v", err)
			}

			tools, err := cli.ListTools(ctx)
			if err != nil {
				t.Fatalf("ListTools: %v", err)
			}
			if len(tools) != 2 || tools[0].Name != "list_missions" {
				t.Fatalf("ListTools = %+v; want list_missions first of 2", tools)
			}

			// Server recorded the protocol-version header on the tools/list call.
			stub.mu.Lock()
			pv := stub.gotProtocolVer
			stub.mu.Unlock()
			if pv != ProtocolVersion {
				t.Errorf("server saw MCP-Protocol-Version=%q; want %q", pv, ProtocolVersion)
			}

			// list_missions via the typed helper.
			missions, err := cli.ListMissions(ctx)
			if err != nil {
				t.Fatalf("ListMissions: %v", err)
			}
			if len(missions) != 2 {
				t.Fatalf("ListMissions returned %d; want 2", len(missions))
			}
			if missions[0].ID != "m-001" || missions[0].Reward.Currency != CurrencyAIGEN {
				t.Errorf("mission[0] = %+v; want id m-001 / AIGEN", missions[0])
			}
			if missions[0].VerificationType != VerificationOracle {
				t.Errorf("mission[0] verification = %q; want oracle", missions[0].VerificationType)
			}
			if missions[1].Reward.Amount != 1000 || missions[1].Reward.Currency != CurrencyUSDC {
				t.Errorf("mission[1] reward = %+v; want 1000 USDC", missions[1].Reward)
			}
			// Raw preserved.
			if !strings.Contains(string(missions[0].Raw), "m-001") {
				t.Error("mission Raw not preserved")
			}
		})
	}
}

func TestCallToolJSONAndDomainError(t *testing.T) {
	stub := newStub(t, false)
	srv := stub.server()
	defer srv.Close()
	cli := newClient(t, srv)

	ctx := context.Background()
	if _, err := cli.Initialize(ctx); err != nil {
		t.Fatalf("Initialize: %v", err)
	}

	// Typed decode of a successful tool result.
	var out struct {
		Accepted bool `json:"accepted"`
	}
	if err := cli.CallToolJSON(ctx, "submit_deliverable",
		map[string]any{"mission_id": "m-001", "proof": "https://example/repo"}, &out); err != nil {
		t.Fatalf("CallToolJSON: %v", err)
	}
	if !out.Accepted {
		t.Error("submit_deliverable: accepted = false; want true")
	}

	// A tool that reports isError=true must surface as *ToolError, not swallowed.
	err := cli.CallToolJSON(ctx, "explode", nil, nil)
	if err == nil {
		t.Fatal("expected ToolError from isError tool, got nil")
	}
	var te *ToolError
	if !errorsAs(err, &te) {
		t.Fatalf("error type = %T; want *ToolError", err)
	}
	if !strings.Contains(te.Message, "mission not found") {
		t.Errorf("ToolError.Message = %q; want it to contain 'mission not found'", te.Message)
	}
}

func TestCallBeforeInitializeRejected(t *testing.T) {
	stub := newStub(t, false)
	srv := stub.server()
	defer srv.Close()
	cli := newClient(t, srv)

	ctx := context.Background()
	if _, err := cli.ListTools(ctx); err != ErrNotInitialized {
		t.Fatalf("ListTools before Initialize = %v; want ErrNotInitialized", err)
	}
	if _, err := cli.CallTool(ctx, "list_missions", nil); err != ErrNotInitialized {
		t.Fatalf("CallTool before Initialize = %v; want ErrNotInitialized", err)
	}
}

func TestUnknownToolRPCError(t *testing.T) {
	stub := newStub(t, false)
	srv := stub.server()
	defer srv.Close()
	cli := newClient(t, srv)

	ctx := context.Background()
	if _, err := cli.Initialize(ctx); err != nil {
		t.Fatalf("Initialize: %v", err)
	}
	_, err := cli.CallTool(ctx, "does_not_exist", nil)
	if err == nil {
		t.Fatal("expected RPCError for unknown tool, got nil")
	}
	var re *RPCError
	if !errorsAs(err, &re) {
		t.Fatalf("error type = %T; want *RPCError", err)
	}
	if re.Code != ErrCodeInvalidParams {
		t.Errorf("RPCError.Code = %d; want %d", re.Code, ErrCodeInvalidParams)
	}
}

func TestClose(t *testing.T) {
	stub := newStub(t, false)
	srv := stub.server()
	defer srv.Close()
	cli := newClient(t, srv)

	ctx := context.Background()
	if _, err := cli.Initialize(ctx); err != nil {
		t.Fatalf("Initialize: %v", err)
	}
	if err := cli.Close(ctx); err != nil {
		t.Fatalf("Close: %v", err)
	}
	stub.mu.Lock()
	deleted := stub.deleted
	stub.mu.Unlock()
	if !deleted {
		t.Error("server did not receive session DELETE")
	}
	if cli.SessionID() != "" {
		t.Error("client retained session id after Close")
	}
}

// TestReadSSE_Reassembly exercises the SSE reader directly: keep-alive comments,
// an interleaved server notification, a response for a different id, and a
// payload split across two data lines mid-token (which the fallback joins).
func TestReadSSE_Reassembly(t *testing.T) {
	const stream = ": ping\n" +
		"\n" +
		"data: {\"jsonrpc\":\"2.0\",\"method\":\"notifications/message\",\"params\":{}}\n" +
		"\n" +
		"data: {\"jsonrpc\":\"2.0\",\"id\":7,\"result\":{\"other\":true}}\n" +
		"\n" +
		// id 42 response, split across two data lines mid-token:
		"data: {\"jsonrpc\":\"2.0\",\"id\":4\n" +
		"data: 2,\"result\":{\"ok\":true,\"n\":5}}\n" +
		"\n"

	res, rpcErr, err := readSSE(strings.NewReader(stream), 42)
	if err != nil {
		t.Fatalf("readSSE: %v", err)
	}
	if rpcErr != nil {
		t.Fatalf("unexpected rpc error: %v", rpcErr)
	}
	var got struct {
		OK bool `json:"ok"`
		N  int  `json:"n"`
	}
	if err := json.Unmarshal(res, &got); err != nil {
		t.Fatalf("decode result %s: %v", res, err)
	}
	if !got.OK || got.N != 5 {
		t.Errorf("result = %+v; want {ok:true n:5}", got)
	}
}

// TestReadSSE_SingleLine covers the common case: one data line per event.
func TestReadSSE_SingleLine(t *testing.T) {
	const stream = "event: message\n" +
		"data: {\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"v\":\"hi\"}}\n\n"
	res, rpcErr, err := readSSE(strings.NewReader(stream), 1)
	if err != nil || rpcErr != nil {
		t.Fatalf("readSSE: err=%v rpcErr=%v", err, rpcErr)
	}
	if !strings.Contains(string(res), `"v":"hi"`) {
		t.Errorf("result = %s; want it to contain v:hi", res)
	}
}

// errorsAs is a tiny local wrapper to avoid importing errors in two files; it
// behaves like errors.As for the concrete pointer types used here.
func errorsAs[T error](err error, target *T) bool {
	for err != nil {
		if t, ok := err.(T); ok {
			*target = t
			return true
		}
		u, ok := err.(interface{ Unwrap() error })
		if !ok {
			return false
		}
		err = u.Unwrap()
	}
	return false
}
