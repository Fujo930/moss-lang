# Moss roadmap

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

## Version 0.2: static confidence

High-value next steps:

- static type inference for local bindings
- static field checks for records
- exhaustive checks for union variants
- richer diagnostic locations for parser and checker errors
- formatter command
- multiline REPL

## Version 0.3: product engineering workflow

Make Moss feel like a language for real systems:

- module imports
- package manifests
- schema migration declarations
- effect definitions with custom capabilities
- JSON and HTTP adapters
- source maps for rule evaluation traces

## Version 0.4: editor and playground

Developer experience:

- syntax highlighting grammar
- language server diagnostics
- browser playground
- test runner with golden output files
- generated API and schema docs

## Research track

The bigger language questions:

- Can business rules compile to explainable traces by default?
- Can schema evolution be represented as first-class code?
- Can effects stay explicit without creating annotation fatigue?
- Can concurrency be structured around product workflows rather than raw tasks?
