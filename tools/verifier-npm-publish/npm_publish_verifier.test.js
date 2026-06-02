// SPDX-License-Identifier: MIT
'use strict';

/**
 * Offline test suite for the OABP/AIGEN npm-publish oracle verifier.
 *
 * Run with:  node --test          (Node >= 18, built-in test runner)
 *
 * Every test injects a fetch-shaped stub via `opts.fetch`, so NOTHING here touches
 * the network. The stub serves canned packuments keyed by registry URL and asserts
 * both the accept branch and each reject branch (missing version / no dist.tarball /
 * pre-creation publish), plus the pure helpers (proof parsing, semver, scope).
 */

const test = require('node:test');
const assert = require('node:assert/strict');

const {
  verify,
  parseProof,
  extractProof,
  compareSemver,
  parseSemver,
  comparePrerelease,
  normalizeScope,
  scopeOf,
  encodeRegistryPath,
  toUnixSeconds,
  parseParams,
  missionCreatedAt,
  NpmRegistryClient,
  DEFAULT_REGISTRY_BASE,
} = require('./npm_publish_verifier.js');

// --------------------------------------------------------------------------- //
// Fetch stub: maps a registry path-suffix -> { status, body }. Longest suffix
// wins, mirroring how the real client builds `${base}/${encodeRegistryPath(name)}`.
// --------------------------------------------------------------------------- //
function makeFetchStub(routes) {
  const calls = [];
  async function fetchStub(url, _init) {
    calls.push(url);
    let best = null;
    for (const suffix of Object.keys(routes)) {
      if (url.endsWith(suffix) && (best === null || suffix.length > best.length)) {
        best = suffix;
      }
    }
    if (best === null) {
      return { status: 404, async text() { return '{}'; } };
    }
    const route = routes[best];
    const bodyText =
      typeof route.body === 'string' ? route.body : JSON.stringify(route.body);
    return { status: route.status, async text() { return bodyText; } };
  }
  fetchStub.calls = calls;
  return fetchStub;
}

// Mission created 2024-06-02T00:00:00Z.
const CREATED_UNIX = Math.floor(Date.parse('2024-06-02T00:00:00Z') / 1000);

// A packument for @oabp/sdk: 0.3.0 published BEFORE creation, 0.3.1 AFTER, and a
// fileless 0.4.0 (registered manifest with an empty dist => no tarball).
const OABP_PACKUMENT = {
  name: '@oabp/sdk',
  'dist-tags': { latest: '0.3.1' },
  versions: {
    '0.3.0': {
      name: '@oabp/sdk',
      version: '0.3.0',
      dist: {
        tarball: 'https://registry.npmjs.org/@oabp/sdk/-/sdk-0.3.0.tgz',
        shasum: 'aaaa',
        integrity: 'sha512-AAAA',
      },
    },
    '0.3.1': {
      name: '@oabp/sdk',
      version: '0.3.1',
      dist: {
        tarball: 'https://registry.npmjs.org/@oabp/sdk/-/sdk-0.3.1.tgz',
        shasum: 'bbbb',
        integrity: 'sha512-BBBB',
      },
    },
    '0.4.0': {
      name: '@oabp/sdk',
      version: '0.4.0',
      dist: {}, // registered but no tarball -> nothing installable
    },
  },
  time: {
    created: '2024-05-01T10:00:00Z',
    modified: '2024-06-02T09:15:00Z',
    '0.3.0': '2024-05-01T10:00:00Z', // BEFORE the mission
    '0.3.1': '2024-06-02T09:15:00Z', // AFTER the mission
    '0.4.0': '2024-06-02T10:00:00Z',
  },
};

// The encoded registry path for @oabp/sdk is "@oabp%2fsdk".
const OABP_ROUTES = {
  '/@oabp%2fsdk': { status: 200, body: OABP_PACKUMENT },
};

