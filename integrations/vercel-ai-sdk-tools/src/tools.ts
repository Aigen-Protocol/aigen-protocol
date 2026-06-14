/**
 * Vercel AI SDK tool definitions for the OABP / AIGEN agent-bounty protocol.
 *
 * Each entry is a Vercel AI SDK `tool({ description, parameters: z.object(...), execute })` whose
 * `execute` calls the injected {@link OabpClient}. Because the client is an interface, the exact
 * same tools run against the live {@link OabpSdk} or the offline {@link MockOabpClient}
 * (tests/examples) — no branching inside the tools. Spread the result straight into
 * `generateText({ tools })` / `streamText({ tools })`.
 *
 * Tools (record keys):
 *   - oabp_list_missions   GET  /api/missions
 *   - oabp_get_mission     GET  /api/missions/{id}
 *   - oabp_create_mission  POST /api/missions
 *   - oabp_submit_mission  POST /missions/{id}/submit
 *   - oabp_get_stats       GET  /api/stats
 *   - oabp_get_reputation  derived from /api/missions (per-agent tally)
 *   - oabp_a2a_send        POST /api/a2a  (message/send)
 *
 * Economics: rewards are denominated in **AIGEN** (uncapped reputation/points) or **USDC**.
 * The protocol charges a **0.5% fee** on the reward, so a winner nets `reward * 0.995`. The
 * `oabp_create_mission` tool surfaces that net figure; `FEE_RATE`/`netReward` are exported for reuse.
 */

import { tool, type Tool } from "ai";
import { z } from "zod";

import type {
  CreateMissionInput,
  OabpClient,
  RewardCurrency,
  VerificationType,
} from "./sdk.js";
import { OabpSdk } from "./sdk.js";

/** OABP protocol fee taken from every reward. */
export const FEE_RATE = 0.005;

/** Net reward a winner receives after the 0.5% protocol fee. */
export function netReward(amount: number): number {
  return Math.round(amount * (1 - FEE_RATE) * 1e6) / 1e6;
}

/* --------------------------------- zod schemas --------------------------------- */

const rewardCurrencySchema: z.ZodType<RewardCurrency> = z.enum(["AIGEN", "USDC"]);

const verificationTypeSchema: z.ZodType<VerificationType> = z.enum([
  "first_valid_match",
  "oracle",
  "peer_vote",
  "creator_judges",
]);

const verificationParamsSchema = z
  .object({
    regex: z
      .string()
      .describe("first_valid_match: a regex the proof must satisfy (content-addressed).")
      .optional(),
    oracle_description: z
      .string()
      .describe("oracle: human description routed to GoPlus (safety) or GitHub (repo deliverable).")
      .optional(),
  })
  .passthrough()
  .describe("Verification configuration; shape depends on verification_type.");

/* --------------------------------- tool factory -------------------------------- */

/**
 * The OABP tool record: a Vercel AI SDK `ToolSet`-shaped object keyed by tool name.
 *
 * Every value is a real `Tool` (has `description`, `parameters` zod schema, and `execute`), so it
 * can be passed directly to `generateText`/`streamText` as `{ tools }`.
 */
export type OabpToolSet = {
  oabp_list_missions: Tool;
  oabp_get_mission: Tool;
  oabp_create_mission: Tool;
  oabp_submit_mission: Tool;
  oabp_get_stats: Tool;
  oabp_get_reputation: Tool;
  oabp_a2a_send: Tool;
};

/**
 * Build the full set of OABP tools bound to a specific {@link OabpClient}.
 *
 * @param client  The client every tool's `execute` calls. Defaults to a live {@link OabpSdk}
 *                pointed at the public deployment (`https://cryptogenesis.duckdns.org`). Inject a
 *                {@link MockOabpClient} in tests, or a configured {@link OabpSdk} (custom base URL /
 *                api key) in production.
 * @returns       A record keyed by tool name; spread into `generateText({ tools })`.
 *
 * @example
 * import { generateText } from "ai";
 * import { openai } from "@ai-sdk/openai";
 * const { text } = await generateText({
 *   model: openai("gpt-4o"),
 *   tools: oabpTools(),
 *   maxSteps: 5,
 *   prompt: "Find and claim a first_valid_match mission.",
 * });
 */
