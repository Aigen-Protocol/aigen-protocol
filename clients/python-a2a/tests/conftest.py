"""Shared test fixtures: an offline fake transport and a real ES256 card signer.

No network is touched. The fake session matches (METHOD, PATH) against registered
handlers and returns canned ``requests.Response`` objects. The signer fixtures
mint a genuine P-256 key, publish it as a JWKS, and sign agent cards with real
ES256 over the JCS canonicalization — so the verification tests exercise the
actual cryptography, not a stub.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Tuple
from urllib.parse import urlparse

import pytest
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

# Make the package importable when tests are run from the repo root without an
# editable install.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oabp_a2a import jcs  # noqa: E402

BASE_URL = "https://oabp.test"


# --------------------------------------------------------------------------- #
# fake HTTP transport
# --------------------------------------------------------------------------- #
Handler = Callable[["RecordedRequest"], "MockResponse"]


@dataclass
class RecordedRequest:
    method: str
    path: str
    url: str
    json: Any
    params: Optional[Mapping[str, Any]]
    headers: Mapping[str, str]


@dataclass
class MockResponse:
    status_code: int = 200
    json_body: Any = None
    text_body: Optional[str] = None

    def build(self) -> requests.Response:
        resp = requests.Response()
        resp.status_code = self.status_code
        if self.text_body is not None:
            body = self.text_body.encode("utf-8")
        elif self.json_body is not None:
            body = json.dumps(self.json_body).encode("utf-8")
        else:
            body = b""
        resp._content = body
        resp.headers["Content-Type"] = "application/json"
        resp.encoding = "utf-8"
        return resp


class FakeSession(requests.Session):
    """A ``requests.Session`` whose ``request`` is fully in-memory."""

    def __init__(self) -> None:
        super().__init__()
        self._routes: Dict[Tuple[str, str], Handler] = {}
        self.calls: list[RecordedRequest] = []

    def route(self, method: str, path: str, handler: Handler) -> None:
        self._routes[(method.upper(), path)] = handler

    def route_json(self, method: str, path: str, body: Any, status: int = 200) -> None:
        self.route(method, path, lambda req: MockResponse(status, json_body=body))

    # requests.Session.request signature (subset we use)
    def request(self, method, url, **kwargs):  # type: ignore[override]
        parsed = urlparse(url)
        path = parsed.path
        rec = RecordedRequest(
            method=method.upper(),
            path=path,
            url=url,
            json=kwargs.get("json"),
            params=kwargs.get("params"),
            headers=dict(self.headers),
        )
        self.calls.append(rec)
        handler = self._routes.get((method.upper(), path))
        if handler is None:
            return MockResponse(404, json_body={"error": f"no route {method} {path}"}).build()
        return handler(rec).build()


@pytest.fixture
def session() -> FakeSession:
    return FakeSession()


# --------------------------------------------------------------------------- #
# ES256 signer fixtures (real crypto)
# --------------------------------------------------------------------------- #
def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


@dataclass
class CardSigner:
    """Real ES256 signer used to produce signed cards and a matching JWKS."""

    private_key: ec.EllipticCurvePrivateKey
    kid: str

    def jwk(self) -> Dict[str, Any]:
        nums = self.private_key.public_key().public_numbers()
        x = nums.x.to_bytes(32, "big")
        y = nums.y.to_bytes(32, "big")
        return {
            "kty": "EC",
            "crv": "P-256",
            "x": _b64url(x),
            "y": _b64url(y),
            "kid": self.kid,
            "alg": "ES256",
            "use": "sig",
        }

    def jwks(self) -> Dict[str, Any]:
        return {"keys": [self.jwk()]}

    def _sign(self, signing_input: bytes) -> str:
        der = self.private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
        return _b64url(raw)

    def sign_card_embedded(self, card: Mapping[str, Any], *, include_kid: bool = True) -> Dict[str, Any]:
        """Return ``card`` plus an embedded detached-JWS ``signature`` field."""
        header: Dict[str, Any] = {"alg": "ES256", "typ": "JWT"}
        if include_kid:
            header["kid"] = self.kid
        header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_b64 = _b64url(jcs.canonicalize(dict(card)))
        sig_b64 = self._sign(f"{header_b64}.{payload_b64}".encode("ascii"))
        # Detached payload form: header..signature
        out = dict(card)
        out["signature"] = f"{header_b64}..{sig_b64}"
        return out

    def sign_card_compact(self, card: Mapping[str, Any]) -> str:
        """Return a full compact JWS whose payload is the card JSON."""
        header = {"alg": "ES256", "typ": "JWT", "kid": self.kid}
        header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_b64 = _b64url(json.dumps(dict(card), separators=(",", ":")).encode("utf-8"))
        sig_b64 = self._sign(f"{header_b64}.{payload_b64}".encode("ascii"))
        return f"{header_b64}.{payload_b64}.{sig_b64}"


@pytest.fixture
def signer() -> CardSigner:
    return CardSigner(ec.generate_private_key(ec.SECP256R1()), kid="oabp-key-1")


@pytest.fixture
def other_signer() -> CardSigner:
    """A different key, used to prove a foreign signature is rejected."""
    return CardSigner(ec.generate_private_key(ec.SECP256R1()), kid="oabp-key-1")


@pytest.fixture
def sample_card() -> Dict[str, Any]:
    return {
        "name": "OABP Reference Agent",
        "description": "Agent that lists and resolves OABP missions.",
        "url": f"{BASE_URL}/api/a2a",
        "version": "1.0.0",
        "protocolVersion": "0.2.0",
        "preferredTransport": "JSONRPC",
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": "list-missions",
                "name": "List missions",
                "description": "Enumerate open OABP missions.",
                "tags": ["oabp", "missions"],
            }
        ],
    }
