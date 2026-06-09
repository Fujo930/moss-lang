"""Corvus CLI — command-line entry point for Moss Agent.

Usage:
    corvus verify file.moss          → run Trust pipeline
    corvus execute file.moss         → compile and run in Python VM
    corvus safe file.moss            → verify then execute
    corvus token file.moss           → extract Token Artifact
    corvus version                   → print version info
    corvus check                     → self-check (Moss version, imports)
"""

from __future__ import annotations

import sys
from pathlib import Path


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except Exception as e:
        print(f"error reading {path}: {e}", file=sys.stderr)
        raise SystemExit(1) from e


def cmd_verify(cv, path: Path) -> int:
    source = _read(path)
    vr = cv.verify(source)
    print(f"trust={vr.trust}  gates={vr.gates}/{vr.gates_total}")
    if vr.failed_gates:
        print(f"failed: {', '.join(vr.failed_gates)}")
    if vr.fix_hints:
        for h in vr.fix_hints[:5]:
            print(f"  line {h.get('line')}: {h.get('hint')}")
    print(f"hash={vr.source_hash}  {vr.elapsed_ms}ms")
    return 0 if vr.trust else 1


def cmd_execute(cv, path: Path) -> int:
    source = _read(path)
    er = cv.execute(source)
    if er.ok:
        sys.stdout.write(er.output)
        sys.stdout.flush()
        return 0
    else:
        print(f"error: {er.error}", file=sys.stderr)
        return 1


def cmd_safe(cv, path: Path) -> int:
    source = _read(path)
    vr, er = cv.safe_execute(source)
    print(f"verify: trust={vr.trust}  gates={vr.gates}/{vr.gates_total}")
    if not vr.trust:
        print(f"SKIPPED: trust verification failed ({', '.join(vr.failed_gates)})")
        return 1
    print(f"execute: ok={er.ok}  {er.elapsed_ms}ms")
    if er.ok and er.output:
        sys.stdout.write(er.output)
        sys.stdout.flush()
    return 0 if er.ok else 1


def cmd_token(cv, path: Path) -> int:
    import json
    source = _read(path)
    t = cv.token(source)
    print(json.dumps(t, indent=2))
    return 0 if t.get("t", True) else 1


def cmd_version(cv) -> int:
    import json
    print(json.dumps(cv.version(), indent=2))
    return 0


def cmd_check() -> int:
    """Self-check: Moss version, imports, quick smoke test."""
    import json
    import time

    t0 = time.perf_counter()
    results = []

    # 1. Version guard
    try:
        from mossagent import Corvus
        cv = Corvus()
        results.append({"check": "version", "ok": True, **cv.version()})
    except Exception as e:
        results.append({"check": "version", "ok": False, "error": str(e)})
        print(json.dumps(results, indent=2))
        return 1

    # 2. Verify smoke test
    try:
        vr = cv.verify("fn add(x, y) = x + y")
        results.append({"check": "verify", "ok": vr.trust, "ms": vr.elapsed_ms})
    except Exception as e:
        results.append({"check": "verify", "ok": False, "error": str(e)})

    # 3. Execute smoke test
    try:
        er = cv.execute("1 + 2")
        results.append({"check": "execute", "ok": er.ok, "ms": er.elapsed_ms})
    except Exception as e:
        results.append({"check": "execute", "ok": False, "error": str(e)})

    elapsed = round((time.perf_counter() - t0) * 1000)
    ok = all(r.get("ok") for r in results)
    print(json.dumps({"ok": ok, "elapsed_ms": elapsed, "checks": results}, indent=2))
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv

    if len(argv) < 2:
        print("corvus: Moss Agent core engine", file=sys.stderr)
        print("usage: corvus <verify|execute|safe|token|version|check> [file]", file=sys.stderr)
        return 1

    cmd = argv[1]

    # check and version don't need a file argument
    if cmd == "check":
        return cmd_check()
    if cmd == "version":
        from mossagent import Corvus
        return cmd_version(Corvus())

    if len(argv) < 3:
        print(f"corvus {cmd}: missing file argument", file=sys.stderr)
        return 1

    path = Path(argv[2])
    if not path.is_file():
        print(f"corvus: file not found: {path}", file=sys.stderr)
        return 1

    from mossagent import Corvus
    cv = Corvus()

    if cmd == "verify":
        return cmd_verify(cv, path)
    elif cmd == "execute":
        return cmd_execute(cv, path)
    elif cmd == "safe":
        return cmd_safe(cv, path)
    elif cmd == "token":
        return cmd_token(cv, path)
    else:
        print(f"corvus: unknown command: {cmd}", file=sys.stderr)
        print("commands: verify execute safe token version check", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
