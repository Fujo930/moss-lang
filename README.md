<p align="center">
  <img src="docs/assets/moss-social-preview.png" width="100%" alt="Moss: Explainable software for humans and AI">
</p>

# Moss language prototype

![Language: Moss](https://img.shields.io/badge/language-Moss-71d6a2)
![Self-hosting: active frontend](https://img.shields.io/badge/self--hosting-active%20frontend-f2c14e)
![Version: 0.7.2](https://img.shields.io/badge/version-0.7.2-4f7edb)
![Built by DeepSeek & Reasonix](https://img.shields.io/badge/built%20by-DeepSeek%20%26%20Reasonix-222222)

Moss is an experimental programming language for long-lived software projects
where humans and AI agents work on the same codebase over time.

This repository is intentionally AI-built: Moss was designed, implemented,
debugged, documented, committed, and pushed by DeepSeek (Codex & Kun) and
Reasonix in collaboration with Fujo930. The project is public as a record of
that process and as a runnable language prototype.

Version `0.7` activates the Moss-written frontend: the lexer, parser, and
checker written in Moss are now selectable compiler frontends via
`--frontend moss`. The host (Python) frontend remains the default and is
used for differential verification. All 9 example programs pass
host/self-host comparison at the token, AST, and bytecode level.

The branching M is Moss's language mark: two contributors meeting in a shared
syntax tree. See `docs/identity.md` for the public description and identity
rules.

## Quick start

From this folder:

```powershell
python -m pip install -e .
moss check examples/order.moss
moss run examples/order.moss
moss test examples/order.moss

# Moss frontend (self-hosted lexer + parser)
moss run --frontend moss examples/order.moss
moss compile --frontend moss examples/order.moss
moss tokens --frontend moss examples/order.moss

# Trust bundles
moss trust examples/order.moss
moss trust-project .

# Browser tools
moss studio       # editor + trust panel (port 8765)
moss playground   # trust report viewer (port 8766)
moss repl         # interactive session
```

## What works now

### Language

- `effect` declarations — named capabilities visible at function boundaries
- `type` declarations for records and simple unions
- `rule` declarations as pure, traceable expression functions
- `fn` declarations with `uses EffectName` — explicit effect tracking
- `test "name" { ... }` blocks for language-level executable checks
- `match` expressions with wildcard and payload binding patterns
- `Result<T, E>` with `Ok(...)`, `Err(...)`, `?` propagation, and `require`/`else`
- records, record field access, and record updates (`with`)
- `List<T>`, `Map<K, V>`, `Option<T>` with full helper builtins
- `while`, `for`, `break`, `continue`, `if`/`else if`/`else`
- `Money` literals (`42.usd`, `9.99.eur`)
- backtick string interpolation `` `Hello {name}!` ``
- `|>` pipe operator, `\x -> expr` lambda, arrow function body `fn f(x) = expr`
- top-level `import "path.moss"` with deterministic import graphs

### Built-in effects

- `Database` — `dbPut` / `dbGet` (in-memory)
- `Network` — `httpGet` / `httpPostJson` (HTTP(S) only, explicit effect gate)
- `FileSystem` — `readText` / `writeText` / `fileExists` / `listFiles`
- `Process` — `processRun` / `processRunJson` (controlled subprocess bridge)

### Compiler & static analysis

- conservative static type inference (locals, branches, list elements)
- exhaustive union `match` checks with payload validation
- flow-sensitive branch merging and record field/update checks
- 32-opcode stack-machine bytecode ISA with `.mbc` binary format
- label-backpatched control flow (if/while/for/match)
- short-circuit `and`/`or` compilation
- source-mapped rule traces (`moss trace --json`)

### Moss-written frontend (`--frontend moss`)

- `moss tokens --frontend moss` — Moss-written lexer, token streams match host
- `moss ast --frontend moss` — Moss-written parser, produces full declaration trees
- `moss check --frontend moss` — Moss-written checker, detects duplicates, unknown types, missing effects
- `moss compile --frontend moss` — full pipeline: Moss lexer → parser → AST → bytecode compiler → `.mbc`
- `moss run --frontend moss` — Moss frontend → bytecode → VM execution
- host/self-host comparison: declarations, names, body statements, metadata, and recursive expression ASTs all verified

### Trust bundles

- `moss trust <file>` — machine-verifiable JSON combining check + trace + golden + lock + selfhost
- `moss trust-project <dir>` — project-wide trust verification
- source SHA-256 cryptographic binding, lock file verification, 5-dimension selfhost comparison
- `moss playground` — browser-based trust report viewer (one-click trust)
- Studio Trust tab — inline trust reports in the editor

### Project system

- `moss.toml` manifests with entry modules and source roots
- deterministic `moss.lock` files with SHA-256 content hashes
- project init, check, run, test, format, lock, and info commands
- import graph validation with cycle detection

### Developer tooling

- `moss-lsp` — stdio language server (diagnostics, symbols, semantic tokens)
- TextMate grammar — `editors/moss.tmLanguage.json`
- `moss studio` — browser editor with run/test/trace/tokens/AST/trust views
- `moss format` — deterministic code formatter with `--check` CI mode
- `moss golden` — deterministic output snapshot testing
- `moss docs` — generated Markdown API references
- `moss repl` — multiline interactive session with state accumulation

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

let name = "Moss"
print(`Hello {name}!`)

let order = { id: "A-100", status: Paid, total: 42.usd }
let shipped = ship(order)?
print("status:", shipped.status)
```

## Commands

```powershell
# Execution
moss run <file.moss> [--frontend host|moss]
moss test <file.moss>
moss compile <file.moss> [--frontend host|moss] [--output file.mbc]

# Inspection
moss check <file.moss> [--json] [--frontend host|moss]
moss tokens <file.moss> [--frontend host|moss]
moss ast <file.moss> [--frontend host|moss]
moss trace <file.moss> [--json]

# Trust
moss trust <file.moss> [--output trust.json]
moss trust-project <directory> [--output project.trust.json]

# Project
moss project-init <dir> [--name <package>]
moss project-check <dir> [--json] [--locked]
moss project-run <dir> [--locked]
moss project-test <dir> [--locked]
moss project-info <dir> [--json]
moss project-lock <dir>
moss project-format <dir> [--check]

# Tooling
moss format <file.moss> [--check]
moss golden <file.moss> [--update]
moss docs <file.moss> [--output <path>]
moss studio [--host HOST] [--port PORT]
moss playground [--host HOST] [--port PORT]
moss repl
moss selfhost [--quick]
moss selfhost-compare <file|dir>
moss-lsp
```

## Project status

This is version `0.7.2`: the Moss-written lexer, parser, and checker are active
as optional compiler frontends via `--frontend moss`. The host (Python)
frontend remains default and serves as the differential-verification baseline.

All commands run on a unified bytecode VM (tree-walking interpreter retired
in 0.5.6). Trust bundles combine static checks, rule traces, golden snapshots,
lock verification, and selfhost comparison into a single cryptographic artifact.

Suitable claims:

- Moss is AI-designed and AI-built by three AIs across 0.1–0.7.
- Moss has an active Moss-written frontend (lexer + parser + checker).
- Moss produces machine-verifiable trust bundles that no other language toolchain can.
- Moss is not fully self-hosted — the bytecode compiler, VM, and CLI still run on Python.
- Moss is alpha software and should not be described as production-ready.

See `docs/history.md` for a commit-by-commit feature guide,
`docs/roadmap.md` for the path from prototype to self-hosting,
`docs/language.md` for the current language surface,
and `docs/identity.md` for the Moss identity.

## Participate

Moss `0.7` is ready for early technical feedback, especially from people
interested in programming-language design, self-hosting, explicit effects,
proof-carrying code, and human/AI software maintenance.

- Read `CONTRIBUTING.md` for approachable first contributions.
- Use GitHub Issues for reproducible bugs, focused proposals, and platform reports.
- Read `docs/ecosystem.md` for the adoption and external-language strategy.
