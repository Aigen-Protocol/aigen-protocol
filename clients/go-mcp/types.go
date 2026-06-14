package mcp

import "encoding/json"

// ProtocolVersion is the MCP revision this client advertises in the initialize
// request. The server replies with the version it will actually use, which the
// client then echoes in the MCP-Protocol-Version header. Date-based versions are
// how MCP is versioned.
const ProtocolVersion = "2025-06-18"

// Implementation identifies a party in the handshake (clientInfo / serverInfo).
type Implementation struct {
	Name    string `json:"name"`
	Title   string `json:"title,omitempty"`
	Version string `json:"version"`
}

// ClientCapabilities advertises what the client supports. The OABP client is a
// plain tool caller, so it advertises no optional capabilities by default; the
// struct is kept so callers and the server see a well-formed object.
type ClientCapabilities struct {
	// Roots, sampling and elicitation are not implemented by this client; their
	// absence (omitempty) signals "unsupported" per the spec.
	Roots        *RootsCapability `json:"roots,omitempty"`
	Sampling     json.RawMessage  `json:"sampling,omitempty"`
	Elicitation  json.RawMessage  `json:"elicitation,omitempty"`
	Experimental json.RawMessage  `json:"experimental,omitempty"`
}

// RootsCapability declares filesystem-roots support.
type RootsCapability struct {
	ListChanged bool `json:"listChanged,omitempty"`
}

// initializeParams is the params object of the initialize request.
type initializeParams struct {
	ProtocolVersion string             `json:"protocolVersion"`
	Capabilities    ClientCapabilities `json:"capabilities"`
	ClientInfo      Implementation     `json:"clientInfo"`
}

// InitializeResult is the server's reply to initialize. Capabilities is kept raw
// because the server's capability set is open-ended; callers that care can
// decode it, and ToolsAvailable reports the common case.
type InitializeResult struct {
	ProtocolVersion string          `json:"protocolVersion"`
	Capabilities    json.RawMessage `json:"capabilities"`
	ServerInfo      Implementation  `json:"serverInfo"`
	Instructions    string          `json:"instructions,omitempty"`
}

// ToolsAvailable reports whether the server advertised a "tools" capability,
// i.e. whether tools/list and tools/call are expected to work.
func (r InitializeResult) ToolsAvailable() bool {
	if len(r.Capabilities) == 0 {
		return false
	}
	var caps struct {
		Tools json.RawMessage `json:"tools"`
	}
	if err := json.Unmarshal(r.Capabilities, &caps); err != nil {
		return false
	}
	return len(caps.Tools) > 0
}

// Tool is a tool advertised by tools/list. InputSchema is the JSON Schema the
// server expects for this tool's arguments; it is kept raw so callers can both
// inspect it and avoid a brittle schema model.
type Tool struct {
	Name         string          `json:"name"`
	Title        string          `json:"title,omitempty"`
	Description  string          `json:"description,omitempty"`
	InputSchema  json.RawMessage `json:"inputSchema,omitempty"`
	OutputSchema json.RawMessage `json:"outputSchema,omitempty"`
}

// listToolsResult is the result of tools/list. NextCursor drives pagination.
type listToolsResult struct {
	Tools      []Tool `json:"tools"`
	NextCursor string `json:"nextCursor,omitempty"`
}

// Content is one block of a tool-call result. Kind "text" carries Text; other
// kinds (image, audio, resource) pass through Raw so nothing is lost.
type Content struct {
	Type string          `json:"type"`
	Text string          `json:"text,omitempty"`
	Raw  json.RawMessage `json:"-"`
}

// UnmarshalJSON decodes a content block and retains the full object in Raw.
func (c *Content) UnmarshalJSON(data []byte) error {
	type alias Content
	var a alias
	if err := json.Unmarshal(data, &a); err != nil {
		return err
	}
	*c = Content(a)
	raw := make(json.RawMessage, len(data))
	copy(raw, data)
	c.Raw = raw
	return nil
}

// ToolResult is the result of tools/call.
//
// MCP tools report two distinct kinds of failure:
//
//   - A JSON-RPC error (returned from CallTool as an *RPCError) means the call
//     itself was malformed or the tool does not exist.
//   - A successful JSON-RPC response with IsError == true means the tool ran but
//     reported a domain error; the message is in Content. Callers should check
//     IsError, which is why CallTool surfaces it rather than swallowing it.
type ToolResult struct {
	Content           []Content       `json:"content"`
	StructuredContent json.RawMessage `json:"structuredContent,omitempty"`
	IsError           bool            `json:"isError,omitempty"`
}

// Text concatenates the text of all text content blocks, which is the common
// way a tool returns a JSON or plain-text payload.
func (r ToolResult) Text() string {
	var b []byte
	for _, c := range r.Content {
		if c.Type == "text" {
			if len(b) > 0 {
				b = append(b, '\n')
			}
			b = append(b, c.Text...)
		}
	}
	return string(b)
}

// payload returns the most useful JSON body of a tool result for typed
// decoding: structuredContent when the server provides it (preferred), else the
// concatenated text (tools commonly return a JSON document as text).
func (r ToolResult) payload() []byte {
	if len(r.StructuredContent) > 0 {
		return r.StructuredContent
	}
	return []byte(r.Text())
}

// ----- OABP domain types (subset, for the typed list_missions helper) --------

// Currency is the denomination of a mission reward: AIGEN (the protocol's
// uncapped off-chain points token) or USDC (real value).
type Currency string

const (
	CurrencyAIGEN Currency = "AIGEN"
	CurrencyUSDC  Currency = "USDC"
)

// VerificationType is how a mission decides a winner: content-addressed
// (first_valid_match), oracle-backed (GoPlus / GitHub), peer_vote, or
// creator_judges.
type VerificationType string

const (
	VerificationFirstValidMatch VerificationType = "first_valid_match"
	VerificationOracle          VerificationType = "oracle"
	VerificationPeerVote        VerificationType = "peer_vote"
	VerificationCreatorJudges   VerificationType = "creator_judges"
)

// Reward is the bounty on a mission.
type Reward struct {
	Amount   float64  `json:"amount"`
	Currency Currency `json:"currency"`
}

// Mission is an open or settled bounty as returned by the list_missions tool.
// Only the documented core is typed; the untouched object is preserved in Raw so
// deployment-specific fields are never dropped.
type Mission struct {
	ID               string           `json:"id"`
	Title            string           `json:"title"`
	Description      string           `json:"description"`
	Reward           Reward           `json:"reward"`
	VerificationType VerificationType `json:"verification_type"`
	Deadline         int64            `json:"deadline"`
	Status           string           `json:"status"`
	Raw              json.RawMessage  `json:"-"`
}

// UnmarshalJSON decodes a Mission and keeps the full object in Raw.
func (m *Mission) UnmarshalJSON(data []byte) error {
	type alias Mission
	var a alias
	if err := json.Unmarshal(data, &a); err != nil {
		return err
	}
	*m = Mission(a)
	raw := make(json.RawMessage, len(data))
	copy(raw, data)
	m.Raw = raw
	return nil
}
