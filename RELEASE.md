# Moss 0.56.0 Release — Saturation Audit Fixes (TAAv2)

Moss `0.56.0` is the second Trust Artifact Alpha snapshot. All 8 vulnerabilities
from the round-2 adversarial audit (saturation attack) have been addressed.

## Round 2 fixes

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| V9 | P0 | Pipe operator parser crash | `self.match_kind("IDENT")` in pipe handler |
| V8 | P0 | LambdaExpr crashes trust pipeline | `render_expr` + `normalize_host_expr` support |
| V10 | P0 | Chain record update VM crash | Result always initialized in `RECORD_UPDATE` |
| V7 | P1 | Null representation mismatch | Selfhost Null unified to `""` |
| V11 | P2 | Type params not validated | `check_param_types()` with warnings |
| V5 | P1 | Arrow-function body boundary | `=` detection skips block parse |
| V6 | P3 | source_sha256 decorative | Round-trip verified (v0.55.0) |

Plus V2/V3/V4 already fixed in v0.55.0.

## Verification

```powershell
python -m pytest tests/test_mosslang.py -q
# 133 passed, 22 subtests

python -m mosslang.cli selfhost-compare examples
# 9/9 comparison passed

python -m mosslang.cli selfhost --quick
# 5/5 sketch tests pass
```

## Known limitations

- Self-host parser: single-line block bodies (`fn f() { expr }`) produce empty statement data — trust correctly reports selfhost mismatch
- Cross-file type resolution: V11 uses warnings for undeclared types, not errors (imported types not resolved)

## Install

```powershell
git clone https://github.com/Fujo930/moss-lang.git
cd moss-lang
git checkout ds-Mosslang
pip install -e .
```

Built by Reasonix for Fujo930.
