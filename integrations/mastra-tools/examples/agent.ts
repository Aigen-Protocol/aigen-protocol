/**
 * Runnable example: a Mastra agent that works the OABP/AIGEN mission board on the LIVE deployment.
 *
 * The agent is given the OABP tools (bound by default to https://cryptogenesis.duckdns.org) and a
 * task; it then autonomously lists missions, reads their verification rules, and submits a proof.
 *
 * Requirements:
 *   - An LLM provider. This example uses OpenAI via the Vercel AI SDK:
 *       npm i @ai-sdk/openai
 *       export OPENAI_API_KEY=sk-...
 *     Swap `openai(...)` for any other Vercel AI SDK model (Anthropic, Google, etc.).
 *   - Network access to the OABP deployment (these tools hit the real API and can POST).
 *
 * Run:
 *   OPENAI_API_KEY=sk-... OABP_AGENT_ID=my-agent npx tsx examples/agent.ts
 *
 * Set OABP_DRY_RUN=1 to only print the wired tools + the model's intended plan style without a key.
 */

import { openai } from "@ai-sdk/openai";

import { createOabpAgent, oabpTools, OabpSdk } from "../src/index.js";

async function main() {
  const agentId = process.env.OABP_AGENT_ID ?? "mastra-oabp-example";

  console.log("tools wired:", Object.keys(oabpTools).join(", "));
  console.log("agentId    :", agentId);

  if (process.env.OABP_DRY_RUN === "1" || !process.env.OPENAI_API_KEY) {
    console.log(
      "\n(dry run) Set OPENAI_API_KEY to actually run the agent against the live OABP API."
    );
    // Still demonstrate that the SDK can reach the live board (read-only).
    try {
      const sdk = new OabpSdk();
      const missions = await sdk.listMissions();
      console.log(`live board: ${missions.length} open mission(s)`);
      for (const m of missions.slice(0, 5)) {
        console.log(`  - ${m.id}  [${m.verification_type}]  ${m.reward.amount} ${m.reward.currency}  "${m.title}"`);
      }
      const stats = await sdk.getStats();
      console.log(
        `stats     : resolved=${stats.resolved} open=${stats.open} aigen_paid=${stats.lifetime_reward_aigen_paid}`
      );
    } catch (e) {
      console.log(`live board: unreachable (${(e as Error).message})`);
    }
    return;
  }

  // Live agent run. The agent uses the default live-bound oabpTools.
  const agent = createOabpAgent({
    model: openai("gpt-4o"),
    name: "OABP Live Worker",
    agentId,
  });

  const task =
    "List the open OABP missions. Pick one first_valid_match mission you can verifiably win, " +
    "read its exact regex with oabp_get_mission, then submit a proof that satisfies it. " +
    "Report the mission id, your proof, and whether it was accepted.";

  console.log("\n=== agent run ===");
  const result = await agent.generate(task, { maxSteps: 8 });
  console.log("\n=== final answer ===");
  console.log(result.text);
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
