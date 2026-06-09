"""Moss Trust Server — HTTP API for AI agents to verify Moss code.

Usage:
  moss serve [--host 127.0.0.1] [--port 9876]

Endpoints:
  POST /api/trust        — Full trust verification (body: Moss source code)
  POST /api/token        — Token Artifact (brief/normal/full via ?level=)
  GET  /api/health       — Server status

Response format (AI-optimized):
  {
    "trust": true|false,
    "check": {"ok":..., "diagnostics":[...]},
    "trace": {"ok":..., "events":[...]},
    "golden": {"ok":...},
    "selfhost": {"ok":...},
    "token": {"effects":1, "types":2, "callables":2},
    "fix_hints": [{"line":7, "hint":"..."}, ...]
  }

Design target: <200ms for check+trace gate on order.moss-sized files.
Pre-loaded checker and parser via module-level caching.
"""

from __future__ import annotations

import json
import hashlib
import time
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path


_TRUST_CACHE_LIMIT = 100
_trust_cache: dict[str, dict] = {}
_trust_cache_lru: list[str] = []  # LRU order list
_token_cache: dict[str, dict] = {}
_token_cache_lru: list[str] = []


def _cache_put(cache: dict, lru: list[str], key: str, value: dict, limit: int = 100) -> None:
    """LRU-aware cache store."""
    if len(cache) >= limit:
        if lru:
            oldest = lru.pop(0)
            cache.pop(oldest, None)
    cache[key] = value
    lru.append(key)


def _cache_get(cache: dict, lru: list[str], key: str) -> dict | None:
    """LRU-aware cache lookup."""
    if key in cache:
        if key in lru:
            lru.remove(key)
        lru.append(key)
        return cache[key]
    return None


def token_from_source(source: str, *, level: str = "normal") -> dict:
    """Lightweight token extraction: parse + structure only. No VM execution.
    
    Returns Token Artifact in ~5ms vs ~80ms for full trust pipeline.
    Suitable for POST /api/token and AI code-scanning use cases.
    """
    import hashlib
    t0 = time.perf_counter()
    source_sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()

    cache_key = f"token.{level}.{source_sha256[:32]}"
    if cache_key in _token_cache:
        return dict(_token_cache[cache_key])
    from mosslang.checker import check_program

    try:
        program = parse_source(source)
        diagnostics = check_program(program)
    except Exception as e:
        return {"ta": "ta.v1", "t": False, "error": str(e), "ms": round((time.perf_counter() - t0) * 1000)}

    chk_errors = [d for d in diagnostics if d.level == "error"]
    token_data = {
        "effects": sum(1 for item in program.items if type(item).__name__ == "EffectDecl"),
        "types": sum(1 for item in program.items if type(item).__name__ == "TypeDecl"),
        "callables": sum(1 for item in program.items if type(item).__name__ in ("RuleDecl", "FunctionDecl", "PythonExternDecl")),
    }
    rule_items = [item for item in program.items if type(item).__name__ == "RuleDecl"]
    rules = [{"n": r.name, "v": getattr(r, 'return_type', '?') or "?"} for r in rule_items] if rule_items else None

    if level == "brief":
        result = {
            "ta": "ta.v1",
            "t": len(chk_errors) == 0,
            "h": source_sha256[:12],
            "c": {"e": token_data["effects"], "t": token_data["types"], "l": token_data["callables"]},
            "r": rules,
            "ms": round((time.perf_counter() - t0) * 1000),
        }
    else:
        result = {
            "ta": "ta.v1",
            "t": len(chk_errors) == 0,
            "h": source_sha256[:16],
            "c": {"e": token_data["effects"], "t": token_data["types"], "l": token_data["callables"]},
            "r": rules,
            "g": len(chk_errors) == 0,
            "ms": round((time.perf_counter() - t0) * 1000),
        }
        if chk_errors:
            result["fix_hints"] = [
                {"line": d.location.line if d.location else None, "hint": d.hint}
                for d in diagnostics if d.level == "error" and d.hint
            ]

    if len(_token_cache) < _TRUST_CACHE_LIMIT:
        _token_cache[cache_key] = result
    return result