function oabpMission(overrides = {}) {
  return {
    id: 'mis_npm_demo',
    title: 'Publish @oabp/sdk to npm',
    verification_type: 'oracle',
    created_at: CREATED_UNIX,
    verification_params: Object.assign(
      {
        packageName: '@oabp/sdk',
        minVersion: '0.3.0',
        requiredScope: '@oabp',
        oracle_description: "Publish '@oabp/sdk' >=0.3.0 to the npm registry.",
      },
      overrides,
    ),
  };
}

// --------------------------------------------------------------------------- //
// ACCEPT branch
// --------------------------------------------------------------------------- //
test('verify: ACCEPT existing scoped name+version+tarball published after creation', async () => {
  const fetch = makeFetchStub(OABP_ROUTES);
  const res = await verify(oabpMission(), { proof: '@oabp/sdk@0.3.1' }, { fetch });

  assert.equal(res.verified, true, res.detail);
  assert.match(res.detail, /@oabp\/sdk@0\.3\.1 published to npm/);
  assert.equal(res.evidence.verifier, 'npm_publish');
  assert.equal(res.evidence.checks.package_exists.ok, true);
  assert.equal(res.evidence.checks.version_present.ok, true);
  assert.equal(res.evidence.checks.has_tarball.ok, true);
  assert.equal(res.evidence.checks.scope_matches.ok, true);
  assert.equal(res.evidence.checks.min_version.ok, true);
  assert.equal(res.evidence.checks.fresh_after_creation.ok, true);
  assert.equal(res.evidence.checks.fresh_after_creation.enforced, true);
  // Exactly one registry GET, against the %2f-encoded scoped path.
  assert.equal(fetch.calls.length, 1);
  assert.ok(fetch.calls[0].endsWith('/@oabp%2fsdk'), fetch.calls[0]);
  // The whole result is JSON-serialisable.
  JSON.parse(JSON.stringify(res));
});

test('verify: ACCEPT an unscoped package, proof as a bare "name@version" string submission', async () => {
  const packument = {
    name: 'oabp-cli',
    'dist-tags': { latest: '1.0.0' },
    versions: {
      '1.0.0': { version: '1.0.0', dist: { tarball: 'https://registry.npmjs.org/oabp-cli/-/oabp-cli-1.0.0.tgz' } },
    },
    time: { '1.0.0': '2024-06-02T08:00:00Z' },
  };
  const fetch = makeFetchStub({ '/oabp-cli': { status: 200, body: packument } });
  const mission = {
    created_at: CREATED_UNIX,
    verification_params: { packageName: 'oabp-cli' },
  };
  const res = await verify(mission, 'oabp-cli@1.0.0', { fetch }); // bare-string submission
  assert.equal(res.verified, true, res.detail);
});

// --------------------------------------------------------------------------- //
// REJECT branches
// --------------------------------------------------------------------------- //
test('verify: REJECT a missing version', async () => {
  const fetch = makeFetchStub(OABP_ROUTES);
  const res = await verify(oabpMission(), { proof: '@oabp/sdk@9.9.9' }, { fetch });
  assert.equal(res.verified, false);
  assert.match(res.detail, /not present/);
  assert.equal(res.evidence.checks.version_present.ok, false);
  assert.deepEqual(
    res.evidence.available_versions_sample,
    ['0.3.0', '0.3.1', '0.4.0'],
  );
});

test('verify: REJECT a version with no dist.tarball (registered shell)', async () => {
  // minVersion lowered so 0.4.0 passes the version gate and we reach has_tarball.
  const fetch = makeFetchStub(OABP_ROUTES);
  const res = await verify(
    oabpMission({ minVersion: '0.1.0' }),
    { proof: '@oabp/sdk@0.4.0' },
    { fetch },
  );
  assert.equal(res.verified, false);
  assert.match(res.detail, /no dist\.tarball/);
  assert.equal(res.evidence.checks.version_present.ok, true);
  assert.equal(res.evidence.checks.has_tarball.ok, false);
});

