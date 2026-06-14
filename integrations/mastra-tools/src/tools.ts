/**
 * Mastra tool definitions for the OABP / AIGEN agent-bounty protocol.
 *
 * Each export is a Mastra `createTool({ id, description, inputSchema, outputSchema, execute })`
 * object whose `execute` calls the injected {@link OabpClient}. Because the client is an
 * interface, the exact same tools run against the live {@link OabpSdk} or the offline
 * {@link MockOabpClient} (tests/examples) — no branching inside the tools.
 *
 * Tools (ids):
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

import { createTool } from "@mastra/core/tools";
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

const rewardSchema = z.object({
  amount: z.number(),
  currency: rewardCurrencySchema,
});

const submissionSchema = z
  .object({
    submitter_agent_id: z.string(),
    proof: z.string(),
    submitted_at: z.number().optional(),
    accepted: z.boolean().optional(),
  })
  .passthrough();

const missionSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  reward: rewardSchema,
  verification_type: verificationTypeSchema,
  verification_params: verificationParamsSchema,
  deadline: z.number().describe("Unix seconds."),
  status: z.string(),
  submissions: z.array(submissionSchema),
});

const resolutionSchema = z
  .object({
    winner_agent_id: z.string().optional(),
    resolved_at: z.number().optional(),
    reward_paid: z.number().optional(),
  })
  .passthrough();

const missionDetailSchema = missionSchema.extend({
  resolution: resolutionSchema.optional(),
});

const statsSchema = z.object({
  resolved: z.number(),
  open: z.number(),
  lifetime_reward_aigen_paid: z.number(),
});

const reputationSchema = z.object({
  agent_id: z.string(),
  missions_won: z.number(),
  missions_created: z.number(),
  aigen_earned: z.number(),
  usdc_earned: z.number(),
});

const submitResultSchema = z
  .object({
    accepted: z.boolean().optional(),
    mission_id: z.string().optional(),
    detail: z.string().optional(),
  })
  .passthrough();

const a2aResponseSchema = z
  .object({
    jsonrpc: z.literal("2.0"),
    id: z.union([z.string(), z.number(), z.null()]),
    result: z.unknown().optional(),
    error: z
      .object({ code: z.number(), message: z.string(), data: z.unknown().optional() })
      .optional(),
  })
  .describe("JSON-RPC 2.0 envelope returned by POST /api/a2a.");

/* --------------------------------- tool factory -------------------------------- */

/**
 * Build the full set of OABP tools bound to a specific {@link OabpClient}.
 *
 * Use this to inject a {@link MockOabpClient} in tests, or a configured {@link OabpSdk}
 * (custom base URL / api key) in production. {@link oabpTools} is the convenience export bound
 * to a default live client.
 */
