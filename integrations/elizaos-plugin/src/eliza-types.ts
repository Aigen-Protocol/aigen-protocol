/**
 * Minimal, local mirror of the `@elizaos/core` surface this plugin builds on.
 *
 * WHY THIS FILE EXISTS
 * --------------------
 * The plugin (`src/plugin.ts`) is a genuine, idiomatic ElizaOS `Plugin`: it exports `Action`s
 * (with `name`, `similes`, `validate`, `handler`, `examples`), a `Provider`, and an `Evaluator`,
 * exactly as ElizaOS defines them. In a real project you install `@elizaos/core` and the runtime
 * supplies these types and the agent loop that calls them.
 *
 * To keep this package **self-contained and offline-buildable** (`tsc --noEmit` with no
 * `npm install`, and a `node:test` that runs without a model or network), we re-declare here the
 * subset of `@elizaos/core` the plugin actually touches, faithful to upstream shapes:
 *   - `Content`, `Memory`, `State`
 *   - `HandlerCallback`, `Handler`, `Validator`
 *   - `ActionExample`, `Action`
 *   - `Provider`, `ProviderResult`
 *   - `Evaluator`, `EvaluationExample`
 *   - `IAgentRuntime` (only the members the plugin uses: `agentId`, `character`, `getSetting`)
 *   - `Plugin`
 *
 * MIGRATING TO THE REAL PACKAGE
 * -----------------------------
 * Every other module imports these from `"./eliza-types.js"`. To run inside a real ElizaOS agent,
 * either (a) install `@elizaos/core` and change those imports to `from "@elizaos/core"` — the names
 * line up 1:1 — or (b) keep this shim; ElizaOS performs duck-typed structural registration, so a
 * `Plugin` shaped exactly like upstream's is accepted as-is. The runtime values
 * (`IAgentRuntime`, `Memory`, callbacks) come from ElizaOS at runtime regardless.
 *
 * This shim contains NO logic — only type declarations — so it cannot drift behaviourally from
 * upstream; it only needs to stay structurally compatible.
 */

/** ElizaOS `UUID` — a branded string in upstream; a plain string is structurally compatible. */
export type UUID = string;

/** The content payload of a message / action result. Mirrors `@elizaos/core` `Content`. */
export interface Content {
  /** The natural-language text shown to the user / next agent. */
  text?: string;
  /** Optional action name(s) this content triggers or reports. */
  actions?: string[];
  /** Free-form action payload echoed back by handlers (kept loose, as upstream does). */
  action?: string;
  /** The user/agent this content is addressed to, when relevant. */
  source?: string;
  /** Arbitrary structured data a handler may attach (e.g. the OABP mission object). */
  [key: string]: unknown;
}

/** A stored message / fact. Mirrors the fields a plugin handler typically reads. */
export interface Memory {
  id?: UUID;
  /** The agent that owns the memory store. */
  agentId?: UUID;
  /** The conversation/thread id. */
  roomId?: UUID;
  /** The author of the message. */
  entityId?: UUID;
  /** The message body. */
  content: Content;
  /** Unix ms; present once persisted. */
  createdAt?: number;
  [key: string]: unknown;
}

/**
 * The agent's working state, threaded through providers/evaluators/handlers.
 * Upstream composes provider outputs into `state.values` / `state.text`; we model the parts a
 * provider writes and a handler reads.
 */
export interface State {
  /** Composed natural-language context block (what providers contribute to the prompt). */
  text?: string;
  /** Structured values keyed by provider, merged by the runtime. */
  values?: Record<string, unknown>;
  /** Raw provider payloads, keyed by provider name. */
  data?: Record<string, unknown>;
  [key: string]: unknown;
}

/**
 * Callback an `Action.handler` invokes to emit a response back into the conversation.
 * This is the function the SUBMIT/CREATE/LIST handlers call with their result `Content`.
 */
