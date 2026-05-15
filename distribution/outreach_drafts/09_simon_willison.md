# Draft — Simon Willison (independent, prolific dev-blogger)

**Channel:** X DM → [@simonw](https://x.com/simonw)
**Fallback:** Email simon@simonwillison.net (public on his blog)
**Send when:** Mon-Wed mornings ET
**Tone:** builder-to-builder, technical, "would you sniff-test this"

---

## Message

Hi Simon —

Your MCP coverage in Oct/Nov 2025 drove most of the tooling I've seen built since. Wanted to flag a thing in case it's interesting:

Just published AIP-1 — a CC0 spec for an open agent bounty protocol. MCP-native by default (§7 makes MCP a primary discovery surface). Reference implementation has 45 MCP tools live, including a streamable-HTTP transport that implements the session-ID anti-CSRF gate correctly (a thing several MCP clients in the wild are getting wrong — empirical data in our autopilot journal: https://cryptogenesis.duckdns.org/journal).

The piece I'd value your sniff test on is §7 — discovery surfaces. AIP-1 mandates ≥3 of: REST, MCP, RSS, webhook, sitemap. The MCP requirement is opinionated; would you push it harder ("MCP MUST be one of the three")? Or push softer ("MCP SHOULD be one of the three"), allowing pure-REST implementations?

Spec: https://cryptogenesis.duckdns.org/specs/AIP-1
Thesis: https://cryptogenesis.duckdns.org/blog/2026-05-15-open-agent-economy

If it's blog-worthy, ship it. If not, the technical critique is enough on its own.

— Bilale (AIGEN Protocol)
Cryptogen@zohomail.eu

---

## Why this hook works
- Praises specific past work (his MCP coverage) without sycophancy
- Shows we've done our homework (session-ID anti-CSRF gate observation)
- Live data link (autopilot journal) gives him something to verify
- Specific opinionated question (MUST vs SHOULD) — short answer possible
- Explicit blog-worthy escape hatch — he writes about what he writes about, no pressure
- Simon is one of the most thoughtful tech writers; if he covers AIP-1, that's 10K+ engineers reached
