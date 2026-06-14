/**
 * Tests for the Vercel AI SDK OABP integration.
 *
 * Uses Node's built-in test runner (`node:test`) + `node:assert` — no network, no LLM, no extra
 * deps beyond `ai` + `zod`. Run with:  npm test  (tsc -p tsconfig.test.json && node --test dist-test/test/)
 *
 * Core acceptance check (per spec): build the tools against {@link MockOabpClient}, run
 * create + submit on a `first_valid_match` mission, and assert the submit tool's `execute`
 * resolves a WINNER. We call `tool.execute(args, options)` directly with a minimal
 * ToolExecutionOptions — the exact code path `generateText` uses when the model emits a tool call,
 * without needing a model.
 */

import test from "node:test";
import assert from "node:assert/strict";

import type { Tool } from "ai";

import { oabpTools, netReward, FEE_RATE } from "../src/tools.js";
import { MockOabpClient } from "../src/mock.js";

const AGENT = "test-agent";

/** Minimal ToolExecutionOptions, as `generateText` supplies on every tool call. */
function execOpts(toolName: string) {
  return {
    toolCallId: `call-${toolName}-${Math.random().toString(36).slice(2, 8)}`,
    messages: [] as never[],
    abortSignal: undefined,
  };
}

/**
 * Invoke a Vercel AI SDK tool's `execute` with a validated input object, exactly as the agent
 * runtime would (args first, options second). Returns the tool's output.
 */
async function run<T = any>(tool: Tool, input: unknown, name = "tool"): Promise<T> {
  assert.equal(typeof tool.execute, "function", `${name} must have an execute()`);
  // `execute` is (args, options) in the AI SDK; both are required at the call site.
  return (tool.execute as (a: unknown, o: unknown) => Promise<T>)(input, execOpts(name));
}

test("oabpTools() returns a record of >=6 tools, each with description + parameters(zod) + execute", () => {
  const tools = oabpTools(new MockOabpClient());
  const keys = Object.keys(tools);

  assert.ok(keys.length >= 6, `expected >=6 tools, got ${keys.length}`);
  assert.deepEqual(
    keys.sort(),
    [
      "oabp_a2a_send",
      "oabp_create_mission",
      "oabp_get_mission",
      "oabp_get_reputation",
      "oabp_get_stats",
      "oabp_list_missions",
      "oabp_submit_mission",
    ],
    "exact tool key set"
  );

  for (const [key, t] of Object.entries(tools) as [string, Tool][]) {
    assert.equal(typeof t.description, "string", `${key} has a description`);
    assert.ok((t.description as string).length > 0, `${key} description non-empty`);
    // The AI SDK stores the input schema under `parameters`.
    const params = (t as { parameters?: unknown }).parameters;
    assert.ok(params, `${key} has parameters`);
    // A zod schema exposes safeParse; this proves it's really a zod schema, not a bare object.
    assert.equal(
      typeof (params as { safeParse?: unknown }).safeParse,
      "function",
      `${key} parameters is a zod schema`
    );
    assert.equal(typeof t.execute, "function", `${key} has execute`);
  }
});

test("oabpTools() defaults its client to the live SDK (callable with no args)", () => {
  const tools = oabpTools();
  assert.equal(typeof tools.oabp_submit_mission.execute, "function");
  assert.ok(Object.keys(tools).length >= 6);
});

test("ACCEPTANCE: the submit tool's execute resolves a WINNER on a first_valid_match mission", async () => {
  const client = new MockOabpClient({ missions: [] }); // empty board, we create our own
  const tools = oabpTools(client);

  // 1) Create a first_valid_match mission.
  const created = await run(
    tools.oabp_create_mission,
    {
      creator_agent_id: "creator-agent",
      title: "Emit a build token",
      description: "Reply with BUILD-<4 digits>.",
      reward_amount: 40,
      reward_currency: "AIGEN",
      verification_type: "first_valid_match",
      verification_params: { regex: "^BUILD-\\d{4}$" },
      deadline_hours: 24,
    },
    "oabp_create_mission"
  );
  const missionId = created.mission.id as string;
  assert.ok(missionId, "created mission has an id");
  assert.equal(created.mission.verification_type, "first_valid_match");
  // Net-reward accounting (0.5% fee) is surfaced by the create tool.
  assert.equal(created.net_reward, netReward(40));
  assert.equal(created.net_reward, 40 * (1 - FEE_RATE));

  // 2) Submit a content-addressed proof that satisfies the regex (this is the claim).
  const submit = await run(
    tools.oabp_submit_mission,
    { mission_id: missionId, submitter_agent_id: AGENT, proof: "BUILD-0007" },
    "oabp_submit_mission"
  );
  assert.equal(submit.accepted, true, `proof should be accepted; detail=${submit.detail}`);
  assert.equal(submit.mission_id, missionId);

  // 3) The mock recorded a WINNER on the now-resolved mission.
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
  const rep = await run(
    tools.oabp_get_reputation,
    { agent_id: AGENT },
    "oabp_get_reputation"
  );
  assert.equal(rep.reputation.missions_won, 1, "winner has 1 win");
  assert.equal(rep.reputation.aigen_earned, 40, "AIGEN earned tallied");
});

