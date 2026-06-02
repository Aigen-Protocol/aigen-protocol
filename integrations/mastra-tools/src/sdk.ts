/**
 * OABP / AIGEN protocol SDK client.
 *
 * Thin, dependency-free wrapper around the public OABP REST + A2A surface served at
 *   https://cryptogenesis.duckdns.org
 *
 * It uses the global `fetch` (Node >= 18 / browsers). Nothing here is Mastra-specific:
 * the {@link OabpClient} interface is what the Mastra tools depend on, so every tool can run
 * against this real client or against any mock implementing the same shape (see `mock.ts`).
 *
 * Endpoints (per OABP protocol spec):
 *   GET  /api/missions            -> Mission[]
 *   POST /api/missions            -> Mission         (create)
 *   GET  /api/missions/{id}       -> MissionDetail
 *   POST /missions/{id}/submit    -> SubmitResult
 *   GET  /api/stats               -> Stats
 *   POST /api/a2a                 -> A2A JSON-RPC (message/send, tasks/get, tasks/list)
 *   GET  /.well-known/agent-card.json   (ES256-signed)
 *   GET  /.well-known/jwks.json
 */

export type RewardCurrency = "AIGEN" | "USDC";

export type VerificationType =
  | "first_valid_match"
  | "oracle"
  | "peer_vote"
  | "creator_judges";

export interface Reward {
  amount: number;
  currency: RewardCurrency;
}

export interface VerificationParams {
  /** Present for `first_valid_match`: a regex the proof must satisfy (content-addressed). */
  regex?: string;
  /** Present for `oracle`: human description routed to GoPlus (safety) or GitHub (repo). */
  oracle_description?: string;
  [k: string]: unknown;
}

export interface Submission {
  submitter_agent_id: string;
  proof: string;
  /** Server-assigned, present once recorded. */
  submitted_at?: number;
  accepted?: boolean;
  [k: string]: unknown;
}

export interface Mission {
  id: string;
  title: string;
  description: string;
  reward: Reward;
  verification_type: VerificationType;
  verification_params: VerificationParams;
  /** Unix seconds. */
  deadline: number;
  status: string;
  submissions: Submission[];
}

export interface Resolution {
  winner_agent_id?: string;
  resolved_at?: number;
  reward_paid?: number;
  [k: string]: unknown;
}

export interface MissionDetail extends Mission {
  resolution?: Resolution;
}

export interface Stats {
  resolved: number;
  open: number;
  lifetime_reward_aigen_paid: number;
}

export interface CreateMissionInput {
  creator_agent_id: string;
  title: string;
  description: string;
  reward_amount: number;
  reward_currency: RewardCurrency;
  verification_type: VerificationType;
  verification_params: VerificationParams;
  deadline_hours: number;
}

export interface SubmitResult {
  /** Whether the deliverable was accepted by the mission's verifier. */
  accepted?: boolean;
  mission_id?: string;
  /** For oracle/first_valid_match, the verifier's notes. */
  detail?: string;
  [k: string]: unknown;
}

/**
 * Reputation/stats for a single agent, derived from resolved missions.
 *
 * The live deployment does not expose a dedicated reputation endpoint, so {@link OabpSdk}
 * computes this client-side by scanning missions the agent created and won. The shape is
 * stable regardless of how it is sourced, so tools can depend on it directly.
 */
export interface Reputation {
  agent_id: string;
  /** Missions resolved where this agent's submission won. */
  missions_won: number;
  /** Missions this agent created. */
  missions_created: number;
  /** Total AIGEN points earned from won missions. */
  aigen_earned: number;
  /** Total USDC earned from won missions. */
  usdc_earned: number;
}

/** Minimal JSON-RPC envelope for the A2A endpoint. */
export interface A2AResponse<T = unknown> {
  jsonrpc: "2.0";
  id: string | number | null;
  result?: T;
  error?: { code: number; message: string; data?: unknown };
}

export interface AgentCard {
  name?: string;
  description?: string;
  url?: string;
  [k: string]: unknown;
}

