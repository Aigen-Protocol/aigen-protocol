/**
 * Oabp — n8n regular (action) node for the OABP / AIGEN agent-bounty marketplace.
 *
 * Resources × operations (>= 6 operations total):
 *   Mission    -> list   (GET  /api/missions)
 *                 get    (GET  /api/missions/{id})
 *                 create (POST /api/missions)
 *                 submit (POST /missions/{id}/submit)
 *   Statistic  -> getStats     (GET /api/stats)
 *   Reputation -> getReputation (derived from /api/missions)
 *
 * The node declares its UI through the standard `INodeTypeDescription.properties`
 * (see `Oabp.properties.ts`) and performs every call in `execute()` via n8n's
 * native `this.helpers.httpRequest` (wrapped in `shared/GenericFunctions.ts`).
 * Each input item is processed independently, with `continueOnFail()` honored.
 */

import type {
  IDataObject,
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
} from 'n8n-workflow';
import { NodeOperationError } from 'n8n-workflow';

import {
  createMission,
  getMission,
  getReputation,
  getStats,
  getOabpConfig,
  listMissions,
  netReward,
  submitMission,
} from '../../shared/GenericFunctions';
import type {
  CreateMissionRequest,
  Mission,
  RewardCurrency,
  SubmitRequest,
  VerificationParams,
  VerificationType,
} from '../../shared/types';
import { oabpNodeProperties } from './Oabp.properties';

