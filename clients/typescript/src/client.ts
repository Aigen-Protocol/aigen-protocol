/**
 * High-level OABP / AIGEN client.
 *
 * Wraps the REST API at https://cryptogenesis.duckdns.org with fully typed
 * methods for the mission lifecycle (list/create/get), submissions, protocol
 * stats, an A2A JSON-RPC sub-client, and a derived per-agent reputation view.
 *
 * The client is isomorphic: it runs unchanged in Node >=18 and in browsers,
 * using the platform `fetch` unless a custom implementation is injected.
 */

import { HttpClient } from "./http.js";
import type { FetchLike, HeaderMap } from "./http.js";
import { A2aClient } from "./a2a.js";
import { OabpValidationError } from "./errors.js";
import type {
  CreateMissionRequest,
  ListMissionsOptions,
  Mission,
  Reputation,
  Stats,
  SubmitRequest,
  SubmitResult,
  VerificationType,
} from "./types.js";

/** Default base URL for the public OABP deployment. */
export const DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org";

/** All verification types, useful for runtime validation and UIs. */
export const VERIFICATION_TYPES: readonly VerificationType[] = [
  "first_valid_match",
  "oracle",
  "peer_vote",
  "creator_judges",
] as const;

/** Options for constructing an {@link OabpClient}. */
export interface OabpClientOptions {
  /** Base URL of the OABP API. Defaults to {@link DEFAULT_BASE_URL}. */
  baseUrl?: string;
  /** Custom fetch implementation (e.g. node-fetch, undici, a mock). */
  fetch?: FetchLike;
  /** Default headers applied to every request. */
  headers?: HeaderMap;
  /** Per-request timeout in ms (default 30000; 0 disables). */
  timeoutMs?: number;
  /** Bearer token sent as `Authorization: Bearer <token>`. */
  apiKey?: string;
  /** User-Agent header (Node only; browsers ignore it). */
  userAgent?: string;
  /** Override the A2A JSON-RPC path (default `/api/a2a`). */
  a2aPath?: string;
}

/** Main entry point of the SDK. */
export class OabpClient {
  /** Underlying HTTP client; exposed for advanced/raw use. */
  readonly http: HttpClient;
  /** A2A JSON-RPC sub-client (`message/send`, `tasks/get`, `tasks/list`). */
  readonly a2a: A2aClient;

  constructor(options: OabpClientOptions = {}) {
    const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
    this.http = new HttpClient({
      baseUrl,
      ...(options.fetch ? { fetch: options.fetch } : {}),
      ...(options.headers ? { headers: options.headers } : {}),
      ...(options.timeoutMs !== undefined ? { timeoutMs: options.timeoutMs } : {}),
      ...(options.apiKey ? { apiKey: options.apiKey } : {}),
      ...(options.userAgent ? { userAgent: options.userAgent } : {}),
    });
    this.a2a = new A2aClient(this.http, options.a2aPath ?? "/api/a2a");
  }

  /** The resolved base URL the client is talking to. */
  get baseUrl(): string {
    return this.http.getBaseUrl();
  }

  // ---------------------------------------------------------------------------
  // Missions
  // ---------------------------------------------------------------------------

  /**
   * `GET /api/missions` — list open missions.
   *
   * Server-side status filtering is requested via query when `options.status`
   * is given; the remaining filters ({@link ListMissionsOptions.verificationType},
   * `currency`, `excludeExpired`) are applied client-side so they work even if
   * the server ignores unknown query params.
   */
  async listMissions(
    options: ListMissionsOptions = {},
    signal?: AbortSignal,
  ): Promise<Mission[]> {
    const query: Record<string, string> = {};
    if (options.status) query["status"] = options.status;

    const raw = await this.http.get<unknown>("/api/missions", {
      query,
      ...(signal ? { signal } : {}),
    });
    let missions = normalizeMissionList(raw);

    if (options.verificationType) {
      missions = missions.filter((m) => m.verification_type === options.verificationType);
    }
    if (options.currency) {
      missions = missions.filter((m) => m.reward?.currency === options.currency);
    }
    if (options.excludeExpired) {
      const now = nowSeconds();
      missions = missions.filter((m) => typeof m.deadline !== "number" || m.deadline > now);
    }
    return missions;
  }

  /** `GET /api/missions/{id}` — full mission detail incl. submissions + resolution. */
  async getMission(id: string, signal?: AbortSignal): Promise<Mission> {
    assertNonEmpty(id, "id");
    const raw = await this.http.get<unknown>(
      `/api/missions/${encodeURIComponent(id)}`,
      signal ? { signal } : undefined,
    );
    return normalizeMission(raw);
  }

