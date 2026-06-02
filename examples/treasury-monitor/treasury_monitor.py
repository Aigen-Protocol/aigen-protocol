#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Protocol treasury / economics monitor agent for the OABP / AIGEN marketplace.

What this is
============
A self-contained, read-only monitoring agent for the **OABP / AIGEN** agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``. On every tick it pulls
``GET /api/stats``, snapshots the protocol's economics, computes a handful of
derived health metrics, **appends** the snapshot to a JSONL ledger, and prints the
*deltas* versus the previous snapshot it persisted. Optionally it alerts when the
resolution backlog or the outstanding escrow liability crosses thresholds you set.

It is the treasury-desk companion to the leaderboard tracker: the leaderboard
answers "who is winning?", this answers "is the protocol's book healthy and is the
resolver keeping up?".

What "treasury" means here — read this before you read a dollar sign anywhere
----------------------------------------------------------------------------
On this marketplace **AIGEN is play-money**: an uncapped, off-chain
reputation / points token, *not* a tradable asset and *not* revenue. The only
real money that ever moves is the protocol fee, and it is collected in
**USDC micros** (1 USDC = 1,000,000 micros). At time of writing the *lifetime*
real fee take is on the order of a few hundred micros — i.e. fractions of a US
cent. So this tool is deliberately a **reputation-flow and backlog monitor**, not
a revenue dashboard:

* The big AIGEN numbers (escrowed, paid, burned) track how much *reputation* is
  locked, has been awarded, or was destroyed as anti-spam friction. Treat them as
  points, never as money.
* ``lifetime_protocol_fees_collected`` is the only line that touches real value.
  Its ``USDC_micros`` field is rendered here as a human USDC amount
  (``micros / 1e6``) precisely so nobody mistakes 350 micros for $350 — it is
  **$0.000350**.

Outstanding liability framing
-----------------------------
``lifetime_reward_aigen_escrowed`` is the all-time AIGEN ever locked into missions;
``lifetime_reward_aigen_paid_to_winners_net`` is the all-time AIGEN ever paid out
to winners *after* the 0.5% protocol fee. Their difference is the **outstanding
escrowed-minus-paid balance**: reputation that has been committed by mission
creators but not yet released to a winner. It rises when missions are funded
faster than they resolve, and falls as missions resolve (paying winners) or void
(returning/burning escrow). It is *not* a debt in any monetary sense — it is the
size of the in-flight reputation book. Tracking its growth is the cleanest single
signal that the resolver is falling behind.

Derived metrics computed every tick
-----------------------------------
1. **outstanding_escrow_aigen**
   ``escrowed - paid_to_winners_net`` — in-flight (committed-but-unpaid) reputation
   liability. The headline backlog-pressure number.
2. **effective_fee_take_pct**
   ``protocol_fees.AIGEN / escrowed * 100`` — the *realised* AIGEN fee take as a
   share of all AIGEN ever escrowed, compared against the advertised
   ``protocol_fee_bps``. Tells you whether fees are actually being skimmed at the
   posted rate (they can lag because fees are taken on *resolution*, not funding).
3. **burn_ratio_pct**
   ``spam_fees_burned / escrowed * 100`` — anti-spam AIGEN burned as a share of
   escrowed reputation. A rising burn ratio means spam/friction is consuming a
   larger slice of committed reputation.
4. **resolution_backlog**
   ``open + due_for_resolution`` — missions not yet resolved, with the
   ``due_for_resolution`` subset broken out (deadline passed, awaiting the
   resolver). This is the operational "is the resolver keeping up?" number.

The exact ``/api/stats`` fields, surfaced verbatim
--------------------------------------------------
Every tick prints these server fields **by their exact API keys** so the output is
a faithful mirror of the endpoint (missing/extra fields degrade gracefully):

* counts: ``total``, ``open``, ``due_for_resolution``, ``resolved``, ``voided``
* reputation flow: ``lifetime_reward_aigen_escrowed``,
  ``lifetime_reward_aigen_paid_to_winners_net``, ``lifetime_spam_fees_burned``
* real fees: ``lifetime_protocol_fees_collected`` →
  ``{AIGEN, USDC_micros, ETH_wei}`` (USDC also rendered human)
* parameters: ``protocol_fee_bps``, ``spam_fee_burn_aigen``, ``min_reward_aigen``,
  ``peer_vote_quorum_aigen``

