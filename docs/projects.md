# Moss projects

Moss `0.5.0` includes a manifest-driven project workflow intended for
long-lived codebases maintained by humans and AI agents.

## Create a project

```powershell
moss new hello-moss
cd hello-moss
moss project-run .
```

This creates a `moss.toml` manifest and `src/main.moss`. Templates provide
focused starting points:

```powershell
moss new hello-basic --template basic
moss new approval-rules --template rules
moss new command-tool --template cli
moss new shared-library --template library
```

`moss project-init` remains available as a compatibility alias for the basic
template.

## Manifest

```toml
[package]
name = "hello-moss"
version = "0.1.0"
entry = "src/main.moss"

[paths]
source = ["src"]
```

`package.entry` must be a `.moss` file inside the project. `paths.source`
declares one or more project-contained roots used to resolve imports.

## Commands

```powershell
moss project-info .
moss project-info --json .
moss project-check .
moss project-check --json .
moss project-lock .
moss project-format .
moss project-format --check .
moss project-run .
moss project-test .
```

`project-info` emits a stable, sorted import graph for humans, CI, and AI
agents. `project-check` follows modules reachable from the entry, checks each
module, then checks their declarations together. It reports missing imports,
project-boundary escapes, cycles, and cross-module declaration conflicts.

`project-run` executes the entry module. `project-test` executes every test
reachable through its imports.

`project-format` formats the same reachable module set used by the other
project commands. Unreachable scratch files are left alone. `--check` reports
drift without writing and is suitable for CI.

## Locked projects

```powershell
moss project-lock .
moss project-check --locked .
moss project-run --locked .
moss project-test --locked .
```

`project-lock` writes a deterministic `moss.lock` containing package metadata,
the reachable import graph, and a SHA-256 digest for every module. Locked
commands fail when modules are added, removed, changed, or rewired. This gives
CI and AI agents an explicit signal that the project they inspected is still
the project being checked or executed.

## Moss checks Moss

The repository root is itself a Moss project. Its entry is the Moss-written
self-host project checker:

```powershell
moss project-info .
moss project-check --locked .
moss project-test --locked .
```

This does not mean Moss is fully self-hosted. It means the project system
now directly describes, checks, and tests the Moss-written frontend.
