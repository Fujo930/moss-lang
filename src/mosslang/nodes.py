from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .errors import SourceLocation


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
    location: SourceLocation | None = None


@dataclass(frozen=True)
class ImportDecl:
    path: str
    location: SourceLocation | None = None


@dataclass(frozen=True)
class TypeDecl:
    name: str
    fields: dict[str, str]
    alias: str | None = None
    location: SourceLocation | None = None


@dataclass(frozen=True)
class RuleDecl:
    name: str
    params: list[Param]
    return_type: str | None
    expr: Any
    location: SourceLocation | None = None


@dataclass(frozen=True)
class FunctionDecl:
    name: str
    params: list[Param]
    return_type: str | None
    uses: list[str]
    body: list[Any]
    location: SourceLocation | None = None


@dataclass(frozen=True)
class TestDecl:
    name: str
    body: list[Any]


@dataclass(frozen=True)
class PythonExternDecl:
    """extern \"python\" fn declaration. Calls a Python function at runtime."""
    name: str
    params: list[Param]
    return_type: str | None
    target: str  # fully-qualified Python callable, e.g. "math.sqrt"
    location: SourceLocation | None = None


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
class WhileStmt:
    condition: Any
    body: list[Any]


@dataclass(frozen=True)
class BreakStmt:
    pass


@dataclass(frozen=True)
class ContinueStmt:
    pass


@dataclass(frozen=True)
class ExprStmt:
    expr: Any


@dataclass(frozen=True)
class Literal:
    value: Any
    location: SourceLocation | None = None


@dataclass(frozen=True)
class NumberLiteral:
    value: Decimal
    location: SourceLocation | None = None


@dataclass(frozen=True)
class Identifier:
    name: str
    location: SourceLocation | None = None


@dataclass(frozen=True)
class RecordLiteral:
    fields: dict[str, Any]
    location: SourceLocation | None = None


@dataclass(frozen=True)
class ListLiteral:
    items: list[Any]
    location: SourceLocation | None = None


@dataclass(frozen=True)
class RecordUpdate:
    base: Any
    updates: dict[str, Any]
    location: SourceLocation | None = None


@dataclass(frozen=True)
class UnaryExpr:
    op: str
    right: Any
    location: SourceLocation | None = None


@dataclass(frozen=True)
class BinaryExpr:
    left: Any
    op: str
    right: Any
    location: SourceLocation | None = None


@dataclass(frozen=True)
class CallExpr:
    callee: Any
    args: list[Any]
    location: SourceLocation | None = None


@dataclass(frozen=True)
class FieldAccess:
    target: Any
    field: str
    location: SourceLocation | None = None


@dataclass(frozen=True)
class IndexAccess:
    target: Any
    index: Any
    location: SourceLocation | None = None


@dataclass(frozen=True)
class TryExpr:
    expr: Any
    location: SourceLocation | None = None


@dataclass(frozen=True)
class MatchCase:
    pattern: Any
    expr: Any


@dataclass(frozen=True)
class MatchExpr:
    subject: Any
    cases: list[MatchCase]
    location: SourceLocation | None = None


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

@dataclass
class LambdaExpr:
    """Anonymous function: \\params -> expr"""
    params: list[Param]
    expr: object
    location: SourceLocation | None = None

