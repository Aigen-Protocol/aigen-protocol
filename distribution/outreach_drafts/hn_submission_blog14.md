# HN Submission — Blog post #14 (Ten MCP client architectures)

**Status:** DRAFT — Bilale to review and submit when ready
**Best timing:** Tuesday or Wednesday 13-15h CET (peak HN morning audience ET)
**URL to submit:** https://cryptogenesis.duckdns.org/blog/2026-05-20-ten-mcp-clients-field-notes
**Recommended account karma:** >100 to avoid throttling

---

## Suggested title (pick one)

**Option A** (empirical framing — strongest for HN technical crowd):
> Ten autonomous MCP clients tested our server for a week: here's what we learned

**Option B** (problem framing):
> Why half of MCP clients fail at session lifecycle (and how to fix your server)

**Option C** (field notes framing):
> Field notes from running an open MCP server for 5 days: 10 client architectures

**Recommended: Option A.** Concrete number + "here's what we learned" = HN algorithm gold.

---

## First comment to post immediately after submission (within 5 min)

```
OP here. Context on why this exists:

We run an open MCP server for an agent bounty protocol. It's been live for 5 days.
We did not invite any clients. Ten different robots showed up on their own, each with a
different implementation.

What surprised us: every client failed in a different way. The failures cluster into 3 categories:

1. Session lifecycle — clients that never DELETE their session (or expect the server to
   survive stale session IDs forever)
2. HTTP→HTTPS redirects — clients that lose their POST body on 301 but not on 308
3. Discovery assumptions — clients that probe /.well-known/oauth-protected-resource
   before connecting (RFC 9728) and refuse to proceed if it's missing

We documented all 10. Each architecture has a server-side mitigation in the TL;DR table.
The blog post is the field notes. The spec work is in AIP-1:
https://cryptogenesis.duckdns.org/specs/AIP-1

Happy to answer questions about any specific architecture.
```

---

## Why this post works on HN

1. **Empirical, not theoretical** — HN respects "we measured this" over "we think this"
2. **10 architectures is specific** — HN readers can scan the table and know if they're affected
3. **Server operators will save time** — the 308 vs 301 tip alone is actionable
4. **Not promotional** — the blog is useful whether or not you use AIGEN
5. **Links to an active external spec discussion** (modelcontextprotocol/issues/2755) — shows the work is being taken seriously by the ecosystem

---

## Cross-post targets (after HN post goes live)

- **lobste.rs** — same URL, tags: `ai`, `distributed-systems`, `networking`
- **/r/LocalLLaMA** — title: "Running an open MCP server for 5 days — 10 client architectures documented"
- **@swyx** (X DM) — "we documented 10 autonomous MCP client architectures — might be useful for your audience [link]"
- **Joao Moura (CrewAI)** — his agent (Sikkra) is one of the 10 architectures. Can tag him.
- **MCP spec discussion** — already commented at github.com/modelcontextprotocol/modelcontextprotocol/issues/2755

---

## Notes for Bilale

- This is the best HN-eligible post we've written. Empirical + useful + honest.
- If you submit it, post the first comment immediately (pasted above — copy-paste ready).
- Don't submit the same day as the AutoGen issue gets traction — space them out.
- Stars on the GitHub repo should jump after HN front page. Tag the repo in your HN profile bio.
