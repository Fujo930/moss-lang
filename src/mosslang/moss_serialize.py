"""Moss compiler output → .mbc serializer.
Converts compiler_core.moss output dict to .mbc binary format.
Independent of BytecodeModule — directly produces bytes that mossvm.exe reads.
"""

from __future__ import annotations

import struct
from typing import Any


# Opcode name → number map (matches bytecode.py Opcode enum and compiler_core.moss)
OPCODE_NAME_MAP = {
    "OP_NOP": 0, "OP_LABEL": 119, "OP_LOAD_CONST": 1, "OP_LOAD_NULL": 2, "OP_LOAD_TRUE": 3, "OP_LOAD_FALSE": 4,
    "OP_LOAD_LOCAL": 5, "OP_LOAD_GLOBAL": 6, "OP_STORE_LOCAL": 7, "OP_STORE_GLOBAL": 8,
    "OP_POP": 9, "OP_DUP": 10,
    "OP_JUMP": 20, "OP_JUMP_IF_FALSE": 21, "OP_JUMP_IF_TRUE": 22,
    "OP_CALL": 23, "OP_RETURN": 24, "OP_BREAK": 25, "OP_CONTINUE": 26,
    "OP_ADD": 30, "OP_SUB": 31, "OP_MUL": 32, "OP_DIV": 33, "OP_MOD": 34,
    "OP_EQ": 35, "OP_NEQ": 36, "OP_LT": 37, "OP_GT": 38, "OP_LTE": 39, "OP_GTE": 40,
    "OP_AND": 41, "OP_OR": 42,
    "OP_NEG": 50, "OP_NOT": 51,
    "OP_BUILD_RECORD": 60, "OP_BUILD_LIST": 61,
    "OP_GET_FIELD": 70, "OP_SET_FIELD": 71, "OP_GET_INDEX": 72, "OP_SET_INDEX": 73,
    "OP_RECORD_UPDATE": 74,
    "OP_TRY_PROPAGATE": 95, "OP_REQUIRE": 92,
    "OP_CHECK_EFFECT": 100,
    # Legacy aliases
    "OP_JUMP_IF_TRUE": 22,
    # Common variant formats  
    "OP_MATCH_BEGIN": 90, "OP_MATCH_END": 91, "OP_BUILD_VARIANT": 62,
}

OPCODES_BY_NUMBER = {v: k for k, v in OPCODE_NAME_MAP.items() if not k.startswith(tuple(f"OP_{x}" for x in ["MATCH", "BUILD_VARIANT"]))}
# Fill gaps: ensure all expected opcodes are in the map
OPCODE_NAME_MAP.setdefault("OP_MATCH_BEGIN", 90)
OPCODE_NAME_MAP.setdefault("OP_MATCH_END", 91)
OPCODE_NAME_MAP.setdefault("OP_BUILD_VARIANT", 62)


def _resolve_opcode(val: Any) -> int:
    """Convert any opcode representation to an int."""
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        # Try name lookup
        if val in OPCODE_NAME_MAP:
            return OPCODE_NAME_MAP[val]
        if val.startswith("OP_"):
            return OPCODE_NAME_MAP.get(val, 0)
        try:
            return int(val)
        except:
            return 0
    # MossVariant or similar: try to extract name
    name = getattr(val, 'name', None)
    if name:
        return OPCODE_NAME_MAP.get(name, 0)
    try:
        return int(str(val))
    except:
        return 0


def encode_varlen(data: bytes) -> bytes:
    """Encode a variable-length byte sequence as length-prefixed."""
    return struct.pack('<I', len(data)) + data


def encode_string(s: str) -> bytes:
    """Encode a UTF-8 string as length-prefixed."""
    return encode_varlen(s.encode('utf-8'))


def encode_instructions(insts: list[dict]) -> bytes:
    """Encode instructions list — matches Python bytecode.py Instruction.encode().
    Format: opcode(1 byte uint8) + arg(4 bytes uint32 LE) + line(4 bytes int32 LE) + column(2 bytes uint16 LE)
    """
    count = len(insts)
    buf = struct.pack('<I', count)
    for inst in insts:
        opcode = _resolve_opcode(inst.get('opcode', 0))
        arg = int(float(str(inst.get('arg', 0))))
        line = int(float(str(inst.get('line', 0))))
        col = int(float(str(inst.get('column', 0))))
        buf += struct.pack('<B I i H', opcode & 0xFF, arg & 0xFFFFFFFF, line, col & 0xFFFF)
    return buf


def encode_constants_json(constants: list[Any]) -> bytes:
    """Encode constants as a JSON array string."""
    import json
    json_str = json.dumps(constants)
    return encode_varlen(json_str.encode('utf-8'))


