# Outreach targets — agent economy category-creation play

**Generated:** 2026-05-15 (post strategy decision: "premier sur un marché qui n'existe pas")
**Owner:** Bilale (autopilot CANNOT send emails — Tier B). Action manually.
**Goal:** ≥5 substantive responses in 2 weeks. Not "thanks for reaching out" — actual engagement on AIP-1 thesis.

## Target profile

People who are:
1. Already working in or adjacent to agent-economy infrastructure
2. Likely to have an opinion on "should there be an open protocol for this?"
3. Have a public following that compounds if they cite AIGEN
4. Reachable on X DM, LinkedIn, or public email

Not on this list (deliberately):
- Cold-emailing big-co PMs (low signal/noise ratio for first wave)
- VCs (too early — no traction → no follow-on)
- Indie devs without distribution (can't compound)

## The 10 targets

### Tier 1 — adjacent protocol founders (ask: "what do you think of AIP-1?")

#### 1. **David Minarsch** — Olas Network (Autonolas) co-founder
- X: [@davidminarsch](https://x.com/davidminarsch)
- Why: building agent-services protocol on Gnosis. Same thesis, different execution. Most likely peer-feedback target.
- Hook: "Built AIP-1 spec for open agent bounty protocol — would value Olas perspective on §5 reputation primitive vs your service-staking model"

#### 2. **Akash Bansal / Yan Zhang** — Ritual founders
- X: [@AkashBansal_](https://x.com/AkashBansal_), [@yan_zhang_](https://x.com/yan_zhang_)
- Why: Ritual is verifiable AI compute on-chain. Adjacent surface — their oracle could plug into AIP-1 §4.4
- Hook: "AIP-1 §4.4 oracle verification — Ritual is the natural plug-in. Open to integration RFC?"

#### 3. **Const (creator of Bittensor)** — Yuma Rao
- X: [@const_reborn](https://x.com/const_reborn)
- Why: Bittensor has subnet markets that look like permissionless task markets. Different design but same spiritual ancestor.
- Hook: "Bittensor subnets and AIP-1 missions are converging on similar primitives — would love your read on the reputation §5 portability question"

### Tier 2 — agent framework maintainers (ask: "would you add OABP support?")

#### 4. **Joao Moura** — CrewAI founder
- X: [@joaomdmoura](https://x.com/joaomdmoura)
- Why: CrewAI is one of the most-starred agent frameworks. If they ship an OABP integration tool, every CrewAI agent gets discovery for free.
- Hook: "CrewAI tools could ship `submit_to_aigen_mission` as a one-liner. AIP-1 spec stable enough to integrate."

#### 5. **Harrison Chase** — LangChain CEO
- X: [@hwchase17](https://x.com/hwchase17)
- Why: LangChain agents need a marketplace surface. They've experimented with LangChain Hub. AIP-1 is the open layer underneath.
- Hook: "LangChain Hub is account-gated; AIP-1 is the permissionless layer. Tools-export integration?"

#### 6. **OpenAgents / AutoGen team @ Microsoft Research**
- Channel: GitHub Issues on `microsoft/autogen` repo (most reliable reach)
- Why: AutoGen agents are research-y, would cite a proper spec rather than build from scratch
- Hook: Open an issue on autogen repo: "Discussion: standardising the agent-task marketplace surface — AIP-1 draft"

### Tier 3 — researchers + thinkers (ask: "would you cite or critique this?")

#### 7. **Lilian Weng** — formerly OpenAI, agent systems research
- X: [@lilianweng](https://x.com/lilianweng)
- Why: her blog posts define how the field thinks about LLM agents. A single mention = compounding mindshare.
- Hook: "Wrote AIP-1 spec for open agent labor markets — your taxonomy of agent capabilities (your June 2023 post) is implicit in §1. Would value your read."

#### 8. **Andrej Karpathy** — independent, tinkering with agents
- X: [@karpathy](https://x.com/karpathy)
- Why: massive following; if he tweets the spec it goes mainstream in tech-twitter overnight.
- Hook: Risky — only reach if you have a substantive question (not "please RT"). Maybe: "Built a 0.5%-fee permissionless agent task protocol on Base. AIP-1 spec is CC0. Curious what you'd remove."

#### 9. **Simon Willison** — independent, prolific dev-blogger
- X: [@simonw](https://x.com/simonw)
- Why: writes the most-read newsletter in LLM tooling. His coverage of MCP last fall drove tens of thousands of readers to the spec.
- Hook: "Permissionless agent bounty protocol with MCP-native discovery — would love your sniff test on §7."

#### 10. **A16z crypto's Daren Matsuoka** — research lead, agent economy thesis
- X: [@darenmatsuoka](https://x.com/darenmatsuoka)
- Why: a16z published "the case for AI agents" in 2024. Daren tracks this space. A cite from him in their next thesis post = signal.
- Hook: "AIP-1 is the protocol layer your June 2024 thesis post called for — open to a 15-min call to walk through?"

## Suggested cadence

- **Week 1 (May 16-22):** Tier 1 + Tier 2 = 5 reaches. Personalised messages, 100-200 words each, link to AIP-1.
- **Week 2 (May 23-29):** Tier 3 = 5 reaches.
- **Don't follow up** if no response after 7 days — move on. Compound mindshare is patience, not pestering.

## Message template (adapt per target)

```
Hi [name],

Quick context: just published AIP-1, a CC0 spec for an open
agent bounty protocol — 0.5% fee, permissionless mission posting,
ELO + decay reputation, 4 verification types, MCP-native.

[ONE specific reason this person should care about this — see hooks above]

Spec: https://github.com/Aigen-Protocol/aigen-protocol/blob/main/specs/AIP-1.md
Reference impl: https://cryptogenesis.duckdns.org

No pitch, no ask. Just looking for the kind of feedback that
makes a draft v0.2 sharper than v0.1.

— [Bilale / your name]
Cryptogen@zohomail.eu
```

## Tracking

Add status next to each name as you reach out:

- 📧 Sent (date)
- 👀 Read receipt
- 💬 Replied (date, summary)
- ❌ No response after 7 days (move on)
- 🔁 Follow-up scheduled (date)

Keep this file under version control. Future autopilot runs can read it to know not to suggest people you already contacted.
