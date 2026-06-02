/**
 * End-to-end demo of @aigen/plugin-oabp WITHOUT a full ElizaOS runtime or a model.
 *
 * It builds a minimal `IAgentRuntime` (just `agentId`, `character`, `getSetting`, and an injected
 * OABP client), then drives the plugin's pieces directly — exactly how the ElizaOS agent loop would
 * call them:
 *
 *   1. oabpMarketplaceProvider.get(...)   -> the context the model would see
 *   2. LIST_OABP_MISSIONS handler         -> list open missions
 *   3. SUBMIT_OABP_MISSION handler        -> claim one (content-addressed proof)
 *   4. claimedMissionsEvaluator.handler   -> record the claim in the ledger
 *
 * OFFLINE by default (MockOabpClient, zero network). Set OABP_LIVE=1 to hit the real API at
 * OABP_BASE_URL (default https://cryptogenesis.duckdns.org) with OABP_AGENT_ID.
 *
 *   node dist-test/examples/run.js
 *   OABP_LIVE=1 OABP_AGENT_ID=my-agent node dist-test/examples/run.js
 */

import { oabpMarketplaceProvider } from "../src/provider.js";
import { listOabpMissionsAction, submitOabpMissionAction } from "../src/actions.js";
import { claimedMissionsEvaluator, getClaimLedger } from "../src/evaluator.js";
import { MockOabpClient } from "../src/mock.js";
import { OabpSdk } from "../src/sdk.js";
import type { OabpClient } from "../src/sdk.js";
import type { Content, HandlerCallback, IAgentRuntime, Memory } from "../src/eliza-types.js";

const LIVE = process.env.OABP_LIVE === "1";
const AGENT = process.env.OABP_AGENT_ID || "elizaos-oabp-example";
const BASE_URL = process.env.OABP_BASE_URL || "https://cryptogenesis.duckdns.org";

function makeRuntime(client: OabpClient): IAgentRuntime {
  const settings: Record<string, string> = { OABP_AGENT_ID: AGENT, OABP_BASE_URL: BASE_URL };
  const rt = {
    agentId: AGENT,
    character: { name: "OABP Hunter (example)" },
    getSetting: (k: string) => settings[k],
  } as IAgentRuntime;
  (rt as unknown as { __oabpClient: OabpClient }).__oabpClient = client;
  return rt;
}

function logCallback(tag: string): HandlerCallback {
  return async (content: Content) => {
    console.log(`  ${tag}: ${content.text}`);
    return [];
  };
}

const msg = (text: string): Memory => ({ content: { text } });

async function main(): Promise<void> {
  console.log(`mode      : ${LIVE ? `LIVE (${BASE_URL})` : "OFFLINE (mock)"}`);
  console.log(`agentId   : ${AGENT}\n`);

  const client: OabpClient = LIVE ? new OabpSdk({ baseUrl: BASE_URL }) : new MockOabpClient();
  const runtime = makeRuntime(client);

  // 1) What the model would see injected by the provider.
  const ctx = await oabpMarketplaceProvider.get(runtime, msg("hi"), {});
  console.log("--- provider context (injected into agent state) ---");
  console.log(ctx.text);
  console.log();

  // 2) LIST.
  console.log("--- LIST_OABP_MISSIONS ---");
  const listOut = (await listOabpMissionsAction.handler(
    runtime,
    msg("what missions are open?"),
    undefined,
    undefined,
    logCallback("list")
  )) as Content;
  const missions = (listOut.missions as { id: string; verification_type: string }[]) ?? [];

  // 3) SUBMIT — pick a content-addressed (first_valid_match) mission we can deterministically win.
  const target =
    missions.find((m) => m.verification_type === "first_valid_match") ?? missions[0];
  if (!target) {
    console.log("\n(no open missions to submit to)");
    return;
  }
  console.log(`\n--- SUBMIT_OABP_MISSION (${target.id}) ---`);
  // For the offline mock's demo-fvm regex ^BUILD-\d{4}$, BUILD-0000 is a valid content-addressed proof.
  const proof = "BUILD-0000";
  const submitOut = (await submitOabpMissionAction.handler(
    runtime,
    msg(`submit mission ${target.id} proof: ${proof}`),
    undefined,
    undefined,
    logCallback("submit")
  )) as Content;

  // 4) Evaluator records the claim.
  await claimedMissionsEvaluator.handler(
    runtime,
    msg(`OABP mission ${target.id}`),
    undefined,
    undefined,
    undefined,
    [{ content: submitOut }]
  );

  console.log("\n=== claim ledger ===");
  for (const rec of getClaimLedger(AGENT)) {
    console.log(`  ${rec.missionId}  accepted=${rec.accepted}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
