#!/usr/bin/env python3
"""
Reference runner for the OABP / AIGEN verifier test vectors.

This is a *self-contained reference implementation* of the two checks the vector
file specifies, used to PROVE the vectors are runnable and to serve as a worked
example you can port to any language. It depends only on the Python standard
library plus `cryptography` (for ECDSA-P256 verification).

It runs three suites against verifier-test-vectors.json:

  1. first_valid_match  -- compile each `regex`, full-match it against `proof`,
                           assert the boolean equals `expected_match`.
                           (Cases that require lookaround are skipped on engines
                           that lack it; Python's `re` supports them, so they run
                           here.)
  2. JCS conformance    -- canonicalize each `input` per RFC 8785 and assert it
                           equals `expected_jcs` (and its UTF-8 hex).
  3. agent-card JWS     -- recompute JCS(card_without_signatures), base64url it as
                           the JWS payload, and ECDSA-P256/SHA-256 verify the
                           detached signature, with strict ES256/P-256 pinning.
                           Assert the valid vector verifies and every malformed
                           vector does not.

Usage:
    python3 run_vectors.py [path/to/verifier-test-vectors.json]

Exit status 0 = all vectors pass; non-zero = at least one vector failed.
No network. No build step. Nothing is written.
"""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives.asymmetric import ec, utils as asym_utils
    from cryptography.hazmat.primitives import hashes
    from cryptography.exceptions import InvalidSignature
    _HAVE_CRYPTO = True
except Exception:  # pragma: no cover - crypto suite is skipped if lib absent
    _HAVE_CRYPTO = False


# --------------------------------------------------------------------------- #
# RFC 8785 JSON Canonicalization Scheme (minimal, dependency-free).
# Mirrors the protocol's reference impl: keys sorted by UTF-16 code unit, no
# insignificant whitespace, ECMAScript Number::toString number formatting.
# --------------------------------------------------------------------------- #
def _escape_string(s: str) -> str:
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o < 0x20:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)  # printable (incl. non-ASCII) stays literal -> UTF-8
    out.append('"')
    return "".join(out)


def _format_number(n) -> str:
    if isinstance(n, bool):  # bool is an int subclass; never reached for JSON nums
        raise TypeError("bool is not a JSON number")
    if isinstance(n, int):
        return str(n)
    if n != n or n in (float("inf"), float("-inf")):
        raise ValueError("Cannot canonicalize a non-finite number")
    if n == 0:
        return "0"  # collapses -0.0 to "0" as ECMAScript does
    # Python's repr yields the shortest round-tripping decimal, matching V8 for
    # the magnitudes used in these vectors (e.g. 1e+21, 1e-27, 1.5, 0.002).
    return repr(n)


