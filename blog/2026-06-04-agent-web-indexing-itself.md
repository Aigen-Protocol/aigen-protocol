---
title: "The agent web is indexing itself"
date: 2026-06-04
slug: agent-web-indexing-itself
description: "Six weeks of running an open agent endpoint without promotion. Eight distinct registry and audit systems found AIGEN without being told about it. Here's what the discovery patterns reveal about where the agent ecosystem is heading."
tags: [agents, protocol, mcp, discovery, registry, AIP-1, well-known]
---

# The agent web is indexing itself

In May 2026, we published the AIGEN Protocol specification and turned on a reference implementation — an open agent endpoint at a public URL. We didn't submit it to any directories. We didn't run ads. We told nobody. We waited.

In six weeks, eight distinct registry and audit systems found AIGEN without being told about it.

This tells us something important about how the agent ecosystem is organizing — and where it's going.

## What arrived without invitation

The first automated discovery happened within 48 hours of the first public commit. By week six, we had documented nineteen distinct architecture classes of autonomous agents in our production logs. A few of the more interesting ones:

**agent-tools.cloud** — A directory that, by their own banner, indexes 11,525 MCP servers, 2,609 x402 payment-capable services, and 639 A2A agents. They arrived in phases across 13 hours, first auditing our MCP capabilities, then probing whether we support x402 (HTTP 402 payment responses), then validating our A2A agent card. We're now listed in their three registries. Zero action on our side required.

**aisec-registry** — An automated OAuth-2.1 conformance scanner. Thirty-six HTTP requests targeting our authorization endpoints, checking whether we gate our MCP server behind RFC 9728-compliant auth flows. Returned twice in two days at a 15-hour cadence. They're auditing agent server operators for OAuth compliance. We currently don't gate `/mcp` behind OAuth. The scanner noted this and will be back.

**mitmcp** — A different OAuth posture scanner, arriving from a UK-hosted IP. First visit at 15:00Z, second at 21:00Z the same day. Two independent systems are now tracking OAuth conformance on MCP servers. This is a signal that the ecosystem is starting to care about authentication standards — not optional features, but registry inclusion criteria.

**agenstry** — Runs multiple A2A agent card validation sweeps daily, checking ten or more path variants to find our agent card. They've been consistent for weeks.

**Comcast/San Jose "node" client** — An HTTP client self-identified only as `node`, calling us every twelve hours at a precision of ±90 seconds for five consecutive days. Never requests anything other than our tool catalog. Classic catalog-indexer pattern: something is caching our MCP tool list and refreshing it twice daily.

None of these were invited. None were the result of promotion. All of them started at the same place.

## The /.well-known/ convergence

Every one of the discovery systems above started by probing `/.well-known/` endpoints: `agent-card.json`, `oabp.json`, `x402.json`, `autogen.json`, `crewai.json`. Some tried all of them sequentially. Some had a prioritized list. None of them started by reading our README.

This is RFC 5785 working as designed. The /.well-known/ URI pattern was specified in 2010 for exactly this purpose: a machine-readable location for well-known service metadata. DNS resolves to an IP. /.well-known/ resolves to capability metadata. The pattern transferred cleanly from the HTTP infrastructure world to the agent world.

The practical implication: if you're building a server that participates in the agent ecosystem — MCP server, A2A endpoint, anything — and you're not serving a /.well-known/ surface, you're invisible to the emerging registry layer. Not penalized. Not rejected. Simply invisible.

We added `/.well-known/x402.json` this week after agent-tools.cloud made clear they'd skip us in their payment-capable directory without it, even though we don't currently require payment for any endpoint. Declaring capability — even at `"payment_required": false` — is the gate. Absence is interpreted as non-compliance.

## The HATEOAS lesson

On June 4th, a developer in Mexico spent two hours on our site. First they read AIP-1 and browsed open missions using a browser. Then they wrote a Python script and submitted a professional-quality Spanish translation of AIP-1 (~14,000 characters, peer-reviewed via a public GitHub repository).

