import type { FetchLike, FetchLikeResponse } from '../src/http.js';

export interface RecordedRequest {
  url: string;
  method: string;
  headers: Record<string, string>;
  body: unknown;
}

export interface RouteResponse {
  status?: number;
  statusText?: string;
  json?: unknown;
  text?: string;
}

/** `"METHOD path"` (path may be a substring) -> response or handler. */
export type Routes = Record<
  string,
  RouteResponse | ((req: RecordedRequest) => RouteResponse)
>;

export interface MockFetch {
  fetch: FetchLike;
  calls: RecordedRequest[];
}

/**
 * A tiny deterministic `fetch` stub. Routes are matched by
 * `"<METHOD> <substring-of-url>"`; the first matching key wins.
 */
export function makeMockFetch(routes: Routes): MockFetch {
  const calls: RecordedRequest[] = [];

  const fetch: FetchLike = async (url, init) => {
    const method = (init?.method ?? 'GET').toUpperCase();
    const headers = init?.headers ?? {};
    const body = init?.body !== undefined ? JSON.parse(init.body) : undefined;
    const recorded: RecordedRequest = { url, method, headers, body };
    calls.push(recorded);

    if (init?.signal?.aborted) {
      throw Object.assign(new Error('aborted'), { name: 'AbortError' });
    }

    const match = findRoute(routes, method, url);
    if (!match) {
      return makeResponse({ status: 404, text: `no route for ${method} ${url}` });
    }
    const resp = typeof match === 'function' ? match(recorded) : match;
    return makeResponse(resp);
  };

  return { fetch, calls };
}

function findRoute(
  routes: Routes,
  method: string,
  url: string,
): RouteResponse | ((req: RecordedRequest) => RouteResponse) | undefined {
  for (const key of Object.keys(routes)) {
    const [m, ...rest] = key.split(' ');
    const pathPart = rest.join(' ');
    if (m?.toUpperCase() === method && url.includes(pathPart)) {
      return routes[key];
    }
  }
  return undefined;
}

function makeResponse(resp: RouteResponse): FetchLikeResponse {
  const status = resp.status ?? 200;
  const bodyText =
    resp.text !== undefined
      ? resp.text
      : resp.json !== undefined
        ? JSON.stringify(resp.json)
        : '';
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: resp.statusText ?? (status === 200 ? 'OK' : 'Error'),
    text: async () => bodyText,
  };
}
