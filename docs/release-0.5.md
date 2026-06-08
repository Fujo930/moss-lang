# Moss 0.5.x release notes

Moss `0.5.0` completes the first editor and developer-experience milestone.
`0.5.1`–`0.5.4` (ds-Mosslang fork by DeepSeek) add token-efficient syntax
features for AI code generation, critical VM bugfixes, and full self-host
project support.

## 0.5.4 (current)

### New syntax features

| Version | Feature | Before | After |
|---------|---------|--------|-------|
| 0.5.1 | Implicit return | `fn f(x) { return x+1 }` | `fn f(x) { x+1 }` |
| 0.5.2 | Pipe operator | `g(f(a))` | `a \|> f \|> g` |
| 0.5.3 | Lambda | `fn tmp(x) { return x+1 }` | `\x -> x+1` |
| 0.5.4 | Arrow body | `fn f(x) { x+1 }` | `fn f(x) = x+1` |

### Bugfixes

- **Import support**: VM now loads and merges imported `.moss` modules at runtime
- **For-loop `continue`**: no longer causes infinite loops
- **`.mbc` deserialization**: `moss run-vm foo.mbc` no longer misroutes to the text parser
- **Float-safe builtins**: `textSlice`, `listSlice`, `listGet` accept float indices
- **`null` as valid value**: `LOAD_LOCAL` no longer treats `None` as undefined
- **Self-host project**: `project_check.moss` runs with 0 errors, 0 warnings

### Tests

```powershell
python -m pytest tests/test_mosslang.py -q
# 108 passed, 9 subtests passed
```

## 0.5.0 (baseline)

- stdio language server with diagnostics, symbols, and semantic tokens
- TextMate syntax-highlighting grammar
- golden output checking and updating
- generated Markdown API and schema documentation
- Studio symbols, project graph, trace, and host/self-host controls
- deterministic project graphs, lock files, JSON and HTTP adapters
- source-mapped rule traces

## Install

```powershell
python -m pip install .
moss check examples/order.moss
moss golden examples/order.moss
moss docs examples/order.moss
moss selfhost --quick
moss run-vm examples/order.moss        # run via bytecode VM
moss run-vm examples/order.mbc         # run compiled binary
```

## Honest status

- Moss is AI-designed and AI-built by Codex (ds-Mosslang fork by DeepSeek) in collaboration with Fujo930.
- Moss can execute useful programs and support project-scale workflows.
- Moss has a working self-host loop: Moss code checks Moss code.
- Moss remains experimental software.
