"""
Moss bytecode instruction set and module format.

Design principles:
- Stack-based VM (simpler codegen, compact encoding)
- Typed opcodes for clarity and safety
- Serializable to/from binary (.mbc) format
- Preserves source mapping for trace/debug
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional
import struct
import json


class Opcode(IntEnum):
    """Moss bytecode instruction set."""
    # ── Stack manipulation ──
    NOP = 0
    LOAD_CONST = 1      # Push constant from pool
    LOAD_NULL = 2       # Push null
    LOAD_TRUE = 3       # Push true
    LOAD_FALSE = 4      # Push false
    LOAD_LOCAL = 5      # Push local variable
    LOAD_GLOBAL = 6     # Push global variable
    STORE_LOCAL = 7     # Pop and store to local
    STORE_GLOBAL = 8    # Pop and store to global
    POP = 9             # Discard top of stack
    DUP = 10            # Duplicate top of stack

    # ── Control flow ──
    JUMP = 20           # Unconditional jump
    JUMP_IF_FALSE = 21  # Pop, jump if false
    JUMP_IF_TRUE = 22   # Pop, jump if true
    CALL = 23           # Call function (arg count on stack)
    RETURN = 24         # Return from function
    BREAK = 25          # Break from loop
    CONTINUE = 26       # Continue loop

    # ── Binary operations ──
    ADD = 30
    SUB = 31
    MUL = 32
    DIV = 33
    MOD = 34
    EQ = 35
    NEQ = 36
    LT = 37
    GT = 38
    LTE = 39
    GTE = 40
    AND = 41
    OR = 42

    # ── Unary operations ──
    NEG = 50            # Numeric negation
    NOT = 51            # Boolean negation

    # ── Data construction ──
    BUILD_RECORD = 60   # Build record from N field name/value pairs on stack
    BUILD_LIST = 61     # Build list from N items on stack
    BUILD_MAP = 62      # Build map from N key/value pairs on stack
    BUILD_VARIANT = 63  # Build variant from name + payload count on stack

    # ── Data access ──
    GET_FIELD = 70      # Pop record, push field value (field name in arg)
    SET_FIELD = 71      # Pop record & value, push updated record
    GET_INDEX = 72      # Pop list & index, push element
    SET_INDEX = 73      # Pop list & index & value, push updated list
    RECORD_UPDATE = 74  # Pop base record, N field updates, push new record

    # ── Pattern matching ──
    MATCH_BEGIN = 80    # Begin match on top of stack
    MATCH_CASE = 81     # Test case pattern, jump if no match
    MATCH_END = 82      # End of match expression
    TEST_VARIANT = 83   # Test if top is variant with given name

    # ── Error handling ──
    TRY = 90            # Mark start of try expression
    UNWRAP = 91         # Pop Result, push value or propagate Err
    REQUIRE = 92        # Pop condition & else value, propagate if false

    # ── Try/Error ──
    TRY_PROPAGATE = 95  # Pop value; if Err, propagate; otherwise unwrap Ok

    # ── Effect guards ──
    CHECK_EFFECT = 100  # Verify effect is allowed in current context

    # ── Import ──
    IMPORT = 110        # Import and run module

    # ── Special ──
    PRINT = 120         # Print top of stack


@dataclass
class Instruction:
    """A single bytecode instruction with optional arg and source location."""
    opcode: Opcode
    arg: int = 0
    line: int = 0
    column: int = 0

    def encode(self) -> bytes:
        """Encode to binary format: opcode(1) arg(4) line(4) column(2)"""
        return struct.pack(
            '<BIiH',
            self.opcode.value,
            self.arg,
            self.line,
            self.column
        )

    @classmethod
    def decode(cls, data: bytes, offset: int = 0) -> tuple[Instruction, int]:
        """Decode from binary format. Returns (instruction, bytes_consumed)."""
        op_val, arg, line, column = struct.unpack_from('<BIiH', data, offset)
        return cls(Opcode(op_val), arg, line, column), 11


@dataclass
class CodeObject:
    """
    A compiled Moss function or module.
    
    Attributes:
        name: Function name or '<module>'
        instructions: Bytecode instruction sequence
        constants: Constant pool (shared across module)
        locals: Local variable names
        arg_count: Number of parameters
        capture_count: Number of captured closure variables
    """
    name: str
    instructions: list[Instruction] = field(default_factory=list)
    constants: list[Any] = field(default_factory=list)
    locals: list[str] = field(default_factory=list)
    arg_count: int = 0
    capture_count: int = 0


@dataclass
class BytecodeModule:
    """
    Compiled Moss module ready for execution by the VM.
    
    Contains one or more code objects (module init + functions/rules).
    """
    version: int = 1
    module_name: str = ""
    code: CodeObject = field(default_factory=lambda: CodeObject("<module>"))
    functions: dict[str, CodeObject] = field(default_factory=dict)
    globals: list[str] = field(default_factory=list)
    effects: list[str] = field(default_factory=list)
    types: dict[str, str] = field(default_factory=dict)  # name -> serialized type info
    imports: list[str] = field(default_factory=list)
    source_path: str = ""

    def add_constant(self, value: Any) -> int:
        """Add a value to the constant pool and return its index."""
        for i, existing in enumerate(self.code.constants):
            if type(existing) is type(value) and existing == value:
                return i
        self.code.constants.append(value)
        return len(self.code.constants) - 1

    def emit(self, opcode: Opcode, arg: int = 0, line: int = 0, column: int = 0) -> None:
        """Emit an instruction into the module code."""
        self.code.instructions.append(Instruction(opcode, arg, line, column))

    def emit_at(self, index: int, opcode: Opcode, arg: int = 0, line: int = 0, column: int = 0) -> None:
        """Overwrite instruction at given index."""
        self.code.instructions[index] = Instruction(opcode, arg, line, column)

    def current_offset(self) -> int:
        """Return the next instruction offset (for backpatching jumps)."""
        return len(self.code.instructions)

    def declare_effect(self, name: str) -> None:
        """Register an effect used by this module."""
        if name not in self.effects:
            self.effects.append(name)

    def declare_import(self, path: str) -> None:
        """Register an import dependency."""
        if path not in self.imports:
            self.imports.append(path)

    def declare_function(self, co: CodeObject) -> None:
        """Register a function code object."""
        self.functions[co.name] = co

    def new_code_object(self, name: str, arg_count: int = 0) -> CodeObject:
        """Create a new code object registered in this module."""
        co = CodeObject(name=name, arg_count=arg_count)
        self.functions[name] = co
        return co

    def serialize(self) -> bytes:
        """Serialize module to .mbc binary format."""
        import io
        
        buf = io.BytesIO()
        # Header: magic + version
        buf.write(b'MOSS')
        buf.write(struct.pack('<I', self.version))
        
        # Module name
        name_bytes = self.module_name.encode('utf-8')
        buf.write(struct.pack('<I', len(name_bytes)))
        buf.write(name_bytes)
        
        # Source path
        path_bytes = self.source_path.encode('utf-8')
        buf.write(struct.pack('<I', len(path_bytes)))
        buf.write(path_bytes)
        
        # Globals
        buf.write(struct.pack('<I', len(self.globals)))
        for g in self.globals:
            gb = g.encode('utf-8')
            buf.write(struct.pack('<I', len(gb)))
            buf.write(gb)
        
        # Effects
        buf.write(struct.pack('<I', len(self.effects)))
        for e in self.effects:
            eb = e.encode('utf-8')
            buf.write(struct.pack('<I', len(eb)))
            buf.write(eb)
        
        # Imports
        buf.write(struct.pack('<I', len(self.imports)))
        for imp in self.imports:
            ib = imp.encode('utf-8')
            buf.write(struct.pack('<I', len(ib)))
            buf.write(ib)
        
        # Code objects
        _serialize_code_object(buf, self.code)
        buf.write(struct.pack('<I', len(self.functions)))
        for co in self.functions.values():
            _serialize_code_object(buf, co)
        
        return buf.getvalue()

    @classmethod
    def deserialize(cls, data: bytes) -> BytecodeModule:
        """Deserialize from .mbc binary format."""
        import io
        
        buf = io.BytesIO(data)
        magic = buf.read(4)
        if magic != b'MOSS':
            raise ValueError(f"Invalid magic: {magic!r}")
        
        version = struct.unpack('<I', buf.read(4))[0]
        
        def _read_string() -> str:
            length = struct.unpack('<I', buf.read(4))[0]
            return buf.read(length).decode('utf-8')
        
        mod = cls(version=version)
        mod.module_name = _read_string()
        mod.source_path = _read_string()
        
        # Globals
        n_globals = struct.unpack('<I', buf.read(4))[0]
        mod.globals = [_read_string() for _ in range(n_globals)]
        
        # Effects
        n_effects = struct.unpack('<I', buf.read(4))[0]
        mod.effects = [_read_string() for _ in range(n_effects)]
        
        # Imports
        n_imports = struct.unpack('<I', buf.read(4))[0]
        mod.imports = [_read_string() for _ in range(n_imports)]
        
        # Code objects
        mod.code = _deserialize_code_object(buf)
        n_funcs = struct.unpack('<I', buf.read(4))[0]
        for _ in range(n_funcs):
            co = _deserialize_code_object(buf)
            mod.functions[co.name] = co
        
        return mod


def _serialize_code_object(buf, co: CodeObject) -> None:
    """Serialize a single code object to buffer."""
    name_bytes = co.name.encode('utf-8')
    buf.write(struct.pack('<I', len(name_bytes)))
    buf.write(name_bytes)
    
    buf.write(struct.pack('<I', co.arg_count))
    buf.write(struct.pack('<I', co.capture_count))
    
    # Locals
    buf.write(struct.pack('<I', len(co.locals)))
    for loc in co.locals:
        lb = loc.encode('utf-8')
        buf.write(struct.pack('<I', len(lb)))
        buf.write(lb)
    
    # Constants (JSON-encoded for simplicity; text/numbers are common case)
    const_json = json.dumps(co.constants, default=str).encode('utf-8')
    buf.write(struct.pack('<I', len(const_json)))
    buf.write(const_json)
    
    # Instructions
    buf.write(struct.pack('<I', len(co.instructions)))
    for inst in co.instructions:
        buf.write(inst.encode())


def _deserialize_code_object(buf) -> CodeObject:
    """Deserialize a single code object from buffer."""
    def _read_string() -> str:
        length = struct.unpack('<I', buf.read(4))[0]
        return buf.read(length).decode('utf-8')
    
    name = _read_string()
    arg_count = struct.unpack('<I', buf.read(4))[0]
    capture_count = struct.unpack('<I', buf.read(4))[0]
    
    n_locals = struct.unpack('<I', buf.read(4))[0]
    locals_list = [_read_string() for _ in range(n_locals)]
    
    const_len = struct.unpack('<I', buf.read(4))[0]
    constants = json.loads(buf.read(const_len).decode('utf-8'))
    
    n_insts = struct.unpack('<I', buf.read(4))[0]
    instructions = []
    for _ in range(n_insts):
        inst, _ = Instruction.decode(buf.read(11))
        instructions.append(inst)
    
    return CodeObject(
        name=name,
        instructions=instructions,
        constants=constants,
        locals=locals_list,
        arg_count=arg_count,
        capture_count=capture_count,
    )


# ── Opcode metadata for debugging / disassembly ──

OPCODE_NAMES: dict[int, str] = {op.value: op.name for op in Opcode}

# Opcodes that take an argument
OPCODES_WITH_ARG = {
    Opcode.LOAD_CONST,
    Opcode.LOAD_LOCAL,
    Opcode.LOAD_GLOBAL,
    Opcode.STORE_LOCAL,
    Opcode.STORE_GLOBAL,
    Opcode.JUMP,
    Opcode.JUMP_IF_FALSE,
    Opcode.JUMP_IF_TRUE,
    Opcode.CALL,
    Opcode.BUILD_RECORD,
    Opcode.BUILD_LIST,
    Opcode.BUILD_MAP,
    Opcode.BUILD_VARIANT,
    Opcode.GET_FIELD,
    Opcode.SET_FIELD,
    Opcode.RECORD_UPDATE,
    Opcode.TEST_VARIANT,
    Opcode.CHECK_EFFECT,
}
