# Moss Language Specification v0.30 (pre-1.0 freeze)

This document specifies the Moss language surface as of v0.30. Breaking changes
after v1.0 require a major version bump. Additions are backward-compatible.

## 1. Lexical structure

Moss source is UTF-8 text. Identifiers: `[a-zA-Z_][a-zA-Z0-9_]*`. Keywords:
`effect type rule fn test import let return require if else elif for while
break continue match true false null and or not uses`.

Comments: `//` to end of line, `#` to end of line.

String literals: `"..."` (single line), `` `...` `` (multiline with `{expr}`
interpolation).

## 2. Declarations

### 2.1 Effects
```
effect Name1, Name2
```

### 2.2 Types
Record: `type Name = field: Type, field: Type` (comma-separated single-line)
or multi-line with `\n  field: Type` indentation.

Alias: `type Name = Variant1 | Variant2`

### 2.3 Rules
```
rule name(params) -> ReturnType = expression
```
Rules are pure, traceable, side-effect-free functions. Every evaluation is
recorded by `moss trace`.

### 2.4 Functions
```
fn name(params) -> ReturnType uses Effect1, Effect2 { body }
fn name(params) = expression  (arrow body shorthand)
```
Last expression in body is implicitly returned.

### 2.5 Tests
```
test "name" { body }
```
Tests execute after module-level setup. `moss test` runs all tests.

## 3. Types

Built-in: `Text`, `Bool`, `Number`, `Money` (`42.usd`), `Null`.
Generic: `List<T>`, `Map<K, V>`, `Option<T>`, `Result<T, E>`.
Variants: `VariantName`, `VariantName(payload)`.

## 4. Expressions

- Literals: strings, numbers, `true`, `false`, `null`, `42.usd`
- Identifiers: variable references
- Records: `{ field: value, ... }`
- Lists: `[item, ...]`
- Field access: `expr.field`
- Index access: `expr[index]`
- Record update: `expr with field = value`
- Binary operators: `+ - * / % == != < > <= >= and or`
- Unary operators: `not`, `-`
- Call: `callee(args)`
- Pipe: `expr |> fn(args)` desugars to `fn(expr, args)`
- Lambda: `\x, y -> expr`
- Try: `expr?` (propagates `Err`, unwraps `Ok`)
- Match: `match expr { pattern -> body, ... }`
- String interpolation: `` `Hello {name}!` ``

## 5. Statements

- `let name = expr` — immutable binding
- `name = expr` — reassignment
- `return expr`
- `require condition else expr` — guard returning `Err(expr)` on failure
- `if cond { ... } else { ... }`
- `for name in iterable { ... }`
- `while cond { ... }`
- `break`, `continue`
- Expression statements: bare `expr`

## 6. Imports and modules

- `import "path.moss"` — relative to importing file, then CWD
- `moss.toml` — project manifest
- `moss.lock` — deterministic import graph hash lock

## 7. Trust verification

```
moss trust file.moss → JSON bundle with:
  check: static diagnostics
  trace: rule evaluation events
  golden: output snapshot
  lock: dependency verification
  selfhost: host/self-host parser equivalence
```

## 8. Moss frontend

```
moss tokens --frontend moss
moss ast --frontend moss
moss check --frontend moss
moss compile --frontend moss
moss run --frontend moss
moss test --frontend moss
```

## 9. Compatibility commitment

This specification is frozen as of v0.30. Additions may be made in 0.x and
1.x without breaking existing programs. Removals or semantic changes require
a major version bump (2.0). The `.mbc` binary format carries a version field;
breaking changes to the format increment the version byte.

## 10. Implementations

- Reference: Python host (mosslang package, ~8k lines)
- Self-hosted: Moss frontend (examples/self_host/, ~2.5k lines)
- Native: C VM (src/vm/mossvm.c, ~500 lines)
- Tools: moss-lsp (Language Server), moss studio (browser editor)
