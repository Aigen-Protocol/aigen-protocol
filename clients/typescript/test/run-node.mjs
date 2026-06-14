/**
 * Dependency-free test runner for the built SDK.
 *
 * Unlike `client.test.ts` (which runs under vitest against the TS source), this
 * runner imports the compiled ESM bundle in `dist/` and exercises it with a
 * hand-rolled mock fetch using only Node's `assert`. It needs ZERO dev
 * dependencies, so `npm run test:node` works in a clean checkout right after
 * `npm run build` — a useful smoke test for the published artifact itself.
 *
 * Usage:  npm run build && npm run test:node
 */

import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const distEntry = resolve(here, "..", "dist", "index.js");

if (!existsSync(distEntry)) {
  console.error(`dist not built. Run \`npm run build\` first (missing ${distEntry}).`);
  process.exit(1);
}

const {
  OabpClient,
  OabpApiError,
  OabpValidationError,
  A2aRpcError,
  computeReputation,
  netReward,
  VERIFICATION_TYPES,
  normalizeMissionList,
} = await import(pathToFileURL(distEntry).href);

// --- minimal mock fetch ------------------------------------------------------

function makeServer() {
  const calls = [];
  const routes = new Map();
  const stripOrigin = (u) => {
    const m = /^https?:\/\/[^/]+(\/.*)?$/.exec(u);
    return m ? m[1] ?? "/" : u;
  };
  const parse = (u) => {
    const i = u.indexOf("?");
    if (i === -1) return { path: stripOrigin(u), query: {} };
    const path = stripOrigin(u.slice(0, i));
    const query = {};
    for (const pair of u.slice(i + 1).split("&")) {
      if (!pair) continue;
      const eq = pair.indexOf("=");
      const k = decodeURIComponent(eq === -1 ? pair : pair.slice(0, eq));
      query[k] = eq === -1 ? "" : decodeURIComponent(pair.slice(eq + 1));
    }
    return { path, query };
  };
  const mkRes = (spec) => {
    const status = spec.status ?? 200;
    const body = spec.text ?? (spec.json !== undefined ? JSON.stringify(spec.json) : "");
    return {
      ok: status >= 200 && status < 300,
      status,
      statusText: spec.statusText ?? "",
      text: async () => body,
    };
  };
  return {
    calls,
    on(method, path, handler) {
      routes.set(`${method} ${path}`, handler);
      return this;
    },
    json(method, path, json, status = 200) {
      return this.on(method, path, () => ({ json, status }));
    },
    get fetch() {
      return async (url, init) => {
        const method = (init?.method ?? "GET").toUpperCase();
        const { path, query } = parse(url);
        let body;
        if (typeof init?.body === "string" && init.body.length) {
          try { body = JSON.parse(init.body); } catch { body = init.body; }
        }
        const headers = {};
        if (init?.headers) for (const [k, v] of Object.entries(init.headers)) headers[k] = String(v);
        const call = { method, url, path, query, body, headers };
        calls.push(call);
        const h = routes.get(`${method} ${path}`);
        if (!h) return mkRes({ status: 404, json: { error: `no route ${method} ${path}` } });
        return mkRes(h(call));
      };
    },
  };
}

// --- tiny test harness -------------------------------------------------------

let passed = 0;
const failures = [];
async function test(name, fn) {
  try {
    await fn();
    passed += 1;
  } catch (err) {
    failures.push({ name, err });
  }
}

const BASE = "https://oabp.test";
const future = Math.floor(Date.now() / 1000) + 3600;
const mission = (over = {}) => ({
  id: "m1", title: "t", description: "d",
  reward: { amount: 1000, currency: "AIGEN" },
  verification_type: "oracle", verification_params: {}, deadline: future,
  status: "open", submissions: [], creator_agent_id: "agent://creator", ...over,
});

await test("netReward applies 0.5% fee", () => {
  assert.equal(netReward(1000), 995);
  assert.equal(netReward(50), 49.75);
});

await test("VERIFICATION_TYPES has the four protocol types", () => {
  assert.deepEqual([...VERIFICATION_TYPES].sort(), ["creator_judges", "first_valid_match", "oracle", "peer_vote"].sort());
});

await test("listMissions normalizes and filters", async () => {
  const s = makeServer();
  s.json("GET", "/api/missions", [
    mission({ id: "a", verification_type: "oracle" }),
    mission({ id: "b", verification_type: "first_valid_match" }),
    mission({ id: "exp", verification_type: "oracle", deadline: 1 }),
  ]);
  const c = new OabpClient({ baseUrl: BASE, fetch: s.fetch });
  const out = await c.listMissions({ status: "open", verificationType: "oracle", excludeExpired: true });
  assert.deepEqual(out.map((m) => m.id), ["a"]);
  assert.equal(s.calls.at(-1).query.status, "open");
});

await test("getMission 404 -> OabpApiError", async () => {
  const s = makeServer();
  s.json("GET", "/api/missions/nope", { error: "not found" }, 404);
  const c = new OabpClient({ baseUrl: BASE, fetch: s.fetch });
  await assert.rejects(() => c.getMission("nope"), (e) => e instanceof OabpApiError && e.status === 404);
});

