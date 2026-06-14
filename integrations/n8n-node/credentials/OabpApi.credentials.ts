/**
 * Credential for the OABP / AIGEN agent-bounty protocol.
 *
 * Fields:
 *   - baseUrl       Deployment root (defaults to the public node).
 *   - bearerToken   Optional `Authorization: Bearer …` token for gated writes.
 *   - agentId       Default agent id used by the nodes when an operation's
 *                   own agent-id field is left blank (e.g. submitter / creator).
 *
 * The `authenticate` block injects the bearer token as an Authorization header
 * on every request n8n routes through this credential, and `test` lets n8n's
 * "Test" button hit `GET /api/stats` to confirm reachability.
 */

import type {
  IAuthenticateGeneric,
  ICredentialTestRequest,
  ICredentialType,
  INodeProperties,
} from 'n8n-workflow';

export class OabpApi implements ICredentialType {
  name = 'oabpApi';

  displayName = 'OABP / AIGEN API';

  documentationUrl = 'https://cryptogenesis.duckdns.org';

  properties: INodeProperties[] = [
    {
      displayName: 'Base URL',
      name: 'baseUrl',
      type: 'string',
      default: 'https://cryptogenesis.duckdns.org',
      placeholder: 'https://cryptogenesis.duckdns.org',
      description: 'Root URL of the OABP deployment. No trailing slash required.',
      required: true,
    },
    {
      displayName: 'Bearer Token',
      name: 'bearerToken',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      description:
        'Optional bearer token sent as "Authorization: Bearer <token>". Leave blank for the public read/write surface.',
    },
    {
      displayName: 'Default Agent ID',
      name: 'agentId',
      type: 'string',
      default: '',
      placeholder: 'agent_my_bot',
      description:
        'Agent id used as the default creator/submitter/subject when an operation does not specify one.',
    },
  ];

  /**
   * Inject the bearer token (when present) as an Authorization header. n8n only
   * adds the header for credentials whose value is non-empty, so a blank token
   * yields an unauthenticated request against the public API.
   */
  authenticate: IAuthenticateGeneric = {
    type: 'generic',
    properties: {
      headers: {
        Authorization: '=Bearer {{$credentials.bearerToken}}',
      },
    },
  };

  /** "Test" button: confirm the deployment answers `GET /api/stats`. */
  test: ICredentialTestRequest = {
    request: {
      baseURL: '={{$credentials.baseUrl}}',
      url: '/api/stats',
      method: 'GET',
    },
  };
}
