# Moss language prototype

Moss is an experimental product-engineering language focused on readable domain
logic, explicit effects, and long-lived code. This repository is a runnable
prototype: it parses Moss source, checks declarations, and interprets a useful
subset of the language.

## Quick start

From this folder:

```powershell
python -m pip install -e .
moss check examples/order.moss
moss run examples/order.moss
moss test examples/order.moss
moss studio
```

You can also run without installing:

```powershell
python -m mosslang.cli run examples/order.moss
```

## What works now

- `effect` declarations
- `type` declarations for records and simple unions
- `rule` declarations as pure expression functions
- `fn` declarations with optional `uses EffectName`
- `test "name" { ... }` blocks for language-level executable checks
- records, record field access, and record updates
- list literals, indexing, `for` loops, `len`, `listPush`, and `range`
- `Map<K, V>` through `mapNew`, `mapPut`, `mapGet`, `mapHas`, `mapKeys`,
  `mapValues`, and `mapRemove`
- `while`, `break`, and `continue`
- Text helpers: `textChars`, `textJoin`, `textSplit`, `textTrim`, `textSlice`,
  `textContains`, `textStartsWith`, and `textEndsWith`
- `FileSystem` effect builtins: `readText`, `writeText`, `fileExists`, and
  `listFiles`
- top-level `import "path.moss"` declarations
- a first self-hosting sketch: `examples/self_host/tokenizer_sketch.moss`
- nullary and payload variants such as `Paid` and `ShipError.NotReady(Pending)`
- `match` expressions with wildcard and payload binding patterns
- `Result` values with `Ok(...)`, `Err(...)`, and `?`
- `require condition else value`, which returns `Err(value)` from `Result`
  functions
- runtime type contracts for function arguments and return values
- `List<T>` runtime type contracts
- a tiny in-memory database through `dbPut` and `dbGet`, guarded by the
  `Database` effect inside functions

## Example

```moss
effect Database

type Order =
  id: Text
  status: Pending | Paid | Shipped | Cancelled
  total: Money

type ShipError = NotReady | Missing

rule canShip(order: Order) -> Bool =
  order.status == Paid and order.total > 0.usd

fn ship(order: Order) -> Result<Order, ShipError> uses Database {
  require canShip(order)
    else ShipError.NotReady(order.status)

  updated = order with status = Shipped
  dbPut(order.id, updated)

  return Ok(updated)
}

let order = { id: "A-100", status: Paid, total: 42.usd }
let shipped = ship(order)?
print("status:", shipped.status)
print("stored:", dbGet("A-100").status)
```

## Commands

```powershell
moss check <file.moss>
moss run <file.moss>
moss test <file.moss>
moss tokens <file.moss>
moss ast <file.moss>
moss studio
```

`moss studio` opens a local HTTP editor at `http://127.0.0.1:8765`.

## Project status

This is version 0.1: a compact interpreter with real syntax and runtime
semantics. The next useful steps are a static type checker, module imports, and
a browser playground.

See `docs/language.md` for the current language surface,
`docs/studio.md` for the browser editor, and
`docs/roadmap.md` for the path from prototype to a serious implementation.
