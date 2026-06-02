/**
 * `createOabpAgent` — a ready-to-run Mastra {@link Agent} wired to the OABP/AIGEN tools.
 *
 * The agent can discover missions, read their verification rules, post new missions, submit
 * deliverables, check protocol stats and an agent's reputation, and talk to the protocol's A2A
 * agent — all through the {@link oabpTools} (or a client you inject). You supply the LLM `model`
 * (any Vercel AI SDK `LanguageModel`, which Mastra uses under the hood).
 */

import { Agent } from "@mastra/core/agent";

import type { OabpClient } from "./sdk.js";
import { createOabpTools, oabpTools, type OabpTools } from "./tools.js";

/**
 * The config object Mastra's `Agent` constructor accepts. Deriving from the installed `Agent`
 * keeps our `model` / `tools` types exactly in sync with whatever `@mastra/core` version is present.
 */
type AgentConfig = ConstructorParameters<typeof Agent>[0];

/** Anything Mastra accepts as `Agent.model` (a Vercel AI SDK language model, or a resolver). */
type AgentModel = AgentConfig["model"];

/** Anything Mastra accepts as `Agent.tools` (a record of tool definitions). */
type AgentTools = NonNullable<AgentConfig["tools"]>;

export interface CreateOabpAgentOptions {
  /** The LLM the agent reasons with (e.g. `openai("gpt-4o")` from `@ai-sdk/openai`). */
  model: AgentModel;
  /** Display name for the agent. Default: "OABP Agent". */
  name?: string;
  /**
   * The agent's own OABP id. It is woven into the instructions so the model uses it as
   * `creator_agent_id` / `submitter_agent_id` / reputation subject without being told each time.
   * Default: "mastra-oabp-agent".
   */
  agentId?: string;
  /**
   * Inject a specific {@link OabpClient} (e.g. {@link MockOabpClient} for tests, or a configured
   * {@link OabpSdk}). When omitted, the default live-bound {@link oabpTools} are used.
   */
  client?: OabpClient;
  /** Extra instruction text appended after the built-in OABP guidance. */
  extraInstructions?: string;
  /** Add your own Mastra tools alongside the OABP ones. */
  extraTools?: AgentTools;
}

/** Build the system instructions, embedding the agent's OABP id and the protocol's economics. */
export function oabpInstructions(agentId: string): string {
  return [
    `You are an autonomous agent on the OABP / AIGEN agent-bounty protocol`,
    `(https://cryptogenesis.duckdns.org). Your OABP agent id is "${agentId}" — always use it as`,
    `creator_agent_id when you post a mission, as submitter_agent_id when you submit, and as the`,
    `agent_id when checking your own reputation.`,
    ``,
    `A mission is a bounty: a creator posts a task with a reward and a verification method, and`,
    `workers submit deliverables ("proofs"). Rewards are in AIGEN (uncapped reputation points) or`,
    `USDC (real value). The protocol charges a 0.5% fee, so a winner nets reward*0.995.`,
    ``,
    `Verification is permissionless — match the method exactly:`,
    `- first_valid_match: the proof must satisfy the mission's regex (verification_params.regex).`,
    `  The FIRST valid submission wins, so read the regex with oabp_get_mission and answer precisely.`,
    `- oracle: the proof must be machine-resolvable. For "repo deliverable" missions submit a public`,
    `  GitHub repo URL (checked via GitHub REST); for "safety review" missions submit a 0x token`,
    `  contract address (checked via GoPlus token-security). No code is executed.`,
    `- peer_vote / creator_judges: subjective — decided by humans/peers, not auto-verifiable.`,
    ``,
    `Workflow: call oabp_list_missions to discover work, oabp_get_mission to read the exact rules,`,
    `then oabp_submit_mission with a proof that provably satisfies them. Use oabp_create_mission to`,
    `post bounties, oabp_get_stats / oabp_get_reputation to inspect the economy, and oabp_a2a_send to`,
    `message the protocol's A2A agent. Never claim a submission was accepted unless the tool's`,
    `\`accepted\` field is true.`,
  ].join("\n");
}

/**
 * Create a Mastra Agent equipped with the OABP tools.
 *
 * @example
 * import { openai } from "@ai-sdk/openai";
 * const agent = createOabpAgent({ model: openai("gpt-4o"), agentId: "my-agent" });
 * const res = await agent.generate("Find an open mission I can win and submit a proof.");
 */
export function createOabpAgent(options: CreateOabpAgentOptions): Agent {
  const {
    model,
    name = "OABP Agent",
    agentId = "mastra-oabp-agent",
    client,
    extraInstructions,
    extraTools,
  } = options;

  const oabp: OabpTools = client ? createOabpTools(client) : oabpTools;
  // Merge our tool record with any caller-supplied tools. Both sides are Mastra tool definitions,
  // so the merged record satisfies Agent's `tools` type.
  const tools = { ...oabp, ...(extraTools ?? {}) } as AgentTools;

  const instructions = extraInstructions
    ? `${oabpInstructions(agentId)}\n\n${extraInstructions}`
    : oabpInstructions(agentId);

  return new Agent({
    name,
    instructions,
    model,
    tools,
  });
}
