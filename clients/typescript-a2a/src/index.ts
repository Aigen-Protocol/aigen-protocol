/**
 * @oabp/a2a-client — TypeScript client for the OABP / AIGEN protocol.
 *
 * Public surface:
 *  - {@link OabpClient}  REST missions + stats + signed agent card + A2A
 *  - {@link A2AClient}   A2A JSON-RPC (message/send, tasks/get, tasks/list)
 *  - {@link verifyAgentCard}  standalone ES256 agent-card verification
 *  - domain & error types
 */

export { OabpClient, type OabpClientOptions } from './client.js';

export {
  A2AClient,
  type A2AClientOptions,
  type Message,
  type Part,
  type TextPart,
  type DataPart,
  type FilePart,
  type Task,
  type TaskStatus,
  type TaskState,
  type SendMessageResult,
} from './a2a.js';

export {
  verifyAgentCard,
  canonicalPayloadBytes,
  toKeyResolver,
  defaultJwksUrl,
  type VerifyAgentCardOptions,
  type VerifiedAgentCard,
  type JsonWebKeySet,
  type KeyResolver,
} from './agentCard.js';

export { canonicalize } from './jcs.js';

export {
  HttpClient,
  type HttpClientOptions,
  type FetchLike,
  type FetchLikeResponse,
} from './http.js';

export {
  OabpError,
  OabpHttpError,
  A2ARpcError,
  AgentCardVerificationError,
} from './errors.js';

export type {
  Mission,
  CreateMissionInput,
  SubmitInput,
  Submission,
  Resolution,
  Reward,
  RewardCurrency,
  VerificationType,
  VerificationParams,
  MissionStatus,
  ProtocolStats,
  AgentCard,
  AgentCardSignature,
} from './types.js';
