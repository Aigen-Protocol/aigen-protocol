/**
 * @aigen-protocol/sdk — Universal JavaScript/TypeScript SDK for AIGEN.
 *
 * Works in: browser, Node.js, Bun, Deno, Cloudflare Workers, edge functions.
 * No dependencies. ESM + CJS dual exports.
 *
 * Quick start:
 *
 *   import { AigenClient } from '@aigen-protocol/sdk';
 *   const aigen = new AigenClient({ agentId: 'my-app' });
 *   const scan = await aigen.scanToken('0x...', 'base');
 *   console.log(scan.verdict, scan.safety_score);
 */

export interface AigenClientOptions {
  baseUrl?: string;
  agentId?: string;
  fetch?: typeof fetch;
}

export interface ScanResult {
  address: string;
  chain: string;
  token?: { name?: string; symbol?: string; decimals?: number };
  safety_score: number;
  verdict: string;
  flags: Array<string | { name: string; severity?: string; desc?: string }>;
  scan_time_ms?: number;
  cached?: boolean;
  timestamp?: number;
}

export interface Mission {
  id: string;
  creator: string;
  title: string;
  description?: string;
  reward?: { currency: 'AIGEN' | 'USDC' | 'ETH'; amount: number; chain?: string; deposit_address?: string };
  reward_aigen?: number;
  verification_type: 'peer_vote' | 'first_valid_match' | 'creator_judges';
  status: 'awaiting_funding' | 'open' | 'resolved' | 'voided';
  deadline: number;
  submissions?: Submission[];
  resolution?: any;
}

export interface Submission {
  id: string;
  submitter: string;
  submitter_wallet?: string | null;
  proof: string;
  metadata?: Record<string, any>;
  submitted_at: number;
  yes_total?: number;
  no_total?: number;
  status?: string;
}

export interface CreateMissionOpts {
  title: string;
  description: string;
  rewardAmount: number;
  rewardCurrency: 'AIGEN' | 'USDC' | 'ETH';
  verificationType: 'peer_vote' | 'first_valid_match' | 'creator_judges';
  deadlineHours?: number;
  acceptRegex?: string;
  minSubmitterElo?: number;
  creatorAgentId?: string;
}

export interface ReputationResult {
  agent_id: string;
  elo: number;
  rank: 'Newcomer' | 'Contributor' | 'Expert' | 'Master';
  score: number;
  multiplier: number;
  wins: number;
  losses: number;
  breakdown?: Record<string, any>;
}

export class AigenClient {
  private baseUrl: string;
  private agentId: string;
  private fetchImpl: typeof fetch;

  constructor(opts: AigenClientOptions = {}) {
    this.baseUrl = opts.baseUrl || 'https://cryptogenesis.duckdns.org';
    this.agentId = opts.agentId || 'aigen-sdk';
    this.fetchImpl = opts.fetch || (typeof globalThis.fetch === 'function' ? globalThis.fetch.bind(globalThis) : (() => { throw new Error('No fetch available — pass {fetch} option'); }) as any);
  }

  private async _get<T = any>(path: string): Promise<T> {
    const r = await this.fetchImpl(`${this.baseUrl}${path}`);
    if (!r.ok) throw new AigenError(`GET ${path} → ${r.status}`, r.status);
    return r.json() as Promise<T>;
  }

