"""RFC 8785 JSON Canonicalization Scheme (JCS).

The OABP agent card is signed over the *canonical* serialization of its
payload, so the verifier must reproduce byte-for-byte the same bytes the
signer hashed. RFC 8785 pins down every degree of freedom in JSON
serialization (key ordering, number formatting, whitespace, string escaping)
so two independent implementations agree.

This is a dependency-free implementation covering the data model that JSON
documents (and therefore agent cards) actually use: ``dict``, ``list``,
``str``, ``bool``, ``int``, ``float`` and ``None``.

References
----------
* RFC 8785 - JSON Canonicalization Scheme (JCS)
* ECMAScript ``Number.prototype.toString`` (number serialization)
"""

from __future__ import annotations

import math
from typing import Any

__all__ = ["canonicalize", "dumps"]

# Characters that MUST be escaped per RFC 8785 section 3.2.2.2 (which defers to
# RFC 8259). The two-character short escapes are mandated for these code points.
_SHORT_ESCAPES = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}


def _escape_string(value: str) -> str:
    """Serialize a Python ``str`` as a canonical JSON string token.

    Per RFC 8785, only the mandatory escapes are used; every other character
    (including non-ASCII) is emitted literally as UTF-8 (the surrounding
    serializer encodes to UTF-8 at the end). Control characters below 0x20 that
    lack a short escape use the ``\\u00XX`` form, lowercase hex.
    """
    out = ['"']
    for ch in value:
        cp = ord(ch)
        short = _SHORT_ESCAPES.get(cp)
        if short is not None:
            out.append(short)
        elif cp < 0x20:
            out.append("\\u%04x" % cp)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _serialize_number(value: float | int) -> str:
    """Serialize a number using the ECMAScript ``Number`` algorithm.

    RFC 8785 requires numbers to be formatted exactly as ECMAScript would. For
    the integer-valued range that JSON documents realistically use this reduces
    to a plain integer literal; otherwise we rely on Python's shortest
    round-trippable ``repr`` and normalize the exponent form to match V8.
    """
    if isinstance(value, bool):  # bool is a subclass of int; guard first
        raise TypeError("bool is not a JSON number")

    if isinstance(value, int):
        return str(value)

    if not math.isfinite(value):
        # JSON has no representation for NaN/Infinity; signing such a card is a
        # programming error rather than something to silently coerce.
        raise ValueError("NaN and Infinity cannot be canonicalized")

    if value == 0:
        # Canonical form folds -0.0 to "0".
        return "0"

    if value == int(value) and abs(value) < 1e21:
        # Integral floats render without a fractional part ("1", not "1.0").
        return str(int(value))

    # Python's repr() already yields the shortest string that round-trips to the
    # same IEEE-754 double, which matches ECMAScript's requirement. We only have
    # to translate Python's exponent spelling ("1e-07") to ECMAScript's
    # ("1e-7": no leading zero in the exponent, explicit '+' for positive).
    text = repr(value)
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


def _serialize(value: Any, out: list[str]) -> None:
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, str):
        out.append(_escape_string(value))
    elif isinstance(value, (int, float)):
        out.append(_serialize_number(value))
    elif isinstance(value, dict):
        out.append("{")
        first = True
        # JSON object keys are always strings; reject anything else up front so a
        # non-string key fails with a clear TypeError rather than deep inside the
        # sort.
        for key in value:
            if not isinstance(key, str):
                raise TypeError(f"object keys must be strings, got {type(key)!r}")
        # RFC 8785 section 3.2.3: members are sorted by the UTF-16 code units of
        # their keys. For the Basic Multilingual Plane (everything an agent card
        # uses) this is identical to ordering by Unicode code point, which is
        # what Python string comparison gives.
        for key in sorted(value.keys(), key=_utf16_sort_key):
            if not first:
                out.append(",")
            first = False
            out.append(_escape_string(key))
            out.append(":")
            _serialize(value[key], out)
        out.append("}")
    elif isinstance(value, (list, tuple)):
        out.append("[")
        first = True
        for item in value:
            if not first:
                out.append(",")
            first = False
            _serialize(item, out)
        out.append("]")
    else:
        raise TypeError(f"object of type {type(value)!r} is not JSON serializable")


def _utf16_sort_key(key: str):
    """Return a sort key matching RFC 8785's UTF-16 code-unit ordering.

    Encoding to UTF-16 big-endian and comparing the byte sequence reproduces the
    code-unit comparison the spec mandates, including correct handling of
    surrogate pairs for code points above the BMP.
    """
    return key.encode("utf-16-be")


def dumps(value: Any) -> str:
    """Return the canonical JSON text (a ``str``) for ``value``."""
    out: list[str] = []
    _serialize(value, out)
    return "".join(out)


def canonicalize(value: Any) -> bytes:
    """Return the canonical UTF-8 bytes for ``value`` per RFC 8785."""
    return dumps(value).encode("utf-8")
