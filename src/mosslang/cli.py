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
from .project import (
    build_project_graph,
    find_manifest,
    initialize_project,
    load_manifest,
    verify_project_lock,
    write_project_lock,
)
from .tokens import tokenize
from .compiler import compile_program
from .vm import VM
from io import StringIO


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="moss", description="Moss language prototype")
    parser.add_argument("--version", action="version", version=f"Moss {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    for command in ("run", "check", "test", "tokens", "ast", "trace"):
        cmd = sub.add_parser(command)
        cmd.add_argument("file", type=Path)
        if command == "check":
            cmd.add_argument("--json", action="store_true", help="emit structured diagnostics and summary")
        if command in ("tokens", "ast"):
            cmd.add_argument("--frontend", choices=("host", "moss"), default="host",
                             help="use host (Python) or moss (self-host) frontend")
        if command == "trace":
            cmd.add_argument("--json", action="store_true", help="emit stable machine-readable rule trace events")

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
    project_cmd.add_argument("--locked", action="store_true", help="fail if moss.lock does not match the project")

    project_run_cmd = sub.add_parser("project-run")
    project_run_cmd.add_argument("directory", type=Path)
    project_run_cmd.add_argument("--locked", action="store_true", help="require a matching moss.lock")

    project_test_cmd = sub.add_parser("project-test")
    project_test_cmd.add_argument("directory", type=Path)
    project_test_cmd.add_argument("--locked", action="store_true", help="require a matching moss.lock")

    project_info_cmd = sub.add_parser("project-info")
    project_info_cmd.add_argument("directory", type=Path)
    project_info_cmd.add_argument("--json", action="store_true", help="emit the deterministic import graph")

    project_init_cmd = sub.add_parser("project-init")
    project_init_cmd.add_argument("directory", type=Path)
    project_init_cmd.add_argument("--name", help="package name; defaults to the directory name")

    new_cmd = sub.add_parser("new", help="create a Moss project from a template")
    new_cmd.add_argument("directory", type=Path)
    new_cmd.add_argument("--name", help="package name; defaults to the directory name")
    new_cmd.add_argument("--template", choices=("basic", "rules", "cli", "library"), default="basic")

    project_lock_cmd = sub.add_parser("project-lock")
    project_lock_cmd.add_argument("directory", type=Path)

    project_format_cmd = sub.add_parser("project-format")
    project_format_cmd.add_argument("directory", type=Path)
    project_format_cmd.add_argument("--check", action="store_true", help="fail if any reachable module needs formatting")

    golden_cmd = sub.add_parser("golden")
    golden_cmd.add_argument("file", type=Path)
    golden_cmd.add_argument("--update", action="store_true", help="write the current output as the golden file")

    docs_cmd = sub.add_parser("docs")
    docs_cmd.add_argument("file", type=Path)
    docs_cmd.add_argument("--output", type=Path)

    sub.add_parser("repl", help="start an interactive multiline Moss session")

    studio_cmd = sub.add_parser("studio")
    studio_cmd.add_argument("--host", default="127.0.0.1")
    studio_cmd.add_argument("--port", type=int, default=8765)

    playground_cmd = sub.add_parser("playground", help="open the Moss Playground trust report viewer")
    playground_cmd.add_argument("--host", default="127.0.0.1")
    playground_cmd.add_argument("--port", type=int, default=8766)

    compile_cmd = sub.add_parser("compile", help="compile moss source to bytecode")
    compile_cmd.add_argument("file", type=Path)
    compile_cmd.add_argument("--output", "-o", type=Path, help="output .mbc file path")

    trust_cmd = sub.add_parser("trust", help="produce a trust bundle (check + trace + golden + lock + selfhost)")
    trust_cmd.add_argument("file", type=Path)
    trust_cmd.add_argument("--output", "-o", type=Path, help="write trust bundle to file (default: stdout)")

    trust_proj_cmd = sub.add_parser("trust-project", help="produce a project-wide trust bundle")
    trust_proj_cmd.add_argument("directory", type=Path)
    trust_proj_cmd.add_argument("--output", "-o", type=Path, help="write trust bundle to file")

    run_vm_cmd = sub.add_parser("run-vm", help="execute compiled bytecode module")
    run_vm_cmd.add_argument("file", type=Path)
    run_vm_cmd.add_argument("--source-root", type=Path, help="source root for resolving imports")

    args = parser.parse_args(argv)

    try:
        if args.command == "studio":
            from .studio import run_studio

            run_studio(args.host, args.port)
            return 0

        if args.command == "playground":
            from .playground import run_playground

            run_playground(args.host, args.port)
            return 0

        if args.command == "selfhost":
            return run_selfhost_checks(quick=args.quick)

        if args.command == "selfhost-compare":
            return run_selfhost_compare(args.file)

        if args.command == "trust":
            return run_trust(args.file, output=args.output)

        if args.command == "trust-project":
            return run_trust_project(args.directory, output=args.output)

        if args.command == "project-check":
            return run_project_check(args.directory, json_output=args.json, locked=args.locked)

        if args.command == "project-run":
            return run_project_run(args.directory, locked=args.locked)

        if args.command == "project-test":
            return run_project_test(args.directory, locked=args.locked)

        if args.command == "project-info":
            return run_project_info(args.directory, json_output=args.json)

        if args.command == "project-init":
            return run_project_init(args.directory, name=args.name)

        if args.command == "new":
            return run_project_init(args.directory, name=args.name, template=args.template)

        if args.command == "project-lock":
            return run_project_lock(args.directory)

        if args.command == "project-format":
            return run_project_format(args.directory, check=args.check)

        if args.command == "golden":
            return run_golden(args.file, update=args.update)

        if args.command == "docs":
            return run_docs(args.file, output=args.output)

        if args.command == "repl":
            return run_repl()

        if args.command == "compile":
            source = args.file.read_text(encoding="utf-8-sig")
            program = parse_source(source)
            diagnostics = check_program(program)
            errors = [d for d in diagnostics if d.level == "error"]
            if errors:
                for d in diagnostics:
                    print(d.format(), file=sys.stderr)
                return 1
            mod = compile_program(program, source_path=str(args.file.resolve()))
            output_path = args.output or args.file.with_suffix(".mbc")
            data = mod.serialize()
            output_path.write_bytes(data)
            print(f"compiled {args.file} -> {output_path}  ({len(data)} bytes)")
            return 0

        if args.command == "run-vm":
            if args.file.suffix.lower() == ".mbc":
                data = args.file.read_bytes()
                from .bytecode import BytecodeModule
                mod = BytecodeModule.deserialize(data)
            else:
                source = args.file.read_text(encoding="utf-8-sig")
                program = parse_source(source)
                diagnostics = check_program(program)
                errors = [d for d in diagnostics if d.level == "error"]
                if errors:
                    for d in diagnostics:
                        print(d.format(), file=sys.stderr)
                    return 1
                mod = compile_program(program, source_path=str(args.file.resolve()))
            base = args.source_root or args.file.parent
            vm = VM(base_path=base)
            vm.load_module(mod)
            vm.run()
            return 0

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
            if getattr(args, "frontend", "host") == "moss":
                from .selfhost import SelfHostFrontend
                sf = SelfHostFrontend()
                for token in sf.tokenize(source):
                    print(repr(token))
            else:
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
            mod = compile_program(program, source_path=str(args.file.resolve()))
            vm = VM(base_path=args.file.parent)
            vm.load_module(mod)
            if args.command == "run":
                vm.run()
            else:
                results = vm.run_tests()
                for result in results:
                    marker = "PASS" if result["status"] == "pass" else "FAIL"
                    detail = f": {result['message']}" if result["message"] else ""
                    print(f"{marker} {result['name']}{detail}")
                failed = sum(1 for result in results if result["status"] == "fail")
                print(f"{len(results) - failed}/{len(results)} tests passed")
                return 1 if failed else 0
            return 0

        if args.command == "trace":
            diagnostics = check_program(program)
            errors = [d for d in diagnostics if d.level == "error"]
            if errors:
                for diagnostic in diagnostics:
                    print(diagnostic.format(), file=sys.stderr)
                return 1
            mod = compile_program(program, source_path=str(args.file.resolve()))
            vm = VM(output=lambda _text: None, base_path=args.file.parent, trace_rules=True)
            vm.load_module(mod)
            vm.run()
            events = [portable_trace_event(event) for event in vm.trace_events]
            if args.json:
                print(json.dumps({"file": args.file.as_posix(), "events": events}))
            else:
                for event in events:
                    location = f"{event.get('line')}:{event.get('column')} " if event.get("line") else ""
                    arguments = ", ".join(f"{name}={value}" for name, value in event["arguments"].items())
                    print(f"{location}{event['rule']}({arguments}) -> {event['result']}")
                print(f"{len(events)} rule evaluation(s)")
            return 0

        parser.error(f"unknown command {args.command}")
        return 2
    except OSError as exc:
        print(f"moss: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
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


def portable_trace_event(event: dict) -> dict:
    result = dict(event)
    if "file" not in result:
        return result
    path = Path(result["file"]).resolve()
    try:
        path = path.relative_to(Path.cwd().resolve())
    except ValueError:
        pass
    result["file"] = path.as_posix()
    return result


def run_project_check(directory: Path, *, json_output: bool = False, locked: bool = False) -> int:
    manifest_path = find_manifest(directory)
    if manifest_path is not None:
        return run_manifest_project_check(manifest_path, json_output=json_output, locked=locked)
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


def run_manifest_project_check(manifest_path: Path, *, json_output: bool = False, locked: bool = False) -> int:
    manifest = load_manifest(manifest_path)
    graph = build_project_graph(manifest)
    results: list[dict] = []
    diagnostics = list(graph.diagnostics)
    if locked:
        diagnostics.extend(verify_project_lock(graph))

    for path in sorted(graph.programs):
        program = graph.programs[path]
        file_diagnostics = [diagnostic_json(item) for item in check_program(program)]
        for item in file_diagnostics:
            diagnostics.append({"file": graph.relative(path), **item})
        results.append(
            {
                "file": graph.relative(path),
                "ok": not any(item["level"] == "error" for item in file_diagnostics),
                "diagnostics": file_diagnostics,
                "summary": summarize(program),
            }
        )

    package_diagnostics = [diagnostic_json(item) for item in check_program(graph.combined_program())]
    diagnostics.extend({"file": "<package>", **item} for item in package_diagnostics)
    error_count = sum(1 for item in diagnostics if item["level"] == "error")
    warning_count = sum(1 for item in diagnostics if item["level"] == "warning")
    payload = {
        "ok": error_count == 0,
        "package": graph.as_json()["package"],
        "files": results,
        "graph": graph.as_json()["modules"],
        "diagnostics": diagnostics,
        "summary": {"files": len(results), "errors": error_count, "warnings": warning_count},
    }
    if json_output:
        print(json.dumps(payload))
    else:
        for diagnostic in diagnostics:
            location = f"{diagnostic.get('line')}:{diagnostic.get('column')}: " if diagnostic.get("line") else ""
            print(f"{diagnostic['file']}: {diagnostic['level']}: {location}{diagnostic['message']}")
        print(
            f"project {manifest.name} {manifest.version}: "
            f"{len(results)} module(s), {warning_count} warning(s), {error_count} error(s)"
        )
    return 1 if error_count else 0


def run_project_info(directory: Path, *, json_output: bool = False) -> int:
    manifest_path = find_manifest(directory)
    if manifest_path is None:
        raise ValueError(f"no moss.toml found from {directory}")
    graph = build_project_graph(load_manifest(manifest_path))
    payload = graph.as_json()
    if json_output:
        print(json.dumps(payload))
    else:
        package = payload["package"]
        print(f"{package['name']} {package['version']} ({package['entry']})")
        for module in payload["modules"]:
            dependencies = ", ".join(module["imports"]) or "-"
            print(f"  {module['path']} -> {dependencies}")
        for diagnostic in payload["diagnostics"]:
            print(f"{diagnostic['file']}: {diagnostic['level']}: {diagnostic['message']}")
    return 1 if any(item["level"] == "error" for item in graph.diagnostics) else 0


def run_project_run(directory: Path, *, locked: bool = False) -> int:
    manifest_path = find_manifest(directory)
    if manifest_path is None:
        raise ValueError(f"no moss.toml found from {directory}")
    manifest = load_manifest(manifest_path)
    graph = build_project_graph(manifest)
    if locked:
        graph.diagnostics.extend(verify_project_lock(graph))
    if graph.diagnostics:
        for diagnostic in graph.diagnostics:
            print(f"{diagnostic['file']}: {diagnostic['level']}: {diagnostic['message']}", file=sys.stderr)
        return 1
    program = graph.programs[manifest.entry]
    diagnostics = check_program(graph.combined_program())
    errors = [item for item in diagnostics if item.level == "error"]
    if errors:
        for diagnostic in diagnostics:
            print(diagnostic.format(), file=sys.stderr)
        return 1
    vm = VM(base_path=manifest.entry.parent, import_paths=[*manifest.source_roots, manifest.root])
    mod = compile_program(program, source_path=str(manifest.entry.resolve()))
    vm.load_module(mod)
    vm.run()
    return 0

def run_project_test(directory: Path, *, locked: bool = False) -> int:
    manifest_path = find_manifest(directory)
    if manifest_path is None:
        raise ValueError(f"no moss.toml found from {directory}")
    manifest = load_manifest(manifest_path)
    graph = build_project_graph(manifest)
    if locked:
        graph.diagnostics.extend(verify_project_lock(graph))
    if graph.diagnostics:
        for diagnostic in graph.diagnostics:
            print(f"{diagnostic['file']}: {diagnostic['level']}: {diagnostic['message']}", file=sys.stderr)
        return 1
    diagnostics = check_program(graph.combined_program())
    errors = [item for item in diagnostics if item.level == "error"]
    if errors:
        for diagnostic in diagnostics:
            print(diagnostic.format(), file=sys.stderr)
        return 1
    program = graph.programs[manifest.entry]
    vm = VM(base_path=manifest.entry.parent, import_paths=[*manifest.source_roots, manifest.root])
    mod = compile_program(program, source_path=str(manifest.entry.resolve()))
    vm.load_module(mod)
    results = vm.run_tests()
    for result in results:
        marker = "PASS" if result["status"] == "pass" else "FAIL"
        detail = f": {result['message']}" if result["message"] else ""
        print(f"{marker} {result['name']}{detail}")
    failed = sum(1 for result in results if result["status"] == "fail")
    print(f"{len(results) - failed}/{len(results)} project tests passed")
    return 1 if failed else 0


def run_project_init(directory: Path, *, name: str | None = None, template: str = "basic") -> int:
    package_name = name or directory.resolve().name
    manifest = initialize_project(directory, package_name, template)
    print(f"created {manifest.name} at {manifest.root}")
    print(f"template: {template}")
    print(f"entry: {manifest.entry.relative_to(manifest.root).as_posix()}")
    return 0


def run_project_lock(directory: Path) -> int:
    manifest_path = find_manifest(directory)
    if manifest_path is None:
        raise ValueError(f"no moss.toml found from {directory}")
    graph = build_project_graph(load_manifest(manifest_path))
    if graph.diagnostics:
        for diagnostic in graph.diagnostics:
            print(f"{diagnostic['file']}: {diagnostic['level']}: {diagnostic['message']}", file=sys.stderr)
        return 1
    path = write_project_lock(graph)
    print(f"locked {len(graph.programs)} module(s): {path}")
    return 0


def run_project_format(directory: Path, *, check: bool = False) -> int:
    from .formatter import format_source

    manifest_path = find_manifest(directory)
    if manifest_path is None:
        raise ValueError(f"no moss.toml found from {directory}")
    graph = build_project_graph(load_manifest(manifest_path))
    if graph.diagnostics:
        for diagnostic in graph.diagnostics:
            print(f"{diagnostic['file']}: {diagnostic['level']}: {diagnostic['message']}", file=sys.stderr)
        return 1
    changed: list[Path] = []
    for path in sorted(graph.programs):
        source = path.read_text(encoding="utf-8-sig")
        formatted = format_source(source)
        if formatted == source:
            continue
        changed.append(path)
        if not check:
            path.write_text(formatted, encoding="utf-8")
    for path in changed:
        prefix = "needs formatting" if check else "formatted"
        print(f"{prefix}: {graph.relative(path)}")
    print(f"project format: {len(graph.programs)} module(s), {len(changed)} changed")
    return 1 if check and changed else 0


def run_golden(path: Path, *, update: bool = False) -> int:
    source = path.read_text(encoding="utf-8-sig")
    program = parse_source(source)
    diagnostics = check_program(program)
    errors = [item for item in diagnostics if item.level == "error"]
    if errors:
        for diagnostic in diagnostics:
            print(diagnostic.format(), file=sys.stderr)
        return 1
    output: list[str] = []
    buf = StringIO()
    vm = VM(output=buf.write, base_path=path.parent)
    mod = compile_program(program, source_path=str(path.resolve()))
    vm.load_module(mod)
    vm.run()
    actual = buf.getvalue()
    golden_path = path.with_suffix(path.suffix + ".golden")
    if update:
        golden_path.write_text(actual, encoding="utf-8")
        print(f"updated: {golden_path}")
        return 0
    if not golden_path.is_file():
        print(f"missing golden file: {golden_path}", file=sys.stderr)
        return 1
    expected = golden_path.read_text(encoding="utf-8")
    if expected != actual:
        print(f"golden output mismatch: {golden_path}", file=sys.stderr)
        return 1
    print(f"PASS {path}")
    return 0


def run_trust(path: Path, *, output: Path | None = None) -> int:
    """Produce a trust bundle for a Moss program."""
    import hashlib

    source = path.read_text(encoding="utf-8-sig")
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    bundle: dict = {
        "moss": __version__,
        "file": path.as_posix(),
        "source_sha256": source_hash,
        "trust": True,
    }

    # 1. Static check
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
        "summary": {
            "effects": sum(1 for item in program.items if type(item).__name__ == "EffectDecl"),
            "imports": sum(1 for item in program.items if type(item).__name__ == "ImportDecl"),
            "types": sum(1 for item in program.items if type(item).__name__ == "TypeDecl"),
            "callables": sum(1 for item in program.items if type(item).__name__ in ("RuleDecl", "FunctionDecl")),
            "tests": sum(1 for item in program.items if type(item).__name__ == "TestDecl"),
        },
    }

    # 2. Lock verification
    lock_path = path.parent / "moss.lock"
    if lock_path.exists():
        from .project import verify_project_lock, build_project_graph, find_manifest, load_manifest
        try:
            manifest_path = find_manifest(path.parent)
            if manifest_path:
                manifest = load_manifest(manifest_path)
                graph = build_project_graph(manifest)
                lock_diags = verify_project_lock(graph)
                bundle["lock"] = {
                    "ok": len(lock_diags) == 0,
                    "locked": True,
                    "diagnostics": lock_diags if lock_diags else None,
                }
                if lock_diags:
                    bundle["trust"] = False
            else:
                bundle["lock"] = {"ok": None, "locked": False, "note": "no moss.toml found"}
        except Exception as e:
            bundle["lock"] = {"ok": False, "locked": False, "error": str(e)}
            bundle["trust"] = False
    else:
        bundle["lock"] = {"ok": None, "locked": False, "note": "no moss.lock file"}

    # 3. Trace rule evaluations
    if not chk_errors:
        vm_trace = VM(output=lambda _t: None, base_path=path.parent, trace_rules=True)
        mod_trace = compile_program(program, source_path=str(path.resolve()))
        vm_trace.load_module(mod_trace)
        vm_trace.run()
        bundle["trace"] = {
            "ok": True,
            "events": [
                portable_trace_event(e) for e in vm_trace.trace_events
            ],
        }
    else:
        bundle["trace"] = {"ok": False, "events": []}
        bundle["trust"] = False

    # 4. Golden snapshot
    if not chk_errors:
        buf = StringIO()
        vm_golden = VM(output=buf.write, base_path=path.parent)
        mod_golden = compile_program(program, source_path=str(path.resolve()))
        vm_golden.load_module(mod_golden)
        vm_golden.run()
        actual = buf.getvalue()
        golden_path = path.with_suffix(path.suffix + ".golden")
        if golden_path.is_file():
            expected = golden_path.read_text(encoding="utf-8")
            golden_ok = expected == actual
            if not golden_ok:
                bundle["trust"] = False
            bundle["golden"] = {
                "ok": golden_ok,
                "snapshot": actual,
                "expected": expected if not golden_ok else None,
            }
        else:
            bundle["golden"] = {"ok": None, "snapshot": actual, "note": "no .golden file"}
    else:
        bundle["golden"] = {"ok": False, "snapshot": None}
        bundle["trust"] = False

    # 5. Self-host comparison with full details
    _saved_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        details = compare_selfhost_details(path)
    finally:
        sys.stdout = _saved_stdout
    bundle["selfhost"] = {
        "ok": details["ok"],
        "declarations_match": details["declarations_match"],
        "names_match": details["names_match"],
        "bodies_match": details["bodies_match"],
        "metadata_match": details["metadata_match"],
        "expressions_match": details["expressions_match"],
        "host_summary": details["host"],
        "selfhost_summary": details["selfhost"],
        "selfhost_errors": details["errors"] if details["errors"] else None,
        "expression_error": details["expression_error"],
        "host_names": details["host_names"],
        "selfhost_names": details["selfhost_names"],
        "host_bodies": details["host_bodies"],
        "selfhost_bodies": details["selfhost_bodies"],
        "host_metadata": details["host_metadata"],
        "selfhost_metadata": details["selfhost_metadata"],
    }
    if not details["ok"]:
        bundle["trust"] = False

    trust_json = json.dumps(bundle, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(trust_json, encoding="utf-8")
        print(f"trust bundle written: {output}")
    else:
        print(trust_json)
    return 0 if bundle["trust"] else 1


def run_trust_project(directory: Path, *, output: Path | None = None) -> int:
    """Produce a project-wide trust bundle."""
    import hashlib
    from .project import find_manifest, load_manifest, build_project_graph, verify_project_lock

    directory = directory.resolve()
    manifest_path = find_manifest(directory)
    if manifest_path is None:
        raise ValueError(f"no moss.toml found from {directory}")

    manifest = load_manifest(manifest_path)
    graph = build_project_graph(manifest)
    lock_diags = verify_project_lock(graph)

    bundle: dict = {
        "moss": __version__,
        "project": manifest.name,
        "root": str(directory),
        "entry": str(manifest.entry.relative_to(manifest.root)),
        "trust": True,
    }

    # Lock verification
    bundle["lock"] = {
        "ok": len(lock_diags) == 0,
        "modules": len(graph.programs),
        "diagnostics": lock_diags if lock_diags else None,
    }
    if lock_diags:
        bundle["trust"] = False

    # Per-file trust results
    files: list[dict] = []
    for module_path in sorted(graph.programs):
        rel = module_path.relative_to(manifest.root) if module_path.is_relative_to(manifest.root) else module_path
        source = module_path.read_text(encoding="utf-8-sig")
        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        program = graph.programs.get(module_path, parse_source(source))
        diagnostics = check_program(program)
        chk_errors = [d for d in diagnostics if d.level == "error"]

        file_result: dict = {
            "file": str(rel),
            "source_sha256": source_hash,
            "check": {
                "ok": len(chk_errors) == 0,
                "diagnostics": [
                    {"level": d.level, "message": d.message,
                     "line": d.location.line if d.location else None,
                     "column": d.location.column if d.location else None}
                    for d in diagnostics
                ],
                "summary": {
                    "effects": sum(1 for item in program.items if type(item).__name__ == "EffectDecl"),
                    "imports": sum(1 for item in program.items if type(item).__name__ == "ImportDecl"),
                    "types": sum(1 for item in program.items if type(item).__name__ == "TypeDecl"),
                    "callables": sum(1 for item in program.items if type(item).__name__ in ("RuleDecl", "FunctionDecl")),
                    "tests": sum(1 for item in program.items if type(item).__name__ == "TestDecl"),
                },
            },
        }

        if chk_errors:
            file_result["trust"] = False
            bundle["trust"] = False
        else:
            file_result["trust"] = True

        files.append(file_result)

    bundle["files"] = files
    bundle["summary"] = {
        "files": len(files),
        "trusted": sum(1 for f in files if f.get("trust", False)),
        "failed": sum(1 for f in files if not f.get("trust", False)),
    }

    trust_json = json.dumps(bundle, indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(trust_json, encoding="utf-8")
        print(f"project trust bundle written: {output}")
    else:
        print(trust_json)
    return 0 if bundle["trust"] else 1


def run_docs(path: Path, *, output: Path | None = None) -> int:
    from .docsgen import generate_api_docs

    rendered = generate_api_docs(path)
    if output is None:
        print(rendered, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"generated: {output}")
    return 0


def run_repl(*, input_fn=input, output_fn=print) -> int:
    vm = VM()
    source_buffer: list[str] = []
    buffer: list[str] = []
    depth = 0
    output_fn(f"Moss {__version__} REPL. Submit a blank line to run; Ctrl-D to exit.")

    while True:
        try:
            line = input_fn("... " if buffer else "moss> ")
        except (EOFError, KeyboardInterrupt, StopIteration):
            output_fn("")
            return 0

        if not line.strip():
            if buffer:
                depth = 0
            else:
                continue
        else:
            buffer.append(line)
            depth += brace_delta(line)
            if depth > 0 or line.strip().endswith(("=", "else")):
                continue

        if not buffer:
            continue
        line_source = "\n".join(buffer) + "\n"
        buffer = []
        source_buffer.append(line_source)
        # Recompile full accumulated source to preserve state
        full_source = "".join(source_buffer)
        try:
            program = parse_source(full_source)
            diagnostics = check_program(program)
            errors = [item for item in diagnostics if item.level == "error"]
            for diagnostic in diagnostics:
                output_fn(diagnostic.format())
            if not errors:
                vm.output = output_fn
                mod = compile_program(program, source_path="<repl>")
                vm.load_module(mod)
                vm.run()
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

        vm = VM(base_path=root)
        mod = compile_program(program, source_path=str(path.resolve()))
        vm.load_module(mod)
        results = vm.run_tests()
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
    details = compare_selfhost_details(path)
    print(f"{path}:")
    print(f"  host: {details['host']}")
    print(f"  selfhost: {details['selfhost']}")
    if details["errors"]:
        for error in details["errors"]:
            print(f"  selfhost parse error: {error}")
        return False
    if not details["declarations_match"]:
        print("  selfhost comparison failed")
        return False
    if not details["names_match"]:
        print(f"  host names: {details['host_names']}")
        print(f"  selfhost names: {details['selfhost_names']}")
        print("  selfhost declaration-name comparison failed")
        return False
    if not details["bodies_match"]:
        print(f"  host body statements: {details['host_bodies']}")
        print(f"  selfhost body statements: {details['selfhost_bodies']}")
        print("  selfhost body-structure comparison failed")
        return False
    if not details["metadata_match"]:
        print(f"  host metadata: {details['host_metadata']}")
        print(f"  selfhost metadata: {details['selfhost_metadata']}")
        print("  selfhost declaration-metadata comparison failed")
        return False
    if details["expression_error"] is not None:
        print(f"  expression AST comparison failed: {details['expression_error']}")
        return False
    print("  selfhost comparison passed")
    return True


def compare_selfhost_details(path: Path) -> dict:
    """Return structured selfhost comparison for trust bundles."""
    source = path.read_text(encoding="utf-8")
    host_program = parse_source(source)
    host = summarize(host_program)
    host_names = host_declaration_names(host_program)
    host_bodies = host_body_statement_kinds(host_program)
    host_metadata = host_declaration_metadata(host_program)

    root = installation_root()
    vm = VM(base_path=root)
    importer = compile_program(parse_source('import "examples/self_host/parser_core.moss"\n'), source_path=str(root / "examples/self_host/parser_core.moss"))
    vm.load_module(importer)
    vm.run()
    tokens = vm.call(vm.globals.get("sketchTokens"), [source])
    parsed = vm.call(vm.globals.get("parseProgram"), [tokens])
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
    expression_error = compare_expression_asts(host_program, vm)

    declarations_match = (not errors) and host == selfhost
    names_match = host_names == selfhost_names
    bodies_match = host_bodies == selfhost_bodies
    metadata_match = host_metadata == selfhost_metadata
    expressions_match = expression_error is None

    return {
        "ok": declarations_match and names_match and bodies_match and metadata_match and expressions_match,
        "host": host,
        "selfhost": selfhost,
        "declarations_match": declarations_match,
        "errors": errors,
        "host_names": host_names if not names_match else None,
        "selfhost_names": selfhost_names if not names_match else None,
        "names_match": names_match,
        "host_bodies": host_bodies if not bodies_match else None,
        "selfhost_bodies": selfhost_bodies if not bodies_match else None,
        "bodies_match": bodies_match,
        "host_metadata": host_metadata if not metadata_match else None,
        "selfhost_metadata": selfhost_metadata if not metadata_match else None,
        "metadata_match": metadata_match,
        "expression_error": expression_error,
        "expressions_match": expressions_match,
    }


def compare_expression_asts(program, vm) -> str | None:
    for expression in program_expressions(program):
        source = render_expr(expression)
        parsed = vm.call(vm.globals.get("parseExpressionSource"), [source])
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
