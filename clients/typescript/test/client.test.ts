import { describe, it, expect, beforeEach } from "vitest";
import { MockServer } from "./mock-fetch.js";
import {
  OabpClient,
  OabpApiError,
  OabpValidationError,
  A2aRpcError,
  computeReputation,
  netReward,
  validateCreateMission,
  normalizeMissionList,
  VERIFICATION_TYPES,
} from "../src/index.js";
import type { Mission, CreateMissionRequest } from "../src/index.js";

const BASE = "https://oabp.test";

function sampleMission(over: Partial<Mission> = {}): Mission {
  return {
    id: "m1",
    title: "Ship a Go CLI",
    description: "Public repo with a working Go CLI",
    reward: { amount: 1000, currency: "AIGEN" },
    verification_type: "oracle",
    verification_params: { oracle_description: "GitHub repo deliverable owner/name in Go" },
    deadline: Math.floor(Date.now() / 1000) + 3600,
    status: "open",
    submissions: [],
    creator_agent_id: "agent://creator",
    ...over,
  };
}

describe("OabpClient construction", () => {
  it("defaults to the public base URL", () => {
    const c = new OabpClient();
    expect(c.baseUrl).toBe("https://cryptogenesis.duckdns.org");
  });

  it("honors a custom base URL and trims the trailing slash", () => {
    const c = new OabpClient({ baseUrl: "https://example.com/" });
    expect(c.baseUrl).toBe("https://example.com");
  });

  it("throws a clear error when no fetch is available and none is injected", () => {
    const saved = (globalThis as { fetch?: unknown }).fetch;
    try {
      // @ts-expect-error - simulate an environment with no global fetch
      delete (globalThis as { fetch?: unknown }).fetch;
      expect(() => new OabpClient({ baseUrl: BASE })).toThrow(/No fetch implementation/);
    } finally {
      (globalThis as { fetch?: unknown }).fetch = saved;
    }
  });
});

describe("listMissions", () => {
  let server: MockServer;
  let client: OabpClient;

  beforeEach(() => {
    server = new MockServer();
    client = new OabpClient({ baseUrl: BASE, fetch: server.fetch });
  });

  it("GETs /api/missions and normalizes the array", async () => {
    server.json("GET", "/api/missions", [
      sampleMission({ id: "a" }),
      sampleMission({ id: "b", reward: { amount: 5, currency: "USDC" } }),
    ]);

    const missions = await client.listMissions();
    expect(missions).toHaveLength(2);
    expect(missions[0]!.id).toBe("a");
    expect(missions[1]!.reward.currency).toBe("USDC");
    expect(server.countCalls("GET", "/api/missions")).toBe(1);
  });

  it("passes status as a query param and applies client-side filters", async () => {
    const now = Math.floor(Date.now() / 1000);
    server.json("GET", "/api/missions", [
      sampleMission({ id: "open-oracle", verification_type: "oracle" }),
      sampleMission({ id: "open-regex", verification_type: "first_valid_match" }),
      sampleMission({ id: "expired", verification_type: "oracle", deadline: now - 10 }),
      sampleMission({ id: "usdc", verification_type: "oracle", reward: { amount: 1, currency: "USDC" } }),
    ]);

    const missions = await client.listMissions({
      status: "open",
      verificationType: "oracle",
      currency: "AIGEN",
      excludeExpired: true,
    });

    expect(missions.map((m) => m.id)).toEqual(["open-oracle"]);
    expect(server.lastCall()!.query.status).toBe("open");
  });

  it("tolerates a {missions:[...]} envelope shape", async () => {
    server.json("GET", "/api/missions", { missions: [sampleMission({ id: "x" })] });
    const missions = await client.listMissions();
    expect(missions.map((m) => m.id)).toEqual(["x"]);
  });
});

