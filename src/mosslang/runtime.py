from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from .errors import MossRuntimeError
from .nodes import (
    AssignStmt,
    BinaryExpr,
    CallExpr,
    EffectDecl,
    ExprStmt,
    FieldAccess,
    ForStmt,
    FunctionDecl,
    Identifier,
    IfStmt,
    ImportDecl,
    IndexAccess,
    LetStmt,
    Literal,
    BreakStmt,
    BindingPattern,
    ContinueStmt,
    LiteralPattern,
    ListLiteral,
    MatchExpr,
    NumberLiteral,
    Program,
    RecordLiteral,
    RecordUpdate,
    RequireStmt,
    ReturnStmt,
    RuleDecl,
    TestDecl,
    TryExpr,
    TypeDecl,
    UnaryExpr,
    VariantPattern,
    WhileStmt,
    WildcardPattern,
)
from .values import Money, Result, Variant, format_value


class ReturnSignal(Exception):
    def __init__(self, value: Any):
        self.value = value


class EarlyErrSignal(Exception):
    def __init__(self, value: Any):
        self.value = value


class RequirementFailedSignal(Exception):
    def __init__(self, value: Any):
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class Environment:
    def __init__(self, parent: Environment | None = None):
        self.parent = parent
        self.values: dict[str, Any] = {}

    def define(self, name: str, value: Any) -> None:
        self.values[name] = value

    def assign(self, name: str, value: Any) -> None:
        if name in self.values:
            self.values[name] = value
            return
        if self.parent is not None and self.parent.contains(name):
            self.parent.assign(name, value)
            return
        self.values[name] = value

    def contains(self, name: str) -> bool:
        return name in self.values or (self.parent is not None and self.parent.contains(name))

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.get(name)
        if name and name[0].isupper():
            return Variant(name)
        raise MossRuntimeError(f"undefined name '{name}'")


@dataclass(frozen=True)
class BuiltinFunction:
    name: str
    fn: Callable[..., Any]
    effect: str | None = None


@dataclass(frozen=True)
class UserFunction:
    decl: FunctionDecl | RuleDecl
    runtime: Runtime
    closure: Environment
    is_rule: bool = False

    @property
    def name(self) -> str:
        return self.decl.name

    @property
    def uses(self) -> list[str]:
        if isinstance(self.decl, FunctionDecl):
            return self.decl.uses
        return []

    @property
    def return_type(self) -> str | None:
        return self.decl.return_type

    def call(self, args: list[Any]) -> Any:
        if len(args) != len(self.decl.params):
            raise MossRuntimeError(f"{self.name} expected {len(self.decl.params)} args, got {len(args)}")

        self.runtime.ensure_call_allowed(self)
        local = Environment(self.closure)
        for param, arg in zip(self.decl.params, args):
            if param.type_name is not None:
                self.runtime.require_type(arg, param.type_name, f"argument '{param.name}' for {self.name}")
            local.define(param.name, arg)

        self.runtime.effect_stack.append(set(self.uses))
        result: Any = None
        try:
            if isinstance(self.decl, RuleDecl):
                result = self.runtime.evaluate(self.decl.expr, local)
            else:
                try:
                    self.runtime.execute_block(self.decl.body, local)
                except ReturnSignal as signal:
                    result = signal.value
        except EarlyErrSignal as signal:
            if self.returns_result():
                result = Result(False, signal.value)
            else:
                raise MossRuntimeError(f"{self.name} used '?' on Err({format_value(signal.value)})")
        except RequirementFailedSignal as signal:
            if self.returns_result():
                result = Result(False, signal.value)
            else:
                raise MossRuntimeError(f"require failed in {self.name}: {format_value(signal.value)}")
        except BreakSignal as exc:
            raise MossRuntimeError("break is only allowed inside loops") from exc
        except ContinueSignal as exc:
            raise MossRuntimeError("continue is only allowed inside loops") from exc
        finally:
            self.runtime.effect_stack.pop()

        if self.return_type is not None:
            self.runtime.require_type(result, self.return_type, f"return value for {self.name}")
        return result

    def returns_result(self) -> bool:
        return self.return_type is not None and self.return_type.startswith("Result")


