/**
 * `INodeProperties[]` describing the OABP regular node's UI: the Resource
 * selector (Mission / Stats / Reputation), the per-resource Operation selector,
 * and every operation's input fields. `displayOptions.show` gates each field to
 * the resource+operation it belongs to.
 *
 * Operations (>= 6, per the package spec):
 *   Mission    -> list, get, create, submit
 *   Stats      -> getStats
 *   Reputation -> getReputation
 */

import type { INodeProperties } from 'n8n-workflow';

export const RESOURCES = ['mission', 'stats', 'reputation'] as const;
export type Resource = (typeof RESOURCES)[number];

/** Every operation value the node implements, across all resources. */
export const OPERATIONS = [
  'list',
  'get',
  'create',
  'submit',
  'getStats',
  'getReputation',
] as const;
export type Operation = (typeof OPERATIONS)[number];

export const oabpNodeProperties: INodeProperties[] = [
  // ---------------------------------------------------------------------------
  // Resource
  // ---------------------------------------------------------------------------
  {
    displayName: 'Resource',
    name: 'resource',
    type: 'options',
    noDataExpression: true,
    default: 'mission',
    options: [
      {
        name: 'Mission',
        value: 'mission',
        description: 'Bounty missions (mis_* ids) on the OABP marketplace',
      },
      {
        name: 'Statistic',
        value: 'stats',
        description: 'Aggregate protocol statistics',
      },
      {
        name: 'Reputation',
        value: 'reputation',
        description: 'Per-agent reputation derived from mission history',
      },
    ],
  },

  // ---------------------------------------------------------------------------
  // Mission operations
  // ---------------------------------------------------------------------------
  {
    displayName: 'Operation',
    name: 'operation',
    type: 'options',
    noDataExpression: true,
    default: 'list',
    displayOptions: { show: { resource: ['mission'] } },
    options: [
      {
        name: 'List',
        value: 'list',
        action: 'List open missions',
        description: 'GET /api/missions — one item per mission',
      },
      {
        name: 'Get',
        value: 'get',
        action: 'Get a mission by ID',
        description: 'GET /api/missions/{id} — detail incl. submissions and resolution',
      },
      {
        name: 'Create',
        value: 'create',
        action: 'Create a mission',
        description: 'POST /api/missions',
      },
      {
        name: 'Submit',
        value: 'submit',
        action: 'Submit a deliverable to a mission',
        description: 'POST /missions/{id}/submit',
      },
    ],
  },

  // ---------------------------------------------------------------------------
  // Stats operations
  // ---------------------------------------------------------------------------
  {
    displayName: 'Operation',
    name: 'operation',
    type: 'options',
    noDataExpression: true,
    default: 'getStats',
    displayOptions: { show: { resource: ['stats'] } },
    options: [
      {
        name: 'Get',
        value: 'getStats',
        action: 'Get protocol statistics',
        description: 'GET /api/stats — resolved, open, lifetime AIGEN paid',
      },
    ],
  },

  // ---------------------------------------------------------------------------
  // Reputation operations
  // ---------------------------------------------------------------------------
  {
    displayName: 'Operation',
    name: 'operation',
    type: 'options',
    noDataExpression: true,
    default: 'getReputation',
    displayOptions: { show: { resource: ['reputation'] } },
    options: [
      {
        name: 'Get',
        value: 'getReputation',
        action: 'Get an agent reputation',
        description:
          'Derived from /api/missions — missions created/won/submitted and AIGEN/USDC earned',
      },
    ],
  },

  // ---------------------------------------------------------------------------
  // Fields: mission:list
  // ---------------------------------------------------------------------------
  {
    displayName: 'Status',
    name: 'status',
    type: 'options',
    default: 'open',
    displayOptions: { show: { resource: ['mission'], operation: ['list'] } },
    description: 'Filter missions by lifecycle status',
    options: [
      { name: 'Any', value: '' },
      { name: 'Open', value: 'open' },
      { name: 'Resolved', value: 'resolved' },
      { name: 'Expired', value: 'expired' },
      { name: 'Cancelled', value: 'cancelled' },
    ],
  },
  {
    displayName: 'Additional Filters',
    name: 'filters',
    type: 'collection',
    placeholder: 'Add Filter',
    default: {},
    displayOptions: { show: { resource: ['mission'], operation: ['list'] } },
    options: [
      {
        displayName: 'Verification Type',
        name: 'verificationType',
        type: 'options',
        default: '',
        description: 'Only return missions using this verification type (filtered client-side)',
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
        description: 'Only return missions denominated in this currency',
        options: [
          { name: 'Any', value: '' },
          { name: 'AIGEN', value: 'AIGEN' },
          { name: 'USDC', value: 'USDC' },
        ],
      },
      {
        displayName: 'Exclude Expired',
        name: 'excludeExpired',
        type: 'boolean',
        default: false,
        description: 'Whether to drop missions whose deadline has already passed',
      },
    ],
  },

  // ---------------------------------------------------------------------------
  // Fields: mission:get
  // ---------------------------------------------------------------------------
  {
    displayName: 'Mission ID',
    name: 'missionId',
    type: 'string',
    default: '',
    required: true,
    placeholder: 'mis_1a2b3c',
    displayOptions: { show: { resource: ['mission'], operation: ['get'] } },
    description: 'The mis_* id of the mission to fetch',
  },

  // ---------------------------------------------------------------------------
  // Fields: mission:create
  // ---------------------------------------------------------------------------
  {
    displayName: 'Title',
    name: 'title',
    type: 'string',
    default: '',
    required: true,
    displayOptions: { show: { resource: ['mission'], operation: ['create'] } },
    description: 'Short title of the mission',
  },
  {
    displayName: 'Description',
    name: 'description',
    type: 'string',
    typeOptions: { rows: 4 },
    default: '',
    required: true,
    displayOptions: { show: { resource: ['mission'], operation: ['create'] } },
    description: 'Full description of what the deliverable must be',
  },
  {
    displayName: 'Reward Amount',
    name: 'rewardAmount',
    type: 'number',
    typeOptions: { minValue: 0, numberPrecision: 6 },
    default: 100,
    required: true,
    displayOptions: { show: { resource: ['mission'], operation: ['create'] } },
    description: 'Gross reward; a winner nets reward * 0.995 after the 0.5% protocol fee',
  },
  {
    displayName: 'Reward Currency',
    name: 'rewardCurrency',
    type: 'options',
    default: 'AIGEN',
    displayOptions: { show: { resource: ['mission'], operation: ['create'] } },
    options: [
      { name: 'AIGEN (reputation points)', value: 'AIGEN' },
      { name: 'USDC', value: 'USDC' },
    ],
  },
  {
    displayName: 'Verification Type',
    name: 'verificationType',
    type: 'options',
    default: 'first_valid_match',
    displayOptions: { show: { resource: ['mission'], operation: ['create'] } },
    description: 'How submissions are judged',
    options: [
      { name: 'First Valid Match (regex)', value: 'first_valid_match' },
      { name: 'Oracle (GoPlus / GitHub)', value: 'oracle' },
      { name: 'Peer Vote', value: 'peer_vote' },
      { name: 'Creator Judges', value: 'creator_judges' },
    ],
  },
  {
    displayName: 'Match Regex',
    name: 'regex',
    type: 'string',
    default: '',
    required: true,
    placeholder: '^https://github\\.com/[^/]+/[^/]+',
    displayOptions: {
      show: {
        resource: ['mission'],
        operation: ['create'],
        verificationType: ['first_valid_match'],
      },
    },
    description: 'Regex a proof must satisfy to win (content-addressed)',
  },
  {
    displayName: 'Oracle Description',
    name: 'oracleDescription',
    type: 'string',
    typeOptions: { rows: 2 },
    default: '',
    required: true,
    placeholder: 'GitHub repo deliverable owner/name in Go',
    displayOptions: {
      show: {
        resource: ['mission'],
        operation: ['create'],
        verificationType: ['oracle'],
      },
    },
    description:
      'What the oracle must verify, e.g. a GoPlus token-security safety review or a GitHub repo deliverable',
  },
  {
    displayName: 'Deadline (Hours)',
    name: 'deadlineHours',
    type: 'number',
    typeOptions: { minValue: 0 },
    default: 24,
    required: true,
    displayOptions: { show: { resource: ['mission'], operation: ['create'] } },
    description: 'Hours from now until the mission deadline',
  },
  {
    displayName: 'Creator Agent ID',
    name: 'creatorAgentId',
    type: 'string',
    default: '',
    placeholder: 'leave blank to use the credential default',
    displayOptions: { show: { resource: ['mission'], operation: ['create'] } },
    description: 'Agent creating the mission; defaults to the credential Default Agent ID',
  },

  // ---------------------------------------------------------------------------
  // Fields: mission:submit
  // ---------------------------------------------------------------------------
  {
    displayName: 'Mission ID',
    name: 'missionId',
    type: 'string',
    default: '',
    required: true,
    placeholder: 'mis_1a2b3c',
    displayOptions: { show: { resource: ['mission'], operation: ['submit'] } },
    description: 'The mis_* id of the mission to submit to',
  },
  {
    displayName: 'Proof',
    name: 'proof',
    type: 'string',
    typeOptions: { rows: 3 },
    default: '',
    required: true,
    placeholder: 'https://github.com/owner/repo  or  free-text proof',
    displayOptions: { show: { resource: ['mission'], operation: ['submit'] } },
    description: 'Proof text or URL evaluated against the mission verification',
  },
  {
    displayName: 'Submitter Agent ID',
    name: 'submitterAgentId',
    type: 'string',
    default: '',
    placeholder: 'leave blank to use the credential default',
    displayOptions: { show: { resource: ['mission'], operation: ['submit'] } },
    description: 'Agent submitting the proof; defaults to the credential Default Agent ID',
  },

  // ---------------------------------------------------------------------------
  // Fields: reputation:getReputation
  // ---------------------------------------------------------------------------
  {
    displayName: 'Agent ID',
    name: 'agentId',
    type: 'string',
    default: '',
    placeholder: 'leave blank to use the credential default',
    displayOptions: { show: { resource: ['reputation'], operation: ['getReputation'] } },
    description: 'Agent to compute reputation for; defaults to the credential Default Agent ID',
  },
];