export class Oabp implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'OABP',
    name: 'oabp',
    icon: 'file:oabp.svg',
    group: ['transform'],
    version: 1,
    subtitle: '={{$parameter["operation"] + ": " + $parameter["resource"]}}',
    description:
      'Interact with the OABP / AIGEN agent-bounty marketplace: list, get, create and submit missions, read protocol stats, and compute agent reputation.',
    defaults: { name: 'OABP' },
    inputs: ['main'],
    outputs: ['main'],
    credentials: [
      {
        name: 'oabpApi',
        required: true,
      },
    ],
    properties: oabpNodeProperties,
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const returnData: INodeExecutionData[] = [];

    // The credential's default agent id backs operations whose own agent field
    // is left blank.
    const { agentId: defaultAgentId } = await getOabpConfig(this);

    for (let i = 0; i < items.length; i++) {
      try {
        const resource = this.getNodeParameter('resource', i) as string;
        const operation = this.getNodeParameter('operation', i) as string;

        if (resource === 'mission' && operation === 'list') {
          const status = this.getNodeParameter('status', i, '') as string;
          const filters = this.getNodeParameter('filters', i, {}) as {
            verificationType?: string;
            currency?: string;
            excludeExpired?: boolean;
          };

          let missions = await listMissions(this, status || undefined);
          if (filters.verificationType) {
            missions = missions.filter((m) => m.verification_type === filters.verificationType);
          }
          if (filters.currency) {
            missions = missions.filter((m) => m.reward?.currency === filters.currency);
          }
          if (filters.excludeExpired) {
            const now = Math.floor(Date.now() / 1000);
            missions = missions.filter(
              (m) => typeof m.deadline !== 'number' || m.deadline > now,
            );
          }

          // One output item per mission.
          for (const mission of missions) {
            returnData.push({
              json: mission as unknown as IDataObject,
              pairedItem: { item: i },
            });
          }
        } else if (resource === 'mission' && operation === 'get') {
          const missionId = this.getNodeParameter('missionId', i) as string;
          assertNonEmpty(this, missionId, 'Mission ID', i);
          const mission = await getMission(this, missionId);
          returnData.push({ json: mission as unknown as IDataObject, pairedItem: { item: i } });
        } else if (resource === 'mission' && operation === 'create') {
          const verificationType = this.getNodeParameter(
            'verificationType',
            i,
          ) as VerificationType;

          const verification_params: VerificationParams = {};
          if (verificationType === 'first_valid_match') {
            const regex = this.getNodeParameter('regex', i, '') as string;
            assertNonEmpty(this, regex, 'Match Regex', i);
            assertValidRegex(this, regex, i);
            verification_params.regex = regex;
          } else if (verificationType === 'oracle') {
            const oracleDescription = this.getNodeParameter('oracleDescription', i, '') as string;
            assertNonEmpty(this, oracleDescription, 'Oracle Description', i);
            verification_params.oracle_description = oracleDescription;
          }

          const creatorAgentId =
            (this.getNodeParameter('creatorAgentId', i, '') as string) || defaultAgentId;
          assertNonEmpty(this, creatorAgentId, 'Creator Agent ID (or credential default)', i);

          const rewardAmount = this.getNodeParameter('rewardAmount', i) as number;
          if (!Number.isFinite(rewardAmount) || rewardAmount <= 0) {
            throw new NodeOperationError(
              this.getNode(),
              'Reward Amount must be a number greater than 0',
              { itemIndex: i },
            );
          }

          const body: CreateMissionRequest = {
            creator_agent_id: creatorAgentId,
            title: this.getNodeParameter('title', i) as string,
            description: this.getNodeParameter('description', i) as string,
            reward_amount: rewardAmount,
            reward_currency: this.getNodeParameter('rewardCurrency', i) as RewardCurrency,
            verification_type: verificationType,
            verification_params,
            deadline_hours: this.getNodeParameter('deadlineHours', i) as number,
          };

          const mission = await createMission(this, body);
          returnData.push({
            json: {
              ...(mission as unknown as IDataObject),
              // Surface the net payout a winner would receive after the 0.5% fee.
              net_reward: netReward(mission.reward?.amount ?? rewardAmount),
            },
            pairedItem: { item: i },
          });
        } else if (resource === 'mission' && operation === 'submit') {
          const missionId = this.getNodeParameter('missionId', i) as string;
          assertNonEmpty(this, missionId, 'Mission ID', i);

          const proof = this.getNodeParameter('proof', i) as string;
          assertNonEmpty(this, proof, 'Proof', i);

          const submitterAgentId =
            (this.getNodeParameter('submitterAgentId', i, '') as string) || defaultAgentId;
          assertNonEmpty(this, submitterAgentId, 'Submitter Agent ID (or credential default)', i);

          const body: SubmitRequest = {
            submitter_agent_id: submitterAgentId,
            proof,
          };
          const result = await submitMission(this, missionId, body);
          returnData.push({
            json: result as unknown as IDataObject,
            pairedItem: { item: i },
          });
        } else if (resource === 'stats' && operation === 'getStats') {
          const stats = await getStats(this);
          returnData.push({ json: stats as unknown as IDataObject, pairedItem: { item: i } });
        } else if (resource === 'reputation' && operation === 'getReputation') {
          const agentId = (this.getNodeParameter('agentId', i, '') as string) || defaultAgentId;
          assertNonEmpty(this, agentId, 'Agent ID (or credential default)', i);
          const reputation = await getReputation(this, agentId);
          returnData.push({
            json: reputation as unknown as IDataObject,
            pairedItem: { item: i },
          });
        } else {
          throw new NodeOperationError(
            this.getNode(),
            `Unsupported operation "${operation}" for resource "${resource}"`,
            { itemIndex: i },
          );
        }
      } catch (error) {
        if (this.continueOnFail()) {
          returnData.push({
            json: { error: (error as Error).message },
            pairedItem: { item: i },
          });
          continue;
        }
        throw error;
      }
    }

    return [returnData];
  }
}

// -----------------------------------------------------------------------------
// Local validation helpers (kept in-node so the description stays self-contained)
// -----------------------------------------------------------------------------

function assertNonEmpty(
  ctx: IExecuteFunctions,
  value: unknown,
  fieldName: string,
  itemIndex: number,
): asserts value is string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new NodeOperationError(ctx.getNode(), `${fieldName} is required`, { itemIndex });
  }
}

function assertValidRegex(ctx: IExecuteFunctions, pattern: string, itemIndex: number): void {
  try {
    // Ensure the mission isn't dead-on-arrival with an uncompilable regex.
    void new RegExp(pattern);
  } catch (e) {
    throw new NodeOperationError(
      ctx.getNode(),
      `Match Regex is not a valid regular expression: ${
        e instanceof Error ? e.message : String(e)
      }`,
      { itemIndex },
    );
  }
}

// Keep `Mission` referenced for downstream typing clarity even though execute()
// serializes through IDataObject.
export type { Mission };
