/**
 * @aigen/mastra-oabp — Mastra (TS) tool definitions & an agent for the OABP / AIGEN protocol.
 *
 * Public surface:
 *   - oabpTools, createOabpTools, OabpTools,
 *     FEE_RATE, netReward                              (tools.ts)
 *   - createOabpAgent, oabpInstructions,
 *     CreateOabpAgentOptions                           (agent.ts)
 *   - OabpSdk, OabpClient, OabpError, and protocol types (sdk.ts)
 *   - MockOabpClient, MockSeed                          (mock.ts)
 */

export * from "./sdk.js";
export * from "./tools.js";
export * from "./agent.js";
export * from "./mock.js";
