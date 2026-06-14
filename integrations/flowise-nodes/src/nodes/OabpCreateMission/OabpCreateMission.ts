/**
 * Flowise Tool node: create (post) an OABP / AIGEN mission.
 *
 * `init()` returns a LangChain `DynamicStructuredTool` (`oabp_create_mission`, zod schema for
 * creator/title/description/reward/verification/deadline) backed by the dependency-free OABP fetch
 * client. The tool posts `POST /api/missions` and surfaces the net reward after the 0.5% fee.
 */

import type { DynamicStructuredTool } from "@langchain/core/tools";

import type {
  ICommonObject,
  INode,
  INodeData,
  INodeParams,
} from "../../flowise-types.js";
import { buildClient } from "../../utils.js";
import { buildCreateMissionTool } from "../../tools.js";
import { OABP_CATEGORY, OABP_CREDENTIAL_INPUT, OABP_ICON, TOOL_BASE_CLASSES } from "../common.js";

class OabpCreateMission_Tools implements INode {
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
    this.label = "OABP Create Mission";
    this.name = "oabpCreateMission";
    this.version = 1.0;
    this.type = "OabpCreateMission";
    this.icon = OABP_ICON;
    this.category = OABP_CATEGORY;
    this.description =
      "Post a new mission (bounty) on the OABP / AIGEN protocol: set a reward in AIGEN points or " +
      "USDC, a verification method (first_valid_match / oracle / peer_vote / creator_judges) and a " +
      "deadline. A 0.5% protocol fee applies.";
    this.baseClasses = TOOL_BASE_CLASSES;
    this.credential = OABP_CREDENTIAL_INPUT;
    this.inputs = [
      {
        label: "Default Creator Agent ID",
        name: "creatorAgentId",
        type: "string",
        optional: true,
        additionalParams: true,
        description:
          "Optional default creator_agent_id hint. The tool's own argument still takes precedence " +
          "when the agent supplies one.",
      },
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
    return buildCreateMissionTool(client);
  }
}

// Flowise reads `module.exports.nodeClass`; under CommonJS emit this named export is that.
export { OabpCreateMission_Tools as nodeClass };
export { OabpCreateMission_Tools };
export default OabpCreateMission_Tools;
