"""Tests for ES256 JWS agent-card verification (real crypto, mocked JWKS)."""

from __future__ import annotations

import base64
import json

import pytest

from oabp_a2a import SignatureError, verify_card
from oabp_a2a import signing


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


# --------------------------------------------------------------------------- #
# positive paths
# --------------------------------------------------------------------------- #
def test_embedded_signature_verifies(signer, sample_card):
    signed = signer.sign_card_embedded(sample_card)
    result = verify_card(signed, signer.jwks())
    assert result.kid == signer.kid
    assert result.header["alg"] == "ES256"
    # signature field stripped from the verified payload
    assert "signature" not in result.payload
    assert result.payload["name"] == sample_card["name"]


def test_embedded_without_kid_uses_sole_key(signer, sample_card):
    signed = signer.sign_card_embedded(sample_card, include_kid=False)
    result = verify_card(signed, signer.jwks())
    assert result.kid is None
    assert result.payload["version"] == sample_card["version"]


def test_compact_jws_card_verifies(signer, sample_card):
    jws = signer.sign_card_compact(sample_card)
    result = verify_card(jws, signer.jwks())
    assert result.payload["name"] == sample_card["name"]
    assert result.kid == signer.kid


def test_structured_proof_object(signer, sample_card):
    # Some signers wrap the JWS as {"proof": {"jws": "<header..sig>"}}.
    signed = signer.sign_card_embedded(sample_card)
    jws = signed.pop("signature")
    signed["proof"] = {"jws": jws}
    result = verify_card(signed, signer.jwks())
    assert result.payload["name"] == sample_card["name"]


# --------------------------------------------------------------------------- #
# tamper / negative paths
# --------------------------------------------------------------------------- #
def test_tampered_payload_is_rejected(signer, sample_card):
    signed = signer.sign_card_embedded(sample_card)
    signed["name"] = "Evil Agent"  # mutate after signing
    with pytest.raises(SignatureError):
        verify_card(signed, signer.jwks())


def test_wrong_key_is_rejected(signer, other_signer, sample_card):
    signed = signer.sign_card_embedded(sample_card)
    # Verify against a JWKS that advertises a *different* key under the same kid.
    with pytest.raises(SignatureError):
        verify_card(signed, other_signer.jwks())


def test_unknown_kid_is_rejected(signer, sample_card):
    signed = signer.sign_card_embedded(sample_card)
    jwks = signer.jwks()
    jwks["keys"][0]["kid"] = "some-other-kid"
    with pytest.raises(SignatureError, match="kid"):
        verify_card(signed, jwks)


def test_missing_signature_field(signer, sample_card):
    with pytest.raises(SignatureError, match="no signature field"):
        verify_card(dict(sample_card), signer.jwks())


def test_non_es256_alg_rejected(signer, sample_card):
    # Forge a header that claims a different alg; signature bytes irrelevant.
    header = _b64url(json.dumps({"alg": "RS256", "kid": signer.kid}).encode())
    sig = _b64url(b"\x00" * 64)
    forged = dict(sample_card)
    forged["signature"] = f"{header}..{sig}"
    with pytest.raises(SignatureError, match="alg"):
        verify_card(forged, signer.jwks())


def test_alg_none_downgrade_rejected(signer, sample_card):
    # Classic JWS "alg: none" downgrade attempt must be refused.
    header = _b64url(json.dumps({"alg": "none"}).encode())
    forged = dict(sample_card)
    forged["signature"] = f"{header}.."
    with pytest.raises(SignatureError):
        verify_card(forged, signer.jwks())


def test_empty_jwks_rejected(signer, sample_card):
    signed = signer.sign_card_embedded(sample_card)
    with pytest.raises(SignatureError, match="keys"):
        verify_card(signed, {"keys": []})


def test_ambiguous_jwks_without_kid_rejected(signer, other_signer, sample_card):
    signed = signer.sign_card_embedded(sample_card, include_kid=False)
    jwks = {"keys": [signer.jwk(), other_signer.jwk()]}
    # two EC keys, no kid in header -> ambiguous
    jwks["keys"][1]["kid"] = "second"
    with pytest.raises(SignatureError, match="ambiguous"):
        verify_card(signed, jwks)


def test_non_ec_jwk_rejected(signer, sample_card):
    signed = signer.sign_card_embedded(sample_card)
    jwks = signer.jwks()
    jwks["keys"][0]["kty"] = "RSA"
    with pytest.raises(SignatureError, match="kty"):
        verify_card(signed, jwks)


def test_bad_signature_length_rejected(signer, sample_card):
    signed = signer.sign_card_embedded(sample_card)
    header, _, _ = signed["signature"].split(".")
    signed["signature"] = f"{header}..{_b64url(b'short')}"
    with pytest.raises(SignatureError, match="bytes"):
        verify_card(signed, signer.jwks())


def test_inlined_payload_must_match_jcs(signer, sample_card):
    # If a signer inlines the payload, the verifier checks it equals our JCS.
    signed = signer.sign_card_embedded(sample_card)
    header, _, sig = signed["signature"].split(".")
    wrong_payload = _b64url(b'{"name":"different"}')
    signed["signature"] = f"{header}.{wrong_payload}.{sig}"
    with pytest.raises(SignatureError, match="JCS"):
        verify_card(signed, signer.jwks())


def test_jwk_to_public_key_off_curve():
    with pytest.raises(SignatureError):
        signing.jwk_to_public_key(
            {"kty": "EC", "crv": "P-256", "x": _b64url(b"\x01" * 32), "y": _b64url(b"\x02" * 32)}
        )
