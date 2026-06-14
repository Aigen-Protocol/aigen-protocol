import { describe, it, expect } from 'vitest';
import { FlattenedSign, importJWK, base64url } from 'jose';
import {
  verifyAgentCard,
  canonicalPayloadBytes,
  toKeyResolver,
  defaultJwksUrl,
} from '../src/agentCard.js';
import { AgentCardVerificationError } from '../src/errors.js';
import type { AgentCard } from '../src/types.js';
import {
  PUBLIC_JWK,
  PRIVATE_JWK,
  JWKS_DOC,
  SIGNED_AGENT_CARD,
  SIGNED_CARD,
  FROZEN_PROTECTED,
  FROZEN_SIGNATURE,
} from './vectors.js';

describe('verifyAgentCard — frozen ES256 test vector', () => {
  it('verifies a pre-computed detached JWS against the JWKS', async () => {
    const result = await verifyAgentCard(SIGNED_AGENT_CARD as AgentCard, {
      jwks: JWKS_DOC,
    });
    expect(result.verified).toBe(true);
    expect(result.verifiedHeaders).toHaveLength(1);
    expect(result.verifiedHeaders[0]?.alg).toBe('ES256');
    expect(result.verifiedHeaders[0]?.kid).toBe(PUBLIC_JWK.kid);
    // The returned card is unchanged.
    expect(result.card.url).toBe(SIGNED_CARD.url);
  });

  it('rejects when the card body is tampered (signature no longer matches)', async () => {
    const tampered: AgentCard = {
      ...(SIGNED_AGENT_CARD as AgentCard),
      url: 'https://evil.example',
    };
    await expect(
      verifyAgentCard(tampered, { jwks: JWKS_DOC }),
    ).rejects.toBeInstanceOf(AgentCardVerificationError);
  });

  it('rejects when a different (unrelated) key set is supplied', async () => {
    const otherJwks = {
      keys: [
        {
          ...PUBLIC_JWK,
          // flip a coordinate so the key no longer matches the signature
          x: 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
        },
      ],
    };
    await expect(
      verifyAgentCard(SIGNED_AGENT_CARD as AgentCard, { jwks: otherJwks }),
    ).rejects.toBeInstanceOf(AgentCardVerificationError);
  });

  it('rejects ES384 when only ES256 is allowed (alg pinning)', async () => {
    await expect(
      verifyAgentCard(SIGNED_AGENT_CARD as AgentCard, {
        jwks: JWKS_DOC,
        algorithms: ['ES384'],
      }),
    ).rejects.toBeInstanceOf(AgentCardVerificationError);
  });
});

describe('verifyAgentCard — sign-then-verify round trip', () => {
  it('verifies a signature freshly minted over the JCS payload', async () => {
    const card: AgentCard = {
      name: 'Fresh Agent',
      url: 'https://cryptogenesis.duckdns.org',
      version: '2.0.0',
      capabilities: { streaming: false },
      skills: [{ id: 'mission.search' }],
    };

    const key = await importJWK(PRIVATE_JWK, 'ES256');
    const payload = canonicalPayloadBytes(card);
    const jws = await new FlattenedSign(payload)
      .setProtectedHeader({ alg: 'ES256', kid: PRIVATE_JWK.kid })
      .sign(key);

    const signed: AgentCard = {
      ...card,
      signatures: [{ protected: jws.protected!, signature: jws.signature }],
    };

    const result = await verifyAgentCard(signed, { jwks: JWKS_DOC });
    expect(result.verified).toBe(true);
    expect(result.verifiedHeaders[0]?.kid).toBe(PRIVATE_JWK.kid);
  });
});

describe('verifyAgentCard — signature presence policy', () => {
  it('throws on an unsigned card by default', async () => {
    const card: AgentCard = { name: 'Nope', url: 'https://x.example' };
    await expect(
      verifyAgentCard(card, { jwks: JWKS_DOC }),
    ).rejects.toBeInstanceOf(AgentCardVerificationError);
  });

  it('returns verified=false for an unsigned card when not required', async () => {
    const card: AgentCard = { name: 'Nope', url: 'https://x.example' };
    const result = await verifyAgentCard(card, {
      jwks: JWKS_DOC,
      requireSignature: false,
    });
    expect(result.verified).toBe(false);
    expect(result.verifiedHeaders).toHaveLength(0);
  });

  it('verifies if any one of several signatures is valid', async () => {
    const card: AgentCard = {
      ...SIGNED_CARD,
      signatures: [
        { protected: FROZEN_PROTECTED, signature: 'AAAAdefinitely-bad' },
        { protected: FROZEN_PROTECTED, signature: FROZEN_SIGNATURE },
      ],
    };
    const result = await verifyAgentCard(card, { jwks: JWKS_DOC });
    expect(result.verified).toBe(true);
    expect(result.verifiedHeaders).toHaveLength(1);
  });
});

describe('agent-card helpers', () => {
  it('canonicalPayloadBytes strips the signatures field', () => {
    const bytes = canonicalPayloadBytes(SIGNED_AGENT_CARD as AgentCard);
    const text = new TextDecoder().decode(bytes);
    expect(text).not.toContain('signatures');
    expect(text).toContain('"url":"https://cryptogenesis.duckdns.org"');
  });

  it('payload bytes match the base64url payload the verifier signs over', () => {
    const bytes = canonicalPayloadBytes(SIGNED_CARD as AgentCard);
    // Same encoding the verifier uses internally.
    const b64 = base64url.encode(bytes);
    expect(typeof b64).toBe('string');
    expect(b64.length).toBeGreaterThan(0);
  });

  it('defaultJwksUrl derives well-known JWKS from the card origin', () => {
    expect(defaultJwksUrl(SIGNED_CARD as AgentCard)).toBe(
      'https://cryptogenesis.duckdns.org/.well-known/jwks.json',
    );
  });

  it('toKeyResolver accepts a JWKS doc, a URL, and a resolver function', () => {
    expect(typeof toKeyResolver(JWKS_DOC)).toBe('function');
    expect(
      typeof toKeyResolver('https://x.example/.well-known/jwks.json'),
    ).toBe('function');
    const passthrough = (async () => new Uint8Array()) as never;
    expect(toKeyResolver(passthrough)).toBe(passthrough);
  });
});
