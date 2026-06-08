# Moss 0.7.3 Release

Moss `0.7.3` is the first release with an **active Moss-written frontend**.
The lexer, parser, and checker written in Moss are selectable via `--frontend moss`
on `tokens`, `ast`, `check`, `compile`, and `run` commands. The host (Python)
frontend remains the default and serves as the differential-verification baseline.

## What's new since 0.5.0

### Active Moss frontend (0.7 series)
- `moss tokens --frontend moss` — Moss-written lexer, token streams match host
- `moss ast --frontend moss` — Moss-written parser, full declaration trees
- `moss check --frontend moss` — Moss-written checker with diagnostics
- `moss compile --frontend moss` — Moss frontend → bytecode → .mbc
- `moss run --frontend moss` — Moss frontend → compiler → VM execution
- 6/9 example programs produce identical runtime output via Moss frontend

### Trust bundles (0.5.7–0.5.8)
- `moss trust <file>` — machine-verifiable JSON bundle (check + trace + golden + lock + selfhost)
- `moss trust-project <dir>` — project-wide trust verification
- Source SHA-256 binding, lock verification, 5-dimension selfhost comparison

### VM unification (0.5.5–0.5.6)
- All 12 commands run on a unified bytecode VM
- Tree-walking interpreter retired
- 32-opcode stack-machine ISA with .mbc binary format

### Moss Playground (0.6.0)
- `moss playground` — browser-based trust report viewer (port 8766)
- Built-in examples, file upload, one-click Trust

### Studio refresh (0.6.1–0.6.2)
- Complete visual refresh: Moss dark theme
- Trust tab with five-gate verification report
- Ctrl+Enter run, Ctrl+S save, clickable diagnostics

### Backtick interpolation (0.5.5)
- `` `Hello {name}!` `` with multiline support and escape sequences
- `|>` pipe operator, `\x -> expr` lambda, arrow function body `fn f(x) = expr`

## Install

### From source (requires Python 3.12+)
```powershell
git clone https://github.com/Fujo930/moss-lang.git
cd moss-lang
git checkout ds-Mosslang
pip install -e .
```

### Windows standalone (no Python required)
Download `Moss-0.7.3-Windows-Portable.zip` or `Moss-0.7.3-Windows-Setup.exe`
from the [Releases page](https://github.com/Fujo930/moss-lang/releases/tag/v0.7.3).

## Verification

```powershell
python -m pytest tests/test_mosslang.py -q
# 129 passed, 18 subtests

python -m mosslang.cli selfhost --quick
# 5/5 sketch tests pass

python -m mosslang.cli selfhost-compare examples
# all examples pass host/self-host comparison

python -m mosslang.cli trust-project .
# 7/7 files trusted
```

## Known limitations

- Moss frontend: For/While/If statement bodies not captured by Moss statement parser
  (affects lists_demo, map_demo, text_fs_demo via `--frontend moss`)
- Windows-only installer (macOS/Linux support planned for 0.8)
- No typed Python FFI yet (planned 0.8)

## Commands

```
moss run/check/test/tokens/ast/trace/compile [--frontend host|moss]
moss trust/trust-project
moss studio/playground/repl
moss golden/docs/format
moss selfhost/selfhost-compare
moss project-check/run/test/init/info/lock/format
moss-lsp
```

Built by DeepSeek (Codex & Kun) and Reasonix in collaboration with Fujo930.
