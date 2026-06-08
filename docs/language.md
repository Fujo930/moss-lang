# Moss language notes

This document describes the syntax and semantics implemented by the current
prototype.

Moss is AI-designed and AI-built. DeepSeek designed, implemented, debugged,
documented, committed, and pushed the current prototype in collaboration with
Fujo930. The current public version is `0.5.0`, a self-hosting preview rather
than a finished self-hosted compiler.

The language's public identity and supported project wording live in
`docs/identity.md`.

## Design center

Moss is for long-lived product software. The prototype keeps three ideas visible:

- domain states should be named directly
- fallible workflows should make failure explicit
- effects should be visible at the function boundary

## Declarations

Effects name capabilities that a function can use:

```moss
effect Database, Network
```

Imports load another Moss file before the current file continues:

```moss
import "examples/modules/word_tools.moss"
```

Relative imports are resolved from the importing file's directory first, then
from the current working directory.

Record types describe domain objects:

```moss
type Order =
  id: Text
  status: Pending | Paid | Shipped | Cancelled
  total: Money
```

Aliases describe simple unions:

```moss
type ShipError = NotReady | Missing
```

Rules are pure expression functions:

```moss
rule canShip(order: Order) -> Bool =
  order.status == Paid and order.total > 0.usd
```

Functions use block bodies and can declare effects:

```moss
fn ship(order: Order) -> Result<Order, ShipError> uses Database {
  require canShip(order)
    else ShipError.NotReady(order.status)

  return Ok(order with status = Shipped)
}
```

Tests are top-level executable checks:

```moss
test "ships paid orders" {
  shipped = ship(order)?
  assert(shipped.status == Shipped, "expected shipped status")
}
```

`moss run` ignores test blocks. `moss test` runs program setup first, then runs
each test block and reports pass/fail results.

## Values

The prototype supports:

- `Text`: string literals
- `Bool`: `true` and `false`
- `Number`: decimal numbers
- `Money`: `42.usd`, `9.99.eur`
- `Null`: `null`
- lists: `[1, 2, 3]`
- records: `{ id: "A-100", status: Paid }`
- variants: `Paid`, `ShipError.NotReady(Pending)`
- results: `Ok(value)`, `Err(value)`

Record update creates a copy:

```moss
let shipped = order with status = Shipped
```

Lists support indexing and a few core builtins:

```moss
let names = ["token", "parser", "checker"]
print(names[1])
print(listGet(names, 10, "missing"))
print(len(names))
print(range(1, 4))
```

`List<T>` can be used in function signatures:

```moss
fn count(items: List<Text>) -> Number {
  return len(items)
}
```

Multiline lists, records, calls, function parameters, and record updates may
use trailing commas. This keeps generated code and edited diffs stable:

```moss
fn join(
  left: Text,
  right: Text,
) -> Text {
  return left + right
}

let node = {
  kind: "Function",
  name: "ship",
}
```

List helpers return new lists rather than mutating the original list:

- `listGet(list, index, default)` returns `default` when the index is out of range
- `listSet(list, index, value)`
- `listSlice(list, start, end)`
- `listConcat(left, right)`
- `listInsert(list, index, value)`
- `listRemove(list, index)`

## Maps

Maps are available through builtins:

```moss
counts = mapNew()
counts = mapPut(counts, "moss", 2)
print(mapGet(counts, "moss", 0))
```

Supported helpers:

- `mapNew()`
- `mapPut(map, key, value)`
- `mapGet(map, key, default)`
- `mapHas(map, key)`
- `mapKeys(map)`
- `mapValues(map)`
- `mapRemove(map, key)`

`Map<K, V>` can be used in signatures and runtime type contracts.

## Branching

`if`, `else if`, and `else` use block bodies:

```moss
fn classify(value: Number) -> Text {
  if value < 0 {
    return "negative"
  } else if value == 0 {
    return "zero"
  } else {
    return "positive"
  }
}
```

## Optional Values

`null` is falsey and can be checked directly:

```moss
item = listGet(tokens, index, null)
if item == null {
  return "EOF"
}
```

`Option<T>` means either `T` or `null` in function signatures:

