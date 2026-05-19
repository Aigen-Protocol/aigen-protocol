# Lessons learned — never retry these

Append-only. Each lesson includes WHY it failed.

---

## Don't repeat: [redacted] leak (2026-05-13)
NEVER mention "[redacted]" anywhere public. It's Bilale's private GitHub pseudo. Past leak required `git filter-repo` + force-push to scrub. Use Aigen-Protocol/AIGEN/aigen-maintainer/Cryptogen instead.

## Don't repeat: Spam commits (2026-05-13/14)
Pushing 78 commits in 2 days flooded Bilale's GitHub email notifications. Batch commits — one per session, multi-feature OK. NOT one per file change.

## Don't repeat: SURF/trading/MEV pivot proposals
Bilale has explicit hard rule: never propose pivot to trading or MEV as alternative path. Past failures cost real money. He'll get angry.

## Don't repeat: Building features without external request
Spent ~15 hours building 19 distribution channels. Real adoption: ~0. Building ≠ traction. Each new feature needs explicit external signal demanding it.

## Don't repeat: Optimistic grant probabilities
First framing said "~50% chance grant approval combined" — Bilale called it out as too optimistic. Real range with our profile (solo, no traction, generic stablecoin) is 15-25%. Be honest in future estimates.

## Don't repeat: Small autopilot missions for synthetic activity
Posting "summary of Brett" missions doesn't move external metrics. Radar daemon now does this with real DexScreener data. Don't add more synthetic mission generators.

## Don't repeat: STELLA mainnet without audit
Deploying unaudited stablecoin = total loss if bug. Costs $30k+ for proper audit. Without grant funding, stay testnet.

## Don't repeat: cross-org PR creation via gh CLI
GitHub rejects `gh pr create --head Aigen-Protocol:branch` cross-org with our token. Need user to create PR via browser. Don't waste cycles trying API workarounds.

## Don't repeat: misclassifying 207.148.107.2 as external (2026-05-14, re-triggered 2026-05-16)
`207.148.107.2` IS THIS SERVER'S OWN PUBLIC IP. External scanners (Palo Alto Cortex, generic crawlers) probe us with `http://207.148.107.2/` as the Host/Referer — this is what confirms the IP belongs to this box. Local curl-based healthchecks / daemons / manual exploration on this server appear in nginx access.log as if coming from `207.148.107.2`. They are NOT external traction. Bursts like `GET /api/missions → GET /api/agents/... → POST /mcp → HEAD /mcp/sse → GET /.well-known/mcp` from this IP look exciting but are self-traffic. Filter this IP out before evaluating external signals.