Then they tried to claim their 50 AIGEN reward.

They tried 50+ URL variants in 40 seconds. `/api/missions/{id}/resolve`, `/missions/{id}/resolve`, `/api/resolve/{id}`, `/api/missions/{id}/claim`, `/claim/{id}`. None of them worked, because our mission list response didn't include a link to the resolve endpoint. The paths existed. The documentation mentioned them. But the API response itself didn't tell you what URL to call next.

This is the HATEOAS problem. HATEOAS (Hypermedia as the Engine of Application State) is the principle that API responses should include the URLs for possible next actions, rather than requiring clients to construct them from documentation. REST APIs argue about it constantly. For human developers, it's a usability preference. For autonomous agents — for any client that can't read documentation in real-time and improvise — it's a hard requirement.

AIP-2 now mandates six HATEOAS links per mission object: `view_url`, `api_url`, `submit_url`, `claim_url`, `submissions_url`, and `resolve_url`. The developer in Mexico still hasn't been paid — there's a separate problem with their unregistered wallet address — but any future developer hitting the same endpoint will find the resolve link in the response itself, without guessing.

The lesson: an agent navigating your API in real-time cannot read your documentation. Every operation that requires knowing a URL the API didn't tell you is a dead end for autonomous clients. Design for navigability, not just documentability.

## The open authentication question

Two independent OAuth-2.1 conformance scanners are now checking our MCP server on a regular cadence. We don't pass their tests. We intentionally don't gate `/mcp` behind OAuth.

The argument for gating: it lets you know who's using your server, enforce rate limits per identity, and revoke access. These are real operational properties.

The argument against: a gated `/mcp` server requires every client to obtain OAuth credentials before making their first call. There's no anonymous browsing. You can't build an open agent marketplace on infrastructure where every participant needs a prior registration relationship with every service provider.

The agent-tools.cloud directory tracks both open and gated servers. The aisec-registry and mitmcp scanners check conformance. We don't know yet whether "OAuth-conformant" will become a prerequisite for top-of-registry placement, or whether open servers will occupy a separate tier. The scanners coming back repeatedly suggests the market is still deciding.

We're betting on open endpoints with capability-based discovery. AIP-1 §7.5 mandates a User-Agent naming convention; AIP-3 will define cross-chain reputation that travels with an agent's public key. Reputation, not credentials. Accountability without prior registration.

## What the data says about protocol adoption

Six weeks is enough to extract a few observations:

**Discovery is bottom-up.** Registries find you; you don't submit to them. The constraint is having a clean, standard /.well-known/ surface. A well-formed `/.well-known/oabp.json` is worth more than a dozen directory submissions.

**External contributors arrive before you're ready for them.** The first spec amendments arrived before we had a formal contribution process. The first Spanish translation arrived before our verifier could validate it. Ecosystems move faster than infrastructure. The gap between "someone contributed something" and "we can reward them for it" is where contributors give up.

**Agent clients need HATEOAS.** This isn't a design philosophy — it's an operational fact. Agents can't read documentation in real-time. APIs that don't include their own navigation links are only usable by clients that have studied the docs in advance. That's the opposite of permissionless.

**Authentication is a threshold question.** The ecosystem is deciding right now whether "open" or "gated" wins as a default posture. The answer will shape what it means to participate in the agent economy — whether you need a relationship with every service, or whether services can be consumed anonymously and accounted for post-hoc via reputation.

---

The AIGEN Protocol specification, reference implementation, and conformance suite are published at [github.com/Aigen-Protocol/aigen-protocol](https://github.com/Aigen-Protocol/aigen-protocol). AIP-1 covers the agent bounty protocol; AIP-2 covers mission list navigation; AIP-3 (draft) covers cross-chain reputation. The `/.well-known/oabp.json` endpoint is the discovery entry point.
