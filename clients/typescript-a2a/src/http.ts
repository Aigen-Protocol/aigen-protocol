import { OabpHttpError } from './errors.js';

/**
 * Minimal `fetch` signature the SDK depends on. Native `fetch` (Node >= 18,
 * all modern browsers, Deno, Bun) satisfies this, and tests can inject a stub.
 */
export type FetchLike = (
  input: string,
  init?: {
    method?: string;
    headers?: Record<string, string>;
    body?: string;
    signal?: AbortSignal;
  },
) => Promise<FetchLikeResponse>;

export interface FetchLikeResponse {
  ok: boolean;
  status: number;
  statusText: string;
  text(): Promise<string>;
}

export interface HttpClientOptions {
  baseUrl: string;
  /** Defaults to the runtime's global `fetch`. */
  fetch?: FetchLike;
  /** Extra headers merged into every request (e.g. an auth token). */
  headers?: Record<string, string>;
  /** Per-request timeout in milliseconds. Set 0 to disable. Default 30000. */
  timeoutMs?: number;
}

/** Thin JSON-over-HTTP helper with timeouts and typed error surfacing. */
export class HttpClient {
  readonly baseUrl: string;
  private readonly fetchImpl: FetchLike;
  private readonly headers: Record<string, string>;
  private readonly timeoutMs: number;

  constructor(opts: HttpClientOptions) {
    const f = opts.fetch ?? resolveGlobalFetch();
    this.fetchImpl = f;
    this.baseUrl = stripTrailingSlash(opts.baseUrl);
    this.headers = { ...(opts.headers ?? {}) };
    this.timeoutMs = opts.timeoutMs ?? 30_000;
  }

  /** Resolve a path against the base URL. Absolute URLs pass through. */
  resolve(path: string): string {
    if (/^https?:\/\//i.test(path)) return path;
    return `${this.baseUrl}/${path.replace(/^\/+/, '')}`;
  }

  async getJson<T>(path: string): Promise<T> {
    return this.request<T>('GET', path);
  }

  async postJson<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>('POST', path, body);
  }

  /** Fetch a raw text body (used for agent cards / JWKS documents). */
  async getText(path: string): Promise<string> {
    const res = await this.send('GET', this.resolve(path));
    const text = await res.text();
    if (!res.ok) throw httpError(res, this.resolve(path), text);
    return text;
  }

  private async request<T>(
    method: 'GET' | 'POST',
    path: string,
    body?: unknown,
  ): Promise<T> {
    const url = this.resolve(path);
    const res = await this.send(method, url, body);
    const text = await res.text();
    if (!res.ok) throw httpError(res, url, text);
    return parseJson<T>(text, url);
  }

  private async send(
    method: 'GET' | 'POST',
    url: string,
    body?: unknown,
  ): Promise<FetchLikeResponse> {
    const headers: Record<string, string> = {
      accept: 'application/json',
      ...this.headers,
    };
    let payload: string | undefined;
    if (body !== undefined) {
      headers['content-type'] = 'application/json';
      payload = JSON.stringify(body);
    }

    const controller =
      this.timeoutMs > 0 ? new AbortController() : undefined;
    const timer =
      controller !== undefined
        ? setTimeout(() => controller.abort(), this.timeoutMs)
        : undefined;
    try {
      const init: Parameters<FetchLike>[1] = { method, headers };
      if (payload !== undefined) init.body = payload;
      if (controller !== undefined) init.signal = controller.signal;
      return await this.fetchImpl(url, init);
    } finally {
      if (timer !== undefined) clearTimeout(timer);
    }
  }
}

function httpError(
  res: FetchLikeResponse,
  url: string,
  body: string,
): OabpHttpError {
  return new OabpHttpError({
    status: res.status,
    statusText: res.statusText,
    url,
    body,
  });
}

function parseJson<T>(text: string, url: string): T {
  if (text.trim() === '') return undefined as unknown as T;
  try {
    return JSON.parse(text) as T;
  } catch (cause) {
    throw new OabpHttpError({
      status: 200,
      statusText: 'Invalid JSON',
      url,
      body: text,
    });
  }
}

function stripTrailingSlash(s: string): string {
  return s.replace(/\/+$/, '');
}

function resolveGlobalFetch(): FetchLike {
  const g = globalThis as { fetch?: unknown };
  if (typeof g.fetch !== 'function') {
    throw new Error(
      'No global fetch available. Provide `fetch` in the client options ' +
        '(Node >= 18 has global fetch).',
    );
  }
  return g.fetch.bind(globalThis) as FetchLike;
}
