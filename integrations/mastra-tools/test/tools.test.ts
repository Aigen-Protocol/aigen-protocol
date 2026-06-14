/**
 * Tests for the Mastra OABP integration.
 *
 * Uses Node's built-in test runner (`node:test`) + `node:assert` — no network, no LLM, no extra
 * deps beyond Mastra + zod. Run with:  npm test  (tsc -p tsconfig.test.json && node --test dist-test/test/)
 *
 * Core acceptance check (per spec): build the tools against {@link MockOabpClient}, run
 * create + submit on a `first_valid_match` mission, and assert the mock recorded a WINNER.
 *
 * Mastra tools expose `execute({ context, runtimeContext, ... })` where `context` is the
 * zod-validated input. We call that directly with a real `RuntimeContext`, which exercises the
 * exact code path an Agent would, without needing a model.
 */

import test from "node:test";
import assert from "node:assert/strict";

import { RuntimeContext } from "@mastra/core/runtime-context";

import { createOabpTools, netReward, FEE_RATE } from "../src/tools.js";
import { MockOabpClient } from "../src/mock.js";
import { createOabpAgent } from "../src/agent.js";

const AGENT = "test-agent";

/**
 * Invoke a Mastra tool's `execute` with a validated input object, exactly as the agent runtime
 * would. Returns the tool's typed output.
 */
async function run<T>(tool: { execute?: (...args: any[]) => Promise<T> }, input: unknown): Promise<T> {
  assert.equal(typeof tool.execute, "function", "tool must have an execute()");
  const runtimeContext = new RuntimeContext();
  return tool.execute!({ context: input, runtimeContext, mastra: undefined });
}

test("every tool has a zod inputSchema and a callable execute", () => {
  const tools = createOabpTools(new MockOabpClient());
  const ids = Object.keys(tools);
  assert.deepEqual(
    ids.sort(),
    [
      "oabp_a2a_send",
      "oabp_create_mission",
      "oabp_get_mission",
      "oabp_get_reputation",
      "oabp_get_stats",
      "oabp_list_missions",
      "oabp_submit_mission",
    ],
    "exact tool id set"
  );
  for (const [id, tool] of Object.entries(tools)) {
    assert.equal(tool.id, id, `tool.id matches record key for ${id}`);
    assert.ok(tool.inputSchema, `${id} has an inputSchema`);
    // A zod schema exposes safeParse; this proves it's really a zod schema, not a bare object.
    assert.equal(typeof (tool.inputSchema as any).safeParse, "function", `${id} inputSchema is zod`);
    assert.ok(tool.outputSchema, `${id} has an outputSchema`);
    assert.equal(typeof tool.execute, "function", `${id} has execute`);
  }
});

test("ACCEPTANCE: create + submit on a first_valid_match mission records a winner", async () => {
  const client = new MockOabpClient({ missions: [] }); // empty board, we create our own
  const tools = createOabpTools(client);

  // 1) Create a first_valid_match mission.
  const created = await run(tools.oabp_create_mission, {
    creator_agent_id: "creator-agent",
    title: "Emit a build token",
    description: "Reply with BUILD-<4 digits>.",
    reward_amount: 40,
    reward_currency: "AIGEN",
    verification_type: "first_valid_match",
    verification_params: { regex: "^BUILD-\\d{4}$" },
    deadline_hours: 24,
  });
  const missionId = created.mission.id;
  assert.ok(missionId, "created mission has an id");
  assert.equal(created.mission.verification_type, "first_valid_match");
  // Net-reward accounting (0.5% fee) is surfaced by the create tool.
  assert.equal(created.net_reward, netReward(40));
  assert.equal(created.net_reward, 40 * (1 - FEE_RATE));

  // 2) Submit a content-addressed proof that satisfies the regex.
  const submit = await run(tools.oabp_submit_mission, {
    mission_id: missionId,
    submitter_agent_id: AGENT,
    proof: "BUILD-0007",
  });
  assert.equal(submit.accepted, true, `proof should be accepted; detail=${submit.detail}`);
  assert.equal(submit.mission_id, missionId);

  // 3) The mock recorded a WINNER on the resolved mission.
  const detail = await client.getMission(missionId);
  assert.equal(detail.status, "resolved", "mission resolved after accepted proof");
  assert.ok(detail.resolution, "resolution present");
  assert.equal(
    detail.resolution!.winner_agent_id,
    AGENT,
    "the submitting agent is recorded as the winner"
  );

  // 4) The submit tool itself proves the submit happened against the client.
  assert.equal(client.submitCalls.length, 1);
  assert.equal(client.submitCalls[0].missionId, missionId);

  // 5) Reputation reflects the win, fed by the same ledger.
  const repTool = await run(tools.oabp_get_reputation, { agent_id: AGENT });
  assert.equal(repTool.reputation.missions_won, 1, "winner has 1 win");
  assert.equal(repTool.reputation.aigen_earned, 40, "AIGEN earned tallied");
});

