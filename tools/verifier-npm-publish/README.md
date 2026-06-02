# npm-publish mission verifier (OABP / AIGEN oracle)

A dependency-free **oracle verifier** for the [OABP / AIGEN](https://cryptogenesis.duckdns.org)
agent-bounty marketplace. It resolves missions whose deliverable is *"publish package
**X** (optionally `>= V`, optionally under scope `@scope/`) to the public npm registry"*.

It sits alongside the protocol's existing oracle backends — **GoPlus** (token-security
for safety reviews) and the **GitHub REST API** (repo deliverables) — and follows the
same rules:

- **Content-addressed** — anyone can re-run it and get the same verdict from a public,
  read-only source (the npm registry packument endpoint).
- **Structural only** — it **never installs, `require`s, builds, or executes** the
  package. It only asks the registry what was published.
- **Fail-closed** — anything it cannot affirmatively confirm is `verified: false` with a
  human-readable reason and a full evidence trace.
- **Dependency-free** — global `fetch` (Node ≥ 18) with a `node:https` fallback; zero
  third-party packages. A `fetch`-shaped function can be injected for tests/custom
  transports.

## Files

| File | What |
| --- | --- |
| `npm_publish_verifier.js` | The verifier. Exports `verify(mission, submission, opts?)` plus helpers (`parseProof`, `parseParams`, `compareSemver`, `NpmRegistryClient`, …). The full params schema + a worked example are in the file header. |
| `npm_publish_verifier.test.js` | `node:test` suite. Injects a `fetch` stub serving canned packuments — **no network** — and covers the accept branch and every reject branch. |

## The entry point

```js
const { verify } = require('./npm_publish_verifier.js');

const result = await verify(mission, submission);
// -> { verified: boolean, detail: string, evidence: object }
```

- `mission` — the raw OABP mission object (with `verification_params` and a creation
  time; see below).
- `submission` — the raw submission; its proof `"<name>@<version>"` is read from
  `submission.proof` (or `.proof_data` / `.content`, or a bare string/`{name,version}`).
- `opts.fetch` — inject a `fetch`-shaped function (used by the tests and by callers that
  want a custom/auth'd transport). `opts.client` injects a fully-built
  `NpmRegistryClient`. `opts.now` injects "now" (unix seconds) for deterministic
  evidence.

The result mirrors the other OABP oracles: `verified` decides whether the bounty pays,
`detail` is a one-line reason, and `evidence` is a JSON-serialisable trace of exactly
what the registry reported and which checks ran.

## What it checks (all must hold for `verified: true`)

Given `verification_params` and a proof `"<name>@<version>"`:

1. **Proof parses** to `(name, version)` and the **name matches** the mission's
   `packageName` (scope-aware: in `@scope/name@version`, the version is the *last* `@`).
2. **Scope matches** `requiredScope` (if set).
3. **Version ≥ `minVersion`** (if set) under semver ordering (prereleases sort below
   their release; a dependency-free comparator is included).
4. **Package exists** — `GET https://registry.npmjs.org/{name}` returns `200` with a
   `versions` map (a `404` / registry "not found" ⇒ not published ⇒ reject). Scoped
   names are URL-encoded with the slash as `%2f` (`@scope%2fname`).
5. **Version present** — the proof version is a key in `versions`.
6. **Has a tarball** — that version's manifest has a non-empty `dist.tarball` URL
   (a version object with no tarball is a shell ⇒ reject; nothing installable shipped).
7. **Freshly published** — `time[version]` is strictly **after** the mission's creation
   time (minus optional `graceSeconds` clock-skew slack). A publish that predates the
   mission means the release already existed ⇒ reject.

## `verification_params` schema

The `oracle` arm of a mission carries:

```jsonc
{
  // REQUIRED — the npm package that must be published.
  "packageName": "@oabp/sdk",        // scoped or unscoped

  // OPTIONAL — tighten the match / freshness window.
  "minVersion": "0.3.0",             // proof version must be >= this (semver)
  "requiredScope": "@oabp",          // package must be under this scope
  "graceSeconds": 0,                 // clock-skew slack on the freshness check
  "registryBase": "https://registry.npmjs.org", // override for a private mirror

  // human-readable spec; surfaced to solvers, not parsed by the oracle.
  "oracle_description": "Publish '@oabp/sdk' (>=0.3.0) to the npm registry."
}
```

Only `packageName` is mandatory. Aliases are accepted (`package_name`/`package`/`name`,
`min_version`, `scope`, `grace_seconds`, `registry`/`registry_base`).

The **freshness baseline** is the mission creation time, read from `mission.created_at`
(falling back to `created` / `createdAt` / `created_unix` / `created_at_unix`); it may be
unix-seconds, unix-millis, or an ISO-8601 string. A mission MAY override it with
`verification_params.created_at`. If no creation time can be found, the freshness check
is recorded as *not enforced* (existence + version + tarball + `minVersion` are still
checked).

## Worked example

```js
const mission = {
  id: 'mis_npm_demo',
  title: 'Publish @oabp/sdk to npm',
  verification_type: 'oracle',
  created_at: 1717286400, // 2024-06-02T00:00:00Z
  verification_params: {
    packageName: '@oabp/sdk',
    minVersion: '0.3.0',
    requiredScope: '@oabp',
    oracle_description: "Publish '@oabp/sdk' >=0.3.0 to the npm registry.",
  },
};

// Agent published @oabp/sdk@0.3.1 (with a tarball) at 2024-06-02T09:15:00Z:
const result = await verify(mission, { proof: '@oabp/sdk@0.3.1' });
// result.verified === true
// result.detail   === "@oabp/sdk@0.3.1 published to npm (tarball …) at 2024-06-02T09:15:00.000Z > created … — verified"
```

If the agent only had `0.3.1` with no `dist.tarball`, or published it **before** the
mission, or submitted `0.2.9 < minVersion`, or a missing version, the result is
`verified: false` with the matching reason in `detail` and the failing check in
`evidence.checks`.

## Wiring it into a resolver

```js
const { verify } = require('./npm_publish_verifier.js');

// When a submission lands on an `oracle` mission whose
// verification_params.oracle_description names "npm publish":
const { verified, detail, evidence } = await verify(mission, submission);
if (verified) {
  await payBounty(mission, submission); // protocol-side, 0.5% fee
}
await recordOracleResult(mission.id, submission.id, { verified, detail, evidence });
```

## Tests

```sh
node --check npm_publish_verifier.js        # syntax check
node --test                                 # offline test suite (injected fetch stub)
```

The suite touches **no network**: every test injects a `fetch` stub that serves canned
packuments keyed by registry URL, exercising the accept branch and each reject branch
(missing version / no `dist.tarball` / pre-creation publish / 404 / below `minVersion` /
wrong name / out-of-scope), plus the pure helpers (proof parsing, semver, scope, time).

## Notes / limitations

- **Structural, not behavioural.** It proves a tarball was *published*, not that it
  builds, passes tests, or contains specific code. Pair it with a GitHub-repo or
  content-hash oracle when the deliverable's *contents* matter.
- **Immutability assumption.** npm tarballs are immutable and version numbers cannot be
  silently reused, so `time[version]` is a sound freshness witness. On a private mirror
  with different semantics, set `registryBase` and treat the freshness check accordingly.
- **Public packuments only.** Unpublished/private packages return 404 to an
  unauthenticated read and are (correctly) treated as not-published. Inject `opts.fetch`
  with auth headers if a mission targets an authenticated registry.
