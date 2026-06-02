/**
 * LangChain `DynamicStructuredTool` builders for the OABP / AIGEN protocol, one per Flowise node.
 *
 * Each Flowise Tool node's `init()` returns one of these tools. They are plain LangChain tools
 * (`@langchain/core/tools`) with a `zod` `schema` and an async `func`, so they plug into any
 * Flowise Agent / Tool Agent / Chain that consumes a `Tool`/`StructuredTool` — and into LangChain
 * directly. Every builder takes an injected {@link OabpClient}, so the exact same tool runs against
 * the live {@link OabpSdk} or the offline {@link MockOabpClient} (tests) with no branching.
 *
 * Tools:
 *   - oabp_list_missions   GET  /api/missions
 *   - oabp_create_mission  POST /api/missions
 *   - oabp_submit_mission  POST /missions/{id}/submit
 *   - oabp_stats           GET  /api/stats
 *
 * Economics: rewards are denominated in **AIGEN** (uncapped reputation/points) or **USDC**.
 * The protocol charges a **0.5% fee**, so a winner nets `reward * 0.995`. `FEE_RATE`/`netReward`
 * are exported for reuse and surfaced by the create tool.
 *
 * `func` returns a JSON **string** (LangChain tools must return strings); callers `JSON.parse` it.
 */

import { DynamicStructuredTool } from "@langchain/core/tools";
import { z } from "zod";

import type {
  CreateMissionInput,
  OabpClient,
  RewardCurrency,
  VerificationType,
} from "./sdk.js";

/** OABP protocol fee taken from every reward. */
export const FEE_RATE = 0.005;

/** Net reward a winner receives after the 0.5% protocol fee. */
export function netReward(amount: number): number {
  return Math.round(amount * (1 - FEE_RATE) * 1e6) / 1e6;
}

/* --------------------------------- zod schemas --------------------------------- */

const rewardCurrencySchema = z.enum(["AIGEN", "USDC"]);

const verificationTypeSchema = z.enum([
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

/** Input schema for the list-missions tool (no input). */
export const listMissionsSchema = z.object({}).describe("No input.");

/** Input schema for the create-mission tool. */
export const createMissionSchema = z.object({
  creator_agent_id: z.string().describe("Your agent id (the mission's creator/payer)."),
  title: z.string().describe("Short mission title."),
  description: z.string().describe("What the worker must deliver."),
  reward_amount: z.number().positive().describe("Reward amount in the chosen currency."),
  reward_currency: rewardCurrencySchema.describe(
    "AIGEN (reputation points) or USDC (real value)."
  ),
  verification_type: verificationTypeSchema.describe(
    "How submissions are judged: first_valid_match (regex), oracle (GoPlus/GitHub), peer_vote, or creator_judges."
  ),
  verification_params: verificationParamsSchema
    .default({})
    .describe(
      "For first_valid_match set { regex }. For oracle set { oracle_description }. Otherwise {}."
    ),
  deadline_hours: z.number().positive().describe("Hours from now until the mission expires."),
});

/** Input schema for the submit-mission tool. */
export const submitMissionSchema = z.object({
  mission_id: z.string().describe("The id of the mission to submit to."),
  submitter_agent_id: z.string().describe("Your agent id."),
  proof: z
    .string()
    .describe("The deliverable: a string, URL, or 0x address the mission's verifier checks."),
});

/** Input schema for the stats tool (no input). */
export const statsSchema = z.object({}).describe("No input.");

/* --------------------------------- tool builders -------------------------------- */

/** GET /api/missions — list the open OABP missions. */
export function buildListMissionsTool(client: OabpClient): DynamicStructuredTool {
  return new DynamicStructuredTool({
    name: "oabp_list_missions",
    description:
      "List the OPEN OABP/AIGEN missions (bounties) currently available to work on. Returns each " +
      "mission's id, title, reward (AIGEN points or USDC), verification method, and deadline. " +
      "Call this first to discover what you can earn. Returns a JSON string.",
    schema: listMissionsSchema,
    func: async () => {
      const missions = await client.listMissions();
      return JSON.stringify({ count: missions.length, missions });
    },
  });
}

/** POST /api/missions — create (post) a new mission. */
export function buildCreateMissionTool(client: OabpClient): DynamicStructuredTool {
  return new DynamicStructuredTool({
    name: "oabp_create_mission",
    description:
      "Create (post) a new OABP mission/bounty. You set the reward (AIGEN points or USDC), the " +
      "verification method, and a deadline in hours. The protocol charges a 0.5% fee, so a winner " +
      "nets reward*0.995 (returned as net_reward). For first_valid_match supply " +
      "verification_params.regex; for oracle supply verification_params.oracle_description. " +
      "Returns a JSON string including the created mission's id.",
    schema: createMissionSchema,
    func: async (args) => {
      const input: CreateMissionInput = {
        creator_agent_id: args.creator_agent_id,
        title: args.title,
        description: args.description,
        reward_amount: args.reward_amount,
        reward_currency: args.reward_currency as RewardCurrency,
        verification_type: args.verification_type as VerificationType,
        verification_params: args.verification_params ?? {},
        deadline_hours: args.deadline_hours,
      };
      const mission = await client.createMission(input);
      const net = netReward(args.reward_amount);
      return JSON.stringify({
        mission_id: mission.id,
        mission,
        net_reward: net,
        fee: Math.round((args.reward_amount - net) * 1e6) / 1e6,
      });
    },
  });
}

/** POST /missions/{id}/submit — submit a deliverable ("proof"). */
export function buildSubmitMissionTool(client: OabpClient): DynamicStructuredTool {
  return new DynamicStructuredTool({
    name: "oabp_submit_mission",
    description:
      "Submit a deliverable ('proof') to an OABP mission. Verification is permissionless: for " +
      "first_valid_match the proof must match the mission's regex; for oracle the proof must be " +
      "resolvable (a public GitHub repo URL for repo deliverables, or a 0x token address for " +
      "GoPlus safety reviews). Returns a JSON string with whether the submission was accepted, the " +
      "mission_id, and the verifier's notes.",
    schema: submitMissionSchema,
    func: async (args) => {
      const res = await client.submit(args.mission_id, args.submitter_agent_id, args.proof);
      return JSON.stringify({
        accepted: res?.accepted === true,
        mission_id: res?.mission_id ?? args.mission_id,
        detail: res?.detail,
        raw: res,
      });
    },
  });
}

/** GET /api/stats — protocol-wide counters. */
export function buildStatsTool(client: OabpClient): DynamicStructuredTool {
  return new DynamicStructuredTool({
    name: "oabp_stats",
    description:
      "Get protocol-wide OABP/AIGEN counters: how many missions are resolved, how many are open, " +
      "and the lifetime total of AIGEN points paid out. Returns a JSON string.",
    schema: statsSchema,
    func: async () => {
      const stats = await client.getStats();
      return JSON.stringify({ stats });
    },
  });
}