test('verify: REJECT a pre-creation publish (release predates the mission)', async () => {
  const fetch = makeFetchStub(OABP_ROUTES);
  // 0.3.0 was published 2024-05-01, before the 2024-06-02 mission.
  const res = await verify(oabpMission(), { proof: '@oabp/sdk@0.3.0' }, { fetch });
  assert.equal(res.verified, false);
  assert.match(res.detail, /freshly published/);
  assert.equal(res.evidence.checks.fresh_after_creation.ok, false);
  assert.equal(res.evidence.checks.fresh_after_creation.enforced, true);
});

test('verify: REJECT a package absent from the registry (404)', async () => {
  const fetch = makeFetchStub({}); // every URL 404s
  const res = await verify(oabpMission(), { proof: '@oabp/sdk@0.3.1' }, { fetch });
  assert.equal(res.verified, false);
  assert.match(res.detail, /not published on the npm registry/);
  assert.equal(res.evidence.checks.package_exists.ok, false);
});

test('verify: REJECT a registry 200 body of {"error":"Not found"} as not-published', async () => {
  const fetch = makeFetchStub({
    '/@oabp%2fsdk': { status: 200, body: { error: 'Not found' } },
  });
  const res = await verify(oabpMission(), { proof: '@oabp/sdk@0.3.1' }, { fetch });
  assert.equal(res.verified, false);
  assert.match(res.detail, /not published on the npm registry/);
});

test('verify: REJECT below minVersion (short-circuits BEFORE any network call)', async () => {
  const fetch = makeFetchStub(OABP_ROUTES);
  const res = await verify(oabpMission(), { proof: '@oabp/sdk@0.2.9' }, { fetch });
  assert.equal(res.verified, false);
  assert.match(res.detail, /below the mission minimum/);
  assert.equal(res.evidence.checks.min_version.ok, false);
  assert.equal(fetch.calls.length, 0, 'must not hit the registry when minVersion already fails');
});

test('verify: REJECT a wrong package name in the proof', async () => {
  const fetch = makeFetchStub(OABP_ROUTES);
  const res = await verify(oabpMission(), { proof: 'totally-other@0.3.1' }, { fetch });
  assert.equal(res.verified, false);
  assert.equal(res.evidence.checks.name_matches.ok, false);
  assert.equal(fetch.calls.length, 0);
});

test('verify: REJECT a package outside the required scope', async () => {
  // packageName itself is unscoped here, but requiredScope demands @oabp.
  const mission = {
    created_at: CREATED_UNIX,
    verification_params: { packageName: 'evil-sdk', requiredScope: '@oabp' },
  };
  const fetch = makeFetchStub({});
  const res = await verify(mission, { proof: 'evil-sdk@1.0.0' }, { fetch });
  assert.equal(res.verified, false);
  assert.match(res.detail, /required scope/);
  assert.equal(res.evidence.checks.scope_matches.ok, false);
  assert.equal(fetch.calls.length, 0);
});

test('verify: REJECT an unparseable proof', async () => {
  const fetch = makeFetchStub(OABP_ROUTES);
  const res = await verify(oabpMission(), { proof: 'noversion' }, { fetch });
  assert.equal(res.verified, false);
  assert.match(res.detail, /invalid proof/);
  assert.equal(res.evidence.checks.proof_parsed.ok, false);
});

test('verify: REJECT invalid verification_params (no packageName)', async () => {
  const fetch = makeFetchStub(OABP_ROUTES);
  const res = await verify(
    { created_at: CREATED_UNIX, verification_params: {} },
    { proof: 'x@1.0.0' },
    { fetch },
  );
  assert.equal(res.verified, false);
  assert.match(res.detail, /invalid verification_params/);
});

// --------------------------------------------------------------------------- //
// Freshness-not-enforced + grace window
// --------------------------------------------------------------------------- //
test('verify: freshness NOT enforced when the mission has no creation time', async () => {
  const fetch = makeFetchStub(OABP_ROUTES);
  const mission = { verification_params: { packageName: '@oabp/sdk' } }; // no created_at
  const res = await verify(mission, { proof: '@oabp/sdk@0.3.0' }, { fetch }); // old upload
  assert.equal(res.verified, true, res.detail); // accepted: freshness unenforced
  assert.equal(res.evidence.checks.fresh_after_creation.enforced, false);
});

