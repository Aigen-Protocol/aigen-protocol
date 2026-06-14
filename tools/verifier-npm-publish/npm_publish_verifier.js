// SPDX-License-Identifier: MIT
'use strict';

/**
 * OABP / AIGEN oracle mission verifier: *agent published a package to the npm registry*.
 *
 * What this is
 * ============
 * A new **oracle** mission-type verifier for the OABP / AIGEN agent-bounty
 * marketplace at https://cryptogenesis.duckdns.org. It resolves missions whose
 * deliverable is "publish package **X** (optionally at version **>= V**, optionally
 * under scope **@scope/**) to the public npm registry".
 *
 * The protocol already ships oracle backends for **GoPlus** (token-security for
 * safety-review missions) and the **GitHub REST API** (repo deliverables). This
 * module adds a sibling in the same spirit: it is **content-addressed** (anyone can
 * re-run it and get the same verdict from a public read-only source), **structural
 * only** (it NEVER installs, requires, builds, or executes the package — it asks the
 * npm registry what was published), and **fail-closed** (anything it cannot
 * affirmatively confirm is `verified:false` with a human-readable reason).
 *
 * It is **dependency-free**: it uses the global `fetch` (Node >= 18) and falls back
 * to the built-in `node:https` module, so it runs in a resolver with zero
 * third-party packages installed. A `fetch`-shaped function can be injected for
 * tests (and for the bundled `node:test` suite) so the verdict logic is exercised
 * with **no network**.
 *
 * Why an npm-registry oracle is sound
 * -----------------------------------
 * The npm registry's read-only "packument" endpoint is a public, re-runnable,
 * content-addressed witness of what an agent actually shipped:
 *
 *   GET https://registry.npmjs.org/{name}
 *
 * returns a JSON document with (the fields this verifier reads):
 *   - `name`             — the package name.
 *   - `dist-tags`        — e.g. `{ latest: "1.2.3" }`.
 *   - `versions`         — map `version -> manifest`. Each manifest carries
 *                          `dist.tarball` (the immutable tarball URL),
 *                          `dist.shasum` and usually `dist.integrity`.
 *   - `time`             — map `version -> ISO-8601 publish timestamp`, plus the
 *                          special keys `created` and `modified` for the package.
 *
 * For a SCOPED package `@scope/name`, the path segment is URL-encoded with the
 * slash as `%2f`: `GET https://registry.npmjs.org/@scope%2fname`.
 *
 * Crucially, `time[version]` records *when that exact version was published*. That
 * lets the oracle prove the version was published **after the mission was created**
 * — i.e. the package was *freshly published for this bounty*, not an already-existing
 * release the submitter merely pointed at. npm also forbids re-publishing an
 * unpublished version's number (the 24h-then-permanent rule) and tarballs are
 * immutable, so a version cannot be silently back-dated.
 *
 * What the verifier checks (all must hold for `verified:true`)
 * ------------------------------------------------------------
 * Given a mission's `verification_params` (see schema below) and a submission whose
 * `proof` is `"<name>@<version>"`:
 *
 *   1. PROOF PARSES   — the proof names an npm package and a concrete version, and
 *                       the package name matches the one the mission asked for. A
 *                       scoped `@scope/name@version` is parsed correctly (the FIRST
 *                       `@` belongs to the scope; the version `@` is the last one).
 *   2. SCOPE MATCHES  — if `requiredScope` is set, the package must live under it
 *                       (`@acme` or `acme`, with or without a leading `@`).
 *   3. MIN VERSION    — if `minVersion` is set, the proof version must be `>=` it
 *                       under semver ordering (a small, dependency-free comparator
 *                       is included; pre-release tags sort below their release).
 *   4. PACKAGE EXISTS — `GET /{name}` returns HTTP 200 with a `versions` map. A 404
 *                       (or registry "not found" body) ⇒ not published ⇒ reject.
 *   5. VERSION PRESENT— the proof's version is a key in `versions`.
 *   6. HAS A TARBALL  — that version's manifest has a non-empty `dist.tarball` URL.
 *                       A version object with no tarball is a shell and is rejected:
 *                       nothing installable was actually shipped.
 *   7. FRESH PUBLISH  — `time[version]` parses to a timestamp strictly **after** the
 *                       mission's creation time (minus an optional `graceSeconds`
 *                       clock-skew slack). A publish that predates the mission means
 *                       the release already existed ⇒ reject.
 *
 * Any check that does not affirmatively pass yields `verified:false` and a `detail`
 * saying which one and why. The full structured trace is returned in `evidence` so a
 * creator/auditor can see exactly what the registry reported.
 *
 * The proof format
 * ----------------
 * `proof = "<name>@<version>"` — e.g. `"@oabp/sdk@0.3.1"` or `"oabp-sdk@0.3.1"`.
 * For ergonomics the verifier also accepts a structured proof object
 * `{ name, version }` (or `{ package, version }`), a `"name|version"` pipe form, a
 * `"name version"` whitespace form, and a bare npm URL
 * `https://www.npmjs.com/package/<name>/v/<version>`. All normalise to the same
 * `(name, version)` pair. The submission may carry the proof as `submission.proof`,
 * `submission.proof_data`, or `submission.content`; a bare string submission is also
 * treated as the proof.
 *
 * verification_params schema
 * ==========================
 * The mission's `verification_params` object (the `oracle` arm of the protocol) for
 * this mission-type is:
 *
 *   {
 *     // REQUIRED — the npm package that must be published.
 *     "packageName": "@oabp/sdk",        // string; scoped or unscoped
 *
 *     // OPTIONAL — tighten the match / freshness window.
 *     "minVersion": "0.3.0",             // string|null; proof version must be >= this (semver)
 *     "requiredScope": "@oabp",          // string|null; package must be under this scope
 *     "graceSeconds": 0,                 // int; clock-skew slack subtracted from the
 *                                        //      mission creation time for the freshness check
 *     "registryBase": "https://registry.npmjs.org", // string; override for a private mirror
 *
 *     // human-readable spec; surfaced to solvers, not parsed by the oracle.
 *     "oracle_description":
 *       "Publish '@oabp/sdk' (>=0.3.0) to the npm registry."
 *   }
 *
 * Only `packageName` is mandatory. `oracle_description` is free text for
 * humans/solvers; the machine truth is the typed fields above. (Aliases are also
 * accepted: `package_name`/`package`/`name`, `min_version`, `scope`,
 * `grace_seconds`, `registry`/`registry_base`.)
 *
 * The freshness baseline (mission creation time) is read from the MISSION object —
 * `mission.created_at` (falling back to `created`, `created_unix`, `createdAt`,
 * `created_at_unix`). It may be a unix-seconds number, a unix-millis number, or an
 * ISO-8601 string. If no creation time can be determined, the freshness check is
 * recorded as "not enforced" (the verifier still checks existence + version +
 * tarball + minVersion). A mission MAY also override it via
 * `verification_params.created_at`.
 *
 * Worked example
 * ==============
 * Mission (created at unix 1717286400 = 2024-06-02T00:00:00Z):
 *
 *   const mission = {
 *     id: "mis_npm_demo",
 *     title: "Publish @oabp/sdk to npm",
 *     verification_type: "oracle",
 *     created_at: 1717286400,
 *     verification_params: {
 *       packageName: "@oabp/sdk",
 *       minVersion: "0.3.0",
 *       requiredScope: "@oabp",
 *       oracle_description: "Publish '@oabp/sdk' >=0.3.0 to the npm registry.",
 *     },
 *   };
 *
 * An agent publishes `@oabp/sdk@0.3.1` (with a tarball) at 2024-06-02T09:15:00Z and
 * submits `proof = "@oabp/sdk@0.3.1"`. The verifier:
 *
 *   - parses the proof -> ("@oabp/sdk", "0.3.1"); name + scope match; ok
 *   - 0.3.1 >= 0.3.0 under semver; ok
 *   - GET /@oabp%2fsdk -> 200; versions has "0.3.1"; ok
 *   - versions["0.3.1"].dist.tarball is a non-empty URL; ok
 *   - time["0.3.1"] = 2024-06-02T09:15:00Z > created 2024-06-02T00:00:00Z -> fresh; ok
 *
 * => { verified:true, detail:"@oabp/sdk@0.3.1 published to npm ...", evidence:{...} }.
 * Had the agent only had `0.3.1` with no `dist.tarball`, or published it BEFORE the
 * mission, or submitted `0.2.9 < minVersion`, or a missing version, the result would
 * be `verified:false` with the corresponding reason.
 *
 * Exports
 * -------
 *   - `verify(mission, submission, opts?) : Promise<{verified, detail, evidence}>`
 *       — the protocol entry point. `opts.fetch` injects a fetch-shaped function;
 *         `opts.now` injects "now" (unix seconds) for deterministic evidence.
 *   - `parseParams(mission)`            — typed view of `verification_params`.
 *   - `parseProof(proof)`               — `{name, version}` from a proof.
 *   - `extractProof(submission)`        — pull the raw proof out of a submission.
 *   - `parseSemver` / `compareSemver`   — dependency-free semver compare.
 *   - `NpmRegistryClient`               — read-only packument client (injectable fetch).
 *   - `DEFAULT_REGISTRY_BASE`
 *
 * @module npm_publish_verifier
 */

