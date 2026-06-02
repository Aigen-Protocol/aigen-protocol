/**
 * Runtime wiring: turn an ElizaOS `IAgentRuntime` into a configured OABP client + identity,
 * and small formatting/economics helpers shared by the actions and the provider.
 *
 * Settings (resolved via `runtime.getSetting`, which ElizaOS sources from the character's
 * `settings`/`secrets` and then the environment):
 *   - `OABP_BASE_URL`  — protocol base URL. Default: https://cryptogenesis.duckdns.org
 *   - `OABP_AGENT_ID`  — the agent id used as submitter/creator. Falls back to `runtime.agentId`.
 *
 * For tests/offline runs, a client can be injected directly (so no network and no real settings
 * are required); see `getClient`.
 */

import { DEFAULT_BASE_URL, OabpSdk } from "./sdk.js";
import type { Mission, OabpClient } from "./sdk.js";
import type { IAgentRuntime } from "./eliza-types.js";

/** Setting key for the OABP base URL. */
export const OABP_BASE_URL = "OABP_BASE_URL";
/** Setting key for the agent id used on submit/create. */
export const OABP_AGENT_ID = "OABP_AGENT_ID";

/** OABP protocol fee taken on rewards (0.5%). Mirrored here so handlers can show net rewards. */
export const FEE_RATE = 0.005;

/** Net reward after the protocol's 0.5% fee. */
export function netReward(amount: number): number {
  return Math.round(amount * (1 - FEE_RATE) * 1e6) / 1e6;
}

/**
 * Allow tests / advanced embedders to inject a client (real or {@link MockOabpClient}) instead of
 * having one constructed from settings. Set `runtime.__oabpClient` (typed loosely) and it wins.
 */
interface RuntimeWithClient extends IAgentRuntime {
  __oabpClient?: OabpClient;
}

/**
 * Resolve the {@link OabpClient} for this runtime.
 * Precedence: injected `runtime.__oabpClient` > a fresh {@link OabpSdk} built from `OABP_BASE_URL`.
 */
export function getClient(runtime: IAgentRuntime): OabpClient {
  const injected = (runtime as RuntimeWithClient).__oabpClient;
  if (injected) return injected;
  const baseUrl = runtime.getSetting(OABP_BASE_URL) || DEFAULT_BASE_URL;
  const apiKey = runtime.getSetting("OABP_API_KEY") || undefined;
  return new OabpSdk({ baseUrl, apiKey });
}

/** The agent id to act as: `OABP_AGENT_ID` setting, else the ElizaOS `runtime.agentId`. */
export function getAgentId(runtime: IAgentRuntime): string {
  return runtime.getSetting(OABP_AGENT_ID) || runtime.agentId;
}

/** True for missions still claimable: status `open` (or unset) and deadline in the future. */
export function isOpen(m: Mission, nowSec = Math.floor(Date.now() / 1000)): boolean {
  const open = (m.status ?? "open").toLowerCase() === "open";
  return open && (typeof m.deadline !== "number" || m.deadline > nowSec);
}

/** `"5 USDC"` / `"25 AIGEN"`. */
export function formatReward(m: Mission): string {
  return `${m.reward.amount} ${m.reward.currency}`;
}

/** Whole hours until `deadline` (>= 0). */
export function hoursLeft(m: Mission, nowSec = Math.floor(Date.now() / 1000)): number {
  if (typeof m.deadline !== "number") return 0;
  return Math.max(0, Math.floor((m.deadline - nowSec) / 3600));
}

/** One-line mission summary used in provider context and action replies. */
export function summarizeMission(m: Mission): string {
  const verif =
    m.verification_type === "first_valid_match" && m.verification_params?.regex
      ? `first_valid_match(/${m.verification_params.regex}/)`
      : m.verification_type === "oracle" && m.verification_params?.oracle_description
        ? `oracle(${m.verification_params.oracle_description})`
        : m.verification_type;
  return `- [${m.id}] ${m.title} — ${formatReward(m)} (net ${netReward(m.reward.amount)} after 0.5% fee), verify=${verif}, ${hoursLeft(m)}h left, ${m.submissions?.length ?? 0} submission(s)`;
}

/**
 * Pull a mission id out of free-form user text. Recognizes `mission <id>`, `#<id>`, `id <id>`,
 * or a bare token that matches a known mission id (checked by the caller). Returns `undefined`
 * when nothing id-like is present.
 */
export function extractMissionId(text: string, knownIds: string[] = []): string | undefined {
  if (!text) return undefined;
  const m =
    text.match(/\bmission[\s:#]+([A-Za-z0-9._-]{2,})/i) ||
    text.match(/\bid[\s:#]+([A-Za-z0-9._-]{2,})/i) ||
    text.match(/#([A-Za-z0-9._-]{2,})/);
  if (m) return m[1];
  // Fall back: the first whitespace token that equals a known mission id.
  if (knownIds.length) {
    for (const tok of text.split(/\s+/)) {
      const clean = tok.replace(/[.,!?;:]+$/g, "");
      if (knownIds.includes(clean)) return clean;
    }
  }
  return undefined;
}

/**
 * Extract the deliverable/proof from user text for SUBMIT.
 *
 * Order of preference:
 *  1. An explicit `proof:` / `deliverable:` / `answer:` (or `=`) label — capture what follows it
 *     (the LAST such label wins, so a leading "submit …" command verb never swallows the value).
 *     This is the canonical form, e.g. `submit mission demo-fvm proof: BUILD-0000`.
 *  2. A bare URL (typical for repo/oracle deliverables).
 *
 * Returns `undefined` if nothing usable is found, so the handler can ask for a deliverable rather
 * than guessing.
 */
export function extractProof(text: string): string | undefined {
  if (!text) return undefined;

  // 1) Labelled value. Use a global scan and keep the last match so "submit ... proof: X" -> X.
  const labelRe = /(?:\bproof|\bdeliverable|\banswer(?:\s+is)?)\s*[:=]\s*([^\n]+)/gi;
  let m: RegExpExecArray | null;
  let last: string | undefined;
  while ((m = labelRe.exec(text)) !== null) last = m[1];
  if (last) {
    // Trim and strip a trailing "for mission ..." / "to mission ..." clause if present.
    return last.replace(/\s+(?:for|to)\s+mission\b.*$/i, "").trim();
  }

  // 2) Fallback: a bare URL.
  const url = text.match(/\bhttps?:\/\/\S+/i);
  if (url) return url[0];

  return undefined;
}
