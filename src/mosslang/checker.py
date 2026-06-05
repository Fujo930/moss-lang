from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import SourceLocation
from .nodes import (
    BinaryExpr,
    BindingPattern,
    CallExpr,
    EffectDecl,
    AssignStmt,
    ExprStmt,
    FieldAccess,
    ForStmt,
    FunctionDecl,
    Identifier,
    IfStmt,
    IndexAccess,
    LetStmt,
    WhileStmt,
    ListLiteral,
    MatchExpr,
    Literal,
    NumberLiteral,
    Program,
    RecordLiteral,
    RecordUpdate,
    RequireStmt,
    ReturnStmt,
    RuleDecl,
    TryExpr,
    TypeDecl,
    UnaryExpr,
    VariantPattern,
    WildcardPattern,
)


@dataclass(frozen=True)
class Diagnostic:
    level: str
    message: str
    location: SourceLocation | None = None

    def format(self) -> str:
        prefix = f"{self.location.format()}: " if self.location is not None else ""
        return f"{self.level}: {prefix}{self.message}"


BUILTIN_EFFECTS = {
    "dbPut": "Database",
    "dbGet": "Database",
    "readText": "FileSystem",
    "writeText": "FileSystem",
    "fileExists": "FileSystem",
    "listFiles": "FileSystem",
}


def check_program(program: Program) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    effects: set[str] = set()
    functions: dict[str, FunctionDecl | RuleDecl] = {}
    types: set[str] = set()

    for item in program.items:
        if isinstance(item, EffectDecl):
            for name in item.names:
                if name in effects:
                    diagnostics.append(Diagnostic("warning", f"duplicate effect '{name}'", item.location))
                effects.add(name)
        elif isinstance(item, TypeDecl):
            if item.name in types:
                diagnostics.append(Diagnostic("error", f"duplicate type '{item.name}'", item.location))
            types.add(item.name)
        elif isinstance(item, (FunctionDecl, RuleDecl)):
            if item.name in functions:
                diagnostics.append(Diagnostic("error", f"duplicate callable '{item.name}'", item.location))
            functions[item.name] = item

    for item in program.items:
        if isinstance(item, FunctionDecl):
            for effect in item.uses:
                if effect not in effects:
                    diagnostics.append(Diagnostic("error", f"{item.name} uses undeclared effect '{effect}'", item.location))
            check_effect_calls(item, functions, diagnostics)

    check_static_types(program, functions, diagnostics)
    return diagnostics


BUILTIN_RETURN_TYPES = {
    "len": "Number",
    "textTrim": "Text",
    "textSlice": "Text",
    "textJoin": "Text",
    "textReplace": "Text",
    "textIndexOf": "Number",
    "textContains": "Bool",
    "textStartsWith": "Bool",
    "textEndsWith": "Bool",
    "fileExists": "Bool",
    "readText": "Text",
}


def check_static_types(
    program: Program,
    functions: dict[str, FunctionDecl | RuleDecl],
    diagnostics: list[Diagnostic],
) -> None:
    types = {item.name: item for item in program.items if isinstance(item, TypeDecl)}
    globals_env: dict[str, str] = {}

    for item in program.items:
        if isinstance(item, LetStmt):
            globals_env[item.name] = infer_expr_type(item.expr, globals_env, functions, types, diagnostics, None)

    for item in program.items:
        if not isinstance(item, FunctionDecl):
            if isinstance(item, RuleDecl):
                env = dict(globals_env)
                env.update({param.name: param.type_name or "Unknown" for param in item.params})
                actual = infer_expr_type(item.expr, env, functions, types, diagnostics, item.location)
                report_mismatch(item.return_type or "Unknown", actual, f"return from {item.name}", diagnostics, item.location)
            continue
        env = dict(globals_env)
        env.update({param.name: param.type_name or "Unknown" for param in item.params})
        check_statement_types(item.body, env, functions, types, diagnostics, item)