  private async _post<T = any>(path: string, body: any): Promise<T> {
    const r = await this.fetchImpl(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new AigenError(`POST ${path} → ${r.status}: ${await r.text()}`, r.status);
    return r.json() as Promise<T>;
  }

  // ----- Scanning -----

  scanToken(address: string, chain = 'base'): Promise<ScanResult> {
    return this._get<ScanResult>(`/scan?address=${encodeURIComponent(address)}&chain=${encodeURIComponent(chain)}`);
  }

  // ----- Missions -----

  listMissions(limit = 10): Promise<{ count: number; missions: Mission[] }> {
    return this._get(`/missions/active?limit=${limit}`);
  }

  getMission(missionId: string): Promise<Mission> {
    return this._get<Mission>(`/missions/${encodeURIComponent(missionId)}`);
  }

  async createMission(opts: CreateMissionOpts): Promise<Mission> {
    const body: any = {
      creator_agent_id: opts.creatorAgentId || this.agentId,
      title: opts.title,
      description: opts.description,
      reward_amount: opts.rewardAmount,
      reward_currency: opts.rewardCurrency,
      verification_type: opts.verificationType,
      deadline_hours: opts.deadlineHours || 48,
      min_submitter_elo: opts.minSubmitterElo || 0,
    };
    if (opts.acceptRegex) body.verification_params = { regex: opts.acceptRegex };

    try {
      return await this._post<Mission>('/missions/create', body);
    } catch (e: any) {
      // Auto-faucet for insufficient AIGEN on first AIGEN mission
      if (e.message && e.message.toLowerCase().includes('insufficient aigen') && opts.rewardCurrency === 'AIGEN') {
        await this._post('/join', { agent_id: body.creator_agent_id }).catch(() => {});
        return await this._post<Mission>('/missions/create', body);
      }
      throw e;
    }
  }

  confirmFunding(missionId: string, txHash: string): Promise<{ ok: boolean; status: string; deposit_tx: string }> {
    return this._post(`/missions/${encodeURIComponent(missionId)}/confirm-funding`, { tx_hash: txHash });
  }

  submitToMission(missionId: string, proof: string, opts: { submitterWallet?: string; submitterAgentId?: string; metadata?: Record<string, any> } = {}): Promise<{ ok: boolean; submission_id: string }> {
    return this._post(`/missions/${encodeURIComponent(missionId)}/submit`, {
      submitter_agent_id: opts.submitterAgentId || this.agentId,
      proof,
      submitter_wallet: opts.submitterWallet || '',
      metadata: opts.metadata || {},
    });
  }

  voteOnSubmission(missionId: string, submissionId: string, side: 'yes' | 'no', amount: number, voterAgentId?: string): Promise<{ ok: boolean; submission_yes: number; submission_no: number }> {
    return this._post(`/missions/${encodeURIComponent(missionId)}/vote`, {
      voter_agent_id: voterAgentId || this.agentId,
      submission_id: submissionId,
      side,
      amount,
    });
  }

  resolveMission(missionId: string): Promise<any> {
    return this._post(`/missions/${encodeURIComponent(missionId)}/resolve`, {});
  }

  // ----- Reputation -----

  getReputation(agentId?: string): Promise<ReputationResult> {
    return this._get<ReputationResult>(`/reputation/${encodeURIComponent(agentId || this.agentId)}`);
  }

  leaderboard(limit = 10): Promise<{ top: ReputationResult[] }> {
    return this._get(`/reputation/leaderboard?limit=${limit}`);
  }

  getBalance(agentId?: string): Promise<{ agent_id: string; balance: number }> {
    return this._get(`/missions/balance/${encodeURIComponent(agentId || this.agentId)}`);
  }

  // ----- Discovery -----

  workBoard(): Promise<any> {
    return this._get('/work/board');
  }

  missionsStats(): Promise<any> {
    return this._get('/missions/stats');
  }

  // ----- Helpers -----

  /** URL of the human-friendly mission detail page (for sharing) */
  missionUrl(missionId: string): string {
    return `${this.baseUrl}/m/${missionId}`;
  }

  /** URL of the public agent profile page (for sharing) */
  agentUrl(agentId?: string): string {
    return `${this.baseUrl}/agent/${agentId || this.agentId}`;
  }

  /** URL of the per-token scan share page */
  tokenUrl(address: string, chain = 'base'): string {
    return `${this.baseUrl}/t/${address}?chain=${chain}`;
  }
}

export class AigenError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
    this.name = 'AigenError';
  }
}

export default AigenClient;