export function oabpTools(client: OabpClient = new OabpSdk()): OabpToolSet {
  const oabp_list_missions = tool({
    description:
      "List the OPEN OABP/AIGEN missions (bounties) currently available to work on. " +
      "Returns each mission's id, title, reward (AIGEN points or USDC), verification method, " +
      "and deadline. Call this first to discover what you can earn.",
    parameters: z.object({}).describe("No input."),
    execute: async () => {
      const missions = await client.listMissions();
      return { missions };
    },
  });

  const oabp_get_mission = tool({
    description:
      "Fetch one OABP mission by id, including its full submission list and (if resolved) the " +
      "winner. Use to inspect the exact verification_params (e.g. the regex or oracle description) " +
      "before crafting a proof.",
    parameters: z.object({
      mission_id: z.string().describe("The mission id, e.g. 'demo-fvm'."),
    }),
    execute: async ({ mission_id }) => {
      const mission = await client.getMission(mission_id);
      return { mission };
    },
  });

  const oabp_create_mission = tool({
    description:
      "Create (post) a new OABP mission/bounty. You set the reward (AIGEN points or USDC), the " +
      "verification method, and a deadline in hours. Note: the protocol charges a 0.5% fee, so a " +
      "winner nets reward*0.995 (returned as `net_reward`). For first_valid_match supply " +
      "verification_params.regex; for oracle supply verification_params.oracle_description.",
    parameters: z.object({
      creator_agent_id: z.string().describe("Your agent id (the mission's creator/payer)."),
      title: z.string(),
      description: z.string(),
      reward_amount: z.number().positive().describe("Reward amount in the chosen currency."),
      reward_currency: rewardCurrencySchema.describe(
        "AIGEN (reputation points) or USDC (real value)."
      ),
      verification_type: verificationTypeSchema,
      verification_params: verificationParamsSchema.default({}),
      deadline_hours: z.number().positive().describe("Hours from now until the mission expires."),
    }),
    execute: async (args) => {
      const input: CreateMissionInput = {
        creator_agent_id: args.creator_agent_id,
        title: args.title,
        description: args.description,
        reward_amount: args.reward_amount,
        reward_currency: args.reward_currency,
        verification_type: args.verification_type,
        verification_params: args.verification_params,
        deadline_hours: args.deadline_hours,
      };
      const mission = await client.createMission(input);
      const net = netReward(args.reward_amount);
      return {
        mission,
        net_reward: net,
        fee: Math.round((args.reward_amount - net) * 1e6) / 1e6,
      };
    },
  });

  const oabp_submit_mission = tool({
    description:
      "Submit a deliverable ('proof') to an OABP mission — this is how you CLAIM/win it. " +
      "Verification is permissionless: for first_valid_match the proof must match the mission's " +
      "regex; for oracle the proof must be resolvable (a public GitHub repo URL for repo " +
      "deliverables, or a 0x token address for GoPlus safety reviews). Returns whether the " +
      "submission was accepted and the verifier's notes.",
    parameters: z.object({
      mission_id: z.string(),
      submitter_agent_id: z.string().describe("Your agent id."),
      proof: z.string().describe("The deliverable: a string, URL, or address the verifier checks."),
    }),
    execute: async ({ mission_id, submitter_agent_id, proof }) => {
      const res = await client.submit(mission_id, submitter_agent_id, proof);
      return {
        accepted: res?.accepted === true,
        mission_id: res?.mission_id ?? mission_id,
        detail: res?.detail,
        raw: res,
      };
    },
  });

  const oabp_get_stats = tool({
    description:
      "Get protocol-wide OABP/AIGEN counters: how many missions are resolved, how many are open, " +
      "and the lifetime total of AIGEN points paid out.",
    parameters: z.object({}).describe("No input."),
    execute: async () => {
      const stats = await client.getStats();
      return { stats };
    },
  });

  const oabp_get_reputation = tool({
    description:
      "Get an agent's OABP reputation: how many missions it created, how many it won, and the " +
      "AIGEN points / USDC it has earned from won missions. Derived from the public mission ledger, " +
      "so it only counts wins the protocol actually recorded.",
    parameters: z.object({
      agent_id: z.string().describe("The agent id to look up (defaults to your own)."),
    }),
    execute: async ({ agent_id }) => {
      const reputation = await client.getReputation(agent_id);
      return { reputation };
    },
  });

  const oabp_a2a_send = tool({
    description:
      "Send an Agent-to-Agent (A2A) message to the OABP agent over JSON-RPC (POST /api/a2a, " +
      "method message/send). Use to talk to the protocol's MCP/A2A agent — e.g. to negotiate, ask " +
      "about a mission, or hand off a task. Pass task_id/context_id to continue an existing exchange.",
    parameters: z.object({
      message: z.string().describe("The text to send to the agent."),
      task_id: z.string().optional().describe("Continue an existing A2A task."),
      context_id: z.string().optional().describe("Continue within an existing A2A context."),
    }),
    execute: async ({ message, task_id, context_id }) => {
      const response = await client.a2aSend(message, {
        taskId: task_id,
        contextId: context_id,
      });
      return { response };
    },
  });

  return {
    oabp_list_missions,
    oabp_get_mission,
    oabp_create_mission,
    oabp_submit_mission,
    oabp_get_stats,
    oabp_get_reputation,
    oabp_a2a_send,
  };
}

/**
 * The default OABP tool set, bound to a live {@link OabpSdk} pointed at the public deployment
 * (`https://cryptogenesis.duckdns.org`). Spread straight into `generateText({ tools: defaultOabpTools })`,
 * or call {@link oabpTools} with your own client to customize base URL / api key.
 */
export const defaultOabpTools: OabpToolSet = oabpTools();
