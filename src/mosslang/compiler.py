
"""Moss bytecode compiler: AST -> BytecodeModule.

Walks the Moss AST produced by parser.py and emits stack-machine
bytecode instructions using the instruction set defined in bytecode.py.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from . import nodes as n
from .bytecode import Opcode, Instruction, CodeObject, BytecodeModule


__all__ = ["compile_program", "Compiler"]


BINARY_OP_MAP = {
    "+": Opcode.ADD, "-": Opcode.SUB, "*": Opcode.MUL, "/": Opcode.DIV,
    "%": Opcode.MOD, "==": Opcode.EQ, "!=": Opcode.NEQ,
    "<": Opcode.LT, ">": Opcode.GT, "<=": Opcode.LTE, ">=": Opcode.GTE,
}


def compile_program(program: n.Program, source_path: str = "module.moss") -> BytecodeModule:
    """Compile a moss program to a bytecode module."""
    compiler = Compiler(source_path)
    return compiler.compile(program)


class Compiler:
    """Compiles Moss AST nodes to bytecode instructions."""

    def __init__(self, source_path: str = "module.moss"):
        self.source_path = source_path
        self.module = BytecodeModule(source_path=source_path)
        self.locals: list[str] = []          # local variable registry
        self.globals: list[str] = []          # global name registry
        self.constants: list[Any] = []        # constant pool
        self.instructions: list[Instruction] = []
        self.label_counter = 0
        # For resolving break/continue targets
        self.loop_breaks: list[int] = []      # stack of label ids for break targets
        self.loop_continues: list[int] = []   # stack of label ids for continue targets

    def compile(self, program: n.Program) -> BytecodeModule:
        """Compile a full program to bytecode."""
        self._setup_globals(program)
        self._compile_declarations(program)

        for item in program.items:
            if self._is_top_level_statement(item):
                self._compile_statement(item)

        self._resolve_labels()
        self.emit(Opcode.RETURN)
        self.module.code = CodeObject(
            name="<module>",
            instructions=list(self.instructions),
            constants=list(self.constants),
            locals=list(self.locals),
            arg_count=0,
        )
        self.module.globals = list(self.globals)
        return self.module

    # ── globals discovery ──

    def _setup_globals(self, program: n.Program) -> None:
        """Register all top-level declared names as globals."""
        for item in program.items:
            if isinstance(item, n.EffectDecl):
                for name in item.names:
                    self.module.declare_effect(name)
                self.globals.append(item.names[0] + "_EFFECT")  # placeholder
            elif isinstance(item, n.TypeDecl):
                self._register_global(item.name)
            elif isinstance(item, n.RuleDecl):
                self._register_global(item.name)
            elif isinstance(item, n.FunctionDecl):
                self._register_global(item.name)
            elif isinstance(item, n.ImportDecl):
                self.module.declare_import(item.path)
            elif isinstance(item, n.TestDecl):
                self._register_global(item.name)

    def _register_global(self, name: str) -> int:
        if name not in self.globals:
            self.globals.append(name)
        return self.globals.index(name)

    def _register_local(self, name: str) -> int:
        if name not in self.locals:
            self.locals.append(name)
        return self.locals.index(name)

    def _find_variable(self, name: str) -> tuple[str, int]:
        """Return ('local'/'global', index) for a variable name."""
        if name in self.locals:
            return ("local", self.locals.index(name))
        if name in self.globals:
            return ("global", self.globals.index(name))
        # Assume global for now; will be resolved by _register_global
        return ("global", self._register_global(name))

    # ── declarations ──

    def _compile_declarations(self, program: n.Program) -> None:
        """Pre-compile all function/rule/test declarations into code objects."""
        for item in program.items:
            if isinstance(item, n.RuleDecl):
                self.module.declare_function(
                    self._compile_rule(item)
                )
            elif isinstance(item, n.FunctionDecl):
                self.module.declare_function(
                    self._compile_function(item)
                )
            elif isinstance(item, n.TestDecl):
                self.module.declare_function(
                    self._compile_test(item)
                )
                self.module.tests.append(item.name)

    def _compile_function(self, decl: n.FunctionDecl) -> CodeObject:
        """Compile a function declaration into a CodeObject."""
        saved_locals = list(self.locals)
        saved_constants = list(self.constants)
        saved_instructions = list(self.instructions)
        saved_breaks = list(self.loop_breaks)
        saved_continues = list(self.loop_continues)

        self.locals = []
        self.instructions = []
        self.loop_breaks = []
        self.loop_continues = []

        for param in decl.params:
            self._register_local(param.name)

        # Compile all but last statement; last may have implicit return
        body = decl.body
        for stmt in body[:-1]:
            self._compile_statement(stmt)

        if body:
            last = body[-1]
            if isinstance(last, n.ReturnStmt):
                self._compile_statement(last)
            elif isinstance(last, n.ExprStmt):
                # Implicit return: compile expression, keep on stack
                self._compile_expression(last.expr)
            else:
                self._compile_statement(last)
                self.emit(Opcode.LOAD_NULL)
        else:
            self.emit(Opcode.LOAD_NULL)

        self.emit(Opcode.RETURN)

        self._resolve_labels()
        co = CodeObject(
            name=decl.name,
            instructions=list(self.instructions),
            constants=list(self.constants),
            locals=list(self.locals),
            arg_count=len(decl.params),
        )

        self.locals = saved_locals
        self.constants = saved_constants
        self.instructions = saved_instructions
        self.loop_breaks = saved_breaks
        self.loop_continues = saved_continues

        return co

    def _compile_test(self, decl: n.TestDecl) -> CodeObject:
        """Compile a test declaration into a callable CodeObject."""
        saved_locals = list(self.locals)
        saved_constants = list(self.constants)
        saved_instructions = list(self.instructions)
        saved_breaks = list(self.loop_breaks)
        saved_continues = list(self.loop_continues)

        self.locals = []
        self.instructions = []
        self.loop_breaks = []
        self.loop_continues = []

        # Compile all statements; last ExprStmt may have implicit return
        body = decl.body
        for stmt in body[:-1]:
            self._compile_statement(stmt)

        if body:
            last = body[-1]
            if isinstance(last, n.ReturnStmt):
                self._compile_statement(last)
            elif isinstance(last, n.ExprStmt):
                self._compile_expression(last.expr)
            else:
                self._compile_statement(last)
                self.emit(Opcode.LOAD_NULL)
        else:
            self.emit(Opcode.LOAD_NULL)

        self.emit(Opcode.RETURN)

        self._resolve_labels()
        co = CodeObject(
            name=decl.name,
            instructions=list(self.instructions),
            constants=list(self.constants),
            locals=list(self.locals),
            arg_count=0,
        )

        self.locals = saved_locals
        self.constants = saved_constants
        self.instructions = saved_instructions
        self.loop_breaks = saved_breaks
        self.loop_continues = saved_continues

        return co

    def _compile_rule(self, decl: n.RuleDecl) -> CodeObject:
        """Compile a rule declaration into a CodeObject (single-expression)."""
        saved_locals = list(self.locals)
        saved_constants = list(self.constants)
        saved_instructions = list(self.instructions)

        self.locals = []
        self.instructions = []

        for param in decl.params:
            self._register_local(param.name)

        self._compile_expression(decl.expr)
        self.emit(Opcode.RETURN)

        self._resolve_labels()
        loc = decl.location
        co = CodeObject(
            name=decl.name,
            instructions=list(self.instructions),
            constants=list(self.constants),
            locals=list(self.locals),
            arg_count=len(decl.params),
            is_rule=True,
            source_line=loc.line if loc else 0,
            source_column=loc.column if loc else 0,
        )

        self.locals = saved_locals
        self.constants = saved_constants
        self.instructions = saved_instructions

        return co

    # ── statements ──

    def _is_top_level_statement(self, item: Any) -> bool:
        return isinstance(item, (
            n.LetStmt, n.AssignStmt, n.ExprStmt,
            n.ReturnStmt, n.RequireStmt, n.IfStmt,
            n.ForStmt, n.WhileStmt, n.BreakStmt, n.ContinueStmt,
        ))

    def _compile_statement(self, stmt: Any) -> None:
        if isinstance(stmt, n.LetStmt):
            self._compile_expression(stmt.expr)
            self._register_local(stmt.name)
            idx = self.locals.index(stmt.name)
            # Duplicate: store to both local (for module code) and global (for functions/tests)
            self.emit(Opcode.DUP)
            self.emit(Opcode.STORE_LOCAL, idx)
            gidx = self._register_global(stmt.name)
            self.emit(Opcode.STORE_GLOBAL, gidx)

        elif isinstance(stmt, n.AssignStmt):
            self._compile_expression(stmt.expr)
            # First assignment in current scope creates a local variable
            if stmt.name not in self.locals and stmt.name not in self.globals:
                self._register_local(stmt.name)
            kind, idx = self._find_variable(stmt.name)
            if kind == "local":
                self.emit(Opcode.STORE_LOCAL, idx)
            else:
                self.emit(Opcode.STORE_GLOBAL, idx)

        elif isinstance(stmt, n.ReturnStmt):
            self._compile_expression(stmt.expr)
            self.emit(Opcode.RETURN)

        elif isinstance(stmt, n.RequireStmt):
            self._compile_expression(stmt.condition)
            ok_label = self._new_label()
            self.emit(Opcode.JUMP_IF_TRUE, ok_label)
            # condition is false = Err
            self._compile_expression(stmt.else_expr)
            self.emit(Opcode.REQUIRE)
            self._emit_label(ok_label)

        elif isinstance(stmt, n.IfStmt):
            self._compile_expression(stmt.condition)
            else_label = self._new_label()
            end_label = self._new_label()
            self.emit(Opcode.JUMP_IF_FALSE, else_label)

            for s in stmt.then_body:
                self._compile_statement(s)

            if stmt.else_body:
                self.emit(Opcode.JUMP, end_label)

            self._emit_label(else_label)

            for s in stmt.else_body:
                self._compile_statement(s)

            self._emit_label(end_label)

        elif isinstance(stmt, n.ForStmt):
            self._compile_expression(stmt.iterable)
            iter_local = self._register_local("__iter_" + stmt.name)
            self.emit(Opcode.STORE_LOCAL, iter_local)

            idx_local = self._register_local("__idx_" + stmt.name)
            self._add_constant(0)
            self.emit(Opcode.LOAD_CONST, self._constant_index(0))
            self.emit(Opcode.STORE_LOCAL, idx_local)

            # Loop header
            start_label = self._new_label()
            break_label = self._new_label()
            continue_label = self._new_label()

            self.loop_breaks.append(break_label)
            self.loop_continues.append(continue_label)

            self._emit_label(start_label)

            # Check index < len(iter)
            self.emit(Opcode.LOAD_LOCAL, idx_local)
            name_idx = self._add_constant("len")
            self.emit(Opcode.LOAD_CONST, name_idx)
            self.emit(Opcode.LOAD_LOCAL, iter_local)
            self.emit(Opcode.CALL, 1)
            self.emit(Opcode.LT)
            self.emit(Opcode.JUMP_IF_FALSE, break_label)

            # Load iter[idx_local]
            self.emit(Opcode.LOAD_LOCAL, iter_local)
            self.emit(Opcode.LOAD_LOCAL, idx_local)
            self.emit(Opcode.GET_INDEX)
            self._register_local(stmt.name)
            loop_var_idx = self.locals.index(stmt.name)
            self.emit(Opcode.STORE_LOCAL, loop_var_idx)

            for s in stmt.body:
                self._compile_statement(s)

            # idx_local = idx_local + 1
            # continue jumps here: execute increment then loop back
            self._emit_label(continue_label)
            self.emit(Opcode.LOAD_LOCAL, idx_local)
            self._add_constant(1)
            self.emit(Opcode.LOAD_CONST, self._constant_index(1))
            self.emit(Opcode.ADD)
            self.emit(Opcode.STORE_LOCAL, idx_local)

            self.emit(Opcode.JUMP, start_label)
            self._emit_label(break_label)

            self.loop_breaks.pop()
            self.loop_continues.pop()

        elif isinstance(stmt, n.WhileStmt):
            start_label = self._new_label()
            break_label = self._new_label()
            continue_label = self._new_label()

            self.loop_breaks.append(break_label)
            self.loop_continues.append(continue_label)

            self._emit_label(start_label)
            self._emit_label(continue_label)

            self._compile_expression(stmt.condition)
            self.emit(Opcode.JUMP_IF_FALSE, break_label)

            for s in stmt.body:
                self._compile_statement(s)

            self.emit(Opcode.JUMP, start_label)
            self._emit_label(break_label)

            self.loop_breaks.pop()
            self.loop_continues.pop()

        elif isinstance(stmt, n.BreakStmt):
            if self.loop_breaks:
                self.emit(Opcode.JUMP, self.loop_breaks[-1])

        elif isinstance(stmt, n.ContinueStmt):
            if self.loop_continues:
                self.emit(Opcode.JUMP, self.loop_continues[-1])

        elif isinstance(stmt, n.ExprStmt):
            self._compile_expression(stmt.expr)
            self.emit(Opcode.POP)  # discard expression result

    # ── expressions ──

    def _compile_expression(self, expr: Any) -> None:
        if isinstance(expr, n.Literal):
            self._compile_literal(expr.value)

        elif isinstance(expr, n.NumberLiteral):
            self._add_constant(expr.value)
            self.emit(Opcode.LOAD_CONST, self._constant_index(expr.value))

        elif isinstance(expr, n.Identifier):
            kind, idx = self._find_variable(expr.name)
            if kind == "local":
                self.emit(Opcode.LOAD_LOCAL, idx)
            else:
                self.emit(Opcode.LOAD_GLOBAL, idx)

        elif isinstance(expr, n.BinaryExpr):
            if expr.op == ".":
                # Field access
                self._compile_field_access(expr)
            elif expr.op == "with":
                self._compile_record_update(expr)
            else:
                if expr.op in ("and", "or"):
                    self._compile_short_circuit(expr)
                else:
                    self._compile_expression(expr.left)
                    self._compile_expression(expr.right)
                    opcode = BINARY_OP_MAP.get(expr.op)
                    if opcode is None:
                        raise ValueError(f"Unknown binary operator: {expr.op}")
                    self.emit(opcode)

        elif isinstance(expr, n.UnaryExpr):
            self._compile_expression(expr.right)
            if expr.op == "-":
                self.emit(Opcode.NEG)
            elif expr.op == "!" or expr.op == "not":
                self.emit(Opcode.NOT)

        elif isinstance(expr, n.CallExpr):
            self._compile_call_expression(expr.callee, expr.args)

        elif isinstance(expr, n.FieldAccess):
            self._compile_expression(expr.target)
            self._add_constant(expr.field)
            self.emit(Opcode.GET_FIELD, self._constant_index(expr.field))

        elif isinstance(expr, n.IndexAccess):
            self._compile_expression(expr.target)
            self._compile_expression(expr.index)
            self.emit(Opcode.GET_INDEX)

        elif isinstance(expr, n.RecordLiteral):
            self._compile_record_literal(expr.fields)

        elif isinstance(expr, n.ListLiteral):
            for item in expr.items:
                self._compile_expression(item)
            self.emit(Opcode.BUILD_LIST, len(expr.items))

        elif isinstance(expr, n.RecordUpdate):
            self._compile_record_update(expr)

        elif isinstance(expr, n.MatchExpr):
            self._compile_match(expr)

        elif isinstance(expr, n.TryExpr):
            # '?' operator: propagate Err, unwrap Ok
            self._compile_expression(expr.expr)
            self.emit(Opcode.TRY_PROPAGATE)

        elif isinstance(expr, n.LambdaExpr):
            self._compile_lambda(expr)

        else:
            raise ValueError(f"Unsupported expression: {type(expr).__name__}")

    def _compile_literal(self, value: Any) -> None:
        """Push a literal value onto the stack."""
        if value is None:
            self.emit(Opcode.LOAD_NULL)
        elif value is True:
            self.emit(Opcode.LOAD_TRUE)
        elif value is False:
            self.emit(Opcode.LOAD_FALSE)
        else:
            self._add_constant(value)
            self.emit(Opcode.LOAD_CONST, self._constant_index(value))

    def _compile_short_circuit(self, expr) -> None:
        """Compile 'and'/'or' with short-circuit evaluation.

        ``A and B``:
          compile A → JUMP_IF_FALSE skip → compile B → JUMP_IF_FALSE skip
          → LOAD_TRUE → JUMP done
          skip: LOAD_FALSE
          done:

        ``A or B``:
          compile A → JUMP_IF_TRUE skip → compile B → JUMP_IF_TRUE skip
          → LOAD_FALSE → JUMP done
          skip: LOAD_TRUE
          done:
        """
        self._compile_expression(expr.left)
        if expr.op == "and":
            skip_label = self._new_label()
            done_label = self._new_label()
            self.emit(Opcode.JUMP_IF_FALSE, skip_label)
            self._compile_expression(expr.right)
            self.emit(Opcode.JUMP_IF_FALSE, skip_label)
            self.emit(Opcode.LOAD_TRUE)
            self.emit(Opcode.JUMP, done_label)
            self._emit_label(skip_label)
            self.emit(Opcode.LOAD_FALSE)
            self._emit_label(done_label)
        else:  # or
            skip_label = self._new_label()
            done_label = self._new_label()
            self.emit(Opcode.JUMP_IF_TRUE, skip_label)
            self._compile_expression(expr.right)
            self.emit(Opcode.JUMP_IF_TRUE, skip_label)
            self.emit(Opcode.LOAD_FALSE)
            self.emit(Opcode.JUMP, done_label)
            self._emit_label(skip_label)
            self.emit(Opcode.LOAD_TRUE)
            self._emit_label(done_label)

    def _compile_field_access(self, expr: n.BinaryExpr) -> None:
        """Compile base.field into GET_FIELD."""
        self._compile_expression(expr.left)
        if isinstance(expr.right, n.Identifier):
            self._add_constant(expr.right.name)
            self.emit(Opcode.GET_FIELD, self._constant_index(expr.right.name))
        else:
            raise ValueError(f"Expected identifier in field access, got {type(expr.right).__name__}")

    def _compile_record_literal(self, fields: dict[str, Any]) -> None:
        """Compile a record literal {key1: val1, key2: val2, ...}."""
        for key, val in fields.items():
            self._add_constant(key)
            self.emit(Opcode.LOAD_CONST, self._constant_index(key))
            self._compile_expression(val)
        self.emit(Opcode.BUILD_RECORD, len(fields))

    def _compile_record_update(self, expr: n.RecordUpdate) -> None:
        """Compile record update: base with field = val."""
        self._compile_expression(expr.base)
        for key, val in expr.updates.items():
            self._add_constant(key)
            self.emit(Opcode.LOAD_CONST, self._constant_index(key))
            self._compile_expression(val)
        self.emit(Opcode.RECORD_UPDATE, len(expr.updates))

    def _compile_call_expression(self, callee: Any, args: list[Any]) -> None:
        """Compile a function call: push name, push args, CALL."""
        if isinstance(callee, n.Identifier):
            name_idx = self._add_constant(callee.name)
            self.emit(Opcode.LOAD_CONST, name_idx)
        elif isinstance(callee, n.FieldAccess):
            self._compile_expression(callee.target)
            name_idx = self._add_constant(callee.field)
            self.emit(Opcode.GET_FIELD, name_idx)
        else:
            self._compile_expression(callee)
        for arg in args:
            self._compile_expression(arg)
        self.emit(Opcode.CALL, len(args))

    def _compile_call(self, name: str, arg_count: int) -> None:
        """Helper to emit a named function call with args on stack."""
        name_idx = self._add_constant(name)
        self.emit(Opcode.LOAD_CONST, name_idx)
        self.emit(Opcode.CALL, arg_count)

    def _compile_lambda(self, expr: n.LambdaExpr) -> None:
        """Compile a lambda into a CodeObject constant."""
        saved_locals = list(self.locals)
        saved_constants = list(self.constants)
        saved_instructions = list(self.instructions)
        saved_breaks = list(self.loop_breaks)
        saved_continues = list(self.loop_continues)

        self.locals = []
        self.instructions = []
        self.loop_breaks = []
        self.loop_continues = []

        for param in expr.params:
            self._register_local(param.name)

        self._compile_expression(expr.expr)
        self.emit(Opcode.RETURN)
        self._resolve_labels()

        co = CodeObject(
            name="<lambda>",
            instructions=list(self.instructions),
            constants=list(self.constants),
            locals=list(self.locals),
            arg_count=len(expr.params),
        )

        self.locals = saved_locals
        self.constants = saved_constants
        self.instructions = saved_instructions
        self.loop_breaks = saved_breaks
        self.loop_continues = saved_continues

        # Push the lambda CodeObject onto the stack
        self._add_constant(co)
        self.emit(Opcode.LOAD_CONST, self._constant_index(co))

    def _compile_match(self, expr: n.MatchExpr) -> None:
        """Compile match: DUP subject, EQ against each variant, jump to matching body."""
        self._compile_expression(expr.subject)
        end_label = self._new_label()
        case_labels = [self._new_label() for _ in expr.cases]

        for i, case in enumerate(expr.cases):
            if isinstance(case.pattern, n.WildcardPattern):
                self.emit(Opcode.POP)  # discard subject
                self._compile_expression(case.expr)
                self.emit(Opcode.JUMP, end_label)
                self._emit_label(case_labels[i])
            elif isinstance(case.pattern, n.VariantPattern):
                self._emit_label(case_labels[i])
                self.emit(Opcode.DUP)
                from .values import Variant
                name_idx = self._add_constant(Variant(case.pattern.name))
                self.emit(Opcode.LOAD_CONST, name_idx)
                self.emit(Opcode.EQ)
                next_lbl = case_labels[i + 1] if i + 1 < len(expr.cases) else end_label
                self.emit(Opcode.JUMP_IF_FALSE, next_lbl)
                self.emit(Opcode.POP)  # discard DUP
                self._compile_expression(case.expr)
                self.emit(Opcode.JUMP, end_label)
            elif isinstance(case.pattern, n.BindingPattern):
                self._emit_label(case_labels[i])
                self._register_local(case.pattern.name)
                idx = self.locals.index(case.pattern.name)
                self.emit(Opcode.DUP)
                self.emit(Opcode.STORE_LOCAL, idx)
                self._compile_expression(case.expr)
                self.emit(Opcode.JUMP, end_label)
            elif isinstance(case.pattern, n.LiteralPattern):
                self._emit_label(case_labels[i])
                self.emit(Opcode.DUP)
                self._compile_literal(case.pattern.value)
                self.emit(Opcode.EQ)
                next_lbl = case_labels[i + 1] if i + 1 < len(expr.cases) else end_label
                self.emit(Opcode.JUMP_IF_FALSE, next_lbl)
                self.emit(Opcode.POP)
                self._compile_expression(case.expr)
                self.emit(Opcode.JUMP, end_label)

        self._emit_label(end_label)
    def _new_label(self) -> int:
        self.label_counter += 1
        return self.label_counter

    def _emit_label(self, label: int) -> None:
        self.instructions.append(Instruction(Opcode.NOP, arg=label))

    def emit(self, opcode: Opcode, arg: int = 0) -> None:
        self.instructions.append(Instruction(opcode, arg=arg))

    def _resolve_labels(self) -> None:
        """Resolve symbolic label references to actual instruction indices."""
        # Build label -> instruction index map
        label_positions: dict[int, int] = {}
        for i, inst in enumerate(self.instructions):
            if inst.opcode == Opcode.NOP and inst.arg > 0:
                label_positions[inst.arg] = i

        # Patch jump instructions
        jump_ops = {Opcode.JUMP, Opcode.JUMP_IF_TRUE, Opcode.JUMP_IF_FALSE}
        for i, inst in enumerate(self.instructions):
            if inst.opcode in jump_ops and inst.arg > 0:
                target = label_positions.get(inst.arg, inst.arg)
                self.instructions[i] = Instruction(inst.opcode, arg=target)

    def _add_constant(self, value: Any) -> int:
        """Add a value to constant pool and return its index."""
        # Normalize to JSON-serializable forms
        if isinstance(value, Decimal):
            value = float(value)
        if value not in self.constants:
            self.constants.append(value)
        return self.constants.index(value)

    def _constant_index(self, value: Any) -> int:
        """Find constant index, raise if not found."""
        if isinstance(value, Decimal):
            value = float(value)
        return self.constants.index(value)
