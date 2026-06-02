package mcp

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
)

// DefaultBaseURL is the public OABP / AIGEN deployment.
const DefaultBaseURL = "https://cryptogenesis.duckdns.org"

// DefaultEndpoint is the path of the MCP Streamable HTTP endpoint.
const DefaultEndpoint = "/mcp"

// defaultUserAgent identifies this SDK in outgoing requests.
const defaultUserAgent = "oabp-mcp-go/0.1"

// Header names used by the Streamable HTTP transport.
const (
	headerSessionID       = "Mcp-Session-Id"
	headerProtocolVersion = "MCP-Protocol-Version"
)

// Client is an MCP Streamable HTTP client for the OABP / AIGEN mission server.
//
// A Client must complete the handshake via Initialize before any tool call.
// After Initialize returns it is safe for concurrent use; the negotiated session
// id and protocol version are guarded by mu.
type Client struct {
	endpoint   *url.URL
	httpClient *http.Client
	clientInfo Implementation
	caps       ClientCapabilities
	userAgent  string
	apiKey     string

	// nextID generates JSON-RPC request ids. Guarded by mu.
	nextID int64

	mu          sync.Mutex
	sessionID   string // assigned by the server on initialize, if any
	protocolVer string // version the server agreed to use
	initialized bool
}

// Option configures a Client.
type Option func(*Client)

// WithBaseURL sets the deployment base URL (default DefaultBaseURL); the MCP
// endpoint path (DefaultEndpoint) is appended. Use WithEndpointURL to point at
// a full, non-default endpoint such as an httptest server URL.
func WithBaseURL(raw string) Option {
	return func(c *Client) {
		if u, err := url.Parse(strings.TrimRight(raw, "/") + DefaultEndpoint); err == nil && u.Host != "" {
			c.endpoint = u
		}
	}
}

// WithEndpointURL sets the full MCP endpoint URL directly (scheme://host/path).
// This is the convenient form for tests: pass an httptest.Server URL.
func WithEndpointURL(raw string) Option {
	return func(c *Client) {
		if u, err := url.Parse(raw); err == nil && u.Host != "" {
			c.endpoint = u
		}
	}
}

// WithHTTPClient injects a custom *http.Client. A nil client is ignored.
//
// The transport may stream responses via SSE, so the injected client should not
// impose a Timeout that would cut a long-lived stream; prefer per-call context
// deadlines instead. A nil-Timeout client (as created by New) is appropriate.
func WithHTTPClient(hc *http.Client) Option {
	return func(c *Client) {
		if hc != nil {
			c.httpClient = hc
		}
	}
}

// WithClientInfo sets the clientInfo (name, version) reported in the handshake.
func WithClientInfo(name, version string) Option {
	return func(c *Client) {
		if name != "" {
			c.clientInfo.Name = name
		}
		if version != "" {
			c.clientInfo.Version = version
		}
	}
}

// WithCapabilities overrides the client capabilities advertised at initialize.
func WithCapabilities(caps ClientCapabilities) Option {
	return func(c *Client) { c.caps = caps }
}

// WithUserAgent overrides the HTTP User-Agent header.
func WithUserAgent(ua string) Option {
	return func(c *Client) {
		if ua != "" {
			c.userAgent = ua
		}
	}
}

// WithAPIKey attaches a bearer token (Authorization header) to every request.
// The public deployment is permissionless; private ones may gate access.
func WithAPIKey(key string) Option {
	return func(c *Client) { c.apiKey = key }
}

// New returns a Client targeting DefaultBaseURL + DefaultEndpoint. The HTTP
// client has no global timeout so SSE streams are not truncated; bound calls
// with the context instead.
func New(opts ...Option) *Client {
	ep, _ := url.Parse(DefaultBaseURL + DefaultEndpoint)
	c := &Client{
		endpoint:   ep,
		httpClient: &http.Client{}, // no Timeout; use ctx deadlines
		clientInfo: Implementation{Name: "oabp-mcp-go", Version: "0.1.0"},
		userAgent:  defaultUserAgent,
	}
	for _, opt := range opts {
		opt(c)
	}
	return c
}

