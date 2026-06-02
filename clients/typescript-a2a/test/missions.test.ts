import { describe, it, expect } from 'vitest';
import { OabpClient } from '../src/client.js';
import { OabpError, OabpHttpError } from '../src/errors.js';
import { makeMockFetch } from './mockFetch.js';
import { SIGNED_AGENT_CARD, JWKS_DOC } from './vectors.js';
import type { Mission } from '../src/types.js';

const BASE = 'https://cryptogenesis.duckdns.org';

const sampleMission: Mission = {
  id: 'm_001',
  title: 'Safety-review token 0xabc',
  description: 'Run a GoPlus token-security review.',
  reward: { amount: 500, currency: 'AIGEN' },
  verification_type: 'oracle',
  verification_params: { oracle_description: 'GoPlus token-security pass' },
  deadline: 1_900_000_000,
  status: 'open',
  submissions: [],
};

describe('OabpClient — missions REST', () => {
  it('GET /api/missions returns an array', async () => {
    const { fetch, calls } = makeMockFetch({
      'GET /api/missions': { json: [sampleMission] },
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    const missions = await oabp.listMissions();
    expect(missions).toHaveLength(1);
    expect(missions[0]?.id).toBe('m_001');
    expect(calls[0]?.url).toBe(`${BASE}/api/missions`);
    expect(calls[0]?.method).toBe('GET');
  });

  it('GET /api/missions tolerates a {missions:[...]} envelope', async () => {
    const { fetch } = makeMockFetch({
      'GET /api/missions': { json: { missions: [sampleMission] } },
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    expect(await oabp.listMissions()).toHaveLength(1);
  });

  it('GET /api/missions/{id} fetches mission detail', async () => {
    const { fetch, calls } = makeMockFetch({
      'GET /api/missions/m_001': {
        json: { ...sampleMission, submissions: [{ submitter_agent_id: 'a', proof: 'p' }] },
      },
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    const m = await oabp.getMission('m_001');
    expect(m.submissions).toHaveLength(1);
    expect(calls[0]?.url).toBe(`${BASE}/api/missions/m_001`);
  });

  it('POST /api/missions sends the create body and returns the mission', async () => {
    const { fetch, calls } = makeMockFetch({
      'POST /api/missions': (req) => ({
        json: { ...sampleMission, id: 'm_new', title: (req.body as { title: string }).title },
      }),
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    const created = await oabp.createMission({
      creator_agent_id: 'agent:me',
      title: 'Build a Go CLI',
      description: 'Deliver a GitHub repo with a working Go CLI.',
      reward_amount: 1000,
      reward_currency: 'AIGEN',
      verification_type: 'oracle',
      verification_params: { oracle_description: 'GitHub repo deliverable' },
      deadline_hours: 72,
    });
    expect(created.id).toBe('m_new');
    expect(created.title).toBe('Build a Go CLI');
    const body = calls[0]?.body as Record<string, unknown>;
    expect(body['creator_agent_id']).toBe('agent:me');
    expect(body['deadline_hours']).toBe(72);
    expect(calls[0]?.headers['content-type']).toBe('application/json');
  });

  it('createMission validates required fields locally before any request', async () => {
    const { fetch, calls } = makeMockFetch({});
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    await expect(
      // @ts-expect-error intentionally missing fields
      oabp.createMission({ title: 'x' }),
    ).rejects.toBeInstanceOf(OabpError);
    expect(calls).toHaveLength(0);
  });

  it('createMission rejects non-positive reward / deadline', async () => {
    const { fetch } = makeMockFetch({});
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    const base = {
      creator_agent_id: 'a',
      title: 't',
      description: 'd',
      reward_currency: 'AIGEN' as const,
      verification_type: 'first_valid_match' as const,
      verification_params: { regex: '.*' },
    };
    await expect(
      oabp.createMission({ ...base, reward_amount: 0, deadline_hours: 24 }),
    ).rejects.toThrow(/reward_amount/);
    await expect(
      oabp.createMission({ ...base, reward_amount: 10, deadline_hours: 0 }),
    ).rejects.toThrow(/deadline_hours/);
  });

  it('POST /missions/{id}/submit sends the proof', async () => {
    const { fetch, calls } = makeMockFetch({
      'POST /missions/m_001/submit': {
        json: { submitter_agent_id: 'agent:me', proof: 'https://github.com/x/y', valid: true },
      },
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    const res = await oabp.submit('m_001', {
      submitter_agent_id: 'agent:me',
      proof: 'https://github.com/x/y',
    });
    expect((res as { valid: boolean }).valid).toBe(true);
    expect(calls[0]?.url).toBe(`${BASE}/missions/m_001/submit`);
    expect((calls[0]?.body as { proof: string }).proof).toBe(
      'https://github.com/x/y',
    );
  });

  it('submit rejects empty proof / missing submitter without a request', async () => {
    const { fetch, calls } = makeMockFetch({});
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    await expect(
      oabp.submit('m_001', { submitter_agent_id: 'a', proof: '' }),
    ).rejects.toBeInstanceOf(OabpError);
    await expect(
      // @ts-expect-error missing submitter
      oabp.submit('m_001', { proof: 'x' }),
    ).rejects.toBeInstanceOf(OabpError);
    expect(calls).toHaveLength(0);
  });

  it('GET /api/stats returns protocol counters', async () => {
    const { fetch } = makeMockFetch({
      'GET /api/stats': {
        json: { resolved: 42, open: 7, lifetime_reward_aigen_paid: 108000 },
      },
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    const stats = await oabp.getStats();
    expect(stats.resolved).toBe(42);
    expect(stats.lifetime_reward_aigen_paid).toBe(108000);
  });

  it('surfaces non-2xx responses as OabpHttpError with status + body', async () => {
    const { fetch } = makeMockFetch({
      'GET /api/missions/missing': {
        status: 404,
        statusText: 'Not Found',
        json: { error: 'no such mission' },
      },
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    await expect(oabp.getMission('missing')).rejects.toMatchObject({
      name: 'OabpHttpError',
      status: 404,
    });
    try {
      await oabp.getMission('missing');
    } catch (e) {
      expect(e).toBeInstanceOf(OabpHttpError);
      expect((e as OabpHttpError).body).toContain('no such mission');
    }
  });

  it('percent-encodes mission ids in the path', async () => {
    const { fetch, calls } = makeMockFetch({
      'GET /api/missions/a%2Fb': { json: sampleMission },
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    await oabp.getMission('a/b');
    expect(calls[0]?.url).toBe(`${BASE}/api/missions/a%2Fb`);
  });
});

describe('OabpClient — agent card over HTTP', () => {
  it('fetchVerifiedAgentCard fetches card + JWKS and verifies', async () => {
    const { fetch, calls } = makeMockFetch({
      'GET /.well-known/agent-card.json': { json: SIGNED_AGENT_CARD },
      'GET /.well-known/jwks.json': { json: JWKS_DOC },
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    const result = await oabp.fetchVerifiedAgentCard();
    expect(result.verified).toBe(true);
    expect(result.card.name).toBe('AIGEN Protocol Agent');
    // It fetched both the card and the JWKS.
    const urls = calls.map((c) => c.url);
    expect(urls).toContain(`${BASE}/.well-known/agent-card.json`);
    expect(urls).toContain(`${BASE}/.well-known/jwks.json`);
  });

  it('fetchVerifiedAgentCard accepts an explicit JWKS (no JWKS fetch)', async () => {
    const { fetch, calls } = makeMockFetch({
      'GET /.well-known/agent-card.json': { json: SIGNED_AGENT_CARD },
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    const result = await oabp.fetchVerifiedAgentCard({ jwks: JWKS_DOC });
    expect(result.verified).toBe(true);
    expect(calls.every((c) => !c.url.includes('jwks'))).toBe(true);
  });

  it('fetchAgentCard rejects a card without a url', async () => {
    const { fetch } = makeMockFetch({
      'GET /.well-known/agent-card.json': { json: { name: 'no url' } },
    });
    const oabp = new OabpClient({ baseUrl: BASE, fetch });
    await expect(oabp.fetchAgentCard()).rejects.toBeInstanceOf(OabpError);
  });
});