def check_statement_types(
    statements: list[Any],
    env: dict[str, str],
    functions: dict[str, FunctionDecl | RuleDecl],
    types: dict[str, TypeDecl],
    diagnostics: list[Diagnostic],
    function: FunctionDecl,
) -> None:
    for statement in statements:
        if isinstance(statement, LetStmt):
            env[statement.name] = infer_expr_type(statement.expr, env, functions, types, diagnostics, function.location)
        elif isinstance(statement, AssignStmt):
            actual = infer_expr_type(statement.expr, env, functions, types, diagnostics, function.location)
            expected = env.get(statement.name, "Unknown")
            if expected not in {"Unknown", "Null"}:
                report_mismatch(expected, actual, f"assignment to {statement.name}", diagnostics, function.location)
            if expected in {"Unknown", "Null"}:
                env[statement.name] = actual
        elif isinstance(statement, ReturnStmt):
            actual = infer_expr_type(statement.expr, env, functions, types, diagnostics, function.location)
            report_mismatch(function.return_type or "Unknown", actual, f"return from {function.name}", diagnostics, function.location)
        elif isinstance(statement, ExprStmt):
            infer_expr_type(statement.expr, env, functions, types, diagnostics, function.location)
        elif isinstance(statement, RequireStmt):
            infer_expr_type(statement.condition, env, functions, types, diagnostics, function.location)
            infer_expr_type(statement.else_expr, env, functions, types, diagnostics, function.location)
        elif isinstance(statement, IfStmt):
            infer_expr_type(statement.condition, env, functions, types, diagnostics, function.location)
            then_env = dict(env)
            else_env = dict(env)
            check_statement_types(statement.then_body, then_env, functions, types, diagnostics, function)
            check_statement_types(statement.else_body, else_env, functions, types, diagnostics, function)
            if statement.else_body:
                for name in set(then_env) & set(else_env):
                    if then_env[name] == else_env[name]:
                        env[name] = then_env[name]
        elif isinstance(statement, ForStmt):
            iterable = infer_expr_type(statement.iterable, env, functions, types, diagnostics, function.location)
            loop_env = dict(env)
            loop_env[statement.name] = generic_argument(iterable, "List") or "Unknown"
            check_statement_types(statement.body, loop_env, functions, types, diagnostics, function)
        elif isinstance(statement, WhileStmt):
            infer_expr_type(statement.condition, env, functions, types, diagnostics, function.location)
            check_statement_types(statement.body, dict(env), functions, types, diagnostics, function)


def infer_expr_type(
    expr: Any,
    env: dict[str, str],
    functions: dict[str, FunctionDecl | RuleDecl],
    types: dict[str, TypeDecl],
    diagnostics: list[Diagnostic],
    location: SourceLocation | None,
) -> str:
    location = getattr(expr, "location", None) or location
    if isinstance(expr, Literal):
        if isinstance(expr.value, bool):
            return "Bool"
        if isinstance(expr.value, str):
            return "Text"
        if expr.value is None:
            return "Null"
    if isinstance(expr, NumberLiteral):
        return "Number"
    if isinstance(expr, Identifier):
        return env.get(expr.name, variant_owner(expr.name, types) or "Unknown")
    if isinstance(expr, ListLiteral):
        item_types = {infer_expr_type(item, env, functions, types, diagnostics, location) for item in expr.items}
        known = {item for item in item_types if item != "Unknown"}
        return f"List<{known.pop()}>" if len(known) == 1 else "List<Any>"
    if isinstance(expr, RecordLiteral):
        fields = {name: infer_expr_type(value, env, functions, types, diagnostics, location) for name, value in expr.fields.items()}
        matches = [
            declaration.name
            for declaration in types.values()
            if declaration.fields and set(declaration.fields) == set(fields)
            and all(types_compatible(declaration.fields[name], fields[name]) for name in fields)
        ]
        return matches[0] if len(matches) == 1 else "Record"
    if isinstance(expr, RecordUpdate):
        base = infer_expr_type(expr.base, env, functions, types, diagnostics, location)
        declaration = types.get(base)
        if declaration is not None:
            for field, value in expr.updates.items():
                if field not in declaration.fields:
                    diagnostics.append(Diagnostic("error", f"{base} has no field '{field}'", location))
                else:
                    actual = infer_expr_type(value, env, functions, types, diagnostics, location)
                    report_mismatch(declaration.fields[field], actual, f"{base}.{field}", diagnostics, location)
        return base
    if isinstance(expr, FieldAccess):
        target = infer_expr_type(expr.target, env, functions, types, diagnostics, location)
        if target == "Number" and len(expr.field) == 3:
            return "Money"
        declaration = types.get(target)
        if declaration is not None:
            if expr.field not in declaration.fields:
                diagnostics.append(Diagnostic("error", f"{target} has no field '{expr.field}'", location))
                return "Unknown"
            return declaration.fields[expr.field]
        return "Unknown"
    if isinstance(expr, IndexAccess):
        target = infer_expr_type(expr.target, env, functions, types, diagnostics, location)
        infer_expr_type(expr.index, env, functions, types, diagnostics, location)
        return generic_argument(target, "List") or "Unknown"
    if isinstance(expr, CallExpr):
        name = dotted_name(expr.callee)
        arg_types = [infer_expr_type(arg, env, functions, types, diagnostics, location) for arg in expr.args]
        if name == "range":
            return "List<Number>"
        if name in {"listPush", "listSet", "listSlice", "listInsert", "listRemove"} and arg_types:
            if name == "listPush" and arg_types[0] == "List<Any>" and len(arg_types) > 1:
                return f"List<{arg_types[1]}>"
            return arg_types[0]
        if name == "listConcat" and arg_types:
            return arg_types[0]
        if name in BUILTIN_RETURN_TYPES:
            return BUILTIN_RETURN_TYPES[name]
        declaration = functions.get(name or "")
        if declaration is not None:
            for param, actual in zip(declaration.params, arg_types):
                report_mismatch(param.type_name or "Unknown", actual, f"argument {param.name} to {declaration.name}", diagnostics, location)
            return declaration.return_type or "Unknown"
        return "Unknown"
    if isinstance(expr, BinaryExpr):
        left = infer_expr_type(expr.left, env, functions, types, diagnostics, location)
        right = infer_expr_type(expr.right, env, functions, types, diagnostics, location)
        if expr.op in {"==", "!=", ">", ">=", "<", "<=", "and", "or"}:
            return "Bool"
        return left if left == right else "Unknown"
    if isinstance(expr, UnaryExpr):
        return "Bool" if expr.op == "not" else infer_expr_type(expr.right, env, functions, types, diagnostics, location)
    if isinstance(expr, TryExpr):
        return generic_argument(infer_expr_type(expr.expr, env, functions, types, diagnostics, location), "Result") or "Unknown"
    if isinstance(expr, MatchExpr):
        subject_type = infer_expr_type(expr.subject, env, functions, types, diagnostics, location)
        check_match_coverage(expr, subject_type, types, diagnostics, location)
        results = {infer_expr_type(case.expr, env, functions, types, diagnostics, location) for case in expr.cases}
        known = {item for item in results if item != "Unknown"}
        return known.pop() if len(known) == 1 else "Unknown"
    return "Unknown"


