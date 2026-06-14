/**
 * MockOabpClient — an in-memory {@link OabpClient} implementing the OABP protocol's
 * verification semantics, with NO network access.
 *
 * It is the deterministic substrate the `node:test` suite runs against:
 *  - `first_valid_match` accepts a proof iff it matches the mission's regex (content-addressed),
 *    and records the FIRST accepted submitter as the winner (`resolution.winner_agent_id`);
 *  - `oracle` accepts iff the proof "looks resolvable" (a GitHub repo URL for repo deliverables,
 *    a 0x token address for safety reviews) — mirroring the real GoPlus/GitHub oracle without
 *    making any external call;
 *  - `peer_vote` / `creator_judges` never auto-accept (subjective).
 *
 * Submissions are recorded; `/api/stats` reflects them, so a tool run is observable end-to-end.
 * This is "real verification semantics" — not a stub that accepts anything.
 */

import type {
  A2AResponse,
  AgentCard,
  CreateMissionInput,
  Mission,
  MissionDetail,
  OabpClient,
  Stats,
  SubmitResult,
} from "./sdk.js";

const GITHUB_REPO_RE = /^https?:\/\/(www\.)?github\.com\/[^/\s]+\/[^/\s]+/i;
const TOKEN_ADDR_RE = /0x[a-fA-F0-9]{40}/;

/** Internal mission record: a Mission plus the bookkeeping the live protocol keeps server-side. */
interface MockMission extends MissionDetail {
  creator_agent_id?: string;
}

export interface MockSeed {
  missions?: Mission[];
  stats?: Partial<Stats>;
  agentCard?: AgentCard;
}

export class MockOabpClient implements OabpClient {
  private missions: Map<string, MockMission> = new Map();
  private resolved = 0;
  private lifetimePaid: number;
  private readonly agentCard: AgentCard;
  /** Records every submit() call for assertions in tests. */
  readonly submitCalls: { missionId: string; agentId: string; proof: string }[] = [];
  /** Records every createMission() call for assertions in tests. */
  readonly createCalls: CreateMissionInput[] = [];

  constructor(seed: MockSeed = {}) {
    for (const m of seed.missions ?? defaultMissions()) {
      this.missions.set(m.id, structuredCloneSafe(m) as MockMission);
    }
    this.resolved = seed.stats?.resolved ?? 0;
    this.lifetimePaid = seed.stats?.lifetime_reward_aigen_paid ?? 0;
    this.agentCard =
      seed.agentCard ??
      ({
        name: "OABP Mock Agent",
        description: "Deterministic mock of the OABP protocol for tests/offline runs.",
        url: "https://cryptogenesis.duckdns.org/api/a2a",
      } as AgentCard);
  }

  async listMissions(): Promise<Mission[]> {
    return [...this.missions.values()]
      .filter((m) => (m.status ?? "open").toLowerCase() === "open")
      .map(structuredCloneSafe);
  }

  async getMission(id: string): Promise<MissionDetail> {
    const m = this.missions.get(id);
    if (!m) throw new Error(`mock: mission ${id} not found`);
    return structuredCloneSafe(m) as MissionDetail;
  }

  async createMission(input: CreateMissionInput): Promise<Mission> {
    this.createCalls.push(input);
    const id = `m-${this.missions.size + 1}-${Math.random().toString(36).slice(2, 6)}`;
    const mission: MockMission = {
      id,
      title: input.title,
      description: input.description,
      reward: { amount: input.reward_amount, currency: input.reward_currency },
      verification_type: input.verification_type,
      verification_params: input.verification_params ?? {},
      deadline: Math.floor(Date.now() / 1000) + input.deadline_hours * 3600,
      status: "open",
      submissions: [],
      creator_agent_id: input.creator_agent_id,
    };
    this.missions.set(id, mission);
    return structuredCloneSafe(mission);
  }

  async submit(missionId: string, submitterAgentId: string, proof: string): Promise<SubmitResult> {
    this.submitCalls.push({ missionId, agentId: submitterAgentId, proof });
    const m = this.missions.get(missionId);
    if (!m) throw new Error(`mock: mission ${missionId} not found`);

    const { accepted, detail } = verify(m, proof);
    m.submissions.push({
      submitter_agent_id: submitterAgentId,
      proof,
      submitted_at: Math.floor(Date.now() / 1000),
      accepted,
    });
    if (accepted && m.status !== "resolved") {
      // First valid submission wins and resolves the mission (content-addressed / oracle).
      m.status = "resolved";
      m.resolution = {
        winner_agent_id: submitterAgentId,
        resolved_at: Math.floor(Date.now() / 1000),
        reward_paid: netReward(m.reward.amount),
      };
      this.resolved += 1;
      if (m.reward.currency === "AIGEN") this.lifetimePaid += m.reward.amount;
    }
    return { accepted, mission_id: missionId, detail };
  }

