# Moss 0.5.7 release notes

Moss `0.5.7` introduces `moss trust`, the first step toward proof-carrying AI
code. A single command produces a machine-verifiable JSON bundle combining:

- **Static check** — type and effect diagnostics with source locations
- **Rule trace** — every `rule` evaluation with arguments, result, file, line, and column
- **Golden snapshot** — deterministic output comparison against `.golden` files
- **Self-host comparison** — host (Python) vs self-host (Moss) parser equivalence

## `moss trust` command

```powershell
moss trust examples/order.moss
moss trust examples/order.moss --output trust.json
```

Exit code `0` means all checks passed (`"trust": true`). Exit code `1` means
at least one check failed.

### Trust bundle structure

```json
{
  "moss": "0.5.7",
  "file": "examples/order.moss",
  "trust": true,
  "check": {
    "ok": true,
    "diagnostics": [],
    "summary": { "effects": 1, "imports": 0, "types": 2, "callables": 2, "tests": 1 }
  },
  "trace": {
    "ok": true,
    "events": [{ "rule": "canShip", "arguments": {...}, "result": "true", ... }]
  },
  "golden": {
    "ok": true,
    "snapshot": "status: Shipped\nstored: Shipped\n"
  },
  "selfhost": {
    "ok": true
  }
}
```

### Trust semantics

- `"trust": true` — all four gates passed: check has no errors, trace ran,
  golden matches, selfhost comparison passed
- `"trust": false` — at least one gate failed. The bundle still includes
  partial results so failures can be diagnosed
- `"golden": {"ok": null}` — the program has no `.golden` file; it's not a
  failure, just an unchecked dimension

## Why this matters

No other programming language toolchain produces a single artifact that
combines static analysis, runtime trace, deterministic output verification,
and compiler integrity proof. When an AI generates Moss code, `moss trust`
answers: "Can I prove this code does what it claims?"

This is the foundation for `moss trust` becoming a standard that other tools
and editors can consume.

## Verification

```powershell
python -m pytest tests/test_mosslang.py -q
# 118 passed, 9 subtests passed

python -m mosslang.cli selfhost --quick
# 5/5 sketch tests pass

python -m mosslang.cli trust examples/order.moss
# {"trust": true, ...}
```

## Upgrade notes

- `.mbc` format unchanged from 0.5.6
- `moss.lock` files are compatible
- No breaking changes to the Moss language
