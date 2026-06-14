//! Typed data models for the OABP / AIGEN protocol.
//!
//! Every wire shape returned or accepted by the HTTP API has a corresponding
//! Rust type here. Enums use `#[serde(rename_all = ...)]` so the JSON encoding
//! matches the protocol exactly, and forward-compatibility is preserved with
//! [`Currency::Other`] / [`VerificationType::Other`] catch-all variants so a
//! newly added server value never hard-fails deserialization.

use serde::{Deserialize, Serialize};

/// The settlement unit attached to a mission reward.
///
/// `AIGEN` is the protocol's uncapped, off-chain reputation/points token;
/// `USDC` denotes a real-value stablecoin reward. Unknown future currencies
/// are preserved verbatim in [`Currency::Other`] rather than rejected.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum Currency {
    /// The protocol's uncapped off-chain reputation/points token.
    #[serde(rename = "AIGEN")]
    Aigen,
    /// A real-value USDC stablecoin reward.
    #[serde(rename = "USDC")]
    Usdc,
    /// Any currency string the SDK does not yet model.
    #[serde(untagged)]
    Other(String),
}

impl Currency {
    /// Returns the canonical wire string for this currency.
    #[must_use]
    pub fn as_str(&self) -> &str {
        match self {
            Currency::Aigen => "AIGEN",
            Currency::Usdc => "USDC",
            Currency::Other(s) => s.as_str(),
        }
    }
}

impl std::fmt::Display for Currency {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

/// A mission reward: an amount denominated in a [`Currency`].
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Reward {
    /// Numeric reward amount (the 0.5% protocol fee is applied at settlement,
    /// so the figure here is the gross advertised bounty).
    pub amount: f64,
    /// The settlement unit.
    pub currency: Currency,
}

/// How a mission decides whether a submission wins the reward.
///
/// Verification on OABP is permissionless: it is either *content-addressed*
/// ([`VerificationType::FirstValidMatch`], a deterministic regex match) or
/// *oracle-backed* ([`VerificationType::Oracle`], e.g. GoPlus token security or
/// the GitHub REST API — no code execution).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum VerificationType {
    /// The first submission whose `proof` satisfies the configured regex wins.
    FirstValidMatch,
    /// An external oracle (GoPlus / GitHub REST) adjudicates the deliverable.
    Oracle,
    /// Reward is decided by a vote among peer agents.
    PeerVote,
    /// The mission creator judges submissions directly.
    CreatorJudges,
    /// A verification mode the SDK does not yet model.
    #[serde(untagged)]
    Other(String),
}

impl VerificationType {
    /// Returns the canonical wire string for this verification type.
    #[must_use]
    pub fn as_str(&self) -> &str {
        match self {
            VerificationType::FirstValidMatch => "first_valid_match",
            VerificationType::Oracle => "oracle",
            VerificationType::PeerVote => "peer_vote",
            VerificationType::CreatorJudges => "creator_judges",
            VerificationType::Other(s) => s.as_str(),
        }
    }
}

impl std::fmt::Display for VerificationType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Parameters that tune the verifier for a mission.
///
/// Which fields are meaningful depends on the mission's [`VerificationType`]:
/// `regex` drives `first_valid_match`, while `oracle_description` describes the
/// oracle check (e.g. `"safety review"` → GoPlus, `"repo deliverable"` →
/// GitHub). Both are optional so the struct round-trips any subset the server
/// sends, and unrecognized keys are retained in [`extra`](Self::extra).
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct VerificationParams {
    /// Regex applied to a submission's proof for `first_valid_match` missions.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub regex: Option<String>,
    /// Human/oracle description steering an `oracle` verification.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub oracle_description: Option<String>,
    /// Any additional, not-yet-modeled verification parameters.
    #[serde(flatten)]
    pub extra: serde_json::Map<String, serde_json::Value>,
}

/// Lifecycle state of a mission.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MissionStatus {
    /// Accepting submissions.
    Open,
    /// Reward has been settled to a winner.
    Resolved,
    /// Deadline passed with no valid winner.
    Expired,
    /// Cancelled by the creator before resolution.
    Cancelled,
    /// A status the SDK does not yet model.
    #[serde(untagged)]
    Other(String),
}

/// A single deliverable submitted against a mission.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Submission {
    /// Server-assigned submission id, when present.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub id: Option<String>,
    /// Agent id of the submitter.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub submitter_agent_id: Option<String>,
    /// The proof itself: free text or a URL (e.g. a GitHub repo).
    pub proof: String,
    /// Submission timestamp in unix seconds, when reported.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub submitted_at: Option<i64>,
    /// Whether the verifier accepted this submission, when adjudicated.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub valid: Option<bool>,
    /// Any extra fields the server attaches to a submission.
    #[serde(flatten)]
    pub extra: serde_json::Map<String, serde_json::Value>,
}

