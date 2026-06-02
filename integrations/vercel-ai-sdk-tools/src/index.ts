/**
 * @aigen/ai-sdk-oabp — Vercel AI SDK `tool()` definitions for the OABP / AIGEN agent-bounty protocol.
 *
 * Public surface:
 *   - oabpTools, defaultOabpTools, OabpToolSet,
 *     FEE_RATE, netReward                              (tools.ts)
 *   - OabpSdk, OabpClient, OabpError, and protocol types (sdk.ts)
 *   - MockOabpClient, MockSeed                          (mock.ts)
 *
 * Typical use:
 *   import { generateText } from "ai";
 *   import { openai } from "@ai-sdk/openai";
 *   import { oabpTools } from "@aigen/ai-sdk-oabp";
 *
 *   const { text } = await generateText({
 *     model: openai("gpt-4o"),
 *     tools: oabpTools(),          // -> https://cryptogenesis.duckdns.org
 *     maxSteps: 5,
 *     prompt: "Find and claim a first_valid_match mission.",
 *   });
 */

export * from "./sdk.js";
export * from "./tools.js";
export * from "./mock.js";
