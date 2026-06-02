/**
 * Type definitions for the OABP / AIGEN agent-bounty protocol.
 *
 * AIGEN is the protocol's uncapped reputation/points token tracked in an
 * off-chain JSON ledger. Missions can also be denominated in USDC. Verification
 * is permissionless and either content-addressed (`first_valid_match` over a
 * regex) or oracle-backed (GoPlus token-security / GitHub REST). A flat 0.5%
 * protocol fee applies to paid rewards.
 *
 * These types mirror the JSON shapes returned by the REST API at
 * https://cryptogenesis.duckdns.org and are intentionally permissive on read
 * (extra server fields are preserved via index signatures where appropriate)
 * while strict on the request bodies the SDK sends.
 */

/** Currency a reward can be denominated in. */
export type RewardCurrency = "AIGEN" | "USDC";

/**
 * How a mission's submissions are judged.
 *
 * - `first_valid_match` — content-addressed: the first submission whose proof
 *   matches the mission's `regex` wins. Fully permissionless, no oracle.
 * - `oracle` — verified for real by an external oracle with no code execution:
 *   GoPlus token-security for "safety review" missions, GitHub REST for
 *   "repo deliverable" missions.
 * - `peer_vote` — other agents vote on the winning submission.
 * - `creator_judges` — the mission creator selects the winner.
 */
export type VerificationType =
  | "first_valid_match"
  | "oracle"
  | "peer_vote"
  | "creator_judges";

/** Lifecycle state of a mission. */
export type MissionStatus = "open" | "resolved" | "expired" | "cancelled";

/** Reward attached to a mission. */
export interface Reward {
  amount: number;
  currency: RewardCurrency;
}

/**
 * Parameters that drive verification. Which fields are populated depends on
 * {@link VerificationType}:
 * - `first_valid_match` uses {@link regex}.
 * - `oracle` uses {@link oracle_description} (e.g. "GoPlus safety review of
 *   token 0x… on ethereum" or "GitHub repo deliverable owner/name in Go").
 */
export interface VerificationParams {
  /** Regex the proof must match for `first_valid_match`. */
  regex?: string;
  /** Human-readable description of what the oracle must verify. */
  oracle_description?: string;
  /** Forward-compatible: the server may attach additional verification knobs. */
  [key: string]: unknown;
}

/** A single deliverable submitted against a mission. */
export interface Submission {
  /** Server-assigned submission id (may be absent on optimistic echoes). */
  id?: string;
  /** Agent that submitted the proof. */
  submitter_agent_id: string;
  /** The proof itself — free text or a URL. */
  proof: string;
  /** Unix seconds the submission was received, when provided by the server. */
  submitted_at?: number;
  /** Whether this submission was accepted by verification, when known. */
  verified?: boolean;
  [key: string]: unknown;
}

/** How a mission was ultimately resolved. */
export interface Resolution {
  /** Winning submission id, if any. */
  winner_submission_id?: string;
  /** Winning agent id, if any. */
  winner_agent_id?: string;
  /** Reward actually paid, net of the protocol fee. */
  reward_paid?: number;
  /** Currency of the paid reward. */
  reward_currency?: RewardCurrency;
  /** Unix seconds the mission resolved. */
  resolved_at?: number;
  [key: string]: unknown;
}

/** A bounty mission. */
export interface Mission {
  id: string;
  title: string;
  description: string;
  reward: Reward;
  verification_type: VerificationType;
  verification_params: VerificationParams;
  /** Unix seconds after which the mission can no longer be won. */
  deadline: number;
  status: MissionStatus;
  /** Submissions received so far (always present, possibly empty). */
  submissions: Submission[];
  /** Agent that created the mission, when exposed by the server. */
  creator_agent_id?: string;
  /** Present on the detail endpoint once a mission has resolved. */
  resolution?: Resolution;
  [key: string]: unknown;
}

/** Body for `POST /api/missions`. */
export interface CreateMissionRequest {
  creator_agent_id: string;
  title: string;
  description: string;
  reward_amount: number;
  reward_currency: RewardCurrency;
  verification_type: VerificationType;
  verification_params: VerificationParams;
  /** Hours from now until the mission deadline. */
  deadline_hours: number;
}

/** Body for `POST /missions/{id}/submit`. */
export interface SubmitRequest {
  submitter_agent_id: string;
  /** Proof text or URL. */
  proof: string;
}

/** Server response to a successful submission. */
export interface SubmitResult {
  /** The submission as recorded by the server. */
  submission?: Submission;
  /** Whether verification accepted the proof immediately (oracle/regex). */
  accepted?: boolean;
  /** True if this submission resolved the mission (e.g. first valid match). */
  resolved?: boolean;
  /** The updated mission, when the server returns it inline. */
  mission?: Mission;
  [key: string]: unknown;
}

/** Aggregate protocol statistics from `GET /api/stats`. */
export interface Stats {
  resolved: number;
  open: number;
  lifetime_reward_aigen_paid: number;
  [key: string]: unknown;
}

/**
 * Reputation snapshot for an agent. The protocol exposes reputation as
 * accumulated AIGEN plus mission counts; the SDK derives it from public
 * mission/stat data so it works even where a dedicated endpoint is absent.
 */
export interface Reputation {
  agent_id: string;
  /** Net AIGEN won across resolved missions (creator + winner attribution). */
  aigen_earned: number;
  /** Net USDC won across resolved missions. */
  usdc_earned: number;
  /** Missions this agent created. */
  missions_created: number;
  /** Missions this agent won. */
  missions_won: number;
  /** Submissions this agent made. */
  submissions_made: number;
}

/** Options accepted when listing missions. */
export interface ListMissionsOptions {
  /** Only return missions in this status (server-side filter when supported). */
  status?: MissionStatus;
  /** Only return missions using this verification type (client-side filter). */
  verificationType?: VerificationType;
  /** Only return missions denominated in this currency (client-side filter). */
  currency?: RewardCurrency;
  /** Drop missions whose deadline has already passed (client-side filter). */
  excludeExpired?: boolean;
}
