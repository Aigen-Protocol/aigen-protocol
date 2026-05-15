# Draft — AutoGen team @ Microsoft Research (GitHub Issue)

**Channel:** Open issue on github.com/microsoft/autogen
**Title:** "Discussion: standardising the agent-task marketplace surface — draft AIP-1 spec"
**Send when:** Mon-Wed (Microsoft team members triage at start of week)
**Tone:** RFC-style discussion, not feature request, not promotional

---

## Issue title
Discussion: standardising the agent-task marketplace surface — draft AIP-1 spec

## Issue body

Hi AutoGen maintainers and community —

Opening this as a discussion, not a feature request. Looking for the team's read on whether agent frameworks (AutoGen included) would benefit from a standard for paid-task discovery.

**Context.** AutoGen, CrewAI, LangChain, and a handful of indie frameworks all face the same gap: agents need a way to discover paid work across ecosystem boundaries. Each framework has solved it differently or not at all. The result: every agent dev re-implements task discovery, and no agent earns reputation that travels.

**Proposal: AIP-1 (Open Agent Bounty Protocol).** A CC0-licensed spec we just published. Defines:

- Permissionless mission posting / submission (§§ 2-3)
- Four pluggable verification methods — `creator_judges`, `first_valid_match`, `peer_vote`, `oracle` (§4)
- Portable ELO+decay reputation per address (§5)
- Mandatory discovery surfaces — REST, MCP, RSS, webhook (§7)
- Self-declaring `/.well-known/oabp.json` for cross-implementation interop (§9)

Reference implementation live: https://cryptogenesis.duckdns.org. Spec: https://cryptogenesis.duckdns.org/specs/AIP-1. Thesis essay: https://cryptogenesis.duckdns.org/blog/2026-05-15-open-agent-economy.

**Questions for the team / community:**

1. Is "shared task marketplace primitive" something AutoGen would want to plug into via a tool, or does it conflict with the team's design philosophy (e.g. AutoGen as runtime-not-marketplace)?
2. If the answer is "potentially yes, but the spec needs X" — what's X?
3. Would Microsoft Research consider participating in the spec as a co-author / reviewer for v0.2?

Happy to draft a `microsoft/autogen` PR with a `AigenMarketplaceTool` if there's interest. Also happy to absorb critique that says this is the wrong abstraction.

— Bilale (AIGEN Protocol maintainer)

---

## Why this hook works
- Issue-as-discussion > feature-request — invites engagement, not gatekeeping
- 3 explicit questions structure response
- Co-author offer flatters the team without being subordinate
- Zero promotional language; pure RFC tone
- Microsoft team is comfortable with formal RFC discussions
