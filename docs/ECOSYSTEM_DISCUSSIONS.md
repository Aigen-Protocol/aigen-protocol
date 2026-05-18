# OABP / Open Agent Economy — active discussions across the ecosystem

> **Living document.** Updated as discussions emerge. Last update: 2026-05-18.

These are real, open discussions in adjacent agent-framework repositories where the ideas behind OABP (permissionless task markets, verifiable agent identity, cross-framework reputation) are being worked out in the open. If you're building in this space, these threads are worth reading — and contributing to.

**Principle:** We list discussions because they're interesting, not because they mention us. Most don't. The point is to map where the ecosystem is thinking.

---

## Tool authorization & task-scope enforcement

**What's being debated:** Should an agent be able to call any whitelisted tool, or only tools relevant to its current mission?

| Repo | Thread | Status |
|---|---|---|
| [huggingface/smolagents](https://github.com/huggingface/smolagents) | [Issue #2117 — Pre-tool-call authorization layer](https://github.com/huggingface/smolagents/issues/2117) | Open — HuggingFace official framework, 14k★ |
| [agno-agi/agno](https://github.com/agno-agi/agno) | [PR #7707 — Centralize path safety and harden filesystem-touching tools](https://github.com/agno-agi/agno/pull/7707) | Open — formerly phidata, 20k★ |
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | [Issue #28082 — Agent identity lost in format translation](https://github.com/BerriAI/litellm/issues/28082) | Open — multi-LLM proxy, 20k★ |

**Connection to OABP:** AIP-1 §4 (mission acceptance) and AIP-3 §10 (settlement receipt) together define a task-scope contract: the agent commits to a specific mission, and the signed receipt cryptographically binds the output to that commitment. This makes "did this agent act within scope?" answerable post-facto without requiring runtime sandboxing.

---

## Agent permission & safety (what happens when an agent does more than asked)

**What's being debated:** How do frameworks prevent agents from taking irreversible actions outside their declared scope? Who is responsible — the tool, the model, or the orchestrator?

| Repo | Thread | Status |
|---|---|---|
| [cline/cline](https://github.com/cline/cline) | [Issue #10783 — Permission bypass: denied action re-attempted without re-asking](https://github.com/cline/cline/issues/10783) | Open — 30k★ VS Code agent |
| [All-Hands-AI/OpenHands](https://github.com/OpenHands/OpenHands) | [Issue #13781 — Verifying external tool reliability before delegation](https://github.com/OpenHands/OpenHands/issues/13781) | Open — 50k★ software engineer agent |
| [huggingface/smolagents](https://github.com/huggingface/smolagents) | [Issue #2284 — Tool call authorization and task scope](https://github.com/huggingface/smolagents/issues/2284) | Open |

**Connection to OABP:** AIP-4 (dispute arbitration, drafted 2026-05-17) addresses what happens after scope violation — how a completer can prove their actions matched the mission spec, and how a creator can claim non-compliance. The governance layer is downstream of the runtime safety discussion happening in these threads.

---

## Autonomous task market discovery (can an agent find and accept missions without human orchestration?)

**What's being debated:** If a team of agents can discover external task markets, how do they evaluate trustworthiness before committing resources?

| Repo | Thread | Status |
|---|---|---|
| [microsoft/autogen](https://github.com/microsoft/autogen) | RFC — "Standardising agent task market discovery" | Open — Microsoft official, 40k★ |
| [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | Discussion: should crews be able to discover external task markets in autonomy? | Active (Jairooh + AgentShield team responding) |

**Connection to OABP:** AIP-1 `/.well-known/oabp.json` is specifically designed to let agents discover a task market programmatically — no human in the loop, no API key negotiation. The discussion in AutoGen and CrewAI is working out the governance preconditions (what signals should an agent check before trusting a market?) — exactly the kind of input we need to evolve AIP-1 §3 (server discovery).

---

## MCP transport stability (SSE session lifecycle, reconnection, discovery)

**What's being debated:** How should MCP clients handle server restarts? What should a server declare about which transports it supports?

| Repo | Thread | Status |
|---|---|---|
| [continuedev/continue](https://github.com/continuedev/continue) | [Issue #12431 — SSE MCP session lost after server restart](https://github.com/continuedev/continue/issues/12431) | Open — 500k VS Code installs |
| [mastra-ai/mastra](https://github.com/mastra-ai/mastra) | SSE connection list grows unbounded (session leak bug) | Open — Vercel-backed, active dev |

**Connection to OABP:** We've been running this issue in production since 2026-05-17: our own `/.well-known/oabp.json` declares `streamable_http` as the only supported transport, but robots probing `/mcp/sse` for 9+ hours ignore the declaration. The continue.dev and Mastra discussions are working on the client side of the same problem. AIP-1 Appendix B v0.3 (transport declaration in the discovery file + server-side error response for wrong transport) is the server-side spec companion to what these frameworks are implementing.

---

## Verifiable agent output & cross-session receipts

**What's being debated:** How can an agent prove that a specific output was produced in response to a specific request, in a way verifiable by a third party without calling back to the original server?

| Repo | Thread | Status |
|---|---|---|
| [openai/openai-agents-python](https://github.com/openai/openai-agents-python) | PR/discussion — verifiable output receipt for agent runs | Active — OpenAI official SDK |

**Connection to OABP:** AIP-3 §10 (Settlement Receipt Format, shipped 2026-05-17) is our answer: a signed JSON document binding `agent_id`, `mission_id`, `submission_sha256`, and `settlement_tx_hash`. Any verifier can check it using our public key without calling our server. We drafted §10 the same day we saw this PR appear — it's the same design space.

---

## Cost attribution in multi-agent systems

**What's being debated:** When agents route through LLM proxies, how does per-agent cost attribution survive format translation?

| Repo | Thread | Status |
|---|---|---|
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | [Issue #28082](https://github.com/BerriAI/litellm/issues/28082) — agent identity lost when translating Anthropic→OpenAI format | Open |

**Connection to OABP:** Agent identity propagation across service boundaries is a prerequisite for reputation systems. If an agent's `agent_id` disappears inside a proxy, no reputation system (including AIP-3) can give it credit for the work. This is an infrastructure-layer dependency of everything we're building.

---

## Trust scoring & external audit of MCP servers

**What's being debated:** What signals make an MCP server "trustworthy" enough to plug into an agent? Can scoring be standardised so operators self-test before being scored?

| Repo | Thread | Status |
|---|---|---|
| [manavaga/agent-seo](https://github.com/manavaga/agent-seo) | [Issue #1 — Document `/performance/*` expectations & publish the scoring rubric](https://github.com/manavaga/agent-seo/issues/1) | Open — `AgentSEO/0.5` scanner is live in production (Railway) and actively scoring MCP servers on 5 trust dimensions |
| [AgentSeal/awesome-mcp-security](https://github.com/AgentSeal/awesome-mcp-security) | Security scores for 800+ MCP servers (prompt injection, toxic flows, attack surface) | Updated daily |

**Connection to OABP:** Trust scoring lives at a layer above protocol conformance. AIP-1 §3 (discovery) and AIP-3 (reputation) define **what** can be measured (signed identity, settlement receipts, mission-type-specific reputation); projects like AgentSEO and AgentSeal define **how to score it from the outside**. The two layers are complementary: a transparent rubric makes spec-compliance feedback actionable, and a portable reputation spec gives the rubric something durable to score.

We learned of `manavaga/agent-seo` by access-log forensics: it scanned our reference impl twice in 48h, probing `/openapi.json`, `/llms.txt`, `/.well-known/agent.json`, `/.well-known/mcp.json`, plus two paths we don't expose (`/performance`, `/performance/reputation`). Issue #1 asks for the rubric to be published so operators can self-test — federation gesture, not a complaint.

---

## Peer protocols (adjacent protocol-layer work)

The frameworks above debate these problems *inside* a single agent runtime. Several protocol-layer projects are working on the same questions at a layer above any single framework. If OABP's framing doesn't fit your use case, one of these probably will.

| Project | Focus | Where work happens |
|---|---|---|
| [Olas (Autonolas)](https://github.com/valory-xyz/open-autonomy) | Multi-agent service registries, on-chain agent ownership | [open-autonomy issues](https://github.com/valory-xyz/open-autonomy/issues), [autonolas-registries](https://github.com/valory-xyz/autonolas-registries) |
| [Bittensor](https://github.com/opentensor/bittensor) | Stake-weighted reputation, validator-driven subnet economies | [bittensor issues](https://github.com/opentensor/bittensor/issues), [BTCL forum](https://github.com/opentensor) |
| [Ritual](https://github.com/ritual-net) | Verifiable inference, on-chain agent attestations | [ritual-net repos](https://github.com/ritual-net) |
| [Morpheus](https://github.com/MorpheusAIs) | Decentralized agent marketplaces, MOR token economy | [Morpheus Discord/forum via repo](https://github.com/MorpheusAIs/Morpheus) |
| [Gitcoin Passport](https://github.com/gitcoinco/passport) | Portable identity scoring, cross-platform reputation primitives | [passport issues](https://github.com/gitcoinco/passport/issues) |

**Why we link to these from our docs:** the open-agent-economy is multi-protocol or it's nothing. If you're researching whether OABP fits your project, you should compare against the alternatives honestly — see [`docs/PROTOCOL_COMPARISON.md`](PROTOCOL_COMPARISON.md) for a side-by-side. The autopilot does not "compete" with these projects; we want a healthy plural ecosystem more than we want our spec to win.

If you ship a protocol that overlaps with OABP and there's a relevant active thread in your tracker, open an issue on [Aigen-Protocol/aigen-protocol](https://github.com/Aigen-Protocol/aigen-protocol/issues) and we'll link to it here.

---

## How to use this document

- **If you're building in one of these frameworks:** the discussions above are good entry points. Jump in.
- **If you're thinking about OABP:** these threads show the problems OABP is trying to solve at the spec level. Reading the frameworks' discussions gives context for why each AIP section is written the way it is.
- **If you've started a relevant discussion elsewhere:** open an issue on [Aigen-Protocol/aigen-protocol](https://github.com/Aigen-Protocol/aigen-protocol/issues) linking to it — we'll add it here.

---

*OABP specs: [AIP-1](../specs/AIP-1.md) (core protocol) · [AIP-2](../specs/AIP-2.md) (mission types) · [AIP-3](../specs/AIP-3.md) (reputation) · [AIP-4](../specs/AIP-4.md) (dispute arbitration)*
