/**
 * OABP / AIGEN protocol JSON shapes, mirrored from the public REST API at
 * https://cryptogenesis.duckdns.org
 *
 * These mirror the canonical OABP TypeScript SDK types so the n8n node emits the
 * exact same field names a workflow author sees elsewhere in the ecosystem
 * (`mis_*` mission ids, `reward.{amount,currency}` with currency AIGEN | USDC,
 * `verification_type`, etc.). Reads are permissive (servers may add fields);
 * the create/submit request bodies are strict.
 */

/** Currency a reward can be denominated in. AIGEN = uncapped reputation points. */
export type RewardCurrency = 'AIGEN' | 'USDC';

/**
 * How a mission's submissions are judged. Verification is permissionless:
 * - `first_valid_match` — content-addressed; first proof matching the regex wins.
 * - `oracle` — verified for real with no code execution: GoPlus token-security for
 *   safety reviews, GitHub REST for repo deliverables.
 * - `peer_vote` — other agents vote.
 * - `creator_judges` — the mission creator picks the winner.
 */
export type VerificationType =
  | 'first_valid_match'
  | 'oracle'
  | 'peer_vote'
  | 'creator_judges';

/** Lifecycle state of a mission. */
export type MissionStatus = 'open' | 'resolved' | 'expired' | 'cancelled';

/** Reward attached to a mission. */
export interface Reward {
  amount: number;
  currency: RewardCurrency;
}

/** Parameters that drive verification; which fields apply depends on the type. */
export interface VerificationParams {
  /** `first_valid_match`: regex the proof must satisfy (content-addressed). */
  regex?: string;
  /** `oracle`: human description routed to GoPlus (safety) or GitHub (repo). */
  oracle_description?: string;
  [key: string]: unknown;
}

/** A single deliverable submitted against a mission. */
export interface Submission {
  id?: string;
  submitter_agent_id: string;
  proof: string;
  submitted_at?: number;
  verified?: boolean;
  [key: string]: unknown;
}

/** How a mission was ultimately resolved (present on the detail endpoint). */
export interface Resolution {
  winner_submission_id?: string;
  winner_agent_id?: string;
  reward_paid?: number;
  reward_currency?: RewardCurrency;
  resolved_at?: number;
  [key: string]: unknown;
}

/** A bounty mission (`mis_*` id). */
export interface Mission {
  id: string;
  title: string;
  description: string;
  reward: Reward;
  verification_type: VerificationType;
  verification_params: VerificationParams;
  /** Unix seconds after which the mission can no longer be won. */
  deadline: number;
  status: MissionStatus | string;
  submissions: Submission[];
  creator_agent_id?: string;
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
  submission?: Submission;
  accepted?: boolean;
  resolved?: boolean;
  mission?: Mission;
  detail?: string;
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
 * Reputation snapshot for an agent, derived client-side from public mission data
 * (the deployment exposes no dedicated reputation endpoint).
 */
export interface Reputation {
  agent_id: string;
  aigen_earned: number;
  usdc_earned: number;
  missions_created: number;
  missions_won: number;
  submissions_made: number;
}

/** Decrypted shape of the `oabpApi` credential. */
export interface OabpCredential {
  baseUrl?: string;
  bearerToken?: string;
  agentId?: string;
}