Persistence
-----------
Each snapshot is one JSON object appended as a single line to the ``--state-file``
JSONL ledger (default ``treasury_state.jsonl``). The object carries the captured
raw fields, the four derived metrics, and a ``ts`` (UTC ISO-8601) / ``ts_unix``
stamp. The *previous* line in that file is the baseline for delta computation, so
deltas are durable across process restarts — kill the loop, restart it tomorrow,
and the first new tick still diffs against yesterday's last snapshot.

Dependencies: Python 3.8+ standard library **plus** the ubiquitous ``requests``
package. No OABP SDK import — this file is intentionally copy-pasteable.

Exit codes
----------
* ``0`` — ran (one shot, or a loop that was interrupted cleanly) and printed.
* ``2`` — a network / API error aborted a one-shot run.
* ``3`` — a configuration / usage error.
* ``4`` — the built-in offline self-test failed.
* ``5`` — ``--once`` with ``--alert-*`` thresholds and a threshold was breached
  (so the tool can drive cron / CI alerting via exit status).

Run
---
    # one snapshot against the live API, print fields + derived metrics + deltas
    python3 treasury_monitor.py --once

    # poll every 5 minutes forever, appending to a custom ledger
    python3 treasury_monitor.py --loop --interval 300 --state-file /var/lib/oabp/treasury.jsonl

    # one shot, non-zero exit if backlog is large or escrow liability grew
    python3 treasury_monitor.py --once \
        --alert-due-for-resolution 5 \
        --alert-outstanding-growth 1000

    # run the offline self-test (no network) and exit
    python3 treasury_monitor.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple

try:
    import requests
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write(
        "ERROR: this agent requires the 'requests' package "
        "(pip install requests).\n"
    )
    raise SystemExit(3)


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"
DEFAULT_STATE_FILE = "treasury_state.jsonl"
DEFAULT_INTERVAL = 300.0  # seconds between loop ticks
HTTP_TIMEOUT = 30.0
USDC_MICROS_PER_UNIT = 1_000_000
ETH_WEI_PER_UNIT = 10**18

# Exact integer count fields we mirror from /api/stats (delta-tracked).
COUNT_FIELDS: Tuple[str, ...] = (
    "total",
    "open",
    "due_for_resolution",
    "resolved",
    "voided",
)

# Exact lifetime AIGEN reputation-flow fields (delta-tracked).
AIGEN_FLOW_FIELDS: Tuple[str, ...] = (
    "lifetime_reward_aigen_escrowed",
    "lifetime_reward_aigen_paid_to_winners_net",
    "lifetime_spam_fees_burned",
)

# Exact protocol parameter fields we surface (rarely change; shown, not diffed).
PARAM_FIELDS: Tuple[str, ...] = (
    "protocol_fee_bps",
    "spam_fee_burn_aigen",
    "min_reward_aigen",
    "peer_vote_quorum_aigen",
)

# Derived metric keys, in print order.
DERIVED_FIELDS: Tuple[str, ...] = (
    "outstanding_escrow_aigen",
    "effective_fee_take_pct",
    "burn_ratio_pct",
    "resolution_backlog",
)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    """ISO-8601 in UTC, seconds precision, trailing 'Z'."""
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _num(value: Any, default: float = 0.0) -> float:
    """Best-effort numeric coercion; never raises on junk."""
    if isinstance(value, bool):  # bool is a subclass of int — exclude it
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _int(value: Any, default: int = 0) -> int:
    return int(_num(value, float(default)))


def _get_nested(mapping: Mapping[str, Any], outer: str, inner: str,
                default: Any = 0) -> Any:
    block = mapping.get(outer)
    if isinstance(block, Mapping):
        return block.get(inner, default)
    return default


def _fmt_num(value: float) -> str:
    """Render a number without noise: ints as ints, floats with thousands sep."""
    if value == int(value):
        return f"{int(value):,}"
    return f"{value:,.4f}"


def _fmt_signed(value: float) -> str:
    """Signed delta with thousands separators; '0' for no change."""
    if value == 0:
        return "0"
    if value == int(value):
        return f"{int(value):+,}"
    return f"{value:+,.4f}"


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}%"


