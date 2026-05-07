# Publishing `@aigen-protocol/plugin-safeagent` to npm

The plugin is fully built and ready in
[Aigen-Protocol/plugin-safeagent#1](https://github.com/Aigen-Protocol/plugin-safeagent/pull/1)
on branch `v2`. Merge that PR first if you want it visible on `main`.

## Pre-publish checklist (already done)

- ✅ Scope `@aigen-protocol/` (we control this; `@elizaos/` is upstream-only)
- ✅ Version 2.0.0
- ✅ `tsc` build succeeds — `dist/index.js` + `dist/index.d.ts` produced
- ✅ 4 actions registered: SHIELD, WATCH_WALLET, SAFE_CHECK, SAFE_SWAP_CALLDATA
- ✅ Live test: SHIELD returned `Score: 100/100 SYSTEM TOKEN` for USDC on Base
- ✅ README has on-chain contract table, signature verification example
- ✅ LICENSE (MIT) included
- ✅ `prepublishOnly` hook re-runs build before publish
- ✅ `publishConfig.access: "public"` set (scoped packages default to private otherwise)

## Steps to publish

```bash
# 1. Clone the plugin repo + checkout v2 branch
git clone https://github.com/Aigen-Protocol/plugin-safeagent
cd plugin-safeagent
git checkout v2
npm install --no-fund --no-audit

# 2. Login to npm (one-time, opens browser for device-code flow)
npm login
# enter: username, email, password (and OTP if 2FA enabled)

# 3. (First time for the @aigen-protocol scope) — create the org on npm
#    Either:
#      - go to https://www.npmjs.com/org/create and create "aigen-protocol"
#      - OR change package.json name to unscoped: "safeagent-eliza-plugin"
#        (less professional but no org creation needed)

# 4. Publish
npm publish
# → published to https://www.npmjs.com/package/@aigen-protocol/plugin-safeagent

# 5. Verify
npm view @aigen-protocol/plugin-safeagent
```

## After publish

1. **Update `Aigen-Protocol/aigen-protocol` README** with the npm install line:
   ```bash
   npm install @aigen-protocol/plugin-safeagent
   ```

2. **Reply on the closed elizaOS issues** (we already linked to GitHub repo,
   now we can link to npm):
   - [elizaOS/eliza#6706](https://github.com/elizaOS/eliza/issues/6706)
   - [elizaOS/eliza#6707](https://github.com/elizaOS/eliza/issues/6707)
   - [elizaOS/eliza#6708](https://github.com/elizaOS/eliza/issues/6708)

   Comment template:
   > Plugin now published per the elizaOS-plugins / npm convention:
   > `npm install @aigen-protocol/plugin-safeagent`
   > Source: https://github.com/Aigen-Protocol/plugin-safeagent
   > Live API: https://cryptogenesis.duckdns.org/mcp

3. **Submit to elizaOS-plugins org** (optional — they may accept a fork
   as a registered plugin):
   - Open issue/PR at https://github.com/elizaOS/elizaos-plugins requesting
     listing as a community plugin. Reference the npm package + 4 actions.

## If you don't have an npm account

1. Create one at https://www.npmjs.com/signup (email = Cryptogen@zohomail.eu
   per existing conventions)
2. Verify email
3. Enable 2FA (recommended for publish auth)
4. Run the steps above

## If npm publish fails

Common errors:
- **403 You do not have permission to publish** → scope `@aigen-protocol/`
  doesn't exist on npm yet. Create org at https://www.npmjs.com/org/create
- **402 Payment Required** → trying to publish private. Confirm `publishConfig.access`
  is `"public"` in package.json (it is).
- **403 Package name too similar to existing** → rename. Suggest:
  `safeagent-elizaos-plugin` or `aigen-safeagent-plugin`.
