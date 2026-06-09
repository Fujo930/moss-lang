"""Corvus CLI — command-line entry point for Moss Agent.

Usage:
    # File-based (traditional)
    corvus verify file.moss
    corvus execute file.moss
    corvus safe file.moss
    corvus token file.moss

    # Source-based (PowerShell / pipe-friendly)
    corvus verify --source "fn add(x,y) = x + y"
    corvus execute --source "print('hello')"
    corvus generate --spec "a function that sorts a list" --source "fn sort(xs) = xs"

    # JSON output (machine-readable)
    corvus verify file.moss --json
    corvus generate --spec "sort a list" --json

    # Meta
    corvus version
    corvus check
"""

from __future__ import annotations

import json as _json
import sys
from pathlib import Path


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except Exception as e:
        print(f"error reading {path}: {e}", file=sys.stderr)
        raise SystemExit(1) from e


def _out(obj: dict | str, *, json_mode: bool) -> None:
    if json_mode:
        print(_json.dumps(obj, indent=2))
    elif isinstance(obj, str):
        sys.stdout.write(obj)
        sys.stdout.flush()
    else:
        print(_json.dumps(obj, indent=2))


def cmd_verify(cv, source: str, *, json_mode: bool = False) -> int:
    vr = cv.verify(source)
    if json_mode:
        _out({
            "trust": vr.trust, "gates": vr.gates, "gates_total": vr.gates_total,
            "failed_gates": vr.failed_gates, "fix_hints": vr.fix_hints,
            "check_ok": vr.check_ok, "trace_ok": vr.trace_ok, "golden_ok": vr.golden_ok,
            "lock_ok": vr.lock_ok, "selfhost_ok": vr.selfhost_ok,
            "hash": vr.source_hash, "ms": vr.elapsed_ms,
        }, json_mode=True)
    else:
        print(f"trust={vr.trust}  gates={vr.gates}/{vr.gates_total}")
        if vr.failed_gates:
            print(f"failed: {', '.join(vr.failed_gates)}")
        if vr.fix_hints:
            for h in vr.fix_hints[:5]:
                print(f"  line {h.get('line')}: {h.get('hint')}")
        print(f"hash={vr.source_hash}  {vr.elapsed_ms}ms")
    return 0 if vr.trust else 1


def cmd_execute(cv, source: str, *, json_mode: bool = False) -> int:
    er = cv.execute(source)
    if json_mode:
        _out({"ok": er.ok, "output": er.output, "error": er.error, "ms": er.elapsed_ms}, json_mode=True)
    elif er.ok:
        _out(er.output, json_mode=False)
    else:
        print(f"error: {er.error}", file=sys.stderr)
    return 0 if er.ok else 1


def cmd_safe(cv, source: str, *, json_mode: bool = False) -> int:
    vr, er = cv.safe_execute(source)
    if json_mode:
        _out({
            "verify": {"trust": vr.trust, "gates": vr.gates, "gates_total": vr.gates_total, "failed_gates": vr.failed_gates},
            "execute": {"ok": er.ok, "output": er.output, "error": er.error, "ms": er.elapsed_ms} if er else None,
        }, json_mode=True)
    else:
        print(f"verify: trust={vr.trust}  gates={vr.gates}/{vr.gates_total}")
        if not vr.trust:
            print(f"SKIPPED: {', '.join(vr.failed_gates)}")
            return 1
        if er:
            print(f"execute: ok={er.ok}  {er.elapsed_ms}ms")
            if er.output:
                _out(er.output, json_mode=False)
        return 0 if (er and er.ok) else 1
    return 0 if (vr.trust and er and er.ok) else 1


def cmd_token(cv, source: str, *, json_mode: bool = False) -> int:
    t = cv.token(source)
    _out(t, json_mode=True)  # Token is always JSON
    return 0 if t.get("t", True) else 1


def cmd_version(cv, *, json_mode: bool = False) -> int:
    _out(cv.version(), json_mode=True)  # always JSON
    return 0


