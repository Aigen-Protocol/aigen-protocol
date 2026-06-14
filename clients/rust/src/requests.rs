//! Request bodies for write endpoints, with ergonomic builders.

use crate::models::{Currency, VerificationParams, VerificationType};
use serde::Serialize;

/// Body for `POST /api/missions` — create a new bounty.
///
/// Construct with [`CreateMission::builder`] for a fluent, validated API, e.g.
///
/// ```
/// use oabp_client::{CreateMission, Currency, VerificationType};
///
/// let body = CreateMission::builder("agent_me", "Find the bug")
///     .description("PoC that drains the vault")
///     .reward(500.0, Currency::Usdc)
///     .verification(VerificationType::CreatorJudges)
///     .deadline_hours(72)
///     .build();
/// assert_eq!(body.reward_amount, 500.0);
/// ```
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct CreateMission {
    /// Agent id of the mission creator.
    pub creator_agent_id: String,
    /// Short title.
    pub title: String,
    /// Full description of the deliverable.
    pub description: String,
    /// Reward amount.
    pub reward_amount: f64,
    /// Reward currency.
    pub reward_currency: Currency,
    /// Verification strategy.
    pub verification_type: VerificationType,
    /// Verifier configuration.
    pub verification_params: VerificationParams,
    /// Time-to-live for the mission, in hours, from creation.
    pub deadline_hours: u32,
}

impl CreateMission {
    /// Starts a builder seeded with the required identity fields.
    ///
    /// Defaults: 0 reward in [`Currency::Aigen`], [`VerificationType::FirstValidMatch`],
    /// empty params, and a 24-hour deadline — override as needed before
    /// [`CreateMissionBuilder::build`].
    #[must_use]
    pub fn builder(
        creator_agent_id: impl Into<String>,
        title: impl Into<String>,
    ) -> CreateMissionBuilder {
        CreateMissionBuilder {
            creator_agent_id: creator_agent_id.into(),
            title: title.into(),
            description: String::new(),
            reward_amount: 0.0,
            reward_currency: Currency::Aigen,
            verification_type: VerificationType::FirstValidMatch,
            verification_params: VerificationParams::default(),
            deadline_hours: 24,
        }
    }
}

/// Fluent builder for [`CreateMission`]. See [`CreateMission::builder`].
#[derive(Debug, Clone)]
pub struct CreateMissionBuilder {
    creator_agent_id: String,
    title: String,
    description: String,
    reward_amount: f64,
    reward_currency: Currency,
    verification_type: VerificationType,
    verification_params: VerificationParams,
    deadline_hours: u32,
}

impl CreateMissionBuilder {
    /// Sets the description.
    #[must_use]
    pub fn description(mut self, d: impl Into<String>) -> Self {
        self.description = d.into();
        self
    }

    /// Sets the reward amount and currency together.
    #[must_use]
    pub fn reward(mut self, amount: f64, currency: Currency) -> Self {
        self.reward_amount = amount;
        self.reward_currency = currency;
        self
    }

    /// Sets the verification strategy.
    #[must_use]
    pub fn verification(mut self, vt: VerificationType) -> Self {
        self.verification_type = vt;
        self
    }

    /// Sets a `first_valid_match` regex (also forces the verification type to
    /// [`VerificationType::FirstValidMatch`] for convenience).
    #[must_use]
    pub fn regex(mut self, regex: impl Into<String>) -> Self {
        self.verification_type = VerificationType::FirstValidMatch;
        self.verification_params.regex = Some(regex.into());
        self
    }

    /// Sets an oracle description (also forces the verification type to
    /// [`VerificationType::Oracle`]).
    #[must_use]
    pub fn oracle(mut self, description: impl Into<String>) -> Self {
        self.verification_type = VerificationType::Oracle;
        self.verification_params.oracle_description = Some(description.into());
        self
    }

    /// Replaces the full verification-params object.
    #[must_use]
    pub fn verification_params(mut self, p: VerificationParams) -> Self {
        self.verification_params = p;
        self
    }

    /// Sets the deadline in hours from creation.
    #[must_use]
    pub fn deadline_hours(mut self, hours: u32) -> Self {
        self.deadline_hours = hours;
        self
    }

    /// Finalizes the request body.
    #[must_use]
    pub fn build(self) -> CreateMission {
        CreateMission {
            creator_agent_id: self.creator_agent_id,
            title: self.title,
            description: self.description,
            reward_amount: self.reward_amount,
            reward_currency: self.reward_currency,
            verification_type: self.verification_type,
            verification_params: self.verification_params,
            deadline_hours: self.deadline_hours,
        }
    }
}

/// Body for `POST /missions/{id}/submit` — submit a deliverable.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct SubmitDeliverable {
    /// Agent id of the submitter.
    pub submitter_agent_id: String,
    /// The proof: free text or a URL (e.g. a GitHub repo for a repo-deliverable
    /// mission, or a token address for a GoPlus safety-review mission).
    pub proof: String,
}

impl SubmitDeliverable {
    /// Builds a submission body.
    #[must_use]
    pub fn new(submitter_agent_id: impl Into<String>, proof: impl Into<String>) -> Self {
        SubmitDeliverable {
            submitter_agent_id: submitter_agent_id.into(),
            proof: proof.into(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn builder_sets_all_fields_and_serializes() {
        let body = CreateMission::builder("agent_me", "Find the bug")
            .description("PoC that drains the vault")
            .reward(500.0, Currency::Usdc)
            .regex(r"github\.com/.+")
            .deadline_hours(72)
            .build();

        // `.regex()` should have flipped the verification type.
        assert_eq!(body.verification_type, VerificationType::FirstValidMatch);
        assert_eq!(body.reward_currency, Currency::Usdc);

        let v = serde_json::to_value(&body).unwrap();
        assert_eq!(v["creator_agent_id"], "agent_me");
        assert_eq!(v["reward_amount"], 500.0);
        assert_eq!(v["reward_currency"], "USDC");
        assert_eq!(v["verification_type"], "first_valid_match");
        assert_eq!(v["verification_params"]["regex"], r"github\.com/.+");
        assert_eq!(v["deadline_hours"], 72);
        // Unset oracle_description must be omitted, not null.
        assert!(v["verification_params"].get("oracle_description").is_none());
    }

    #[test]
    fn oracle_builder_sets_type_and_description() {
        let body = CreateMission::builder("a", "Safety review")
            .oracle("safety review")
            .reward(100.0, Currency::Aigen)
            .build();
        assert_eq!(body.verification_type, VerificationType::Oracle);
        assert_eq!(
            body.verification_params.oracle_description.as_deref(),
            Some("safety review")
        );
    }

    #[test]
    fn submit_body_serializes() {
        let v = serde_json::to_value(SubmitDeliverable::new("agent_x", "https://github.com/me/repo"))
            .unwrap();
        assert_eq!(v["submitter_agent_id"], "agent_x");
        assert_eq!(v["proof"], "https://github.com/me/repo");
    }
}
