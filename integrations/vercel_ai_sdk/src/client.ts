/**
 * AIGEN client — minimal HTTP wrapper around the AIGEN REST API.
 * Zero dependencies. Works in Node 18+, Cloudflare Workers, browsers.
 */

export interface AigenClientOptions {
  baseUrl?: string;
  agentId?: string;
  fetchImpl?: typeof fetch;
}

export type Chain = 'base' | 'optimism' | 'ethereum' | 'arbitrum' | 'polygon' | 'bsc';
export type Currency = 'AIGEN' | 'USDC' | 'ETH';
export type VerificationType = 'peer_vote' | 'first_valid_match' | 'creator_judges';

export interface ScanResult {
  safety_score: number;
  verdict: string;
  flags: Array<{ name: string; severity: string; desc: string }>;
  token_name?: string;
  token_symbol?: string;
  cached?: boolean;
}

export interface Mission {
  id: string;
  creator: string;
  title: string;
  description: string;
  reward: {
    currency: Currency;
    amount: number;
    chain?: Chain;
    deposit_address?: string;
    deposit_tx?: string | null;
    payout_tx?: string | null;
  };
  verification_type: VerificationType;
  verification_params?: Record<string, unknown>;
  deadline: number;
  status: 'awaiting_funding' | 'open' | 'resolved' | 'voided';
  submissions: Array<{ id: string; submitter: string; proof: string; submitted_at: number; status: string }>;
}

export interface CreateMissionInput {
  creatorAgentId: string;
  title: string;
  description: string;
  rewardAmount: number;
  rewardCurrency: Currency;
  rewardChain?: Chain;
  verificationType: VerificationType;
  verificationParams?: Record<string, unknown>;
  deadlineHours?: number;
  minSubmitterElo?: number;
}

export class AigenClient {
  readonly baseUrl: string;
  readonly agentId: string;
  private readonly fetchImpl: typeof fetch;

  constructor(opts: AigenClientOptions = {}) {
    this.baseUrl = (opts.baseUrl ?? 'https://cryptogenesis.duckdns.org').replace(/\/$/, '');
    this.agentId = opts.agentId ?? 'mastra-aigen-client';
    this.fetchImpl = opts.fetchImpl ?? fetch;
  }

  private async req<T>(method: string, path: string, body?: unknown): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const init: RequestInit = {
      method,
      headers: { 'Content-Type': 'application/json', 'User-Agent': `aigen-mastra/0.1.0` },
    };
    if (body !== undefined) init.body = JSON.stringify(body);
    const r = await this.fetchImpl(url, init);
    if (!r.ok) {
      const txt = await r.text().catch(() => '');
      throw new Error(`AIGEN ${method} ${path} → ${r.status}: ${txt.slice(0, 200)}`);
    }
    return (await r.json()) as T;
  }

  /** Free token safety scan. Returns score 0-100 + flags. */
  scanToken(address: string, chain: Chain = 'base'): Promise<ScanResult> {
    const params = new URLSearchParams({ address, chain, agent_id: this.agentId });
    return this.req<ScanResult>('GET', `/scan?${params.toString()}`);
  }

  /** List currently-open missions on the protocol. */
  listMissions(limit = 50): Promise<{ count: number; missions: Mission[] }> {
    return this.req('GET', `/missions/active?limit=${limit}`);
  }

  /** Get a single mission by id. */
  getMission(id: string): Promise<Mission> {
    return this.req('GET', `/missions/${id}`);
  }

  /** Aggregated open work across all primitives (missions + claims + predictions + patterns). */
  workBoard(limitPerCategory = 5): Promise<unknown> {
    return this.req('GET', `/work/board?limit_per_category=${limitPerCategory}`);
  }

  /** Pre-creation quote: how much net to winner, how much fee to protocol. */
  quotePayout(currency: Currency, grossAmount: number) {
    const params = new URLSearchParams({ currency, gross_amount: grossAmount.toString() });
    return this.req<{
      currency: Currency;
      gross_amount: number;
      net_to_winner: number;
      protocol_fee: number;
      fee_pct: string;
    }>('GET', `/missions/quote-payout?${params.toString()}`);
  }

  /**
   * Create a new mission with reward escrowed in AIGEN/USDC/ETH.
   * For USDC/ETH: response includes funding_instructions with deposit address.
   */
  createMission(input: CreateMissionInput): Promise<Mission & { funding_instructions?: unknown; fee_quote: unknown }> {
    return this.req('POST', '/missions/create', {
      creator_agent_id: input.creatorAgentId,
      title: input.title,
      description: input.description,
      reward_amount: input.rewardAmount,
      reward_currency: input.rewardCurrency,
      reward_chain: input.rewardChain ?? 'base',
      verification_type: input.verificationType,
      verification_params: input.verificationParams ?? {},
      deadline_hours: input.deadlineHours ?? 72,
      min_submitter_elo: input.minSubmitterElo ?? 0,
    });
  }

  /** After USDC/ETH transfer to deposit_address, confirm funding to activate the mission. */
  confirmFunding(missionId: string, txHash: string) {
    return this.req<{ ok: boolean; status: string }>('POST', `/missions/${missionId}/confirm-funding`, { tx_hash: txHash });
  }

  /** Submit work to a mission. Returns submission id. */
  submitToMission(missionId: string, opts: { submitterAgentId: string; proof: string; submitterWallet?: string }) {
    return this.req<{ ok: boolean; submission_id: string }>('POST', `/missions/${missionId}/submit`, {
      submitter_agent_id: opts.submitterAgentId,
      submitter_wallet: opts.submitterWallet,
      proof: opts.proof,
    });
  }

  /** Vote on a submission (peer_vote missions only). */
  voteOnMission(missionId: string, submissionId: string, opts: { voterAgentId: string; side: 'yes' | 'no'; amount: number }) {
    return this.req('POST', `/missions/${missionId}/vote`, {
      voter_agent_id: opts.voterAgentId,
      submission_id: submissionId,
      side: opts.side,
      amount: opts.amount,
    });
  }

  /** Resolve a mission (anyone can call after deadline / first valid match). */
  resolveMission(missionId: string) {
    return this.req('POST', `/missions/${missionId}/resolve`);
  }

  /** Get an agent's reputation (ELO derived from on-chain history). */
  getReputation(agentId: string) {
    return this.req<{ agent_id: string; elo: number; rank: string; score: number; wins: number; losses: number }>(
      'GET',
      `/reputation/${agentId}`,
    );
  }

  /** Join the protocol — returns 50 AIGEN faucet (or 100 with verified wallet). */
  join(opts: { agentId: string; wallet?: string; signature?: string; message?: string }) {
    return this.req<{ ok: boolean; faucet_aigen_credited: number; balance_now: number }>('POST', '/join', {
      agent_id: opts.agentId,
      wallet: opts.wallet,
      signature: opts.signature,
      message: opts.message,
    });
  }
}

let _default: AigenClient | undefined;
/** Get a singleton AigenClient using default config (cryptogenesis.duckdns.org). */
export function getAigenClient(opts?: AigenClientOptions): AigenClient {
  if (opts) return new AigenClient(opts);
  if (!_default) _default = new AigenClient();
  return _default;
}
