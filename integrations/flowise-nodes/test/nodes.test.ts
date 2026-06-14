/**
 * Tests for the flowise-oabp Tool nodes.
 *
 * Uses Node's built-in test runner (`node:test`) + `node:assert` — no network, no LLM, no Flowise
 * runtime. Run with:  npm test  (tsc -p tsconfig.test.json && node --test dist-test/test/)
 *
 * Core acceptance check (per spec): instantiate `OabpSubmitMission_Tools`, call `init()` with a
 * MOCK client injected via `options.oabpClient`, and assert the returned tool's `func` submits to
 * the client AND returns the mission id. We also assert each node implements `INode`
 * (label/name/type/baseClasses) and that `init()` returns a tool carrying a zod schema, across all
 * four node classes.
 */

import test from "node:test";
import assert from "node:assert/strict";

import { DynamicStructuredTool } from "@langchain/core/tools";

import { OabpListMissions_Tools } from "../src/nodes/OabpListMissions/OabpListMissions.js";
import { OabpCreateMission_Tools } from "../src/nodes/OabpCreateMission/OabpCreateMission.js";
import { OabpSubmitMission_Tools } from "../src/nodes/OabpSubmitMission/OabpSubmitMission.js";
import { OabpStats_Tools } from "../src/nodes/OabpStats/OabpStats.js";
import { MockOabpClient } from "../src/mock.js";
import { netReward, FEE_RATE } from "../src/tools.js";
import type { ICommonObject, INode, INodeData } from "../src/flowise-types.js";

/** Minimal INodeData a node needs at init() time. */
function nodeData(name: string, type: string): INodeData {
  return { id: `${name}_0`, label: name, name, type, inputs: {} };
}

/** Call a LangChain tool's func with validated args (what a Flowise agent does under the hood). */
async function callTool(tool: DynamicStructuredTool, args: Record<string, unknown>): Promise<string> {
  // `invoke` runs zod validation + the func, returning the (string) tool output.
  const out = await tool.invoke(args);
  return typeof out === "string" ? out : JSON.stringify(out);
}

const ALL_NODE_CLASSES = [
  OabpListMissions_Tools,
  OabpCreateMission_Tools,
  OabpSubmitMission_Tools,
  OabpStats_Tools,
] as const;

test(">= 4 node classes, each implementing INode (label/name/type/baseClasses) in the Tools category", () => {
  assert.ok(ALL_NODE_CLASSES.length >= 4, "at least 4 node classes exported");
  const seenTypes = new Set<string>();
  for (const Cls of ALL_NODE_CLASSES) {
    const node: INode = new Cls();
    assert.equal(typeof node.label, "string", "label is a string");
    assert.ok(node.label.length > 0, "label non-empty");
    assert.equal(typeof node.name, "string", "name is a string");
    assert.ok(node.name.length > 0, "name non-empty");
    assert.equal(typeof node.type, "string", "type is a string");
    assert.ok(node.type.length > 0, "type non-empty");
    assert.ok(Array.isArray(node.baseClasses), "baseClasses is an array");
    assert.ok(node.baseClasses.includes("Tool"), `${node.name} baseClasses includes 'Tool'`);
    assert.equal(node.category, "Tools", "category is 'Tools'");
    assert.equal(typeof node.init, "function", "init is a function");
    assert.equal(typeof node.version, "number", "version is a number");
    // credential descriptor is a 'credential'-typed input
    assert.ok(node.credential, `${node.name} exposes a credential input`);
    assert.equal(node.credential!.type, "credential");
    assert.deepEqual(node.credential!.credentialNames, ["oabpApi"]);
    assert.ok(!seenTypes.has(node.type), `node.type '${node.type}' is unique`);
    seenTypes.add(node.type);
  }
});

test("each node.init() returns a DynamicStructuredTool whose schema is a zod schema", async () => {
  const client = new MockOabpClient();
  const options: ICommonObject = { oabpClient: client };
  for (const Cls of ALL_NODE_CLASSES) {
    const node = new Cls();
    const tool = (await node.init(nodeData(node.name, node.type), "", options)) as DynamicStructuredTool;
    assert.ok(tool instanceof DynamicStructuredTool, `${node.name}.init() returns a DynamicStructuredTool`);
    assert.equal(typeof tool.name, "string", "tool has a name");
    assert.ok(tool.description.length > 0, "tool has a description");
    // A zod schema exposes safeParse; this proves it's really a zod schema, not a bare object.
    assert.equal(typeof (tool.schema as { safeParse?: unknown }).safeParse, "function", `${node.name} tool.schema is zod`);
    assert.equal(typeof tool.func, "function", "tool has a func");
  }
});

