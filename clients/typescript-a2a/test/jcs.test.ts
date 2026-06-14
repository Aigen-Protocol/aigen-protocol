import { describe, it, expect } from 'vitest';
import { canonicalize } from '../src/jcs.js';

describe('canonicalize (RFC 8785 JSON Canonicalization Scheme)', () => {
  it('sorts object keys by UTF-16 code unit', () => {
    expect(canonicalize({ b: 1, a: 2, c: 3 })).toBe('{"a":2,"b":1,"c":3}');
  });

  it('emits no insignificant whitespace', () => {
    expect(canonicalize({ x: [1, 2, { y: 3 }] })).toBe('{"x":[1,2,{"y":3}]}');
  });

  it('preserves array order', () => {
    expect(canonicalize([3, 1, 2])).toBe('[3,1,2]');
  });

  it('drops undefined object members and nulls array holes', () => {
    expect(canonicalize({ a: undefined, b: 1 })).toBe('{"b":1}');
    expect(canonicalize([1, undefined, 2])).toBe('[1,null,2]');
  });

  it('handles the literals null / true / false', () => {
    expect(canonicalize(null)).toBe('null');
    expect(canonicalize({ t: true, f: false, n: null })).toBe(
      '{"f":false,"n":null,"t":true}',
    );
  });

  it('serializes integers and reals per ECMAScript number rules', () => {
    expect(canonicalize(1)).toBe('1');
    expect(canonicalize(1.5)).toBe('1.5');
    expect(canonicalize(-0)).toBe('0');
    expect(canonicalize(1e21)).toBe('1e+21');
  });

  it('escapes strings the same way JSON.stringify does', () => {
    expect(canonicalize('a"b\\c/d')).toBe('"a\\"b\\\\c/d"');
    expect(canonicalize('tab\tnewline\n')).toBe('"tab\\tnewline\\n"');
  });

  it('orders keys correctly for a nested object', () => {
    const input = {
      numbers: [333333333.33333329, 1e30, 4.5, 2e-3, 1e-27],
      string: 'a"b\\c/d',
      literals: [null, true, false],
    };
    const out = canonicalize(input);
    // Keys sorted: literals < numbers < string
    expect(out.indexOf('"literals"')).toBeLessThan(out.indexOf('"numbers"'));
    expect(out.indexOf('"numbers"')).toBeLessThan(out.indexOf('"string"'));
    expect(out).toContain('[null,true,false]');
  });

  it('throws on non-finite numbers and bigints', () => {
    expect(() => canonicalize(Number.NaN)).toThrow();
    expect(() => canonicalize(Number.POSITIVE_INFINITY)).toThrow();
    expect(() => canonicalize({ big: 1n })).toThrow();
  });

  it('is stable regardless of insertion order', () => {
    const a = canonicalize({ url: 'u', name: 'n', version: 'v' });
    const b = canonicalize({ version: 'v', name: 'n', url: 'u' });
    expect(a).toBe(b);
  });
});
