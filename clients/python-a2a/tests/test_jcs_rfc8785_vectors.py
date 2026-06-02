"""Conformance tests against the official RFC 8785 Appendix B example.

These pin the canonicalizer to the exact bytes the spec mandates, which is what
makes our signature verification interoperable with the OABP signer (and any
other RFC 8785 signer).

The Appendix B input string is constructed from explicit code points (via
``chr``) so this source file contains no literal control characters and there is
zero ambiguity about which bytes are being canonicalized.
"""

from __future__ import annotations

from oabp_a2a import jcs

# RFC 8785 Appendix B "string" member, code point by code point:
#   U+20AC EURO SIGN, '$', U+000F (control), U+000A LINE FEED,
#   'A', "'", 'B', '"', '\\', '"', '/'
_APPENDIX_B_STRING = (
    chr(0x20AC) + "$" + chr(0x0F) + chr(0x0A) + "A" + "'" + "B" + '"' + "\\" + '"' + "/"
)

# Expected canonical serialization of that string token (what JCS must emit),
# built the same way to avoid any literal control/escape ambiguity in source.
_APPENDIX_B_STRING_CANON = (
    '"' + chr(0x20AC) + "$" + "\\u000f" + "\\n" + "A'B" + '\\"' + "\\\\" + '\\"' + '/"'
)


def test_appendix_b_string_token():
    assert jcs.dumps(_APPENDIX_B_STRING) == _APPENDIX_B_STRING_CANON


def test_rfc8785_appendix_b_example():
    data = {
        "numbers": [
            333333333.33333329,
            1e30,
            4.50,
            2e-3,
            0.000000000000000000000000001,
        ],
        "string": _APPENDIX_B_STRING,
        "literals": [None, True, False],
    }
    expected = (
        '{"literals":[null,true,false],'
        '"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27],'
        '"string":' + _APPENDIX_B_STRING_CANON + "}"
    )
    assert jcs.dumps(data) == expected
    assert jcs.canonicalize(data) == expected.encode("utf-8")


def test_rfc8785_number_table():
    cases = {
        0: "0",
        -0.0: "0",
        1: "1",
        1.0: "1",
        -1.5: "-1.5",
        1e30: "1e+30",
        2e-3: "0.002",
        333333333.33333329: "333333333.3333333",
        1e-27: "1e-27",
        100000000000000000000: "100000000000000000000",
    }
    for value, expected in cases.items():
        assert jcs.dumps(value) == expected, f"{value!r} -> {jcs.dumps(value)!r}"