test('verify: graceSeconds widens the freshness window', async () => {
  // Publish 0.3.0 at 2024-05-01; with a huge grace it counts as "after" creation.
  const fetch = makeFetchStub(OABP_ROUTES);
  const grace = CREATED_UNIX - Math.floor(Date.parse('2024-04-30T00:00:00Z') / 1000);
  const res = await verify(
    oabpMission({ minVersion: '0.1.0', graceSeconds: grace }),
    { proof: '@oabp/sdk@0.3.0' },
    { fetch },
  );
  assert.equal(res.verified, true, res.detail);
  assert.equal(res.evidence.checks.fresh_after_creation.ok, true);
});

test('verify: a params-level created_at override is respected', async () => {
  // Override creation to 2024-06-02T12:00:00Z (AFTER the 0.3.1 publish) -> reject.
  const fetch = makeFetchStub(OABP_ROUTES);
  const override = Math.floor(Date.parse('2024-06-02T12:00:00Z') / 1000);
  const res = await verify(
    oabpMission({ created_at: override }),
    { proof: '@oabp/sdk@0.3.1' },
    { fetch },
  );
  assert.equal(res.verified, false);
  assert.match(res.detail, /freshly published/);
});

// --------------------------------------------------------------------------- //
// Submission proof variants
// --------------------------------------------------------------------------- //
test('extractProof: reads proof / proof_data / content / bare value', () => {
  assert.equal(extractProof({ proof: 'a@1' }), 'a@1');
  assert.equal(extractProof({ proof_data: 'a@1' }), 'a@1');
  assert.equal(extractProof({ content: 'a@1' }), 'a@1');
  assert.equal(extractProof('a@1'), 'a@1');
  assert.deepEqual(extractProof({ name: 'a', version: '1' }), { name: 'a', version: '1' });
  assert.equal(extractProof(null), undefined);
});

test('parseProof: scoped, unscoped, pipe, whitespace, JSON, URL, object', () => {
  assert.deepEqual(parseProof('@oabp/sdk@0.3.1'), { name: '@oabp/sdk', version: '0.3.1' });
  assert.deepEqual(parseProof('oabp-sdk@0.3.1'), { name: 'oabp-sdk', version: '0.3.1' });
  assert.deepEqual(parseProof('oabp-sdk|0.3.1'), { name: 'oabp-sdk', version: '0.3.1' });
  assert.deepEqual(parseProof('oabp-sdk 0.3.1'), { name: 'oabp-sdk', version: '0.3.1' });
  assert.deepEqual(parseProof('{"name":"@oabp/sdk","version":"0.3.1"}'), {
    name: '@oabp/sdk',
    version: '0.3.1',
  });
  assert.deepEqual(parseProof('https://www.npmjs.com/package/@oabp/sdk/v/0.3.1'), {
    name: '@oabp/sdk',
    version: '0.3.1',
  });
  assert.deepEqual(parseProof({ name: 'x', version: '2.0.0' }), { name: 'x', version: '2.0.0' });
  for (const bad of ['', 'noversion', '@only', '   ', '|0.1', 'name|']) {
    assert.throws(() => parseProof(bad), /proof/i, 'expected throw for ' + JSON.stringify(bad));
  }
});

