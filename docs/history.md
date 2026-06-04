# Moss commit history

This file explains the repository history in human terms. The Git commit
messages stay short; this document gives future readers the memory behind them.

## efeb3d1 Initial Moss language prototype

Started the executable Moss prototype: a tokenizer, parser, AST, interpreter,
CLI commands, domain records, variants, `Result`, `require`, `?`, `match`, and a
small effect-guarded database capability.

Why it matters: this made Moss a runnable language instead of only a design
idea. The first useful domain workflow is `examples/order.moss`.

## 0779a66 Add Moss test blocks

Added top-level `test "name" { ... }` blocks and `moss test`.

Why it matters: Moss programs can carry executable checks beside the code they
exercise. This is the first piece of a real developer workflow.

## c854978 Add lists and for loops

Added list literals, indexing, `for` loops, `len`, `listPush`, `range`, and
`List<T>` runtime contracts.

Why it matters: Moss can now express collection workflows, which are required
for source processing, parsers, checkers, and most business logic.

## 63d3977 Add text and filesystem primitives

Added `while`, `break`, `continue`, text helpers, and the `FileSystem` effect
with `readText`, `writeText`, `fileExists`, and `listFiles`.

Why it matters: Moss can read real files and process text. This opened the path
to Moss reading Moss source code.

## 00bbb6b Add map primitives

Added `Map<K, V>` runtime contracts and map helpers: `mapNew`, `mapPut`,
`mapGet`, `mapHas`, `mapKeys`, `mapValues`, and `mapRemove`.

Why it matters: maps are the natural structure for symbol tables, counters,
indexes, and future compiler environments.

## a9cbc2b Add file imports

Added top-level `import "path.moss"` declarations and relative import
resolution. The CLI and runtime now carry a base path for imports.

Why it matters: Moss programs can be split into modules. Self-hosting code can
be organized as reusable library files instead of one large script.

## 8879e95 Add tokenizer self-hosting sketch

Added the first Moss-written tokenizer sketch under `examples/self_host`.

Why it matters: this is the first actual step toward Moss writing Moss. It
proved Moss could read a `.moss` file and tokenize it from Moss code.

## 7184878 Add structured self-hosting tokens

Upgraded the tokenizer sketch from plain string labels to structured token
records with `kind`, `value`, `line`, and `column`. Added `Option<T>`,
`listGet`, `listSet`, and better string escape support.

Why it matters: a real parser needs structured tokens and safe lookahead. This
commit made the self-hosting path more than a demo.

## 1e9d142 Add self-hosting parser sketch

Added `parser_sketch.moss`, a Moss-written line parser that consumes tokens and
produces simple AST-like nodes.

Why it matters: Moss moved from lexing Moss source to parsing Moss source.

## 05a7433 Expand self-hosting parser summary

Extended the parser sketch so it recognizes and summarizes top-level
declarations: `effect`, `type`, `rule`, `fn`, `test`, `let`, and imports.

Why it matters: the Moss-written parser began understanding the shape of Moss
programs, not only individual lines.

## 8d232c5 Add else-if branches

Added `else if` syntax to the host parser and interpreter behavior.

Why it matters: parser and checker code naturally has many branches. `else if`
makes Moss code much easier to write and read.

## cc8c605 Add Studio workspace file saving

Added workspace-relative open/save APIs to Moss Studio, with path sandboxing so
the editor only reads and writes inside the repository. The browser editor now
supports saving directly back into project files.

Why it matters: Studio became an actual local editing surface for Moss source,
not just a scratchpad.

## 56ce024 Add list editing helpers

Added immutable list helpers: `listSlice`, `listConcat`, `listInsert`, and
`listRemove`.

Why it matters: parsers and AST transforms need list editing constantly. These
helpers make future Moss-written compiler code cleaner.

## d5b83dc Show imports in summaries

Updated CLI and Studio summaries to include import counts.

Why it matters: modules are now visible in tooling output, which helps users
understand what a file contains at a glance.

## 7d4f8a6 Split self-hosting parser core

Split the Moss-written parser into a reusable `parser_core.moss` and a thin
`parser_sketch.moss` example runner.

Why it matters: the self-hosting frontend now has a library shape. Future Moss
checker and parser work can import the core instead of depending on a demo file.

## Current direction

The next self-hosting milestones are:

- parse real Moss expressions into structured AST nodes
- build a Moss-written checker sketch over the parsed declarations
- compare Moss-written frontend output against the Python host frontend
- gradually replace host pieces only after the Moss version is tested