// Endpoint returns the configured MCP endpoint URL.
func (c *Client) Endpoint() string { return c.endpoint.String() }

// SessionID returns the session id assigned by the server, or "" if the server
// did not assign one (sessions are optional in the transport).
func (c *Client) SessionID() string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.sessionID
}

// ProtocolVersion returns the protocol version the server agreed to use, set
// after Initialize. Empty before the handshake.
func (c *Client) NegotiatedProtocolVersion() string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.protocolVer
}

// ErrNotInitialized is returned when a tool call is attempted before Initialize.
var ErrNotInitialized = errors.New("mcp: client not initialized (call Initialize first)")

// Initialize performs the MCP opening handshake in the required order:
//
//  1. POST an "initialize" request with this client's protocolVersion,
//     capabilities and clientInfo, and read the server's InitializeResult.
//  2. Persist the server-assigned Mcp-Session-Id (if any) and the negotiated
//     protocol version.
//  3. POST the mandatory "notifications/initialized" notification.
//
// After Initialize returns nil, tool calls are permitted. Initialize is
// idempotent: once the handshake has succeeded a further call is a no-op, so a
// failed first attempt can be retried without leaving the client half-open.
func (c *Client) Initialize(ctx context.Context) (*InitializeResult, error) {
	c.mu.Lock()
	already := c.initialized
	c.mu.Unlock()
	if already {
		// Idempotent: a second Initialize on an established session is a no-op.
		return &InitializeResult{ProtocolVersion: c.NegotiatedProtocolVersion()}, nil
	}

	params := initializeParams{
		ProtocolVersion: ProtocolVersion,
		Capabilities:    c.caps,
		ClientInfo:      c.clientInfo,
	}

	// Step 1: send initialize and capture the session header from the response.
	resp, sessionID, err := c.callWithHeaders(ctx, "initialize", params)
	if err != nil {
		return nil, err
	}
	var result InitializeResult
	if len(resp) > 0 {
		if err := json.Unmarshal(resp, &result); err != nil {
			return nil, fmt.Errorf("mcp: decode initialize result: %w", err)
		}
	}

	// Step 2: persist session + negotiated version.
	negotiated := result.ProtocolVersion
	if negotiated == "" {
		negotiated = ProtocolVersion
	}
	c.mu.Lock()
	if sessionID != "" {
		c.sessionID = sessionID
	}
	c.protocolVer = negotiated
	c.mu.Unlock()

	// Step 3: the mandatory initialized notification. This MUST carry the
	// session header (set above) so the server binds it to the session.
	if err := c.notify(ctx, "notifications/initialized", nil); err != nil {
		return nil, fmt.Errorf("mcp: send notifications/initialized: %w", err)
	}

	c.mu.Lock()
	c.initialized = true
	c.mu.Unlock()
	return &result, nil
}

// Close terminates the MCP session. If the server assigned a session id, Close
// sends an HTTP DELETE to the endpoint with that id, as the transport allows for
// explicit session teardown. A 405 (server does not support client-initiated
// termination) is treated as success. It is safe to call Close on an
// uninitialized client.
func (c *Client) Close(ctx context.Context) error {
	c.mu.Lock()
	sid := c.sessionID
	pv := c.protocolVer
	c.initialized = false
	c.sessionID = ""
	c.mu.Unlock()
	if sid == "" {
		return nil
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodDelete, c.endpoint.String(), nil)
	if err != nil {
		return fmt.Errorf("mcp: build session-delete request: %w", err)
	}
	req.Header.Set("User-Agent", c.userAgent)
	req.Header.Set(headerSessionID, sid)
	if pv != "" {
		req.Header.Set(headerProtocolVersion, pv)
	}
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		return fmt.Errorf("mcp: session delete: %w", err)
	}
	defer drain(resp.Body)
	if resp.StatusCode == http.StatusMethodNotAllowed {
		return nil // server keeps session lifecycle to itself; not an error
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return &HTTPError{StatusCode: resp.StatusCode, Status: resp.Status}
	}
	return nil
}

