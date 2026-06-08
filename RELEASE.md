# Moss 0.55.0 Release — Trust Artifact Audit Fixes (TAA)

Moss `0.55.0` is the **Trust Artifact Alpha** snapshot. All 6 vulnerabilities
discovered in the adversarial audit (audit-report.md) have been fixed.

## What's fixed

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| V2 | **High** | Rules could silently call effect builtins | Checker now validates `RuleDecl` purity |
| V5 | **High** | Arrow-function bodies ate subsequent declarations | Self-host parser skips block parsing for arrow bodies |
| V1 | Medium | Parse/runtime errors produced no JSON | Global exception guard in `run_trust()` |
| V4 | Medium | Single-file `moss trust` missed lock | Upward directory search for `moss.lock` |
| V6 | Low | `source_sha256` never verified | Round-trip verification on file output |
| V3 | Low | `trace.ok` always mirrored check | Independent rules-vs-events validation |

## Verification

```powershell
python -m pytest tests/test_mosslang.py -q
# 133 passed, 22 subtests

python -m mosslang.cli selfhost-compare examples
# 9/9 comparison passed
```

## Trust bundle improvements

- Bundle always produced — `_error` field on parse/runtime failures
- `trace.rules_declared` / `trace.events_captured` — independent trace signal
- `_hash_verified` — source SHA-256 confirmed on file output

## Install

```powershell
git clone https://github.com/Fujo930/moss-lang.git
cd moss-lang
git checkout ds-Mosslang
pip install -e .
```

Built by Reasonix for Fujo930.
