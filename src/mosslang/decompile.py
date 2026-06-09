"""Moss Decompile — .mbc bytecode to structure overview.

Brand 4 of the dual-brand architecture (Trust + Token + Server + Decompile).

Uses BytecodeModule.deserialize() for reliable parsing,
then produces a structural overview with instruction counts, function listings, and metadata.
"""

from __future__ import annotations

from pathlib import Path


def decompile_mbc(path: Path) -> str:
    """Decompile a .mbc file to a structural overview string."""
    try:
        data = path.read_bytes()
    except Exception as e:
        return f"error reading file: {e}"

    if data[:4] != b'MOSS':
        return "error: not a valid .mbc file"

    try:
        from .bytecode import BytecodeModule
        mod = BytecodeModule.deserialize(data)
    except Exception as e:
        return f"error deserializing .mbc: {e}"

    lines = []
    lines.append(f"// decompiled: {mod.source_path or mod.module_name or '?'}")
    lines.append(f"// version {mod.version}")
    lines.append("")

    # Effects
    for e in mod.effects:
        lines.append(f"effect {e}")
    # Imports
    for imp in mod.imports:
        lines.append(f'import "{imp}"')

    if mod.effects or mod.imports:
        lines.append("")

    # Main code object
    co = mod.code
    lines.append(f"// main: {len(co.instructions)} instructions, {len(co.locals)} locals, {len(co.constants)} constants")
    lines.append("")

    # Instruction listing
    for i, inst in enumerate(co.instructions):
        op_name = inst.opcode.name
        detail = ""
        if inst.arg is not None:
            ci = inst.arg & 0x7FFFFFFF
            if op_name == "LOAD_CONST" and ci < len(co.constants):
                detail = f"  # {co.constants[ci]!r}"
            elif op_name == "LOAD_GLOBAL" and ci < len(mod.globals):
                detail = f"  # {mod.globals[ci]}"
            elif op_name == "STORE_GLOBAL" and ci < len(mod.globals):
                detail = f"  # {mod.globals[ci]}"
            elif op_name == "LOAD_LOCAL" and ci < len(co.locals):
                detail = f"  # {co.locals[ci]}"
            elif op_name == "STORE_LOCAL" and ci < len(co.locals):
                detail = f"  # {co.locals[ci]}"
            elif op_name == "CALL" and ci > 0:
                detail = f"  # {ci} args"
        lines.append(f"  [{i:3d}] {op_name:16s} arg={inst.arg:4d}{detail}")

    # Functions
    if mod.functions:
        lines.append("")
        lines.append(f"// {len(mod.functions)} functions:")
        for fn_name, fn_co in mod.functions.items():
            lines.append(f"//   fn {fn_name} ({len(fn_co.locals)} locals, {len(fn_co.instructions)} instructions)")

    # Tests
    if mod.tests:
        lines.append("")
        lines.append("// tests:")
        for t in mod.tests:
            lines.append(f'//   test: "{t}"')

    lines.append("")
    lines.append("// decompile complete")
    return "\n".join(lines) + "\n"