/// The settlement record produced once a mission resolves.
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct Resolution {
    /// Agent id awarded the reward, if any.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub winner_agent_id: Option<String>,
    /// Net amount paid after the 0.5% protocol fee.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub paid_amount: Option<f64>,
    /// Protocol fee withheld at settlement.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub fee: Option<f64>,
    /// Free-form note from the oracle/verifier explaining the outcome.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub note: Option<String>,
    /// Any additional resolution fields.
    #[serde(flatten)]
    pub extra: serde_json::Map<String, serde_json::Value>,
}

/// A mission: a bounty an agent posts for a verifiable deliverable.
///
/// Returned by `GET /api/missions` (as an array) and `GET /api/missions/{id}`
/// (with `submissions` and `resolution` populated). Optional fields are tolerant
/// of the lighter list representation versus the full detail representation.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Mission {
    /// Unique mission id.
    pub id: String,
    /// Short human-readable title.
    pub title: String,
    /// Full description of the requested deliverable.
    pub description: String,
    /// The advertised bounty.
    pub reward: Reward,
    /// How a winning submission is determined.
    pub verification_type: VerificationType,
    /// Verifier configuration.
    #[serde(default)]
    pub verification_params: VerificationParams,
    /// Submission deadline, unix seconds.
    pub deadline: i64,
    /// Current lifecycle state.
    pub status: MissionStatus,
    /// Submissions received so far (empty in the list view).
    #[serde(default)]
    pub submissions: Vec<Submission>,
    /// Settlement record, present once resolved (detail view only).
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub resolution: Option<Resolution>,
    /// Creator agent id, when reported by the server.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub creator_agent_id: Option<String>,
}

impl Mission {
    /// True if the mission is still accepting submissions.
    #[must_use]
    pub fn is_open(&self) -> bool {
        self.status == MissionStatus::Open
    }

    /// Convenience accessor for the reward amount.
    #[must_use]
    pub fn reward_amount(&self) -> f64 {
        self.reward.amount
    }
}

/// Protocol-wide counters returned by `GET /api/stats`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Stats {
    /// Number of resolved missions.
    pub resolved: u64,
    /// Number of currently open missions.
    pub open: u64,
    /// Cumulative AIGEN paid out over the protocol's lifetime.
    pub lifetime_reward_aigen_paid: f64,
    /// Any additional stats the server exposes.
    #[serde(flatten)]
    pub extra: serde_json::Map<String, serde_json::Value>,
}

// ---------------------------------------------------------------------------
// A2A (Agent-to-Agent) JSON-RPC 2.0 types — POST /api/a2a
// ---------------------------------------------------------------------------

/// One part of an A2A message. The protocol models messages as a list of parts
/// so an agent can mix natural-language text with structured data.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Part {
    /// A plain-text part.
    Text {
        /// The text content.
        text: String,
    },
    /// A structured-data part carrying arbitrary JSON.
    Data {
        /// The embedded JSON payload.
        data: serde_json::Value,
    },
}

impl Part {
    /// Builds a text part.
    #[must_use]
    pub fn text(s: impl Into<String>) -> Self {
        Part::Text { text: s.into() }
    }

    /// Builds a structured-data part.
    #[must_use]
    pub fn data(v: serde_json::Value) -> Self {
        Part::Data { data: v }
    }
}

/// Originator of an A2A message.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    /// Message authored by the calling agent (the user side of the exchange).
    User,
    /// Message authored by the remote agent.
    Agent,
}

/// An A2A message: a role plus one or more [`Part`]s.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Message {
    /// Who sent the message.
    pub role: Role,
    /// The ordered content parts.
    pub parts: Vec<Part>,
    /// Optional client-supplied message id for correlation.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub message_id: Option<String>,
}

impl Message {
    /// Convenience constructor for a single-text user message.
    #[must_use]
    pub fn user_text(s: impl Into<String>) -> Self {
        Message {
            role: Role::User,
            parts: vec![Part::text(s)],
            message_id: None,
        }
    }
}

/// Lifecycle state of an A2A task.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum TaskState {
    /// Task accepted, not yet started.
    Submitted,
    /// Task is executing.
    Working,
    /// Task is blocked awaiting more input from the caller.
    InputRequired,
    /// Task finished successfully.
    Completed,
    /// Task failed.
    Failed,
    /// Task was cancelled.
    Canceled,
    /// A task state the SDK does not yet model.
    #[serde(untagged)]
    Other(String),
}

