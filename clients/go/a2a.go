package oabp

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync/atomic"
)

// A2A (Agent-to-Agent) support: a JSON-RPC 2.0 client over POST /api/a2a, plus
// helpers to fetch the ES256-signed agent card and the JWKS used to verify it.

// pathA2A is the JSON-RPC endpoint.
const pathA2A = "/api/a2a"

// JSON-RPC method names exposed by the protocol's A2A endpoint.
const (
	A2AMethodMessageSend = "message/send"
	A2AMethodTasksGet    = "tasks/get"
	A2AMethodTasksList   = "tasks/list"
)

// rpcRequest is a JSON-RPC 2.0 request envelope.
type rpcRequest struct {
	JSONRPC string `json:"jsonrpc"`
	ID      int64  `json:"id"`
	Method  string `json:"method"`
	Params  any    `json:"params,omitempty"`
}

// rpcError is a JSON-RPC 2.0 error object.
type rpcError struct {
	Code    int             `json:"code"`
	Message string          `json:"message"`
	Data    json.RawMessage `json:"data,omitempty"`
}

// Error implements error.
func (e *rpcError) Error() string {
	if len(e.Data) > 0 {
		return fmt.Sprintf("oabp a2a: rpc error %d: %s: %s", e.Code, e.Message, string(e.Data))
	}
	return fmt.Sprintf("oabp a2a: rpc error %d: %s", e.Code, e.Message)
}

// rpcResponse is a JSON-RPC 2.0 response envelope. Result is left raw so callers
// can decode it into the appropriate type.
type rpcResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Result  json.RawMessage `json:"result"`
	Error   *rpcError       `json:"error"`
}

// rpcID is a monotonically increasing JSON-RPC id source. A single atomic
// counter is sufficient because ids only need to be unique per client.
var rpcID atomic.Int64

// A2ACall performs a raw JSON-RPC call against the A2A endpoint and decodes the
// result into out (which may be nil to discard it). It returns the JSON-RPC
// error as an *rpcError when the server reports one.
//
// Most callers should use the typed helpers (SendMessage, GetTask, ListTasks)
// instead; A2ACall is exported for forward-compatibility with methods this SDK
// version does not yet model.
func (c *Client) A2ACall(ctx context.Context, method string, params, out any) error {
	reqEnv := rpcRequest{
		JSONRPC: "2.0",
		ID:      rpcID.Add(1),
		Method:  method,
		Params:  params,
	}
	var respEnv rpcResponse
	if err := c.doJSON(ctx, http.MethodPost, pathA2A, reqEnv, &respEnv); err != nil {
		return err
	}
	if respEnv.Error != nil {
		return respEnv.Error
	}
	if out == nil || len(respEnv.Result) == 0 {
		return nil
	}
	if err := json.Unmarshal(respEnv.Result, out); err != nil {
		return fmt.Errorf("oabp a2a: decode result of %q: %w", method, err)
	}
	return nil
}

// A2AMessage is an A2A message, following the A2A protocol shape: a role and an
// ordered list of parts. Use TextMessage for the common single-text case.
type A2AMessage struct {
	Role      string    `json:"role"`
	Parts     []A2APart `json:"parts"`
	MessageID string    `json:"messageId,omitempty"`
	Metadata  any       `json:"metadata,omitempty"`
}

// A2APart is one part of a message. Kind is "text" for textual parts; the Text
// field carries the content. Other kinds (file/data) pass through Raw.
type A2APart struct {
	Kind string `json:"kind"`
	Text string `json:"text,omitempty"`
}

// TextMessage builds a user-role A2A message carrying a single text part.
func TextMessage(text string) A2AMessage {
	return A2AMessage{
		Role:  "user",
		Parts: []A2APart{{Kind: "text", Text: text}},
	}
}

// A2ATask is a task returned by the A2A endpoint. The protocol's task objects
// vary in their fields across implementations, so the documented core (id /
// status) is typed and the full object is retained in Raw.
type A2ATask struct {
	ID     string          `json:"id"`
	Status json.RawMessage `json:"status,omitempty"`
	Raw    json.RawMessage `json:"-"`
}