describe("getMission", () => {
  let server: MockServer;
  let client: OabpClient;

  beforeEach(() => {
    server = new MockServer();
    client = new OabpClient({ baseUrl: BASE, fetch: server.fetch });
  });

  it("GETs /api/missions/{id} and url-encodes the id", async () => {
    server.on("GET", "/api/missions/m%20space", () => ({
      json: sampleMission({ id: "m space" }),
    }));
    const m = await client.getMission("m space");
    expect(m.id).toBe("m space");
  });

  it("throws OabpValidationError on an empty id without making a request", async () => {
    await expect(client.getMission("")).rejects.toBeInstanceOf(OabpValidationError);
    expect(server.calls).toHaveLength(0);
  });

  it("surfaces a 404 as OabpApiError with status and parsed data", async () => {
    server.json("GET", "/api/missions/nope", { error: "mission not found" }, 404);
    const err = await client.getMission("nope").catch((e) => e);
    expect(err).toBeInstanceOf(OabpApiError);
    expect((err as OabpApiError).status).toBe(404);
    expect((err as OabpApiError).data).toEqual({ error: "mission not found" });
  });
});

describe("createMission", () => {
  let server: MockServer;
  let client: OabpClient;

  beforeEach(() => {
    server = new MockServer();
    client = new OabpClient({ baseUrl: BASE, fetch: server.fetch });
  });

  const validReq: CreateMissionRequest = {
    creator_agent_id: "agent://me",
    title: "Audit a token",
    description: "Run a safety review",
    reward_amount: 250,
    reward_currency: "AIGEN",
    verification_type: "oracle",
    verification_params: { oracle_description: "GoPlus safety review of 0xabc on ethereum" },
    deadline_hours: 48,
  };

  it("POSTs the body to /api/missions and returns the created mission", async () => {
    server.on("POST", "/api/missions", (call) => ({
      status: 201,
      json: sampleMission({ id: "created", title: (call.body as CreateMissionRequest).title }),
    }));

    const m = await client.createMission(validReq);
    expect(m.id).toBe("created");

    const sent = server.lastCall()!;
    expect(sent.method).toBe("POST");
    expect(sent.body).toMatchObject({ creator_agent_id: "agent://me", reward_amount: 250 });
    expect(sent.headers["Content-Type"]).toBe("application/json");
  });

  it("validates client-side and never hits the network on bad input", async () => {
    await expect(
      client.createMission({ ...validReq, reward_amount: -1 }),
    ).rejects.toThrow(/reward_amount must be greater than 0/);
    await expect(
      client.createMission({ ...validReq, reward_currency: "BTC" as never }),
    ).rejects.toThrow(/reward_currency/);
    await expect(
      client.createMission({ ...validReq, deadline_hours: 0 }),
    ).rejects.toThrow(/deadline_hours/);
    expect(server.calls).toHaveLength(0);
  });

  it("requires a compilable regex for first_valid_match missions", () => {
    expect(() =>
      validateCreateMission({
        ...validReq,
        verification_type: "first_valid_match",
        verification_params: {},
      }),
    ).toThrow(/require verification_params.regex/);

    expect(() =>
      validateCreateMission({
        ...validReq,
        verification_type: "first_valid_match",
        verification_params: { regex: "([unclosed" },
      }),
    ).toThrow(/not a valid regular expression/);

    expect(() =>
      validateCreateMission({
        ...validReq,
        verification_type: "first_valid_match",
        verification_params: { regex: "^0x[a-fA-F0-9]{40}$" },
      }),
    ).not.toThrow();
  });
});

describe("submit", () => {
  let server: MockServer;
  let client: OabpClient;

  beforeEach(() => {
    server = new MockServer();
    client = new OabpClient({ baseUrl: BASE, fetch: server.fetch });
  });

  it("POSTs to /missions/{id}/submit with proof and returns the result", async () => {
    server.on("POST", "/missions/m1/submit", (call) => ({
      json: {
        accepted: true,
        resolved: true,
        submission: {
          submitter_agent_id: (call.body as { submitter_agent_id: string }).submitter_agent_id,
          proof: (call.body as { proof: string }).proof,
          verified: true,
        },
      },
    }));

    const res = await client.submit("m1", {
      submitter_agent_id: "agent://me",
      proof: "https://github.com/owner/repo",
    });

    expect(res.accepted).toBe(true);
    expect(res.resolved).toBe(true);
    expect(res.submission?.verified).toBe(true);
    expect(server.lastCall()!.body).toMatchObject({ proof: "https://github.com/owner/repo" });
  });

  it("rejects empty proof / agent id before the request", async () => {
    await expect(
      client.submit("m1", { submitter_agent_id: "", proof: "x" }),
    ).rejects.toBeInstanceOf(OabpValidationError);
    await expect(
      client.submit("m1", { submitter_agent_id: "a", proof: "  " }),
    ).rejects.toBeInstanceOf(OabpValidationError);
    expect(server.calls).toHaveLength(0);
  });
});

