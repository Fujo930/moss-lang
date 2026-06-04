# Moss language notes

This document describes the syntax and semantics implemented by the current
prototype.

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
print(len(names))
print(range(1, 4))
```

`List<T>` can be used in function signatures:

```moss
fn count(items: List<Text>) -> Number {
  return len(items)
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
