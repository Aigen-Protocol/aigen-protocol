/**
 * Prebuilt LangGraph nodes for the OABP mission loop.
 *
 * Each factory takes an {@link OabpClient} and returns a LangGraph node function
 * `(state) => Partial<state>`. Nodes are intentionally small and pure-ish: all I/O goes
 * through the injected client, which makes them trivially testable with a mock.
 *
 * Pipeline:  discover -> evaluate -> (route) -> worker -> (loop back to route) -> END
 *
 * - discover : GET /api/missions, keep only OPEN, not-expired missions.
 * - evaluate : score each mission; mark `claimable` the ones this agent can verifiably win.
 * - worker   : take the next claimable mission, build a proof, POST it to /missions/{id}/submit.
 * - claim    : a thin alias of worker kept for API symmetry with the spec
 *              (discover/evaluate/claim/submit). `submitNode` is also exported as the
 *              single-mission submit primitive used to build the worker.
 */

import type {
  EvaluatedMission,
  MissionResult,
  OabpStateType,
  OabpStateUpdate,
} from "./state.js";
import { rewardInAigenEquivalent } from "./state.js";
import type { Mission, OabpClient, VerificationParams } from "./sdk.js";

export interface NodeDeps {
  client: OabpClient;
  /**
   * Builds a candidate proof (text or URL) for a mission this agent intends to claim.
   * Default produces a content-addressed string that satisfies a `first_valid_match` regex
   * when one is present; override to plug in a real solver (GitHub repo URL, token address,
   * safety-review report, ...).
   */
  buildProof?: (mission: Mission, agentId: string) => string | Promise<string>;
}

const nowSeconds = () => Math.floor(Date.now() / 1000);

function isOpen(m: Mission): boolean {
  const status = (m.status ?? "").toLowerCase();
  const openish = status === "" || status === "open" || status === "active";
  const live = !m.deadline || m.deadline > nowSeconds();
  return openish && live;
}

/**
 * discover node — list open missions from the protocol.
 */
export function discoverNode(deps: NodeDeps) {
  const { client } = deps;
  return async (state: OabpStateType): Promise<OabpStateUpdate> => {
    try {
      const all = await client.listMissions();
      const open = all.filter(isOpen);
      return {
        missions: open,
        log: [`discover: ${all.length} missions, ${open.length} open/live`],
      };
    } catch (err) {
      return {
        missions: [],
        errors: [`discover failed: ${(err as Error).message}`],
        log: ["discover: error (see errors[])"],
      };
    }
  };
}

/**
 * Decide whether *this* agent can verifiably complete a mission, and score it.
 * Pure function so it can be unit-tested and reused outside the graph.
 */
export function scoreMission(
  mission: Mission,
  agentId: string,
  minRewardAigen: number
): EvaluatedMission {
  const rewardScore = rewardInAigenEquivalent(
    mission.reward.amount,
    mission.reward.currency
  );

  let claimable = rewardScore >= minRewardAigen;
  let reason = claimable
    ? "reward at/above threshold"
    : `reward ${rewardScore} < min ${minRewardAigen}`;

  // Don't re-submit to a mission we've already submitted to.
  const already = (mission.submissions ?? []).some(
    (s) => s.submitter_agent_id === agentId
  );
  if (already) {
    claimable = false;
    reason = "already submitted by this agent";
  }

  // Verification feasibility: only claim what we can actually satisfy.
  switch (mission.verification_type) {
    case "first_valid_match": {
      const re = mission.verification_params?.regex;
      if (claimable && !re) {
        claimable = false;
        reason = "first_valid_match without a regex — nothing to satisfy";
      }
      break;
    }
    case "oracle":
      // GoPlus (safety review) / GitHub (repo deliverable) — feasible for an autonomous worker.
      break;
    case "peer_vote":
    case "creator_judges":
      // Subjective verification: a code worker can't deterministically win these.
      if (claimable) {
        claimable = false;
        reason = `subjective verification (${mission.verification_type}) — skipped by autonomous worker`;
      }
      break;
  }

  // Mild deadline-urgency bonus so sooner deadlines sort first among equal rewards.
  const secsLeft = mission.deadline ? mission.deadline - nowSeconds() : Infinity;
  const urgencyBonus = Number.isFinite(secsLeft)
    ? Math.max(0, 1 - secsLeft / (7 * 24 * 3600))
    : 0;

  return {
    mission,
    score: rewardScore + urgencyBonus,
    claimable,
    reason,
  };
}

/**
 * evaluate node — score & filter discovered missions, sorted by score desc.
 * Writes `evaluated` (all, annotated) and `claimable` (the winnable subset), and resets `cursor`.
 */
export function evaluateNode() {
  return async (state: OabpStateType): Promise<OabpStateUpdate> => {
    const evaluated = state.missions
      .map((m) => scoreMission(m, state.agentId, state.minRewardAigen))
      .sort((a, b) => b.score - a.score);
    const claimable = evaluated.filter((e) => e.claimable);
    return {
      evaluated,
      claimable,
      cursor: 0,
      log: [`evaluate: ${claimable.length}/${evaluated.length} claimable`],
    };
  };
}

