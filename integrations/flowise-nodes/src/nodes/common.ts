/**
 * Shared metadata for all OABP Flowise Tool nodes.
 *
 *  - `OABP_CATEGORY` — every node lives in the Flowise "Tools" category;
 *  - `TOOL_BASE_CLASSES` — what each Tool node advertises in `baseClasses` so Flowise lets it
 *    connect to any Tool/Agent input. We compute this from the real `DynamicStructuredTool`
 *    prototype chain (mirroring Flowise's own `getBaseClasses`) and ensure 'Tool' is present;
 *  - `OABP_CREDENTIAL_INPUT` — the `type: 'credential'` input descriptor each node exposes so the
 *    OABP base URL + bearer come from a saved Flowise credential;
 *  - `OABP_ICON` — the node icon file name (resolved relative to the compiled node module).
 */

import { DynamicStructuredTool } from "@langchain/core/tools";

import type { INodeParams } from "../flowise-types.js";
import { getBaseClasses } from "../utils.js";

/** Flowise category for tool nodes. */
export const OABP_CATEGORY = "Tools" as const;

/** Icon shipped alongside the nodes (see `src/icons/oabp.svg`). */
export const OABP_ICON = "oabp.svg" as const;

/**
 * `baseClasses` for an OABP tool node. Flowise reads this to decide where the node can be wired;
 * a tool must surface 'Tool' (and ideally its concrete class chain). Deduplicated, 'Tool' first.
 */
export const TOOL_BASE_CLASSES: string[] = (() => {
  const chain = getBaseClasses(DynamicStructuredTool); // e.g. DynamicStructuredTool, StructuredTool, Tool, ...
  const set = ["Tool", ...chain];
  return [...new Set(set)];
})();

/**
 * The credential descriptor every OABP node references via its `credential` field. It points at
 * the `oabpApi` credential (see `src/credentials/OabpApi.credential.ts`), which holds the base URL
 * and an optional bearer token. Marked optional so the node still works against the default public
 * deployment with no credential configured.
 */
export const OABP_CREDENTIAL_INPUT: INodeParams = {
  label: "Connect Credential",
  name: "credential",
  type: "credential",
  credentialNames: ["oabpApi"],
  optional: true,
  description:
    "OABP connection (base URL + optional bearer). Omit to use the public deployment " +
    "https://cryptogenesis.duckdns.org with no auth.",
};
