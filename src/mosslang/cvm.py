"""Moss C VM bridge — Python compatibility layer.

Provides `mosslang.cvm` module for running Moss code through the C VM
from Python. Used by the CLI, Studio, and as a library API.

Usage:
    from mosslang.cvm import compile_and_run, compile_to_mbc, run_mbc

    output = compile_and_run("examples/order.moss")
    mbc_bytes = compile_to_mbc("examples/order.moss")
    result = run_mbc(mbc_bytes)
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


def _find_mossvm() -> Path | None:
    """Find mossvm.exe in known locations."""
    import sys
    candidates = [
        Path(__file__).resolve().parents[2] / "bin" / "mossvm.exe",
        Path(sys.executable).parent / "mossvm.exe" if getattr(sys, 'frozen', False) else None,
        Path.cwd() / "mossvm.exe",
    ]
    for c in candidates:
        if c and c.is_file():
            return c
    return None


def compile_and_run(source_path: str | Path) -> tuple[str, int]:
    """Compile and run a Moss file through the full pipeline (Python compiler → C VM).
    
    Returns (output_text, exit_code).
    """
    import subprocess, tempfile
    source_path = Path(source_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"source not found: {source_path}")

    mbc_path = Path(tempfile.mktemp(suffix=".mbc"))
    try:
        # Compile with Python
        from mosslang.parser import parse_source
        from mosslang.checker import check_program
        from mosslang.compiler import compile_program
        source = source_path.read_text(encoding="utf-8-sig")
        program = parse_source(source)
        diagnostics = check_program(program)
        errors = [d for d in diagnostics if d.level == "error"]
        if errors:
            return "\n".join(d.message for d in errors), 1
        mod = compile_program(program, source_path=str(source_path.resolve()))
        mbc_path.write_bytes(mod.serialize())
        
        # Run with C VM
        cvm = _find_mossvm()
        if not cvm:
            return "C VM not found", 1
        result = subprocess.run([str(cvm), str(mbc_path)], capture_output=True, text=True, timeout=30)
        lines = [l for l in (result.stdout or "").splitlines() if "LOAD OK" not in l]
        return "\n".join(lines), result.returncode
    finally:
        mbc_path.unlink(missing_ok=True)


def compile_to_mbc(source_path: str | Path) -> bytes:
    """Compile a Moss file to .mbc bytes using the Python compiler."""
    source_path = Path(source_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"source not found: {source_path}")
    from mosslang.parser import parse_source
    from mosslang.compiler import compile_program
    source = source_path.read_text(encoding="utf-8-sig")
    program = parse_source(source)
    mod = compile_program(program, source_path=str(source_path.resolve()))
    return mod.serialize()


def run_mbc(mbc_bytes: bytes, timeout: int = 30) -> tuple[str, int]:
    """Run .mbc bytes through the C VM directly."""
    import tempfile
    cvm = _find_mossvm()
    if not cvm:
        return "C VM not found", 1
    mbc_path = Path(tempfile.mktemp(suffix=".mbc"))
    try:
        mbc_path.write_bytes(mbc_bytes)
        result = subprocess.run([str(cvm), str(mbc_path)], capture_output=True, text=True, timeout=timeout)
        lines = [l for l in (result.stdout or "").splitlines() if "LOAD OK" not in l]
        return "\n".join(lines), result.returncode
    finally:
        mbc_path.unlink(missing_ok=True)


def trust_artifact_cvm(source_path: str | Path) -> dict:
    """Run Trust Artifact verification using C VM for golden gate."""
    import hashlib
    source_path = Path(source_path)
    source = source_path.read_text(encoding="utf-8-sig")
    source_hash = hashlib.sha256(source.encode()).hexdigest()

    from mosslang.parser import parse_source
    from mosslang.checker import check_program
    from mosslang.compiler import compile_program
    from mosslang.vm import VM
    from io import StringIO

    program = parse_source(source)
    diagnostics = check_program(program)

    bundle = {
        "artifact": "Moss Trust Artifact (C VM)",
        "source_sha256": source_hash,
        "check": {"ok": not any(d.level == "error" for d in diagnostics)},
        "c_vm": False,
    }

    if bundle["check"]["ok"]:
        # Python VM golden
        buf = StringIO()
        vm = VM(output=buf.write, base_path=source_path.parent)
        mod = compile_program(program, source_path=str(source_path.resolve()))
        vm.load_module(mod)
        vm.run()
        py_out = buf.getvalue()

        # C VM golden
        try:
            c_out, code = compile_and_run(source_path)
            bundle["golden"] = {
                "ok": py_out.rstrip() == c_out.rstrip(),
                "python": py_out,
                "c_vm": c_out,
            }
            bundle["c_vm"] = True
        except Exception:
            bundle["golden"] = {"ok": False, "python": py_out, "c_vm": None}

    return bundle
