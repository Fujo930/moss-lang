# Moss 0.5.0 release notes

Moss `0.5.0` completes the first editor and developer-experience milestone.
The language remains a self-hosting preview: the active host compiler is still
Python, while Moss-written frontend stages are checked, tested, and compared
against it.

## Highlights

- stdio language server with diagnostics, symbols, and semantic tokens
- TextMate syntax-highlighting grammar
- golden output checking and updating
- generated Markdown API and schema documentation
- Studio symbols, project graph, trace, and host/self-host controls
- deterministic project graphs, lock files, JSON and HTTP adapters, and
  source-mapped rule traces from the completed 0.4 milestone

## Install

```powershell
python -m pip install .
moss check examples/order.moss
moss golden examples/order.moss
moss docs examples/order.moss
moss selfhost --quick
```

## Build artifacts

```powershell
python -m pip install build
python -m build
powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1
```

## Release verification

```powershell
python -m unittest discover -s tests -q
python -m mosslang.cli project-format --check .
python -m mosslang.cli project-check --locked .
python -m mosslang.cli project-test --locked .
python -m mosslang.cli selfhost --quick
python -m mosslang.cli selfhost-compare examples
python -m mosslang.cli golden examples/order.moss
```

## Honest status

- Moss is AI-designed and AI-built by Codex in collaboration with Fujo930.
- Moss can execute useful programs and support project-scale workflows.
- Moss has begun self-hosting, but is not fully self-hosted.
- Moss remains experimental software.
