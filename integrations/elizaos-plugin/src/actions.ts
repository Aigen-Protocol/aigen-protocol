/**
 * ElizaOS Actions for the OABP / AIGEN agent-bounty protocol.
 *
 *   - LIST_OABP_MISSIONS    GET  /api/missions   — show open, claimable missions
 *   - CREATE_OABP_MISSION   POST /api/missions   — post a new bounty
 *   - SUBMIT_OABP_MISSION   POST /missions/{id}/submit — submit a deliverable (claim = submit)
 *
 * Each is a genuine `Action` with `name`, `similes`, `validate`, `handler`, and `examples`
 * (multi-turn conversations in ElizaOS's `ActionExample[][]` format). Handlers route all I/O
 * through the runtime-resolved {@link OabpClient} (`getClient`), so they run unchanged against the
 * live API or an injected mock, and emit results via the ElizaOS `callback(content)`.
 */

import type { Action, Content, HandlerCallback, IAgentRuntime, Memory, State } from "./eliza-types.js";
import type {
  CreateMissionInput,
  Mission,
  RewardCurrency,
  VerificationType,
} from "./sdk.js";
import {
  extractMissionId,
  extractProof,
  getAgentId,
  getClient,
  isOpen,
  netReward,
  summarizeMission,
} from "./runtime.js";

/** Safely read the user message text. */
function messageText(message: Memory): string {
  return (message?.content?.text ?? "").toString();
}

/** Emit content through the ElizaOS callback (if provided) and also return it as the handler result. */
async function reply(callback: HandlerCallback | undefined, content: Content): Promise<Content> {
  if (callback) await callback(content);
  return content;
}

/* ------------------------------------------------------------------ *
 * LIST_OABP_MISSIONS
 * ------------------------------------------------------------------ */

export const listOabpMissionsAction: Action = {
  name: "LIST_OABP_MISSIONS",
  similes: [
    "LIST_MISSIONS",
    "SHOW_MISSIONS",
    "OABP_MISSIONS",
    "OPEN_BOUNTIES",
    "FIND_BOUNTIES",
    "WHAT_BOUNTIES",
    "BROWSE_OABP",
  ],
  description:
    "List the currently OPEN missions (bounties) on the OABP/AIGEN marketplace, with rewards, " +
    "verification method, and time left. Use when the user asks what bounties/missions/tasks are " +
    "available to work on.",

  validate: async (runtime: IAgentRuntime, message: Memory): Promise<boolean> => {
    const t = messageText(message).toLowerCase();
    // Cheap intent gate: mentions a marketplace concept + a "list/show/available" verb.
    const noun = /(mission|bounty|bounties|task|marketplace|oabp|aigen)/.test(t);
    const verb = /(list|show|what|which|open|available|browse|find|see|any)/.test(t);
    return noun && verb;
  },

  handler: async (
    runtime: IAgentRuntime,
    _message: Memory,
    _state?: State,
    _options?: Record<string, unknown>,
    callback?: HandlerCallback
  ): Promise<Content> => {
    const client = getClient(runtime);
    try {
      const all = await client.listMissions();
      const open = all.filter((m) => isOpen(m));
      if (open.length === 0) {
        return reply(callback, {
          text: "No open OABP missions right now. Check back soon, or post one with CREATE_OABP_MISSION.",
          actions: ["LIST_OABP_MISSIONS"],
        });
      }
      const lines = open
        .slice()
        .sort((a, b) => rewardWeight(b) - rewardWeight(a))
        .map(summarizeMission);
      return reply(callback, {
        text: `${open.length} open OABP mission(s):\n${lines.join("\n")}`,
        actions: ["LIST_OABP_MISSIONS"],
        missions: open,
      });
    } catch (err) {
      return reply(callback, {
        text: `Could not fetch OABP missions: ${(err as Error).message}`,
        actions: ["LIST_OABP_MISSIONS"],
      });
    }
  },

  examples: [
    [
      { name: "{{user1}}", content: { text: "What OABP missions are open right now?" } },
      {
        name: "{{agent}}",
        content: {
          text: "2 open OABP mission(s):\n- [m-42] Ship a Go CLI deliverable — 5 USDC ...\n- [demo-fvm] Emit the magic build token — 25 AIGEN ...",
          actions: ["LIST_OABP_MISSIONS"],
        },
      },
    ],
    [
      { name: "{{user1}}", content: { text: "show me the available bounties on the marketplace" } },
      {
        name: "{{agent}}",
        content: { text: "Here are the open bounties on OABP:", actions: ["LIST_OABP_MISSIONS"] },
      },
    ],
  ],
};

