/**
 * A tiny, dependency-free mock `fetch` for exercising the SDK without a network.
 *
 * It records every call, lets each test register route handlers keyed by
 * `METHOD path` (path is matched without query string), and synthesizes a
 * standards-compliant `Response`-like object good enough for the SDK's HTTP
 * layer (it only uses `.ok`, `.status`, `.statusText`, and `.text()`).
 *
 * Shared by both the vitest suite (`client.test.ts`) and the pure-Node runner
 * (`run-node.mjs` consumes the compiled JS form), so the same assertions cover
 * both `npm test` (vitest) and `npm run test:node` (no dev deps required).
 */

import type { FetchLike } from "../src/http.js";

export interface RecordedCall {
  method: string;
  url: string;
  path: string;
  query: Record<string, string>;
  body: unknown;
  headers: Record<string, string>;
}

export interface MockResponseSpec {
  status?: number;
  statusText?: string;
  json?: unknown;
  text?: string;
  headers?: Record<string, string>;
}

export type RouteHandler = (call: RecordedCall) => MockResponseSpec;

/** Minimal Response shape the SDK relies on. */
interface MinimalResponse {
  ok: boolean;
  status: number;
  statusText: string;
  text(): Promise<string>;
}

function makeResponse(spec: MockResponseSpec): MinimalResponse {
  const status = spec.status ?? 200;
  const body =
    spec.text !== undefined
      ? spec.text
      : spec.json !== undefined
        ? JSON.stringify(spec.json)
        : "";
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: spec.statusText ?? statusTextFor(status),
    text: () => Promise.resolve(body),
  };
}

function statusTextFor(status: number): string {
  const map: Record<number, string> = {
    200: "OK",
    201: "Created",
    400: "Bad Request",
    401: "Unauthorized",
    404: "Not Found",
    422: "Unprocessable Entity",
    500: "Internal Server Error",
  };
  return map[status] ?? "";
}

function parseUrl(url: string): { path: string; query: Record<string, string> } {
  const qIndex = url.indexOf("?");
  if (qIndex === -1) return { path: stripOrigin(url), query: {} };
  const path = stripOrigin(url.slice(0, qIndex));
  const query: Record<string, string> = {};
  for (const pair of url.slice(qIndex + 1).split("&")) {
    if (!pair) continue;
    const eq = pair.indexOf("=");
    const k = decodeURIComponent(eq === -1 ? pair : pair.slice(0, eq));
    const v = eq === -1 ? "" : decodeURIComponent(pair.slice(eq + 1));
    query[k] = v;
  }
  return { path, query };
}

function stripOrigin(url: string): string {
  const m = /^https?:\/\/[^/]+(\/.*)?$/.exec(url);
  if (m) return m[1] ?? "/";
  return url;
}

export class MockServer {
  readonly calls: RecordedCall[] = [];
  private routes = new Map<string, RouteHandler>();

  /** Register a handler for `METHOD /path` (query is ignored when matching). */
  on(method: string, path: string, handler: RouteHandler): this {
    this.routes.set(`${method.toUpperCase()} ${path}`, handler);
    return this;
  }

  /** Convenience: respond with static JSON for a route. */
  json(method: string, path: string, json: unknown, status = 200): this {
    return this.on(method, path, () => ({ json, status }));
  }

  /** The fetch implementation to hand to the SDK. */
  get fetch(): FetchLike {
    return (input: string, init?: RequestInit): Promise<Response> => {
      const method = (init?.method ?? "GET").toUpperCase();
      const { path, query } = parseUrl(input);

      let body: unknown = undefined;
      if (typeof init?.body === "string" && init.body.length > 0) {
        try {
          body = JSON.parse(init.body);
        } catch {
          body = init.body;
        }
      }

      const headers: Record<string, string> = {};
      const h = init?.headers;
      if (h && typeof h === "object" && !Array.isArray(h)) {
        for (const [k, v] of Object.entries(h as Record<string, string>)) {
          headers[k] = String(v);
        }
      }

      const call: RecordedCall = { method, url: input, path, query, body, headers };
      this.calls.push(call);

      const handler = this.routes.get(`${method} ${path}`);
      if (!handler) {
        return Promise.resolve(
          makeResponse({ status: 404, json: { error: `no mock route for ${method} ${path}` } }) as unknown as Response,
        );
      }
      return Promise.resolve(makeResponse(handler(call)) as unknown as Response);
    };
  }

  /** Number of times a given route was hit. */
  countCalls(method: string, path: string): number {
    return this.calls.filter((c) => c.method === method.toUpperCase() && c.path === path).length;
  }

  /** Last recorded call (for assertions on body/headers). */
  lastCall(): RecordedCall | undefined {
    return this.calls[this.calls.length - 1];
  }

  reset(): void {
    this.calls.length = 0;
    this.routes.clear();
  }
}
