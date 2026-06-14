import { HttpClient } from './http.js';
import { A2ARpcError, OabpError } from './errors.js';

/** A2A message part (text is the part type the protocol relies on). */
export interface TextPart {
  kind: 'text';
  text: string;
}

/** A part referencing structured data. */
export interface DataPart {
  kind: 'data';
  data: unknown;
}

/** A part referencing a file by URI or inline bytes. */
export interface FilePart {
  kind: 'file';
  file: { uri?: string; bytes?: string; name?: string; mimeType?: string };
}

export type Part = TextPart | DataPart | FilePart;

/** An A2A message. */
export interface Message {
  role: 'user' | 'agent';
  parts: Part[];
  messageId?: string;
  taskId?: string;
  contextId?: string;
  kind?: 'message';
  [key: string]: unknown;
}

/** A2A task lifecycle states. */
export type TaskState =
  | 'submitted'
  | 'working'
  | 'input-required'
  | 'completed'
  | 'canceled'
  | 'failed'
  | 'rejected'
  | 'unknown';

export interface TaskStatus {
  state: TaskState;
  message?: Message;
  timestamp?: string;
}

/** An A2A task returned by `message/send`, `tasks/get`, `tasks/list`. */
export interface Task {
  id: string;
  contextId?: string;
  status: TaskStatus;
  history?: Message[];
  artifacts?: Array<Record<string, unknown>>;
  kind?: 'task';
  [key: string]: unknown;
}

/** A `message/send` result is either a direct Message or a Task. */
export type SendMessageResult = Message | Task;

interface JsonRpcRequest {
  jsonrpc: '2.0';
  id: number | string;
  method: string;
  params?: unknown;
}

interface JsonRpcResponse<T> {
  jsonrpc: '2.0';
  id: number | string | null;
  result?: T;
  error?: { code: number; message: string; data?: unknown };
}

export interface A2AClientOptions {
  /** Full URL of the A2A JSON-RPC endpoint, e.g. `…/api/a2a`. */
  endpoint: string;
  /** Shared HttpClient (reuses fetch impl, headers, timeout). */
  http: HttpClient;
}

/**
 * Minimal, spec-faithful A2A JSON-RPC client.
 *
 * Supports the methods the OABP endpoint exposes: `message/send`, `tasks/get`,
 * and `tasks/list`. Each call is a single JSON-RPC 2.0 request; transport
 * errors surface as {@link OabpHttpError} and RPC errors as {@link A2ARpcError}.
 */
export class A2AClient {
  private readonly http: HttpClient;
  private readonly endpoint: string;
  private idCounter = 0;

  constructor(opts: A2AClientOptions) {
    this.http = opts.http;
    this.endpoint = opts.endpoint;
  }

  /** Send a message; returns a Message or a Task per the A2A spec. */
  async sendMessage(
    message: Message,
    configuration?: Record<string, unknown>,
  ): Promise<SendMessageResult> {
    const params: Record<string, unknown> = { message };
    if (configuration !== undefined) params['configuration'] = configuration;
    return this.call<SendMessageResult>('message/send', params);
  }

  /** Convenience: send a single text message as the user role. */
  async sendText(
    text: string,
    extra?: Partial<Omit<Message, 'parts' | 'role'>>,
  ): Promise<SendMessageResult> {
    const message: Message = {
      ...extra,
      role: 'user',
      parts: [{ kind: 'text', text }],
      messageId:
        typeof extra?.messageId === 'string' ? extra.messageId : randomId(),
    };
    return this.sendMessage(message);
  }

  /** Fetch a task by id. `historyLength` caps returned history when supported. */
  async getTask(id: string, historyLength?: number): Promise<Task> {
    const params: Record<string, unknown> = { id };
    if (historyLength !== undefined) params['historyLength'] = historyLength;
    return this.call<Task>('tasks/get', params);
  }

  /** List tasks. The endpoint may return an array or a `{ tasks: [...] }`. */
  async listTasks(
    params: Record<string, unknown> = {},
  ): Promise<Task[]> {
    const result = await this.call<Task[] | { tasks?: Task[] }>(
      'tasks/list',
      params,
    );
    if (Array.isArray(result)) return result;
    return result.tasks ?? [];
  }

  /** Issue a raw JSON-RPC call against the A2A endpoint. */
  async call<T>(method: string, params?: unknown): Promise<T> {
    const id = ++this.idCounter;
    const request: JsonRpcRequest = { jsonrpc: '2.0', id, method };
    if (params !== undefined) request.params = params;

    const res = await this.http.postJson<JsonRpcResponse<T>>(
      this.endpoint,
      request,
    );

    if (res == null || typeof res !== 'object') {
      throw new OabpError(
        `A2A endpoint returned a non-object response for ${method}`,
      );
    }
    if (res.error) {
      throw new A2ARpcError({
        code: res.error.code,
        message: res.error.message,
        data: res.error.data,
      });
    }
    if (!('result' in res)) {
      throw new OabpError(
        `A2A response for ${method} had neither result nor error`,
      );
    }
    return res.result as T;
  }
}

function randomId(): string {
  const c = (globalThis as { crypto?: Crypto }).crypto;
  if (c && typeof c.randomUUID === 'function') return c.randomUUID();
  return `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}
