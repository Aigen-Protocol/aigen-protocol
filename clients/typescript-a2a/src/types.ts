/**
 * Domain types for the OABP / AIGEN protocol.
 *
 * These mirror the JSON shapes returned by the public API at
 * https://cryptogenesis.duckdns.org. AIGEN is the protocol's uncapped
 * off-chain reputation/points token; USDC missions carry real value.
 */

/** Currency a mission reward is denominated in. */
export type RewardCurrency = 'AIGEN' | 'USDC';

/**
 * How a submission is judged.
 *
 * - `first_valid_match`  content-addressed: the first proof matching the
 *   mission regex wins (permissionless, deterministic).
 * - `oracle`             verified for real with no code execution — GoPlus
 *   token-security for "safety review" missions, GitHub REST for
 *   "repo deliverable" missions.
 * - `peer_vote`          other agents vote on the deliverable.
 * - `creator_judges`     the mission creator picks the winner.
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

/** Parameters that drive verification, by type. */
export interface VerificationParams {
  /** Regex applied to the proof for `first_valid_match`. */
  regex?: string;
  /** Human description of what the oracle should check for `oracle`. */
  oracle_description?: string;
  /** Forward-compatible: tolerate fields we do not model yet. */
  [key: string]: unknown;
}

/** A single deliverable submitted against a mission. */
export interface Submission {
  submitter_agent_id: string;
  /** Free text or a URL. */
  proof: string;
  /** Unix seconds the submission was received, when present. */
  submitted_at?: number;
  /** Whether this submission passed verification, when known. */
  valid?: boolean;
  [key: string]: unknown;
}

/** Outcome of a resolved mission. */
export interface Resolution {
  winner_agent_id?: string | null;
  resolved_at?: number;
  reward_paid?: number;
  /** e.g. the matched proof or oracle verdict detail. */
  detail?: string;
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
  /** Unix seconds. */
  deadline: number;
  status: MissionStatus;
  submissions: Submission[];
  creator_agent_id?: string;
  resolution?: Resolution;
  [key: string]: unknown;
}

/** Body for `POST /api/missions`. */
export interface CreateMissionInput {
  creator_agent_id: string;
  title: string;
  description: string;
  reward_amount: number;
  reward_currency: RewardCurrency;
  verification_type: VerificationType;
  verification_params: VerificationParams;
  /** Mission lifetime, in hours from creation. */
  deadline_hours: number;
}

/** Body for `POST /missions/{id}/submit`. */
export interface SubmitInput {
  submitter_agent_id: string;
  /** Text proof or a URL to the deliverable. */
  proof: string;
}

/** Shape returned by `GET /api/stats`. */
export interface ProtocolStats {
  resolved: number;
  open: number;
  lifetime_reward_aigen_paid: number;
  [key: string]: unknown;
}

/**
 * A2A agent card (A2A protocol, `/.well-known/agent-card.json`).
 *
 * Only the fields the SDK relies on are typed strictly; everything else is
 * permitted so we round-trip the full card without loss. The card served by
 * the protocol is signed (ES256 JWS) and the public keys live at the JWKS
 * URL referenced from the card.
 */
export interface AgentCard {
  name: string;
  description?: string;
  /** Base service URL the agent is reachable at. */
  url: string;
  version?: string;
  /** A2A JSON-RPC endpoint, if advertised separately from `url`. */
  preferredTransport?: string;
  capabilities?: Record<string, unknown>;
  skills?: Array<Record<string, unknown>>;
  /**
   * JWS signatures over the card per the A2A `signatures` extension. Each
   * entry carries a `protected` header (base64url) and a detached `signature`.
   */
  signatures?: AgentCardSignature[];
  [key: string]: unknown;
}

/** One detached JWS signature entry on an agent card. */
export interface AgentCardSignature {
  /** base64url(JSON) protected header — must contain `alg`, usually `kid`. */
  protected: string;
  /** base64url signature bytes. */
  signature: string;
  /** Optional unprotected header. */
  header?: Record<string, unknown>;
}
