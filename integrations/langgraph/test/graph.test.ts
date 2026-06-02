/**
 * Tests for the LangGraph OABP integration.
 *
 * Uses Node's built-in test runner (`node:test`) + `node:assert` — no network, no extra deps.
 * Run with:  npm test   (which does: tsc && node --test dist-test/)
 *
 * Core acceptance check: `buildGraph()` compiles and runs one tick against the mock SDK,
 * and the worker submits exactly the missions the evaluator deemed claimable.
 */

import test from "node:test";
import assert from "node:assert/strict";

import { buildGraph, build_graph, runOnce } from "../src/graph.js";
import { MockOabpClient } from "../src/mock.js";
import { defaultBuildProof, scoreMission, sampleStringForRegex } from "../src/nodes.js";
import type { Mission } from "../src/sdk.js";
import type { OabpStateType } from "../src/state.js";

const AGENT = "test-agent";

test("buildGraph compiles and exposes a CompiledStateGraph", () => {
  const client = new MockOabpClient();
  const graph = buildGraph({ client });
  assert.equal(typeof graph.invoke, "function");
  assert.equal(typeof graph.stream, "function");
  assert.equal(build_graph, buildGraph, "snake_case alias must equal camelCase");
});

test("one tick: discover -> evaluate -> worker routes claimable missions and submits them", async () => {
  const client = new MockOabpClient();
  const graph = buildGraph({ client });

  const final = (await graph.invoke({ agentId: AGENT })) as OabpStateType;

  // Discovered the 3 open seed missions.
  assert.equal(final.missions.length, 3);

  // Evaluator marks fvm + oracle claimable; peer_vote is not.
  const claimableIds = final.claimable.map((e) => e.mission.id).sort();
  assert.deepEqual(claimableIds, ["demo-fvm", "demo-oracle-repo"]);

  // Worker submitted exactly the claimable ones (cursor walked the whole list).
  assert.equal(final.results.length, 2);
  assert.equal(final.cursor, 2);
  assert.equal(client.submitCalls.length, 2);
  for (const id of ["demo-fvm", "demo-oracle-repo"]) {
    assert.ok(
      client.submitCalls.some((c) => c.missionId === id),
      `expected a submit for ${id}`
    );
  }

  // The first_valid_match mission must be ACCEPTED (proof was content-addressed to its regex).
  const fvm = final.results.find((r) => r.missionId === "demo-fvm");
  assert.ok(fvm, "fvm result present");
  assert.equal(fvm!.submitted, true);
  assert.equal(fvm!.accepted, true, `fvm should be accepted; detail=${fvm!.detail}`);

  // No fatal errors.
  assert.deepEqual(final.errors, []);
});

test("runOnce() convenience runner returns the same final state", async () => {
  const client = new MockOabpClient();
  const final = (await runOnce({ client, recursionLimit: 25 }, { agentId: AGENT })) as OabpStateType;
  assert.equal(final.results.length, 2);
  // stats should reflect the accepted first_valid_match resolution
  const stats = await client.getStats();
  assert.ok(stats.resolved >= 1, "at least one mission resolved in the mock");
});

test("evaluator honors minRewardAigen threshold and dedupes prior submissions", async () => {
  const now = Math.floor(Date.now() / 1000);
  const small: Mission = {
    id: "tiny",
    title: "tiny reward",
    description: "below threshold",
    reward: { amount: 1, currency: "AIGEN" },
    verification_type: "first_valid_match",
    verification_params: { regex: "^OK$" },
    deadline: now + 3600,
    status: "open",
    submissions: [],
  };
  const big: Mission = {
    id: "big",
    title: "already mine",
    description: "already submitted by this agent",
    reward: { amount: 999, currency: "AIGEN" },
    verification_type: "first_valid_match",
    verification_params: { regex: "^OK$" },
    deadline: now + 3600,
    status: "open",
    submissions: [{ submitter_agent_id: AGENT, proof: "OK" }],
  };
  const client = new MockOabpClient({ missions: [small, big] });
  const final = (await buildGraph({ client }).invoke({
    agentId: AGENT,
    minRewardAigen: 10,
  })) as OabpStateType;

  // 'tiny' filtered by threshold; 'big' filtered as already-submitted -> nothing claimable.
  assert.deepEqual(final.claimable, []);
  assert.equal(final.results.length, 0);
  assert.equal(client.submitCalls.length, 0);
});

test("scoreMission ranks USDC above AIGEN and skips subjective verification", () => {
  const now = Math.floor(Date.now() / 1000);
  const usdc = scoreMission(
    {
      id: "u",
      title: "u",
      description: "",
      reward: { amount: 5, currency: "USDC" },
      verification_type: "oracle",
      verification_params: { oracle_description: "github repo" },
      deadline: now + 3600,
      status: "open",
      submissions: [],
    },
    AGENT,
    1
  );
  const aigen = scoreMission(
    {
      id: "a",
      title: "a",
      description: "",
      reward: { amount: 50, currency: "AIGEN" },
      verification_type: "first_valid_match",
      verification_params: { regex: "^x$" },
      deadline: now + 3600,
      status: "open",
      submissions: [],
    },
    AGENT,
    1
  );
  assert.ok(usdc.score > aigen.score, "5 USDC should outrank 50 AIGEN");
  assert.equal(usdc.claimable, true);

  const peer = scoreMission(
    {
      id: "p",
      title: "p",
      description: "",
      reward: { amount: 1000, currency: "AIGEN" },
      verification_type: "peer_vote",
      verification_params: {},
      deadline: now + 3600,
      status: "open",
      submissions: [],
    },
    AGENT,
    1
  );
  assert.equal(peer.claimable, false, "peer_vote must not be auto-claimed");
});

test("defaultBuildProof produces a regex-satisfying proof for first_valid_match", () => {
  const m: Mission = {
    id: "x",
    title: "x",
    description: "",
    reward: { amount: 1, currency: "AIGEN" },
    verification_type: "first_valid_match",
    verification_params: { regex: "^BUILD-\\d{4}$" },
    deadline: Math.floor(Date.now() / 1000) + 3600,
    status: "open",
    submissions: [],
  };
  const proof = defaultBuildProof(m, AGENT);
  assert.match(proof, /^BUILD-\d{4}$/);
});

test("sampleStringForRegex handles common patterns and bails safely on hard ones", () => {
  assert.match(sampleStringForRegex("^BUILD-\\d{4}$")!, /^BUILD-\d{4}$/);
  assert.match(sampleStringForRegex("^[a-z]{3}$")!, /^[a-z]{3}$/);
  // alternation/groups are not safely sampleable -> null (worker then falls back gracefully)
  assert.equal(sampleStringForRegex("^(cat|dog)$"), null);
});