const https = require('node:https');
const http = require('node:http');
const { URL } = require('node:url');

const DEFAULT_REGISTRY_BASE = 'https://registry.npmjs.org';
const HTTP_TIMEOUT_MS = 20000;
const USER_AGENT =
  'oabp-npm-publish-verifier/1.0 (+https://cryptogenesis.duckdns.org)';

// --------------------------------------------------------------------------- //
// Time parsing
// --------------------------------------------------------------------------- //

/**
 * Coerce a unix-seconds number, unix-millis number, or ISO-8601 string into unix
 * SECONDS. Returns `null` if it cannot be parsed.
 *
 * Heuristic for bare numbers: values with absolute magnitude >= 1e12 are treated
 * as milliseconds (year ~2001+ in ms), otherwise as seconds.
 *
 * @param {*} value
 * @returns {number|null}
 */
function toUnixSeconds(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number' && Number.isFinite(value)) {
    return Math.abs(value) >= 1e12 ? Math.floor(value / 1000) : Math.floor(value);
  }
  if (typeof value === 'string') {
    const s = value.trim();
    if (s === '') return null;
    // All-digit string -> numeric epoch.
    if (/^-?\d+$/.test(s)) {
      const n = Number(s);
      if (Number.isFinite(n)) {
        return Math.abs(n) >= 1e12 ? Math.floor(n / 1000) : Math.floor(n);
      }
    }
    const ms = Date.parse(s); // handles ISO-8601 incl. trailing 'Z' and offsets
    if (!Number.isNaN(ms)) return Math.floor(ms / 1000);
    return null;
  }
  return null;
}

