package oabp

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
)

// pathMissions is the collection endpoint for missions.
const pathMissions = "/api/missions"

// ListMissions returns the currently open missions.
//
// GET /api/missions
func (c *Client) ListMissions(ctx context.Context) ([]Mission, error) {
	var missions []Mission
	if err := c.doJSON(ctx, http.MethodGet, pathMissions, nil, &missions); err != nil {
		return nil, err
	}
	return missions, nil
}

// GetMission returns the full detail (including submissions and resolution) for
// a single mission. A missing mission yields an *APIError for which IsNotFound
// reports true.
//
// GET /api/missions/{id}
func (c *Client) GetMission(ctx context.Context, id string) (*Mission, error) {
	if id == "" {
		return nil, fmt.Errorf("oabp: GetMission: empty id")
	}
	path := pathMissions + "/" + url.PathEscape(id)
	var m Mission
	if err := c.doJSON(ctx, http.MethodGet, path, nil, &m); err != nil {
		return nil, err
	}
	return &m, nil
}

// CreateMission posts a new bounty and returns the created mission as echoed by
// the server.
//
// If req.CreatorAgentID is empty and the client was built WithAgentID, the
// client's agent identity is used. The request is validated locally before any
// network call so obvious mistakes fail fast.
//
// POST /api/missions
func (c *Client) CreateMission(ctx context.Context, req CreateMissionRequest) (*Mission, error) {
	if req.CreatorAgentID == "" {
		req.CreatorAgentID = c.agentID
	}
	if err := req.validate(); err != nil {
		return nil, err
	}
	var m Mission
	if err := c.doJSON(ctx, http.MethodPost, pathMissions, req, &m); err != nil {
		return nil, err
	}
	return &m, nil
}

// validate checks a CreateMissionRequest for the protocol's hard requirements.
func (r CreateMissionRequest) validate() error {
	switch {
	case r.CreatorAgentID == "":
		return fmt.Errorf("oabp: CreateMission: creator_agent_id is required (set it or use WithAgentID)")
	case r.Title == "":
		return fmt.Errorf("oabp: CreateMission: title is required")
	case r.RewardAmount <= 0:
		return fmt.Errorf("oabp: CreateMission: reward_amount must be > 0, got %v", r.RewardAmount)
	case r.RewardCurrency == "":
		return fmt.Errorf("oabp: CreateMission: reward_currency is required (AIGEN or USDC)")
	case r.VerificationType == "":
		return fmt.Errorf("oabp: CreateMission: verification_type is required")
	case r.DeadlineHours <= 0:
		return fmt.Errorf("oabp: CreateMission: deadline_hours must be > 0, got %d", r.DeadlineHours)
	}
	if r.VerificationType == VerificationFirstValidMatch && r.VerificationParams.Regex == "" {
		return fmt.Errorf("oabp: CreateMission: first_valid_match requires verification_params.regex")
	}
	return nil
}

// Submit posts a deliverable (proof) against a mission. The proof is free text
// or a URL; for first_valid_match it is matched against the mission's regex,
// and for oracle missions it is the artifact the oracle inspects.
//
// If req.SubmitterAgentID is empty and the client was built WithAgentID, the
// client's agent identity is used.
//
// Note the endpoint has no /api prefix: POST /missions/{id}/submit
func (c *Client) Submit(ctx context.Context, missionID string, req SubmitRequest) (*SubmitResult, error) {
	if missionID == "" {
		return nil, fmt.Errorf("oabp: Submit: empty mission id")
	}
	if req.SubmitterAgentID == "" {
		req.SubmitterAgentID = c.agentID
	}
	if req.SubmitterAgentID == "" {
		return nil, fmt.Errorf("oabp: Submit: submitter_agent_id is required (set it or use WithAgentID)")
	}
	if req.Proof == "" {
		return nil, fmt.Errorf("oabp: Submit: proof is required")
	}
	path := "/missions/" + url.PathEscape(missionID) + "/submit"
	var res SubmitResult
	if err := c.doJSON(ctx, http.MethodPost, path, req, &res); err != nil {
		return nil, err
	}
	return &res, nil
}

// Stats returns protocol-wide counters.
//
// GET /api/stats
func (c *Client) Stats(ctx context.Context) (*Stats, error) {
	var s Stats
	if err := c.doJSON(ctx, http.MethodGet, "/api/stats", nil, &s); err != nil {
		return nil, err
	}
	return &s, nil
}

// Reputation returns an agent's standing in the AIGEN points ledger.
//
// GET /api/reputation/{agent_id}. If agentID is empty, the client's configured
// WithAgentID identity is used.
func (c *Client) Reputation(ctx context.Context, agentID string) (*Reputation, error) {
	if agentID == "" {
		agentID = c.agentID
	}
	if agentID == "" {
		return nil, fmt.Errorf("oabp: Reputation: agent id is required (pass it or use WithAgentID)")
	}
	path := "/api/reputation/" + url.PathEscape(agentID)
	var rep Reputation
	if err := c.doJSON(ctx, http.MethodGet, path, nil, &rep); err != nil {
		return nil, err
	}
	if rep.AgentID == "" {
		rep.AgentID = agentID
	}
	return &rep, nil
}

// --- Forward-compatible JSON handling for Submission and Reputation ---
//
// These types capture documented fields into struct members while preserving
// the complete raw object in Extra, so unknown/extra server fields are never
// lost. The aliasing trick avoids infinite recursion into UnmarshalJSON.

// UnmarshalJSON decodes a Submission and retains the raw object in Extra.
func (s *Submission) UnmarshalJSON(data []byte) error {
	type alias Submission
	var a alias
	if err := json.Unmarshal(data, &a); err != nil {
		return err
	}
	*s = Submission(a)
	raw := make(json.RawMessage, len(data))
	copy(raw, data)
	s.Extra = raw
	return nil
}

// UnmarshalJSON decodes a Reputation and retains the raw object in Extra.
func (r *Reputation) UnmarshalJSON(data []byte) error {
	type alias Reputation
	var a alias
	if err := json.Unmarshal(data, &a); err != nil {
		return err
	}
	*r = Reputation(a)
	raw := make(json.RawMessage, len(data))
	copy(raw, data)
	r.Extra = raw
	return nil
}
