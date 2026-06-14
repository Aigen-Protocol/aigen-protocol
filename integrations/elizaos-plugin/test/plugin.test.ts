/**
 * Tests for the ElizaOS OABP plugin.
 *
 * Uses Node's built-in test runner (`node:test`) + `node:assert` — NO network, NO model, NO extra
 * deps (the `@elizaos/core` surface is mirrored locally in `src/eliza-types.ts`). Run with:
 *   npm test   (which does: tsc -p tsconfig.test.json && node --test dist-test/test/)
 *
 * Core acceptance check (per spec): build a minimal `IAgentRuntime` carrying an injected
 * {@link MockOabpClient}, invoke the SUBMIT_OABP_MISSION handler with a captured `callback`, and
 * assert the callback's text contains the mission id (and the mock recorded the submission).
 */

import test from "node:test";
import assert from "node:assert/strict";

import oabpPlugin, {
  oabpPlugin as namedPlugin,
  listOabpMissionsAction,
  createOabpMissionAction,
  submitOabpMissionAction,
  oabpMarketplaceProvider,
  claimedMissionsEvaluator,
  getClaimLedger,
  resetClaimLedger,
  parseCreateRequest,
} from "../src/index.js";
import { MockOabpClient } from "../src/mock.js";
import type {
  Action,
  Content,
  HandlerCallback,
  IAgentRuntime,
  Memory,
} from "../src/eliza-types.js";
import type { OabpClient } from "../src/sdk.js";

const AGENT = "test-eliza-agent";

/** Build a minimal runtime that injects a client and serves the two documented settings. */
function makeRuntime(client: OabpClient, settings: Record<string, string> = {}): IAgentRuntime {
  const merged: Record<string, string> = { OABP_AGENT_ID: AGENT, ...settings };
  const rt = {
    agentId: AGENT,
    character: { name: "Tester" },
    getSetting(key: string): string | undefined {
      return merged[key];
    },
  } as IAgentRuntime;
  // Injected client (honored by getClient via runtime.__oabpClient).
  (rt as unknown as { __oabpClient: OabpClient }).__oabpClient = client;
  return rt;
}

/** A user message memory. */
function msg(text: string): Memory {
  return { content: { text } };
}

/** Capture callback invocations so we can assert on the emitted Content. */
function captureCallback(): { cb: HandlerCallback; calls: Content[] } {
  const calls: Content[] = [];
  const cb: HandlerCallback = async (content: Content) => {
    calls.push(content);
    return [];
  };
  return { cb, calls };
}

/* ------------------------------------------------------------------ */

test("default export is a Plugin with actions>=3, providers>=1, evaluators>=1", () => {
  assert.equal(oabpPlugin, namedPlugin, "default and named export are the same object");
  assert.equal(oabpPlugin.name, "@aigen/plugin-oabp");
  assert.ok(Array.isArray(oabpPlugin.actions));
  assert.ok((oabpPlugin.actions?.length ?? 0) >= 3, "actions[] length >= 3");
  assert.ok(Array.isArray(oabpPlugin.providers));
  assert.ok((oabpPlugin.providers?.length ?? 0) >= 1, "providers[] length >= 1");
  assert.ok((oabpPlugin.evaluators?.length ?? 0) >= 1, "evaluators[] length >= 1");
});

test("every action has validate(), handler(), and >= 1 examples entry", () => {
  const actions: Action[] = oabpPlugin.actions ?? [];
  const names = actions.map((a) => a.name).sort();
  assert.deepEqual(names, ["CREATE_OABP_MISSION", "LIST_OABP_MISSIONS", "SUBMIT_OABP_MISSION"]);
  for (const a of actions) {
    assert.equal(typeof a.validate, "function", `${a.name}.validate`);
    assert.equal(typeof a.handler, "function", `${a.name}.handler`);
    assert.ok(Array.isArray(a.examples) && a.examples.length >= 1, `${a.name}.examples >= 1`);
    // each examples entry is itself a non-empty conversation array
    for (const convo of a.examples!) {
      assert.ok(Array.isArray(convo) && convo.length >= 1, `${a.name} example convo non-empty`);
      for (const turn of convo) {
        assert.equal(typeof turn.name, "string");
        assert.ok(turn.content && typeof turn.content === "object");
      }
    }
    assert.ok(Array.isArray(a.similes) && a.similes!.length >= 1, `${a.name}.similes`);
  }
});

