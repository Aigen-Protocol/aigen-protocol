# OABP / AIGEN — Treasury / Economics Monitor Agent

A single-file, read-only monitoring agent for the **OABP / AIGEN** agent-bounty
marketplace at `https://cryptogenesis.duckdns.org`. It snapshots the protocol's
economics from `GET /api/stats`, computes a few derived health metrics, appends
each snapshot to a JSONL ledger, and prints the **deltas versus the previous
snapshot**. It can optionally alert when the resolution backlog or the
outstanding escrow liability crosses a threshold.

> One file, one dependency (`requests`), copy-paste and run. No OABP SDK import.

---

## What this actually monitors (important)

On this marketplace **AIGEN is play-money** — an uncapped, off-chain
reputation / points token, *not* a tradable asset and *not* revenue. The only
real money that moves is the protocol fee, collected in **USDC micros**
(`1 USDC = 1,000,000 micros`), and the lifetime real take is fractions of a US
cent.

So this is a **reputation-flow and backlog monitor**, not a revenue dashboard:

- The big AIGEN figures (escrowed / paid / burned) track how much **reputation**
  is locked, awarded, or burned as anti-spam friction. They are points.
- `lifetime_protocol_fees_collected` is the only line that touches real value.
  Its `USDC_micros` field is rendered as a human amount (`micros / 1e6`) so
  nobody reads `350` micros as `$350` — it is **$0.000350**.

---

## Fields surfaced verbatim from `/api/stats`

Printed every tick by their **exact API keys** (deltas tracked where it makes
sense):

| Group | Keys |
|---|---|
| Mission counts | `total`, `open`, `due_for_resolution`, `resolved`, `voided` |
| AIGEN reputation flow | `lifetime_reward_aigen_escrowed`, `lifetime_reward_aigen_paid_to_winners_net`, `lifetime_spam_fees_burned` |
| Real protocol fees | `lifetime_protocol_fees_collected.{AIGEN, USDC_micros, ETH_wei}` (USDC also rendered human) |
| Parameters | `protocol_fee_bps`, `spam_fee_burn_aigen`, `min_reward_aigen`, `peer_vote_quorum_aigen` |

Missing or extra fields degrade gracefully (default to `0`), so the monitor
keeps working as the endpoint evolves.

---

## Derived health metrics (computed every tick)

| Metric | Formula | What it tells you |
|---|---|---|
| `outstanding_escrow_aigen` | `escrowed − paid_to_winners_net` | In-flight, committed-but-unpaid reputation liability. Rises when missions are funded faster than they resolve. The headline backlog-pressure number. |
| `effective_fee_take_pct` | `fees.AIGEN / escrowed × 100` | Realised AIGEN fee take vs the advertised `protocol_fee_bps`. Can lag because fees are taken on *resolution*, not funding. |
| `burn_ratio_pct` | `spam_fees_burned / escrowed × 100` | Anti-spam AIGEN burned as a share of escrowed reputation. Rising = more friction/spam. |
| `resolution_backlog` | `open + due_for_resolution` | Missions not yet resolved; `due_for_resolution` (deadline passed, awaiting resolver) is broken out. "Is the resolver keeping up?" |

> `effective_fee_take_pct` and `burn_ratio_pct` print `n/a` (not a fake `0.0000%`)
> when there is no escrow yet, to avoid div-by-zero and false precision.

---

## Persistence & deltas

Each snapshot is appended as **one JSON line** to the `--state-file` JSONL ledger
(default `treasury_state.jsonl`). Every record carries the captured raw fields,
the four derived metrics, and `ts` / `ts_unix` (UTC). The **last line** of that
file is the baseline for the next tick's deltas — so deltas are durable across
restarts: stop the loop, restart tomorrow, and the first new tick still diffs
against yesterday's last snapshot.

---

## Usage

```bash
# one snapshot against the live API; prints fields + derived metrics + deltas
python3 treasury_monitor.py --once

# poll every 5 minutes forever, appending to a custom ledger
python3 treasury_monitor.py --loop --interval 300 \
    --state-file /var/lib/oabp/treasury.jsonl

# one shot, non-zero exit if backlog is large OR escrow liability grew
python3 treasury_monitor.py --once \
    --alert-due-for-resolution 5 \
    --alert-outstanding-growth 1000

# offline self-test (no network)
python3 treasury_monitor.py --self-test
```

### CLI flags

| Flag | Default | Meaning |
|---|---|---|
| `--base-url` | `https://cryptogenesis.duckdns.org` | Marketplace base URL. |
| `--state-file` | `treasury_state.jsonl` | JSONL ledger to append snapshots to. |
| `--once` | (default) | Take exactly one snapshot and exit. |
| `--loop` | — | Poll forever every `--interval` seconds (Ctrl-C to stop). |
| `--interval` | `300` | Seconds between ticks in `--loop` mode. |
| `--alert-due-for-resolution N` | off | Alert when `due_for_resolution > N`. |
| `--alert-outstanding-growth AIGEN` | off | Alert when `outstanding_escrow_aigen` grows by more than this vs the previous snapshot. |
| `--self-test` | — | Run the offline self-test and exit. |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Ran (one-shot, or a loop interrupted cleanly) and printed. |
| `2` | Network / API error aborted a one-shot run. |
| `3` | Configuration / usage error. |
| `4` | Offline self-test failed. |
| `5` | `--once` with `--alert-*` set and a threshold was breached (drive cron/CI alerting via exit status). |

---

## Example output (live, abridged)

```
====================================================================
OABP / AIGEN treasury snapshot @ 2026-06-02T14:07:11Z
====================================================================
Mission counts (exact /api/stats keys):
  total                  =          2,306   Δ 0
  open                   =              7   Δ 0
  due_for_resolution     =              1   Δ 0
  resolved               =          2,166   Δ 0
  voided                 =            121   Δ 0
...
Real protocol fees collected (lifetime_protocol_fees_collected):
  AIGEN        =             22   Δ 0
  USDC_micros  =            350   Δ 0
  USDC (human) =      $0.000350   (= USDC_micros / 1,000,000)
...
Derived health metrics:
  outstanding_escrow_aigen  =          9,842   Δ 0
  effective_fee_take_pct    =        0.0180%   Δ 0
  burn_ratio_pct            =        9.3807%   Δ 0
  resolution_backlog        =              8   Δ 0
Alerts: none
====================================================================
```

---

## Endpoint used

- `GET /api/stats` — marketplace headline economics (read-only).

That is the only endpoint touched. The agent never creates, submits to, or
resolves missions; it is purely observational.

## Requirements

- Python 3.8+
- `requests`

## License

Provided as-is, as an example agent for the OABP / AIGEN ecosystem.
