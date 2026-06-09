r"""Moss tokenizer - produces a flat token stream for the parser.

Backtick string interpolation:
  `Hello {name}, you have {count} items`
  -> BK_PART("Hello "), INTERP_START, IDENT(name), INTERP_END,
     BK_PART(", you have "), INTERP_START, IDENT(count), INTERP_END,
     BK_PART(" items")

  Use backslash-brace for a literal brace inside an interpolated backtick string.
  Regular "..." strings are unchanged (no interpolation).
  Backtick strings are multiline; "..." strings reject newlines.
"""
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
    "|>": "PUNCT",
}

SINGLE_CHAR_TOKENS = {
    "(": "PUNCT",
    ")": "PUNCT",
    "{": "PUNCT",
    "}": "PUNCT",
    "[": "PUNCT",
    "]": "PUNCT",
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


def _is_ident_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    line = 1
    column = 1

    # Interpolation state for backtick strings
    _interp_depth = 0
    _collecting_bt = False   # True when collecting text inside a backtick string
    _bt_buf: list[str] = []
    _bt_start_line = 0
    _bt_start_col = 0
    _bt_has_interp = False

    def add(kind: str, value: str, start_line: int, start_col: int) -> None:
        tokens.append(Token(kind, value, start_line, start_col))

    def _flush_bt() -> None:
        if not _collecting_bt:
            return
        text = "".join(_bt_buf)
        if text:
            kind = "BK_PART" if _bt_has_interp else "STRING"
            add(kind, text, _bt_start_line, _bt_start_col)

    def _start_bt(s_line: int, s_col: int, has_interp: bool = False) -> None:
        nonlocal _collecting_bt, _bt_buf, _bt_start_line, _bt_start_col, _bt_has_interp
        _collecting_bt = True
        _bt_buf = []
        _bt_start_line = s_line
        _bt_start_col = s_col
        _bt_has_interp = has_interp

    _ESCAPE_BT = {"n": "\n", "t": "\t", "r": "\r", "`": "`", "\\": "\\", "{": "{"}

    while i < len(source):
        ch = source[i]
        start_line = line
        start_col = column

        # ── Backtick string collection mode ──
        if _collecting_bt:
            if ch == '`':
                _flush_bt()
                _collecting_bt = False
                _bt_buf = []
                i += 1
                column += 1
                continue

            if ch == '\\':
                if i + 1 >= len(source):
                    raise MossSyntaxError("unterminated string escape", SourceLocation(line, column))
                esc = source[i + 1]
                if esc in _ESCAPE_BT:
                    _bt_buf.append(_ESCAPE_BT[esc])
                    i += 2
                    column += 2
                    continue
                _bt_buf.append(ch)
                i += 1
                column += 1
                continue

            if ch == '{':
                _bt_has_interp = True
                _flush_bt()
                add("INTERP_START", "", start_line, start_col)
                _collecting_bt = False
                _bt_buf = []
                _interp_depth += 1
                i += 1
                column += 1
                continue

            if ch == '\n':
                _bt_buf.append(ch)
                i += 1
                line += 1
                column = 1
                continue

            _bt_buf.append(ch)
            i += 1
            column += 1
            continue

        # ── End of interpolation expression ──
        if _interp_depth > 0 and ch == '}':
            add("INTERP_END", "", start_line, start_col)
            _interp_depth -= 1
            i += 1
            column += 1
            _start_bt(start_line, start_col, has_interp=True)
            continue

        # ── Normal tokenizer ──

        if ch in " \t\r\ufeff":
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
                    mapping = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}
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

        if ch == '`':
            i += 1
            column += 1
            _start_bt(start_line, start_col)
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

    if _collecting_bt:
        raise MossSyntaxError("unterminated backtick string", SourceLocation(_bt_start_line, _bt_start_col))
    if _interp_depth > 0:
        raise MossSyntaxError("unterminated string interpolation", SourceLocation(line, column))

    tokens.append(Token("EOF", "", line, column))
    return tokens
