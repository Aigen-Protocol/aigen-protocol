/**
 * `oabpMarketplaceProvider` — an ElizaOS Provider that injects the current OPEN OABP missions into
 * the agent's state, so the model is always aware of what bounties it could list/create/submit to.
 *
 * ElizaOS calls `get(runtime, message, state)` while composing state; the returned `text` is spliced
 * into the prompt context, and `values`/`data` are merged into `state.values`/`state.data`
 * (namespaced under the provider name). We surface a compact, ranked snapshot plus structured data
 * the actions can reuse.
 *
 * It is non-`dynamic` (runs on every composeState) and `position: 50` so it lands after core
 * providers. All I/O goes through the runtime-resolved {@link OabpClient}, so it is offline-testable.
 */

import type { IAgentRuntime, Memory, Provider, ProviderResult, State } from "./eliza-types.js";
import type { Mission, Stats } from "./sdk.js";
import { formatReward, getClient, isOpen, netReward, summarizeMission } from "./runtime.js";

/** Cap how many missions we inline into context to keep the prompt bounded. */
const MAX_MISSIONS_IN_CONTEXT = 12;

export const oabpMarketplaceProvider: Provider = {
  name: "OABP_MARKETPLACE",
  description:
    "Live snapshot of open OABP/AIGEN missions (bounties) the agent can list, create, or submit to, " +
    "plus protocol stats. Injected into context so the agent knows what work is available.",
  dynamic: false,
  position: 50,

  get: async (runtime: IAgentRuntime, _message: Memory, _state?: State): Promise<ProviderResult> => {
    const client = getClient(runtime);

    let missions: Mission[] = [];
    let stats: Stats | undefined;
    let errorText = "";

    try {
      const all = await client.listMissions();
      missions = all.filter((m) => isOpen(m)).sort((a, b) => rewardWeight(b) - rewardWeight(a));
    } catch (err) {
      errorText = `\n(OABP missions unavailable: ${(err as Error).message})`;
    }

    // Stats are best-effort; never let them break the provider.
    try {
      stats = await client.getStats();
    } catch {
      stats = undefined;
    }

    const shown = missions.slice(0, MAX_MISSIONS_IN_CONTEXT);
    const header =
      missions.length === 0
        ? "# OABP marketplace\nNo open missions right now."
        : `# OABP marketplace — ${missions.length} open mission(s)` +
          (missions.length > shown.length ? ` (showing top ${shown.length})` : "");

    const body = shown.map(summarizeMission).join("\n");
    const statsLine = stats
      ? `\nProtocol: ${stats.open} open, ${stats.resolved} resolved, ${stats.lifetime_reward_aigen_paid} AIGEN paid lifetime.`
      : "";
    const guidance =
      missions.length > 0
        ? "\nUse LIST_OABP_MISSIONS to show these, SUBMIT_OABP_MISSION <id> to claim one, or CREATE_OABP_MISSION to post your own. Rewards shown are gross; OABP charges a 0.5% fee."
        : "\nUse CREATE_OABP_MISSION to post a bounty.";

    const text = `${header}\n${body}${statsLine}${guidance}${errorText}`.trim();

    return {
      text,
      values: {
        oabp_open_count: missions.length,
        oabp_resolved: stats?.resolved ?? null,
        oabp_lifetime_aigen_paid: stats?.lifetime_reward_aigen_paid ?? null,
        // Lightweight list for quick reference by the model / other providers.
        oabp_open_mission_ids: missions.map((m) => m.id),
      },
      data: {
        // Full structured missions for actions/evaluators that want to avoid a re-fetch.
        missions,
        stats: stats ?? null,
        top: shown.map((m) => ({
          id: m.id,
          title: m.title,
          reward: formatReward(m),
          net_reward: netReward(m.reward.amount),
          verification_type: m.verification_type,
        })),
      },
    };
  },
};

/** Same weighting the LIST action uses: USDC ~1000× the uncapped AIGEN points. */
function rewardWeight(m: Mission): number {
  return m.reward.currency === "USDC" ? m.reward.amount * 1000 : m.reward.amount;
}