def cmd_check(*, json_mode: bool = False) -> int:
    import time

    t0 = time.perf_counter()
    results = []

    try:
        from mossagent import Corvus
        cv = Corvus()
        results.append({"check": "version", "ok": True, **cv.version()})
    except Exception as e:
        results.append({"check": "version", "ok": False, "error": str(e)})
        _out({"ok": False, "checks": results}, json_mode=json_mode)
        return 1

    try:
        vr = cv.verify("fn add(x, y) = x + y")
        results.append({"check": "verify", "ok": vr.trust, "ms": vr.elapsed_ms})
    except Exception as e:
        results.append({"check": "verify", "ok": False, "error": str(e)})

    try:
        er = cv.execute("1 + 2")
        results.append({"check": "execute", "ok": er.ok, "ms": er.elapsed_ms})
    except Exception as e:
        results.append({"check": "execute", "ok": False, "error": str(e)})

    elapsed = round((time.perf_counter() - t0) * 1000)
    ok = all(r.get("ok") for r in results)
    _out({"ok": ok, "elapsed_ms": elapsed, "checks": results}, json_mode=json_mode)
    return 0 if ok else 1


def cmd_generate(cv, spec: str, *, json_mode: bool = False, provider: str = "openai", model: str | None = None) -> int:
    """Generate Moss code from a specification using an LLM.

    Requires LLM_API_KEY env var (or pass --model for local).
    Supports: openai, claude, local (Ollama/LM Studio/vLLM).
    """
    from .generator import Generator
    from .llm import create_adapter

    try:
        adapter = create_adapter(provider, model=model)
    except Exception as e:
        _out({"ok": False, "error": f"LLM setup failed: {e}"}, json_mode=json_mode)
        return 1

    gen = Generator(cv, adapter.generate)
    result = gen.generate(spec)

    if json_mode:
        _out({
            "spec": spec,
            "trust": result.trust,
            "attempts": result.attempts,
            "moss_code": result.moss_code if result.trust else None,
            "error": result.final_error,
        }, json_mode=True)
    else:
        if result.trust:
            print(f"OK (attempt {result.attempts}):")
            print(result.moss_code)
        else:
            print(f"FAIL ({result.attempts} attempts): {result.final_error}", file=sys.stderr)
    return 0 if result.trust else 1


def cmd_agent(cv, task: str, *, json_mode: bool = False, provider: str = "openai", model: str | None = None, max_rounds: int = 15) -> int:
    """Run the multi-turn autonomous Agent on a task.
    
    The Agent explores the codebase, writes Moss code, verifies it,
    fixes failures, runs tests, and commits.  Full autonomous loop.
    """
    from .agent import Agent
    from .llm import create_adapter

    try:
        adapter = create_adapter(provider, model=model)
    except Exception as e:
        _out({"ok": False, "error": f"LLM setup failed: {e}"}, json_mode=json_mode)
        return 1

    agent = Agent(adapter.generate, max_rounds=max_rounds)
    result = agent.run(task)

    if json_mode:
        _out({
            "ok": result.ok,
            "task": result.task,
            "rounds": result.rounds,
            "trust": result.trust,
            "summary": result.summary,
            "moss_code": result.moss_code[:500] if result.moss_code else None,
            "files": result.file_paths,
            "elapsed_s": result.elapsed_s,
        }, json_mode=True)
    else:
        print(f"Agent done in {result.rounds} rounds ({result.elapsed_s}s)")
        print(f"Trust: {result.trust}")
        print(f"Summary: {result.summary}")
        if result.moss_code:
            print(f"\n--- Moss code ---\n{result.moss_code[:500]}")
    return 0 if result.ok else 1


def cmd_chat(*, json_mode: bool = False, message: str = "", provider: str = "openai", model: str | None = None) -> int:
    """Multi-turn chat with conversation history and session persistence.
    
    Uses ChatSession for prefix-cache-optimized multi-turn conversation.
    Saves session to corvus_chat.json so context survives restarts.
    """
    from .chat import ChatSession
    from .llm import create_adapter

    if not message:
        print("corvus chat: missing --message argument", file=sys.stderr)
        return 1

    try:
        adapter = create_adapter(provider, model=model)
    except Exception as e:
        _out({"ok": False, "error": f"LLM setup failed: {e}"}, json_mode=json_mode)
        return 1

    # Load existing session or create new
    session_path = Path("corvus_chat.json")
    if session_path.is_file():
        try:
            session = ChatSession.load(session_path, adapter.generate)
        except Exception:
            session = ChatSession().bind(adapter.generate)
    else:
        session = ChatSession().bind(adapter.generate)

    result = session.send(message)
    session.save(session_path)

    stats = session.stats()
    if json_mode:
        _out({
            "ok": True,
            "question": result.question,
            "answer": result.answer,
            "turn": result.turn,
            "total_tokens": result.total_tokens,
            "new_tokens": result.new_tokens,
            "cache_hit_pct": result.cache_hit_pct,
            "session_turns": stats["turns"],
            "session_messages": stats["messages"],
            "elapsed_s": result.elapsed_s,
        }, json_mode=True)
    else:
        print(result.answer)
        print(f"\n--- turn {result.turn} · cache hit {result.cache_hit_pct}% · {result.elapsed_s}s ---")
    return 0


