/**
 * flowise-oabp — Flowise custom Tool nodes for the OABP / AIGEN agent-bounty protocol.
 *
 * Flowise loads node and credential **modules** (each a file whose `module.exports` carries a
 * `nodeClass` / `credClass`), so the node/credential files are the real entrypoints when dropped
 * into `packages/components/nodes` (or pointed at via `NODES_SOURCE_PATH`). This index is the
 * convenience surface for programmatic use / tests: it re-exports the node classes, the credential,
 * the tool builders, and the SDK + mock.
 *
 * Nodes (Flowise "Tools" category), each `init()` returns a LangChain `DynamicStructuredTool`:
 *   - OabpListMissions_Tools   -> oabp_list_missions   (GET  /api/missions)
 *   - OabpCreateMission_Tools  -> oabp_create_mission  (POST /api/missions)
 *   - OabpSubmitMission_Tools  -> oabp_submit_mission  (POST /missions/{id}/submit)
 *   - OabpStats_Tools          -> oabp_stats           (GET  /api/stats)
 */

export { OabpListMissions_Tools } from "./nodes/OabpListMissions/OabpListMissions.js";
export { OabpCreateMission_Tools } from "./nodes/OabpCreateMission/OabpCreateMission.js";
export { OabpSubmitMission_Tools } from "./nodes/OabpSubmitMission/OabpSubmitMission.js";
export { OabpStats_Tools } from "./nodes/OabpStats/OabpStats.js";

export { OabpApi } from "./credentials/OabpApi.credential.js";

export {
  buildListMissionsTool,
  buildCreateMissionTool,
  buildSubmitMissionTool,
  buildStatsTool,
  FEE_RATE,
  netReward,
  listMissionsSchema,
  createMissionSchema,
  submitMissionSchema,
  statsSchema,
} from "./tools.js";

export {
  OABP_CATEGORY,
  OABP_ICON,
  OABP_CREDENTIAL_INPUT,
  TOOL_BASE_CLASSES,
} from "./nodes/common.js";

export {
  buildClient,
  resolveCredential,
  getBaseClasses,
  type OabpCredentialData,
} from "./utils.js";

export * from "./sdk.js";
export { MockOabpClient, type MockSeed } from "./mock.js";

export type {
  ICommonObject,
  INode,
  INodeData,
  INodeParams,
  INodeCredential,
  INodeOptionsValue,
} from "./flowise-types.js";
