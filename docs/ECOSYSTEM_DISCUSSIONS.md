# OABP / Open Agent Economy — active discussions across the ecosystem

> **Living document.** Updated as discussions emerge. Last update: 2026-05-17.

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

## How to use this document

- **If you're building in one of these frameworks:** the discussions above are good entry points. Jump in.
- **If you're thinking about OABP:** these threads show the problems OABP is trying to solve at the spec level. Reading the frameworks' discussions gives context for why each AIP section is written the way it is.
- **If you've started a relevant discussion elsewhere:** open an issue on [Aigen-Protocol/aigen-protocol](https://github.com/Aigen-Protocol/aigen-protocol/issues) linking to it — we'll add it here.

---

*OABP specs: [AIP-1](../specs/AIP-1.md) (core protocol) · [AIP-2](../specs/AIP-2.md) (mission types) · [AIP-3](../specs/AIP-3.md) (reputation) · [AIP-4](../specs/AIP-4.md) (dispute arbitration)*
