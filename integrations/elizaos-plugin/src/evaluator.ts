/**
 * `claimedMissionsEvaluator` — an ElizaOS Evaluator (stub) that runs after interactions and tracks
 * which OABP missions this agent has submitted to / claimed.
 *
 * In ElizaOS, evaluators are the post-interaction reflection step: the runtime calls `validate`,
 * and if it passes, `handler` extracts/records facts. This one watches for SUBMIT_OABP_MISSION
 * outcomes (in the action's response content or echoed in the message) and maintains a small,
 * in-memory ledger of claimed mission ids + verdicts, keyed by agent. It is intentionally a
 * dependency-free stub: it does NOT call the network and does NOT persist beyond the process —
 * swap `CLAIM_LEDGER` for `runtime`'s memory/DB API to make it durable.
 *
 * Exposed so a host app (or the tests) can read what was tracked: see `getClaimLedger`.
 */

import type {
  Content,
  EvaluationExample,
  Evaluator,
  IAgentRuntime,
  Memory,
  State,
} from "./eliza-types.js";

/** One recorded claim attempt. */
export interface ClaimRecord {
  agentId: string;
  missionId: string;
  /** true=accepted, false=rejected, null=pending/unknown. */
  accepted: boolean | null;
  at: number;
}

/**
 * Process-local ledger keyed by `agentId`. A real deployment would persist this via the runtime's
 * memory/knowledge store; kept in-module so the stub is self-contained and assertable in tests.
 */
const CLAIM_LEDGER = new Map<string, ClaimRecord[]>();

/** Read the recorded claims for an agent (newest last). Returns a copy. */
export function getClaimLedger(agentId: string): ClaimRecord[] {
  return (CLAIM_LEDGER.get(agentId) ?? []).map((r) => ({ ...r }));
}

/** Clear the ledger (test helper / session reset). If `agentId` is omitted, clears everything. */
export function resetClaimLedger(agentId?: string): void {
  if (agentId) CLAIM_LEDGER.delete(agentId);
  else CLAIM_LEDGER.clear();
}

/** Append a record, deduping on (agentId, missionId) by updating the latest verdict. */
function record(rec: ClaimRecord): void {
  const list = CLAIM_LEDGER.get(rec.agentId) ?? [];
  const existing = list.find((r) => r.missionId === rec.missionId);
  if (existing) {
    existing.accepted = rec.accepted;
    existing.at = rec.at;
  } else {
    list.push(rec);
  }
  CLAIM_LEDGER.set(rec.agentId, list);
}

/**
 * Pull a SUBMIT outcome from a content object. The SUBMIT action attaches `{ missionId, accepted }`
 * to its response content and writes a text line `"... OABP mission <id>: ACCEPTED/..."`. We read
 * the structured fields first, then fall back to parsing the text.
 */
function extractClaim(content: Content | undefined): { missionId: string; accepted: boolean | null } | null {
  if (!content) return null;

  // Only consider SUBMIT-related content.
  const isSubmit =
    (Array.isArray(content.actions) && content.actions.includes("SUBMIT_OABP_MISSION")) ||
    /OABP mission\s+\S+/i.test(String(content.text ?? ""));
  if (!isSubmit) return null;

  // Structured path (preferred): set by submitOabpMissionAction.
  if (typeof content.missionId === "string") {
    const acc = typeof content.accepted === "boolean" ? content.accepted : null;
    return { missionId: content.missionId, accepted: acc };
  }

  // Text fallback: "... OABP mission <id>: ACCEPTED ✅ ..." / "... not accepted ...".
  const text = String(content.text ?? "");
  const m = text.match(/OABP mission\s+([A-Za-z0-9._-]+)/i);
  if (!m) return null;
  const accepted = /accepted\s*✅|: ACCEPTED/i.test(text)
    ? true
    : /not accepted|❌/i.test(text)
      ? false
      : null;
  return { missionId: m[1], accepted };
}

export const claimedMissionsEvaluator: Evaluator = {
  name: "TRACK_OABP_CLAIMS",
  similes: ["TRACK_CLAIMS", "RECORD_MISSION_CLAIMS", "OABP_CLAIM_LEDGER"],
  description:
    "After an interaction, record any OABP mission this agent submitted to/claimed (mission id + " +
    "accepted/rejected/pending), maintaining a per-agent claim ledger. Stub: in-memory, no network.",
  // Always run so we catch claims even when the agent's reply wasn't an explicit action call.
  alwaysRun: true,

  validate: async (_runtime: IAgentRuntime, message: Memory, _state?: State): Promise<boolean> => {
    // Run when the message OR conversation mentions an OABP submission/claim.
    const t = String(message?.content?.text ?? "");
    return /OABP mission\s+\S+/i.test(t) || /SUBMIT_OABP_MISSION/.test(JSON.stringify(message?.content ?? {}));
  },

  handler: async (
    runtime: IAgentRuntime,
    message: Memory,
    _state?: State,
    _options?: Record<string, unknown>,
    _callback?: unknown,
    responses?: Memory[]
  ): Promise<ClaimRecord[]> => {
    const agentId = runtime.getSetting("OABP_AGENT_ID") || runtime.agentId;

    // Inspect the agent's response memories first (where the SUBMIT action result lives), then the
    // triggering message itself.
    const candidates: (Content | undefined)[] = [
      ...((responses ?? []).map((r) => r.content)),
      message?.content,
    ];

    const recorded: ClaimRecord[] = [];
    for (const c of candidates) {
      const claim = extractClaim(c);
      if (claim) {
        const rec: ClaimRecord = {
          agentId,
          missionId: claim.missionId,
          accepted: claim.accepted,
          at: Date.now(),
        };
        record(rec);
        recorded.push(rec);
      }
    }
    return recorded;
  },

  examples: [
    {
      prompt: "The agent just submitted a deliverable to an OABP mission.",
      messages: [
        { name: "{{user1}}", content: { text: "submit mission demo-fvm proof: BUILD-0000" } },
        {
          name: "{{agent}}",
          content: {
            text: "Submitted deliverable to OABP mission demo-fvm: ACCEPTED ✅ — regex matched",
            actions: ["SUBMIT_OABP_MISSION"],
            missionId: "demo-fvm",
            accepted: true,
          },
        },
      ],
      outcome: "Record { missionId: 'demo-fvm', accepted: true } in this agent's claim ledger.",
    },
  ],
};
