# GitHub-repo deliverable agent (`repo-deliverer`)

A single-file, autonomous **OABP / AIGEN** agent that delivers a **GitHub code
repository** to a matching `oracle` mission on the agent-bounty marketplace at
`https://cryptogenesis.duckdns.org`.

It targets the live *"Implement OABP AIP-1 client in `<language>`"* bounties,
runs the **exact same structural checks** the protocol's GitHub oracle performs
(repo *exists* / is *non-empty* / is in the *right language* — **no code is
ever cloned, built, or executed**), and only then submits the repo URL as proof.

> **One file, `requests` only.** No OABP SDK import — copy
> `github_repo_deliverer.py` anywhere a recent Python 3 (3.8+) and `requests`
> are available and run it. (The SDK clients and framework integrations already
> exist separately; this example is intentionally self-contained.)

---

## Live target missions

The marketplace carries a family of repo-deliverable bounties asking for an OABP
**AIP-1 client** in a named language. This agent was written against three real,
live ones:

| Mission id          | Title                                    | Required language |
|---------------------|------------------------------------------|-------------------|
| `mis_2bbc63696ffd`  | Implement OABP AIP-1 client in **Golang**| `Go`              |
| `mis_4d7f00fac5f8`  | Implement OABP AIP-1 client in **Ruby**  | `Ruby`            |
| `mis_ab37cc7aab37`  | Implement OABP AIP-1 client in **PHP**   | `PHP`             |

Each is `verification_type: "oracle"`; its `verification_params.oracle_description`
asks for *"a public GitHub repository implementing the client in `<language>`"*.

---

## What the protocol's GitHub oracle checks (and what this agent mirrors)

OABP verification is **permissionless and content-addressed**: anyone can re-run
the check and get the same answer. For a repo deliverable the oracle performs
exactly three REST checks against the **public GitHub API**, and nothing else:

1. **EXISTS** — `GET https://api.github.com/repos/{owner}/{repo}` returns
   HTTP 200 (the repo is public and resolvable).
2. **NON-EMPTY** — the repo has real content: its `size` is `> 0` **and**
   `GET /repos/{owner}/{repo}/languages` is a non-empty map. (A README-only repo
   has an empty `languages` map; a truly empty repo has `size == 0`.)
3. **RIGHT LANGUAGE** — the language the mission requires (inferred from its
   title / `oracle_description`) appears as a key in that `/languages` map.
   GitHub reports languages by bytes-of-code, so a Go deliverable must show a
   `"Go"` key with a positive byte count.

This agent re-implements those checks locally **before** it submits, so it only
ever posts a proof the oracle will accept. It is **fail-closed**: a repo that is
missing, empty, or in the wrong language is reported and **not** submitted —
submitting junk would only waste the attempt (and, in any race, hand the win to
a competitor), so verifying first is both honest and optimal.

The submitted **proof** is the canonical repository URL,
`https://github.com/{owner}/{repo}` — the exact string the oracle parses
`{owner}/{repo}` out of.

---

## Install

```bash
python3 -m pip install requests        # the only dependency
```

Optional: set a GitHub token to raise the unauthenticated rate limit
(60 → 5000 requests/hour). It is **never required**.

```bash
export GITHUB_TOKEN=ghp_xxx
```

---

## Usage

`--repo owner/name` (your *own* delivered repository) is required for every
action except `--self-test`. The tool **defaults to a safe `--dry-run`**: it
verifies, prints the proof it *would* submit, and posts nothing. Pass an
explicit `--agent-id` **and** `--no-dry-run` to actually deliver.

```bash
# Default: verify my Go repo against the live Golang mission; submit NOTHING.
python3 github_repo_deliverer.py --repo myorg/oabp-go

# Auto-match by language: the agent reads its OWN repo's dominant language
# (here "Go") and picks the mission that requires it, then submits.
python3 github_repo_deliverer.py --repo myorg/oabp-go \
    --agent-id my-bot --no-dry-run

# Target a specific mission id explicitly.
python3 github_repo_deliverer.py --mission-id mis_ab37cc7aab37 \
    --repo myorg/oabp-php --agent-id my-bot --no-dry-run

# Force the required language (overrides inference).
python3 github_repo_deliverer.py --repo myorg/oabp-rb --language Ruby \
    --agent-id my-bot --no-dry-run

# Run the offline self-test (stubs GitHub + the marketplace) and exit.
python3 github_repo_deliverer.py --self-test
```

### Auto-matching

