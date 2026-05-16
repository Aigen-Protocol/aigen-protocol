/** OABP TypeScript client — AIP-1 v0.1
 * Spec: https://cryptogenesis.duckdns.org/specs/AIP-1
 * License: CC0-1.0 (same as the spec)
 *
 * Usage:
 *   import { OABPClient } from 'oabp';
 *   const client = new OABPClient('https://cryptogenesis.duckdns.org');
 *   const missions = await client.listMissions();
 *   const sub = await client.submit('mis_abc123', '0xMe', 'ipfs://Qm...', '0xhash');
 *   const rep = await client.agent('0xMe');
 *
 * Works in Node 18+ (native fetch) and modern browsers.
 * Zero runtime dependencies.
 */

export const VERSION = "0.1.0";
export const AIP_SUPPORTED = [1] as const;

// ---- Error ----

export class OABPError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
    public readonly body?: string,
  ) {
    super(message);
    this.name = "OABPError";
  }
}

// ---- Data types (AIP-1 §§ 2-3-5) ----

export interface Mission {
  id: string;
  creator: string;
  title: string;
  description: string;
  reward_asset: string;
  reward_amount: number;
  verification_type: "creator_judges" | "first_valid_match" | "peer_vote" | "oracle";
  verification_params: Record<string, unknown>;
  deadline: string;   // ISO 8601 UTC
  status: "open" | "escrowed" | "resolved" | "voided";
  created_at: string;
  extra: Record<string, unknown>;  // forward-compat unknown fields
}

export interface Submission {
  submission_id: string;
  mission_id: string;
  submitter: string;
  content_uri: string;
  content_hash: string;
  submitted_at: string;
  metadata: Record<string, unknown>;
}

export interface AgentReputation {
  agent_id: string;
  rating: number;         // ELO; starts at 1400
  completed: number;
  missions_won: number;
  missions_lost: number;
  last_activity_ts?: string;
  badge_url?: string;     // embeddable SVG
  extra: Record<string, unknown>;
}

// ---- Client ----

