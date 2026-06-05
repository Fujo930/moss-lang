<p align="center">
  <img src="src/mosslang/studio_assets/moss-mark.svg" width="88" alt="Moss branching M mark">
</p>

# Moss language prototype

![Language: Moss](https://img.shields.io/badge/language-Moss-71d6a2)
![Self-hosting: verified frontend](https://img.shields.io/badge/self--hosting-verified%20frontend-f2c14e)
![Version: 0.4.0-alpha](https://img.shields.io/badge/version-0.4.0--alpha-4f7edb)
![Built by Codex](https://img.shields.io/badge/built%20by-Codex-222222)

Moss is an experimental programming language for long-lived software projects
where humans and AI agents work on the same codebase over time.

This repository is intentionally AI-built: Moss was designed, implemented,
debugged, documented, committed, and pushed by Codex in collaboration with
Fujo930. The project is public as a record of that process and as a runnable
language prototype.

Version `0.4.0-alpha` begins the product-engineering roadmap with project
manifests, deterministic module graphs, project-wide checking, and project
commands. Moss is not fully self-hosted yet, but its Moss-written frontend is
now declared, checked, and tested as a Moss project.

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
moss format --check examples/order.moss
moss selfhost
moss selfhost --quick
moss selfhost-compare examples
moss repl
moss studio
```

You can also run without installing:

```powershell
python -m mosslang.cli run examples/order.moss
```

To build local release artifacts:

```powershell
python -m pip install build
python -m build
```

To build the standalone Windows compiler, Studio, and installer:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1
```

The Windows installer includes its own runtime, adds an optional `moss` PATH
entry, creates Moss Studio shortcuts, and uses `Documents/Moss Workspace` as
the editable Studio workspace.

The package exposes a console command named `moss`.

## What works now

- `effect` declarations
- `type` declarations for records and simple unions
- `rule` declarations as pure expression functions
- `fn` declarations with optional `uses EffectName`
- `test "name" { ... }` blocks for language-level executable checks
- records, record field access, and record updates
- `if`, `else if`, and `else` blocks
- list literals, indexing, `for` loops, `len`, `listPush`, `listGet`,
  `listSet`, `listSlice`, `listConcat`, `listInsert`, `listRemove`, and
  `range`
- `Map<K, V>` through `mapNew`, `mapPut`, `mapGet`, `mapHas`, `mapKeys`,
  `mapValues`, and `mapRemove`
- `while`, `break`, and `continue`
- Text helpers: `textChars`, `textJoin`, `textSplit`, `textTrim`, `textSlice`,
  `textContains`, `textIndexOf`, `textReplace`, `textStartsWith`, and
  `textEndsWith`
- deterministic JSON parsing and serialization through `jsonParse` and
  `jsonStringify`
- `FileSystem` effect builtins: `readText`, `writeText`, `fileExists`, and
  `listFiles`
- top-level `import "path.moss"` declarations
- `moss.toml` manifests, deterministic import graphs, and declared source roots
- deterministic `moss.lock` files with module content hashes
- project initialization, inspection, checking, running, and testing commands
- project-wide checks for missing imports, cycles, and declaration conflicts
- self-hosting sketches with structured token records, reusable lexer/parser
  cores, structured expression and recursive control-flow statement AST nodes,
  a top-level declaration parser, and a first checker sketch:
  `examples/self_host/tokenizer_sketch.moss` and
  `examples/self_host/expression_sketch.moss` and
  `examples/self_host/statement_sketch.moss` and
  `examples/self_host/parser_sketch.moss` and
  `examples/self_host/checker_sketch.moss`
- `moss selfhost`, which runs the tokenizer/parser/checker sketches plus
  `examples/self_host/project_check.moss`; the project check parses and checks
  the self-hosting Moss files with Moss code
- nullary and payload variants such as `Paid` and `ShipError.NotReady(Pending)`
- `match` expressions with wildcard and payload binding patterns
- `Result` values with `Ok(...)`, `Err(...)`, and `?`
- `require condition else value`, which returns `Err(value)` from `Result`
  functions
- runtime type contracts for function arguments and return values
- conservative static inference for local bindings, assignments, calls, returns,
  and list element types
- static record-field access/update checks and exhaustive union `match` checks
- flow-sensitive branch inference and payload-aware union pattern checks
- expression-located diagnostics and complete host/self-host expression AST comparison
- `List<T>`, `Map<K, V>`, and `Option<T>` runtime type contracts
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
moss check --json <file.moss>
moss project-check <directory>
moss project-check --json <directory>
moss project-info <directory>
moss project-info --json <directory>
moss project-lock <directory>
moss project-run <directory>
moss project-test <directory>
moss project-init <directory> [--name <package-name>]
moss run <file.moss>
moss test <file.moss>
moss tokens <file.moss>
moss ast <file.moss>
moss format <file.moss>
moss format --check <file.moss>
moss selfhost
moss selfhost --quick
moss selfhost-compare examples
moss repl
moss studio
```

`moss studio` opens a local HTTP editor at `http://127.0.0.1:8765`.

`moss check --json` emits stable machine-readable diagnostics, source
locations, and a declaration summary for CI, editors, and AI agents.

`moss project-check` recursively checks every `.moss` file in a directory and
returns an aggregate project health result.
When it finds a `moss.toml`, it follows the entry module's reachable import
graph and performs an additional package-wide static check.

`moss project-info` exposes the deterministic module graph for humans, CI, and
AI agents. `moss project-run` and `moss project-test` run the manifest entry
with its declared source roots. `moss project-init` creates a minimal runnable
project.

`moss project-lock` writes the current module graph and SHA-256 source hashes to
`moss.lock`. Use `moss project-check --locked`, `moss project-run --locked`, or
`moss project-test --locked` in CI when project drift must be explicit.

`moss format` normalizes block indentation, expression spacing, trailing
whitespace, and the final newline while preserving strings and comments.
`--check` makes it suitable for CI.

`moss selfhost --quick` runs the fast self-hosting sketches. `moss selfhost`
also runs the slower Moss-written project check over `examples/self_host`.
`moss selfhost-compare examples` compares Python-host and Moss-written parser
declarations, metadata, recursive statement shapes, and complete recursive
expression and match-pattern ASTs across all root example programs.

## Project status

This is version `0.4.0-alpha`: a compact interpreter with real syntax, runtime
semantics, project engineering tooling, a browser editor, and a verified
Moss-written frontend.
The repository is released under the MIT License.

Suitable claims:

- Moss is AI-designed and AI-built.
- Moss can run useful example programs today.
- Moss has begun self-hosting.
- Moss is still alpha software and should not be described as fully self-hosted.

The current 0.4 work continues toward module boundaries, package dependencies,
custom effects, adapters, traces, and frontend replacement.

GitHub's language bar is powered by Linguist. `.moss` files are marked
detectable in `.gitattributes`, but GitHub will only show `Moss` as a first-class
language after Moss is accepted into the upstream Linguist language list.

See `docs/language.md` for the current language surface,
`docs/projects.md` for manifests and project commands,
`docs/studio.md` for the browser editor,
`docs/history.md` for a commit-by-commit feature guide, and
`docs/roadmap.md` for the path from prototype to a serious implementation.
See `docs/release.md` for the public `0.3.0-alpha` release notes and packaging
checklist, and `docs/identity.md` for the Moss identity.