/**
 * Unix seconds -> ISO-8601 string (or `null` if not representable). Used purely to
 * make the evidence human-readable.
 * @param {number|null} ts
 * @returns {string|null}
 */
function isoFromUnix(ts) {
  if (ts === null || ts === undefined || !Number.isFinite(ts)) return null;
  try {
    return new Date(ts * 1000).toISOString();
  } catch (_e) {
    return null;
  }
}

// --------------------------------------------------------------------------- //
// Package-name + scope helpers
// --------------------------------------------------------------------------- //

/**
 * Normalise a scope to a leading-`@`, lowercased form: `acme` -> `@acme`,
 * `@Acme` -> `@acme`. Returns `null` for an empty/invalid scope.
 * @param {*} scope
 * @returns {string|null}
 */
function normalizeScope(scope) {
  if (typeof scope !== 'string') return null;
  let s = scope.trim().toLowerCase();
  if (s === '') return null;
  if (!s.startsWith('@')) s = '@' + s;
  // strip any accidental trailing slash / name part
  const slash = s.indexOf('/');
  if (slash !== -1) s = s.slice(0, slash);
  return s.length > 1 ? s : null;
}

/**
 * The scope of a package name, lowercased with a leading `@`, or `null` if the
 * package is unscoped. `@acme/sdk` -> `@acme`; `sdk` -> `null`.
 * @param {string} name
 * @returns {string|null}
 */
function scopeOf(name) {
  if (typeof name !== 'string') return null;
  const s = name.trim();
  if (s.startsWith('@') && s.includes('/')) {
    return s.slice(0, s.indexOf('/')).toLowerCase();
  }
  return null;
}

/**
 * npm package names are compared case-sensitively by the registry, but new names
 * must be lowercase; we compare on a trimmed, lowercased form so `Foo` and `foo`
 * are treated as the same package for matching purposes.
 * @param {string} name
 * @returns {string}
 */
function canonicalName(name) {
  return (typeof name === 'string' ? name : '').trim().toLowerCase();
}

/**
 * Encode a package name for the registry path. A scoped name `@scope/pkg` becomes
 * `@scope%2fpkg` (the leading `@` is kept literal — that is exactly the form the npm
 * registry serves; only the `/` is percent-encoded, as `%2f`). An unscoped name is
 * returned percent-encoded as a single segment.
 * @param {string} name
 * @returns {string}
 */
function encodeRegistryPath(name) {
  const s = String(name).trim();
  if (s.startsWith('@') && s.includes('/')) {
    const i = s.indexOf('/');
    const scope = s.slice(1, i); // text after '@', before '/'
    const pkg = s.slice(i + 1);
    return '@' + encodeURIComponent(scope) + '%2f' + encodeURIComponent(pkg);
  }
  return encodeURIComponent(s);
}

// --------------------------------------------------------------------------- //
// Proof parsing  ("name@version", scoped, "name|version", JSON, npm URL)
// --------------------------------------------------------------------------- //

/**
 * Parse a submission proof into `{ name, version }`.
 *
 * Accepted forms (in priority order):
 *   - an object `{ name, version }` / `{ package, version }`
 *   - `"@scope/name@version"` or `"name@version"`  (canonical; scope-aware)
 *   - a JSON object string `'{"name":"...","version":"..."}'`
 *   - `"name|version"` (pipe) or `"name version"` (whitespace)
 *   - an npm URL `https://www.npmjs.com/package/<name>/v/<version>`
 *
 * Throws `Error` if no `(name, version)` pair can be extracted.
 *
 * @param {*} proof
 * @returns {{name: string, version: string}}
 */
