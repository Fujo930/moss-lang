from __future__ import annotations

from dataclasses import dataclass

from .errors import MossSyntaxError, SourceLocation


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int

    @property
    def location(self) -> SourceLocation:
        return SourceLocation(self.line, self.column)

    def __repr__(self) -> str:
        return f"Token({self.kind!r}, {self.value!r}, {self.line}, {self.column})"


TWO_CHAR_TOKENS = {
    "->": "ARROW",
    "==": "OP",
    "!=": "OP",
    ">=": "OP",
    "<=": "OP",
}

SINGLE_CHAR_TOKENS = {
    "(": "PUNCT",
    ")": "PUNCT",
    "{": "PUNCT",
    "}": "PUNCT",
    ",": "PUNCT",
    ":": "PUNCT",
    ";": "PUNCT",
    ".": "PUNCT",
    "?": "PUNCT",
    "|": "PUNCT",
    "+": "OP",
    "-": "OP",
    "*": "OP",
    "/": "OP",
    ">": "OP",
    "<": "OP",
    "=": "OP",
}


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    line = 1
    column = 1

    def add(kind: str, value: str, start_line: int, start_col: int) -> None:
        tokens.append(Token(kind, value, start_line, start_col))

    while i < len(source):
        ch = source[i]

        if ch in " \t\r":
            i += 1
            column += 1
            continue

        if ch == "\n":
            add("NEWLINE", "\n", line, column)
            i += 1
            line += 1
            column = 1
            continue

        if ch == "#":
            while i < len(source) and source[i] != "\n":
                i += 1
                column += 1
            continue

        if ch == "/" and i + 1 < len(source) and source[i + 1] == "/":
            while i < len(source) and source[i] != "\n":
                i += 1
                column += 1
            continue

        start_line = line
        start_col = column

        if ch == '"':
            i += 1
            column += 1
            value_chars: list[str] = []
            while i < len(source):
                current = source[i]
                if current == '"':
                    i += 1
                    column += 1
                    add("STRING", "".join(value_chars), start_line, start_col)
                    break
                if current == "\\":
                    if i + 1 >= len(source):
                        raise MossSyntaxError("unterminated string escape", SourceLocation(line, column))
                    escaped = source[i + 1]
                    mapping = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
                    value_chars.append(mapping.get(escaped, escaped))
                    i += 2
                    column += 2
                    continue
                if current == "\n":
                    raise MossSyntaxError("unterminated string literal", SourceLocation(line, column))
                value_chars.append(current)
                i += 1
                column += 1
            else:
                raise MossSyntaxError("unterminated string literal", SourceLocation(start_line, start_col))
            continue

        if ch.isdigit():
            start = i
            while i < len(source) and source[i].isdigit():
                i += 1
                column += 1
            if i < len(source) and source[i] == "." and i + 1 < len(source) and source[i + 1].isdigit():
                i += 1
                column += 1
                while i < len(source) and source[i].isdigit():
                    i += 1
                    column += 1
            add("NUMBER", source[start:i], start_line, start_col)
            continue

        if ch.isalpha() or ch == "_":
            start = i
            while i < len(source) and (source[i].isalnum() or source[i] == "_"):
                i += 1
                column += 1
            add("IDENT", source[start:i], start_line, start_col)
            continue

        two = source[i : i + 2]
        if two in TWO_CHAR_TOKENS:
            add(TWO_CHAR_TOKENS[two], two, start_line, start_col)
            i += 2
            column += 2
            continue

        if ch in SINGLE_CHAR_TOKENS:
            add(SINGLE_CHAR_TOKENS[ch], ch, start_line, start_col)
            i += 1
            column += 1
            continue

        raise MossSyntaxError(f"unexpected character {ch!r}", SourceLocation(line, column))

    tokens.append(Token("EOF", "", line, column))
    return tokens
