"""Corvus — Moss Agent core engine.

Corvus is headless: no GUI, no CLI, no HTTP server. Those are thin
shells around it. Corvus only imports mosslang and stdlib.

Usage:
    from mossagent import Corvus
    c = Corvus()
    result = c.verify(source)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _version import MOSS_VERSION, MOSS_REQUIRED, AGENT_VERSION


# ── Version guard ─────────────────────────────────────────────────────
class CorvusVersionError(RuntimeError):
    """Raised when the installed Moss is older than the minimum required."""


def _version_tuple(v: str) -> tuple[int, ...]:
    parts = v.replace("a", ".").replace("-dev", "")
    return tuple(int(x) for x in parts.split(".") if x.isdigit())


_CUR = _version_tuple(MOSS_VERSION)
_REQ = _version_tuple(MOSS_REQUIRED)
if _CUR < _REQ:
    raise CorvusVersionError(
        f"Corvus requires Moss {MOSS_REQUIRED}+, found {MOSS_VERSION}"
    )


# ── Result types ──────────────────────────────────────────────────────

@dataclass
class VerifyResult:
    """Structured Trust pipeline result."""
    trust: bool
    gates: int
    gates_total: int
    failed_gates: list[str]
    check_ok: bool | None
    trace_ok: bool | None
    golden_ok: bool | None
    lock_ok: bool | None
    selfhost_ok: bool | None
    fix_hints: list[dict]
    source_hash: str
    elapsed_ms: int
    raw: dict


@dataclass
class ExecuteResult:
    """VM execution result."""
    output: str
    ok: bool
    error: str | None
    elapsed_ms: int


# ── Corvus engine ─────────────────────────────────────────────────────

class Corvus:
    """Headless Moss Agent core."""

    def __init__(self, base_path: Path | None = None) -> None:
        self.base_path = base_path or Path.cwd()

    # ── Metadata ──────────────────────────────────────────────────

    def version(self) -> dict:
        return {
            "corvus": AGENT_VERSION,
            "moss": MOSS_VERSION,
            "moss_required": MOSS_REQUIRED,
            "ok": _CUR >= _REQ,
        }

    # ── Verify ────────────────────────────────────────────────────

    def verify(self, source: str) -> VerifyResult:
        """Run full Trust pipeline.  Primary entry point for AI validation."""
        from mosslang.trust_server import trust_from_source

        b = trust_from_source(source)
        return VerifyResult(
            trust=b.get("trust", False),
            gates=b.get("gates", 0),
            gates_total=b.get("gates_total", 5),
            failed_gates=b.get("failed_gates", []),
            check_ok=b.get("check", {}).get("ok"),
            trace_ok=b.get("trace", {}).get("ok"),
            golden_ok=b.get("golden", {}).get("ok"),
            lock_ok=b.get("lock", {}).get("ok"),
            selfhost_ok=b.get("selfhost", {}).get("ok"),
            fix_hints=b.get("fix_hints", []) or [],
            source_hash=b.get("source_sha256", "")[:16],
            elapsed_ms=b.get("elapsed_ms", 0),
            raw=b,
        )

    # ── Execute ───────────────────────────────────────────────────

    def execute(self, source: str) -> ExecuteResult:
        """Compile and run in Python VM. Does NOT verify first."""
        import time
        from io import StringIO
        from mosslang.parser import parse_source
        from mosslang.compiler import compile_program
        from mosslang.vm import VM

        t0 = time.perf_counter()
        try:
            mod = compile_program(parse_source(source), source_path="<corvus>")
            buf = StringIO()
            vm = VM(output=buf.write)
            vm.load_module(mod)
            vm.run()
            return ExecuteResult(
                output=buf.getvalue(), ok=True, error=None,
                elapsed_ms=round((time.perf_counter() - t0) * 1000),
            )
        except Exception as e:
            return ExecuteResult(
                output="", ok=False, error=str(e),
                elapsed_ms=round((time.perf_counter() - t0) * 1000),
            )

    # ── Safe execute ──────────────────────────────────────────────

    def safe_execute(self, source: str) -> tuple[VerifyResult, ExecuteResult | None]:
        """Verify then execute. Returns (verify, execute|None)."""
        vr = self.verify(source)
        if not vr.trust:
            return vr, None
        return vr, self.execute(source)

    # ── Token ─────────────────────────────────────────────────────

    def token(self, source: str, *, level: str = "normal") -> dict:
        """Extract Token Artifact (~3ms)."""
        from mosslang.trust_server import token_from_source
        return token_from_source(source, level=level)

    # ── Hash ─────────────────────────────────────────────────────

    def source_hash(self, source: str) -> str:
        return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