function parseProof(proof) {
  // Already structured.
  if (proof && typeof proof === 'object' && !Array.isArray(proof)) {
    const name = proof.name || proof.package || proof.package_name || proof.packageName;
    const version = proof.version || proof.ver;
    if (typeof name === 'string' && typeof version === 'string' && name.trim() && version.trim()) {
      return { name: name.trim(), version: version.trim() };
    }
    throw new Error("proof object must carry non-empty 'name' and 'version'");
  }

  if (typeof proof !== 'string' || !proof.trim()) {
    throw new Error("proof must be a non-empty string of the form 'name@version'");
  }
  const s = proof.trim();

  // JSON object string.
  if (s.startsWith('{')) {
    let obj = null;
    try {
      obj = JSON.parse(s);
    } catch (_e) {
      obj = null;
    }
    if (obj && typeof obj === 'object') return parseProof(obj);
  }

  // npm package URL: .../package/<name>/v/<version>  (name may be scoped, with %2f or /)
  const urlMatch = s.match(
    /^(?:https?:\/\/)?(?:www\.)?npmjs\.com\/package\/(.+?)\/v\/([^/\s]+)\/?$/i,
  );
  if (urlMatch) {
    const rawName = decodeURIComponent(urlMatch[1].replace(/%2f/gi, '/')).trim();
    const version = urlMatch[2].trim();
    if (rawName && version) return { name: rawName, version };
  }

  // Pipe form: name|version
  if (s.includes('|')) {
    const i = s.indexOf('|');
    const name = s.slice(0, i).trim();
    const version = s.slice(i + 1).trim();
    if (name && version) return { name, version };
  }

  // Canonical "name@version" — scope-aware: the version separator is the LAST '@'
  // that is not the scope's leading '@'.
  const at = s.lastIndexOf('@');
  if (at > 0) {
    const name = s.slice(0, at).trim();
    const version = s.slice(at + 1).trim();
    if (name && version) return { name, version };
  }

  // Whitespace form: "name version"
  const parts = s.split(/\s+/);
  if (parts.length === 2 && parts[0] && parts[1]) {
    return { name: parts[0].trim(), version: parts[1].trim() };
  }

  throw new Error(
    "could not parse proof " + JSON.stringify(proof) +
      " into (name, version); expected 'name@version'",
  );
}

/**
 * Pull the raw proof value out of a submission object. A submission may carry it as
 * `proof`, `proof_data`, `proofData`, `content`, or `data`; a bare string/obj
 * submission is itself treated as the proof.
 * @param {*} submission
 * @returns {*}
 */
function extractProof(submission) {
  if (submission === null || submission === undefined) return undefined;
  if (typeof submission === 'string') return submission;
  if (typeof submission === 'object' && !Array.isArray(submission)) {
    for (const key of ['proof', 'proof_data', 'proofData', 'content', 'data']) {
      if (submission[key] !== undefined && submission[key] !== null) {
        return submission[key];
      }
    }
    // a {name, version} submission with no wrapper is itself the proof
    if (submission.name && submission.version) return submission;
    return undefined;
  }
  return submission;
}

// --------------------------------------------------------------------------- //
// Minimal semver parse + compare (dependency-free)
// --------------------------------------------------------------------------- //
// Implements enough of semver 2.0.0 ordering for the `minVersion` gate:
//   major.minor.patch, with an optional `-prerelease` and ignored `+build`.
//   A version WITH a prerelease sorts BELOW the same version without one.
//   Prerelease identifiers compare numerically when numeric, else lexically;
//   numeric < non-numeric; more identifiers > fewer when all prior are equal.

const SEMVER_RE =
  /^[v=\s]*?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z-.]+))?(?:\+[0-9A-Za-z-.]+)?\s*$/;

/**
 * Parse a semver string into `{ strict, major, minor, patch, prerelease[] }`.
 * `strict` is `false` when the string did not match strict semver, in which case
 * the numeric core is a best-effort extraction and comparisons are approximate.
 * @param {string} version
 * @returns {{strict: boolean, major: number, minor: number, patch: number, prerelease: Array<string|number>}}
 */
