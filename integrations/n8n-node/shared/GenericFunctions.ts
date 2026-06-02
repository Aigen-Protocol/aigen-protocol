/**
 * Shared REST helpers for the OABP / AIGEN n8n nodes.
 *
 * Every network call funnels through {@link oabpApiRequest}, which builds an
 * {@link IHttpRequestOptions} and dispatches it via n8n's native
 * `this.helpers.httpRequest` (no third-party HTTP client). Both the regular
 * `Oabp` node (`execute`) and the `OabpTrigger` node (`poll`) reuse these
 * functions, so credential resolution, base-URL handling, bearer auth, and
 * error mapping are defined once.
 *
 * Endpoints (per the OABP protocol spec):
 *   GET  /api/missions            -> Mission[]
 *   POST /api/missions            -> Mission            (create)
 *   GET  /api/missions/{id}       -> Mission            (detail + resolution)
 *   POST /missions/{id}/submit    -> SubmitResult
 *   GET  /api/stats               -> Stats
 */

import type {
  IDataObject,
  IExecuteFunctions,
  IHttpRequestMethods,
  IHttpRequestOptions,
  IPollFunctions,
} from 'n8n-workflow';
import { NodeApiError } from 'n8n-workflow';

import type {
  CreateMissionRequest,
  Mission,
  OabpCredential,
  Reputation,
  Stats,
  SubmitRequest,
  SubmitResult,
} from './types';

/** Public OABP deployment used when the credential leaves `baseUrl` blank. */
export const DEFAULT_BASE_URL = 'https://cryptogenesis.duckdns.org';

/** Flat protocol fee applied to every paid reward. */
export const PROTOCOL_FEE_RATE = 0.005;

/** Net reward a winner receives after the 0.5% protocol fee. */
export function netReward(gross: number): number {
  return Math.round(gross * (1 - PROTOCOL_FEE_RATE) * 1e6) / 1e6;
}

/** Context type accepted by the request helper (execute or poll). */
type OabpContext = IExecuteFunctions | IPollFunctions;

/** Strip trailing slashes so we can safely concatenate paths. */
function trimBaseUrl(url: string): string {
  return url.replace(/\/+$/, '');
}

/**
 * Resolve the `oabpApi` credential into a base URL + auth headers + default
 * agent id. Returns sensible defaults when optional fields are blank.
 */
export async function getOabpConfig(
  ctx: OabpContext,
): Promise<{ baseUrl: string; headers: Record<string, string>; agentId: string }> {
  const creds = (await ctx.getCredentials('oabpApi')) as OabpCredential;
  const baseUrl = trimBaseUrl(
    typeof creds.baseUrl === 'string' && creds.baseUrl.trim() !== ''
      ? creds.baseUrl.trim()
      : DEFAULT_BASE_URL,
  );
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (typeof creds.bearerToken === 'string' && creds.bearerToken.trim() !== '') {
    headers.Authorization = `Bearer ${creds.bearerToken.trim()}`;
  }
  const agentId =
    typeof creds.agentId === 'string' && creds.agentId.trim() !== '' ? creds.agentId.trim() : '';
  return { baseUrl, headers, agentId };
}

/**
 * Perform a single authenticated request against the OABP REST API using n8n's
 * built-in HTTP helper. Throws a {@link NodeApiError} (so failures render
 * cleanly in the n8n UI) on transport errors.
 *
 * @param ctx     execute/poll context (provides `helpers.httpRequest`).
 * @param method  HTTP verb.
 * @param path    API path beginning with `/` (e.g. `/api/missions`).
 * @param body    JSON body for POST requests.
 * @param qs      query-string parameters.
 */
export async function oabpApiRequest<T = IDataObject>(
  ctx: OabpContext,
  method: IHttpRequestMethods,
  path: string,
  body?: IDataObject,
  qs?: IDataObject,
): Promise<T> {
  const { baseUrl, headers } = await getOabpConfig(ctx);

  const options: IHttpRequestOptions = {
    method,
    url: `${baseUrl}${path}`,
    headers,
    json: true,
  };
  if (body !== undefined) options.body = body;
  if (qs !== undefined && Object.keys(qs).length > 0) options.qs = qs;

  try {
    return (await ctx.helpers.httpRequest(options)) as T;
  } catch (error) {
    throw new NodeApiError(ctx.getNode(), error as IDataObject, {
      message: `OABP request failed: ${method} ${path}`,
    });
  }
}

// -----------------------------------------------------------------------------
// Response normalizers — defensive against shape drift across deployments.
// -----------------------------------------------------------------------------

function numberOr(value: unknown, fallback: number): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return fallback;
}

/** Coerce one raw API object into a well-formed {@link Mission}. */
export function normalizeMission(raw: unknown): Mission {
  const o = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const rewardObj = (o.reward ?? {}) as Record<string, unknown>;
  const submissionsRaw = Array.isArray(o.submissions) ? o.submissions : [];

  return {
    ...o,
    id: String(o.id ?? ''),
    title: String(o.title ?? ''),
    description: String(o.description ?? ''),
    reward: {
      amount: numberOr(rewardObj.amount, 0),
      currency: rewardObj.currency === 'USDC' ? 'USDC' : 'AIGEN',
    },
    verification_type:
      (o.verification_type as Mission['verification_type']) ?? 'first_valid_match',
    verification_params:
      o.verification_params && typeof o.verification_params === 'object'
        ? (o.verification_params as Mission['verification_params'])
        : {},
    deadline: numberOr(o.deadline, 0),
    status: (o.status as Mission['status']) ?? 'open',
    submissions: submissionsRaw
      .filter((s): s is Record<string, unknown> => s !== null && typeof s === 'object')
      .map((s) => ({
        ...s,
        submitter_agent_id: String(s.submitter_agent_id ?? ''),
        proof: String(s.proof ?? ''),
      })),
  } as Mission;
}