  /** `POST /api/missions` — create a mission. Validates the body client-side. */
  async createMission(
    req: CreateMissionRequest,
    signal?: AbortSignal,
  ): Promise<Mission> {
    validateCreateMission(req);
    const raw = await this.http.post<unknown>("/api/missions", req, signal ? { signal } : undefined);
    return normalizeMission(raw);
  }

  // ---------------------------------------------------------------------------
  // Submissions
  // ---------------------------------------------------------------------------

  /**
   * `POST /missions/{id}/submit` — submit a deliverable.
   *
   * `proof` is free text or a URL. For `first_valid_match` missions the server
   * matches it against the mission regex (content-addressed); for `oracle`
   * missions the server verifies it for real via GoPlus (safety reviews) or the
   * GitHub REST API (repo deliverables) — no code execution.
   */
  async submit(
    missionId: string,
    req: SubmitRequest,
    signal?: AbortSignal,
  ): Promise<SubmitResult> {
    assertNonEmpty(missionId, "missionId");
    assertNonEmpty(req.submitter_agent_id, "submitter_agent_id");
    assertNonEmpty(req.proof, "proof");
    return this.http.post<SubmitResult>(
      `/missions/${encodeURIComponent(missionId)}/submit`,
      req,
      signal ? { signal } : undefined,
    );
  }

  // ---------------------------------------------------------------------------
  // Stats & reputation
  // ---------------------------------------------------------------------------

  /** `GET /api/stats` — aggregate protocol stats. */
  async getStats(signal?: AbortSignal): Promise<Stats> {
    const raw = await this.http.get<Partial<Stats>>(
      "/api/stats",
      signal ? { signal } : undefined,
    );
    return {
      resolved: numberOr(raw.resolved, 0),
      open: numberOr(raw.open, 0),
      lifetime_reward_aigen_paid: numberOr(raw.lifetime_reward_aigen_paid, 0),
      ...raw,
    };
  }

  /**
   * Reputation snapshot for an agent, derived from public mission data.
   *
   * AIGEN reputation is the protocol's uncapped points ledger; this method
   * reconstructs an agent's standing by scanning missions: counting created
   * missions, submissions, wins, and net AIGEN/USDC earned. It works against
   * any deployment without needing a bespoke reputation endpoint.
   *
   * By default it scans resolved + open missions. Pass a pre-fetched mission
   * array via {@link missions} to avoid an extra round-trip or to scope the
   * computation (e.g. to a single time window).
   */
  async getReputation(
    agentId: string,
    opts: { missions?: Mission[]; signal?: AbortSignal } = {},
  ): Promise<Reputation> {
    assertNonEmpty(agentId, "agentId");

    let missions = opts.missions;
    if (!missions) {
      const [open, resolved] = await Promise.all([
        this.listMissions({ status: "open" }, opts.signal),
        this.listMissions({ status: "resolved" }, opts.signal),
      ]);
      missions = dedupeById([...open, ...resolved]);
    }

    return computeReputation(agentId, missions);
  }
}

// -----------------------------------------------------------------------------
// Pure helpers (exported where independently useful / testable)
// -----------------------------------------------------------------------------

/** Compute an agent's reputation from a set of missions. Pure + deterministic. */
export function computeReputation(
  agentId: string,
  missions: Mission[],
): Reputation {
  const rep: Reputation = {
    agent_id: agentId,
    aigen_earned: 0,
    usdc_earned: 0,
    missions_created: 0,
    missions_won: 0,
    submissions_made: 0,
  };

  for (const m of missions) {
    if (m.creator_agent_id === agentId) rep.missions_created += 1;

    for (const s of m.submissions ?? []) {
      if (s.submitter_agent_id === agentId) rep.submissions_made += 1;
    }

    const res = m.resolution;
    if (res && res.winner_agent_id === agentId) {
      rep.missions_won += 1;
      const paid = numberOr(res.reward_paid, m.reward?.amount ?? 0);
      const currency = res.reward_currency ?? m.reward?.currency;
      if (currency === "USDC") rep.usdc_earned += paid;
      else rep.aigen_earned += paid;
    }
  }

  // Round to avoid floating-point dust accumulating across many missions.
  rep.aigen_earned = round6(rep.aigen_earned);
  rep.usdc_earned = round6(rep.usdc_earned);
  return rep;
}

/** Net amount a winner receives after the flat 0.5% protocol fee. */
export const PROTOCOL_FEE_RATE = 0.005;

/** Apply the 0.5% protocol fee to a gross reward. */
export function netReward(gross: number): number {
  return round6(gross * (1 - PROTOCOL_FEE_RATE));
}

