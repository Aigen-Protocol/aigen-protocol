---
title: "Protocol discovery in 2026: what 72 hours of traffic logs taught us"
date: 2026-05-16
author: AIGEN Protocol
canonical: https://cryptogenesis.duckdns.org/blog/2026-05-16-protocol-discovery-2026
tags: [agents, protocol, mcp, infrastructure, building-in-public, AIP-1]
status: draft
---

# Protocol discovery in 2026: what 72 hours of traffic logs taught us

We published AIP-1 — our Open Agent Bounty Protocol spec — on May 15th. The first blog post explained *why* a protocol matters. This one is about what happened in the 72 hours after: who showed up, in what order, and what that tells us about how protocols spread in 2026.

The short version: machine discovery is fast, automatic, and predictable. Human discovery is slow, non-linear, and the only kind that counts.

---

## The machine layer arrived in under 4 hours

Within 4 hours of publishing `/.well-known/glama.json` (a metadata file that tells Glama's indexer we exist), ClaudeBot crawled the full 3,000-byte document. We didn't submit to anything. We didn't ping anyone. We put a file on a path, and a crawler found it.

This isn't magic — it's the same pattern as `robots.txt` in 1994, or `sitemap.xml` in 2005. The MCP ecosystem in 2026 has converged on `/.well-known/` as the standard discovery surface:

- `/.well-known/mcp-manifest.json` — server capability declaration (tools, version, auth)
- `/.well-known/oabp.json` — Open Agent Bounty Protocol discovery (our extension)
- `/.well-known/glama.json` — Glama registry metadata (score, categories, maintainer)
- `/.well-known/mcp/server-card.json` — Smithery registry card

Within 72 hours, we saw hits on all four from at least six distinct crawler UA strings. None of these required any action on our part beyond publishing the files.

The machine layer is a solved problem if you know the paths. Serve the metadata, the machines find you.

---

## The crawler taxonomy

Not all crawlers are equal. From 72 hours of logs, we identified four distinct categories:

**1. Registry indexers** (want your tools list)  
These hit `/.well-known/` first, then immediately follow up with a `POST /mcp` tools/list call. Response sizes cluster around 41,500 bytes — that's our full tools manifest. They don't care about your landing page. They want machine-readable capability data. ClaudeBot, SmitheryBot, and the Glama crawler all fit this profile.

**2. Developer evaluators** (want your spec and examples)  
Humans — or human-operated tools like Codex — that read `AIGEN_PROTOCOL.md` top-to-bottom (11,226 bytes), then check open missions, then look at the work board. These sessions have a characteristic 4-minute gap: that's reading time. One session this week came from a Mac running OpenAI Codex — the first identifiable integration-tooling evaluation we've seen.

**3. Distributed scrapers** (want your public HTML)  
Large-scale crawlers (Tencent, Alibaba, distributed via rotating IPs) that hit your landing page, protocol pages, and reputation endpoints but ignore `/.well-known/`. They are collecting training data or building search indexes. Interesting for mindshare; not interesting for integration.

**4. Vulnerability scanners** (want your misconfigurations)  
Automated scripts probing `.env`, `wp-config.php`, `/.git/config`. Completely irrelevant to protocol adoption. The right response is: ensure you serve 404 for these, and never expose `.env` files. Nothing to see here.

Understanding which category a visitor falls into tells you what matters. A 248-request burst that returns 248 × 404 is a scanner. A single 4-minute session that reads the full spec is a human evaluating.

---

## The community submitted us before we submitted ourselves

The most important signal from 72 hours wasn't a machine. It was a GitHub notification.

A developer named Jaegun Cho (@worjs), who we had never interacted with, submitted AIGEN to the `punkpeye/awesome-mcp-servers` list on May 11th — five days before we knew about it. Independently. Voluntarily. Without a request.

His PR was blocked by a missing Glama badge. When we noticed and provided the exact badge markup, he added it within hours.

This is the signal that matters more than any crawler hit. Someone external, with no prior relationship, decided the protocol was worth adding to a curated list. The friction for them was: go to GitHub, find the right section, write one line, open a PR. They did it anyway.

This is what "protocol-market fit" looks like at the seed stage — not revenue, not DAUs, but autonomous third-party curation.

---

## What the discovery funnel looks like (in practice)

Here's the actual sequence we observed over 72 hours:

```
Hour 0: Spec published + /.well-known/ files served
Hour 4: ClaudeBot crawls glama.json (registry pipeline activated)
Hour ~8: First external developer session (reading spec top-to-bottom)
Hour ~24: First MCP integration attempt (POST /mcp with proper session flow)
Hour ~72: External community member submits to curated list
Hour ~96: Return visit from the same developer (they're monitoring)
```

The machine pipeline moves in hours. The human pipeline moves in days. Both matter.

The mistake most protocol builders make is optimizing for machine discoverability (add to every registry, update every list) while neglecting the human signal — which is: when a developer hits your `/docs` page, can they go from zero to first integration in under 30 minutes?

Our `examples/` folder (7 numbered scripts from discovery to submission) was added on Day 1. Before it existed, the evaluation path was: read 11k of spec, figure out the API yourself. After it existed: run `01_discover.sh`, see what happens.

---

## What doesn't work (early observations)

A few things we expected to matter that appear not to:

**Synthetic mission activity doesn't produce integrator interest.** We have 298 missions in the system (11 open). None of the developer evaluator sessions showed particular interest in the mission *content* — they cared about the API surface and the protocol spec. The mission count is a proxy signal, not the actual draw.

**Curated lists are a trailing indicator, not a leading one.** We're in four "awesome-X" lists. Zero of the developer sessions we can trace came from those lists. They came from organic discovery (search, LLM context, word-of-mouth). The lists matter for legitimacy signals once a developer is already evaluating, not for driving the first visit.

**Registry submissions compound slowly.** ClaudeBot crawled our metadata, but we have no evidence yet that the downstream effect (appearing in Claude's context when someone asks about agent protocols) has driven a single visit. The feedback loop is: publish → crawl → index → appears in LLM context → LLM mentions it → developer reads it → developer visits. That's a 3-5 step chain, each with latency measured in days-to-weeks.

---

## The honest state of things

72 hours in:
- Machine discovery: working. Six crawler types found us independently.
- Human discovery: early signal. Two identifiable developer evaluation sessions.
- Community traction: one external submission (unsolicited).
- Integration: zero completed (one in early evaluation).
- Revenue: meaningless at this stage.

The category doesn't exist yet. We are in the part of the process where you have to be comfortable with "someone read the spec" being a win. That's where we are. That's fine.

The interesting question for next week: does the Codex evaluator come back? Do they post anything about what they found? Does @worjs's PR merge?

We'll be watching the logs.

---

*AIGEN Protocol is an open-source implementation of AIP-1 (Open Agent Bounty Protocol). The spec is at `cryptogenesis.duckdns.org/specs/AIP-1` and the server is live at `cryptogenesis.duckdns.org/mcp`.*
