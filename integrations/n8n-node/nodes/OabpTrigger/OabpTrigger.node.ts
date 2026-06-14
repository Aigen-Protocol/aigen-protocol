/**
 * OabpTrigger — n8n polling trigger for the OABP / AIGEN marketplace.
 *
 * On each poll it fetches open missions (`GET /api/missions`), compares their
 * `mis_*` ids against the set of ids already seen (persisted in the node's
 * workflow static data), and emits ONE output item per newly-opened mission.
 * Already-seen missions are never re-emitted (id-dedup), so a downstream agent
 * reacts to each new bounty exactly once.
 *
 * The poll interval itself is configured through n8n's standard trigger
 * schedule UI; this node implements `poll()`, which n8n invokes on that
 * schedule. In `manual` mode (the editor "fetch test event" button) it returns
 * the current open missions without mutating the seen-set, so testing is
 * side-effect-free.
 */

import type {
  IDataObject,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
  IPollFunctions,
} from 'n8n-workflow';

import { listMissions } from '../../shared/GenericFunctions';
import type { Mission } from '../../shared/types';

/** Shape of the state we persist between polls. */
interface TriggerStaticData extends IDataObject {
  /** Mission ids already emitted, so they are never emitted again. */
  seenIds?: string[];
  /** True once the very first poll has run (used to optionally skip backfill). */
  initialized?: boolean;
}

export class OabpTrigger implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'OABP Trigger',
    name: 'oabpTrigger',
    icon: 'file:oabp.svg',
    group: ['trigger'],
    version: 1,
    subtitle: '={{"newly-opened missions"}}',
    description:
      'Starts the workflow when a new mission opens on the OABP / AIGEN marketplace. Polls GET /api/missions and emits one item per newly-seen mis_* id.',
    defaults: { name: 'OABP Trigger' },
    // A polling trigger has no input and a single main output.
    inputs: [],
    outputs: ['main'],
    polling: true,
    credentials: [
      {
        name: 'oabpApi',
        required: true,
      },
    ],
    properties: [
      {
        displayName: 'Verification Type',
        name: 'verificationType',
        type: 'options',
        default: '',
        description: 'Only emit newly-opened missions using this verification type',
        options: [
          { name: 'Any', value: '' },
          { name: 'First Valid Match', value: 'first_valid_match' },
          { name: 'Oracle', value: 'oracle' },
          { name: 'Peer Vote', value: 'peer_vote' },
          { name: 'Creator Judges', value: 'creator_judges' },
        ],
      },
      {
        displayName: 'Currency',
        name: 'currency',
        type: 'options',
        default: '',
        description: 'Only emit newly-opened missions denominated in this currency',
        options: [
          { name: 'Any', value: '' },
          { name: 'AIGEN', value: 'AIGEN' },
          { name: 'USDC', value: 'USDC' },
        ],
      },
      {
        displayName: 'Minimum Reward Amount',
        name: 'minReward',
        type: 'number',
        typeOptions: { minValue: 0 },
        default: 0,
        description: 'Skip missions whose reward amount is below this threshold',
      },
      {
        displayName: 'Emit Existing Missions on First Poll',
        name: 'emitExistingOnFirstPoll',
        type: 'boolean',
        default: false,
        description:
          'Whether the first poll should emit all currently-open missions. When off, the first poll only records existing ids and emits nothing, so you only get missions opened from now on.',
      },
    ],
  };

  async poll(this: IPollFunctions): Promise<INodeExecutionData[][] | null> {
    const verificationType = this.getNodeParameter('verificationType', '') as string;
    const currency = this.getNodeParameter('currency', '') as string;
    const minReward = this.getNodeParameter('minReward', 0) as number;
    const emitExistingOnFirstPoll = this.getNodeParameter(
      'emitExistingOnFirstPoll',
      false,
    ) as boolean;

    // Fetch the current open missions, then apply the client-side filters.
    let missions = await listMissions(this, 'open');
    missions = missions.filter((m) => applyFilters(m, verificationType, currency, minReward));

    const isManual = this.getMode() === 'manual';

    if (isManual) {
      // Editor "fetch test event": return current open missions, mutate nothing.
      const data = missions.map(toItem);
      return data.length ? [data] : null;
    }

    const staticData = this.getWorkflowStaticData('node') as TriggerStaticData;
    const seen = new Set<string>(Array.isArray(staticData.seenIds) ? staticData.seenIds : []);

    const firstPoll = !staticData.initialized;

    const fresh: Mission[] = [];
    for (const mission of missions) {
      if (!mission.id) continue;
      if (seen.has(mission.id)) continue;
      seen.add(mission.id);
      // On the very first poll, only emit when explicitly asked to backfill.
      if (firstPoll && !emitExistingOnFirstPoll) continue;
      fresh.push(mission);
    }

    // Persist the updated seen-set + initialized flag for the next poll.
    staticData.seenIds = [...seen];
    staticData.initialized = true;

    if (fresh.length === 0) {
      // Returning null signals "nothing new" so the workflow is not triggered.
      return null;
    }

    return [fresh.map(toItem)];
  }
}

/** Apply the configured client-side filters to a mission. */
function applyFilters(
  mission: Mission,
  verificationType: string,
  currency: string,
  minReward: number,
): boolean {
  if (verificationType && mission.verification_type !== verificationType) return false;
  if (currency && mission.reward?.currency !== currency) return false;
  if (minReward > 0 && (mission.reward?.amount ?? 0) < minReward) return false;
  return true;
}

/** Wrap a mission as an n8n execution item. */
function toItem(mission: Mission): INodeExecutionData {
  return { json: mission as unknown as IDataObject };
}
