#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OABP / AIGEN oracle mission verifier: *a submitted dataset URL is a real
dataset that meets the mission's schema* (CSV / JSONL / JSON).

What this is
============
A new **oracle** mission-type verifier for the OABP / AIGEN agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``. It resolves missions whose
deliverable is a **downloadable dataset** — e.g. *"produce a CSV of >= 1,000
token-pairs with columns ``symbol, address, chain, decimals`` and host it at a
public URL"*, or *"deliver a JSONL training set of >= 5,000 records, each with
keys ``prompt`` (string) and ``label`` (one of …) "*. The agent's submission
``proof`` is the URL the dataset is reachable at; this verifier downloads it
(size-capped), parses it with the **standard library only**, and decides whether
it satisfies the mission's declarative schema.

The protocol already ships oracle backends that are **content-addressed** (anyone
can re-run them and get the same verdict from a public read-only source):
**GoPlus** (token-security for safety-review missions), the **GitHub REST API**
(repo deliverables), the package-publish verifiers (**PyPI**, **npm**), and the
**URL-liveness** oracle. This module adds a *dataset-shape* oracle in the same
spirit:

* **Read-only.** It issues a single ``GET`` (optionally following redirects),
  never a write/POST. It downloads at most ``max_bytes`` of the body and
  **never executes, imports, evals, or renders** anything — it only *parses and
  inspects* the bytes with ``csv`` / ``json``. No pickle, no code paths, no
  eval; a malicious dataset is at most malformed text, which yields a reject.
* **Content-addressed.** The verdict is a pure function of what the public URL
  returns: the bytes, parsed under a fixed grammar, checked against a small set
  of declarative assertions (format, row/record count, required columns/keys,
  per-field types, integrity). Any auditor can re-run the same ``GET`` + parse
  and re-derive the result. The full trace — observed format, byte count, row
  count, the columns/keys seen, and every violation — is returned in
  ``VerifyResult.evidence``.
* **Fail-closed.** Anything it cannot affirmatively confirm — a wrong/unparseable
  format, too few rows, a missing required column/key in *any* sampled record, a
  per-field type mismatch, an empty file, an inconsistent header — yields
  ``verified=False`` with a precise, human-readable reason and a list of the
  first few ``violations``. Network / DNS / TLS / oversize failures are
  *verdicts* (the dataset is not verifiably present/conformant), not crashes.
* **SSRF-hardened.** By default the verifier **refuses** to fetch private,
  loopback, link-local, or otherwise non-public hosts (``127.0.0.1``,
  ``localhost``, ``10.0.0.0/8``, ``169.254.169.254``, IPv6 ULA/loopback, …),
  enforced on **every hop** of a redirect chain. An oracle that a resolver runs
  against arbitrary submitter-controlled URLs is a classic *server-side request
  forgery* primitive; blocking private address space by default prevents a
  submission from coaxing the resolver into probing its own internal network.
  See "SSRF / safety" below. (When ``source_url`` is pinned in the params, the
  proof URL must additionally equal it — binding the deliverable to an expected
  location.)

It depends on the **Python standard library only** (``csv``, ``json``,
``urllib``, ``http.client``, ``socket``, ``ipaddress``, ``io``), so it runs in a
resolver with zero third-party packages installed. Python 3.7+.

Why a dataset-shape oracle is sound (and its limits)
----------------------------------------------------
A public, downloadable dataset is a re-runnable, content-addressed witness: at
the moment of verification, ``GET <url>`` returns bytes that either do or do not
parse as the required format and satisfy the schema. That is exactly the
machine-checkable core of "deliver a dataset of shape X". The verifier records
the observed format, byte/row counts, the header/keys, and which checks ran in
``evidence`` so a creator/auditor can re-derive the verdict.

Its limits are inherent and the mission designer should account for them:

* **It proves shape, not authorship, novelty, or semantic correctness.** The
  oracle confirms the *structure* (format, count, columns/keys, field types,
  integrity). It does **not** confirm the values are *correct*, *novel*, or
  *non-plagiarised* — anyone can host a conformant-but-junk CSV. For value-level
  guarantees, pin ``source_url`` to a domain you control/expect, put a
  mission-issued nonce column/key in ``required_columns`` /
  ``required_keys`` + ``schema`` (a token the creator hands the solver
  out-of-band, raising the bar from "right shape" to "right shape carrying the
  mission's secret"), and/or layer a peer-vote / creator-judges stage on top of
  a ``verified=True`` from this oracle.
* **Sampling on huge files.** To verify a mult-million-row dataset without
  reading it all into memory, the row/record-count check streams the *whole*
  file (counting every row up to a hard cap), but the *per-field type* and
  *required-column/key presence* checks are applied to at most the first
  ``sample_rows`` records (default 1000). So a dataset that is conformant in its
  first ``sample_rows`` rows and short/garbage afterwards could pass type/key
  checks while still failing (or passing) the count check. This is the standard
  cost of bounded verification; raise ``sample_rows`` (up to where ``max_bytes``
  is exhausted) to widen the type/key window, or set ``sample_rows: 0`` to check
  *every* row that fits under ``max_bytes``. The count itself is never sampled —
  it reflects all rows the verifier could read within ``max_bytes`` (and if the
  body is truncated at ``max_bytes`` the count is reported as a *lower bound* and
  a ``min_rows`` pass on truncated data is treated conservatively; see below).

What the verifier checks (all configured checks must hold for ``verified=True``)
--------------------------------------------------------------------------------
Given a mission's ``verification_params`` (schema below) and a submission
``proof`` carrying the dataset URL:

1. **URL PARSES & IS ALLOWED** — the proof yields an ``http(s)`` URL. If
   ``source_url`` is set, the proof URL must equal it (normalised). The host is
   checked against the **SSRF blocklist** (private / loopback / link-local /
   reserved address space, by name *and* by every resolved IP) unless
   ``allow_private`` is explicitly true.
2. **DOWNLOADED** — a single ``GET`` (with ``timeout``, ``max_bytes`` cap, and
   optional redirect following) completes without a transport error, and the
   final status is ``200`` (or in ``expect_status``). A DNS / connection / TLS /
   timeout / non-200 failure ⇒ the dataset is not verifiably present ⇒ reject.
3. **NON-EMPTY** — the downloaded body is non-empty (and, for CSV, has at least a
   header plus one data row; for JSON, a non-empty array / object-of-records).
4. **PARSES AS <format>** — the bytes parse under the declared ``format``
   (``csv`` | ``jsonl`` | ``json``) with the stdlib. CSV uses ``csv.reader`` /
   ``csv.DictReader`` (consistent column count per row = "consistent header");
   ``jsonl`` parses one JSON value per non-blank line; ``json`` parses a single
   JSON document that must be an array of objects (or an object whose values, or
   whose ``data`` / ``rows`` / ``records`` / ``items`` field, is such an array).
   A parse error on any required row ⇒ reject (with the line/row number).
5. **ROW/RECORD COUNT >= min_rows** — the number of *data* records (excluding the
   CSV header) is at least ``min_rows``.
6. **REQUIRED COLUMNS / KEYS PRESENT IN EVERY (sampled) RECORD** — every name in
   ``required_columns`` (CSV) or ``required_keys`` (JSON/JSONL) appears in every
   sampled record. For CSV this is enforced once on the header *and* per-row
   (rows must not be short). For JSON/JSONL each sampled object must contain
   every required key.
7. **PER-FIELD TYPE CONFORMANCE** *(optional)* — where ``schema`` maps a
   field/column to a type (``string`` | ``int`` | ``integer`` | ``number`` |
   ``float`` | ``bool`` | ``boolean`` | ``null`` | ``array`` | ``object`` |
   ``any``, optionally ``"type?"`` to allow null/empty, or a list of allowed
   types), every sampled record's value for that field must conform. For CSV
   (all values are strings) the check is *parse-able-as*: ``int`` ⇒ the string is
   an integer literal, ``number`` ⇒ a float literal, ``bool`` ⇒
   ``true/false/0/1/yes/no`` (case-insensitive), etc. For JSON/JSONL the check is
   against the actual JSON type.
8. **BASIC INTEGRITY** — no empty file; a consistent header (CSV: every row has
   the same column count as the header; JSON: top-level is a records array, not a
   scalar; JSONL: no blank-line-only file). Duplicate column names in a CSV
   header, or a ragged row, are integrity violations.

Any configured check that does not affirmatively pass yields ``verified=False``
and a ``detail`` naming the first failing check, plus ``evidence['violations']``
(a capped list of structured ``{check, row?, column?, key?, reason}`` records)
and ``evidence['rows']`` / ``evidence['columns']`` per the OABP evidence
convention for this verifier (``evidence['rows']``, ``evidence['columns']``, and
``evidence['violations']`` are ALWAYS present).

The proof format
----------------
``proof`` is simply **the URL** the dataset is downloadable at — e.g.
``"https://data.example.com/pairs.csv"``. For convenience the verifier also
accepts a JSON object ``{"url": "..."}`` (or ``{"dataset_url": ...}`` /
``{"download_url": ...}`` / ``{"link": ...}``) and a bare host
(``data.example.com/x`` → ``https://data.example.com/x``). When the params do
not pin a ``format``, the verifier infers it from the URL extension
(``.csv`` → csv, ``.jsonl`` / ``.ndjson`` → jsonl, ``.json`` → json) and, failing
that, from the response ``Content-Type`` (``text/csv``, ``application/x-ndjson``,
``application/json``); if still ambiguous it defaults to ``csv``. Pinning
``format`` in the params is recommended.

verification_params schema
==========================
The mission's ``verification_params`` object (the ``oracle`` arm of the protocol)
for this mission-type is::

    {
      # FORMAT — one of "csv" | "jsonl" | "json". Optional: if omitted, inferred
      # from the URL extension then the Content-Type, defaulting to "csv".
      "format": "csv",

      # SIZE — minimum number of DATA records (CSV: excludes the header row).
      "min_rows": 1000,                 # int >= 0; default 0 (no minimum)

      # COLUMNS / KEYS — the required field names that must be present in EVERY
      # sampled record. Use `required_columns` for csv and `required_keys` for
      # json/jsonl; either name is accepted for any format (they are aliases).
      "required_columns": ["symbol", "address", "chain", "decimals"],  # [str]
      # "required_keys": ["prompt", "label"],                          # alias

      # SCHEMA — OPTIONAL per-field type map. Keys are field/column names; values
      # are a type name, a "type?" (nullable/optional-empty), or a list of
      # allowed type names. Recognised types:
      #   "string","int"/"integer","number"/"float","bool"/"boolean",
      #   "null","array","object","any".
      # A trailing "?" (e.g. "int?") additionally allows JSON null / empty-string
      # (CSV). A field in `schema` is implicitly required UNLESS its type set
      # includes "null"/"?" or "any" — set `schema_implies_required: false` to
      # turn that off and only require names listed in required_columns/keys.
      "schema": {
        "symbol":   "string",
        "address":  "string",
        "chain":    "string",
        "decimals": "int",
        "score":    "number?",          # nullable / may be empty in CSV
        "tags":     ["array", "null"]   # JSON array or null (json/jsonl only)
      },
      "schema_implies_required": true,  # bool; default true

      # SAMPLING — the per-field type & required-key checks run on at most this
      # many leading records (the COUNT check always streams every row that fits
      # under max_bytes). 0 = check every readable row. Default 1000.
      "sample_rows": 1000,              # int >= 0; default 1000

      # CSV DIALECT — optional hints for the stdlib csv parser.
      "delimiter": ",",                 # str (single char); default ","
      "has_header": true,               # bool; default true (first row = header)
      "encoding": "utf-8",              # str; body decode charset; default utf-8

      # FETCH CONTROLS.
      "max_bytes": 33554432,            # int; hard cap on body read (default 32 MiB)
      "timeout": 30,                    # float seconds; per-request (default 30)
      "expect_status": 200,             # int | [int,...]; acceptable final status
      "follow_redirects": true,         # bool; follow 3xx (default true)
      "max_redirects": 5,               # int; redirect hops allowed (default 5)

      # TARGET PINNING — bind the deliverable to an exact URL you expect, so a
      # submitter can't satisfy the mission by hosting the dataset elsewhere.
      "source_url": "https://data.example.com/pairs.csv",  # str|null

      # SSRF GUARD — keep FALSE in production. When false (default) the verifier
      # refuses private/loopback/link-local/reserved targets by name and by every
      # resolved IP. Only set true for trusted internal testing.
      "allow_private": false,           # bool; default false

      # human-readable spec; surfaced to solvers, not parsed by the oracle.
      "oracle_description":
          "Deliver a CSV of >=1000 token-pairs with columns symbol,address,chain,decimals."
    }

Nothing forces a *content* constraint, but a sensible dataset mission sets at
least one of ``min_rows`` / ``required_columns`` / ``required_keys`` / ``schema``;
with none of them the oracle only checks "downloads, non-empty, and parses as
<format>" (and :meth:`VerificationParams.from_mapping` emits that as the
``evidence``/``detail`` so the creator can see the bar was minimal).
``oracle_description`` is free text for humans/solvers; the machine truth is the
typed fields above.

Worked example
==============
Mission::

    verification_params = {
        "format": "csv",
        "min_rows": 3,
        "required_columns": ["symbol", "address", "decimals"],
        "schema": {"symbol": "string", "address": "string", "decimals": "int"},
        "source_url": "https://data.example.com/pairs.csv",
        "oracle_description":
            "Deliver a CSV of >=3 token-pairs with symbol,address,decimals.",
    }

An agent hosts the file and submits ``proof = "https://data.example.com/pairs.csv"``.
The verifier:

* parses the proof -> ``https://data.example.com/pairs.csv``; equals
  ``source_url``; host is public (not private) -> allowed; ✓
* ``GET`` the URL -> HTTP ``200`` within the 32 MiB cap; body non-empty; ✓
* parses as CSV; header ``symbol,address,decimals`` -> contains all required
  columns; every row has 3 fields (consistent header); ✓
* 4 data rows >= ``min_rows`` (3); ✓
* per row: ``symbol``/``address`` are strings (always true for CSV), ``decimals``
  parses as ``int``; ✓

=> ``VerifyResult(verified=True, detail="dataset … 4 rows, columns
[symbol,address,decimals] … verified", evidence={"rows":4, "columns":[…],
"violations":[]})``. Had the file had 2 rows, omitted ``decimals``, carried a
non-integer ``decimals``, or been hosted off ``data.example.com``, the result
would be ``verified=False`` with the corresponding ``violations``.