/* ------------------------------------------------------------------ *
 * CREATE_OABP_MISSION
 * ------------------------------------------------------------------ */

/** Parsed fields for a create request, with sensible defaults filled by `parseCreateRequest`. */
interface ParsedCreate {
  title: string;
  description: string;
  reward_amount: number;
  reward_currency: RewardCurrency;
  verification_type: VerificationType;
  verification_params: { regex?: string; oracle_description?: string };
  deadline_hours: number;
}

/**
 * Best-effort parser turning a natural-language "post a bounty" request into a CreateMissionInput.
 * It is deterministic and dependency-free (no LLM), so the action works in tests; an embedding
 * agent can also pass fully-structured fields via `options` (see handler).
 */
export function parseCreateRequest(text: string): ParsedCreate {
  const t = text || "";

  // reward: "<amount> <AIGEN|USDC>" (default 10 AIGEN)
  const rewardM = t.match(/\b(\d+(?:\.\d+)?)\s*(aigen|usdc)\b/i);
  const reward_amount = rewardM ? Number(rewardM[1]) : 10;
  const reward_currency: RewardCurrency = rewardM && /usdc/i.test(rewardM[2]) ? "USDC" : "AIGEN";

  // deadline: "in <n> hours/days" (default 24h)
  let deadline_hours = 24;
  const hM = t.match(/\b(\d+)\s*h(?:ours?)?\b/i);
  const dM = t.match(/\b(\d+)\s*d(?:ays?)?\b/i);
  if (hM) deadline_hours = Number(hM[1]);
  else if (dM) deadline_hours = Number(dM[1]) * 24;

  // verification: regex (content-addressed) wins; else "safety/token" or "repo/github" -> oracle.
  const regexM = t.match(/\bregex[\s:]+\/?([^/\n]+?)\/?(?:\s|$)/i) || t.match(/\/(\^[^/\n]+\$)\//);
  let verification_type: VerificationType;
  const verification_params: ParsedCreate["verification_params"] = {};
  if (regexM) {
    verification_type = "first_valid_match";
    verification_params.regex = regexM[1].trim();
  } else if (/\b(safety|token[- ]?security|goplus|rug)\b/i.test(t)) {
    verification_type = "oracle";
    verification_params.oracle_description = "GoPlus token-security safety review";
  } else if (/\b(repo|repository|github|deliverable|code)\b/i.test(t)) {
    verification_type = "oracle";
    verification_params.oracle_description = "GitHub repo deliverable";
  } else {
    // No machine-verifiable signal -> creator judges (subjective).
    verification_type = "creator_judges";
  }

  // title: explicit `title: ...` else first sentence/line, trimmed.
  const titleM = t.match(/\btitle[\s:]+([^\n.]+)/i);
  const title = (titleM ? titleM[1] : firstClause(t) || "Untitled OABP mission").trim().slice(0, 120);

  // description: explicit `desc: ...` else the whole prompt.
  const descM = t.match(/\b(?:desc|description)[\s:]+([^\n]+)/i);
  const description = (descM ? descM[1] : t || title).trim().slice(0, 1000);

  return {
    title,
    description,
    reward_amount,
    reward_currency,
    verification_type,
    verification_params,
    deadline_hours,
  };
}

function firstClause(t: string): string {
  const stripped = t.replace(/^\s*(create|post|open|add|make|new)\b[\s:]*/i, "");
  const m = stripped.match(/^[^.\n]{3,80}/);
  return m ? m[0] : "";
}

export const createOabpMissionAction: Action = {
  name: "CREATE_OABP_MISSION",
  similes: [
    "CREATE_MISSION",
    "POST_MISSION",
    "POST_BOUNTY",
    "OPEN_BOUNTY",
    "NEW_MISSION",
    "ADD_MISSION",
    "OFFER_BOUNTY",
  ],
  description:
    "Create (post) a new mission/bounty on the OABP/AIGEN marketplace: a title, description, " +
    "reward (AIGEN points or USDC), a verification method, and a deadline. Use when the user wants " +
    "to OFFER a task for other agents to complete.",

  validate: async (runtime: IAgentRuntime, message: Memory): Promise<boolean> => {
    const t = messageText(message).toLowerCase();
    const verb = /(create|post|open|add|make|offer|new)\b/.test(t);
    const noun = /(mission|bounty|task)/.test(t);
    return verb && noun;
  },

  handler: async (
    runtime: IAgentRuntime,
    message: Memory,
    _state?: State,
    options?: Record<string, unknown>,
    callback?: HandlerCallback
  ): Promise<Content> => {
    const client = getClient(runtime);
    const creator_agent_id = getAgentId(runtime);

    // An embedding agent may pass fully-structured fields via `options`; else parse the text.
    const parsed = parseCreateRequest(messageText(message));
    const input: CreateMissionInput = {
      creator_agent_id,
      title: (options?.title as string) ?? parsed.title,
      description: (options?.description as string) ?? parsed.description,
      reward_amount: (options?.reward_amount as number) ?? parsed.reward_amount,
      reward_currency: (options?.reward_currency as RewardCurrency) ?? parsed.reward_currency,
      verification_type: (options?.verification_type as VerificationType) ?? parsed.verification_type,
      verification_params:
        (options?.verification_params as CreateMissionInput["verification_params"]) ??
        parsed.verification_params,
      deadline_hours: (options?.deadline_hours as number) ?? parsed.deadline_hours,
    };

    try {
      const mission = await client.createMission(input);
      const id = mission?.id ?? "(pending)";
      return reply(callback, {
        text:
          `Posted OABP mission [${id}] "${input.title}" — reward ${input.reward_amount} ` +
          `${input.reward_currency} (net ${netReward(input.reward_amount)} after 0.5% fee), ` +
          `verify=${input.verification_type}, deadline in ${input.deadline_hours}h.`,
        actions: ["CREATE_OABP_MISSION"],
        mission,
      });
    } catch (err) {
      return reply(callback, {
        text: `Could not create OABP mission: ${(err as Error).message}`,
        actions: ["CREATE_OABP_MISSION"],
      });
    }
  },

  examples: [
    [
      {
        name: "{{user1}}",
        content: {
          text: "Post a bounty: title: Build a Go CLI; reward 5 USDC; github repo deliverable; in 48 hours",
        },
      },
      {
        name: "{{agent}}",
        content: {
          text: 'Posted OABP mission [m-77] "Build a Go CLI" — reward 5 USDC (net 4.975 after 0.5% fee), verify=oracle, deadline in 48h.',
          actions: ["CREATE_OABP_MISSION"],
        },
      },
    ],
    [
      {
        name: "{{user1}}",
        content: { text: "create a mission rewarding 25 AIGEN, proof must match regex /^BUILD-\\d{4}$/" },
      },
      {
        name: "{{agent}}",
        content: {
          text: 'Posted OABP mission [demo-fvm] "rewarding 25 AIGEN" — reward 25 AIGEN ..., verify=first_valid_match, deadline in 24h.',
          actions: ["CREATE_OABP_MISSION"],
        },
      },
    ],
  ],
};

/* ------------------------------------------------------------------ *
 * SUBMIT_OABP_MISSION
 * ------------------------------------------------------------------ */

export const submitOabpMissionAction: Action = {
  name: "SUBMIT_OABP_MISSION",
  similes: [
    "SUBMIT_MISSION",
    "CLAIM_MISSION",
    "SUBMIT_PROOF",
    "SUBMIT_DELIVERABLE",
    "COMPLETE_MISSION",
    "ANSWER_MISSION",
    "WORK_MISSION",
  ],
  description:
    "Submit a deliverable ('proof') to an OABP mission to claim its reward (in OABP, claiming IS " +
    "submitting). Use when the user wants to complete/answer/claim a specific mission and has a " +
    "deliverable (a string, a URL, a GitHub repo, or a token address).",

  validate: async (runtime: IAgentRuntime, message: Memory): Promise<boolean> => {
    const t = messageText(message).toLowerCase();
    const verb = /(submit|claim|complete|answer|deliver|work on)\b/.test(t);
    const noun = /(mission|bounty|proof|deliverable|#)/.test(t);
    return verb && noun;
  },

  handler: async (
    runtime: IAgentRuntime,
    message: Memory,
    _state?: State,
    options?: Record<string, unknown>,
    callback?: HandlerCallback
  ): Promise<Content> => {
    const client = getClient(runtime);
    const submitter_agent_id = getAgentId(runtime);
    const text = messageText(message);

    // Resolve which mission: explicit option > id parsed from text (validated against open list).
    let missionId: string | undefined =
      (options?.missionId as string | undefined) ?? (options?.mission_id as string | undefined);
    let open: Mission[] = [];
    if (!missionId) {
      try {
        open = (await client.listMissions()).filter((m) => isOpen(m));
      } catch {
        open = [];
      }
      missionId = extractMissionId(text, open.map((m) => m.id));
    }

    if (!missionId) {
      return reply(callback, {
        text:
          "Which mission should I submit to? Tell me the mission id (e.g. `submit mission m-42 proof: ...`). " +
          (open.length ? `Open: ${open.map((m) => m.id).join(", ")}.` : ""),
        actions: ["SUBMIT_OABP_MISSION"],
      });
    }

    const proof = (options?.proof as string) ?? extractProof(text);
    if (!proof) {
      return reply(callback, {
        text: `I have mission ${missionId} but no deliverable. Give me a proof (a URL, a GitHub repo, a token address, or text) e.g. \`proof: https://github.com/me/repo\`.`,
        actions: ["SUBMIT_OABP_MISSION"],
      });
    }

    try {
      const result = await client.submit(missionId, submitter_agent_id, proof);
      const accepted = result?.accepted;
      const verdict =
        accepted === true ? "ACCEPTED ✅" : accepted === false ? "not accepted ❌" : "submitted (pending verification)";
      const detail = result?.detail ? ` — ${result.detail}` : "";
      return reply(callback, {
        // Acceptance criterion: callback text contains the mission id.
        text: `Submitted deliverable to OABP mission ${missionId}: ${verdict}${detail}`,
        actions: ["SUBMIT_OABP_MISSION"],
        missionId,
        accepted,
        result,
      });
    } catch (err) {
      return reply(callback, {
        text: `Could not submit to OABP mission ${missionId}: ${(err as Error).message}`,
        actions: ["SUBMIT_OABP_MISSION"],
        missionId,
      });
    }
  },

  examples: [
    [
      {
        name: "{{user1}}",
        content: { text: "submit mission demo-fvm proof: BUILD-0000" },
      },
      {
        name: "{{agent}}",
        content: {
          text: "Submitted deliverable to OABP mission demo-fvm: ACCEPTED ✅ — regex matched",
          actions: ["SUBMIT_OABP_MISSION"],
        },
      },
    ],
    [
      {
        name: "{{user1}}",
        content: { text: "claim mission m-77, here is my deliverable https://github.com/me/go-cli" },
      },
      {
        name: "{{agent}}",
        content: {
          text: "Submitted deliverable to OABP mission m-77: ACCEPTED ✅ — github repo present",
          actions: ["SUBMIT_OABP_MISSION"],
        },
      },
    ],
  ],
};

/** Reward weight used to sort the LIST output: USDC weighted ~1000× the uncapped AIGEN points. */
function rewardWeight(m: Mission): number {
  return m.reward.currency === "USDC" ? m.reward.amount * 1000 : m.reward.amount;
}

/** All three actions, in registration order. */
export const oabpActions: Action[] = [
  listOabpMissionsAction,
  createOabpMissionAction,
  submitOabpMissionAction,
];
