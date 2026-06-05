from __future__ import annotations

from typing import Any

from .checker import check_program
from .errors import MossError
from .nodes import EffectDecl, FunctionDecl, RuleDecl, TestDecl, TypeDecl
from .parser import parse_source
from .tokens import tokenize


SEMANTIC_TOKEN_TYPES = ["keyword", "string", "number", "type", "function", "variable", "operator"]
KEYWORDS = {
    "effect", "type", "rule", "fn", "test", "import", "let", "return", "require",
    "else", "if", "for", "in", "while", "break", "continue", "match", "uses",
    "with", "and", "or", "not", "true", "false", "null",
}


def analyze_document(source: str) -> dict[str, Any]:
    try:
        program = parse_source(source)
    except MossError as exc:
        location = getattr(exc, "location", None)
        diagnostic = {"severity": 1, "message": getattr(exc, "message", str(exc))}
        if location is not None:
            diagnostic["range"] = lsp_range(location.line, location.column, 1)
        return {"diagnostics": [diagnostic], "symbols": [], "semanticTokens": semantic_tokens(source)}

    diagnostics = []
    for item in check_program(program):
        diagnostic = {"severity": 1 if item.level == "error" else 2, "message": item.message}
        if item.location is not None:
            diagnostic["range"] = lsp_range(item.location.line, item.location.column, 1)
        diagnostics.append(diagnostic)
    return {
        "diagnostics": diagnostics,
        "symbols": document_symbols(program),
        "semanticTokens": semantic_tokens(source),
    }


def document_symbols(program: Any) -> list[dict[str, Any]]:
    symbols = []
    kinds = {EffectDecl: 5, TypeDecl: 23, RuleDecl: 12, FunctionDecl: 12, TestDecl: 6}
    for item in program.items:
        kind = kinds.get(type(item))
        if kind is None:
            continue
        name = getattr(item, "name", None) or ", ".join(item.names)
        location = getattr(item, "location", None)
        line = location.line if location is not None else 1
        column = location.column if location is not None else 1
        symbols.append({"name": name, "kind": kind, "range": lsp_range(line, column, len(name)), "selectionRange": lsp_range(line, column, len(name))})
    return symbols


def semantic_tokens(source: str) -> list[int]:
    encoded: list[int] = []
    previous_line = 0
    previous_column = 0
    try:
        tokens = tokenize(source)
    except MossError:
        return encoded
    for token in tokens:
        token_type = semantic_token_type(token.kind, token.value)
        if token_type is None or token.kind in {"EOF", "NEWLINE"}:
            continue
        line = token.line - 1
        column = token.column - 1
        delta_line = line - previous_line
        delta_column = column - previous_column if delta_line == 0 else column
        encoded.extend([delta_line, delta_column, max(1, len(token.value)), SEMANTIC_TOKEN_TYPES.index(token_type), 0])
        previous_line = line
        previous_column = column
    return encoded


def semantic_token_type(kind: str, value: str) -> str | None:
    if kind == "STRING":
        return "string"
    if kind == "NUMBER":
        return "number"
    if kind == "IDENT":
        if value in KEYWORDS:
            return "keyword"
        if value and value[0].isupper():
            return "type"
        return "variable"
    if kind == "SYMBOL":
        return "operator"
    return None


def lsp_range(line: int, column: int, length: int) -> dict[str, Any]:
    start = {"line": max(0, line - 1), "character": max(0, column - 1)}
    return {"start": start, "end": {"line": start["line"], "character": start["character"] + max(1, length)}}