export type HandlerCallback = (response: Content, files?: unknown[]) => Promise<Memory[] | void>;

/** Options bag passed to a handler (kept permissive, matching upstream's `{ [key: string]: unknown }`). */
export type HandlerOptions = { [key: string]: unknown };

/** The function an `Action` runs once `validate` passes. */
export type Handler = (
  runtime: IAgentRuntime,
  message: Memory,
  state?: State,
  options?: HandlerOptions,
  callback?: HandlerCallback,
  responses?: Memory[]
) => Promise<unknown>;

/** Cheap predicate gating whether an `Action`/`Evaluator` should run for a message. */
export type Validator = (runtime: IAgentRuntime, message: Memory, state?: State) => Promise<boolean>;

/** One turn in an `Action.examples` conversation. Mirrors `@elizaos/core` `ActionExample`. */
export interface ActionExample {
  /** Speaker label (e.g. "{{user1}}", "{{agent}}"). */
  name: string;
  /** What was said / done. */
  content: Content;
}

/** A registered capability the agent can choose to perform. Mirrors `@elizaos/core` `Action`. */
export interface Action {
  name: string;
  /** Alternate phrasings that should map to this action (used by the action-selection step). */
  similes?: string[];
  /** Human description of when/why to use the action. */
  description: string;
  validate: Validator;
  handler: Handler;
  /** Few-shot conversations: an array of multi-turn examples. */
  examples?: ActionExample[][];
}

/** What a `Provider.get` returns: text injected into context plus structured values/data. */
export interface ProviderResult {
  text?: string;
  values?: Record<string, unknown>;
  data?: Record<string, unknown>;
}

/** A context contributor consulted while composing state. Mirrors `@elizaos/core` `Provider`. */
export interface Provider {
  name: string;
  description?: string;
  /** If true, only runs when explicitly requested (not on every composeState). */
  dynamic?: boolean;
  /** Ordering hint; lower runs earlier. */
  position?: number;
  get: (runtime: IAgentRuntime, message: Memory, state?: State) => Promise<ProviderResult>;
}

/** A few-shot example for an evaluator (kept minimal; upstream carries more optional fields). */
export interface EvaluationExample {
  prompt: string;
  messages: Array<{ name: string; content: Content }>;
  outcome: string;
}

/** A post-interaction reflection step. Mirrors the `@elizaos/core` `Evaluator` shape. */
export interface Evaluator {
  name: string;
  similes?: string[];
  description: string;
  /** Run even when the agent didn't explicitly act. */
  alwaysRun?: boolean;
  validate: Validator;
  handler: Handler;
  examples: EvaluationExample[];
}

/** A character definition (the subset a plugin reads). Mirrors `@elizaos/core` `Character`. */
export interface Character {
  name: string;
  bio?: string | string[];
  settings?: Record<string, unknown> & { secrets?: Record<string, unknown> };
  [key: string]: unknown;
}

/**
 * The runtime handed to validators/handlers/providers. Only the members this plugin uses are
 * declared; the real `IAgentRuntime` is much larger.
 */
export interface IAgentRuntime {
  /** This agent's id (used as the OABP submitter/creator agent id fallback). */
  agentId: UUID;
  character: Character;
  /**
   * Resolve a configuration value. ElizaOS checks character `settings`/`secrets` then env.
   * Returns `undefined` when unset.
   */
  getSetting(key: string): string | undefined;
}

/** The unit of distribution ElizaOS loads. Mirrors `@elizaos/core` `Plugin`. */
export interface Plugin {
  name: string;
  description: string;
  /** Optional async init hook (config validation, client warm-up). */
  init?: (config: Record<string, string>, runtime: IAgentRuntime) => Promise<void>;
  actions?: Action[];
  providers?: Provider[];
  evaluators?: Evaluator[];
  /** Default settings surfaced to operators (documented in the README). */
  config?: Record<string, unknown>;
}
