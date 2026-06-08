#!/usr/bin/env python3
"""Moss C VM fuzzer — generates random Moss source, compiles, and feeds to mossvm.

Usage:
  python tools/fuzz_mossvm.py [--duration 3600] [--seed 42]

The fuzzer generates valid Moss programs from a grammar, compiles them with the
Python host compiler, and runs the resulting .mbc in the C VM. Crashes, hangs,
and output mismatches between Python VM and C VM are logged.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from io import StringIO

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from mosslang.parser import parse_source
from mosslang.checker import check_program
from mosslang.compiler import compile_program
from mosslang.vm import VM
from mosslang.errors import MossError

MOSSVM = ROOT / "bin" / "mossvm.exe"


# ── Moss source grammar (simplified) ──

IDENTIFIERS = ["x", "y", "z", "a", "b", "data", "result", "val", "n", "name", "age", "price"]
LITERALS = ["42", "3.14", "true", "false", "null", '"hello"', '"moss"', '"world"']
BINOPS = ["+", "-", "*", "/", "==", "!=", "<", ">", "<=", ">=", "and", "or"]
UNARYOPS = ["-", "not"]

def random_expr(depth=0):
    if depth > 5: return random.choice(LITERALS) + random.choice(["", "", "", f" + {random.choice(LITERALS)}"])
    kind = random.choice(["lit", "id", "call", "binop", "unary", "record", "list", "ifelse"])
    if kind == "lit": return random.choice(LITERALS)
    if kind == "id": return random.choice(IDENTIFIERS)
    if kind == "call":
        fn = random.choice(["print", "len", "assert", "double", "greet"])
        nargs = random.randint(0, 2)
        args = ", ".join(random_expr(depth+1) for _ in range(nargs))
        return f"{fn}({args})" if nargs > 0 else f"{fn}()"
    if kind == "binop":
        return f"({random_expr(depth+1)} {random.choice(BINOPS)} {random_expr(depth+1)})"
    if kind == "unary":
        return f"({random.choice(UNARYOPS)} {random_expr(depth+1)})"
    if kind == "record":
        fields = ", ".join(f"{random.choice(IDENTIFIERS)}: {random_expr(depth+1)}" for _ in range(random.randint(1,3)))
        return f"{{ {fields} }}"
    if kind == "list":
        items = ", ".join(random.choice(LITERALS) for _ in range(random.randint(1,4)))
        return f"[{items}]"
    if kind == "ifelse":
        return f"if {random_expr(depth+1)} {{ {random.choice(LITERALS)} }} else {{ {random.choice(LITERALS)} }}"
    return random.choice(LITERALS)

def random_statement():
    kind = random.choice(["let", "assign", "expr", "fn_simple"])
    if kind == "let":
        return f"let {random.choice(IDENTIFIERS)} = {random_expr()}"
    if kind == "assign":
        return f"let {random.choice(IDENTIFIERS)} = {random.choice(IDENTIFIERS)} = {random_expr()}"
    if kind == "expr":
        return f"print({random_expr()})"
    if kind == "fn_simple":
        name = random.choice(IDENTIFIERS)
        return f"fn {name}(x, y) {{ return x + y }}\nprint({name}({random_expr()}, {random_expr()}))"
    return f"print({random_expr()})"

def random_source():
    n = random.randint(1, 8)
    stmts = [random_statement() for _ in range(n)]
    return "\n".join(stmts) + "\n"


def run_python_vm(source: str) -> tuple[str, bool]:
    """Run source on Python VM, return (output, success)"""
    try:
        program = parse_source(source)
        diagnostics = check_program(program)
        errors = [d for d in diagnostics if d.level == "error"]
        if errors:
            return "\n".join(d.message for d in errors), False
        buf = StringIO()
        vm = VM(output=buf.write, base_path=ROOT)
        mod = compile_program(program, source_path="<fuzzer>")
        vm.load_module(mod)
        vm.run()
        return buf.getvalue(), True
    except MossError as e:
        return str(e), False
    except Exception as e:
        return f"Python VM crash: {e}", False


def run_c_vm(mbc_path: Path) -> tuple[str, bool]:
    """Run .mbc on C VM, return (stdout, success)"""
    try:
        result = subprocess.run(
            [str(MOSSVM), str(mbc_path)],
            capture_output=True, text=True, timeout=10
        )
        lines = [l for l in result.stdout.splitlines()
                 if "LOAD OK" not in l and "mossvm:" not in l]
        return "\n".join(lines), result.returncode == 0
    except subprocess.TimeoutExpired:
        return "<timeout>", False
    except Exception as e:
        return f"<C VM crash: {e}>", False


def fuzz(duration: int = 3600, seed: int = 0):
    start = time.time()
    if seed: random.seed(seed)
    count = 0
    crashes = 0
    mismatches = 0
    total = 0

    log_path = ROOT / "fuzz_results.jsonl"
    with open(log_path, "w") as log:
        while time.time() - start < duration:
            total += 1
            source = random_source()
            source_hash = hashlib.sha256(source.encode()).hexdigest()[:12]

            # Run Python VM for reference
            py_out, py_ok = run_python_vm(source)
            if not py_ok:
                count += 1
                continue  # Skip programs that don't check/parse

            # Compile and run C VM
            try:
                with tempfile.NamedTemporaryFile(suffix=".mbc", delete=False) as f:
                    mbc_path = Path(f.name)
                subprocess.run(
                    [sys.executable, "-m", "mosslang.cli", "compile", "-o", str(mbc_path)],
                    input=source, capture_output=True, text=True, timeout=10,
                    cwd=str(ROOT),
                    # Can't use stdin for moss compile — need a temp .moss file
                )
                # Actually, moss compile needs a file, not stdin. Use subprocess differently.
                mbc_path.unlink(missing_ok=True)

                # Write source to temp file
                with tempfile.NamedTemporaryFile(suffix=".moss", mode="w", delete=False, encoding="utf-8") as f:
                    f.write(source)
                    moss_path = Path(f.name)
                mbc_path = moss_path.with_suffix(".mbc")
                subprocess.run(
                    [sys.executable, "-m", "mosslang.cli", "compile", str(moss_path), "-o", str(mbc_path)],
                    capture_output=True, text=True, timeout=10, cwd=str(ROOT)
                )
                c_out, c_ok = run_c_vm(mbc_path)
                moss_path.unlink(missing_ok=True)
                mbc_path.unlink(missing_ok=True)

                if not c_ok:
                    crashes += 1
                    entry = {"hash": source_hash, "status": "CRASH", "source": source[:500], "c_out": c_out[:200]}
                    log.write(json.dumps(entry) + "\n")
                    print(f"[{total:5d}] CRASH  {source_hash}  {c_out[:80]}")
                    continue

                if py_out.rstrip() != c_out.rstrip():
                    mismatches += 1
                    entry = {"hash": source_hash, "status": "MISMATCH", "source": source[:500],
                             "py_out": py_out[:200], "c_out": c_out[:200]}
                    log.write(json.dumps(entry) + "\n")
                    print(f"[{total:5d}] MISMATCH {source_hash}")
                    continue

                count += 1
                if total % 10 == 0:
                    elapsed = int(time.time() - start)
                    print(f"[{total:5d}] OK (rate={count/elapsed:.1f}/s) {source_hash}", end="\r")

            except Exception as e:
                crashes += 1
                print(f"[{total:5d}] FUZZER CRASH {e}")

    print(f"\n\nDone. {total} programs, {count} valid, {crashes} C VM crashes, {mismatches} output mismatches")
    print(f"Results: {log_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=60, help="Fuzz duration in seconds")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()
    fuzz(args.duration, args.seed)
