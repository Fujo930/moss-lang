"""Tests for Diagnostic error code classification (alpha(t)2.1)."""

from __future__ import annotations

import unittest
from mosslang.checker import Diagnostic, _classify_diagnostic


class DiagnosticCodeTests(unittest.TestCase):
    def test_all_13_codes_classify(self):
        patterns = [
            ("duplicate effect", "E001"),
            ("duplicate type", "E002"),
            ("duplicate callable", "E003"),
            ("uses undeclared effect", "E004"),
            ("does not declare uses", "E005"),
            ("rules must be pure", "E006"),
            ("has undeclared type", "E007"),
            ("type mismatch", "E008"),
            ("non-exhaustive match", "E009"),
            ("has no field", "E010"),
            ("declared but never used", "W001"),
            ("will never match", "W002"),
            ("possible import cycle", "W003"),
        ]
        for pattern, expected_code in patterns:
            code, hint = _classify_diagnostic(f"some prefix {pattern} suffix")
            self.assertEqual(
                code, expected_code,
                f"Pattern '{pattern}' should classify to '{expected_code}' but got '{code}'"
            )
            self.assertTrue(hint, f"Pattern '{pattern}' should have a hint")

    def test_unknown_message_returns_empty(self):
        code, hint = _classify_diagnostic("completely unrelated diagnostic message")
        self.assertEqual(code, "", "Unknown message should return empty code")
        self.assertEqual(hint, "", "Unknown message should return empty hint")

    def test_diagnostic_auto_attaches_code(self):
        d = Diagnostic("error", "duplicate effect 'Foo'")
        self.assertEqual(d.code, "E001")
        self.assertTrue(d.hint)

    def test_diagnostic_code_not_overwritten(self):
        d = Diagnostic("error", "duplicate effect 'Foo'", code="CUSTOM", hint="my hint")
        self.assertEqual(d.code, "CUSTOM", "Existing code should not be overwritten")
        self.assertEqual(d.hint, "my hint")

    def test_e005_dual_match(self):
        # E005 matches both "does not declare uses" and "is missing effect"
        for msg in ["foo calls dbPut but does not declare uses Database",
                     "foo calls bar but is missing effect(s): Database"]:
            code, _ = _classify_diagnostic(msg)
            self.assertEqual(code, "E005", f"'{msg[:30]}...' should classify to E005")


if __name__ == "__main__":
    unittest.main()
