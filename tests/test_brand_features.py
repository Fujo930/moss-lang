"""Tests for alpha(t)3.1 brand features — decompile, signing, trust header, stack guard.

Covers the four-brand architecture (Trust + Token + Server + Decompile)
features that were added in alpha(t)3 and refined in alpha(t)3.1.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pytest


class DecompileTests(unittest.TestCase):
    """Brand 4 — Moss Decompile."""

    def test_decompile_python_vm_mbc(self) -> None:
        """decompile produces valid output from Python VM .mbc."""
        from mosslang.cli import main as cli_main

        order_path = Path(__file__).parent.parent / "examples" / "order.moss"
        with tempfile.NamedTemporaryFile(suffix=".mbc", delete=False) as f:
            mbc_path = f.name
        try:
            code = cli_main(["compile", str(order_path), "-o", mbc_path])
            self.assertEqual(code, 0)

            # Capture stdout
            import sys, io
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = cli_main(["decompile", mbc_path])
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

            self.assertEqual(code, 0)
            self.assertIn("// decompiled:", output)
            self.assertIn("// version", output)
            self.assertIn("effect Database", output)
            self.assertIn("// main:", output)
            self.assertIn("// decompile complete", output)
        finally:
            Path(mbc_path).unlink(missing_ok=True)

    def test_decompile_selfhost_mbc(self) -> None:
        """decompile handles selfhost-compiled .mbc files."""
        from mosslang.cli import main as cli_main

        mbc_path = Path(__file__).parent.parent / "build" / "embedded" / "lexer_core.mbc"
        self.assertTrue(mbc_path.exists(), f"missing: {mbc_path}")

        import sys, io
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            code = cli_main(["decompile", str(mbc_path)])
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        self.assertEqual(code, 0)
        self.assertIn("// decompiled:", output)
        self.assertIn("// 7 functions:", output)

    def test_decompile_invalid_file_rejected(self) -> None:
        """decompile rejects non-.mbc files."""
        from mosslang.cli import main as cli_main

        import sys, io
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        try:
            code = cli_main(["decompile", str(Path(__file__))])
            output = sys.stderr.getvalue()
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        self.assertNotEqual(code, 0)

    def test_decompile_output_to_file(self) -> None:
        """decompile --output writes to file."""
        from mosslang.cli import main as cli_main

        mbc_path = Path(__file__).parent.parent / "build" / "embedded" / "lexer_core.mbc"
        with tempfile.NamedTemporaryFile(suffix=".moss", delete=False) as f:
            out_path = f.name
        try:
            code = cli_main(["decompile", str(mbc_path), "-o", out_path])
            self.assertEqual(code, 0, f"exit code {code}")
            result = Path(out_path).read_text(encoding="utf-8")
            self.assertIn("// decompiled:", result)
        finally:
            Path(out_path).unlink(missing_ok=True)


class TokenSignTests(unittest.TestCase):
    """Token Artifact HMAC signing and verification."""

    def _make_key(self, path: Path) -> None:
        from mosslang.cli import main as cli_main
        import os
        code = cli_main(["keygen", "-o", str(path)])
        self.assertEqual(code, 0)

    def test_token_sign_produces_valid_json(self) -> None:
        """token-sign produces JSON with 'sig' field."""
        from mosslang.cli import main as cli_main

        order_path = Path(__file__).parent.parent / "examples" / "order.moss"
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = f.name
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as kf:
            key_path = kf.name
        try:
            self._make_key(Path(key_path))
            code = cli_main(["token-sign", str(order_path), "-k", key_path, "-o", out_path])
            self.assertEqual(code, 0)
            token = json.loads(Path(out_path).read_text())
            self.assertIn("sig", token)
            self.assertEqual(token["sig"]["algorithm"], "HMAC-SHA256")
            self.assertIn("hmac", token["sig"])
            self.assertIn("payload", token["sig"])
        finally:
            Path(out_path).unlink(missing_ok=True)
            Path(key_path).unlink(missing_ok=True)

    def test_token_sign_verify_roundtrip(self) -> None:
        """token-sign → verify-sig passes round-trip."""
        from mosslang.cli import main as cli_main

        order_path = Path(__file__).parent.parent / "examples" / "order.moss"
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = f.name
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as kf:
            key_path = kf.name
        try:
            self._make_key(Path(key_path))
            code = cli_main(["token-sign", str(order_path), "-k", key_path, "-o", out_path])
            self.assertEqual(code, 0)

            code = cli_main(["token-verify-sig", out_path, "-k", key_path])
            self.assertEqual(code, 0, "verification should pass on unmodified token")
        finally:
            Path(out_path).unlink(missing_ok=True)
            Path(key_path).unlink(missing_ok=True)

    def test_token_verify_sig_detects_tampering(self) -> None:
        """token-verify-sig rejects tampered token."""
        from mosslang.cli import main as cli_main

        order_path = Path(__file__).parent.parent / "examples" / "order.moss"
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = f.name
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as kf:
            key_path = kf.name
        try:
            self._make_key(Path(key_path))
            code = cli_main(["token-sign", str(order_path), "-k", key_path, "-o", out_path])
            self.assertEqual(code, 0)

            # Tamper
            token = json.loads(Path(out_path).read_text())
            token["c"]["effects"] = 99999
            Path(out_path).write_text(json.dumps(token), encoding="utf-8")

            import sys, io
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = cli_main(["token-verify-sig", out_path, "-k", key_path])
            finally:
                sys.stdout = old_stdout

            self.assertNotEqual(code, 0, "should reject tampered token")
        finally:
            Path(out_path).unlink(missing_ok=True)
            Path(key_path).unlink(missing_ok=True)

    def test_token_verify_no_sig_rejected(self) -> None:
        """token-verify-sig rejects token without 'sig' field."""
        from mosslang.cli import main as cli_main

        order_path = Path(__file__).parent.parent / "examples" / "order.moss"
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = f.name
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as kf:
            key_path = kf.name
        try:
            self._make_key(Path(key_path))
            # Generate unsigned token
            import sys, io
            old = sys.stdout
            sys.stdout = io.StringIO()
            try:
                cli_main(["token", str(order_path), "-o", out_path])
            finally:
                sys.stdout = old

            code = cli_main(["token-verify-sig", out_path, "-k", key_path])
            self.assertNotEqual(code, 0, "should reject unsigned token")
        finally:
            Path(out_path).unlink(missing_ok=True)
            Path(key_path).unlink(missing_ok=True)


class ArtifactSignTests(unittest.TestCase):
    """Trust Artifact HMAC signing and verification."""

    def _make_key(self, path: Path) -> None:
        from mosslang.cli import main as cli_main
        code = cli_main(["keygen", "-o", str(path)])
        self.assertEqual(code, 0)

    def _make_bundle(self, out_path: Path) -> None:
        from mosslang.cli import main as cli_main
        order = Path(__file__).parent.parent / "examples" / "order.moss"
        code = cli_main(["trust", str(order), "-o", str(out_path)])
        self.assertEqual(code, 0)

    def test_artifact_sign_verify_roundtrip(self) -> None:
        """artifact-sign → verify-sig round-trip passes."""
        from mosslang.cli import main as cli_main

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as bf:
            bundle_path = bf.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as sf:
            signed_path = sf.name
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as kf:
            key_path = kf.name
        try:
            self._make_key(Path(key_path))
            self._make_bundle(Path(bundle_path))

            code = cli_main(["artifact-sign", bundle_path, "-k", key_path, "-o", signed_path])
            self.assertEqual(code, 0)

            code = cli_main(["artifact-verify-sig", signed_path, "-k", key_path])
            self.assertEqual(code, 0, "verification should pass on unmodified artifact")
        finally:
            for p in [bundle_path, signed_path, key_path]:
                Path(p).unlink(missing_ok=True)

    def test_artifact_verify_sig_detects_tampering(self) -> None:
        """artifact-verify-sig rejects tampered evidence."""
        from mosslang.cli import main as cli_main

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as bf:
            bundle_path = bf.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as sf:
            signed_path = sf.name
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as kf:
            key_path = kf.name
        try:
            self._make_key(Path(key_path))
            self._make_bundle(Path(bundle_path))

            code = cli_main(["artifact-sign", bundle_path, "-k", key_path, "-o", signed_path])
            self.assertEqual(code, 0)

            # Tamper evidence body
            signed = json.loads(Path(signed_path).read_text())
            signed["check"]["ok"] = False
            Path(signed_path).write_text(json.dumps(signed), encoding="utf-8")

            code = cli_main(["artifact-verify-sig", signed_path, "-k", key_path])
            self.assertNotEqual(code, 0, "should reject tampered artifact")
        finally:
            for p in [bundle_path, signed_path, key_path]:
                Path(p).unlink(missing_ok=True)

    def test_artifact_verify_sig_detects_injected_keys(self) -> None:
        """artifact-verify-sig detects extra top-level keys."""
        from mosslang.cli import main as cli_main

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as bf:
            bundle_path = bf.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as sf:
            signed_path = sf.name
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as kf:
            key_path = kf.name
        try:
            self._make_key(Path(key_path))
            self._make_bundle(Path(bundle_path))

            code = cli_main(["artifact-sign", bundle_path, "-k", key_path, "-o", signed_path])
            self.assertEqual(code, 0)

            # Inject extra field
            signed = json.loads(Path(signed_path).read_text())
            signed["injected_backdoor"] = {"malicious": True}
            Path(signed_path).write_text(json.dumps(signed), encoding="utf-8")

            code = cli_main(["artifact-verify-sig", signed_path, "-k", key_path])
            self.assertNotEqual(code, 0, "should reject extra keys")
        finally:
            for p in [bundle_path, signed_path, key_path]:
                Path(p).unlink(missing_ok=True)


class TrustHeaderTests(unittest.TestCase):
    """Trust Header — @trust annotation on source files."""

    def test_token_header_writes_trust_line(self) -> None:
        """moss token --header writes // @trust header."""
        from mosslang.cli import main as cli_main

        order_path = Path(__file__).parent.parent / "examples" / "order.moss"
        original = order_path.read_text(encoding="utf-8")

        try:
            import sys, io
            old = sys.stdout
            sys.stdout = io.StringIO()
            try:
                code = cli_main(["token", str(order_path), "--header"])
            finally:
                sys.stdout = old
            self.assertEqual(code, 0)

            first_line = order_path.read_text(encoding="utf-8").splitlines()[0]
            self.assertTrue(first_line.startswith("// @trust"), f"got: {first_line}")
        finally:
            order_path.write_text(original, encoding="utf-8")

    def test_token_header_missing_file(self) -> None:
        """moss token --header on missing file returns error."""
        from mosslang.cli import main as cli_main

        import sys, io
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        try:
            code = cli_main(["token", "/nonexistent/moss/file.moss", "--header"])
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        self.assertNotEqual(code, 0)