CLI
===
    # verify a live submission against the public internet:
    python3 dataset_verifier.py \
        --format csv --min-rows 1000 \
        --required-columns symbol,address,chain,decimals \
        --schema 'decimals=int' --schema 'score=number?' \
        --source-url https://data.example.com/pairs.csv \
        --proof https://data.example.com/pairs.csv

    # verify a LOCAL file (skips the network; --file <path> bypasses the GET):
    python3 dataset_verifier.py --format jsonl --min-rows 2 \
        --required-keys prompt,label --file ./train.jsonl

    # run the bundled OFFLINE self-test (stubs the transport; no network) and exit:
    python3 dataset_verifier.py --self-test

Exit codes (CLI):
* ``0`` — verified True (or, under --self-test, all assertions passed).
* ``1`` — verified False (the submission does not satisfy the mission).
* ``2`` — usage / configuration error.
"""

from __future__ import annotations

import argparse
import csv
import http.client
import io
import ipaddress
import json
import os
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

__all__ = [
    "VerifyResult",
    "VerificationParams",
    "HttpResponse",
    "HttpClient",
    "HttpError",
    "SSRFBlocked",
    "DatasetParseError",
    "verify",
    "verify_mission",
    "verify_bytes",
    "parse_proof_url",
    "normalize_url",
    "is_public_host",
    "check_value_type",
    "DEFAULT_MAX_BYTES",
    "DEFAULT_TIMEOUT",
    "DEFAULT_SAMPLE_ROWS",
    "DEFAULT_MAX_VIOLATIONS",
]

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_MAX_BYTES = 32 << 20         # 32 MiB body cap (datasets are bigger than pages)
DEFAULT_TIMEOUT = 30.0               # seconds per request
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_SAMPLE_ROWS = 1000           # type/key checks applied to first N records
DEFAULT_MAX_VIOLATIONS = 50          # cap on the violations list in evidence
DEFAULT_MAX_CSV_FIELD = 1 << 20      # csv.field_size_limit guard (1 MiB / field)
USER_AGENT = "oabp-dataset-verifier/1.0 (+https://cryptogenesis.duckdns.org)"

VALID_FORMATS = ("csv", "jsonl", "json")

# Type aliases recognised in `schema`. Canonical -> set of accepted spellings.
_TYPE_ALIASES = {
    "string": "string", "str": "string", "text": "string",
    "int": "int", "integer": "int",
    "number": "number", "float": "number", "double": "number", "decimal": "number",
    "bool": "bool", "boolean": "bool",
    "null": "null", "none": "null",
    "array": "array", "list": "array",
    "object": "object", "dict": "object", "map": "object",
    "any": "any", "*": "any",
}

# A transport is any callable (method, url, headers, timeout, max_bytes) -> HttpResponse.
# Injecting one lets the offline self-test stub the network with zero sockets.
Transport = Callable[..., "HttpResponse"]


# --------------------------------------------------------------------------- #
# Result + params dataclasses
# --------------------------------------------------------------------------- #
@dataclass
class VerifyResult:
    """Typed outcome of an oracle verification.

    Attributes
    ----------
    verified:
        ``True`` only if every configured check passed. The protocol pays the
        bounty iff this is ``True``.
    detail:
        Human-readable one-line explanation (the accept reason, or the FIRST
        failing check and why). Safe to log / surface to the creator.
    evidence:
        Structured, content-addressed trace of what the dataset contained and
        which checks ran. For this verifier the convention is that ``evidence``
        always carries (at least) ``rows`` (int), ``columns`` (list[str]), and
        ``violations`` (list of structured records), alongside the observed
        ``format``, ``bytes`` read, a ``truncated`` flag, and a per-check map.
        Always JSON-serialisable.
    """

    verified: bool
    detail: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verified": self.verified,
            "detail": self.detail,
            "evidence": self.evidence,
        }

    def __bool__(self) -> bool:  # truthy == verified, convenient in callers
        return self.verified


@dataclass(frozen=True)
class FieldType:
    """A parsed per-field type spec from ``schema``.

    ``types`` is the set of accepted canonical type names; ``nullable`` is True
    if a JSON null (or, for CSV, an empty string) is also acceptable (a trailing
    ``?`` or an explicit ``null`` in a list). ``any`` short-circuits to accept
    anything.
    """

    types: Tuple[str, ...]
    nullable: bool

    @property
    def is_any(self) -> bool:
        return "any" in self.types

    @property
    def implies_required(self) -> bool:
        """A schema field is implicitly required unless it admits null/any."""
        return not (self.nullable or self.is_any or "null" in self.types)

    def describe(self) -> str:
        base = "|".join(self.types) if self.types else "any"
        return base + ("?" if self.nullable and "null" not in self.types else "")


def _parse_field_type(raw: Any) -> FieldType:
    """Parse one schema value into a :class:`FieldType`.

    Accepts ``"int"``, ``"int?"``, ``["array","null"]``, ``["string"]``, etc.
    Unknown type names are normalised to ``"any"`` (be liberal in what a mission
    author can write rather than crash the oracle on a typo — but record it).
    """
    spellings: List[str]
    if isinstance(raw, str):
        spellings = [raw]
    elif isinstance(raw, (list, tuple)):
        spellings = [str(x) for x in raw]
    else:
        spellings = [str(raw)]

    canon: List[str] = []
    nullable = False
    for sp in spellings:
        s = sp.strip().lower()
        if not s:
            continue
        if s.endswith("?"):
            nullable = True
            s = s[:-1].strip()
        if not s:
            continue
        c = _TYPE_ALIASES.get(s, "any")
        if c == "null":
            nullable = True
        if c not in canon:
            canon.append(c)
    if not canon:
        canon = ["any"]
    # collapse: if "any" present, that's all that matters
    if "any" in canon:
        return FieldType(types=("any",), nullable=nullable)
    return FieldType(types=tuple(canon), nullable=nullable)


@dataclass(frozen=True)
class VerificationParams:
    """Parsed, validated view of a dataset mission's ``verification_params``.

    See the module docstring for the JSON schema. ``from_mapping`` is tolerant:
    unknown keys are ignored and wrong-typed optionals fall back to their
    defaults. Unlike the URL-liveness oracle it does NOT require the mission to
    constrain content (a dataset mission with no min_rows/columns/keys/schema is
    a valid, if minimal, "must download and parse as <format>" mission) — but it
    DOES reject an unrecognised ``format``.
    """

    format: str = "csv"
    format_explicit: bool = False
    min_rows: int = 0
    required_names: Tuple[str, ...] = ()
    schema: Mapping[str, FieldType] = field(default_factory=dict)
    schema_implies_required: bool = True
    sample_rows: int = DEFAULT_SAMPLE_ROWS
    delimiter: str = ","
    has_header: bool = True
    encoding: str = "utf-8"
    max_bytes: int = DEFAULT_MAX_BYTES
    timeout: float = DEFAULT_TIMEOUT
    expect_status: Tuple[int, ...] = (200,)
    follow_redirects: bool = True
    max_redirects: int = DEFAULT_MAX_REDIRECTS
    source_url: Optional[str] = None
    allow_private: bool = False
    max_violations: int = DEFAULT_MAX_VIOLATIONS
    oracle_description: Optional[str] = None

    # -- derived ----------------------------------------------------------- #
    def effective_required(self) -> Tuple[str, ...]:
        """All names that must be present in every record: the explicit
        ``required_columns`` / ``required_keys`` UNION the schema fields that the
        schema implies are required (unless ``schema_implies_required`` is off).
        Order-preserving, de-duplicated.
        """
        out: List[str] = []
        seen = set()
        for n in self.required_names:
            if n not in seen:
                seen.add(n)
                out.append(n)
        if self.schema_implies_required:
            for name, ft in self.schema.items():
                if ft.implies_required and name not in seen:
                    seen.add(name)
                    out.append(name)
        return tuple(out)

    @classmethod
    def from_mapping(
        cls, data: Optional[Mapping[str, Any]]
    ) -> "VerificationParams":
        if not isinstance(data, Mapping):
            raise ValueError("verification_params must be an object")

        def _opt_str(*keys: str) -> Optional[str]:
            for k in keys:
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return None

        def _bool(key: str, default: bool, *aliases: str) -> bool:
            for k in (key, *aliases):
                if k in data:
                    v = data.get(k)
                    if isinstance(v, bool):
                        return v
                    if isinstance(v, str):
                        return v.strip().lower() in ("1", "true", "yes", "on")
                    if isinstance(v, (int, float)):
                        return bool(v)
            return default

        def _int(key: str, default: int, *aliases: str) -> int:
            for k in (key, *aliases):
                if k in data:
                    try:
                        return int(data.get(k))  # type: ignore[arg-type]
                    except (TypeError, ValueError):
                        return default
            return default

        def _float(key: str, default: float, *aliases: str) -> float:
            for k in (key, *aliases):
                if k in data:
                    try:
                        return float(data.get(k))  # type: ignore[arg-type]
                    except (TypeError, ValueError):
                        return default
            return default

        def _str_list(*keys: str) -> Tuple[str, ...]:
            for k in keys:
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    # allow a comma-separated string for convenience
                    parts = [p.strip() for p in v.split(",") if p.strip()]
                    if parts:
                        return tuple(parts)
                if isinstance(v, (list, tuple)):
                    out = [str(x).strip() for x in v if str(x).strip()]
                    if out:
                        return tuple(out)
            return ()

        # format: optional; validate against VALID_FORMATS.
        fmt_raw = _opt_str("format", "dataset_format", "file_format")
        fmt_explicit = fmt_raw is not None
        fmt = (fmt_raw or "csv").lower()
        # normalise some synonyms
        if fmt in ("ndjson", "jsonlines", "jsonl"):
            fmt = "jsonl"
        elif fmt in ("csv", "tsv"):
            # tsv is csv with a tab delimiter; record and set delimiter below
            fmt = "csv"
        elif fmt in ("json",):
            fmt = "json"
        if fmt not in VALID_FORMATS:
            raise ValueError(
                "unsupported format %r (must be one of %s)"
                % (fmt_raw, ", ".join(VALID_FORMATS))
            )

        # required column/key names: either spelling is accepted for any format.
        required_names = _str_list(
            "required_columns", "required_keys", "required_fields",
            "columns", "keys",
        )

        # schema: optional per-field type map.
        schema_raw = data.get("schema")
        schema: Dict[str, FieldType] = {}
        if isinstance(schema_raw, Mapping):
            for k, v in schema_raw.items():
                name = str(k).strip()
                if name:
                    schema[name] = _parse_field_type(v)

        # delimiter (and tsv shorthand)
        delim = _opt_str("delimiter", "sep") or ","
        if (fmt_raw or "").lower() == "tsv":
            delim = "\t"
        if len(delim) != 1:
            # csv requires a 1-char delimiter; fall back to comma on a bad value
            delim = "\t" if delim in ("\\t", "tab") else ","

        min_rows = max(0, _int("min_rows", 0, "min_records", "min_count"))
        sample_rows = max(0, _int("sample_rows", DEFAULT_SAMPLE_ROWS, "sample"))
        max_bytes = max(1, _int("max_bytes", DEFAULT_MAX_BYTES, "max_body_bytes"))
        timeout = _float("timeout", DEFAULT_TIMEOUT, "timeout_seconds")
        if timeout <= 0:
            timeout = DEFAULT_TIMEOUT
        max_redirects = max(0, _int("max_redirects", DEFAULT_MAX_REDIRECTS))
        max_violations = max(1, _int("max_violations", DEFAULT_MAX_VIOLATIONS))

        # expect_status: int | [int,...]; default (200,)
        es_raw = data.get("expect_status", data.get("status", 200))
        if isinstance(es_raw, bool):
            es: Tuple[int, ...] = (200,)
        elif isinstance(es_raw, int):
            es = (es_raw,)
        elif isinstance(es_raw, (list, tuple)):
            tmp: List[int] = []
            for x in es_raw:
                try:
                    if isinstance(x, bool):
                        continue
                    tmp.append(int(x))
                except (TypeError, ValueError):
                    continue
            es = tuple(tmp) if tmp else (200,)
        else:
            try:
                es = (int(es_raw),)
            except (TypeError, ValueError):
                es = (200,)

        return cls(
            format=fmt,
            format_explicit=fmt_explicit,
            min_rows=min_rows,
            required_names=required_names,
            schema=schema,
            schema_implies_required=_bool("schema_implies_required", True),
            sample_rows=sample_rows,
            delimiter=delim,
            has_header=_bool("has_header", True, "header"),
            encoding=_opt_str("encoding", "charset") or "utf-8",
            max_bytes=max_bytes,
            timeout=timeout,
            expect_status=es,
            follow_redirects=_bool("follow_redirects", True, "follow"),
            max_redirects=max_redirects,
            source_url=_opt_str("source_url", "expected_url", "url"),
            allow_private=_bool("allow_private", False, "allow_internal"),
            max_violations=max_violations,
            oracle_description=_opt_str("oracle_description"),
        )


# --------------------------------------------------------------------------- #
# URL parsing / normalisation
# --------------------------------------------------------------------------- #
def normalize_url(url: str, *, default_scheme: str = "https") -> str:
    """Lightly normalise a URL for comparison / fetching.

    * a bare host (``data.example.com`` or ``data.example.com/x``) gains a
      scheme (``https://`` by default);
    * scheme + host are lowercased; the path/query are preserved;
    * a default port matching the scheme (``:80`` for http, ``:443`` for https)
      is dropped;
    * an empty path is normalised to ``/``.

    Raises ``ValueError`` if no usable ``http(s)`` URL can be formed.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")
    s = url.strip()

    if "://" not in s:
        s = "%s://%s" % (default_scheme, s)

    parts = urllib.parse.urlsplit(s)
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError("url scheme must be http or https, got %r" % parts.scheme)
    if not parts.hostname:
        raise ValueError("url has no host: %r" % url)

    host = parts.hostname.lower()
    port = parts.port
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
    netloc = host if port is None else "%s:%d" % (host, port)

    path = parts.path or "/"
    rebuilt = urllib.parse.urlunsplit((scheme, netloc, path, parts.query, ""))
    return rebuilt


def parse_proof_url(proof: Any, *, default_scheme: str = "https") -> str:
    """Extract the dataset URL from a submission proof.

    Accepted forms:
      * a plain URL string ``"https://data.example.com/pairs.csv"``
      * a bare host ``"data.example.com/pairs.csv"`` (gets ``default_scheme``)
      * a JSON object / dict carrying ``url`` (or ``dataset_url`` /
        ``download_url`` / ``link`` / ``href`` / ``proof``)

    Returns the normalised URL. Raises ``ValueError`` if none can be extracted.
    """
    if isinstance(proof, Mapping):
        for key in (
            "url", "dataset_url", "download_url", "endpoint", "link", "href",
            "proof", "target", "file",
        ):
            v = proof.get(key)
            if isinstance(v, str) and v.strip():
                return normalize_url(v, default_scheme=default_scheme)
        raise ValueError("proof object carries no 'url'/'dataset_url'/'link' string")

    if not isinstance(proof, str) or not proof.strip():
        raise ValueError("proof must be a non-empty URL string")
    s = proof.strip()

    if s.startswith("{"):
        try:
            obj = json.loads(s)
        except ValueError:
            obj = None
        if isinstance(obj, Mapping):
            return parse_proof_url(obj, default_scheme=default_scheme)

    return normalize_url(s, default_scheme=default_scheme)


# --------------------------------------------------------------------------- #
# SSRF guard: is this host safe to fetch?  (shared idiom with url_liveness)
# --------------------------------------------------------------------------- #
_BLOCKED_HOST_NAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
    }
)
_BLOCKED_HOST_SUFFIXES = (
    ".localhost",
    ".local",
    ".internal",
    ".intranet",
    ".lan",
    ".home.arpa",
)


