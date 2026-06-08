# Moss 0.56.1 Release — V5 + V8 Root-Cause Fix

Moss `0.56.1` fixes the last two reproducible vulnerabilities from the saturation audit:
arrow-function body parsing (V5) and lambda expression support (V8) in the self-host parser.

## Fixed

### V5 — Self-host arrow-function body boundary (High)
**Root cause**: `parseNamedLine` used `lineText` which consumed `{...}` block tokens,
then `advanceToNextLine` skipped past the block entirely. `parseBlockStatements` was
called AFTER the block line, causing it to parse subsequent top-level declarations
as the function body.

**Fix**: Rewrote `parseNamedLine` for Function/Test declarations to parse signature
tokens token-by-token, stopping at `{` (then calling `parseBlockStatements` with
correct state) or `=` (then reading arrow expression). Also strips trailing `}`
from `readLineTokens` output to prevent "unexpected token" errors.

### V8 — Lambda expression support (P0)
**Root cause**: Selfhost lexer classifies `\` as SYMBOL, not LAMBDA. Expression
parser had no handler for `\`.

**Fix**: Added `\` detection in `parsePrimaryExpr` → new `parseLambdaExpr` parses
params up to `->` and body via `parseUpdateExpr`. Added Lambda branch to
`normalize_selfhost_expr` for AST comparison.

## Verification

```powershell
python -m pytest tests/test_mosslang.py -q
# 133 passed, 22 subtests

python -m mosslang.cli selfhost-compare examples
# 9/9 comparison passed

python -m mosslang.cli selfhost --quick
# 5/5 sketch tests pass

python -m mosslang.cli trust audit_tests/v5_arrow_boundary.moss
# trust=true, bodies_match=true

python -m mosslang.cli trust audit_tests/v8_lambda.moss
# trust=true, expressions_match=true
```

## Install

```powershell
git clone https://github.com/Fujo930/moss-lang.git
cd moss-lang
git checkout ds-Mosslang
pip install -e .
```

Built by Reasonix for Fujo930.
