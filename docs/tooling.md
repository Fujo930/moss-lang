# Moss developer tooling

Moss `0.5.0` gives editors, CI, humans, and AI agents shared structured compiler
surfaces.

## Language server

Install the package and configure an editor LSP client to start:

```text
moss-lsp
```

The stdio server supports document synchronization, source-located diagnostics,
document symbols, and full semantic tokens. It uses the same parser and checker
as the CLI and Studio.

## Syntax highlighting

`editors/moss.tmLanguage.json` is a portable TextMate grammar for `.moss`
source. Editors that support TextMate grammars can use it independently or
alongside semantic tokens from `moss-lsp`.

## Golden output

```powershell
moss golden examples/order.moss
moss golden --update examples/order.moss
```

The first command compares program output with `examples/order.moss.golden`.
The update form records an intentional new result. Golden files are plain text
and should be reviewed with source changes.

## Generated documentation

```powershell
moss docs examples/order.moss
moss docs examples/order.moss --output build/order-api.md
```

Generated Markdown includes declared effects, record fields, union variants,
rules, functions, parameters, return types, and function effects.

## Studio

`moss studio` starts the local browser workbench. In addition to checking,
running, and testing source, Studio can inspect declaration symbols, project
graphs, source-mapped traces, and host/self-host comparisons. Its JSON API is
documented in `docs/studio.md` and is intentionally reusable by future clients.
