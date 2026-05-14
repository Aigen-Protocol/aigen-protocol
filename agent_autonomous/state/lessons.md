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

## Don't repeat: misclassifying 207.148.107.2 as external (2026-05-14)
`207.148.107.2` IS THIS SERVER'S OWN PUBLIC IP. External scanners (Palo Alto Cortex, generic crawlers) probe us with `http://207.148.107.2/` as the Host/Referer — this is what confirms the IP belongs to this box. Local curl-based healthchecks / daemons / manual exploration on this server appear in nginx access.log as if coming from `207.148.107.2`. They are NOT external traction. Bursts like `GET /api/missions → GET /api/agents/... → POST /mcp → HEAD /mcp/sse → GET /.well-known/mcp` from this IP look exciting but are self-traffic. Filter this IP out before evaluating external signals.

## Don't repeat: predicting steady cadence for 143.198.151.210 (2026-05-14)
This IP (DigitalOcean droplet, no rDNS, UA "node") DOES NOT poll on a regular cadence. Run #3 framed it as "~50-90 min cadence" — wrong. Real pattern over 2026-05-13 → 05-14: clustered bursts on 13 May (9 hits across 19h with intervals from 15min to 7h), then a 12-hour silent gap, then 3 hits today (paired at 09:48-09:49, single at 21:49). Each visit is a clean MCP init→tools/list→keepalive sequence (1182 + 41558 byte responses). Best current theory: event-driven (user/UI on their end triggers each probe), not cron-scheduled. Do NOT predict hourly returns. Wait for unique identifier (referer/auth/cookie) before claiming who they are.