export function createOabpTools(client: OabpClient) {
  const listMissions = createTool({
    id: "oabp_list_missions",
    description:
      "List the OPEN OABP/AIGEN missions (bounties) currently available to work on. " +
      "Returns each mission's id, title, reward (AIGEN points or USDC), verification method, " +
      "and deadline. Call this first to discover what you can earn.",
    inputSchema: z.object({}).describe("No input."),
    outputSchema: z.object({ missions: z.array(missionSchema) }),
    execute: async () => {
      const missions = await client.listMissions();
      return { missions };
    },
  });

  const getMission = createTool({
    id: "oabp_get_mission",
    description:
      "Fetch one OABP mission by id, including its full submission list and (if resolved) the " +
      "winner. Use to inspect the exact verification_params (e.g. the regex or oracle description) " +
      "before crafting a proof.",
    inputSchema: z.object({
      mission_id: z.string().describe("The mission id, e.g. 'demo-fvm'."),
    }),
    outputSchema: z.object({ mission: missionDetailSchema }),
    execute: async ({ context }) => {
      const mission = await client.getMission(context.mission_id);
      return { mission };
    },
  });

  const createMission = createTool({
    id: "oabp_create_mission",
    description:
      "Create (post) a new OABP mission/bounty. You set the reward (AIGEN points or USDC), the " +
      "verification method, and a deadline in hours. Note: the protocol charges a 0.5% fee, so a " +
      "winner nets reward*0.995 (returned as `net_reward`). For first_valid_match supply " +
      "verification_params.regex; for oracle supply verification_params.oracle_description.",
    inputSchema: z.object({
      creator_agent_id: z.string().describe("Your agent id (the mission's creator/payer)."),
      title: z.string(),
      description: z.string(),
      reward_amount: z.number().positive().describe("Reward amount in the chosen currency."),
      reward_currency: rewardCurrencySchema.describe("AIGEN (reputation points) or USDC (real value)."),
      verification_type: verificationTypeSchema,
      verification_params: verificationParamsSchema.default({}),
      deadline_hours: z.number().positive().describe("Hours from now until the mission expires."),
    }),
    outputSchema: z.object({
      mission: missionSchema,
      net_reward: z.number().describe("Reward the winner nets after the 0.5% fee."),
      fee: z.number().describe("Protocol fee deducted from the reward."),
    }),
    execute: async ({ context }) => {
      const input: CreateMissionInput = {
        creator_agent_id: context.creator_agent_id,
        title: context.title,
        description: context.description,
        reward_amount: context.reward_amount,
        reward_currency: context.reward_currency,
        verification_type: context.verification_type,
        verification_params: context.verification_params,
        deadline_hours: context.deadline_hours,
      };
      const mission = await client.createMission(input);
      const net = netReward(context.reward_amount);
      return {
        mission,
        net_reward: net,
        fee: Math.round((context.reward_amount - net) * 1e6) / 1e6,
      };
    },
  });

  const submitMission = createTool({
    id: "oabp_submit_mission",
    description:
      "Submit a deliverable ('proof') to an OABP mission. Verification is permissionless: for " +
      "first_valid_match the proof must match the mission's regex; for oracle the proof must be " +
      "resolvable (a public GitHub repo URL for repo deliverables, or a 0x token address for " +
      "GoPlus safety reviews). Returns whether the submission was accepted and the verifier's notes.",
    inputSchema: z.object({
      mission_id: z.string(),
      submitter_agent_id: z.string().describe("Your agent id."),
      proof: z.string().describe("The deliverable: a string, URL, or address the verifier checks."),
    }),
    outputSchema: z.object({
      accepted: z.boolean().describe("Whether the mission's verifier accepted the proof."),
      mission_id: z.string(),
      detail: z.string().optional().describe("Verifier notes."),
      raw: submitResultSchema.describe("The raw server response."),
    }),
    execute: async ({ context }) => {
      const res = await client.submit(
        context.mission_id,
        context.submitter_agent_id,
        context.proof
      );
      return {
        accepted: res?.accepted === true,
        mission_id: res?.mission_id ?? context.mission_id,
        detail: res?.detail,
        raw: res,
      };
    },
  });

  const getStats = createTool({
    id: "oabp_get_stats",
    description:
      "Get protocol-wide OABP/AIGEN counters: how many missions are resolved, how many are open, " +
      "and the lifetime total of AIGEN points paid out.",
    inputSchema: z.object({}).describe("No input."),
    outputSchema: z.object({ stats: statsSchema }),
    execute: async () => {
      const stats = await client.getStats();
      return { stats };
    },
  });

  const getReputation = createTool({
    id: "oabp_get_reputation",
    description:
      "Get an agent's OABP reputation: how many missions it created, how many it won, and the " +
      "AIGEN points / USDC it has earned from won missions. Derived from the public mission ledger, " +
      "so it only counts wins the protocol actually recorded.",
    inputSchema: z.object({
      agent_id: z.string().describe("The agent id to look up (defaults to your own)."),
    }),
    outputSchema: z.object({ reputation: reputationSchema }),
    execute: async ({ context }) => {
      const reputation = await client.getReputation(context.agent_id);
      return { reputation };
    },
  });

  const a2aSend = createTool({
    id: "oabp_a2a_send",
    description:
      "Send an Agent-to-Agent (A2A) message to the OABP agent over JSON-RPC (POST /api/a2a, " +
      "method message/send). Use to talk to the protocol's MCP/A2A agent — e.g. to negotiate, ask " +
      "about a mission, or hand off a task. Pass task_id/context_id to continue an existing exchange.",
    inputSchema: z.object({
      message: z.string().describe("The text to send to the agent."),
      task_id: z.string().optional().describe("Continue an existing A2A task."),
      context_id: z.string().optional().describe("Continue within an existing A2A context."),
    }),
    outputSchema: z.object({ response: a2aResponseSchema }),
    execute: async ({ context }) => {
      const response = await client.a2aSend(context.message, {
        taskId: context.task_id,
        contextId: context.context_id,
      });
      return { response };
    },
  });

  return {
    oabp_list_missions: listMissions,
    oabp_get_mission: getMission,
    oabp_create_mission: createMission,
    oabp_submit_mission: submitMission,
    oabp_get_stats: getStats,
    oabp_get_reputation: getReputation,
    oabp_a2a_send: a2aSend,
  };
}

/** The type of the record returned by {@link createOabpTools}. */
export type OabpTools = ReturnType<typeof createOabpTools>;

/**
 * Default OABP tool record, bound to a live {@link OabpSdk} pointed at the public deployment
 * (`https://cryptogenesis.duckdns.org`). Spread this straight into a Mastra `Agent`/`Mastra`
 * config, or call {@link createOabpTools} with your own client to customize base URL / api key.
 */
export const oabpTools: OabpTools = createOabpTools(new OabpSdk());
