#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OABP / AIGEN oracle mission verifier: *agent published a package to PyPI*.

What this is
============
A new **oracle** mission-type verifier for the OABP / AIGEN agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``. It resolves missions whose
deliverable is "publish package **X** (optionally at version **>= V**) to PyPI".

The protocol already ships two oracle backends — **GoPlus** (token-security for
safety-review missions) and the **GitHub REST API** (repo deliverables). This
module adds a third, in the same spirit: it is **content-addressed** (anyone can
re-run it and get the same verdict from a public read-only source), **structural
only** (it never installs, imports, builds, or executes the package — it asks
PyPI's JSON API what was published), and **fail-closed** (anything it cannot
affirmatively confirm is ``verified=False`` with a human-readable reason).

It depends on the **Python standard library only** (``urllib``), so it runs in a
resolver with zero third-party packages installed.

Why a PyPI oracle is sound
--------------------------
PyPI's read-only JSON API is a public, re-runnable, content-addressed witness of
what an agent actually shipped:

* ``GET https://pypi.org/pypi/{name}/json`` — the *project* document: ``info``
  (metadata, ``version`` = latest), ``releases`` (every published version ->
  list of uploaded file objects), ``urls`` (files for the latest version).
* ``GET https://pypi.org/pypi/{name}/{version}/json`` — the *release* document
  for one exact version (``urls`` = that version's files). The verifier prefers
  this narrower endpoint when a specific version is required, and falls back to
  reading the version out of the project document's ``releases`` map.

Crucially, each uploaded file object carries an ``upload_time_iso_8601`` (and a
legacy ``upload_time``) timestamp. That lets the oracle prove the artifact was
uploaded **after the mission was created** — i.e. the package was *freshly
published for this bounty*, not an already-existing release the submitter merely
pointed at. (PyPI also forbids re-uploading a filename that already exists, so a
version cannot be silently back-dated by re-upload.)

What the verifier checks (all must hold for ``verified=True``)
--------------------------------------------------------------
Given a mission's ``verification_params`` (see schema below) and a submission
``proof`` of ``"<name>|<version>"``:

1. **PROOF PARSES** — the proof names a PyPI package and a concrete version, and
   the package name matches the one the mission asked for (PEP 503 *normalised*
   comparison: ``Foo.Bar_baz`` ≡ ``foo-bar-baz``). Optionally the normalised
   name must equal an explicit ``required_normalized_name``.
2. **PROJECT EXISTS** — ``GET /pypi/{name}/json`` returns HTTP 200 (the project
   is registered and public). A 404 ⇒ not published ⇒ reject.
3. **VERSION PRESENT** — the proof's version is a key in the project's
   ``releases`` map (or the release document for it returns 200). A version that
   is registered but yields the empty file list is still "present" structurally,
   but fails check 4.
4. **HAS A FILE** — that version has **>= 1 uploaded file** (an sdist
   ``.tar.gz`` and/or a wheel ``.whl``). A version with an empty file list is a
   *yanked-clean / registered-but-never-uploaded* shell and is rejected: nothing
   installable was actually shipped.
5. **FRESHLY PUBLISHED** — the **earliest** file ``upload_time`` for that
   version is strictly **after** the mission's ``created_at`` (minus an optional
   ``grace_seconds`` clock-skew slack). An upload that predates the mission means
   the release already existed and was not produced for this bounty ⇒ reject.
6. **MIN VERSION** *(optional)* — if ``min_version`` is set, the proof's version
   must be ``>=`` it under PEP 440 ordering (a small, dependency-free comparator
   is included; it degrades gracefully to a tuple compare on exotic strings).

Any check that does not affirmatively pass yields ``verified=False`` and a
``detail`` saying which one and why. The full structured trace is returned in
``VerifyResult.evidence`` so a creator/auditor can see exactly what PyPI reported.

The proof format
----------------
``proof = "<package-name>|<version>"`` — e.g. ``"oabp-sdk|0.3.1"``. The pipe is
used (not a bare ``name==version``) so the proof is unambiguous and trivial to
parse. ``name==version`` (pip-style) and a JSON ``{"name":..,"version":..}`` are
also accepted for convenience; all normalise to the same ``(name, version)``.

verification_params schema
==========================
The mission's ``verification_params`` object (the ``oracle`` arm of the protocol)
for this mission-type is::

    {
      # REQUIRED — the PyPI project that must be published.
      "package_name": "oabp-sdk",         # str; PEP 503 normalised before compare

      # OPTIONAL — tighten the match / freshness window.
      "min_version": "0.3.0",             # str|null; proof version must be >= this (PEP 440)
      "required_normalized_name":         # str|null; if set, normalised proof name must == this
          "oabp-sdk",
      "require_sdist": false,             # bool; if true, >=1 file must be an sdist (.tar.gz)
      "require_wheel": false,             # bool; if true, >=1 file must be a wheel (.whl)
      "grace_seconds": 0,                 # int; clock-skew slack subtracted from created_at
                                          #      when enforcing "upload after creation"

      # OPTIONAL — but STRONGLY recommended; this is what makes the bounty
      # "freshly published". When omitted, the verifier falls back to the
      # mission's own created_at / deadline passed alongside (see verify()).
      "created_at": 1717286400,           # int (unix); the upload must be AFTER this

      # human-readable spec; surfaced to solvers, not parsed by the oracle.
      "oracle_description":
          "Publish package 'oabp-sdk' (>=0.3.0) to PyPI with at least one wheel."
    }

Only ``package_name`` is mandatory. ``oracle_description`` is free text for
humans/solvers; the machine truth is the typed fields above.

Worked example
==============
Mission (created at unix ``1_717_286_400`` = 2024-06-02T00:00:00Z)::

    verification_params = {
        "package_name": "oabp-sdk",
        "min_version": "0.3.0",
        "require_wheel": True,
        "created_at": 1717286400,
        "oracle_description":
            "Publish 'oabp-sdk' >=0.3.0 to PyPI with at least one wheel.",
    }

An agent publishes ``oabp-sdk 0.3.1`` (an sdist + a wheel) at
``2024-06-02T09:15:00Z`` and submits ``proof = "oabp-sdk|0.3.1"``. The verifier:

