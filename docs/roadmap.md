# Moss roadmap

Moss is an AI-designed and AI-built language prototype. Codex has designed,
implemented, repaired, documented, committed, and pushed the current repository
in collaboration with Fujo930.

## Version 0.1: executable sketch

Implemented:

- tokenizer, parser, AST, interpreter
- `effect`, `type`, `rule`, and `fn`
- record values and record updates
- variants and namespaced variants
- `Result`, `?`, and `require`
- `match` expressions
- top-level `test` blocks and `moss test`
- lists, indexing, `for` loops, and list helper builtins
- `Map<K, V>` and map helper builtins
- `while`, `break`, `continue`, and `else if`
- Text helpers and `FileSystem` effect builtins
- top-level file imports
- `Option<T>` type contracts and safe list helpers
- first Moss-written tokenizer sketch with structured token records
- first Moss-written line parser sketch
- first Moss-written checker sketch
- effect checking for the built-in database capability
- runtime type contracts
- CLI commands: `check`, `run`, `tokens`, `ast`
- browser editor through `moss studio`
- tests and examples

## Version 0.2: self-hosting preview

Implemented:

- `moss selfhost --quick` for fast self-hosting smoke checks
- `moss selfhost` for the full Moss-written self-host project check
- Moss-written project checker with project-wide type-name collection
- structured Moss-written expression and simple statement AST parsers
- host/self-host declaration count and name comparison across bundled examples
- self-host checker coverage for duplicate declarations, duplicate record
  fields, import paths, parse errors, undeclared effects, record field types,
  function parameter and return types, and rule parameter and return types
- text helpers needed by compiler code: `textIndexOf` and `textReplace`
- release metadata for a public alpha package as `0.2.0`
- branching M language identity and a refreshed, denser Moss Studio

This version is public-ready as an alpha. It should be described as
"self-hosting started" or "self-hosting preview", not "fully self-hosted".

## Version 0.3: static confidence

Implemented:

- recursive Moss-written `if`/`else`, `for`, and `while` statement AST nodes
- structured `break` and `continue` statements in the Moss-written frontend
- host/self-host recursive function and test body statement-shape comparison

High-value next steps:

- structured match-pattern comparison
- compare complete Moss-written AST output against the Python host frontend
- static type inference for local bindings
- static field checks for records
- exhaustive checks for union variants
- richer diagnostic locations for parser and checker errors
- formatter command
- multiline REPL

## Version 0.4: product engineering workflow

Make Moss feel like a language for real systems:

- module imports
- package manifests
- schema migration declarations
- effect definitions with custom capabilities
- JSON and HTTP adapters
- source maps for rule evaluation traces

## Version 0.5: editor and playground

Developer experience:

- syntax highlighting grammar
- language server diagnostics
- source-located Studio diagnostics and host/self-host comparison controls
- hosted browser playground built from the local Studio API shape
- test runner with golden output files
- generated API and schema docs

## Research track

The bigger language questions:

- Can business rules compile to explainable traces by default?
- Can schema evolution be represented as first-class code?
- Can effects stay explicit without creating annotation fatigue?
- Can concurrency be structured around product workflows rather than raw tasks?
