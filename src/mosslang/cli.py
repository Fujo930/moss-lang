from __future__ import annotations

import argparse
import json
import os
import pprint
import re
import sys
from collections import Counter
from pathlib import Path

from . import __version__
from . import nodes as ast_nodes
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
        if command == "check":
            cmd.add_argument("--json", action="store_true", help="emit structured diagnostics and summary")

    format_cmd = sub.add_parser("format")
    format_cmd.add_argument("file", type=Path)
    format_cmd.add_argument("--check", action="store_true", help="report whether formatting would change the file")

    selfhost_cmd = sub.add_parser("selfhost")
    selfhost_cmd.add_argument("--quick", action="store_true", help="skip the slower project-level self-host check")

    compare_cmd = sub.add_parser("selfhost-compare")
    compare_cmd.add_argument("file", type=Path)

    project_cmd = sub.add_parser("project-check")
    project_cmd.add_argument("directory", type=Path)
    project_cmd.add_argument("--json", action="store_true", help="emit one structured project result")

    sub.add_parser("repl", help="start an interactive multiline Moss session")

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

        if args.command == "project-check":
            return run_project_check(args.directory, json_output=args.json)

        if args.command == "repl":
            return run_repl()

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
            summary = summarize(program)
            if args.json:
                print(
                    json.dumps(
                        {
                            "ok": not any(d.level == "error" for d in diagnostics),
                            "file": str(args.file),
                            "diagnostics": [diagnostic_json(item) for item in diagnostics],
                            "summary": summary,
                        }
                    )
                )
                return 1 if any(d.level == "error" for d in diagnostics) else 0
            for diagnostic in diagnostics:
                print(diagnostic.format())
            if any(d.level == "error" for d in diagnostics):
                return 1
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
        if getattr(args, "command", None) == "check" and getattr(args, "json", False):
            location = getattr(exc, "location", None)
            diagnostic = {"level": "error", "message": getattr(exc, "message", str(exc))}
            if location is not None:
                diagnostic.update({"line": location.line, "column": location.column})
            print(json.dumps({"ok": False, "file": str(args.file), "diagnostics": [diagnostic], "summary": None}))
            return 1
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


def diagnostic_json(diagnostic) -> dict:
    result = {"level": diagnostic.level, "message": diagnostic.message}
    if diagnostic.location is not None:
        result.update({"line": diagnostic.location.line, "column": diagnostic.location.column})
    return result


def run_project_check(directory: Path, *, json_output: bool = False) -> int:
    paths = sorted(directory.rglob("*.moss"))
    results: list[dict] = []
    error_count = 0
    warning_count = 0

    for path in paths:
        try:
            program = parse_source(path.read_text(encoding="utf-8-sig"))
            diagnostics = check_program(program)
            summary = summarize(program)
        except MossError as exc:
            location = getattr(exc, "location", None)
            diagnostic = {"level": "error", "message": getattr(exc, "message", str(exc))}
            if location is not None:
                diagnostic.update({"line": location.line, "column": location.column})
            diagnostics = []
            result = {"file": str(path), "ok": False, "diagnostics": [diagnostic], "summary": None}
        else:
            result = {
                "file": str(path),
                "ok": not any(item.level == "error" for item in diagnostics),
                "diagnostics": [diagnostic_json(item) for item in diagnostics],
                "summary": summary,
            }

        error_count += sum(1 for item in result["diagnostics"] if item["level"] == "error")
        warning_count += sum(1 for item in result["diagnostics"] if item["level"] == "warning")
        results.append(result)

    payload = {
        "ok": error_count == 0,
        "directory": str(directory),
        "files": results,
        "summary": {"files": len(paths), "errors": error_count, "warnings": warning_count},
    }
    if json_output:
        print(json.dumps(payload))
    else:
        for result in results:
            for diagnostic in result["diagnostics"]:
                location = f"{diagnostic.get('line')}:{diagnostic.get('column')}: " if diagnostic.get("line") else ""
                print(f"{result['file']}: {diagnostic['level']}: {location}{diagnostic['message']}")
        print(f"project: {len(paths)} file(s), {warning_count} warning(s), {error_count} error(s)")
    return 1 if error_count else 0


