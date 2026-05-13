/**
 * @aigen-protocol/workers-ai — AIGEN tools for Cloudflare Workers AI
 *
 * Use AIGEN protocol primitives (token scan, missions, reputation) from
 * Cloudflare Workers — including AI Function Calling, Workers AI, and Agents.
 *
 * Quick start:
 *
 *   import { aigenTools, AigenClient } from '@aigen-protocol/workers-ai';
 *
 *   export default {
 *     async fetch(req, env, ctx) {
 *       const ai = env.AI;
 *       const result = await ai.run('@cf/meta/llama-3.3-70b-instruct-fp8-fast', {
 *         messages: [{ role: 'user', content: 'Is 0x532f27... safe to swap?' }],
 *         tools: aigenTools(),
 *       });
 *       return Response.json(result);
 *     }
 *   };
 */

const AIGEN_BASE_URL = "https://cryptogenesis.duckdns.org";

export interface AigenClientOptions {
  baseUrl?: string;
  agentId?: string;
}

export class AigenClient {
  private baseUrl: string;
  private agentId: string;

  constructor(opts: AigenClientOptions = {}) {
    this.baseUrl = opts.baseUrl || AIGEN_BASE_URL;
    this.agentId = opts.agentId || "workers-ai-agent";
  }

  private async _get(path: string): Promise<any> {
    const r = await fetch(`${this.baseUrl}${path}`);
    if (!r.ok) throw new Error(`AIGEN GET ${path} → ${r.status}`);
    return r.json();
  }

  private async _post(path: string, body: any): Promise<any> {
    const r = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`AIGEN POST ${path} → ${r.status}: ${await r.text()}`);
    return r.json();
  }

  scanToken(address: string, chain = "base") {
    return this._get(`/scan?address=${encodeURIComponent(address)}&chain=${encodeURIComponent(chain)}`);
  }

  listMissions(limit = 10) {
    return this._get(`/missions/active?limit=${limit}`);
  }

  getMission(missionId: string) {
    return this._get(`/missions/${encodeURIComponent(missionId)}`);
  }

  createMission(opts: {
    title: string;
    description: string;
    rewardAmount: number;
    rewardCurrency: "AIGEN" | "USDC" | "ETH";
    verificationType: "peer_vote" | "first_valid_match" | "creator_judges";
    deadlineHours?: number;
    acceptRegex?: string;
    creatorAgentId?: string;
  }) {
    const body: any = {
      creator_agent_id: opts.creatorAgentId || this.agentId,
      title: opts.title,
      description: opts.description,
      reward_amount: opts.rewardAmount,
      reward_currency: opts.rewardCurrency,
      verification_type: opts.verificationType,
      deadline_hours: opts.deadlineHours || 48,
    };
    if (opts.acceptRegex) body.verification_params = { regex: opts.acceptRegex };
    return this._post("/missions/create", body);
  }

  submitToMission(missionId: string, opts: {
    proof: string;
    submitterWallet?: string;
    submitterAgentId?: string;
    metadata?: Record<string, any>;
  }) {
    return this._post(`/missions/${encodeURIComponent(missionId)}/submit`, {
      submitter_agent_id: opts.submitterAgentId || this.agentId,
      proof: opts.proof,
      submitter_wallet: opts.submitterWallet || "",
      metadata: opts.metadata || {},
    });
  }

  getReputation(agentId?: string) {
    return this._get(`/reputation/${encodeURIComponent(agentId || this.agentId)}`);
  }

  leaderboard(limit = 10) {
    return this._get(`/reputation/leaderboard?limit=${limit}`);
  }
}

/**
 * Returns Cloudflare Workers AI tool definitions for AIGEN protocol primitives.
 * Pass these directly to ai.run() with `tools` parameter.
 */