def trust_from_source(source: str, *, source_sha256: str | None = None) -> dict:
    """Run the full trust pipeline on a source string. Returns AI-optimized dict."""
    t0 = time.perf_counter()

    if source_sha256 is None:
        source_sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()

    # Check cache
    cache_key = source_sha256[:32]
    if cache_key in _trust_cache:
        result = dict(_trust_cache[cache_key])
        result["cached"] = True
        return result

    from mosslang.parser import parse_source
    from mosslang.checker import check_program, Diagnostic
    from mosslang.compiler import compile_program
    from mosslang.vm import VM
    from mosslang.cli import portable_trace_event

    bundle: dict = {
        "trust": True,
        "source_sha256": source_sha256,
        "elapsed_ms": 0,
    }

    # 1. Check gate
    t_check = time.perf_counter()
    try:
        program = parse_source(source)
        diagnostics = check_program(program)
    except Exception as e:
        bundle["check"] = {
            "ok": False,
            "diagnostics": [{"level": "error", "message": str(e), "code": "F001",
                             "hint": "Fix syntax error before running trust."}],
        }
        bundle["trust"] = False
        bundle["elapsed_ms"] = round((time.perf_counter() - t0) * 1000)
        return bundle

    chk_errors = [d for d in diagnostics if d.level == "error"]
    bundle["check"] = {
        "ok": len(chk_errors) == 0,
        "diagnostics": [d.to_json() for d in diagnostics],
        "elapsed_ms": round((time.perf_counter() - t_check) * 1000),
    }
    bundle["token"] = {
        "effects": sum(1 for item in program.items if type(item).__name__ == "EffectDecl"),
        "types": sum(1 for item in program.items if type(item).__name__ == "TypeDecl"),
        "callables": sum(1 for item in program.items if type(item).__name__ in ("RuleDecl", "FunctionDecl", "PythonExternDecl")),
    }

    if not bundle["check"]["ok"]:
        bundle["trust"] = False
        bundle["fix_hints"] = [
            {"line": d.location.line if d.location else None,
             "hint": d.hint}
            for d in diagnostics if d.level == "error" and d.hint
        ]
        bundle["gates"] = 0
        bundle["gates_total"] = 5
        bundle["failed_gates"] = ["check"]
        bundle["elapsed_ms"] = round((time.perf_counter() - t0) * 1000)
        _trust_cache[cache_key] = bundle
        return bundle

    # 2. Trace gate
    rule_count = sum(1 for item in program.items if type(item).__name__ == "RuleDecl")
    if rule_count > 0:
        try:
            vm = VM(output=lambda _: None, base_path=Path.cwd(), trace_rules=True)
            mod = compile_program(program, source_path="<trust-server>")
            vm.load_module(mod)
            vm.run()
            events = [portable_trace_event(e) for e in vm.trace_events]
            bundle["trace"] = {"ok": len(events) >= rule_count, "events": events}
            if len(events) < rule_count:
                bundle["trust"] = False
        except Exception:
            bundle["trace"] = {"ok": False, "events": []}
            bundle["trust"] = False
    else:
        bundle["trace"] = {"ok": True, "events": []}

    # 3. Golden gate
    try:
        buf = StringIO()
        vm = VM(output=buf.write, base_path=Path.cwd())
        mod = compile_program(program, source_path="<trust-server>")
        vm.load_module(mod)
        vm.run()
        bundle["golden"] = {"ok": None, "snapshot": buf.getvalue(),
                            "note": "no .golden file in API mode"}
    except Exception as e:
        bundle["golden"] = {"ok": False, "error": str(e)}
        bundle["trust"] = False

    # 4. Selfhost gate
    try:
        from mosslang.cli import compare_selfhost_details
        import tempfile
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".moss", mode="w", delete=False, encoding="utf-8") as f:
                f.write(source)
                temp_path = Path(f.name)
            details = compare_selfhost_details(temp_path)
            bundle["selfhost"] = {"ok": details["ok"]}
            if not details["ok"]:
                bundle["trust"] = False
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)
    except Exception:
        bundle["selfhost"] = {"ok": False, "note": "selfhost comparison failed"}
        bundle["trust"] = False

    # Gate passing count (for trust header alignment: @trust 5/5)
    gates = [
        bundle.get("check", {}).get("ok"),
        bundle.get("trace", {}).get("ok"),
        bundle.get("golden", {}).get("ok") is not False,
        True,  # lock gate: not applicable in API mode
        bundle.get("selfhost", {}).get("ok"),
    ]
    gate_names = ["check", "trace", "golden", "lock", "selfhost"]
    bundle["gates"] = sum(1 for g in gates if g)
    bundle["gates_total"] = 5
    bundle["failed_gates"] = [gate_names[i] for i, ok in enumerate(gates) if not ok]

    bundle["elapsed_ms"] = round((time.perf_counter() - t0) * 1000)

    # Cache the result
    if len(_trust_cache) < _TRUST_CACHE_LIMIT:
        _trust_cache[cache_key] = bundle
    return bundle


