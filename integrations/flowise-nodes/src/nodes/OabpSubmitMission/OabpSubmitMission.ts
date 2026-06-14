/**
 * Flowise Tool node: submit a deliverable to an OABP / AIGEN mission.
 *
 * `init()` returns a LangChain `DynamicStructuredTool` (`oabp_submit_mission`, zod schema for
 * mission_id/submitter_agent_id/proof) backed by the dependency-free OABP fetch client. The tool
 * posts `POST /missions/{id}/submit`; the response says whether the permissionless verifier
 * (regex for first_valid_match, GoPlus/GitHub for oracle) accepted the proof, and echoes the
 * mission id.
 */

import type { DynamicStructuredTool } from "@langchain/core/tools";

import type {
  ICommonObject,
  INode,
  INodeData,
  INodeParams,
} from "../../flowise-types.js";
import { buildClient } from "../../utils.js";
import { buildSubmitMissionTool } from "../../tools.js";
import { OABP_CATEGORY, OABP_CREDENTIAL_INPUT, OABP_ICON, TOOL_BASE_CLASSES } from "../common.js";

class OabpSubmitMission_Tools implements INode {
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
    this.label = "OABP Submit Mission";
    this.name = "oabpSubmitMission";
    this.version = 1.0;
    this.type = "OabpSubmitMission";
    this.icon = OABP_ICON;
    this.category = OABP_CATEGORY;
    this.description =
      "Submit a deliverable ('proof') to an OABP / AIGEN mission. Verification is permissionless: " +
      "a regex for first_valid_match, GoPlus token-security or a GitHub repo for oracle missions. " +
      "Returns whether the submission was accepted plus the verifier's notes.";
    this.baseClasses = TOOL_BASE_CLASSES;
    this.credential = OABP_CREDENTIAL_INPUT;
    this.inputs = [
      {
        label: "Default Submitter Agent ID",
        name: "submitterAgentId",
        type: "string",
        optional: true,
        additionalParams: true,
        description:
          "Optional default submitter_agent_id hint. The tool's own argument still takes precedence " +
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
    return buildSubmitMissionTool(client);
  }
}

// Flowise reads `module.exports.nodeClass`; under CommonJS emit this named export is that.
export { OabpSubmitMission_Tools as nodeClass };
export { OabpSubmitMission_Tools };
export default OabpSubmitMission_Tools;
