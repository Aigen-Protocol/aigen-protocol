#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A2A discovery crawler for the OABP / AIGEN marketplace — fetch + cryptographically verify agent cards.

What this is
============
A self-contained agent that performs **A2A agent discovery with cryptographic
trust** against the OABP / AIGEN deployment at
``https://cryptogenesis.duckdns.org`` (or any other A2A endpoint you point it
at). For each base URL it:

1. fetches the agent card from ``/.well-known/agent-card.json`` (the A2A
   well-known discovery path),
2. fetches the signing keys from ``/.well-known/jwks.json``,
3. **verifies the card's ES256 / JWS signature against the JWKS** (EC P-256,
   ``kid`` ``aigen-es256-1`` on the reference deployment), and
4. prints, per agent: ``name``, ``version``, ``url``, ``capabilities``, the A2A
   ``protocolVersion`` (``0.3.0``), the declared **MCP transport** (``/mcp``),
   the number of ``skills``, and a ``VERIFIED`` / ``INVALID`` verdict.

It depends only on ``requests`` and ``cryptography`` — nothing else, no OABP
SDK import — so it is copy-pasteable into any agent.

Discovery + trust model
========================
A2A agents publish a self-describing **agent card** at the well-known URL
``<origin>/.well-known/agent-card.json``. The card advertises the agent's
identity (``name``/``version``), its service ``url``, transport
``capabilities``, the A2A ``protocolVersion`` it speaks, the interfaces it
exposes (A2A JSON-RPC at ``/api/a2a``, an **MCP** server at ``/mcp``), and its
``skills``. Discovery is *permissionless*: anyone can fetch a card.

Because a card is just JSON served over HTTP, its **authenticity** must be
established cryptographically rather than trusted on faith. The OABP card is
signed with **ES256** (ECDSA / NIST P-256 / SHA-256) and the *public* half of
the signing key is published as a **JWK** in the JWKS at
``<origin>/.well-known/jwks.json`` (``kid`` ``aigen-es256-1``). A verifier
reconstructs the exact bytes the signer hashed, checks the ECDSA signature with
the published public key, and only then trusts the card's contents.

The bytes that were signed are the **RFC 8785 (JCS) canonicalization** of the
card payload — JSON canonicalization removes every serialization degree of
freedom (key order, number formatting, whitespace, string escaping) so an
independent verifier reproduces the signer's bytes exactly. This file ships a
tiny in-file JCS canonicalizer (no external JCS dependency), validated against
the RFC 8785 Appendix B test vector in the offline self-test.

Card signature shapes supported
-------------------------------
OABP / A2A deployments wrap the JWS in more than one way; this crawler accepts
all three it has seen in the wild:

* **embedded detached JWS** — the card is a JSON object carrying its signature
  in a ``signature`` (or ``jws`` / ``proof``) field, in *detached-payload
  compact* form ``BASE64URL(header) || '..' || BASE64URL(signature)``. The
  signed payload is ``JCS(card)`` with the signature field removed. This is what
  the OABP signer (``sign_card.py``, ``kid=aigen-es256-1``) emits.
* **full compact JWS** — the whole document is a standard three-part compact JWS
  ``header.payload.signature`` whose decoded payload is the card JSON.
* **A2A ``signatures[]`` array** — the card carries a ``signatures`` list of
  ``{protected, signature, header?}`` detached-JWS entries (A2A card-signature
  extension); the signed payload is ``JCS(card)`` with the ``signatures`` field
  removed. The card is VERIFIED if **any** entry verifies.

Hardening (what this verifier refuses)
--------------------------------------
* **``alg`` is pinned to ES256.** The algorithm is *never* taken from the JWS
  header to decide how to verify (the classic "alg confusion" attack). A header
  advertising ``RS256``/``HS256``/anything-but-``ES256`` is rejected.
* **``alg: none`` is rejected** (the unsigned-token downgrade).
* The JWK must be ``kty=EC`` / ``crv=P-256``; coordinates must lie on the curve.
* When the JWS header names a ``kid`` it MUST select a matching JWK; a missing
  ``kid`` only resolves if the JWKS holds exactly one EC key (otherwise the set
  is ambiguous and rejected — never guessed).
* If a signer *inlines* the payload, it MUST byte-equal our JCS canonicalization
  of the stripped card; inlined bytes are never trusted blindly.
* The ECDSA signature is the raw ``R || S`` (64 bytes for P-256); any other
  length is rejected before any curve math.

``--insecure-skip-verify`` (OFF by default) fetches and prints the card without
running signature verification — for debugging an endpoint whose keys you do not
yet trust. It marks the verdict ``SKIPPED`` and never prints ``VERIFIED``.

Dependencies
------------
Python 3.8+, ``requests`` and ``cryptography``. No OABP SDK import.