def _ip_is_public(ip: "ipaddress._BaseAddress") -> bool:
    """True only for genuinely routable public addresses.

    Rejects loopback, private (RFC1918 / ULA), link-local, multicast,
    unspecified, reserved, and (for v4) ``0.0.0.0/8`` and the ``100.64.0.0/10``
    CGNAT range. IPv4-mapped / 6to4 IPv6 is unwrapped and re-checked.
    """
    if isinstance(ip, ipaddress.IPv6Address):
        mapped = getattr(ip, "ipv4_mapped", None)
        if mapped is not None:
            return _ip_is_public(mapped)
        sixto4 = getattr(ip, "sixtofour", None)
        if sixto4 is not None:
            return _ip_is_public(sixto4)

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    ):
        return False
    if not getattr(ip, "is_global", True):
        return False
    if isinstance(ip, ipaddress.IPv4Address):
        if ipaddress.IPv4Address("100.64.0.0") <= ip <= ipaddress.IPv4Address(
            "100.127.255.255"
        ):
            return False
    return True


def _resolve_host_ips(host: str) -> List[str]:
    """Resolve a hostname to its IP literals (both families). May raise socket.gaierror."""
    out: List[str] = []
    seen = set()
    for info in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP):
        addr = info[4][0]
        addr = addr.split("%", 1)[0]
        if addr not in seen:
            seen.add(addr)
            out.append(addr)
    return out


def is_public_host(host: str) -> Tuple[bool, str]:
    """Decide whether ``host`` is safe (public) to fetch.

    Returns ``(ok, reason)``. ``ok`` is ``False`` if the host is a known-local
    name, has a non-public suffix, is an IP literal in private/reserved space,
    or resolves (via DNS) to ANY non-public IP (DNS-rebinding / split-horizon
    defence). A DNS failure returns ``(False, "...unresolvable...")`` — a host we
    cannot resolve is not a confirmed-public target (fail-closed).
    """
    h = (host or "").strip().lower().rstrip(".")
    if not h:
        return False, "empty host"

    if h in _BLOCKED_HOST_NAMES:
        return False, "host %r is a reserved local name" % host
    for suf in _BLOCKED_HOST_SUFFIXES:
        if h.endswith(suf):
            return False, "host %r has non-public suffix %r" % (host, suf)

    literal = h
    if literal.startswith("[") and literal.endswith("]"):
        literal = literal[1:-1]
    try:
        ip = ipaddress.ip_address(literal)
    except ValueError:
        ip = None
    if ip is not None:
        if _ip_is_public(ip):
            return True, "public ip literal %s" % ip
        return False, "host resolves to non-public address %s" % ip

    try:
        addrs = _resolve_host_ips(h)
    except socket.gaierror as exc:
        return False, "host %r is unresolvable (%s)" % (host, exc)
    except OSError as exc:  # pragma: no cover - env dependent
        return False, "host %r resolution failed (%s)" % (host, exc)
    if not addrs:
        return False, "host %r resolved to no addresses" % host
    for a in addrs:
        try:
            ipa = ipaddress.ip_address(a)
        except ValueError:  # pragma: no cover - getaddrinfo returns valid IPs
            return False, "host %r resolved to unparseable address %r" % (host, a)
        if not _ip_is_public(ipa):
            return False, "host %r resolves to non-public address %s" % (host, a)
    return True, "host %r resolves to public address(es) %s" % (host, ",".join(addrs))


# --------------------------------------------------------------------------- #
# HTTP response + client (stdlib urllib, size cap + redirect control + SSRF)
# --------------------------------------------------------------------------- #
class HttpError(Exception):
    """A transport failure (DNS / connection / TLS / timeout / decode).

    Distinct from "the dataset is malformed / too small" (which the verifier
    represents as ``verified=False``): an ``HttpError`` means the GET could not
    be completed at all, so the dataset is not verifiably present — the verifier
    turns it into ``verified=False`` with the cause.
    """


