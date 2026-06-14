/**
 * OabpState — the graph state schema.
 *
 * The spec calls for a "TypedDict OabpState". In LangGraph(.js) the idiomatic equivalent of a
 * Python `TypedDict` state is an `Annotation.Root({...})` schema: each key is a *channel* with an
 * optional reducer + default. `typeof OabpState.State` is the read type (what nodes receive) and
 * `typeof OabpState.Update` is the write type (what nodes may return) — the TS analogue of a
 * `TypedDict` (read) / `TypedDict(total=False)` (partial update).
 *
 * Channels:
 *  - missions      : missions discovered this run (replaced wholesale by discover).
 *  - evaluated     : missions annotated with a score/decision (replaced by evaluate).
 *  - claimable     : subset routed to the worker (replaced by evaluate).
 *  - results       : worker submission outcomes (appended — survives multiple worker passes).
 *  - cursor        : index of the next claimable mission the worker should handle.
 *  - agentId       : identity used when submitting / on A2A.
 *  - minRewardAigen: evaluation threshold (AIGEN-equivalent reward floor).
 *  - log           : human-readable trace, appended by every node.
 *  - errors        : non-fatal errors collected without aborting the run.
 */

import { Annotation } from "@langchain/langgraph";
import type { Mission, RewardCurrency, SubmitResult } from "./sdk.js";

/** A mission after the evaluate step has scored it. */
export interface EvaluatedMission {
  mission: Mission;
  /** Higher is more attractive. */
  score: number;
  /** Whether this agent should attempt the mission. */
  claimable: boolean;
  /** Why it was (not) deemed claimable — useful for audit. */
  reason: string;
}

/** Outcome of a single worker attempt on one mission. */
export interface MissionResult {
  missionId: string;
  title: string;
  submitted: boolean;
  accepted: boolean;
  proof: string;
  detail?: string;
  raw?: SubmitResult;
  error?: string;
}

/** last-write-wins reducer. */
function replace<T>(left: T, right: T | undefined): T {
  return right === undefined ? left : right;
}

/** append reducer that also accepts a single item. */
function append<T>(left: T[], right: T[] | T | undefined): T[] {
  if (right === undefined) return left;
  return left.concat(Array.isArray(right) ? right : [right]);
}

export const OabpState = Annotation.Root({
  missions: Annotation<Mission[]>({
    reducer: replace,
    default: () => [],
  }),
  evaluated: Annotation<EvaluatedMission[]>({
    reducer: replace,
    default: () => [],
  }),
  claimable: Annotation<EvaluatedMission[]>({
    reducer: replace,
    default: () => [],
  }),
  results: Annotation<MissionResult[]>({
    reducer: append,
    default: () => [],
  }),
  cursor: Annotation<number>({
    reducer: replace,
    default: () => 0,
  }),
  agentId: Annotation<string>({
    reducer: replace,
    default: () => "langgraph-oabp-worker",
  }),
  minRewardAigen: Annotation<number>({
    reducer: replace,
    default: () => 1,
  }),
  log: Annotation<string[]>({
    reducer: append,
    default: () => [],
  }),
  errors: Annotation<string[]>({
    reducer: append,
    default: () => [],
  }),
});

/** Read type — what a node receives (the "TypedDict"). */
export type OabpStateType = typeof OabpState.State;
/** Write type — the partial update a node may return. */
export type OabpStateUpdate = typeof OabpState.Update;

/**
 * Rough AIGEN-equivalent value of a reward, so AIGEN and USDC missions can be ranked together.
 * USDC is "real" money; weight it well above the uncapped AIGEN reputation token.
 */
export function rewardInAigenEquivalent(amount: number, currency: RewardCurrency): number {
  return currency === "USDC" ? amount * 1000 : amount;
}