def report_mismatch(
    expected: str,
    actual: str,
    context: str,
    diagnostics: list[Diagnostic],
    location: SourceLocation | None,
) -> None:
    if not types_compatible(expected, actual):
        diagnostics.append(Diagnostic("error", f"type mismatch for {context}: expected {expected}, got {actual}", location))


def types_compatible(expected: str, actual: str) -> bool:
    if expected in {"Any", "Unknown"} or actual in {"Any", "Unknown"}:
        return True
    if "|" in expected:
        return any(types_compatible(part.strip(), actual) for part in expected.split("|"))
    expected_list = generic_argument(expected, "List")
    actual_list = generic_argument(actual, "List")
    if expected_list is not None and actual_list is not None:
        return types_compatible(expected_list, actual_list)
    return expected == actual


def generic_argument(type_name: str, container: str) -> str | None:
    prefix = container + "<"
    if not type_name.startswith(prefix) or not type_name.endswith(">"):
        return None
    return type_name[len(prefix) : -1].split(",", 1)[0].strip()


def variant_owner(name: str, types: dict[str, TypeDecl]) -> str | None:
    matches = [
        declaration.name
        for declaration in types.values()
        if declaration.alias and name in {part.strip() for part in declaration.alias.split("|")}
    ]
    return matches[0] if len(matches) == 1 else None


def check_match_coverage(
    expr: MatchExpr,
    subject_type: str,
    types: dict[str, TypeDecl],
    diagnostics: list[Diagnostic],
    location: SourceLocation | None,
) -> None:
    declaration = types.get(subject_type)
    union_text = declaration.alias if declaration is not None else subject_type if "|" in subject_type else None
    if not union_text:
        return

    variants = union_variants(union_text)
    expected = set(variants)
    covered: set[str] = set()
    catches_all = False
    for case in expr.cases:
        pattern = case.pattern
        if catches_all:
            diagnostics.append(Diagnostic("warning", "unreachable match case after catch-all", location))
            continue
        if isinstance(pattern, (WildcardPattern, BindingPattern)):
            catches_all = True
            continue
        if isinstance(pattern, VariantPattern):
            name = pattern.name.split(".")[-1]
            if name not in expected:
                diagnostics.append(Diagnostic("error", f"variant '{name}' is not part of {subject_type}", location))
                continue
            expected_arity = variants[name]
            if expected_arity is not None and len(pattern.payload) != expected_arity:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        f"variant '{name}' expects {expected_arity} payload pattern(s), got {len(pattern.payload)}",
                        location,
                    )
                )
            if name in covered:
                diagnostics.append(Diagnostic("warning", f"duplicate match case '{name}'", location))
            covered.add(name)

    missing = sorted(expected - covered)
    if missing and not catches_all:
        diagnostics.append(Diagnostic("error", f"non-exhaustive match for {subject_type}; missing: {', '.join(missing)}", location))


