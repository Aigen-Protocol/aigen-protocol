#!/usr/bin/env python3
"""Test suite for ``oabp_mission_lint``.

Pure-stdlib ``unittest`` (no pytest, no network). The suite is self-contained:
network-touching helpers (``fetch_min_reward_aigen``) are exercised via the
``--no-network`` / ``--min-reward`` paths or monkeypatched, so nothing here
hits the live OABP server.

Run with either::

    python -m unittest discover -s tests
    python tests/test_oabp_mission_lint.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout
from typing import Any, Dict, List

# Make the single-file module importable when run from anywhere.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import oabp_mission_lint as lint  # noqa: E402


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def clean_oracle_mission() -> Dict[str, Any]:
    return {
        "creator_agent_id": "agent-genesis-001",
        "title": "Publish an idiomatic Go client for the OABP mission API",
        "description": (
            "Build a public GitHub repository containing a Go client for the "
            "OABP mission API (list/get/create/submit). The repo must be "
            "non-empty and its primary language must be Go. Submit the repo URL."
        ),
        "reward_amount": 250,
        "reward_currency": "AIGEN",
        "verification_type": "oracle",
        "verification_params": {
            "oracle_description": (
                "Verify the submitted GitHub repository exists, is non-empty, "
                "and its primary language is Go (golang deliverable)."
            )
        },
        "deadline_hours": 72,
    }


def clean_fvm_mission() -> Dict[str, Any]:
    return {
        "creator_agent_id": "agent-x",
        "title": "Provide the SHA-256 of the genesis manifest",
        "description": (
            "Submit the lowercase hex SHA-256 digest of the published genesis "
            "manifest file. The proof must be exactly 64 hex characters."
        ),
        "reward_amount": 50,
        "reward_currency": "AIGEN",
        "verification_type": "first_valid_match",
        "verification_params": {"regex": "^[0-9a-f]{64}$"},
        "deadline_hours": 24,
    }


def broken_mission() -> Dict[str, Any]:
    """Exactly four independent defects: empty title, bad currency,
    sub-minimum reward, uncompilable regex."""
    return {
        "creator_agent_id": "agent-test",
        "title": "",                       # ERROR: empty
        "description": "Please do the thing quickly, thanks a lot here.",
        "reward_amount": 3,                # ERROR: below the 10 AIGEN floor
        "reward_currency": "DOGE",         # ERROR: not AIGEN/USDC
        "verification_type": "first_valid_match",
        "verification_params": {"regex": "(unclosed[group"},  # ERROR: bad regex
        "deadline_hours": 48,
    }


def lint_mission(mission: Dict[str, Any], **kw: Any) -> List[lint.Finding]:
    """Lint a mission dict offline with the fallback minimum reward."""
    kw.setdefault("min_reward_aigen", lint.FALLBACK_MIN_REWARD_AIGEN)
    kw.setdefault("min_reward_source", "fallback")
    linter = lint.MissionLinter(**kw)
    return linter.lint(lint.normalize_mission(mission))


def codes(findings: List[lint.Finding], severity: str = None) -> List[str]:
    out = []
    for f in findings:
        if severity is None or f.severity.value == severity:
            out.append(f.code)
    return out


def errors(findings: List[lint.Finding]) -> List[str]:
    return codes(findings, "ERROR")


def warns(findings: List[lint.Finding]) -> List[str]:
    return codes(findings, "WARN")


# --------------------------------------------------------------------------- #
# Acceptance: clean missions pass; broken yields one ERROR per defect
# --------------------------------------------------------------------------- #
class TestAcceptance(unittest.TestCase):
    def test_clean_oracle_mission_has_no_errors(self):
        findings = lint_mission(clean_oracle_mission())
        self.assertEqual(errors(findings), [], f"unexpected errors: {errors(findings)}")
        self.assertFalse(lint.has_errors(findings))

    def test_clean_fvm_mission_has_no_errors(self):
        findings = lint_mission(clean_fvm_mission())
        self.assertEqual(errors(findings), [], f"unexpected errors: {errors(findings)}")
        self.assertFalse(lint.has_errors(findings))

    def test_broken_mission_one_error_per_defect(self):
        findings = lint_mission(broken_mission())
        err_codes = set(errors(findings))
        self.assertIn("title.empty", err_codes)
        self.assertIn("reward.currency.invalid", err_codes)
        self.assertIn("reward.amount.below_min", err_codes)
        self.assertIn("fvm.regex.uncompilable", err_codes)
        # Exactly four defects -> exactly four ERRORs (no double counting).
        self.assertEqual(
            len(errors(findings)), 4, f"errors were: {errors(findings)}"
        )
        self.assertTrue(lint.has_errors(findings))


# --------------------------------------------------------------------------- #
# Required fields
# --------------------------------------------------------------------------- #
class TestRequiredFields(unittest.TestCase):
    def test_each_missing_required_field_is_an_error(self):
        base = clean_fvm_mission()
        for fld in lint.MissionLinter.REQUIRED_FIELDS:
            m = dict(base)
            m.pop(fld, None)
            findings = lint_mission(m)
            self.assertIn(
                "required.missing",
                errors(findings),
                f"missing {fld!r} should raise required.missing",
            )
            # The finding should point at the missing field.
            missing = [
                f for f in findings
                if f.code == "required.missing" and f.field == fld
            ]
            self.assertTrue(missing, f"no required.missing finding for {fld!r}")

    def test_null_required_field_is_an_error(self):
        m = clean_fvm_mission()
        m["title"] = None
        findings = lint_mission(m)
        self.assertIn("required.missing", errors(findings))

    def test_missing_creator_is_warning_not_error(self):
        m = clean_fvm_mission()
        m.pop("creator_agent_id")
        findings = lint_mission(m)
        self.assertNotIn("creator_agent_id.missing", errors(findings))
        self.assertIn("creator_agent_id.missing", warns(findings))


# --------------------------------------------------------------------------- #
# Currency
# --------------------------------------------------------------------------- #
class TestCurrency(unittest.TestCase):
    def test_aigen_ok(self):
        m = clean_fvm_mission()
        m["reward_currency"] = "AIGEN"
        self.assertNotIn("reward.currency.invalid", errors(lint_mission(m)))

    def test_usdc_ok(self):
        m = clean_fvm_mission()
        m["reward_currency"] = "USDC"
        self.assertNotIn("reward.currency.invalid", errors(lint_mission(m)))

    def test_unknown_currency_error(self):
        m = clean_fvm_mission()
        m["reward_currency"] = "ETH"
        self.assertIn("reward.currency.invalid", errors(lint_mission(m)))

    def test_lowercase_currency_error(self):
        m = clean_fvm_mission()
        m["reward_currency"] = "aigen"  # case-sensitive per protocol enum
        self.assertIn("reward.currency.invalid", errors(lint_mission(m)))


# --------------------------------------------------------------------------- #
# Verification type
# --------------------------------------------------------------------------- #
class TestVerificationType(unittest.TestCase):
    def test_all_four_allowed_types_accepted(self):
        for vt in lint.ALLOWED_VERIFICATION_TYPES:
            m = clean_fvm_mission()
            m["verification_type"] = vt
            # Give peer_vote / creator_judges / oracle valid params so the only
            # thing under test is the type acceptance itself.
            if vt == "oracle":
                m["verification_params"] = {
                    "oracle_description": "GitHub repo deliverable in python."
                }
            elif vt in ("peer_vote", "creator_judges"):
                m["verification_params"] = {}
            findings = lint_mission(m)
            self.assertNotIn(
                "verification.type.invalid",
                errors(findings),
                f"{vt!r} should be a valid verification_type",
            )

    def test_invalid_type_error(self):
        m = clean_fvm_mission()
        m["verification_type"] = "vibes"
        self.assertIn("verification.type.invalid", errors(lint_mission(m)))

    def test_subjective_types_emit_info(self):
        for vt in ("peer_vote", "creator_judges"):
            m = clean_fvm_mission()
            m["verification_type"] = vt
            m["verification_params"] = {}
            findings = lint_mission(m)
            self.assertIn("verification.type.subjective", codes(findings, "INFO"))
            self.assertEqual(errors(findings), [])


# --------------------------------------------------------------------------- #
# Reward amount + minimum floor
# --------------------------------------------------------------------------- #
class TestRewardAmount(unittest.TestCase):
    def test_below_min_aigen_error(self):
        m = clean_fvm_mission()
        m["reward_amount"] = 9
        self.assertIn("reward.amount.below_min", errors(lint_mission(m)))

    def test_at_min_aigen_ok(self):
        m = clean_fvm_mission()
        m["reward_amount"] = lint.FALLBACK_MIN_REWARD_AIGEN
        self.assertNotIn("reward.amount.below_min", errors(lint_mission(m)))

    def test_zero_reward_error(self):
        m = clean_fvm_mission()
        m["reward_amount"] = 0
        self.assertIn("reward.amount.nonpositive", errors(lint_mission(m)))

    def test_negative_reward_error(self):
        m = clean_fvm_mission()
        m["reward_amount"] = -5
        self.assertIn("reward.amount.nonpositive", errors(lint_mission(m)))

    def test_non_numeric_reward_error(self):
        m = clean_fvm_mission()
        m["reward_amount"] = "lots"
        self.assertIn("reward.amount.not_numeric", errors(lint_mission(m)))

    def test_usdc_skips_aigen_floor(self):
        m = clean_fvm_mission()
        m["reward_currency"] = "USDC"
        m["reward_amount"] = 1  # below AIGEN floor but USDC, so no floor error
        findings = lint_mission(m)
        self.assertNotIn("reward.amount.below_min", errors(findings))
        self.assertIn("reward.amount.usdc", codes(findings, "INFO"))

    def test_custom_min_reward_override(self):
        m = clean_fvm_mission()
        m["reward_amount"] = 50
        findings = lint_mission(m, min_reward_aigen=100, min_reward_source="override")
        self.assertIn("reward.amount.below_min", errors(findings))


# --------------------------------------------------------------------------- #
# Deadline
# --------------------------------------------------------------------------- #
class TestDeadline(unittest.TestCase):
    def test_nonpositive_deadline_error(self):
        for bad in (0, -1, -100.5):
            m = clean_fvm_mission()
            m["deadline_hours"] = bad
            self.assertIn(
                "deadline.nonpositive", errors(lint_mission(m)), f"hours={bad}"
            )

    def test_non_numeric_deadline_error(self):
        m = clean_fvm_mission()
        m["deadline_hours"] = "soon"
        self.assertIn("deadline.not_numeric", errors(lint_mission(m)))

    def test_short_deadline_warn(self):
        m = clean_fvm_mission()
        m["deadline_hours"] = 0.25
        findings = lint_mission(m)
        self.assertIn("deadline.too_short", warns(findings))
        self.assertEqual(errors(findings), [])

    def test_huge_deadline_warn(self):
        m = clean_fvm_mission()
        m["deadline_hours"] = lint.DEADLINE_HOURS_WARN_LONG + 1000
        findings = lint_mission(m)
        self.assertIn("deadline.too_long", warns(findings))

    def test_live_absolute_deadline_in_past_warn(self):
        # A normalized live mission stores absolute unix in _deadline_unix.
        m = clean_fvm_mission()
        m.pop("deadline_hours")
        m["deadline"] = 1  # 1970 -> in the past
        findings = lint_mission(m)
        self.assertIn("deadline.in_past", warns(findings))


# --------------------------------------------------------------------------- #
# Title / description bounds
# --------------------------------------------------------------------------- #
class TestTextBounds(unittest.TestCase):
    def test_empty_title_error(self):
        m = clean_fvm_mission()
        m["title"] = "   "
        self.assertIn("title.empty", errors(lint_mission(m)))

    def test_empty_description_error(self):
        m = clean_fvm_mission()
        m["description"] = ""
        self.assertIn("description.empty", errors(lint_mission(m)))

    def test_short_title_warn(self):
        m = clean_fvm_mission()
        m["title"] = "hi"
        findings = lint_mission(m)
        self.assertIn("title.too_short", warns(findings))
        self.assertEqual(errors(findings), [])

    def test_long_title_warn(self):
        m = clean_fvm_mission()
        m["title"] = "x" * (lint.TITLE_MAX_LEN + 5)
        self.assertIn("title.too_long", warns(lint_mission(m)))

    def test_non_string_title_error(self):
        m = clean_fvm_mission()
        m["title"] = 12345
        self.assertIn("title.not_string", errors(lint_mission(m)))


# --------------------------------------------------------------------------- #
# first_valid_match params
# --------------------------------------------------------------------------- #
class TestFirstValidMatch(unittest.TestCase):
    def test_missing_regex_error(self):
        m = clean_fvm_mission()
        m["verification_params"] = {}
        self.assertIn("fvm.regex.missing", errors(lint_mission(m)))

    def test_empty_regex_error(self):
        m = clean_fvm_mission()
        m["verification_params"] = {"regex": ""}
        self.assertIn("fvm.regex.empty", errors(lint_mission(m)))

    def test_uncompilable_regex_error(self):
        m = clean_fvm_mission()
        m["verification_params"] = {"regex": "([a-z"}
        self.assertIn("fvm.regex.uncompilable", errors(lint_mission(m)))

    def test_non_string_regex_error(self):
        m = clean_fvm_mission()
        m["verification_params"] = {"regex": 42}
        self.assertIn("fvm.regex.not_string", errors(lint_mission(m)))

    def test_good_anchored_regex_clean(self):
        m = clean_fvm_mission()
        m["verification_params"] = {"regex": "^[0-9a-f]{64}$"}
        findings = lint_mission(m)
        self.assertEqual(errors(findings), [])
        self.assertNotIn("fvm.regex.matches_empty", warns(findings))
        self.assertNotIn("fvm.regex.no_probe_match", warns(findings))


class TestRegexEmptyMatchWarn(unittest.TestCase):
    """Acceptance: the empty-string-match WARN check is covered."""

    def test_dot_star_warns_matches_empty(self):
        for pat in (".*", "(.*)", "^.*$", ".*?", "[\\s\\S]*"):
            m = clean_fvm_mission()
            m["verification_params"] = {"regex": pat}
            findings = lint_mission(m)
            self.assertIn(
                "fvm.regex.matches_empty",
                warns(findings),
                f"{pat!r} should warn matches_empty",
            )
            # It is spammy, not unresolvable -> WARN, never ERROR.
            self.assertEqual(errors(findings), [], f"{pat!r} should not error")

    def test_optional_only_matches_empty(self):
        # 'a?' matches the empty string too.
        m = clean_fvm_mission()
        m["verification_params"] = {"regex": "a?"}
        self.assertIn("fvm.regex.matches_empty", warns(lint_mission(m)))

    def test_analyze_regex_flags_empty_directly(self):
        a = lint.analyze_regex(".*")
        self.assertTrue(a.compiles)
        self.assertTrue(a.matches_empty)
        self.assertFalse(a.provably_empty)


class TestRegexSatisfiability(unittest.TestCase):
    """Acceptance: the satisfiability check is covered."""

    def test_provably_empty_after_end_anchor(self):
        # '$x' requires content after end-of-string -> empty language.
        a = lint.analyze_regex("$x")
        self.assertTrue(a.compiles)
        self.assertTrue(a.provably_empty)
        m = clean_fvm_mission()
        m["verification_params"] = {"regex": "$x"}
        self.assertIn("fvm.regex.unsatisfiable", errors(lint_mission(m)))

    def test_provably_empty_negative_lookahead(self):
        a = lint.analyze_regex("(?!)abc")
        self.assertTrue(a.provably_empty)
        m = clean_fvm_mission()
        m["verification_params"] = {"regex": "(?!)abc"}
        self.assertIn("fvm.regex.unsatisfiable", errors(lint_mission(m)))

    def test_provably_empty_boundary_contradiction(self):
        a = lint.analyze_regex("foo\\b\\Bbar")
        self.assertTrue(a.provably_empty)

    def test_content_before_interior_start_anchor_is_empty(self):
        # 'a^b' requires 'a' before start-of-string -> empty language.
        a = lint.analyze_regex("a^b")
        self.assertTrue(a.provably_empty)

    def test_satisfiable_pattern_not_flagged_empty(self):
        for pat in ("^[0-9a-f]{64}$", "^PASS$", r"^\d{1,10}$", "^0x[a-fA-F0-9]{40}$"):
            a = lint.analyze_regex(pat)
            self.assertTrue(a.compiles, pat)
            self.assertFalse(a.provably_empty, f"{pat!r} wrongly flagged empty")

    def test_narrow_but_valid_pattern_no_error(self):
        # A pattern no probe string happens to match must NOT error — at most a
        # WARN (no_probe_match). This guards against false-positive blocking.
        m = clean_fvm_mission()
        # Very specific literal unlikely to be in the probe corpus.
        m["verification_params"] = {"regex": "^GENESIS-MANIFEST-7f3a9c-OK$"}
        findings = lint_mission(m)
        self.assertNotIn("fvm.regex.unsatisfiable", errors(findings))
        self.assertEqual(errors(findings), [])

    def test_probe_match_false_is_warn_only(self):
        # Construct a pattern that compiles, is not provably empty, but matches
        # nothing in the corpus: a long fixed literal.
        a = lint.analyze_regex("^this_exact_string_is_not_in_the_corpus_12345$")
        self.assertTrue(a.compiles)
        self.assertFalse(a.provably_empty)
        self.assertEqual(a.probe_matched, False)
        m = clean_fvm_mission()
        m["verification_params"] = {
            "regex": "^this_exact_string_is_not_in_the_corpus_12345$"
        }
        findings = lint_mission(m)
        self.assertIn("fvm.regex.no_probe_match", warns(findings))
        self.assertEqual(errors(findings), [])

    def test_anchoring_info_when_unanchored(self):
        m = clean_fvm_mission()
        m["verification_params"] = {"regex": "[0-9a-f]{64}"}  # not anchored
        findings = lint_mission(m)
        self.assertIn("fvm.regex.unanchored", codes(findings, "INFO"))


# --------------------------------------------------------------------------- #
# oracle params
# --------------------------------------------------------------------------- #
class TestOracle(unittest.TestCase):
    def _oracle_mission(self, desc: Any) -> Dict[str, Any]:
        m = clean_oracle_mission()
        if desc is None:
            m["verification_params"] = {}
        else:
            m["verification_params"] = {"oracle_description": desc}
        return m

    def test_missing_oracle_description_error(self):
        self.assertIn(
            "oracle.description.missing", errors(lint_mission(self._oracle_mission(None)))
        )

    def test_empty_oracle_description_error(self):
        self.assertIn(
            "oracle.description.missing",
            errors(lint_mission(self._oracle_mission("   "))),
        )

    def test_safety_review_with_token_and_chain_clean(self):
        desc = (
            "GoPlus token-security safety review for token "
            "0x1234567890abcdef1234567890abcdef12345678 on ethereum mainnet."
        )
        findings = lint_mission(self._oracle_mission(desc))
        self.assertEqual(errors(findings), [])
        self.assertNotIn("oracle.safety.no_token", warns(findings))
        self.assertNotIn("oracle.safety.no_chain", warns(findings))

    def test_safety_review_missing_token_warn(self):
        desc = "Run a GoPlus safety review on ethereum for this token."
        findings = lint_mission(self._oracle_mission(desc))
        self.assertIn("oracle.safety.no_token", warns(findings))

    def test_safety_review_missing_chain_warn(self):
        desc = (
            "GoPlus safety review for token "
            "0x1234567890abcdef1234567890abcdef12345678."
        )
        findings = lint_mission(self._oracle_mission(desc))
        self.assertIn("oracle.safety.no_chain", warns(findings))

    def test_repo_deliverable_with_language_clean(self):
        desc = "Verify the GitHub repository deliverable, primary language Rust."
        findings = lint_mission(self._oracle_mission(desc))
        self.assertEqual(errors(findings), [])
        self.assertNotIn("oracle.repo.no_language", codes(findings, "INFO"))

    def test_repo_deliverable_without_language_info(self):
        desc = "Verify the github.com repository exists and is non-empty."
        findings = lint_mission(self._oracle_mission(desc))
        self.assertIn("oracle.repo.no_language", codes(findings, "INFO"))

    def test_unrecognized_oracle_description_warn(self):
        # No 0x token, no chain, no repo/language/deliverable signal, no slug:
        # the built-in GoPlus/GitHub oracles can't resolve this.
        desc = "Confirm the work was done well and meets expectations overall."
        findings = lint_mission(self._oracle_mission(desc))
        self.assertIn("oracle.description.unrecognized", warns(findings))


# --------------------------------------------------------------------------- #
# Normalization (live shape -> create-body shape)
# --------------------------------------------------------------------------- #
class TestNormalization(unittest.TestCase):
    def test_nested_reward_object_is_flattened(self):
        live = {
            "id": "42",
            "title": "x",
            "reward": {"amount": 250, "currency": "AIGEN"},
        }
        out = lint.normalize_mission(live)
        self.assertEqual(out["reward_amount"], 250)
        self.assertEqual(out["reward_currency"], "AIGEN")

    def test_absolute_deadline_stashed(self):
        live = {"id": "42", "deadline": 1700000000}
        out = lint.normalize_mission(live)
        self.assertEqual(out["_deadline_unix"], 1700000000)
        self.assertNotIn("deadline_hours", out)

    def test_create_body_passthrough(self):
        m = clean_fvm_mission()
        out = lint.normalize_mission(m)
        self.assertEqual(out["reward_amount"], m["reward_amount"])
        self.assertEqual(out["reward_currency"], m["reward_currency"])

    def test_original_not_mutated(self):
        live = {"id": "42", "reward": {"amount": 5, "currency": "USDC"}}
        lint.normalize_mission(live)
        self.assertNotIn("reward_amount", live)


# --------------------------------------------------------------------------- #
# Line index (source pointers)
# --------------------------------------------------------------------------- #
class TestLineIndex(unittest.TestCase):
    def test_top_level_keys_located(self):
        src = (
            "{\n"
            '  "title": "hi",\n'
            '  "reward_currency": "AIGEN"\n'
            "}\n"
        )
        idx = lint.build_line_index(src)
        self.assertEqual(idx["title"], 2)
        self.assertEqual(idx["reward_currency"], 3)

    def test_nested_regex_dotted_path(self):
        src = (
            "{\n"
            '  "verification_params": {\n'
            '    "regex": "^x$"\n'
            "  }\n"
            "}\n"
        )
        idx = lint.build_line_index(src)
        self.assertEqual(idx["verification_params.regex"], 3)

    def test_empty_source_returns_empty_index(self):
        self.assertEqual(lint.build_line_index(None), {})
        self.assertEqual(lint.build_line_index(""), {})

    def test_findings_carry_line_numbers(self):
        src = json.dumps(broken_mission(), indent=2)
        idx = lint.build_line_index(src)
        linter = lint.MissionLinter(line_index=idx)
        findings = linter.lint(lint.normalize_mission(json.loads(src)))
        title_err = [f for f in findings if f.code == "title.empty"]
        self.assertTrue(title_err)
        self.assertIsNotNone(title_err[0].line)


# --------------------------------------------------------------------------- #
# Output rendering
# --------------------------------------------------------------------------- #
class TestRendering(unittest.TestCase):
    def test_json_output_is_valid_findings_array(self):
        findings = lint_mission(broken_mission())
        out = lint.render_json(findings, source_label="unit")
        payload = json.loads(out)  # must parse
        self.assertIn("findings", payload)
        self.assertIsInstance(payload["findings"], list)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["counts"]["ERROR"], 4)
        for f in payload["findings"]:
            self.assertIn("severity", f)
            self.assertIn("code", f)
            self.assertIn("message", f)
            self.assertIn("field", f)
            self.assertIn("line", f)
            self.assertIn(f["severity"], ("ERROR", "WARN", "INFO"))

    def test_json_clean_mission_ok_true_empty_findings_array(self):
        findings = lint_mission(clean_oracle_mission())
        payload = json.loads(lint.render_json(findings, source_label="unit"))
        self.assertTrue(payload["ok"])
        self.assertIsInstance(payload["findings"], list)
        self.assertEqual(payload["counts"]["ERROR"], 0)

    def test_text_output_contains_summary(self):
        findings = lint_mission(broken_mission())
        text = lint.render_text(findings, source_label="unit")
        self.assertIn("summary:", text)
        self.assertIn("FAIL", text)

    def test_text_clean_says_pass(self):
        findings = lint_mission(clean_oracle_mission())
        text = lint.render_text(findings, source_label="unit")
        self.assertIn("PASS", text)


# --------------------------------------------------------------------------- #
# CLI end-to-end (no network) via run()
# --------------------------------------------------------------------------- #
class TestCli(unittest.TestCase):
    def _write(self, name: str, mission: Dict[str, Any]) -> str:
        import tempfile

        fd, path = tempfile.mkstemp(prefix=name, suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(mission, fh, indent=2)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_run_clean_file_exit_zero(self):
        path = self._write("clean", clean_oracle_mission())
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = lint.run(["--file", path, "--no-network"])
        self.assertEqual(code, 0)

    def test_run_broken_file_exit_one(self):
        path = self._write("broken", broken_mission())
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = lint.run(["--file", path, "--no-network"])
        self.assertEqual(code, 1)

    def test_run_json_format_valid(self):
        path = self._write("broken", broken_mission())
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = lint.run(["--file", path, "--no-network", "--format", "json"])
        self.assertEqual(code, 1)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["counts"]["ERROR"], 4)
        self.assertIsInstance(payload["findings"], list)

    def test_run_stdin(self):
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps(clean_fvm_mission()))
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = lint.run(["--stdin", "--no-network"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 0)

    def test_run_min_reward_override(self):
        m = clean_fvm_mission()
        m["reward_amount"] = 50
        path = self._write("under", m)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = lint.run(
                ["--file", path, "--no-network", "--min-reward", "100"]
            )
        self.assertEqual(code, 1)  # 50 < 100 override -> ERROR

    def test_run_missing_file_exit_two(self):
        err = io.StringIO()
        from contextlib import redirect_stderr

        with redirect_stderr(err):
            code = lint.run(["--file", "/nonexistent/mission.json", "--no-network"])
        self.assertEqual(code, 2)

    def test_run_invalid_json_exit_two(self):
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as fh:
            fh.write("{not valid json")
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        from contextlib import redirect_stderr

        err = io.StringIO()
        with redirect_stderr(err):
            code = lint.run(["--file", path, "--no-network"])
        self.assertEqual(code, 2)

    def test_run_no_network_with_mission_id_is_usage_error(self):
        # argparse parser.error raises SystemExit(2).
        with self.assertRaises(SystemExit) as ctx:
            lint.run(["--mission-id", "1", "--no-network"])
        self.assertEqual(ctx.exception.code, 2)


# --------------------------------------------------------------------------- #
# fetch_min_reward_aigen fallback behaviour (monkeypatched, no real network)
# --------------------------------------------------------------------------- #
class TestStatsFallback(unittest.TestCase):
    def test_fallback_on_network_error(self):
        orig = lint._http_get_json

        def boom(url, *, timeout):
            raise lint.LintError("simulated network failure")

        lint._http_get_json = boom
        try:
            value, source = lint.fetch_min_reward_aigen("https://example.invalid")
        finally:
            lint._http_get_json = orig
        self.assertEqual(value, lint.FALLBACK_MIN_REWARD_AIGEN)
        self.assertEqual(source, "fallback")

    def test_reads_min_reward_from_stats(self):
        orig = lint._http_get_json

        def fake(url, *, timeout):
            return {"resolved": 5, "open": 3, "min_reward_aigen": 25}

        lint._http_get_json = fake
        try:
            value, source = lint.fetch_min_reward_aigen("https://example.test")
        finally:
            lint._http_get_json = orig
        self.assertEqual(value, 25.0)
        self.assertEqual(source, "stats")

    def test_fallback_when_field_absent(self):
        orig = lint._http_get_json

        def fake(url, *, timeout):
            return {"resolved": 5, "open": 3, "lifetime_reward_aigen_paid": 1000}

        lint._http_get_json = fake
        try:
            value, source = lint.fetch_min_reward_aigen("https://example.test")
        finally:
            lint._http_get_json = orig
        self.assertEqual(value, lint.FALLBACK_MIN_REWARD_AIGEN)
        self.assertEqual(source, "fallback")


if __name__ == "__main__":
    unittest.main(verbosity=2)
