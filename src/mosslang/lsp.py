from __future__ import annotations

import json
import sys
from typing import Any, BinaryIO

from .tooling import SEMANTIC_TOKEN_TYPES, analyze_document


def main() -> int:
    return run_server(sys.stdin.buffer, sys.stdout.buffer)


def run_server(reader: BinaryIO, writer: BinaryIO) -> int:
    documents: dict[str, str] = {}
    while message := read_message(reader):
        method = message.get("method")
        params = message.get("params", {})
        request_id = message.get("id")
        if method == "initialize":
            respond(writer, request_id, {"capabilities": {"textDocumentSync": 1, "documentSymbolProvider": True, "semanticTokensProvider": {"legend": {"tokenTypes": SEMANTIC_TOKEN_TYPES, "tokenModifiers": []}, "full": True}}})
        elif method == "shutdown":
            respond(writer, request_id, None)
        elif method == "exit":
            return 0
        elif method in {"textDocument/didOpen", "textDocument/didChange"}:
            document = params["textDocument"]
            uri = document["uri"]
            text = document.get("text")
            if text is None:
                text = params["contentChanges"][-1]["text"]
            documents[uri] = text
            notify(writer, "textDocument/publishDiagnostics", {"uri": uri, "diagnostics": analyze_document(text)["diagnostics"]})
        elif method == "textDocument/documentSymbol":
            respond(writer, request_id, analyze_document(documents.get(params["textDocument"]["uri"], ""))["symbols"])
        elif method == "textDocument/semanticTokens/full":
            respond(writer, request_id, {"data": analyze_document(documents.get(params["textDocument"]["uri"], ""))["semanticTokens"]})
        elif request_id is not None:
            respond(writer, request_id, None)
    return 0


def read_message(reader: BinaryIO) -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = reader.readline()
        if not line:
            return None
        if line in {b"\r\n", b"\n"}:
            break
        name, value = line.decode("ascii").split(":", 1)
        headers[name.lower()] = value.strip()
    return json.loads(reader.read(int(headers["content-length"])).decode("utf-8"))


def write_message(writer: BinaryIO, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    writer.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii") + data)
    writer.flush()


def respond(writer: BinaryIO, request_id: Any, result: Any) -> None:
    write_message(writer, {"jsonrpc": "2.0", "id": request_id, "result": result})


def notify(writer: BinaryIO, method: str, params: Any) -> None:
    write_message(writer, {"jsonrpc": "2.0", "method": method, "params": params})