def run_repl(*, input_fn=input, output_fn=print) -> int:
    runtime = Runtime(output_fn)
    buffer: list[str] = []
    depth = 0
    output_fn(f"Moss {__version__} REPL. Submit a blank line to run; Ctrl-D to exit.")

    while True:
        try:
            line = input_fn("... " if buffer else "moss> ")
        except (EOFError, KeyboardInterrupt, StopIteration):
            output_fn("")
            return 0

        if not line.strip() and buffer:
            depth = 0
        else:
            buffer.append(line)
            depth += brace_delta(line)
            if depth > 0 or line.strip().endswith(("=", "else")):
                continue

        if not buffer:
            continue
        source = "\n".join(buffer) + "\n"
        buffer = []
        try:
            program = parse_source(source)
            diagnostics = check_program(program)
            errors = [item for item in diagnostics if item.level == "error"]
            for diagnostic in diagnostics:
                output_fn(diagnostic.format())
            if not errors:
                runtime.run(program)
        except MossError as exc:
            output_fn(f"error: {exc}")


def brace_delta(line: str) -> int:
    try:
        tokens = tokenize(line + "\n")
    except MossError:
        return 0
    return sum(1 if token.value == "{" else -1 if token.value == "}" else 0 for token in tokens)


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
    expression_error = compare_expression_asts(host_program, runtime)

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
    if expression_error is not None:
        print(f"  expression AST comparison failed: {expression_error}")
        return False
    print("  selfhost comparison passed")
    return True


def compare_expression_asts(program, runtime: Runtime) -> str | None:
    for expression in program_expressions(program):
        source = render_expr(expression)
        parsed = runtime.call(runtime.globals.get("parseExpressionSource"), [source])
        if parsed["state"]["errors"]:
            return f"{source}: {parsed['state']['errors'][0]}"
        host = normalize_host_expr(expression)
        selfhost = normalize_selfhost_expr(parsed["expr"])
        if host != selfhost:
            return f"{source}: host={host!r}, selfhost={selfhost!r}"
    return None


def program_expressions(program) -> list[object]:
    result: list[object] = []
    for item in program.items:
        if isinstance(item, ast_nodes.RuleDecl):
            result.append(item.expr)
        elif isinstance(item, (ast_nodes.FunctionDecl, ast_nodes.TestDecl)):
            result.extend(statement_expressions(item.body))
        elif isinstance(item, (ast_nodes.LetStmt, ast_nodes.AssignStmt, ast_nodes.ReturnStmt, ast_nodes.ExprStmt)):
            result.append(item.expr)
        elif isinstance(item, ast_nodes.RequireStmt):
            result.extend([item.condition, item.else_expr])
    return result


def statement_expressions(statements) -> list[object]:
    result: list[object] = []
    for statement in statements:
        if isinstance(statement, (ast_nodes.LetStmt, ast_nodes.AssignStmt, ast_nodes.ReturnStmt, ast_nodes.ExprStmt)):
            result.append(statement.expr)
        elif isinstance(statement, ast_nodes.RequireStmt):
            result.extend([statement.condition, statement.else_expr])
        elif isinstance(statement, ast_nodes.IfStmt):
            result.append(statement.condition)
            result.extend(statement_expressions(statement.then_body))
            result.extend(statement_expressions(statement.else_body))
        elif isinstance(statement, ast_nodes.ForStmt):
            result.append(statement.iterable)
            result.extend(statement_expressions(statement.body))
        elif isinstance(statement, ast_nodes.WhileStmt):
            result.append(statement.condition)
            result.extend(statement_expressions(statement.body))
    return result


