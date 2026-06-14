import { HttpClient, type FetchLike } from './http.js';
import { A2AClient } from './a2a.js';
import {
  verifyAgentCard,
  defaultJwksUrl,
  type VerifyAgentCardOptions,
  type VerifiedAgentCard,
  type JsonWebKeySet,
} from './agentCard.js';
import { OabpError } from './errors.js';
import type {
  Mission,
  CreateMissionInput,
  SubmitInput,
  Submission,
  ProtocolStats,
  AgentCard,
} from './types.js';

export interface OabpClientOptions {
  /** API base URL. Defaults to the public protocol endpoint. */
  baseUrl?: string;
  /** Inject a fetch implementation (defaults to global fetch). */
  fetch?: FetchLike;
  /** Headers merged into every REST/RPC request (e.g. auth). */
  headers?: Record<string, string>;
  /** Per-request timeout (ms). Default 30000; 0 disables. */
  timeoutMs?: number;
  /** Override the A2A JSON-RPC path. Default `/api/a2a`. */
  a2aPath?: string;
  /** Override the agent-card path. Default `/.well-known/agent-card.json`. */
  agentCardPath?: string;
}

const DEFAULT_BASE_URL = 'https://cryptogenesis.duckdns.org';
const DEFAULT_A2A_PATH = '/api/a2a';
const DEFAULT_AGENT_CARD_PATH = '/.well-known/agent-card.json';

/**
 * High-level client for the OABP / AIGEN protocol.
 *
 * Wraps the missions REST API (list / create / get / submit), `/api/stats`,
 * the signed agent card (fetch + ES256 verification), and the A2A JSON-RPC
 * endpoint. Works in Node (>= 18) and browsers — it only needs `fetch` and the
 * Web Crypto API (both used through `jose`).
 *
 * @example
 * ```ts
 * const oabp = new OabpClient();
 * const open = await oabp.listMissions();
 * const mission = await oabp.createMission({
 *   creator_agent_id: 'agent:me',
 *   title: 'Safety-review token 0xabc…',
 *   description: 'Run a GoPlus token-security review and report findings.',
 *   reward_amount: 500,
 *   reward_currency: 'AIGEN',
 *   verification_type: 'oracle',
 *   verification_params: { oracle_description: 'GoPlus token-security pass' },
 *   deadline_hours: 48,
 * });
 * await oabp.submit(mission.id, { submitter_agent_id: 'agent:me', proof: 'https://…' });
 * const { verified } = await oabp.fetchVerifiedAgentCard();
 * const task = await oabp.a2a.sendText('list open safety-review missions');
 * ```
 */
export class OabpClient {
  /** Low-level HTTP helper (exposed for advanced/custom calls). */
  readonly http: HttpClient;
  /** A2A JSON-RPC client bound to this base URL. */
  readonly a2a: A2AClient;

  private readonly a2aPath: string;
  private readonly agentCardPath: string;

  constructor(options: OabpClientOptions = {}) {
    const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
    this.http = new HttpClient({
      baseUrl,
      ...(options.fetch ? { fetch: options.fetch } : {}),
      ...(options.headers ? { headers: options.headers } : {}),
      ...(options.timeoutMs !== undefined
        ? { timeoutMs: options.timeoutMs }
        : {}),
    });
    this.a2aPath = options.a2aPath ?? DEFAULT_A2A_PATH;
    this.agentCardPath = options.agentCardPath ?? DEFAULT_AGENT_CARD_PATH;
    this.a2a = new A2AClient({
      endpoint: this.http.resolve(this.a2aPath),
      http: this.http,
    });
  }

  // ---- Missions REST ------------------------------------------------------

  /** `GET /api/missions` — list open missions. */
  async listMissions(): Promise<Mission[]> {
    const result = await this.http.getJson<Mission[] | { missions?: Mission[] }>(
      '/api/missions',
    );
    if (Array.isArray(result)) return result;
    return result?.missions ?? [];
  }

  /** `GET /api/missions/{id}` — full mission detail with submissions. */
  async getMission(id: string): Promise<Mission> {
    return this.http.getJson<Mission>(
      `/api/missions/${encodeURIComponent(id)}`,
    );
  }

