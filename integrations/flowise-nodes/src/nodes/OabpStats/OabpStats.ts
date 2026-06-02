/**
 * Flowise Tool node: read protocol-wide OABP / AIGEN stats.
 *
 * `init()` returns a LangChain `DynamicStructuredTool` (`oabp_stats`, empty zod schema) backed by
 * the dependency-free OABP fetch client. The tool calls `GET /api/stats` and returns the resolved
 * / open mission counts and the lifetime AIGEN paid out.
 */

import type { DynamicStructuredTool } from "@langchain/core/tools";

import type {
  ICommonObject,
  INode,
  INodeData,
  INodeParams,
} from "../../flowise-types.js";
import { buildClient } from "../../utils.js";
import { buildStatsTool } from "../../tools.js";
import { OABP_CATEGORY, OABP_CREDENTIAL_INPUT, OABP_ICON, TOOL_BASE_CLASSES } from "../common.js";

class OabpStats_Tools implements INode {
  label: string;
  name: string;
  version: number;
  type: string;
  icon: string;
  category: string;
  description: string;
  baseClasses: string[];
  credential: INodeParams;
  inputs: INodeParams[];

  constructor() {
    this.label = "OABP Stats";
    this.name = "oabpStats";
    this.version = 1.0;
    this.type = "OabpStats";
    this.icon = OABP_ICON;
    this.category = OABP_CATEGORY;
    this.description =
      "Read protocol-wide OABP / AIGEN counters: resolved missions, open missions, and the " +
      "lifetime total of AIGEN points paid out.";
    this.baseClasses = TOOL_BASE_CLASSES;
    this.credential = OABP_CREDENTIAL_INPUT;
    this.inputs = [
      {
        label: "Base URL",
        name: "baseUrl",
        type: "string",
        optional: true,
        additionalParams: true,
        placeholder: "https://cryptogenesis.duckdns.org",
        description:
          "Override the OABP base URL (otherwise taken from the credential, else the public deployment).",
      },
    ];
  }

  async init(nodeData: INodeData, _input: string, options: ICommonObject = {}): Promise<DynamicStructuredTool> {
    const client = await buildClient(nodeData, options);
    return buildStatsTool(client);
  }
}

// Flowise reads `module.exports.nodeClass`; under CommonJS emit this named export is that.
export { OabpStats_Tools as nodeClass };
export { OabpStats_Tools };
export default OabpStats_Tools;
