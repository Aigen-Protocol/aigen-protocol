/**
 * Flowise Tool node: list open OABP / AIGEN missions.
 *
 * `init()` returns a LangChain `DynamicStructuredTool` (`oabp_list_missions`, empty zod schema)
 * backed by the dependency-free OABP fetch client. Drop it into a Flowise Agent/Tool Agent so the
 * model can discover open bounties (`GET /api/missions`).
 */

import type { DynamicStructuredTool } from "@langchain/core/tools";

import type {
  ICommonObject,
  INode,
  INodeData,
  INodeParams,
} from "../../flowise-types.js";
import { buildClient } from "../../utils.js";
import { buildListMissionsTool } from "../../tools.js";
import { OABP_CATEGORY, OABP_CREDENTIAL_INPUT, OABP_ICON, TOOL_BASE_CLASSES } from "../common.js";

class OabpListMissions_Tools implements INode {
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
    this.label = "OABP List Missions";
    this.name = "oabpListMissions";
    this.version = 1.0;
    this.type = "OabpListMissions";
    this.icon = OABP_ICON;
    this.category = OABP_CATEGORY;
    this.description =
      "List the OPEN missions (bounties) on the OABP / AIGEN agent-bounty protocol — id, title, " +
      "reward (AIGEN/USDC), verification method and deadline.";
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
    return buildListMissionsTool(client);
  }
}

/**
 * Flowise loads node modules by reading `module.exports.nodeClass`. Under CommonJS emit (this
 * package compiles to CJS), `export { X as nodeClass }` becomes `exports.nodeClass`, i.e.
 * `module.exports.nodeClass` — exactly what the loader expects. The named/default exports are for
 * programmatic use and tests.
 */
export { OabpListMissions_Tools as nodeClass };
export { OabpListMissions_Tools };
export default OabpListMissions_Tools;
