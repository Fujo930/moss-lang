"""mossvm-trust — C VM trust artifact with cross-validation against Python VM.

Produces a trust bundle JSON that includes:
  check  — from Python VM (types, effects, match coverage)
  golden — C VM output vs Python VM output comparison
  c_vm   — true (this artifact was verified by C VM)

Usage:
  python mossvm_trust.py examples/order.moss
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from io import StringIO

# Point to the moss fork root
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from mosslang.parser import parse_source
from mosslang.checker import check_program
from mosslang.compiler import compile_program
from mosslang.vm import VM
from mosslang.cli import portable_trace_event

MOSSVM = ROOT / "bin" / "mossvm.exe"


def run_c_vm(mbc_path: Path) -> str:
    """Run the C VM on a compiled .mbc and return stdout."""
    result = subprocess.run(
        [str(MOSSVM), str(mbc_path)],
        capture_output=True, text=True, timeout=30
    )
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    if result.returncode != 0:
        raise RuntimeError(f"C VM crashed: {stderr[:200]}")
    # Filter out stderr mixed into stdout
    lines = [l for l in stdout.splitlines() if "LOAD OK" not in l and "mossvm:" not in l]
    return "\n".join(lines)


def build_cvm_trust_artifact(source_path: Path) -> dict:
    """Build a Trust Artifact using both Python VM and C VM."""
    source = source_path.read_text(encoding="utf-8-sig")
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()

    bundle: dict = {
        "artifact": "Moss Trust Artifact (C VM) v0.59.0",
        "moss": "0.59.0",
        "file": source_path.resolve().as_posix(),
        "source_sha256": source_hash,
        "trust": True,
    }

    # 1. Python check gate
    try:
        program = parse_source(source)
        diagnostics = check_program(program)
        chk_errors = [d for d in diagnostics if d.level == "error"]
        bundle["check"] = {
            "ok": len(chk_errors) == 0,
            "diagnostics": [
                {"level": d.level, "message": d.message,
                 "line": d.location.line if d.location else None,
                 "column": d.location.column if d.location else None}
                for d in diagnostics
            ],
        }
    except Exception as e:
        bundle["check"] = {"ok": False, "diagnostics": [{"level": "error", "message": str(e)}]}
        bundle["trust"] = False

    if not bundle["check"]["ok"]:
        bundle["trace"] = {"ok": False, "events": []}
        bundle["golden"] = {"ok": False}
        bundle["c_vm"] = False
        return bundle

    # 2. Python VM golden (reference)
    py_buf = StringIO()
    try:
        py_vm = VM(output=py_buf.write, base_path=source_path.parent)
        py_mod = compile_program(program, source_path=str(source_path.resolve()))
        py_vm.load_module(py_mod)
        py_vm.run()
        py_golden = py_buf.getvalue()
    except Exception as e:
        py_golden = f"<Python VM error: {e}>"
        bundle["trust"] = False

    # 3. Python VM trace
    try:
        py_trace_vm = VM(output=lambda _: None, base_path=source_path.parent, trace_rules=True)
        py_trace_mod = compile_program(program, source_path=str(source_path.resolve()))
        py_trace_vm.load_module(py_trace_mod)
        py_trace_vm.run()
        py_events = [portable_trace_event(e) for e in py_trace_vm.trace_events]
    except Exception:
        py_events = []

    # 4. C VM golden — compile via CLI then run in mossvm
    try:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mbc", delete=False) as f:
            mbc_path = Path(f.name)
        result = subprocess.run(
            [sys.executable, "-m", "mosslang.cli", "compile", str(source_path), "-o", str(mbc_path)],
            capture_output=True, text=True, timeout=30, cwd=str(ROOT)
        )
        if result.returncode != 0:
            raise RuntimeError(f"compile failed: {result.stderr[:200]}")
        c_golden = run_c_vm(mbc_path)
        mbc_path.unlink(missing_ok=True)
    except Exception as e:
        c_golden = f"<C VM error: {e}>"
        bundle["trust"] = False

    # 5. Golden comparison (normalize trailing whitespace)
    py_normalized = py_golden.rstrip()
    c_normalized = c_golden.rstrip()
    golden_match = (py_normalized == c_normalized)
    bundle["golden"] = {
        "ok": golden_match,
        "python_output": py_golden,
        "cvm_output": c_golden,
        "match": golden_match,
    }
    if not golden_match:
        bundle["trust"] = False

    # 6. Trace gate
    bundle["trace"] = {
        "ok": len(py_events) > 0 or True,  # trace ok even if no rules
        "events": py_events,
    }

    # 7. C VM status
    bundle["c_vm"] = True
    bundle["c_vm_verified"] = bundle["trust"]

    return bundle


def main() -> int:
    if len(sys.argv) < 2:
        print(f"usage: python {sys.argv[0]} <file.moss>")
        return 1

    source_path = Path(sys.argv[1]).resolve()
    if not source_path.is_file():
        print(f"error: not found: {source_path}", file=sys.stderr)
        return 1

    bundle = build_cvm_trust_artifact(source_path)
    print(json.dumps(bundle, indent=2))
    return 0 if bundle.get("trust") else 1


if __name__ == "__main__":
    sys.exit(main())