function parseSemver(version) {
  if (typeof version !== 'string' || !version.trim()) {
    return { strict: false, major: 0, minor: 0, patch: 0, prerelease: [] };
  }
  const m = version.match(SEMVER_RE);
  if (!m) {
    const nums = (version.match(/\d+/g) || []).map((n) => parseInt(n, 10));
    return {
      strict: false,
      major: nums[0] || 0,
      minor: nums[1] || 0,
      patch: nums[2] || 0,
      prerelease: [],
    };
  }
  const pre = m[4]
    ? m[4].split('.').map((id) => (/^\d+$/.test(id) ? parseInt(id, 10) : id))
    : [];
  return {
    strict: true,
    major: parseInt(m[1], 10),
    minor: parseInt(m[2], 10),
    patch: parseInt(m[3], 10),
    prerelease: pre,
  };
}

/**
 * Compare two prerelease identifier arrays per semver 2.0.0 §11.4.
 * @param {Array<string|number>} a
 * @param {Array<string|number>} b
 * @returns {number} -1 | 0 | 1
 */
function comparePrerelease(a, b) {
  // No prerelease outranks a prerelease (1.0.0 > 1.0.0-rc.1).
  if (a.length === 0 && b.length === 0) return 0;
  if (a.length === 0) return 1;
  if (b.length === 0) return -1;
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) {
    const x = a[i];
    const y = b[i];
    const xNum = typeof x === 'number';
    const yNum = typeof y === 'number';
    if (xNum && yNum) {
      if (x !== y) return x < y ? -1 : 1;
    } else if (xNum !== yNum) {
      // numeric identifiers have lower precedence than non-numeric
      return xNum ? -1 : 1;
    } else {
      if (x !== y) return x < y ? -1 : 1;
    }
  }
  if (a.length === b.length) return 0;
  return a.length < b.length ? -1 : 1;
}

/**
 * Compare two version strings: returns -1 / 0 / 1 for a <, ==, > b under (approx)
 * semver ordering. Pure JS, no `semver` dependency.
 * @param {string} a
 * @param {string} b
 * @returns {number}
 */
function compareSemver(a, b) {
  const pa = parseSemver(a);
  const pb = parseSemver(b);
  if (pa.major !== pb.major) return pa.major < pb.major ? -1 : 1;
  if (pa.minor !== pb.minor) return pa.minor < pb.minor ? -1 : 1;
  if (pa.patch !== pb.patch) return pa.patch < pb.patch ? -1 : 1;
  return comparePrerelease(pa.prerelease, pb.prerelease);
}

// --------------------------------------------------------------------------- //
// verification_params parsing
// --------------------------------------------------------------------------- //

/**
 * @typedef {Object} VerificationParams
 * @property {string} packageName
 * @property {string|null} minVersion
 * @property {string|null} requiredScope     normalised (`@scope`) or null
 * @property {number} graceSeconds
 * @property {string} registryBase
 * @property {number|null} createdAtOverride  params-level created_at override (unix s) or null
 * @property {string|null} oracleDescription
 */

/**
 * Parse + validate a mission's `verification_params` into a typed view. Tolerant:
 * unknown keys are ignored, wrong-typed optionals fall back to defaults, aliases are
 * accepted, and only `packageName` is mandatory.
 * @param {object} mission  the raw OABP mission object
 * @returns {VerificationParams}
 */
function parseParams(mission) {
  const vp =
    mission && typeof mission === 'object' && mission.verification_params &&
    typeof mission.verification_params === 'object'
      ? mission.verification_params
      : null;
  if (!vp) {
    throw new Error('mission.verification_params must be an object');
  }

  const rawName = vp.packageName || vp.package_name || vp.package || vp.name;
  if (typeof rawName !== 'string' || !rawName.trim()) {
    throw new Error(
      'verification_params.packageName is required and must be a non-empty string',
    );
  }

  const optStr = (...keys) => {
    for (const k of keys) {
      const v = vp[k];
      if (typeof v === 'string' && v.trim()) return v.trim();
    }
    return null;
  };

  let grace = 0;
  for (const k of ['graceSeconds', 'grace_seconds']) {
    const v = vp[k];
    if (v !== undefined && v !== null) {
      const n = parseInt(v, 10);
      if (Number.isFinite(n)) {
        grace = Math.max(0, n);
        break;
      }
    }
  }

  const registryBase =
    optStr('registryBase', 'registry_base', 'registry') || DEFAULT_REGISTRY_BASE;

  const createdOverride = toUnixSeconds(
    vp.created_at !== undefined ? vp.created_at : vp.createdAt,
  );

  return {
    packageName: rawName.trim(),
    minVersion: optStr('minVersion', 'min_version', 'minimum_version'),
    requiredScope: normalizeScope(optStr('requiredScope', 'scope', 'required_scope')),
    graceSeconds: grace,
    registryBase: registryBase.replace(/\/+$/, ''),
    createdAtOverride: createdOverride,
    oracleDescription: optStr('oracle_description', 'oracleDescription'),
  };
}

