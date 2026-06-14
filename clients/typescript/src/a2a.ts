/**
 * A2A (Agent-to-Agent) JSON-RPC 2.0 client for the OABP protocol.
 *
 * The protocol exposes an A2A endpoint at `POST /api/a2a` with the methods
 * `message/send`, `tasks/get`, and `tasks/list`, an ES256-signed agent card at
 * `/.well-known/agent-card.json`, and a JWKS at `/.well-known/jwks.json`.
 *
 * This client speaks the JSON-RPC envelope, surfaces RPC-level errors as typed
 * exceptions, and can fetch the agent card and JWKS so callers can verify the
 * card signature with their own crypto library if desired.
 */

import type { HttpClient } from "./http.js";
import { OabpError } from "./errors.js";

/** JSON-RPC 2.0 request envelope. */
export interface JsonRpcRequest<P = unknown> {
  jsonrpc: "2.0";
  id: string | number;
  method: string;
  params?: P;
}

/** JSON-RPC 2.0 error object. */
export interface JsonRpcErrorObject {
  code: number;
  message: string;
  data?: unknown;
}

/** JSON-RPC 2.0 response envelope. */
export interface JsonRpcResponse<R = unknown> {
  jsonrpc: "2.0";
  id: string | number | null;
  result?: R;
  error?: JsonRpcErrorObject;
}

/** Thrown when an A2A JSON-RPC call returns an `error` member. */
export class A2aRpcError extends OabpError {
  readonly code: number;
  readonly data: unknown;
  constructor(err: JsonRpcErrorObject) {
    super(`A2A RPC error ${err.code}: ${err.message}`);
    this.name = "A2aRpcError";
    this.code = err.code;
    this.data = err.data;
  }
}

/** A part of an A2A message (text is the common case for OABP). */
export interface A2aPart {
  kind: "text" | "file" | "data";
  text?: string;
  [key: string]: unknown;
}

/** An A2A message. */
export interface A2aMessage {
  role: "user" | "agent";
  parts: A2aPart[];
  messageId?: string;
  [key: string]: unknown;
}

/** An A2A task as returned by `tasks/get` / `tasks/list`. */
export interface A2aTask {
  id: string;
  status?: { state?: string; [key: string]: unknown };
  history?: A2aMessage[];
  artifacts?: unknown[];
  [key: string]: unknown;
}

/** Result of `message/send`: either a direct message or a created task. */
export type SendMessageResult = A2aMessage | A2aTask;

/** Public signing key entry from the JWKS document. */
export interface Jwk {
  kty: string;
  crv?: string;
  x?: string;
  y?: string;
  kid?: string;
  alg?: string;
  use?: string;
  [key: string]: unknown;
}

/** JWKS document at `/.well-known/jwks.json`. */
export interface Jwks {
  keys: Jwk[];
}

/** The agent card served at `/.well-known/agent-card.json`. */
export interface AgentCard {
  name: string;
  description?: string;
  url?: string;
  version?: string;
  capabilities?: Record<string, unknown>;
  skills?: Array<Record<string, unknown>>;
  /** Detached JWS signatures over the card, when the server signs it. */
  signatures?: Array<{ protected: string; signature: string; header?: unknown }>;
  [key: string]: unknown;
}

/** Convenience helper to build a single-text-part user message. */
export function textMessage(text: string, messageId?: string): A2aMessage {
  const msg: A2aMessage = { role: "user", parts: [{ kind: "text", text }] };
  if (messageId !== undefined) msg.messageId = messageId;
  return msg;
}

let rpcCounter = 0;
function nextRpcId(): string {
  rpcCounter += 1;
  // Best-effort unique id; collisions don't matter functionally but help logs.
  return `oabp-${Date.now().toString(36)}-${rpcCounter}`;
}

/** A2A JSON-RPC client bound to an {@link HttpClient}. */
export class A2aClient {
  private readonly http: HttpClient;
  private readonly rpcPath: string;

  constructor(http: HttpClient, rpcPath = "/api/a2a") {
    this.http = http;
    this.rpcPath = rpcPath;
  }

  /** Low-level JSON-RPC call. Throws {@link A2aRpcError} on RPC errors. */
  async call<R, P = unknown>(
    method: string,
    params?: P,
    signal?: AbortSignal,
  ): Promise<R> {
    const id = nextRpcId();
    const payload: JsonRpcRequest<P> = { jsonrpc: "2.0", id, method };
    if (params !== undefined) payload.params = params;

    const res = await this.http.post<JsonRpcResponse<R>>(this.rpcPath, payload, {
      ...(signal ? { signal } : {}),
    });

    if (res.error) throw new A2aRpcError(res.error);
    return res.result as R;
  }

  /** `message/send` — send a message, returns a message or a created task. */
  sendMessage(
    message: A2aMessage,
    options?: { configuration?: Record<string, unknown>; signal?: AbortSignal },
  ): Promise<SendMessageResult> {
    const params: Record<string, unknown> = { message };
    if (options?.configuration) params["configuration"] = options.configuration;
    return this.call<SendMessageResult>("message/send", params, options?.signal);
  }

  /** Convenience: send a plain-text message in one call. */
  sendText(text: string, signal?: AbortSignal): Promise<SendMessageResult> {
    return this.sendMessage(textMessage(text), signal ? { signal } : undefined);
  }

  /** `tasks/get` — fetch a task by id. */
  getTask(id: string, signal?: AbortSignal): Promise<A2aTask> {
    return this.call<A2aTask>("tasks/get", { id }, signal);
  }

  /** `tasks/list` — list tasks (optionally filtered by server-supported keys). */
  listTasks(
    params?: Record<string, unknown>,
    signal?: AbortSignal,
  ): Promise<A2aTask[]> {
    return this.call<A2aTask[]>("tasks/list", params ?? {}, signal);
  }

  /** Fetch the ES256-signed agent card. */
  getAgentCard(signal?: AbortSignal): Promise<AgentCard> {
    return this.http.get<AgentCard>("/.well-known/agent-card.json", signal ? { signal } : undefined);
  }

  /** Fetch the JWKS used to verify the agent-card signature. */
  getJwks(signal?: AbortSignal): Promise<Jwks> {
    return this.http.get<Jwks>("/.well-known/jwks.json", signal ? { signal } : undefined);
  }
}
