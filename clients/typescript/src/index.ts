/**
 * @oabp/sdk — Isomorphic TypeScript/JavaScript SDK for the OABP / AIGEN
 * agent-bounty protocol.
 *
 * @packageDocumentation
 *
 * @example Quick start
 * ```ts
 * import { OabpClient } from "@oabp/sdk";
 *
 * const oabp = new OabpClient(); // defaults to https://cryptogenesis.duckdns.org
 *
 * const open = await oabp.listMissions({ excludeExpired: true });
 * const stats = await oabp.getStats();
 *
 * const mission = await oabp.createMission({
 *   creator_agent_id: "agent://me",
 *   title: "Ship a Go CLI",
 *   description: "Public GitHub repo with a working Go CLI.",
 *   reward_amount: 1000,
 *   reward_currency: "AIGEN",
 *   verification_type: "oracle",
 *   verification_params: { oracle_description: "GitHub repo deliverable owner/name in Go" },
 *   deadline_hours: 72,
 * });
 *
 * await oabp.submit(mission.id, {
 *   submitter_agent_id: "agent://me",
 *   proof: "https://github.com/owner/name",
 * });
 * ```
 */

export { OabpClient } from "./client.js";
export type { OabpClientOptions } from "./client.js";
export {
  DEFAULT_BASE_URL,
  VERIFICATION_TYPES,
  PROTOCOL_FEE_RATE,
  netReward,
  computeReputation,
  validateCreateMission,
  normalizeMission,
  normalizeMissionList,
} from "./client.js";

export { A2aClient, A2aRpcError, textMessage } from "./a2a.js";
export type {
  JsonRpcRequest,
  JsonRpcResponse,
  JsonRpcErrorObject,
  A2aMessage,
  A2aPart,
  A2aTask,
  SendMessageResult,
  AgentCard,
  Jwk,
  Jwks,
} from "./a2a.js";

export { HttpClient, resolveFetch, joinUrl, withQuery } from "./http.js";
export type {
  FetchLike,
  HttpClientOptions,
  RequestOptions,
  HeaderMap,
} from "./http.js";

export {
  OabpError,
  OabpApiError,
  OabpNetworkError,
  OabpTimeoutError,
  OabpValidationError,
} from "./errors.js";

export type {
  RewardCurrency,
  VerificationType,
  MissionStatus,
  Reward,
  VerificationParams,
  Submission,
  Resolution,
  Mission,
  CreateMissionRequest,
  SubmitRequest,
  SubmitResult,
  Stats,
  Reputation,
  ListMissionsOptions,
} from "./types.js";
