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

    for command in ("run", "check", "tokens", "ast"):
        cmd = sub.add_parser(command)
        cmd.add_argument("file", type=Path)

    studio_cmd = sub.add_parser("studio")
    studio_cmd.add_argument("--host", default="127.0.0.1")
    studio_cmd.add_argument("--port", type=int, default=8765)

    args = parser.parse_args(argv)

    try:
        if args.command == "studio":
            from .studio import run_studio

            run_studio(args.host, args.port)
            return 0

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
            effect_count = sum(1 for item in program.items if item.__class__.__name__ == "EffectDecl")
            type_count = sum(1 for item in program.items if item.__class__.__name__ == "TypeDecl")
            callable_count = sum(1 for item in program.items if item.__class__.__name__ in {"RuleDecl", "FunctionDecl"})
            print(f"ok: {effect_count} effect block(s), {type_count} type(s), {callable_count} callable(s)")
            return 0

        if args.command == "run":
            diagnostics = check_program(program)
            errors = [d for d in diagnostics if d.level == "error"]
            if errors:
                for diagnostic in diagnostics:
                    print(f"{diagnostic.level}: {diagnostic.message}", file=sys.stderr)
                return 1
            Runtime().run(program)
            return 0

        parser.error(f"unknown command {args.command}")
        return 2
    except OSError as exc:
        print(f"moss: {exc}", file=sys.stderr)
        return 1
    except MossError as exc:
        print(f"moss: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