```moss
fn tokenAt(tokens: List<MossToken>, index: Number) -> Option<MossToken> {
  return listGet(tokens, index, null)
}
```

## Loops

`for` loops iterate over lists:

```moss
let total = 0
for value in [1, 2, 3] {
  total = total + value
}
```

Loop bindings are scoped to the loop body. Assignments to outer variables update
the outer binding, so accumulators work naturally.

`while` loops support `break` and `continue`:

```moss
index = 0
while index < len(chars) {
  if chars[index] == ":" {
    break
  }
  index = index + 1
}
```

## Text

Core text helpers are available as builtins:

- `textChars(text)`
- `textJoin(parts, separator)`
- `textSplit(text, separator)`
- `textTrim(text)`
- `textSlice(text, start, end)`
- `textContains(text, needle)`
- `textIndexOf(text, needle)`
- `textReplace(text, old, new)`
- `textStartsWith(text, prefix)`
- `textEndsWith(text, suffix)`

`textJoin(parts)` uses an empty separator.

## File System

Moss can read and write text files through the `FileSystem` effect:

```moss
effect FileSystem

fn load(path: Text) -> Result<Text, Text> uses FileSystem {
  return Ok(readText(path))
}
```

Available builtins:

- `readText(path)`
- `writeText(path, text)`
- `fileExists(path)`
- `listFiles(path)`
- `pathJoin(parts...)`

## Result flow

`?` unwraps `Ok(value)`. If it sees `Err(error)` inside a function returning
`Result<OkType, ErrType>`, it returns `Err(error)` from that function.

```moss
fn outer() -> Result<Text, Text> {
  value = mightFail()?
  return Ok(value)
}
```

`require condition else error` is the domain-rule sibling of `?`. If the
condition is false inside a `Result` function, Moss returns `Err(error)`.

## Match expressions

`match` keeps state-heavy business logic out of long chains of `if`.

```moss
rule explain(result) =
  match result {
    Ok(order) -> "shipped " + order.id
    Err(ShipError.NotReady(status)) -> "not ready: " + status
    _ -> "unknown"
  }
```

Patterns currently support:

- `_` wildcards
- literal values such as `"paid"` and `42`
- variants such as `Paid`
- payload variants such as `ShipError.NotReady(status)`
- `Ok(value)` and `Err(error)` result patterns
- lowercase binding names

## Effects

The runtime includes two effect-guarded builtins:

- `dbPut(key, value)`
- `dbGet(key)`

Inside a function, both require `uses Database`.

```moss
fn save(order: Order) uses Database {
  dbPut(order.id, order)
}
```

`moss check` catches direct missing effect declarations before execution, and
the runtime enforces the same rule dynamically.

## Type contracts

Function arguments and return values are checked at runtime. For example, if a
function expects `Order`, Moss verifies required fields and their declared
types.

`Result<Order, ShipError>` checks both branches: `Ok(...)` must contain an
`Order`, and `Err(...)` must contain a value matching `ShipError`.

The 0.3 checker also performs conservative static inference. When a type is
known, `moss check` validates local assignments, callable arguments, returns,
record field access, record updates, and union `match` coverage before running
the program. Unknown values remain allowed instead of producing speculative
errors.

Tools and agents can use `moss check --json file.moss` to receive structured
diagnostics with source locations and a declaration summary.

## Self-Hosting Sketches

The `examples/self_host` folder contains the first Moss-written pieces of a
Moss frontend:

- `token_tools.moss` defines structured token records
- `lexer_core.moss` turns source text into tokens
- `tokenizer_sketch.moss` runs the lexer against a Moss file
- `expression_core.moss` parses structured expression AST nodes, including
  precedence, calls, field/index access, lists, records, record updates, and `?`
- `statement_core.moss` parses structured statements such as `let`,
  assignment, `return`, expression statements, `require`, `break`, and
  `continue`
- `parser_core.moss` consumes those tokens into simple top-level AST nodes
  and recursively preserves `if`/`else`, `for`, and `while` bodies
- `parser_sketch.moss` runs the parser against a Moss file
  and summarizes declarations such as `effect`, `type`, `rule`, `fn`, and `test`
