#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OABP / AIGEN mission verifier: *a documentation deliverable meets a quality bar*.

What this is
============
A **deterministic, explainable** verifier for the OABP / AIGEN agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``. The protocol pays bounties
for *content* work — docs, READMEs, guides, API references, tutorials, and
**translations**. This module resolves those missions: given a mission's
``verification_params`` (the structural quality bar the creator set) and a
submission ``proof`` (a URL to the rendered/raw markdown, or the raw markdown
text itself), it fetches/reads the markdown and **scores its structure**, then
returns a precise pass/fail per rule plus an aggregate score.

It sits next to the protocol's existing verifier styles:

* **content-addressed** (``first_valid_match`` — regex over the proof string),
* **oracle-backed** (GoPlus token-security for safety reviews; GitHub REST for
  repo deliverables; on-chain settlement; PyPI publication),

and adds the missing one for the *content* economy: a **structural document
grader**. Like the other verifiers it is:

* **Deterministic & re-runnable** — the same markdown always yields the same
  verdict. Every rule is a mechanical check over the document's structure
  (word count, headings, fenced code blocks, links). Anyone can re-run it and
  reproduce the result; nothing depends on a model, a clock, or hidden state.
* **Explainable** — the result carries a **per-check breakdown** (one entry per
  rule, each ``{"ok": bool, ...}``) and an aggregate ``score`` in ``[0, 1]``, so
  a creator/auditor/solver sees *exactly* which rule passed or failed and by how
  much. The ``detail`` line names the FIRST failing rule.
* **stdlib only** — ``urllib`` + ``re``; runs in a resolver with zero
  third-party packages installed. The HTTP transport is **injectable**
  (constructor / ``fetch=`` callable), so the bundled offline self-test stubs all
  network with canned bytes and the grader itself never needs the internet when
  the proof is raw markdown.
* **Fail-closed** — anything it cannot affirmatively confirm (proof unparseable,
  fetch failed, a required section missing, too few words, a required link
  absent) is ``verified=False`` with a human-readable reason and the failing
  check named in the breakdown.

⚠️ **What this does NOT do.** It grades **structure, not subjective prose
quality.** It does not judge whether the writing is *good*, *accurate*,
*well-argued*, or *correctly translated* — those are not mechanically decidable
and would require an LLM/human (which this module deliberately avoids, for
determinism and reproducibility). It checks the *measurable contract* the
creator encoded: "at least N words, these sections present, ≥K code examples,
these links included, links not obviously broken, (optionally) written in the
target language." Subjective acceptance, if a mission needs it, is the protocol's
``peer_vote`` / ``creator_judges`` path — not this verifier.

How it grades (the checks)
==========================
Given ``verification_params`` (schema below) and the document's markdown, the
verifier runs an ordered list of independent checks. Each check is **skipped**
(``"enforced": False``, counts as a pass) when its corresponding param is unset,
so a creator only pays for the structure they actually require:

1. **word_count** — the document's word count is ``>= min_words``. Words are
   counted on the *prose* (code-fence bodies are excluded by default, since a
   wall of code should not inflate a "write 800 words" bounty; toggle with
   ``count_code_words``). Markdown punctuation/markup is stripped before
   counting (headings ``#``, list bullets, emphasis ``*_`` , link syntax, inline
   backticks) so the count reflects real words, not markup.