test("ACCEPTANCE: SUBMIT handler against a mock client -> callback text contains the mission id", async () => {
  resetClaimLedger(AGENT);
  const client = new MockOabpClient(); // seeds demo-fvm (first_valid_match ^BUILD-\d{4}$)
  const runtime = makeRuntime(client);
  const { cb, calls } = captureCallback();

  const result = (await submitOabpMissionAction.handler(
    runtime,
    msg("submit mission demo-fvm proof: BUILD-0000"),
    undefined,
    undefined,
    cb
  )) as Content;

  // The callback must have fired with text mentioning the mission id.
  assert.equal(calls.length, 1, "callback invoked exactly once");
  assert.match(calls[0].text ?? "", /demo-fvm/, "callback text contains the mission id");
  // And the same content is returned by the handler.
  assert.match(result.text ?? "", /demo-fvm/);
  assert.equal(result.missionId, "demo-fvm");

  // The mock actually recorded the submission, and the content-addressed proof was accepted.
  assert.equal(client.submitCalls.length, 1);
  assert.equal(client.submitCalls[0].missionId, "demo-fvm");
  assert.equal(client.submitCalls[0].agentId, AGENT);
  assert.equal(result.accepted, true, "BUILD-0000 satisfies ^BUILD-\\d{4}$");
  assert.match(calls[0].text ?? "", /ACCEPTED/);
});

test("SUBMIT handler with explicit options (missionId + proof) bypasses parsing", async () => {
  const client = new MockOabpClient();
  const runtime = makeRuntime(client);
  const { cb, calls } = captureCallback();

  const out = (await submitOabpMissionAction.handler(
    runtime,
    msg("please do the thing"),
    undefined,
    { missionId: "demo-oracle-repo", proof: "https://github.com/aigen-protocol/example-go-cli" },
    cb
  )) as Content;

  assert.match(calls[0].text ?? "", /demo-oracle-repo/);
  assert.equal(out.accepted, true, "github url accepted by the oracle mock");
  assert.equal(client.submitCalls[0].missionId, "demo-oracle-repo");
});

test("SUBMIT handler asks for a mission id when none is resolvable", async () => {
  const client = new MockOabpClient();
  const runtime = makeRuntime(client);
  const { cb, calls } = captureCallback();

  await submitOabpMissionAction.handler(runtime, msg("submit my proof now"), undefined, undefined, cb);
  assert.equal(client.submitCalls.length, 0, "no submit without an id");
  assert.match(calls[0].text ?? "", /which mission/i);
  // It should list the open ids to help the user.
  assert.match(calls[0].text ?? "", /demo-fvm/);
});

test("LIST handler returns open missions via the callback", async () => {
  const client = new MockOabpClient();
  const runtime = makeRuntime(client);
  const { cb, calls } = captureCallback();

  const out = (await listOabpMissionsAction.handler(
    runtime,
    msg("what missions are open?"),
    undefined,
    undefined,
    cb
  )) as Content;

  assert.match(calls[0].text ?? "", /open OABP mission/);
  assert.ok(Array.isArray(out.missions));
  // 3 seed missions are all open.
  assert.equal((out.missions as unknown[]).length, 3);
});

test("CREATE handler posts a mission and echoes its id + net reward", async () => {
  const client = new MockOabpClient();
  const runtime = makeRuntime(client);
  const { cb, calls } = captureCallback();

  const out = (await createOabpMissionAction.handler(
    runtime,
    msg("post a bounty: title: Build a Go CLI; reward 5 USDC; github repo deliverable; in 48 hours"),
    undefined,
    undefined,
    cb
  )) as Content;

  assert.match(calls[0].text ?? "", /Posted OABP mission/);
  assert.match(calls[0].text ?? "", /5 USDC/);
  assert.match(calls[0].text ?? "", /net 4\.975/); // 5 * (1 - 0.005)
  const mission = out.mission as { verification_type?: string } | undefined;
  assert.equal(mission?.verification_type, "oracle");
});