export class OABPClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly userAgent: string;
  private _endpoints: Record<string, string> | null = null;

  static readonly DEFAULT_TIMEOUT_MS = 15_000;
  static readonly DEFAULT_ENDPOINTS: Record<string, string> = {
    missions: "/missions",
    missions_active: "/missions/active",
    missions_stats: "/missions/stats",
    agents: "/api/agents",
    agent_badge: "/api/agents/{id}/badge.svg",
    leaderboard: "/api/leaderboard",
    submissions: "/api/submissions",
    feed: "/feed.xml",
  };

  constructor(baseUrl: string, options?: { timeoutMs?: number; userAgent?: string }) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.timeoutMs = options?.timeoutMs ?? OABPClient.DEFAULT_TIMEOUT_MS;
    this.userAgent = options?.userAgent ?? `oabp-typescript/${VERSION}`;
  }

  // ---- Discovery (AIP-1 §9) ----

  /** Fetch /.well-known/oabp.json and return the raw manifest. */
  static async discover(baseUrl: string, timeoutMs = 10_000): Promise<Record<string, unknown>> {
    const url = `${baseUrl.replace(/\/$/, "")}/.well-known/oabp.json`;
    return OABPClient._request(url, {}, timeoutMs, "oabp-typescript-discover/0.1") as Promise<Record<string, unknown>>;
  }

  /** Returns the endpoint map from oabp.json, falling back to AIP-1 defaults. Cached. */
  async endpoints(): Promise<Record<string, string>> {
    if (this._endpoints) return this._endpoints;
    try {
      const info = await OABPClient.discover(this.baseUrl, this.timeoutMs);
      this._endpoints = (info["endpoints"] as Record<string, string> | undefined) ?? {};
    } catch {
      this._endpoints = { ...OABPClient.DEFAULT_ENDPOINTS };
    }
    return this._endpoints;
  }

  // ---- HTTP helpers ----

  private static async _request(
    url: string,
    init: RequestInit,
    timeoutMs: number,
    userAgent: string,
  ): Promise<unknown> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, {
        ...init,
        signal: controller.signal,
        headers: {
          "User-Agent": userAgent,
          Accept: "application/json",
          ...(init.headers as Record<string, string> | undefined ?? {}),
        },
      });
      const text = await res.text();
      if (!res.ok) throw new OABPError(`HTTP ${res.status} on ${url}`, res.status, text);
      return JSON.parse(text);
    } catch (err) {
      if (err instanceof OABPError) throw err;
      throw new OABPError(String(err));
    } finally {
      clearTimeout(timer);
    }
  }

  private async _get(path: string): Promise<unknown> {
    return OABPClient._request(`${this.baseUrl}${path}`, { method: "GET" }, this.timeoutMs, this.userAgent);
  }

  private async _post(path: string, body: unknown): Promise<unknown> {
    return OABPClient._request(
      `${this.baseUrl}${path}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
      this.timeoutMs,
      this.userAgent,
    );
  }

  // ---- Parsers ----

  private static _parseMission(d: Record<string, unknown>): Mission {
    const reward = (d["reward"] as Record<string, unknown> | undefined) ?? {};
    const verification = (d["verification"] as Record<string, unknown> | undefined) ?? {};
    const known = new Set(["id", "creator", "title", "description", "reward", "verification", "deadline", "status", "created_at"]);
    return {
      id: d["id"] as string,
      creator: d["creator"] as string,
      title: (d["title"] as string | undefined) ?? "",
      description: (d["description"] as string | undefined) ?? "",
      reward_asset: (reward["asset"] as string | undefined) ?? "AIGEN",
      reward_amount: Number(reward["amount"] ?? 0),
      verification_type: ((verification["type"] as string | undefined) ?? "creator_judges") as Mission["verification_type"],
      verification_params: (verification["params"] as Record<string, unknown> | undefined) ?? {},
      deadline: (d["deadline"] as string | undefined) ?? "",
      status: ((d["status"] as string | undefined) ?? "open") as Mission["status"],
      created_at: (d["created_at"] as string | undefined) ?? "",
      extra: Object.fromEntries(Object.entries(d).filter(([k]) => !known.has(k))),
    };
  }

  private static _parseSubmission(d: Record<string, unknown>): Submission {
    return {
      submission_id: d["submission_id"] as string,
      mission_id: d["mission_id"] as string,
      submitter: d["submitter"] as string,
      content_uri: (d["content_uri"] as string | undefined) ?? "",
      content_hash: (d["content_hash"] as string | undefined) ?? "",
      submitted_at: (d["submitted_at"] as string | undefined) ?? "",
      metadata: (d["metadata"] as Record<string, unknown> | undefined) ?? {},
    };
  }

  private static _parseReputation(d: Record<string, unknown>): AgentReputation {
    const known = new Set(["agent_id", "id", "rating", "completed", "missions_won", "missions_lost", "last_activity_ts", "badge_url"]);
    return {
      agent_id: (d["agent_id"] as string | undefined) ?? (d["id"] as string | undefined) ?? "",
      rating: Number(d["rating"] ?? 1400),
      completed: Number(d["completed"] ?? 0),
      missions_won: Number(d["missions_won"] ?? 0),
      missions_lost: Number(d["missions_lost"] ?? 0),
      last_activity_ts: d["last_activity_ts"] as string | undefined,
      badge_url: d["badge_url"] as string | undefined,
      extra: Object.fromEntries(Object.entries(d).filter(([k]) => !known.has(k))),
    };
  }

  // ---- Mission operations ----

  async listMissions(status = "open", limit = 50): Promise<Mission[]> {
    const ep = await this.endpoints();
    const path = status === "open"
      ? (ep["missions_active"] ?? "/missions/active")
      : (ep["missions"] ?? "/missions");
    const data = await this._get(`${path}?status=${encodeURIComponent(status)}&limit=${limit}`);
    const items = (Array.isArray(data) ? data : ((data as Record<string, unknown>)["missions"] ?? (data as Record<string, unknown>)["items"] ?? [])) as Record<string, unknown>[];
    return items.map(OABPClient._parseMission);
  }

  async getMission(missionId: string): Promise<Mission> {
    const ep = await this.endpoints();
    const data = await this._get(`${ep["missions"] ?? "/missions"}/${missionId}`);
    return OABPClient._parseMission(data as Record<string, unknown>);
  }

  /** AIP-1 §3 — submit a candidate solution. */
  async submit(
    missionId: string,
    agentId: string,
    contentUri: string,
    contentHash: string,
    metadata?: Record<string, unknown>,
  ): Promise<Submission> {
    const ep = await this.endpoints();
    const data = await this._post(`${ep["missions"] ?? "/missions"}/${missionId}/submit`, {
      submitter: agentId,
      content_uri: contentUri,
      content_hash: contentHash,
      metadata: metadata ?? {},
    });
    return OABPClient._parseSubmission(data as Record<string, unknown>);
  }

  async getSubmission(_missionId: string, submissionId: string): Promise<Submission> {
    const ep = await this.endpoints();
    const data = await this._get(`${ep["submissions"] ?? "/api/submissions"}/${submissionId}`);
    return OABPClient._parseSubmission(data as Record<string, unknown>);
  }

  // ---- Agent / reputation (AIP-1 §5) ----

  async agent(agentId: string): Promise<AgentReputation> {
    const ep = await this.endpoints();
    const data = await this._get(`${ep["agents"] ?? "/api/agents"}/${agentId}`);
    return OABPClient._parseReputation(data as Record<string, unknown>);
  }

  /** Returns the embeddable badge SVG URL (AIP-1 §5 mandatory). Sync. */
  agentBadgeUrl(agentId: string): string {
    const tpl = this._endpoints?.["agent_badge"] ?? OABPClient.DEFAULT_ENDPOINTS["agent_badge"]!;
    return `${this.baseUrl}${tpl.replace("{id}", agentId)}`;
  }

  async leaderboard(limit = 50): Promise<AgentReputation[]> {
    const ep = await this.endpoints();
    const data = await this._get(`${ep["leaderboard"] ?? "/api/leaderboard"}?limit=${limit}`);
    const items = (Array.isArray(data) ? data : ((data as Record<string, unknown>)["agents"] ?? (data as Record<string, unknown>)["items"] ?? [])) as Record<string, unknown>[];
    return items.map(OABPClient._parseReputation);
  }
}