2. **required_sections** — every heading name in ``required_sections`` appears as
   an **H2 or H3** heading (``##`` / ``###``) in the document. Matching is
   case-insensitive and ignores a trailing ``:`` and surrounding markdown
   (so ``## Installation`` satisfies a required ``"Installation"``). Set
   ``heading_levels`` to widen/narrow the accepted levels (default ``[2, 3]``).
3. **code_fences** — the document contains ``>= required_code_fences`` *fenced*
   code blocks (```` ``` ```` or ``~~~`` fences). Inline ``code`` spans do **not**
   count — a docs bounty that asks for "3 runnable examples" means 3 blocks.
4. **must_link** — every URL/substring in ``must_link`` is present as a link
   target (or, failing that, anywhere in the raw text). Comparison normalises a
   trailing slash and is scheme-insensitive (``http``/``https``) so
   ``example.com/x`` matches ``https://example.com/x/``.
5. **no_broken_relative_links** — no markdown link/image points at a
   *relative* path that "looks broken": empty ``()``, a literal placeholder
   (``#``, ``TODO``, ``FIXME``, ``url``, ``link``, ``path/to/...``,
   ``./TODO``…), or whitespace inside the target. (It cannot resolve a relative
   path against a real filesystem from a URL proof, so it flags only
   *structurally* broken/placeholder targets — never false-positives a real
   relative link.) Absolute ``http(s)://`` and ``mailto:`` links are out of
   scope here (their reachability is not a structural property).
6. **language** *(optional, heuristic)* — if ``lang`` is set (e.g. ``"fr"``,
   ``"es"``, ``"de"``, ``"pt"``, ``"it"``, ``"en"``), a lightweight,
   dependency-free heuristic checks the prose is *plausibly* in that language by
   the density of common stop-words for the language (and, for the target,
   against the others). This is a **soft signal** for translation missions
   ("translate the README to French"): it catches an untouched English copy
   submitted as a French translation, but it is explicitly a heuristic, not a
   language classifier, and is reported as such in the breakdown. Tune the bar
   with ``lang_min_ratio`` (default ``1.0`` — the target language's stop-word
   density must merely lead the field).

The aggregate ``score`` ∈ ``[0, 1]`` is the fraction of **enforced** checks that
passed (``passed_enforced / total_enforced``; ``1.0`` when nothing is enforced).
``verified`` is ``True`` iff **every enforced check passed** (i.e. ``score ==
1.0`` over enforced checks AND none failed). The score is a transparency/ranking
aid (e.g. "this submission got 4/5"); payment is gated on ``verified``.

The proof format
----------------
``proof`` is either:

* **raw markdown** — the document text itself (anything containing a newline, a
  heading, or a fence, that is not a bare URL, is treated as inline markdown);
  no network needed. Best for agents that submit the artifact directly.
* **a URL** — ``https://…`` / ``http://…`` pointing at the rendered or raw
  markdown (e.g. a raw GitHub URL ``https://raw.githubusercontent.com/…/README.md``
  or a gist/raw paste). The verifier GETs it (injectable transport) and grades
  the returned bytes as markdown. A non-2xx / unreachable URL ⇒ reject.
* **a JSON object** — ``{"url": "..."}`` or ``{"markdown": "..."}`` (or
  ``{"text": "..."}``) for callers that prefer an explicit, typed proof.

(If ``verification_params.source_url`` is set, it is used as the *canonical*
source and the ``proof`` may be just an attestation; an explicit URL/markdown in
the proof overrides it. ``repo_path`` / ``source_path`` may point at a local file
the resolver can read directly — handy for CI that checked the repo out.)

verification_params schema
==========================
The mission's ``verification_params`` object for this mission-type is::

    {
      # WHERE the document is (all optional; proof can also carry it):
      "source_url": "https://raw.githubusercontent.com/acme/x/main/README.md",
                                    # canonical URL of the doc (proof may override)
      "repo_path":  "docs/guide.md",# OR a path the resolver can read locally
                                    #   (alias: "source_path")

      # STRUCTURAL BAR (each rule is enforced only when its param is set):
      "min_words": 600,             # int >=0; prose word-count floor
      "required_sections":          # list[str]; each must appear as an H2/H3 heading
          ["Overview", "Installation", "Usage", "API", "License"],
      "required_code_fences": 3,    # int >=0; minimum number of fenced code blocks
      "must_link": [                # list[str]; each URL/substring must be linked/present
          "https://cryptogenesis.duckdns.org",
          "https://pypi.org/project/oabp-sdk/"
      ],

      # KNOBS:
      "heading_levels": [2, 3],     # which heading levels satisfy required_sections
      "count_code_words": false,    # include code-fence text in the word count?
      "check_relative_links": true, # run the broken-relative-link check (default true)
      "lang": "fr",                 # OPTIONAL target language for a translation bounty
      "lang_min_ratio": 1.0,        # how strongly the target language must lead (>=1.0)

      # human-readable spec; surfaced to solvers, not parsed by the verifier:
      "description":
          "Write a >=600-word French guide with Overview/Installation/Usage/API/"
          "License sections, >=3 code examples, linking the protocol + SDK."
    }

Every field is optional; a mission with *no* structural params verifies any
non-empty, fetchable document (``score == 1.0``) — useful as a smoke check. The
typed fields are the machine truth; ``description`` is for humans/solvers.

Worked example
==============
Mission::

    verification_params = {
        "min_words": 200,
        "required_sections": ["Overview", "Usage", "License"],
        "required_code_fences": 1,
        "must_link": ["https://cryptogenesis.duckdns.org"],
        "lang": "en",
        "description": "Short English guide: Overview/Usage/License, >=1 example, "
                       "links the protocol.",
    }

An agent submits the raw markdown of a 250-word guide with ``## Overview``,
``## Usage``, ``## License``, one fenced ```` ```python ```` block, and a link to
``https://cryptogenesis.duckdns.org``. The verifier:

* word_count 250 >= 200; ✓
* every required section is an H2; ✓
* 1 fenced block >= 1; ✓
* the protocol URL is linked; ✓
* no broken relative links; ✓
* English stop-word density leads; ✓

=> ``VerifyResult(verified=True, score=1.0, detail="all 6 structural checks
passed …", checks={...})``. Drop the ``## License`` heading and it becomes
``verified=False, score≈0.83, detail="required section 'License' is missing …"``
with ``checks["required_sections"]["ok"] == False`` and the missing name listed.

CLI
===
    # grade raw markdown from a file (no network):
    python3 doc_quality_verifier.py \
        --min-words 200 --required-sections Overview,Usage,License \
        --required-code-fences 1 --must-link https://cryptogenesis.duckdns.org \
        --proof-file ./guide.md --json

    # grade a live URL submission:
    python3 doc_quality_verifier.py \
        --required-sections Overview,Usage --required-code-fences 2 \
        --proof https://raw.githubusercontent.com/acme/x/main/README.md

    # run the bundled OFFLINE self-test (stubs all I/O; no network) and exit:
    python3 doc_quality_verifier.py --self-test

Exit codes (CLI):
* ``0`` — verified True (or, under --self-test, all assertions passed).
* ``1`` — verified False (the document does not satisfy the mission).
* ``2`` — usage / configuration error.
* ``3`` — a fetch / network error prevented a verdict.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

__all__ = [
    "VerifyResult",
    "VerificationParams",
    "DocFetcher",
    "FetchError",
    "verify",
    "verify_mission",
    "grade_markdown",
    "parse_proof",
    "count_words",
    "find_headings",
    "count_code_fences",
    "extract_links",
    "STOPWORDS",
]

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
HTTP_TIMEOUT = 20.0
USER_AGENT = "oabp-doc-quality-verifier/1.0 (+https://cryptogenesis.duckdns.org)"
MAX_FETCH_BYTES = 8 * 1024 * 1024  # 8 MiB cap on a fetched document

# A "URL-ish" proof: a bare http(s) URL with no embedded whitespace.
_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)

# Fenced code block opener: ``` or ~~~ (>=3), optional info string, line-anchored.
# Captures the fence char run so a closing fence must use the same char & length.
_FENCE_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<fence>`{3,}|~{3,})(?P<info>[^\n]*)$")

# ATX heading: 1-6 leading #, a space, then the text (line-anchored).
_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})[ \t]+(?P<text>.+?)[ \t]*#*[ \t]*$")

# Markdown inline/reference link & image targets.
#   [text](target "title")   ![alt](target)   [text](<target with spaces>)
#   reference: [id]: target
# The destination is EITHER an angle-bracket form ``<...>`` (which may legally
# contain spaces) OR a bare run with no whitespace/closing-paren; an optional
# title follows. Captures the destination (angle brackets are stripped by the
# consumer via _clean_target).
_INLINE_LINK_RE = re.compile(
    r"!?\[[^\]]*\]\(\s*(<[^>]*>|[^)\s]*)(?:\s+[^)]*)?\)"
)
_REF_DEF_RE = re.compile(r"^[ \t]*\[[^\]]+\]:\s*(\S+)", re.MULTILINE)
_AUTOLINK_RE = re.compile(r"<((?:https?|mailto):[^>\s]+)>")
_BARE_URL_RE = re.compile(r"https?://[^\s)>\]]+")

# Placeholder / structurally-broken relative targets.
_BROKEN_REL_TARGETS = {
    "", "#", "todo", "fixme", "tbd", "xxx", "url", "link", "href", "path",
    "./", "../", "./todo", "#todo", "path/to/file", "path/to", "your-link-here",
    "insert-link", "changeme",
}


def _clean_target(target: str) -> str:
    """Normalise a captured link destination: strip ``<>`` wrapping + surrounding ws.

    CommonMark allows an angle-bracket destination ``<...>`` that may contain
    spaces; we keep the inner text (including any whitespace, so the
    broken-relative-link check can still flag a spaced target).
    """
    t = (target or "").strip()
    if len(t) >= 2 and t.startswith("<") and t.endswith(">"):
        t = t[1:-1]
    return t


# --------------------------------------------------------------------------- #
# Result + params dataclasses  (house style: VerifyResult / VerificationParams)
# --------------------------------------------------------------------------- #
@dataclass
class VerifyResult:
    """Typed outcome of a doc-quality verification.

    Attributes
    ----------
    verified:
        ``True`` only if every *enforced* structural check passed. The protocol
        pays the bounty iff this is ``True``.
    score:
        Aggregate quality score in ``[0.0, 1.0]`` — the fraction of enforced
        checks that passed (``1.0`` when no check is enforced). A transparency /
        ranking aid; payment is gated on ``verified``, not on ``score``.
    detail:
        Human-readable one-line explanation (the accept summary, or the FIRST
        failing check and why). Safe to log / surface to the creator.
    checks:
        The **per-check breakdown**: an ordered ``dict`` mapping each rule name
        (``word_count``, ``required_sections``, ``code_fences``, ``must_link``,
        ``no_broken_relative_links``, ``language``) to a small JSON-safe object
        ``{"ok": bool, "enforced": bool, ...}`` enumerating that rule's outcome
        (expected vs actual, what was found/missing). Lets anyone re-derive the
        verdict. The top-level ``checks`` also carries an ``_evidence`` summary
        (word count, headings seen, fence count, links) and a ``_summary`` of how
        many checks were enforced/passed.
    """

    verified: bool
    score: float
    detail: str
    checks: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verified": self.verified,
            "score": self.score,
            "detail": self.detail,
            "checks": self.checks,
        }

    def __bool__(self) -> bool:  # truthy == verified, convenient in callers
        return self.verified


@dataclass(frozen=True)
class VerificationParams:
    """Parsed, validated view of a doc-quality mission's ``verification_params``.

    See the module docstring for the JSON schema. ``from_mapping`` is tolerant:
    unknown keys are ignored and wrong-typed optionals fall back to their
    defaults. Nothing is strictly required — an empty params object grades any
    non-empty document (every check unenforced -> ``score == 1.0``).
    """

    source_url: Optional[str] = None
    repo_path: Optional[str] = None
    min_words: Optional[int] = None
    required_sections: Tuple[str, ...] = ()
    required_code_fences: Optional[int] = None
    must_link: Tuple[str, ...] = ()
    heading_levels: Tuple[int, ...] = (2, 3)
    count_code_words: bool = False
    check_relative_links: bool = True
    lang: Optional[str] = None
    lang_min_ratio: float = 1.0
    description: Optional[str] = None

    @classmethod
    def from_mapping(
        cls, data: Optional[Mapping[str, Any]]
    ) -> "VerificationParams":
        if data is None:
            return cls()
        if not isinstance(data, Mapping):
            raise ValueError("verification_params must be an object")

        def _opt_str(*keys: str) -> Optional[str]:
            for k in keys:
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return None

        def _opt_int(*keys: str) -> Optional[int]:
            for k in keys:
                if k in data and data.get(k) is not None:
                    v = data.get(k)
                    if isinstance(v, bool):
                        continue
                    try:
                        return int(v)
                    except (TypeError, ValueError):
                        continue
            return None

        def _str_list(*keys: str) -> Tuple[str, ...]:
            for k in keys:
                v = data.get(k)
                if isinstance(v, str):
                    # allow a comma/newline separated string for convenience
                    parts = [p.strip() for p in re.split(r"[,\n]", v)]
                    return tuple(p for p in parts if p)
                if isinstance(v, (list, tuple)):
                    return tuple(
                        str(p).strip() for p in v if str(p).strip()
                    )
            return ()

        def _bool(key: str, default: bool) -> bool:
            v = data.get(key, default)
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() in ("1", "true", "yes", "on")
            if isinstance(v, (int, float)):
                return bool(v)
            return default

        # heading levels (default [2, 3]); clamp to 1..6, keep order, dedupe.
        levels_raw = data.get("heading_levels")
        levels: Tuple[int, ...]
        if isinstance(levels_raw, (list, tuple)) and levels_raw:
            seen: List[int] = []
            for x in levels_raw:
                try:
                    n = int(x)
                except (TypeError, ValueError):
                    continue
                if 1 <= n <= 6 and n not in seen:
                    seen.append(n)
            levels = tuple(seen) if seen else (2, 3)
        else:
            levels = (2, 3)

        min_words = _opt_int("min_words", "min_word_count", "minimum_words")
        if min_words is not None and min_words < 0:
            min_words = 0
        rcf = _opt_int("required_code_fences", "min_code_fences", "code_fences")
        if rcf is not None and rcf < 0:
            rcf = 0

        lang = _opt_str("lang", "language", "target_language")
        if lang:
            lang = lang.strip().lower()[:5]

        lang_min_ratio_v = data.get("lang_min_ratio")
        try:
            lang_min_ratio = float(lang_min_ratio_v) if lang_min_ratio_v is not None else 1.0
        except (TypeError, ValueError):
            lang_min_ratio = 1.0
        if lang_min_ratio < 1.0:
            lang_min_ratio = 1.0

        return cls(
            source_url=_opt_str("source_url", "url", "doc_url"),
            repo_path=_opt_str("repo_path", "source_path", "path", "file"),
            min_words=min_words,
            required_sections=_str_list("required_sections", "sections"),
            required_code_fences=rcf,
            must_link=_str_list("must_link", "required_links", "links"),
            heading_levels=levels,
            count_code_words=_bool("count_code_words", False),
            check_relative_links=_bool("check_relative_links", True),
            lang=lang,
            lang_min_ratio=lang_min_ratio,
            description=_opt_str("description", "oracle_description", "spec"),
        )


# --------------------------------------------------------------------------- #
# Proof parsing  (raw markdown | URL | JSON {url|markdown})
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ParsedProof:
    """A normalised proof: exactly one of ``markdown`` or ``url`` is set."""

    markdown: Optional[str] = None
    url: Optional[str] = None


def _looks_like_markdown(s: str) -> bool:
    """Heuristic: does this string look like inline markdown rather than a URL?

    True when it spans multiple lines, or carries a heading / fence / common
    markdown markup. A single-line bare ``http(s)://…`` token is treated as a
    URL, not markdown.
    """
    if "\n" in s:
        return True
    stripped = s.strip()
    if _URL_RE.match(stripped):
        return False
    # single-line text that isn't a URL: treat short markup as markdown
    if re.search(r"(^|\s)#{1,6}\s", stripped) or "```" in stripped or "~~~" in stripped:
        return True
    if re.search(r"\[[^\]]+\]\([^)]*\)", stripped):
        return True
    # a single plain line with spaces and no URL -> still markdown (prose)
    return " " in stripped and not _URL_RE.match(stripped)


def parse_proof(proof: Any) -> ParsedProof:
    """Parse a submission proof into a :class:`ParsedProof` (markdown XOR url).

    Accepted forms (in priority order):
      * a mapping ``{"markdown"|"text"|"content": "..."}`` -> inline markdown
      * a mapping ``{"url"|"source_url"|"link": "..."}``   -> URL
      * a JSON object string of either shape
      * a bare ``http(s)://…`` URL string                  -> URL
      * any other non-empty string                          -> inline markdown

    Raises ``ValueError`` if no document can be located in the proof.
    """
    if isinstance(proof, Mapping):
        md = proof.get("markdown")
        if not isinstance(md, str):
            md = proof.get("text")
        if not isinstance(md, str):
            md = proof.get("content")
        if isinstance(md, str) and md.strip():
            return ParsedProof(markdown=md)
        url = proof.get("url") or proof.get("source_url") or proof.get("link")
        if isinstance(url, str) and url.strip():
            return ParsedProof(url=url.strip())
        raise ValueError("proof object must carry a non-empty 'markdown' or 'url'")

    if not isinstance(proof, str) or not proof.strip():
        raise ValueError(
            "proof must be a non-empty string (markdown text or a document URL)"
        )
    s = proof.strip()

    # JSON object string.
    if s.startswith("{"):
        try:
            obj = json.loads(s)
        except ValueError:
            obj = None
        if isinstance(obj, Mapping):
            return parse_proof(obj)

    # Bare URL.
    if _URL_RE.match(s):
        return ParsedProof(url=s)

    # Otherwise: treat the whole thing as inline markdown.
    if _looks_like_markdown(s) or len(s) > 0:
        return ParsedProof(markdown=proof)

    raise ValueError("could not interpret proof as markdown or a URL")


# --------------------------------------------------------------------------- #
# Document fetcher (stdlib urllib). Read-only. Transport injectable.
# --------------------------------------------------------------------------- #
class FetchError(Exception):
    """A network / transport / decode failure fetching a document URL.

    Distinct from "the document fails a structural check" (which the verifier
    represents as ``verified=False``, not an exception): this is reserved for
    *infrastructure* failures (transport, non-2xx, unreadable body) that
    prevented reaching a verdict at all.
    """


class DocFetcher:
    """Read-only document fetcher (stdlib ``urllib`` only).

    GETs a URL and returns its decoded text. A ``fetch`` callable with signature
    ``(url, timeout) -> (status:int, body:bytes)`` may be injected (this is how
    the offline self-test stubs the network with canned bytes). Local file paths
    (``repo_path`` / ``source_path``) are read directly off disk by
    :func:`read_local`.
    """

    def __init__(
        self,
        *,
        timeout: float = HTTP_TIMEOUT,
        max_bytes: int = MAX_FETCH_BYTES,
        fetch: Optional[Callable[[str, float], Tuple[int, bytes]]] = None,
    ) -> None:
        self.timeout = float(timeout)
        self.max_bytes = int(max_bytes)
        self._fetch = fetch

    def get_text(self, url: str) -> str:
        """GET ``url`` and return its decoded body text, or raise FetchError."""
        if self._fetch is not None:
            try:
                status, body = self._fetch(url, self.timeout)
            except Exception as exc:  # pragma: no cover - injected transport
                raise FetchError("GET %s failed: %s" % (url, exc)) from exc
            return self._decode(url, status, body)

        req = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/plain, text/markdown, */*"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.getcode()
                body = resp.read(self.max_bytes + 1)
        except urllib.error.HTTPError as exc:
            raise FetchError("GET %s -> HTTP %s %s" % (url, exc.code, exc.reason)) from exc
        except urllib.error.URLError as exc:
            raise FetchError("GET %s failed: %s" % (url, exc.reason)) from exc
        except (TimeoutError, OSError) as exc:  # pragma: no cover - env dependent
            raise FetchError("GET %s failed: %s" % (url, exc)) from exc
        return self._decode(url, status, body)

    def _decode(self, url: str, status: int, body: bytes) -> str:
        if not (200 <= int(status) < 300):
            raise FetchError("GET %s -> HTTP %s" % (url, status))
        if isinstance(body, (bytes, bytearray)):
            if len(body) > self.max_bytes:
                raise FetchError(
                    "document at %s exceeds %d bytes" % (url, self.max_bytes)
                )
            try:
                return body.decode("utf-8")
            except UnicodeDecodeError:
                return body.decode("utf-8", errors="replace")
        return str(body)

    @staticmethod
    def read_local(path: str, *, max_bytes: int = MAX_FETCH_BYTES) -> str:
        """Read a local markdown file off disk (for repo_path / CI proofs)."""
        try:
            with open(path, "rb") as fh:
                data = fh.read(max_bytes + 1)
        except OSError as exc:
            raise FetchError("could not read local file %s: %s" % (path, exc)) from exc
        if len(data) > max_bytes:
            raise FetchError("local file %s exceeds %d bytes" % (path, max_bytes))
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# Markdown structural analysis  (pure, deterministic, stdlib only)
# --------------------------------------------------------------------------- #
def _split_fences(markdown: str) -> Tuple[List[str], List[Tuple[str, str]], int]:
    """Separate prose lines from fenced-code blocks.

    Returns ``(prose_lines, code_blocks, fence_count)`` where:
      * ``prose_lines`` = every line NOT inside a fenced block (the fence lines
        themselves are also excluded),
      * ``code_blocks`` = list of ``(info_string, body_text)`` for each fenced
        block (body excludes the fences),
      * ``fence_count`` = number of *closed or open* fenced blocks (an unterminated
        fence at EOF still counts as one block — it opened).

    A fence opens on a line matching :data:`_FENCE_RE` and closes on the next line
    whose fence char matches and whose run length is ``>=`` the opener's (CommonMark
    rule). Indented (<4 sp) fences are honoured; we do not treat 4-space-indented
    code as fenced (that is indented code, out of scope for the "fenced" count).
    """
    lines = markdown.split("\n")
    prose: List[str] = []
    blocks: List[Tuple[str, str]] = []
    fence_count = 0

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = _FENCE_RE.match(line)
        # Only treat as a fence opener if it is not indented as code (>=4 spaces).
        opener = None
        if m and len(m.group("indent").replace("\t", "    ")) < 4:
            opener = m
        if opener is None:
            prose.append(line)
            i += 1
            continue

        fence = opener.group("fence")
        fence_char = fence[0]
        fence_len = len(fence)
        info = opener.group("info").strip()
        body_lines: List[str] = []
        i += 1
        closed = False
        while i < n:
            close = _FENCE_RE.match(lines[i])
            if (
                close
                and close.group("fence")[0] == fence_char
                and len(close.group("fence")) >= fence_len
                and close.group("info").strip() == ""
            ):
                closed = True
                i += 1
                break
            body_lines.append(lines[i])
            i += 1
        fence_count += 1  # an opened block counts whether or not it closed
        blocks.append((info, "\n".join(body_lines)))
        _ = closed  # informational only
    return prose, blocks, fence_count


def count_code_fences(markdown: str) -> int:
    """Number of fenced code blocks (```` ``` ```` / ``~~~``) in ``markdown``.

    Inline code spans (`` `like this` ``) are NOT counted. An unterminated fence
    counts as one block (it opened a code region).
    """
    _, _, count = _split_fences(markdown)
    return count


def _strip_inline_markup(text: str) -> str:
    """Remove inline markdown markup so word-counting reflects real words."""
    # inline code spans -> keep the words inside (they're still words a reader sees),
    #   but drop the backticks. (Fenced blocks are removed upstream.)
    text = re.sub(r"`+", " ", text)
    # images/links: keep the visible text, drop the target. ![alt](x) / [txt](x)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r" \1 ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r" \1 ", text)
    # reference-style [txt][id] -> txt ; [txt] -> txt
    text = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", r" \1 ", text)
    # autolinks <http...> -> drop
    text = re.sub(r"<[^>\s]+>", " ", text)
    # emphasis / strikethrough markers
    text = re.sub(r"[*_~]+", " ", text)
    # blockquote / list bullets / heading hashes at line start
    text = re.sub(r"(?m)^[ \t]*([#>*+\-]|\d+\.)[ \t]+", " ", text)
    text = re.sub(r"(?m)^[ \t]*#{1,6}[ \t]*", " ", text)
    # table pipes
    text = text.replace("|", " ")
    return text


_WORD_RE = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)


def count_words(markdown: str, *, include_code: bool = False) -> int:
    """Count prose words in ``markdown`` (deterministic).

    By default the bodies of fenced code blocks are excluded (so a wall of code
    can't inflate a word-count bounty); pass ``include_code=True`` to count them.
    Markdown markup is stripped before counting; a "word" is a run of Unicode
    letters (allowing internal apostrophes/hyphens), so numbers and punctuation
    do not count.
    """
    prose_lines, blocks, _ = _split_fences(markdown)
    text = "\n".join(prose_lines)
    if include_code:
        text = text + "\n" + "\n".join(b for _, b in blocks)
    text = _strip_inline_markup(text)
    return len(_WORD_RE.findall(text))


def _normalize_heading(text: str) -> str:
    """Normalise a heading/section name for case/markup-insensitive comparison."""
    t = text.strip()
    t = t.rstrip(":").strip()
    # strip inline markup from the heading text (links, code, emphasis, numbers)
    t = re.sub(r"`+", "", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[*_~]+", "", t)
    # collapse a leading "1. " / "1.2 " numbering
    t = re.sub(r"^\s*\d+(\.\d+)*[.)]?\s+", "", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def find_headings(markdown: str) -> List[Tuple[int, str]]:
    """Return ``[(level, normalized_text), ...]`` for every ATX heading.

    Headings *inside* fenced code blocks are ignored (they're code, not
    structure). ``# Title`` -> ``(1, "title")``; ``### API Reference:`` ->
    ``(3, "api reference")``.
    """
    prose_lines, _, _ = _split_fences(markdown)
    out: List[Tuple[int, str]] = []
    for line in prose_lines:
        m = _HEADING_RE.match(line)
        if not m:
            continue
        level = len(m.group("hashes"))
        out.append((level, _normalize_heading(m.group("text"))))
    return out


def extract_links(markdown: str) -> List[str]:
    """Return every link/image target found in ``markdown`` (deduped, ordered).

    Covers inline ``[..](target)`` / ``![..](target)``, reference definitions
    ``[id]: target``, autolinks ``<http..>``, and bare ``http(s)://`` URLs in the
    prose. Targets inside fenced code blocks are excluded.
    """
    prose_lines, _, _ = _split_fences(markdown)
    text = "\n".join(prose_lines)
    seen: List[str] = []

    def _add(t: str) -> None:
        t = (t or "").strip()
        if t and t not in seen:
            seen.append(t)

    for m in _INLINE_LINK_RE.finditer(text):
        _add(_clean_target(m.group(1)))
    for m in _REF_DEF_RE.finditer(text):
        _add(m.group(1))
    for m in _AUTOLINK_RE.finditer(text):
        _add(m.group(1))
    for m in _BARE_URL_RE.finditer(text):
        _add(m.group(0))
    return seen


def _norm_url_for_match(u: str) -> str:
    """Normalise a URL/substring for must_link comparison.

    Lowercase, drop the scheme (``http(s)://``) and a trailing slash, so
    ``https://Example.com/X/`` and ``http://example.com/x`` compare equal.
    """
    s = (u or "").strip().lower()
    s = re.sub(r"^https?://", "", s)
    s = s.rstrip("/")
    return s


# --------------------------------------------------------------------------- #
# Broken-relative-link detection
# --------------------------------------------------------------------------- #
def _all_link_targets_with_kind(markdown: str) -> List[str]:
    """Every inline/reference/image link target (NOT bare/auto URLs).

    Used by the broken-relative-link check, which only inspects *authored*
    ``[..](target)`` style links (a bare URL in prose has no "target" to be
    broken).
    """
    prose_lines, _, _ = _split_fences(markdown)
    text = "\n".join(prose_lines)
    out: List[str] = []
    for m in _INLINE_LINK_RE.finditer(text):
        out.append(_clean_target(m.group(1)))
    for m in _REF_DEF_RE.finditer(text):
        out.append(m.group(1))
    return out


def _is_relative_target(target: str) -> bool:
    t = (target or "").strip()
    if not t:
        return True  # empty () is "relative & broken"
    low = t.lower()
    if low.startswith(("http://", "https://", "mailto:", "tel:", "ftp://")):
        return False
    if low.startswith("#"):
        # pure in-page anchor; treat "#" alone as broken, "#section" as relative-ok
        return True
    if low.startswith("//"):  # protocol-relative -> treat as absolute-ish
        return False
    return True


def find_broken_relative_links(markdown: str) -> List[str]:
    """Return the list of *structurally broken* relative link targets.

    A relative target is flagged when it is empty, a known placeholder
    (``#``, ``TODO``, ``path/to/file``…), or contains internal whitespace. Real
    relative paths (``./foo.md``, ``../img/x.png``, ``#section``) are NOT flagged
    (their on-disk existence can't be checked from a URL/markdown proof, so we
    never false-positive them).
    """
    broken: List[str] = []
    for raw in _all_link_targets_with_kind(markdown):
        target = (raw or "").strip()
        if not _is_relative_target(target):
            continue
        low = target.lower()
        if (
            low in _BROKEN_REL_TARGETS
            or target == ""
            or re.search(r"\s", target)            # whitespace inside a target
            or low.startswith("path/to")
            or low in ("todo", "fixme", "tbd")
        ):
            if target not in broken:
                broken.append(target or "<empty>")
    return broken


# --------------------------------------------------------------------------- #
# Language heuristic (stop-word density). Dependency-free, explicitly a heuristic.
# --------------------------------------------------------------------------- #
STOPWORDS: Dict[str, set] = {
    "en": {
        "the", "and", "of", "to", "a", "in", "is", "it", "you", "that", "for",
        "on", "with", "as", "are", "this", "be", "or", "an", "by", "from", "at",
        "your", "can", "will", "not", "if", "we", "but", "they", "have", "has",
    },
    "fr": {
        "le", "la", "les", "de", "des", "un", "une", "et", "est", "que", "qui",
        "dans", "pour", "vous", "ce", "cette", "sur", "avec", "pas", "ne", "se",
        "au", "aux", "du", "en", "il", "elle", "nous", "votre", "sont", "plus",
    },
    "es": {
        "el", "la", "los", "las", "de", "un", "una", "y", "es", "que", "en",
        "para", "con", "por", "se", "no", "su", "al", "del", "como", "más",
        "este", "esta", "usted", "son", "lo", "pero", "puede", "tu", "the",
    },
    "de": {
        "der", "die", "das", "und", "ist", "ein", "eine", "zu", "in", "den",
        "von", "mit", "sich", "auf", "für", "nicht", "auch", "es", "im", "dem",
        "sie", "wir", "sind", "wird", "kann", "oder", "als", "aus", "bei",
    },
    "pt": {
        "o", "a", "os", "as", "de", "um", "uma", "e", "que", "em", "para",
        "com", "por", "se", "não", "do", "da", "no", "na", "mais", "como",
        "este", "esta", "você", "são", "mas", "pode", "seu", "sua", "dos",
    },
    "it": {
        "il", "la", "lo", "i", "le", "di", "un", "una", "e", "che", "in", "per",
        "con", "non", "del", "della", "si", "al", "come", "più", "questo",
        "questa", "sono", "ma", "può", "tuo", "tua", "dei", "delle", "da",
    },
}


def _language_scores(markdown: str) -> Dict[str, float]:
    """Stop-word density per known language for the document's prose.

    Returns ``{lang: ratio}`` where ratio = (count of that language's stop-words
    seen) / (total word tokens). Tokenises lowercased word runs (Unicode
    letters). Deterministic; no model.
    """
    prose_lines, _, _ = _split_fences(markdown)
    text = _strip_inline_markup("\n".join(prose_lines)).lower()
    tokens = _WORD_RE.findall(text)
    total = len(tokens) or 1
    scores: Dict[str, float] = {}
    token_set_counts: Dict[str, int] = {lang: 0 for lang in STOPWORDS}
    for tok in tokens:
        for lang, words in STOPWORDS.items():
            if tok in words:
                token_set_counts[lang] += 1
    for lang in STOPWORDS:
        scores[lang] = token_set_counts[lang] / total
    return scores


# --------------------------------------------------------------------------- #
# The grader  (pure: markdown + params -> VerifyResult)
# --------------------------------------------------------------------------- #
def grade_markdown(
    params: VerificationParams,
    markdown: str,
    *,
    source: Optional[str] = None,
) -> VerifyResult:
    """Grade a markdown document against ``params``. Pure & deterministic.

    Runs every structural check, builds the per-check breakdown + evidence, and
    returns a :class:`VerifyResult` whose ``score`` is the fraction of *enforced*
    checks that passed and whose ``verified`` is ``True`` iff all enforced checks
    passed. No network, no LLM — same input, same output, always.

    :param params:  the parsed :class:`VerificationParams`.
    :param markdown: the document text.
    :param source:  optional provenance string (URL / path / "inline") recorded
                    in the evidence.
    """
    checks: Dict[str, Any] = {}

    # ---- evidence (computed once, reused by checks) --------------------- #
    word_count = count_words(markdown, include_code=params.count_code_words)
    headings = find_headings(markdown)
    fence_count = count_code_fences(markdown)
    links = extract_links(markdown)
    heading_names_at_levels = {
        name for (lvl, name) in headings if lvl in params.heading_levels
    }
    all_heading_names = {name for (_lvl, name) in headings}

    checks["_evidence"] = {
        "source": source,
        "char_count": len(markdown),
        "word_count": word_count,
        "counted_code_words": params.count_code_words,
        "heading_count": len(headings),
        "headings": [
            {"level": lvl, "text": name} for (lvl, name) in headings
        ][:200],
        "code_fence_count": fence_count,
        "link_count": len(links),
        "links": links[:200],
    }

    enforced = 0
    passed = 0
    first_failure: Optional[str] = None

    def record(name: str, is_enforced: bool, ok: bool, extra: Dict[str, Any]) -> None:
        nonlocal enforced, passed, first_failure
        entry = {"ok": bool(ok), "enforced": bool(is_enforced)}
        entry.update(extra)
        checks[name] = entry
        if is_enforced:
            enforced += 1
            if ok:
                passed += 1
            elif first_failure is None:
                first_failure = name

    # ---- 1) word_count -------------------------------------------------- #
    if params.min_words is not None:
        ok = word_count >= params.min_words
        record(
            "word_count",
            True,
            ok,
            {
                "word_count": word_count,
                "min_words": params.min_words,
                "reason": None if ok
                else "document has %d words; mission requires >= %d"
                % (word_count, params.min_words),
            },
        )
    else:
        record("word_count", False, True, {"word_count": word_count})

    # ---- 2) required_sections ------------------------------------------- #
    if params.required_sections:
        wanted = [_normalize_heading(s) for s in params.required_sections]
        missing = [
            orig
            for orig, norm in zip(params.required_sections, wanted)
            if norm not in heading_names_at_levels
        ]
        # be lenient: if a wanted name exists at *some* heading level (just not
        # the configured one), report it as present-but-wrong-level (still fail,
        # but say so clearly).
        wrong_level = [
            orig
            for orig, norm in zip(params.required_sections, wanted)
            if norm in all_heading_names and norm not in heading_names_at_levels
        ]
        ok = not missing
        record(
            "required_sections",
            True,
            ok,
            {
                "required": list(params.required_sections),
                "levels": list(params.heading_levels),
                "present": [
                    orig
                    for orig, norm in zip(params.required_sections, wanted)
                    if norm in heading_names_at_levels
                ],
                "missing": missing,
                "present_at_wrong_level": wrong_level,
                "reason": None if ok
                else "required section %r is missing (as an H%s heading)%s"
                % (
                    missing[0],
                    "/H".join(str(x) for x in params.heading_levels),
                    " — found at a different heading level"
                    if missing[0] in wrong_level else "",
                ),
            },
        )
    else:
        record("required_sections", False, True, {"required": []})

    # ---- 3) code_fences ------------------------------------------------- #
    if params.required_code_fences is not None:
        ok = fence_count >= params.required_code_fences
        record(
            "code_fences",
            True,
            ok,
            {
                "code_fence_count": fence_count,
                "required_code_fences": params.required_code_fences,
                "reason": None if ok
                else "document has %d fenced code block(s); mission requires >= %d"
                % (fence_count, params.required_code_fences),
            },
        )
    else:
        record("code_fences", False, True, {"code_fence_count": fence_count})

    # ---- 4) must_link --------------------------------------------------- #
    if params.must_link:
        norm_links = [_norm_url_for_match(x) for x in links]
        # also consider the raw document text, so an unlinked-but-present URL counts
        raw_norm = _norm_url_for_match(markdown)
        missing_links: List[str] = []
        present_links: List[str] = []
        for want in params.must_link:
            nw = _norm_url_for_match(want)
            found = any(nw == nl or nw in nl or nl in nw for nl in norm_links) or (
                nw in raw_norm
            )
            (present_links if found else missing_links).append(want)
        ok = not missing_links
        record(
            "must_link",
            True,
            ok,
            {
                "required": list(params.must_link),
                "present": present_links,
                "missing": missing_links,
                "reason": None if ok
                else "required link %r is not present in the document"
                % (missing_links[0],),
            },
        )
    else:
        record("must_link", False, True, {"required": []})

    # ---- 5) no_broken_relative_links ------------------------------------ #
    # Enforced only when the check is enabled AND the document has authored
    # ``[..](target)`` links to inspect — a doc with no such links cannot have a
    # broken one, so it does not count against (or toward) the score.
    if params.check_relative_links:
        authored_targets = _all_link_targets_with_kind(markdown)
        if authored_targets:
            broken = find_broken_relative_links(markdown)
            ok = not broken
            record(
                "no_broken_relative_links",
                True,
                ok,
                {
                    "authored_link_count": len(authored_targets),
                    "broken": broken,
                    "reason": None if ok
                    else "document has %d broken/placeholder relative link(s): %s"
                    % (len(broken), ", ".join(repr(b) for b in broken[:5])),
                },
            )
        else:
            record(
                "no_broken_relative_links",
                False,
                True,
                {"applicable": False, "broken": [],
                 "note": "no authored markdown links to check"},
            )
    else:
        record("no_broken_relative_links", False, True, {"broken": []})

    # ---- 6) language (heuristic) ---------------------------------------- #
    if params.lang:
        scores = _language_scores(markdown)
        target = params.lang
        if target not in scores:
            # unknown target language: cannot run the heuristic -> do not block,
            # but mark it unenforced + explain.
            record(
                "language",
                False,
                True,
                {
                    "lang": target,
                    "supported": sorted(STOPWORDS.keys()),
                    "note": "no stop-word table for %r; language heuristic skipped"
                    % (target,),
                    "heuristic": True,
                },
            )
        else:
            target_score = scores[target]
            others = {k: v for k, v in scores.items() if k != target}
            best_other = max(others.values()) if others else 0.0
            best_other_lang = (
                max(others, key=others.get) if others else None
            )
            # pass iff the target language's stop-word density >= every other
            # language's, scaled by lang_min_ratio, AND we actually saw some
            # target stop-words (target_score > 0) on a non-trivial document.
            lead_ok = target_score >= best_other * params.lang_min_ratio
            saw_target = target_score > 0.0
            ok = bool(lead_ok and (saw_target or best_other == 0.0))
            record(
                "language",
                True,
                ok,
                {
                    "lang": target,
                    "heuristic": True,
                    "target_stopword_ratio": round(target_score, 4),
                    "best_other_lang": best_other_lang,
                    "best_other_ratio": round(best_other, 4),
                    "lang_min_ratio": params.lang_min_ratio,
                    "all_scores": {k: round(v, 4) for k, v in scores.items()},
                    "reason": None if ok
                    else "prose does not look like %r (its stop-word density %.3f "
                    "does not lead %r at %.3f) — likely not translated"
                    % (target, target_score, best_other_lang, best_other),
                },
            )
    else:
        record("language", False, True, {"lang": None})

    # ---- aggregate ------------------------------------------------------ #
    score = 1.0 if enforced == 0 else passed / enforced
    verified = (first_failure is None)
    checks["_summary"] = {
        "enforced": enforced,
        "passed": passed,
        "failed": enforced - passed,
        "score": round(score, 4),
        "first_failure": first_failure,
    }

    if verified:
        n = enforced if enforced else 0
        detail = (
            "all %d structural check%s passed (%d words, %d/%d heading sections, "
            "%d code block(s), %d link(s)) — verified"
            % (
                n,
                "" if n == 1 else "s",
                word_count,
                len(params.required_sections),
                len(params.required_sections),
                fence_count,
                len(links),
            )
        )
        if enforced == 0:
            detail = (
                "no structural checks were configured; document is non-empty "
                "(%d words) — verified" % (word_count,)
            )
    else:
        detail = str(checks[first_failure].get("reason") or first_failure)

    return VerifyResult(
        verified=verified, score=round(score, 4), detail=detail, checks=checks
    )


# --------------------------------------------------------------------------- #
# The verifier  (resolves a proof -> document -> grade)
# --------------------------------------------------------------------------- #
def verify(
    params: VerificationParams,
    proof: Any,
    *,
    fetcher: Optional[DocFetcher] = None,
) -> VerifyResult:
    """Resolve a doc-quality mission. Fetch/read the document, then grade it.

    Resolution order for the document text:
      1. inline markdown in the proof (no network),
      2. a URL in the proof (fetched via ``fetcher``),
      3. ``params.source_url`` (fetched), else ``params.repo_path`` (read local).

    :param params:  the parsed :class:`VerificationParams`.
    :param proof:   the submission proof (markdown text, a URL, or JSON; see
                    :func:`parse_proof`).
    :param fetcher: inject a :class:`DocFetcher` (or a stub in tests). If omitted,
                    a default read-only fetcher (real ``urllib``) is created.
    :returns:       a :class:`VerifyResult` (``verified``/``score``/``detail``/
                    ``checks``). A fetch failure yields ``verified=False`` with the
                    cause in ``detail`` and ``checks["_fetch"]``.
    """
    fetcher = fetcher or DocFetcher()

    # 0) locate the document.
    markdown: Optional[str] = None
    source: Optional[str] = None
    try:
        parsed = parse_proof(proof)
        if parsed.markdown is not None:
            markdown, source = parsed.markdown, "inline"
        elif parsed.url is not None:
            source = parsed.url
            markdown = fetcher.get_text(parsed.url)
    except ValueError as exc:
        # proof itself unparseable: fall back to params source if any (below);
        # else fail.
        if not (params.source_url or params.repo_path):
            return VerifyResult(
                verified=False,
                score=0.0,
                detail="invalid proof: %s" % exc,
                checks={"_proof": {"ok": False, "reason": str(exc)}},
            )
    except FetchError as exc:
        return VerifyResult(
            verified=False,
            score=0.0,
            detail="could not fetch document: %s" % exc,
            checks={"_fetch": {"ok": False, "reason": str(exc)}},
        )

    if markdown is None:
        # fall back to the mission's canonical source.
        try:
            if params.source_url:
                source = params.source_url
                markdown = fetcher.get_text(params.source_url)
            elif params.repo_path:
                source = params.repo_path
                markdown = DocFetcher.read_local(params.repo_path)
        except FetchError as exc:
            return VerifyResult(
                verified=False,
                score=0.0,
                detail="could not fetch document: %s" % exc,
                checks={"_fetch": {"ok": False, "reason": str(exc)}},
            )

    if markdown is None:
        return VerifyResult(
            verified=False,
            score=0.0,
            detail="no document located: proof carried no markdown/URL and the "
            "mission set no source_url/repo_path",
            checks={"_proof": {"ok": False, "reason": "no document"}},
        )

    if not markdown.strip():
        return VerifyResult(
            verified=False,
            score=0.0,
            detail="document is empty",
            checks={"_evidence": {"source": source, "char_count": len(markdown)},
                    "_empty": {"ok": False}},
        )

    return grade_markdown(params, markdown, source=source)


def verify_mission(
    mission: Mapping[str, Any],
    proof: Any,
    *,
    fetcher: Optional[DocFetcher] = None,
) -> VerifyResult:
    """Convenience wrapper: verify a raw OABP mission dict + a proof.

    Reads ``verification_params`` straight off the mission object so a resolver
    can pass the JSON it already has from ``GET /api/missions/{id}``.
    """
    if not isinstance(mission, Mapping):
        return VerifyResult(False, 0.0, "mission is not an object", {})
    try:
        params = VerificationParams.from_mapping(mission.get("verification_params"))
    except ValueError as exc:
        return VerifyResult(
            False, 0.0, "invalid verification_params: %s" % exc, {"error": str(exc)}
        )
    return verify(params, proof, fetcher=fetcher)


# =========================================================================== #
# Offline self-test (stubs all I/O; no network). Runs under --self-test.
# =========================================================================== #
_ACCEPT_MD = """\
# OABP SDK Guide

A friendly guide to using the protocol from Python.

## Overview

This is the overview of the project and what it does for you. It explains the
core ideas in plain English so that you can get started quickly and with
confidence. We keep the prose simple and direct.

## Installation

Install the SDK from the package index:

```bash
pip install oabp-sdk
```

## Usage

Here is how you call the API to list open missions and submit a proof.

```python
from oabp import Client

client = Client(base_url="https://cryptogenesis.duckdns.org")
for mission in client.missions():
    print(mission.id, mission.title)
```

See the [protocol home](https://cryptogenesis.duckdns.org) for more, and the
[local notes](./NOTES.md) for design rationale.

## License

This guide is released under the MIT license. Use it freely in your own work.
"""


def _self_test(verbose: bool = False) -> None:
    """Assertions proving accept/reject behaviour against stubbed I/O."""

    def say(msg: str) -> None:
        if verbose:
            print(msg)

    # ---- primitive analysers -------------------------------------------- #
    assert count_code_fences(_ACCEPT_MD) == 2, count_code_fences(_ACCEPT_MD)
    assert count_code_fences("no code here") == 0
    assert count_code_fences("```\nx\n```\n~~~\ny\n~~~") == 2
    # inline code is NOT a fence:
    assert count_code_fences("use `pip install x` inline") == 0
    # unterminated fence still counts as one block:
    assert count_code_fences("```python\nprint(1)") == 1

    # find_headings -> [(level, name), ...]; invert to name -> level for lookup.
    hs = {name: lvl for (lvl, name) in find_headings(_ACCEPT_MD)}
    assert hs.get("overview") == 2, hs
    assert "installation" in [n for (_l, n) in find_headings(_ACCEPT_MD)]
    # heading inside a fence is ignored:
    assert find_headings("```\n# not a heading\n```") == []
    # trailing colon + case-insensitive:
    assert ("api reference") in [
        n for (_l, n) in find_headings("### API Reference:")
    ]

    assert count_words("one two three") == 3
    # code body excluded by default:
    wc_excl = count_words("hello world\n```\nlots of code words here now\n```")
    assert wc_excl == 2, wc_excl
    wc_incl = count_words(
        "hello world\n```\nlots of code words here now\n```", include_code=True
    )
    assert wc_incl > wc_excl

    links = extract_links(_ACCEPT_MD)
    assert "https://cryptogenesis.duckdns.org" in links
    assert "./NOTES.md" in links
    # a real relative link must NOT be flagged broken:
    assert find_broken_relative_links("[ok](./NOTES.md)") == []
    # placeholders / empty / whitespace ARE flagged:
    assert find_broken_relative_links("[bad](#)") == ["#"]
    assert find_broken_relative_links("[bad]()") == ["<empty>"]
    assert find_broken_relative_links("[bad](path/to/file)") == ["path/to/file"]
    # a whitespace-containing relative target (angle-bracket destination form):
    assert find_broken_relative_links("[bad](<my page.md>)") == ["my page.md"]
    # absolute URLs are out of scope for the relative-link check:
    assert find_broken_relative_links("[x](https://example.com)") == []

    # ---- ACCEPT: a complete doc passes every enforced check ------------- #
    params = VerificationParams.from_mapping(
        {
            "min_words": 80,
            "required_sections": ["Overview", "Installation", "Usage", "License"],
            "required_code_fences": 2,
            "must_link": ["https://cryptogenesis.duckdns.org"],
            "lang": "en",
            "description": "English SDK guide.",
        }
    )
    r = grade_markdown(params, _ACCEPT_MD, source="inline")
    say("ACCEPT detail: " + r.detail)
    say("ACCEPT checks: " + json.dumps(r.checks["_summary"]))
    assert r.verified is True, r.detail
    assert r.score == 1.0, r.score
    assert r.checks["word_count"]["ok"] is True
    assert r.checks["required_sections"]["ok"] is True
    assert r.checks["required_sections"]["missing"] == []
    assert r.checks["code_fences"]["ok"] is True
    assert r.checks["must_link"]["ok"] is True
    assert r.checks["no_broken_relative_links"]["ok"] is True
    assert r.checks["language"]["ok"] is True
    # the breakdown enumerates each rule with pass/fail + enforced flags:
    for rule in (
        "word_count", "required_sections", "code_fences", "must_link",
        "no_broken_relative_links", "language",
    ):
        assert "ok" in r.checks[rule] and "enforced" in r.checks[rule]
    assert r.checks["_summary"]["enforced"] == 6
    assert r.checks["_summary"]["passed"] == 6
    assert bool(r) is True  # __bool__ == verified
    json.dumps(r.to_dict())  # JSON-serialisable

    # ---- REJECT: a required section is missing -------------------------- #
    md_no_license = _ACCEPT_MD.replace("## License", "## Legal Notes")
    r2 = grade_markdown(params, md_no_license, source="inline")
    say("REJECT missing-section detail: " + r2.detail)
    assert r2.verified is False
    assert r2.checks["required_sections"]["ok"] is False
    assert "License" in r2.checks["required_sections"]["missing"]
    assert "License" in r2.detail
    assert r2.score < 1.0 and r2.checks["_summary"]["failed"] >= 1

    # ---- REJECT: too few words ------------------------------------------ #
    # isolate word_count by turning the default relative-link check off, so this
    # is the ONLY enforced check -> a failure scores 0.0.
    big_min = VerificationParams.from_mapping(
        {"min_words": 100000, "check_relative_links": False}
    )
    r3 = grade_markdown(big_min, _ACCEPT_MD)
    assert r3.verified is False
    assert r3.checks["word_count"]["ok"] is False
    assert "words" in r3.detail
    assert r3.checks["_summary"]["enforced"] == 1
    assert r3.score == 0.0, r3.score
    # with the relative-link check ON (default), word_count fails but the
    # link check passes -> partial score 0.5, still verified False.
    big_min2 = VerificationParams.from_mapping({"min_words": 100000})
    r3b = grade_markdown(big_min2, _ACCEPT_MD)
    assert r3b.verified is False
    assert r3b.score == 0.5, r3b.score
    assert r3b.checks["_summary"]["enforced"] == 2

    # ---- REJECT: too few code fences ------------------------------------ #
    need_fences = VerificationParams.from_mapping({"required_code_fences": 5})
    r4 = grade_markdown(need_fences, _ACCEPT_MD)
    assert r4.verified is False
    assert r4.checks["code_fences"]["ok"] is False
    assert r4.checks["code_fences"]["code_fence_count"] == 2

    # ---- REJECT: a required link is absent ------------------------------ #
    need_link = VerificationParams.from_mapping(
        {"must_link": ["https://pypi.org/project/oabp-sdk/"]}
    )
    r5 = grade_markdown(need_link, _ACCEPT_MD)
    assert r5.verified is False
    assert r5.checks["must_link"]["ok"] is False
    assert "pypi.org/project/oabp-sdk/" in r5.detail

    # ---- must_link matches scheme-insensitively + trailing slash -------- #
    ok_link = VerificationParams.from_mapping(
        {"must_link": ["http://cryptogenesis.duckdns.org/"]}
    )
    r5b = grade_markdown(ok_link, _ACCEPT_MD)
    assert r5b.verified is True, r5b.detail

    # ---- REJECT: broken relative link ----------------------------------- #
    md_broken = _ACCEPT_MD + "\n\nSee [the appendix](path/to/file) for details.\n"
    r6 = grade_markdown(
        VerificationParams.from_mapping({"check_relative_links": True}), md_broken
    )
    assert r6.verified is False
    assert r6.checks["no_broken_relative_links"]["ok"] is False
    assert "path/to/file" in r6.checks["no_broken_relative_links"]["broken"]

    # ---- REJECT: language heuristic catches an untranslated English copy - #
    fr_params = VerificationParams.from_mapping({"lang": "fr"})
    r7 = grade_markdown(fr_params, _ACCEPT_MD)  # the doc is English
    say("REJECT wrong-language detail: " + r7.detail)
    assert r7.verified is False
    assert r7.checks["language"]["ok"] is False
    assert r7.checks["language"]["heuristic"] is True

    # ---- ACCEPT: a genuinely French doc passes the language heuristic --- #
    fr_doc = """\
# Guide du SDK OABP

Ceci est un guide en français pour utiliser le protocole depuis Python.

## Présentation

Cette section présente le projet et ce qu'il fait pour vous. Elle explique les
idées principales dans un langage simple afin que vous puissiez commencer
rapidement et avec confiance. Nous gardons le texte clair et direct pour que
chaque lecteur comprenne sans difficulté ce qui est proposé ici.

## Installation

Installez le SDK depuis l'index des paquets avec la commande suivante.

```bash
pip install oabp-sdk
```

## Utilisation

Voici comment appeler l'API pour lister les missions ouvertes et soumettre une
preuve à la plateforme.

```python
from oabp import Client
client = Client(base_url="https://cryptogenesis.duckdns.org")
```

Consultez la [page du protocole](https://cryptogenesis.duckdns.org) pour en
savoir plus sur le fonctionnement et les détails de cette intégration.
"""
    fr_full = VerificationParams.from_mapping(
        {
            "min_words": 60,
            "required_sections": ["Présentation", "Installation", "Utilisation"],
            "required_code_fences": 2,
            "must_link": ["https://cryptogenesis.duckdns.org"],
            "lang": "fr",
        }
    )
    r8 = grade_markdown(fr_full, fr_doc)
    say("ACCEPT french detail: " + r8.detail)
    assert r8.verified is True, (r8.detail, r8.checks.get("language"))
    assert r8.checks["language"]["ok"] is True

    # ---- no checks configured -> any non-empty doc verifies (score 1.0) - #
    empty_params = VerificationParams.from_mapping({})
    r9 = grade_markdown(empty_params, "Just a sentence of prose.")
    assert r9.verified is True
    assert r9.score == 1.0
    assert r9.checks["_summary"]["enforced"] == 0

    # ---- proof parsing -------------------------------------------------- #
    assert parse_proof("https://example.com/x.md").url == "https://example.com/x.md"
    assert parse_proof("# Title\n\nbody").markdown is not None
    assert parse_proof({"markdown": "# x"}).markdown == "# x"
    assert parse_proof({"url": "https://e.com/x"}).url == "https://e.com/x"
    assert parse_proof('{"url": "https://e.com/y"}').url == "https://e.com/y"
    for bad in ["", "   ", {}, {"foo": "bar"}]:
        try:
            parse_proof(bad)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected ValueError for proof %r" % (bad,))

    # ---- verify(): inline-markdown proof, no network -------------------- #
    r10 = verify(params, _ACCEPT_MD)  # markdown proof
    assert r10.verified is True, r10.detail
    assert r10.checks["_evidence"]["source"] == "inline"

    # ---- verify(): URL proof via an injected stub fetcher --------------- #
    def stub_fetch(url: str, timeout: float) -> Tuple[int, bytes]:
        routes = {
            "https://example.com/good.md": (200, _ACCEPT_MD.encode("utf-8")),
            "https://example.com/missing.md": (404, b"not found"),
        }
        return routes.get(url, (404, b""))

    fetcher = DocFetcher(fetch=stub_fetch)
    r11 = verify(params, "https://example.com/good.md", fetcher=fetcher)
    assert r11.verified is True, r11.detail
    assert r11.checks["_evidence"]["source"] == "https://example.com/good.md"

    r12 = verify(params, "https://example.com/missing.md", fetcher=fetcher)
    assert r12.verified is False
    assert "_fetch" in r12.checks
    assert "could not fetch" in r12.detail

    # ---- verify_mission(): reads params off a raw mission dict ---------- #
    mission = {
        "id": "mis_doc_demo",
        "title": "Write the OABP SDK guide",
        "verification_type": "oracle",
        "verification_params": {
            "min_words": 80,
            "required_sections": ["Overview", "Usage", "License"],
            "required_code_fences": 1,
            "must_link": ["https://cryptogenesis.duckdns.org"],
            "description": "Short English guide.",
        },
    }
    r13 = verify_mission(mission, _ACCEPT_MD)
    assert r13.verified is True, r13.detail
    mission_bad = dict(mission)
    mission_bad["verification_params"] = dict(mission["verification_params"])
    mission_bad["verification_params"]["required_code_fences"] = 9
    r14 = verify_mission(mission_bad, _ACCEPT_MD)
    assert r14.verified is False
    assert r14.checks["code_fences"]["ok"] is False

    # ---- to_dict round-trips and is JSON serialisable ------------------- #
    d = r.to_dict()
    assert set(d) == {"verified", "score", "detail", "checks"}
    json.dumps(d)

    say("all self-test assertions passed")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="doc_quality_verifier",
        description=(
            "OABP/AIGEN verifier: grade a documentation/translation deliverable "
            "against a structural quality bar (word count, required H2/H3 "
            "sections, fenced code blocks, required links, broken-relative-link "
            "check, optional language heuristic). Deterministic & explainable; "
            "grades STRUCTURE, not subjective prose quality. Pure standard "
            "library; no LLM; transport injectable."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--proof", help="Submission proof: a document URL or raw markdown.")
    p.add_argument(
        "--proof-file",
        help="Read the proof (raw markdown) from this local file instead of --proof.",
    )
    p.add_argument("--min-words", type=int, default=None, help="Minimum prose words.")
    p.add_argument(
        "--required-sections",
        default=None,
        help="Comma-separated H2/H3 section names that must be present.",
    )
    p.add_argument(
        "--required-code-fences",
        type=int,
        default=None,
        help="Minimum number of fenced code blocks.",
    )
    p.add_argument(
        "--must-link",
        action="append",
        default=None,
        help="A URL/substring that must be linked/present (repeatable).",
    )
    p.add_argument(
        "--heading-levels",
        default="2,3",
        help="Comma-separated heading levels that satisfy required-sections.",
    )
    p.add_argument(
        "--count-code-words",
        action="store_true",
        help="Include fenced-code text in the word count.",
    )
    p.add_argument(
        "--no-relative-link-check",
        action="store_true",
        help="Disable the broken/placeholder relative-link check.",
    )
    p.add_argument(
        "--lang",
        default=None,
        help="Optional target language for the (heuristic) translation check "
        "(en|fr|es|de|pt|it).",
    )
    p.add_argument(
        "--lang-min-ratio",
        type=float,
        default=1.0,
        help="How strongly the target language must lead the stop-word density.",
    )
    p.add_argument(
        "--source-url",
        default=None,
        help="Canonical document URL (used if the proof carries no doc).",
    )
    p.add_argument(
        "--repo-path",
        default=None,
        help="Local path to read the document from (used if no proof/url).",
    )
    p.add_argument(
        "--json", action="store_true", help="Print the full VerifyResult as JSON."
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help="Run the offline self-test (stubs all I/O; no network) and exit.",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    if args.self_test:
        try:
            _self_test(verbose=True)
        except AssertionError as exc:  # pragma: no cover
            sys.stderr.write("SELF-TEST FAILED: %s\n" % exc)
            return 2
        print("\ndoc-quality-verifier self-test: OK")
        return 0

    levels = [s.strip() for s in (args.heading_levels or "2,3").split(",") if s.strip()]
    try:
        params = VerificationParams.from_mapping(
            {
                "min_words": args.min_words,
                "required_sections": args.required_sections,
                "required_code_fences": args.required_code_fences,
                "must_link": args.must_link,
                "heading_levels": levels,
                "count_code_words": args.count_code_words,
                "check_relative_links": not args.no_relative_link_check,
                "lang": args.lang,
                "lang_min_ratio": args.lang_min_ratio,
                "source_url": args.source_url,
                "repo_path": args.repo_path,
            }
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2

    # determine the proof.
    proof: Any
    if args.proof_file:
        try:
            proof = DocFetcher.read_local(args.proof_file)
        except FetchError as exc:
            sys.stderr.write("ERROR: %s\n" % exc)
            return 2
    elif args.proof:
        proof = args.proof
    elif args.source_url or args.repo_path:
        proof = ""  # rely on params source; verify() falls back
    else:
        sys.stderr.write(
            "ERROR: provide --proof, --proof-file, or --source-url/--repo-path "
            "(or use --self-test).\n"
        )
        return 2

    try:
        result = verify(params, proof)
    except FetchError as exc:
        sys.stderr.write("fetch error: %s\n" % exc)
        return 3

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        head = "VERIFIED" if result.verified else "REJECTED"
        print("%s (score %.3f): %s" % (head, result.score, result.detail))
    return 0 if result.verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