class Runtime:
    def __init__(self, output: Callable[[str], None] | None = None, base_path: str | Path | None = None):
        self.effects: set[str] = set()
        self.types: dict[str, TypeDecl] = {}
        self.globals = Environment()
        self.db: dict[str, Any] = {}
        self.output = output or print
        self.effect_stack: list[set[str]] = []
        self.base_path = Path(base_path) if base_path is not None else Path.cwd()
        self.imported_paths: set[Path] = set()
        self.install_builtins()
        self.tests: list[TestDecl] = []

    def install_builtins(self) -> None:
        self.globals.define("print", BuiltinFunction("print", self.builtin_print))
        self.globals.define("assert", BuiltinFunction("assert", self.builtin_assert))
        self.globals.define("len", BuiltinFunction("len", self.builtin_len))
        self.globals.define("listPush", BuiltinFunction("listPush", self.builtin_list_push))
        self.globals.define("listGet", BuiltinFunction("listGet", self.builtin_list_get))
        self.globals.define("listSet", BuiltinFunction("listSet", self.builtin_list_set))
        self.globals.define("listSlice", BuiltinFunction("listSlice", self.builtin_list_slice))
        self.globals.define("listConcat", BuiltinFunction("listConcat", self.builtin_list_concat))
        self.globals.define("listInsert", BuiltinFunction("listInsert", self.builtin_list_insert))
        self.globals.define("listRemove", BuiltinFunction("listRemove", self.builtin_list_remove))
        self.globals.define("range", BuiltinFunction("range", self.builtin_range))
        self.globals.define("mapNew", BuiltinFunction("mapNew", self.builtin_map_new))
        self.globals.define("mapPut", BuiltinFunction("mapPut", self.builtin_map_put))
        self.globals.define("mapGet", BuiltinFunction("mapGet", self.builtin_map_get))
        self.globals.define("mapHas", BuiltinFunction("mapHas", self.builtin_map_has))
        self.globals.define("mapKeys", BuiltinFunction("mapKeys", self.builtin_map_keys))
        self.globals.define("mapValues", BuiltinFunction("mapValues", self.builtin_map_values))
        self.globals.define("mapRemove", BuiltinFunction("mapRemove", self.builtin_map_remove))
        self.globals.define("textChars", BuiltinFunction("textChars", self.builtin_text_chars))
        self.globals.define("textJoin", BuiltinFunction("textJoin", self.builtin_text_join))
        self.globals.define("textSplit", BuiltinFunction("textSplit", self.builtin_text_split))
        self.globals.define("textTrim", BuiltinFunction("textTrim", self.builtin_text_trim))
        self.globals.define("textSlice", BuiltinFunction("textSlice", self.builtin_text_slice))
        self.globals.define("textContains", BuiltinFunction("textContains", self.builtin_text_contains))
        self.globals.define("textStartsWith", BuiltinFunction("textStartsWith", self.builtin_text_starts_with))
        self.globals.define("textEndsWith", BuiltinFunction("textEndsWith", self.builtin_text_ends_with))
        self.globals.define("pathJoin", BuiltinFunction("pathJoin", self.builtin_path_join))
        self.globals.define("Ok", BuiltinFunction("Ok", lambda value=None: Result(True, value)))
        self.globals.define("Err", BuiltinFunction("Err", lambda value=None: Result(False, value)))
        self.globals.define("dbPut", BuiltinFunction("dbPut", self.builtin_db_put, effect="Database"))
        self.globals.define("dbGet", BuiltinFunction("dbGet", self.builtin_db_get, effect="Database"))
        self.globals.define("readText", BuiltinFunction("readText", self.builtin_read_text, effect="FileSystem"))
        self.globals.define("writeText", BuiltinFunction("writeText", self.builtin_write_text, effect="FileSystem"))
        self.globals.define("fileExists", BuiltinFunction("fileExists", self.builtin_file_exists, effect="FileSystem"))
        self.globals.define("listFiles", BuiltinFunction("listFiles", self.builtin_list_files, effect="FileSystem"))

    def run(self, program: Program) -> Environment:
        statements: list[Any] = []
        for item in program.items:
            if isinstance(item, ImportDecl):
                self.run_import(item.path)
            elif isinstance(item, EffectDecl):
                self.effects.update(item.names)
            elif isinstance(item, TypeDecl):
                self.types[item.name] = item
            elif isinstance(item, RuleDecl):
                self.globals.define(item.name, UserFunction(item, self, self.globals, is_rule=True))
            elif isinstance(item, FunctionDecl):
                self.globals.define(item.name, UserFunction(item, self, self.globals))
            elif isinstance(item, TestDecl):
                self.tests.append(item)
            else:
                statements.append(item)

        for statement in statements:
            try:
                self.execute(statement, self.globals)
            except ReturnSignal:
                raise MossRuntimeError("return is only allowed inside functions")
            except RequirementFailedSignal as signal:
                raise MossRuntimeError(f"top-level require failed: {format_value(signal.value)}")
            except EarlyErrSignal as signal:
                raise MossRuntimeError(f"top-level '?' received Err({format_value(signal.value)})")
            except BreakSignal as exc:
                raise MossRuntimeError("break is only allowed inside loops") from exc
            except ContinueSignal as exc:
                raise MossRuntimeError("continue is only allowed inside loops") from exc
        return self.globals

    def run_import(self, import_path: str) -> None:
        from .parser import parse_source

        resolved = self.resolve_import_path(import_path)
        if resolved in self.imported_paths:
            return
        self.imported_paths.add(resolved)
        source = resolved.read_text(encoding="utf-8-sig")
        imported_program = parse_source(source)
        previous_base = self.base_path
        self.base_path = resolved.parent
        try:
            self.run(imported_program)
        finally:
            self.base_path = previous_base

    def resolve_import_path(self, import_path: str) -> Path:
        path = Path(import_path)
        candidates = [path] if path.is_absolute() else [self.base_path / path, Path.cwd() / path]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        raise MossRuntimeError(f"import not found: {import_path}")

    def run_tests(self, program: Program) -> list[dict[str, str]]:
        self.run(program)
        results: list[dict[str, str]] = []
        for test in self.tests:
            try:
                self.execute_block(test.body, Environment(self.globals))
            except MossRuntimeError as exc:
                results.append({"name": test.name, "status": "fail", "message": str(exc)})
            except ReturnSignal:
                results.append({"name": test.name, "status": "fail", "message": "return is not allowed inside test blocks"})
            except RequirementFailedSignal as signal:
                results.append({"name": test.name, "status": "fail", "message": f"require failed: {format_value(signal.value)}"})
            except EarlyErrSignal as signal:
                results.append({"name": test.name, "status": "fail", "message": f"'?' received Err({format_value(signal.value)})"})
            except BreakSignal:
                results.append({"name": test.name, "status": "fail", "message": "break is only allowed inside loops"})
            except ContinueSignal:
                results.append({"name": test.name, "status": "fail", "message": "continue is only allowed inside loops"})
            else:
                results.append({"name": test.name, "status": "pass", "message": ""})
        return results

    def execute_block(self, statements: list[Any], env: Environment) -> None:
        for statement in statements:
            self.execute(statement, env)

    def execute(self, statement: Any, env: Environment) -> None:
        if isinstance(statement, LetStmt):
            env.define(statement.name, self.evaluate(statement.expr, env))
            return
        if isinstance(statement, AssignStmt):
            env.assign(statement.name, self.evaluate(statement.expr, env))
            return
        if isinstance(statement, ReturnStmt):
            raise ReturnSignal(self.evaluate(statement.expr, env))
        if isinstance(statement, RequireStmt):
            if not truthy(self.evaluate(statement.condition, env)):
                raise RequirementFailedSignal(self.evaluate(statement.else_expr, env))
            return
        if isinstance(statement, IfStmt):
            if truthy(self.evaluate(statement.condition, env)):
                self.execute_block(statement.then_body, Environment(env))
            else:
                self.execute_block(statement.else_body, Environment(env))
            return
        if isinstance(statement, ForStmt):
            iterable = self.evaluate(statement.iterable, env)
            if not isinstance(iterable, list):
                raise MossRuntimeError("for loop target must be a List")
            for item in iterable:
                loop_env = Environment(env)
                loop_env.define(statement.name, item)
                try:
                    self.execute_block(statement.body, loop_env)
                except ContinueSignal:
                    continue
                except BreakSignal:
                    break
            return
        if isinstance(statement, WhileStmt):
            while truthy(self.evaluate(statement.condition, env)):
                try:
                    self.execute_block(statement.body, Environment(env))
                except ContinueSignal:
                    continue
                except BreakSignal:
                    break
            return
        if isinstance(statement, BreakStmt):
            raise BreakSignal()
        if isinstance(statement, ContinueStmt):
            raise ContinueSignal()
        if isinstance(statement, ExprStmt):
            self.evaluate(statement.expr, env)
            return
        raise MossRuntimeError(f"cannot execute {type(statement).__name__}")

    def evaluate(self, expr: Any, env: Environment) -> Any:
        if isinstance(expr, Literal):
            return expr.value
        if isinstance(expr, NumberLiteral):
            return expr.value
        if isinstance(expr, Identifier):
            return env.get(expr.name)
        if isinstance(expr, RecordLiteral):
            return {key: self.evaluate(value, env) for key, value in expr.fields.items()}
        if isinstance(expr, ListLiteral):
            return [self.evaluate(item, env) for item in expr.items]
        if isinstance(expr, RecordUpdate):
            base = self.evaluate(expr.base, env)
            if not isinstance(base, dict):
                raise MossRuntimeError("record update target must be a record")
            updated = dict(base)
            for key, value in expr.updates.items():
                updated[key] = self.evaluate(value, env)
            return updated
        if isinstance(expr, UnaryExpr):
            right = self.evaluate(expr.right, env)
            if expr.op == "not":
                return not truthy(right)
            if expr.op == "-":
                return -right
            raise MossRuntimeError(f"unknown unary operator {expr.op}")
        if isinstance(expr, BinaryExpr):
            return self.evaluate_binary(expr, env)
        if isinstance(expr, FieldAccess):
            target = self.evaluate(expr.target, env)
            return self.get_field(target, expr.field)
        if isinstance(expr, IndexAccess):
            target = self.evaluate(expr.target, env)
            index = self.evaluate(expr.index, env)
            return self.get_index(target, index)
        if isinstance(expr, CallExpr):
            callee = self.evaluate(expr.callee, env)
            args = [self.evaluate(arg, env) for arg in expr.args]
            return self.call(callee, args)
        if isinstance(expr, TryExpr):
            value = self.evaluate(expr.expr, env)
            if not isinstance(value, Result):
                raise MossRuntimeError("'?' can only be used with Result values")
            if value.ok:
                return value.value
            raise EarlyErrSignal(value.value)
        if isinstance(expr, MatchExpr):
            return self.evaluate_match(expr, env)
        raise MossRuntimeError(f"cannot evaluate {type(expr).__name__}")

    def evaluate_match(self, expr: MatchExpr, env: Environment) -> Any:
        subject = self.evaluate(expr.subject, env)
        for case in expr.cases:
            bindings = match_pattern(case.pattern, subject)
            if bindings is None:
                continue
            case_env = Environment(env)
            for name, value in bindings.items():
                case_env.define(name, value)
            return self.evaluate(case.expr, case_env)
        raise MossRuntimeError(f"match did not cover value {format_value(subject)}")

    def evaluate_binary(self, expr: BinaryExpr, env: Environment) -> Any:
        if expr.op == "and":
            left = self.evaluate(expr.left, env)
            if not truthy(left):
                return False
            return truthy(self.evaluate(expr.right, env))
        if expr.op == "or":
            left = self.evaluate(expr.left, env)
            if truthy(left):
                return True
            return truthy(self.evaluate(expr.right, env))

        left = self.evaluate(expr.left, env)
        right = self.evaluate(expr.right, env)

        if expr.op == "==":
            return left == right
        if expr.op == "!=":
            return left != right
        if expr.op == "+":
            return add_values(left, right)
        if expr.op == "-":
            return subtract_values(left, right)
        if expr.op == "*":
            return multiply_values(left, right)
        if expr.op == "/":
            return divide_values(left, right)
        if expr.op in {">", ">=", "<", "<="}:
            return compare_values(left, right, expr.op)
        raise MossRuntimeError(f"unknown binary operator {expr.op}")

    def get_field(self, target: Any, field: str) -> Any:
        if isinstance(target, Decimal):
            return Money(target, field)
        if isinstance(target, dict):
            if field not in target:
                raise MossRuntimeError(f"record has no field '{field}'")
            return target[field]
        if isinstance(target, Variant) and not target.payload:
            return Variant(f"{target.name}.{field}")
        if isinstance(target, Result):
            if field == "ok":
                return target.ok
            if field == "value":
                return target.value
        raise MossRuntimeError(f"value {format_value(target)} has no field '{field}'")

    def get_index(self, target: Any, index: Any) -> Any:
        if not isinstance(index, Decimal):
            raise MossRuntimeError("index must be a Number")
        numeric_index = int(index)
        if index != numeric_index:
            raise MossRuntimeError("index must be an integer Number")
        try:
            if isinstance(target, (list, str)):
                return target[numeric_index]
        except IndexError as exc:
            raise MossRuntimeError(f"index out of range: {numeric_index}") from exc
        raise MossRuntimeError("index target must be a List or Text")

    def call(self, callee: Any, args: list[Any]) -> Any:
        if isinstance(callee, BuiltinFunction):
            self.ensure_effect_allowed(callee.effect, callee.name)
            return callee.fn(*args)
        if isinstance(callee, UserFunction):
            return callee.call(args)
        if isinstance(callee, Variant):
            return Variant(callee.name, tuple(args))
        raise MossRuntimeError(f"{format_value(callee)} is not callable")

    def ensure_call_allowed(self, callee: UserFunction) -> None:
        if not self.effect_stack:
            return
        allowed = self.effect_stack[-1]
        missing = [effect for effect in callee.uses if effect not in allowed]
        if missing:
            joined = ", ".join(missing)
            raise MossRuntimeError(f"calling {callee.name} requires missing effect(s): {joined}")

    def ensure_effect_allowed(self, effect: str | None, callee: str) -> None:
        if effect is None or not self.effect_stack:
            return
        if effect not in self.effect_stack[-1]:
            raise MossRuntimeError(f"{callee} requires effect {effect}; add 'uses {effect}' to this function")

    def builtin_print(self, *values: Any) -> None:
        self.output(" ".join(format_value(value) for value in values))

    def builtin_assert(self, condition: Any, message: Any = "assertion failed") -> None:
        if not truthy(condition):
            raise MossRuntimeError(format_value(message))

    def builtin_len(self, value: Any) -> Decimal:
        if not isinstance(value, (list, str, dict)):
            raise MossRuntimeError("len expects a List, Text, or record")
        return Decimal(len(value))

    def builtin_list_push(self, values: Any, value: Any) -> Any:
        if not isinstance(values, list):
            raise MossRuntimeError("listPush expects a List")
        return [*values, value]

    def builtin_list_get(self, values: Any, index: Any, default: Any = None) -> Any:
        if not isinstance(values, list):
            raise MossRuntimeError("listGet expects a List")
        numeric_index = decimal_to_int(index, "listGet index")
        if numeric_index < 0 or numeric_index >= len(values):
            return default
        return values[numeric_index]

    def builtin_list_set(self, values: Any, index: Any, value: Any) -> Any:
        if not isinstance(values, list):
            raise MossRuntimeError("listSet expects a List")
        numeric_index = decimal_to_int(index, "listSet index")
        if numeric_index < 0 or numeric_index >= len(values):
            raise MossRuntimeError(f"listSet index out of range: {numeric_index}")
        updated = list(values)
        updated[numeric_index] = value
        return updated

    def builtin_list_slice(self, values: Any, start: Any, end: Any | None = None) -> Any:
        if not isinstance(values, list):
            raise MossRuntimeError("listSlice expects a List")
        start_value = decimal_to_int(start, "listSlice start")
        end_value = None if end is None else decimal_to_int(end, "listSlice end")
        return values[start_value:end_value]

    def builtin_list_concat(self, left: Any, right: Any) -> Any:
        if not isinstance(left, list) or not isinstance(right, list):
            raise MossRuntimeError("listConcat expects two Lists")
        return [*left, *right]

    def builtin_list_insert(self, values: Any, index: Any, value: Any) -> Any:
        if not isinstance(values, list):
            raise MossRuntimeError("listInsert expects a List")
        numeric_index = decimal_to_int(index, "listInsert index")
        if numeric_index < 0 or numeric_index > len(values):
            raise MossRuntimeError(f"listInsert index out of range: {numeric_index}")
        return [*values[:numeric_index], value, *values[numeric_index:]]

    def builtin_list_remove(self, values: Any, index: Any) -> Any:
        if not isinstance(values, list):
            raise MossRuntimeError("listRemove expects a List")
        numeric_index = decimal_to_int(index, "listRemove index")
        if numeric_index < 0 or numeric_index >= len(values):
            raise MossRuntimeError(f"listRemove index out of range: {numeric_index}")
        return [*values[:numeric_index], *values[numeric_index + 1 :]]

    def builtin_range(self, start: Any, end: Any | None = None) -> list[Decimal]:
        if end is None:
            start_value = 0
            end_value = decimal_to_int(start, "range end")
        else:
            start_value = decimal_to_int(start, "range start")
            end_value = decimal_to_int(end, "range end")
        return [Decimal(item) for item in range(start_value, end_value)]

    def builtin_map_new(self) -> dict[Any, Any]:
        return {}

    def builtin_map_put(self, mapping: Any, key: Any, value: Any) -> dict[Any, Any]:
        require_map(mapping, "mapPut")
        require_hashable(key, "mapPut key")
        updated = dict(mapping)
        updated[key] = value
        return updated

    def builtin_map_get(self, mapping: Any, key: Any, default: Any = None) -> Any:
        require_map(mapping, "mapGet")
        require_hashable(key, "mapGet key")
        return mapping.get(key, default)

    def builtin_map_has(self, mapping: Any, key: Any) -> bool:
        require_map(mapping, "mapHas")
        require_hashable(key, "mapHas key")
        return key in mapping

    def builtin_map_keys(self, mapping: Any) -> list[Any]:
        require_map(mapping, "mapKeys")
        return list(mapping.keys())

    def builtin_map_values(self, mapping: Any) -> list[Any]:
        require_map(mapping, "mapValues")
        return list(mapping.values())

    def builtin_map_remove(self, mapping: Any, key: Any) -> dict[Any, Any]:
        require_map(mapping, "mapRemove")
        require_hashable(key, "mapRemove key")
        updated = dict(mapping)
        updated.pop(key, None)
        return updated

    def builtin_text_chars(self, text: Any) -> list[str]:
        require_text(text, "textChars")
        return list(text)

    def builtin_text_join(self, values: Any, separator: Any = "") -> str:
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise MossRuntimeError("textJoin expects a List<Text>")
        require_text(separator, "textJoin separator")
        return separator.join(values)

    def builtin_text_split(self, text: Any, separator: Any) -> list[str]:
        require_text(text, "textSplit")
        require_text(separator, "textSplit separator")
        if separator == "":
            return list(text)
        return text.split(separator)

    def builtin_text_trim(self, text: Any) -> str:
        require_text(text, "textTrim")
        return text.strip()

    def builtin_text_slice(self, text: Any, start: Any, end: Any | None = None) -> str:
        require_text(text, "textSlice")
        start_value = decimal_to_int(start, "textSlice start")
        end_value = None if end is None else decimal_to_int(end, "textSlice end")
        return text[start_value:end_value]

    def builtin_text_contains(self, text: Any, needle: Any) -> bool:
        require_text(text, "textContains")
        require_text(needle, "textContains needle")
        return needle in text

    def builtin_text_starts_with(self, text: Any, prefix: Any) -> bool:
        require_text(text, "textStartsWith")
        require_text(prefix, "textStartsWith prefix")
        return text.startswith(prefix)

    def builtin_text_ends_with(self, text: Any, suffix: Any) -> bool:
        require_text(text, "textEndsWith")
        require_text(suffix, "textEndsWith suffix")
        return text.endswith(suffix)

    def builtin_path_join(self, *parts: Any) -> str:
        if not parts:
            return ""
        for part in parts:
            require_text(part, "pathJoin")
        return str(Path(parts[0]).joinpath(*parts[1:]))

    def builtin_db_put(self, key: Any, value: Any) -> Any:
        self.db[str(key)] = value
        return value

    def builtin_db_get(self, key: Any) -> Any:
        return self.db.get(str(key))

    def builtin_read_text(self, path: Any) -> str:
        require_text(path, "readText")
        return Path(path).read_text(encoding="utf-8-sig")

    def builtin_write_text(self, path: Any, text: Any) -> str:
        require_text(path, "writeText path")
        require_text(text, "writeText text")
        Path(path).write_text(text, encoding="utf-8")
        return path

    def builtin_file_exists(self, path: Any) -> bool:
        require_text(path, "fileExists")
        return Path(path).exists()

    def builtin_list_files(self, path: Any) -> list[str]:
        require_text(path, "listFiles")
        directory = Path(path)
        if not directory.is_dir():
            raise MossRuntimeError(f"listFiles expects a directory: {path}")
        return sorted(str(item) for item in directory.iterdir())

    def require_type(self, value: Any, expected: str, context: str) -> None:
        if not self.value_matches_type(value, expected):
            actual = describe_value_type(value)
            raise MossRuntimeError(f"type mismatch for {context}: expected {expected}, got {actual}")

    def value_matches_type(self, value: Any, expected: str) -> bool:
        expected = expected.strip()
        if expected in {"Any", "Unknown"}:
            return True
        if "|" in expected:
            return any(self.value_matches_type(value, part.strip()) for part in split_top_level(expected, "|"))
        if expected == "Text":
            return isinstance(value, str)
        if expected == "Bool":
            return isinstance(value, bool)
        if expected == "Number":
            return isinstance(value, Decimal)
        if expected == "Money":
            return isinstance(value, Money)
        if expected == "Null":
            return value is None
        generic = parse_generic(expected)
        if generic is not None:
            name, args = generic
            if name == "Result" and len(args) == 2:
                if not isinstance(value, Result):
                    return False
                ok_type, err_type = args
                return self.value_matches_type(value.value, ok_type if value.ok else err_type)
            if name == "List" and len(args) == 1:
                return isinstance(value, list) and all(self.value_matches_type(item, args[0]) for item in value)
            if name == "Option" and len(args) == 1:
                return value is None or self.value_matches_type(value, args[0])
            if name == "Map" and len(args) == 2:
                return isinstance(value, dict) and all(
                    self.value_matches_type(key, args[0]) and self.value_matches_type(item, args[1])
                    for key, item in value.items()
                )
            return True

        declared = self.types.get(expected)
        if declared is not None:
            if declared.alias is not None:
                if isinstance(value, Variant) and value.name.startswith(expected + "."):
                    suffix = value.name[len(expected) + 1 :]
                    return self.value_matches_type(Variant(suffix, value.payload), declared.alias)
                return self.value_matches_type(value, declared.alias)
            if not isinstance(value, dict):
                return False
            for field, field_type in declared.fields.items():
                if field not in value or not self.value_matches_type(value[field], field_type):
                    return False
            return True

        if isinstance(value, Variant):
            return value.name == expected or value.name.endswith("." + expected) or value.name.startswith(expected + ".")
        return True


def truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (Decimal, int, float)):
        return value != 0
    if isinstance(value, Result):
        return value.ok
    return True


def add_values(left: Any, right: Any) -> Any:
    if isinstance(left, Money) and isinstance(right, Money):
        require_same_currency(left, right)
        return Money(left.amount + right.amount, left.currency)
    if isinstance(left, str) or isinstance(right, str):
        return format_value(left) + format_value(right)
    return left + right


def subtract_values(left: Any, right: Any) -> Any:
    if isinstance(left, Money) and isinstance(right, Money):
        require_same_currency(left, right)
        return Money(left.amount - right.amount, left.currency)
    return left - right


def multiply_values(left: Any, right: Any) -> Any:
    if isinstance(left, Money) and isinstance(right, Decimal):
        return Money(left.amount * right, left.currency)
    if isinstance(right, Money) and isinstance(left, Decimal):
        return Money(right.amount * left, right.currency)
    return left * right


def divide_values(left: Any, right: Any) -> Any:
    if isinstance(left, Money) and isinstance(right, Decimal):
        return Money(left.amount / right, left.currency)
    return left / right


def compare_values(left: Any, right: Any, op: str) -> bool:
    if isinstance(left, Money) and isinstance(right, Money):
        require_same_currency(left, right)
        left_value: Any = left.amount
        right_value: Any = right.amount
    else:
        left_value = left
        right_value = right

    if op == ">":
        return left_value > right_value
    if op == ">=":
        return left_value >= right_value
    if op == "<":
        return left_value < right_value
    if op == "<=":
        return left_value <= right_value
    raise MossRuntimeError(f"unknown comparison operator {op}")


