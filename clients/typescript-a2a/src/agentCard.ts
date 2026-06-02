import {
  createLocalJWKSet,
  createRemoteJWKSet,
  customFetch,
  flattenedVerify,
  decodeProtectedHeader,
  base64url,
  type JWK,
  type JWSHeaderParameters,
  type FlattenedJWSInput,
  type FlattenedVerifyGetKey,
} from 'jose';
import type { AgentCard, AgentCardSignature } from './types.js';
import { canonicalize } from './jcs.js';
import { AgentCardVerificationError } from './errors.js';

/** A JSON Web Key Set document. */
export interface JsonWebKeySet {
  keys: JWK[];
}

/**
 * A key resolver compatible with jose's flattened verify: given a JWS protected
 * header and the flattened JWS, returns the key to verify with. Both
 * `createLocalJWKSet` and `createRemoteJWKSet` produce one of these.
 */
export type KeyResolver = FlattenedVerifyGetKey;

export interface VerifyAgentCardOptions {
  /**
   * Where to get verification keys. One of:
   *  - a JWKS document `{ keys: [...] }` (verified locally), or
   *  - a JWKS URL string (fetched via `createRemoteJWKSet`), or
   *  - a ready-made jose key resolver.
   */
  jwks?: JsonWebKeySet | string | KeyResolver;
  /** Restrict accepted signature algorithms. Defaults to `['ES256']`. */
  algorithms?: string[];
  /**
   * If true (default), a card carrying no `signatures` array throws. Set false
   * to allow unsigned cards to pass verification as "no signatures present".
   */
  requireSignature?: boolean;
  /**
   * Custom fetch used only when `jwks` is a URL string. Lets callers (and the
   * `OabpClient`) route remote JWKS fetches through the same fetch as the rest
   * of the SDK (injected impl, proxy, etc.). Native `fetch` by default.
   */
  customFetch?: (input: string, init?: unknown) => Promise<unknown>;
}

export interface VerifiedAgentCard {
  card: AgentCard;
  /** True when at least one signature verified against the key set. */
  verified: boolean;
  /** Protected headers of the signatures that verified. */
  verifiedHeaders: JWSHeaderParameters[];
}

/**
 * Build a jose key resolver from a JWKS document, a JWKS URL, or pass through
 * an existing resolver.
 */
export function toKeyResolver(
  jwks: JsonWebKeySet | string | KeyResolver,
  fetchImpl?: (input: string, init?: unknown) => Promise<unknown>,
): KeyResolver {
  if (typeof jwks === 'function') return jwks;
  if (typeof jwks === 'string') {
    // jose's fetch typing rarely matches lib.dom's fetch; the `[customFetch]`
    // Symbol key is jose's sanctioned escape hatch for a custom fetch impl.
    const opts = fetchImpl
      ? ({ [customFetch]: fetchImpl } as unknown as undefined)
      : undefined;
    return createRemoteJWKSet(new URL(jwks), opts) as unknown as KeyResolver;
  }
  return createLocalJWKSet(jwks) as unknown as KeyResolver;
}

/**
 * Default JWKS URL for a card: `/.well-known/jwks.json` on the card's origin.
 */
export function defaultJwksUrl(card: AgentCard): string {
  const origin = new URL(card.url).origin;
  return `${origin}/.well-known/jwks.json`;
}

/**
 * Verify the detached JWS signature(s) on an A2A agent card.
 *
 * The signing input follows the A2A card-signature convention (detached JWS,
 * RFC 7515): `BASE64URL(protected) + '.' + BASE64URL(JCS(card\{signatures}))`.
 * The card is canonicalized (RFC 8785) with its `signatures` field removed,
 * exactly as the signer produced it.
 */
export async function verifyAgentCard(
  card: AgentCard,
  options: VerifyAgentCardOptions = {},
): Promise<VerifiedAgentCard> {
  const algorithms = options.algorithms ?? ['ES256'];
  const requireSignature = options.requireSignature ?? true;

  const signatures = card.signatures ?? [];
  if (signatures.length === 0) {
    if (requireSignature) {
      throw new AgentCardVerificationError(
        'Agent card has no signatures to verify',
      );
    }
    return { card, verified: false, verifiedHeaders: [] };
  }

  const resolver = options.jwks
    ? toKeyResolver(options.jwks, options.customFetch)
    : toKeyResolver(defaultJwksUrl(card), options.customFetch);

  // Canonical payload = the card without its signatures, JCS-encoded.
  const payloadBytes = canonicalPayloadBytes(card);
  const payloadB64 = base64url.encode(payloadBytes);

  const verifiedHeaders: JWSHeaderParameters[] = [];
  const failures: string[] = [];

  for (const sig of signatures) {
    try {
      // Surface a clear error if the protected header is malformed before
      // handing the JWS to jose.
      decodeProtectedHeader({ protected: sig.protected });
    } catch (cause) {
      failures.push(`malformed protected header: ${describe(cause)}`);
      continue;
    }

    const flattened = toFlattenedDetached(sig, payloadB64);
    try {
      const result = await flattenedVerify(flattened, resolver, {
        algorithms,
      });
      // A verified detached JWS always carries a protected header.
      if (result.protectedHeader !== undefined) {
        verifiedHeaders.push(result.protectedHeader);
      }
    } catch (cause) {
      failures.push(describe(cause));
    }
  }

  if (verifiedHeaders.length === 0) {
    throw new AgentCardVerificationError(
      `No agent-card signature verified (${signatures.length} tried): ` +
        failures.join('; '),
      { cause: failures },
    );
  }

  return { card, verified: true, verifiedHeaders };
}

/** Canonical bytes signed for an agent card (card minus `signatures`). */
export function canonicalPayloadBytes(card: AgentCard): Uint8Array {
  const { signatures: _omit, ...rest } = card;
  return new TextEncoder().encode(canonicalize(rest));
}

/** Assemble a detached flattened JWS jose can verify. */
function toFlattenedDetached(
  sig: AgentCardSignature,
  payloadB64: string,
): FlattenedJWSInput {
  const input: FlattenedJWSInput = {
    payload: payloadB64,
    protected: sig.protected,
    signature: sig.signature,
  };
  if (sig.header !== undefined) input.header = sig.header;
  return input;
}

function describe(err: unknown): string {
  if (err instanceof Error) return `${err.name}: ${err.message}`;
  return String(err);
}