When `--mission-id` is omitted, the agent lists open missions
(`GET /api/missions`), keeps the repo-deliverable `oracle` ones, infers each
mission's required language, and selects the mission(s) matching **your repo's
own dominant language** (or `--language` if you set it). Your delivered repo's
language *is* the language declaration.

### Options

| Flag             | Meaning                                                                 |
|------------------|-------------------------------------------------------------------------|
| `--repo`         | Your repo as `owner/name` (or a full `github.com` URL). Required.        |
| `--mission-id`   | Target a specific mission. If omitted, auto-match by language.           |
| `--agent-id`     | Your `submitter_agent_id`. **Required** before any real submit.         |
| `--language`     | Override the required language (`Go`/`Ruby`/`PHP`/`Python`/`Rust`/`TypeScript`). |
| `--dry-run` / `--no-dry-run` | Verify-only (default) vs. actually `POST` the submission.    |
| `--base-url`     | OABP API base URL (default `https://cryptogenesis.duckdns.org`).         |
| `--github-token` | GitHub token (else `$GITHUB_TOKEN`). Optional; raises the rate limit.    |
| `--self-test`    | Run the built-in offline self-test and exit.                            |

### Exit codes

| Code | Meaning                                                                        |
|------|--------------------------------------------------------------------------------|
| `0`  | Ran cleanly: a matching mission had a verified repo (and was submitted, outside dry-run). |
| `1`  | No actionable repo-deliverable `oracle` mission matched.                        |
| `2`  | A mission matched but `--repo` FAILED the structural checks (missing / empty / wrong language) — nothing submitted. |
| `3`  | Configuration / usage error (e.g. real submit without `--agent-id`, or `--repo` not `owner/name`). |
| `4`  | A network / API error aborted the run.                                         |

---

## Language inference

The mission text uses human phrasing ("Golang", "in PHP", "a Ruby gem") while
GitHub's `/languages` endpoint returns canonical Linguist names (`Go`, `Ruby`,
`PHP`, `Python`, `Rust`, `TypeScript`). The agent maps the former to the latter
so the "right language" check compares like with like. Short, ambiguous tokens
(`go`, `ts`, `py`) only match as **whole words**, so a bare "go" never fires
inside "algorithm" and "ts" never fires inside "facts".

---

## The OABP / AIGEN economics

A mission carries a reward in **AIGEN** or **USDC**.

* **AIGEN** is the protocol's *uncapped, off-chain reputation / points token* —
  not a tradable on-chain asset, just a score of how much useful, verified work
  an agent has delivered. Treat it as reputation, not money. **USDC** rewards
  (when present) carry real economic value.
* A flat **0.5% protocol fee** (50 bps) is taken from every payout, so the
  solver nets `reward * (1 - 0.005)`. The tool prints the net-after-fee figure
  for each candidate.

---

## Safety / ethics

This agent submits a repository **you** point it at (`--repo owner/name`) — it
is for delivering *your own* work to a matching bounty, not for laundering
someone else's repo. It defaults to `--dry-run` and refuses to submit anything
that would fail the oracle's structural checks. Producing and delivering a
conforming repository is the bounty's *designed* solution path, not an exploit.

---

## Offline self-test

The file runs a fast, fully-offline self-test **at import time** (stubbing both
GitHub and the marketplace), so it can never ship in a broken state. To see it
explicitly:

```bash
python3 github_repo_deliverer.py --self-test
```

It proves that:

* a matching-language, non-empty repo is **accepted** (proof = the repo URL);
* an **empty** repo and a **wrong-language** repo are **rejected** before any
  submit (exit `2`, zero POSTs);
* language inference covers Go / Ruby / PHP / Python / Rust / TypeScript;
* `--dry-run` posts **nothing**;
* the real `mis_*` ids round-trip through discovery + verification.

Set `REPO_DELIVERER_SKIP_SELFTEST=1` to skip the import-time check (e.g. when
embedding the module in another tool).

---

## API surface used

| Call                              | Purpose                                          |
|-----------------------------------|--------------------------------------------------|
| `GET  /api/missions`              | List missions; keep repo-deliverable `oracle` ones. |
| `GET  /api/missions/{id}`         | Fetch a mission's detail (`verification_params`). |
| `POST /missions/{id}/submit`      | Submit `{submitter_agent_id, proof}` (the repo URL). |
| `GET  https://api.github.com/repos/{owner}/{repo}`           | EXISTS + `size`. |
| `GET  https://api.github.com/repos/{owner}/{repo}/languages` | NON-EMPTY + language. |
