# Moss 0.6.0 release notes

Moss `0.6.0` introduces **Moss Playground** — a browser-based trust report
viewer. Paste Moss code, click "Trust", and see a green/red verification
report in real time.

This is the first version capable of demonstrating Moss's unique value
proposition — "Trust this AI" — in a single browser window.

## `moss playground`

```powershell
moss playground
# Opens http://127.0.0.1:8766
```

The Playground provides:

- **Code editor** — paste Moss code or upload a `.moss` file
- **Built-in examples** — Order workflow, Match demo, Refund service
- **One-click Trust** — runs the full trust pipeline and displays results
- **Visual report** — green/red gates for Check, Trace, Golden, and Selfhost
- **Trace details** — expandable rule evaluation events with file:line:column
- **Snapshot display** — program output visible inline
- **Selfhost comparison** — host/selfhost declaration diffs on failure

### Deployable frontend

The Playground HTML is a self-contained single page under `playground_assets/`.
It can be deployed to GitHub Pages or any static host. Without a local Moss
backend, the Trust button shows a friendly message directing users to install
Moss.

### `/api/trust` endpoint

The Playground backend exposes a JSON API:

```
POST /api/trust  {"source": "..."}
→  {"trust": true/false, "check": {...}, "trace": {...}, "golden": {...}}
```

This is the same trust pipeline used by `moss trust` on the CLI, now
accessible to web applications.

## Verification

```powershell
python -m pytest tests/test_mosslang.py -q
# 123 passed, 9 subtests passed

python -m mosslang.cli selfhost --quick
# 5/5 sketch tests pass

python -m mosslang.cli trust-project .
# 7/7 files trusted
```

## Upgrade notes

- `.mbc` format unchanged
- `moss.lock` files are compatible
- No breaking changes to the Moss language
- `pip install -e .` picks up the new `playground_assets/` package data
