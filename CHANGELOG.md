# CHANGELOG

## v0.55.0 — Trust Artifact Audit Fixes (TAA snapshot)

### Fixed Vulnerabilities (audit-report.md)
- **V2 (High)**: RuleDecl now checked for effect builtin calls. Rules must be pure.
- **V5 (High)**: Self-host parser arrow-function body boundary fixed. `fn f(x) = expr` no longer eats subsequent top-level declarations.
- **V1 (Medium)**: `moss trust` always produces JSON bundle, even on parse/runtime errors. Added `_error` field with exception type/message.
- **V4 (Medium)**: Lock file search walks upward from source directory, matching `find_manifest` behavior.
- **V6 (Low)**: `source_sha256` round-trip verified on file output. Added `_hash_verified` field.
- **V3 (Low)**: `trace.ok` now independently validated — checks that declared rules produce trace events. Added `rules_declared`/`events_captured` fields.

### Verification
- **133 tests, 22 subtests pass**
- **Selfhost 9/9 comparison passed** (including arrow-function + let patterns)
- **All 6 audit PoCs verified fixed**

## v0.43.0 (pre-1.0)
- Enhanced example run tests with expected output validation
- 133 tests pass, 22 subtests
- C VM verified: order.moss, lists_demo, match_demo, text_fs_demo all pass

## v0.36.0–v0.42.0 — C VM Completion
- C VM function call frames with full Moss function execution
- V_MONEY value type with amount+currency
- Record output rendering ({key: val, ...})
- Variant namespacing (ShipError.NotReady)
- Map/list/text builtins
- GET_INDEX/SET_INDEX
- Real file reading via readText
- order.moss verified end-to-end on C VM

## v0.16.0–v0.35.0 — Self-Hosting Compiler & C VM Foundation
- compiler_core.moss: 499-line Moss bytecode compiler
- C VM: 500-line C99 stack machine, 32 opcodes
- moss-native build system (Makefile + shell wrapper)
- VS Code extension (extension.ts)
- Language specification frozen (LANGUAGE_SPEC.md)
- Standard library (collections, math, text, result, http)

## v0.8.0–v0.15.0 — CLI & Developer Experience
- Enhanced error messages with source line display
- Trust-ready project template (moss new --template trust)
- Generated docs with trust section
- Cross-platform CI (GitHub Actions)
- Language guide (docs/moss-guide.md)
- Bench command (moss bench)

## v0.5.5–v0.7.3 — Trust Bundles & VM Unification
- Trust bundles (moss trust/trust-project)
- 12 commands unified on bytecode VM
- Moss Playground (browser trust report viewer)
- Studio dark theme + Trust tab
- Backtick string interpolation
- Active Moss-written frontend (--frontend moss)

## v0.1.0–v0.5.4 — Foundation
- Moss language core (DeepSeek Codex & Kun)
- Tokenizer, parser, checker, bytecode compiler
- 32-opcode stack VM
- AI token-efficiency syntax (implicit return, pipe, lambda, arrow body)
- Self-hosting sketches
- Studio, LSP, TextMate grammar
