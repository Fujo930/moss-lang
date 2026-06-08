# Moss 0.5.8 release notes

Moss `0.5.8` deepens the trust bundle with cryptographic integrity, dependency
verification, and detailed self-host comparison diagnostics. A new
`moss trust-project` command extends trust verification to entire projects.

## Trust bundle enhancements

### Source hash

Every trust bundle now includes `source_sha256` — the SHA-256 hash of the
source file. This cryptographically binds the trust bundle to the exact
source it verifies.

```json
{
  "source_sha256": "dad1930f601b44ec...",
  ...
}
```

### Lock verification

When `moss.lock` and `moss.toml` exist alongside the source file, the trust
bundle automatically verifies the deterministic import graph against the lock
file. Module count and hash drift diagnostics are included.

```json
{
  "lock": {
    "ok": true,
    "locked": true,
    "modules": 7,
    "diagnostics": null
  }
}
```

### Self-host comparison details

The `selfhost` section now breaks down all five comparison dimensions:

- `declarations_match` — effect/import/type/callable/test counts match
- `names_match` — declaration names match between host and self-host
- `bodies_match` — recursive statement-kind counts inside function bodies match
- `metadata_match` — record fields, aliases, parameters, return types, effects match
- `expressions_match` — complete recursive expression and match-pattern ASTs match

Mismatched dimensions include the conflicting host and self-host values,
making failures diagnosable without re-running commands.

## `moss trust-project`

```powershell
moss trust-project .
moss trust-project examples --output project.trust.json
```

Produces a project-wide trust bundle that includes:

- Project name, root, and entry module
- Lock verification (module graph hash check)
- Per-file check diagnostics, source hashes, and trust status
- Summary counts (files, trusted, failed)

## Verification

```powershell
python -m pytest tests/test_mosslang.py -q
# 121 passed, 9 subtests passed

python -m mosslang.cli trust examples/order.moss
# {"trust": true, "source_sha256": "...", "selfhost": {...}, ...}

python -m mosslang.cli trust-project .
# 7/7 files trusted

python -m mosslang.cli selfhost --quick
# 5/5 sketch tests pass
```

## Upgrade notes

- `.mbc` format unchanged
- `moss.lock` files are compatible
- No breaking changes to the Moss language
- Trust bundles from 0.5.7 are forward-compatible (new keys are additive)
