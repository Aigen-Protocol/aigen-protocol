# Response draft — generic 2nd-implementation announcement

**Status:** DRAFT (autopilot never sends — Bilale's decision when/how)
**Created:** 2026-06-05 by autopilot
**Trigger:** someone files an `implementation-announcement` issue on
`Aigen-Protocol/aigen-protocol` (template path
`.github/ISSUE_TEMPLATE/implementation-announcement.md`), OR emails
`Cryptogen@zohomail.eu` saying "I built / am building a second OABP
implementation", OR opens a PR adding their server to
`docs/SECOND_IMPLEMENTATION.md`.

**Why this template exists:** as of this writing there are zero second
implementations. The day someone announces one is a category-defining moment
for AIGEN — the spec acquires real authority because a non-AIGEN party
implemented it. The response has to land cleanly: welcoming, technical, not
promotional, no capture wording.

**Anti-pattern to avoid:** anything that reads like "welcome to the AIGEN
ecosystem". The whole point of AIP-1 being CC0 is that there is no AIGEN
ecosystem to join — there's an open spec and you implemented it. Frame as
peer-to-peer recognition.

---

## Channel A — they opened a GitHub issue using the implementation-announcement template

> Congrats on shipping. Genuinely big — you're the first non-AIGEN
> implementation we're aware of, and that's the signal the spec needed.
>
> A few things, in order of usefulness to you:
>
> **1. Conformance.** If you haven't already, the conformance suite is at
> `sdk/python/tests/test_oabp_conformance.py` (28 tests, Apache-2.0). Point it
> at your base URL and tell us what fails — those failures are spec gaps, not
> your bugs. We'll either fix the spec or write an interop note.
>
> **2. The `/.well-known/` discovery surface.** If you serve
> `agent-card.json` + `oabp.json` correctly, the 19 crawlers documented in
> `docs/SECOND_IMPLEMENTATION.md` will find you within ~2 weeks (Agenstry,
> AgentSEO, agent-tools.cloud, Waggle, etc., all auto-discover). You don't
> have to submit anywhere.
>
> **3. Differentiation, not parity.** AIGEN's reference impl is one of many
> valid shapes the spec allows. If your verification types, mission graph, or
> reputation model differs in interesting ways, please write that up — it's
> what makes the spec stronger. We'll link to it from our SECOND_IMPLEMENTATION
> doc as a worked alternative.
>
> **4. Spec friction.** What's the single thing in AIP-1 that was hardest to
> implement / most ambiguous / most opinionated-where-it-shouldn't-be? That
> answer feeds directly into v0.4 scope. Concrete is better than vague — a
> section number and "this constraint made me do X workaround" is gold.
>
> **5. Listings.** Happy to PR you into `awesome-mcp-servers`, blog post,
> whatever recognition channels are useful — your call, no pressure.
>
> No "welcome to the ecosystem." There isn't one. There's a spec, and now you
> implement it independently. That's the whole shape.
>
> — Aigen-Protocol maintainer

## Channel B — they emailed Cryptogen@zohomail.eu

Same body as Channel A, plus a single opening line:

> Hi —
>
> Thanks for the heads-up by email. Below is roughly what I'd reply if you
> opened a GitHub issue, but happy to keep the conversation in email if you
> prefer.

…then the 5 numbered points verbatim.

## Channel C — they opened a PR adding their server to docs/SECOND_IMPLEMENTATION.md

PR comment (terse, not a wall of text):

> Merging shortly — thank you for self-listing. A few asks, none blocking:
>
> 1. Run `python -m pytest sdk/python/tests/test_oabp_conformance.py --base-url <yours>` and paste pass/fail counts in a follow-up issue if convenient. Failures help us tighten the spec.
> 2. If your verification types or mission graph differ from AIGEN's reference, please drop a 1-paragraph diff note in a follow-up — useful for future implementers comparing approaches.
> 3. Optional: open an issue tagged `spec-discussion` for the single biggest friction point you hit. That's the v0.4 input we need most.
>
> No promotion, no capture. The spec is CC0, your impl is yours.

---

## Notes for Bilale

- **Time-bounded relevance:** this template stays fresh as long as second
  implementations are <5 globally. Once we have 5+, drop the "first non-AIGEN
  implementation we're aware of" framing — it stops being a category-defining
  moment and becomes routine.
- **Tone calibration:** Channel A is intentionally direct — no headers,
  numbered list, ~280 words. If the announcer's own tone is more formal, mirror
  them. If they're Asian / non-native English speaker, simpler sentence
  structure helps; the substance stays the same.
- **The "no ecosystem to join" line is load-bearing.** It's the explicit
  rejection of capture-wording — the focus.md anti-priority *"écosystème non
  cloisonné"*. Don't soften it, don't remove it. Re-frame if you want, but
  preserve the assertion.
- **What NOT to say in any channel:**
  - "Welcome to the AIGEN family / community / ecosystem"
  - "We'd love to feature you on our website"
  - "Let's coordinate on a launch announcement"
  - Anything that positions AIGEN as the curator of an ecosystem the
    implementer just joined. The whole AIP-1 thesis dies the moment that
    framing wins.
- **Recognition asks (point 5):** offer, don't impose. If they decline
  awesome-mcp-servers PR or blog mention, drop it immediately. Some
  implementers want quiet adoption — respect it; that's also a healthy signal.
- **If conformance fails massively:** don't react as if they're failing the
  test. The test is the artefact under examination, not their impl. Phrase
  every gap as "spec ambiguity" until proven otherwise.

## Cross-references

- `.github/ISSUE_TEMPLATE/implementation-announcement.md` — the trigger
- `docs/SECOND_IMPLEMENTATION.md` — the starter pack (20 architecture classes
  documented as of 2026-06-05)
- `sdk/python/tests/test_oabp_conformance.py` — the conformance suite
- `focus.md` § Anti-priorities — the "écosystème non cloisonné" commitment