def cmd_chat_reset(*, json_mode: bool = False) -> int:
    """Reset the chat session."""
    session_path = Path("corvus_chat.json")
    if session_path.is_file():
        session_path.unlink()
    if json_mode:
        _out({"ok": True, "message": "Chat session reset."}, json_mode=True)
    else:
        print("Chat session reset.")
    return 0


def cmd_chat_stats(*, json_mode: bool = False) -> int:
    """Show chat session statistics."""
    from .chat import ChatSession

    session_path = Path("corvus_chat.json")
    if not session_path.is_file():
        if json_mode:
            _out({"ok": True, "turns": 0, "messages": 0}, json_mode=True)
        else:
            print("No active chat session.")
        return 0

    try:
        session = ChatSession.load(session_path)
        stats = session.stats()
        if json_mode:
            _out({"ok": True, **stats}, json_mode=True)
        else:
            print(f"Chat session: {stats['turns']} turns, {stats['messages']} messages")
            print(f"System prompt: {stats['system_chars']} chars (~{stats['system_chars']//4} tokens, cached)")
            print(f"History: {stats['history_chars']} chars (~{stats['history_chars']//4} tokens)")
            print(f"Estimated cache hit rate: {stats['estimated_cache_hit_pct']}%")
    except Exception as e:
        if json_mode:
            _out({"ok": False, "error": str(e)}, json_mode=True)
        else:
            print(f"Error reading session: {e}")
    return 0


def cmd_test(cv, *, json_mode: bool = False) -> int:
    """Run the Python test suite and report results."""
    import time as _time, re
    from .tools import dispatch_tool

    t0 = _time.perf_counter()
    result = dispatch_tool("bash", {"command": "python -m pytest tests/ -q --tb=short 2>&1", "timeout": 60})
    elapsed = round((_time.perf_counter() - t0) * 1000)
    output = result.get("output", "")
    passed = failed = xfailed = errors = 0
    for line in output.splitlines():
        m = re.search(r'(\d+) passed', line); passed = int(m.group(1)) if m else passed
        m = re.search(r'(\d+) failed', line); failed = int(m.group(1)) if m else failed
        m = re.search(r'(\d+) xfailed', line); xfailed = int(m.group(1)) if m else xfailed
        m = re.search(r'(\d+) error', line); errors = int(m.group(1)) if m else errors
    if json_mode:
        _out({"passed": passed, "failed": failed, "xfailed": xfailed, "errors": errors, "elapsed_ms": elapsed}, json_mode=True)
    else:
        print(f"Tests: {passed} passed, {failed} failed, {xfailed} xfailed, {errors} errors · {elapsed}ms")
    return 0 if failed == 0 and errors == 0 else 1


