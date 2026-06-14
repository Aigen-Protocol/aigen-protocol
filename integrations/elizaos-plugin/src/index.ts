/**
 * @aigen/plugin-oabp — ElizaOS plugin (Actions + Provider + Evaluator) for the OABP / AIGEN
 * agent-bounty protocol.
 *
 * Public surface:
 *   - default + `oabpPlugin`                              (plugin.ts) — the ElizaOS Plugin object
 *   - LIST/CREATE/SUBMIT actions + `oabpActions`          (actions.ts)
 *   - `oabpMarketplaceProvider`                           (provider.ts)
 *   - `claimedMissionsEvaluator`, `getClaimLedger`, ...   (evaluator.ts)
 *   - `getClient`, `getAgentId`, `FEE_RATE`, `netReward`,
 *     `OABP_BASE_URL`, `OABP_AGENT_ID`, helpers           (runtime.ts)
 *   - `OabpSdk`, `OabpClient`, `OabpError`, protocol types (sdk.ts)
 *   - `MockOabpClient`, `MockSeed`                         (mock.ts)
 *   - ElizaOS-compatible type re-exports                  (eliza-types.ts)
 */

// Named exports from the plugin module (incl. `oabpPlugin`), plus its default re-exported as the
// package default (the ElizaOS Plugin object).
export * from "./plugin.js";
export { default } from "./plugin.js";

export * from "./actions.js";
export * from "./provider.js";
export * from "./evaluator.js";
export * from "./runtime.js";
export * from "./sdk.js";
export * from "./mock.js";
// Re-export the ElizaOS-compatible types so embedders can use them without a second import.
export type {
  Action,
  ActionExample,
  Content,
  Evaluator,
  EvaluationExample,
  Handler,
  HandlerCallback,
  IAgentRuntime,
  Memory,
  Plugin,
  Provider,
  ProviderResult,
  State,
  Validator,
} from "./eliza-types.js";
