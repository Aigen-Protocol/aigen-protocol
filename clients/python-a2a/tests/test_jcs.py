"""Tests for the RFC 8785 JSON Canonicalization implementation."""

from __future__ import annotations

import pytest

from oabp_a2a import jcs


def test_object_keys_are_sorted():
    assert jcs.dumps({"b": 1, "a": 2, "c": 3}) == '{"a":2,"b":1,"c":3}'


def test_nested_sorting_and_no_whitespace():
    value = {"z": {"y": 1, "x": 2}, "a": [3, {"m": 1, "k": 2}]}
    assert jcs.dumps(value) == '{"a":[3,{"k":2,"m":1}],"z":{"x":2,"y":1}}'


def test_unicode_kept_literal_and_sorted_by_code_unit():
    # RFC 8785 appendix-style check: emoji and accented chars stay literal.
    value = {"é": 1, "a": 2, "€": 3}
    out = jcs.dumps(value)
    assert out == '{"a":2,"é":1,"€":3}'
    # And the bytes are UTF-8.
    assert jcs.canonicalize(value).decode("utf-8") == out


def test_string_escaping():
    assert jcs.dumps('he said "hi"\n\t\\') == '"he said \\"hi\\"\\n\\t\\\\"'
    # Control char without a short escape uses \u00xx lowercase.
    assert jcs.dumps("\x01") == '"\\u0001"'


def test_integers_and_floats():
    assert jcs.dumps(0) == "0"
    assert jcs.dumps(-0.0) == "0"
    assert jcs.dumps(1.0) == "1"
    assert jcs.dumps(1.5) == "1.5"
    assert jcs.dumps(1000000000000000000000) == "1000000000000000000000"


def test_float_exponent_normalized_to_ecmascript():
    # Python repr is "1e-07"; ECMAScript / RFC 8785 want "1e-7".
    assert jcs.dumps(1e-7) == "1e-7"
    assert jcs.dumps(1e21) == "1e+21"


def test_bool_and_null():
    assert jcs.dumps(True) == "true"
    assert jcs.dumps(False) == "false"
    assert jcs.dumps(None) == "null"
    assert jcs.dumps({"a": True, "b": None}) == '{"a":true,"b":null}'


def test_canonical_is_order_independent():
    a = {"x": 1, "y": {"p": 2, "q": 3}}
    b = {"y": {"q": 3, "p": 2}, "x": 1}
    assert jcs.canonicalize(a) == jcs.canonicalize(b)


def test_rejects_nan_and_infinity():
    with pytest.raises(ValueError):
        jcs.dumps(float("nan"))
    with pytest.raises(ValueError):
        jcs.dumps(float("inf"))


def test_rejects_non_string_keys():
    with pytest.raises(TypeError):
        jcs.dumps({1: "x"})
