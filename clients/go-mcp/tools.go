package mcp

import (
	"context"
	"encoding/json"
	"fmt"
)

// ListTools calls tools/list and returns every advertised tool, transparently
// following the server's pagination cursor. The handshake must have completed.
func (c *Client) ListTools(ctx context.Context) ([]Tool, error) {
	if !c.isInitialized() {
		return nil, ErrNotInitialized
	}
	var all []Tool
	cursor := ""
	for {
		var params map[string]any
		if cursor != "" {
			params = map[string]any{"cursor": cursor}
		}
		raw, err := c.call(ctx, "tools/list", params)
		if err != nil {
			return nil, err
		}
		var page listToolsResult
		if len(raw) > 0 {
			if err := json.Unmarshal(raw, &page); err != nil {
				return nil, fmt.Errorf("mcp: decode tools/list result: %w", err)
			}
		}
		all = append(all, page.Tools...)
		if page.NextCursor == "" {
			break
		}
		cursor = page.NextCursor
	}
	return all, nil
}

// CallTool invokes tools/call for the named tool with the given arguments
// (which are JSON-encoded; pass nil or an empty map for no arguments).
//
// The returned error is non-nil only for transport or protocol failures (an
// *HTTPError, or an *RPCError when the call is malformed / the tool is unknown).
// A tool that ran but reported a domain-level failure returns a non-nil
// ToolResult with IsError == true; callers should check that flag. This split
// mirrors MCP's two failure channels.
func (c *Client) CallTool(ctx context.Context, name string, args any) (*ToolResult, error) {
	if !c.isInitialized() {
		return nil, ErrNotInitialized
	}
	if name == "" {
		return nil, fmt.Errorf("mcp: CallTool: empty tool name")
	}
	params := map[string]any{"name": name}
	if args != nil {
		params["arguments"] = args
	}
	raw, err := c.call(ctx, "tools/call", params)
	if err != nil {
		return nil, err
	}
	var result ToolResult
	if len(raw) > 0 {
		if err := json.Unmarshal(raw, &result); err != nil {
			return nil, fmt.Errorf("mcp: decode tools/call result for %q: %w", name, err)
		}
	}
	return &result, nil
}

// CallToolJSON is CallTool plus a typed decode: it calls the tool, fails if the
// tool reported isError (surfacing the error text), and otherwise unmarshals the
// tool's payload (structuredContent when present, else its text content) into
// out. It is the ergonomic path for tools that return a JSON document.
func (c *Client) CallToolJSON(ctx context.Context, name string, args any, out any) error {
	res, err := c.CallTool(ctx, name, args)
	if err != nil {
		return err
	}
	if res.IsError {
		return &ToolError{Tool: name, Message: res.Text()}
	}
	if out == nil {
		return nil
	}
	payload := res.payload()
	if len(payload) == 0 {
		return nil
	}
	if err := json.Unmarshal(payload, out); err != nil {
		return fmt.Errorf("mcp: decode %q payload: %w", name, err)
	}
	return nil
}

// ToolError reports that a tool executed but returned isError = true. It carries
// the tool name and the message the tool emitted.
type ToolError struct {
	Tool    string
	Message string
}

// Error implements error.
func (e *ToolError) Error() string {
	if e.Message == "" {
		return fmt.Sprintf("mcp: tool %q reported an error", e.Tool)
	}
	return fmt.Sprintf("mcp: tool %q error: %s", e.Tool, e.Message)
}

// isInitialized reports whether the handshake has completed.
func (c *Client) isInitialized() bool {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.initialized
}

// ----- OABP mission convenience wrappers -------------------------------------

// ListMissions calls the OABP "list_missions" tool and decodes the open
// missions. The OABP MCP server may return the missions either as a bare JSON
// array or wrapped in an object ({"missions":[...]}); both are handled.
//
// Tool naming is a server-side detail; if a deployment exposes the tool under a
// different name, use CallToolJSON directly with that name.
func (c *Client) ListMissions(ctx context.Context) ([]Mission, error) {
	res, err := c.CallTool(ctx, "list_missions", map[string]any{})
	if err != nil {
		return nil, err
	}
	if res.IsError {
		return nil, &ToolError{Tool: "list_missions", Message: res.Text()}
	}
	return decodeMissions(res.payload())
}

// decodeMissions accepts both a bare array and an object that wraps the array
// under "missions" or "data".
func decodeMissions(payload []byte) ([]Mission, error) {
	if len(payload) == 0 {
		return nil, nil
	}
	var arr []Mission
	if err := json.Unmarshal(payload, &arr); err == nil {
		return arr, nil
	}
	var wrapped struct {
		Missions []Mission `json:"missions"`
		Data     []Mission `json:"data"`
	}
	if err := json.Unmarshal(payload, &wrapped); err != nil {
		return nil, fmt.Errorf("mcp: decode missions payload: %w", err)
	}
	if wrapped.Missions != nil {
		return wrapped.Missions, nil
	}
	return wrapped.Data, nil
}