def render_expr(expr) -> str:
    if isinstance(expr, ast_nodes.Literal):
        if expr.value is None:
            return "null"
        if isinstance(expr.value, bool):
            return "true" if expr.value else "false"
        return json.dumps(expr.value)
    if isinstance(expr, ast_nodes.NumberLiteral):
        return str(expr.value)
    if isinstance(expr, ast_nodes.Identifier):
        return expr.name
    if isinstance(expr, ast_nodes.RecordLiteral):
        return "{ " + ", ".join(f"{name}: {render_expr(value)}" for name, value in expr.fields.items()) + " }"
    if isinstance(expr, ast_nodes.ListLiteral):
        return "[" + ", ".join(render_expr(item) for item in expr.items) + "]"
    if isinstance(expr, ast_nodes.RecordUpdate):
        return f"{render_expr(expr.base)} with {{ " + ", ".join(
            f"{name} = {render_expr(value)}" for name, value in expr.updates.items()
        ) + " }"
    if isinstance(expr, ast_nodes.UnaryExpr):
        return f"({expr.op} {render_expr(expr.right)})"
    if isinstance(expr, ast_nodes.BinaryExpr):
        return f"({render_expr(expr.left)} {expr.op} {render_expr(expr.right)})"
    if isinstance(expr, ast_nodes.CallExpr):
        return f"{render_expr(expr.callee)}(" + ", ".join(render_expr(arg) for arg in expr.args) + ")"
    if isinstance(expr, ast_nodes.FieldAccess):
        return f"{render_expr(expr.target)}.{expr.field}"
    if isinstance(expr, ast_nodes.IndexAccess):
        return f"{render_expr(expr.target)}[{render_expr(expr.index)}]"
    if isinstance(expr, ast_nodes.TryExpr):
        return f"{render_expr(expr.expr)}?"
    if isinstance(expr, ast_nodes.MatchExpr):
        cases = ", ".join(f"{render_pattern(case.pattern)} -> {render_expr(case.expr)}" for case in expr.cases)
        return f"match {render_expr(expr.subject)} {{ {cases} }}"
    raise TypeError(f"cannot render {type(expr).__name__}")


def render_pattern(pattern) -> str:
    if isinstance(pattern, ast_nodes.WildcardPattern):
        return "_"
    if isinstance(pattern, ast_nodes.BindingPattern):
        return pattern.name
    if isinstance(pattern, ast_nodes.LiteralPattern):
        if pattern.value is None:
            return "null"
        if isinstance(pattern.value, bool):
            return "true" if pattern.value else "false"
        return json.dumps(pattern.value) if isinstance(pattern.value, str) else str(pattern.value)
    if isinstance(pattern, ast_nodes.VariantPattern):
        if not pattern.payload:
            return pattern.name
        return f"{pattern.name}(" + ", ".join(render_pattern(item) for item in pattern.payload) + ")"
    raise TypeError(f"cannot render pattern {type(pattern).__name__}")


def normalize_host_expr(expr):
    if isinstance(expr, ast_nodes.Literal):
        return ("Null", "") if expr.value is None else ("Bool", str(expr.value).lower()) if isinstance(expr.value, bool) else ("Text", expr.value)
    if isinstance(expr, ast_nodes.NumberLiteral):
        return ("Number", str(expr.value))
    if isinstance(expr, ast_nodes.Identifier):
        return ("Identifier", expr.name)
    if isinstance(expr, ast_nodes.RecordLiteral):
        return ("Record", tuple(sorted((key, normalize_host_expr(value)) for key, value in expr.fields.items())))
    if isinstance(expr, ast_nodes.ListLiteral):
        return ("List", tuple(normalize_host_expr(item) for item in expr.items))
    if isinstance(expr, ast_nodes.RecordUpdate):
        return ("RecordUpdate", normalize_host_expr(expr.base), tuple(sorted((key, normalize_host_expr(value)) for key, value in expr.updates.items())))
    if isinstance(expr, ast_nodes.UnaryExpr):
        return ("Unary", expr.op, normalize_host_expr(expr.right))
    if isinstance(expr, ast_nodes.BinaryExpr):
        return ("Binary", expr.op, normalize_host_expr(expr.left), normalize_host_expr(expr.right))
    if isinstance(expr, ast_nodes.CallExpr):
        return ("Call", normalize_host_expr(expr.callee), tuple(normalize_host_expr(arg) for arg in expr.args))
    if isinstance(expr, ast_nodes.FieldAccess):
        return ("Field", expr.field, normalize_host_expr(expr.target))
    if isinstance(expr, ast_nodes.IndexAccess):
        return ("Index", normalize_host_expr(expr.target), normalize_host_expr(expr.index))
    if isinstance(expr, ast_nodes.TryExpr):
        return ("Try", normalize_host_expr(expr.expr))
    if isinstance(expr, ast_nodes.MatchExpr):
        return ("Match", normalize_host_expr(expr.subject), tuple((normalize_host_pattern(case.pattern), normalize_host_expr(case.expr)) for case in expr.cases))
    raise TypeError(type(expr).__name__)