/** Coerce a raw list payload (array, or `{missions:[…]}`) into missions. */
export function normalizeMissionList(raw: unknown): Mission[] {
  const arr = Array.isArray(raw)
    ? raw
    : raw && typeof raw === 'object' && Array.isArray((raw as { missions?: unknown }).missions)
      ? (raw as { missions: unknown[] }).missions
      : [];
  return arr
    .filter((m): m is Record<string, unknown> => m !== null && typeof m === 'object')
    .map(normalizeMission);
}

// -----------------------------------------------------------------------------
// Typed endpoint wrappers
// -----------------------------------------------------------------------------

/** `GET /api/missions` — list missions (optionally server-filtered by status). */
export async function listMissions(
  ctx: OabpContext,
  status?: string,
): Promise<Mission[]> {
  const qs: IDataObject = {};
  if (status) qs.status = status;
  const raw = await oabpApiRequest<unknown>(ctx, 'GET', '/api/missions', undefined, qs);
  return normalizeMissionList(raw);
}

/** `GET /api/missions/{id}` — mission detail incl. submissions + resolution. */
export async function getMission(ctx: OabpContext, id: string): Promise<Mission> {
  const raw = await oabpApiRequest<unknown>(
    ctx,
    'GET',
    `/api/missions/${encodeURIComponent(id)}`,
  );
  return normalizeMission(raw);
}

/** `POST /api/missions` — create a mission. */
export async function createMission(
  ctx: OabpContext,
  req: CreateMissionRequest,
): Promise<Mission> {
  const raw = await oabpApiRequest<unknown>(
    ctx,
    'POST',
    '/api/missions',
    req as unknown as IDataObject,
  );
  return normalizeMission(raw);
}

/** `POST /missions/{id}/submit` — submit a deliverable. */
export async function submitMission(
  ctx: OabpContext,
  missionId: string,
  req: SubmitRequest,
): Promise<SubmitResult> {
  return oabpApiRequest<SubmitResult>(
    ctx,
    'POST',
    `/missions/${encodeURIComponent(missionId)}/submit`,
    req as unknown as IDataObject,
  );
}

/** `GET /api/stats` — aggregate protocol stats. */
export async function getStats(ctx: OabpContext): Promise<Stats> {
  const raw = await oabpApiRequest<Partial<Stats>>(ctx, 'GET', '/api/stats');
  return {
    resolved: numberOr(raw.resolved, 0),
    open: numberOr(raw.open, 0),
    lifetime_reward_aigen_paid: numberOr(raw.lifetime_reward_aigen_paid, 0),
    ...raw,
  };
}

/**
 * Derive a per-agent reputation snapshot from public mission data.
 *
 * The deployment has no dedicated reputation endpoint, so we scan open +
 * resolved missions and tally created/won/submitted plus net AIGEN/USDC earned
 * (net of the 0.5% fee where a resolution doesn't already report the paid
 * amount). Pure given its mission input — deterministic and testable.
 */
export function computeReputation(agentId: string, missions: Mission[]): Reputation {
  const rep: Reputation = {
    agent_id: agentId,
    aigen_earned: 0,
    usdc_earned: 0,
    missions_created: 0,
    missions_won: 0,
    submissions_made: 0,
  };

  for (const m of missions) {
    if (m.creator_agent_id === agentId) rep.missions_created += 1;
    for (const s of m.submissions ?? []) {
      if (s.submitter_agent_id === agentId) rep.submissions_made += 1;
    }
    const res = m.resolution;
    if (res && res.winner_agent_id === agentId) {
      rep.missions_won += 1;
      const gross = res.reward_paid ?? m.reward?.amount ?? 0;
      // If the server already reports reward_paid it is net; otherwise apply fee.
      const paid = res.reward_paid !== undefined ? gross : netReward(gross);
      const currency = res.reward_currency ?? m.reward?.currency;
      if (currency === 'USDC') rep.usdc_earned += paid;
      else rep.aigen_earned += paid;
    }
  }

  rep.aigen_earned = Math.round(rep.aigen_earned * 1e6) / 1e6;
  rep.usdc_earned = Math.round(rep.usdc_earned * 1e6) / 1e6;
  return rep;
}

/** Fetch open+resolved missions and compute reputation for `agentId`. */
export async function getReputation(
  ctx: OabpContext,
  agentId: string,
): Promise<Reputation> {
  const [open, resolved] = await Promise.all([
    listMissions(ctx, 'open'),
    listMissions(ctx, 'resolved'),
  ]);
  const seen = new Set<string>();
  const merged: Mission[] = [];
  for (const m of [...open, ...resolved]) {
    if (m.id && seen.has(m.id)) continue;
    if (m.id) seen.add(m.id);
    merged.push(m);
  }
  return computeReputation(agentId, merged);
}