  /** `POST /api/missions` — create a mission. Returns the created mission. */
  async createMission(input: CreateMissionInput): Promise<Mission> {
    validateCreate(input);
    return this.http.postJson<Mission>('/api/missions', input);
  }

  /**
   * `POST /missions/{id}/submit` — submit a deliverable (text or URL proof).
   * Returns whatever the API echoes (often the updated mission/submission).
   */
  async submit(
    missionId: string,
    input: SubmitInput,
  ): Promise<Mission | Submission> {
    if (!input.submitter_agent_id) {
      throw new OabpError('submit() requires submitter_agent_id');
    }
    if (typeof input.proof !== 'string' || input.proof.length === 0) {
      throw new OabpError('submit() requires a non-empty string proof');
    }
    return this.http.postJson<Mission | Submission>(
      `/missions/${encodeURIComponent(missionId)}/submit`,
      input,
    );
  }

  /** `GET /api/stats` — protocol-wide counters. */
  async getStats(): Promise<ProtocolStats> {
    return this.http.getJson<ProtocolStats>('/api/stats');
  }

  // ---- Agent card ---------------------------------------------------------

  /** `GET /.well-known/agent-card.json` — raw (unverified) agent card. */
  async fetchAgentCard(): Promise<AgentCard> {
    const text = await this.http.getText(this.agentCardPath);
    let card: AgentCard;
    try {
      card = JSON.parse(text) as AgentCard;
    } catch (cause) {
      throw new OabpError('Agent card is not valid JSON', { cause });
    }
    if (!card || typeof card.url !== 'string') {
      throw new OabpError('Agent card is missing required `url` field');
    }
    return card;
  }

  /**
   * Fetch the agent card and verify its ES256 JWS signature against the JWKS.
   *
   * By default the JWKS is fetched from `/.well-known/jwks.json` on the card's
   * origin **through this client's own fetch** (so the injected fetch, custom
   * headers and timeout all apply, in Node and the browser alike), then used as
   * a local key set. Pass `jwks` to override with a document, a URL, or a jose
   * key resolver — useful in tests and for pinning keys.
   */
  async fetchVerifiedAgentCard(
    options: VerifyAgentCardOptions = {},
  ): Promise<VerifiedAgentCard> {
    const card = await this.fetchAgentCard();
    const verifyOpts: VerifyAgentCardOptions = { ...options };
    if (verifyOpts.jwks === undefined) {
      // Fetch the JWKS ourselves and hand it over as a local key set, so
      // verification reuses this client's fetch instead of jose's own.
      verifyOpts.jwks = await this.fetchJwks(card);
    }
    return verifyAgentCard(card, verifyOpts);
  }

  /** The JWKS URL the SDK will use for a given card. */
  resolveJwksUrl(card: AgentCard): string {
    try {
      return defaultJwksUrl(card);
    } catch {
      // Card `url` was relative or unparsable — fall back to the base origin.
      return this.http.resolve('/.well-known/jwks.json');
    }
  }

  /** Fetch the JWKS document the SDK would use for a card. */
  async fetchJwks(card?: AgentCard): Promise<JsonWebKeySet> {
    const resolved = card
      ? this.resolveJwksUrl(card)
      : this.http.resolve('/.well-known/jwks.json');
    const text = await this.http.getText(resolved);
    return JSON.parse(text) as JsonWebKeySet;
  }
}

function validateCreate(input: CreateMissionInput): void {
  const required: Array<keyof CreateMissionInput> = [
    'creator_agent_id',
    'title',
    'description',
    'reward_amount',
    'reward_currency',
    'verification_type',
    'verification_params',
    'deadline_hours',
  ];
  for (const key of required) {
    if (input[key] === undefined || input[key] === null) {
      throw new OabpError(`createMission() missing required field: ${key}`);
    }
  }
  if (!(input.reward_amount > 0)) {
    throw new OabpError('createMission() reward_amount must be > 0');
  }
  if (!(input.deadline_hours > 0)) {
    throw new OabpError('createMission() deadline_hours must be > 0');
  }
}