// --------------------------------------------------------------------------- //
// Pure helpers
// --------------------------------------------------------------------------- //
test('compareSemver: numeric, prerelease, build ordering', () => {
  assert.equal(compareSemver('0.3.1', '0.3.0'), 1);
  assert.equal(compareSemver('0.3.0', '0.3.0'), 0);
  assert.equal(compareSemver('0.2.9', '0.3.0'), -1);
  assert.equal(compareSemver('1.10.0', '1.9.0'), 1); // numeric, not lexical
  assert.equal(compareSemver('1.0.0', '1.0.0-rc.1'), 1); // release > prerelease
  assert.equal(compareSemver('1.0.0-rc.1', '1.0.0'), -1);
  assert.equal(compareSemver('1.0.0-alpha', '1.0.0-alpha.1'), -1); // fewer < more
  assert.equal(compareSemver('1.0.0-alpha.1', '1.0.0-alpha.beta'), -1); // numeric < alnum
  assert.equal(compareSemver('1.0.0+build.5', '1.0.0+build.9'), 0); // build ignored
  assert.equal(compareSemver('v2.0.0', '2.0.0'), 0); // leading v tolerated
});

test('comparePrerelease: empty outranks non-empty', () => {
  assert.equal(comparePrerelease([], []), 0);
  assert.equal(comparePrerelease([], ['rc', 1]), 1);
  assert.equal(comparePrerelease(['rc', 1], []), -1);
});

test('parseSemver: strict flag', () => {
  assert.equal(parseSemver('1.2.3').strict, true);
  assert.equal(parseSemver('1.2.3-rc.1+b').strict, true);
  assert.equal(parseSemver('not-a-version').strict, false);
});

test('normalizeScope / scopeOf', () => {
  assert.equal(normalizeScope('acme'), '@acme');
  assert.equal(normalizeScope('@Acme'), '@acme');
  assert.equal(normalizeScope('@acme/pkg'), '@acme');
  assert.equal(normalizeScope(''), null);
  assert.equal(scopeOf('@acme/pkg'), '@acme');
  assert.equal(scopeOf('@ACME/pkg'), '@acme');
  assert.equal(scopeOf('pkg'), null);
});

test('encodeRegistryPath: scoped uses %2f, unscoped is a single segment', () => {
  assert.equal(encodeRegistryPath('@oabp/sdk'), '@oabp%2fsdk');
  assert.equal(encodeRegistryPath('oabp-sdk'), 'oabp-sdk');
});

test('toUnixSeconds: seconds, millis, ISO, junk', () => {
  assert.equal(toUnixSeconds(1717286400), 1717286400);
  assert.equal(toUnixSeconds(1717286400000), 1717286400); // millis -> seconds
  assert.equal(toUnixSeconds('2024-06-02T00:00:00Z'), 1717286400);
  assert.equal(toUnixSeconds('1717286400'), 1717286400);
  assert.equal(toUnixSeconds('not a date'), null);
  assert.equal(toUnixSeconds(null), null);
});

test('parseParams: aliases + defaults + required packageName', () => {
  const p = parseParams({
    verification_params: {
      package_name: '@oabp/sdk',
      min_version: '0.3.0',
      scope: 'oabp',
      grace_seconds: '30',
      registry: 'https://registry.example.com/',
    },
  });
  assert.equal(p.packageName, '@oabp/sdk');
  assert.equal(p.minVersion, '0.3.0');
  assert.equal(p.requiredScope, '@oabp');
  assert.equal(p.graceSeconds, 30);
  assert.equal(p.registryBase, 'https://registry.example.com');
  assert.throws(() => parseParams({ verification_params: {} }), /packageName is required/);
  assert.throws(() => parseParams({}), /must be an object/);
});

test('missionCreatedAt: created_at, fallbacks, override', () => {
  assert.equal(missionCreatedAt({ created_at: 1717286400 }, { createdAtOverride: null }), 1717286400);
  assert.equal(missionCreatedAt({ created: '2024-06-02T00:00:00Z' }, { createdAtOverride: null }), 1717286400);
  assert.equal(missionCreatedAt({ created_at: 1 }, { createdAtOverride: 999 }), 999); // override wins
  assert.equal(missionCreatedAt({}, { createdAtOverride: null }), null);
});

test('NpmRegistryClient: default base + injected fetch returns null on 404', async () => {
  const client = new NpmRegistryClient({ fetch: makeFetchStub({}) });
  assert.equal(client.base, DEFAULT_REGISTRY_BASE);
  assert.equal(await client.getPackument('does-not-exist'), null);
});
