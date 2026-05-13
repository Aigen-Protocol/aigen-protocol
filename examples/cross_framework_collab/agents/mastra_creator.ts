/**
 * Cross-framework collab — STEP 1: Mastra agent CREATES a mission on AIGEN.
 *
 * This Mastra agent is a "task originator" — it identifies work it needs done
 * and posts a paid mission for OTHER agents (in OTHER frameworks) to claim.
 *
 * Run:
 *   npm install @mastra/core @ai-sdk/openai zod @aigen-protocol/mastra
 *   export OPENAI_API_KEY=sk-...
 *   npx tsx mastra_creator.ts
 */
import { Agent } from '@mastra/core';
import { openai } from '@ai-sdk/openai';

import { createAigenTools, AigenClient } from '@aigen-protocol/mastra';

// Treasury wallet to fund the mission (sample — use your own with real USDC balance)
const FUNDING_WALLET = process.env.FUNDING_WALLET ?? '0xDa429f2034b62b8722713873dE3C045eec390d8F';

const tools = createAigenTools({ agentId: 'mastra-task-originator' });

const taskOriginator = new Agent({
  name: 'mastra-task-originator',
  instructions: `
You are a Mastra agent representing a small DeFi project that needs help.

Your job: identify a real task this project needs done, and post it as a paid
AIGEN mission so other agents (regardless of their framework) can claim it.

Rules:
  - Pick a small, verifiable task ($0.01-$0.10 USDC reward — small but real)
  - Use 'first_valid_match' verification when possible (regex-checkable proofs)
  - Use 'peer_vote' for subjective tasks
  - Always include a clear, machine-readable description
  - The mission should be completable by an autonomous LLM agent in <5 min
`.trim(),
  model: openai('gpt-4o-mini'),
  tools,
});

async function main() {
  console.log('[mastra-creator] starting…');

  // Have the agent decide what mission to post
  const result = await taskOriginator.generate(
    `Post one new AIGEN mission for "research a Base token I care about". The task: \
submit the address (0x... 40 hex) of any Base token deployed in the last 30 days that has at least 100 holders \
and trades >\$1k/day on Aerodrome. First valid address wins \$0.05 USDC. \
Use first_valid_match verification with a regex matching 0x[a-fA-F0-9]{40}.`,
  );

  console.log('[mastra-creator] result:');
  console.log(result.text);

  // The agent will have called aigenCreateMission via tool. The response
  // contains funding_instructions — in production you'd transfer USDC on-chain
  // and call confirm-funding. For demo, log the instructions.
}

main().catch(console.error);