// UnmarshalJSON decodes an A2ATask and keeps the raw object in Raw.
func (t *A2ATask) UnmarshalJSON(data []byte) error {
	type alias A2ATask
	var a alias
	if err := json.Unmarshal(data, &a); err != nil {
		return err
	}
	*t = A2ATask(a)
	raw := make(json.RawMessage, len(data))
	copy(raw, data)
	t.Raw = raw
	return nil
}

// SendMessage invokes the A2A "message/send" method and returns the raw result,
// which per the A2A spec is either a Message or a Task depending on the agent.
// The bytes are returned verbatim so callers can decode whichever they expect.
func (c *Client) SendMessage(ctx context.Context, msg A2AMessage) (json.RawMessage, error) {
	params := map[string]any{"message": msg}
	var result json.RawMessage
	if err := c.A2ACall(ctx, A2AMethodMessageSend, params, &result); err != nil {
		return nil, err
	}
	return result, nil
}

// GetTask invokes the A2A "tasks/get" method for a given task id.
func (c *Client) GetTask(ctx context.Context, taskID string) (*A2ATask, error) {
	if taskID == "" {
		return nil, fmt.Errorf("oabp a2a: GetTask: empty task id")
	}
	params := map[string]any{"id": taskID}
	var task A2ATask
	if err := c.A2ACall(ctx, A2AMethodTasksGet, params, &task); err != nil {
		return nil, err
	}
	return &task, nil
}

// ListTasks invokes the A2A "tasks/list" method and returns the tasks. Some
// deployments wrap the array in a {"tasks":[...]} object; both shapes are
// handled.
func (c *Client) ListTasks(ctx context.Context) ([]A2ATask, error) {
	var raw json.RawMessage
	if err := c.A2ACall(ctx, A2AMethodTasksList, map[string]any{}, &raw); err != nil {
		return nil, err
	}
	// Try a bare array first.
	var tasks []A2ATask
	if err := json.Unmarshal(raw, &tasks); err == nil {
		return tasks, nil
	}
	// Fall back to a wrapped object.
	var wrapped struct {
		Tasks []A2ATask `json:"tasks"`
	}
	if err := json.Unmarshal(raw, &wrapped); err != nil {
		return nil, fmt.Errorf("oabp a2a: decode tasks/list result: %w", err)
	}
	return wrapped.Tasks, nil
}

// AgentCard is the (partial) A2A agent card describing this protocol's agent.
// Only the commonly used fields are typed; the complete signed document is in
// Raw for callers that verify the ES256 signature against the JWKS.
type AgentCard struct {
	Name               string          `json:"name"`
	Description        string          `json:"description,omitempty"`
	URL                string          `json:"url,omitempty"`
	Version            string          `json:"version,omitempty"`
	ProtocolVersion    string          `json:"protocolVersion,omitempty"`
	PreferredTransport string          `json:"preferredTransport,omitempty"`
	Raw                json.RawMessage `json:"-"`
}

// UnmarshalJSON decodes an AgentCard and keeps the raw document in Raw so the
// ES256 JWS signature can be verified by the caller.
func (a *AgentCard) UnmarshalJSON(data []byte) error {
	type alias AgentCard
	var v alias
	if err := json.Unmarshal(data, &v); err != nil {
		return err
	}
	*a = AgentCard(v)
	raw := make(json.RawMessage, len(data))
	copy(raw, data)
	a.Raw = raw
	return nil
}

// AgentCard fetches the ES256-signed agent card from
// /.well-known/agent-card.json.
func (c *Client) AgentCard(ctx context.Context) (*AgentCard, error) {
	var card AgentCard
	if err := c.doJSON(ctx, http.MethodGet, "/.well-known/agent-card.json", nil, &card); err != nil {
		return nil, err
	}
	return &card, nil
}

// JWKS fetches the JSON Web Key Set used to verify the agent card's ES256
// signature, from /.well-known/jwks.json. The keys are returned as raw JSON
// objects so callers can feed them to their JWK library of choice.
func (c *Client) JWKS(ctx context.Context) ([]json.RawMessage, error) {
	var set struct {
		Keys []json.RawMessage `json:"keys"`
	}
	if err := c.doJSON(ctx, http.MethodGet, "/.well-known/jwks.json", nil, &set); err != nil {
		return nil, err
	}
	return set.Keys, nil
}
