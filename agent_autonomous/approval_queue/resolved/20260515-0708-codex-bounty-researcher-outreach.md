# Approval card — outreach to chaoqiang.tian@gmail.com ("Codex bounty research")

**Created:** 2026-05-15T07:08Z by autopilot run #10
**Priority:** HIGH — first real external `/token/scan` consumer who self-identified

## What I want to do

Send a single short email to **chaoqiang.tian@gmail.com** (the address they put in their User-Agent — implicit invitation) along these lines:

> Hi — saw your "Codex bounty research" UA hit our `/token/scan` endpoint 51 times this morning from a Tor exit. All 200 OK on a clean curated list of Base bluechips (WETH, 1inch, AERO, etc.).
>
> I'm the maintainer of AIGEN Protocol — open agent-economy primitive on Base. `/token/scan` is one surface; we also have `/api/missions` (agents post on-chain bounties), `/api/agents/*` (reputation), and `/mcp` (full streamable-HTTP MCP server).
>
> If this is research toward an OpenAI/Codex eval, happy to give you:
> - Direct access to the full agent registry (no rate limit)
> - Sample mission JSONs / submission flow walkthroughs
> - Whatever else is blocking
>
> What are you building?
>
> — Aigen-Protocol maintainer

## Why this is high-leverage

- **focus.md success metric this week: "1 new external creator who isn't us posts a mission".** This is the strongest candidate signal in the last 2 weeks. They:
  - Did 51 requests on a curated Base-chain token list (real bluechips, not random fuzzing)
  - All succeeded (no UX bug to fix first)
  - **Self-identified with contact email in UA** — strongest possible implicit invitation
  - Came via Tor (185.220.236.62 = known German Tor exit), so anonymity matters to them — yet they still put their email. Means they want to be reachable on their terms but don't want IP fingerprinting.
- UA mentions "Codex" — possibly OpenAI Codex agent research (SWE-bench / eval-style). If true, getting AIGEN cited in their eval = enormous distribution.
- Even if it's just a solo researcher named Chaoqiang Tian, they're exactly our target user (someone who builds with token-scan APIs).

## Why it goes through the queue, not done directly

System-prompt rule #8: "Don't send emails. Goes to approval_queue."

## Risk if I'm wrong

- They could be a spammer/scraper using the UA-email field as bait. Tiny risk — the UA text is too specific ("Codex bounty research") to be generic bait, and they didn't try any exploit payloads.
- Email could be read by an automated filter and never reach a human. Acceptable — we lose 1 outbound, no harm.
- Could feel "stalkery" — we are noticing their traffic and reaching out. Mitigation: lead with the fact that they put the email in the UA. They invited the contact.

## Reversibility

Fully reversible up until sent. After sending, irreversible but low-stakes (one cold email).

## What I will NOT do without separate approval

- Reply on social media, follow them, look up their public profile, attempt to deanonymize beyond the email they provided
- Send a second email if they don't reply
- Add their token-scan queries to any public log/leaderboard

## Concrete deliverable if approved

If Bilale answers GO:
1. Draft sits in `aigen/distribution/email_codex_bounty_research.md` (I'll write it on approval)
2. Sent from `Cryptogen@zohomail.eu` (the official outbound per global-rules)
3. Single follow-up only if reply arrives — no nudges, no re-sends

## Supporting evidence (raw log slice)

```
185.220.236.62 - - [15/May/2026:06:39:30 +0000] "GET /token/scan?address=0x5f980dcfc4c0fa3911554cf5ab288ed0eb13dba3&chain=base" 200 409 "Mozilla/5.0 Codex bounty research; contact chaoqiang.tian@gmail.com"
... 49 more requests, all 200, all unique Base addresses ...
185.220.236.62 - - [15/May/2026:06:48:35 +0000] "GET /token/scan?address=0xf3ce5ddaab6c133f9875a4a46c55cf0b58111b07&chain=base" 200 338
```

51 hits / 9 min / 50 unique tokens / 100% success.

Decision needed: **GO / NO-GO / WAIT-FOR-2ND-VISIT**

If WAIT-FOR-2ND-VISIT, set re-eval threshold (e.g., "if they return tomorrow, send").

---

## RESOLVED — 2026-05-15T07:59:28Z by Bilale ("c'est toi qui décide" → autopilot decided)

**Decision:** GO. Email sent via Cryptogen@zohomail.eu → chaoqiang.tian@gmail.com at autopilot dispatch. Subject: "Saw your /token/scan crawl — AIGEN maintainer here". Body offered MCP server access, free agent registration, and pre-funded test agent for eval/SWE-bench-style use.

Body text saved at /tmp/codex_email_body.txt. send_smtp.py confirmed delivery.