def union_variants(union_text: str) -> dict[str, int | None]:
    """Return variant names and declared payload arity; None means unspecified."""
    result: dict[str, int | None] = {}
    for part in split_top_level(union_text, "|"):
        member = part.strip()
        if "(" not in member or not member.endswith(")"):
            result[member] = None
            continue
        name, payload = member.split("(", 1)
        content = payload[:-1].strip()
        result[name.strip()] = 0 if not content else len(split_top_level(content, ","))
    return result


def split_top_level(text: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(text):
        if char in "(<[":
            depth += 1
        elif char in ")>]":
            depth = max(0, depth - 1)
        elif char == delimiter and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts


def check_effect_calls(
    function: FunctionDecl,
    functions: dict[str, FunctionDecl | RuleDecl],
    diagnostics: list[Diagnostic],
) -> None:
    allowed = set(function.uses)
    for call_name in collect_call_names(function.body):
        if call_name in BUILTIN_EFFECTS and BUILTIN_EFFECTS[call_name] not in allowed:
            effect = BUILTIN_EFFECTS[call_name]
            diagnostics.append(
                Diagnostic("error", f"{function.name} calls {call_name} but does not declare uses {effect}", function.location)
            )
        callee = functions.get(call_name)
        if isinstance(callee, FunctionDecl):
            missing = [effect for effect in callee.uses if effect not in allowed]
            if missing:
                joined = ", ".join(missing)
                diagnostics.append(
                    Diagnostic("error", f"{function.name} calls {call_name} but is missing effect(s): {joined}", function.location)
                )


def collect_call_names(nodes: list[Any]) -> list[str]:
    names: list[str] = []
    for node in nodes:
        names.extend(collect_expr_calls(node))
        if isinstance(node, IfStmt):
            names.extend(collect_call_names(node.then_body))
            names.extend(collect_call_names(node.else_body))
        if isinstance(node, ForStmt):
            names.extend(collect_call_names(node.body))
        if isinstance(node, WhileStmt):
            names.extend(collect_call_names(node.body))
    return names


def collect_expr_calls(node: Any) -> list[str]:
    names: list[str] = []

    if isinstance(node, (LetStmt, ReturnStmt, ExprStmt, AssignStmt)):
        names.extend(collect_expr_calls(node.expr))
    elif isinstance(node, RequireStmt):
        names.extend(collect_expr_calls(node.condition))
        names.extend(collect_expr_calls(node.else_expr))
    elif isinstance(node, CallExpr):
        call_name = dotted_name(node.callee)
        if call_name is not None:
            names.append(call_name)
        names.extend(collect_expr_calls(node.callee))
        for arg in node.args:
            names.extend(collect_expr_calls(arg))
    elif isinstance(node, BinaryExpr):
        names.extend(collect_expr_calls(node.left))
        names.extend(collect_expr_calls(node.right))
    elif isinstance(node, UnaryExpr):
        names.extend(collect_expr_calls(node.right))
    elif isinstance(node, FieldAccess):
        names.extend(collect_expr_calls(node.target))
    elif isinstance(node, IndexAccess):
        names.extend(collect_expr_calls(node.target))
        names.extend(collect_expr_calls(node.index))
    elif isinstance(node, TryExpr):
        names.extend(collect_expr_calls(node.expr))
    elif isinstance(node, MatchExpr):
        names.extend(collect_expr_calls(node.subject))
        for case in node.cases:
            names.extend(collect_expr_calls(case.expr))
    elif isinstance(node, ListLiteral):
        for item in node.items:
            names.extend(collect_expr_calls(item))
    elif isinstance(node, RecordLiteral):
        for value in node.fields.values():
            names.extend(collect_expr_calls(value))
    elif isinstance(node, RecordUpdate):
        names.extend(collect_expr_calls(node.base))
        for value in node.updates.values():
            names.extend(collect_expr_calls(value))
    elif isinstance(node, IfStmt):
        names.extend(collect_expr_calls(node.condition))
    elif isinstance(node, ForStmt):
        names.extend(collect_expr_calls(node.iterable))
    elif isinstance(node, WhileStmt):
        names.extend(collect_expr_calls(node.condition))
    return names


def dotted_name(node: Any) -> str | None:
    if isinstance(node, Identifier):
        return node.name
    if isinstance(node, FieldAccess):
        prefix = dotted_name(node.target)
        if prefix is None:
            return None
        return f"{prefix}.{node.field}"
    return None