Exit codes
----------
* ``0`` — every crawled agent produced a ``VERIFIED`` (or ``SKIPPED``, with
  ``--insecure-skip-verify``) verdict.
* ``1`` — at least one agent failed verification (``INVALID``) or could not be
  fetched, but the crawl itself completed and was printed.
* ``2`` — a usage / configuration error.
* ``4`` — the built-in offline self-test failed.

Run
---
    # crawl the default OABP deployment, fetch + verify its card
    python3 a2a_discovery_crawler.py

    # crawl several agents (repeat --url)
    python3 a2a_discovery_crawler.py \
        --url https://cryptogenesis.duckdns.org \
        --url https://another-a2a-agent.example

    # machine-readable output
    python3 a2a_discovery_crawler.py --json

    # fetch + print WITHOUT verifying the signature (debugging only)
    python3 a2a_discovery_crawler.py --insecure-skip-verify

    # run the offline self-test (no network) and exit
    python3 a2a_discovery_crawler.py --self-test
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    import requests
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write(
        "ERROR: this agent requires the 'requests' package "
        "(pip install requests).\n"
    )
    raise SystemExit(2)

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.ec import (
        SECP256R1,
        EllipticCurvePublicKey,
        EllipticCurvePublicNumbers,
    )
    from cryptography.hazmat.primitives.asymmetric.utils import (
        encode_dss_signature,
    )
except ImportError:  # pragma: no cover - environment guard
    sys.stderr.write(
        "ERROR: this agent requires the 'cryptography' package "
        "(pip install cryptography).\n"
    )
    raise SystemExit(2)


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"
AGENT_CARD_PATH = "/.well-known/agent-card.json"
JWKS_PATH = "/.well-known/jwks.json"
HTTP_TIMEOUT = 30.0
USER_AGENT = "oabp-a2a-discovery-crawler/1.0 (+https://cryptogenesis.duckdns.org)"

# Candidate fields that may carry the detached JWS inside a card object.
# ``signature`` is what the OABP signer uses; the others interop with other
# A2A card signers. ``signatures`` (plural) is the A2A array extension and is
# handled separately.
SIGNATURE_FIELDS = ("signature", "jws", "proof")

# ES256 over P-256 produces 32-byte R and S integers.
_P256_COORD_BYTES = 32

# The reference deployment's signing-key id (informational; verification works
# for any kid present in both the card header and the JWKS).
EXPECTED_KID = "aigen-es256-1"


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

class CrawlError(Exception):
    """A network / HTTP problem fetching a discovery document."""


class SignatureError(Exception):
    """The card signature is missing, malformed, or fails to verify."""


# ========================================================================== #
# In-file RFC 8785 (JCS) canonicalizer — no external dependency.
#
# The signer hashes the JCS canonicalization of the card payload, so the
# verifier must reproduce those exact bytes. RFC 8785 fixes key ordering
# (UTF-16 code-unit sort), number formatting (ECMAScript Number.toString),
# whitespace (none) and string escaping (mandatory short escapes only).
# Conformance is checked against the RFC 8785 Appendix B vector in --self-test.
# ========================================================================== #

# Two-character short escapes mandated by RFC 8785 sec. 3.2.2.2 (-> RFC 8259).
_JCS_SHORT_ESCAPES = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}


def _jcs_escape_string(value: str) -> str:
    """Serialize a ``str`` as a canonical JSON string token (RFC 8785)."""
    out = ['"']
    for ch in value:
        cp = ord(ch)
        short = _JCS_SHORT_ESCAPES.get(cp)
        if short is not None:
            out.append(short)
        elif cp < 0x20:
            out.append("\\u%04x" % cp)  # lowercase hex, per spec
        else:
            out.append(ch)  # non-ASCII emitted literally; UTF-8 at the end
    out.append('"')
    return "".join(out)


def _jcs_serialize_number(value: Any) -> str:
    """Serialize a number using the ECMAScript ``Number`` algorithm (RFC 8785)."""
    if isinstance(value, bool):  # bool is a subclass of int — guard first
        raise TypeError("bool is not a JSON number")
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise ValueError("NaN and Infinity cannot be canonicalized")
    if value == 0:
        return "0"  # canonical form folds -0.0 to "0"
    if value == int(value) and abs(value) < 1e21:
        return str(int(value))  # integral floats render without a fraction
    text = repr(value)  # shortest round-trippable double, like ECMAScript
    if "e" in text or "E" in text:
        mantissa, _, exp = text.replace("E", "e").partition("e")
        sign = "+"
        if exp.startswith("-"):
            sign, exp = "-", exp[1:]
        elif exp.startswith("+"):
            exp = exp[1:]
        exp = exp.lstrip("0") or "0"
        text = f"{mantissa}e{sign}{exp}"
    return text