* parses the proof -> ``("oabp-sdk", "0.3.1")``; normalised name matches; ✓
* ``GET /pypi/oabp-sdk/0.3.1/json`` -> 200, two files (``.tar.gz`` + ``.whl``); ✓
* a wheel is present (``require_wheel`` satisfied); ✓
* earliest upload ``2024-06-02T09:15:00Z`` > ``created_at`` -> fresh; ✓
* ``0.3.1 >= 0.3.0`` under PEP 440; ✓

=> ``VerifyResult(verified=True, detail="oabp-sdk 0.3.1 published to PyPI …",
evidence={...})``. Had the agent only registered ``0.3.1`` with no files, or
uploaded it *before* ``created_at``, or submitted ``0.2.9 < min_version``, the
result would be ``verified=False`` with the corresponding reason.

CLI
===
    # verify a live submission against the live PyPI:
    python3 pypi_publish_verifier.py \
        --package-name oabp-sdk --min-version 0.3.0 \
        --created-at 1717286400 --proof "oabp-sdk|0.3.1"

    # run the bundled OFFLINE self-test (stubs PyPI; no network) and exit:
    python3 pypi_publish_verifier.py --self-test

Exit codes (CLI):
* ``0`` — verified True (or, under --self-test, all assertions passed).
* ``1`` — verified False (the submission does not satisfy the mission).
* ``2`` — usage / configuration error.
* ``3`` — a PyPI / network error prevented a verdict.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

__all__ = [
    "VerifyResult",
    "VerificationParams",
    "PyPIClient",
    "PyPIError",
    "verify",
    "verify_mission",
    "normalize_name",
    "parse_proof",
    "parse_version",
    "compare_versions",
    "DEFAULT_PYPI_BASE",
]

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_PYPI_BASE = "https://pypi.org"
HTTP_TIMEOUT = 20.0
USER_AGENT = "oabp-pypi-publish-verifier/1.0 (+https://cryptogenesis.duckdns.org)"

# File-type detection (PyPI's own packagetype, with a filename-suffix fallback).
_SDIST_SUFFIXES = (".tar.gz", ".zip", ".tar.bz2")
_WHEEL_SUFFIXES = (".whl",)