test("submit is REJECTED when the proof does not match the regex (real verification, not a stub)", async () => {
  const client = new MockOabpClient({ missions: [] });
  const tools = oabpTools(client);
  const created = await run(
    tools.oabp_create_mission,
    {
      creator_agent_id: "creator-agent",
      title: "Strict token",
      description: "must match",
      reward_amount: 10,
      reward_currency: "AIGEN",
      verification_type: "first_valid_match",
      verification_params: { regex: "^BUILD-\\d{4}$" },
      deadline_hours: 24,
    },
    "oabp_create_mission"
  );
  const submit = await run(
    tools.oabp_submit_mission,
    { mission_id: created.mission.id, submitter_agent_id: AGENT, proof: "not-a-build-token" },
    "oabp_submit_mission"
  );
  assert.equal(submit.accepted, false, "junk proof must be rejected");
  const detail = await client.getMission(created.mission.id);
  assert.notEqual(detail.status, "resolved", "rejected proof does not resolve the mission");
  assert.equal(detail.resolution, undefined, "no winner recorded for a rejected proof");
});

test("oracle mission: GitHub repo URL is accepted, plain text is not", async () => {
  const client = new MockOabpClient({ missions: [] });
  const tools = oabpTools(client);
  const created = await run(
    tools.oabp_create_mission,
    {
      creator_agent_id: "creator-agent",
      title: "Ship a repo",
      description: "public GitHub repo",
      reward_amount: 5,
      reward_currency: "USDC",
      verification_type: "oracle",
      verification_params: { oracle_description: "GitHub repo deliverable" },
      deadline_hours: 48,
    },
    "oabp_create_mission"
  );

  const bad = await run(
    tools.oabp_submit_mission,
    { mission_id: created.mission.id, submitter_agent_id: AGENT, proof: "trust me it exists" },
    "oabp_submit_mission"
  );
  assert.equal(bad.accepted, false, "non-URL proof rejected by GitHub oracle");

  const good = await run(
    tools.oabp_submit_mission,
    {
      mission_id: created.mission.id,
      submitter_agent_id: AGENT,
      proof: "https://github.com/aigen-protocol/example-go-cli",
    },
    "oabp_submit_mission"
  );
  assert.equal(good.accepted, true, "GitHub repo URL accepted by oracle");
  const detail = await client.getMission(created.mission.id);
  assert.equal(detail.resolution?.winner_agent_id, AGENT);
});

test("list / get / stats / a2a tools round-trip through the client", async () => {
  const client = new MockOabpClient(); // 3 default seed missions
  const tools = oabpTools(client);

  const list = await run(tools.oabp_list_missions, {}, "oabp_list_missions");
  assert.equal(list.missions.length, 3, "lists the 3 open seed missions");

  const get = await run(tools.oabp_get_mission, { mission_id: "demo-fvm" }, "oabp_get_mission");
  assert.equal(get.mission.id, "demo-fvm");
  assert.equal(get.mission.verification_params.regex, "^BUILD-\\d{4}$");

  const stats = await run(tools.oabp_get_stats, {}, "oabp_get_stats");
  assert.equal(stats.stats.open, 3);
  assert.equal(stats.stats.resolved, 0);

  const a2a = await run(tools.oabp_a2a_send, { message: "hello" }, "oabp_a2a_send");
  assert.equal(a2a.response.jsonrpc, "2.0");
});