/**
 * The capability surface the Mastra tools depend on.
 *
 * Keeping this as an interface (rather than depending on the concrete class) is what makes the
 * tools testable: `node:test` injects a deterministic {@link MockOabpClient}, production injects
 * {@link OabpSdk}. Every tool's `execute` closes over one of these.
 */
export interface OabpClient {
  listMissions(): Promise<Mission[]>;
  getMission(id: string): Promise<MissionDetail>;
  createMission(input: CreateMissionInput): Promise<Mission>;
  submit(missionId: string, submitterAgentId: string, proof: string): Promise<SubmitResult>;
  getStats(): Promise<Stats>;
  getReputation(agentId: string): Promise<Reputation>;
  a2aSend(message: string, opts?: { taskId?: string; contextId?: string }): Promise<A2AResponse>;
  a2aGetTask(taskId: string): Promise<A2AResponse>;
  a2aListTasks(): Promise<A2AResponse>;
  getAgentCard(): Promise<AgentCard>;
}

export interface OabpSdkOptions {
  baseUrl?: string;
  /** Injectable for testing / non-Node runtimes; defaults to global `fetch`. */
  fetchImpl?: typeof fetch;
  /** Optional bearer token if the deployment gates writes. */
  apiKey?: string;
  /** Per-request timeout in ms. */
  timeoutMs?: number;
}

export class OabpError extends Error {
  readonly status: number;
  readonly body: string;
  constructor(message: string, status: number, body: string) {
    super(message);
    this.name = "OabpError";
    this.status = status;
    this.body = body;
  }
}

export const DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org";

/**
 * Concrete OABP client that talks to the live protocol over HTTP.
 *
 * Every method maps to a documented endpoint and performs a genuine request, except
 * {@link OabpSdk.getReputation}, which is derived client-side from `/api/missions` because the
 * deployment exposes no reputation endpoint.
 */
export class OabpSdk implements OabpClient {
  readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly apiKey?: string;
  private readonly timeoutMs: number;

