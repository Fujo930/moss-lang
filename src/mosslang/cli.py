from __future__ import annotations

import argparse
import pprint
import sys
from pathlib import Path

from .checker import check_program
from .errors import MossError
from .parser import parse_source
from .runtime import Runtime
from .tokens import tokenize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="moss", description="Moss language prototype")
    sub = parser.add_subparsers(dest="command", required=True)

    for command in ("run", "check", "test", "tokens", "ast"):
        cmd = sub.add_parser(command)
        cmd.add_argument("file", type=Path)

    selfhost_cmd = sub.add_parser("selfhost")
    selfhost_cmd.add_argument("--quick", action="store_true", help="skip the slower project-level self-host check")

    compare_cmd = sub.add_parser("selfhost-compare")
    compare_cmd.add_argument("file", type=Path)

    studio_cmd = sub.add_parser("studio")
    studio_cmd.add_argument("--host", default="127.0.0.1")
    studio_cmd.add_argument("--port", type=int, default=8765)

    args = parser.parse_args(argv)

    try:
        if args.command == "studio":
            from .studio import run_studio

            run_studio(args.host, args.port)
            return 0

        if args.command == "selfhost":
            return run_selfhost_checks(quick=args.quick)

        if args.command == "selfhost-compare":
            return run_selfhost_compare(args.file)

        source = args.file.read_text(encoding="utf-8")
        if args.command == "tokens":
            for token in tokenize(source):
                print(repr(token))
            return 0

        program = parse_source(source)

        if args.command == "ast":
            pprint.pp(program)
            return 0

        if args.command == "check":
            diagnostics = check_program(program)
            for diagnostic in diagnostics:
                print(f"{diagnostic.level}: {diagnostic.message}")
            if any(d.level == "error" for d in diagnostics):
                return 1
            summary = summarize(program)
            print(
                f"ok: {summary['effects']} effect block(s), {summary['imports']} import(s), "
                f"{summary['types']} type(s), {summary['callables']} callable(s), {summary['tests']} test(s)"
            )
            return 0

        if args.command in {"run", "test"}:
            diagnostics = check_program(program)
            errors = [d for d in diagnostics if d.level == "error"]
            if errors:
                for diagnostic in diagnostics:
                    print(f"{diagnostic.level}: {diagnostic.message}", file=sys.stderr)
                return 1
            runtime = Runtime(base_path=args.file.parent)
            if args.command == "run":
                runtime.run(program)
            else:
                results = runtime.run_tests(program)
                for result in results:
                    marker = "PASS" if result["status"] == "pass" else "FAIL"
                    detail = f": {result['message']}" if result["message"] else ""
                    print(f"{marker} {result['name']}{detail}")
                failed = sum(1 for result in results if result["status"] == "fail")
                print(f"{len(results) - failed}/{len(results)} tests passed")
                return 1 if failed else 0
            return 0

        parser.error(f"unknown command {args.command}")
        return 2
    except OSError as exc:
        print(f"moss: {exc}", file=sys.stderr)
        return 1
    except MossError as exc:
        print(f"moss: {exc}", file=sys.stderr)
        return 1


def summarize(program):
    return {
        "effects": sum(1 for item in program.items if item.__class__.__name__ == "EffectDecl"),
        "imports": sum(1 for item in program.items if item.__class__.__name__ == "ImportDecl"),
        "types": sum(1 for item in program.items if item.__class__.__name__ == "TypeDecl"),
        "callables": sum(1 for item in program.items if item.__class__.__name__ in {"RuleDecl", "FunctionDecl"}),
        "tests": sum(1 for item in program.items if item.__class__.__name__ == "TestDecl"),
    }


def run_selfhost_checks(quick: bool = False) -> int:
    paths = [
        Path("examples/self_host/tokenizer_sketch.moss"),
        Path("examples/self_host/expression_sketch.moss"),
        Path("examples/self_host/statement_sketch.moss"),
        Path("examples/self_host/parser_sketch.moss"),
        Path("examples/self_host/checker_sketch.moss"),
    ]
    if not quick:
        paths.append(Path("examples/self_host/project_check.moss"))
    failed = 0

    for path in paths:
        source = path.read_text(encoding="utf-8")
        program = parse_source(source)
        diagnostics = check_program(program)
        errors = [d for d in diagnostics if d.level == "error"]
        if errors:
            failed = failed + 1
            for diagnostic in diagnostics:
                print(f"{path}: {diagnostic.level}: {diagnostic.message}")
            continue

        runtime = Runtime(base_path=Path.cwd())
        results = runtime.run_tests(program)
        test_failures = [r for r in results if r["status"] == "fail"]
        if test_failures:
            failed = failed + 1
            for result in test_failures:
                detail = f": {result['message']}" if result["message"] else ""
                print(f"FAIL {path} {result['name']}{detail}")
        else:
            print(f"PASS {path} ({len(results)} test(s))")

    return 1 if failed else 0


def run_selfhost_compare(path: Path) -> int:
    paths = sorted(path.glob("*.moss")) if path.is_dir() else [path]
    failed = 0

    for source_path in paths:
        if not compare_selfhost_file(source_path):
            failed += 1
    return 1 if failed else 0


def compare_selfhost_file(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    host = summarize(parse_source(source))

    runtime = Runtime(base_path=Path.cwd())
    runtime.run(parse_source('import "examples/self_host/parser_core.moss"\n'))
    tokens = runtime.call(runtime.globals.get("sketchTokens"), [source])
    parsed = runtime.call(runtime.globals.get("parseProgram"), [tokens])
    nodes = parsed["nodes"]
    errors = parsed["errors"]
    selfhost = {
        "effects": sum(1 for item in nodes if item["kind"] == "Effect"),
        "imports": sum(1 for item in nodes if item["kind"] == "Import"),
        "types": sum(1 for item in nodes if item["kind"] == "Type"),
        "callables": sum(1 for item in nodes if item["kind"] in {"Rule", "Function"}),
        "tests": sum(1 for item in nodes if item["kind"] == "Test"),
    }

    print(f"{path}:")
    print(f"  host: {host}")
    print(f"  selfhost: {selfhost}")
    if errors:
        for error in errors:
            print(f"  selfhost parse error: {error}")
        return False
    if host != selfhost:
        print("  selfhost comparison failed")
        return False
    print("  selfhost comparison passed")
    return True


if __name__ == "__main__":
    raise SystemExit(main())