test("submit is REJECTED when the proof does not match the regex (real verification, not a stub)", async () => {
  const client = new MockOabpClient({ missions: [] });
  const tools = createOabpTools(client);
  const created = await run(tools.oabp_create_mission, {
    creator_agent_id: "creator-agent",
    title: "Strict token",
    description: "must match",
    reward_amount: 10,
    reward_currency: "AIGEN",
    verification_type: "first_valid_match",
    verification_params: { regex: "^BUILD-\\d{4}$" },
    deadline_hours: 24,
  });
  const submit = await run(tools.oabp_submit_mission, {
    mission_id: created.mission.id,
    submitter_agent_id: AGENT,
    proof: "not-a-build-token",
  });
  assert.equal(submit.accepted, false, "junk proof must be rejected");
  const detail = await client.getMission(created.mission.id);
  assert.notEqual(detail.status, "resolved", "rejected proof does not resolve the mission");
  assert.equal(detail.resolution, undefined, "no winner recorded for a rejected proof");
});

test("oracle mission: GitHub repo URL is accepted, plain text is not", async () => {
  const client = new MockOabpClient({ missions: [] });
  const tools = createOabpTools(client);
  const created = await run(tools.oabp_create_mission, {
    creator_agent_id: "creator-agent",
    title: "Ship a repo",
    description: "public GitHub repo",
    reward_amount: 5,
    reward_currency: "USDC",
    verification_type: "oracle",
    verification_params: { oracle_description: "GitHub repo deliverable" },
    deadline_hours: 48,
  });

  const bad = await run(tools.oabp_submit_mission, {
    mission_id: created.mission.id,
    submitter_agent_id: AGENT,
    proof: "trust me it exists",
  });
  assert.equal(bad.accepted, false, "non-URL proof rejected by GitHub oracle");

  const good = await run(tools.oabp_submit_mission, {
    mission_id: created.mission.id,
    submitter_agent_id: AGENT,
    proof: "https://github.com/aigen-protocol/example-go-cli",
  });
  assert.equal(good.accepted, true, "GitHub repo URL accepted by oracle");
  const detail = await client.getMission(created.mission.id);
  assert.equal(detail.resolution?.winner_agent_id, AGENT);
});

test("list / stats / a2a tools round-trip through the client", async () => {
  const client = new MockOabpClient(); // 3 default seed missions
  const tools = createOabpTools(client);

  const list = await run(tools.oabp_list_missions, {});
  assert.equal(list.missions.length, 3, "lists the 3 open seed missions");

  const get = await run(tools.oabp_get_mission, { mission_id: "demo-fvm" });
  assert.equal(get.mission.id, "demo-fvm");
  assert.equal(get.mission.verification_params.regex, "^BUILD-\\d{4}$");

  const stats = await run(tools.oabp_get_stats, {});
  assert.equal(stats.stats.open, 3);
  assert.equal(stats.stats.resolved, 0);

  const a2a = await run(tools.oabp_a2a_send, { message: "hello" });
  assert.equal(a2a.response.jsonrpc, "2.0");
});

test("createOabpAgent builds an Agent wired to the OABP tools (offline mock client)", () => {
  // A minimal fake model object is enough to construct the Agent; we don't call the LLM here.
  const fakeModel = {
    specificationVersion: "v1",
    provider: "test",
    modelId: "fake",
    doGenerate: async () => ({ text: "" }),
    doStream: async () => ({ stream: undefined }),
  } as unknown as Parameters<typeof createOabpAgent>[0]["model"];

  const agent = createOabpAgent({
    model: fakeModel,
    name: "Test OABP Agent",
    agentId: "test-agent",
    client: new MockOabpClient(),
  });
  assert.equal(typeof agent.generate, "function", "agent exposes generate()");
  assert.equal(agent.name, "Test OABP Agent");
});
