# Moss 0.5.5 release notes

Moss `0.5.5` adds backtick string interpolation, switches `moss run` and
`moss test` to the bytecode VM, and fixes several bytecode compiler gaps
discovered during the switch.

This release continues the 0.5.x token-efficient syntax series started by
DeepSeek (Kun) in 0.5.1–0.5.4.

## Backtick string interpolation

```moss
let name = "Moss"
print(`Hello {name}!`)  // Hello Moss!

let a = 1
let b = 2
print(`{a} + {b} = {a + b}`)  // 1 + 2 = 3

fn greet(n) = `Hello {n}!`
print(greet("World"))  // Hello World!
```

Backtick strings support:

- multiline text (backtick strings span newlines)
- `{expression}` interpolation at any position
- nested function calls and operators inside `{...}`
- arrow function bodies with interpolation (`fn f(x) = \`...\``)
- escape sequences: `` \n \t \r \` \\ \{ ``

Regular `"..."` strings are unchanged and never interpolate.

## Bytecode VM as default execution engine

`moss run` and `moss test` now compile programs to bytecode and execute them
on the stack VM instead of the tree-walking interpreter. The tree-walking
interpreter is still used by `moss trace`, `moss repl`, `moss studio`,
`moss selfhost`, and `moss selfhost-compare`.

Bytecode-level additions for this change:

- `TestDecl` compilation into callable `CodeObject` entries
- `BytecodeModule.tests` list in the `.mbc` binary format
- module-level `let` variables are stored as both local and global so
  functions and test blocks can reference them
- mixed string/number `+` in the VM now formats through `format_value`

## Tokenizer: backtick mode and `|>` pipe

The tokenizer now distinguishes backtick strings from regular strings and
emits `BK_PART`, `INTERP_START`, and `INTERP_END` tokens for interpolation
regions. The `|>` pipe operator token was added in 0.5.2 but the tokenizer
entry was previously missing; this release includes it.

## What's changed

| Area | Change |
|------|--------|
| Tokenizer | Backtick collection mode with interpolation token emission |
| Parser | `_parse_interpolation_chain` desugars backtick strings to `+` chains |
| Compiler | `TestDecl` compilation, `let` stores to both local and global |
| Bytecode | `tests` field in `BytecodeModule` serialization |
| VM | Mixed-type `+` via `format_value`, `tests` list populated on load |
| CLI | `moss run`/`moss test` use bytecode VM |
| Syntax | `` ` `` backtick strings with `{expr}` interpolation |

## Verification

```powershell
python -m pytest tests/test_mosslang.py -q
# 116 passed, 9 subtests passed

python -m mosslang.cli selfhost --quick
# 5/5 sketch tests pass

python -m mosslang.cli test examples/order.moss
# PASS ship stores paid order
# 1/1 tests passed
```

## Upgrade notes

- `moss.lock` files from earlier versions are compatible.
- `.mbc` files from 0.5.4 are incompatible (new `tests` field in binary
  format). Recompile with `moss compile`.
- Backtick strings cannot contain unescaped `` ` `` characters. Use `` \` ``
  to include a literal backtick.
