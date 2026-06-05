from __future__ import annotations

from pathlib import Path

from .nodes import EffectDecl, FunctionDecl, RuleDecl, TypeDecl
from .parser import parse_source


def generate_api_docs(path: Path) -> str:
    program = parse_source(path.read_text(encoding="utf-8-sig"))
    lines = [f"# {path.stem} API", ""]
    for item in program.items:
        if isinstance(item, EffectDecl):
            lines.extend([f"## Effect: {', '.join(item.names)}", "", "Explicit capability declaration.", ""])
        elif isinstance(item, TypeDecl):
            lines.extend([f"## Type: {item.name}", ""])
            if item.alias:
                lines.extend([f"`{item.name} = {item.alias}`", ""])
            else:
                lines.extend(["| Field | Type |", "| --- | --- |"])
                lines.extend(f"| `{name}` | `{type_name}` |" for name, type_name in item.fields.items())
                lines.append("")
        elif isinstance(item, (FunctionDecl, RuleDecl)):
            kind = "Rule" if isinstance(item, RuleDecl) else "Function"
            params = ", ".join(f"{param.name}: {param.type_name or 'Any'}" for param in item.params)
            signature = f"{item.name}({params}) -> {item.return_type or 'Any'}"
            if isinstance(item, FunctionDecl) and item.uses:
                signature += " uses " + ", ".join(item.uses)
            lines.extend([f"## {kind}: {item.name}", "", f"`{signature}`", ""])
    return "\n".join(lines).rstrip() + "\n"
