from __future__ import annotations

import ast
import json
import pprint
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
}

EXAMPLES = {
    "Order workflow": "order.moss",
    "Not ready result": "not_ready.moss",
    "Match expression": "match_demo.moss",
    "Lists and loops": "lists_demo.moss",
    "Text and files": "text_fs_demo.moss",
}


def analyze_source(source: str, *, execute: bool, test: bool = False) -> dict[str, Any]:
    output: list[str] = []
    response: dict[str, Any] = {
        "ok": False,
        "diagnostics": [],
        "output": output,
        "tokens": [],
        "ast": "",
        "summary": {"effects": 0, "types": 0, "callables": 0, "tests": 0},
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
            runtime = Runtime(output.append)
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
        response["diagnostics"].append({"level": "error", "message": str(exc)})
        response["output"].append(f"moss: {exc}")
        return response


def diagnostic_to_json(diagnostic: Diagnostic) -> dict[str, str]:
    return {"level": diagnostic.level, "message": diagnostic.message}


def summarize_program(program: Any) -> dict[str, int]:
    return {
        "effects": sum(1 for item in program.items if item.__class__.__name__ == "EffectDecl"),
        "types": sum(1 for item in program.items if item.__class__.__name__ == "TypeDecl"),
        "callables": sum(1 for item in program.items if item.__class__.__name__ in {"RuleDecl", "FunctionDecl"}),
        "tests": sum(1 for item in program.items if item.__class__.__name__ == "TestDecl"),
    }


def asset_bytes(name: str) -> bytes:
    asset = resources.files("mosslang").joinpath("studio_assets", name)
    return asset.read_bytes()


def example_source(filename: str) -> str:
    root = Path(__file__).resolve().parents[2]
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

            source = str(payload.get("source", ""))
            if self.path == "/api/check":
                self.send_json(analyze_source(source, execute=False))
                return
            if self.path == "/api/run":
                self.send_json(analyze_source(source, execute=True))
                return
            if self.path == "/api/test":
                self.send_json(analyze_source(source, execute=True, test=True))
                return
            self.send_error(HTTPStatus.NOT_FOUND)

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