// HTTPError is returned for transport-level (non-2xx) failures that are not a
// JSON-RPC error, such as a 4xx/5xx on the POST itself.
type HTTPError struct {
	StatusCode int
	Status     string
	Body       string
}

// Error implements error.
func (e *HTTPError) Error() string {
	if b := strings.TrimSpace(e.Body); b != "" {
		if len(b) > 300 {
			b = b[:300] + "…"
		}
		return fmt.Sprintf("mcp: http %s: %s", e.Status, b)
	}
	return fmt.Sprintf("mcp: http %s", e.Status)
}

// call sends a JSON-RPC request and returns its raw result. It requires the
// session header (when one exists) and the negotiated protocol-version header.
func (c *Client) call(ctx context.Context, method string, params any) (json.RawMessage, error) {
	res, _, err := c.callWithHeaders(ctx, method, params)
	return res, err
}

// callWithHeaders sends a JSON-RPC request and additionally returns the
// Mcp-Session-Id from the response (used by Initialize to capture a new
// session). It marshals params, attaches the lifecycle headers, posts to the
// endpoint, and parses the single response — whether delivered as JSON or SSE.
func (c *Client) callWithHeaders(ctx context.Context, method string, params any) (json.RawMessage, string, error) {
	id := c.allocID()

	var rawParams json.RawMessage
	if params != nil {
		p, err := json.Marshal(params)
		if err != nil {
			return nil, "", fmt.Errorf("mcp: encode params of %q: %w", method, err)
		}
		rawParams = p
	}
	reqEnv := rpcRequest{
		JSONRPC: jsonrpcVersion,
		ID:      json.RawMessage(strconv.FormatInt(id, 10)),
		Method:  method,
		Params:  rawParams,
	}
	body, err := json.Marshal(reqEnv)
	if err != nil {
		return nil, "", fmt.Errorf("mcp: encode request %q: %w", method, err)
	}

	httpResp, err := c.post(ctx, body)
	if err != nil {
		return nil, "", err
	}
	defer drain(httpResp.Body)

	sessionID := httpResp.Header.Get(headerSessionID)

	if httpResp.StatusCode < 200 || httpResp.StatusCode >= 300 {
		b, _ := io.ReadAll(io.LimitReader(httpResp.Body, 8<<10))
		return nil, sessionID, &HTTPError{StatusCode: httpResp.StatusCode, Status: httpResp.Status, Body: string(b)}
	}

	result, rpcErr, err := readResult(httpResp, id)
	if err != nil {
		return nil, sessionID, err
	}
	if rpcErr != nil {
		return nil, sessionID, rpcErr
	}
	return result, sessionID, nil
}

// notify sends a JSON-RPC notification (no id, no response body). On the
// Streamable HTTP transport the server typically replies 202 Accepted with an
// empty body; any 2xx is accepted.
func (c *Client) notify(ctx context.Context, method string, params any) error {
	var rawParams json.RawMessage
	if params != nil {
		p, err := json.Marshal(params)
		if err != nil {
			return fmt.Errorf("mcp: encode params of %q: %w", method, err)
		}
		rawParams = p
	}
	note := rpcNotification{JSONRPC: jsonrpcVersion, Method: method, Params: rawParams}
	body, err := json.Marshal(note)
	if err != nil {
		return fmt.Errorf("mcp: encode notification %q: %w", method, err)
	}
	httpResp, err := c.post(ctx, body)
	if err != nil {
		return err
	}
	defer drain(httpResp.Body)
	if httpResp.StatusCode < 200 || httpResp.StatusCode >= 300 {
		b, _ := io.ReadAll(io.LimitReader(httpResp.Body, 8<<10))
		return &HTTPError{StatusCode: httpResp.StatusCode, Status: httpResp.Status, Body: string(b)}
	}
	return nil
}