def normalize_host_pattern(pattern):
    if isinstance(pattern, ast_nodes.WildcardPattern):
        return ("PatternWildcard", "")
    if isinstance(pattern, ast_nodes.BindingPattern):
        return ("PatternBinding", pattern.name)
    if isinstance(pattern, ast_nodes.LiteralPattern):
        value = "null" if pattern.value is None else str(pattern.value).lower() if isinstance(pattern.value, bool) else str(pattern.value)
        return ("PatternLiteral", value)
    if isinstance(pattern, ast_nodes.VariantPattern):
        return ("PatternVariant", pattern.name, tuple(normalize_host_pattern(item) for item in pattern.payload))
    raise TypeError(type(pattern).__name__)


def normalize_selfhost_expr(expr):
    kind = expr["kind"]
    if kind in {"Number", "Text", "Bool", "Null", "Identifier"}:
        return (kind, expr["value"])
    if kind == "Record":
        return (kind, tuple(sorted((key, normalize_selfhost_expr(value)) for key, value in expr["right"].items())))
    if kind == "List":
        return (kind, tuple(normalize_selfhost_expr(item) for item in expr["right"]))
    if kind == "RecordUpdate":
        return (kind, normalize_selfhost_expr(expr["left"]), tuple(sorted((key, normalize_selfhost_expr(value)) for key, value in expr["right"].items())))
    if kind == "Unary":
        return (kind, expr["value"], normalize_selfhost_expr(expr["right"]))
    if kind == "Binary":
        return (kind, expr["value"], normalize_selfhost_expr(expr["left"]), normalize_selfhost_expr(expr["right"]))
    if kind == "Call":
        return (kind, normalize_selfhost_expr(expr["left"]), tuple(normalize_selfhost_expr(arg) for arg in expr["right"]))
    if kind == "Field":
        return (kind, expr["value"], normalize_selfhost_expr(expr["left"]))
    if kind == "Index":
        return (kind, normalize_selfhost_expr(expr["left"]), normalize_selfhost_expr(expr["right"]))
    if kind == "Try":
        return (kind, normalize_selfhost_expr(expr["left"]))
    if kind == "Match":
        return (kind, normalize_selfhost_expr(expr["left"]), tuple((normalize_selfhost_pattern(case["pattern"]), normalize_selfhost_expr(case["expression"])) for case in expr["right"]))
    raise ValueError(f"unknown self-host expression kind {kind}")


def normalize_selfhost_pattern(pattern):
    if pattern["kind"] in {"PatternWildcard", "PatternBinding", "PatternLiteral"}:
        return (pattern["kind"], pattern["value"])
    if pattern["kind"] == "PatternVariant":
        return (pattern["kind"], pattern["value"], tuple(normalize_selfhost_pattern(item) for item in pattern["right"]))
    raise ValueError(f"unknown self-host pattern kind {pattern['kind']}")


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
