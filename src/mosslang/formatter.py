from __future__ import annotations

from .tokens import tokenize


def format_source(source: str) -> str:
    """Normalize Moss indentation without rewriting source tokens or comments."""
    depth = 0
    formatted: list[str] = []
    previous_content = ""

    for raw_line in source.splitlines():
        content = raw_line.strip()
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
