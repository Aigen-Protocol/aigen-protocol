/**
 * Isomorphic HTTP layer. Resolves a `fetch` implementation that works in both
 * modern Node (>=18, global fetch) and browsers, lets callers inject their own,
 * adds JSON encoding, timeouts, abort propagation, and structured errors.
 */

import {
  OabpApiError,
  OabpNetworkError,
  OabpTimeoutError,
} from "./errors.js";

/** Minimal structural type for a fetch implementation. */
export type FetchLike = (
  input: string,
  init?: RequestInit,
) => Promise<Response>;

/** Resolve a usable fetch: caller override → global fetch → throw. */
export function resolveFetch(custom?: FetchLike): FetchLike {
  if (custom) return custom;
  const g = globalThis as { fetch?: FetchLike };
  if (typeof g.fetch === "function") {
    // Bind so implementations that rely on `this === globalThis` keep working.
    return g.fetch.bind(globalThis) as FetchLike;
  }
  throw new OabpNetworkError(
    "No fetch implementation found. Use Node >=18, a browser, or pass `fetch` " +
      "to the client (e.g. `new OabpClient({ fetch: require('node-fetch') })`).",
    undefined,
  );
}

/** Headers map the client always sends, merged with per-request headers. */
export type HeaderMap = Record<string, string>;

export interface HttpClientOptions {
  baseUrl: string;
  fetch?: FetchLike;
  headers?: HeaderMap;
  /** Per-request timeout in ms. 0 disables the SDK-managed timeout. */
  timeoutMs?: number;
  /** Optional bearer token sent as `Authorization: Bearer <token>`. */
  apiKey?: string;
  /** Optional default user-agent (ignored by browsers). */
  userAgent?: string;
}

export interface RequestOptions {
  /** Extra query parameters; undefined/null values are skipped. */
  query?: Record<string, string | number | boolean | undefined | null>;
  /** JSON body to send; serialized with `JSON.stringify`. */
  body?: unknown;
  /** Additional headers for this request only. */
  headers?: HeaderMap;
  /** Caller-provided abort signal, combined with the timeout signal. */
  signal?: AbortSignal;
}

const DEFAULT_TIMEOUT_MS = 30_000;

/** Strip a single trailing slash so path joins stay predictable. */
function trimTrailingSlash(s: string): string {
  return s.endsWith("/") ? s.slice(0, -1) : s;
}

/** Join base + path tolerating leading/trailing slashes on either side. */
export function joinUrl(baseUrl: string, path: string): string {
  const base = trimTrailingSlash(baseUrl);
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${base}${p}`;
}

/** Append query params to a URL, skipping nullish values. */
export function withQuery(
  url: string,
  query?: RequestOptions["query"],
): string {
  if (!query) return url;
  const pairs: string[] = [];
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null) continue;
    pairs.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  }
  if (pairs.length === 0) return url;
  return url.includes("?") ? `${url}&${pairs.join("&")}` : `${url}?${pairs.join("&")}`;
}

/**
 * Combine an optional caller signal with a timeout signal. Returns the combined
 * signal plus a cleanup function and a flag-getter that reports whether the
 * timeout (rather than the caller) fired.
 */
function buildSignal(
  timeoutMs: number,
  external?: AbortSignal,
): { signal: AbortSignal; cleanup: () => void; timedOut: () => boolean } {
  // No SDK timeout and no external signal: nothing to manage.
  if (timeoutMs <= 0 && !external) {
    return { signal: new AbortController().signal, cleanup: () => {}, timedOut: () => false };
  }

  const controller = new AbortController();
  let timedOut = false;
  let timer: ReturnType<typeof setTimeout> | undefined;

  if (timeoutMs > 0) {
    timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    // Don't keep the Node event loop alive solely for this timer.
    (timer as { unref?: () => void }).unref?.();
  }

  const onExternalAbort = () => controller.abort();
  if (external) {
    if (external.aborted) controller.abort();
    else external.addEventListener("abort", onExternalAbort, { once: true });
  }

  return {
    signal: controller.signal,
    cleanup: () => {
      if (timer) clearTimeout(timer);
      external?.removeEventListener("abort", onExternalAbort);
    },
    timedOut: () => timedOut,
  };
}

/** Best-effort JSON parse: returns the parsed value or the raw string. */
function safeJson(text: string): unknown {
  if (text.length === 0) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** Thin, typed HTTP client around the resolved fetch. */
export class HttpClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: FetchLike;
  private readonly baseHeaders: HeaderMap;
  private readonly timeoutMs: number;

  constructor(opts: HttpClientOptions) {
    this.baseUrl = trimTrailingSlash(opts.baseUrl);
    this.fetchImpl = resolveFetch(opts.fetch);
    this.timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;

    const headers: HeaderMap = {
      Accept: "application/json",
      ...(opts.headers ?? {}),
    };
    if (opts.apiKey) headers["Authorization"] = `Bearer ${opts.apiKey}`;
    // User-Agent is forbidden as a header name in browsers; only set it where
    // there's no `window` (i.e. Node-like environments).
    if (opts.userAgent && typeof (globalThis as { window?: unknown }).window === "undefined") {
      headers["User-Agent"] = opts.userAgent;
    }
    this.baseHeaders = headers;
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  async request<T>(
    method: string,
    path: string,
    options: RequestOptions = {},
  ): Promise<T> {
    const url = withQuery(joinUrl(this.baseUrl, path), options.query);

    const headers: HeaderMap = { ...this.baseHeaders, ...(options.headers ?? {}) };
    const init: RequestInit = { method, headers };

    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }

    const { signal, cleanup, timedOut } = buildSignal(this.timeoutMs, options.signal);
    init.signal = signal;

    let response: Response;
    try {
      response = await this.fetchImpl(url, init);
    } catch (err) {
      cleanup();
      if (timedOut()) throw new OabpTimeoutError(this.timeoutMs);
      if (isAbortError(err)) {
        // Caller-provided signal aborted before the timeout.
        throw new OabpNetworkError(`Request to ${url} was aborted`, err);
      }
      throw new OabpNetworkError(
        `Network request to ${url} failed: ${describeError(err)}`,
        err,
      );
    } finally {
      cleanup();
    }

    const text = await response.text();
    const data = safeJson(text);

    if (!response.ok) {
      throw new OabpApiError({
        status: response.status,
        statusText: response.statusText,
        url,
        method,
        body: text,
        data,
      });
    }

    return data as T;
  }

  get<T>(path: string, options?: RequestOptions): Promise<T> {
    return this.request<T>("GET", path, options);
  }

  post<T>(path: string, body: unknown, options?: RequestOptions): Promise<T> {
    return this.request<T>("POST", path, { ...(options ?? {}), body });
  }
}

/** Detect an AbortError across runtimes (DOMException vs plain Error). */
function isAbortError(err: unknown): boolean {
  return (
    typeof err === "object" &&
    err !== null &&
    "name" in err &&
    (err as { name?: unknown }).name === "AbortError"
  );
}

function describeError(err: unknown): string {
  if (err instanceof Error) return err.message;
  return String(err);
}
