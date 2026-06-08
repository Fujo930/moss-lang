"""Moss self-host frontend bridge.

Loads the Moss-written lexer, parser, and checker from examples/self_host/
and exposes them as callable functions that return Python objects.

The self-host modules are loaded via the bytecode VM and called through
VM.call().  Returned Moss values (dicts, lists, strings) are translated
into idiomatic Python types.

Usage:
    from .selfhost import SelfHostFrontend
    f = SelfHostFrontend()
    tokens = f.tokenize("let x = 1")
    # tokens is a list[Token] matching tokens.py Token format
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .parser import parse_source
from .compiler import compile_program
from .vm import VM
from .tokens import Token


def _find_selfhost_root() -> Path:
    """Return the root directory containing the self_host examples."""
    return Path(__file__).resolve().parents[2] / "examples" / "self_host"


class SelfHostFrontend:
    """Bridge to Moss-written lexer, parser, and checker."""

    def __init__(self, root: Path | None = None):
        self._root = root or _find_selfhost_root()
        self._vm: VM | None = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        vm = VM(base_path=self._root.parent)
        # Load parser_core, which transitively imports lexer_core + statement_core
        importer = (
            f'import "examples/self_host/parser_core.moss"\n'
        )
        mod = compile_program(parse_source(importer), source_path=str(self._root / "parser_core.moss"))
        vm.load_module(mod)
        vm.run()
        self._vm = vm
        self._loaded = True

    def tokenize(self, source: str) -> list[Token]:
        """Tokenize source using the Moss-written lexer.

        Token kinds from the selfhost lexer use 'SYMBOL' for all operators
        and punctuation (host distinguishes OP/PUNCT).  Token values and
        positions are identical to the host lexer.
        """
        self._ensure_loaded()
        assert self._vm is not None
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
        assert self._vm is not None
        tokens = self._vm.call(self._vm.globals.get("sketchTokens"), [source])
        return self._vm.call(self._vm.globals.get("parseProgram"), [tokens])

    def parse_expression(self, source: str) -> dict:
        """Parse a single expression using the Moss-written expression parser."""
        self._ensure_loaded()
        assert self._vm is not None
        return self._vm.call(self._vm.globals.get("parseExpressionSource"), [source])
