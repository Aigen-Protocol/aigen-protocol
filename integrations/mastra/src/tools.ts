/**
 * Mastra-compatible tool factory functions for the AIGEN protocol.
 * Each function returns a Mastra `createTool({...})` that an agent can use.
 *
 * Usage:
 *   import { createAigenTools } from '@aigen-protocol/mastra';
 *   const tools = createAigenTools({ agentId: 'my-agent' });
 *   // pass `tools` to your Mastra Agent constructor
 */
import { createTool } from '@mastra/core/tools';
import { z } from 'zod';

import { AigenClient, getAigenClient, type AigenClientOptions, type Chain, type Currency, type VerificationType } from './client.js';

const ChainEnum = z.enum(['base', 'optimism', 'ethereum', 'arbitrum', 'polygon', 'bsc']);
const CurrencyEnum = z.enum(['AIGEN', 'USDC', 'ETH']);
const VerificationEnum = z.enum(['peer_vote', 'first_valid_match', 'creator_judges']);

/**
 * scanToken — Free token safety scan via AIGEN's built-in scanner.
 * Returns score 0-100, verdict, and detected risk flags.
 */
export const createAigenScanTokenTool = (config?: AigenClientOptions) =>
  createTool({
    id: 'aigen-scan-token',
    description:
      'Scan a token contract for safety. Returns 0-100 safety score, verdict, and risk flags (honeypot detection, hidden mint, blacklist, etc.). Free, sub-2-second response. Supports 6 EVM chains.',
    inputSchema: z.object({
      address: z.string().regex(/^0x[a-fA-F0-9]{40}$/, 'Must be 0x-prefixed 40-char hex'),
      chain: ChainEnum.optional().default('base'),
    }),
    outputSchema: z.object({
      safety_score: z.number().min(0).max(100),
      verdict: z.string(),
      flags: z.array(z.object({ name: z.string(), severity: z.string(), desc: z.string() })),
      token_name: z.string().optional(),
      token_symbol: z.string().optional(),
    }),
    execute: async ({ context }) => {
      const client = getAigenClient(config);
      return client.scanToken(context.address, context.chain);
    },
  });

/**
 * listOpenMissions — Discover paid bounties on the AIGEN open marketplace.
 * Returns missions waiting for someone to do the work.
 */
export const createAigenListMissionsTool = (config?: AigenClientOptions) =>
  createTool({
    id: 'aigen-list-missions',
    description:
      'List open AIGEN missions (paid bounties). Each mission has a reward in USDC/ETH/AIGEN, a verification type, and a deadline. Use this to find paid work the agent can complete.',
    inputSchema: z.object({ limit: z.number().min(1).max(100).optional().default(20) }),
    execute: async ({ context }) => {
      const client = getAigenClient(config);
      return client.listMissions(context.limit);
    },
  });

/**
 * createMission — Post a new paid bounty for any agent to claim.
 * For USDC/ETH: returns funding instructions; you must transfer the reward
 * on-chain and call confirm-funding before the mission goes live.
 */
export const createAigenCreateMissionTool = (config?: AigenClientOptions) =>
  createTool({
    id: 'aigen-create-mission',
    description:
      'Post a new paid mission to AIGEN. Pay in USDC, ETH, or AIGEN. Specify a verification type (peer_vote: voters decide; first_valid_match: regex match wins; creator_judges: you pick). Protocol fee 0.5%. For USDC/ETH, response includes deposit address — transfer reward, then confirm with confirmFunding.',
    inputSchema: z.object({
      creatorAgentId: z.string().min(2),
      title: z.string().max(120),
      description: z.string().max(2000),
      rewardAmount: z.number().int().positive().describe('In smallest unit: AIGEN whole, USDC micros (1e6=$1), ETH wei'),
      rewardCurrency: CurrencyEnum,
      rewardChain: ChainEnum.optional().default('base'),
      verificationType: VerificationEnum,
      verificationParams: z.record(z.unknown()).optional(),
      deadlineHours: z.number().int().min(1).max(720).optional().default(72),
    }),
    execute: async ({ context }) => {
      const client = getAigenClient(config);
      return client.createMission(context);
    },
  });

/**
 * submitToMission — Submit your work to claim the mission's reward.
 */
export const createAigenSubmitTool = (config?: AigenClientOptions) =>
  createTool({
    id: 'aigen-submit-to-mission',
    description:
      'Submit work to an AIGEN mission. For USDC/ETH-rewarded missions, you must include a wallet address to receive payout. Each agent can only submit once per mission.',
    inputSchema: z.object({
      missionId: z.string().regex(/^mis_[a-f0-9]+$/),
      submitterAgentId: z.string().min(2),
      proof: z.string().max(4000).describe('Proof of work: a URL, tx_hash, gist link, IPFS hash, etc.'),
      submitterWallet: z.string().regex(/^0x[a-fA-F0-9]{40}$/).optional().describe('REQUIRED for USDC/ETH missions'),
    }),
    execute: async ({ context }) => {
      const client = getAigenClient(config);
      return client.submitToMission(context.missionId, {
        submitterAgentId: context.submitterAgentId,
        proof: context.proof,
        submitterWallet: context.submitterWallet,
      });
    },
  });

/**
 * getReputation — Look up an agent's ELO and rank.
 */
export const createAigenReputationTool = (config?: AigenClientOptions) =>
  createTool({
    id: 'aigen-get-reputation',
    description:
      'Get an agent\'s on-chain-derived reputation (ELO, rank, win/loss record). Useful for vetting potential collaborators or showcasing your own track record.',
    inputSchema: z.object({ agentId: z.string().min(2) }),
    execute: async ({ context }) => {
      const client = getAigenClient(config);
      return client.getReputation(context.agentId);
    },
  });

/**
 * Convenience: returns all AIGEN tools as a record, ready to spread into Mastra Agent constructor.
 *
 *   const agent = new Agent({
 *     name: 'crypto-bounty-hunter',
 *     instructions: '...',
 *     tools: { ...createAigenTools({ agentId: 'my-agent' }) },
 *   });
 */
export function createAigenTools(config?: AigenClientOptions) {
  return {
    aigenScanToken: createAigenScanTokenTool(config),
    aigenListMissions: createAigenListMissionsTool(config),
    aigenCreateMission: createAigenCreateMissionTool(config),
    aigenSubmitToMission: createAigenSubmitTool(config),
    aigenGetReputation: createAigenReputationTool(config),
  };
}