class SSRFBlocked(HttpError):
    """The target host was refused by the SSRF guard (private/reserved/local)."""


@dataclass
class HttpResponse:
    """A captured (capped) HTTP response.

    Attributes
    ----------
    status:      final HTTP status code (after any followed redirects).
    url:         final URL fetched (after redirects).
    body:        response body bytes, truncated to ``max_bytes``.
    headers:     response headers (lowercased keys).
    truncated:   True if the body was cut at ``max_bytes`` (more bytes existed).
    redirects:   the chain of intermediate URLs that were followed (if any).
    """

    status: int
    url: str
    body: bytes
    headers: Dict[str, str] = field(default_factory=dict)
    truncated: bool = False
    redirects: List[str] = field(default_factory=list)

    @property
    def content_type(self) -> str:
        return (self.headers.get("content-type", "") or "").split(";", 1)[0].strip().lower()


class HttpClient:
    """Read-only HTTP GET client with a size cap, redirect control, and SSRF guard.

    stdlib ``urllib`` / ``http.client`` only. The byte transport is pluggable via
    ``transport`` (signature ``(method, url, headers, timeout, max_bytes) ->
    HttpResponse``) so the offline self-test can stub the network with zero
    sockets. When no transport is injected, :meth:`_default_transport` performs a
    real, capped GET.

    SSRF enforcement happens in :meth:`get`: the host of **every** URL in the
    redirect chain is checked with :func:`is_public_host` unless ``allow_private``
    is set.
    """

    def __init__(
        self,
        *,
        allow_private: bool = False,
        transport: Optional[Transport] = None,
        verify_tls: bool = True,
    ) -> None:
        self.allow_private = bool(allow_private)
        self._transport = transport
        self.verify_tls = bool(verify_tls)

    # -- public API -------------------------------------------------------- #
    def get(
        self,
        url: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_bytes: int = DEFAULT_MAX_BYTES,
        follow_redirects: bool = True,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
    ) -> HttpResponse:
        """Perform a capped GET, manually following redirects with an SSRF check
        on every hop. Returns an :class:`HttpResponse`; raises :class:`HttpError`
        / :class:`SSRFBlocked` on transport failure or a blocked host.
        """
        current = url
        chain: List[str] = []
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
        for hop in range(max_redirects + 1):
            self._guard(current)
            resp = self._fetch_once(
                current, headers=headers, timeout=timeout, max_bytes=max_bytes
            )
            if (
                follow_redirects
                and resp.status in (301, 302, 303, 307, 308)
                and resp.headers.get("location")
                and hop < max_redirects
            ):
                loc = resp.headers["location"]
                nxt = urllib.parse.urljoin(current, loc)
                try:
                    nxt = normalize_url(nxt)
                except ValueError as exc:
                    raise HttpError("bad redirect target %r: %s" % (loc, exc))
                chain.append(current)
                current = nxt
                continue
            resp.redirects = chain
            return resp
        raise HttpError(
            "too many redirects (> %d) starting at %s" % (max_redirects, url)
        )

    # -- internals --------------------------------------------------------- #
    def _guard(self, url: str) -> None:
        if self.allow_private:
            return
        host = urllib.parse.urlsplit(url).hostname or ""
        ok, reason = is_public_host(host)
        if not ok:
            raise SSRFBlocked("refused to fetch %s: %s" % (url, reason))

    def _fetch_once(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout: float,
        max_bytes: int,
    ) -> HttpResponse:
        if self._transport is not None:
            try:
                resp = self._transport(
                    "GET", url, dict(headers), timeout, max_bytes
                )
            except (HttpError, SSRFBlocked):
                raise
            except Exception as exc:  # pragma: no cover - injected transport
                raise HttpError("GET %s failed: %s" % (url, exc)) from exc
            if not isinstance(resp, HttpResponse):
                raise HttpError("injected transport returned a non-HttpResponse")
            return resp
        return self._default_transport("GET", url, dict(headers), timeout, max_bytes)

    def _default_transport(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        timeout: float,
        max_bytes: int,
    ) -> HttpResponse:
        """Real, capped GET using urllib WITHOUT auto-following redirects.

        We disable urllib's automatic redirect handling so the caller can
        SSRF-check each hop; ``urlopen`` therefore returns 3xx responses as
        normal results rather than chasing them itself.
        """
        req = urllib.request.Request(url, headers=headers, method=method)

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):  # noqa: D401
                return None  # never auto-follow; we handle it

        handlers: List[urllib.request.BaseHandler] = [_NoRedirect()]
        if url.lower().startswith("https"):
            ctx = ssl.create_default_context()
            if not self.verify_tls:  # pragma: no cover - opt-in only
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            handlers.append(urllib.request.HTTPSHandler(context=ctx))
        opener = urllib.request.build_opener(*handlers)

        try:
            resp = opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            body, truncated = _read_capped(exc, max_bytes)
            return HttpResponse(
                status=exc.code,
                url=url,
                body=body,
                headers=_lower_headers(getattr(exc, "headers", None)),
                truncated=truncated,
            )
        except urllib.error.URLError as exc:
            raise HttpError("GET %s failed: %s" % (url, exc.reason)) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise HttpError("GET %s timed out after %ss" % (url, timeout)) from exc
        except (ssl.SSLError, http.client.HTTPException, OSError) as exc:
            raise HttpError("GET %s failed: %s" % (url, exc)) from exc

        with resp:
            body, truncated = _read_capped(resp, max_bytes)
            status = resp.getcode() or 0
            final_url = resp.geturl() or url
            hdrs = _lower_headers(resp.headers)
        return HttpResponse(
            status=status,
            url=final_url,
            body=body,
            headers=hdrs,
            truncated=truncated,
        )


def _read_capped(resp: Any, max_bytes: int) -> Tuple[bytes, bool]:
    """Read at most ``max_bytes`` from a file-like response; flag truncation.

    Reads ``max_bytes + 1`` so we can tell whether more data existed beyond the
    cap, then trims back to ``max_bytes``.
    """
    try:
        chunk = resp.read(max_bytes + 1)
    except (TimeoutError, socket.timeout) as exc:
        raise HttpError("read timed out: %s" % exc) from exc
    except (ssl.SSLError, http.client.HTTPException, OSError) as exc:
        raise HttpError("read failed: %s" % exc) from exc
    if chunk is None:
        return b"", False
    if len(chunk) > max_bytes:
        return chunk[:max_bytes], True
    return chunk, False


def _lower_headers(headers: Any) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if headers is None:
        return out
    try:
        items = headers.items()
    except AttributeError:  # pragma: no cover - defensive
        return out
    for k, v in items:
        out[str(k).lower()] = str(v)
    return out


# --------------------------------------------------------------------------- #
# Format inference + decoding
# --------------------------------------------------------------------------- #
def infer_format(url: str, content_type: str = "") -> str:
    """Infer ``csv`` | ``jsonl`` | ``json`` from a URL extension then a
    Content-Type, defaulting to ``csv``.

    Extension wins (it is part of the content-addressed proof); Content-Type is
    the fallback. ``application/x-ndjson`` / ``application/jsonl`` -> jsonl;
    ``application/json`` -> json; ``text/csv`` -> csv.
    """
    path = urllib.parse.urlsplit(url).path.lower()
    # consider compound extensions like .csv.gz? we don't decompress; ignore .gz
    base = path[:-3] if path.endswith(".gz") else path
    if base.endswith(".csv") or base.endswith(".tsv"):
        return "csv"
    if base.endswith(".jsonl") or base.endswith(".ndjson"):
        return "jsonl"
    if base.endswith(".json"):
        return "json"

    ct = (content_type or "").lower()
    if "ndjson" in ct or "jsonl" in ct or "json-seq" in ct:
        return "jsonl"
    if "csv" in ct or "tab-separated" in ct or "tsv" in ct:
        return "csv"
    if "json" in ct:
        return "json"
    return "csv"


def _decode_body(body: bytes, encoding: str) -> Tuple[str, bool]:
    """Decode bytes to text, stripping a UTF-8/UTF-16 BOM if present.

    Returns ``(text, replaced)`` where ``replaced`` is True if any byte could not
    be decoded cleanly (decoded with ``errors='replace'``) — a soft signal of a
    wrong encoding / binary payload that the integrity check can surface.
    """
    enc = (encoding or "utf-8").lower()
    # BOM sniffing
    if body[:3] == b"\xef\xbb\xbf":
        body = body[3:]
        enc = "utf-8"
    elif body[:2] in (b"\xff\xfe", b"\xfe\xff"):
        enc = "utf-16"
    try:
        return body.decode(enc), False
    except (LookupError, UnicodeDecodeError):
        try:
            return body.decode("utf-8"), False
        except UnicodeDecodeError:
            return body.decode("utf-8", errors="replace"), True


# --------------------------------------------------------------------------- #
# Per-value type checking
# --------------------------------------------------------------------------- #
_INT_RE = re.compile(r"[+-]?\d+\Z")
_FLOAT_RE = re.compile(
    r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?\Z"
)
_BOOL_TRUE = frozenset({"true", "1", "yes", "y", "t"})
_BOOL_FALSE = frozenset({"false", "0", "no", "n", "f"})


def _string_is_int(s: str) -> bool:
    return bool(_INT_RE.match(s.strip()))


def _string_is_number(s: str) -> bool:
    t = s.strip()
    if not t:
        return False
    if _FLOAT_RE.match(t):
        return True
    # accept inf / nan spellings? No — keep datasets clean. Reject.
    return False


def _string_is_bool(s: str) -> bool:
    t = s.strip().lower()
    return t in _BOOL_TRUE or t in _BOOL_FALSE


def check_value_type(value: Any, ft: FieldType, *, is_csv: bool) -> Tuple[bool, str]:
    """Check one value against a :class:`FieldType`.

    For CSV every value is a string, so numeric/bool types are checked as
    *parse-able-as* (``"42"`` is a valid ``int``, ``"4.2"`` a valid ``number``,
    ``"true"`` a valid ``bool``); ``array``/``object`` are not meaningful for a
    flat CSV cell and are accepted only as ``string`` unless the type set also
    admits ``string``/``any`` (otherwise rejected). For JSON/JSONL the actual
    JSON runtime type is checked.

    Returns ``(ok, reason)``. ``reason`` is empty on success.
    """
    if ft.is_any:
        return True, ""

    # null / empty handling
    if value is None:
        return (ft.nullable or "null" in ft.types), (
            "" if (ft.nullable or "null" in ft.types) else "value is null but %s required" % ft.describe()
        )
    if is_csv and isinstance(value, str) and value == "":
        # empty CSV cell == null-ish
        if ft.nullable or "null" in ft.types:
            return True, ""
        # an empty string is a valid "string" only if string is permitted
        if "string" in ft.types:
            return True, ""
        return False, "empty cell but %s required" % ft.describe()

    for t in ft.types:
        if t == "null":
            if value is None:
                return True, ""
            continue
        if t == "string":
            if is_csv or isinstance(value, str):
                return True, ""
            continue
        if t == "int":
            if is_csv:
                if isinstance(value, str) and _string_is_int(value):
                    return True, ""
            else:
                if isinstance(value, bool):
                    continue  # JSON bool is not an int here
                if isinstance(value, int):
                    return True, ""
                # a JSON float that is integral? be strict: require int type.
            continue
        if t == "number":
            if is_csv:
                if isinstance(value, str) and _string_is_number(value):
                    return True, ""
            else:
                if isinstance(value, bool):
                    continue
                if isinstance(value, (int, float)):
                    return True, ""
            continue
        if t == "bool":
            if is_csv:
                if isinstance(value, str) and _string_is_bool(value):
                    return True, ""
            else:
                if isinstance(value, bool):
                    return True, ""
            continue
        if t == "array":
            if is_csv:
                continue  # a flat CSV cell is never a JSON array
            if isinstance(value, list):
                return True, ""
            continue
        if t == "object":
            if is_csv:
                continue
            if isinstance(value, dict):
                return True, ""
            continue
    # nothing matched
    observed = _observed_type(value, is_csv=is_csv)
    return False, "value %s is not %s" % (observed, ft.describe())


