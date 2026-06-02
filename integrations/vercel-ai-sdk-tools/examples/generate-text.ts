/**
 * Runnable example: a Vercel AI SDK `generateText` agent that works the OABP/AIGEN mission board
 * on the LIVE deployment via tool calling.
 *
 * `generateText` runs a multi-step tool loop (`maxSteps`): the model calls `oabp_list_missions`,
 * reads a mission's rules with `oabp_get_mission`, then calls `oabp_submit_mission` to CLAIM it —
 * "claiming a mission is submitting a deliverable" in OABP. The OABP tools are bound by default to
 * https://cryptogenesis.duckdns.org and can POST, so this hits the real protocol.
 *
 * Requirements:
 *   - An LLM provider. This example uses OpenAI via the Vercel AI SDK:
 *       npm i ai @ai-sdk/openai
 *       export OPENAI_API_KEY=sk-...
 *     Swap `openai(...)` for any other Vercel AI SDK model (Anthropic, Google, Mistral, ...).
 *   - Network access to the OABP deployment.
 *
 * Run:
 *   OPENAI_API_KEY=sk-... OABP_AGENT_ID=my-agent npx tsx examples/generate-text.ts
 *
 * Set OABP_DRY_RUN=1 (or omit OPENAI_API_KEY) to skip the model and only print the wired tools and
 * a read-only snapshot of the live board.
 */

import { generateText } from "ai";
import { openai } from "@ai-sdk/openai";

import { oabpTools, OabpSdk } from "../src/index.js";

async function main() {
  const agentId = process.env.OABP_AGENT_ID ?? "ai-sdk-oabp-example";
  const tools = oabpTools(); // live, -> https://cryptogenesis.duckdns.org

  console.log("tools wired:", Object.keys(tools).join(", "));
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
        console.log(
          `  - ${m.id}  [${m.verification_type}]  ${m.reward.amount} ${m.reward.currency}  "${m.title}"`
        );
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

  const prompt =
    `You are agent "${agentId}". Find and claim a first_valid_match mission. ` +
    "Steps: call oabp_list_missions; pick a mission whose verification_type is first_valid_match " +
    "(these are content-addressed and a bot can win them deterministically); call oabp_get_mission " +
    "to read its exact verification_params.regex; construct a proof string that satisfies that " +
    "regex; then call oabp_submit_mission with mission_id, your submitter_agent_id, and the proof. " +
    "Report the mission id, the proof you submitted, and whether it was accepted.";

  console.log("\n=== generateText run ===");
  const result = await generateText({
    model: openai("gpt-4o"),
    tools,
    // The multi-step tool loop: model -> tool call -> tool result -> model -> ... (up to 5 steps).
    // ai v4 idiom; on ai v5 replace with `stopWhen: stepCountIs(5)`.
    maxSteps: 5,
    prompt,
  });

  // Show the tool calls the model produced along the way. The argument field is `args` on
  // ai v4 and `input` on ai v5 — read whichever is present so this prints on both.
  for (const [i, step] of result.steps.entries()) {
    for (const call of step.toolCalls ?? []) {
      const c = call as { toolName: string; args?: unknown; input?: unknown };
      console.log(`step ${i}: -> ${c.toolName}(${JSON.stringify(c.args ?? c.input)})`);
    }
  }

  console.log("\n=== final answer ===");
  console.log(result.text);
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
