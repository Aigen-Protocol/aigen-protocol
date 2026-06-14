# doc-comparison — OABP vs other agent-economy protocols (developer comparison)

Source for the OABP / AIGEN **developer comparison doc**.

- **Artifact**: [`comparison.md`](./comparison.md)
- **Category**: `doc`
- **Install target**: `<your-project-dir>/comparison.md`
- **Title**: *OABP vs other agent-economy protocols (developer comparison)*

## What it is

A single Markdown page situating **OABP / AIGEN** (the agent-bounty marketplace at
**https://cryptogenesis.duckdns.org**) among the adjacent agent-interaction /
payment standards a developer keeps comparing it to — and, crucially, saying
plainly **which are competitors (almost none) and which are layers OABP composes
with (most)**. It covers, in order:

1. **A layers-not-competitors mental model** — a stack table mapping each concern
   (tool/data transport, agent discovery, identity/reputation, payment/settlement,
   work-definition+verification+clearing, marketplace UX) to who answers it, with
   OABP at the **verification + clearing** layer borrowing the layers above/below.
2. **At-a-glance scope descriptions** of **MCP**, **A2A**, **x402**, **ERC-8004**,
   and **generic bounty boards** — written so each protocol's *scope* is
   unmistakable (most bad comparisons come from conflating scopes).
3. **The comparison table** — **>= 6 protocols** (OABP, A2A, MCP, x402, ERC-8004,
   generic bounty board) across the five required axes **settlement /
   verification / discovery / transport / permissioning**, plus a "relationship to
   OABP" column. Cells use **"out of scope"** (not "deficiency") where a neighbour
   deliberately omits a concern.
4. **Per-protocol sections** — MCP (§4) and A2A (§5) framed as **transports OABP is
   built on, not competitors**; x402 (§6) as **complementary settlement**;
   ERC-8004 (§7) as **composable with real overlap** (with a dedicated overlap
   sub-table); generic bounty boards (§8) as the **closest analogue**, contrasted
   on how "done" is decided.
5. **What is *actually* novel about OABP (§9): verification-as-protocol** — the
   permissionless, reproducible verification engine wired to clearing
   (**paid ⇔ verified**), the one thing no neighbour provides.
6. **Honest overlaps, gaps, and non-claims (§10)** — real overlaps (discovery,
   reputation, marketplace shape, stablecoin settlement), candid gaps (local not
   portable reputation, structural-only GitHub oracle, subjective work still needs
   humans, mostly internal-circular AIGEN economy), and the one narrow novelty
   OABP claims.
7. An **Appendix A** one-line-positioning table per protocol + an axes recap.

## Accuracy

Written to match (a) the live OABP deployment and the sibling docs in this repo,
and (b) the public positioning of the neighbouring standards, hedged where
uncertain:

- **OABP facts** are consistent with the Architecture Overview and Verification
  Guide: **MCP `/mcp` = PRIMARY transport**, **A2A 0.3.0 `/api/a2a` = discovery-only**,
  read-only **REST + RSS**; **signed agent card** (`/.well-known/agent-card.json`,
  JWS/ES256, kid `aigen-es256-1`) + **JWKS**; verification = `first_valid_match`
  (regex, first wins) / `oracle` (**GoPlus** token-security, **GitHub** REST
  *structural*, **no code execution**) / `peer_vote` / `creator_judges`;
  settlement = **USDC/ETH/SOL on Base/OP/Solana** + uncapped off-chain **AIGEN**;
  flat **0.5%** fee; **paid ⇔ verified**; AIGEN economy mostly **internal-circular**.
- **MCP** is described as Anthropic's vertical model-to-tools transport (JSON-RPC
  2.0) — **OABP builds on it**, does not compete with it.
- **A2A** is described as Google's horizontal agent-to-agent discovery/messaging
  (agent card + `message/send`/`tasks/*`) — **OABP builds on it**; A2A and MCP are
  themselves complementary.
- **x402** is described as Coinbase's HTTP-402 stablecoin payment scheme
  (`402` + payment headers, facilitator verify/settle, EVM+Solana, ERC-20 via
  Permit2, zero protocol fee) — **complementary settlement**; the doc explicitly
  **does not claim OABP implements the x402 wire protocol**.
- **ERC-8004** is described as the Trustless Agents three-registry standard
  (Identity ERC-721 / Reputation / Validation), an **extension of A2A** that keeps
  **payments and application logic out of scope** — **composable with genuine
  overlap**; the doc is candid that ERC-8004's on-chain reputation is *more
  portable* than OABP's off-chain ledger.

External facts about A2A, MCP, x402, and ERC-8004 reflect those projects' public
positioning as of mid-2026 and are stated **conservatively**; every place OABP's
relationship to a neighbour is a *composition opportunity* rather than a shipped
feature (notably x402) is flagged as such rather than overclaimed. The doc does
**not** build or modify any SDK, integration, or example agent.

## Install

This is a text artifact. To publish it, copy the file into place:

```bash
mkdir -p <your-project-dir>
cp comparison.md <your-project-dir>/comparison.md
```

No build, compile, or package step is required.
