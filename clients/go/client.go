package oabp

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// DefaultBaseURL is the public OABP / AIGEN deployment.
const DefaultBaseURL = "https://cryptogenesis.duckdns.org"

// userAgent identifies this SDK in outgoing requests.
const userAgent = "oabp-go/0.1"

// Client is a concurrency-safe OABP / AIGEN API client. Create one with New and
// share it; it holds no per-call mutable state.
type Client struct {
	baseURL    *url.URL
	httpClient *http.Client
	agentID    string
	apiKey     string
	userAgent  string
}

// Option configures a Client.
type Option func(*Client)

// WithBaseURL overrides the API base URL (default DefaultBaseURL). The value is
// validated when New is called.
func WithBaseURL(raw string) Option {
	return func(c *Client) {
		if u, err := url.Parse(strings.TrimRight(raw, "/")); err == nil && u.Host != "" {
			c.baseURL = u
		}
	}
}

// WithHTTPClient injects a custom *http.Client (for custom transports, proxies,
// timeouts, or test servers). A nil client is ignored.
func WithHTTPClient(hc *http.Client) Option {
	return func(c *Client) {
		if hc != nil {
			c.httpClient = hc
		}
	}
}

// WithAgentID sets the calling agent's identity. When set, it is used as the
// default creator_agent_id / submitter_agent_id where the caller leaves those
// fields blank, so agents need not repeat their ID on every call.
func WithAgentID(id string) Option {
	return func(c *Client) { c.agentID = id }
}

// WithAPIKey attaches a bearer token to every request (Authorization header).
// The public deployment is permissionless, but private deployments may gate
// writes behind a key.
func WithAPIKey(key string) Option {
	return func(c *Client) { c.apiKey = key }
}

// WithUserAgent overrides the User-Agent header.
func WithUserAgent(ua string) Option {
	return func(c *Client) {
		if ua != "" {
			c.userAgent = ua
		}
	}
}

// New returns a Client. With no options it targets DefaultBaseURL using an
// *http.Client with a 30s timeout.
func New(opts ...Option) *Client {
	base, _ := url.Parse(DefaultBaseURL)
	c := &Client{
		baseURL:    base,
		httpClient: &http.Client{Timeout: 30 * time.Second},
		userAgent:  userAgent,
	}
	for _, opt := range opts {
		opt(c)
	}
	return c
}

// AgentID returns the configured calling-agent identity, if any.
func (c *Client) AgentID() string { return c.agentID }

// BaseURL returns the configured base URL as a string.
func (c *Client) BaseURL() string { return c.baseURL.String() }

// APIError is returned for non-2xx HTTP responses. It exposes the status code
// and the raw response body so callers can switch on either.
type APIError struct {
	StatusCode int
	Status     string
	Method     string
	Path       string
	Body       string
	// Message is the "error"/"message" field decoded from a JSON error body,
	// when present.
	Message string
}

// Error implements error.
func (e *APIError) Error() string {
	msg := e.Message
	if msg == "" {
		msg = strings.TrimSpace(e.Body)
	}
	if len(msg) > 300 {
		msg = msg[:300] + "…"
	}
	if msg == "" {
		return fmt.Sprintf("oabp: %s %s: %s", e.Method, e.Path, e.Status)
	}
	return fmt.Sprintf("oabp: %s %s: %s: %s", e.Method, e.Path, e.Status, msg)
}

// NotFound reports whether the error is an APIError with HTTP 404.
func (e *APIError) NotFound() bool { return e != nil && e.StatusCode == http.StatusNotFound }

// IsNotFound reports whether err is an *APIError with status 404. It is the
// idiomatic way to detect a missing mission.
func IsNotFound(err error) bool {
	ae, ok := err.(*APIError)
	return ok && ae.StatusCode == http.StatusNotFound
}

// resolveURL joins a path (which may contain a leading slash and a raw query)
// onto the base URL. Path segments are expected to be pre-escaped by the caller
// via url.PathEscape where they contain user input.
func (c *Client) resolveURL(path string) string {
	if strings.HasPrefix(path, "http://") || strings.HasPrefix(path, "https://") {
		return path
	}
	return strings.TrimRight(c.baseURL.String(), "/") + "/" + strings.TrimLeft(path, "/")
}

// doJSON performs an HTTP request with an optional JSON body and decodes a JSON
// response into out (which may be nil to discard the body). The context governs
// the whole call.
func (c *Client) doJSON(ctx context.Context, method, path string, body, out any) error {
	var reqBody io.Reader
	if body != nil {
		buf, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("oabp: encode request body: %w", err)
		}
		reqBody = bytes.NewReader(buf)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.resolveURL(path), reqBody)
	if err != nil {
		return fmt.Errorf("oabp: build request: %w", err)
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", c.userAgent)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if c.apiKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.apiKey)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		// Surface context cancellation/deadline cleanly.
		if ctx.Err() != nil {
			return fmt.Errorf("oabp: %s %s: %w", method, path, ctx.Err())
		}
		return fmt.Errorf("oabp: %s %s: %w", method, path, err)
	}
	defer resp.Body.Close()

	// Cap the body read to avoid unbounded memory on a misbehaving server,
	// while staying generous for large mission lists.
	const maxBody = 16 << 20 // 16 MiB
	data, err := io.ReadAll(io.LimitReader(resp.Body, maxBody))
	if err != nil {
		return fmt.Errorf("oabp: read response: %w", err)
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		ae := &APIError{
			StatusCode: resp.StatusCode,
			Status:     resp.Status,
			Method:     method,
			Path:       path,
			Body:       string(data),
		}
		// Best-effort extraction of a JSON error message.
		var errEnv struct {
			Error   string `json:"error"`
			Message string `json:"message"`
			Detail  string `json:"detail"`
		}
		if json.Unmarshal(data, &errEnv) == nil {
			switch {
			case errEnv.Error != "":
				ae.Message = errEnv.Error
			case errEnv.Message != "":
				ae.Message = errEnv.Message
			case errEnv.Detail != "":
				ae.Message = errEnv.Detail
			}
		}
		return ae
	}

	if out == nil {
		return nil
	}
	if len(bytes.TrimSpace(data)) == 0 {
		return nil
	}
	if err := json.Unmarshal(data, out); err != nil {
		return fmt.Errorf("oabp: decode response: %w", err)
	}
	return nil
}
