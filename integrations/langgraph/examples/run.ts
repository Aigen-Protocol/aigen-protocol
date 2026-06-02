/**
 * Runnable example: drive the OABP mission loop with LangGraph.
 *
 * By default it runs fully offline against {@link MockOabpClient} (no network), so it works
 * anywhere. Set OABP_LIVE=1 to point it at the real protocol via {@link OabpSdk} (read +
 * write to https://cryptogenesis.duckdns.org). The graph code is identical either way — only
 * the injected client changes.
 *
 *   Offline:  npm run example
 *   Live:     OABP_LIVE=1 OABP_AGENT_ID=my-agent npm run example
 *
 * It streams the graph so you can watch discover -> evaluate -> worker* unfold, then prints a
 * compact summary and the protocol stats.
 */

import { buildGraph } from "../src/graph.js";
import { MockOabpClient } from "../src/mock.js";
import { defaultBuildProof } from "../src/nodes.js";
import { OabpSdk, type Mission, type OabpClient } from "../src/sdk.js";
import type { OabpStateType } from "../src/state.js";

/**
 * A slightly smarter proof builder than the default: for oracle missions it supplies a
 * resolvable deliverable (a GitHub repo URL, or a token address for "safety review" missions)
 * so the oracle branch can be demonstrated succeeding. For everything else it defers to the
 * built-in content-addressed builder. Plug your real solver in here.
 */
function exampleBuildProof(mission: Mission, agentId: string): string {
  if (mission.verification_type === "oracle") {
    const desc = (mission.verification_params?.oracle_description ?? "").toLowerCase();
    if (desc.includes("safety") || desc.includes("token")) {
      // a real token contract address would go here
      return "0x1234567890abcdef1234567890abcdef12345678";
    }
    // a real, public deliverable repo would go here
    return "https://github.com/aigen-protocol/example-go-cli";
  }
  return defaultBuildProof(mission, agentId);
}

async function main() {
  const live = process.env.OABP_LIVE === "1";
  const agentId = process.env.OABP_AGENT_ID ?? "langgraph-oabp-example";

  const client: OabpClient = live
    ? new OabpSdk({ baseUrl: process.env.OABP_BASE_URL, apiKey: process.env.OABP_API_KEY })
    : new MockOabpClient();

  console.log(`mode      : ${live ? "LIVE (real OABP API)" : "OFFLINE (mock)"}`);
  console.log(`agentId   : ${agentId}\n`);

  const graph = buildGraph({ client, buildProof: exampleBuildProof });

  // Stream in "values" mode: each chunk is the full accumulated state, so the LAST chunk is
  // the final state. We print each node's freshly-appended log lines as the run unfolds, then
  // reuse that same final state for the summary (single pass — no second invoke).
  let final: OabpStateType | undefined;
  let printedLogs = 0;
  const stream = await graph.stream(
    { agentId, minRewardAigen: 1 },
    { recursionLimit: 50, streamMode: "values" }
  );
  for await (const chunk of stream) {
    const state = chunk as OabpStateType;
    final = state;
    const logs = state.log ?? [];
    for (let k = printedLogs; k < logs.length; k++) console.log(`  ${logs[k]}`);
    printedLogs = logs.length;
  }
  if (!final) throw new Error("graph produced no state");

  console.log("\n=== summary ===");
  console.log(`discovered : ${final.missions.length} open missions`);
  console.log(`claimable  : ${final.claimable.length}`);
  for (const r of final.results) {
    const verdict = r.submitted ? (r.accepted ? "ACCEPTED" : "submitted") : `FAILED(${r.error})`;
    console.log(`  - ${r.missionId.padEnd(18)} ${verdict.padEnd(18)} proof="${r.proof}"`);
  }
  if (final.errors.length) console.log(`errors     : ${final.errors.join("; ")}`);

  try {
    const stats = await client.getStats();
    console.log(
      `\nprotocol   : resolved=${stats.resolved} open=${stats.open} ` +
        `aigen_paid=${stats.lifetime_reward_aigen_paid}`
    );
  } catch (e) {
    console.log(`\nprotocol   : stats unavailable (${(e as Error).message})`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