# --------------------------------------------------------------------------- #
# Result + params dataclasses
# --------------------------------------------------------------------------- #
@dataclass
class VerifyResult:
    """Typed outcome of an oracle verification.

    Attributes
    ----------
    verified:
        ``True`` only if every required check passed. The protocol pays the
        bounty iff this is ``True``.
    detail:
        Human-readable one-line explanation (the accept reason, or the FIRST
        failing check and why). Safe to log / surface to the creator.
    evidence:
        Structured, content-addressed trace of what PyPI reported and which
        checks ran. Lets anyone re-derive the verdict without re-querying.
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
class VerificationParams:
    """Parsed, validated view of a PyPI-publish mission's ``verification_params``.

    See the module docstring for the JSON schema. ``from_mapping`` is tolerant:
    unknown keys are ignored, wrong-typed optionals fall back to their defaults,
    and only ``package_name`` is mandatory.
    """

    package_name: str
    min_version: Optional[str] = None
    required_normalized_name: Optional[str] = None
    require_sdist: bool = False
    require_wheel: bool = False
    grace_seconds: int = 0
    created_at: Optional[int] = None
    oracle_description: Optional[str] = None

    @classmethod
    def from_mapping(
        cls, data: Optional[Mapping[str, Any]]
    ) -> "VerificationParams":
        if not isinstance(data, Mapping):
            raise ValueError("verification_params must be an object")
        name = data.get("package_name") or data.get("package") or data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                "verification_params.package_name is required and must be a "
                "non-empty string"
            )

        def _opt_str(*keys: str) -> Optional[str]:
            for k in keys:
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return None

        def _bool(key: str, default: bool = False) -> bool:
            v = data.get(key, default)
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() in ("1", "true", "yes", "on")
            if isinstance(v, (int, float)):
                return bool(v)
            return default

        def _int(key: str, default: int = 0) -> int:
            v = data.get(key, default)
            try:
                return int(v)
            except (TypeError, ValueError):
                return default

        created = data.get("created_at")
        created_int: Optional[int]
        try:
            created_int = int(created) if created is not None else None
        except (TypeError, ValueError):
            created_int = None

        return cls(
            package_name=name.strip(),
            min_version=_opt_str("min_version", "minimum_version"),
            required_normalized_name=_opt_str(
                "required_normalized_name", "normalized_name"
            ),
            require_sdist=_bool("require_sdist"),
            require_wheel=_bool("require_wheel"),
            grace_seconds=max(0, _int("grace_seconds", 0)),
            created_at=created_int,
            oracle_description=_opt_str("oracle_description"),
        )


# --------------------------------------------------------------------------- #
# PEP 503 name normalisation
# --------------------------------------------------------------------------- #
_NORMALIZE_RE = re.compile(r"[-_.]+")


def normalize_name(name: str) -> str:
    """PEP 503 normalised project name: lowercase, runs of ``-_.`` -> single ``-``.

    ``Foo.Bar_baz`` -> ``foo-bar-baz``. This is exactly how PyPI compares
    project names, so name matching here is faithful to the index.
    """
    return _NORMALIZE_RE.sub("-", (name or "").strip()).lower()


# --------------------------------------------------------------------------- #
# Proof parsing ("name|version", "name==version", or JSON)
# --------------------------------------------------------------------------- #
def parse_proof(proof: Any) -> Tuple[str, str]:
    """Parse a submission proof into ``(package_name, version)``.

    Accepted forms (in priority order):
      * ``"name|version"``                     (canonical)
      * ``'{"name": "...", "version": "..."}'`` (JSON object, or a dict already)
      * ``"name==version"``                    (pip pin style)
      * ``"name version"`` / ``"name@version"`` (whitespace / ``@`` separated)
      * a bare PyPI release URL ``https://pypi.org/project/<name>/<version>/``

    Raises ``ValueError`` if no ``(name, version)`` pair can be extracted.
    """
    # Already a mapping (e.g. proof posted as structured JSON).
    if isinstance(proof, Mapping):
        name = proof.get("name") or proof.get("package") or proof.get("package_name")
        version = proof.get("version")
        if isinstance(name, str) and isinstance(version, str) and name and version:
            return name.strip(), version.strip()
        raise ValueError("proof object must carry non-empty 'name' and 'version'")

    if not isinstance(proof, str) or not proof.strip():
        raise ValueError("proof must be a non-empty string of the form 'name|version'")
    s = proof.strip()

    # JSON object string.
    if s.startswith("{"):
        try:
            obj = json.loads(s)
        except ValueError:
            obj = None
        if isinstance(obj, Mapping):
            return parse_proof(obj)

    # PyPI project URL: .../project/<name>/<version>/
    m = re.match(
        r"^(?:https?://)?(?:www\.)?pypi\.org/project/([^/\s]+)/([^/\s]+)/?$", s
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Canonical pipe form.
    if "|" in s:
        name, _, version = s.partition("|")
        name, version = name.strip(), version.strip()
        if name and version:
            return name, version

    # pip pin: name==version
    if "==" in s:
        name, _, version = s.partition("==")
        name, version = name.strip(), version.strip()
        if name and version:
            return name, version

    # name@version
    if "@" in s:
        name, _, version = s.partition("@")
        name, version = name.strip(), version.strip()
        if name and version:
            return name, version

    # whitespace separated: "name version"
    parts = s.split()
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0].strip(), parts[1].strip()

    raise ValueError(
        "could not parse proof %r into (name, version); expected 'name|version'"
        % (proof,)
    )


# --------------------------------------------------------------------------- #
# Minimal PEP 440-ish version parse + compare (stdlib only, no `packaging`)
# --------------------------------------------------------------------------- #
_VERSION_RE = re.compile(
    r"^\s*v?"
    r"(?:(?P<epoch>[0-9]+)!)?"
    r"(?P<release>[0-9]+(?:\.[0-9]+)*)"
    r"(?P<pre>[-_.]?(?:a|b|c|rc|alpha|beta|pre|preview)[-_.]?[0-9]*)?"
    r"(?P<post>[-_.]?(?:post|rev|r)[-_.]?[0-9]*|-[0-9]+)?"
    r"(?P<dev>[-_.]?dev[-_.]?[0-9]*)?"
    r"(?:\+[a-z0-9]+(?:[-_.][a-z0-9]+)*)?"  # local segment (ignored for ordering)
    r"\s*$",
    re.IGNORECASE,
)

# Pre-release labels -> canonical, with a sort rank below the final release.
_PRE_NORMALIZE = {"alpha": "a", "beta": "b", "c": "rc", "pre": "rc", "preview": "rc"}
_PRE_RANK = {"a": 0, "b": 1, "rc": 2}


def _num_suffix(token: Optional[str]) -> int:
    if not token:
        return 0
    m = re.search(r"[0-9]+", token)
    return int(m.group(0)) if m else 0


def parse_version(version: str) -> Tuple[bool, tuple]:
    """Parse ``version`` into a sortable key.

    Returns ``(strict, key)`` where ``strict`` is ``True`` if the string parsed
    as a PEP 440 version (so the key is meaningful for ordering), or ``False``
    when it did not — in which case ``key`` is a best-effort fallback and callers
    should treat comparisons as approximate.

    The key models the important ordering rules: epoch, then numeric release
    tuple, then pre-release < final < post-release, with dev releases sorting
    *below* everything at the same release.
    """
    if not isinstance(version, str) or not version.strip():
        return False, (0, (0,), 5, 0, 0, 0)

    m = _VERSION_RE.match(version)
    if not m:
        # Fallback: split leading numeric dotted groups; flag as non-strict.
        nums = re.findall(r"[0-9]+", version)
        release = tuple(int(n) for n in nums) if nums else (0,)
        return False, (0, release, 4, 0, 0, 0)

    epoch = int(m.group("epoch") or 0)
    release = tuple(int(p) for p in m.group("release").split("."))

    pre = m.group("pre")
    post = m.group("post")
    dev = m.group("dev")

    # phase ordering at a given release:
    #   dev-only (no pre/post) ...... 0  (lowest)
    #   pre-release ................. 1
    #   final ....................... 4
    #   post-release ................ 5
    if pre:
        label = re.search(r"[a-z]+", pre, re.IGNORECASE)
        lab = (label.group(0).lower() if label else "rc")
        lab = _PRE_NORMALIZE.get(lab, lab)
        pre_rank = _PRE_RANK.get(lab, 2)
        phase = 1
        pre_num = _num_suffix(pre)
    else:
        phase = 4
        pre_rank = 0
        pre_num = 0

    post_num = _num_suffix(post) if post else 0
    if post:
        phase = 5

    if dev:
        dev_num = _num_suffix(dev)
        # a dev release sorts below the corresponding phase
        phase = phase - 1 if phase > 0 else 0
        has_dev = 0  # dev present sorts before "no dev" at same phase
    else:
        dev_num = 0
        has_dev = 1

    key = (epoch, release, phase, pre_rank, pre_num, post_num, has_dev, dev_num)
    return True, key


def compare_versions(a: str, b: str) -> int:
    """Return -1/0/1 for ``a`` <, ==, > ``b`` under (approximate) PEP 440 order.

    Pure stdlib. Pads the release tuples so ``1.2`` == ``1.2.0``. When either
    string is non-strict the comparison is best-effort (numeric release tuple),
    which is sufficient for the ``min_version`` gate on normal version strings.
    """
    _, ka = parse_version(a)
    _, kb = parse_version(b)

    # Compare epoch.
    if ka[0] != kb[0]:
        return -1 if ka[0] < kb[0] else 1
    # Compare release tuples, zero-padded to equal length.
    ra, rb = ka[1], kb[1]
    n = max(len(ra), len(rb))
    ra = ra + (0,) * (n - len(ra))
    rb = rb + (0,) * (n - len(rb))
    if ra != rb:
        return -1 if ra < rb else 1
    # Compare the rest of the key (phase, pre, post, dev …).
    rest_a, rest_b = ka[2:], kb[2:]
    if rest_a != rest_b:
        return -1 if rest_a < rest_b else 1
    return 0


# --------------------------------------------------------------------------- #
# upload_time parsing
# --------------------------------------------------------------------------- #
def _parse_upload_time(file_obj: Mapping[str, Any]) -> Optional[int]:
    """Best-effort unix-seconds for a PyPI file's upload time.

    Prefers ``upload_time_iso_8601`` (e.g. ``2024-06-02T09:15:00.123456Z``),
    falls back to the legacy naive ``upload_time`` (``2024-06-02T09:15:00``,
    treated as UTC, which is what PyPI uses). Returns ``None`` if neither parses.
    """
    iso = file_obj.get("upload_time_iso_8601")
    if isinstance(iso, str) and iso:
        ts = _iso_to_unix(iso)
        if ts is not None:
            return ts
    legacy = file_obj.get("upload_time")
    if isinstance(legacy, str) and legacy:
        ts = _iso_to_unix(legacy)
        if ts is not None:
            return ts
    return None


def _iso_to_unix(value: str) -> Optional[int]:
    s = value.strip()
    # Normalise trailing 'Z' to an explicit UTC offset for fromisoformat.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    # datetime.fromisoformat (3.7+) accepts microseconds and +HH:MM offsets.
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # last resort: a few explicit formats
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(value.strip().rstrip("Z"), fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)  # PyPI legacy times are UTC
    return int(dt.timestamp())


# --------------------------------------------------------------------------- #
# PyPI JSON client (stdlib urllib)
# --------------------------------------------------------------------------- #
class PyPIError(Exception):
    """A network / transport / decode failure talking to the PyPI JSON API.

    Distinct from "the package/version is simply absent" (which the verifier
    represents as ``verified=False``, not an exception): this is reserved for
    *infrastructure* failures that prevented reaching a verdict at all.
    """


class PyPIClient:
    """Read-only client for the PyPI JSON API (``/pypi/{name}[/{version}]/json``).

    stdlib ``urllib`` only. A 404 is returned to the caller as ``None`` (the
    project/version does not exist) rather than raised — only genuine transport
    or unexpected-status failures raise :class:`PyPIError`.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_PYPI_BASE,
        *,
        timeout: float = HTTP_TIMEOUT,
        opener: Optional[Callable[[urllib.request.Request, float], Any]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)
        # ``opener`` lets tests inject a fake transport with the signature
        # ``(request, timeout) -> (status:int, body:bytes)``.
        self._opener = opener

    # -- low level --------------------------------------------------------- #
    def _get_json(self, path: str) -> Optional[Any]:
        url = self.base_url + path
        req = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            method="GET",
        )
        if self._opener is not None:
            try:
                status, body = self._opener(req, self.timeout)
            except Exception as exc:  # pragma: no cover - injected transport
                raise PyPIError("GET %s failed: %s" % (url, exc)) from exc
            return self._decode(url, status, body)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.getcode()
                body = resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise PyPIError(
                "GET %s -> HTTP %s %s" % (url, exc.code, exc.reason)
            ) from exc
        except urllib.error.URLError as exc:
            raise PyPIError("GET %s failed: %s" % (url, exc.reason)) from exc
        except (TimeoutError, OSError) as exc:  # pragma: no cover - env dependent
            raise PyPIError("GET %s failed: %s" % (url, exc)) from exc
        return self._decode(url, status, body)

    @staticmethod
    def _decode(url: str, status: int, body: bytes) -> Optional[Any]:
        if status == 404:
            return None
        if status != 200:
            raise PyPIError("GET %s -> HTTP %s" % (url, status))
        try:
            return json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise PyPIError("GET %s -> non-JSON body: %s" % (url, exc)) from exc

    # -- endpoints --------------------------------------------------------- #
    def get_project(self, name: str) -> Optional[Dict[str, Any]]:
        """``GET /pypi/{name}/json`` -> project doc, or ``None`` if 404."""
        data = self._get_json("/pypi/%s/json" % name)
        return data if isinstance(data, dict) else None

    def get_release(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        """``GET /pypi/{name}/{version}/json`` -> release doc, or ``None`` if 404."""
        data = self._get_json("/pypi/%s/%s/json" % (name, version))
        return data if isinstance(data, dict) else None


# --------------------------------------------------------------------------- #
# File classification helpers
# --------------------------------------------------------------------------- #
def _file_kind(file_obj: Mapping[str, Any]) -> str:
    """Return 'sdist' | 'wheel' | 'other' for a PyPI file object.

    Prefers PyPI's own ``packagetype`` ('sdist' / 'bdist_wheel'); falls back to
    the filename suffix when that field is absent.
    """
    ptype = str(file_obj.get("packagetype") or "").lower()
    if ptype == "sdist":
        return "sdist"
    if ptype in ("bdist_wheel", "wheel"):
        return "wheel"
    fname = str(file_obj.get("filename") or "").lower()
    if fname.endswith(_WHEEL_SUFFIXES):
        return "wheel"
    if fname.endswith(_SDIST_SUFFIXES):
        return "sdist"
    return "other"


def _summarize_files(files: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Compact, JSON-safe summary of a version's uploaded files for evidence."""
    summary: List[Dict[str, Any]] = []
    earliest: Optional[int] = None
    kinds = {"sdist": 0, "wheel": 0, "other": 0}
    for f in files:
        if not isinstance(f, Mapping):
            continue
        kind = _file_kind(f)
        kinds[kind] = kinds.get(kind, 0) + 1
        ts = _parse_upload_time(f)
        if ts is not None and (earliest is None or ts < earliest):
            earliest = ts
        summary.append(
            {
                "filename": f.get("filename"),
                "packagetype": f.get("packagetype"),
                "kind": kind,
                "upload_time_iso_8601": f.get("upload_time_iso_8601")
                or f.get("upload_time"),
                "yanked": bool(f.get("yanked", False)),
            }
        )
    return {
        "count": len(summary),
        "kinds": kinds,
        "earliest_upload_unix": earliest,
        "files": summary,
    }


def _iso(ts: Optional[int]) -> Optional[str]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# The oracle
# --------------------------------------------------------------------------- #
def verify(
    params: VerificationParams,
    proof: Any,
    *,
    mission_created_at: Optional[int] = None,
    client: Optional[PyPIClient] = None,
) -> VerifyResult:
    """Resolve a PyPI-publish mission. Structural-only; fail-closed.

    :param params:  the parsed :class:`VerificationParams` for the mission.
    :param proof:   the submission proof (``"name|version"`` etc; see
                    :func:`parse_proof`).
    :param mission_created_at: unix seconds the mission was created. Used for the
                    freshness check when ``params.created_at`` is not set. If both
                    are ``None``, the freshness check is **skipped** and the
                    evidence records that it could not be enforced (the verifier
                    still verifies existence + version + file + min_version).
    :param client:  inject a :class:`PyPIClient` (or a stub in tests).
    :returns:       a :class:`VerifyResult` (``verified``/``detail``/``evidence``).
    """
    client = client or PyPIClient()
    created_at = params.created_at if params.created_at is not None else mission_created_at

    evidence: Dict[str, Any] = {
        "verifier": "pypi_publish",
        "params": {
            "package_name": params.package_name,
            "normalized_package_name": normalize_name(params.package_name),
            "min_version": params.min_version,
            "required_normalized_name": params.required_normalized_name,
            "require_sdist": params.require_sdist,
            "require_wheel": params.require_wheel,
            "grace_seconds": params.grace_seconds,
        },
        "created_at_unix": created_at,
        "created_at_iso": _iso(created_at),
        "checks": {},
    }
    checks: Dict[str, Any] = evidence["checks"]

    def reject(detail: str) -> VerifyResult:
        return VerifyResult(verified=False, detail=detail, evidence=evidence)

    # --- 0) PARSE PROOF --------------------------------------------------- #
    try:
        proof_name, proof_version = parse_proof(proof)
    except ValueError as exc:
        checks["proof_parsed"] = {"ok": False, "reason": str(exc)}
        return reject("invalid proof: %s" % exc)
    evidence["proof"] = {"raw": proof, "name": proof_name, "version": proof_version}
    checks["proof_parsed"] = {"ok": True}

    # --- 1) NAME MATCHES MISSION ----------------------------------------- #
    norm_proof = normalize_name(proof_name)
    norm_wanted = normalize_name(params.package_name)
    name_ok = norm_proof == norm_wanted
    checks["name_matches"] = {
        "ok": name_ok,
        "proof_normalized": norm_proof,
        "wanted_normalized": norm_wanted,
    }
    if not name_ok:
        return reject(
            "proof package %r (normalised %r) does not match mission package "
            "%r (normalised %r)"
            % (proof_name, norm_proof, params.package_name, norm_wanted)
        )
    if params.required_normalized_name is not None:
        req_norm = normalize_name(params.required_normalized_name)
        req_ok = norm_proof == req_norm
        checks["required_normalized_name"] = {
            "ok": req_ok,
            "expected": req_norm,
            "actual": norm_proof,
        }
        if not req_ok:
            return reject(
                "normalised package name %r != required %r"
                % (norm_proof, req_norm)
            )

    # --- 1b) MIN VERSION (cheap, do before any network if it already fails) #
    if params.min_version is not None:
        cmp = compare_versions(proof_version, params.min_version)
        min_ok = cmp >= 0
        checks["min_version"] = {
            "ok": min_ok,
            "proof_version": proof_version,
            "min_version": params.min_version,
            "compare": cmp,
        }
        if not min_ok:
            return reject(
                "version %s is below the mission minimum %s"
                % (proof_version, params.min_version)
            )

    # --- 2) PROJECT EXISTS ------------------------------------------------ #
    try:
        project = client.get_project(proof_name)
    except PyPIError as exc:
        checks["project_exists"] = {"ok": False, "error": str(exc)}
        # Infra error -> not a verdict; surface as not-verified with the cause.
        return reject("could not query PyPI for %r: %s" % (proof_name, exc))

    if project is None:
        checks["project_exists"] = {"ok": False, "reason": "404 / not on PyPI"}
        return reject(
            "package %r is not published on PyPI (project JSON 404)" % proof_name
        )
    checks["project_exists"] = {"ok": True}
    info = project.get("info") if isinstance(project.get("info"), Mapping) else {}
    evidence["pypi_info"] = {
        "name": info.get("name"),
        "latest_version": info.get("version"),
        "summary": info.get("summary"),
    }

    # --- 3) VERSION PRESENT + 4) HAS A FILE ------------------------------- #
    releases = project.get("releases")
    files: List[Mapping[str, Any]] = []
    version_present = False

    if isinstance(releases, Mapping) and proof_version in releases:
        version_present = True
        rel_files = releases.get(proof_version)
        if isinstance(rel_files, list):
            files = [f for f in rel_files if isinstance(f, Mapping)]

    # If the project doc didn't list the version (or listed it with no files),
    # confirm via the narrower release endpoint — authoritative for one version.
    if not version_present or not files:
        try:
            rel_doc = client.get_release(proof_name, proof_version)
        except PyPIError as exc:
            # We already have the project doc; treat a release-endpoint infra
            # error as non-fatal and rely on what releases[] told us.
            rel_doc = None
            checks.setdefault("release_endpoint", {})["error"] = str(exc)
        if rel_doc is not None:
            version_present = True
            urls = rel_doc.get("urls")
            if isinstance(urls, list):
                rel_files2 = [f for f in urls if isinstance(f, Mapping)]
                if rel_files2:
                    files = rel_files2

    checks["version_present"] = {"ok": version_present, "version": proof_version}
    if not version_present:
        avail = (
            sorted(releases.keys())[-10:] if isinstance(releases, Mapping) else []
        )
        evidence["available_versions_sample"] = avail
        return reject(
            "version %s of %s is not present on PyPI" % (proof_version, proof_name)
        )

    file_summary = _summarize_files(files)
    evidence["release_files"] = file_summary
    has_file = file_summary["count"] >= 1
    checks["has_file"] = {"ok": has_file, "file_count": file_summary["count"]}
    if not has_file:
        return reject(
            "version %s of %s is registered but has no uploaded files "
            "(nothing installable was published)" % (proof_version, proof_name)
        )

    # Optional sdist / wheel requirements.
    if params.require_sdist:
        ok_sd = file_summary["kinds"].get("sdist", 0) >= 1
        checks["require_sdist"] = {"ok": ok_sd}
        if not ok_sd:
            return reject(
                "mission requires an sdist (.tar.gz) but %s %s has none"
                % (proof_name, proof_version)
            )
    if params.require_wheel:
        ok_wh = file_summary["kinds"].get("wheel", 0) >= 1
        checks["require_wheel"] = {"ok": ok_wh}
        if not ok_wh:
            return reject(
                "mission requires a wheel (.whl) but %s %s has none"
                % (proof_name, proof_version)
            )

    # --- 5) FRESHLY PUBLISHED (upload after mission creation) ------------- #
    earliest = file_summary["earliest_upload_unix"]
    if created_at is None:
        checks["fresh_after_creation"] = {
            "ok": True,
            "enforced": False,
            "reason": "no mission created_at provided; freshness not enforced",
        }
    elif earliest is None:
        # Files exist but carry no parseable timestamp: cannot prove freshness.
        checks["fresh_after_creation"] = {
            "ok": False,
            "enforced": True,
            "reason": "no parseable upload_time on any file",
        }
        return reject(
            "could not determine upload time for %s %s; cannot confirm it was "
            "freshly published" % (proof_name, proof_version)
        )
    else:
        threshold = created_at - max(0, params.grace_seconds)
        fresh = earliest > threshold
        checks["fresh_after_creation"] = {
            "ok": fresh,
            "enforced": True,
            "earliest_upload_unix": earliest,
            "earliest_upload_iso": _iso(earliest),
            "threshold_unix": threshold,
            "threshold_iso": _iso(threshold),
            "grace_seconds": params.grace_seconds,
        }
        if not fresh:
            return reject(
                "version %s of %s was uploaded at %s, which is NOT after the "
                "mission creation time %s — it was not freshly published for "
                "this bounty"
                % (
                    proof_version,
                    proof_name,
                    _iso(earliest),
                    _iso(created_at),
                )
            )

    # --- ALL CHECKS PASSED ------------------------------------------------ #
    kinds = file_summary["kinds"]
    kind_str = ", ".join(
        "%dx %s" % (n, k) for k, n in kinds.items() if n
    ) or "%d file(s)" % file_summary["count"]
    detail = (
        "%s %s published to PyPI (%s)%s%s — verified"
        % (
            proof_name,
            proof_version,
            kind_str,
            (
                " uploaded %s" % _iso(earliest)
                if earliest is not None
                else ""
            ),
            (
                " > created %s" % _iso(created_at)
                if created_at is not None and earliest is not None
                else ""
            ),
        )
    )
    return VerifyResult(verified=True, detail=detail, evidence=evidence)


def verify_mission(
    mission: Mapping[str, Any],
    proof: Any,
    *,
    client: Optional[PyPIClient] = None,
) -> VerifyResult:
    """Convenience wrapper: verify a raw OABP mission dict + a proof.

    Reads ``verification_params`` and the mission's ``created_at`` (falling back
    to ``created`` / ``created_unix`` / ``created_at_unix``) straight off the
    mission object, so a resolver can pass the JSON it already has.
    """
    if not isinstance(mission, Mapping):
        return VerifyResult(False, "mission is not an object", {})
    try:
        params = VerificationParams.from_mapping(mission.get("verification_params"))
    except ValueError as exc:
        return VerifyResult(
            False,
            "invalid verification_params: %s" % exc,
            {"error": str(exc)},
        )

    created_at = None
    for key in ("created_at", "created", "created_unix", "created_at_unix"):
        v = mission.get(key)
        if v is not None:
            try:
                created_at = int(v)
                break
            except (TypeError, ValueError):
                continue

    return verify(params, proof, mission_created_at=created_at, client=client)


# =========================================================================== #
# Offline self-test (stubs PyPI; no network). Runs under --self-test.
# =========================================================================== #
def _fixture_opener(routes: Dict[str, Tuple[int, Any]]):
    """Build a ``PyPIClient`` opener returning canned ``(status, body)`` per path.

    ``routes`` maps a URL *suffix* (e.g. ``/pypi/oabp-sdk/json``) to
    ``(status_code, json_obj_or_bytes)``. Longest matching suffix wins.
    """

    def opener(req: urllib.request.Request, timeout: float):
        url = req.full_url
        best: Optional[str] = None
        for suffix in routes:
            if url.endswith(suffix) and (best is None or len(suffix) > len(best)):
                best = suffix
        if best is None:
            return 404, b"{}"
        status, payload = routes[best]
        body = payload if isinstance(payload, (bytes, bytearray)) else json.dumps(
            payload
        ).encode("utf-8")
        return status, body

    return opener


def _file(filename: str, packagetype: str, iso: str, yanked: bool = False):
    return {
        "filename": filename,
        "packagetype": packagetype,
        "upload_time_iso_8601": iso,
        "upload_time": iso.replace("Z", "").split(".")[0],
        "yanked": yanked,
    }


def _self_test(verbose: bool = False) -> None:
    """Assertions proving accept/reject behaviour against a stubbed PyPI."""

    def say(msg: str) -> None:
        if verbose:
            print(msg)

    # ---- name normalisation (PEP 503) ----------------------------------- #
    assert normalize_name("Foo.Bar_baz") == "foo-bar-baz"
    assert normalize_name("OABP__SDK") == "oabp-sdk"
    assert normalize_name("a---b...c") == "a-b-c"

    # ---- proof parsing -------------------------------------------------- #
    assert parse_proof("oabp-sdk|0.3.1") == ("oabp-sdk", "0.3.1")
    assert parse_proof("oabp-sdk==0.3.1") == ("oabp-sdk", "0.3.1")
    assert parse_proof("oabp-sdk@0.3.1") == ("oabp-sdk", "0.3.1")
    assert parse_proof("oabp-sdk 0.3.1") == ("oabp-sdk", "0.3.1")
    assert parse_proof('{"name": "oabp-sdk", "version": "0.3.1"}') == (
        "oabp-sdk",
        "0.3.1",
    )
    assert parse_proof("https://pypi.org/project/oabp-sdk/0.3.1/") == (
        "oabp-sdk",
        "0.3.1",
    )
    for bad in ["", "noversion", "|0.1", "name|", "   "]:
        try:
            parse_proof(bad)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected ValueError for proof %r" % bad)

    # ---- version comparison (PEP 440-ish) ------------------------------- #
    assert compare_versions("0.3.1", "0.3.0") == 1
    assert compare_versions("0.3.0", "0.3.0") == 0
    assert compare_versions("0.2.9", "0.3.0") == -1
    assert compare_versions("1.2", "1.2.0") == 0
    assert compare_versions("1.0.0", "1.0.0rc1") == 1       # final > pre-release
    assert compare_versions("1.0.0rc1", "1.0.0") == -1
    assert compare_versions("1.0.0", "1.0.0.post1") == -1   # post > final
    assert compare_versions("2.0.0", "1.9.9") == 1
    assert compare_versions("1.10.0", "1.9.0") == 1         # numeric, not lexical

    CREATED = _iso_to_unix("2024-06-02T00:00:00Z")  # mission creation
    assert CREATED is not None

    params = VerificationParams.from_mapping(
        {
            "package_name": "oabp-sdk",
            "min_version": "0.3.0",
            "created_at": CREATED,
            "oracle_description": "Publish oabp-sdk >=0.3.0 to PyPI.",
        }
    )

    # ---- ACCEPT: existing name + version + file, uploaded AFTER creation - #
    accept_routes = {
        "/pypi/oabp-sdk/json": (
            200,
            {
                "info": {"name": "oabp-sdk", "version": "0.3.1", "summary": "OABP SDK"},
                "releases": {
                    "0.3.0": [
                        _file(
                            "oabp_sdk-0.3.0.tar.gz",
                            "sdist",
                            "2024-05-01T10:00:00Z",  # pre-creation (old release)
                        )
                    ],
                    "0.3.1": [
                        _file(
                            "oabp_sdk-0.3.1.tar.gz",
                            "sdist",
                            "2024-06-02T09:15:00Z",
                        ),
                        _file(
                            "oabp_sdk-0.3.1-py3-none-any.whl",
                            "bdist_wheel",
                            "2024-06-02T09:15:30Z",
                        ),
                    ],
                },
            },
        ),
    }
    client = PyPIClient(opener=_fixture_opener(accept_routes))
    r = verify(params, "oabp-sdk|0.3.1", client=client)
    say("ACCEPT detail: " + r.detail)
    assert r.verified is True, r.detail
    assert r.evidence["checks"]["has_file"]["ok"] is True
    assert r.evidence["checks"]["fresh_after_creation"]["ok"] is True
    assert r.evidence["release_files"]["count"] == 2
    assert r.evidence["release_files"]["kinds"]["wheel"] == 1
    # The dataclass carries the evidence dict.
    assert isinstance(r, VerifyResult) and isinstance(r.evidence, dict)
    assert bool(r) is True  # __bool__ == verified

    # ACCEPT also when require_wheel is set (a wheel is present).
    params_wheel = VerificationParams.from_mapping(
        {"package_name": "oabp-sdk", "created_at": CREATED, "require_wheel": True}
    )
    r_wheel = verify(params_wheel, "oabp-sdk|0.3.1", client=client)
    assert r_wheel.verified is True, r_wheel.detail

    # ---- REJECT: missing version --------------------------------------- #
    r_missing_ver = verify(params, "oabp-sdk|9.9.9", client=client)
    say("REJECT missing-version detail: " + r_missing_ver.detail)
    assert r_missing_ver.verified is False
    assert "not present" in r_missing_ver.detail
    assert r_missing_ver.evidence["checks"]["version_present"]["ok"] is False

    # ---- REJECT: fileless release (registered, zero files) -------------- #
    fileless_routes = {
        "/pypi/ghostpkg/json": (
            200,
            {
                "info": {"name": "ghostpkg", "version": "1.0.0"},
                "releases": {"1.0.0": []},  # registered but no files
            },
        ),
        "/pypi/ghostpkg/1.0.0/json": (
            200,
            {"info": {"name": "ghostpkg", "version": "1.0.0"}, "urls": []},
        ),
    }
    fileless_client = PyPIClient(opener=_fixture_opener(fileless_routes))
    params_ghost = VerificationParams.from_mapping(
        {"package_name": "ghostpkg", "created_at": CREATED}
    )
    r_fileless = verify(params_ghost, "ghostpkg|1.0.0", client=fileless_client)
    say("REJECT fileless detail: " + r_fileless.detail)
    assert r_fileless.verified is False
    assert "no uploaded files" in r_fileless.detail
    assert r_fileless.evidence["checks"]["version_present"]["ok"] is True
    assert r_fileless.evidence["checks"]["has_file"]["ok"] is False

    # ---- REJECT: pre-creation upload (release predates the mission) ----- #
    r_old = verify(params, "oabp-sdk|0.3.0", client=client)  # uploaded 2024-05-01
    say("REJECT pre-creation detail: " + r_old.detail)
    assert r_old.verified is False
    assert "freshly published" in r_old.detail
    assert r_old.evidence["checks"]["fresh_after_creation"]["ok"] is False
    assert r_old.evidence["checks"]["fresh_after_creation"]["enforced"] is True

    # ---- REJECT: project absent (404) ----------------------------------- #
    empty_client = PyPIClient(opener=_fixture_opener({}))  # everything 404s
    r_absent = verify(params, "oabp-sdk|0.3.1", client=empty_client)
    say("REJECT absent-project detail: " + r_absent.detail)
    assert r_absent.verified is False
    assert "not published on PyPI" in r_absent.detail
    assert r_absent.evidence["checks"]["project_exists"]["ok"] is False

    # ---- REJECT: below min_version (short-circuits before network) ------ #
    r_low = verify(params, "oabp-sdk|0.2.9", client=client)
    say("REJECT below-min detail: " + r_low.detail)
    assert r_low.verified is False
    assert "below the mission minimum" in r_low.detail
    assert r_low.evidence["checks"]["min_version"]["ok"] is False

    # ---- REJECT: wrong package name ------------------------------------- #
    r_wrongname = verify(params, "totally-other|0.3.1", client=client)
    assert r_wrongname.verified is False
    assert r_wrongname.evidence["checks"]["name_matches"]["ok"] is False

    # ---- REJECT: require_sdist but only a wheel exists ------------------ #
    wheelonly_routes = {
        "/pypi/wheelonly/json": (
            200,
            {
                "info": {"name": "wheelonly", "version": "1.0.0"},
                "releases": {
                    "1.0.0": [
                        _file(
                            "wheelonly-1.0.0-py3-none-any.whl",
                            "bdist_wheel",
                            "2024-06-02T09:15:00Z",
                        )
                    ]
                },
            },
        ),
    }
    wheelonly_client = PyPIClient(opener=_fixture_opener(wheelonly_routes))
    params_needs_sdist = VerificationParams.from_mapping(
        {"package_name": "wheelonly", "created_at": CREATED, "require_sdist": True}
    )
    r_needs_sdist = verify(params_needs_sdist, "wheelonly|1.0.0", client=wheelonly_client)
    assert r_needs_sdist.verified is False
    assert "requires an sdist" in r_needs_sdist.detail

    # ---- version resolved ONLY via the release endpoint (not in releases) #
    rel_only_routes = {
        "/pypi/latebind/json": (
            200,
            {"info": {"name": "latebind", "version": "0.9.0"}, "releases": {}},
        ),
        "/pypi/latebind/0.9.0/json": (
            200,
            {
                "info": {"name": "latebind", "version": "0.9.0"},
                "urls": [
                    _file("latebind-0.9.0.tar.gz", "sdist", "2024-06-02T11:00:00Z")
                ],
            },
        ),
    }
    rel_only_client = PyPIClient(opener=_fixture_opener(rel_only_routes))
    params_lb = VerificationParams.from_mapping(
        {"package_name": "latebind", "created_at": CREATED}
    )
    r_lb = verify(params_lb, "latebind|0.9.0", client=rel_only_client)
    assert r_lb.verified is True, r_lb.detail
    assert r_lb.evidence["checks"]["version_present"]["ok"] is True

    # ---- freshness NOT enforced when no created_at anywhere ------------- #
    params_nocreate = VerificationParams.from_mapping({"package_name": "oabp-sdk"})
    r_nofresh = verify(params_nocreate, "oabp-sdk|0.3.0", client=client)
    assert r_nofresh.verified is True, r_nofresh.detail  # old upload OK: unenforced
    assert r_nofresh.evidence["checks"]["fresh_after_creation"]["enforced"] is False

    # ---- verify_mission() wrapper reads params + created_at off the dict  #
    mission = {
        "id": "mis_pypi_demo",
        "title": "Publish oabp-sdk to PyPI",
        "verification_type": "oracle",
        "created_at": CREATED,
        "verification_params": {
            "package_name": "oabp-sdk",
            "min_version": "0.3.0",
            "oracle_description": "Publish oabp-sdk >=0.3.0 to PyPI.",
        },
    }
    r_mission = verify_mission(mission, "oabp-sdk|0.3.1", client=client)
    assert r_mission.verified is True, r_mission.detail
    r_mission_bad = verify_mission(mission, "oabp-sdk|0.3.0", client=client)
    assert r_mission_bad.verified is False  # pre-creation upload

    # ---- to_dict round-trips and is JSON serialisable ------------------- #
    d = r.to_dict()
    assert set(d) == {"verified", "detail", "evidence"}
    json.dumps(d)  # must not raise

    say("all self-test assertions passed")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pypi_publish_verifier",
        description=(
            "OABP/AIGEN oracle verifier: confirm an agent PUBLISHED a package to "
            "PyPI for a bounty. Queries the read-only PyPI JSON API to check the "
            "release exists, the version has >=1 uploaded file, and it was "
            "uploaded AFTER the mission was created. Structural only; no install "
            "or code execution; pure standard library."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--package-name", help="Mission's required PyPI package name.")
    p.add_argument("--proof", help="Submission proof, e.g. 'oabp-sdk|0.3.1'.")
    p.add_argument("--min-version", default=None, help="Minimum version (PEP 440).")
    p.add_argument(
        "--required-normalized-name",
        default=None,
        help="If set, the proof's normalised name must equal this.",
    )
    p.add_argument(
        "--require-sdist", action="store_true", help="Require an sdist (.tar.gz)."
    )
    p.add_argument(
        "--require-wheel", action="store_true", help="Require a wheel (.whl)."
    )
    p.add_argument(
        "--grace-seconds",
        type=int,
        default=0,
        help="Clock-skew slack subtracted from created_at for the freshness check.",
    )
    p.add_argument(
        "--created-at",
        type=int,
        default=None,
        help="Mission creation time (unix seconds); the upload must be AFTER it.",
    )
    p.add_argument(
        "--base-url",
        default=DEFAULT_PYPI_BASE,
        help="PyPI base URL (override for a private index / mirror).",
    )
    p.add_argument(
        "--json", action="store_true", help="Print the full VerifyResult as JSON."
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help="Run the offline self-test (stubs PyPI; no network) and exit.",
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
        print("\npypi-publish-verifier self-test: OK")
        return 0

    if not args.package_name or not args.proof:
        sys.stderr.write(
            "ERROR: --package-name and --proof are required (or use --self-test).\n"
        )
        return 2

    try:
        params = VerificationParams.from_mapping(
            {
                "package_name": args.package_name,
                "min_version": args.min_version,
                "required_normalized_name": args.required_normalized_name,
                "require_sdist": args.require_sdist,
                "require_wheel": args.require_wheel,
                "grace_seconds": args.grace_seconds,
                "created_at": args.created_at,
            }
        )
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2

    client = PyPIClient(base_url=args.base_url)
    try:
        result = verify(params, args.proof, client=client)
    except PyPIError as exc:
        sys.stderr.write("PyPI error: %s\n" % exc)
        return 3

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(("VERIFIED" if result.verified else "REJECTED") + ": " + result.detail)
    return 0 if result.verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
