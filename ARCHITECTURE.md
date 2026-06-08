# Moss Architecture

## Pipeline

```
Source (.moss) → tokens.py → parser.py → checker.py → compiler.py → vm.py (Python)
               ↘          SelfHostFrontend    ↗                  mossvm.c (C)
                 Moss lexer → Moss parser → Moss checker → Moss compiler
```

## Layers

| Layer | Python (host) | Moss (self-host) |
|-------|--------------|-------------------|
| Lexer | tokens.py (300 lines) | lexer_core.moss (150 lines) |
| Parser | parser.py (700 lines) | parser_core.moss (450 lines) |
| Checker | checker.py (530 lines) | checker_core.moss (330 lines) |
| Compiler | compiler.py (600 lines) | compiler_core.moss (500 lines) |
| VM (exec) | vm.py (700 lines, 32 opcodes) | mossvm.c (500 lines C, 32 opcodes) |

## File Map

```
src/mosslang/
  tokens.py       — Lexer: source → Token stream
  parser.py       — Recursive descent parser: Token → AST
  nodes.py        — AST node definitions (30+ frozen dataclasses)
  checker.py      — Static checker: type inference, effect tracking, diagnostics
  compiler.py     — AST → BytecodeModule compiler (32 opcodes, label backpatch)
  bytecode.py     — Opcode enum + Instruction + BytecodeModule + .mbc serialization
  vm.py           — Stack VM: Frame + _execute + 32 opcode dispatch
  values.py       — Runtime values: Money, Variant, Result, format_value
  errors.py       — MossSyntaxError, MossRuntimeError, SourceLocation
  runtime.py      — Tree-walking interpreter (retired in 0.5.6, kept for reference)
  selfhost.py     — SelfHostFrontend bridge: loads Moss modules into VM
  cli.py          — CLI: argparse + 25 commands
  lsp.py          — Language Server Protocol over stdio
  studio.py       — Studio HTTP server + JSON API
  playground.py   — Playground HTTP server + /api/trust
  project.py      — Project manifests, import graphs, lock files
  formatter.py    — Deterministic code formatter
  docsgen.py      — Markdown API doc generator
  tooling.py      — Editor-facing analysis interface
  desktop.py      — Desktop entry point

examples/self_host/
  token_tools.moss      — Token record type + helpers
  lexer_core.moss       — Moss-written lexer
  expression_core.moss   — Expression parser
  statement_core.moss    — Statement parser  
  parser_core.moss       — Top-level declaration parser
  checker_core.moss      — Static checker
  compiler_core.moss     — Bytecode compiler (v0.16)

src/vm/
  mossvm.c        — C VM (500 lines C99, zero-dependency)
  grove.h         — Grove editor C platform layer

editors/
  vscode/          — VS Code extension (package.json + extension.ts)
  moss.tmLanguage.json — TextMate syntax highlighting

stdlib/
  collections.moss, math.moss, text.moss, result.moss, http.moss

bin/
  mossvm.exe      — Compiled C VM binary

docs/              — docs/, RELEASE.md, CHANGELOG.md, LANGUAGE_SPEC.md
```

## Cross-cutting concepts

1. **Token efficiency**: Every syntax feature was designed to reduce AI generation cost
2. **Trust bundles**: check + trace + golden + lock + selfhost → cryptographic verification
3. **Self-host bridge**: MossNode dicts → Python AST via `moss_nodes_to_program()`
4. **Call frames**: Python Frame / C frames[] — both save/restore on CALL/RETURN
5. **Dual VM**: Python VM (development, 700 lines) + C VM (deployment, 500 lines)
6. **Binary format**: .mbc files portable between Python VM and C VM
