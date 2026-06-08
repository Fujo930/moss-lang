"""Moss self-host frontend bridge.

Loads the Moss-written lexer, parser, and checker from examples/self_host/
and exposes them as callable functions that return Python objects.

The self-host modules are loaded via the bytecode VM and called through
VM.call().  Returned Moss values (dicts, lists, strings) are translated
into idiomatic Python types.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from .parser import parse_source as _parse_source
from .compiler import compile_program as _compile_program
from .vm import VM
from .tokens import Token
from . import nodes as n


def _find_selfhost_root() -> Path:
    """Return the root directory containing the self_host examples."""
    return Path(__file__).resolve().parents[2] / "examples" / "self_host"


# ── MossNode dict → Python AST converter ──

def _moss_expr_to_ast(ex: dict | None) -> Any:
    """Convert a Moss expression dict to a Python AST node."""
    if ex is None:
        return n.Literal(None)
    kind = ex.get("kind", "")
    val = ex.get("value", "")
    left = ex.get("left")
    right = ex.get("right")

    if kind == "Identifier":
        return n.Identifier(val)
    if kind == "Text":
        return n.Literal(val)
    if kind == "Number":
        return n.NumberLiteral(Decimal(val))
    if kind == "Bool":
        return n.Literal(val == "true")
    if kind in ("Binary",):
        return n.BinaryExpr(
            left=_moss_expr_to_ast(left),
            op=val,
            right=_moss_expr_to_ast(right),
        )
    if kind == "Unary":
        op = val if val else "not"
        return n.UnaryExpr(op=op, right=_moss_expr_to_ast(right))
    if kind == "Call":
        args = [_moss_expr_to_ast(a) for a in (right if isinstance(right, list) else [])]
        return n.CallExpr(callee=_moss_expr_to_ast(left), args=args)
    if kind == "Field":
        return n.FieldAccess(target=_moss_expr_to_ast(left), field=val)
    if kind == "Index":
        return n.IndexAccess(target=_moss_expr_to_ast(left), index=_moss_expr_to_ast(right))
    if kind == "Try":
        return n.TryExpr(expr=_moss_expr_to_ast(left))
    if kind == "Record":
        fields = {}
        if isinstance(right, dict):
            for k, v in right.items():
                fields[k] = _moss_expr_to_ast(v)
        return n.RecordLiteral(fields=fields)
    if kind == "RecordUpdate":
        updates = {}
        if isinstance(right, dict):
            for k, v in right.items():
                updates[k] = _moss_expr_to_ast(v)
        return n.RecordUpdate(base=_moss_expr_to_ast(left), updates=updates)
    if kind == "List":
        items = [_moss_expr_to_ast(a) for a in (right if isinstance(right, list) else [])]
        return n.ListLiteral(items=items)
    if kind == "Match":
        cases = []
        raw_cases = right if isinstance(right, list) else []
        for c in raw_cases:
            if isinstance(c, dict):
                pattern_raw = c.get("pattern", c.get("left"))
                body_raw = c.get("body", c.get("right", c.get("value")))
                pattern = _moss_pattern_to_ast(pattern_raw)
                body = _moss_expr_to_ast(body_raw)
                cases.append(n.MatchCase(pattern=pattern, body=body))
        return n.MatchExpr(subject=_moss_expr_to_ast(left), cases=cases)
    if kind == "PatternVariant":
        name = val or (left.get("value") if isinstance(left, dict) else "")
        payload_patterns = [_moss_pattern_to_ast(p) for p in (right if isinstance(right, list) else [])]
        if payload_patterns:
            return n.VariantPattern(name=name, payload=payload_patterns)
        return n.VariantPattern(name=name)
    # Default: return expression dict as literal (for unsupported kinds during development)
    return n.Literal(f"<{kind}>")


def _moss_pattern_to_ast(pt: dict | None) -> Any:
    """Convert a Moss pattern dict to a Python AST pattern node."""
    if pt is None:
        return n.WildcardPattern()
    kind = pt.get("kind", "")
    val = pt.get("value", "")
    left = pt.get("left")
    right = pt.get("right")

    if kind == "PatternWildcard" or kind == "Wildcard":
        return n.WildcardPattern()
    if kind == "PatternBinding":
        return n.BindingPattern(name=val)
    if kind == "PatternLiteral" or kind == "Text":
        return n.LiteralPattern(value=val)
    if kind == "PatternVariant":
        name = val or (left.get("value") if isinstance(left, dict) else "")
        payload = [_moss_pattern_to_ast(p) for p in (right if isinstance(right, list) else [])]
        if payload:
            return n.VariantPattern(name=name, payload=payload)
        return n.VariantPattern(name=name)
    return n.WildcardPattern()


def _moss_stmt_to_ast(stmt: dict) -> Any:
    """Convert a Moss statement dict to a Python AST statement node."""
    kind = stmt.get("kind", "")
    name = stmt.get("name", "")
    val = stmt.get("value")

    if kind == "Expr":
        return n.ExprStmt(expr=_moss_expr_to_ast(val))
    if kind == "Let":
        expr = _moss_expr_to_ast(val)
        # 'val' could be the data dict directly for Let nodes from parser
        if isinstance(val, dict):
            expr = _moss_expr_to_ast(val)
        return n.LetStmt(name=name, expr=expr)
    if kind == "Assign":
        return n.AssignStmt(name=name, expr=_moss_expr_to_ast(val))
    if kind == "Return":
        return n.ReturnStmt(expr=_moss_expr_to_ast(val))
    if kind == "Require":
        if isinstance(val, dict):
            return n.RequireStmt(
                condition=_moss_expr_to_ast(val.get("condition")),
                else_expr=_moss_expr_to_ast(val.get("error")),
            )
        return n.ExprStmt(expr=n.Literal(None))
    if kind == "If":
        if isinstance(val, dict):
            # New format: {expression, then_body, else_body} or old: {condition, then, else}
            condition = _moss_expr_to_ast(val.get("expression") or val.get("condition"))
            then_list = val.get("then_body") or val.get("then") or []
            then_body = [_moss_stmt_to_ast(s) for s in then_list]
            else_list = val.get("else_body") or val.get("else") or []
            else_body = [_moss_stmt_to_ast(s) for s in else_list]
            return n.IfStmt(condition=condition, then_body=then_body, else_body=else_body)
        return n.ExprStmt(expr=n.Literal(None))
    if kind == "For":
        if isinstance(val, dict):
            # New format: {expression, body} or old: {iterable, body}
            iterable = _moss_expr_to_ast(val.get("expression") or val.get("iterable"))
            body_list = val.get("body") or []
            body = [_moss_stmt_to_ast(s) for s in body_list]
            return n.ForStmt(name=name, iterable=iterable, body=body)
        return n.ExprStmt(expr=n.Literal(None))
    if kind == "While":
        if isinstance(val, dict):
            # New format: {expression, body} or old: {condition, body}
            condition = _moss_expr_to_ast(val.get("expression") or val.get("condition"))
            body_list = val.get("body") or []
            body = [_moss_stmt_to_ast(s) for s in body_list]
            return n.WhileStmt(condition=condition, body=body)
        return n.ExprStmt(expr=n.Literal(None))
    if kind in ("Break",):
        return n.BreakStmt()
    if kind in ("Continue",):
        return n.ContinueStmt()
    # Fallback
    return n.ExprStmt(expr=n.Literal(None))


def _parse_params_from_value(value: str) -> list[n.Param]:
    """Parse ( name: Type, name: Type ) → list of Param from a value string."""
    params: list[n.Param] = []
    if not value.startswith("("):
        return params
    inner = value.split(")", 1)[0][1:]
    if not inner.strip():
        return params
    for part in inner.split(","):
        part = part.strip()
        if ":" in part:
            pname, ptype = part.split(":", 1)
            params.append(n.Param(name=pname.strip(), type_name=ptype.strip()))
        else:
            params.append(n.Param(name=part.strip()))
    return params


def _parse_return_type(value: str) -> str | None:
    """Extract return type from value string like '(params) -> Type ...'

    Handles generic types with optional spaces like 'Result < Order , ShipError >'.
    """
    if "->" not in value:
        return None
    after = value.split("->", 1)[1].strip()
    if after.startswith("{"):
        return None
    # Collect until we hit 'uses', '{', or end
    end = len(after)
    for kw in (" uses ", "{"):
        idx = after.find(kw)
        if idx != -1 and idx < end:
            end = idx
    ret = after[:end].strip()
    # Strip trailing '=' (rule body marker)
    ret = ret.rstrip("=").strip()
    # Remove excess spaces inside <...>
    import re
    ret = re.sub(r'\s*<\s*', '<', ret)
    ret = re.sub(r'\s*>\s*', '>', ret)
    ret = re.sub(r'\s*,\s*', ', ', ret)
    return ret if ret else None


def _parse_uses(value: str) -> list[str]:
    """Extract effect names from '... uses Effect1, Effect2'."""
    if "uses" not in value:
        return []
    after = value.split("uses", 1)[1].strip()
    # Remove trailing { if present
    after = after.rstrip("{").strip()
    return [e.strip() for e in after.split(",") if e.strip()]


def _parse_type_fields(value: str) -> dict[str, str]:
    """Parse 'id:Text;status:Pending|Paid;total:Money' → dict."""
    fields: dict[str, str] = {}
    if not value or ":" not in value:
        return fields
    for part in value.split(";"):
        part = part.strip()
        if ":" in part:
            k, v = part.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields


def moss_nodes_to_program(nodes: list[dict], source: str = "") -> n.Program:
    """Convert MossNode dicts from the selfhost parser to a Python Program AST.
    
    The selfhost parser renders some declarations as two nodes: one for the
    declaration header (Rule/Function) and a following Expr/Let/etc. for the
    body.  This function consolidates them.
    """
    items: list[Any] = []
    i = 0
    while i < len(nodes):
        node = nodes[i]
        kind = node.get("kind", "")
        name = node.get("name", "")
        value = node.get("value", "")
        data = node.get("data")

        if kind == "Effect":
            names_list = [v.strip() for v in value.split(",") if v.strip()]
            items.append(n.EffectDecl(names=names_list))
            i += 1

        elif kind == "Import":
            items.append(n.ImportDecl(path=name or value))
            i += 1

        elif kind == "Type":
            if value.startswith("="):
                items.append(n.TypeDecl(name=name, fields={}, alias=value[1:].strip()))
            else:
                items.append(n.TypeDecl(name=name, fields=_parse_type_fields(value)))
            i += 1

        elif kind == "Rule":
            params = _parse_params_from_value(value)
            ret_type = _parse_return_type(value)
            expr = n.Literal(None)
            if isinstance(data, dict) and data.get("kind") and data.get("kind") != "None":
                expr = _moss_expr_to_ast(data)
            elif i + 1 < len(nodes) and nodes[i + 1].get("kind") == "Expr":
                next_data = nodes[i + 1].get("data")
                if isinstance(next_data, dict):
                    expr = _moss_expr_to_ast(next_data)
                i += 1
            if isinstance(expr, n.Literal) and expr.value is None and source:
                # Fall back: re-parse the full rule declaration through the host parser
                import re
                # Extract the rule text: 'rule name(...) = body_expression'
                pattern = rf'\brule\s+{re.escape(name)}\b[^\n]*=[^\n]*'
                found = re.search(pattern, source)
                if found:
                    rule_start = found.start()
                    # Find end of rule body: next top-level declaration or EOF
                    rest = source[found.end():]
                    end_match = re.search(r'\n\s*\b(?:effect|type|rule|fn|test|import)\b', rest)
                    if end_match:
                        rule_text = source[rule_start:found.end() + end_match.start()].strip()
                    else:
                        rule_text = source[rule_start:].strip()
                    try:
                        from .parser import parse_source as _ps
                        rule_prog = _ps(rule_text + '\n')
                        for rule_item in rule_prog.items:
                            if isinstance(rule_item, n.RuleDecl) and rule_item.name == name:
                                expr = rule_item.expr
                                break
                    except Exception:
                        pass
            items.append(n.RuleDecl(name=name, params=params, return_type=ret_type, expr=expr))
            i += 1

        elif kind == "Function":
            params = _parse_params_from_value(value)
            ret_type = _parse_return_type(value)
            uses = _parse_uses(value)
            body: list[Any] = []
            if isinstance(data, list):
                body = [_moss_stmt_to_ast(s) for s in data]
            items.append(n.FunctionDecl(
                name=name, params=params, return_type=ret_type,
                uses=uses, body=body,
            ))
            i += 1

        elif kind == "Test":
            body: list[Any] = []
            if isinstance(data, list):
                body = [_moss_stmt_to_ast(s) for s in data]
            items.append(n.TestDecl(name=name, body=body))
            i += 1

        elif kind == "Let":
            expr = _moss_expr_to_ast(data) if isinstance(data, dict) else n.Literal(None)
            items.append(n.LetStmt(name=name, expr=expr))
            i += 1

        elif kind == "Expr":
            expr = _moss_expr_to_ast(data) if isinstance(data, dict) else n.Literal(None)
            items.append(n.ExprStmt(expr=expr))
            i += 1

        else:
            i += 1

    return n.Program(items=items)


class SelfHostFrontend:
    """Bridge to Moss-written lexer, parser, checker, and compiler."""

    def __init__(self, root: Path | None = None):
        self._root = root or _find_selfhost_root()
        self._vm: VM | None = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        vm = VM(base_path=self._root.parent)
        importer = (
            f'import "examples/self_host/parser_core.moss"\n'
            f'import "examples/self_host/checker_core.moss"\n'
        )
        mod = _compile_program(_parse_source(importer), source_path=str(self._root / "parser_core.moss"))
        vm.load_module(mod)
        vm.run()
        self._vm = vm
        self._loaded = True

    def tokenize(self, source: str) -> list[Token]:
        """Tokenize source using the Moss-written lexer."""
        self._ensure_loaded()
        raw = self._vm.call(self._vm.globals.get("sketchTokens"), [source])
        tokens: list[Token] = []
        for t in raw:
            if isinstance(t, dict):
                tokens.append(Token(
                    kind=str(t.get("kind", "?")),
                    value=str(t.get("value", "")),
                    line=int(t.get("line", 0)),
                    column=int(t.get("column", 0)),
                ))
        return tokens

    def parse(self, source: str) -> dict:
        """Parse source using the Moss-written parser. Returns {nodes, errors} dict."""
        self._ensure_loaded()
        tokens = self._vm.call(self._vm.globals.get("sketchTokens"), [source])
        return self._vm.call(self._vm.globals.get("parseProgram"), [tokens])

    def parse_to_ast(self, source: str) -> n.Program:
        """Parse source through Moss frontend and convert to Python AST."""
        parsed = self.parse(source)
        return moss_nodes_to_program(parsed.get("nodes", []), source)

    def check(self, source: str) -> dict:
        """Check source using the Moss-written checker."""
        self._ensure_loaded()
        tokens = self._vm.call(self._vm.globals.get("sketchTokens"), [source])
        parsed = self._vm.call(self._vm.globals.get("parseProgram"), [tokens])
        nodes = parsed.get("nodes", [])
        return self._vm.call(self._vm.globals.get("checkProgramNodes"), [nodes])
