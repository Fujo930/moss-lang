"""Moss bytecode virtual machine - executes BytecodeModule."""
from __future__ import annotations
from decimal import Decimal
from typing import Any, Callable
from pathlib import Path
import json

from .bytecode import Opcode, CodeObject, BytecodeModule
from .errors import MossRuntimeError, SourceLocation
from .values import Money, Result, Variant, format_value


class ReturnSignal(Exception):
    def __init__(self, value: Any):
        self.value = value

class BreakSignal(Exception):
    pass

class ContinueSignal(Exception):
    pass

class RequirementFailedSignal(Exception):
    def __init__(self, value: Any):
        self.value = value

class EarlyErrSignal(Exception):
    def __init__(self, value: Any):
        self.value = value


class Frame:
    __slots__ = ('code', 'pc', 'stack', 'locals', 'captured', 'global_names')
    def __init__(self, code, captured=None, global_names=None):
        self.code = code
        self.pc = 0
        self.stack = []
        self.locals = [None] * len(code.locals) if code.locals else []
        self.captured = captured or {}
        self.global_names = global_names or []


class VM:
    """Stack-based bytecode virtual machine for Moss."""
    
    def __init__(self, output=None, base_path=None, trace_rules=False, import_paths=None):
        self.globals = {}
        self.functions = {}
        self.effects = set()
        self.types = {}
        self.db = {}
        self.output = output or print
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.import_paths = [Path(p) for p in import_paths] if import_paths else []
        self.trace_rules = trace_rules
        self.trace_events = []
        self.effect_stack = []
        self.tests = []
        self._module = None
        self._imported_paths: set[Path] = set()
        self._function_globals: dict[str, list[str]] = {}
        self._module_globals: dict[str, list[str]] = {}
        self._function_source_paths: dict[str, str] = {}
        
    def load_module(self, module):
        self._module = module
        self.globals.clear()
        self.functions.clear()
        self._imported_paths = set()
        self._function_globals.clear()
        self._function_source_paths.clear()
        self._module_globals.clear()
        for name in module.globals:
            self.globals[name] = None
        for name, fn_co in module.functions.items():
            self.functions[name] = fn_co
            self._function_source_paths[name] = module.source_path
        self.effects = set(module.effects)
        self.tests = list(module.tests)
        self.install_builtins()
        # Register moss-defined functions as globals
        for name, fn_co in module.functions.items():
            self.globals[name] = fn_co
        # Process imports: compile and merge imported modules
        self._load_imports(module)
        
    def install_builtins(self):
        b = self.globals
        b['print'] = self._mk_builtin('print', self.builtin_print)
        b['assert'] = self._mk_builtin('assert', self.builtin_assert)
        b['len'] = self._mk_builtin('len', self.builtin_len)
        b['listNew'] = self._mk_builtin('listNew', lambda args: [])
        b['listPush'] = self._mk_builtin('listPush', self.builtin_list_push)
        b['listGet'] = self._mk_builtin('listGet', self.builtin_list_get)
        b['listSet'] = self._mk_builtin('listSet', self.builtin_list_set)
        b['listSlice'] = self._mk_builtin('listSlice', self.builtin_list_slice)
        b['listConcat'] = self._mk_builtin('listConcat', self.builtin_list_concat)
        b['listInsert'] = self._mk_builtin('listInsert', self.builtin_list_insert)
        b['listRemove'] = self._mk_builtin('listRemove', self.builtin_list_remove)
        b['range'] = self._mk_builtin('range', self.builtin_range)
        b['mapNew'] = self._mk_builtin('mapNew', lambda args: {})
        b['mapPut'] = self._mk_builtin('mapPut', self.builtin_map_put)
        b['mapGet'] = self._mk_builtin('mapGet', self.builtin_map_get)
        b['mapHas'] = self._mk_builtin('mapHas', self.builtin_map_has)
        b['mapKeys'] = self._mk_builtin('mapKeys', self.builtin_map_keys)
        b['mapValues'] = self._mk_builtin('mapValues', self.builtin_map_values)
        b['mapRemove'] = self._mk_builtin('mapRemove', self.builtin_map_remove)
        b['textChars'] = self._mk_builtin('textChars', self.builtin_text_chars)
        b['textJoin'] = self._mk_builtin('textJoin', self.builtin_text_join)
        b['textSplit'] = self._mk_builtin('textSplit', self.builtin_text_split)
        b['textTrim'] = self._mk_builtin('textTrim', self.builtin_text_trim)
        b['textSlice'] = self._mk_builtin('textSlice', self.builtin_text_slice)
        b['textContains'] = self._mk_builtin('textContains', self.builtin_text_contains)
        b['textIndexOf'] = self._mk_builtin('textIndexOf', self.builtin_text_index_of)
        b['textReplace'] = self._mk_builtin('textReplace', self.builtin_text_replace)
        b['textStartsWith'] = self._mk_builtin('textStartsWith', self.builtin_text_starts_with)
        b['textEndsWith'] = self._mk_builtin('textEndsWith', self.builtin_text_ends_with)
        b['pathJoin'] = self._mk_builtin('pathJoin', self.builtin_path_join)
        b['jsonParse'] = self._mk_builtin('jsonParse', self.builtin_json_parse)
        b['jsonStringify'] = self._mk_builtin('jsonStringify', self.builtin_json_stringify)
        b['httpGet'] = self._mk_builtin('httpGet', self.builtin_http_get, 'Network')
        b['httpPostJson'] = self._mk_builtin('httpPostJson', self.builtin_http_post_json, 'Network')
        b['Ok'] = self._mk_builtin('Ok', lambda args: Result(True, args[0] if args else None))
        b['Err'] = self._mk_builtin('Err', lambda args: Result(False, args[0] if args else None))
        b['dbPut'] = self._mk_builtin('dbPut', self.builtin_db_put, 'Database')
        b['dbGet'] = self._mk_builtin('dbGet', self.builtin_db_get, 'Database')
        b['readText'] = self._mk_builtin('readText', self.builtin_read_text, 'FileSystem')
        b['writeText'] = self._mk_builtin('writeText', self.builtin_write_text, 'FileSystem')
        b['fileExists'] = self._mk_builtin('fileExists', self.builtin_file_exists, 'FileSystem')
        b['listFiles'] = self._mk_builtin('listFiles', self.builtin_list_files, 'FileSystem')

    def _mk_builtin(self, name, fn, effect=None):
        from .bytecode import CodeObject
        co = CodeObject(name="<builtin>", arg_count=0, capture_count=0, locals=[], constants=[], instructions=[])
        return _BuiltinFunction(name, fn, co, effect)

    def run(self):
        if not self._module:
            raise MossRuntimeError("no module loaded")
        co = self._module.code
        frame = Frame(co, global_names=self._module.globals)
        try:
            self._execute(frame)
        except ReturnSignal:
            pass

    def run_tests(self):
        if not self._module:
            raise MossRuntimeError("no module loaded")
        co = self._module.code
        frame = Frame(co, global_names=self._module.globals)
        # Execute module-level code to register tests
        try:
            self._execute(frame)
        except ReturnSignal:
            pass
        
        results = []
        for test_name in self.tests:
            try:
                fn_co = self.functions.get(test_name)
                if fn_co is None:
                    results.append({'name': test_name, 'status': 'fail', 'message': 'test function not found'})
                    continue
                fn_globals = self._function_globals.get(test_name, self._module.globals if self._module else [])
                frame = Frame(fn_co, captured={'globals': self.globals}, global_names=fn_globals)
                self._execute(frame)
                results.append({'name': test_name, 'status': 'pass', 'message': ''})
            except Exception as exc:
                results.append({'name': test_name, 'status': 'fail', 'message': str(exc)})
        return results

    def call(self, func: Any, args: list[Any]) -> Any:
        """Call a Moss function from Python host code."""
        if isinstance(func, CodeObject):
            fn_name = func.name
            fn_globals = self._function_globals.get(fn_name, self._module.globals if self._module else [])
            frame = Frame(func, captured={'globals': self.globals}, global_names=fn_globals)
            for i, arg in enumerate(args):
                if i < len(frame.locals):
                    frame.locals[i] = arg
            try:
                self._execute(frame)
                return frame.stack.pop() if frame.stack else None
            except ReturnSignal as sig:
                return sig.value
        raise MossRuntimeError(f"cannot call {type(func).__name__}")

    def _execute(self, frame):
        while frame.pc < len(frame.code.instructions):
            inst = frame.code.instructions[frame.pc]
            op = inst.opcode
            arg = inst.arg
            frame.pc += 1
            
            if op == Opcode.NOP:
                pass
            elif op == Opcode.LOAD_CONST:
                frame.stack.append(frame.code.constants[arg])
            elif op == Opcode.LOAD_NULL:
                frame.stack.append(None)
            elif op == Opcode.LOAD_TRUE:
                frame.stack.append(True)
            elif op == Opcode.LOAD_FALSE:
                frame.stack.append(False)
            elif op == Opcode.LOAD_LOCAL:
                frame.stack.append(frame.locals[arg])
            elif op == Opcode.LOAD_GLOBAL:
                global_names = frame.global_names if frame.global_names else (self._module.globals if self._module else [])
                name = global_names[arg] if arg < len(global_names) else str(arg)
                val = self.globals.get(name)
                if val is not None:
                    frame.stack.append(val)
                elif name and name[0].isupper():
                    frame.stack.append(Variant(name))
                else:
                    raise MossRuntimeError(f"undefined global '{name}'")
            elif op == Opcode.STORE_LOCAL:
                frame.locals[arg] = frame.stack.pop()
            elif op == Opcode.STORE_GLOBAL:
                global_names = frame.global_names if frame.global_names else (self._module.globals if self._module else [])
                name = global_names[arg] if arg < len(global_names) else str(arg)
                self.globals[name] = frame.stack.pop()
            elif op == Opcode.POP:
                frame.stack.pop()
            elif op == Opcode.DUP:
                frame.stack.append(frame.stack[-1])
            elif op == Opcode.JUMP:
                frame.pc = arg
            elif op == Opcode.JUMP_IF_FALSE:
                if not frame.stack.pop():
                    frame.pc = arg
            elif op == Opcode.JUMP_IF_TRUE:
                if frame.stack.pop():
                    frame.pc = arg
            elif op == Opcode.CALL:
                self._do_call(frame, arg)
            elif op == Opcode.RETURN:
                return
            elif op == Opcode.BREAK:
                raise BreakSignal()
            elif op == Opcode.CONTINUE:
                raise ContinueSignal()
            elif op in (Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DIV, Opcode.MOD,
                         Opcode.EQ, Opcode.NEQ, Opcode.LT, Opcode.GT, Opcode.LTE, Opcode.GTE,
                         Opcode.AND, Opcode.OR):
                self._do_binary(frame, op)
            elif op == Opcode.NEG:
                frame.stack.append(-frame.stack.pop())
            elif op == Opcode.NOT:
                frame.stack.append(not frame.stack.pop())
            elif op == Opcode.BUILD_RECORD:
                count = arg
                fields = {}
                for _ in range(count):
                    val = frame.stack.pop()
                    key = frame.stack.pop()
                    fields[key] = val
                fields_rev = {k: fields[k] for k in reversed(list(fields.keys()))}
                frame.stack.append(fields_rev)
            elif op == Opcode.BUILD_LIST:
                count = arg
                items = [frame.stack.pop() for _ in range(count)]
                frame.stack.append(list(reversed(items)))
            elif op == Opcode.BUILD_VARIANT:
                name_idx = arg
                name = frame.code.constants[name_idx]
                payload_count = frame.stack.pop()
                payload = tuple(frame.stack.pop() for _ in range(payload_count))
                frame.stack.append(Variant(name, tuple(reversed(payload))))
            elif op == Opcode.GET_FIELD:
                record = frame.stack.pop()
                field_name = frame.code.constants[arg] if arg < len(frame.code.constants) else str(arg)
                # Money literal: number.currency
                if isinstance(record, (int, float)) and isinstance(field_name, str):
                    from decimal import Decimal
                    from .values import Money
                    frame.stack.append(Money(Decimal(str(record)), field_name))
                elif isinstance(record, dict):
                    frame.stack.append(record.get(field_name))
                elif isinstance(record, Variant) and not record.payload:
                    frame.stack.append(Variant(f"{record.name}.{field_name}"))
                elif isinstance(record, Variant):
                    raise MossRuntimeError(f"variant {record.name} has no field {field_name}")
                else:
                    try:
                        frame.stack.append(getattr(record, field_name))
                    except AttributeError:
                        raise MossRuntimeError(f"cannot access field '{field_name}' on {type(record).__name__}")
            elif op == Opcode.SET_FIELD:
                record = frame.stack.pop()
                val = frame.stack.pop()
                if isinstance(record, dict):
                    record = dict(record)
                    record[arg] = val
                frame.stack.append(record)
            elif op == Opcode.GET_INDEX:
                idx = int(frame.stack.pop())
                lst = frame.stack.pop()
                try:
                    frame.stack.append(lst[idx])
                except (IndexError, TypeError) as e:
                    raise MossRuntimeError(
                        f"index {idx} out of range for {type(lst).__name__} of length {len(lst)} "
                        f"in '{frame.code.name}' at instruction {frame.pc - 1}"
                    ) from e
            elif op == Opcode.SET_INDEX:
                idx = frame.stack.pop()
                lst = frame.stack.pop()
                val = frame.stack.pop()
                new_lst = list(lst)
                new_lst[idx] = val
                frame.stack.append(new_lst)
            elif op == Opcode.RECORD_UPDATE:
                count = arg
                updates = {}
                for _ in range(count):
                    val = frame.stack.pop()
                    key = frame.stack.pop()
                    updates[key] = val
                base = frame.stack.pop()
                if isinstance(base, dict):
                    result = dict(base)
                    result.update(updates)
                frame.stack.append(result)
            elif op == Opcode.MATCH_BEGIN:
                pass
            elif op == Opcode.MATCH_END:
                pass
            elif op == Opcode.REQUIRE:
                else_val = frame.stack.pop()
                raise RequirementFailedSignal(else_val)
            elif op == Opcode.TRY_PROPAGATE:
                val = frame.stack.pop()
                if isinstance(val, Result) and not val.ok:
                    raise EarlyErrSignal(val.value)
                frame.stack.append(val if not isinstance(val, Result) else val.value)
            else:
                raise MossRuntimeError(f"unknown opcode: {op}")

    def _do_call(self, frame, arg_count):
        args = [frame.stack.pop() for _ in range(arg_count)]
        args.reverse()
        callee = frame.stack.pop()
        
        # Resolve name to callable
        if isinstance(callee, str):
            callee = self._resolve_callable(callee, frame)
        
        if isinstance(callee, _BuiltinFunction):
            result = callee(args)
            frame.stack.append(result)
        elif isinstance(callee, Variant):
            frame.stack.append(Variant(callee.name, tuple(args)))
        elif isinstance(callee, CodeObject):
            fn_name = callee.name
            fn_globals = self._function_globals.get(fn_name, self._module.globals if self._module else [])
            new_frame = Frame(callee, captured={'globals': self.globals}, global_names=fn_globals)
            for i, arg in enumerate(args):
                if i < len(new_frame.locals):
                    new_frame.locals[i] = arg
            # Record argument names/values for potential trace
            arg_names = list(new_frame.code.locals[:callee.arg_count]) if callee.is_rule else []
            arg_values = list(args[:callee.arg_count]) if callee.is_rule else []
            try:
                self._execute(new_frame)
                if new_frame.stack:
                    result = new_frame.stack.pop()
                    if callee.is_rule and self.trace_rules:
                        source_path = self._function_source_paths.get(fn_name, self._module.source_path if self._module else "")
                        self.trace_events.append({
                            "rule": fn_name,
                            "arguments": {name: format_value(val) for name, val in zip(arg_names, arg_values)},
                            "result": format_value(result),
                            "file": source_path,
                            "line": callee.source_line,
                            "column": callee.source_column,
                        })
                    frame.stack.append(result)
            except ReturnSignal as sig:
                result = sig.value
                if callee.is_rule and self.trace_rules:
                    source_path = self._function_source_paths.get(fn_name, self._module.source_path if self._module else "")
                    self.trace_events.append({
                        "rule": fn_name,
                        "arguments": {name: format_value(val) for name, val in zip(arg_names, arg_values)},
                        "result": format_value(result),
                        "file": source_path,
                        "line": callee.source_line,
                        "column": callee.source_column,
                    })
                frame.stack.append(result)
            except BreakSignal:
                raise MossRuntimeError("break outside loop")
            except ContinueSignal:
                raise MossRuntimeError("continue outside loop")
            except RequirementFailedSignal as sig:
                frame.stack.append(Result(False, sig.value))
            except EarlyErrSignal as sig:
                frame.stack.append(Result(False, sig.value))
        else:
            raise MossRuntimeError(f"cannot call {type(callee).__name__}")

    def _resolve_callable(self, name, frame):
        # Check frame locals for lambda / closure values
        if name in frame.code.locals:
            idx = frame.code.locals.index(name)
            val = frame.locals[idx]
            if isinstance(val, CodeObject):
                return val
        if name in self.globals:
            return self.globals[name]
        if name in self.functions:
            return self.functions[name]
        # Variant constructors
        if name and name[0].isupper():
            return Variant(name)
        raise MossRuntimeError(f"undefined function '{name}'")

    def _do_binary(self, frame, op):
        right = frame.stack.pop()
        left = frame.stack.pop()
        
        # Extract Money amounts for comparison/arithmetic
        left_val = left.amount if isinstance(left, Money) else left
        right_val = right.amount if isinstance(right, Money) else right

        if op == Opcode.ADD:
            if isinstance(left, Money) and isinstance(right, Money):
                if left.currency != right.currency:
                    raise MossRuntimeError(f"currency mismatch: {left.currency} vs {right.currency}")
                frame.stack.append(Money(left.amount + right.amount, left.currency))
            elif isinstance(left, Money):
                frame.stack.append(Money(left.amount + Decimal(str(right)), left.currency))
            elif isinstance(right, Money):
                frame.stack.append(Money(Decimal(str(left)) + right.amount, right.currency))
            else:
                if isinstance(left, str) or isinstance(right, str):
                    from .values import format_value
                    frame.stack.append(format_value(left) + format_value(right))
                else:
                    frame.stack.append(left + right)
        elif op == Opcode.SUB:
            if isinstance(left, Money) and isinstance(right, Money):
                if left.currency != right.currency:
                    raise MossRuntimeError(f"currency mismatch: {left.currency} vs {right.currency}")
                frame.stack.append(Money(left.amount - right.amount, left.currency))
            else:
                frame.stack.append(left - right)
        elif op == Opcode.MUL:
            if isinstance(left, Money):
                frame.stack.append(Money(left.amount * Decimal(str(right)), left.currency))
            elif isinstance(right, Money):
                frame.stack.append(Money(Decimal(str(left)) * right.amount, right.currency))
            else:
                frame.stack.append(left * right)
        elif op == Opcode.DIV:
            if isinstance(left, Money):
                frame.stack.append(Money(left.amount / Decimal(str(right)), left.currency))
            else:
                frame.stack.append(left / right)
        elif op == Opcode.MOD:
            frame.stack.append(left % right)
        elif op == Opcode.EQ:
            frame.stack.append(left_val == right_val and (not isinstance(left, Money) or not isinstance(right, Money) or left.currency == right.currency))
        elif op == Opcode.NEQ:
            frame.stack.append(left_val != right_val or (isinstance(left, Money) and isinstance(right, Money) and left.currency != right.currency))
        elif op == Opcode.LT:
            frame.stack.append(left_val < right_val)
        elif op == Opcode.GT:
            frame.stack.append(left_val > right_val)
        elif op == Opcode.LTE:
            frame.stack.append(left_val <= right_val)
        elif op == Opcode.GTE:
            frame.stack.append(left_val >= right_val)
        elif op == Opcode.AND:
            frame.stack.append(left and right)
        elif op == Opcode.OR:
            frame.stack.append(left or right)

    # ── Builtin implementations ──

    def builtin_print(self, args):
        self.output(" ".join(format_value(a) for a in args) + "\n")
        return None

    def builtin_assert(self, args):
        condition, *rest = args
        msg = rest[0] if rest else "assertion failed"
        if not condition:
            raise MossRuntimeError(str(msg))
        return None

    def builtin_len(self, args):
        return len(args[0])

    def builtin_list_push(self, args):
        lst, item = args
        lst.append(item)
        return lst

    def builtin_list_get(self, args):
        lst = args[0]
        idx = int(args[1])
        if len(args) > 2:
            return lst[idx] if idx < len(lst) else args[2]
        return lst[idx]

    def builtin_list_set(self, args):
        lst, idx, val = args
        lst[idx] = val
        return lst

    def builtin_list_slice(self, args):
        lst = args[0]
        start = int(args[1])
        end = int(args[2]) if len(args) > 2 else None
        return lst[start:end]

    def builtin_list_concat(self, args):
        a, b = args
        return a + b

    def builtin_list_insert(self, args):
        lst, idx, val = args
        lst.insert(int(idx), val)
        return lst

    def builtin_list_remove(self, args):
        lst, idx = args
        del lst[idx]
        return lst

    def builtin_range(self, args):
        if len(args) == 1:
            return list(range(int(float(args[0]))))
        return list(range(int(float(args[0])), int(float(args[1]))))

    def builtin_map_new(self, args):
        return {}

    def builtin_map_put(self, args):
        m, k, v = args
        m[k] = v
        return m

    def builtin_map_get(self, args):
        m = args[0]
        k = args[1]
        if len(args) > 2:
            return m.get(k, args[2])
        return m[k]

    def builtin_map_has(self, args):
        m, k = args
        return k in m

    def builtin_map_keys(self, args):
        return list(args[0].keys())

    def builtin_map_values(self, args):
        return list(args[0].values())

    def builtin_map_remove(self, args):
        m, k = args
        del m[k]
        return m

    def builtin_text_chars(self, args):
        return list(args[0])

    def builtin_text_join(self, args):
        if len(args) == 0:
            return ""
        if len(args) == 1:
            return "".join(args[0])
        parts, sep = args
        return sep.join(parts)

    def builtin_text_split(self, args):
        text, sep = args
        return text.split(sep)

    def builtin_text_trim(self, args):
        return args[0].strip()

    def builtin_text_slice(self, args):
        text = args[0]
        start = int(args[1])
        end = int(args[2]) if len(args) > 2 else None
        return text[start:end]

    def builtin_text_contains(self, args):
        text, sub = args
        return sub in text

    def builtin_text_index_of(self, args):
        text, sub = args
        try:
            return text.index(sub)
        except ValueError:
            return -1

    def builtin_text_replace(self, args):
        text, old, new = args
        return text.replace(old, new)

    def builtin_text_starts_with(self, args):
        text, prefix = args
        return text.startswith(prefix)

    def builtin_text_ends_with(self, args):
        text, suffix = args
        return text.endswith(suffix)

    def builtin_path_join(self, args):
        return str(Path(args[0]) / args[1])

    def builtin_json_parse(self, args):
        return json.loads(args[0])

    def builtin_json_stringify(self, args):
        return json.dumps(args[0], default=str)

    def builtin_http_get(self, args):
        from urllib import request as url_request
        with url_request.urlopen(args[0]) as resp:
            return resp.read().decode('utf-8')

    def builtin_http_post_json(self, args):
        from urllib import request as url_request
        url, body = args
        data = json.dumps(body).encode('utf-8')
        req = url_request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        with url_request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))

    def builtin_db_put(self, args):
        key, val = args
        self.db[key] = val
        return val

    def builtin_db_get(self, args):
        return self.db[args[0]]

    def builtin_read_text(self, args):
        return Path(args[0]).read_text(encoding='utf-8')

    def builtin_write_text(self, args):
        Path(args[0]).write_text(args[1], encoding='utf-8')
        return None

    def builtin_file_exists(self, args):
        return Path(args[0]).exists()

    def builtin_list_files(self, args):
        return [str(p) for p in Path(args[0]).iterdir()]

    def _load_imports(self, module) -> None:
        """Compile and merge all imported modules into the VM state."""
        from .parser import parse_source
        from .compiler import compile_program
        source_dir = Path(module.source_path).parent if module.source_path else self.base_path
        for import_path in module.imports:
            resolved = self._resolve_import_path(import_path, source_dir)
            if resolved in self._imported_paths:
                continue
            self._imported_paths.add(resolved)
            source = resolved.read_text(encoding="utf-8-sig")
            program = parse_source(source)
            imported_mod = compile_program(program, source_path=str(resolved))
            self._module_globals[str(resolved)] = list(imported_mod.globals)
            for name, fn_co in imported_mod.functions.items():
                self.functions[name] = fn_co
                self.globals[name] = fn_co
                self._function_globals[name] = list(imported_mod.globals)
                self._function_source_paths[name] = str(resolved)
            self.effects.update(imported_mod.effects)
            self.tests.extend(imported_mod.tests)
            self._load_imports(imported_mod)

    def _resolve_import_path(self, import_path: str, source_dir: Path) -> Path:
        from pathlib import Path as _Path
        path = _Path(import_path)
        if path.is_absolute():
            return path.resolve()
        candidates = [source_dir / path, self.base_path / path, _Path.cwd() / path]
        for search_path in self.import_paths:
            candidates.append(search_path / path)
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        raise MossRuntimeError(f"import not found: {import_path}")

class _BuiltinFunction:
    def __init__(self, name, fn, co, effect=None):
        self._name = name
        self._fn = fn
        self.code = co
        self.effect = effect

    def __call__(self, args):
        return self._fn(args)
