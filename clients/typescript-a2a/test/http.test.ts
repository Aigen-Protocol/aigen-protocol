import { describe, it, expect } from 'vitest';
import { HttpClient } from '../src/http.js';
import { OabpHttpError } from '../src/errors.js';
import { makeMockFetch } from './mockFetch.js';

const BASE = 'https://cryptogenesis.duckdns.org';

describe('HttpClient', () => {
  it('strips trailing slashes from the base URL and joins paths once', async () => {
    const { fetch, calls } = makeMockFetch({ 'GET /api/stats': { json: {} } });
    const http = new HttpClient({ baseUrl: `${BASE}///`, fetch });
    await http.getJson('/api/stats');
    expect(calls[0]?.url).toBe(`${BASE}/api/stats`);
  });

  it('passes absolute URLs through resolve()', () => {
    const http = new HttpClient({ baseUrl: BASE, fetch: makeMockFetch({}).fetch });
    expect(http.resolve('https://other.example/x')).toBe('https://other.example/x');
    expect(http.resolve('api/y')).toBe(`${BASE}/api/y`);
  });

  it('sends a JSON content-type only when there is a body', async () => {
    const { fetch, calls } = makeMockFetch({
      'GET /a': { json: {} },
      'POST /b': { json: {} },
    });
    const http = new HttpClient({ baseUrl: BASE, fetch });
    await http.getJson('/a');
    await http.postJson('/b', { x: 1 });
    expect(calls[0]?.headers['content-type']).toBeUndefined();
    expect(calls[1]?.headers['content-type']).toBe('application/json');
  });

  it('merges custom headers into every request', async () => {
    const { fetch, calls } = makeMockFetch({ 'GET /a': { json: {} } });
    const http = new HttpClient({
      baseUrl: BASE,
      fetch,
      headers: { authorization: 'Bearer token' },
    });
    await http.getJson('/a');
    expect(calls[0]?.headers['authorization']).toBe('Bearer token');
    expect(calls[0]?.headers['accept']).toBe('application/json');
  });

  it('returns undefined for an empty 2xx body', async () => {
    const { fetch } = makeMockFetch({ 'GET /a': { text: '' } });
    const http = new HttpClient({ baseUrl: BASE, fetch });
    expect(await http.getJson('/a')).toBeUndefined();
  });

  it('raises OabpHttpError on invalid JSON in a 2xx body', async () => {
    const { fetch } = makeMockFetch({ 'GET /a': { text: 'not json {' } });
    const http = new HttpClient({ baseUrl: BASE, fetch });
    await expect(http.getJson('/a')).rejects.toBeInstanceOf(OabpHttpError);
  });

  it('aborts when the timeout elapses', async () => {
    // fetch resolves only after the abort signal fires.
    const slowFetch = (async (
      _url: string,
      init?: { signal?: AbortSignal },
    ) => {
      return await new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () =>
          reject(Object.assign(new Error('aborted'), { name: 'AbortError' })),
        );
      });
    }) as unknown as Parameters<typeof HttpClient>[0]['fetch'];

    const http = new HttpClient({ baseUrl: BASE, fetch: slowFetch, timeoutMs: 20 });
    await expect(http.getJson('/slow')).rejects.toMatchObject({
      name: 'AbortError',
    });
  });

  it('throws a clear error when no global fetch and none injected', () => {
    const original = (globalThis as { fetch?: unknown }).fetch;
    try {
      // @ts-expect-error simulate an environment without fetch
      delete (globalThis as { fetch?: unknown }).fetch;
      expect(() => new HttpClient({ baseUrl: BASE })).toThrow(/global fetch/);
    } finally {
      (globalThis as { fetch?: unknown }).fetch = original;
    }
  });
});