describe("getStats", () => {
  it("GETs /api/stats and fills defaults", async () => {
    const server = new MockServer();
    const client = new OabpClient({ baseUrl: BASE, fetch: server.fetch });
    server.json("GET", "/api/stats", { resolved: 12, open: 3, lifetime_reward_aigen_paid: 108000 });
    const stats = await client.getStats();
    expect(stats).toMatchObject({ resolved: 12, open: 3, lifetime_reward_aigen_paid: 108000 });
  });
});

describe("reputation", () => {
  it("computeReputation aggregates created/won/submitted and net earnings", () => {
    const missions: Mission[] = [
      sampleMission({
        id: "won-aigen",
        creator_agent_id: "agent://other",
        reward: { amount: 1000, currency: "AIGEN" },
        status: "resolved",
        submissions: [{ submitter_agent_id: "agent://me", proof: "p" }],
        resolution: { winner_agent_id: "agent://me", reward_paid: 995, reward_currency: "AIGEN" },
      }),
      sampleMission({
        id: "won-usdc",
        creator_agent_id: "agent://me",
        reward: { amount: 50, currency: "USDC" },
        status: "resolved",
        submissions: [{ submitter_agent_id: "agent://me", proof: "q" }],
        resolution: { winner_agent_id: "agent://me", reward_currency: "USDC" },
      }),
      sampleMission({
        id: "lost",
        creator_agent_id: "agent://other",
        status: "resolved",
        submissions: [{ submitter_agent_id: "agent://me", proof: "r" }],
        resolution: { winner_agent_id: "agent://rival", reward_paid: 10, reward_currency: "AIGEN" },
      }),
    ];

    const rep = computeReputation("agent://me", missions);
    expect(rep.missions_created).toBe(1);
    expect(rep.missions_won).toBe(2);
    expect(rep.submissions_made).toBe(3);
    expect(rep.aigen_earned).toBe(995);
    // USDC win fell back to mission reward amount (50) since reward_paid absent.
    expect(rep.usdc_earned).toBe(50);
  });

  it("getReputation merges open + resolved lists and dedupes", async () => {
    const server = new MockServer();
    const client = new OabpClient({ baseUrl: BASE, fetch: server.fetch });

    server.on("GET", "/api/missions", (call) => {
      if (call.query.status === "resolved") {
        return {
          json: [
            sampleMission({
              id: "r1",
              status: "resolved",
              resolution: { winner_agent_id: "agent://me", reward_paid: 200, reward_currency: "AIGEN" },
            }),
          ],
        };
      }
      return {
        json: [sampleMission({ id: "o1", creator_agent_id: "agent://me" })],
      };
    });

    const rep = await client.getReputation("agent://me");
    expect(rep.missions_created).toBe(1);
    expect(rep.missions_won).toBe(1);
    expect(rep.aigen_earned).toBe(200);
    expect(server.countCalls("GET", "/api/missions")).toBe(2);
  });
});

