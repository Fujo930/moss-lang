# Release notes

## 0.2.0 alpha

Moss `0.2.0` is the first public-ready self-hosting preview.

Public description:

> Moss is an AI-designed and AI-built programming language prototype for
> long-lived AI-and-human software projects. It can run Moss programs today and
> has begun self-hosting with Moss-written lexer, parser, checker, and project
> check sketches.

Use this wording carefully:

- Good: "AI-designed and AI-built by Codex in collaboration with Fujo930."
- Good: "self-hosting preview" or "self-hosting started."
- Good: "Moss code now reads and checks Moss code."
- Avoid: "fully self-hosted."
- Avoid: "production ready."

The release also introduces the branching M language mark and a refreshed Moss
Studio. The mark, colors, and supported public wording are documented in
`docs/identity.md`.

## Install from the repository

```powershell
python -m pip install -e .
moss check examples/order.moss
moss run examples/order.moss
moss test examples/order.moss
moss selfhost --quick
```

## Build local artifacts

```powershell
python -m pip install build
python -m build
```

The build command creates a source distribution and wheel under `dist/`.

## Release checklist

- `python -m unittest discover -s tests -v`
- `python -m mosslang.cli selfhost --quick`
- `python -m mosslang.cli selfhost`
- `python -m build`

## Current limitations

- The host interpreter, parser, and CLI are still Python.
- The Moss-written frontend is a checked self-hosting sketch, not the active
  compiler frontend.
- The self-host parser currently focuses on top-level declarations and simple
  signature/type metadata, plus structured expressions and simple statements.
- Diagnostics are useful but still early.
- GitHub will not show `Moss` as a first-class language until Linguist adds it.

## Included developer surfaces

- CLI checking, running, testing, token inspection, and AST inspection
- host/self-host declaration comparison across bundled examples
- Moss Studio with workspace-relative open/save, examples, live checking,
  execution, tests, diagnostics, AST, and tokens
