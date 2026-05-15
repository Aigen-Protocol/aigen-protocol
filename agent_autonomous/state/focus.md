# Current focus

**Set: 2026-05-14, expanded 2026-05-15 by Bilale: "tous sauf mail"**

> "scaller aigen, etre actif sur github tu es libre"
> + "tous sauf mail" (act directly on everything except email)

## Translation
Scale AIGEN traction by acting, not by filing approval cards. Email is the ONLY thing that still goes to queue. Everything else in Tier A (system_prompt) — GitHub comments, registry submissions, AIGEN missions, code commits — execute directly.

## Concrete priorities (in order)

1. **React to external signals AS THEY ARRIVE.** Webhook fires → you're awake. Don't journal-only when there's a real lever.
   - Codex researcher (chaoqiang.tian) sent email 2026-05-15T08:00Z — if reply arrives in inbox, surface it (Tier A: poll IMAP read-only is OK)
   - Nico (PR#5) — if he replies on the PR, webhook fires you, draft + post a follow-up reply directly (Tier A)
   - 52.186.175.98 (Azure MCP tool-caller) — if returns, attempt to identify (User-Agent, header inspection); consider posting a paid AIGEN mission targeting their use case
   - ke/JS 0.64.2 — if persists, look up what "ke" is, comment publicly somewhere they'd see (their issue tracker, X)
   - Codex eval / SWE-bench-style researchers (ANY UA mentioning "eval", "research", "benchmark") — they self-identified, treat as warm leads

2. **Submit AIGEN to MCP registries you haven't covered yet.**
   - Smithery (https://smithery.ai) — check if listed, submit if not
   - Glama (https://glama.ai/mcp) — check if listed, submit if not
   - mcp.so (PR on github.com/chatmcp/mcp-directory) — we have PR #2298, check status, comment if stale
   - One new MCP-related list per day. Don't repeat a registry already on the list.
   - awesome-mcp-servers PR #6288 punkpeye — check status, comment if stale
   - TensorBlock #542 — check status, comment if stale

3. **Post paid AIGEN missions when justified by external signal.**
   - Cap: $5 USDC / mission, $20 USDC / day total. AIGEN-token rewards unlimited (5000+ in treasury).
   - Examples of justified: "review @nicbstme's HustlerOps integration once live", "test the MCP tools-list response from a fresh client perspective", "fuzz /api/missions for invalid params"
   - NOT justified: synthetic activity, "summary of <random token>", anything radar already does

4. **Substantive commits to AIGEN repo when shipping value.**
   - Doc fix triggered by real client confusion → commit + push
   - New MCP tool that closes a real gap an external client showed up needing → commit + push
   - NOT justified: refactoring, polish, adding new daemons

## Anti-priorities (don't do)

- Don't write approval cards for Tier A actions — that was the over-cautious behavior of run #1-#22
- Don't refactor code without external trigger
- Don't add more autonomous daemons (have enough)
- Don't post synthetic AIGEN missions (radar daemon handles fresh-token coverage)
- **Don't send emails** (Tier B — still queue)
- **Don't transfer treasury funds beyond $5/mission $20/day caps** (Tier B)
- Don't touch your own systemd/run.sh/system_prompt/.gitignore unilaterally

## Success metric this week (revised 2026-05-15)

By 2026-05-21, at least 2 of these:
- ≥1 commit per day shipped that closes an external user's gap
- ≥1 real MCP registry submission per day (with link)
- ≥3 substantive GitHub comments per week (not "thanks", real engagement)
- ≥1 new external creator posts a mission OR ≥1 external submitter completes one
- Codex researcher OR Nico OR 52.186.175.98 client replies to outreach
- Treasury USDC > $1.00 (currently $0.078574 — need 13× growth)

If none of these by 2026-05-21 → escalate to Bilale that the autonomy unblock didn't move the needle.
