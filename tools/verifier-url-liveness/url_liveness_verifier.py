#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OABP / AIGEN oracle mission verifier: *a submitted URL is live and serves the
required content*.

What this is
============
A new **oracle** mission-type verifier for the OABP / AIGEN agent-bounty
marketplace at ``https://cryptogenesis.duckdns.org``. It resolves missions whose
deliverable is "deploy a service / demo / docs site reachable at a public URL
that serves <content>" — e.g. *"stand up a live health endpoint that returns 200
and the JSON ``{\"status\":\"ok\"}\"*, or *"publish the API reference at
https://docs.example.com and make sure the page contains 'POST /api/missions'."*

The protocol already ships oracle backends that are **content-addressed**
(anyone can re-run them and get the same verdict from a public read-only source):
**GoPlus** (token-security for safety-review missions), the **GitHub REST API**
(repo deliverables), and the package-publish verifiers (**PyPI**, **npm**). This
module adds an HTTP-liveness oracle in the same spirit:

* **Read-only.** It issues a single ``GET`` (optionally following redirects),
  never a write/POST. It downloads at most ``max_bytes`` of the body and never
  executes, imports, or renders anything — it only *inspects* the response.
* **Content-addressed.** The verdict is a pure function of what the public URL
  returns: status code, response bytes, and a small set of declarative
  assertions (substring / regex / JSON-path). Any auditor can re-run the same
  ``GET`` and re-derive the result.
* **Fail-closed.** Anything it cannot affirmatively confirm — a wrong status, a
  missing substring, a failed JSON-path, an oversized body, a blocked host —
  yields ``verified=False`` with a precise, human-readable reason. Network /
  DNS / TLS failures are *verdicts* (the site is not reachably live), not
  crashes.
* **SSRF-hardened.** By default the verifier **refuses** to fetch private,
  loopback, link-local, or otherwise non-public hosts (``127.0.0.1``,
  ``localhost``, ``10.0.0.0/8``, ``169.254.0.0/16``, IPv6 ULA/loopback, …). A
  liveness oracle that a resolver runs against arbitrary submitter-controlled
  URLs is a classic *server-side request forgery* primitive; blocking private
  address space by default prevents a submission from coaxing the resolver into
  probing its own internal network. This guard is enforced **on every hop** of a
  redirect chain (not just the first URL). See "SSRF / safety" below.

It depends on the **Python standard library only** (``urllib``,
``http.client``, ``socket``, ``ipaddress``), so it runs in a resolver with zero
third-party packages installed. Python 3.7+.

Why an HTTP-liveness oracle is sound (and its limits)
-----------------------------------------------------
A public HTTP endpoint is a re-runnable, content-addressed witness: at the
moment of verification, ``GET <url>`` either does or does not return the required
status and content from the public internet. That is exactly the deliverable for
"deploy something reachable". The verifier records the observed status, byte
count, and which assertions matched in ``evidence`` so a creator/auditor can
re-derive the verdict.

Its limits are inherent and the mission designer should account for them:

* **Liveness is point-in-time.** The site was up *when verified*; the oracle
  does not guarantee it stays up. (Re-running the oracle re-checks liveness.)
* **It proves content is served, not authorship.** Anyone can host a page
  containing the required string. Use ``host_allow`` / ``url_pattern`` to bind
  the deliverable to a domain the mission controls or expects, or layer a
  GitHub-repo / content-hash oracle when *who built it* matters. Putting a
  mission-issued nonce in ``must_contain`` (a token the creator hands the solver
  out-of-band) raises the bar from "serves the string" to "serves the
  mission's secret string".

What the verifier checks (all configured checks must hold for ``verified=True``)
--------------------------------------------------------------------------------
Given a mission's ``verification_params`` (schema below) and a submission
``proof`` carrying the URL the agent deployed:

1. **URL PARSES & IS ALLOWED** — the proof yields an ``http(s)`` URL. If
   ``verification_params.url`` is set, the proof URL must equal it (normalised);
   otherwise if ``url_pattern`` is set, the proof URL must match that regex.
   The host is then checked against ``host_allow`` (if set) — and, unless
   ``allow_private`` is explicitly true, against the **SSRF blocklist** (private
   / loopback / link-local / reserved address space, by name *and* by every
   resolved IP).
2. **REACHABLE** — a single ``GET`` (with ``timeout``, ``max_bytes`` cap, and
   optional redirect following) completes without a transport error. A DNS /
   connection / TLS / timeout failure ⇒ the site is not reachably live ⇒ reject.
3. **STATUS MATCHES** — the final response status equals ``expect_status``
   (default ``200``). ``expect_status`` may also be a list of acceptable codes.
4. **CONTAINS** *(optional)* — every string in ``must_contain`` appears in the
   (decoded) body. (Set ``case_insensitive`` to fold case.)
5. **MATCHES** *(optional)* — the body matches the ``must_match`` regular
   expression (``re.search``).
6. **JSON-PATH** *(optional)* — the body parses as JSON and the dotted
   ``require_json_path`` assertion(s) hold, e.g. ``"status==ok"`` or
   ``"data.0.id==42"`` (see :func:`eval_json_path`). Supports ``==`` / ``!=`` /
   ``exists`` and array indexing.

Any configured check that does not affirmatively pass yields ``verified=False``
and a ``detail`` saying which one and why. The structured trace — the observed
status, byte count, and a per-assertion ``matched`` map — is returned in
``VerifyResult.evidence`` (``evidence['status']``, ``evidence['bytes']``,
``evidence['matched']`` are always present, per the OABP evidence convention for
this verifier).

The proof format
----------------
``proof`` is simply **the URL** the agent deployed — e.g.
``"https://demo.example.com/health"``. For convenience the verifier also accepts
a JSON object ``{"url": "..."}`` (or ``{"endpoint": "..."}`` / ``{"link": ...}``)
and a bare host (``demo.example.com`` → ``https://demo.example.com``). A scheme
of ``http://`` is upgraded to ``https://`` before the request when
``upgrade_insecure`` is true (the default), unless the mission explicitly
``allow_http``.

verification_params schema
==========================
The mission's ``verification_params`` object (the ``oracle`` arm of the protocol)
for this mission-type is::

    {
      # TARGET — provide exactly one of `url` or `url_pattern` (or neither, and
      # rely on host_allow). `url` pins the exact URL; `url_pattern` constrains
      # it by regex (e.g. only under your domain / path prefix).
      "url": "https://demo.example.com/health",   # str|null; exact expected URL
      "url_pattern":                               # str|null; regex the proof URL must match
          "^https://[a-z0-9.-]+\\.example\\.com/health$",

      # STATUS — the acceptable final HTTP status (default 200). May be a single
      # int or a list of ints.
      "expect_status": 200,                        # int | [int, ...]; default 200

      # CONTENT ASSERTIONS — all optional; all that ARE set must hold.
      "must_contain": ["status", "ok"],            # [str]; every string must appear in body
      "must_match": "\"version\"\\s*:\\s*\"\\d+", # str; regex (re.search) over body
      "require_json_path": "status==ok",           # str | [str]; dotted JSON-path assertions
                                                   #   e.g. "data.0.id==42", "ready exists"

      # FETCH CONTROLS.
      "max_bytes": 1048576,                        # int; hard cap on body read (default 1 MiB)
      "timeout": 10,                               # float seconds; per-request timeout (default 10)
      "follow_redirects": true,                    # bool; follow 3xx (default true), capped at max_redirects
      "max_redirects": 5,                          # int; redirect hops allowed (default 5)
      "case_insensitive": false,                   # bool; fold case for must_contain / must_match
      "upgrade_insecure": true,                    # bool; rewrite http:// -> https:// before GET (default true)
      "allow_http": false,                         # bool; permit a plain-http target (default false)

      # HOST ALLOW-LISTING — pin the deliverable to a domain you expect, so a
      # submitter can't satisfy the mission by hosting the content on someone
      # else's site. Either a regex (`host_allow`) or an explicit suffix list.
      "host_allow": "(^|\\.)example\\.com$",       # str|null; regex the host must match
      "host_allow_suffixes": ["example.com"],      # [str]|null; host must end with one of these

      # SSRF GUARD — keep this FALSE in production. When false (default) the
      # verifier refuses private/loopback/link-local/reserved targets by name
      # and by every resolved IP. Only set true for trusted internal testing.
      "allow_private": false,                      # bool; default false (block private address space)

      # human-readable spec; surfaced to solvers, not parsed by the oracle.
      "oracle_description":
          "Deploy a public health endpoint returning 200 with JSON {\"status\":\"ok\"}."
    }

None of the assertion fields are individually mandatory, but a mission MUST
constrain the target somehow — at least one of ``url`` / ``url_pattern`` /
``host_allow`` / ``host_allow_suffixes`` is required, otherwise the oracle would
accept *any* live URL the submitter names (and :meth:`VerificationParams.from_mapping`
raises ``ValueError``). ``oracle_description`` is free text for humans/solvers;
the machine truth is the typed fields above.

Worked example
==============
Mission::

    verification_params = {
        "url": "https://demo.example.com/health",
        "expect_status": 200,
        "must_contain": ["ok"],
        "require_json_path": "status==ok",
        "host_allow_suffixes": ["example.com"],
        "oracle_description":
            "Deploy a public health endpoint returning 200 with {\"status\":\"ok\"}.",
    }

An agent deploys the endpoint and submits ``proof = "https://demo.example.com/health"``.
The verifier:

* parses the proof -> ``https://demo.example.com/health``; equals ``url``; host
  ends with ``example.com``; host is public (not private) -> allowed; ✓
* ``GET`` the URL -> HTTP ``200`` within the size cap; ✓ (status check passes)
* body ``{"status":"ok","version":"1"}`` contains ``"ok"``; ✓
* body parses as JSON and ``status == "ok"``; ✓

=> ``VerifyResult(verified=True, detail="https://demo.example.com/health is live …",
evidence={"status":200, "bytes":29, "matched":{...}, ...})``. Had the endpoint
returned ``503``, omitted ``ok``, failed the JSON-path, or been hosted on a
non-``example.com`` domain (or a private IP), the result would be
``verified=False`` with the corresponding reason.

CLI
===
    # verify a live submission against the public internet:
    python3 url_liveness_verifier.py \
        --url https://demo.example.com/health \
        --expect-status 200 --must-contain ok \
        --require-json-path "status==ok" \
        --host-allow-suffix example.com \
        --proof https://demo.example.com/health

    # run the bundled OFFLINE self-test (stubs the transport; no network) and exit:
    python3 url_liveness_verifier.py --self-test

Exit codes (CLI):
* ``0`` — verified True (or, under --self-test, all assertions passed).
* ``1`` — verified False (the submission does not satisfy the mission).
* ``2`` — usage / configuration error.
"""

from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

__all__ = [
    "VerifyResult",
    "VerificationParams",
    "HttpResponse",
    "HttpClient",
    "HttpError",
    "SSRFBlocked",
    "verify",
    "verify_mission",
    "parse_proof_url",
    "normalize_url",
    "eval_json_path",
    "is_public_host",
    "DEFAULT_MAX_BYTES",
    "DEFAULT_TIMEOUT",
]

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
DEFAULT_MAX_BYTES = 1 << 20          # 1 MiB body cap
DEFAULT_TIMEOUT = 10.0               # seconds per request
DEFAULT_MAX_REDIRECTS = 5
USER_AGENT = "oabp-url-liveness-verifier/1.0 (+https://cryptogenesis.duckdns.org)"

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
        Structured, content-addressed trace of what the URL returned and which
        checks ran. For this verifier the convention is that ``evidence`` always
        carries (at least) ``status`` (int|None), ``bytes`` (int), and
        ``matched`` (a per-assertion pass/fail map), alongside the full
        per-check trace. Always JSON-serialisable.
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
    """Parsed, validated view of a URL-liveness mission's ``verification_params``.

    See the module docstring for the JSON schema. ``from_mapping`` is tolerant:
    unknown keys are ignored and wrong-typed optionals fall back to their
    defaults — but it REQUIRES that the mission constrain the target (one of
    ``url`` / ``url_pattern`` / ``host_allow`` / ``host_allow_suffixes``),
    otherwise the oracle would accept any URL the submitter names.
    """

    url: Optional[str] = None
    url_pattern: Optional[str] = None
    expect_status: Tuple[int, ...] = (200,)
    must_contain: Tuple[str, ...] = ()
    must_match: Optional[str] = None
    require_json_path: Tuple[str, ...] = ()
    max_bytes: int = DEFAULT_MAX_BYTES
    timeout: float = DEFAULT_TIMEOUT
    follow_redirects: bool = True
    max_redirects: int = DEFAULT_MAX_REDIRECTS
    case_insensitive: bool = False
    upgrade_insecure: bool = True
    allow_http: bool = False
    host_allow: Optional[str] = None
    host_allow_suffixes: Tuple[str, ...] = ()
    allow_private: bool = False
    oracle_description: Optional[str] = None

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
                    return (v.strip(),)
                if isinstance(v, (list, tuple)):
                    out = [str(x).strip() for x in v if str(x).strip()]
                    if out:
                        return tuple(out)
            return ()

        # expect_status: int | [int, ...]; default (200,)
        es_raw = data.get("expect_status", data.get("status", 200))
        if isinstance(es_raw, bool):  # guard: bool is an int subclass
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

        url = _opt_str("url", "expected_url", "target_url")
        url_pattern = _opt_str("url_pattern", "url_regex")
        host_allow = _opt_str("host_allow", "host_pattern", "allowed_host")
        host_allow_suffixes = _str_list(
            "host_allow_suffixes", "allowed_host_suffixes", "host_suffixes"
        )

        # The target MUST be constrained somehow, else the oracle is wide open.
        if not (url or url_pattern or host_allow or host_allow_suffixes):
            raise ValueError(
                "verification_params must constrain the target: set at least one "
                "of 'url', 'url_pattern', 'host_allow', or 'host_allow_suffixes'"
            )

        max_bytes = max(1, _int("max_bytes", DEFAULT_MAX_BYTES, "max_body_bytes"))
        timeout = _float("timeout", DEFAULT_TIMEOUT, "timeout_seconds")
        if timeout <= 0:
            timeout = DEFAULT_TIMEOUT
        max_redirects = max(0, _int("max_redirects", DEFAULT_MAX_REDIRECTS))

        return cls(
            url=url,
            url_pattern=url_pattern,
            expect_status=es,
            must_contain=_str_list("must_contain", "contains"),
            must_match=_opt_str("must_match", "match_regex", "body_regex"),
            require_json_path=_str_list(
                "require_json_path", "json_path", "json_paths"
            ),
            max_bytes=max_bytes,
            timeout=timeout,
            follow_redirects=_bool("follow_redirects", True, "follow"),
            max_redirects=max_redirects,
            case_insensitive=_bool("case_insensitive", False, "ignore_case"),
            upgrade_insecure=_bool("upgrade_insecure", True, "force_https"),
            allow_http=_bool("allow_http", False, "permit_http"),
            host_allow=host_allow,
            host_allow_suffixes=host_allow_suffixes,
            allow_private=_bool("allow_private", False, "allow_internal"),
            oracle_description=_opt_str("oracle_description"),
        )


# --------------------------------------------------------------------------- #
# URL parsing / normalisation
# --------------------------------------------------------------------------- #
def normalize_url(url: str, *, default_scheme: str = "https") -> str:
    """Lightly normalise a URL for comparison / fetching.

    * a bare host (``demo.example.com`` or ``demo.example.com/x``) gains a
      scheme (``https://`` by default);
    * scheme + host are lowercased; the path is preserved;
    * a default port matching the scheme (``:80`` for http, ``:443`` for https)
      is dropped;
    * a trailing slash on an empty path is normalised to ``/``.

    Raises ``ValueError`` if no usable ``http(s)`` URL can be formed.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")
    s = url.strip()

    if "://" not in s:
        # bare host[/path] -> add scheme
        s = "%s://%s" % (default_scheme, s)

    parts = urllib.parse.urlsplit(s)
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError("url scheme must be http or https, got %r" % parts.scheme)
    if not parts.hostname:
        raise ValueError("url has no host: %r" % url)

    host = parts.hostname.lower()
    port = parts.port
    # drop default ports
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None
    netloc = host if port is None else "%s:%d" % (host, port)

    path = parts.path or "/"
    # do not strip a meaningful trailing slash; only collapse empty path to "/"
    rebuilt = urllib.parse.urlunsplit((scheme, netloc, path, parts.query, ""))
    return rebuilt


def parse_proof_url(proof: Any, *, default_scheme: str = "https") -> str:
    """Extract the deployed URL from a submission proof.

    Accepted forms:
      * a plain URL string ``"https://demo.example.com/health"``
      * a bare host ``"demo.example.com"`` (gets ``default_scheme``)
      * a JSON object / dict carrying ``url`` (or ``endpoint`` / ``link`` /
        ``href`` / ``proof``)

    Returns the normalised URL. Raises ``ValueError`` if none can be extracted.
    """
    if isinstance(proof, Mapping):
        for key in ("url", "endpoint", "link", "href", "proof", "target"):
            v = proof.get(key)
            if isinstance(v, str) and v.strip():
                return normalize_url(v, default_scheme=default_scheme)
        raise ValueError("proof object carries no 'url'/'endpoint'/'link' string")

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
# SSRF guard: is this host safe to fetch?
# --------------------------------------------------------------------------- #
# Hostnames that are obviously local even before DNS resolution.
_BLOCKED_HOST_NAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
    }
)
# Suffixes that are, by convention, never public.
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
    unspecified, reserved, and (for v4) the metadata-friendly ``0.0.0.0/8`` and
    ``100.64.0.0/10`` CGNAT range. IPv4-mapped IPv6 is unwrapped and re-checked.
    """
    # Unwrap IPv4-mapped / 6to4-ish IPv6 so 0::ffff:127.0.0.1 can't sneak past.
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
    # global must be true for a routable address
    if not getattr(ip, "is_global", True):
        return False
    if isinstance(ip, ipaddress.IPv4Address):
        # 100.64.0.0/10 CGNAT is not in is_private on older stdlib; block it.
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
        # strip any scope id (e.g. fe80::1%eth0)
        addr = addr.split("%", 1)[0]
        if addr not in seen:
            seen.add(addr)
            out.append(addr)
    return out


def is_public_host(host: str) -> Tuple[bool, str]:
    """Decide whether ``host`` is safe (public) to fetch.

    Returns ``(ok, reason)``. ``ok`` is ``False`` if the host is a known-local
    name, has a non-public suffix, is an IP literal in private/reserved space,
    or resolves (via DNS) to ANY non-public IP. The "any resolved IP" rule is
    deliberate: a public-looking name that resolves to ``127.0.0.1`` (DNS
    rebinding / internal split-horizon) is still blocked.

    A DNS failure returns ``(False, "...unresolvable...")`` — fail-closed: a host
    we cannot resolve is not a confirmed-public target.
    """
    h = (host or "").strip().lower().rstrip(".")
    if not h:
        return False, "empty host"

    if h in _BLOCKED_HOST_NAMES:
        return False, "host %r is a reserved local name" % host
    for suf in _BLOCKED_HOST_SUFFIXES:
        if h.endswith(suf):
            return False, "host %r has non-public suffix %r" % (host, suf)

    # If the host is already an IP literal, check it directly (no DNS).
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

    # Otherwise resolve and require EVERY address to be public.
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
# HTTP response + client (stdlib urllib, with size cap + redirect control + SSRF)
# --------------------------------------------------------------------------- #
class HttpError(Exception):
    """A transport failure (DNS / connection / TLS / timeout / decode).

    Distinct from "the site returned the wrong status / content" (which the
    verifier represents as ``verified=False``, not an exception): an ``HttpError``
    means the GET could not be completed at all, so the site is not reachably
    live — the verifier turns it into ``verified=False`` with the cause.
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

    def text(self, *, errors: str = "replace") -> str:
        """Decode the (capped) body to text, honouring a charset hint if present."""
        charset = "utf-8"
        ctype = self.headers.get("content-type", "")
        m = re.search(r"charset=([\w\-]+)", ctype, re.IGNORECASE)
        if m:
            charset = m.group(1)
        try:
            return self.body.decode(charset, errors=errors)
        except (LookupError, UnicodeDecodeError):
            return self.body.decode("utf-8", errors="replace")


class HttpClient:
    """Read-only HTTP GET client with a size cap, redirect control, and SSRF guard.

    stdlib ``urllib`` / ``http.client`` only. The actual byte transport is
    pluggable via ``transport`` (signature
    ``(method, url, headers, timeout, max_bytes) -> HttpResponse``) so the
    offline self-test can stub the network with zero sockets. When no transport
    is injected, :meth:`_default_transport` performs a real, capped GET.

    SSRF enforcement happens in :meth:`get` (which the verifier always calls):
    the host of **every** URL in the redirect chain is checked with
    :func:`is_public_host` unless ``allow_private`` is set.
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
            # Is this a redirect we should follow?
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
        # Exhausted redirect budget.
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

        We disable urllib's automatic redirect handling (a custom no-op handler)
        so the caller can SSRF-check each hop; ``urlopen`` therefore returns 3xx
        responses as normal results rather than chasing them itself.
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
            # A 4xx/5xx (or a non-followed 3xx surfaced as error): capture it as
            # a real response so the status check can run against it.
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
# JSON-path assertion: "a.b.c==value" | "a.0.b!=x" | "a.b exists"
# --------------------------------------------------------------------------- #
_SENTINEL_MISSING = object()


def _navigate(doc: Any, path: str) -> Any:
    """Walk a dotted path through nested dicts/lists. Returns _SENTINEL_MISSING
    if any segment is absent. Integer segments index into lists (or are used as
    string keys into dicts when the dict has them).
    """
    cur: Any = doc
    if path == "" or path == "$":
        return cur
    # allow a leading "$." (jq-ish) for ergonomics
    p = path[2:] if path.startswith("$.") else path
    for seg in p.split("."):
        seg = seg.strip()
        if seg == "":
            continue
        if isinstance(cur, Mapping):
            if seg in cur:
                cur = cur[seg]
                continue
            return _SENTINEL_MISSING
        if isinstance(cur, (list, tuple)):
            # numeric index into a sequence
            if re.fullmatch(r"-?\d+", seg):
                idx = int(seg)
                if -len(cur) <= idx < len(cur):
                    cur = cur[idx]
                    continue
            return _SENTINEL_MISSING
        return _SENTINEL_MISSING
    return cur


def _coerce_expected(raw: str) -> Any:
    """Interpret the RHS of a ==/!= assertion as JSON if it looks like JSON,
    else as a trimmed string. So ``status==ok`` compares to ``"ok"`` and
    ``count==3`` compares to the number ``3`` and ``ready==true`` to ``True``.
    """
    s = raw.strip()
    if s == "":
        return ""
    # strip surrounding matching quotes -> literal string
    if (s[0] == s[-1]) and s[0] in ("'", '"') and len(s) >= 2:
        return s[1:-1]
    try:
        return json.loads(s)
    except ValueError:
        return s


def _values_equal(actual: Any, expected: Any) -> bool:
    """Equality with light, predictable coercion.

    Exact match wins. Otherwise compares string forms (so ``3`` == ``"3"`` and
    ``True`` == ``"true"``), and treats JSON-number/strings numerically when both
    look numeric. Designed to be intuitive for mission authors writing
    ``status==ok`` / ``count==3`` without worrying about JSON typing.
    """
    if actual == expected:
        return True
    # numeric compare if both look numeric
    try:
        if isinstance(actual, bool) or isinstance(expected, bool):
            raise TypeError
        return float(actual) == float(expected)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        pass
    # bool/string normalisation
    def norm(v: Any) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)

    return norm(actual).strip().lower() == norm(expected).strip().lower()


def eval_json_path(doc: Any, assertion: str) -> Tuple[bool, Dict[str, Any]]:
    """Evaluate one dotted JSON-path assertion against a parsed JSON ``doc``.

    Supported assertion grammar (whitespace around operators is allowed):

    * ``path==value``  — value at ``path`` equals ``value`` (JSON-typed RHS, or
      a quoted/plain string). e.g. ``status==ok``, ``data.0.id==42``,
      ``ready==true``.
    * ``path!=value``  — value at ``path`` is present and does **not** equal it.
    * ``path exists``  — ``path`` resolves to a present value (any value,
      including ``null``).
    * ``path``         — shorthand for ``path exists``.

    ``path`` segments are dot-separated; numeric segments index sequences
    (``data.0`` = first element). Returns ``(ok, info)`` where ``info`` is a
    JSON-safe description of what was found (for evidence).
    """
    a = (assertion or "").strip()
    if not a:
        return False, {"assertion": assertion, "error": "empty assertion"}

    # operator detection (order matters: != before =, == before bare)
    op: Optional[str] = None
    path = a
    expected_raw: Optional[str] = None
    if "!=" in a:
        op = "!="
        path, _, expected_raw = a.partition("!=")
    elif "==" in a:
        op = "=="
        path, _, expected_raw = a.partition("==")
    elif a.lower().endswith(" exists"):
        op = "exists"
        path = a[: -len(" exists")]
    else:
        op = "exists"
        path = a

    path = path.strip()
    found = _navigate(doc, path)
    present = found is not _SENTINEL_MISSING
    found_repr: Any
    if present:
        # keep evidence JSON-safe and compact
        found_repr = found if _json_safe(found) else repr(found)
    else:
        found_repr = None

    info: Dict[str, Any] = {
        "assertion": assertion,
        "op": op,
        "path": path,
        "present": present,
        "found": found_repr,
    }

    if op == "exists":
        info["ok"] = present
        return present, info

    expected = _coerce_expected(expected_raw or "")
    info["expected"] = expected
    if not present:
        info["ok"] = False
        return False, info
    eq = _values_equal(found, expected)
    ok = eq if op == "==" else (not eq)
    info["ok"] = ok
    return ok, info


def _json_safe(value: Any) -> bool:
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------- #
# The oracle
# --------------------------------------------------------------------------- #
def verify(
    params: VerificationParams,
    proof: Any,
    *,
    client: Optional[HttpClient] = None,
) -> VerifyResult:
    """Resolve a URL-liveness mission. Read-only; SSRF-guarded; fail-closed.

    :param params:  the parsed :class:`VerificationParams` for the mission.
    :param proof:   the submission proof — the deployed URL (string, bare host,
                    or ``{"url": ...}``; see :func:`parse_proof_url`).
    :param client:  inject an :class:`HttpClient` (or one wrapping a stub
                    transport in tests). When omitted, a real client is built
                    honouring ``params.allow_private``.
    :returns:       a :class:`VerifyResult`. ``evidence`` always carries
                    ``status`` / ``bytes`` / ``matched`` plus a per-check trace.
    """
    if client is None:
        client = HttpClient(allow_private=params.allow_private)

    evidence: Dict[str, Any] = {
        "verifier": "url_liveness",
        "params": {
            "url": params.url,
            "url_pattern": params.url_pattern,
            "expect_status": list(params.expect_status),
            "must_contain": list(params.must_contain),
            "must_match": params.must_match,
            "require_json_path": list(params.require_json_path),
            "max_bytes": params.max_bytes,
            "timeout": params.timeout,
            "follow_redirects": params.follow_redirects,
            "host_allow": params.host_allow,
            "host_allow_suffixes": list(params.host_allow_suffixes),
            "allow_private": params.allow_private,
        },
        # Convention for THIS verifier: these three keys are always present.
        "status": None,
        "bytes": 0,
        "matched": {},
        "checks": {},
    }
    checks: Dict[str, Any] = evidence["checks"]
    matched: Dict[str, Any] = evidence["matched"]

    def reject(detail: str) -> VerifyResult:
        return VerifyResult(verified=False, detail=detail, evidence=evidence)

    # --- 0) PARSE PROOF URL ---------------------------------------------- #
    try:
        target = parse_proof_url(
            proof,
            default_scheme="http" if params.allow_http and not params.upgrade_insecure else "https",
        )
    except ValueError as exc:
        checks["proof_parsed"] = {"ok": False, "reason": str(exc)}
        return reject("invalid proof: %s" % exc)
    evidence["proof"] = {"raw": proof if isinstance(proof, str) else repr(proof)}

    # Optional http->https upgrade before anything else.
    if target.lower().startswith("http://"):
        if params.upgrade_insecure and not params.allow_http:
            target = "https://" + target[len("http://"):]
        elif not params.allow_http:
            checks["scheme"] = {"ok": False, "reason": "plain http not allowed"}
            return reject(
                "proof URL uses http:// but the mission requires https "
                "(set allow_http to permit)"
            )
    evidence["target_url"] = target
    checks["proof_parsed"] = {"ok": True, "url": target}

    parts = urllib.parse.urlsplit(target)
    host = (parts.hostname or "").lower()

    # --- 1) URL / HOST ALLOWED ------------------------------------------- #
    # 1a) exact url pin
    if params.url is not None:
        try:
            want = normalize_url(params.url)
        except ValueError as exc:
            checks["url_match"] = {"ok": False, "reason": "bad params.url: %s" % exc}
            return reject("misconfigured mission: params.url is not a URL (%s)" % exc)
        url_ok = (target == want)
        checks["url_match"] = {"ok": url_ok, "expected": want, "actual": target}
        if not url_ok:
            return reject(
                "proof URL %s does not equal the required URL %s" % (target, want)
            )
    # 1b) url_pattern
    if params.url_pattern is not None:
        try:
            pat = re.compile(params.url_pattern)
        except re.error as exc:
            checks["url_pattern"] = {"ok": False, "reason": "bad regex: %s" % exc}
            return reject("misconfigured mission: bad url_pattern (%s)" % exc)
        pm = pat.search(target)
        checks["url_pattern"] = {"ok": bool(pm), "pattern": params.url_pattern}
        if not pm:
            return reject(
                "proof URL %s does not match url_pattern %r"
                % (target, params.url_pattern)
            )
    # 1c) host_allow regex
    if params.host_allow is not None:
        try:
            hpat = re.compile(params.host_allow)
        except re.error as exc:
            checks["host_allow"] = {"ok": False, "reason": "bad regex: %s" % exc}
            return reject("misconfigured mission: bad host_allow (%s)" % exc)
        hm = hpat.search(host)
        checks["host_allow"] = {"ok": bool(hm), "pattern": params.host_allow, "host": host}
        if not hm:
            return reject(
                "host %r is not allowed by host_allow %r (the URL must be on an "
                "expected domain)" % (host, params.host_allow)
            )
    # 1d) host_allow_suffixes
    if params.host_allow_suffixes:
        suf_ok = any(
            host == s.lower().lstrip(".") or host.endswith("." + s.lower().lstrip("."))
            for s in params.host_allow_suffixes
        )
        checks["host_allow_suffixes"] = {
            "ok": suf_ok,
            "suffixes": list(params.host_allow_suffixes),
            "host": host,
        }
        if not suf_ok:
            return reject(
                "host %r does not end with any allowed suffix %s"
                % (host, list(params.host_allow_suffixes))
            )

    # 1e) SSRF guard (host must be public unless private targets are allowed).
    # Authoritative enforcement lives in HttpClient._guard, which runs on EVERY
    # redirect hop; this is a friendly early reject with rich evidence. We gate
    # on the *client's* allow_private (the single source of truth for whether the
    # network layer will block private hosts) so the pre-check and the per-hop
    # guard never disagree — e.g. a test/internal client built with
    # allow_private=True bypasses both here and in the transport.
    enforce_ssrf = not getattr(client, "allow_private", params.allow_private)
    if enforce_ssrf:
        pub_ok, pub_reason = is_public_host(host)
        checks["ssrf_guard"] = {"ok": pub_ok, "reason": pub_reason, "host": host}
        if not pub_ok:
            return reject(
                "refused to verify a non-public target: %s (set allow_private "
                "only for trusted internal testing)" % pub_reason
            )
    else:
        checks["ssrf_guard"] = {"ok": True, "enforced": False, "host": host}

    # --- 2) FETCH (reachable?) ------------------------------------------- #
    try:
        resp = client.get(
            target,
            timeout=params.timeout,
            max_bytes=params.max_bytes,
            follow_redirects=params.follow_redirects,
            max_redirects=params.max_redirects,
        )
    except SSRFBlocked as exc:
        checks["reachable"] = {"ok": False, "ssrf": True, "error": str(exc)}
        return reject(str(exc))
    except HttpError as exc:
        checks["reachable"] = {"ok": False, "error": str(exc)}
        return reject("URL is not reachably live: %s" % exc)

    body_text = resp.text()
    evidence["status"] = resp.status
    evidence["bytes"] = len(resp.body)
    evidence["final_url"] = resp.url
    evidence["truncated"] = resp.truncated
    if resp.redirects:
        evidence["redirect_chain"] = resp.redirects
    checks["reachable"] = {
        "ok": True,
        "final_url": resp.url,
        "bytes": len(resp.body),
        "truncated": resp.truncated,
    }

    # --- 3) STATUS MATCHES ----------------------------------------------- #
    status_ok = resp.status in params.expect_status
    matched["status"] = status_ok
    checks["status"] = {
        "ok": status_ok,
        "actual": resp.status,
        "expected": list(params.expect_status),
    }
    if not status_ok:
        return reject(
            "GET %s returned HTTP %d, expected %s"
            % (resp.url, resp.status, list(params.expect_status))
        )

    # Body for substring/regex, optionally case-folded.
    hay = body_text.lower() if params.case_insensitive else body_text

    # --- 4) MUST_CONTAIN ------------------------------------------------- #
    if params.must_contain:
        contain_map: Dict[str, bool] = {}
        first_missing: Optional[str] = None
        for needle in params.must_contain:
            n = needle.lower() if params.case_insensitive else needle
            present = n in hay
            contain_map[needle] = present
            if not present and first_missing is None:
                first_missing = needle
        matched["must_contain"] = contain_map
        all_present = first_missing is None
        checks["must_contain"] = {"ok": all_present, "results": contain_map}
        if not all_present:
            return reject(
                "response body does not contain required substring %r"
                % first_missing
            )

    # --- 5) MUST_MATCH (regex) ------------------------------------------- #
    if params.must_match is not None:
        flags = re.IGNORECASE if params.case_insensitive else 0
        try:
            rx = re.compile(params.must_match, flags)
        except re.error as exc:
            checks["must_match"] = {"ok": False, "reason": "bad regex: %s" % exc}
            return reject("misconfigured mission: bad must_match regex (%s)" % exc)
        mm = rx.search(body_text)
        matched["must_match"] = bool(mm)
        checks["must_match"] = {
            "ok": bool(mm),
            "pattern": params.must_match,
            "match": (mm.group(0)[:200] if mm else None),
        }
        if not mm:
            return reject(
                "response body does not match required regex %r" % params.must_match
            )

    # --- 6) REQUIRE_JSON_PATH -------------------------------------------- #
    if params.require_json_path:
        try:
            doc = json.loads(resp.body.decode("utf-8", errors="strict"))
            json_ok = True
            json_err = None
        except (ValueError, UnicodeDecodeError) as exc:
            doc = None
            json_ok = False
            json_err = str(exc)
        if not json_ok:
            matched["require_json_path"] = {"_json_parse": False}
            checks["require_json_path"] = {
                "ok": False,
                "reason": "response body is not valid JSON: %s" % json_err,
            }
            return reject(
                "response body is not valid JSON, cannot evaluate require_json_path"
            )

        jp_results: List[Dict[str, Any]] = []
        jp_matched: Dict[str, bool] = {}
        first_fail: Optional[Dict[str, Any]] = None
        for assertion in params.require_json_path:
            ok, info = eval_json_path(doc, assertion)
            jp_results.append(info)
            jp_matched[assertion] = ok
            if not ok and first_fail is None:
                first_fail = info
        matched["require_json_path"] = jp_matched
        all_jp = first_fail is None
        checks["require_json_path"] = {"ok": all_jp, "results": jp_results}
        if not all_jp:
            ff = first_fail or {}
            return reject(
                "JSON-path assertion failed: %s (found=%r)"
                % (ff.get("assertion"), ff.get("found"))
            )

    # --- ALL CHECKS PASSED ----------------------------------------------- #
    bits: List[str] = ["HTTP %d" % resp.status]
    if params.must_contain:
        bits.append("contains %d substring(s)" % len(params.must_contain))
    if params.must_match is not None:
        bits.append("matches regex")
    if params.require_json_path:
        bits.append("%d JSON-path assertion(s)" % len(params.require_json_path))
    detail = "%s is live (%s) — verified" % (resp.url, ", ".join(bits))
    return VerifyResult(verified=True, detail=detail, evidence=evidence)


def verify_mission(
    mission: Mapping[str, Any],
    proof: Any,
    *,
    client: Optional[HttpClient] = None,
) -> VerifyResult:
    """Convenience wrapper: verify a raw OABP mission dict + a proof.

    Reads ``verification_params`` straight off the mission object so a resolver
    can pass the JSON it already has. If the proof is not given explicitly, this
    will also look for it on the mission's most recent submission
    (``mission['submissions'][-1]['proof']``) when present.
    """
    if not isinstance(mission, Mapping):
        return VerifyResult(
            False, "mission is not an object", {"status": None, "bytes": 0, "matched": {}}
        )
    try:
        params = VerificationParams.from_mapping(mission.get("verification_params"))
    except ValueError as exc:
        return VerifyResult(
            False,
            "invalid verification_params: %s" % exc,
            {"error": str(exc), "status": None, "bytes": 0, "matched": {}},
        )

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
    ``body`` is ``bytes`` or a JSON-serialisable object (it is JSON-encoded). A
    ``Location`` header drives redirect tests. A missing route raises
    :class:`HttpError` (simulating an unreachable host) so the "not reachable"
    branch can be exercised without DNS.
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
        return HttpResponse(
            status=status, url=norm, body=raw, headers=h, truncated=truncated
        )

    return transport


def _client_for(routes, *, allow_private=True) -> HttpClient:
    # allow_private=True here only so the self-test can use example.com style
    # hosts via a STUB transport without real DNS; SSRF is tested separately via
    # is_public_host() and the real-guard path with allow_private=False.
    return HttpClient(allow_private=allow_private, transport=_stub_transport(routes))


def _self_test(verbose: bool = False) -> None:  # noqa: C901 - exhaustive by design
    """Assertions proving accept/reject behaviour against a stubbed transport."""

    def say(msg: str) -> None:
        if verbose:
            print(msg)

    # ---- URL normalisation ---------------------------------------------- #
    assert normalize_url("demo.example.com") == "https://demo.example.com/"
    assert normalize_url("HTTPS://Demo.Example.COM:443/Health") == (
        "https://demo.example.com/Health"
    )
    assert normalize_url("http://x.example.com:80/a?b=c") == "http://x.example.com/a?b=c"
    for bad in ["", "   ", "ftp://x.example.com", "https://"]:
        try:
            normalize_url(bad)
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected ValueError for url %r" % bad)

    # ---- proof parsing -------------------------------------------------- #
    assert parse_proof_url("https://a.example.com/h") == "https://a.example.com/h"
    assert parse_proof_url("a.example.com") == "https://a.example.com/"
    assert parse_proof_url('{"url": "https://a.example.com/h"}') == (
        "https://a.example.com/h"
    )
    assert parse_proof_url({"endpoint": "https://a.example.com/h"}) == (
        "https://a.example.com/h"
    )

    # ---- SSRF guard (the security-critical part) ------------------------ #
    # Private / loopback / link-local / reserved must be blocked by IP literal.
    for bad_host in (
        "127.0.0.1",
        "localhost",
        "10.0.0.5",
        "192.168.1.10",
        "172.16.0.1",
        "169.254.169.254",  # cloud metadata endpoint
        "0.0.0.0",
        "::1",
        "[::1]",
        "fd00::1",          # IPv6 ULA
        "fe80::1",          # IPv6 link-local
        "100.64.0.1",       # CGNAT
        "foo.localhost",
        "service.internal",
        "host.local",
    ):
        ok, reason = is_public_host(bad_host)
        assert ok is False, "SSRF guard should block %r (got ok, %s)" % (bad_host, reason)
    # Public IP literals must pass.
    for good_host in ("8.8.8.8", "1.1.1.1", "[2606:4700:4700::1111]"):
        ok, _ = is_public_host(good_host)
        assert ok is True, "public host %r should pass the SSRF guard" % good_host

    # The guard must fire through verify() (allow_private=False, real guard path)
    # even when a stub transport is provided — the host is checked before fetch.
    ssrf_params = VerificationParams.from_mapping(
        {"url": "http://127.0.0.1/health", "expect_status": 200, "allow_http": True}
    )
    # Use a real HttpClient (allow_private=False) but with a stub transport so no
    # socket is opened; the SSRF guard rejects before the transport is reached.
    ssrf_client = HttpClient(
        allow_private=False,
        transport=_stub_transport({"http://127.0.0.1/health": (200, {"x": 1}, None)}),
    )
    r_ssrf = verify(ssrf_params, "http://127.0.0.1/health", client=ssrf_client)
    say("SSRF reject detail: " + r_ssrf.detail)
    assert r_ssrf.verified is False
    assert "non-public" in r_ssrf.detail
    assert r_ssrf.evidence["checks"]["ssrf_guard"]["ok"] is False
    # localhost by name too
    ssrf_params2 = VerificationParams.from_mapping(
        {"url_pattern": ".*", "expect_status": 200}
    )
    r_ssrf2 = verify(ssrf_params2, "https://localhost/x", client=HttpClient(allow_private=False))
    assert r_ssrf2.verified is False
    assert r_ssrf2.evidence["checks"]["ssrf_guard"]["ok"] is False

    # ---- JSON-path evaluator -------------------------------------------- #
    doc = {"status": "ok", "version": "1", "count": 3, "ready": True,
           "data": [{"id": 41}, {"id": 42}], "nested": {"a": {"b": "deep"}}}
    assert eval_json_path(doc, "status==ok")[0] is True
    assert eval_json_path(doc, "status==down")[0] is False
    assert eval_json_path(doc, "count==3")[0] is True           # numeric RHS
    assert eval_json_path(doc, "count==4")[0] is False
    assert eval_json_path(doc, "ready==true")[0] is True        # bool RHS
    assert eval_json_path(doc, "data.1.id==42")[0] is True      # list index + nested
    assert eval_json_path(doc, "data.0.id==42")[0] is False
    assert eval_json_path(doc, "nested.a.b==deep")[0] is True
    assert eval_json_path(doc, "missing exists")[0] is False
    assert eval_json_path(doc, "status exists")[0] is True
    assert eval_json_path(doc, "status!=down")[0] is True
    assert eval_json_path(doc, "status!=ok")[0] is False
    assert eval_json_path(doc, "missing==x")[0] is False        # absent path != match

    CREATED_URL = "https://demo.example.com/health"

    # ================================================================== #
    # ACCEPT: status 200 + must_contain + json-path all pass.
    # ================================================================== #
    accept_params = VerificationParams.from_mapping(
        {
            "url": CREATED_URL,
            "expect_status": 200,
            "must_contain": ["ok", "version"],
            "require_json_path": ["status==ok", "version exists"],
            "host_allow_suffixes": ["example.com"],
            "oracle_description": "Deploy a public health endpoint returning 200.",
        }
    )
    accept_routes = {
        CREATED_URL: (
            200,
            {"status": "ok", "version": "1.0.3"},
            {"content-type": "application/json"},
        )
    }
    r = verify(accept_params, CREATED_URL, client=_client_for(accept_routes))
    say("ACCEPT detail: " + r.detail)
    assert r.verified is True, r.detail
    assert r.evidence["status"] == 200
    assert r.evidence["bytes"] > 0
    assert r.evidence["matched"]["status"] is True
    assert r.evidence["matched"]["must_contain"] == {"ok": True, "version": True}
    assert r.evidence["matched"]["require_json_path"] == {
        "status==ok": True,
        "version exists": True,
    }
    assert isinstance(r, VerifyResult) and isinstance(r.evidence, dict)
    assert bool(r) is True
    json.dumps(r.to_dict())  # evidence must be JSON-serialisable

    # ACCEPT via url_pattern (not exact url) + must_match regex.
    accept2 = VerificationParams.from_mapping(
        {
            "url_pattern": r"^https://[a-z0-9.-]+\.example\.com/health$",
            "expect_status": [200, 204],
            "must_match": r"\"version\"\s*:\s*\"\d+",
            "host_allow_suffixes": ["example.com"],
        }
    )
    r2 = verify(accept2, "https://api.example.com/health",
                client=_client_for({
                    "https://api.example.com/health": (
                        200, {"version": "2"}, {"content-type": "application/json"})
                }))
    assert r2.verified is True, r2.detail
    assert r2.evidence["matched"]["must_match"] is True

    # ================================================================== #
    # REJECT: wrong status (503).
    # ================================================================== #
    bad_status_routes = {CREATED_URL: (503, {"status": "down"}, None)}
    r_status = verify(accept_params, CREATED_URL, client=_client_for(bad_status_routes))
    say("REJECT wrong-status detail: " + r_status.detail)
    assert r_status.verified is False
    assert "HTTP 503" in r_status.detail
    assert r_status.evidence["status"] == 503
    assert r_status.evidence["matched"]["status"] is False
    assert r_status.evidence["checks"]["status"]["ok"] is False

    # ================================================================== #
    # REJECT: missing required substring (200 but body lacks "version").
    # ================================================================== #
    miss_substr_routes = {
        CREATED_URL: (200, {"status": "ok"}, {"content-type": "application/json"})
    }
    r_substr = verify(accept_params, CREATED_URL, client=_client_for(miss_substr_routes))
    say("REJECT missing-substring detail: " + r_substr.detail)
    assert r_substr.verified is False
    assert "does not contain required substring 'version'" in r_substr.detail
    assert r_substr.evidence["status"] == 200
    assert r_substr.evidence["matched"]["status"] is True
    assert r_substr.evidence["matched"]["must_contain"]["ok" if False else "version"] is False

    # ================================================================== #
    # REJECT: failed JSON-path. Body satisfies must_contain ["ok","version"] as
    # raw substrings (so we get PAST step 4) but the typed json-path status==ok
    # fails because status is "degraded" -> isolates the json-path failure.
    # ================================================================== #
    bad_jsonpath_routes = {
        CREATED_URL: (
            200,
            {"status": "degraded", "version": "1.0.3", "note": "service ok? no"},
            {"content-type": "application/json"},
        )
    }
    r_jp = verify(accept_params, CREATED_URL, client=_client_for(bad_jsonpath_routes))
    say("REJECT failed-json-path detail: " + r_jp.detail)
    assert r_jp.verified is False
    assert "JSON-path assertion failed" in r_jp.detail
    assert r_jp.evidence["matched"]["must_contain"] == {"ok": True, "version": True}
    assert r_jp.evidence["matched"]["require_json_path"]["status==ok"] is False

    # ================================================================== #
    # REJECT: body is not JSON but a json-path is required.
    # ================================================================== #
    notjson_routes = {CREATED_URL: (200, b"ok version <html>not json</html>", None)}
    r_njson = verify(accept_params, CREATED_URL, client=_client_for(notjson_routes))
    assert r_njson.verified is False
    assert "not valid JSON" in r_njson.detail

    # ================================================================== #
    # REJECT: unreachable (stub has no route -> simulated DNS/conn failure).
    # ================================================================== #
    r_unreach = verify(accept_params, CREATED_URL, client=_client_for({}))
    say("REJECT unreachable detail: " + r_unreach.detail)
    assert r_unreach.verified is False
    assert "not reachably live" in r_unreach.detail
    assert r_unreach.evidence["checks"]["reachable"]["ok"] is False

    # ================================================================== #
    # REJECT: right content but WRONG HOST (host_allow_suffixes mismatch).
    # ================================================================== #
    evil_url = "https://demo.evil.com/health"
    evil_params = VerificationParams.from_mapping(
        {
            "url_pattern": r"^https://.+/health$",  # pattern alone would allow it
            "expect_status": 200,
            "host_allow_suffixes": ["example.com"],  # ...but host pin does not
        }
    )
    r_host = verify(
        evil_params,
        evil_url,
        client=_client_for({evil_url: (200, {"status": "ok"}, None)}),
    )
    say("REJECT wrong-host detail: " + r_host.detail)
    assert r_host.verified is False
    assert "allowed suffix" in r_host.detail
    assert r_host.evidence["checks"]["host_allow_suffixes"]["ok"] is False

    # ================================================================== #
    # REJECT: url_pattern mismatch.
    # ================================================================== #
    pat_params = VerificationParams.from_mapping(
        {"url_pattern": r"^https://demo\.example\.com/health$", "expect_status": 200}
    )
    r_pat = verify(
        pat_params,
        "https://demo.example.com/WRONG",
        client=_client_for({"https://demo.example.com/WRONG": (200, {}, None)}),
    )
    assert r_pat.verified is False
    assert "url_pattern" in r_pat.detail

    # ================================================================== #
    # REJECT: exact url pin mismatch.
    # ================================================================== #
    r_urlpin = verify(
        accept_params,
        "https://demo.example.com/other",
        client=_client_for({"https://demo.example.com/other": (200, {}, None)}),
    )
    assert r_urlpin.verified is False
    assert "does not equal the required URL" in r_urlpin.detail

    # ================================================================== #
    # Redirect following + per-hop SSRF: a public->public redirect is followed.
    # ================================================================== #
    redir_params = VerificationParams.from_mapping(
        {
            "url_pattern": r"^https://start\.example\.com/$",
            "expect_status": 200,
            "must_contain": ["landed"],
            "host_allow_suffixes": ["example.com"],
            "follow_redirects": True,
        }
    )
    redir_routes = {
        "https://start.example.com/": (
            301, b"", {"location": "https://end.example.com/final"}
        ),
        "https://end.example.com/final": (200, b"you landed here", None),
    }
    r_redir = verify(redir_params, "https://start.example.com/",
                     client=_client_for(redir_routes))
    say("ACCEPT redirect detail: " + r_redir.detail)
    assert r_redir.verified is True, r_redir.detail
    assert r_redir.evidence.get("redirect_chain") == ["https://start.example.com/"]
    assert r_redir.evidence["final_url"] == "https://end.example.com/final"

    # Redirect to a PRIVATE host must be blocked ON THE HOP by the per-hop guard
    # (allow_private=False), NOT merely by the initial pre-check. To prove that,
    # the START host is a PUBLIC IP literal (passes is_public_host with no DNS),
    # so the in-verify pre-check passes; the rejection therefore must come from
    # HttpClient.get()'s per-hop _guard when it tries to follow the 302 to
    # 127.0.0.1. A public IP literal start also dodges the sandbox's lack of DNS.
    pub_ip_start = "https://93.184.216.34/"   # public address; guarded via IP branch
    redir_ssrf_client = HttpClient(
        allow_private=False,
        transport=_stub_transport({
            pub_ip_start: (302, b"", {"location": "http://127.0.0.1/secret"}),
            "http://127.0.0.1/secret": (200, b"secret", None),
        }),
    )
    redir_ssrf_params = VerificationParams.from_mapping(
        {"url": pub_ip_start, "expect_status": 200,
         "host_allow": r"^93\.184\.216\.34$"}
    )
    # sanity: the initial pre-check on the public IP literal must PASS
    assert is_public_host("93.184.216.34")[0] is True
    r_redir_ssrf = verify(redir_ssrf_params, pub_ip_start, client=redir_ssrf_client)
    say("REJECT redirect-to-private detail: " + r_redir_ssrf.detail)
    assert r_redir_ssrf.verified is False
    # the initial SSRF pre-check passed (public IP); the block came from the hop:
    assert r_redir_ssrf.evidence["checks"]["ssrf_guard"]["ok"] is True
    assert r_redir_ssrf.evidence["checks"]["reachable"].get("ssrf") is True
    assert "refused to fetch" in r_redir_ssrf.detail

    # ================================================================== #
    # case_insensitive must_contain.
    # ================================================================== #
    ci_params = VerificationParams.from_mapping(
        {"url": CREATED_URL, "must_contain": ["STATUS"], "case_insensitive": True,
         "host_allow_suffixes": ["example.com"]}
    )
    r_ci = verify(ci_params, CREATED_URL,
                  client=_client_for({CREATED_URL: (200, b'{"status":"ok"}', None)}))
    assert r_ci.verified is True, r_ci.detail

    # ================================================================== #
    # max_bytes truncation still allows a substring within the cap to match,
    # and the evidence flags truncation.
    # ================================================================== #
    big_body = b"PREFIX-NEEDLE" + (b"x" * 10_000)
    trunc_params = VerificationParams.from_mapping(
        {"url": CREATED_URL, "must_contain": ["NEEDLE"], "max_bytes": 32,
         "host_allow_suffixes": ["example.com"]}
    )
    r_trunc = verify(trunc_params, CREATED_URL,
                     client=_client_for({CREATED_URL: (200, big_body, None)}))
    assert r_trunc.verified is True, r_trunc.detail
    assert r_trunc.evidence["truncated"] is True
    assert r_trunc.evidence["bytes"] == 32

    # ================================================================== #
    # http:// upgraded to https:// by default (upgrade_insecure).
    # ================================================================== #
    up_params = VerificationParams.from_mapping(
        {"url": "https://demo.example.com/health", "expect_status": 200,
         "host_allow_suffixes": ["example.com"]}
    )
    r_up = verify(up_params, "http://demo.example.com/health",
                  client=_client_for({CREATED_URL: (200, b"ok", None)}))
    assert r_up.verified is True, r_up.detail
    assert r_up.evidence["target_url"].startswith("https://")

    # http:// rejected when not allowed and upgrade disabled.
    noup_params = VerificationParams.from_mapping(
        {"url_pattern": r"^http://.+", "upgrade_insecure": False, "allow_http": False,
         "expect_status": 200}
    )
    r_noup = verify(noup_params, "http://demo.example.com/health",
                    client=_client_for({}))
    assert r_noup.verified is False
    assert "http" in r_noup.detail.lower()

    # ================================================================== #
    # from_mapping requires the target to be constrained.
    # ================================================================== #
    try:
        VerificationParams.from_mapping({"expect_status": 200})
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for unconstrained mission")

    # ================================================================== #
    # verify_mission() reads params + (optionally) the last submission's proof.
    # ================================================================== #
    mission = {
        "id": "mis_url_demo",
        "title": "Deploy a health endpoint",
        "verification_type": "oracle",
        "verification_params": {
            "url": CREATED_URL,
            "expect_status": 200,
            "must_contain": ["ok"],
            "host_allow_suffixes": ["example.com"],
        },
        "submissions": [{"submitter_agent_id": "agent_1", "proof": CREATED_URL}],
    }
    r_mission = verify_mission(
        mission, None, client=_client_for({CREATED_URL: (200, b'{"status":"ok"}', None)})
    )
    assert r_mission.verified is True, r_mission.detail
    r_mission_bad = verify_mission(
        mission, None, client=_client_for({CREATED_URL: (500, b"err", None)})
    )
    assert r_mission_bad.verified is False

    # invalid params object -> graceful reject with evidence convention intact
    r_badparams = verify_mission({"verification_params": {"expect_status": 200}}, "x")
    assert r_badparams.verified is False
    assert "invalid verification_params" in r_badparams.detail
    assert set(["status", "bytes", "matched"]).issubset(r_badparams.evidence)

    say("all self-test assertions passed")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="url_liveness_verifier",
        description=(
            "OABP/AIGEN oracle verifier: confirm a submitted URL is LIVE and "
            "serves the required content. Does a read-only, size-capped GET "
            "(redirect-aware), checks the status and optional substring / regex "
            "/ JSON-path assertions, and refuses private/loopback targets by "
            "default (SSRF guard). Pure standard library; no code execution."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--proof", help="Submission proof: the deployed URL.")
    p.add_argument("--url", default=None, help="Exact expected URL (pins the target).")
    p.add_argument(
        "--url-pattern", default=None, help="Regex the proof URL must match."
    )
    p.add_argument(
        "--expect-status",
        type=int,
        action="append",
        default=None,
        help="Acceptable HTTP status (repeatable). Default 200.",
    )
    p.add_argument(
        "--must-contain",
        action="append",
        default=None,
        help="Required substring in the body (repeatable).",
    )
    p.add_argument("--must-match", default=None, help="Regex the body must match.")
    p.add_argument(
        "--require-json-path",
        action="append",
        default=None,
        help="JSON-path assertion, e.g. 'status==ok' (repeatable).",
    )
    p.add_argument(
        "--host-allow", default=None, help="Regex the target host must match."
    )
    p.add_argument(
        "--host-allow-suffix",
        action="append",
        default=None,
        help="Allowed host suffix, e.g. example.com (repeatable).",
    )
    p.add_argument(
        "--max-bytes", type=int, default=DEFAULT_MAX_BYTES, help="Body read cap."
    )
    p.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, help="Per-request timeout (s)."
    )
    p.add_argument(
        "--no-follow-redirects",
        action="store_true",
        help="Do not follow 3xx redirects.",
    )
    p.add_argument(
        "--case-insensitive",
        action="store_true",
        help="Fold case for must-contain / must-match.",
    )
    p.add_argument(
        "--allow-http",
        action="store_true",
        help="Permit a plain-http target (default upgrades to https).",
    )
    p.add_argument(
        "--allow-private",
        action="store_true",
        help="DANGER: disable the SSRF guard (allow private/loopback targets).",
    )
    p.add_argument(
        "--json", action="store_true", help="Print the full VerifyResult as JSON."
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help="Run the offline self-test (stubs the transport; no network) and exit.",
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
        print("\nurl-liveness-verifier self-test: OK")
        return 0

    if not args.proof:
        sys.stderr.write("ERROR: --proof <url> is required (or use --self-test).\n")
        return 2

    raw_params: Dict[str, Any] = {
        "url": args.url,
        "url_pattern": args.url_pattern,
        "expect_status": args.expect_status if args.expect_status else 200,
        "must_contain": args.must_contain or [],
        "must_match": args.must_match,
        "require_json_path": args.require_json_path or [],
        "host_allow": args.host_allow,
        "host_allow_suffixes": args.host_allow_suffix or [],
        "max_bytes": args.max_bytes,
        "timeout": args.timeout,
        "follow_redirects": not args.no_follow_redirects,
        "case_insensitive": args.case_insensitive,
        "allow_http": args.allow_http,
        "allow_private": args.allow_private,
    }
    try:
        params = VerificationParams.from_mapping(raw_params)
    except ValueError as exc:
        sys.stderr.write("ERROR: %s\n" % exc)
        return 2

    client = HttpClient(allow_private=args.allow_private)
    result = verify(params, args.proof, client=client)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(("VERIFIED" if result.verified else "REJECTED") + ": " + result.detail)
    return 0 if result.verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
