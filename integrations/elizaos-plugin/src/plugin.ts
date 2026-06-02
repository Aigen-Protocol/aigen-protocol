/**
 * `@aigen/plugin-oabp` — the ElizaOS Plugin object wiring the OABP / AIGEN agent-bounty protocol
 * into an ElizaOS agent.
 *
 * It bundles:
 *   - Actions:   LIST_OABP_MISSIONS, CREATE_OABP_MISSION, SUBMIT_OABP_MISSION
 *   - Provider:  oabpMarketplaceProvider  (injects open-mission context into state)
 *   - Evaluator: claimedMissionsEvaluator (tracks claimed missions — stub ledger)
 *
 * Settings (resolved via `runtime.getSetting`, sourced from the character's `settings`/`secrets`
 * then the environment):
 *   - OABP_BASE_URL  (default https://cryptogenesis.duckdns.org)
 *   - OABP_AGENT_ID  (default: the ElizaOS runtime agentId)
 *
 * `init` validates/normalizes those settings at load time (non-fatal: it only logs guidance, since
 * defaults are sensible and the protocol's writes may be open).
 */

import type { IAgentRuntime, Plugin } from "./eliza-types.js";
import { oabpActions } from "./actions.js";
import { oabpMarketplaceProvider } from "./provider.js";
import { claimedMissionsEvaluator } from "./evaluator.js";
import { DEFAULT_BASE_URL } from "./sdk.js";
import { OABP_AGENT_ID, OABP_BASE_URL } from "./runtime.js";

export const oabpPlugin: Plugin = {
  name: "@aigen/plugin-oabp",
  description:
    "OABP / AIGEN agent-bounty marketplace for ElizaOS: list, create, and submit/claim missions " +
    "(content-addressed `first_valid_match` or oracle-backed verification), with a live-marketplace " +
    "context provider and a claim-tracking evaluator. Talks to the OABP REST + A2A API.",

  config: {
    [OABP_BASE_URL]: DEFAULT_BASE_URL,
    [OABP_AGENT_ID]: "",
  },

  async init(config: Record<string, string>, runtime: IAgentRuntime): Promise<void> {
    const baseUrl = runtime.getSetting(OABP_BASE_URL) || config?.[OABP_BASE_URL] || DEFAULT_BASE_URL;
    const agentId = runtime.getSetting(OABP_AGENT_ID) || runtime.agentId;
    // Light validation; never throw — the plugin works against the public API with defaults.
    try {
      // eslint-disable-next-line no-new
      new URL(baseUrl);
    } catch {
      // eslint-disable-next-line no-console
      console.warn(`[@aigen/plugin-oabp] OABP_BASE_URL is not a valid URL: "${baseUrl}". Falling back to ${DEFAULT_BASE_URL}.`);
    }
    if (!agentId) {
      // eslint-disable-next-line no-console
      console.warn("[@aigen/plugin-oabp] No OABP_AGENT_ID set and runtime.agentId is empty; submissions need an agent id.");
    }
  },

  actions: oabpActions,
  providers: [oabpMarketplaceProvider],
  evaluators: [claimedMissionsEvaluator],
};

/** Default export is the Plugin object (what ElizaOS loads). */
export default oabpPlugin;