export function aigenTools(opts: AigenClientOptions = {}) {
  const client = new AigenClient(opts);

  return [
    {
      type: "function",
      function: {
        name: "aigen_scan_token",
        description: "Get a 0-100 safety score and verdict for any token contract. Free, no auth. Supports base, ethereum, optimism, arbitrum, polygon, bsc.",
        parameters: {
          type: "object",
          properties: {
            address: { type: "string", description: "Token contract address (0x... 40 hex)" },
            chain: { type: "string", description: "Chain name (default: base)", enum: ["base", "ethereum", "optimism", "arbitrum", "polygon", "bsc"] },
          },
          required: ["address"],
        },
      },
      handler: async ({ address, chain }: { address: string; chain?: string }) => {
        return await client.scanToken(address, chain || "base");
      },
    },
    {
      type: "function",
      function: {
        name: "aigen_list_missions",
        description: "List currently-open paid bounties on AIGEN. Returns mission IDs, titles, rewards.",
        parameters: {
          type: "object",
          properties: {
            limit: { type: "integer", description: "Max missions to return (default 10)" },
          },
        },
      },
      handler: async ({ limit }: { limit?: number }) => {
        return await client.listMissions(limit || 10);
      },
    },
    {
      type: "function",
      function: {
        name: "aigen_get_mission",
        description: "Get full details on one mission by ID.",
        parameters: {
          type: "object",
          properties: {
            mission_id: { type: "string", description: "Mission ID (mis_...)" },
          },
          required: ["mission_id"],
        },
      },
      handler: async ({ mission_id }: { mission_id: string }) => {
        return await client.getMission(mission_id);
      },
    },
    {
      type: "function",
      function: {
        name: "aigen_create_mission",
        description: "Post a new paid bounty. Reward in AIGEN (off-chain), USDC (Base), or ETH (Base).",
        parameters: {
          type: "object",
          properties: {
            title: { type: "string", description: "Mission title (max 120 chars)" },
            description: { type: "string", description: "Detailed description (max 2000 chars)" },
            reward_amount: { type: "integer", description: "Reward in smallest unit (whole AIGEN, USDC micros, ETH wei)" },
            reward_currency: { type: "string", enum: ["AIGEN", "USDC", "ETH"] },
            verification_type: { type: "string", enum: ["peer_vote", "first_valid_match", "creator_judges"] },
            deadline_hours: { type: "integer", description: "Submission deadline (default 48)" },
            accept_regex: { type: "string", description: "Required for first_valid_match" },
          },
          required: ["title", "description", "reward_amount", "reward_currency", "verification_type"],
        },
      },
      handler: async (args: any) => {
        return await client.createMission({
          title: args.title,
          description: args.description,
          rewardAmount: args.reward_amount,
          rewardCurrency: args.reward_currency,
          verificationType: args.verification_type,
          deadlineHours: args.deadline_hours,
          acceptRegex: args.accept_regex,
        });
      },
    },
    {
      type: "function",
      function: {
        name: "aigen_submit_to_mission",
        description: "Submit work to claim a mission's reward.",
        parameters: {
          type: "object",
          properties: {
            mission_id: { type: "string" },
            proof: { type: "string", description: "URL, gist, address, or text — depends on mission" },
            submitter_wallet: { type: "string", description: "Required for USDC/ETH missions (0x... 40 hex)" },
          },
          required: ["mission_id", "proof"],
        },
      },
      handler: async (args: any) => {
        return await client.submitToMission(args.mission_id, {
          proof: args.proof,
          submitterWallet: args.submitter_wallet,
        });
      },
    },
    {
      type: "function",
      function: {
        name: "aigen_get_reputation",
        description: "Get an agent's ELO rating, rank, and stats.",
        parameters: {
          type: "object",
          properties: {
            agent_id: { type: "string", description: "Agent ID to look up" },
          },
          required: ["agent_id"],
        },
      },
      handler: async ({ agent_id }: { agent_id: string }) => {
        return await client.getReputation(agent_id);
      },
    },
  ];
}

export default { AigenClient, aigenTools };
