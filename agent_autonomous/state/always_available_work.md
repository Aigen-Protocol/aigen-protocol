# Always-available improvement backlog

**For: AIGEN autopilot**
**Rule: when nothing external is happening, pick ONE item from this list, execute, mark done.**

Items are ordered by leverage (highest first). Don't pick randomly — pick the first NOT-YET-DONE item that you can complete in one run.

When you complete an item: change its checkbox from `[ ]` to `[x]`, add `→ done <ISO timestamp> in <commit-sha or "no commit">`. If partially done, leave `[ ]` and add a note.

---

## A. Registry submissions (single-shot, high mindshare)

- [~] **Smithery** — submit AIGEN to https://smithery.ai → **partial done 2026-05-16T09:00Z** in commit pending
  - Smithery's official submission flow requires browser/GitHub OAuth at `smithery.ai/new` — that's Tier B (Bilale's job).
  - **Autopilot pre-staged the metadata fallback**: `/.well-known/mcp/server-card.json` (200/6214B, all 22 tools listed) per Smithery's official docs at `smithery.ai/docs/build/publish.md`. When SmitheryBot/1.0 crawls or when Bilale submits, scan succeeds first-try (same pattern as Lesson 52 glama.json).
  - **Remaining for Bilale**: visit https://smithery.ai/new , log in via GitHub, paste `https://cryptogenesis.duckdns.org/mcp` as the server URL, complete the publishing workflow.
  - Reasoning: Smithery is the most-used MCP registry in 2026; not being listed there = invisible.

- [ ] **Glama** — submit AIGEN to https://glama.ai/mcp
  - Glama indexes from `/.well-known/oabp.json` automatically once they discover us. PR their list if needed.
  - Hint: a Glama fiche was mentioned in journal earlier — verify status, push to completion.

- [~] **PulseMCP** — submit to https://pulsemcp.com → **invalid 2026-05-16T09:48Z** — `pulsemcp/registry` GitHub repo returns 404; doesn't exist. Need to check pulsemcp.com directly for alternative submission flow (Bilale's job — needs browser login).

- [ ] **MCP Marketplace** (mcp.so) — bump PR #2298 status
  - `gh pr view 2298 --repo chatmcp/mcp-directory` to check state
  - If stale (>3 days no activity): post a polite "bump — happy to address any blockers" comment

- [ ] **awesome-mcp-servers** (punkpeye) — bump PR #6288
  - Same flow as mcp.so. Polite bump if stale.

- [x] **TensorBlock** PR #542 — addressed review feedback → done 2026-05-16T09:35Z in commit f5e4b40 on `Aigen-Protocol/awesome-mcp-servers-4@add-aigen-protocol-fresh` (auto-updates PR #542). Review by @wilsonccccc on 2026-05-14T17:45Z asked for (1) neutral phrasing — removed `**0.5% protocol fee** vs 5–20% on Replit/Bountybird/Superteam Earn` promo language and bold; (2) mirror entry into `docs/finance--crypto.md`. Both done in 2-line diff. Reply comment posted: https://github.com/TensorBlock/awesome-mcp-servers/pull/542#issuecomment-4466476638. Watch list: re-review within 7 days, else polite bump.

- [ ] **awesome-agents-frameworks** — find PR opportunity for an "open agent bounty protocol" entry

## B. Concrete code/doc improvements (do in repo)

- [x] **TypeScript SDK skeleton** in `sdk/typescript/` → done 2026-05-16T09:55Z in commit pending
  - `package.json` + `tsconfig.json` + `src/index.ts` — full port of Python SDK surface
  - Zero runtime deps, native fetch, Node 18+/browser, strict TypeScript
  - Exports: `OABPClient`, `Mission`, `Submission`, `AgentReputation`, `OABPError`, `VERSION`
  - README updated to reference both Python and TypeScript SDKs

- [ ] **OpenAPI 3.1 response examples** in `specs/openapi-aip-1.yaml`
  - For each path, add `examples:` block with a realistic JSON payload
  - Makes the spec importable into Swagger/Insomnia/Postman with usable examples

- [x] **`examples/` folder** at repo root → done 2026-05-16T09:15Z in commit 7f77933
  - Added 7 numbered entry-level files (`01_discover.sh` → `07_python_sdk.py`) covering discovery, mission list, single-mission read, agent reputation, both submit flows (`first_valid_match` + `peer_vote`), and Python SDK usage. All curl scripts smoke-tested against live `cryptogenesis.duckdns.org`. Integrated above the existing `autonomous_bounty_hunter.py` section so the README presents a clean "first 5 minutes" tour before the full-agent example. Per backlog scope (one file per verification type) — kept `creator_judges` and `oracle` out of v1 since AIGEN has zero live missions of either type to demo against; will add when at least one of each exists.

- [ ] **AIP-2 draft** — Mission Type Registry
  - Use AIP-1 structure (sections + appendices)
  - Define well-known mission categories (token-scan, code-review, doc-write, test-create, etc.)
  - Each category has a JSON schema for its expected fields

- [ ] **Conformance suite expansion** — `sdk/python/tests/test_oabp_conformance.py`
  - Add tests for: deadline validation, status transitions, fee calculation, reward asset normalization
  - Currently 15 tests; aim for 30 covering edge cases

- [ ] **`/missions/feed.xml`** — RSS feed specifically for new missions
  - Easy plug into Feedly, Inoreader for agents that want to poll
  - Auto-generate from missions table

- [ ] **Tutorial: "Implement AIP-1 in 60 minutes"** as new blog post
  - Walk through building a minimal OABP-compliant server in any language
  - The clearest path to "second implementation exists"

## C. Content (compound mindshare)

- [x] **Blog post #2** draft in `blog/` → done 2026-05-16T09:50Z in commit pending
  - Published `blog/2026-05-16-protocol-discovery-2026.md` (~1300 words)
  - Topic: "Protocol discovery in 2026: what 72 hours of traffic logs taught us"
  - Covers: machine vs human discovery, crawler taxonomy (4 types), @worjs unsolicited submission as the real signal, honest state of things after 72h. Honest, specific, no marketing.
  - **Bilale to do**: review tone/voice, then post to HN + submit as blog route.

- [ ] **AIP-1 v0.2 spec draft** — incorporate any feedback received since publication
  - If `gh api notifications` shows new comments on AIP-1, address them
  - If outreach replied with critique, version it

- [ ] **"How to read the autopilot journal" guide** for new visitors
  - Lives in `docs/READING_JOURNAL.md`
  - Explains: emoji vocabulary, what "no-op" means, why it's valuable, how to spot real signals

## D. Outreach support (drafts only — Bilale sends emails)

- [ ] **Find 5 more outreach candidates** in adjacency space
  - Add to `distribution/outreach_targets_2026_06.md` (next month's batch)
  - Tier 1+2+3 structure as before

- [ ] **GitHub issue templates** in `.github/ISSUE_TEMPLATE/`
  - Spec discussion template, bug template, implementation announcement template
  - Lowers friction for outsiders to contribute

- [ ] **Anti-FUD doc**: pre-emptive answers to predictable critiques
  - "Why CC0 not MIT", "Why ELO not stake-weighted", "Why permissionless instead of curated"
  - Lives in `docs/FAQ.md`. Lets you respond to critique with a link instead of writing fresh each time.

## E. Self-improvements (system_prompt + autopilot infra)

- [ ] **Cost per run trending**: detect when api-equivalent cost climbs unexpectedly
  - Add to dashboard if today_spent > 1.5× rolling 7d average → alert

- [ ] **Inbox response drafts** for likely email replies
  - If Codex researcher replies, what do we send? Draft `distribution/outreach_drafts/responses/`
  - If Nico replies on PR #5, what's the next thing to offer?

- [ ] **A "second implementation starter pack"** in `docs/SECOND_IMPLEMENTATION.md`
  - For someone forking AIP-1 to build their own. Bullet list of must-haves, common pitfalls, how to claim the badge.

---

## How to use this list

1. At start of run: read this file.
2. If 2 previous runs were watching-only (no concrete improvement shipped), MUST pick from here.
3. Look for the highest-leverage `[ ]` item you can complete in one run.
4. Execute it. Update this file. Commit (if applicable). Chat about it in plain French.
5. If an item is too big for one run, take the first slice and add a note about what's left.

**Rule of thumb**: every 24h, this file should have at least 1 new `[x]` (or 1 new partial-progress note).

---

## Items that are NOT here (and shouldn't be added)

- Refactoring for cleanliness sake (no external request)
- Performance optimization (we have ~0 traffic, premature)
- New autonomous daemons (already enough)
- Synthetic mission generation (radar does that)
- UI polish (use the budget on real work instead)
- Anything in Tier B/C (queue for Bilale)
