"""Moss Translator — .mbc bytecode to target language source code.

Translates compiled Moss modules (.mbc) into Go or Python source code.
Uses structural mapping: one opcode → 1-3 lines of target code.
No control-flow reconstruction (yet) — uses goto labels for correct semantics.

Supported targets: go, python (extensible architecture).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mosslang.bytecode import BytecodeModule, CodeObject, Opcode, Instruction


@dataclass
class TranslateResult:
    """Translation output."""
    target: str
    source: str
    functions: list[str]  # per-function translated bodies
    ok: bool
    error: str | None = None


class Translator:
    """Base translator with shared logic. Target backends override emit_*."""

    # Subclasses override this
    TARGET_NAME: str = ""

    def translate(self, module: BytecodeModule) -> TranslateResult:
        """Translate a full BytecodeModule."""
        try:
            funcs = []
            funcs.append(self._translate_code("main", module.code, module))
            for name, co in module.functions.items():
                funcs.append(self._translate_code(name, co, module))
            return TranslateResult(
                target=self.TARGET_NAME,
                source="\n\n".join(funcs),
                functions=funcs,
                ok=True,
            )
        except Exception as e:
            return TranslateResult(
                target=self.TARGET_NAME, source="", functions=[], ok=False, error=str(e)
            )

    def _translate_code(self, name: str, co: CodeObject, module: BytecodeModule) -> str:
        raise NotImplementedError


class GoTranslator(Translator):
    """Translate .mbc to Go source code."""

    TARGET_NAME = "go"

    # Opcode → Go mappings
    _OP_MAP = {
        "NOP":           "_ = nil",
        "LABEL":         "// label {arg}",
        "LOAD_CONST":    "{t} = _const[{arg}]",
        "LOAD_NULL":     "{t} = nil",
        "LOAD_TRUE":     "{t} = true",
        "LOAD_FALSE":    "{t} = false",
        "LOAD_LOCAL":    "{t} = _loc[{arg}]",
        "LOAD_GLOBAL":   "{t} = _g_{arg}",
        "STORE_LOCAL":   "_loc[{arg}] = stack_pop()",
        "STORE_GLOBAL":  "_g_{arg} = stack_pop()",
        "POP":           "stack_pop()",
        "DUP":           "stack_push(stack_peek())",
        "JUMP":          "goto L{arg}",
        "JUMP_IF_FALSE": "if !toBool(stack_pop()) {{ goto L{arg} }}",
        "JUMP_IF_TRUE":  "if toBool(stack_pop()) {{ goto L{arg} }}",
        "CALL":          "{t} = call_fn(stack_pop(), stack_pop_n({arg}))",
        "RETURN":        "return stack_pop()",
        "ADD":           "{t} = binAdd(stack_pop2())",
        "SUB":           "{t} = binSub(stack_pop2())",
        "MUL":           "{t} = binMul(stack_pop2())",
        "DIV":           "{t} = binDiv(stack_pop2())",
        "EQ":            "{t} = binEq(stack_pop2())",
        "NEQ":           "{t} = !binEq(stack_pop2())",
        "LT":            "{t} = binLt(stack_pop2())",
        "GT":            "{t} = binGt(stack_pop2())",
        "NOT":           "{t} = !toBool(stack_pop())",
        "NEG":           "{t} = -toFloat(stack_pop())",
        "BUILD_LIST":    "{t} = stack_pop_n({arg})",
        "BUILD_RECORD":  "{t} = buildRecord(stack_pop_n({arg}*2))",
        "GET_FIELD":     "{t} = getField(stack_pop(), {arg})",
        "GET_INDEX":     "{t} = stack_pop().([]interface{{}})[''...]",
        "PRINT":         "fmt.Println(stack_pop())",
    }

    def _translate_code(self, name: str, co: CodeObject, module: BytecodeModule) -> str:
        lines = []
        is_main = (name == "main")
        fn_name = "main" if is_main else name

        lines.append(f"// Moss function: {fn_name}")
        lines.append(f"func moss_{fn_name}() interface{{}} {{")
        lines.append("    _stack := make([]interface{}, 0, 256)")

        for i, inst in enumerate(co.instructions):
            # Label target
            lines.append(f"")
            lines.append(f"    L{i}:")
            template = self._OP_MAP.get(inst.opcode.name, f"    // op {inst.opcode.name} arg={inst.arg}")

            if "{t}" in template:
                lines.append(f"    _t{i} := interface{{}}(nil)")
                template = template.replace("{t}", f"_t{i}")
                lines.append(f"    _stack = append(_stack, _t{i})")

            lines.append(f"    {template.format(arg=inst.arg)}")

        lines.append("    return nil")
        lines.append("}")
        return "\n".join(lines)


class PythonTranslator(Translator):
    """Translate .mbc to Python source code."""

    TARGET_NAME = "python"

    def _translate_code(self, name: str, co: CodeObject, module: BytecodeModule) -> str:
        lines = []
        fn_name = name if name != "main" else "main"

        lines.append(f"# Moss function: {fn_name}")
        lines.append(f"def moss_{fn_name}():")
        lines.append(f"    _stack = []")

        for i, inst in enumerate(co.instructions):
            op = inst.opcode.name
            arg = inst.arg

            if op == "NOP" or op == "LABEL":
                lines.append(f"    # label {i}: {op}")
            elif op == "LOAD_CONST":
                c = co.constants[arg] if arg < len(co.constants) else None
                lines.append(f"    _stack.append({c!r})  # LOAD_CONST")
            elif op == "LOAD_NULL":
                lines.append(f"    _stack.append(None)")
            elif op == "LOAD_TRUE":
                lines.append(f"    _stack.append(True)")
            elif op == "LOAD_FALSE":
                lines.append(f"    _stack.append(False)")
            elif op == "LOAD_LOCAL":
                lines.append(f"    _stack.append(_loc{arg})  # LOAD_LOCAL")
            elif op == "LOAD_GLOBAL":
                lines.append(f"    _stack.append(_g_{arg})  # LOAD_GLOBAL")
            elif op == "STORE_LOCAL":
                lines.append(f"    _loc{arg} = _stack.pop()")
            elif op == "STORE_GLOBAL":
                lines.append(f"    _g_{arg} = _stack.pop()")
            elif op == "POP":
                lines.append(f"    _stack.pop()")
            elif op == "DUP":
                lines.append(f"    _stack.append(_stack[-1])")
            elif op == "JUMP":
                lines.append(f"    continue  # JUMP to {arg}")
            elif op == "JUMP_IF_FALSE":
                lines.append(f"    if not _stack.pop(): continue  # JUMP_IF_FALSE")
            elif op == "JUMP_IF_TRUE":
                lines.append(f"    if _stack.pop(): continue  # JUMP_IF_TRUE")
            elif op == "CALL":
                lines.append(f"    _callee = _stack.pop()")
                lines.append(f"    _args = [_stack.pop() for _ in range({arg})][::-1]")
                lines.append(f"    _stack.append(_callee(*_args))")
            elif op == "RETURN":
                lines.append(f"    return _stack.pop() if _stack else None")
            elif op in ("ADD", "SUB", "MUL", "DIV", "MOD"):
                op_map = {"ADD": "+", "SUB": "-", "MUL": "*", "DIV": "/", "MOD": "%"}
                lines.append(f"    _r = _stack.pop()")
                lines.append(f"    _l = _stack.pop()")
                lines.append(f"    _stack.append(_l {op_map[op]} _r)")
            elif op in ("EQ", "NEQ", "LT", "GT", "LTE", "GTE"):
                op_map = {"EQ": "==", "NEQ": "!=", "LT": "<", "GT": ">", "LTE": "<=", "GTE": ">="}
                lines.append(f"    _r = _stack.pop()")
                lines.append(f"    _l = _stack.pop()")
                lines.append(f"    _stack.append(_l {op_map[op]} _r)")
            elif op == "NOT":
                lines.append(f"    _stack.append(not _stack.pop())")
            elif op == "NEG":
                lines.append(f"    _stack.append(-_stack.pop())")
            elif op == "AND":
                lines.append(f"    _r = _stack.pop(); _stack.append(_stack.pop() and _r)")
            elif op == "OR":
                lines.append(f"    _r = _stack.pop(); _stack.append(_stack.pop() or _r)")
            elif op == "BUILD_LIST":
                lines.append(f"    _stack.append([_stack.pop() for _ in range({arg})][::-1])")
            elif op == "BUILD_RECORD":
                lines.append(f"    # BUILD_RECORD arg={arg}")
            elif op == "GET_FIELD":
                c = co.constants[arg] if arg < len(co.constants) else str(arg)
                lines.append(f"    _stack.append(_stack.pop().get({c!r}))")
            elif op == "GET_INDEX":
                lines.append(f"    _idx = _stack.pop(); _stack.append(_stack.pop()[_idx])")
            elif op == "PRINT":
                lines.append(f"    print(_stack.pop())")
            elif op == "CALL_PYTHON":
                lines.append(f"    # CALL_PYTHON arg={arg}")
            elif op == "CHECK_EFFECT":
                lines.append(f"    # CHECK_EFFECT")
            elif op == "REQUIRE":
                lines.append(f"    _err = _stack.pop()")
                lines.append(f"    if not _stack.pop(): raise Exception(_err)")
            else:
                lines.append(f"    # {op} arg={arg}")

        lines.append(f"    return _stack.pop() if _stack else None")
        return "\n".join(lines)


def translate_module(module: BytecodeModule, target: str = "python") -> TranslateResult:
    """Convenience: translate a BytecodeModule to the given target language."""
    if target == "go":
        return GoTranslator().translate(module)
    elif target == "python":
        return PythonTranslator().translate(module)
    else:
        return TranslateResult(target=target, source="", functions=[], ok=False, error=f"unknown target: {target}")
