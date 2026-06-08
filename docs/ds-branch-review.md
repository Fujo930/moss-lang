# ds-Mosslang Branch Review

## Branch identity

- **Branch**: `ds-Mosslang`
- **Version**: Moss 0.54 experimental preview
- **Status**: NOT a stable release. Intended for Codex/main branch review.
- **Parent**: main (Moss 0.5.0 base)
- **Commits**: 72 (from initial fork to 0.54)

## What this branch adds

### Compiler & VM
- 32-opcode bytecode ISA + `.mbc` binary serialization format (bytecode.py)
- AST → BytecodeModule compiler (compiler.py, ~600 lines)
- Stack-based VM in Python (vm.py, ~700 lines)
- **C VM prototype** (src/vm/mossvm.c, ~500 lines C99, zero dependencies)
  - Verified: order.moss, lists_demo, match_demo produce correct output on C VM
  - Build: `cc -o mossvm src/vm/mossvm.c -lm`
  - Limited builtins: print, len, assert, dbPut, dbGet, range, listNew/listPush/listGet, textJoin, textChars, readText, mapNew/mapPut/mapGet/mapHas/mapKeys/mapValues
  - Not yet implemented: jsonParse/jsonStringify, httpGet/httpPostJson, processRun, match opcodes
  - Makefile + moss-native.sh provided

### Trust bundles
- `moss trust <file>` — single-command trust verification producing machine-readable JSON
- `moss trust-project <dir>` — project-wide trust verification
- Trust bundle contains: check (static diagnostics), trace (rule evaluations), golden (output snapshot), lock (dependency verification), selfhost (parser equivalence)
- Source SHA-256 cryptographic binding
- `moss playground` — browser-based trust report viewer (port 8766)
- Studio Trust tab — inline trust reports in the editor

### Moss-written frontend CLI integration
- `moss tokens --frontend moss` — Moss-written lexer
- `moss ast --frontend moss` — Moss-written parser
- `moss check --frontend moss` — Moss-written checker
- `moss compile --frontend moss` — full pipeline via Moss frontend
- `moss run --frontend moss` — Moss frontend → compiler → VM
- `moss test --frontend moss` — Moss frontend + test execution
- `compiler_core.moss` — 499-line Moss-written bytecode compiler (self-compiles)
- SelfHostFrontend bridge (selfhost.py): loads Moss modules into VM, translates MossNode dicts to Python AST

### Tooling
- Backtick string interpolation (`` `Hello {name}!` ``)
- Studio dark theme rewrite + Trust tab
- Playground browser trust report viewer
- VS Code extension scaffolding (extension.ts, package.json)
- moss bench command (VM execution benchmark)
- Enhanced error messages with source line + caret
- Standard library modules (stdlib/: collections, math, text, result, http)
- moss-native.sh + Makefile build system

### Project structure
- CHANGELOG.md — full version history
- ARCHITECTURE.md — system architecture documentation
- Language spec (LANGUAGE_SPEC.md)
- Standard library (stdlib/)
- Grove C platform layer header (src/vm/grove.h)

## Verified commands (all pass)

```
moss check examples/order.moss     ✅
moss run examples/order.moss       ✅
moss test examples/order.moss      ✅
moss format --check examples/order.moss ✅
moss project-check .                ✅
moss selfhost --quick               ✅ (5/5 sketches)
moss selfhost-compare examples      ✅ (all examples)
moss trust examples/order.moss      ✅ (trust=true, all gates pass)
moss trust-project .                ✅ (7/7 files trusted)
moss compile examples/order.moss    ✅
moss run --frontend moss examples/order.moss ✅
moss check --frontend moss examples/order.moss ✅
moss tokens --frontend moss examples/order.moss ✅
moss ast --frontend moss examples/order.moss ✅
moss compile --frontend moss examples/order.moss ✅
C VM (bin/mossvm.exe)              ✅ (order.moss: Shipped/Shipped)
```

## Failed or known-issue commands

```
moss project-test .                ❌ compiler_sketch.moss parse error
```

## Experimental / incomplete

- C VM: 26 builtins implemented, 14 as stubs. Match/While/For/If opcodes not implemented.
- compiler_core.moss: calls Python compiler for function/rule bodies via bridge. Full standalone compilation needs work.
- VS Code extension: extension.ts exists but not packaged or published.
- Grove: header-only (grove.h), no implementation.
- `moss get` / package registry: designed but not implemented.
- TextMate grammar: editors/moss.tmLanguage.json from main branch, not updated for 0.54 syntax additions.

## pyproject.toml status
- ✅ Restored from main branch
- ✅ Version set to 0.54
- ✅ Package data includes studio_assets/* and playground_assets/*
- ✅ Console scripts: moss, moss-lsp
- ✅ Build system: setuptools

## .gitignore status
- ✅ bin/ excluded
- ✅ __pycache__, *.pyc, .pytest_cache, etc. excluded
- ✅ reasonix.toml excluded

## Version narrative
All remaining references to 0.33, 0.5.0, 0.6.0 have been harmonized to 0.54 experimental preview on the ds-Mosslang branch.

## Recommended for merging into main
- bytecode.py + compiler.py + vm.py (core VM infrastructure)
- Backtick string interpolation
- Enhanced error messages
- moss bench command
- Studio dark theme (app.css, app.js, index.html — backwards compatible)
- CHANGELOG.md, ARCHITECTURE.md
- Standard library modules (stdlib/)
- .gitignore updates

## Recommended to keep on experimental branch
- C VM (src/vm/mossvm.c) — incomplete, needs more builtins and opcode coverage
- compiler_core.moss — experimental, calls Python bridges
- moss trust/trust-project — novel concept but needs design review
- moss playground — depends on trust bundle
- --frontend moss integration — bridge complexity needs review
- VS Code extension — scaffolding only
- Grove header — no implementation

## High-risk files
- src/vm/mossvm.c — large C file with memory management, needs valgrind/asan review
- src/mosslang/selfhost.py — complex MossNode-to-AST bridge
- src/mosslang/playground.py — HTTP server, needs security review
- examples/self_host/compiler_core.moss — 499 lines of Moss code, self-compilation not fully verified

## Recommendations for Codex

1. Merge bytecode/VM infrastructure as the new execution engine. The tree-walking runtime.py is already marked retired.
2. Review trust bundle concept — it's the most novel contribution. Decide if it belongs in main or stays experimental.
3. Keep C VM separate until it reaches feature parity with Python VM (match, while, for, jsonParse, httpGet, processRun).
4. Review —frontend moss bridge complexity. The MossNode-to-AST conversion in selfhost.py is the riskiest code.
5. Test the VS Code extension in a real VS Code instance before merging.

## Decision governance

This branch does NOT decide Moss's mainline direction. It presents experimental
work for review. Final merge decisions rest with Codex, based on Moss's README,
history, roadmap, design intent, and test results.