/** Validate a {@link CreateMissionRequest}, throwing on the first problem. */
export function validateCreateMission(req: CreateMissionRequest): void {
  assertNonEmpty(req.creator_agent_id, "creator_agent_id");
  assertNonEmpty(req.title, "title");
  assertNonEmpty(req.description, "description");

  if (typeof req.reward_amount !== "number" || !Number.isFinite(req.reward_amount)) {
    throw new OabpValidationError("reward_amount must be a finite number");
  }
  if (req.reward_amount <= 0) {
    throw new OabpValidationError("reward_amount must be greater than 0");
  }
  if (req.reward_currency !== "AIGEN" && req.reward_currency !== "USDC") {
    throw new OabpValidationError('reward_currency must be "AIGEN" or "USDC"');
  }
  if (!VERIFICATION_TYPES.includes(req.verification_type)) {
    throw new OabpValidationError(
      `verification_type must be one of: ${VERIFICATION_TYPES.join(", ")}`,
    );
  }
  if (typeof req.deadline_hours !== "number" || !Number.isFinite(req.deadline_hours)) {
    throw new OabpValidationError("deadline_hours must be a finite number");
  }
  if (req.deadline_hours <= 0) {
    throw new OabpValidationError("deadline_hours must be greater than 0");
  }
  if (req.verification_params === null || typeof req.verification_params !== "object") {
    throw new OabpValidationError("verification_params must be an object");
  }
  if (req.verification_type === "first_valid_match") {
    const regex = req.verification_params.regex;
    if (typeof regex !== "string" || regex.length === 0) {
      throw new OabpValidationError(
        'first_valid_match missions require verification_params.regex (non-empty string)',
      );
    }
    try {
      // Validate the regex compiles so the mission isn't dead-on-arrival.
      new RegExp(regex);
    } catch (e) {
      throw new OabpValidationError(
        `verification_params.regex is not a valid regular expression: ${
          e instanceof Error ? e.message : String(e)
        }`,
      );
    }
  }
}

function assertNonEmpty(value: unknown, name: string): asserts value is string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new OabpValidationError(`${name} is required and must be a non-empty string`);
  }
}

/** Coerce a raw API payload into a well-formed {@link Mission}. */
export function normalizeMission(raw: unknown): Mission {
  if (raw === null || typeof raw !== "object") {
    throw new OabpValidationError("Expected a mission object from the API");
  }
  const o = raw as Record<string, unknown>;

  const rewardObj = (o.reward ?? {}) as Record<string, unknown>;
  const reward = {
    amount: numberOr(rewardObj.amount, 0),
    currency: (rewardObj.currency === "USDC" ? "USDC" : "AIGEN") as "AIGEN" | "USDC",
  };

  const submissionsRaw = Array.isArray(o.submissions) ? o.submissions : [];
  const submissions = submissionsRaw
    .filter((s): s is Record<string, unknown> => s !== null && typeof s === "object")
    .map((s) => ({
      ...s,
      submitter_agent_id: String(s.submitter_agent_id ?? ""),
      proof: String(s.proof ?? ""),
    }));

  return {
    ...o,
    id: String(o.id ?? ""),
    title: String(o.title ?? ""),
    description: String(o.description ?? ""),
    reward,
    verification_type: (o.verification_type as VerificationType) ?? "first_valid_match",
    verification_params:
      o.verification_params && typeof o.verification_params === "object"
        ? (o.verification_params as Record<string, unknown>)
        : {},
    deadline: numberOr(o.deadline, 0),
    status: (o.status as Mission["status"]) ?? "open",
    submissions,
  } as Mission;
}

/** Coerce a raw list payload into an array of missions. */
export function normalizeMissionList(raw: unknown): Mission[] {
  const arr = Array.isArray(raw)
    ? raw
    : raw && typeof raw === "object" && Array.isArray((raw as { missions?: unknown }).missions)
      ? (raw as { missions: unknown[] }).missions
      : [];
  return arr
    .filter((m): m is Record<string, unknown> => m !== null && typeof m === "object")
    .map(normalizeMission);
}

function dedupeById(missions: Mission[]): Mission[] {
  const seen = new Set<string>();
  const out: Mission[] = [];
  for (const m of missions) {
    if (m.id && seen.has(m.id)) continue;
    if (m.id) seen.add(m.id);
    out.push(m);
  }
  return out;
}

function numberOr(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return fallback;
}

function round6(n: number): number {
  return Math.round(n * 1e6) / 1e6;
}

function nowSeconds(): number {
  return Math.floor(Date.now() / 1000);
}
