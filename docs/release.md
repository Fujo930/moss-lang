# Release notes

## 0.6.0

Moss `0.6.0` introduces the Playground: a browser-based trust report viewer.
Paste Moss code, click Trust, see the result. See `docs/release-0.6.0.md`.

## 0.5.8

Moss `0.5.8` hardens the trust bundle with source hashes, lock verification,
selfhost comparison details, and `moss trust-project`. See `docs/release-0.5.8.md`.

## 0.5.7

Moss `0.5.7` introduces `moss trust`, which produces a machine-verifiable
JSON bundle combining static check, rule trace, golden snapshot, and
host/self-host comparison. See `docs/release-0.5.7.md` for details.

## 0.5.6

Moss `0.5.6` unifies the CLI execution engine: `run`, `test`, `trace`,
`golden`, `project-run`, `project-test`, and `selfhost` all run on the
bytecode VM. See `docs/release-0.5.6.md` for details.

## 0.5.5

Moss `0.5.5` adds backtick string interpolation and switches `moss run` and
`moss test` to the bytecode VM. See `docs/release-0.5.5.md` for details.

## 0.3.0-alpha

Moss `0.3.0-alpha` completes the static-confidence roadmap and provides a
verified Moss-written frontend preview.

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
moss selfhost-compare examples
moss repl
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
- `python -m mosslang.cli selfhost-compare examples`
- `python -m mosslang.cli project-check examples`
- `python -m build`

## Current limitations

- The host interpreter, parser, and CLI are still Python.
- The Moss-written frontend is a checked self-hosting sketch, not the active
  compiler frontend.
- The verified Moss frontend is not yet wired in as the default compiler
  frontend.
- Static inference remains intentionally conservative.
- GitHub will not show `Moss` as a first-class language until Linguist adds it.

## Included developer surfaces

- CLI checking, running, testing, token inspection, and AST inspection
- host/self-host declaration comparison across bundled examples
- Moss Studio with workspace-relative open/save, examples, live checking,
  execution, tests, diagnostics, AST, and tokens