describe("A2A JSON-RPC", () => {
  let server: MockServer;
  let client: OabpClient;

  beforeEach(() => {
    server = new MockServer();
    client = new OabpClient({ baseUrl: BASE, fetch: server.fetch });
  });

  it("message/send wraps params in a JSON-RPC envelope and unwraps result", async () => {
    server.on("POST", "/api/a2a", (call) => {
      const req = call.body as { jsonrpc: string; id: string; method: string; params: unknown };
      expect(req.jsonrpc).toBe("2.0");
      expect(req.method).toBe("message/send");
      return { json: { jsonrpc: "2.0", id: req.id, result: { id: "task-1", status: { state: "completed" } } } };
    });

    const res = await client.a2a.sendText("hello agent");
    expect(res).toMatchObject({ id: "task-1" });
  });

  it("tasks/get and tasks/list call the right methods", async () => {
    server.on("POST", "/api/a2a", (call) => {
      const req = call.body as { id: string; method: string; params: { id?: string } };
      if (req.method === "tasks/get") {
        return { json: { jsonrpc: "2.0", id: req.id, result: { id: req.params.id } } };
      }
      if (req.method === "tasks/list") {
        return { json: { jsonrpc: "2.0", id: req.id, result: [{ id: "t1" }, { id: "t2" }] } };
      }
      return { json: { jsonrpc: "2.0", id: req.id, error: { code: -32601, message: "method not found" } } };
    });

    const task = await client.a2a.getTask("abc");
    expect(task.id).toBe("abc");
    const tasks = await client.a2a.listTasks();
    expect(tasks.map((t) => t.id)).toEqual(["t1", "t2"]);
  });

  it("maps a JSON-RPC error member to A2aRpcError", async () => {
    server.on("POST", "/api/a2a", (call) => {
      const req = call.body as { id: string };
      return { json: { jsonrpc: "2.0", id: req.id, error: { code: -32602, message: "invalid params", data: { field: "message" } } } };
    });

    const err = await client.a2a.getTask("x").catch((e) => e);
    expect(err).toBeInstanceOf(A2aRpcError);
    expect((err as A2aRpcError).code).toBe(-32602);
    expect((err as A2aRpcError).data).toEqual({ field: "message" });
  });

  it("fetches the agent card and JWKS from well-known paths", async () => {
    server.json("GET", "/.well-known/agent-card.json", { name: "OABP Agent", version: "1.0.0" });
    server.json("GET", "/.well-known/jwks.json", { keys: [{ kty: "EC", crv: "P-256", kid: "k1" }] });

    const card = await client.a2a.getAgentCard();
    expect(card.name).toBe("OABP Agent");
    const jwks = await client.a2a.getJwks();
    expect(jwks.keys[0]!.kid).toBe("k1");
  });
});

describe("auth + headers + timeout", () => {
  it("adds an Authorization bearer header when apiKey is set", async () => {
    const server = new MockServer();
    const client = new OabpClient({ baseUrl: BASE, fetch: server.fetch, apiKey: "secret-token" });
    server.json("GET", "/api/stats", { resolved: 0, open: 0, lifetime_reward_aigen_paid: 0 });
    await client.getStats();
    expect(server.lastCall()!.headers["Authorization"]).toBe("Bearer secret-token");
  });

  it("surfaces a server 500 as OabpApiError", async () => {
    const server = new MockServer();
    const client = new OabpClient({ baseUrl: BASE, fetch: server.fetch });
    server.json("GET", "/api/stats", { error: "boom" }, 500);
    await expect(client.getStats()).rejects.toBeInstanceOf(OabpApiError);
  });
});

describe("pure helpers", () => {
  it("netReward applies the 0.5% protocol fee", () => {
    expect(netReward(1000)).toBe(995);
    expect(netReward(50)).toBe(49.75);
  });

  it("VERIFICATION_TYPES lists exactly the four protocol types", () => {
    expect([...VERIFICATION_TYPES].sort()).toEqual(
      ["creator_judges", "first_valid_match", "oracle", "peer_vote"].sort(),
    );
  });

  it("normalizeMissionList coerces malformed rows defensively", () => {
    const out = normalizeMissionList([
      { id: 7, reward: { amount: "12.5", currency: "USDC" } },
      null,
      "garbage",
      { id: "ok" },
    ]);
    expect(out).toHaveLength(2);
    expect(out[0]!.id).toBe("7");
    expect(out[0]!.reward).toEqual({ amount: 12.5, currency: "USDC" });
    expect(out[0]!.submissions).toEqual([]);
    expect(out[1]!.reward.currency).toBe("AIGEN");
  });
});