await test("createMission validates before sending", async () => {
  const s = makeServer();
  const c = new OabpClient({ baseUrl: BASE, fetch: s.fetch });
  await assert.rejects(
    () => c.createMission({ creator_agent_id: "a", title: "t", description: "d", reward_amount: -1, reward_currency: "AIGEN", verification_type: "oracle", verification_params: {}, deadline_hours: 1 }),
    (e) => e instanceof OabpValidationError,
  );
  assert.equal(s.calls.length, 0);
});

await test("createMission posts body and returns mission", async () => {
  const s = makeServer();
  s.on("POST", "/api/missions", (call) => ({ status: 201, json: mission({ id: "created", title: call.body.title }) }));
  const c = new OabpClient({ baseUrl: BASE, fetch: s.fetch });
  const m = await c.createMission({ creator_agent_id: "a", title: "Hello", description: "d", reward_amount: 5, reward_currency: "AIGEN", verification_type: "oracle", verification_params: { oracle_description: "x" }, deadline_hours: 1 });
  assert.equal(m.id, "created");
  assert.equal(s.calls.at(-1).body.reward_amount, 5);
});

await test("submit posts proof and returns result", async () => {
  const s = makeServer();
  s.on("POST", "/missions/m1/submit", (call) => ({ json: { accepted: true, resolved: true, submission: { submitter_agent_id: call.body.submitter_agent_id, proof: call.body.proof } } }));
  const c = new OabpClient({ baseUrl: BASE, fetch: s.fetch });
  const r = await c.submit("m1", { submitter_agent_id: "agent://me", proof: "https://github.com/o/r" });
  assert.equal(r.accepted, true);
  assert.equal(s.calls.at(-1).body.proof, "https://github.com/o/r");
});

await test("getStats returns aggregate", async () => {
  const s = makeServer();
  s.json("GET", "/api/stats", { resolved: 12, open: 3, lifetime_reward_aigen_paid: 108000 });
  const c = new OabpClient({ baseUrl: BASE, fetch: s.fetch });
  const stats = await c.getStats();
  assert.equal(stats.lifetime_reward_aigen_paid, 108000);
});

await test("computeReputation aggregates", () => {
  const rep = computeReputation("me", [
    mission({ id: "w", creator_agent_id: "other", status: "resolved", submissions: [{ submitter_agent_id: "me", proof: "p" }], resolution: { winner_agent_id: "me", reward_paid: 995, reward_currency: "AIGEN" } }),
    mission({ id: "c", creator_agent_id: "me" }),
  ]);
  assert.equal(rep.missions_created, 1);
  assert.equal(rep.missions_won, 1);
  assert.equal(rep.submissions_made, 1);
  assert.equal(rep.aigen_earned, 995);
});

await test("A2A message/send round trip", async () => {
  const s = makeServer();
  s.on("POST", "/api/a2a", (call) => {
    assert.equal(call.body.jsonrpc, "2.0");
    return { json: { jsonrpc: "2.0", id: call.body.id, result: { id: "task-1" } } };
  });
  const c = new OabpClient({ baseUrl: BASE, fetch: s.fetch });
  const res = await c.a2a.sendText("hi");
  assert.equal(res.id, "task-1");
});

await test("A2A error -> A2aRpcError", async () => {
  const s = makeServer();
  s.on("POST", "/api/a2a", (call) => ({ json: { jsonrpc: "2.0", id: call.body.id, error: { code: -32602, message: "bad" } } }));
  const c = new OabpClient({ baseUrl: BASE, fetch: s.fetch });
  await assert.rejects(() => c.a2a.getTask("x"), (e) => e instanceof A2aRpcError && e.code === -32602);
});

await test("agent card + jwks fetched from well-known", async () => {
  const s = makeServer();
  s.json("GET", "/.well-known/agent-card.json", { name: "OABP Agent" });
  s.json("GET", "/.well-known/jwks.json", { keys: [{ kty: "EC", kid: "k1" }] });
  const c = new OabpClient({ baseUrl: BASE, fetch: s.fetch });
  assert.equal((await c.a2a.getAgentCard()).name, "OABP Agent");
  assert.equal((await c.a2a.getJwks()).keys[0].kid, "k1");
});

await test("apiKey adds bearer header", async () => {
  const s = makeServer();
  s.json("GET", "/api/stats", { resolved: 0, open: 0, lifetime_reward_aigen_paid: 0 });
  const c = new OabpClient({ baseUrl: BASE, fetch: s.fetch, apiKey: "tok" });
  await c.getStats();
  assert.equal(s.calls.at(-1).headers["Authorization"], "Bearer tok");
});

await test("normalizeMissionList coerces malformed rows", () => {
  const out = normalizeMissionList([{ id: 7, reward: { amount: "12.5", currency: "USDC" } }, null, "x", { id: "ok" }]);
  assert.equal(out.length, 2);
  assert.equal(out[0].id, "7");
  assert.deepEqual(out[0].reward, { amount: 12.5, currency: "USDC" });
});

// --- report ------------------------------------------------------------------

if (failures.length) {
  console.error(`\nnode runner: ${passed} passed, ${failures.length} FAILED\n`);
  for (const f of failures) {
    console.error(`  ✗ ${f.name}`);
    console.error(`    ${f.err && f.err.message ? f.err.message : f.err}`);
  }
  process.exit(1);
}
console.log(`node runner: ${passed} passed, 0 failed (against dist/index.js)`);