class StackGuardTests(unittest.TestCase):
    """Python VM stack depth and value stack guards."""

    def test_frame_depth_guard(self) -> None:
        """VM.MAX_FRAME_DEPTH exists and has a reasonable default."""
        from mosslang.vm import VM
        self.assertGreater(VM.MAX_FRAME_DEPTH, 1000)

    def test_stack_size_guard(self) -> None:
        """VM.MAX_STACK_SIZE exists and matches C VM STACK_MAX."""
        from mosslang.vm import VM
        self.assertEqual(VM.MAX_STACK_SIZE, 4096)

    def test_value_stack_overflow_caught(self) -> None:
        """Value stack overflow raises MossRuntimeError, not segfault."""
        from mosslang.vm import VM
        from mosslang.bytecode import BytecodeModule, CodeObject, Instruction, Opcode

        mod = BytecodeModule(source_path="test.moss")
        co = CodeObject(
            name="<module>",
            instructions=[
                Instruction(Opcode.LOAD_CONST, 0),
                Instruction(Opcode.JUMP, 0),
            ],
            constants=[42],
            locals=[],
            arg_count=0,
        )
        mod.code = co

        vm = VM()
        vm.load_module(mod)

        from mosslang.errors import MossRuntimeError
        with self.assertRaises(MossRuntimeError) as ctx:
            vm.run()
        self.assertIn("value stack overflow", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
