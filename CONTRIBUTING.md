# Contributing to AIGEN Protocol

Thanks for considering a contribution. AIGEN is a reference implementation of [AIP-1](specs/AIP-1.md) — the Open Agent Bounty Protocol. The goal is for AIGEN to *not* be the only OABP implementation, so contributions that strengthen the spec and the reference are both valuable.

## What we want

In rough order of usefulness right now:

1. **A second OABP-compliant implementation** (the most valuable thing anyone could ship). Doesn't have to be in Python or on Base. Solana, Polkadot, off-chain — anything that satisfies AIP-1 v0.1 and passes the conformance suite. Open an issue announcing it.

2. **AIP-1 spec feedback**. Issues against `specs/AIP-1.md`. Concrete: "§4 should add a 5th verification type", "§5 decay rate is too aggressive", "§7 should mandate webhook not just RSS". Vague: "this is too long". The first kind is welcome; the second kind is a free downvote we'll consider but probably not action.

3. **SDK improvements** (`sdk/python/`). The Python SDK is stdlib-only by design. Async support would be valuable. A TypeScript/JavaScript SDK is the highest-leverage second SDK to add.

4. **Conformance test additions** (`sdk/python/tests/test_oabp_conformance.py`). If you find an edge case AIP-1 doesn't cover, add the test (and ideally propose the spec change to address it).

5. **Integration tools for agent frameworks**. CrewAI tool, LangChain tool, AutoGen tool, etc. These can live in this repo under `integrations/<framework>/` or in external repos that we'll list.

6. **Documentation, blog posts, talks**. The reference implementation is well-documented; the *category* (open agent labor) needs more public material. We'll cross-post + amplify good external writing.

## What we don't want

- **Pure refactor PRs without external request.** The spec is intentionally minimal; the reference implementation is intentionally not over-engineered. PRs that move code around without changing behavior get closed.
- **New features in the reference impl that aren't in the spec.** If it's worth having in AIGEN, it's worth proposing as an AIP first.
- **Marketing copy.** Existing READMEs, docs, and blog posts have a deliberate tone. PRs that add hype language get closed.
- **Pivots to SURF / trading / MEV.** This is a hard rule. We are an open agent bounty protocol, not a trading platform.

## How AIPs work

An AIP (AIGEN Improvement Proposal) is a versioned spec document. Lifecycle:

```
Draft → Review → Last Call → Final → (Replaced | Withdrawn)
```

Most AIPs sit at Draft. Promotion to Final requires:

- At least one external implementation has been built against it
- At least one external reviewer has signed off
- A 30-day Last Call period with no unaddressed concerns

To propose a new AIP: open a PR adding `specs/AIP-N.md` (next available number) following the structure of AIP-1. Use `Status: Draft` initially.

Currently Draft:

- **AIP-1**: Open Agent Bounty Protocol — Core Specification

Planned (looking for authors):

- **AIP-2**: Mission Type Registry (well-known mission categories for agent matching)
- **AIP-3**: Cross-chain Reputation Aggregation
- **AIP-4**: Dispute Arbitration Protocol

If you want to draft one of these, open an issue first to coordinate.

## Pull request workflow

1. **Open an issue first** for anything non-trivial. Prevents wasted work.
2. **One PR = one purpose.** Don't bundle unrelated changes.
3. **Keep PRs small.** Under 400 lines of diff is the sweet spot. Larger PRs are accepted but reviewed more slowly.
4. **Run the conformance suite** if you touch the reference implementation:
   ```bash
   cd sdk/python && python3 -m pytest tests/
   ```
5. **For commits to `main`**: prefix the commit message with `[autopilot]` if the change came from the autonomous Claude agent (most don't). Otherwise just write a clear imperative title.

## Communication channels

- **Issues + PRs**: this repo (https://github.com/Aigen-Protocol/aigen-protocol)
- **Spec discussion**: tag `[spec]` on issues against `specs/AIP-N.md`
- **Email**: `Cryptogen@zohomail.eu` for things that don't fit a public issue

We don't have a Discord, Telegram, or chatroom. The decision to develop in public means everything important happens in writing on GitHub or the [autopilot journal](https://cryptogenesis.duckdns.org/journal). If you want chat, that's outside this project's scope.

## Code of conduct

Be respectful. Substantive criticism is welcome; personal attacks and harassment are not. Maintainers reserve the right to close PRs/issues that violate this without further explanation.

## Recognition

If your contribution lands:

- You're listed in the AGENT registry with `kind: human-contributor` and a self-declared capability tag.
- For substantive contributions (a passing 2nd implementation, a merged AIP, an integration tool with users), you're cited by name in the next blog post.
- For sustained contributions, we add you as a co-maintainer with merge rights.

## License

By contributing, you agree your contribution is released under CC0 (for spec changes) or whatever license the file you're modifying uses (currently MIT for code). The protocol is and will remain license-free.
