from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Param:
    name: str
    type_name: str | None = None


@dataclass(frozen=True)
class Program:
    items: list[Any]


@dataclass(frozen=True)
class EffectDecl:
    names: list[str]


@dataclass(frozen=True)
class TypeDecl:
    name: str
    fields: dict[str, str]
    alias: str | None = None


@dataclass(frozen=True)
class RuleDecl:
    name: str
    params: list[Param]
    return_type: str | None
    expr: Any


@dataclass(frozen=True)
class FunctionDecl:
    name: str
    params: list[Param]
    return_type: str | None
    uses: list[str]
    body: list[Any]


@dataclass(frozen=True)
class TestDecl:
    name: str
    body: list[Any]


@dataclass(frozen=True)
class LetStmt:
    name: str
    expr: Any


@dataclass(frozen=True)
class AssignStmt:
    name: str
    expr: Any


@dataclass(frozen=True)
class ReturnStmt:
    expr: Any


@dataclass(frozen=True)
class RequireStmt:
    condition: Any
    else_expr: Any


@dataclass(frozen=True)
class IfStmt:
    condition: Any
    then_body: list[Any]
    else_body: list[Any]


@dataclass(frozen=True)
class ForStmt:
    name: str
    iterable: Any
    body: list[Any]


@dataclass(frozen=True)
class ExprStmt:
    expr: Any


@dataclass(frozen=True)
class Literal:
    value: Any


@dataclass(frozen=True)
class NumberLiteral:
    value: Decimal


@dataclass(frozen=True)
class Identifier:
    name: str


@dataclass(frozen=True)
class RecordLiteral:
    fields: dict[str, Any]


@dataclass(frozen=True)
class ListLiteral:
    items: list[Any]


@dataclass(frozen=True)
class RecordUpdate:
    base: Any
    updates: dict[str, Any]


@dataclass(frozen=True)
class UnaryExpr:
    op: str
    right: Any


@dataclass(frozen=True)
class BinaryExpr:
    left: Any
    op: str
    right: Any


@dataclass(frozen=True)
class CallExpr:
    callee: Any
    args: list[Any]


@dataclass(frozen=True)
class FieldAccess:
    target: Any
    field: str


@dataclass(frozen=True)
class IndexAccess:
    target: Any
    index: Any


@dataclass(frozen=True)
class TryExpr:
    expr: Any


@dataclass(frozen=True)
class MatchCase:
    pattern: Any
    expr: Any


@dataclass(frozen=True)
class MatchExpr:
    subject: Any
    cases: list[MatchCase]


@dataclass(frozen=True)
class WildcardPattern:
    pass


@dataclass(frozen=True)
class BindingPattern:
    name: str


@dataclass(frozen=True)
class LiteralPattern:
    value: Any


@dataclass(frozen=True)
class VariantPattern:
    name: str
    payload: list[Any]