def _observed_type(value: Any, *, is_csv: bool) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        if is_csv:
            return "string(%r)" % (value[:24] + ("…" if len(value) > 24 else ""))
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


# --------------------------------------------------------------------------- #
# Dataset parsing + checking (the heart of the oracle)
# --------------------------------------------------------------------------- #
class DatasetParseError(Exception):
    """The body could not be parsed under the declared format (a verdict, not a
    crash): the verifier turns it into ``verified=False`` with the line/row."""

    def __init__(self, message: str, *, row: Optional[int] = None) -> None:
        super().__init__(message)
        self.row = row


@dataclass
class _CheckState:
    """Accumulator threaded through a streaming pass over the dataset."""

    rows: int = 0                       # data records counted (excl. CSV header)
    sampled: int = 0                    # records actually type/key-checked
    columns: List[str] = field(default_factory=list)   # CSV header / union of keys
    violations: List[Dict[str, Any]] = field(default_factory=list)
    max_violations: int = DEFAULT_MAX_VIOLATIONS
    integrity_ok: bool = True

    def add_violation(self, check: str, reason: str, **loc: Any) -> None:
        if len(self.violations) < self.max_violations:
            rec: Dict[str, Any] = {"check": check, "reason": reason}
            rec.update({k: v for k, v in loc.items() if v is not None})
            self.violations.append(rec)


def _check_record(
    record: Mapping[str, Any],
    *,
    rownum: int,
    required: Sequence[str],
    schema: Mapping[str, FieldType],
    is_csv: bool,
    state: _CheckState,
) -> None:
    """Apply required-key presence + per-field type checks to ONE record."""
    # required keys present?
    for name in required:
        if name not in record:
            state.add_violation(
                "required_columns" if is_csv else "required_keys",
                "missing required %s %r" % ("column" if is_csv else "key", name),
                row=rownum, column=(name if is_csv else None),
                key=(None if is_csv else name),
            )
    # per-field types?
    for name, ft in schema.items():
        if name not in record:
            # presence is governed by `required`; a schema field that is not
            # required and absent is fine. If it WAS required, the loop above
            # already flagged it. So only type-check present fields here.
            continue
        ok, reason = check_value_type(record[name], ft, is_csv=is_csv)
        if not ok:
            state.add_violation(
                "schema", reason, row=rownum,
                column=(name if is_csv else None),
                key=(None if is_csv else name),
            )


def _iter_csv(
    text: str, params: VerificationParams, state: _CheckState
) -> None:
    """Stream a CSV body: count rows, capture header, integrity + sampled checks."""
    try:
        csv.field_size_limit(min(DEFAULT_MAX_CSV_FIELD, sys.maxsize))
    except (OverflowError, ValueError):  # pragma: no cover - platform dependent
        pass
    reader = csv.reader(io.StringIO(text), delimiter=params.delimiter)
    header: Optional[List[str]] = None
    expected_width: Optional[int] = None
    required = params.effective_required()
    schema = params.schema
    sample_cap = params.sample_rows

    try:
        for raw_row in reader:
            # csv yields a list of strings per row
            if params.has_header and header is None:
                header = [c.strip() for c in raw_row]
                state.columns = list(header)
                expected_width = len(header)
                # integrity: duplicate header names
                seen: Dict[str, int] = {}
                for c in header:
                    seen[c] = seen.get(c, 0) + 1
                dups = sorted([c for c, n in seen.items() if n > 1])
                if dups:
                    state.integrity_ok = False
                    state.add_violation(
                        "integrity",
                        "duplicate column name(s) in header: %s" % ", ".join(dups),
                    )
                # an empty header (single blank field) is an integrity problem
                if expected_width == 0 or (expected_width == 1 and header[0] == ""):
                    state.integrity_ok = False
                    state.add_violation("integrity", "CSV header is empty")
                continue

            if not params.has_header and header is None:
                # headerless: synthesise positional column names col0..colN
                expected_width = len(raw_row)
                header = ["col%d" % i for i in range(expected_width)]
                state.columns = list(header)
                # fall through to treat THIS row as data

            # a fully blank trailing line -> skip (common file artefact)
            if len(raw_row) == 1 and raw_row[0] == "" :
                continue

            state.rows += 1
            rownum = state.rows  # 1-based data-row index

            # integrity: consistent header (column count)
            if expected_width is not None and len(raw_row) != expected_width:
                state.integrity_ok = False
                state.add_violation(
                    "integrity",
                    "row has %d fields, header has %d (ragged row)"
                    % (len(raw_row), expected_width),
                    row=rownum,
                )

            # sampled per-record checks (presence + types)
            if sample_cap == 0 or state.sampled < sample_cap:
                state.sampled += 1
                # build a dict from header -> cell (missing cells => absent key)
                rec: Dict[str, Any] = {}
                hdr = header or []
                for i, name in enumerate(hdr):
                    if i < len(raw_row):
                        rec[name] = raw_row[i]
                _check_record(
                    rec, rownum=rownum, required=required, schema=schema,
                    is_csv=True, state=state,
                )
    except csv.Error as exc:
        raise DatasetParseError("CSV parse error: %s" % exc, row=state.rows + 1)

    if header is None:
        # no rows at all
        state.integrity_ok = False
        raise DatasetParseError("CSV is empty (no header / no rows)")


def _iter_jsonl(
    text: str, params: VerificationParams, state: _CheckState
) -> None:
    """Stream a JSONL/NDJSON body: one JSON value per non-blank line."""
    required = params.effective_required()
    schema = params.schema
    sample_cap = params.sample_rows
    col_order: List[str] = []
    col_seen = set()
    saw_any = False

    for lineno, line in enumerate(io.StringIO(text), start=1):
        s = line.strip()
        if not s:
            continue  # blank lines allowed between records
        saw_any = True
        try:
            obj = json.loads(s)
        except ValueError as exc:
            raise DatasetParseError(
                "JSONL line %d is not valid JSON: %s" % (lineno, exc), row=lineno
            )
        state.rows += 1
        rownum = state.rows
        if not isinstance(obj, Mapping):
            state.integrity_ok = False
            state.add_violation(
                "integrity",
                "JSONL record is a %s, expected an object" % _observed_type(obj, is_csv=False),
                row=rownum,
            )
            # still count it; presence/type checks can't apply to a non-object
            continue
        # track union of keys for evidence.columns
        for k in obj.keys():
            if k not in col_seen:
                col_seen.add(k)
                col_order.append(k)
        if sample_cap == 0 or state.sampled < sample_cap:
            state.sampled += 1
            _check_record(
                obj, rownum=rownum, required=required, schema=schema,
                is_csv=False, state=state,
            )

    state.columns = col_order
    if not saw_any:
        state.integrity_ok = False
        raise DatasetParseError("JSONL is empty (no records)")


def _iter_json(
    text: str, params: VerificationParams, state: _CheckState
) -> None:
    """Parse a single JSON document; require an array of objects (directly, or as
    the values of an object, or under a conventional ``data``/``rows``/...key)."""
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise DatasetParseError("body is not valid JSON: %s" % exc)

    records = _extract_records_array(doc)
    if records is None:
        state.integrity_ok = False
        raise DatasetParseError(
            "JSON top-level is not a records array (got %s); expected an array of "
            "objects, or an object with a 'data'/'rows'/'records'/'items' array"
            % _observed_type(doc, is_csv=False)
        )

    required = params.effective_required()
    schema = params.schema
    sample_cap = params.sample_rows
    col_order: List[str] = []
    col_seen = set()

    for idx, obj in enumerate(records, start=1):
        state.rows += 1
        rownum = idx
        if not isinstance(obj, Mapping):
            state.integrity_ok = False
            state.add_violation(
                "integrity",
                "record %d is a %s, expected an object" % (idx, _observed_type(obj, is_csv=False)),
                row=rownum,
            )
            continue
        for k in obj.keys():
            if k not in col_seen:
                col_seen.add(k)
                col_order.append(k)
        if sample_cap == 0 or state.sampled < sample_cap:
            state.sampled += 1
            _check_record(
                obj, rownum=rownum, required=required, schema=schema,
                is_csv=False, state=state,
            )

    state.columns = col_order


def _extract_records_array(doc: Any) -> Optional[List[Any]]:
    """From a parsed JSON document, return the list of records, or None.

    * a top-level list -> that list.
    * a top-level object with one of ``data`` / ``rows`` / ``records`` /
      ``items`` / ``results`` that is a list -> that list.
    * a top-level object whose VALUES are all objects (a map keyed by id) ->
      the list of values.
    """
    if isinstance(doc, list):
        return doc
    if isinstance(doc, Mapping):
        for key in ("data", "rows", "records", "items", "results", "dataset"):
            v = doc.get(key)
            if isinstance(v, list):
                return v
        # a dict-of-records (id -> object)?
        vals = list(doc.values())
        if vals and all(isinstance(v, Mapping) for v in vals):
            return vals
    return None


