# Moss Language Guide

Moss is a programming language for long-lived projects where humans and AI
agents work on the same codebase. This guide covers the language surface as of
v0.13.0.

## Quick tour

```moss
effect Database                          // declare a capability

type Order =                             // domain record
  id: Text
  status: Pending | Paid | Shipped
  total: Money

type ShipError = NotReady | Missing      // simple union

rule canShip(o: Order) -> Bool =         // pure, traceable rule
  o.status == Paid and o.total > 0.usd

fn ship(o: Order) -> Result<Order, ShipError> uses Database {
  require canShip(o)                     // explicit failure path
    else ShipError.NotReady(o.status)
  return Ok(o with status = Shipped)
}
```

## Effects

Effects name capabilities. Functions declare which effects they use. The
compiler enforces that only functions declaring `uses EffectName` can call
effect-guarded builtins.

```moss
effect Database, Network, FileSystem
```

Built-in effect-guarded functions: `dbPut`/`dbGet` (Database),
`httpGet`/`httpPostJson` (Network), `readText`/`writeText`/`fileExists`/
`listFiles` (FileSystem), `processRun`/`processRunJson` (Process).

## Types

### Records

```moss
type Order =
  id: Text
  status: Pending | Paid | Shipped | Cancelled
  total: Money
```

### Simple unions (aliases)

```moss
type ShipError = NotReady | Missing
```

### Built-in types

`Text`, `Bool`, `Number`, `Money` (`42.usd`, `9.99.eur`), `Null`, `List<T>`,
`Map<K, V>`, `Option<T>`, `Result<T, E>`, variant literals (`Paid`,
`ShipError.NotReady(Pending)`).

## Rules

Rules are pure expression functions — no side effects, no effects declaration.
Every rule evaluation is recorded by `moss trace` with arguments, result,
source file, line, and column.

```moss
rule canShip(o: Order) -> Bool =
  o.status == Paid and o.total > 0.usd
```

## Functions

```moss
fn process(o: Order) -> Result<Order, ShipError> uses Database, Network {
  require canShip(o) else Err("not ready")
  // ... body with return, if/else, for, while, etc.
  return Ok(updated)
}

// Arrow body shorthand (single expression)
fn double(x) = x * 2

// Implicit return — last expression is auto-returned
fn add(a, b) { a + b }
```

## Testing

```moss
test "ships paid orders" {
  result = ship(order)?
  assert(result.status == Shipped, "expected shipped status")
}
```

Run with `moss test file.moss`. Test blocks execute after all top-level setup.

## Pattern matching

```moss
match result {
  Ok(order) -> "shipped " + order.id
  Err(ShipError.NotReady(status)) -> "not ready: " + status
  _ -> "unknown"
}
```

Exhaustiveness is checked — all union variants must be covered.

## Result and error propagation

```moss
let value = fallible()?        // ? propagates Err, unwraps Ok
require condition else Err(x)  // explicit guard with custom error
```

## Collections

```moss
let items = [1, 2, 3]          // List
let byId = mapNew()             // Map

// Pipe operator
let result = items |> map(\x -> x * 2) |> filter(\x -> x > 3)

// Lambda
let double = \x -> x * 2
```

## String interpolation

```moss
let name = "Moss"
print(`Hello {name}!`)          // Backtick strings interpolate {expr}
```

## Imports and projects

```moss
import "lib.moss"               // top-level import
```

Projects use `moss.toml` manifests with deterministic `moss.lock` files.

## Trust verification

```powershell
moss trust order.moss           # produces a machine-verifiable JSON bundle
moss trust order.moss -o trust.json
moss trust-project .             # project-wide trust verification
```

Trust bundles combine: static check, rule trace, deterministic output
snapshot, dependency lock verification, and host/self-host parser comparison.

## Moss frontend

```powershell
moss tokens --frontend moss order.moss   # Moss-written lexer
moss check --frontend moss order.moss    # Moss-written checker
moss compile --frontend moss order.moss  # Moss frontend → .mbc
moss run --frontend moss order.moss      # Moss frontend → VM execution
```

The Moss-written lexer, parser, and checker produce output verified
byte-for-byte against the Python host frontend.
