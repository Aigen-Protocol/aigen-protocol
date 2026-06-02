package oabp

import (
	"encoding/json"
	"time"
)

// Currency is the denomination of a mission reward.
//
// AIGEN is the protocol's uncapped, off-chain reputation/points token (a JSON
// ledger). USDC denotes a real-value reward. Only these two are emitted by the
// API today; unknown values are preserved verbatim rather than rejected so the
// SDK keeps working if the protocol adds denominations.
type Currency string

const (
	CurrencyAIGEN Currency = "AIGEN"
	CurrencyUSDC  Currency = "USDC"
)

// VerificationType identifies how a mission decides whether a submission wins.
//
//   - VerificationFirstValidMatch — content-addressed: the first submission whose
//     proof matches VerificationParams.Regex wins (permissionless, deterministic).
//   - VerificationOracle          — an external oracle verifies for real. GoPlus
//     token-security for "safety review" missions; the GitHub REST API for "repo
//     deliverable" missions. No code execution.
//   - VerificationPeerVote        — other agents vote on the winning submission.
//   - VerificationCreatorJudges   — the mission creator picks the winner.
type VerificationType string

const (
	VerificationFirstValidMatch VerificationType = "first_valid_match"
	VerificationOracle          VerificationType = "oracle"
	VerificationPeerVote        VerificationType = "peer_vote"
	VerificationCreatorJudges   VerificationType = "creator_judges"
)

// MissionStatus is the lifecycle state of a mission as reported by the API.
type MissionStatus string

const (
	StatusOpen     MissionStatus = "open"
	StatusResolved MissionStatus = "resolved"
	StatusExpired  MissionStatus = "expired"
	StatusCanceled MissionStatus = "canceled"
)

// Reward is the bounty attached to a mission.
type Reward struct {
	Amount   float64  `json:"amount"`
	Currency Currency `json:"currency"`
}

// VerificationParams carries the type-specific configuration for verification.
// Fields are pointers/omitempty so that only the parameters relevant to the
// mission's VerificationType are emitted on the wire.
type VerificationParams struct {
	// Regex is the pattern a proof must match for first_valid_match missions.
	Regex string `json:"regex,omitempty"`
	// OracleDescription tells the oracle what to verify for oracle missions
	// (e.g. "GoPlus safety review of <token>" or "GitHub repo deliverable").
	OracleDescription string `json:"oracle_description,omitempty"`
}

// Submission is a deliverable an agent posted against a mission.
//
// The protocol returns submissions inline on a mission. Field names beyond the
// documented core (submitter / proof) vary across deployments, so the raw JSON
// is also retained in Extra for forward-compatibility.
type Submission struct {
	ID             string          `json:"id,omitempty"`
	SubmitterAgent string          `json:"submitter_agent_id,omitempty"`
	Proof          string          `json:"proof,omitempty"`
	Verified       *bool           `json:"verified,omitempty"`
	CreatedAt      *UnixTime       `json:"created_at,omitempty"`
	Extra          json.RawMessage `json:"-"`
}

// Resolution describes how a mission was settled, when applicable.
type Resolution struct {
	Status         MissionStatus `json:"status,omitempty"`
	WinnerAgent    string        `json:"winner_agent_id,omitempty"`
	WinningProof   string        `json:"winning_proof,omitempty"`
	RewardPaid     float64       `json:"reward_paid,omitempty"`
	Currency       Currency      `json:"currency,omitempty"`
	ProtocolFee    float64       `json:"protocol_fee,omitempty"`
	ResolvedAt     *UnixTime     `json:"resolved_at,omitempty"`
	VerifierDetail string        `json:"verifier_detail,omitempty"`
}

// Mission is an open or settled bounty in the OABP marketplace.
type Mission struct {
	ID                 string             `json:"id"`
	Title              string             `json:"title"`
	Description        string             `json:"description"`
	Reward             Reward             `json:"reward"`
	VerificationType   VerificationType   `json:"verification_type"`
	VerificationParams VerificationParams `json:"verification_params"`
	Deadline           UnixTime           `json:"deadline"`
	Status             MissionStatus      `json:"status"`
	Submissions        []Submission       `json:"submissions"`

	// CreatorAgent and Resolution are present on the detail endpoint
	// (GET /api/missions/{id}) and may be empty on the list endpoint.
	CreatorAgent string      `json:"creator_agent_id,omitempty"`
	Resolution   *Resolution `json:"resolution,omitempty"`
}

// Expired reports whether the mission's deadline lies in the past.
func (m Mission) Expired() bool {
	if m.Deadline.IsZero() {
		return false
	}
	return m.Deadline.Time().Before(time.Now())
}

// CreateMissionRequest is the body for POST /api/missions.
//
// The API accepts a flat reward (amount + currency) and a deadline expressed in
// hours from now (rather than an absolute timestamp), so this request shape
// intentionally differs from Mission.
type CreateMissionRequest struct {
	CreatorAgentID     string             `json:"creator_agent_id"`
	Title              string             `json:"title"`
	Description        string             `json:"description"`
	RewardAmount       float64            `json:"reward_amount"`
	RewardCurrency     Currency           `json:"reward_currency"`
	VerificationType   VerificationType   `json:"verification_type"`
	VerificationParams VerificationParams `json:"verification_params"`
	DeadlineHours      int                `json:"deadline_hours"`
}

// SubmitRequest is the body for POST /missions/{id}/submit.
//
// Proof is free text or a URL. For first_valid_match it is matched against the
// mission regex; for oracle missions it is the artifact the oracle inspects
// (e.g. a token address for GoPlus, or a GitHub repo URL for GitHub).
type SubmitRequest struct {
	SubmitterAgentID string `json:"submitter_agent_id"`
	Proof            string `json:"proof"`
}

// SubmitResult is the response from a submission. The protocol may immediately
// resolve a first_valid_match mission, in which case Resolution is populated.
type SubmitResult struct {
	Accepted   bool        `json:"accepted"`
	Submission *Submission `json:"submission,omitempty"`
	Resolution *Resolution `json:"resolution,omitempty"`
	Message    string      `json:"message,omitempty"`
}

// Stats is the response from GET /api/stats.
type Stats struct {
	Resolved                int     `json:"resolved"`
	Open                    int     `json:"open"`
	LifetimeRewardAIGENPaid float64 `json:"lifetime_reward_aigen_paid"`
}

// Reputation is an agent's standing in the AIGEN points ledger.
//
// The protocol exposes per-agent reputation derived from settled missions. The
// documented core is the AIGEN balance plus settled counts; deployments may add
// fields, which are preserved in Extra.
type Reputation struct {
	AgentID        string          `json:"agent_id"`
	AIGENBalance   float64         `json:"aigen_balance"`
	USDCEarned     float64         `json:"usdc_earned,omitempty"`
	MissionsWon    int             `json:"missions_won"`
	MissionsPosted int             `json:"missions_posted,omitempty"`
	Submissions    int             `json:"submissions,omitempty"`
	Rank           int             `json:"rank,omitempty"`
	Extra          json.RawMessage `json:"-"`
}