# --------------------------------------------------------------------------- #
# verify_bytes: run all checks against already-downloaded bytes (no network)
# --------------------------------------------------------------------------- #
def verify_bytes(
    body: bytes,
    params: VerificationParams,
    *,
    fmt: Optional[str] = None,
    truncated: bool = False,
    source: str = "<bytes>",
) -> VerifyResult:
    """Run the full dataset checks against in-memory bytes (used by both the
    networked :func:`verify` and the ``--file`` CLI path / tests).

    ``fmt`` overrides the params/inferred format (pass the format you decided on
    after inspecting the URL/Content-Type). ``truncated`` should be True if the
    bytes were cut at ``max_bytes`` (the count check then treats a ``min_rows``
    pass conservatively — see below). Returns a :class:`VerifyResult` whose
    ``evidence`` always carries ``rows`` / ``columns`` / ``violations``.
    """
    fmt = (fmt or params.format or "csv").lower()
    evidence: Dict[str, Any] = {
        "verifier": "dataset",
        "format": fmt,
        "params": {
            "format": params.format,
            "min_rows": params.min_rows,
            "required": list(params.effective_required()),
            "schema": {k: v.describe() for k, v in params.schema.items()},
            "sample_rows": params.sample_rows,
            "max_bytes": params.max_bytes,
            "source_url": params.source_url,
            "allow_private": params.allow_private,
        },
        # Convention for THIS verifier: these three keys are ALWAYS present.
        "rows": 0,
        "columns": [],
        "violations": [],
        "bytes": len(body),
        "truncated": bool(truncated),
        "sampled": 0,
        "checks": {},
    }
    checks: Dict[str, Any] = evidence["checks"]

    def reject(detail: str) -> VerifyResult:
        return VerifyResult(verified=False, detail=detail, evidence=evidence)

    # --- NON-EMPTY ------------------------------------------------------- #
    if not body:
        checks["non_empty"] = {"ok": False}
        evidence["violations"].append({"check": "integrity", "reason": "empty file (0 bytes)"})
        return reject("dataset is empty (0 bytes downloaded)")
    checks["non_empty"] = {"ok": True, "bytes": len(body)}

    # --- DECODE ---------------------------------------------------------- #
    text, replaced = _decode_body(body, params.encoding)
    if replaced:
        # not fatal by itself, but a strong integrity smell; record it.
        evidence["decode_lossy"] = True

    # --- PARSE + STREAM CHECKS ------------------------------------------ #
    state = _CheckState(max_violations=params.max_violations)
    try:
        if fmt == "csv":
            _iter_csv(text, params, state)
        elif fmt == "jsonl":
            _iter_jsonl(text, params, state)
        elif fmt == "json":
            _iter_json(text, params, state)
        else:  # pragma: no cover - guarded earlier
            return reject("unsupported format %r" % fmt)
    except DatasetParseError as exc:
        checks["parse"] = {"ok": False, "reason": str(exc), "row": exc.row}
        evidence["rows"] = state.rows
        evidence["columns"] = state.columns
        evidence["sampled"] = state.sampled
        evidence["violations"] = state.violations + [
            {"check": "parse", "reason": str(exc),
             **({"row": exc.row} if exc.row is not None else {})}
        ]
        loc = (" at row %d" % exc.row) if exc.row is not None else ""
        return reject("dataset does not parse as %s%s: %s" % (fmt, loc, exc))

    checks["parse"] = {"ok": True}
    evidence["rows"] = state.rows
    evidence["columns"] = state.columns
    evidence["sampled"] = state.sampled
    evidence["violations"] = state.violations

    # --- INTEGRITY ------------------------------------------------------- #
    checks["integrity"] = {"ok": state.integrity_ok}
    if not state.integrity_ok:
        # find the first integrity violation reason for the headline
        first = next((v for v in state.violations if v.get("check") == "integrity"), None)
        why = first["reason"] if first else "inconsistent structure"
        return reject("dataset failed integrity: %s" % why)

    # --- ROW COUNT ------------------------------------------------------- #
    count_ok = state.rows >= params.min_rows
    # If the body was truncated at max_bytes, the count is a LOWER BOUND. A
    # min_rows PASS on truncated data is still acceptable (we have proof of at
    # least that many records); a FAIL is reported as such but flagged so the
    # creator knows more rows may exist beyond the cap.
    checks["min_rows"] = {
        "ok": count_ok, "rows": state.rows, "min_rows": params.min_rows,
        "truncated": bool(truncated),
    }
    if not count_ok:
        bound = " (body truncated at max_bytes; true count may be higher)" if truncated else ""
        evidence["violations"].insert(0, {
            "check": "min_rows",
            "reason": "only %d record(s), need >= %d%s" % (state.rows, params.min_rows, bound),
        })
        return reject(
            "dataset has %d record(s), below the required minimum of %d%s"
            % (state.rows, params.min_rows, bound)
        )

    # --- REQUIRED COLUMNS / KEYS + SCHEMA (already accumulated) ---------- #
    required = params.effective_required()
    req_violations = [v for v in state.violations if v.get("check") in ("required_columns", "required_keys")]
    schema_violations = [v for v in state.violations if v.get("check") == "schema"]
    checks["required"] = {
        "ok": not req_violations, "names": list(required),
        "violations": len(req_violations),
    }
    checks["schema"] = {
        "ok": not schema_violations, "fields": list(params.schema.keys()),
        "violations": len(schema_violations),
    }
    if req_violations:
        v = req_violations[0]
        return reject(
            "dataset is missing a required %s: %s"
            % ("column" if v.get("check") == "required_columns" else "key", v["reason"])
        )
    if schema_violations:
        v = schema_violations[0]
        where = ""
        if v.get("row") is not None:
            where = " (row %d, %s %r)" % (
                v["row"],
                "column" if v.get("column") else "key",
                v.get("column") or v.get("key"),
            )
        return reject("dataset has a type violation%s: %s" % (where, v["reason"]))

    # --- ACCEPT ---------------------------------------------------------- #
    bits = ["%d record(s)" % state.rows, "format %s" % fmt]
    if state.columns:
        shown = state.columns[:8]
        more = "" if len(state.columns) <= 8 else ", +%d more" % (len(state.columns) - 8)
        bits.append("columns [%s%s]" % (", ".join(shown), more))
    if required:
        bits.append("all %d required field(s) present" % len(required))
    if params.schema:
        bits.append("schema OK over %d sampled record(s)" % state.sampled)
    detail = "dataset verified: " + ", ".join(bits)
    return VerifyResult(verified=True, detail=detail, evidence=evidence)


# --------------------------------------------------------------------------- #
# The oracle (networked entry point)
# --------------------------------------------------------------------------- #
def verify(
    params: VerificationParams,
    proof: Any,
    *,
    client: Optional[HttpClient] = None,
) -> VerifyResult:
    """Resolve a dataset mission. Read-only; SSRF-guarded; fail-closed.

    :param params:  the parsed :class:`VerificationParams` for the mission.
    :param proof:   the submission proof — the dataset URL (string, bare host, or
                    ``{"url": ...}``; see :func:`parse_proof_url`).
    :param client:  inject an :class:`HttpClient` (or one wrapping a stub
                    transport in tests). When omitted, a real client is built
                    honouring ``params.allow_private``.
    :returns:       a :class:`VerifyResult`. ``evidence`` always carries
                    ``rows`` / ``columns`` / ``violations`` plus a per-check trace.
    """
    if client is None:
        client = HttpClient(allow_private=params.allow_private)

    pre_evidence: Dict[str, Any] = {
        "verifier": "dataset",
        "rows": 0,
        "columns": [],
        "violations": [],
        "checks": {},
    }

    def reject_pre(detail: str) -> VerifyResult:
        return VerifyResult(verified=False, detail=detail, evidence=pre_evidence)

    # --- 0) PARSE PROOF URL ---------------------------------------------- #
    try:
        target = parse_proof_url(proof)
    except ValueError as exc:
        pre_evidence["checks"]["proof_parsed"] = {"ok": False, "reason": str(exc)}
        return reject_pre("invalid proof: %s" % exc)
    pre_evidence["target_url"] = target
    pre_evidence["checks"]["proof_parsed"] = {"ok": True, "url": target}

    parts = urllib.parse.urlsplit(target)
    host = (parts.hostname or "").lower()

    # --- 1) SOURCE-URL PIN ----------------------------------------------- #
    if params.source_url is not None:
        try:
            want = normalize_url(params.source_url)
        except ValueError as exc:
            pre_evidence["checks"]["source_url"] = {"ok": False, "reason": "bad params.source_url: %s" % exc}
            return reject_pre("misconfigured mission: source_url is not a URL (%s)" % exc)
        url_ok = (target == want)
        pre_evidence["checks"]["source_url"] = {"ok": url_ok, "expected": want, "actual": target}
        if not url_ok:
            return reject_pre(
                "proof URL %s does not equal the required source_url %s" % (target, want)
            )

    # --- 1b) SSRF guard (friendly early reject; authoritative guard is in
    # HttpClient._guard which runs on EVERY hop). Gate on the CLIENT's
    # allow_private so the pre-check and per-hop guard never disagree. --------- #
    if not getattr(client, "allow_private", params.allow_private):
        ok, reason = is_public_host(host)
        pre_evidence["checks"]["ssrf"] = {"ok": ok, "reason": reason, "host": host}
        if not ok:
            return reject_pre("refused to fetch %s: %s" % (target, reason))

    # --- 2) DOWNLOAD ----------------------------------------------------- #
    try:
        resp = client.get(
            target,
            timeout=params.timeout,
            max_bytes=params.max_bytes,
            follow_redirects=params.follow_redirects,
            max_redirects=params.max_redirects,
        )
    except SSRFBlocked as exc:
        pre_evidence["checks"]["download"] = {"ok": False, "reason": str(exc), "ssrf": True}
        return reject_pre(str(exc))
    except HttpError as exc:
        pre_evidence["checks"]["download"] = {"ok": False, "reason": str(exc)}
        return reject_pre("dataset is not reachable: %s" % exc)

    pre_evidence["final_url"] = resp.url
    if resp.redirects:
        pre_evidence["redirect_chain"] = resp.redirects

    # --- 3) STATUS ------------------------------------------------------- #
    status_ok = resp.status in params.expect_status
    pre_evidence["checks"]["status"] = {
        "ok": status_ok, "status": resp.status, "expected": list(params.expect_status),
    }
    if not status_ok:
        return reject_pre(
            "download returned HTTP %d (expected %s)"
            % (resp.status, list(params.expect_status))
        )

    # --- 4) DECIDE FORMAT + RUN CONTENT CHECKS --------------------------- #
    if params.format_explicit:
        fmt = params.format
    else:
        fmt = infer_format(resp.url, resp.content_type)

    result = verify_bytes(
        resp.body, params, fmt=fmt, truncated=resp.truncated, source=resp.url
    )
    # Merge the network-stage trace into the content-stage evidence.
    ev = result.evidence
    ev.setdefault("checks", {})
    ev["checks"].update(pre_evidence["checks"])
    ev["target_url"] = target
    ev["final_url"] = resp.url
    if resp.redirects:
        ev["redirect_chain"] = resp.redirects
    ev["content_type"] = resp.content_type or None
    if not params.format_explicit:
        ev["format_inferred"] = fmt
    return result


def verify_mission(
    mission: Mapping[str, Any],
    proof: Any = None,
    *,
    client: Optional[HttpClient] = None,
) -> VerifyResult:
    """Convenience wrapper: verify a raw OABP mission dict + a proof.

    Reads ``verification_params`` straight off the mission object so a resolver
    can pass the JSON it already has. If the proof is not given explicitly, this
    will also look for it on the mission's most recent submission
    (``mission['submissions'][-1]['proof']``) when present.
    """
    base = {"verifier": "dataset", "rows": 0, "columns": [], "violations": [], "checks": {}}
    if not isinstance(mission, Mapping):
        return VerifyResult(False, "mission is not an object", dict(base))
    try:
        params = VerificationParams.from_mapping(mission.get("verification_params"))
    except ValueError as exc:
        ev = dict(base)
        ev["error"] = str(exc)
        return VerifyResult(False, "invalid verification_params: %s" % exc, ev)

    if proof is None:
        subs = mission.get("submissions")
        if isinstance(subs, (list, tuple)) and subs:
            last = subs[-1]
            if isinstance(last, Mapping):
                proof = last.get("proof") or last.get("proof_data") or last.get("content")

    return verify(params, proof, client=client)


# =========================================================================== #
# Offline self-test (stubs the transport; no network). Runs under --self-test.
# =========================================================================== #
def _stub_transport(routes: Dict[str, Tuple[int, Any, Optional[Dict[str, str]]]]):
    """Build a transport returning canned ``(status, body, headers)`` per URL.

    ``routes`` maps an exact normalised URL to ``(status, body, headers)`` where
    ``body`` is ``bytes`` or ``str`` (str is UTF-8 encoded). A ``Location`` header
    drives redirect tests. A missing route raises :class:`HttpError` (simulating
    an unreachable host) so the "not reachable" branch can be exercised without
    DNS.
    """

    def transport(method, url, headers, timeout, max_bytes):
        norm = normalize_url(url)
        if norm not in routes:
            raise HttpError("stub: no route for %s (simulated DNS/conn failure)" % norm)
        status, body, hdrs = routes[norm]
        if isinstance(body, (bytes, bytearray)):
            raw = bytes(body)
        elif isinstance(body, str):
            raw = body.encode("utf-8")
        else:
            raw = json.dumps(body).encode("utf-8")
        truncated = False
        if len(raw) > max_bytes:
            raw = raw[:max_bytes]
            truncated = True
        h = {"content-type": "application/octet-stream"}
        if hdrs:
            h.update({k.lower(): v for k, v in hdrs.items()})
        return HttpResponse(status=status, url=norm, body=raw, headers=h, truncated=truncated)

    return transport