def cmd_desktop() -> int:
    """Launch the Corvus Desktop GUI application."""
    try:
        from .desktop import main as desktop_main
    except ImportError as e:
        print(f"Cannot launch desktop: {e}", file=sys.stderr)
        print("Install PySide6: pip install PySide6", file=sys.stderr)
        return 1
    return desktop_main()
    """Run the Python test suite and report results.
    
    This is the test-feedback loop: run pytest, parse failures,
    and report structured results suitable for the Agent to consume.
    """
    import time as _time
    from .tools import dispatch_tool

    t0 = _time.perf_counter()
    result = dispatch_tool("bash", {"command": "python -m pytest tests/ -q --tb=short 2>&1", "timeout": 60})
    elapsed = round((_time.perf_counter() - t0) * 1000)

    # Parse pytest output
    output = result.get("output", "")
    passed = 0
    failed = 0
    xfailed = 0
    errors = 0
    failures: list[dict] = []

    for line in output.splitlines():
        if "passed" in line and "failed" in line:
            import re
            m = re.search(r'(\d+) passed', line)
            if m: passed = int(m.group(1))
            m = re.search(r'(\d+) failed', line)
            if m: failed = int(m.group(1))
            m = re.search(r'(\d+) xfailed', line)
            if m: xfailed = int(m.group(1))
            m = re.search(r'(\d+) error', line)
            if m: errors = int(m.group(1))
        if line.startswith("FAILED ") or line.startswith("ERROR "):
            failures.append({"test": line.strip()})

    if json_mode:
        _out({
            "passed": passed, "failed": failed, "xfailed": xfailed, "errors": errors,
            "failures": failures[:20],
            "elapsed_ms": elapsed,
            "raw": output[-500:],
        }, json_mode=True)
    else:
        print(f"Tests: {passed} passed, {failed} failed, {xfailed} xfailed, {errors} errors · {elapsed}ms")
        if failures:
            for f in failures[:10]:
                print(f"  FAIL: {f['test']}")
    return 0 if failed == 0 and errors == 0 else 1


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv

    # Parse --json flag anywhere
    json_mode = False
    args = [a for a in argv if a != "--json"]
    if len(args) < len(argv):
        json_mode = True

    source_text: str | None = None
    source_file: str | None = None
    spec_text: str | None = None
    message_text: str | None = None
    provider: str = "openai"
    model: str | None = None
    max_rounds: int = 15

    # Parse --source, --spec, --file, --provider, --model, --max-rounds, --msg
    remaining: list[str] = []
    i = 1
    while i < len(args):
        if args[i] == "--source" and i + 1 < len(args):
            source_text = args[i + 1]; i += 2
        elif args[i] == "--spec" and i + 1 < len(args):
            spec_text = args[i + 1]; i += 2
        elif args[i] == "--file" and i + 1 < len(args):
            source_file = args[i + 1]; i += 2
        elif args[i] == "--provider" and i + 1 < len(args):
            provider = args[i + 1]; i += 2
        elif args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]; i += 2
        elif args[i] == "--max-rounds" and i + 1 < len(args):
            try: max_rounds = int(args[i + 1])
            except ValueError: pass
            i += 2
        elif args[i] in ("--message", "--msg") and i + 1 < len(args):
            message_text = args[i + 1]; i += 2
        else:
            remaining.append(args[i]); i += 1

    if len(remaining) < 1:
        print("corvus: Moss Agent core engine", file=sys.stderr)
        print("usage: corvus <command> [--source code|--file path|--spec desc] [--json]", file=sys.stderr)
        print("commands: verify execute safe token generate agent chat test version check", file=sys.stderr)
        return 1

    cmd = remaining[0]

    # version, check, test, chat need no source/spec
    if cmd == "version":
        from mossagent import Corvus
        return cmd_version(Corvus(), json_mode=json_mode)
    if cmd == "check":
        return cmd_check(json_mode=json_mode)
    if cmd == "test":
        from mossagent import Corvus
        return cmd_test(Corvus(), json_mode=json_mode)

    if cmd == "desktop":
        return cmd_desktop()

    # chat, chat-reset, chat-stats need no source/spec
    if cmd == "chat":
        if not message_text:
            print("corvus chat: missing --msg argument", file=sys.stderr)
            return 1
        return cmd_chat(json_mode=json_mode, message=message_text, provider=provider, model=model)
    if cmd == "chat-reset":
        return cmd_chat_reset(json_mode=json_mode)
    if cmd == "chat-stats":
        return cmd_chat_stats(json_mode=json_mode)

    # agent needs a task (--spec)
    if cmd == "agent":
        if not spec_text:
            print("corvus agent: missing --spec argument (the task description)", file=sys.stderr)
            return 1
        from mossagent import Corvus
        return cmd_agent(Corvus(), spec_text, json_mode=json_mode, provider=provider, model=model, max_rounds=max_rounds)

    # generate needs a spec
    if cmd == "generate":
        if not spec_text:
            print("corvus generate: missing --spec argument", file=sys.stderr)
            return 1
        from mossagent import Corvus
        return cmd_generate(Corvus(), spec_text, json_mode=json_mode, provider=provider, model=model)

    # All other commands need source
    if source_text:
        src = source_text
    elif source_file:
        src = _read(Path(source_file))
    else:
        print(f"corvus {cmd}: need --source, --file, or a file path", file=sys.stderr)
        print("usage: corvus <command> [--source code|--file path] [--json]", file=sys.stderr)
        print("commands: verify execute safe token generate agent chat test version check", file=sys.stderr)
        return 1

    from mossagent import Corvus
    cv = Corvus()

    if cmd == "verify":
        return cmd_verify(cv, src, json_mode=json_mode)
    elif cmd == "execute":
        return cmd_execute(cv, src, json_mode=json_mode)
    elif cmd == "safe":
        return cmd_safe(cv, src, json_mode=json_mode)
    elif cmd == "token":
        return cmd_token(cv, src, json_mode=json_mode)
    else:
        print(f"corvus: unknown command: {cmd}", file=sys.stderr)
        print("commands: verify execute safe token generate agent chat test version check", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
