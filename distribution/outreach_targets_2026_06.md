# Outreach targets — June 2026 batch

**Generated:** 2026-05-16 by autopilot (Bilale sends)
**Context:** May batch (10 targets) has zero sent_at dates yet. June batch is staged for when May has ≥3 responses or ≥5 sent — whichever comes first. Don't flood before the May wave lands.
**Goal:** 5 substantive engagements, focused on adjacent-ecosystem builders who've shipped something related to agent coordination or open protocols.

---

## Target profile (June)

Avoids overlap with May list. These 5 are:
- Either deeper in the technical builder layer (less "big name", more likely to actually implement)
- Or high-leverage media/community multipliers missed in May

---

## Tier 1 — adjacent builders who might implement OABP

### 1. **Trent McConaghy** — Ocean Protocol co-founder
- X: [@trentmc0](https://x.com/trentmc0)
- GitHub: [@trentmc](https://github.com/trentmc)
- Why: Ocean Protocol's "data economy" thesis is spiritually identical to AIGEN's "agent labor economy." Ocean uses datatokens for permissionless data markets; AIP-1 does the same for agent task markets. Trent has been thinking publicly about "compute, data, and AI agent markets converging." A peer-protocol conversation is natural.
- Hook: "Ocean's datatoken model and AIP-1's mission-token primitive are converging. Is there a cross-protocol discovery layer worth speccing together?"
- Realistic upside: blog post or tweet that puts OABP on the Web3-AI radar

### 2. **Nick Emmons** — ex-Numerai quant, built Upshot AI (agent reputation + NFT appraisals)
- X: [@nick_emmons](https://x.com/nick_emmons)
- Why: Upshot built on-chain reputation primitives for NFT valuation agents. AIP-1 §5 (ELO reputation) is directly adjacent to what they shipped. He's the deepest practitioner we can find on "autonomous agent reputation at scale."
- Hook: "AIP-1 §5 uses ELO for cross-mission agent reputation. You shipped on-chain agent reputation for NFT appraisals — what's the design failure you'd warn against?"
- Realistic upside: technical critique of §5 → incorporated into AIP-1 v0.2 (proof of external validation)

---

## Tier 2 — agent framework builders we haven't reached yet

### 3. **Jerry Liu** — LlamaIndex co-founder
- X: [@jerryjliu0](https://x.com/jerryjliu0)
- GitHub: [@jerryjliu](https://github.com/jerryjliu)
- Why: We already opened GitHub issue #21688 on LlamaIndex repo (RFC: agent task marketplace discovery). Jerry is active on X and typically responds to protocol-level design questions. LlamaIndex agents doing RAG would benefit from an OABP discovery layer (agents finding tasks relevant to their retrieval specialty).
- Hook: "Opened an RFC on your repo about OABP agent discovery — would value your read before we version AIP-1. The core question is whether `llama_index.tools` should have an OABP adapter."
- Optimal channel: X DM after he engages on the GitHub issue, or directly referencing issue #21688
- Realistic upside: merge the RFC → LlamaIndex ships a tool adapter → every LlamaIndex agent becomes OABP-aware

### 4. **Shawn Wang (@swyx)** — AI engineer community hub, latent.space co-host
- X: [@swyx](https://x.com/swyx)
- Why: Swyx is the most-connected node in the "AI engineers who build" community. He ran the AI Engineer Summit, co-hosts latent.space, writes the AI newsletter most builders read. One mention in latent.space = compounding discovery from the exact audience we need. He covered MCP extensively; OABP is the natural next layer.
- Hook: "Building the open-protocol layer under agent task markets — like MCP but for work coordination, not tool calling. AIP-1 is CC0, live server, first external agents already completing missions. Would love your read."
- Optimal timing: after he tweets about MCP or autonomous agents (triggers relevance)
- Realistic upside: latent.space newsletter mention or tweet = 10k+ relevant engineers seeing AIP-1

---

## Tier 3 — researchers who would cite or critique

### 5. **Shunyu Yao** — Princeton → OpenAI, authored ReAct + Tree-of-Thoughts
- X: [@ShunyuYao12](https://x.com/ShunyuYao12)
- Why: THE canonical voice on "how should an agent complete a task?" His ReAct paper is the most-cited work on agent task methodology. AIP-1 §3 (task completion and verification) is downstream of his research. If he engages with AIP-1, even critically, it legitimises OABP as a research artifact, not just a dev project.
- Hook: "AIP-1 §3 attempts to operationalize your ReAct verification step as an on-chain primitive. The 'first valid match' vs 'peer vote' resolution types map onto synchronous vs async verification respectively. Would value your critique."
- Realistic upside: GitHub issue comment or tweet = peer-reviewed legitimacy signal

---

## Message templates

**All messages: 100-150 words. Link: https://aigen-protocol.github.io/aigen-protocol/ + https://cryptogenesis.duckdns.org/specs/AIP-1**

Outreach drafts will be in `distribution/outreach_drafts/11_trent_mcconaghy.md` through `15_shunyu_yao.md`.

---

## Timing

| Target | Optimal channel | Optimal timing |
|---|---|---|
| Trent McConaghy | X DM | After he tweets about AI+Web3 (watch X feed) |
| Nick Emmons | X DM | Cold, any time — technical audience, no spam risk |
| Jerry Liu | X DM referencing issue | After LlamaIndex issue gets any traction |
| Swyx | X DM | After he tweets about MCP or agent protocols |
| Shunyu Yao | X DM or reply to tweet | After he publishes next agent paper/thread |

---

## Success criteria

- ≥2 of 5 reply with substantive engagement (not just "thanks")
- ≥1 says something citable about AIP-1 publicly
- ≥1 opens a GitHub issue on Aigen-Protocol/aigen-protocol from this batch