def _fmt_pct_delta(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    if value == 0:
        return "0"
    return f"{value:+.4f}pp"


def usdc_micros_to_human(micros: Any) -> str:
    """Render USDC micros (1 USDC == 1_000_000 micros) as a human '$X.XXXXXX'."""
    units = _num(micros) / USDC_MICROS_PER_UNIT
    # 6 decimals = micro resolution; keep the sign for completeness.
    return f"${units:,.6f}"


def eth_wei_to_human(wei: Any) -> str:
    """Render ETH wei as a human ETH amount (mostly zero on this marketplace)."""
    units = _num(wei) / ETH_WEI_PER_UNIT
    return f"{units:.9f}"


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #

def fetch_stats(base_url: str, timeout: float = HTTP_TIMEOUT,
                session: Optional["requests.Session"] = None) -> Dict[str, Any]:
    """GET /api/stats and return the decoded JSON object.

    Raises requests.RequestException on transport errors and ValueError if the
    body is not a JSON object.
    """
    url = base_url.rstrip("/") + "/api/stats"
    sess = session or requests
    resp = sess.get(url, timeout=timeout, headers={"Accept": "application/json"})
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError(
            f"/api/stats returned {type(data).__name__}, expected JSON object"
        )
    return data


# --------------------------------------------------------------------------- #
# Snapshot model
# --------------------------------------------------------------------------- #

def build_snapshot(stats: Mapping[str, Any]) -> Dict[str, Any]:
    """Turn a raw /api/stats payload into a normalised, persisted snapshot.

    The snapshot keeps every tracked field under its **exact API key** plus a
    ``derived`` block and timestamps. Unknown/missing fields default to 0 so the
    monitor never crashes on a sparse or evolving endpoint.
    """
    now = _utc_now()

    counts = {k: _int(stats.get(k, 0)) for k in COUNT_FIELDS}
    aigen_flow = {k: _int(stats.get(k, 0)) for k in AIGEN_FLOW_FIELDS}
    params = {k: _int(stats.get(k, 0)) for k in PARAM_FIELDS}

    fees = {
        "AIGEN": _int(_get_nested(stats, "lifetime_protocol_fees_collected",
                                  "AIGEN", 0)),
        "USDC_micros": _int(_get_nested(stats, "lifetime_protocol_fees_collected",
                                        "USDC_micros", 0)),
        "ETH_wei": _int(_get_nested(stats, "lifetime_protocol_fees_collected",
                                    "ETH_wei", 0)),
    }

    derived = compute_derived(counts, aigen_flow, fees)

    snapshot: Dict[str, Any] = {
        "ts": _iso(now),
        "ts_unix": int(now.timestamp()),
    }
    snapshot.update(counts)
    snapshot.update(aigen_flow)
    snapshot["lifetime_protocol_fees_collected"] = fees
    snapshot.update(params)
    snapshot["derived"] = derived
    return snapshot


def compute_derived(counts: Mapping[str, Any], aigen_flow: Mapping[str, Any],
                    fees: Mapping[str, Any]) -> Dict[str, Any]:
    """Compute the four derived health metrics from already-normalised inputs."""
    escrowed = _num(aigen_flow.get("lifetime_reward_aigen_escrowed", 0))
    paid_net = _num(aigen_flow.get("lifetime_reward_aigen_paid_to_winners_net", 0))
    burned = _num(aigen_flow.get("lifetime_spam_fees_burned", 0))
    fee_aigen = _num(fees.get("AIGEN", 0))

    outstanding = escrowed - paid_net

    # Ratios are undefined (None) when there is no escrow yet — avoids div/0 and
    # avoids printing a fake 0.0000% that looks like a real measurement.
    if escrowed > 0:
        effective_fee_take_pct: Optional[float] = fee_aigen / escrowed * 100.0
        burn_ratio_pct: Optional[float] = burned / escrowed * 100.0
    else:
        effective_fee_take_pct = None
        burn_ratio_pct = None

    backlog = _int(counts.get("open", 0)) + _int(counts.get("due_for_resolution", 0))

    return {
        "outstanding_escrow_aigen": outstanding,
        "effective_fee_take_pct": effective_fee_take_pct,
        "burn_ratio_pct": burn_ratio_pct,
        "resolution_backlog": backlog,
    }


# --------------------------------------------------------------------------- #
# Persistence (JSONL append + last-line read)
# --------------------------------------------------------------------------- #

def read_last_snapshot(state_file: str) -> Optional[Dict[str, Any]]:
    """Return the last valid JSON object in the JSONL ledger, or None.

    Tolerates trailing blank lines and a partially-written final line (in which
    case it walks backwards to the last fully-parseable record).
    """
    if not os.path.exists(state_file):
        return None
    try:
        with open(state_file, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return None
    for raw in reversed(lines):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def append_snapshot(state_file: str, snapshot: Mapping[str, Any]) -> None:
    """Append one snapshot as a single JSON line to the JSONL ledger."""
    directory = os.path.dirname(os.path.abspath(state_file))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory, exist_ok=True)
    line = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
    with open(state_file, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# --------------------------------------------------------------------------- #
# Delta computation
# --------------------------------------------------------------------------- #

def compute_deltas(current: Mapping[str, Any],
                   previous: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Compute field-by-field deltas of `current` vs `previous` snapshot.

    Returns a dict with the same shape as the tracked fields. When `previous` is
    None (first ever snapshot) every delta is None to mean "no baseline".
    """
    have_prev = isinstance(previous, Mapping)

    def d_num(key: str) -> Optional[float]:
        if not have_prev or key not in previous:
            return None
        return _num(current.get(key, 0)) - _num(previous.get(key, 0))

    def d_fee(key: str) -> Optional[float]:
        cur = _num(_get_nested(current, "lifetime_protocol_fees_collected", key, 0))
        if not have_prev:
            return None
        prev_block = previous.get("lifetime_protocol_fees_collected")
        if not isinstance(prev_block, Mapping) or key not in prev_block:
            return None
        return cur - _num(prev_block.get(key, 0))

    def d_derived(key: str) -> Optional[float]:
        cur_block = current.get("derived")
        if not isinstance(cur_block, Mapping):
            return None
        cur_val = cur_block.get(key)
        if not have_prev:
            return None
        prev_block = previous.get("derived")
        if not isinstance(prev_block, Mapping):
            return None
        prev_val = prev_block.get(key)
        if cur_val is None or prev_val is None:
            return None
        return _num(cur_val) - _num(prev_val)

    deltas: Dict[str, Any] = {"_has_baseline": have_prev}
    for key in COUNT_FIELDS + AIGEN_FLOW_FIELDS:
        deltas[key] = d_num(key)
    deltas["fees"] = {
        "AIGEN": d_fee("AIGEN"),
        "USDC_micros": d_fee("USDC_micros"),
        "ETH_wei": d_fee("ETH_wei"),
    }
    deltas["derived"] = {key: d_derived(key) for key in DERIVED_FIELDS}
    return deltas


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #

def evaluate_alerts(snapshot: Mapping[str, Any], deltas: Mapping[str, Any],
                    *, due_threshold: Optional[int],
                    outstanding_growth: Optional[float]) -> List[str]:
    """Return a list of human-readable alert strings for any breached threshold."""
    alerts: List[str] = []

    if due_threshold is not None:
        due = _int(snapshot.get("due_for_resolution", 0))
        if due > due_threshold:
            alerts.append(
                f"due_for_resolution={due} exceeds threshold {due_threshold} "
                f"(resolver backlog)"
            )

    if outstanding_growth is not None:
        d_out = deltas.get("derived", {}).get("outstanding_escrow_aigen")
        if d_out is not None and d_out > outstanding_growth:
            alerts.append(
                f"outstanding escrow grew by {_fmt_signed(d_out)} AIGEN, exceeds "
                f"threshold +{_fmt_num(outstanding_growth)} (escrow outpacing payouts)"
            )

    return alerts


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def render_report(snapshot: Mapping[str, Any], deltas: Mapping[str, Any],
                  alerts: List[str]) -> str:
    """Build the full human-readable tick report as a string."""
    out: List[str] = []
    have_prev = bool(deltas.get("_has_baseline"))
    baseline_note = "" if have_prev else "  (first snapshot — no baseline yet)"

    out.append("=" * 72)
    out.append(f"OABP / AIGEN treasury snapshot @ {snapshot.get('ts', '?')}"
               f"{baseline_note}")
    out.append("=" * 72)
    out.append("Reminder: AIGEN is play-money reputation/points. The only real")
    out.append("money is the USDC fee, shown in micros (1 USDC = 1,000,000 micros).")
    out.append("")

    # --- Mission counts ----------------------------------------------------- #
    out.append("Mission counts (exact /api/stats keys):")
    for key in COUNT_FIELDS:
        cur = _int(snapshot.get(key, 0))
        d = deltas.get(key)
        d_str = _fmt_signed(d) if d is not None else "(no baseline)"
        out.append(f"  {key:<22} = {_fmt_num(cur):>14}   Δ {d_str}")
    out.append("")

    # --- AIGEN reputation flow --------------------------------------------- #
    out.append("AIGEN reputation flow (play-money points, not revenue):")
    for key in AIGEN_FLOW_FIELDS:
        cur = _int(snapshot.get(key, 0))
        d = deltas.get(key)
        d_str = _fmt_signed(d) if d is not None else "(no baseline)"
        out.append(f"  {key:<46} = {_fmt_num(cur):>12}   Δ {d_str}")
    out.append("")

    # --- Real protocol fees ------------------------------------------------- #
    fees = snapshot.get("lifetime_protocol_fees_collected", {})
    if not isinstance(fees, Mapping):
        fees = {}
    fee_deltas = deltas.get("fees", {})
    usdc_micros = _int(fees.get("USDC_micros", 0))
    out.append("Real protocol fees collected (lifetime_protocol_fees_collected):")
    d_aigen = fee_deltas.get("AIGEN")
    out.append(
        f"  AIGEN        = {_fmt_num(_int(fees.get('AIGEN', 0))):>14}   "
        f"Δ {_fmt_signed(d_aigen) if d_aigen is not None else '(no baseline)'}"
    )
    d_usdc = fee_deltas.get("USDC_micros")
    out.append(
        f"  USDC_micros  = {_fmt_num(usdc_micros):>14}   "
        f"Δ {_fmt_signed(d_usdc) if d_usdc is not None else '(no baseline)'}"
    )
    out.append(
        f"  USDC (human) = {usdc_micros_to_human(usdc_micros):>14}   "
        f"(= USDC_micros / 1,000,000)"
    )
    d_eth = fee_deltas.get("ETH_wei")
    eth_wei = _int(fees.get("ETH_wei", 0))
    out.append(
        f"  ETH_wei      = {_fmt_num(eth_wei):>14}   "
        f"Δ {_fmt_signed(d_eth) if d_eth is not None else '(no baseline)'}"
    )
    out.append(f"  ETH (human)  = {eth_wei_to_human(eth_wei):>14} ETH")
    out.append("")

    # --- Protocol parameters ----------------------------------------------- #
    out.append("Protocol parameters (config, shown for context):")
    for key in PARAM_FIELDS:
        out.append(f"  {key:<22} = {_fmt_num(_int(snapshot.get(key, 0))):>14}")
    out.append("")

    # --- Derived metrics ---------------------------------------------------- #
    derived = snapshot.get("derived", {})
    if not isinstance(derived, Mapping):
        derived = {}
    d_derived = deltas.get("derived", {})
    out.append("Derived health metrics:")

    out.append(
        f"  outstanding_escrow_aigen  = "
        f"{_fmt_num(_num(derived.get('outstanding_escrow_aigen', 0))):>14}   "
        f"Δ {_fmt_signed(d_derived.get('outstanding_escrow_aigen')) if d_derived.get('outstanding_escrow_aigen') is not None else '(no baseline)'}"
    )
    out.append("      (escrowed - paid_to_winners_net = in-flight committed reputation)")

    out.append(
        f"  effective_fee_take_pct    = "
        f"{_fmt_pct(derived.get('effective_fee_take_pct')):>14}   "
        f"Δ {_fmt_pct_delta(d_derived.get('effective_fee_take_pct'))}"
    )
    out.append("      (realised AIGEN fee / escrowed; compare to protocol_fee_bps)")

    out.append(
        f"  burn_ratio_pct            = "
        f"{_fmt_pct(derived.get('burn_ratio_pct')):>14}   "
        f"Δ {_fmt_pct_delta(d_derived.get('burn_ratio_pct'))}"
    )
    out.append("      (spam_fees_burned / escrowed)")

    out.append(
        f"  resolution_backlog        = "
        f"{_fmt_num(_num(derived.get('resolution_backlog', 0))):>14}   "
        f"Δ {_fmt_signed(d_derived.get('resolution_backlog')) if d_derived.get('resolution_backlog') is not None else '(no baseline)'}"
    )
    out.append(
        f"      (open + due_for_resolution; due_for_resolution="
        f"{_int(snapshot.get('due_for_resolution', 0))} awaiting resolver)"
    )
    out.append("")

    # --- Alerts ------------------------------------------------------------- #
    if alerts:
        out.append("!! ALERTS:")
        for a in alerts:
            out.append(f"   * {a}")
    else:
        out.append("Alerts: none")
    out.append("=" * 72)
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# One tick = fetch + snapshot + persist + diff + render
# --------------------------------------------------------------------------- #

def run_tick(base_url: str, state_file: str, *,
             due_threshold: Optional[int],
             outstanding_growth: Optional[float],
             session: Optional["requests.Session"] = None,
             stats_override: Optional[Mapping[str, Any]] = None) -> Tuple[
                 Dict[str, Any], Dict[str, Any], List[str]]:
    """Perform a single monitoring tick.

    If `stats_override` is provided the network fetch is skipped (used by the
    self-test and by callers feeding synthetic data). Returns
    ``(snapshot, deltas, alerts)``.
    """
    stats = dict(stats_override) if stats_override is not None else fetch_stats(
        base_url, session=session)

    previous = read_last_snapshot(state_file)
    snapshot = build_snapshot(stats)
    deltas = compute_deltas(snapshot, previous)
    alerts = evaluate_alerts(
        snapshot, deltas,
        due_threshold=due_threshold,
        outstanding_growth=outstanding_growth,
    )
    append_snapshot(state_file, snapshot)
    return snapshot, deltas, alerts


# --------------------------------------------------------------------------- #
# Offline self-test (no network)
# --------------------------------------------------------------------------- #

def _self_test() -> int:
    """Feed two synthetic snapshots through the pipeline and assert behaviour.

    Verifies:
      * derived metrics (outstanding, effective fee take, burn ratio, backlog),
      * USDC micros -> human rendering,
      * JSONL append (two lines after two ticks),
      * delta computation across the two ticks (e.g. +N resolved),
      * the rendered report contains the expected delta strings.
    """
    import tempfile

    failures: List[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            failures.append(msg)

    # --- Synthetic snapshot #1 (baseline) ---------------------------------- #
    stats1: Dict[str, Any] = {
        "total": 2300,
        "open": 7,
        "due_for_resolution": 1,
        "resolved": 2160,
        "voided": 121,
        "lifetime_reward_aigen_escrowed": 122000,
        "lifetime_reward_aigen_paid_to_winners_net": 112000,
        "lifetime_spam_fees_burned": 11400,
        "lifetime_protocol_fees_collected": {
            "AIGEN": 20,
            "USDC_micros": 350,
            "USDC_human": "$0.000350",
            "ETH_wei": 0,
            "ETH_human": "0.000000000",
        },
        "protocol_fee_bps": 50,
        "spam_fee_burn_aigen": 5,
        "min_reward_aigen": 10,
        "peer_vote_quorum_aigen": 50,
    }

    # --- Synthetic snapshot #2 (later: +6 resolved, +2 total, escrow grows) - #
    stats2: Dict[str, Any] = dict(stats1)
    stats2["total"] = 2302
    stats2["open"] = 4
    stats2["due_for_resolution"] = 0
    stats2["resolved"] = 2166        # +6 resolved vs baseline
    stats2["lifetime_reward_aigen_escrowed"] = 122325      # +325
    stats2["lifetime_reward_aigen_paid_to_winners_net"] = 112483  # +483
    stats2["lifetime_spam_fees_burned"] = 11475            # +75
    stats2["lifetime_protocol_fees_collected"] = {
        "AIGEN": 22,                 # +2
        "USDC_micros": 350,          # unchanged
        "ETH_wei": 0,
    }

    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.join(tmp, "treasury_state.jsonl")

        # --- Tick 1: no baseline, all deltas None -------------------------- #
        snap1, d1, a1 = run_tick(
            base_url="http://example.invalid", state_file=state,
            due_threshold=None, outstanding_growth=None,
            stats_override=stats1,
        )
        check(d1.get("_has_baseline") is False,
              "tick1 should have no baseline")
        check(snap1["derived"]["outstanding_escrow_aigen"] == 10000.0,
              f"tick1 outstanding should be 10000, got "
              f"{snap1['derived']['outstanding_escrow_aigen']}")
        check(snap1["derived"]["resolution_backlog"] == 8,
              f"tick1 backlog should be 8 (open7+due1), got "
              f"{snap1['derived']['resolution_backlog']}")
        # effective fee take = 20 / 122000 * 100
        eff = snap1["derived"]["effective_fee_take_pct"]
        check(abs(eff - (20 / 122000 * 100)) < 1e-9,
              f"tick1 effective_fee_take_pct wrong: {eff}")
        # burn ratio = 11400 / 122000 * 100
        br = snap1["derived"]["burn_ratio_pct"]
        check(abs(br - (11400 / 122000 * 100)) < 1e-9,
              f"tick1 burn_ratio_pct wrong: {br}")
        check(a1 == [], f"tick1 should have no alerts, got {a1}")

        # --- Tick 2: baseline = tick1 -------------------------------------- #
        snap2, d2, a2 = run_tick(
            base_url="http://example.invalid", state_file=state,
            due_threshold=5, outstanding_growth=1000,
            stats_override=stats2,
        )
        check(d2.get("_has_baseline") is True,
              "tick2 should have a baseline")
        # +6 resolved is the headline delta we asserted in the spec.
        check(d2.get("resolved") == 6.0,
              f"tick2 resolved delta should be +6, got {d2.get('resolved')}")
        check(d2.get("total") == 2.0,
              f"tick2 total delta should be +2, got {d2.get('total')}")
        check(d2.get("open") == -3.0,
              f"tick2 open delta should be -3, got {d2.get('open')}")
        check(d2.get("lifetime_reward_aigen_escrowed") == 325.0,
              f"tick2 escrowed delta should be +325, got "
              f"{d2.get('lifetime_reward_aigen_escrowed')}")
        # outstanding: tick2 (122325-112483=9842) - tick1 (10000) = -158
        out_d = d2["derived"]["outstanding_escrow_aigen"]
        check(out_d == -158.0,
              f"tick2 outstanding delta should be -158, got {out_d}")
        check(snap2["derived"]["outstanding_escrow_aigen"] == 9842.0,
              f"tick2 outstanding should be 9842, got "
              f"{snap2['derived']['outstanding_escrow_aigen']}")
        # AIGEN fee delta +2
        check(d2["fees"].get("AIGEN") == 2.0,
              f"tick2 AIGEN fee delta should be +2, got {d2['fees'].get('AIGEN')}")
        check(d2["fees"].get("USDC_micros") == 0.0,
              f"tick2 USDC_micros fee delta should be 0, got "
              f"{d2['fees'].get('USDC_micros')}")
        # No alerts: due_for_resolution=0 (<=5), outstanding shrank (not >1000).
        check(a2 == [], f"tick2 should have no alerts, got {a2}")

        # --- JSONL append: exactly two records ----------------------------- #
        with open(state, "r", encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        check(len(lines) == 2,
              f"JSONL ledger should have 2 lines, got {len(lines)}")
        try:
            rec0 = json.loads(lines[0])
            rec1 = json.loads(lines[1])
            check(rec0["resolved"] == 2160 and rec1["resolved"] == 2166,
                  "JSONL records out of order or wrong content")
        except (json.JSONDecodeError, KeyError) as exc:
            failures.append(f"JSONL records not parseable: {exc}")

        # --- USDC micros -> human rendering -------------------------------- #
        check(usdc_micros_to_human(350) == "$0.000350",
              f"usdc render wrong: {usdc_micros_to_human(350)}")
        check(usdc_micros_to_human(1_500_000) == "$1.500000",
              f"usdc render wrong: {usdc_micros_to_human(1_500_000)}")

        # --- Rendered report contains the expected delta strings ----------- #
        report = render_report(snap2, d2, a2)
        check("+6" in report,
              "rendered report should show '+6' resolved delta")
        check("$0.000350" in report,
              "rendered report should show human USDC '$0.000350'")
        check("outstanding_escrow_aigen" in report,
              "rendered report should include outstanding_escrow_aigen")

        # --- Alert path: force a breach ------------------------------------ #
        stats3 = dict(stats2)
        stats3["due_for_resolution"] = 9          # > threshold 5
        stats3["lifetime_reward_aigen_escrowed"] = 999999  # huge escrow jump
        snap3, d3, a3 = run_tick(
            base_url="http://example.invalid", state_file=state,
            due_threshold=5, outstanding_growth=1000,
            stats_override=stats3,
        )
        check(len(a3) == 2,
              f"tick3 should raise 2 alerts (due + outstanding), got {a3}")
        check(any("due_for_resolution" in a for a in a3),
              "tick3 should alert on due_for_resolution")
        check(any("outstanding escrow grew" in a for a in a3),
              "tick3 should alert on outstanding escrow growth")

    if failures:
        sys.stderr.write("SELF-TEST FAILED:\n")
        for f in failures:
            sys.stderr.write(f"  - {f}\n")
        return 4
    sys.stdout.write("self-test OK: derived metrics, deltas (+6 resolved), "
                     "JSONL append, USDC human render, and alerts all verified.\n")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="treasury_monitor.py",
        description=(
            "Snapshot OABP / AIGEN protocol economics from /api/stats, persist to "
            "a JSONL ledger, and print deltas vs the previous snapshot. AIGEN is "
            "play-money reputation; real USDC fees are micros."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--base-url", default=DEFAULT_BASE_URL,
        help=f"Marketplace base URL (default: {DEFAULT_BASE_URL})",
    )
    p.add_argument(
        "--state-file", default=DEFAULT_STATE_FILE,
        help=f"JSONL ledger to append snapshots to (default: {DEFAULT_STATE_FILE})",
    )

    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--once", action="store_true",
        help="Take exactly one snapshot and exit (default mode).",
    )
    mode.add_argument(
        "--loop", action="store_true",
        help="Poll forever every --interval seconds (Ctrl-C to stop).",
    )

    p.add_argument(
        "--interval", type=float, default=DEFAULT_INTERVAL,
        help=f"Seconds between ticks in --loop mode (default: {int(DEFAULT_INTERVAL)}).",
    )
    p.add_argument(
        "--alert-due-for-resolution", type=int, default=None, metavar="N",
        help="Alert when due_for_resolution exceeds N (resolver backlog).",
    )
    p.add_argument(
        "--alert-outstanding-growth", type=float, default=None, metavar="AIGEN",
        help=("Alert when outstanding escrow (escrowed - paid_net) grows by more "
              "than this many AIGEN vs the previous snapshot."),
    )
    p.add_argument(
        "--self-test", action="store_true",
        help="Run the offline self-test (no network) and exit.",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.self_test:
        return _self_test()

    if args.interval <= 0:
        sys.stderr.write("ERROR: --interval must be > 0.\n")
        return 3

    base_url = args.base_url
    state_file = args.state_file
    due_threshold = args.alert_due_for_resolution
    outstanding_growth = args.alert_outstanding_growth

    # --- Loop mode --------------------------------------------------------- #
    if args.loop:
        session = requests.Session()
        tick_no = 0
        try:
            while True:
                tick_no += 1
                try:
                    snapshot, deltas, alerts = run_tick(
                        base_url, state_file,
                        due_threshold=due_threshold,
                        outstanding_growth=outstanding_growth,
                        session=session,
                    )
                    print(render_report(snapshot, deltas, alerts))
                    sys.stdout.flush()
                except requests.RequestException as exc:
                    sys.stderr.write(
                        f"[tick {tick_no}] network/API error: {exc} "
                        f"(will retry in {args.interval:.0f}s)\n"
                    )
                except ValueError as exc:
                    sys.stderr.write(
                        f"[tick {tick_no}] bad response: {exc} "
                        f"(will retry in {args.interval:.0f}s)\n"
                    )
                time.sleep(args.interval)
        except KeyboardInterrupt:
            sys.stderr.write("\nInterrupted — exiting cleanly.\n")
            return 0

    # --- One-shot mode (default) ------------------------------------------- #
    try:
        snapshot, deltas, alerts = run_tick(
            base_url, state_file,
            due_threshold=due_threshold,
            outstanding_growth=outstanding_growth,
        )
    except requests.RequestException as exc:
        sys.stderr.write(f"ERROR: could not reach {base_url}/api/stats: {exc}\n")
        return 2
    except ValueError as exc:
        sys.stderr.write(f"ERROR: bad /api/stats response: {exc}\n")
        return 2

    print(render_report(snapshot, deltas, alerts))

    # Non-zero exit on a one-shot alert so cron / CI can react to exit status.
    if alerts:
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
