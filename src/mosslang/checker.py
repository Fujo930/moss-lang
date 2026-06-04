from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .nodes import (
    BinaryExpr,
    CallExpr,
    EffectDecl,
    AssignStmt,
    ExprStmt,
    FieldAccess,
    FunctionDecl,
    Identifier,
    IfStmt,
    LetStmt,
    MatchExpr,
    Program,
    RecordLiteral,
    RecordUpdate,
    RequireStmt,
    ReturnStmt,
    RuleDecl,
    TryExpr,
    TypeDecl,
    UnaryExpr,
)


@dataclass(frozen=True)
class Diagnostic:
    level: str
    message: str


BUILTIN_EFFECTS = {
    "dbPut": "Database",
    "dbGet": "Database",
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
                    diagnostics.append(Diagnostic("warning", f"duplicate effect '{name}'"))
                effects.add(name)
        elif isinstance(item, TypeDecl):
            if item.name in types:
                diagnostics.append(Diagnostic("error", f"duplicate type '{item.name}'"))
            types.add(item.name)
        elif isinstance(item, (FunctionDecl, RuleDecl)):
            if item.name in functions:
                diagnostics.append(Diagnostic("error", f"duplicate callable '{item.name}'"))
            functions[item.name] = item

    for item in program.items:
        if isinstance(item, FunctionDecl):
            for effect in item.uses:
                if effect not in effects:
                    diagnostics.append(Diagnostic("error", f"{item.name} uses undeclared effect '{effect}'"))
            check_effect_calls(item, functions, diagnostics)

    return diagnostics


def check_effect_calls(
    function: FunctionDecl,
    functions: dict[str, FunctionDecl | RuleDecl],
    diagnostics: list[Diagnostic],
) -> None:
    allowed = set(function.uses)
    for call_name in collect_call_names(function.body):
        if call_name in BUILTIN_EFFECTS and BUILTIN_EFFECTS[call_name] not in allowed:
            effect = BUILTIN_EFFECTS[call_name]
            diagnostics.append(Diagnostic("error", f"{function.name} calls {call_name} but does not declare uses {effect}"))
        callee = functions.get(call_name)
        if isinstance(callee, FunctionDecl):
            missing = [effect for effect in callee.uses if effect not in allowed]
            if missing:
                joined = ", ".join(missing)
                diagnostics.append(Diagnostic("error", f"{function.name} calls {call_name} but is missing effect(s): {joined}"))


def collect_call_names(nodes: list[Any]) -> list[str]:
    names: list[str] = []
    for node in nodes:
        names.extend(collect_expr_calls(node))
        if isinstance(node, IfStmt):
            names.extend(collect_call_names(node.then_body))
            names.extend(collect_call_names(node.else_body))
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
    elif isinstance(node, TryExpr):
        names.extend(collect_expr_calls(node.expr))
    elif isinstance(node, MatchExpr):
        names.extend(collect_expr_calls(node.subject))
        for case in node.cases:
            names.extend(collect_expr_calls(case.expr))
    elif isinstance(node, RecordLiteral):
        for value in node.fields.values():
            names.extend(collect_expr_calls(value))
    elif isinstance(node, RecordUpdate):
        names.extend(collect_expr_calls(node.base))
        for value in node.updates.values():
            names.extend(collect_expr_calls(value))
    elif isinstance(node, IfStmt):
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
