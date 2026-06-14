"""ES256 JWS verification of OABP agent cards against a JWKS.

The OABP agent card published at ``/.well-known/agent-card.json`` is signed with
ES256 (ECDSA over the NIST P-256 curve with SHA-256). The public half of the
signing key is published as a JWK in the JWKS at ``/.well-known/jwks.json``.

Two on-the-wire shapes are supported, because both are used in the wild by A2A /
agent-card deployments:

``embedded``
    The card is a normal JSON object that carries its own signature in a
    ``signature`` (or ``jws`` / ``proof``) field. That field holds a JWS in
    *detached-payload compact* form: ``BASE64URL(header) || '..' ||
    BASE64URL(signature)`` with the payload omitted. The payload that was signed
    is the RFC 8785 (JCS) canonicalization of the card object *with the
    signature field removed*. This is the form the OABP signer (`sign_card.py`)
    emits.

``compact``
    The whole document is a standard three-part compact JWS
    ``header.payload.signature`` and the decoded payload is the card JSON.

Verification is deliberately strict: ``alg`` must be ``ES256``, the JWS header's
``kid`` (when present) must select the matching JWK, ``kty``/``crv`` must be
``EC``/``P-256``, and the ECDSA signature is checked over the exact signing
input. Nothing here trusts the ``alg`` field to choose an algorithm (the classic
JWS "alg confusion" pitfall): the algorithm is fixed to ES256 by this verifier.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.ec import (
    SECP256R1,
    EllipticCurvePublicKey,
    EllipticCurvePublicNumbers,
)
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from . import jcs
from .errors import SignatureError

__all__ = [
    "SIGNATURE_FIELDS",
    "VerifiedCard",
    "b64url_decode",
    "verify_card",
    "jwk_to_public_key",
]

# Candidate field names that may carry the detached JWS inside the card object.
# ``signature`` is what the OABP signer uses; the others are accepted for
# interop with other A2A card signers.
SIGNATURE_FIELDS = ("signature", "jws", "proof")

# ES256 P-256 produces 32-byte R and S integers.
_P256_COORD_BYTES = 32


@dataclass(frozen=True)
class VerifiedCard:
    """Result of a successful card verification."""

    payload: Mapping[str, Any]
    """The verified card object (signature field stripped for the embedded form,
    or the decoded payload for the compact form)."""

    kid: Optional[str]
    """The key id taken from the JWS header (``None`` if the header had none)."""

    header: Mapping[str, Any]
    """The decoded, verified JWS protected header."""


def b64url_decode(data: str) -> bytes:
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

    Raises :class:`SignatureError` if the JWK is not an EC P-256 key.
    """
    if jwk.get("kty") != "EC":
        raise SignatureError(f"unsupported JWK kty {jwk.get('kty')!r}, expected 'EC'")
    if jwk.get("crv") != "P-256":
        raise SignatureError(
            f"unsupported JWK crv {jwk.get('crv')!r}, expected 'P-256'"
        )
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
    keys = jwks.get("keys")
    if not isinstance(keys, list) or not keys:
        raise SignatureError("JWKS has no 'keys' array")
    return keys


def _select_jwk(
    jwks: Mapping[str, Any], kid: Optional[str]
) -> Mapping[str, Any]:
    """Pick the JWK to verify with.

    If the header named a ``kid`` we require an exact match. Otherwise, if the
    set has exactly one usable EC key we use it; an ambiguous set without a
    ``kid`` is rejected rather than guessed.
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
    raise SignatureError(
        "JWS header has no 'kid' and JWKS is ambiguous (multiple EC keys)"
    )


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


def _decode_header(header_b64: str) -> dict:
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


def _verify_embedded(
    card: Mapping[str, Any], jws: str, jwks: Mapping[str, Any]
) -> VerifiedCard:
    parts = jws.split(".")
    if len(parts) != 3:
        raise SignatureError(
            "embedded card signature must be a detached compact JWS "
            "(header..signature)"
        )
    header_b64, payload_b64, sig_b64 = parts

    header = _decode_header(header_b64)
    kid = header.get("kid")
    jwk = _select_jwk(jwks, kid)
    public_key = jwk_to_public_key(jwk)

    # Reconstruct the signed payload: JCS of the card without its signature field.
    stripped = {k: v for k, v in card.items() if k not in SIGNATURE_FIELDS}
    if payload_b64:
        # Some signers inline the payload instead of detaching it. If present, it
        # MUST equal the JCS canonicalization we expect; we never trust the
        # inlined bytes blindly.
        expected = _b64url_encode(jcs.canonicalize(stripped)).decode("ascii")
        if payload_b64 != expected:
            raise SignatureError(
                "inlined JWS payload does not match the card's JCS canonicalization"
            )
        payload_segment = payload_b64
    else:
        payload_segment = _b64url_encode(jcs.canonicalize(stripped)).decode("ascii")

    signing_input = f"{header_b64}.{payload_segment}".encode("ascii")
    signature = b64url_decode(sig_b64)
    _verify_es256(public_key, signing_input, signature)
    return VerifiedCard(payload=stripped, kid=kid, header=header)


def _verify_compact(jws: str, jwks: Mapping[str, Any]) -> VerifiedCard:
    parts = jws.split(".")
    if len(parts) != 3 or not parts[1]:
        raise SignatureError("compact JWS must have a non-empty payload segment")
    header_b64, payload_b64, sig_b64 = parts

    header = _decode_header(header_b64)
    kid = header.get("kid")
    jwk = _select_jwk(jwks, kid)
    public_key = jwk_to_public_key(jwk)

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = b64url_decode(sig_b64)
    _verify_es256(public_key, signing_input, signature)

    try:
        payload = json.loads(b64url_decode(payload_b64))
    except (ValueError, UnicodeDecodeError) as exc:
        raise SignatureError(f"invalid JWS payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise SignatureError("JWS payload is not a JSON object")
    return VerifiedCard(payload=payload, kid=kid, header=header)


def verify_card(card: Any, jwks: Mapping[str, Any]) -> VerifiedCard:
    """Verify an agent card's ES256 signature against ``jwks``.

    ``card`` may be:

    * a ``dict`` with an embedded ``signature``/``jws``/``proof`` field
      (detached-payload JWS over the JCS of the rest of the card), or
    * a compact JWS string ``header.payload.signature``.

    Returns a :class:`VerifiedCard` on success; raises :class:`SignatureError`
    on any failure (bad shape, wrong algorithm, unknown key, bad signature).
    """
    if isinstance(card, str):
        text = card.strip()
        if text.count(".") == 2 and "{" not in text:
            return _verify_compact(text, jwks)
        # A JSON string body: parse then treat as the dict form.
        try:
            card = json.loads(text)
        except ValueError as exc:
            raise SignatureError(f"card is neither compact JWS nor JSON: {exc}") from exc

    if not isinstance(card, Mapping):
        raise SignatureError(f"card must be a mapping or compact JWS, got {type(card)!r}")

    for field in SIGNATURE_FIELDS:
        value = card.get(field)
        if isinstance(value, str) and value:
            return _verify_embedded(card, value, jwks)
        if isinstance(value, Mapping):
            # A structured proof object, e.g. {"jws": "..."} or
            # {"signature": {"jws": "..."}}. Pull out the inner compact JWS.
            inner = value.get("jws") or value.get("signature") or value.get("value")
            if isinstance(inner, str) and inner:
                return _verify_embedded(card, inner, jwks)

    raise SignatureError(
        "card has no signature field "
        f"(looked for {', '.join(SIGNATURE_FIELDS)})"
    )
