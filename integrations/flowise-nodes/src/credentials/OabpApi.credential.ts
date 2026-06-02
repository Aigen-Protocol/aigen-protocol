/**
 * Flowise credential: OABP / AIGEN connection.
 *
 * Holds the protocol base URL and an optional bearer token. Every OABP node references this
 * credential by name (`oabpApi`) via its `credential` input. The base URL defaults to the public
 * deployment, and the bearer is only needed if a deployment gates writes — so the credential is
 * effectively optional for read-only use against `https://cryptogenesis.duckdns.org`.
 *
 * Flowise discovers a credential module by its default/`credClass` export and renders `inputs` in
 * the "Add Credential" dialog; the values are encrypted at rest and decrypted at run time via
 * `getCredentialData(nodeData.credential, options)` (see `src/utils.ts`).
 */

import type { INodeCredential, INodeParams } from "../flowise-types.js";
import { DEFAULT_BASE_URL } from "../sdk.js";

class OabpApi implements INodeCredential {
  label: string;
  name: string;
  version: number;
  description: string;
  inputs: INodeParams[];

  constructor() {
    this.label = "OABP API";
    this.name = "oabpApi";
    this.version = 1.0;
    this.description =
      "Connection to the OABP / AIGEN agent-bounty protocol. Base URL defaults to the public " +
      "deployment; the bearer token is only required if the deployment gates writes.";
    this.inputs = [
      {
        label: "Base URL",
        name: "oabpBaseUrl",
        type: "string",
        default: DEFAULT_BASE_URL,
        placeholder: DEFAULT_BASE_URL,
        description: "OABP base URL, e.g. https://cryptogenesis.duckdns.org",
      },
      {
        label: "Bearer Token",
        name: "oabpApiKey",
        type: "password",
        optional: true,
        description:
          "Optional bearer token sent as `Authorization: Bearer …`. Leave blank for the public, " +
          "read/write-open deployment.",
      },
    ];
  }
}

// Flowise reads `module.exports.credClass`; under CommonJS emit this named export is that.
export { OabpApi as credClass };
export { OabpApi };
export default OabpApi;