def _client_for(routes, *, allow_private=True) -> HttpClient:
    # allow_private=True here only so the self-test can use example.com hosts via
    # a STUB transport without real DNS; SSRF is tested separately via
    # is_public_host() and the real-guard path with allow_private=False.
    return HttpClient(allow_private=allow_private, transport=_stub_transport(routes))


# Fixtures shared by the self-test ------------------------------------------- #
_CSV_GOOD = (
    "symbol,address,chain,decimals\n"
    "WETH,0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2,ethereum,18\n"
    "USDC,0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48,ethereum,6\n"
    "WBTC,0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599,ethereum,8\n"
    "ARB,0x912CE59144191C1204E64559FE8253a0e49E6548,arbitrum,18\n"
)
_CSV_SHORT = "symbol,address,decimals\nWETH,0xabc,18\n"
_CSV_MISSING_COL = (
    "symbol,address\n"             # no 'decimals' column
    "WETH,0xabc\nUSDC,0xdef\nWBTC,0x123\n"
)
_CSV_BAD_TYPE = (
    "symbol,address,decimals\n"
    "WETH,0xabc,18\n"
    "USDC,0xdef,six\n"             # decimals 'six' is not an int
    "WBTC,0x123,8\n"
)
_CSV_RAGGED = (
    "symbol,address,decimals\n"
    "WETH,0xabc,18\n"
    "USDC,0xdef\n"                 # ragged: 2 fields, header has 3
    "WBTC,0x123,8\n"
)
_CSV_DUP_HEADER = "symbol,address,symbol\nA,0x1,A2\nB,0x2,B2\n"

_JSONL_GOOD = "\n".join([
    json.dumps({"prompt": "hi", "label": "greeting", "score": 0.9}),
    json.dumps({"prompt": "bye", "label": "farewell", "score": 0.1}),
    "",  # blank line allowed
    json.dumps({"prompt": "ok", "label": "ack", "score": None}),
]) + "\n"
_JSONL_MISSING_KEY = "\n".join([
    json.dumps({"prompt": "hi", "label": "greeting"}),
    json.dumps({"prompt": "bye"}),          # missing 'label'
]) + "\n"
_JSONL_BAD_TYPE = "\n".join([
    json.dumps({"prompt": "hi", "label": "greeting", "score": 0.9}),
    json.dumps({"prompt": "bye", "label": 7, "score": 0.1}),  # label int, want string
]) + "\n"
_JSONL_BAD_LINE = json.dumps({"prompt": "hi", "label": "g"}) + "\n{not json}\n"
_JSONL_NONOBJECT = json.dumps(["a", "b"]) + "\n" + json.dumps({"prompt": "x", "label": "y"}) + "\n"

_JSON_ARRAY_GOOD = json.dumps([
    {"id": 1, "name": "a", "tags": ["x"]},
    {"id": 2, "name": "b", "tags": []},
    {"id": 3, "name": "c", "tags": None},
])
_JSON_WRAPPED_GOOD = json.dumps({
    "data": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
    "meta": {"total": 2},
})
_JSON_SCALAR = json.dumps({"hello": "world"})  # no records array
_JSON_BAD_TYPE = json.dumps([
    {"id": 1, "name": "a"},
    {"id": "two", "name": "b"},   # id not int
])