def _jcs_utf16_sort_key(key: str) -> bytes:
    """Sort key matching RFC 8785's UTF-16 code-unit ordering."""
    return key.encode("utf-16-be")


def _jcs_serialize(value: Any, out: List[str]) -> None:
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, str):
        out.append(_jcs_escape_string(value))
    elif isinstance(value, (int, float)):
        out.append(_jcs_serialize_number(value))
    elif isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise TypeError(f"object keys must be strings, got {type(key)!r}")
        out.append("{")
        first = True
        for key in sorted(value.keys(), key=_jcs_utf16_sort_key):
            if not first:
                out.append(",")
            first = False
            out.append(_jcs_escape_string(key))
            out.append(":")
            _jcs_serialize(value[key], out)
        out.append("}")
    elif isinstance(value, (list, tuple)):
        out.append("[")
        first = True
        for item in value:
            if not first:
                out.append(",")
            first = False
            _jcs_serialize(item, out)
        out.append("]")
    else:
        raise TypeError(f"object of type {type(value)!r} is not JSON serializable")


def jcs_dumps(value: Any) -> str:
    """Return the canonical JSON text (a ``str``) for ``value`` per RFC 8785."""
    out: List[str] = []
    _jcs_serialize(value, out)
    return "".join(out)


def jcs_canonicalize(value: Any) -> bytes:
    """Return the canonical UTF-8 bytes for ``value`` per RFC 8785."""
    return jcs_dumps(value).encode("utf-8")


# ========================================================================== #
# JOSE / ES256 verification primitives
# ========================================================================== #

def b64url_decode(data: Any) -> bytes:
    """Decode base64url, tolerating missing padding (per the JOSE spec)."""
    if isinstance(data, bytes):
        data = data.decode("ascii")
    pad = (-len(data)) % 4
    try:
        return base64.urlsafe_b64decode(data + ("=" * pad))
    except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise SignatureError(f"invalid base64url segment: {exc}") from exc


def _b64url_encode(raw: bytes) -> bytes:
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


def jwk_to_public_key(jwk: Mapping[str, Any]) -> EllipticCurvePublicKey:
    """Build a P-256 public key from a JWK mapping.

    Raises :class:`SignatureError` if the JWK is not an EC P-256 key or the
    coordinates do not lie on the curve.
    """
    if jwk.get("kty") != "EC":
        raise SignatureError(f"unsupported JWK kty {jwk.get('kty')!r}, expected 'EC'")
    if jwk.get("crv") != "P-256":
        raise SignatureError(f"unsupported JWK crv {jwk.get('crv')!r}, expected 'P-256'")
    try:
        x = int.from_bytes(b64url_decode(jwk["x"]), "big")
        y = int.from_bytes(b64url_decode(jwk["y"]), "big")
    except KeyError as exc:
        raise SignatureError(f"JWK missing coordinate {exc}") from exc
    try:
        return EllipticCurvePublicNumbers(x, y, SECP256R1()).public_key()
    except ValueError as exc:
        # Raised when (x, y) is not actually on the curve.
        raise SignatureError(f"JWK coordinates are not on P-256: {exc}") from exc


