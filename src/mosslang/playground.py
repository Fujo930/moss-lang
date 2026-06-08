"""Moss Playground — trust report viewer.

Run with `moss playground` to serve a browser-based trust report
at http://127.0.0.1:8766.  The frontend is a single self-contained
HTML page that can also be deployed to GitHub Pages.
"""

from __future__ import annotations

import json
import tempfile
import hashlib
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from io import StringIO
from pathlib import Path

from .parser import parse_source
from .checker import check_program
from .compiler import compile_program
from .vm import VM
from .errors import MossError
from .cli import portable_trace_event


PLAYGROUND_PORT = 8766


def asset_bytes(name: str) -> bytes:
    asset = resources.files("mosslang").joinpath("playground_assets", name)
    return asset.read_bytes()


def run_trust_from_source(source: str) -> dict:
    """Run the full trust pipeline on a source string and return a bundle dict."""
    import hashlib

    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    bundle: dict = {
        "moss": _get_version(),
        "source_sha256": source_hash,
        "trust": True,
    }

    # 1. Parse
    try:
        program = parse_source(source)
    except MossError as e:
        return {
            "moss": _get_version(),
            "source_sha256": source_hash,
            "trust": False,
            "check": {
                "ok": False,
                "diagnostics": [{
                    "level": "error", "message": getattr(e, "message", str(e)),
                    "line": getattr(e, "location", None) and e.location.line,
                    "column": getattr(e, "location", None) and e.location.column,
                }],
                "summary": {"effects": 0, "imports": 0, "types": 0, "callables": 0, "tests": 0},
            },
            "trace": {"ok": False, "events": []},
            "golden": {"ok": False, "snapshot": None},
            "error": str(e),
        }

    # 2. Check
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

    # 3. Trace & Golden
    if not chk_errors:
        try:
            vm_trace = VM(output=lambda _t: None, base_path=Path.cwd(), trace_rules=True)
            mod = compile_program(program, source_path="<playground>")
            vm_trace.load_module(mod)
            vm_trace.run()
            bundle["trace"] = {
                "ok": True,
                "events": [portable_trace_event(e) for e in vm_trace.trace_events],
            }

            buf = StringIO()
            vm_out = VM(output=buf.write, base_path=Path.cwd())
            mod2 = compile_program(program, source_path="<playground>")
            vm_out.load_module(mod2)
            vm_out.run()
            bundle["golden"] = {"ok": None, "snapshot": buf.getvalue(), "note": "no .golden file in playground"}
        except Exception as e:
            bundle["trace"] = {"ok": False, "events": [], "error": str(e)}
            bundle["golden"] = {"ok": False, "snapshot": None, "error": str(e)}
            bundle["trust"] = False
    else:
        bundle["trace"] = {"ok": False, "events": []}
        bundle["golden"] = {"ok": False, "snapshot": None}
        bundle["trust"] = False

    return bundle


def _get_version() -> str:
    from . import __version__
    return __version__


def _playground_html() -> bytes:
    return asset_bytes("index.html")


def make_playground_handler() -> type[BaseHTTPRequestHandler]:
    class PlaygroundHandler(BaseHTTPRequestHandler):
        server_version = "MossPlayground/0.1"

        def do_GET(self) -> None:
            if self.path in {"/", "/index.html"}:
                self._send_html()
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            try:
                body = json.loads(self.rfile.read(length)) if length else {}
            except json.JSONDecodeError:
                self.send_json({"error": "invalid JSON"}, 400)
                return

            if self.path == "/api/trust":
                source = body.get("source", "")
                if not source.strip():
                    self.send_json({"error": "no source provided"}, 400)
                    return
                bundle = run_trust_from_source(source)
                self.send_json(bundle)
                return

            self.send_error(HTTPStatus.NOT_FOUND)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def _send_html(self) -> None:
            data = _playground_html()
            self._send_bytes(data, "text/html; charset=utf-8")

        def _send_bytes(self, data: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, payload: dict, status: int = 200) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):
            pass  # silent

    return PlaygroundHandler


def run_playground(host: str = "127.0.0.1", port: int = PLAYGROUND_PORT) -> None:
    server = ThreadingHTTPServer((host, port), make_playground_handler())
    address = f"http://{host}:{server.server_port}"
    print(f"Moss Playground running at {address}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
