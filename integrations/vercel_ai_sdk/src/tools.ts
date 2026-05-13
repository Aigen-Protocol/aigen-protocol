/**
 * Vercel AI SDK tool definitions for AIGEN.
 *
 * Uses the `tool()` factory from 'ai' (Vercel AI SDK). Compatible with
 * generateText({ tools }), streamText({ tools }), and the AI SDK's agent loop.
 *
 * Quick start:
 *   import { generateText } from 'ai';
 *   import { openai } from '@ai-sdk/openai';
 *   import { aigenTools } from '@aigen-protocol/vercel-ai-sdk';
 *
 *   const result = await generateText({
 *     model: openai('gpt-4o-mini'),
 *     tools: aigenTools({ agentId: 'my-agent' }),
 *     prompt: 'Find an open AIGEN mission and submit a proof.',
 *   });
 */
import { tool } from 'ai';
import { z } from 'zod';

import { AigenClient, getAigenClient, type AigenClientOptions } from './client.js';

const ChainEnum = z.enum(['base', 'optimism', 'ethereum', 'arbitrum', 'polygon', 'bsc']);
const CurrencyEnum = z.enum(['AIGEN', 'USDC', 'ETH']);
const VerificationEnum = z.enum(['peer_vote', 'first_valid_match', 'creator_judges']);

/**
 * scanToken — Free token safety scan via AIGEN.
 */
export const aigenScanToken = (config?: AigenClientOptions) =>
  tool({
    description:
      'Scan a token contract for safety. Returns 0-100 safety score, verdict, and risk flags ' +
      '(honeypot detection, hidden mint, blacklist, etc.). Free, sub-2-second, supports 6 EVM chains. ' +
      'Use BEFORE any token swap or transfer.',
    parameters: z.object({
      address: z.string().regex(/^0x[a-fA-F0-9]{40}$/),
      chain: ChainEnum.optional().default('base'),
    }),
    execute: async ({ address, chain }) => {
      const client = getAigenClient(config);
      return await client.scanToken(address, chain);
    },
  });

/**
 * listMissions — Discover open paid bounties on AIGEN.
 */
export const aigenListMissions = (config?: AigenClientOptions) =>
  tool({
    description:
      'List currently-open paid missions on the AIGEN bounty marketplace. ' +
      'Use this to find paid work the agent can complete autonomously.',
    parameters: z.object({
      limit: z.number().min(1).max(100).optional().default(20),
    }),
    execute: async ({ limit }) => {
      const client = getAigenClient(config);
      return await client.listMissions(limit);
    },
  });

/**
 * createMission — Post a new paid mission.
 */
export const aigenCreateMission = (config?: AigenClientOptions) =>
  tool({
    description:
      'Post a new paid mission on AIGEN. Pay in USDC, ETH, or AIGEN. Protocol fee 0.5%. ' +
      'For USDC/ETH the response includes a deposit address — must transfer reward on-chain ' +
      'and call confirm-funding before mission goes live.',
    parameters: z.object({
      creatorAgentId: z.string().min(2),
      title: z.string().max(120),
      description: z.string().max(2000),
      rewardAmount: z.number().int().positive().describe('Smallest unit: USDC micros (1e6=$1), ETH wei, AIGEN whole'),
      rewardCurrency: CurrencyEnum,
      rewardChain: ChainEnum.optional().default('base'),
      verificationType: VerificationEnum,
      deadlineHours: z.number().int().min(1).max(720).optional().default(168),
    }),
    execute: async (input) => {
      const client = getAigenClient(config);
      return await client.createMission(input);
    },
  });

/**
 * submitToMission — Submit work to claim a mission's reward.
 */
export const aigenSubmitToMission = (config?: AigenClientOptions) =>
  tool({
    description:
      'Submit work to claim a mission\'s reward. For USDC/ETH-rewarded missions, you MUST include ' +
      'a wallet address to receive payout. One submission per agent per mission.',
    parameters: z.object({
      missionId: z.string().regex(/^mis_[a-f0-9]+$/),
      submitterAgentId: z.string().min(2),
      proof: z.string().max(4000).describe('Proof of work: URL, tx hash, gist, IPFS hash, etc.'),
      submitterWallet: z.string().regex(/^0x[a-fA-F0-9]{40}$/).optional().describe('REQUIRED for USDC/ETH missions'),
    }),
    execute: async ({ missionId, submitterAgentId, proof, submitterWallet }) => {
      const client = getAigenClient(config);
      return await client.submitToMission(missionId, {
        submitterAgentId,
        proof,
        submitterWallet,
      });
    },
  });

/**
 * getReputation — Look up an agent's ELO and rank.
 */
export const aigenGetReputation = (config?: AigenClientOptions) =>
  tool({
    description:
      'Get an agent\'s on-chain-derived reputation: ELO, rank, wins, losses. ' +
      'Useful for vetting potential collaborators or showcasing your own track record.',
    parameters: z.object({
      agentId: z.string().min(2),
    }),
    execute: async ({ agentId }) => {
      const client = getAigenClient(config);
      return await client.getReputation(agentId);
    },
  });

/**
 * Convenience: returns all AIGEN tools as an object ready to spread into
 * Vercel AI SDK generateText/streamText.
 *
 *   const result = await generateText({
 *     model: openai('gpt-4o-mini'),
 *     tools: { ...aigenTools({ agentId: 'my-bot' }) },
 *     prompt: '...',
 *   });
 */
export function aigenTools(config?: AigenClientOptions) {
  return {
    aigenScanToken: aigenScanToken(config),
    aigenListMissions: aigenListMissions(config),
    aigenCreateMission: aigenCreateMission(config),
    aigenSubmitToMission: aigenSubmitToMission(config),
    aigenGetReputation: aigenGetReputation(config),
  };
}
