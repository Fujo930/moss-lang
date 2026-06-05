from __future__ import annotations

import re

from .tokens import tokenize


def format_source(source: str) -> str:
    """Normalize Moss indentation without rewriting source tokens or comments."""
    depth = 0
    formatted: list[str] = []
    previous_content = ""

    for raw_line in source.splitlines():
        content = canonical_spacing(raw_line.strip())
        if not content:
            formatted.append("")
            continue

        tokens = [token for token in tokenize(content + "\n") if token.kind not in {"NEWLINE", "EOF"}]
        leading_closes = 0
        for token in tokens:
            if token.kind != "PUNCT" or token.value != "}":
                break
            leading_closes += 1

        existing_depth = (len(raw_line) - len(raw_line.lstrip())) // 2
        line_depth = max(0, depth - leading_closes)
        if content.startswith("else ") and previous_content.startswith("require "):
            line_depth = depth + 1
        if depth == 0:
            line_depth = existing_depth
        formatted.append("  " * line_depth + content)
        opens = sum(1 for token in tokens if token.kind == "PUNCT" and token.value == "{")
        closes = sum(1 for token in tokens if token.kind == "PUNCT" and token.value == "}")
        if depth != 0 or existing_depth == 0:
            depth = max(0, depth + opens - closes)
        previous_content = content

    while formatted and formatted[-1] == "":
        formatted.pop()
    return "\n".join(formatted) + "\n"


def canonical_spacing(content: str) -> str:
    code, protected = protect_literals_and_comment(content)
    code = code.replace("->", "\x01")
    code = re.sub(r"\s*(==|!=|>=|<=|[=+*/<>|])\s*", r" \1 ", code)
    code = re.sub(r"\s*-\s*", " - ", code)
    code = re.sub(r"\s*,\s*", ", ", code)
    code = re.sub(r"\s*:\s*", ": ", code)
    code = re.sub(r"([\[(])\s+", r"\1", code)
    code = re.sub(r"\s+([\])}])", r"\1", code)
    code = re.sub(r"[ \t]+", " ", code).strip().replace("\x01", "->")
    for marker, original in protected:
        code = code.replace(marker, original)
    return code


def protect_literals_and_comment(content: str) -> tuple[str, list[tuple[str, str]]]:
    protected: list[tuple[str, str]] = []
    output: list[str] = []
    index = 0
    while index < len(content):
        if content[index] == '"':
            end = index + 1
            while end < len(content):
                if content[end] == "\\":
                    end += 2
                    continue
                if content[end] == '"':
                    end += 1
                    break
                end += 1
            marker = f"\x02{len(protected)}\x03"
            protected.append((marker, content[index:end]))
            output.append(marker)
            index = end
            continue
        if content[index] == "#" or content[index : index + 2] == "//":
            marker = f"\x02{len(protected)}\x03"
            protected.append((marker, content[index:]))
            output.append(marker)
            break
        output.append(content[index])
        index += 1
    return "".join(output), protected