def _self_test(verbose: bool = False) -> None:  # noqa: C901 - exhaustive by design
    """Assertions proving accept/reject behaviour over CSV + JSONL + JSON."""

    def say(msg: str) -> None:
        if verbose:
            print(msg)

    # ---- URL / proof helpers -------------------------------------------- #
    assert normalize_url("data.example.com/x.csv") == "https://data.example.com/x.csv"
    assert normalize_url("HTTPS://Data.Example.COM:443/A.JSON") == "https://data.example.com/A.JSON"
    for bad in ["", "   ", "ftp://x.example.com/a", "https://"]:
        try:
            normalize_url(bad)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected ValueError for url %r" % bad)
    assert parse_proof_url('{"dataset_url": "https://d.example.com/a.csv"}') == "https://d.example.com/a.csv"
    assert parse_proof_url({"download_url": "https://d.example.com/a.jsonl"}) == "https://d.example.com/a.jsonl"
    say("url/proof parsing OK")

    # ---- format inference ----------------------------------------------- #
    assert infer_format("https://x/y.csv") == "csv"
    assert infer_format("https://x/y.jsonl") == "jsonl"
    assert infer_format("https://x/y.ndjson") == "jsonl"
    assert infer_format("https://x/y.json") == "json"
    assert infer_format("https://x/y", "application/x-ndjson") == "jsonl"
    assert infer_format("https://x/y", "text/csv; charset=utf-8") == "csv"
    assert infer_format("https://x/y", "application/json") == "json"
    assert infer_format("https://x/y") == "csv"
    say("format inference OK")

    # ---- type checking primitives --------------------------------------- #
    ftint = _parse_field_type("int")
    assert check_value_type("42", ftint, is_csv=True)[0] is True
    assert check_value_type("4.2", ftint, is_csv=True)[0] is False
    assert check_value_type(42, ftint, is_csv=False)[0] is True
    assert check_value_type(True, ftint, is_csv=False)[0] is False   # bool != int
    assert check_value_type(4.2, ftint, is_csv=False)[0] is False
    ftnum = _parse_field_type("number")
    assert check_value_type("4.2", ftnum, is_csv=True)[0] is True
    assert check_value_type(4, ftnum, is_csv=False)[0] is True
    ftnull = _parse_field_type("number?")
    assert check_value_type("", ftnull, is_csv=True)[0] is True
    assert check_value_type(None, ftnull, is_csv=False)[0] is True
    ftarr = _parse_field_type(["array", "null"])
    assert check_value_type([], ftarr, is_csv=False)[0] is True
    assert check_value_type(None, ftarr, is_csv=False)[0] is True
    assert check_value_type({}, ftarr, is_csv=False)[0] is False
    ftany = _parse_field_type("any")
    assert check_value_type({"x": 1}, ftany, is_csv=False)[0] is True
    say("type-check primitives OK")

    # ---- effective_required derivation ---------------------------------- #
    p = VerificationParams.from_mapping({
        "format": "csv",
        "required_columns": ["a"],
        "schema": {"a": "string", "b": "int", "c": "int?"},
    })
    # a (explicit) + b (schema, required) ; c is nullable so NOT implied-required
    assert set(p.effective_required()) == {"a", "b"}, p.effective_required()
    say("effective_required OK")

    # ========================= CSV PATH ================================== #
    csv_url = "https://data.example.com/pairs.csv"
    base_csv = {
        "format": "csv", "min_rows": 3,
        "required_columns": ["symbol", "address", "decimals"],
        "schema": {"symbol": "string", "address": "string", "decimals": "int"},
        "source_url": csv_url,
    }
    p = VerificationParams.from_mapping(base_csv)

    r = verify(p, csv_url, client=_client_for({csv_url: (200, _CSV_GOOD, {"content-type": "text/csv"})}))
    assert r.verified, r.detail
    assert r.evidence["rows"] == 4, r.evidence["rows"]
    assert r.evidence["columns"] == ["symbol", "address", "chain", "decimals"]
    assert r.evidence["violations"] == []
    say("CSV good -> verified (%s)" % r.detail)

    # too few rows
    r = verify(p, csv_url, client=_client_for({csv_url: (200, _CSV_SHORT, None)}))
    assert not r.verified and "below the required minimum" in r.detail, r.detail
    assert r.evidence["rows"] == 1
    say("CSV short -> rejected (%s)" % r.detail)

    # missing required column (min_rows lowered so the count passes and we hit the column check)
    p2 = VerificationParams.from_mapping({**base_csv, "min_rows": 2})
    r = verify(p2, csv_url, client=_client_for({csv_url: (200, _CSV_MISSING_COL, None)}))
    assert not r.verified and "required column" in r.detail, r.detail
    assert any(v["check"] == "required_columns" for v in r.evidence["violations"]) or \
        any(v["check"] == "schema" for v in r.evidence["violations"]), r.evidence["violations"]
    say("CSV missing-col -> rejected (%s)" % r.detail)

    # wrong type
    p3 = VerificationParams.from_mapping({**base_csv, "min_rows": 2})
    r = verify(p3, csv_url, client=_client_for({csv_url: (200, _CSV_BAD_TYPE, None)}))
    assert not r.verified and "type violation" in r.detail, r.detail
    assert any(v["check"] == "schema" and v.get("column") == "decimals" for v in r.evidence["violations"])
    say("CSV bad-type -> rejected (%s)" % r.detail)

    # ragged row (integrity)
    r = verify(p3, csv_url, client=_client_for({csv_url: (200, _CSV_RAGGED, None)}))
    assert not r.verified, r.detail
    assert ("integrity" in r.detail) or ("type violation" in r.detail) or ("required column" in r.detail), r.detail
    assert any(v["check"] == "integrity" for v in r.evidence["violations"])
    say("CSV ragged -> rejected (%s)" % r.detail)

    # duplicate header (integrity)
    pdup = VerificationParams.from_mapping({"format": "csv", "min_rows": 1})
    r = verify(pdup, csv_url, client=_client_for({csv_url: (200, _CSV_DUP_HEADER, None)}))
    assert not r.verified and "integrity" in r.detail, r.detail
    say("CSV dup-header -> rejected (%s)" % r.detail)

    # ========================= JSONL PATH ================================ #
    jl_url = "https://data.example.com/train.jsonl"
    base_jl = {
        "format": "jsonl", "min_rows": 2,
        "required_keys": ["prompt", "label"],
        "schema": {"prompt": "string", "label": "string", "score": "number?"},
        "source_url": jl_url,
    }
    pj = VerificationParams.from_mapping(base_jl)

    r = verify(pj, jl_url, client=_client_for({jl_url: (200, _JSONL_GOOD, {"content-type": "application/x-ndjson"})}))
    assert r.verified, r.detail
    assert r.evidence["rows"] == 3, r.evidence["rows"]           # blank line not counted
    assert set(r.evidence["columns"]) >= {"prompt", "label", "score"}
    say("JSONL good -> verified (%s)" % r.detail)

    # missing key
    r = verify(pj, jl_url, client=_client_for({jl_url: (200, _JSONL_MISSING_KEY, None)}))
    assert not r.verified and "required key" in r.detail, r.detail
    assert any(v["check"] == "required_keys" and v.get("key") == "label" for v in r.evidence["violations"])
    say("JSONL missing-key -> rejected (%s)" % r.detail)

    # bad type (label is int)
    r = verify(pj, jl_url, client=_client_for({jl_url: (200, _JSONL_BAD_TYPE, None)}))
    assert not r.verified and "type violation" in r.detail, r.detail
    say("JSONL bad-type -> rejected (%s)" % r.detail)

    # malformed line
    r = verify(pj, jl_url, client=_client_for({jl_url: (200, _JSONL_BAD_LINE, None)}))
    assert not r.verified and "does not parse as jsonl" in r.detail, r.detail
    say("JSONL bad-line -> rejected (%s)" % r.detail)

    # non-object record (integrity)
    pj2 = VerificationParams.from_mapping({**base_jl, "min_rows": 1})
    r = verify(pj2, jl_url, client=_client_for({jl_url: (200, _JSONL_NONOBJECT, None)}))
    assert not r.verified, r.detail
    assert any(v["check"] == "integrity" for v in r.evidence["violations"])
    say("JSONL non-object -> rejected (%s)" % r.detail)

    # ========================= JSON PATH ================================= #
    js_url = "https://data.example.com/records.json"
    base_js = {
        "format": "json", "min_rows": 3,
        "required_keys": ["id", "name"],
        "schema": {"id": "int", "name": "string", "tags": ["array", "null"]},
        "source_url": js_url,
    }
    pjs = VerificationParams.from_mapping(base_js)

    r = verify(pjs, js_url, client=_client_for({js_url: (200, _JSON_ARRAY_GOOD, {"content-type": "application/json"})}))
    assert r.verified, r.detail
    assert r.evidence["rows"] == 3, r.evidence["rows"]
    say("JSON array good -> verified (%s)" % r.detail)

    # wrapped {"data":[...]}
    pjs_w = VerificationParams.from_mapping({"format": "json", "min_rows": 2, "required_keys": ["id", "name"],
                                             "schema": {"id": "int", "name": "string"}, "source_url": js_url})
    r = verify(pjs_w, js_url, client=_client_for({js_url: (200, _JSON_WRAPPED_GOOD, None)}))
    assert r.verified, r.detail
    assert r.evidence["rows"] == 2
    say("JSON wrapped good -> verified (%s)" % r.detail)

    # scalar / no records array
    r = verify(pjs, js_url, client=_client_for({js_url: (200, _JSON_SCALAR, None)}))
    assert not r.verified and "does not parse as json" in r.detail, r.detail
    say("JSON scalar -> rejected (%s)" % r.detail)

    # bad type in json
    pjs_b = VerificationParams.from_mapping({"format": "json", "min_rows": 2, "required_keys": ["id", "name"],
                                             "schema": {"id": "int", "name": "string"}, "source_url": js_url})
    r = verify(pjs_b, js_url, client=_client_for({js_url: (200, _JSON_BAD_TYPE, None)}))
    assert not r.verified and "type violation" in r.detail, r.detail
    say("JSON bad-type -> rejected (%s)" % r.detail)

    # ========================= NETWORK-STAGE REJECTS ===================== #
    # source_url mismatch
    pmm = VerificationParams.from_mapping({**base_csv})
    r = verify(pmm, "https://evil.example.com/pairs.csv",
               client=_client_for({csv_url: (200, _CSV_GOOD, None)}))
    assert not r.verified and "does not equal the required source_url" in r.detail, r.detail
    say("source_url mismatch -> rejected (%s)" % r.detail)

    # non-200
    r = verify(p, csv_url, client=_client_for({csv_url: (404, "not found", None)}))
    assert not r.verified and "HTTP 404" in r.detail, r.detail
    say("HTTP 404 -> rejected (%s)" % r.detail)

    # unreachable (no route)
    r = verify(p, csv_url, client=_client_for({}))
    assert not r.verified and "not reachable" in r.detail, r.detail
    say("unreachable -> rejected (%s)" % r.detail)

    # empty body
    r = verify(p, csv_url, client=_client_for({csv_url: (200, b"", None)}))
    assert not r.verified and "empty" in r.detail, r.detail
    say("empty body -> rejected (%s)" % r.detail)

    # ---- SSRF guard (real guard path, allow_private=False) -------------- #
    ok, _ = is_public_host("127.0.0.1")
    assert ok is False
    ok, _ = is_public_host("localhost")
    assert ok is False
    ok, _ = is_public_host("169.254.169.254")
    assert ok is False
    ok, _ = is_public_host("10.0.0.5")
    assert ok is False
    ok, _ = is_public_host("8.8.8.8")
    assert ok is True
    # verify() refuses a private proof when allow_private is False
    pssrf = VerificationParams.from_mapping({"format": "csv", "min_rows": 1})
    client_priv_block = HttpClient(allow_private=False, transport=_stub_transport({}))
    r = verify(pssrf, "http://127.0.0.1/pairs.csv", client=client_priv_block)
    assert not r.verified and "refused to fetch" in r.detail, r.detail
    say("SSRF private -> refused (%s)" % r.detail)

    # ---- truncation: count is a lower bound ----------------------------- #
    # cap the body so it truncates; min_rows beyond the readable count fails but
    # is flagged as possibly-higher.
    big = "a,b\n" + "".join("%d,%d\n" % (i, i) for i in range(100))
    ptr = VerificationParams.from_mapping({"format": "csv", "min_rows": 9999, "max_bytes": 40})
    # max_bytes 40 cuts the body; rows < 9999 -> reject with truncation note
    r = verify(ptr, csv_url, client=_client_for({csv_url: (200, big, None)}))
    assert not r.verified and "truncated" in r.detail, r.detail
    say("truncated under-count -> rejected with note (%s)" % r.detail)

    # ---- verify_bytes direct (no network) + verify_mission -------------- #
    rb = verify_bytes(_CSV_GOOD.encode("utf-8"),
                      VerificationParams.from_mapping({"format": "csv", "min_rows": 4,
                                                       "required_columns": ["symbol", "decimals"],
                                                       "schema": {"decimals": "int"}}))
    assert rb.verified, rb.detail
    say("verify_bytes direct -> verified (%s)" % rb.detail)

    mission = {
        "id": "mis_demo",
        "verification_type": "oracle",
        "verification_params": base_jl,
        "submissions": [{"submitter_agent_id": "agent_x", "proof": jl_url}],
    }
    r = verify_mission(mission, None,
                       client=_client_for({jl_url: (200, _JSONL_GOOD, None)}))
    assert r.verified, r.detail
    say("verify_mission (proof from submissions) -> verified (%s)" % r.detail)

    # bad format in params -> verify_mission surfaces it
    r = verify_mission({"verification_params": {"format": "parquet"}}, "https://x/y")
    assert not r.verified and "invalid verification_params" in r.detail, r.detail
    say("bad format -> rejected (%s)" % r.detail)

    say("all self-test assertions passed")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dataset_verifier.py",
        description=(
            "OABP / AIGEN dataset-deliverable mission verifier. Downloads a "
            "submitted dataset URL (size-capped, read-only, SSRF-guarded), parses "
            "it as CSV / JSONL / JSON with the stdlib, and checks row count, "
            "required columns/keys, per-field schema types, and integrity. Prints "
            "the VerifyResult JSON and exits 0 (verified) / 1 (rejected) / 2 (usage)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--proof", help="the submission proof: the dataset URL (or {\"url\":...}).")
    p.add_argument("--file", help="verify a LOCAL file at this path instead of fetching (offline).")
    p.add_argument("--format", choices=list(VALID_FORMATS),
                   help="dataset format; if omitted, inferred from URL ext / Content-Type (default csv).")
    p.add_argument("--min-rows", type=int, default=0, help="minimum number of data records.")
    p.add_argument("--required-columns", default="",
                   help="comma-separated required column names (CSV).")
    p.add_argument("--required-keys", default="",
                   help="comma-separated required keys (JSON/JSONL).")
    p.add_argument("--schema", action="append", default=[],
                   metavar="NAME=TYPE",
                   help="per-field type, e.g. 'decimals=int' or 'score=number?' or "
                        "'tags=array|null'. Repeatable.")
    p.add_argument("--sample-rows", type=int, default=DEFAULT_SAMPLE_ROWS,
                   help="type/key checks run on the first N records (0 = all).")
    p.add_argument("--delimiter", default=",", help="CSV delimiter (single char).")
    p.add_argument("--no-header", action="store_true",
                   help="CSV has no header row (synthesise col0..colN).")
    p.add_argument("--encoding", default="utf-8", help="body decode charset.")
    p.add_argument("--source-url", help="pin: the proof URL must equal this exact URL.")
    p.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES,
                   help="hard cap on body bytes downloaded/read.")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="request timeout seconds.")
    p.add_argument("--expect-status", default="200",
                   help="acceptable final HTTP status (comma-separated for several).")
    p.add_argument("--allow-private", action="store_true",
                   help="DANGEROUS: permit private/loopback/reserved targets (testing only).")
    p.add_argument("--no-follow-redirects", action="store_true", help="do not follow 3xx redirects.")
    p.add_argument("--self-test", action="store_true",
                   help="Run the offline self-test (stubs the transport; no network) and exit.")
    p.add_argument("--quiet", action="store_true", help="print only the JSON result, no extra lines.")
    return p


def _params_from_args(args: argparse.Namespace) -> VerificationParams:
    schema_map: Dict[str, Any] = {}
    for item in args.schema:
        if "=" not in item:
            raise ValueError("--schema must be NAME=TYPE, got %r" % item)
        name, _, typ = item.partition("=")
        name = name.strip()
        typ = typ.strip()
        if not name or not typ:
            raise ValueError("--schema must be NAME=TYPE, got %r" % item)
        # support 'a|b' -> list
        schema_map[name] = [t for t in typ.split("|")] if "|" in typ else typ

    req_cols = [c.strip() for c in args.required_columns.split(",") if c.strip()]
    req_keys = [c.strip() for c in args.required_keys.split(",") if c.strip()]
    es = [s.strip() for s in str(args.expect_status).split(",") if s.strip()]

    data: Dict[str, Any] = {
        "min_rows": args.min_rows,
        "sample_rows": args.sample_rows,
        "delimiter": args.delimiter,
        "has_header": not args.no_header,
        "encoding": args.encoding,
        "max_bytes": args.max_bytes,
        "timeout": args.timeout,
        "expect_status": es if len(es) != 1 else es[0],
        "allow_private": args.allow_private,
        "follow_redirects": not args.no_follow_redirects,
    }
    if args.format:
        data["format"] = args.format
    if req_cols:
        data["required_columns"] = req_cols
    if req_keys:
        data["required_keys"] = req_keys
    if schema_map:
        data["schema"] = schema_map
    if args.source_url:
        data["source_url"] = args.source_url
    return VerificationParams.from_mapping(data)


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.self_test:
        try:
            _self_test(verbose=not args.quiet)
        except AssertionError as exc:  # pragma: no cover
            sys.stderr.write("SELF-TEST FAILED: %s\n" % exc)
            return 2
        if not args.quiet:
            print("\ndataset-verifier self-test: OK")
        return 0

    try:
        params = _params_from_args(args)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2

    # --file: verify a local dataset offline (skips the network entirely).
    if args.file:
        try:
            with open(args.file, "rb") as fh:
                body = fh.read(params.max_bytes + 1)
        except OSError as exc:
            sys.stderr.write("ERROR: cannot read --file %r: %s\n" % (args.file, exc))
            return 2
        truncated = len(body) > params.max_bytes
        if truncated:
            body = body[: params.max_bytes]
        if args.format:
            fmt = args.format
        else:
            fmt = infer_format("file://" + os.path.abspath(args.file), "")
        result = verify_bytes(body, params, fmt=fmt, truncated=truncated, source=args.file)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.verified else 1

    if not args.proof:
        sys.stderr.write("ERROR: --proof <url> is required (or use --file / --self-test).\n")
        return 2

    result = verify(params, args.proof)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