// post performs the HTTP POST common to requests and notifications, attaching
// the transport headers (Accept for both JSON and SSE, the negotiated protocol
// version, and the session id once one exists).
func (c *Client) post(ctx context.Context, body []byte) (*http.Response, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.endpoint.String(), bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("mcp: build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	// The server MAY answer with a single JSON object or an SSE stream; accept
	// both, as the Streamable HTTP transport requires.
	req.Header.Set("Accept", "application/json, text/event-stream")
	req.Header.Set("User-Agent", c.userAgent)
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}

	c.mu.Lock()
	sid, pv := c.sessionID, c.protocolVer
	c.mu.Unlock()
	if sid != "" {
		req.Header.Set(headerSessionID, sid)
	}
	if pv != "" {
		req.Header.Set(headerProtocolVersion, pv)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		if ctx.Err() != nil {
			return nil, ctx.Err()
		}
		return nil, fmt.Errorf("mcp: post %s: %w", c.endpoint.Path, err)
	}
	return resp, nil
}

// allocID returns the next JSON-RPC request id.
func (c *Client) allocID() int64 {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.nextID++
	return c.nextID
}

// readResult parses an MCP response body and returns the result matching wantID.
//
// It handles both transport encodings:
//   - application/json: a single JSON-RPC response object.
//   - text/event-stream: a sequence of SSE events; each event's "data:" payload
//     is a JSON-RPC message. The function scans events, skipping server-initiated
//     requests/notifications (those have a "method" and no matching id), until it
//     finds the response whose id == wantID.
func readResult(resp *http.Response, wantID int64) (json.RawMessage, *RPCError, error) {
	mediaType := contentType(resp.Header.Get("Content-Type"))
	switch mediaType {
	case "text/event-stream":
		return readSSE(resp.Body, wantID)
	default: // application/json (or unspecified): treat as a single JSON object
		data, err := io.ReadAll(io.LimitReader(resp.Body, 16<<20))
		if err != nil {
			return nil, nil, fmt.Errorf("mcp: read response: %w", err)
		}
		if len(bytes.TrimSpace(data)) == 0 {
			return nil, nil, fmt.Errorf("mcp: empty response body for request id %d", wantID)
		}
		var env rpcResponse
		if err := json.Unmarshal(data, &env); err != nil {
			return nil, nil, fmt.Errorf("mcp: decode response: %w", err)
		}
		return env.Result, env.Error, nil
	}
}

