"""Moss Decompile — .mbc bytecode to structure overview.

Brand 4 of the dual-brand architecture (Trust + Token + Server + Decompile).

Reads the .mbc binary format and produces a structural overview
with instruction counts, function listings, and metadata.
"""

from __future__ import annotations

import struct
import io
from pathlib import Path


def decompile_mbc(path: Path) -> str:
    """Decompile a .mbc file to a structural overview string."""
    data = path.read_bytes()
    if data[:4] != b'MOSS':
        return "error: not a valid .mbc file"

    buf = io.BytesIO(data)
    buf.read(4)  # magic
    version = struct.unpack('<I', buf.read(4))[0]

    def _ru32(): return struct.unpack('<I', buf.read(4))[0]
    def _rs(): l = _ru32(); return buf.read(l).decode('utf-8') if l > 0 else ""
    def _rb(): l = _ru32(); return buf.read(l)

    module_name = _rs()
    source_path = _rs()

    lines = [f"// decompiled: {source_path or module_name or '?'}",
             f"// version {version}", ""]

    n_globals = _ru32()
    globals_list = [_rs() for _ in range(n_globals)]
    n_eff = _ru32()
    eff_list = [_rs() for _ in range(n_eff)]
    for e in eff_list:
        if e: lines.append(f"effect {e}")
    n_imp = _ru32()
    imp_list = [_rs() for _ in range(n_imp)]
    for imp in imp_list:
        if imp: lines.append(f'import "{imp}"')
    n_tests_early = _ru32()
    _ = [_rs() for _ in range(n_tests_early)]

    if eff_list or imp_list:
        lines.append("")

    # Skip main code object header
    _ = _rs()  # co_name
    _ = _ru32(); _ = _ru32()  # argc, capc
    _ = buf.read(1)  # is_rule
    _ = _ru32(); _ = _ru32()  # source line, col
    n_loc = _ru32()
    loc_names = [_rs() for _ in range(n_loc)]
    cl = _ru32()
    _ = _rb()  # constants
    n_inst = _ru32()
    _ = buf.read(n_inst * 11)  # instructions

    lines.append(f"// main: {n_inst} instructions, {n_loc} locals, {n_globals} globals")
    lines.append("")

    # Functions
    n_funcs = _ru32()
    lines.append(f"// {n_funcs} functions:")
    for fi in range(min(n_funcs, 50)):
        fn_name = _rs(); _ = _rs()  # name, co_name
        _ = _ru32(); _ = _ru32(); _ = buf.read(1)  # argc, capc, is_rule
        _ = _ru32(); _ = _ru32()  # srcl, srcc
        fl = _ru32(); _ = [_rs() for _ in range(fl)]
        fc = _ru32(); _ = _rb()
        fi_c = _ru32(); _ = buf.read(fi_c * 11)
        lines.append(f"//   fn {fn_name} ({fl} locals, {fi_c} instructions)")

    # Skip remaining functions
    for fi in range(50, n_funcs):
        _ = _rs(); _ = _rs(); _ = _ru32(); _ = _ru32(); _ = buf.read(1)
        _ = _ru32(); _ = _ru32(); fl = _ru32(); _ = [_rs() for _ in range(fl)]
        fc = _ru32(); _ = _rb(); fi_c = _ru32(); _ = buf.read(fi_c * 11)

    # Tests
    tests = [_rs() for _ in range(n_tests_early if n_tests_early > 0 else _ru32())]
    for t in tests:
        if t:
            lines.append(f'//   test: "{t}"')

    lines.append("")
    lines.append("// decompile complete")
    return "\n".join(lines) + "\n"