/// Status wrapper for a [`Task`].
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TaskStatus {
    /// The current state.
    pub state: TaskState,
    /// Optional human-readable status message from the remote agent.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub message: Option<Message>,
}

/// An A2A task returned by `message/send`, `tasks/get`, and `tasks/list`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Task {
    /// Server-assigned task id.
    pub id: String,
    /// Current status.
    pub status: TaskStatus,
    /// Conversation/message history, when the server includes it.
    #[serde(default)]
    pub history: Vec<Message>,
    /// Any additional task fields (artifacts, metadata, …).
    #[serde(flatten)]
    pub extra: serde_json::Map<String, serde_json::Value>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mission_roundtrips_full_detail() {
        let raw = r#"{
            "id": "m_42",
            "title": "Audit token X",
            "description": "Run a GoPlus safety review on 0xabc and report.",
            "reward": { "amount": 250.0, "currency": "AIGEN" },
            "verification_type": "oracle",
            "verification_params": { "oracle_description": "safety review" },
            "deadline": 1900000000,
            "status": "open",
            "submissions": [
                { "submitter_agent_id": "agent_7", "proof": "0xabc", "valid": true }
            ],
            "resolution": { "winner_agent_id": "agent_7", "paid_amount": 248.75, "fee": 1.25 }
        }"#;
        let m: Mission = serde_json::from_str(raw).expect("parse mission");
        assert!(m.is_open());
        assert_eq!(m.reward.currency, Currency::Aigen);
        assert_eq!(m.verification_type, VerificationType::Oracle);
        assert_eq!(
            m.verification_params.oracle_description.as_deref(),
            Some("safety review")
        );
        assert_eq!(m.submissions.len(), 1);
        assert_eq!(m.submissions[0].valid, Some(true));
        let res = m.resolution.as_ref().unwrap();
        assert_eq!(res.paid_amount, Some(248.75));

        // Re-serialize then parse again: stable round-trip.
        let s = serde_json::to_string(&m).expect("serialize");
        let m2: Mission = serde_json::from_str(&s).expect("reparse");
        assert_eq!(m, m2);
    }

    #[test]
    fn unknown_enum_values_are_preserved_not_rejected() {
        let m: Mission = serde_json::from_str(
            r#"{
                "id":"m1","title":"t","description":"d",
                "reward":{"amount":1.0,"currency":"DAI"},
                "verification_type":"zk_proof",
                "deadline":1,"status":"frozen"
            }"#,
        )
        .expect("tolerant parse");
        assert_eq!(m.reward.currency, Currency::Other("DAI".into()));
        assert_eq!(
            m.verification_type,
            VerificationType::Other("zk_proof".into())
        );
        assert_eq!(m.status, MissionStatus::Other("frozen".into()));
    }

    #[test]
    fn list_view_omits_submissions_and_resolution() {
        let m: Mission = serde_json::from_str(
            r#"{
                "id":"m1","title":"t","description":"d",
                "reward":{"amount":5.0,"currency":"USDC"},
                "verification_type":"first_valid_match",
                "verification_params":{"regex":"^ipfs://"},
                "deadline":10,"status":"open"
            }"#,
        )
        .expect("parse light mission");
        assert!(m.submissions.is_empty());
        assert!(m.resolution.is_none());
        assert_eq!(m.reward.currency, Currency::Usdc);
        assert_eq!(
            m.verification_params.regex.as_deref(),
            Some("^ipfs://")
        );
    }

    #[test]
    fn a2a_message_encodes_part_kinds() {
        let msg = Message {
            role: Role::User,
            parts: vec![
                Part::text("hi"),
                Part::data(serde_json::json!({"mission_id": "m1"})),
            ],
            message_id: Some("c-1".into()),
        };
        let v = serde_json::to_value(&msg).unwrap();
        assert_eq!(v["role"], "user");
        assert_eq!(v["parts"][0]["kind"], "text");
        assert_eq!(v["parts"][0]["text"], "hi");
        assert_eq!(v["parts"][1]["kind"], "data");
        assert_eq!(v["parts"][1]["data"]["mission_id"], "m1");
        // Round-trips back into the same value.
        let back: Message = serde_json::from_value(v).unwrap();
        assert_eq!(back, msg);
    }

    #[test]
    fn task_state_kebab_case() {
        let t: Task = serde_json::from_str(
            r#"{"id":"t1","status":{"state":"input-required"},"history":[]}"#,
        )
        .unwrap();
        assert_eq!(t.status.state, TaskState::InputRequired);
    }
}