def serialize_compiler_output(compiler_dict: dict, source_path: str = "module.moss", module_name: str = "") -> bytes:
    """Serialize compiler_core.moss output dict to .mbc binary format.
    
    The .mbc format (as read by mossvm.c):
      - magic: 'MOSS' (4 bytes)
      - version: uint32 LE
      - module_name: string
      - source_path: string
      - globals: count(uint32) + strings...
      - effects: count + strings...
      - imports: count + strings...
      - tests: count + strings...
      - code_object:
        - name: string
        - arg_count: uint32
        - cap_count: uint32
        - is_rule: uint8
        - source_line: uint32
        - source_column: uint32
        - locals: count + strings...
        - constants: JSON string
        - instructions
      - functions: count + [function...]
    
    Returns .mbc bytes.
    """
    buf = bytearray()
    
    # Header
    buf += b'MOSS'
    buf += struct.pack('<I', 1)  # version
    
    # Module name and source path
    buf += encode_string(module_name)
    buf += encode_string(source_path)
    
    # Globals
    globals_list = _to_strings(compiler_dict.get('globals', []))
    buf += struct.pack('<I', len(globals_list))
    for g in globals_list:
        buf += encode_string(g)
    
    # Effects
    effects_list = _to_strings(compiler_dict.get('effects', []))
    buf += struct.pack('<I', len(effects_list))
    for e in effects_list:
        buf += encode_string(e)
    
    # Imports
    imports_list = _to_strings(compiler_dict.get('imports', []))
    buf += struct.pack('<I', len(imports_list))
    for imp in imports_list:
        buf += encode_string(imp)
    
    # Tests
    tests_list = _to_strings(compiler_dict.get('tests', []))
    buf += struct.pack('<I', len(tests_list))
    for t in tests_list:
        buf += encode_string(t)
    
    # Main code object
    buf += _encode_code_object(compiler_dict, module_name)
    
    # Functions — compiled function dicts have instructions but need cross-module
    # index resolution. For now, use stubs that the Python VM handles correctly.
    # When v0.95+ delivers full compiler self-hosting, these stubs get replaced
    # with the real Moss-compiled function bodies.
    functions_dict = compiler_dict.get('functions', {})
    if isinstance(functions_dict, dict):
        func_names = list(functions_dict.keys())
    else:
        func_names = []
    buf += struct.pack('<I', len(func_names))
    for fname in func_names:
        fdata = functions_dict[fname]
        fname_str = str(fname)
        if isinstance(fdata, dict) and 'instructions' in fdata and len(fdata.get('instructions', [])) > 2:
            # v0.85+ compiled function — try to use Moss instructions if opcodes are valid
            insts = fdata.get('instructions', [])
            consts = [str(c) for c in fdata.get('constants', [])]
            locs = [str(l) for l in fdata.get('locals', ['__self'])]
            ac = int(float(str(fdata.get('arg_count', 0))))
            # Validate: Moss instructions load from function-local context
            buf += _encode_code_object(
                {'name': fname_str, 'arg_count': ac, 'locals': locs,
                 'constants': consts, 'instructions': insts}, fname_str)
        else:
            stub = {'name': fname_str, 'arg_count': 0, 'locals': ['__self'],
                    'constants': [], 'instructions': [
                        {'opcode': 'OP_LOAD_NULL', 'arg': 0, 'line': 0, 'column': 0},
                        {'opcode': 'OP_RETURN', 'arg': 0, 'line': 0, 'column': 0}]}
            buf += _encode_code_object(stub, fname_str)
    
    return bytes(buf)


def _encode_code_object(data: dict, name: str) -> bytes:
    """Encode a single code object (main or function)."""
    buf = bytearray()
    
    buf += encode_string(name)
    buf += struct.pack('<I', int(float(str(data.get('arg_count', 0)))))
    buf += struct.pack('<I', 0)  # cap_count
    buf += struct.pack('<B', 1 if data.get('is_rule') else 0)
    buf += struct.pack('<I', 0)  # source_line
    buf += struct.pack('<I', 0)  # source_column
    
    locals_list = _to_strings(data.get('locals', []))
    buf += struct.pack('<I', len(locals_list))
    for l in locals_list:
        buf += encode_string(l)
    
    # Constants as JSON
    constants = data.get('constants', [])
    constants_json = _constants_to_json(constants)
    buf += encode_varlen(constants_json.encode('utf-8'))
    
    # Instructions
    instructions = data.get('instructions', [])
    buf += encode_instructions(instructions)
    
    return bytes(buf)


def _to_strings(items: list) -> list[str]:
    """Convert mixed list items to strings."""
    return [str(i).replace('<__main__.Variant object at 0x', 'OP_') for i in items]


def _constants_to_json(constants: list) -> str:
    """Convert constants list to JSON string suitable for mossvm.c parser."""
    import json
    result = []
    for c in constants:
        if isinstance(c, str):
            result.append(c)
        elif isinstance(c, (int, float)):
            result.append(str(c))
        elif c is None:
            result.append('null')
        elif isinstance(c, bool):
            result.append('true' if c else 'false')
        else:
            result.append(str(c))
    return json.dumps(result)
