from __future__ import annotations

import argparse
import os
import pprint
import re
import sys
from collections import Counter
from pathlib import Path

from . import __version__
from .checker import check_program
from .errors import MossError
from .nodes import FunctionDecl, RuleDecl, TypeDecl
from .parser import parse_source
from .runtime import Runtime
from .tokens import tokenize


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="moss", description="Moss language prototype")
    parser.add_argument("--version", action="version", version=f"Moss {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    for command in ("run", "check", "test", "tokens", "ast"):
        cmd = sub.add_parser(command)
        cmd.add_argument("file", type=Path)

    format_cmd = sub.add_parser("format")
    format_cmd.add_argument("file", type=Path)
    format_cmd.add_argument("--check", action="store_true", help="report whether formatting would change the file")

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
        if args.command == "format":
            from .formatter import format_source

            formatted = format_source(source)
            if args.check:
                if formatted != source:
                    print(f"needs formatting: {args.file}")
                    return 1
                print(f"formatted: {args.file}")
                return 0
            args.file.write_text(formatted, encoding="utf-8")
            print(f"formatted: {args.file}")
            return 0

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
                print(diagnostic.format())
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
                    print(diagnostic.format(), file=sys.stderr)
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
    root = installation_root()
    previous_directory = Path.cwd()
    try:
        os.chdir(root)
        return run_selfhost_checks_from_root(root, quick)
    finally:
        os.chdir(previous_directory)


def run_selfhost_checks_from_root(root: Path, quick: bool) -> int:
    paths = [
        root / "examples/self_host/tokenizer_sketch.moss",
        root / "examples/self_host/expression_sketch.moss",
        root / "examples/self_host/statement_sketch.moss",
        root / "examples/self_host/parser_sketch.moss",
        root / "examples/self_host/checker_sketch.moss",
    ]
    if not quick:
        paths.append(root / "examples/self_host/project_check.moss")
    failed = 0

    for path in paths:
        source = path.read_text(encoding="utf-8")
        program = parse_source(source)
        diagnostics = check_program(program)
        errors = [d for d in diagnostics if d.level == "error"]
        if errors:
            failed = failed + 1
            for diagnostic in diagnostics:
                print(f"{display_installation_path(path, root)}: {diagnostic.format()}")
            continue

        runtime = Runtime(base_path=root)
        results = runtime.run_tests(program)
        test_failures = [r for r in results if r["status"] == "fail"]
        if test_failures:
            failed = failed + 1
            for result in test_failures:
                detail = f": {result['message']}" if result["message"] else ""
                print(f"FAIL {display_installation_path(path, root)} {result['name']}{detail}")
        else:
            print(f"PASS {display_installation_path(path, root)} ({len(results)} test(s))")

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
    host_program = parse_source(source)
    host = summarize(host_program)
    host_names = host_declaration_names(host_program)
    host_bodies = host_body_statement_kinds(host_program)
    host_metadata = host_declaration_metadata(host_program)

    root = installation_root()
    runtime = Runtime(base_path=root)
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
    selfhost_names = selfhost_declaration_names(nodes)
    selfhost_bodies = selfhost_body_statement_kinds(nodes)
    selfhost_metadata = selfhost_declaration_metadata(nodes)

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
    if host_names != selfhost_names:
        print(f"  host names: {host_names}")
        print(f"  selfhost names: {selfhost_names}")
        print("  selfhost declaration-name comparison failed")
        return False
    if host_bodies != selfhost_bodies:
        print(f"  host body statements: {host_bodies}")
        print(f"  selfhost body statements: {selfhost_bodies}")
        print("  selfhost body-structure comparison failed")
        return False
    if host_metadata != selfhost_metadata:
        print(f"  host metadata: {host_metadata}")
        print(f"  selfhost metadata: {selfhost_metadata}")
        print("  selfhost declaration-metadata comparison failed")
        return False
    print("  selfhost comparison passed")
    return True


def host_declaration_names(program) -> dict[str, list[str]]:
    result = {"imports": [], "types": [], "rules": [], "functions": [], "tests": []}
    for item in program.items:
        kind = item.__class__.__name__
        if kind == "ImportDecl":
            result["imports"].append(item.path)
        elif kind == "TypeDecl":
            result["types"].append(item.name)
        elif kind == "RuleDecl":
            result["rules"].append(item.name)
        elif kind == "FunctionDecl":
            result["functions"].append(item.name)
        elif kind == "TestDecl":
            result["tests"].append(item.name)
    return {key: sorted(values) for key, values in result.items()}


def selfhost_declaration_names(nodes: list[dict]) -> dict[str, list[str]]:
    mapping = {"Import": "imports", "Type": "types", "Rule": "rules", "Function": "functions", "Test": "tests"}
    result = {"imports": [], "types": [], "rules": [], "functions": [], "tests": []}
    for item in nodes:
        target = mapping.get(item["kind"])
        if target is not None:
            result[target].append(item["value"] if item["kind"] == "Import" else item["name"])
    return {key: sorted(values) for key, values in result.items()}


def host_body_statement_kinds(program) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for item in program.items:
        kind = item.__class__.__name__
        if kind not in {"FunctionDecl", "TestDecl"}:
            continue
        label = ("fn:" if kind == "FunctionDecl" else "test:") + item.name
        counts: Counter[str] = Counter()
        count_host_statements(item.body, counts)
        result[label] = dict(sorted(counts.items()))
    return result


def count_host_statements(statements, counts: Counter[str]) -> None:
    for statement in statements:
        kind = statement.__class__.__name__.removesuffix("Stmt")
        counts[kind] += 1
        if kind == "If":
            count_host_statements(statement.then_body, counts)
            count_host_statements(statement.else_body, counts)
        elif kind in {"For", "While"}:
            count_host_statements(statement.body, counts)


def selfhost_body_statement_kinds(nodes: list[dict]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for item in nodes:
        if item["kind"] not in {"Function", "Test"}:
            continue
        label = ("fn:" if item["kind"] == "Function" else "test:") + item["name"]
        counts: Counter[str] = Counter()
        count_selfhost_statements(item["data"] or [], counts)
        result[label] = dict(sorted(counts.items()))
    return result


def count_selfhost_statements(statements: list[dict], counts: Counter[str]) -> None:
    for statement in statements:
        kind = statement["kind"]
        counts[kind] += 1
        value = statement.get("value")
        if kind == "If" and isinstance(value, dict):
            count_selfhost_statements(value.get("thenBody", []), counts)
            count_selfhost_statements(value.get("elseBody", []), counts)
        elif kind in {"For", "While"} and isinstance(value, dict):
            count_selfhost_statements(value.get("body", []), counts)


def host_declaration_metadata(program) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for item in program.items:
        if isinstance(item, TypeDecl):
            result[f"type:{item.name}"] = {
                "fields": {name: normalize_type_text(value) for name, value in sorted(item.fields.items())},
                "alias": normalize_type_text(item.alias or ""),
            }
        elif isinstance(item, (RuleDecl, FunctionDecl)):
            result[f"{'rule' if isinstance(item, RuleDecl) else 'fn'}:{item.name}"] = {
                "params": [(param.name, normalize_type_text(param.type_name or "")) for param in item.params],
                "return": normalize_type_text(item.return_type or ""),
                "uses": sorted(item.uses) if isinstance(item, FunctionDecl) else [],
            }
    return result


def selfhost_declaration_metadata(nodes: list[dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for item in nodes:
        if item["kind"] == "Type":
            fields: dict[str, str] = {}
            alias = ""
            if item["value"].startswith("="):
                alias = normalize_type_text(item["value"][1:])
            else:
                for field in item["value"].split(";"):
                    if ":" in field:
                        name, value = field.split(":", 1)
                        fields[name.strip()] = normalize_type_text(value)
            result[f"type:{item['name']}"] = {"fields": dict(sorted(fields.items())), "alias": alias}
        elif item["kind"] in {"Rule", "Function"}:
            result[f"{'rule' if item['kind'] == 'Rule' else 'fn'}:{item['name']}"] = parse_selfhost_signature(item["value"])
    return result


def parse_selfhost_signature(text: str) -> dict:
    params: list[tuple[str, str]] = []
    match = re.search(r"\((.*?)\)", text)
    if match:
        for part in split_signature_parts(match.group(1)):
            if ":" in part:
                name, type_name = part.split(":", 1)
                params.append((name.strip(), normalize_type_text(type_name)))
            elif part.strip():
                params.append((part.strip(), ""))

    return_type = ""
    return_match = re.search(r"->(.*?)(?:\buses\b|\{|=|$)", text)
    if return_match:
        return_type = normalize_type_text(return_match.group(1))
    uses: list[str] = []
    uses_match = re.search(r"\buses\b(.*?)(?:\{|$)", text)
    if uses_match:
        uses = sorted(part.strip() for part in uses_match.group(1).split(",") if part.strip())
    return {"params": params, "return": return_type, "uses": uses}


def split_signature_parts(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(text):
        if char == "<":
            depth += 1
        elif char == ">":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts


def normalize_type_text(text: str) -> str:
    parts = text.strip().split()
    normalized = " ".join(parts)
    normalized = re.sub(r"\s*([<>,.])\s*", r"\1", normalized)
    normalized = re.sub(r"\s*\|\s*", " | ", normalized)
    return normalized


def installation_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root is not None:
        return Path(frozen_root)
    return Path.cwd()


def display_installation_path(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path


if __name__ == "__main__":
    raise SystemExit(main())