- `checker_core.moss` performs the first Moss-written declaration checks
- `checker_sketch.moss` runs those checks against a Moss file
- `project_check.moss` checks the self-hosting Moss files as a small project

Run the fast self-hosting path with:

```powershell
moss selfhost --quick
```

Run the full self-hosting project check with:

```powershell
moss selfhost
```

Compare the host parser and Moss-written parser across the bundled examples:

```powershell
moss selfhost-compare examples
```

Format a Moss file in place, or check formatting without changing it:

```powershell
moss format examples/order.moss
moss format --check examples/order.moss
```

The formatter normalizes block indentation, common expression spacing,
trailing whitespace, and the final newline while preserving strings and
comments.

As of `0.5.0`, the Moss-written checker validates duplicate declarations,
duplicate record fields, import shape, undeclared effects, parse errors, and
simple type references in record fields, function signatures, and rule
signatures. This is the start of self-hosting, not the end state.

The Moss-written parser preserves declaration names and builds structured nodes
for expressions, recursive match patterns, and control-flow statements.
`moss selfhost-compare examples` checks declarations, metadata, recursive
statement shapes, and complete recursive expression and pattern AST
equivalence.

Start a persistent multiline session with:

```powershell
moss repl
```

## Projects and manifests

A Moss project is rooted by `moss.toml`. The manifest names the package,
selects one entry module, and declares source roots used to resolve imports:

```toml
[package]
name = "my-service"
version = "0.1.0"
entry = "src/main.moss"

[paths]
source = ["src", "lib"]
```

Project commands follow the reachable import graph from the entry module:

```powershell
moss project-init my-service
moss project-info my-service
moss project-check my-service
moss project-run my-service
moss project-test my-service
```

The graph is deterministic and rejects missing imports, imports outside the
project root, cycles, and cross-module declaration conflicts. See
`docs/projects.md` for the complete current workflow.

## JSON

`jsonParse(text)` converts JSON objects, arrays, strings, booleans, nulls, and
numbers into ordinary Moss values. JSON numbers become Moss `Number` values.
Malformed input reports a runtime error with its JSON line and column.

`jsonStringify(value)` produces compact JSON with deterministically sorted
object keys. It accepts records, lists, Text, Bool, Number, and null, and
rejects values such as functions, variants, and results that do not have an
unambiguous JSON representation.

```moss
let payload = jsonParse("{\"name\":\"Moss\",\"version\":4}")
print(payload.name)
print(jsonStringify({ version: payload.version, name: payload.name }))
```

## HTTP and the Network effect

HTTP access is an explicit capability. A function must declare `uses Network`
before calling `httpGet(url)` or `httpPostJson(url, value)`:

```moss
effect Network

fn loadStatus(url: Text) -> Text uses Network {
  return httpGet(url)
}

fn publish(url: Text, value: Any) -> Text uses Network {
  return httpPostJson(url, value)
}
```

Both adapters accept only HTTP(S) URLs. `httpPostJson` uses the same
deterministic JSON encoding as `jsonStringify`. Transport failures and
non-success HTTP responses become Moss runtime errors.

## External processes and the Process effect

Process execution is an explicit capability. Commands and arguments are passed
directly to the operating system without a command shell:

```moss
effect Process

fn inspect(command: Text) -> Any uses Process {
  return processRun(command, ["--version"])
}
```

`processRun(command, args, input)` returns a record containing `exitCode`,
`stdout`, and `stderr`. It has a fixed 30-second timeout, runs from the current
Moss source/project directory, and does not invoke a command shell implicitly.
Calling a shell executable explicitly still grants that shell its normal
behavior.

`processRunJson(command, args, value)` sends one deterministic JSON value on
stdin and parses one JSON value from stdout. A nonzero exit code or malformed
JSON response becomes a Moss runtime error.

The `Process` effect makes external execution visible and avoids shell
injection by construction. It is not a sandbox: Moss code granted this effect
can start any executable available to the current user.

## Rule traces

Rules are intended to express inspectable business decisions. `moss trace`
executes a program while recording every rule evaluation:

```powershell
moss trace examples/order.moss
moss trace --json examples/order.moss
```

Each event contains the rule name, formatted arguments, result, and the source
file, line, and column where the rule is declared. Imported rules retain their
own module source map.