// readSSE consumes an SSE stream and returns the JSON-RPC response with id ==
// wantID. SSE framing: events are separated by blank lines; lines beginning
// "data:" carry the payload, lines beginning ":" are comments. We decode each
// event's data as a JSON-RPC frame and return the first one that is a response
// to our request, skipping comments, keep-alives, and server-initiated
// requests/notifications.
//
// Per the SSE spec multiple data lines in one event join with "\n"; a JSON-RPC
// message therefore normally arrives on a single data line. For robustness, if
// the "\n"-joined payload does not parse as JSON we also try a plain
// concatenation, so a server that splits a JSON token across data lines is still
// handled.
func readSSE(r io.Reader, wantID int64) (json.RawMessage, *RPCError, error) {
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 0, 64<<10), 16<<20)

	var dataLines [][]byte
	flush := func() (json.RawMessage, *RPCError, bool) {
		if len(dataLines) == 0 {
			return nil, nil, false
		}
		joined := bytes.Join(dataLines, []byte("\n"))
		dataLines = dataLines[:0]
		env, ok := parseFrame(joined)
		if !ok {
			// Retry with a plain concatenation in case a JSON token was split
			// across data lines by the server.
			if cat := bytes.Join(splitNonEmpty(joined), nil); len(cat) > 0 {
				env, ok = parseFrame(cat)
			}
			if !ok {
				return nil, nil, false // not a JSON-RPC frame (e.g. keep-alive)
			}
		}
		// Skip server-initiated requests/notifications (they carry a method).
		if env.Method != "" {
			return nil, nil, false
		}
		if !idMatches(env.ID, wantID) {
			return nil, nil, false // a response to a different request
		}
		return env.Result, env.Error, true
	}

	for sc.Scan() {
		line := sc.Bytes()
		if len(bytes.TrimSpace(line)) == 0 {
			if res, rpcErr, done := flush(); done {
				return res, rpcErr, nil
			}
			continue
		}
		if bytes.HasPrefix(line, []byte(":")) {
			continue // SSE comment / keep-alive
		}
		if rest, ok := cutPrefix(line, []byte("data:")); ok {
			rest = bytes.TrimPrefix(rest, []byte(" "))
			// Copy: the scanner reuses its buffer between Scan calls.
			cp := make([]byte, len(rest))
			copy(cp, rest)
			dataLines = append(dataLines, cp)
		}
		// Other SSE fields (event:, id:, retry:) are not needed here.
	}
	if err := sc.Err(); err != nil {
		return nil, nil, fmt.Errorf("mcp: read SSE stream: %w", err)
	}
	// Stream ended; resolve any trailing event without a terminating blank line.
	if res, rpcErr, done := flush(); done {
		return res, rpcErr, nil
	}
	return nil, nil, fmt.Errorf("mcp: SSE stream closed without a response to request id %d", wantID)
}

// parseFrame decodes a JSON-RPC frame, returning ok=false if the bytes are not
// valid JSON (so non-JSON SSE payloads are ignored rather than fatal).
func parseFrame(b []byte) (rpcResponse, bool) {
	b = bytes.TrimSpace(b)
	if len(b) == 0 || b[0] != '{' {
		return rpcResponse{}, false
	}
	var env rpcResponse
	if err := json.Unmarshal(b, &env); err != nil {
		return rpcResponse{}, false
	}
	return env, true
}

// splitNonEmpty splits on newlines and drops empty segments, used for the
// fallback plain-concatenation reassembly.
func splitNonEmpty(b []byte) [][]byte {
	parts := bytes.Split(b, []byte("\n"))
	out := parts[:0]
	for _, p := range parts {
		if len(bytes.TrimSpace(p)) > 0 {
			out = append(out, p)
		}
	}
	return out
}

// idMatches reports whether a JSON-RPC id field equals the wanted integer id.
// Ids are compared as their JSON numeric value to tolerate "1" vs " 1 ".
func idMatches(raw json.RawMessage, want int64) bool {
	if len(raw) == 0 {
		return false
	}
	var n json.Number
	if err := json.Unmarshal(raw, &n); err != nil {
		return false
	}
	got, err := n.Int64()
	if err != nil {
		return false
	}
	return got == want
}

// contentType extracts the bare media type from a Content-Type header value.
func contentType(v string) string {
	if v == "" {
		return ""
	}
	mt, _, err := mime.ParseMediaType(v)
	if err != nil {
		// Fall back to the substring before any ';'.
		if i := strings.IndexByte(v, ';'); i >= 0 {
			return strings.TrimSpace(strings.ToLower(v[:i]))
		}
		return strings.TrimSpace(strings.ToLower(v))
	}
	return mt
}

// cutPrefix is strings.CutPrefix for byte slices (Go 1.20+ has bytes.CutPrefix,
// but we keep a local copy to support the module's go 1.22 floor without
// assuming the helper across toolchains).
func cutPrefix(s, prefix []byte) ([]byte, bool) {
	if bytes.HasPrefix(s, prefix) {
		return s[len(prefix):], true
	}
	return s, false
}

// drain reads and closes a response body so the connection can be reused.
func drain(rc io.ReadCloser) {
	if rc == nil {
		return
	}
	_, _ = io.Copy(io.Discard, io.LimitReader(rc, 1<<20))
	_ = rc.Close()
}