test("parseCreateRequest maps regex -> first_valid_match and safety -> oracle", () => {
  const fvm = parseCreateRequest("reward 25 AIGEN, proof must match regex /^BUILD-\\d{4}$/ in 24h");
  assert.equal(fvm.verification_type, "first_valid_match");
  assert.equal(fvm.verification_params.regex, "^BUILD-\\d{4}$");
  assert.equal(fvm.reward_amount, 25);
  assert.equal(fvm.reward_currency, "AIGEN");

  const safety = parseCreateRequest("create a token-security safety review bounty, 10 USDC, in 2 days");
  assert.equal(safety.verification_type, "oracle");
  assert.match(safety.verification_params.oracle_description ?? "", /GoPlus|safety/i);
  assert.equal(safety.reward_currency, "USDC");
  assert.equal(safety.deadline_hours, 48);
});

test("validators gate on intent", async () => {
  const client = new MockOabpClient();
  const runtime = makeRuntime(client);
  assert.equal(await listOabpMissionsAction.validate(runtime, msg("show me open bounties")), true);
  assert.equal(await listOabpMissionsAction.validate(runtime, msg("what's the weather")), false);
  assert.equal(await createOabpMissionAction.validate(runtime, msg("post a new bounty")), true);
  assert.equal(await submitOabpMissionAction.validate(runtime, msg("claim mission m-1")), true);
  assert.equal(await submitOabpMissionAction.validate(runtime, msg("hello there")), false);
});

test("provider injects open-mission context into state", async () => {
  const client = new MockOabpClient();
  const runtime = makeRuntime(client);
  const res = await oabpMarketplaceProvider.get(runtime, msg("hi"), {});
  assert.match(res.text ?? "", /OABP marketplace/);
  assert.match(res.text ?? "", /demo-fvm/);
  assert.equal(res.values?.oabp_open_count, 3);
  assert.ok(Array.isArray((res.values as { oabp_open_mission_ids?: unknown }).oabp_open_mission_ids));
  assert.ok(Array.isArray((res.data as { missions?: unknown[] }).missions));
});

test("evaluator records claimed missions in the per-agent ledger", async () => {
  resetClaimLedger(AGENT);
  const client = new MockOabpClient();
  const runtime = makeRuntime(client);

  // Simulate the agent having just submitted: the response memory carries the SUBMIT content.
  const responses: Memory[] = [
    {
      content: {
        text: "Submitted deliverable to OABP mission demo-fvm: ACCEPTED ✅ — regex matched",
        actions: ["SUBMIT_OABP_MISSION"],
        missionId: "demo-fvm",
        accepted: true,
      },
    },
  ];
  const triggering = msg("submit mission demo-fvm proof: BUILD-0000");

  assert.equal(await claimedMissionsEvaluator.validate(runtime, triggering), true);
  const recorded = (await claimedMissionsEvaluator.handler(
    runtime,
    triggering,
    undefined,
    undefined,
    undefined,
    responses
  )) as Array<{ missionId: string; accepted: boolean | null }>;

  assert.equal(recorded.length, 1);
  assert.equal(recorded[0].missionId, "demo-fvm");
  assert.equal(recorded[0].accepted, true);

  const ledger = getClaimLedger(AGENT);
  assert.equal(ledger.length, 1);
  assert.equal(ledger[0].missionId, "demo-fvm");
  assert.equal(ledger[0].accepted, true);
  assert.equal(ledger[0].agentId, AGENT);
});

test("evaluator dedupes on (agent, mission) updating the latest verdict", async () => {
  resetClaimLedger(AGENT);
  const client = new MockOabpClient();
  const runtime = makeRuntime(client);
  const mk = (accepted: boolean | null): Memory[] => [
    { content: { actions: ["SUBMIT_OABP_MISSION"], missionId: "m-x", accepted, text: "OABP mission m-x" } },
  ];
  const t = msg("OABP mission m-x update");
  await claimedMissionsEvaluator.handler(runtime, t, undefined, undefined, undefined, mk(null));
  await claimedMissionsEvaluator.handler(runtime, t, undefined, undefined, undefined, mk(true));
  const ledger = getClaimLedger(AGENT);
  assert.equal(ledger.length, 1, "single entry per mission");
  assert.equal(ledger[0].accepted, true, "verdict updated to latest");
});
