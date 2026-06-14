/**
 * Frozen ES256 agent-card test vector.
 *
 * Generated once with `jose` (P-256 / ES256) and pinned here so the JWS
 * verification path is exercised against bytes the test process never signs
 * itself. ECDSA verification is deterministic, so this signature validates
 * reproducibly on every run and across machines.
 *
 * The signing input is the detached-JWS convention used by `verifyAgentCard`:
 *   BASE64URL(protected) + '.' + BASE64URL(JCS(card without `signatures`))
 */

/** Public JWK (goes in the served JWKS). */
export const PUBLIC_JWK = {
  kty: 'EC',
  crv: 'P-256',
  x: 'SDZtb9ajbfNaV49KtNAX8yG5nb4c8dFn8pFeHsSLQio',
  y: 'C1vn8mobhBufzHvH7_DkGnBbAYi_ZaNmsVEoznFiDB8',
  kid: 'vSEx1EvN-Ft3ZjwQHGPUoQbvn5bNlZipEdl9F84Wzyc',
  alg: 'ES256',
  use: 'sig',
} as const;

/**
 * Matching private JWK — used only by the "sign then verify" round-trip test
 * to mint fresh signatures. Never shipped or used in production code.
 */
export const PRIVATE_JWK = {
  kty: 'EC',
  crv: 'P-256',
  x: 'SDZtb9ajbfNaV49KtNAX8yG5nb4c8dFn8pFeHsSLQio',
  y: 'C1vn8mobhBufzHvH7_DkGnBbAYi_ZaNmsVEoznFiDB8',
  d: 'Xnwl11pwrBQBPi_ptIYYX3rBeOnk_bpwn35PQQff1Qg',
  kid: 'vSEx1EvN-Ft3ZjwQHGPUoQbvn5bNlZipEdl9F84Wzyc',
  alg: 'ES256',
} as const;

/** The card body that was signed (no `signatures` field). */
export const SIGNED_CARD = {
  name: 'AIGEN Protocol Agent',
  description: 'OABP mission marketplace agent',
  url: 'https://cryptogenesis.duckdns.org',
  version: '1.0.0',
  preferredTransport: 'JSONRPC',
} as const;

/** base64url(protected header) of the frozen signature. */
export const FROZEN_PROTECTED =
  'eyJhbGciOiJFUzI1NiIsImtpZCI6InZTRXgxRXZOLUZ0M1pqd1FIR1BVb1Fidm41Yk5sWmlwRWRsOUY4NFd6eWMifQ';

/** base64url(signature bytes) of the frozen signature. */
export const FROZEN_SIGNATURE =
  'kieK_gzfUPriGRR61mX_SUaxeNLt0djcXhW9gVemXxhg-9fO1H7UcFx8ISNZAwwji_yfgLC5omRs3uDawMvYug';

/** The JWKS document a server would serve at `/.well-known/jwks.json`. */
export const JWKS_DOC = { keys: [PUBLIC_JWK] } as const;

/** Full signed agent card as served at `/.well-known/agent-card.json`. */
export const SIGNED_AGENT_CARD = {
  ...SIGNED_CARD,
  signatures: [{ protected: FROZEN_PROTECTED, signature: FROZEN_SIGNATURE }],
} as const;