test("ACCEPTANCE: OabpSubmitMission_Tools.init(mock).func submits and returns the mission id", async () => {
  const client = new MockOabpClient({ missions: [] });
  // Create a first_valid_match mission directly on the mock so we have a concrete id to submit to.
  const mission = await client.createMission({
    creator_agent_id: "creator-agent",
    title: "Emit a build token",
    description: "Reply with BUILD-<4 digits>.",
    reward_amount: 40,
    reward_currency: "AIGEN",
    verification_type: "first_valid_match",
    verification_params: { regex: "^BUILD-\\d{4}$" },
    deadline_hours: 24,
  });

  const node = new OabpSubmitMission_Tools();
  const tool = (await node.init(
    nodeData("oabpSubmitMission", "OabpSubmitMission"),
    "",
    { oabpClient: client } as ICommonObject
  )) as DynamicStructuredTool;

  assert.equal(tool.name, "oabp_submit_mission");

  // Run the tool's func with a content-addressed proof that satisfies the regex.
  const raw = await callTool(tool, {
    mission_id: mission.id,
    submitter_agent_id: "worker-agent",
    proof: "BUILD-0007",
  });
  const result = JSON.parse(raw) as { accepted: boolean; mission_id: string; detail?: string };

  // The tool submitted to the injected client...
  assert.equal(client.submitCalls.length, 1, "func submitted exactly once");
  assert.equal(client.submitCalls[0].missionId, mission.id, "submitted to the right mission");
  assert.equal(client.submitCalls[0].agentId, "worker-agent");
  assert.equal(client.submitCalls[0].proof, "BUILD-0007");

  // ...and returned the mission id (acceptance) plus the accept decision.
  assert.equal(result.mission_id, mission.id, "tool result carries the mission id");
  assert.equal(result.accepted, true, `proof accepted; detail=${result.detail}`);

  // And the mock recorded the submitter as the resolved winner (real verification, not a stub).
  const detail = await client.getMission(mission.id);
  assert.equal(detail.status, "resolved");
  assert.equal(detail.resolution?.winner_agent_id, "worker-agent");
});

test("submit tool REJECTS a proof that does not match the regex (real verification)", async () => {
  const client = new MockOabpClient({ missions: [] });
  const mission = await client.createMission({
    creator_agent_id: "creator-agent",
    title: "Strict token",
    description: "must match",
    reward_amount: 10,
    reward_currency: "AIGEN",
    verification_type: "first_valid_match",
    verification_params: { regex: "^BUILD-\\d{4}$" },
    deadline_hours: 24,
  });
  const node = new OabpSubmitMission_Tools();
  const tool = (await node.init(
    nodeData("oabpSubmitMission", "OabpSubmitMission"),
    "",
    { oabpClient: client } as ICommonObject
  )) as DynamicStructuredTool;

  const raw = await callTool(tool, {
    mission_id: mission.id,
    submitter_agent_id: "worker-agent",
    proof: "not-a-build-token",
  });
  const result = JSON.parse(raw) as { accepted: boolean };
  assert.equal(result.accepted, false, "junk proof rejected");
  const detail = await client.getMission(mission.id);
  assert.notEqual(detail.status, "resolved", "rejected proof does not resolve the mission");
});

test("create tool posts a mission and surfaces net reward after the 0.5% fee", async () => {
  const client = new MockOabpClient({ missions: [] });
  const node = new OabpCreateMission_Tools();
  const tool = (await node.init(
    nodeData("oabpCreateMission", "OabpCreateMission"),
    "",
    { oabpClient: client } as ICommonObject
  )) as DynamicStructuredTool;

  const raw = await callTool(tool, {
    creator_agent_id: "creator-agent",
    title: "Ship a repo",
    description: "public GitHub repo with a Go CLI",
    reward_amount: 100,
    reward_currency: "USDC",
    verification_type: "oracle",
    verification_params: { oracle_description: "GitHub repo deliverable, Go language" },
    deadline_hours: 48,
  });
  const result = JSON.parse(raw) as { mission_id: string; net_reward: number; fee: number };

  assert.equal(client.createCalls.length, 1, "create posted exactly once");
  assert.equal(client.createCalls[0].verification_type, "oracle");
  assert.ok(result.mission_id, "create tool returns the new mission id");
  assert.equal(result.net_reward, netReward(100), "net reward computed with the 0.5% fee");
  assert.equal(result.net_reward, 100 * (1 - FEE_RATE));
  assert.equal(result.fee, 0.5, "fee is 0.5% of 100");
});

test("list & stats tools round-trip through the injected client", async () => {
  const client = new MockOabpClient(); // 3 default seed missions
  const listNode = new OabpListMissions_Tools();
  const listTool = (await listNode.init(
    nodeData("oabpListMissions", "OabpListMissions"),
    "",
    { oabpClient: client } as ICommonObject
  )) as DynamicStructuredTool;
  const listRaw = await callTool(listTool, {});
  const list = JSON.parse(listRaw) as { count: number; missions: unknown[] };
  assert.equal(list.count, 3, "lists the 3 open seed missions");
  assert.equal(list.missions.length, 3);

  const statsNode = new OabpStats_Tools();
  const statsTool = (await statsNode.init(
    nodeData("oabpStats", "OabpStats"),
    "",
    { oabpClient: client } as ICommonObject
  )) as DynamicStructuredTool;
  const statsRaw = await callTool(statsTool, {});
  const stats = JSON.parse(statsRaw) as { stats: { open: number; resolved: number } };
  assert.equal(stats.stats.open, 3);
  assert.equal(stats.stats.resolved, 0);
});

test("init() without an injected client builds a live OabpSdk (no network call made here)", async () => {
  // No oabpClient in options and no credential -> a real OabpSdk pointed at the public deployment.
  // We only assert a tool is produced; we do NOT invoke it (that would hit the network).
  const node = new OabpStats_Tools();
  const tool = (await node.init(nodeData("oabpStats", "OabpStats"), "", {})) as DynamicStructuredTool;
  assert.ok(tool instanceof DynamicStructuredTool);
  assert.equal(tool.name, "oabp_stats");
});