def decimal_to_int(value: Any, context: str) -> int:
    if not isinstance(value, Decimal):
        raise MossRuntimeError(f"{context} must be a Number")
    integer = int(value)
    if value != integer:
        raise MossRuntimeError(f"{context} must be an integer Number")
    return integer


def require_text(value: Any, context: str) -> None:
    if not isinstance(value, str):
        raise MossRuntimeError(f"{context} expects Text")


def require_map(value: Any, context: str) -> None:
    if not isinstance(value, dict):
        raise MossRuntimeError(f"{context} expects Map")


def require_hashable(value: Any, context: str) -> None:
    try:
        hash(value)
    except TypeError as exc:
        raise MossRuntimeError(f"{context} must be hashable") from exc


def require_same_currency(left: Money, right: Money) -> None:
    if left.currency != right.currency:
        raise MossRuntimeError(f"currency mismatch: {left.currency} vs {right.currency}")


def match_pattern(pattern: Any, value: Any) -> dict[str, Any] | None:
    if isinstance(pattern, WildcardPattern):
        return {}
    if isinstance(pattern, BindingPattern):
        return {pattern.name: value}
    if isinstance(pattern, LiteralPattern):
        return {} if value == pattern.value else None
    if isinstance(pattern, VariantPattern):
        if isinstance(value, Result) and pattern.name in {"Ok", "Err"}:
            if (pattern.name == "Ok") != value.ok or len(pattern.payload) != 1:
                return None
            return match_pattern(pattern.payload[0], value.value)
        if not isinstance(value, Variant):
            return None
        if value.name != pattern.name and not value.name.endswith("." + pattern.name):
            return None
        if len(pattern.payload) != len(value.payload):
            return None
        bindings: dict[str, Any] = {}
        for child_pattern, child_value in zip(pattern.payload, value.payload):
            child_bindings = match_pattern(child_pattern, child_value)
            if child_bindings is None:
                return None
            for name, bound_value in child_bindings.items():
                if name in bindings and bindings[name] != bound_value:
                    return None
                bindings[name] = bound_value
        return bindings
    raise MossRuntimeError(f"unknown match pattern {type(pattern).__name__}")


def describe_value_type(value: Any) -> str:
    if isinstance(value, str):
        return "Text"
    if isinstance(value, bool):
        return "Bool"
    if isinstance(value, Decimal):
        return "Number"
    if isinstance(value, Money):
        return "Money"
    if isinstance(value, Result):
        return "Result"
    if isinstance(value, Variant):
        return value.name
    if isinstance(value, dict):
        return "record"
    if value is None:
        return "Null"
    return type(value).__name__


def parse_generic(type_text: str) -> tuple[str, list[str]] | None:
    if "<" not in type_text or not type_text.endswith(">"):
        return None
    name, rest = type_text.split("<", 1)
    args_text = rest[:-1]
    return name.strip(), [part.strip() for part in split_top_level(args_text, ",")]


def split_top_level(text: str, separator: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(text):
        if char == "<":
            depth += 1
        elif char == ">" and depth > 0:
            depth -= 1
        elif char == separator and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts
