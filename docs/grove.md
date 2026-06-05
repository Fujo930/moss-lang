# Moss Grove

Moss Grove is the planned Moss-native development environment. It will be a
separate, public, MIT-licensed open-source repository at
`github.com/Fujo930/moss-grove`.

Grove is planned for the 0.10 milestone after Moss has a stable self-host
frontend, a small native runtime, and usable window and editor APIs. The
repository should be created during 0.8 when those contracts have executable
implementations; creating an empty repository earlier would imply progress that
does not yet exist.

## Purpose

Grove is both a useful editor and an architectural test. It must prove that Moss
can build and maintain a substantial native application over a long lifetime.

It is not intended to replace every editor surface:

- Moss Studio remains the lightweight browser playground.
- The VS Code extension remains the easiest path for existing editor users.
- Moss Grove becomes the complete Moss-native environment.

## Architecture

```text
Moss Grove
  Moss: editor model, commands, project workflows, extensions, UI behavior
  C platform layer: windows, rendering, input, clipboard, file watching, OS APIs
  Moss compiler and LSP: analysis, refactoring, execution, tests, and traces
```

Grove must not require a browser, Electron, Node, or Python for normal use.
Python and Node remain optional external ecosystems accessed through explicit
Moss bindings.

## Repository boundary

The `moss-lang` repository owns:

- language syntax and semantics
- compiler, VM, standard library, and LSP
- shared editor, debugging, trace, and extension protocols

The `moss-grove` repository owns:

- native editor application and user experience
- Grove-specific extensions and release artifacts
- Grove issues, roadmap, and contributor community

Shared protocols must be versioned and documented so other editors can use them
without depending on Grove internals.

## Initial release requirements

- multi-file editing, tabs, project navigation, search, and command palette
- completion, diagnostics, navigation, rename, formatting, and testing
- source-mapped debugging and rule traces
- effect, type, module, and call-graph inspection
- stable plugin API and structured automation commands
- Windows, macOS, and Linux release artifacts
- daily development of Moss itself is practical inside Grove
