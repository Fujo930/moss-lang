# Moss projects

Moss `0.4.0-alpha` introduces a manifest-driven project workflow intended for
long-lived codebases maintained by humans and AI agents.

## Create a project

```powershell
moss project-init hello-moss
cd hello-moss
moss project-run .
```

This creates a `moss.toml` manifest and `src/main.moss`.

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
moss project-run .
moss project-test .
```

`project-info` emits a stable, sorted import graph for humans, CI, and AI
agents. `project-check` follows modules reachable from the entry, checks each
module, then checks their declarations together. It reports missing imports,
project-boundary escapes, cycles, and cross-module declaration conflicts.

`project-run` executes the entry module. `project-test` executes every test
reachable through its imports.

## Moss checks Moss

The repository root is itself a Moss project. Its entry is the Moss-written
self-host project checker:

```powershell
moss project-info .
moss project-check .
moss project-test .
```

This does not mean Moss is fully self-hosted. It means the 0.4 project system
now directly describes, checks, and tests the Moss-written frontend.