def _iter_jwks(jwks: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    keys = jwks.get("keys") if isinstance(jwks, Mapping) else None
    if not isinstance(keys, list) or not keys:
        raise SignatureError("JWKS has no 'keys' array")
    return keys


def _select_jwk(jwks: Mapping[str, Any], kid: Optional[str]) -> Mapping[str, Any]:
    """Pick the JWK to verify with.

    A header ``kid`` requires an exact match. Without a ``kid`` we use the sole
    EC key if there is exactly one; an ambiguous set is rejected, not guessed.
    """
    keys = list(_iter_jwks(jwks))
    if kid is not None:
        for jwk in keys:
            if jwk.get("kid") == kid:
                return jwk
        raise SignatureError(f"no JWK in JWKS matches kid {kid!r}")
    ec_keys = [k for k in keys if k.get("kty") == "EC"]
    if len(ec_keys) == 1:
        return ec_keys[0]
    if not ec_keys:
        raise SignatureError("JWKS contains no EC keys")
    raise SignatureError("JWS header has no 'kid' and JWKS is ambiguous (multiple EC keys)")


def _verify_es256(
    public_key: EllipticCurvePublicKey, signing_input: bytes, signature: bytes
) -> None:
    """Verify a raw (R||S) ES256 signature over ``signing_input``."""
    if len(signature) != 2 * _P256_COORD_BYTES:
        raise SignatureError(
            f"ES256 signature must be {2 * _P256_COORD_BYTES} bytes, "
            f"got {len(signature)}"
        )
    r = int.from_bytes(signature[:_P256_COORD_BYTES], "big")
    s = int.from_bytes(signature[_P256_COORD_BYTES:], "big")
    der = encode_dss_signature(r, s)
    try:
        public_key.verify(der, signing_input, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise SignatureError("ES256 signature does not verify") from exc


def _decode_protected_header(header_b64: str) -> Dict[str, Any]:
    """Decode and validate a JWS protected header, pinning ``alg`` to ES256.

    The algorithm is fixed to ES256 by THIS verifier — it is never taken from
    the header to choose a verification routine. ``alg: none`` and any
    non-ES256 ``alg`` are rejected here (alg-confusion / downgrade defence).
    """
    try:
        header = json.loads(b64url_decode(header_b64))
    except (ValueError, UnicodeDecodeError) as exc:
        raise SignatureError(f"invalid JWS header: {exc}") from exc
    if not isinstance(header, dict):
        raise SignatureError("JWS header is not a JSON object")
    alg = header.get("alg")
    if alg != "ES256":
        raise SignatureError(f"unsupported JWS alg {alg!r}, expected 'ES256'")
    return header


# --------------------------------------------------------------------------- #
# Card verification (three on-the-wire shapes)
# --------------------------------------------------------------------------- #

class VerifiedCard:
    """Result of a successful card verification."""

    __slots__ = ("payload", "kid", "header")

    def __init__(
        self, payload: Mapping[str, Any], kid: Optional[str], header: Mapping[str, Any]
    ) -> None:
        self.payload = payload  # verified card object (signature stripped)
        self.kid = kid          # kid from the verified JWS header (or None)
        self.header = header    # the decoded, verified protected header


def _verify_detached(
    stripped: Mapping[str, Any],
    header_b64: str,
    payload_b64: str,
    sig_b64: str,
    jwks: Mapping[str, Any],
) -> VerifiedCard:
    """Verify a detached JWS over ``JCS(stripped)``.

    ``payload_b64`` may be empty (truly detached). If a signer inlined the
    payload it MUST byte-equal our JCS of the stripped card — never trusted
    blindly.
    """
    header = _decode_protected_header(header_b64)
    kid = header.get("kid")
    jwk = _select_jwk(jwks, kid)
    public_key = jwk_to_public_key(jwk)

    expected = _b64url_encode(jcs_canonicalize(dict(stripped))).decode("ascii")
    if payload_b64:
        if payload_b64 != expected:
            raise SignatureError(
                "inlined JWS payload does not match the card's JCS canonicalization"
            )
        payload_segment = payload_b64
    else:
        payload_segment = expected

    signing_input = f"{header_b64}.{payload_segment}".encode("ascii")
    _verify_es256(public_key, signing_input, b64url_decode(sig_b64))
    return VerifiedCard(payload=dict(stripped), kid=kid, header=header)


def _verify_embedded(
    card: Mapping[str, Any], jws: str, jwks: Mapping[str, Any]
) -> VerifiedCard:
    """Embedded detached compact JWS (``header..signature``) in a card field."""
    parts = jws.split(".")
    if len(parts) != 3:
        raise SignatureError(
            "embedded card signature must be a detached compact JWS "
            "(header..signature)"
        )
    header_b64, payload_b64, sig_b64 = parts
    # The signed payload is the card minus ALL signature-carrying fields.
    stripped = {k: v for k, v in card.items() if k not in SIGNATURE_FIELDS}
    return _verify_detached(stripped, header_b64, payload_b64, sig_b64, jwks)


def _verify_compact(jws: str, jwks: Mapping[str, Any]) -> VerifiedCard:
    """Full compact JWS ``header.payload.signature`` whose payload is the card."""
    parts = jws.split(".")
    if len(parts) != 3 or not parts[1]:
        raise SignatureError("compact JWS must have a non-empty payload segment")
    header_b64, payload_b64, sig_b64 = parts

    header = _decode_protected_header(header_b64)
    kid = header.get("kid")
    jwk = _select_jwk(jwks, kid)
    public_key = jwk_to_public_key(jwk)

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    _verify_es256(public_key, signing_input, b64url_decode(sig_b64))

    try:
        payload = json.loads(b64url_decode(payload_b64))
    except (ValueError, UnicodeDecodeError) as exc:
        raise SignatureError(f"invalid JWS payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise SignatureError("JWS payload is not a JSON object")
    return VerifiedCard(payload=payload, kid=kid, header=header)


def _verify_signatures_array(
    card: Mapping[str, Any], signatures: Sequence[Any], jwks: Mapping[str, Any]
) -> VerifiedCard:
    """A2A ``signatures[]`` extension: list of detached ``{protected,signature}``.

    The signed payload is ``JCS(card)`` with the ``signatures`` field removed.
    VERIFIED if ANY entry verifies; otherwise the collected failures are raised.
    """
    stripped = {k: v for k, v in card.items() if k != "signatures"}
    failures: List[str] = []
    for entry in signatures:
        if not isinstance(entry, Mapping):
            failures.append("signature entry is not an object")
            continue
        protected = entry.get("protected")
        sig = entry.get("signature")
        if not isinstance(protected, str) or not isinstance(sig, str):
            failures.append("signature entry missing 'protected'/'signature' string")
            continue
        try:
            # Detached: payload segment is empty in the wire form.
            return _verify_detached(stripped, protected, "", sig, jwks)
        except SignatureError as exc:
            failures.append(str(exc))
    raise SignatureError(
        "no entry in 'signatures' verified "
        f"({len(list(signatures))} tried): " + "; ".join(failures)
    )


def verify_card(card: Any, jwks: Mapping[str, Any]) -> VerifiedCard:
    """Verify an agent card's ES256 signature against ``jwks``.

    ``card`` may be a compact-JWS string, or a ``dict`` carrying its signature
    as an embedded ``signature``/``jws``/``proof`` field (detached JWS over the
    JCS of the rest of the card) **or** an A2A ``signatures`` array. Returns a
    :class:`VerifiedCard`; raises :class:`SignatureError` on any failure.
    """
    if isinstance(card, str):
        text = card.strip()
        if text.count(".") == 2 and "{" not in text:
            return _verify_compact(text, jwks)
        try:
            card = json.loads(text)
        except ValueError as exc:
            raise SignatureError(f"card is neither compact JWS nor JSON: {exc}") from exc

    if not isinstance(card, Mapping):
        raise SignatureError(f"card must be a mapping or compact JWS, got {type(card)!r}")

    # 1) Embedded single detached JWS (OABP sign_card.py form).
    for field in SIGNATURE_FIELDS:
        value = card.get(field)
        if isinstance(value, str) and value:
            return _verify_embedded(card, value, jwks)
        if isinstance(value, Mapping):
            inner = value.get("jws") or value.get("signature") or value.get("value")
            if isinstance(inner, str) and inner:
                return _verify_embedded(card, inner, jwks)

    # 2) A2A signatures[] array extension.
    sigs = card.get("signatures")
    if isinstance(sigs, list) and sigs:
        return _verify_signatures_array(card, sigs, jwks)

    raise SignatureError(
        "card has no signature field "
        f"(looked for {', '.join(SIGNATURE_FIELDS)} or a non-empty 'signatures' array)"
    )


# ========================================================================== #
# HTTP fetch of the discovery documents
# ========================================================================== #

def _build_session(session: Optional[requests.Session]) -> Tuple[requests.Session, bool]:
    if session is not None:
        return session, False
    s = requests.Session()
    s.headers.update({"Accept": "application/json", "User-Agent": USER_AGENT})
    return s, True


def _origin(base_url: str) -> str:
    """Return ``scheme://host[:port]`` for ``base_url`` (well-known lives there)."""
    base_url = base_url.strip()
    if "://" not in base_url:
        base_url = "https://" + base_url
    head, _, rest = base_url.partition("://")
    host = rest.split("/", 1)[0]
    return f"{head}://{host}"


def _get_json(session: requests.Session, url: str) -> Any:
    try:
        resp = session.get(url, timeout=HTTP_TIMEOUT)
    except requests.exceptions.RequestException as exc:
        raise CrawlError(f"GET {url} failed: {exc}") from exc
    if resp.status_code != 200:
        raise CrawlError(f"GET {url} returned HTTP {resp.status_code}")
    text = resp.text
    try:
        return json.loads(text)
    except ValueError as exc:
        raise CrawlError(f"GET {url} did not return JSON: {exc}") from exc


def fetch_agent_card(session: requests.Session, base_url: str) -> Any:
    """GET ``<origin>/.well-known/agent-card.json`` (object or compact-JWS string)."""
    return _get_json(session, _origin(base_url) + AGENT_CARD_PATH)


def fetch_jwks(session: requests.Session, base_url: str) -> Dict[str, Any]:
    """GET ``<origin>/.well-known/jwks.json``."""
    data = _get_json(session, _origin(base_url) + JWKS_PATH)
    if not isinstance(data, Mapping):
        raise CrawlError("JWKS endpoint did not return a JSON object")
    return dict(data)


# ========================================================================== #
# Card field extraction (A2A schema, tolerant of variants)
# ========================================================================== #

def _card_object(card: Any) -> Mapping[str, Any]:
    """Return the card as a dict, decoding a compact-JWS payload if needed."""
    if isinstance(card, Mapping):
        return card
    if isinstance(card, str):
        text = card.strip()
        if text.count(".") == 2 and "{" not in text:
            parts = text.split(".")
            try:
                payload = json.loads(b64url_decode(parts[1]))
            except Exception:  # noqa: BLE001 - best-effort for display only
                return {}
            return payload if isinstance(payload, Mapping) else {}
        try:
            obj = json.loads(text)
        except ValueError:
            return {}
        return obj if isinstance(obj, Mapping) else {}
    return {}


def _mcp_transport(card: Mapping[str, Any]) -> Optional[str]:
    """Extract the declared MCP transport endpoint (``/mcp``) from the card.

    A2A cards advertise extra transports via ``additionalInterfaces`` (and some
    deployments use ``interfaces`` / ``mcp`` / ``mcpServers``). We surface the
    ``url`` of whichever interface is tagged MCP. Falls back to scanning for an
    interface whose transport mentions "mcp" or whose url ends in ``/mcp``.
    """
    def _scan(interfaces: Any) -> Optional[str]:
        if not isinstance(interfaces, list):
            return None
        for iface in interfaces:
            if not isinstance(iface, Mapping):
                continue
            transport = str(iface.get("transport", "")).upper()
            url = iface.get("url")
            if transport == "MCP" and isinstance(url, str):
                return url
            if isinstance(url, str) and (transport == "MCP" or url.rstrip("/").endswith("/mcp")):
                return url
        return None

    for key in ("additionalInterfaces", "interfaces"):
        found = _scan(card.get(key))
        if found:
            return found

    mcp = card.get("mcp")
    if isinstance(mcp, Mapping):
        for k in ("url", "endpoint", "transport"):
            if isinstance(mcp.get(k), str):
                return mcp[k]
    if isinstance(mcp, str):
        return mcp

    servers = card.get("mcpServers")
    if isinstance(servers, Mapping):
        for v in servers.values():
            if isinstance(v, Mapping) and isinstance(v.get("url"), str):
                return v["url"]
    return None


def summarize_card(card: Any, verdict: str, kid: Optional[str]) -> Dict[str, Any]:
    """Pull the human-facing fields out of a (possibly raw) card."""
    obj = _card_object(card)
    skills = obj.get("skills")
    skills_count = len(skills) if isinstance(skills, list) else 0
    caps = obj.get("capabilities")
    return {
        "name": obj.get("name"),
        "version": obj.get("version"),
        "url": obj.get("url"),
        "protocolVersion": obj.get("protocolVersion"),
        "preferredTransport": obj.get("preferredTransport"),
        "mcpTransport": _mcp_transport(obj),
        "capabilities": caps if isinstance(caps, Mapping) else {},
        "skillsCount": skills_count,
        "kid": kid,
        "verdict": verdict,
    }


# ========================================================================== #
# Crawl one agent
# ========================================================================== #

def crawl_agent(
    base_url: str,
    *,
    session: Optional[requests.Session] = None,
    skip_verify: bool = False,
) -> Dict[str, Any]:
    """Fetch and (unless skipped) verify one agent's card.

    Returns a summary dict with a ``verdict`` of ``VERIFIED`` / ``INVALID`` /
    ``SKIPPED`` / ``ERROR`` and (on error) an ``error`` message.
    """
    sess, owns = _build_session(session)
    try:
        try:
            card = fetch_agent_card(sess, base_url)
        except CrawlError as exc:
            return {
                "base_url": base_url, "verdict": "ERROR", "error": str(exc),
                "name": None, "version": None, "url": None,
                "protocolVersion": None, "preferredTransport": None,
                "mcpTransport": None, "capabilities": {}, "skillsCount": 0,
                "kid": None,
            }

        if skip_verify:
            summary = summarize_card(card, "SKIPPED", None)
            summary["base_url"] = base_url
            return summary

        try:
            jwks = fetch_jwks(sess, base_url)
            verified = verify_card(card, jwks)
            summary = summarize_card(card, "VERIFIED", verified.kid)
        except (CrawlError, SignatureError) as exc:
            summary = summarize_card(card, "INVALID", None)
            summary["error"] = str(exc)
        summary["base_url"] = base_url
        return summary
    finally:
        if owns:
            sess.close()


# ========================================================================== #
# Rendering
# ========================================================================== #

def _fmt_caps(caps: Mapping[str, Any]) -> str:
    if not caps:
        return "(none)"
    enabled = [k for k, v in caps.items() if v is True]
    other = [f"{k}={v}" for k, v in caps.items() if v is not True and v is not False]
    parts = enabled + other
    return ", ".join(parts) if parts else "(none declared true)"


def render_text(summaries: Sequence[Mapping[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("== A2A discovery crawl ==")
    for s in summaries:
        verdict = s.get("verdict", "?")
        mark = {
            "VERIFIED": "[ VERIFIED ]",
            "INVALID": "[ INVALID  ]",
            "SKIPPED": "[ SKIPPED  ]",
            "ERROR": "[  ERROR   ]",
        }.get(verdict, f"[ {verdict} ]")
        lines.append("")
        lines.append(f"{mark}  {s.get('base_url')}")
        if verdict == "ERROR":
            lines.append(f"    error: {s.get('error')}")
            continue
        lines.append(f"    name             : {s.get('name')}")
        lines.append(f"    version          : {s.get('version')}")
        lines.append(f"    url              : {s.get('url')}")
        lines.append(f"    protocolVersion  : {s.get('protocolVersion')}")
        lines.append(f"    preferredTransport: {s.get('preferredTransport')}")
        lines.append(f"    MCP transport    : {s.get('mcpTransport')}")
        lines.append(f"    capabilities     : {_fmt_caps(s.get('capabilities') or {})}")
        lines.append(f"    skills           : {s.get('skillsCount')}")
        if s.get("kid"):
            lines.append(f"    signed by kid    : {s.get('kid')}")
        if verdict == "INVALID" and s.get("error"):
            lines.append(f"    reason           : {s.get('error')}")
    lines.append("")
    n_ok = sum(1 for s in summaries if s.get("verdict") in ("VERIFIED", "SKIPPED"))
    lines.append(f"{n_ok}/{len(summaries)} agent(s) trusted "
                 f"(VERIFIED, or SKIPPED with --insecure-skip-verify).")
    return "\n".join(lines)


# ========================================================================== #
# Offline self-test (no network)
# ========================================================================== #

def _self_test() -> bool:
    """Real-crypto, no-network self-test.

    Mints an ephemeral P-256 key, signs a fixture card in the OABP embedded
    detached-JWS form, and asserts:
      * a clean card VERIFIES and surfaces name/version/MCP transport;
      * flipping ONE byte of the card payload flips the verdict to INVALID;
      * an ``alg: none`` signature is rejected with a clear error;
      * a non-ES256 ``alg`` (alg-confusion) is rejected;
      * the JCS canonicalizer matches the RFC 8785 Appendix B vector.
    Returns True on success.
    """
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    def b64u(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    # --- RFC 8785 Appendix B conformance (numbers/sorting/escaping) ---------
    appendix_b_string = (
        chr(0x20AC) + "$" + chr(0x0F) + chr(0x0A) + "A" + "'" + "B"
        + '"' + "\\" + '"' + "/"
    )
    appendix_b_canon = (
        '"' + chr(0x20AC) + "$" + "\\u000f" + "\\n" + "A'B" + '\\"' + "\\\\" + '\\"' + '/"'
    )
    data = {
        "numbers": [333333333.33333329, 1e30, 4.50, 2e-3, 1e-27],
        "string": appendix_b_string,
        "literals": [None, True, False],
    }
    expected_jcs = (
        '{"literals":[null,true,false],'
        '"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27],'
        '"string":' + appendix_b_canon + "}"
    )
    assert jcs_dumps(data) == expected_jcs, "JCS Appendix B mismatch"

    # --- mint an ephemeral signer + matching JWKS (kid aigen-es256-1) -------
    priv = ec.generate_private_key(SECP256R1())
    nums = priv.public_key().public_numbers()
    kid = EXPECTED_KID
    jwks = {
        "keys": [{
            "kty": "EC", "crv": "P-256",
            "x": b64u(nums.x.to_bytes(32, "big")),
            "y": b64u(nums.y.to_bytes(32, "big")),
            "kid": kid, "alg": "ES256", "use": "sig",
        }]
    }

    card = {
        "name": "AIGEN Protocol",
        "description": "OABP agent-bounty marketplace agent",
        "url": "https://cryptogenesis.duckdns.org/api/a2a",
        "version": "1.0.0",
        "protocolVersion": "0.3.0",
        "preferredTransport": "JSONRPC",
        "capabilities": {"streaming": False, "pushNotifications": False},
        "additionalInterfaces": [
            {"transport": "JSONRPC", "url": "https://cryptogenesis.duckdns.org/api/a2a"},
            {"transport": "MCP", "url": "https://cryptogenesis.duckdns.org/mcp"},
        ],
        "skills": [
            {"id": "list-missions", "name": "List missions"},
            {"id": "create-mission", "name": "Create mission"},
            {"id": "submit-proof", "name": "Submit proof"},
        ],
    }

    def sign_embedded(payload: Mapping[str, Any]) -> Dict[str, Any]:
        header = {"alg": "ES256", "typ": "JWT", "kid": kid}
        header_b64 = b64u(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_b64 = b64u(jcs_canonicalize(dict(payload)))
        der = priv.sign(
            f"{header_b64}.{payload_b64}".encode("ascii"), ec.ECDSA(hashes.SHA256())
        )
        r, s = decode_dss_signature(der)
        sig_b64 = b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
        out = dict(payload)
        out["signature"] = f"{header_b64}..{sig_b64}"  # detached payload
        return out

    # (1) clean card verifies + fields surface correctly
    signed = sign_embedded(card)
    result = verify_card(signed, jwks)
    assert result.kid == kid, f"kid mismatch: {result.kid!r}"
    assert result.header["alg"] == "ES256"
    assert "signature" not in result.payload, "signature must be stripped"
    summary = summarize_card(signed, "VERIFIED", result.kid)
    assert summary["name"] == "AIGEN Protocol", summary["name"]
    assert summary["version"] == "1.0.0", summary["version"]
    assert summary["protocolVersion"] == "0.3.0", summary["protocolVersion"]
    assert summary["mcpTransport"] == "https://cryptogenesis.duckdns.org/mcp", (
        summary["mcpTransport"]
    )
    assert summary["skillsCount"] == 3, summary["skillsCount"]

    # (2) tamper ONE byte of the payload -> INVALID
    tampered = dict(signed)
    # flip a single character of the (already-signed) name field
    original = tampered["name"]
    flipped = original[:-1] + ("Q" if original[-1] != "Q" else "R")
    assert flipped != original
    tampered["name"] = flipped
    flipped_to_invalid = False
    try:
        verify_card(tampered, jwks)
    except SignatureError:
        flipped_to_invalid = True
    assert flipped_to_invalid, "tampered card MUST fail verification"
    # and the crawl-summary path reports INVALID rather than raising
    try:
        verify_card(tampered, jwks)
        v = "VERIFIED"
    except SignatureError:
        v = "INVALID"
    assert v == "INVALID"

    # (3) alg:none downgrade rejected with a clear error
    none_header = b64u(json.dumps({"alg": "none"}).encode("utf-8"))
    none_card = dict(card)
    none_card["signature"] = f"{none_header}.."
    rejected_none = False
    try:
        verify_card(none_card, jwks)
    except SignatureError as exc:
        rejected_none = "alg" in str(exc).lower()
    assert rejected_none, "alg:none MUST be rejected with an alg error"

    # (4) alg-confusion (RS256 header over the real key) rejected
    rs_header = b64u(json.dumps({"alg": "RS256", "kid": kid}).encode("utf-8"))
    rs_sig = b64u(b"\x00" * 64)
    rs_card = dict(card)
    rs_card["signature"] = f"{rs_header}..{rs_sig}"
    rejected_rs = False
    try:
        verify_card(rs_card, jwks)
    except SignatureError as exc:
        rejected_rs = "alg" in str(exc).lower()
    assert rejected_rs, "non-ES256 alg MUST be rejected"

    # (5) the A2A signatures[] array shape also verifies
    header = {"alg": "ES256", "kid": kid}
    header_b64 = b64u(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = b64u(jcs_canonicalize(dict(card)))
    der = priv.sign(f"{header_b64}.{payload_b64}".encode("ascii"), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    arr_sig = b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    arr_card = dict(card)
    arr_card["signatures"] = [{"protected": header_b64, "signature": arr_sig}]
    arr_result = verify_card(arr_card, jwks)
    assert arr_result.kid == kid
    assert "signatures" not in arr_result.payload

    return True


# ========================================================================== #
# CLI
# ========================================================================== #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="a2a_discovery_crawler.py",
        description=(
            "Fetch and cryptographically verify A2A agent cards (ES256/JWS over "
            "RFC 8785 JCS) for the OABP / AIGEN marketplace."
        ),
    )
    parser.add_argument(
        "--url",
        dest="urls",
        action="append",
        metavar="BASE_URL",
        help=(
            "Agent base URL to crawl (repeatable). Defaults to "
            f"{DEFAULT_BASE_URL} when omitted."
        ),
    )
    parser.add_argument(
        "--insecure-skip-verify",
        action="store_true",
        help="Fetch and print the card WITHOUT verifying its signature (debug only).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a table.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the offline self-test (no network) and exit.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.self_test:
        try:
            _self_test()
        except AssertionError as exc:
            sys.stderr.write(f"SELF-TEST FAILED: {exc}\n")
            return 4
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"SELF-TEST ERROR: {exc!r}\n")
            return 4
        print("self-test OK")
        return 0

    urls = args.urls or [DEFAULT_BASE_URL]

    summaries: List[Dict[str, Any]] = []
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        for url in urls:
            summaries.append(
                crawl_agent(
                    url, session=session, skip_verify=args.insecure_skip_verify
                )
            )
    finally:
        session.close()

    if args.json:
        print(json.dumps(summaries, indent=2, sort_keys=True))
    else:
        print(render_text(summaries))

    # Exit non-zero if any agent failed verification or could not be fetched.
    bad = any(s.get("verdict") in ("INVALID", "ERROR") for s in summaries)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