/**
 * Determine the mission creation time (unix seconds) used as the freshness baseline.
 * Reads `mission.created_at` then a series of fallbacks; accepts seconds, millis, or
 * ISO strings. A params-level override wins. Returns `null` if none can be found.
 * @param {object} mission
 * @param {VerificationParams} params
 * @returns {number|null}
 */
function missionCreatedAt(mission, params) {
  if (params && params.createdAtOverride !== null && params.createdAtOverride !== undefined) {
    return params.createdAtOverride;
  }
  if (!mission || typeof mission !== 'object') return null;
  for (const key of ['created_at', 'created', 'createdAt', 'created_unix', 'created_at_unix']) {
    if (mission[key] !== undefined && mission[key] !== null) {
      const ts = toUnixSeconds(mission[key]);
      if (ts !== null) return ts;
    }
  }
  return null;
}

// --------------------------------------------------------------------------- //
// Read-only npm registry client
// --------------------------------------------------------------------------- //

class NpmRegistryError extends Error {}

/**
 * Read-only client for the npm registry packument endpoint `GET /{name}`.
 *
 * Uses an injected `fetch`-shaped function when provided (the test suite injects a
 * stub), otherwise the global `fetch` (Node >= 18), otherwise a built-in
 * `node:https`/`node:http` fallback. A 404 (or a registry "not found" body) is
 * surfaced to the caller as `null` (the package does not exist) rather than thrown;
 * only genuine transport / unexpected-status failures throw `NpmRegistryError`.
 */
class NpmRegistryClient {
  /**
   * @param {object} [options]
   * @param {string} [options.base]            registry base URL
   * @param {number} [options.timeoutMs]
   * @param {Function} [options.fetch]         injected fetch-shaped function
   */
  constructor(options = {}) {
    this.base = (options.base || DEFAULT_REGISTRY_BASE).replace(/\/+$/, '');
    this.timeoutMs = options.timeoutMs || HTTP_TIMEOUT_MS;
    this._fetch =
      options.fetch ||
      (typeof globalThis.fetch === 'function' ? globalThis.fetch.bind(globalThis) : null);
  }

  /**
   * Fetch the packument for `name`. Returns the parsed JSON object, or `null` if the
   * package does not exist (404 / registry not-found). Throws `NpmRegistryError` on
   * transport / decode / unexpected-status failures.
   * @param {string} name
   * @returns {Promise<object|null>}
   */
  async getPackument(name) {
    const url = this.base + '/' + encodeRegistryPath(name);
    let status;
    let bodyText;
    if (this._fetch) {
      let resp;
      try {
        resp = await this._fetch(url, {
          method: 'GET',
          headers: { 'User-Agent': USER_AGENT, Accept: 'application/json' },
        });
      } catch (err) {
        throw new NpmRegistryError('GET ' + url + ' failed: ' + (err && err.message));
      }
      status = resp.status;
      if (status === 404) return null;
      try {
        bodyText = await resp.text();
      } catch (err) {
        throw new NpmRegistryError('GET ' + url + ' body read failed: ' + (err && err.message));
      }
    } else {
      const res = await this._rawGet(url);
      status = res.status;
      if (status === 404) return null;
      bodyText = res.body;
    }

    if (status !== 200) {
      throw new NpmRegistryError('GET ' + url + ' -> HTTP ' + status);
    }
    let json;
    try {
      json = JSON.parse(bodyText);
    } catch (err) {
      throw new NpmRegistryError('GET ' + url + ' -> non-JSON body: ' + (err && err.message));
    }
    // The registry sometimes returns 200 with {"error":"Not found"} / {"error":"version not found"}.
    if (json && typeof json === 'object' && typeof json.error === 'string' && !json.versions) {
      if (/not\s*found/i.test(json.error)) return null;
      throw new NpmRegistryError('GET ' + url + ' -> registry error: ' + json.error);
    }
    return json;
  }

  /**
   * Minimal dependency-free HTTPS/HTTP GET used only when no `fetch` is available.
   * @param {string} url
   * @returns {Promise<{status:number, body:string}>}
   * @private
   */
  _rawGet(url) {
    return new Promise((resolve, reject) => {
      let u;
      try {
        u = new URL(url);
      } catch (err) {
        reject(new NpmRegistryError('bad url ' + url + ': ' + (err && err.message)));
        return;
      }
      const mod = u.protocol === 'http:' ? http : https;
      const req = mod.request(
        u,
        {
          method: 'GET',
          headers: { 'User-Agent': USER_AGENT, Accept: 'application/json' },
        },
        (res) => {
          const chunks = [];
          res.on('data', (c) => chunks.push(c));
          res.on('end', () =>
            resolve({ status: res.statusCode || 0, body: Buffer.concat(chunks).toString('utf8') }),
          );
        },
      );
      req.setTimeout(this.timeoutMs, () => {
        req.destroy(new NpmRegistryError('GET ' + url + ' timed out'));
      });
      req.on('error', (err) =>
        reject(new NpmRegistryError('GET ' + url + ' failed: ' + (err && err.message))),
      );
      req.end();
    });
  }
}

