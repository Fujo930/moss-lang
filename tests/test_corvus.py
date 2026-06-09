"""Tests for Corvus — Moss Agent core engine."""

from __future__ import annotations

import unittest

from mossagent.core import Corvus, CorvusVersionError, VerifyResult, ExecuteResult


class CorvusVersionTests(unittest.TestCase):
    """Shared version infrastructure."""

    def test_version_guard_passes(self) -> None:
        """Corvus imports successfully when Moss meets requirement."""
        from _version import MOSS_VERSION, MOSS_REQUIRED
        cv = Corvus()
        info = cv.version()
        self.assertTrue(info["ok"])
        self.assertEqual(info["moss"], MOSS_VERSION)
        self.assertEqual(info["moss_required"], MOSS_REQUIRED)
        self.assertIn("corvus", info)

    def test_version_tuple_parsing(self) -> None:
        """Version tuple parser handles alpha and dev suffixes."""
        from mossagent.core import _version_tuple
        self.assertEqual(_version_tuple("0.1.0a3.1"), (0, 1, 0, 3, 1))
        self.assertEqual(_version_tuple("0.1.0-dev"), (0, 1, 0))
        self.assertEqual(_version_tuple("1.0.0"), (1, 0, 0))


class CorvusVerifyTests(unittest.TestCase):
    """Trust pipeline verification."""

    def setUp(self) -> None:
        self.cv = Corvus()

    def test_verify_valid_source(self) -> None:
        """Valid Moss source passes Trust verification."""
        vr = self.cv.verify("fn add(x, y) = x + y")
        self.assertIsInstance(vr, VerifyResult)
        self.assertTrue(vr.trust)
        self.assertGreater(vr.gates, 0)
        self.assertGreater(vr.elapsed_ms, 0)
        self.assertNotEqual(vr.source_hash, "")

    def test_verify_invalid_source(self) -> None:
        """Invalid Moss source fails Trust verification."""
        vr = self.cv.verify("fn @#$% invalid")
        self.assertIsInstance(vr, VerifyResult)
        self.assertFalse(vr.trust)
        # Parse errors → check gate fails even if no explicit failed_gates list
        self.assertFalse(vr.check_ok)

    def test_verify_empty_source(self) -> None:
        """Empty source is rejected."""
        vr = self.cv.verify("")
        self.assertFalse(vr.trust)

    def test_verify_returns_fix_hints(self) -> None:
        """Failed verification includes fix hints when available."""
        vr = self.cv.verify("fn bad {")
        self.assertFalse(vr.trust)
        # fix_hints is a list — may be empty or populated
        self.assertIsInstance(vr.fix_hints, list)

    def test_verify_with_effect(self) -> None:
        """Source with declared effect passes."""
        src = 'effect DB\nfn save(o) uses DB { o }'
        vr = self.cv.verify(src)
        self.assertTrue(vr.trust)


class CorvusExecuteTests(unittest.TestCase):
    """Python VM execution."""

    def setUp(self) -> None:
        self.cv = Corvus()

    def test_execute_simple(self) -> None:
        """Simple expression executes and returns output."""
        er = self.cv.execute("1 + 2")
        self.assertTrue(er.ok)
        self.assertEqual(er.error, None)

    def test_execute_print(self) -> None:
        """print() output is captured."""
        er = self.cv.execute('print("hello world")')
        self.assertTrue(er.ok)
        self.assertEqual(er.output, "hello world\n")

    def test_execute_error(self) -> None:
        """Syntax error returns ok=False with error message."""
        er = self.cv.execute("{")
        self.assertFalse(er.ok)
        self.assertIsNotNone(er.error)


class CorvusSafeExecuteTests(unittest.TestCase):
    """Safe execute: verify then run."""

    def setUp(self) -> None:
        self.cv = Corvus()

    def test_safe_execute_passing(self) -> None:
        """When trust passes, code is executed."""
        vr, er = self.cv.safe_execute("42 * 2")
        self.assertTrue(vr.trust)
        self.assertIsNotNone(er)
        self.assertTrue(er.ok)

    def test_safe_execute_failing(self) -> None:
        """When trust fails, execution is skipped."""
        vr, er = self.cv.safe_execute("{ bad syntax")
        self.assertFalse(vr.trust)
        self.assertIsNone(er)


class CorvusTokenTests(unittest.TestCase):
    """Token Artifact extraction."""

    def setUp(self) -> None:
        self.cv = Corvus()

    def test_token_basic(self) -> None:
        """Token extraction returns structured skeleton."""
        t = self.cv.token("fn f() = 1", level="brief")
        self.assertIn("ta", t)
        self.assertIn("c", t)

    def test_token_counts(self) -> None:
        """Token correctly counts effects, types, callables."""
        src = 'fn add(x, y) = x + y\nfn sub(x, y) = x - y'
        t = self.cv.token(src, level="normal")
        c = t.get("c", {})
        self.assertEqual(c.get("e", 0), 0)  # no effects
        self.assertEqual(c.get("t", 0), 0)  # no types
        self.assertEqual(c.get("l", 0), 2)  # two callables


class CorvusHashTests(unittest.TestCase):
    """Source hashing."""

    def test_hash_stable(self) -> None:
        cv = Corvus()
        h1 = cv.source_hash("hello")
        h2 = cv.source_hash("hello")
        self.assertEqual(h1, h2)

    def test_hash_different(self) -> None:
        cv = Corvus()
        h1 = cv.source_hash("hello")
        h2 = cv.source_hash("world")
        self.assertNotEqual(h1, h2)

    def test_hash_length(self) -> None:
        cv = Corvus()
        self.assertEqual(len(cv.source_hash("test")), 16)


if __name__ == "__main__":
    unittest.main()