  async getStats(): Promise<Stats> {
    const open = [...this.missions.values()].filter(
      (m) => (m.status ?? "open").toLowerCase() === "open"
    ).length;
    return {
      resolved: this.resolved,
      open,
      lifetime_reward_aigen_paid: this.lifetimePaid,
    };
  }

  async a2aSend(message: string): Promise<A2AResponse> {
    return {
      jsonrpc: "2.0",
      id: 1,
      result: {
        kind: "message",
        role: "agent",
        parts: [{ kind: "text", text: `echo: ${message}` }],
      },
    };
  }

  async a2aGetTask(taskId: string): Promise<A2AResponse> {
    return {
      jsonrpc: "2.0",
      id: 1,
      result: { id: taskId, status: { state: "completed" }, kind: "task" },
    };
  }

  async a2aListTasks(): Promise<A2AResponse> {
    return { jsonrpc: "2.0", id: 1, result: { tasks: [] } };
  }

  async getAgentCard(): Promise<AgentCard> {
    return structuredCloneSafe(this.agentCard);
  }
}

/** Net reward after the protocol's 0.5% fee. */
function netReward(amount: number): number {
  return Math.round(amount * (1 - 0.005) * 1e6) / 1e6;
}

/** Pure mirror of the OABP verifiers (no I/O), used by the mock. */
function verify(m: Mission, proof: string): { accepted: boolean; detail: string } {
  switch (m.verification_type) {
    case "first_valid_match": {
      const re = m.verification_params?.regex;
      if (!re) return { accepted: false, detail: "no regex configured" };
      try {
        const ok = new RegExp(re).test(proof);
        return { accepted: ok, detail: ok ? "regex matched" : "regex did not match" };
      } catch {
        return { accepted: false, detail: "invalid regex" };
      }
    }
    case "oracle": {
      const desc = (m.verification_params?.oracle_description ?? "").toLowerCase();
      if (desc.includes("safety") || desc.includes("goplus") || desc.includes("token")) {
        const ok = TOKEN_ADDR_RE.test(proof);
        return { accepted: ok, detail: ok ? "token address present (GoPlus)" : "no token address" };
      }
      // default oracle path: GitHub repo deliverable
      const ok = GITHUB_REPO_RE.test(proof);
      return { accepted: ok, detail: ok ? "github repo present" : "no github repo url" };
    }
    default:
      return { accepted: false, detail: `${m.verification_type} requires human/peer resolution` };
  }
}

function defaultMissions(): Mission[] {
  const now = Math.floor(Date.now() / 1000);
  return [
    {
      id: "demo-fvm",
      title: "Emit the magic build token",
      description: "Reply with a token of the form BUILD-<4 digits> to prove the run.",
      reward: { amount: 25, currency: "AIGEN" },
      verification_type: "first_valid_match",
      verification_params: { regex: "^BUILD-\\d{4}$" },
      deadline: now + 6 * 3600,
      status: "open",
      submissions: [],
    },
    {
      id: "demo-oracle-repo",
      title: "Ship a Go CLI deliverable",
      description: "Provide a public GitHub repo with a Go CLI.",
      reward: { amount: 5, currency: "USDC" },
      verification_type: "oracle",
      verification_params: { oracle_description: "GitHub repo deliverable, Go language" },
      deadline: now + 48 * 3600,
      status: "open",
      submissions: [],
    },
    {
      id: "demo-peervote",
      title: "Best meme about gas fees",
      description: "Subjective, decided by peer vote.",
      reward: { amount: 100, currency: "AIGEN" },
      verification_type: "peer_vote",
      verification_params: {},
      deadline: now + 72 * 3600,
      status: "open",
      submissions: [],
    },
  ];
}

function structuredCloneSafe<T>(v: T): T {
  const sc = (globalThis as { structuredClone?: <U>(x: U) => U }).structuredClone;
  return sc ? sc(v) : (JSON.parse(JSON.stringify(v)) as T);
}
