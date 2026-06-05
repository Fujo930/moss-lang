# Moss commit history

This file explains the repository history in human terms. The Git commit
messages stay short; this document gives future readers the memory behind them.

Moss is AI-designed and AI-built. Codex designed, implemented, debugged,
documented, committed, and pushed the current language prototype in
collaboration with Fujo930. This history is intentionally part development log,
part memory for future AI agents and human contributors.

## 0.4.0-alpha project foundation

Moss now supports `moss.toml` package manifests, deterministic reachable import
graphs, declared source roots, and project initialization, inspection,
checking, running, and testing commands. Project checks reject missing imports,
project-boundary escapes, cycles, and cross-module declaration conflicts.

The repository root is now a Moss project whose entry is the Moss-written
self-host project checker. The first project-wide check exposed and fixed a
real duplicate global helper in the self-host frontend.

Why it matters: Moss can now reason about a codebase as a project rather than
as isolated files, and its own Moss-written compiler work is the first real
consumer of that model.

## 0.3.0-alpha static confidence

The static checker now merges local types learned independently by both sides
of a complete `if`/`else`, while refusing to assume a type when the branches
disagree.

Why it matters: compiler code commonly initializes a value before branching.
Moss can now retain that value's proven type after control flow rejoins.

Union matches now reject variants outside the subject union, validate payload
pattern counts when the alias declares them, and warn about cases made
unreachable by an earlier catch-all.

Why it matters: exhaustive matching is only trustworthy when every accepted
case actually belongs to the union and can bind the payload it claims.

The Moss-written expression frontend now parses structured match expressions
and recursive patterns. `selfhost-compare` renders every host expression,
parses it through the Moss frontend, and compares the complete recursive AST,
including match patterns.

Why it matters: declaration counts and statement shapes can hide parser
disagreements. Expression equivalence makes the self-host frontend a much
stronger candidate for replacing the Python frontend.

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

## 0.2.0 self-hosting preview

Recent work moved Moss from "has sketches" to "can check its self-hosting
folder as a project":

- the self-host parser now captures top-level imports, effects, types, rules,
  functions, tests, lets, record field names, and record field type text
- the self-host checker now reports duplicate declarations, duplicate tests,
  duplicate imports, duplicate effects, duplicate record fields, malformed
  import paths, parse errors, undeclared effects, and unknown simple type
  references
- function and rule signatures are checked for unknown parameter and return
  types
- `moss selfhost --quick` runs the fast tokenizer/parser/checker sketches
- `moss selfhost` also runs `project_check.moss`, which uses Moss code to check
  the self-hosting Moss files with a project-wide type-name table
- the self-host parser ignores braces inside string tokens when tracking block
  depth
- `textIndexOf` and `textReplace` were added so Moss compiler code can do less
  awkward text processing

Why it matters: Moss is not fully self-hosted, but the repository now contains a
working loop where Moss code reads and checks Moss code. That is the first real
self-hosting foothold.

## Structured self-host AST and comparison

The Moss-written frontend now builds structured expression nodes for literals,
operators, calls, field/index access, `?`, lists, records, and record updates.
It also builds simple statement nodes for `let`, assignment, `return`, calls,
and `require`, and attaches those nodes to parsed function bodies.

`moss selfhost-compare examples` now compares declaration counts and names from
the Python host parser and Moss-written parser across every bundled root
example.

Why it matters: self-hosting progress is no longer measured only by whether a
sketch runs. The repository now has an executable equivalence gate that can be
made stricter as the Moss AST grows.

## Current direction

The next self-hosting milestones are:

- parse recursive control flow and match expressions into structured AST nodes
- compare full Moss-written AST output against the Python host frontend
- gradually replace host pieces only after the Moss version is tested

## Language identity and Studio refresh

Added the branching M as Moss's reusable language mark, documented the public
identity, and refreshed Studio around the same green, gold, blue, and ink
palette. Studio now groups commands by purpose, exposes its preview status,
counts diagnostics, uses the mark as its favicon, and has clearer accessible
labels.

Why it matters: Moss now has a recognizable public face without hiding its
alpha status, and the editor remains focused on repeated programming work.

## Recursive self-host control flow

The Moss-written parser now recursively retains `if`/`else`, `for`, and `while`
bodies, including structured `break` and `continue` statements. The
`selfhost-compare` gate now compares recursive statement-kind counts inside
every bundled function and test body, in addition to declarations and names.

Why it matters: two parsers can agree on declarations while disagreeing on the
programs inside them. Moss now tests a deeper and more useful layer of
self-hosting equivalence.

## Located diagnostics and formatter

Checker diagnostics now carry structured line and column locations through the
CLI and Studio. Studio diagnostics can move the cursor directly to the reported
declaration. Added conservative `moss format` and `moss format --check`
commands that preserve comments and tokens while normalizing block indentation
and whitespace.

Why it matters: static confidence needs findings that lead back to source, and
long-lived human/AI projects need one repeatable formatting gate.

## Conservative static type environment

Added static inference for local bindings, assignments, list operations,
callable arguments, and returns. Known record types now reject missing fields
and invalid record updates before execution. Union matches report missing
variants and duplicate cases.

Why it matters: Moss now catches useful domain-model mistakes without requiring
every intermediate value to carry an annotation or pretending unknown values
are errors.

## Declaration metadata equivalence

The host/self-host comparison now checks record fields, aliases, callable
parameters, return types, and declared effects in addition to names and
recursive statement shapes.

Why it matters: the Moss-written frontend must preserve the contracts that
tools, checkers, and future code generation depend on, not merely recognize
that a declaration exists.
