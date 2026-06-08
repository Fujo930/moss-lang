# Moss 0.5.6 release notes

Moss `0.5.6` unifies the command-line execution engine: `moss run`, `moss test`,
`moss trace`, `moss golden`, `moss project-run`, `moss project-test`, and
`moss selfhost` now all run on the bytecode VM.

This completes the 0.5.x foundation work — a single, consistent execution
path for every moss CLI command that executes user code.

## VM unifies execution

| Command | 0.5.5 | 0.5.6 |
|---------|-------|-------|
| `moss run` | VM | VM |
| `moss test` | VM | VM |
| `moss trace` | Runtime | **VM** |
| `moss golden` | Runtime | **VM** |
| `moss project-run` | Runtime | **VM** |
| `moss project-test` | Runtime | **VM** |
| `moss selfhost` | Runtime | **VM** |
| `moss repl` | Runtime | Runtime |
| `moss selfhost-compare` | Runtime | Runtime |

`moss repl` and `moss selfhost-compare` remain on the tree-walking Runtime
for now; they use Runtime-specific APIs (`call()`, mutable environment) that
need a VM refactor planned for 0.5.7.

## Bug fixes

- **Short-circuit `and`/`or`** — The bytecode compiler now emits jump-based
  short-circuit evaluation for `and` and `or`, matching the Runtime's
  behaviour. This was the root cause of selfhost sketches crashing on the VM
  with out-of-bounds index errors in `while ... and ...` loops.
- **`textJoin` parameter order** — The VM's `builtin_text_join` now accepts
  `textJoin(parts)` with one argument (empty separator) and uses the correct
  `(parts, separator)` order, matching the Runtime.
- **Project import paths** — The VM now respects `import_paths` (declared
  source roots in `moss.toml`), resolving imports from multiple directories
  as the Runtime does.
- **Imported module tests** — Test blocks from imported modules are now
  discovered and executed by `moss project-test` and `moss selfhost`.

## New: VM trace support

`moss trace` now works on the bytecode VM. Rules are tagged at compile time
(`CodeObject.is_rule`), and the VM records a structured trace event after
each rule evaluation with the rule name, formatted arguments, result, source
file, line, and column. The `--json` output format is compatible with the
Runtime-era format.

## Compiler additions

- `CodeObject.is_rule` flag set by `_compile_rule`
- `CodeObject.source_line` / `source_column` from the rule declaration
- `_compile_test` for test block compilation
- `_compile_short_circuit` for jump-based `and`/`or`
- `BytecodeModule.tests` list serialized in `.mbc` format

## Verification

```powershell
python -m pytest tests/test_mosslang.py -q
# 116 passed, 9 subtests passed

python -m mosslang.cli selfhost --quick
# 5/5 sketch tests PASS

python -m mosslang.cli trace examples/order.moss
# 10:1 canShip(order=...) -> true
# 1 rule evaluation(s)

python -m mosslang.cli test examples/order.moss
# PASS ship stores paid order
# 1/1 tests passed
```

## Upgrade notes

- `.mbc` files from 0.5.5 are incompatible (new `is_rule`, `source_line`,
  `source_column` fields in `CodeObject` serialization).
- `moss repl` and `moss selfhost-compare` still use the Runtime; their
  arrow-function-with-implicit-return behaviour may differ from VM commands.
