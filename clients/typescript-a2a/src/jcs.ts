/**
 * JSON Canonicalization Scheme (RFC 8785) — minimal, dependency-free.
 *
 * The A2A agent-card signature is computed over the canonical JSON form of the
 * card with its `signatures` field removed, so signer and verifier must agree
 * byte-for-byte. RFC 8785 fixes that: keys sorted by UTF-16 code unit, no
 * insignificant whitespace, and ECMAScript `JSON.stringify` number formatting
 * (which Node/V8 already implement per the spec's referenced algorithm).
 */
export function canonicalize(value: unknown): string {
  return serialize(value);
}

function serialize(value: unknown): string {
  if (value === null) return 'null';

  const t = typeof value;
  if (t === 'number') {
    if (!Number.isFinite(value as number)) {
      throw new Error('Cannot canonicalize a non-finite number');
    }
    // V8's JSON number serialization follows the ECMAScript Number::toString
    // algorithm that RFC 8785 mandates.
    return JSON.stringify(value);
  }
  if (t === 'boolean') return value ? 'true' : 'false';
  if (t === 'string') return JSON.stringify(value);
  if (t === 'bigint') {
    throw new Error('Cannot canonicalize a bigint');
  }

  if (Array.isArray(value)) {
    const items = value.map((v) => serialize(v === undefined ? null : v));
    return `[${items.join(',')}]`;
  }

  if (t === 'object') {
    const obj = value as Record<string, unknown>;
    const keys = Object.keys(obj)
      .filter((k) => obj[k] !== undefined)
      .sort(compareCodeUnits);
    const parts = keys.map(
      (k) => `${JSON.stringify(k)}:${serialize(obj[k])}`,
    );
    return `{${parts.join(',')}}`;
  }

  throw new Error(`Cannot canonicalize value of type ${t}`);
}

/** Compare two strings by UTF-16 code unit, as RFC 8785 requires. */
function compareCodeUnits(a: string, b: string): number {
  const len = Math.min(a.length, b.length);
  for (let i = 0; i < len; i++) {
    const d = a.charCodeAt(i) - b.charCodeAt(i);
    if (d !== 0) return d;
  }
  return a.length - b.length;
}
