from __future__ import annotations

import ast
import json
import os
import pprint
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any

from .checker import Diagnostic, check_program
from .errors import MossError
from .parser import parse_source
from .runtime import Runtime
from .tokens import tokenize


ASSET_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}

EXAMPLES = {
    "Order workflow": "order.moss",
    "Not ready result": "not_ready.moss",
    "Match expression": "match_demo.moss",
    "Lists and loops": "lists_demo.moss",
    "Text and files": "text_fs_demo.moss",
    "Maps": "map_demo.moss",
    "Imports": "import_demo.moss",
    "Tokenizer sketch": "self_host/tokenizer_sketch.moss",
    "Parser sketch": "self_host/parser_sketch.moss",
    "Checker sketch": "self_host/checker_sketch.moss",
}


def analyze_source(
    source: str,
    *,
    execute: bool,
    test: bool = False,
    path: str | None = None,
) -> dict[str, Any]:
    output: list[str] = []
    response: dict[str, Any] = {
        "ok": False,
        "diagnostics": [],
        "output": output,
        "tokens": [],
        "ast": "",
        "summary": {"effects": 0, "imports": 0, "types": 0, "callables": 0, "tests": 0},
    }

    try:
        program = parse_source(source)
        diagnostics = check_program(program)
        response["diagnostics"] = [diagnostic_to_json(diagnostic) for diagnostic in diagnostics]
        response["tokens"] = [
            {"kind": token.kind, "value": token.value, "line": token.line, "column": token.column}
            for token in tokenize(source)
            if token.kind != "EOF"
        ]
        response["ast"] = pprint.pformat(program, width=96)
        response["summary"] = summarize_program(program)

        if any(d.level == "error" for d in diagnostics):
            return response

        if execute:
            runtime = Runtime(output.append, base_path=analysis_base_path(path))
            if test:
                results = runtime.run_tests(program)
                for result in results:
                    marker = "PASS" if result["status"] == "pass" else "FAIL"
                    detail = f": {result['message']}" if result["message"] else ""
                    output.append(f"{marker} {result['name']}{detail}")
                failed = sum(1 for result in results if result["status"] == "fail")
                output.append(f"{len(results) - failed}/{len(results)} tests passed")
                response["ok"] = failed == 0
                return response
            runtime.run(program)
        response["ok"] = True
        return response
    except MossError as exc:
        diagnostic: dict[str, Any] = {"level": "error", "message": getattr(exc, "message", str(exc))}
        location = getattr(exc, "location", None)
        if location is not None:
            diagnostic["line"] = location.line
            diagnostic["column"] = location.column
        response["diagnostics"].append(diagnostic)
        response["output"].append(f"moss: {exc}")
        return response


def diagnostic_to_json(diagnostic: Diagnostic) -> dict[str, Any]:
    result: dict[str, Any] = {"level": diagnostic.level, "message": diagnostic.message}
    if diagnostic.location is not None:
        result["line"] = diagnostic.location.line
        result["column"] = diagnostic.location.column
    return result


def summarize_program(program: Any) -> dict[str, int]:
    return {
        "effects": sum(1 for item in program.items if item.__class__.__name__ == "EffectDecl"),
        "imports": sum(1 for item in program.items if item.__class__.__name__ == "ImportDecl"),
        "types": sum(1 for item in program.items if item.__class__.__name__ == "TypeDecl"),
        "callables": sum(1 for item in program.items if item.__class__.__name__ in {"RuleDecl", "FunctionDecl"}),
        "tests": sum(1 for item in program.items if item.__class__.__name__ == "TestDecl"),
    }


def workspace_root() -> Path:
    configured = os.environ.get("MOSS_WORKSPACE")
    if configured:
        return Path(configured).expanduser()
    if getattr(sys, "frozen", False):
        return Path.home() / "Documents" / "Moss Workspace"
    return Path(__file__).resolve().parents[2]


def resolve_workspace_path(path_text: str) -> Path:
    if not path_text.strip():
        raise ValueError("path is required")
    if "\0" in path_text:
        raise ValueError("path cannot contain null bytes")

    root = workspace_root().resolve()
    path = Path(path_text)
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("path must stay inside the Moss workspace") from exc
    return resolved


def workspace_relative_path(path: Path) -> str:
    return path.resolve().relative_to(workspace_root().resolve()).as_posix()


def analysis_base_path(path_text: str | None) -> Path:
    if path_text is None or not path_text.strip():
        return Path.cwd()
    try:
        return resolve_workspace_path(path_text).parent
    except ValueError:
        return Path.cwd()


def asset_bytes(name: str) -> bytes:
    asset = resources.files("mosslang").joinpath("studio_assets", name)
    return asset.read_bytes()


def example_source(filename: str) -> str:
    frozen_root = getattr(sys, "_MEIPASS", None)
    root = Path(frozen_root) if frozen_root is not None else Path(__file__).resolve().parents[2]
    return (root / "examples" / filename).read_text(encoding="utf-8")


def make_handler() -> type[BaseHTTPRequestHandler]:
    class StudioHandler(BaseHTTPRequestHandler):
        server_version = "MossStudio/0.1"

        def do_GET(self) -> None:
            if self.path in {"/", "/index.html"}:
                self.send_asset("index.html")
                return
            if self.path == "/app.css":
                self.send_asset("app.css")
                return
            if self.path == "/app.js":
                self.send_asset("app.js")
                return
            if self.path == "/moss-mark.svg":
                self.send_asset("moss-mark.svg")
                return
            if self.path == "/api/examples":
                examples = []
                for label, filename in EXAMPLES.items():
                    examples.append({"label": label, "filename": filename, "source": example_source(filename)})
                self.send_json({"examples": examples})
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except json.JSONDecodeError:
                self.send_json({"ok": False, "diagnostics": [{"level": "error", "message": "invalid JSON"}]}, status=400)
                return

            if self.path == "/api/file/read":
                self.handle_file_read(payload)
                return
            if self.path == "/api/file/write":
                self.handle_file_write(payload)
                return

            source = str(payload.get("source", ""))
            path = str(payload.get("path", ""))
            if self.path == "/api/check":
                self.send_json(analyze_source(source, execute=False))
                return
            if self.path == "/api/run":
                self.send_json(analyze_source(source, execute=True, path=path))
                return
            if self.path == "/api/test":
                self.send_json(analyze_source(source, execute=True, test=True, path=path))
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def handle_file_read(self, payload: dict[str, Any]) -> None:
            try:
                path = resolve_workspace_path(str(payload.get("path", "")))
                if not path.is_file():
                    self.send_json({"ok": False, "message": "file not found"}, status=404)
                    return
                self.send_json(
                    {"ok": True, "path": workspace_relative_path(path), "source": path.read_text(encoding="utf-8-sig")}
                )
            except (OSError, ValueError) as exc:
                self.send_json({"ok": False, "message": str(exc)}, status=400)

        def handle_file_write(self, payload: dict[str, Any]) -> None:
            try:
                path = resolve_workspace_path(str(payload.get("path", "")))
                source = str(payload.get("source", ""))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding="utf-8")
                self.send_json({"ok": True, "path": workspace_relative_path(path)})
            except (OSError, ValueError) as exc:
                self.send_json({"ok": False, "message": str(exc)}, status=400)

        def send_asset(self, name: str) -> None:
            data = asset_bytes(name)
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ASSET_TYPES.get(Path(name).suffix, "application/octet-stream"))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:
            return

    return StudioHandler


def run_studio(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), make_handler())
    address = f"http://{host}:{server.server_port}"
    print(f"Moss Studio running at {address}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