// --------------------------------------------------------------------------- //
// The oracle
// --------------------------------------------------------------------------- //

/**
 * @typedef {Object} VerifyResult
 * @property {boolean} verified  true iff every required check passed (pay iff true)
 * @property {string}  detail    one-line human-readable accept reason / first failure
 * @property {object}  evidence  structured, JSON-serialisable trace of what npm reported
 */

/**
 * Resolve an npm-publish mission. Structural-only; fail-closed; content-addressed.
 *
 * @param {object} mission     the raw OABP mission (with `verification_params` and a
 *                             creation time). See the header for the params schema.
 * @param {object|string} submission  the raw submission; its proof is `"name@version"`
 *                             read from `submission.proof` (or `.proof_data` /
 *                             `.content`, or the bare value).
 * @param {object} [opts]
 * @param {Function} [opts.fetch]  injected fetch-shaped function (tests / custom transport)
 * @param {NpmRegistryClient} [opts.client]  inject a fully-built client (wins over opts.fetch)
 * @param {number} [opts.now]      "now" in unix seconds (for deterministic evidence)
 * @returns {Promise<VerifyResult>}
 */
async function verify(mission, submission, opts = {}) {
  const nowUnix = Number.isFinite(opts.now) ? opts.now : Math.floor(Date.now() / 1000);

  const evidence = {
    verifier: 'npm_publish',
    checked_at_unix: nowUnix,
    checked_at_iso: isoFromUnix(nowUnix),
    checks: {},
  };
  const checks = evidence.checks;
  const reject = (detail) => ({ verified: false, detail, evidence });

  // --- parse params ----------------------------------------------------- //
  let params;
  try {
    params = parseParams(mission);
  } catch (err) {
    checks.params = { ok: false, reason: err.message };
    return reject('invalid verification_params: ' + err.message);
  }
  const createdAt = missionCreatedAt(mission, params);
  evidence.params = {
    packageName: params.packageName,
    canonical_package_name: canonicalName(params.packageName),
    minVersion: params.minVersion,
    requiredScope: params.requiredScope,
    graceSeconds: params.graceSeconds,
    registryBase: params.registryBase,
  };
  evidence.mission_created_at_unix = createdAt;
  evidence.mission_created_at_iso = isoFromUnix(createdAt);

  // --- 0) extract + parse proof ----------------------------------------- //
  const rawProof = extractProof(submission);
  let proofName;
  let proofVersion;
  try {
    const parsed = parseProof(rawProof);
    proofName = parsed.name;
    proofVersion = parsed.version;
  } catch (err) {
    checks.proof_parsed = { ok: false, reason: err.message };
    return reject('invalid proof: ' + err.message);
  }
  evidence.proof = { raw: rawProof, name: proofName, version: proofVersion };
  checks.proof_parsed = { ok: true };

  // --- 1) NAME MATCHES MISSION ------------------------------------------ //
  const nameOk = canonicalName(proofName) === canonicalName(params.packageName);
  checks.name_matches = {
    ok: nameOk,
    proof_name: canonicalName(proofName),
    wanted_name: canonicalName(params.packageName),
  };
  if (!nameOk) {
    return reject(
      'proof package "' + proofName + '" does not match mission package "' +
        params.packageName + '"',
    );
  }

  // --- 2) SCOPE (optional) ---------------------------------------------- //
  if (params.requiredScope) {
    const actualScope = scopeOf(proofName);
    const scopeOk = actualScope === params.requiredScope;
    checks.scope_matches = {
      ok: scopeOk,
      required: params.requiredScope,
      actual: actualScope,
    };
    if (!scopeOk) {
      return reject(
        'package "' + proofName + '" is not under required scope "' +
          params.requiredScope + '" (scope=' + (actualScope || 'none') + ')',
      );
    }
  }

  // --- 3) MIN VERSION (cheap; before any network) ----------------------- //
  if (params.minVersion) {
    const cmp = compareSemver(proofVersion, params.minVersion);
    const minOk = cmp >= 0;
    checks.min_version = {
      ok: minOk,
      proof_version: proofVersion,
      min_version: params.minVersion,
      compare: cmp,
    };
    if (!minOk) {
      return reject(
        'version ' + proofVersion + ' is below the mission minimum ' + params.minVersion,
      );
    }
  }

  // --- build client ----------------------------------------------------- //
  const client =
    opts.client ||
    new NpmRegistryClient({ base: params.registryBase, fetch: opts.fetch });

  // --- 4) PACKAGE EXISTS ------------------------------------------------ //
  let packument;
  try {
    packument = await client.getPackument(proofName);
  } catch (err) {
    checks.package_exists = { ok: false, error: String((err && err.message) || err) };
    return reject('could not query the npm registry for "' + proofName + '": ' + (err && err.message));
  }
  if (packument === null || typeof packument !== 'object') {
    checks.package_exists = { ok: false, reason: '404 / not on the npm registry' };
    return reject('package "' + proofName + '" is not published on the npm registry');
  }
  const versions =
    packument.versions && typeof packument.versions === 'object' ? packument.versions : {};
  const timeMap = packument.time && typeof packument.time === 'object' ? packument.time : {};
  const distTags =
    packument['dist-tags'] && typeof packument['dist-tags'] === 'object'
      ? packument['dist-tags']
      : {};
  checks.package_exists = { ok: true, version_count: Object.keys(versions).length };
  evidence.registry_info = {
    name: packument.name,
    latest: distTags.latest,
    version_count: Object.keys(versions).length,
  };

  // --- 5) VERSION PRESENT ----------------------------------------------- //
  const manifest = Object.prototype.hasOwnProperty.call(versions, proofVersion)
    ? versions[proofVersion]
    : undefined;
  const versionPresent = manifest !== undefined && manifest !== null;
  checks.version_present = { ok: versionPresent, version: proofVersion };
  if (!versionPresent) {
    evidence.available_versions_sample = Object.keys(versions).slice(-10);
    return reject(
      'version ' + proofVersion + ' of ' + proofName + ' is not present on the npm registry',
    );
  }

  // --- 6) HAS A TARBALL ------------------------------------------------- //
  const dist = manifest && typeof manifest.dist === 'object' && manifest.dist ? manifest.dist : {};
  const tarball = typeof dist.tarball === 'string' ? dist.tarball.trim() : '';
  const hasTarball = tarball.length > 0;
  checks.has_tarball = {
    ok: hasTarball,
    tarball: tarball || null,
    shasum: typeof dist.shasum === 'string' ? dist.shasum : null,
    integrity: typeof dist.integrity === 'string' ? dist.integrity : null,
  };
  if (!hasTarball) {
    return reject(
      'version ' + proofVersion + ' of ' + proofName +
        ' has no dist.tarball (nothing installable was published)',
    );
  }

  // --- 7) FRESHLY PUBLISHED (time[version] AFTER mission creation) ------ //
  const publishRaw = timeMap[proofVersion];
  const publishUnix = toUnixSeconds(publishRaw);
  if (createdAt === null) {
    checks.fresh_after_creation = {
      ok: true,
      enforced: false,
      reason: 'no mission creation time available; freshness not enforced',
      published_iso: typeof publishRaw === 'string' ? publishRaw : isoFromUnix(publishUnix),
    };
  } else if (publishUnix === null) {
    checks.fresh_after_creation = {
      ok: false,
      enforced: true,
      reason: 'no parseable time[' + proofVersion + '] in the packument',
    };
    return reject(
      'could not determine the publish time of ' + proofName + '@' + proofVersion +
        '; cannot confirm it was freshly published',
    );
  } else {
    const threshold = createdAt - Math.max(0, params.graceSeconds);
    const fresh = publishUnix > threshold;
    checks.fresh_after_creation = {
      ok: fresh,
      enforced: true,
      published_unix: publishUnix,
      published_iso: isoFromUnix(publishUnix),
      threshold_unix: threshold,
      threshold_iso: isoFromUnix(threshold),
      grace_seconds: params.graceSeconds,
    };
    if (!fresh) {
      return reject(
        'version ' + proofVersion + ' of ' + proofName + ' was published at ' +
          isoFromUnix(publishUnix) + ', which is NOT after the mission creation time ' +
          isoFromUnix(createdAt) + ' — it was not freshly published for this bounty',
      );
    }
  }

  // --- ALL CHECKS PASSED ------------------------------------------------ //
  const detail =
    proofName + '@' + proofVersion + ' published to npm (tarball ' + tarball + ')' +
    (publishUnix !== null ? ' at ' + isoFromUnix(publishUnix) : '') +
    (createdAt !== null && publishUnix !== null ? ' > created ' + isoFromUnix(createdAt) : '') +
    ' — verified';
  return { verified: true, detail, evidence };
}

module.exports = {
  verify,
  parseParams,
  parseProof,
  extractProof,
  missionCreatedAt,
  parseSemver,
  compareSemver,
  comparePrerelease,
  normalizeScope,
  scopeOf,
  canonicalName,
  encodeRegistryPath,
  toUnixSeconds,
  isoFromUnix,
  NpmRegistryClient,
  NpmRegistryError,
  DEFAULT_REGISTRY_BASE,
};