def canonicalize(value) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _escape_string(value)
    if isinstance(value, (int, float)):
        return _format_number(value)
    if isinstance(value, list):
        return "[" + ",".join(canonicalize(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys(), key=lambda k: k.encode("utf-16-be"))
        return "{" + ",".join(_escape_string(k) + ":" + canonicalize(value[k]) for k in keys) + "}"
    raise TypeError(f"Cannot canonicalize value of type {type(value)!r}")


# --------------------------------------------------------------------------- #
# base64url (no padding)
# --------------------------------------------------------------------------- #
def b64u_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# --------------------------------------------------------------------------- #
# Engine capability probe (for the lookahead-tagged cases).
# --------------------------------------------------------------------------- #
def _engine_supports_lookahead() -> bool:
    try:
        re.compile(r"(?!x)x")
        return True
    except re.error:
        return False


# --------------------------------------------------------------------------- #
# Suite 1 — first_valid_match
# --------------------------------------------------------------------------- #
def run_first_valid_match(doc: dict) -> tuple[int, int, int]:
    cases = doc["first_valid_match"]["cases"]
    have_la = _engine_supports_lookahead()
    passed = failed = skipped = 0
    print("first_valid_match")
    for c in cases:
        if "lookahead" in c.get("requires", []) and not have_la:
            skipped += 1
            print(f"  SKIP {c['id']:34} (engine lacks lookahead)")
            continue
        try:
            got = re.fullmatch(c["regex"], c["proof"]) is not None
        except re.error as e:
            failed += 1
            print(f"  FAIL {c['id']:34} regex did not compile: {e}")
            continue
        if got == c["expected_match"]:
            passed += 1
        else:
            failed += 1
            print(f"  FAIL {c['id']:34} expected {c['expected_match']} got {got}")
    print(f"  -> {passed} passed, {failed} failed, {skipped} skipped\n")
    return passed, failed, skipped


# --------------------------------------------------------------------------- #
# Suite 2 — JCS conformance
# --------------------------------------------------------------------------- #
def run_jcs_conformance(doc: dict) -> tuple[int, int, int]:
    cases = doc["agent_card_signature"]["jcs_conformance"]["cases"]
    passed = failed = 0
    print("jcs_conformance (RFC 8785)")
    for c in cases:
        got = canonicalize(c["input"])
        ok_str = got == c["expected_jcs"]
        ok_hex = got.encode("utf-8").hex() == c["expected_jcs_hex"]
        if ok_str and ok_hex:
            passed += 1
        else:
            failed += 1
            print(f"  FAIL {c['id']:30} got {got!r}")
            if not ok_hex:
                print(f"       hex got {got.encode().hex()} exp {c['expected_jcs_hex']}")
    print(f"  -> {passed} passed, {failed} failed\n")
    return passed, failed, 0


# --------------------------------------------------------------------------- #
# Suite 3 — agent-card detached ES256/JWS
# --------------------------------------------------------------------------- #
def _jwk_to_public_key(jwk: dict):
    crv = jwk["crv"]
    curve = {"P-256": ec.SECP256R1(), "P-384": ec.SECP384R1(), "P-521": ec.SECP521R1()}.get(crv)
    if curve is None:
        raise ValueError(f"unsupported curve {crv}")
    x = int.from_bytes(b64u_decode(jwk["x"]), "big")
    y = int.from_bytes(b64u_decode(jwk["y"]), "big")
    return ec.EllipticCurvePublicNumbers(x, y, curve).public_key()


def verify_detached_es256(protected_b64: str, payload_b64: str, signature_b64: str, jwk: dict) -> tuple[bool, str]:
    """Strict ES256/P-256 detached-JWS verification.

    Pins alg==ES256 and curve==P-256 (rejecting alg:none and wrong-curve keys),
    treats the signature as raw 64-byte r||s, and verifies over
    BASE64URL(protected)+'.'+payload.
    """
    try:
        header = json.loads(b64u_decode(protected_b64))
    except Exception as e:
        return False, f"unparseable protected header: {e}"
    if header.get("alg") != "ES256":
        return False, f"alg {header.get('alg')!r} not in allow-list [ES256]"
    if jwk.get("crv") != "P-256":
        return False, f"key curve {jwk.get('crv')!r} != P-256 (ES256 requires P-256)"
    raw = b64u_decode(signature_b64) if signature_b64 else b""
    if len(raw) != 64:
        return False, f"signature is {len(raw)} bytes, ES256 requires 64 (r||s)"
    r = int.from_bytes(raw[:32], "big")
    s = int.from_bytes(raw[32:], "big")
    der = asym_utils.encode_dss_signature(r, s)
    signing_input = (protected_b64 + "." + payload_b64).encode("ascii")
    try:
        key = _jwk_to_public_key(jwk)
        key.verify(der, signing_input, ec.ECDSA(hashes.SHA256()))
        return True, "ok"
    except InvalidSignature:
        return False, "ECDSA verification failed"
    except Exception as e:
        return False, f"verify error: {e}"


def run_agent_card(doc: dict) -> tuple[int, int, int]:
    if not _HAVE_CRYPTO:
        print("agent_card_signature: SKIPPED (the `cryptography` package is not installed)\n")
        return 0, 0, 1

    acs = doc["agent_card_signature"]
    jwks_key = acs["jwks"]["document"]["keys"][0]
    passed = failed = 0
    print("agent_card_signature (detached ES256/JWS over JCS payload)")

    # Recompute the canonical payload from the card itself and cross-check it
    # against the frozen value, then use it for the valid vector.
    recomputed = canonicalize(acs["payload"]["card_without_signatures"])
    if recomputed != acs["canonical"]["jcs_string"]:
        failed += 1
        print("  FAIL canonical payload: recomputed JCS != stored jcs_string")
    payload_b64 = b64u_encode(recomputed.encode("utf-8"))

    # Valid
    v = acs["valid"]
    ok, why = verify_detached_es256(v["protected"], payload_b64, v["signature"], jwks_key)
    if ok == v["expected_verify"]:
        passed += 1
        print(f"  PASS {v['id']:38} verify={ok}")
    else:
        failed += 1
        print(f"  FAIL {v['id']:38} verify={ok} ({why}) expected {v['expected_verify']}")

    # Malformed
    for c in acs["malformed"]["cases"]:
        key = jwks_key if c["verify_with"] == "jwks" else c["verification_jwk"]
        ok, why = verify_detached_es256(
            c["protected"], c["payload_b64url"], c.get("signature", ""), key
        )
        if ok == c["expected_verify"]:
            passed += 1
            print(f"  PASS {c['id']:38} verify={ok} ({why})")
        else:
            failed += 1
            print(f"  FAIL {c['id']:38} verify={ok} ({why}) expected {c['expected_verify']}")

    print(f"  -> {passed} passed, {failed} failed\n")
    return passed, failed, 0


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else Path(__file__).with_name("verifier-test-vectors.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    print(f"Loaded {path.name}: {doc.get('title')}\n")

    tp = tf = ts = 0
    for runner in (run_first_valid_match, run_jcs_conformance, run_agent_card):
        p, f, s = runner(doc)
        tp += p
        tf += f
        ts += s

    print("=" * 60)
    print(f"TOTAL: {tp} passed, {tf} failed, {ts} skipped")
    return 0 if tf == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