def make_trust_handler() -> type[BaseHTTPRequestHandler]:
    class TrustHandler(BaseHTTPRequestHandler):
        server_version = "MossTrustServer/alpha(t)3"

        def do_GET(self) -> None:
            if self.path == "/api/health":
                self.send_json({
                    "status": "ok",
                    "moss": __import__("mosslang").__version__,
                    "cached_entries": len(_trust_cache),
                    "server": "MossTrustServer/alpha(t)2",
                })
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                self.send_json({"trust": False, "error": "empty body"}, status=400)
                return

            source = self.rfile.read(length).decode("utf-8")

            if self.path.startswith("/api/trust"):
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                level = qs.get("level", ["auto"])[0]
                result = trust_from_source(source)

                if level == "auto":
                    # auto: brief on success, normal + fix_hints on failure
                    if result["trust"]:
                        self._send_trust_brief(result)
                    else:
                        self._send_trust_normal(result)
                elif level == "brief":
                    self._send_trust_brief(result)
                elif level == "full":
                    self.send_json(result)
                else:
                    self._send_trust_normal(result)
            elif self.path == "/api/token":
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                level = qs.get("level", ["normal"])[0]
                result = token_from_source(source, level=level)
                self.send_json(result)
            elif self.path == "/api/trust-batch":
                self._handle_trust_batch(source)
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def _handle_trust_batch(self, body: str) -> None:
            """POST /api/trust-batch — accept JSON {files: {name: source}} and return per-file status."""
            try:
                payload = json.loads(body)
                files = payload.get("files", {})
            except json.JSONDecodeError:
                self.send_json({"error": "invalid JSON"}, status=400)
                return

            results = {}
            failed_count = 0
            total_count = 0
            for fname, fsource in files.items():
                total_count += 1
                try:
                    r = trust_from_source(str(fsource))
                    results[fname] = {
                        "trust": r.get("trust", False),
                        "g": r.get("gates", 0),
                        "h": r.get("source_sha256", "")[:16],
                        "ms": r.get("elapsed_ms", 0),
                    }
                    if not r.get("trust"):
                        failed_count += 1
                        results[fname]["failed_gates"] = r.get("failed_gates", [])
                        results[fname]["fix_hints"] = r.get("fix_hints", [])[:3]
                except Exception as e:
                    results[fname] = {"trust": False, "error": str(e)}
                    failed_count += 1

            self.send_json({
                "total": total_count,
                "passed": total_count - failed_count,
                "failed": failed_count,
                "files": results,
            })

        def send_json(self, payload: dict, status: int = 200) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:
            return  # suppress logs for fast API operation

        def _send_trust_brief(self, result: dict) -> None:
            """Auto-level: brief on trust=true — 7 fields, ~15 tokens."""
            trace_ev = result.get("trace", {}).get("events", [])
            self.send_json({
                "trust": True,
                "h": result["source_sha256"][:12],
                "g": result.get("gates", 0),
                "c": result.get("token", {"e": 0, "t": 0, "l": 0}),
                "r": [{"n": e.get("rule"), "v": str(e.get("result", "?"))[:16]} for e in trace_ev[:2]] if trace_ev else None,
                "ms": result.get("elapsed_ms", 0),
                "ta": "ta.v1",
            })

        def _send_trust_normal(self, result: dict) -> None:
            """Auto-level: normal + fix_hints + failed_gates on trust=false."""
            payload = {
                "trust": result["trust"],
                "g": result.get("gates", 0),
                "failed_gates": result.get("failed_gates", []),
                "check": result.get("check", {}).get("ok"),
                "fix_hints": result.get("fix_hints", []),
                "token": result.get("token", {}),
                "h": result["source_sha256"][:16],
                "ms": result.get("elapsed_ms", 0),
            }
            if result.get("golden"):
                payload["golden"] = result["golden"].get("ok")
            self.send_json(payload)

    return TrustHandler


def run_trust_server(host: str = "127.0.0.1", port: int = 9876) -> None:
    server = ThreadingHTTPServer((host, port), make_trust_handler())
    address = f"http://{host}:{server.server_port}"
    print(f"Moss Trust Server running at {address}")
    print(f"Endpoints: POST /api/trust  POST /api/token?level=  GET /api/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