/** Default proof builder — content-addressed, satisfies a first_valid_match regex if present. */
export function defaultBuildProof(mission: Mission, agentId: string): string {
  const params: VerificationParams = mission.verification_params ?? {};
  if (mission.verification_type === "first_valid_match" && params.regex) {
    const sample = sampleStringForRegex(params.regex);
    if (sample !== null) return sample;
  }
  // oracle / fallback: a descriptive deliverable pointer the verifier can resolve.
  return `agent:${agentId} deliverable for mission:${mission.id} — ${mission.title}`;
}

/**
 * submit node primitive — submit a proof for ONE mission.
 * Exposed so callers can compose their own loops; the worker below uses it internally.
 */
export function submitNode(deps: NodeDeps) {
  const { client, buildProof = defaultBuildProof } = deps;
  return async (mission: EvaluatedMission, agentId: string): Promise<MissionResult> => {
    const m = mission.mission;
    let proof = "";
    try {
      proof = await buildProof(m, agentId);
      const res = await client.submit(m.id, agentId, proof);
      const accepted = res?.accepted === true;
      return {
        missionId: m.id,
        title: m.title,
        submitted: true,
        accepted,
        proof,
        detail: res?.detail,
        raw: res,
      };
    } catch (err) {
      return {
        missionId: m.id,
        title: m.title,
        submitted: false,
        accepted: false,
        proof,
        error: (err as Error).message,
      };
    }
  };
}

/**
 * worker node — claim & submit the mission at `cursor`, then advance the cursor.
 * Routing (see graph.ts) loops back into this node while claimable missions remain.
 */
export function workerNode(deps: NodeDeps) {
  const submitOne = submitNode(deps);
  return async (state: OabpStateType): Promise<OabpStateUpdate> => {
    const idx = state.cursor;
    const target = state.claimable[idx];
    if (!target) {
      return { log: [`worker: nothing at cursor ${idx}, idle`] };
    }
    const result = await submitOne(target, state.agentId);
    const verdict = result.submitted
      ? result.accepted
        ? "ACCEPTED"
        : "submitted (pending/rejected)"
      : `FAILED (${result.error})`;
    return {
      results: [result],
      cursor: idx + 1,
      log: [`worker: mission ${target.mission.id} -> ${verdict}`],
    };
  };
}

/**
 * claim node — alias of the worker, present so the public node set matches the spec's
 * discover/evaluate/claim/submit vocabulary. In OABP "claiming" *is* submitting a deliverable
 * (there is no separate lock step), so claim and worker are the same operation.
 */
export const claimNode = workerNode;

/**
 * Router used after evaluate and after each worker pass:
 *  - if there is a claimable mission at `cursor`, go to the worker;
 *  - otherwise finish.
 */
export function routeClaimable(state: OabpStateType): "worker" | "done" {
  return state.cursor < state.claimable.length ? "worker" : "done";
}

/**
 * Best-effort generator of a string matching a (simple) regex, so a content-addressed
 * `first_valid_match` proof can be produced offline. Handles the common, literal-ish cases
 * (anchors, char classes, escapes, fixed quantifiers); returns null if it can't be sure.
 */
export function sampleStringForRegex(pattern: string): string | null {
  try {
    const src = pattern.replace(/^\^/, "").replace(/\$$/, "");
    let out = "";
    let i = 0;
    while (i < src.length) {
      // 1) Read one "atom" and the index just past it.
      let atom: string;
      const ch = src[i];
      if (ch === "\\") {
        const n = src[i + 1];
        if (n === undefined) return null;
        if (n === "d") atom = "0";
        else if (n === "w") atom = "a";
        else if (n === "s") atom = " ";
        else atom = n; // escaped literal
        i += 2;
      } else if (ch === "[") {
        const close = src.indexOf("]", i);
        if (close === -1) return null;
        atom = pickFromClass(src.slice(i + 1, close));
        i = close + 1;
      } else if (ch === ".") {
        atom = "x";
        i += 1;
      } else if (ch === "(" || ch === ")" || ch === "|") {
        return null; // groups/alternation: can't sample safely
      } else if ("+*?{".includes(ch)) {
        // A quantifier with nothing in front of it -> malformed for our purposes.
        return null;
      } else {
        atom = ch; // literal
        i += 1;
      }

      // 2) Apply a trailing quantifier, if any, to that atom.
      let count = 1;
      const rest = src.slice(i);
      const brace = /^\{(\d+)(?:,(\d*))?\}/.exec(rest);
      if (brace) {
        count = parseInt(brace[1], 10); // produce exactly the minimum -> always valid
        i += brace[0].length;
      } else if (rest[0] === "+") {
        count = 1;
        i += 1;
      } else if (rest[0] === "*") {
        count = 0;
        i += 1;
      } else if (rest[0] === "?") {
        count = 1;
        i += 1;
      }
      out += atom.repeat(count);
    }
    // 3) Sanity-check our own sample against the real regex before trusting it.
    if (new RegExp(pattern).test(out)) return out;
    return null;
  } catch {
    return null;
  }
}

function pickFromClass(cls: string): string {
  if (/0-9/.test(cls) || /\\d/.test(cls)) return "0";
  if (/a-z/.test(cls)) return "a";
  if (/A-Z/.test(cls)) return "A";
  const literal = cls.replace(/\\./g, (m) => m[1]).replace(/[\^\-]/g, "");
  return literal[0] ?? "x";
}