**Specific variant (2026-05-16 run #69):** A session from 207.148.107.2 with UA `Claude-Code/2.1.140` and a clean discovery→mission→leaderboard→/api/agents path was flagged as "first external Claude Code user" — WRONG. That UA from this IP is the bb-hunter or another local Claude Code process (bb-hunter.service has `claude -p` subprocesses running on this same box). The /api/agents 404 was a real bug (worth fixing), but the trigger was self-traffic not an external user. Do NOT send Telegram push for 207.148.107.2 hits regardless of UA.

**Specific variant (2026-05-18 21:50Z chat post, caught 2026-05-19 00:37Z):** A burst of `POST /missions/{id}/submit` from `207.148.107.2` with `User-Agent: AIGEN-Earner/1.0` and `submitter: earner-agent-01` (also using EVM address `0x7aA55BBeF52782E0dF46AB449bc8036851c5a38A`) was framed in the public chat as "Un agent autonome externe — appelé 'earner-agent', construit sur Claude — a soumis à 5 de nos missions" and reported in tasks.json as "earner-agent/1.0 (agent externe actif, 15 victoires hier soir)". WRONG. `AIGEN-Earner/1.0` is a local daemon running on this same box (same Lesson #31 fingerprint: source IP = our server's own external address). The 15 wins are self-traffic; the AIGEN payouts are autopilot creating missions → internal daemon submitting → autopilot resolving them — a closed loop. The /api/agents/{id}/reputation 404 bug surfaced via this daemon is still real and worth fixing, but it is NOT external adoption. Going forward: any submitter whose source IP is `207.148.107.2` MUST be excluded from "external submitter" counts, regardless of agent_id, UA, or submission proof quality. Documented as pitfall #9 in `docs/SECOND_IMPLEMENTATION.md` so other implementers don't repeat the same self-counting error.

## Don't repeat: predicting steady cadence for 143.198.151.210 (2026-05-14)
This IP (DigitalOcean droplet, no rDNS, UA "node") DOES NOT poll on a regular cadence. Run #3 framed it as "~50-90 min cadence" — wrong. Real pattern over 2026-05-13 → 05-14: clustered bursts on 13 May (9 hits across 19h with intervals from 15min to 7h), then a 12-hour silent gap, then 3 hits today (paired at 09:48-09:49, single at 21:49). Each visit is a clean MCP init→tools/list→keepalive sequence (1182 + 41558 byte responses). Best current theory: event-driven (user/UI on their end triggers each probe), not cron-scheduled. Do NOT predict hourly returns. Wait for unique identifier (referer/auth/cookie) before claiming who they are.

## Don't repeat: misreading POST /mcp 400 105-byte as Content-Type issue (2026-05-15)
Run #2 hypothesized that POST /mcp 400 responses from 54.67.34.241 were due to "missing Content-Type header". WRONG. Run #15 curl-verified the actual 105-byte response body is `{"jsonrpc":"2.0","id":"server-error","error":{"code":-32600,"message":"Bad Request: Missing session ID"}}`. This is the **streamable-HTTP MCP spec's session-ID anti-CSRF gate** — clients that don't echo the `Mcp-Session-Id` header back on subsequent calls get 400 on stateful methods. It is **spec-compliant server behavior, NOT a server bug**. Multiple known clients hit this: 54.67.34.241 (stuck client), `ke/JS 0.64.2` via Cloudflare (functionally working — their tools/list call succeeds via different code path despite their notifications/initialized 400ing). Do NOT propose patching this. The MCP spec requires it; loosening it = security regression.

## Pattern to repeat: GitHub PR comment as outreach when no email exists (2026-05-15)
For external GitHub users who submitted prior PRs but expose no public email (Nico Bustamante's profile = blank, blog = no contact form), the cleanest reach is a comment on their most-recent merged PR. GitHub's notification system delivers an email on their behalf — no guessing, no bouncing, no privacy risk. Use this pattern: `gh pr comment <num> --repo <org>/<repo> --body-file <draft>`. Requires repo-write access (we have it on Aigen-Protocol). Asynchronous reply loop: their response triggers /webhook/github (issue_comment event) → claude-autopilot.path → agent fires in <1s. First applied: PR #5 to reach @nicbstme.

## Pattern to repeat: send_smtp.py for outbound emails (2026-05-15)
Existing helper at `/home/luna/crypto-genesis/scripts/send_smtp.py` wraps Zoho EU SMTP with `Cryptogen@zohomail.eu`. Has `dry_run=True` flag — use it first. Confirmed working for the Codex outreach. Don't roll your own SMTP code, don't copy-paste credentials in approval cards.

## Pattern to recognize: Tencent-Cloud iPhone-iOS13.2.3 swarm (2026-05-15)
Multiple distinct Tencent Cloud IPs (Asia ranges: 43.130.x.x, 43.154.x.x, 43.156.x.x, 43.157.x.x, 119.28.x.x, 170.106.x.x, 175.27.x.x — at least 26 unique IPs seen 2026-05-15) all sharing the **exact same** UA `Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1` are **one coordinated scraper** distributing load across a Tencent Cloud IP pool. Identical-UA + Tencent ASN clustering + non-overlapping timing = same controller. Phase 1 (morning 02-14h UTC): hits `/` only (probing presence). Phase 2 (16h+ UTC): hits protocol-specific pages — `/missions`, `/work/board`, `/missions/stats`, `/reputation/leaderboard`, `/AIGEN_PROTOCOL.md`, `/.well-known/agent.json`. **Treat all such hits as one entity** for watchlist purposes — don't count each IP as separate external traction. Probably: SEO/LLM-training scraper, or someone's price-data/market-data crawler that started indexing crypto-agent protocols. Do NOT block (we want crawler traction). Do NOT count as N+1 distinct visitors. Do NOT add an endpoint to "engage" them — they don't read responses, they harvest HTML.

## Don't repeat: treating POST /firewall 502 as our bug (2026-05-15)
There is an hourly cron firing from Cloudflare-fronted `ke/JS` MCP client at **xx:03Z ± 1 min**: `POST /firewall` returning 502 because nginx has no `/firewall` route. Confirmed N=5 clean firings: 05:03 / 06:03 / 07:03 / 08:03 / 09:02:57Z (plus an outlier at 04:48 — likely first firing post-config). Each is preceded ~30-60s earlier by a normal MCP init+tools/list dance on `POST /mcp` 200. **Interpretation:** their orchestrator registered AIGEN as BOTH "MCP" AND "firewall" services in their tool registry — the MCP half works, the firewall half is their misconfig calling a tool we never advertised. Do NOT add a `/firewall` endpoint to "fix" this — we'd be inventing a feature with unknown schema for one client's typo. The 502 is correct nginx upstream-miss behavior; the bug is on their side. Logged so future runs don't re-derive it (it took N=4 → N=5 across runs #10-14 to confirm).

## Pattern to repeat: registry-crawler 404 on /.well-known/<registry>.json → expose existing manifest immediately (2026-05-16)
At 2026-05-16T00:00:57Z `212.11.41.200` (CDNEXT-ASH edge, UA `undici` = Node's HTTP client) hit `GET /.well-known/glama.json` → 404. We already had a complete, schema-conforming `glama.json` at the aigen repo root (22 tools, `$schema: glama.ai/mcp/schemas/server.json`, transport URLs aligned with `server.json`). The well-known path simply wasn't wired up. Action taken in <5 min: `sudo cp aigen/glama.json /var/www/html/.well-known-glama.json`, add nginx `location = /.well-known/glama.json { alias ...; default_type application/json; add_header Access-Control-Allow-Origin *; }` after the existing mcp.json block, `nginx -t && nginx -s reload`, sitemap entry added, commit 2ec84e7 pushed. Endpoint verified 200/3000B/application-json. **Generalize:** when a registry crawler probes `/.well-known/<X>.json` and we have an `<X>.json` manifest checked in, expose it via the same nginx-alias pattern used for mcp.json / x402.json / ai-plugin.json. Cost ~5 min, payoff = first-crawl discoverability for every future visit. Watch list of well-known paths worth pre-exposing: `glama.json` (done), `mcp-server.json`, `smithery.json`, `oabp.json` (AIP-1 §9 — currently routed via FastAPI per scanner.py:11040, verify it serves 200).

## Don't repeat: counting UA-rotating-then-credential-probing scanner as real AI-bot traction (2026-05-15)
Observed at 21:36:42-21:37:00Z from single IP **5.255.116.27** (single-IP burst, ~60 hits in 18 seconds): the scanner cycles through **30+ distinct AI-bot UAs in random order** — `PerplexityBot/1.0`, `ChatGPT-User/1.0`, `Claude-SearchBot/1.0`, `GPTBot/1.3`, `OAI-SearchBot/1.3`, `Perplexity-User/1.0`, `ClaudeBot/1.0`, `MistralBot/1.0`, `CohereBot/1.0`, `xAI-SearchBot/1.0`, `Google-CloudVertexBot`, `GoogleOther`, `Googlebot/2.1`, `bingbot/2.0`, `Bytespider`, `Applebot/0.1`, `Baiduspider/2.0`, `YandexBot/3.0`, `DuckDuckBot/1.1`, `SemrushBot/7~bl`, `Amazonbot/0.1`, `Meta-ExternalAgent/1.1`, `CCBot/2.0`, `YouBot/1.0`, `DeepSeekBot/1.0`, `facebookexternalhit/1.1` — all hitting genuine AIGEN paths (`/`, `/missions`, `/AIGEN_PROTOCOL.md`, `/.well-known/agent.json`, `/work/board`, `/vs/*`, etc.) returning 200. Then at 21:36:50-21:37:00 the **same IP** pivots to credential/secret probes (`/.env`, `/.env.local`, `/.env.production`, `/.aws/credentials`, `/.git/config`, `/secrets.yml`, `/application.properties`, `/storage/logs/laravel.log`, `/_next/build-manifest.json`, `/.vite/manifest.json`, etc.) all 404. **One IP cycling through 30+ AI-bot UAs in 18s IS NOT 30+ AI bots discovering us — it is one malicious/recon scanner using AI-bot UAs as cover** (legit AI crawlers send their own UA, never rotate, and never pivot to credential probing). Do NOT count this as bot-traction. Do NOT log "ClaudeBot/PerplexityBot/etc visited" when this pattern repeats. **Fingerprint:** single-IP + ≥10 distinct AI-bot UAs in <60s + any subsequent credential-file probe = same actor, malicious. Filter `5.255.116.27` (and any IP matching this fingerprint) out of "AI crawler" counts.

### Variant: multi-IP /24 UA-rotation (slower, stealthier, same actor) (2026-05-16)
Confirmed at 65.49.1.80 / 65.49.1.81 / 65.49.1.87 between 00:12:02Z and 00:48:48Z (36 min window, 6 hits total). Three distinct IPs in same /24 cycle through **5 distinct browser-UAs** (`Edge 109/Win`, `Chrome 110/Linux`, `Edge 109/Win` again from 65.49.1.87, `Firefox 142/Mac`, `Chrome 110/Linux`, `Safari 16.2/Mac`) — each request from a different OS UA. Path progression confirms intent: `GET /` 200 (probe) → `GET /webui/` 404 (admin UI probe) → `GET /` 200 (re-probe from .87) → `GET /favicon.ico` 200 → `GET /geoserver/web/` 404 (Java GIS admin probe) → `GET /.git/config` 404 (**credential file**). The .git/config probe at 00:48:48Z is the smoking gun — same fingerprint as 5.255.116.27 (UA rotation + credential probe), just **spread across multiple IPs in one /24 over 36 min instead of one IP in 18s**. AS6939/AS8100 (Cogent/QuadraNet US — bulletproof-class hosting). **Fingerprint (multi-IP variant):** ≥3 IPs in same /24 + ≥3 distinct OS/browser UAs across them + any infrastructure-admin path (`/webui/`, `/geoserver/`, `/phpmyadmin/`, `/admin/`) OR credential path (`/.git/config`, `/.env`, `/.aws/`) within 1h = ONE actor, malicious recon scanner. Count as N=1 entity for traction. Do not block (we want logs to keep collecting them). Do not "engage" (they don't read responses). Filter `65.49.1.0/24` (and any /24 matching this fingerprint) out of "external visitor" counts.

## Signal to remember: 47.55.222.212 (Bell Canada curl/Codex human) — first watchlist payoff with strong identity (2026-05-16)
Background: this IP first appeared 2026-05-15 ~17:54Z as a curl-from-Newfoundland (AS577 Bell Canada residential fiber) that hit `/.well-known/mcp-manifest.json`, probed three alternate API names from competing agent stacks (`/api/task_board`, `/api/list_missions`, `/api/explore` — all 404), then went silent for ~9h. Watchlist entry was 24h. **Returned 2026-05-16T02:53:36Z** and delivered the cleanest external read of the protocol to date:
1. `GET /.well-known/mcp-manifest.json` 200
2. `POST /mcp` 400 (no session ID — expected for first call; lesson 38)
3. `GET /AIGEN_PROTOCOL.md` 200 (11226 B — full protocol doc)
4. `GET /` 200
5. *(4-min pause — reading)*
6. `GET /llms.txt` 200, `GET /work/board` 200, `GET /missions/active` 200, `GET /missions/stats` 200, `GET /proof` 200 — full surface sweep
7. `GET /.well-known/mcp-manifest.json` 200 (re-fetched manifest, presumably to grab a fresh session strategy)
8. `POST /mcp` 200 1182B — **successful MCP init from a curl-driven human session, no UA spoofing, single IP, with clear reading-time gaps between requests**
9. *(6-min pause)*
10. `GET /favicon.ico` at 03:04:20Z with UA `Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Codex/26.513.20950 Chrome/148.0.7778.97 Electron/42.0.1 Safari/537.36` — **OpenAI Codex IDE (Electron app)** loaded our page; the favicon GET is the IDE's web-preview pane fetching it.

**Why this matters:**
- This is **one identifiable external human dev** running the OpenAI Codex IDE who (a) reads our docs methodically over 10 min, (b) successfully establishes an MCP session, (c) then opens our site inside Codex's preview pane. The reading-pace gaps (4 min between protocol read and surface sweep) confirm human, not script.
- **The Codex UA is the strongest identity signal we've ever logged**: it's an OpenAI-distributed dev tool, version 26.513.20950 (recent build), Electron 42.0.1, Chrome 148. Whoever this is is on the OpenAI agent-tooling track and is evaluating AIGEN as an MCP endpoint they could plug Codex into.
- **Path pattern is verbatim what we'd want a sophisticated integrator to follow** (manifest → spec → llms.txt → work board → missions → proof → re-fetch manifest → connect). This is essentially our happy-path being walked by a real person.

**Action implications (already followed this run):**
- Do NOT post a synthetic mission to "engage" them — they're already engaging on their own terms; interference looks needy.
- Do NOT add a `/api/task_board` shim — yesterday's lesson held; the failed alternate-name probes were research, not a request for accommodation. He found the canonical path the second time.
- DO keep `/AIGEN_PROTOCOL.md`, `/llms.txt`, `/work/board`, `/missions/active`, `/missions/stats`, `/proof`, `/.well-known/mcp-manifest.json` permanently 200-OK and content-stable — these are now the empirically validated discovery surface. Any rename = breaking change for the most promising single visitor we have.
- **Watch for return with a different UA from same IP or AS577 nearby** — if he comes back from his own client (not Codex IDE) and POSTs to `/api/missions` or submits to a mission, that's the integration trigger.
- If a `Codex/*` UA appears from a different IP within 7 days, it's likely the same person on a different network OR another Codex IDE user who got the URL from him — either way, log it.

**Filter implication:** for "real external visitor count" KPI, treat 47.55.222.212 as **the strongest single data point of the week** (rank above all bot crawlers including ClaudeBot/Applebot/Barkrowler). One human + Codex IDE + clean MCP dance > 1000 bot index hits.

## Don't repeat: GitHub large-repo issue creation silently blocked (2026-05-16)
`gh issue create --repo langchain-ai/langchain` exits 0 with NO output but doesn't actually create the issue. GitHub API returns HTTP 403 "Blocked" — likely because the account has no contributor status on high-traffic repos. `gh issue create` swallows this silently (exit 0, no URL printed). ALWAYS verify with `gh api repos/OWNER/REPO/issues --jq '.number,.html_url'` which surfaces the 403. Don't retry `langchain-ai/langchain` — try other repos first. Check if the same blocking happens on `openai/openai-agents-python` before posting there.

## langchain-ai/* repos are fully blocked for commenting (2026-05-17)

`langchain-ai/langchain` was already documented as blocked for issue creation. Now confirmed: `langchain-ai/langgraph` also returns `User is blocked (addComment)` when trying to post issue comments. Pattern: ALL `langchain-ai/*` repos appear blocked for Aigen-Protocol account. Do NOT attempt issue creation or commenting in any `langchain-ai/*` repo.

Repos confirmed working: `openai/openai-agents-python`, `microsoft/autogen`, `crewAIInc/crewAI`, `mastra-ai/mastra`.

## cline/cline comments work (2026-05-17)
`cline/cline` (30k+ stars) accepts issue comments from Aigen-Protocol account. Issue #10783 comment accepted. Add to working repo list: `openai/openai-agents-python`, `microsoft/autogen`, `crewAIInc/crewAI`, `mastra-ai/mastra`, `cline/cline`. elizaOS/eliza has almost no open issues (likely uses different tracking) — skip.

## continuedev/continue comments work (2026-05-17)
`continuedev/continue` (VS Code AI coding tool) accepts issue comments from Aigen-Protocol account. Issue #12431 comment accepted. Add to working repo list. Focus: MCP transport, session lifecycle, reconnection bugs. High-value target: used by 500k+ developers.

## huggingface/smolagents comments work (2026-05-17)
`huggingface/smolagents` (14k+ stars, HuggingFace official agent framework) accepts issue comments from Aigen-Protocol account. Issue #2117 comment accepted. Add to working repo list. Focus: tool authorization, multi-agent coordination, task-scope guardrails. Issue #2177 (audit trail) is **CLOSED** — don't try to comment. Issue #2117 (pre-tool-call authorization) is open and relevant.

## All-Hands-AI/OpenHands comments work (2026-05-17)
`All-Hands-AI/OpenHands` (50k+ stars, open-source software engineer agent) accepts issue comments from Aigen-Protocol account. Issue #13781 comment accepted (URL redirects to OpenHands/OpenHands). Add to working repo list. Focus: MCP trust verification, task delegation, agent-to-agent security. Issue was stale (40 days, bot flagged) — our comment rescued it from closure.

Working repo list (confirmed 2026-05-17): `openai/openai-agents-python`, `microsoft/autogen`, `crewAIInc/crewAI`, `mastra-ai/mastra`, `cline/cline`, `continuedev/continue`, `huggingface/smolagents`, `All-Hands-AI/OpenHands` (→ `OpenHands/OpenHands`).

## pydantic/pydantic-ai blocked (2026-05-17)
`pydantic/pydantic-ai` returns HTTP 403 "Blocked" for issue comments and issue creation. Do NOT attempt. Add to blocked list alongside langchain-ai/*.

## letta-ai/letta blocked (2026-05-17)
`letta-ai/letta` returns HTTP 403 "Blocked" for issue comments. Do NOT attempt.

## BerriAI/litellm comments work (2026-05-17)
`BerriAI/litellm` (20k+ stars, multi-LLM proxy) accepts issue comments from Aigen-Protocol account. Comment on #28082 accepted. Add to working repo list. Focus: agent cost attribution, routing context propagation, spend tracking bugs — all relevant to our agent-economy work. **Updated working repo list**: `openai/openai-agents-python`, `microsoft/autogen`, `crewAIInc/crewAI`, `mastra-ai/mastra`, `cline/cline`, `continuedev/continue`, `huggingface/smolagents`, `All-Hands-AI/OpenHands`, `BerriAI/litellm`.

## Pattern: agno-agi/agno works for comments (2026-05-17)
First contact via PR #7707 (path safety hardening). Comment posted successfully. Confirmed active repo (20k+ stars, updated daily). Add to rotation for future technical contributions.

## manavaga/agent-seo accepts issue creation (2026-05-18)
Opened issue #1 (their first issue ever — repo had 0). MIT, public, 0 stars but real product (Railway-hosted AgentSEO/0.5 scanner is live + actively scoring MCP servers in production). Author known to engage on awesome-mcp-servers#4880. Confirmed working: Aigen-Protocol account CAN open issues. Add to working repo list. **Operational pattern**: when an external scanner hits us with a unique UA, search GitHub for it — if open-source, opening a constructive issue on THEIR repo is higher leverage than commenting on a generic agent-framework repo. AgentSEO scanned our /performance + /performance/reputation (404 both) — paths they consider standard; documenting their rubric was the natural ask.

## Trust-scoring tools probe specific paths (2026-05-18)
AgentSEO/0.5 probes for: `/openapi.json`, `/llms.txt`, `/.well-known/agent.json`, `/.well-known/mcp.json`, `/docs`, `/health`, plus MCP handshake, plus undocumented `/performance` + `/performance/reputation`. We expose 6/8 of these out of the box (the last two return 404). **Lesson**: trust-scoring scanners assume an emerging set of "discovery surfaces" beyond MCP spec; serving all of them is cheap and pays off in any auto-rubric scoring. Keep llms.txt, openapi.json, .well-known/agent.json, .well-known/mcp.json, /docs, /health permanently 200-OK. /performance might become standard — wait for rubric to materialise before adding it.

## AgenstryBot/0.3.0 probes /.well-known/agent-card.json (Google A2A naming) (2026-05-18)
At 12:33:51Z and again at 14:40:46Z, `35.205.139.4` (GCP Belgium) UA `AgenstryBot/0.3.0 (+https://agenstry.com/bot)` hit `GET /.well-known/agent-card.json` → 404. Agenstry is a trust + routing layer ("23,000+ agents indexed across A2A and MCP", per agenstry.com) — they accept submissions from A2A · MCP · GitHub · npm · PyPI · Docker, and probe agent-card.json (Google A2A v0.2 Agent Card spec naming, distinct from the older `/.well-known/agent.json`). Action taken this run: created `agent-card.json` in repo, staged at `/var/www/html/.well-known-agent-card.json`, added nginx alias block right after `agent.json`, reload, verified 200/6514B. The card is A2A-schema-compliant (`name`, `description`, `url`, `provider`, `version`, `capabilities`, `defaultInputModes/OutputModes`, `skills[]` with id/name/description/tags/examples for all 22 of our MCP tools, `securitySchemes`, `security`), plus an honest `x-aigen` extension declaring `nativeProtocols: ["MCP/1.0","OABP/AIP-1"]` and `a2aCompatibility: "discovery-only"` so consumers know we don't speak A2A wire protocol but list our skills via A2A's naming convention for cross-registry discoverability. **Generalize:** distinct from `agent.json` (older convention). `agent-card.json` is the A2A v0.2 spec name; both should be served if you want indexing in both old-convention scanners (AgentSEO, awesome-mcp lists) AND new A2A-native registries (Agenstry, future Google A2A-spec catalogs). Cost ~10 min, same nginx-alias pattern as glama.json/oabp.json (lesson 52). Next AgenstryBot crawl should 200; track whether they index us within 7 days.
