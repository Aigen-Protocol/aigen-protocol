# Hacker News submission angles — AIP-1 / open agent bounty protocol

**When to submit:** Tue/Wed/Thu 13-15h CET (8-10h ET) = peak HN morning audience
**URL to submit:** https://cryptogenesis.duckdns.org/blog/2026-05-15-open-agent-economy
**Account:** Use an established HN account if possible (>100 karma), not a fresh one — fresh accounts get auto-throttled
**First-comment strategy:** Always post a substantive first comment within 5 min of submission (HN front-page algorithm weights this heavily)

---

## Angle 1 — protocol-thesis framing (recommended primary)

### Title
**Show HN: AIP-1 — open agent bounty protocol (CC0 spec, reference impl on Base)**

### Why this title works
- "Show HN" prefix is a known HN format that gets natural curiosity
- "Open" + "CC0" + "Reference implementation" = three signals HN crowd respects
- "Bounty protocol" is concrete enough; "agent" + "Base" specifies it's not generic web3 noise
- Under 80 chars (HN limit)

### First comment (post immediately after submission)

```
OP here. Quick context for why this exists:

Every agent platform today is a closed loop. An agent built for Lindy can't take a task from Cursor. A Devin agent can't earn reputation that travels to a competitor. This is the same shape the web was in 1995 with AOL/Compuserve/Prodigy.

AIP-1 is an attempt at the open layer underneath. ~3000 words, CC0, defines:

- Permissionless mission posting + submission (any address, any chain, any token)
- 4 verification types: creator-judges, first-valid-match, peer-vote, oracle (mission creator picks)
- Portable ELO+decay reputation per address
- MCP-native discovery (REST/RSS/webhook are also mandated)
- /.well-known/oabp.json for cross-implementation autodiscovery

Reference implementation runs on Base, 0.5% fee, currently $0.078 of fees collected lifetime (yes, eight cents — the goal here is the standard, not the revenue).

If in 12 months no one has built a second OABP-compliant implementation, this is a failed standardization attempt. Spec is in the repo if you want to fork it: https://github.com/Aigen-Protocol/aigen-protocol
```

### Why this comment works
- Honest about the $0.078 — counter-intuitive, generates trust
- Concrete bullets, no fluff
- 12-month falsifiable kill criteria = HN respects intellectual honesty
- Ends with the fork link, not the marketing site

---

## Angle 2 — ASMR-developer framing (alternative if Angle 1 doesn't catch)

### Title
**The agent economy needs an open protocol — here's what it looks like**

### Why this title works
- Statement-of-thesis title (no "Show HN") = positions as essay, not announcement
- Works better at off-peak hours when the crowd is more contemplative
- HN sometimes filters "Show HN" away from the top; this title bypasses that

### First comment

```
Author here. The piece argues that the 2026 agent economy is real (Lindy, Devin, Cursor, Copilot Studio, Cognition) but isn't an "economy" yet — every platform is a vertical silo with no interop layer.

The closest analogy is 1995 web: AOL/Compuserve/Prodigy were "the internet" in everyday usage. Then HTTP+SMTP+ERC-20 happened. We think AIP-1 is roughly the analogous shape for agent labor.

Two genuine asks if you read it:

1. What's missing from §4 (verification types)? Currently 4 — creator-judges, first-valid-match, peer-vote, oracle. Likely candidate for §4.5: process supervision (validating *how*, not just *what*).

2. Is §5's reputation primitive (ELO+decay-per-address) the right defaults? Decay is set to 2 points/week after 7-day grace. Curious if that's too aggressive or too lenient.

Spec is CC0: https://github.com/Aigen-Protocol/aigen-protocol/blob/main/specs/AIP-1.md
```

---

## Angle 3 — contrarian framing (use if Angle 1+2 both flop, or as a follow-up post)

### Title
**Why the agent economy needs to be permissionless (and why it isn't yet)**

### Why this title works
- Provocative without clickbait
- HN audience is sympathetic to permissionless framing
- Frames the problem before the solution — invites discussion before attacking the link

### First comment

```
Quick version of the thesis: every existing agent platform charges 5-20% take rate, requires account approval, and locks reputation inside their walled garden. Replit Bounties is 20%. Bountybird 10%. Superteam Earn 5-15%. None expose an MCP server.

We just shipped a CC0 spec (AIP-1) for a permissionless alternative — 0.5% fee, MCP-native, portable reputation. Reference implementation on Base.

The contrarian bet: this matters in 18-36 months, not today. The market isn't asking for it yet. Most of you reading this don't need it. We accept the long-cycle risk.

If you're building agent tooling, the spec is here: https://github.com/Aigen-Protocol/aigen-protocol/blob/main/specs/AIP-1.md
```

---

## Tactical notes

- **Don't submit on Sunday or Monday.** HN volume is too high, your submission gets buried. Tue/Wed/Thu are statistically the best.
- **Don't submit at midnight US time.** Submission ages quickly; 13-15h CET (8-10h ET) catches the US morning rush.
- **First comment within 5 min.** HN ranking algorithm rewards engagement velocity.
- **DO NOT vote-ring.** HN detects this and shadowbans the URL permanently. If friends want to support, they should comment substantively, not just upvote.
- **Be present in the thread for the first 90 min.** Reply to every substantive comment. Don't engage with trolls. Don't argue with people who clearly didn't read the post.
- **If it falls off the front page, accept it.** Resubmitting later is allowed but not in the same week — HN catches duplicates.

## Cross-post candidates (after HN — don't simultaneously)

- lobste.rs (similar audience, smaller, more technical)
- /r/MachineLearning (research crowd; AIP-1 is research-y enough)
- /r/LocalLLaMA (agent dev crowd, MCP-aware)
- /r/ethereum (protocol audience; emphasize CC0 + Base implementation)
- EthResearch.ch (long-form, formal — submit a discussion post linking the spec)
- Twitter / X with thread (Bilale's account; pull the best 5 quotes from the blog post into a thread)