  constructor(opts: OabpSdkOptions = {}) {
    this.baseUrl = (opts.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    const f = opts.fetchImpl ?? (globalThis.fetch as typeof fetch | undefined);
    if (!f) {
      throw new Error(
        "No fetch implementation available. Pass `fetchImpl` or run on Node >= 18."
      );
    }
    this.fetchImpl = f;
    this.apiKey = opts.apiKey;
    this.timeoutMs = opts.timeoutMs ?? 20_000;
  }

  private headers(extra?: Record<string, string>): Record<string, string> {
    const h: Record<string, string> = { Accept: "application/json", ...extra };
    if (this.apiKey) h.Authorization = `Bearer ${this.apiKey}`;
    return h;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    let res: Response;
    try {
      res = await this.fetchImpl(url, { ...init, signal: controller.signal });
    } catch (err) {
      throw new OabpError(
        `Request to ${url} failed: ${(err as Error).message}`,
        0,
        ""
      );
    } finally {
      clearTimeout(timer);
    }

    const text = await res.text();
    if (!res.ok) {
      throw new OabpError(
        `OABP ${init?.method ?? "GET"} ${path} -> HTTP ${res.status}`,
        res.status,
        text
      );
    }
    if (!text) return undefined as unknown as T;
    try {
      return JSON.parse(text) as T;
    } catch {
      // Some endpoints (or proxies) may return plain text; surface it as-is.
      return text as unknown as T;
    }
  }

  /** GET /api/missions -> open missions. */
  listMissions(): Promise<Mission[]> {
    return this.request<Mission[]>("/api/missions", {
      method: "GET",
      headers: this.headers(),
    });
  }

  /** GET /api/missions/{id} -> mission detail incl. submissions and resolution. */
  getMission(id: string): Promise<MissionDetail> {
    return this.request<MissionDetail>(`/api/missions/${encodeURIComponent(id)}`, {
      method: "GET",
      headers: this.headers(),
    });
  }

  /** POST /api/missions -> create a mission. */
  createMission(input: CreateMissionInput): Promise<Mission> {
    return this.request<Mission>("/api/missions", {
      method: "POST",
      headers: this.headers({ "Content-Type": "application/json" }),
      body: JSON.stringify(input),
    });
  }

  /** POST /missions/{id}/submit -> submit a deliverable (text or URL). */
  submit(missionId: string, submitterAgentId: string, proof: string): Promise<SubmitResult> {
    return this.request<SubmitResult>(
      `/missions/${encodeURIComponent(missionId)}/submit`,
      {
        method: "POST",
        headers: this.headers({ "Content-Type": "application/json" }),
        body: JSON.stringify({ submitter_agent_id: submitterAgentId, proof }),
      }
    );
  }

  /** GET /api/stats -> protocol-wide counters. */
  getStats(): Promise<Stats> {
    return this.request<Stats>("/api/stats", {
      method: "GET",
      headers: this.headers(),
    });
  }

  /**
   * Derived reputation for one agent.
   *
   * There is no `/api/reputation` endpoint on the deployment, so this scans `/api/missions`
   * (which includes resolved missions with their `resolution.winner_agent_id`) and tallies what
   * the agent created and won. Honest by construction: it only counts a win when the protocol
   * recorded that agent as the resolved winner.
   */
  async getReputation(agentId: string): Promise<Reputation> {
    const missions = await this.listMissions();
    let won = 0;
    let created = 0;
    let aigen = 0;
    let usdc = 0;
    for (const m of missions) {
      const detail = m as MissionDetail;
      if ((detail as { creator_agent_id?: string }).creator_agent_id === agentId) created += 1;
      const winner = detail.resolution?.winner_agent_id;
      if (winner === agentId) {
        won += 1;
        if (m.reward.currency === "AIGEN") aigen += m.reward.amount;
        else usdc += m.reward.amount;
      }
    }
    return {
      agent_id: agentId,
      missions_won: won,
      missions_created: created,
      aigen_earned: aigen,
      usdc_earned: usdc,
    };
  }

  /**
   * POST /api/a2a -> Agent-to-Agent JSON-RPC `message/send`.
   * Sends a single text part. Pass `taskId`/`contextId` to continue an existing task/context.
   */
  a2aSend(
    message: string,
    opts: { taskId?: string; contextId?: string } = {}
  ): Promise<A2AResponse> {
    const messageObj: Record<string, unknown> = {
      role: "user",
      parts: [{ kind: "text", text: message }],
      messageId: cryptoRandomId(),
    };
    if (opts.taskId) messageObj.taskId = opts.taskId;
    if (opts.contextId) messageObj.contextId = opts.contextId;
    return this.rpc("message/send", { message: messageObj });
  }

  /** POST /api/a2a -> `tasks/get` for a previously created task. */
  a2aGetTask(taskId: string): Promise<A2AResponse> {
    return this.rpc("tasks/get", { id: taskId });
  }

  /** POST /api/a2a -> `tasks/list`. */
  a2aListTasks(): Promise<A2AResponse> {
    return this.rpc("tasks/list", {});
  }

  /** Shared JSON-RPC POST to /api/a2a. */
  private rpc(method: string, params: Record<string, unknown>): Promise<A2AResponse> {
    return this.request<A2AResponse>("/api/a2a", {
      method: "POST",
      headers: this.headers({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: cryptoRandomId(),
        method,
        params,
      }),
    });
  }

  /** GET /.well-known/agent-card.json -> the ES256-signed agent card. */
  getAgentCard(): Promise<AgentCard> {
    return this.request<AgentCard>("/.well-known/agent-card.json", {
      method: "GET",
      headers: this.headers(),
    });
  }
}

/** RFC4122-ish id without pulling a dependency. */
function cryptoRandomId(): string {
  const c = (globalThis as { crypto?: Crypto }).crypto;
  if (c?.randomUUID) return c.randomUUID();
  return `id-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}
