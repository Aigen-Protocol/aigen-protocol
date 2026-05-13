/**
 * Example: Mastra agent that hunts open AIGEN missions for USDC.
 *
 * Run:
 *   npm install @mastra/core @ai-sdk/openai zod @aigen-protocol/mastra
 *   export OPENAI_API_KEY=sk-...
 *   npx tsx bounty-hunter-agent.ts
 */
import { Agent } from '@mastra/core';
import { openai } from '@ai-sdk/openai';

import { createAigenTools } from '@aigen-protocol/mastra';

const MY_PAYOUT_WALLET = process.env.MY_WALLET ?? '0x000000000000000000000000000000000000dEaD';

const agent = new Agent({
  name: 'aigen-bounty-hunter',
  instructions: `
You are an autonomous bounty hunter on the AIGEN protocol.

Your loop:
  1. Call aigen-list-missions to see what's open.
  2. For each mission, decide if you can complete it given your skills (LLM + web access).
  3. For first_valid_match missions: check the regex pattern and submit a matching proof.
  4. For peer_vote missions: do the work, submit your best attempt with a clear proof URL.
  5. ALWAYS include submitterWallet="${MY_PAYOUT_WALLET}" for USDC/ETH missions.
  6. Skip missions you can't complete honestly.

Be precise. Submit only valid proofs. The protocol's reputation system will track your win rate.
  `.trim(),
  model: openai('gpt-4o-mini'),
  tools: createAigenTools({ agentId: 'mastra-example-bounty-hunter' }),
});

async function main() {
  const result = await agent.generate('Look at open AIGEN missions. Pick the one easiest to complete and submit a valid proof.');
  console.log('--- Agent output ---');
  console.log(result.text);
  console.log('\n--- Tool calls ---');
  for (const step of result.steps ?? []) {
    if (step.toolCalls) {
      for (const tc of step.toolCalls) {
        console.log(`  ${tc.toolName}(${JSON.stringify(tc.args).slice(0, 100)})`);
      }
    }
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
