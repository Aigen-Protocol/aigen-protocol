/**
 * Dependency-light build using only `typescript` (no tsup/bundler).
 *
 * Emits the same dist layout the package.json `exports` map points at:
 *   - dist/index.js   (ESM)         + dist/index.d.ts
 *   - dist/index.cjs  (CommonJS)    + dist/index.d.cts
 *
 * It runs `tsc` twice (ESM then CJS into a temp dir), renames the CJS output to
 * `.cjs`/`.d.cts`, and rewrites the relative `./x.js` import specifiers inside
 * the CJS files to `./x.cjs` so Node resolves the CommonJS variants. This is a
 * fallback for environments without tsup; the default `npm run build` uses tsup.
 *
 * Usage:  npm run build:tsc
 */

import { spawnSync } from "node:child_process";
import {
  mkdirSync,
  rmSync,
  readdirSync,
  readFileSync,
  writeFileSync,
  renameSync,
  existsSync,
} from "node:fs";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");
const tmpCjs = join(root, ".tmp-cjs");

function run(args) {
  const res = spawnSync(process.execPath, [tscBin(), ...args], {
    cwd: root,
    stdio: "inherit",
  });
  if (res.status !== 0) {
    console.error(`tsc ${args.join(" ")} failed with code ${res.status}`);
    process.exit(res.status ?? 1);
  }
}

function tscBin() {
  const local = join(root, "node_modules", "typescript", "bin", "tsc");
  if (existsSync(local)) return local;
  console.error("typescript not found in node_modules. Run `npm install` first.");
  process.exit(1);
}

// Clean.
rmSync(dist, { recursive: true, force: true });
rmSync(tmpCjs, { recursive: true, force: true });
mkdirSync(dist, { recursive: true });

// 1) ESM build (declarations + .js) straight into dist.
run([
  "--project", "tsconfig.json",
  "--module", "ESNext",
  "--moduleResolution", "Bundler",
  "--outDir", "dist",
  "--declaration", "true",
  "--declarationMap", "false",
  "--sourceMap", "true",
]);

// 2) CJS build into a temp dir, then fold into dist as .cjs / .d.cts.
run([
  "--project", "tsconfig.json",
  "--module", "CommonJS",
  "--moduleResolution", "Node",
  "--outDir", ".tmp-cjs",
  "--declaration", "true",
  "--declarationMap", "false",
  "--sourceMap", "true",
  // CJS output must not be subject to verbatimModuleSyntax ESM-only rules.
  "--verbatimModuleSyntax", "false",
]);

/** Rewrite ./foo.js specifiers to ./foo.cjs in a CJS source string. */
function rewriteCjsImports(code) {
  return code
    .replace(/require\((['"])(\.\.?\/[^'"]+?)\.js\1\)/g, "require($1$2.cjs$1)")
    .replace(/from (['"])(\.\.?\/[^'"]+?)\.js\1/g, "from $1$2.cjs$1");
}

for (const file of readdirSync(tmpCjs)) {
  const src = join(tmpCjs, file);
  const code = readFileSync(src, "utf8");

  if (file.endsWith(".d.ts")) {
    const out = join(dist, file.replace(/\.d\.ts$/, ".d.cts"));
    writeFileSync(out, rewriteCjsImports(code));
  } else if (file.endsWith(".js")) {
    const out = join(dist, file.replace(/\.js$/, ".cjs"));
    writeFileSync(out, rewriteCjsImports(code));
  } else if (file.endsWith(".js.map")) {
    renameSync(src, join(dist, file.replace(/\.js\.map$/, ".cjs.map")));
  }
}

rmSync(tmpCjs, { recursive: true, force: true });
console.log("build:tsc complete — dist/index.js (ESM) + dist/index.cjs (CJS) + .d.ts/.d.cts");
