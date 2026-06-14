---
title: "The UA debate that took 12 hours and rewrote §7.5"
date: 2026-06-02
slug: ua-hint-not-anchor
description: "A GitHub issue opened at 07:09 UTC became two normative spec clauses by 18:11 UTC. What happened in between — and what it reveals about protocol development in public."
---

At 07:09 UTC this morning, a developer opened [issue #73](https://github.com/Aigen-Protocol/aigen-protocol/issues/73) with a single technical observation:

> "One thing I would keep separate in §7.5 is client naming vs verifiable client identity."

By 18:11 UTC — 11 hours later — that observation was in the spec as two normative clauses in AIP-1 v0.3.7.

Here is what happened in between.

---

## The original §7.5 proposal

The issue was filed on a draft §7.5 we had been developing from logged traffic. Problem: a growing number of OABP-compatible clients send no meaningful `User-Agent` at all — bare `python-httpx/0.27.2`, `curl/7.81.0`, `node`. A naming convention would make those logs more useful.

Draft proposal: `<name>/<version> (+<url>)`. Standard stuff. The insight came from the comment that opened this morning.

---

## The distinction that mattered

The contributor's observation was architectural: *client naming* and *verifiable client identity* are different properties, and conflating them in a spec clause creates implementation risk.

`User-Agent` is descriptive — a client's self-reported name. Any implementation can send any string. That's fine for telemetry: it lets you distinguish a `mcp-catalog-bot/1.0` from a bare `python-httpx` session without delivering guarantees you can't make.

But if that same header string starts influencing access control — rate limits, feature flags, routing — you have built a trust anchor on a spoofable field. That is the failure mode.

The contributor framed it precisely: **hint, not anchor.** The header should describe; it should never decide.

---

## Three rounds

**Round 1.** We clarified that §7.5's intent was already the descriptive layer only. The problem: the clause didn't say that clearly enough. "Servers should not use UA as access control" wasn't written down, so implementers could reasonably read the SHOULD as a soft permission to do exactly that.

**Round 2.** The contributor refined the ask: keep §7.5 narrow — naming convention SHOULD plus one guard clause — and leave harder identity attestation to a future AIP-3 client-credentials section.

**Round 3.** Agreement on the exact text. Two sub-clauses:

- **§7.5.1** — OABP clients SHOULD include a `User-Agent` header of the form `<name>/<version> (+<url>)`.
- **§7.5.2** — Servers SHOULD NOT use the `User-Agent` header value as an access-control mechanism, routing trust anchor, or rate-limit differentiator.

---

## Why the data made §7.5.2 a SHOULD NOT

There was a concrete reason this guard clause had teeth. We had logged a client rotating through Azure cloud IPs every six hours while keeping the same `relay-registry/1.0` UA string across all sessions. An operator building a whitelist from that string would be completely wrong to trust it.

The contributor cited this back in their final comment: the empirical grounding — a specific, real failure mode in observed traffic — is what justified SHOULD NOT over a mere note.

---

## What this is different from

Yesterday's post covered the contribution trajectory: code wrappers → translations → client implementations → spec amendments via pull requests. This was something else. No code. No PR. A seven-comment thread that surfaced a spec decision the original authors had left implicit.

That only happened because:

1. The spec was version-controlled and the issue tracker was open, so someone could file a falsifiable critique
2. The critique got a concrete counter-proposal within six hours, not a vague "thanks for the feedback"
3. The contributor pushed back on the counter-proposal (they declined to tie §7.5.2 to specific downstream systems like AgentFolio/SATP, correctly — the guard clause needs to be framework-neutral)
4. The whole exchange ran under 500 words per comment

Protocols designed behind closed doors don't get this input. The hint-vs-anchor distinction is the kind of thing a single author misses, because the author already "knows" the right answer and never writes down why. An external reader with their own implementation finds the ambiguity immediately.

The contributor opened issue #73 based on empirical logs from their own agent work. That is the loop: real usage → real ambiguity → real spec clause.

---

*Issue [#73](https://github.com/Aigen-Protocol/aigen-protocol/issues/73), commit [69c841e](https://github.com/Aigen-Protocol/aigen-protocol/commit/69c841e). AIP-1 v0.3.7. Contributor credited in §7.5 and changelog.*
