from __future__ import annotations

from decimal import Decimal

from .errors import MossSyntaxError
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
    MatchCase,
    MatchExpr,
    NumberLiteral,
    Param,
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
from .tokens import Token, tokenize


DECL_START = {"effect", "type", "rule", "fn", "test", "import"}
STMT_START = {"let", "return", "require", "if", "for", "while", "break", "continue"}


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.current = 0

    def parse(self) -> Program:
        items: list[object] = []
        self.skip_newlines()
        while not self.check_kind("EOF"):
            if self.check_value("effect"):
                items.append(self.parse_effect_decl())
            elif self.check_value("import"):
                items.append(self.parse_import_decl())
            elif self.check_value("type"):
                items.append(self.parse_type_decl())
            elif self.check_value("rule"):
                items.append(self.parse_rule_decl())
            elif self.check_value("fn"):
                items.append(self.parse_function_decl())
            elif self.check_value("test"):
                items.append(self.parse_test_decl())
            else:
                items.append(self.parse_statement())
            self.skip_newlines()
        return Program(items)

    def parse_effect_decl(self) -> EffectDecl:
        self.expect_value("effect")
        names = [self.expect_ident()]
        while self.match_value(","):
            names.append(self.expect_ident())
        self.consume_statement_end()
        return EffectDecl(names)

    def parse_import_decl(self) -> ImportDecl:
        self.expect_value("import")
        if not self.match_kind("STRING"):
            raise self.error("expected import path string")
        path = self.previous().value
        self.consume_statement_end()
        return ImportDecl(path)

    def parse_type_decl(self) -> TypeDecl:
        self.expect_value("type")
        name = self.expect_ident()
        self.expect_value("=")

        if self.match_value("{"):
            fields: dict[str, str] = {}
            self.skip_newlines()
            while not self.match_value("}"):
                field_name = self.expect_ident()
                self.expect_value(":")
                fields[field_name] = self.parse_type_text_until({",", "}", "\n"})
                if not self.match_value(","):
                    self.skip_newlines()
                else:
                    self.skip_newlines()
            self.consume_statement_end()
            return TypeDecl(name=name, fields=fields)

        if self.match_kind("NEWLINE"):
            fields = {}
            self.skip_newlines()
            while not self.check_kind("EOF") and not self.is_top_level_start():
                field_name = self.expect_ident()
                self.expect_value(":")
                fields[field_name] = self.parse_type_text_until({"\n"})
                self.consume_statement_end()
            return TypeDecl(name=name, fields=fields)

        alias = self.parse_type_text_until({"\n"})
        self.consume_statement_end()
        return TypeDecl(name=name, fields={}, alias=alias)

    def parse_rule_decl(self) -> RuleDecl:
        self.expect_value("rule")
        name = self.expect_ident()
        params = self.parse_params()
        return_type = self.parse_optional_return_type(stop_values={"="})
        self.expect_value("=")
        self.skip_newlines()
        expr = self.parse_expression()
        self.consume_statement_end()
        return RuleDecl(name=name, params=params, return_type=return_type, expr=expr)

    def parse_function_decl(self) -> FunctionDecl:
        self.expect_value("fn")
        name = self.expect_ident()
        params = self.parse_params()
        return_type = self.parse_optional_return_type(stop_values={"uses", "{"})
        uses: list[str] = []
        if self.match_value("uses"):
            uses.append(self.expect_ident())
            while self.match_value(","):
                uses.append(self.expect_ident())
        body = self.parse_block()
        self.consume_statement_end()
        return FunctionDecl(name=name, params=params, return_type=return_type, uses=uses, body=body)

    def parse_test_decl(self) -> TestDecl:
        self.expect_value("test")
        if self.match_kind("STRING"):
            name = self.previous().value
        else:
            name = self.expect_ident()
        body = self.parse_block()
        self.consume_statement_end()
        return TestDecl(name, body)

    def parse_params(self) -> list[Param]:
        params: list[Param] = []
        self.expect_value("(")
        self.skip_newlines()
        if self.match_value(")"):
            return params
        while True:
            name = self.expect_ident()
            type_name = None
            if self.match_value(":"):
                type_name = self.parse_type_text_until({",", ")"})
            params.append(Param(name, type_name))
            if self.match_value(","):
                self.skip_newlines()
                continue
            self.expect_value(")")
            return params

    def parse_optional_return_type(self, stop_values: set[str]) -> str | None:
        if not self.match_value("->"):
            return None
        return self.parse_type_text_until(stop_values | {"\n"})

    def parse_type_text_until(self, stop_values: set[str]) -> str:
        parts: list[str] = []
        angle_depth = 0
        while not self.check_kind("EOF"):
            token = self.peek()
            if token.value == "<":
                angle_depth += 1
            elif token.value == ">" and angle_depth > 0:
                angle_depth -= 1
            if angle_depth == 0 and (token.value in stop_values or (token.kind == "NEWLINE" and "\n" in stop_values)):
                break
            if token.kind == "NEWLINE":
                break
            parts.append(self.advance().value)
        if not parts:
            raise self.error("expected type")
        return format_type_text(parts)

    def parse_block(self) -> list[object]:
        self.expect_value("{")
        statements: list[object] = []
        self.skip_newlines()
        while not self.check_value("}"):
            if self.check_kind("EOF"):
                raise self.error("expected '}' before end of file")
            statements.append(self.parse_statement())
            self.skip_newlines()
        self.expect_value("}")
        return statements

    def parse_statement(self) -> object:
        self.skip_newlines()
        if self.match_value("let"):
            name = self.expect_ident()
            self.expect_value("=")
            expr = self.parse_expression()
            self.consume_statement_end()
            return LetStmt(name, expr)

        if self.match_value("return"):
            expr = self.parse_expression()
            self.consume_statement_end()
            return ReturnStmt(expr)

        if self.match_value("require"):
            condition = self.parse_expression()
            self.skip_newlines()
            self.expect_value("else")
            else_expr = self.parse_expression()
            self.consume_statement_end()
            return RequireStmt(condition, else_expr)

        if self.match_value("if"):
            condition = self.parse_expression()
            then_body = self.parse_block()
            else_body: list[object] = []
            if self.match_value("else"):
                else_body = self.parse_block()
                self.consume_statement_end()
                return IfStmt(condition, then_body, else_body)
            if self.match_kind("NEWLINE"):
                self.skip_newlines()
                if self.match_value("else"):
                    else_body = self.parse_block()
                    self.consume_statement_end()
                return IfStmt(condition, then_body, else_body)
            self.consume_statement_end()
            return IfStmt(condition, then_body, else_body)

        if self.match_value("for"):
            name = self.expect_ident()
            self.expect_value("in")
            iterable = self.parse_expression()
            body = self.parse_block()
            self.consume_statement_end()
            return ForStmt(name, iterable, body)

        if self.match_value("while"):
            condition = self.parse_expression()
            body = self.parse_block()
            self.consume_statement_end()
            return WhileStmt(condition, body)

        if self.match_value("break"):
            self.consume_statement_end()
            return BreakStmt()

        if self.match_value("continue"):
            self.consume_statement_end()
            return ContinueStmt()

        if self.check_kind("IDENT") and self.peek_next().value == "=":
            name = self.advance().value
            self.expect_value("=")
            expr = self.parse_expression()
            self.consume_statement_end()
            return AssignStmt(name, expr)

        expr = self.parse_expression()
        self.consume_statement_end()
        return ExprStmt(expr)

    def parse_expression(self) -> object:
        return self.parse_update()

    def parse_update(self) -> object:
        expr = self.parse_or()
        if self.match_value("with"):
            updates: dict[str, object] = {}
            if self.match_value("{"):
                self.skip_newlines()
                while not self.match_value("}"):
                    field = self.expect_ident()
                    if not (self.match_value("=") or self.match_value(":")):
                        raise self.error("expected '=' or ':' in record update")
                    updates[field] = self.parse_expression()
                    if self.match_value(","):
                        self.skip_newlines()
                    else:
                        self.skip_newlines()
            else:
                field = self.expect_ident()
                self.expect_value("=")
                updates[field] = self.parse_expression()
                while self.match_value(","):
                    field = self.expect_ident()
                    self.expect_value("=")
                    updates[field] = self.parse_expression()
            return RecordUpdate(expr, updates)
        return expr

    def parse_or(self) -> object:
        expr = self.parse_and()
        while self.match_value("or"):
            op = self.previous().value
            right = self.parse_and()
            expr = BinaryExpr(expr, op, right)
        return expr

    def parse_and(self) -> object:
        expr = self.parse_equality()
        while self.match_value("and"):
            op = self.previous().value
            right = self.parse_equality()
            expr = BinaryExpr(expr, op, right)
        return expr

    def parse_equality(self) -> object:
        expr = self.parse_comparison()
        while self.match_value("==") or self.match_value("!="):
            op = self.previous().value
            right = self.parse_comparison()
            expr = BinaryExpr(expr, op, right)
        return expr

    def parse_comparison(self) -> object:
        expr = self.parse_term()
        while self.match_value(">") or self.match_value(">=") or self.match_value("<") or self.match_value("<="):
            op = self.previous().value
            right = self.parse_term()
            expr = BinaryExpr(expr, op, right)
        return expr

    def parse_term(self) -> object:
        expr = self.parse_factor()
        while self.match_value("+") or self.match_value("-"):
            op = self.previous().value
            right = self.parse_factor()
            expr = BinaryExpr(expr, op, right)
        return expr

    def parse_factor(self) -> object:
        expr = self.parse_unary()
        while self.match_value("*") or self.match_value("/"):
            op = self.previous().value
            right = self.parse_unary()
            expr = BinaryExpr(expr, op, right)
        return expr

    def parse_unary(self) -> object:
        if self.check_kind("IDENT") and self.match_value("not"):
            op = self.previous().value
            right = self.parse_unary()
            return UnaryExpr(op, right)
        if self.check_kind("OP") and self.match_value("-"):
            op = self.previous().value
            right = self.parse_unary()
            return UnaryExpr(op, right)
        return self.parse_postfix()

    def parse_postfix(self) -> object:
        expr = self.parse_primary()
        while True:
            if self.match_value("("):
                args: list[object] = []
                self.skip_newlines()
                if not self.check_value(")"):
                    while True:
                        args.append(self.parse_expression())
                        if self.match_value(","):
                            self.skip_newlines()
                            continue
                        break
                self.expect_value(")")
                expr = CallExpr(expr, args)
                continue

            if self.match_value("."):
                field = self.expect_ident()
                expr = FieldAccess(expr, field)
                continue

            if self.match_value("["):
                index = self.parse_expression()
                self.expect_value("]")
                expr = IndexAccess(expr, index)
                continue

            if self.match_value("?"):
                expr = TryExpr(expr)
                continue

            return expr

    def parse_primary(self) -> object:
        if self.match_kind("NUMBER"):
            return NumberLiteral(Decimal(self.previous().value))

        if self.match_kind("STRING"):
            return Literal(self.previous().value)

        if self.match_value("true"):
            return Literal(True)

        if self.match_value("false"):
            return Literal(False)

        if self.match_value("null"):
            return Literal(None)

        if self.match_value("match"):
            return self.parse_match_expr()

        if self.match_kind("IDENT"):
            return Identifier(self.previous().value)

        if self.match_value("("):
            expr = self.parse_expression()
            self.expect_value(")")
            return expr

        if self.match_value("{"):
            fields: dict[str, object] = {}
            self.skip_newlines()
            while not self.match_value("}"):
                field = self.expect_ident()
                self.expect_value(":")
                fields[field] = self.parse_expression()
                if self.match_value(","):
                    self.skip_newlines()
                    continue
                self.skip_newlines()
            return RecordLiteral(fields)

        if self.match_value("["):
            items: list[object] = []
            self.skip_newlines()
            if not self.check_value("]"):
                while True:
                    items.append(self.parse_expression())
                    if self.match_value(","):
                        self.skip_newlines()
                        continue
                    break
            self.expect_value("]")
            return ListLiteral(items)

        raise self.error("expected expression")

    def parse_match_expr(self) -> MatchExpr:
        subject = self.parse_expression()
        self.expect_value("{")
        cases: list[MatchCase] = []
        self.skip_newlines()
        while not self.match_value("}"):
            pattern = self.parse_pattern()
            self.expect_value("->")
            expr = self.parse_expression()
            cases.append(MatchCase(pattern, expr))
            if self.match_value(",") or self.match_value(";"):
                self.skip_newlines()
            else:
                self.skip_newlines()
        return MatchExpr(subject, cases)

    def parse_pattern(self) -> object:
        if self.match_value("_"):
            return WildcardPattern()
        if self.match_kind("STRING"):
            return LiteralPattern(self.previous().value)
        if self.match_kind("NUMBER"):
            return LiteralPattern(Decimal(self.previous().value))
        if self.match_value("true"):
            return LiteralPattern(True)
        if self.match_value("false"):
            return LiteralPattern(False)
        if self.match_value("null"):
            return LiteralPattern(None)
        if self.match_kind("IDENT"):
            name = self.previous().value
            while self.match_value("."):
                name += "." + self.expect_ident()
            payload: list[object] = []
            if self.match_value("("):
                self.skip_newlines()
                if not self.check_value(")"):
                    while True:
                        payload.append(self.parse_pattern())
                        if self.match_value(","):
                            self.skip_newlines()
                            continue
                        break
                self.expect_value(")")
            if name and name[0].islower() and "." not in name and not payload:
                return BindingPattern(name)
            return VariantPattern(name, payload)
        raise self.error("expected pattern")

    def is_top_level_start(self) -> bool:
        if self.check_kind("EOF"):
            return True
        if not self.check_kind("IDENT"):
            return False
        return self.peek().value in DECL_START | STMT_START

    def consume_statement_end(self) -> None:
        if self.match_value(";"):
            self.skip_newlines()
            return
        if self.match_kind("NEWLINE"):
            self.skip_newlines()
            return
        if self.check_kind("EOF") or self.check_value("}"):
            return
        raise self.error("expected end of statement")

    def skip_newlines(self) -> None:
        while self.match_kind("NEWLINE"):
            pass

    def match_value(self, value: str) -> bool:
        if self.check_value(value):
            self.advance()
            return True
        return False

    def match_kind(self, kind: str) -> bool:
        if self.check_kind(kind):
            self.advance()
            return True
        return False

    def expect_value(self, value: str) -> Token:
        if self.match_value(value):
            return self.previous()
        raise self.error(f"expected {value!r}")

    def expect_ident(self) -> str:
        if self.match_kind("IDENT"):
            return self.previous().value
        raise self.error("expected identifier")

    def check_value(self, value: str) -> bool:
        return self.peek().value == value

    def check_kind(self, kind: str) -> bool:
        return self.peek().kind == kind

    def advance(self) -> Token:
        if not self.check_kind("EOF"):
            self.current += 1
        return self.previous()

    def peek(self) -> Token:
        return self.tokens[self.current]

    def peek_next(self) -> Token:
        if self.current + 1 >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[self.current + 1]

    def previous(self) -> Token:
        return self.tokens[self.current - 1]

    def error(self, message: str) -> MossSyntaxError:
        return MossSyntaxError(message, self.peek().location)


def parse_source(source: str) -> Program:
    return Parser(tokenize(source)).parse()


def format_type_text(parts: list[str]) -> str:
    text = ""
    for part in parts:
        if not text:
            text = part
        elif part in {">", ")", "]", ","}:
            text += part
        elif part in {"<", "(", "[", "."}:
            text += part
        elif text.endswith(("<", "(", "[", ".")):
            text += part
        elif part == "|":
            text += " | "
        else:
            text += " " + part
    return text.replace(", ", ", ")
