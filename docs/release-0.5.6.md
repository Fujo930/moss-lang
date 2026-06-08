# Moss 0.5.6 release notes

Moss `0.5.6` completes the VM migration: every Moss command now executes
through the bytecode compiler and stack VM. The tree-walking Runtime
interpreter (`runtime.py`) is no longer used for any CLI, Studio, selfhost,
or REPL execution path.

## All commands on VM

| Command | Engine |
|---------|--------|
| `moss run` | VM ✅ (since 0.5.5) |
| `moss test` | VM ✅ (since 0.5.5) |
| `moss trace` | VM ✅ |
| `moss trace --json` | VM ✅ |
| `moss golden` | VM ✅ |
| `moss project-run` | VM ✅ |
| `moss project-test` | VM ✅ |
| `moss selfhost` | VM ✅ |
| `moss selfhost --quick` | VM ✅ |
| `moss selfhost-compare` | VM ✅ |
| `moss repl` | VM ✅ |
| `moss studio` | VM ✅ |

## VM additions

- `VM.call(func, args)` — call a Moss function from Python host code
- `VM._load_imports` passes through `tests` list from imported modules
- Enhanced `GET_INDEX` error message with list type, length, and function name

## VM `builtin_print` behavior preserved

The VM `builtin_print` appends `\n` to every line (same as 0.5.1–0.5.5).
Studio wraps VM output to strip trailing newlines for its JSON response
format.

## REPL state accumulation

The REPL now accumulates all entered source lines and recompiles the full
program on each submission. This preserves variable definitions across
multiple entries, matching the original Runtime REPL behavior.

## Verification

```powershell
python -m pytest tests/test_mosslang.py -q
# 116 passed, 9 subtests passed

python -m mosslang.cli selfhost --quick
# 5/5 sketch tests pass

python -m mosslang.cli selfhost-compare examples
# all examples pass host/self-host comparison

python -m mosslang.cli project-test --locked .
# 1/1 project tests passed
```

## Removed

- `cli.py` no longer imports `Runtime`

## Upgrade notes

- `.mbc` format unchanged from 0.5.5
- `moss.lock` files are compatible
- No breaking changes to the Moss language
