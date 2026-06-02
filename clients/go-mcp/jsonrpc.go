package mcp

import (
	"encoding/json"
	"fmt"
)

// jsonrpcVersion is the JSON-RPC version MCP mandates.
const jsonrpcVersion = "2.0"

// rpcRequest is a JSON-RPC 2.0 request. A request always carries an id; a
// notification (see rpcNotification) never does. ID is json.RawMessage so the
// caller controls its encoding (we use integers), and so the zero value is not
// confused with id 0.
type rpcRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

// rpcNotification is a JSON-RPC 2.0 notification: a request with no id, to which
// the server returns no response. MCP uses these for lifecycle events such as
// notifications/initialized.
type rpcNotification struct {
	JSONRPC string          `json:"jsonrpc"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

// rpcResponse is a JSON-RPC 2.0 response. Exactly one of Result / Error is set
// on a well-formed response. Result and ID are left raw so the caller decodes
// them as needed (ID is used to match a response to its request when several
// messages arrive on one SSE stream).
type rpcResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   *RPCError       `json:"error,omitempty"`
	// Method is non-empty when the decoded frame is actually a server-initiated
	// request or notification rather than a response; readResult uses this to
	// skip such frames on an SSE stream.
	Method string `json:"method,omitempty"`
}

// RPCError is a JSON-RPC 2.0 error object as returned by the MCP server. It
// implements error, so it can be returned directly from client methods and
// inspected with errors.As.
type RPCError struct {
	Code    int             `json:"code"`
	Message string          `json:"message"`
	Data    json.RawMessage `json:"data,omitempty"`
}

// Error implements error.
func (e *RPCError) Error() string {
	if len(e.Data) > 0 {
		return fmt.Sprintf("mcp: rpc error %d: %s: %s", e.Code, e.Message, string(e.Data))
	}
	return fmt.Sprintf("mcp: rpc error %d: %s", e.Code, e.Message)
}

// Standard JSON-RPC error codes, surfaced for callers that switch on Code.
const (
	ErrCodeParse          = -32700
	ErrCodeInvalidRequest = -32600
	ErrCodeMethodNotFound = -32601
	ErrCodeInvalidParams  = -32602
	ErrCodeInternal       = -32603
)
