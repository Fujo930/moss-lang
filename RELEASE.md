# Moss 0.58.0 — Trust Artifact General Availability

Moss `0.58.0` is the **Trust Artifact GA release**. After three independent adversarial audits
(16 + 22 + 40 = 78 attack vectors) and seven patch releases, the Trust Artifact pipeline
is formally specified, threat-modeled, and production-ready.

## What is a Trust Artifact

A Moss Trust Artifact is a machine-verifiable JSON document containing **five independent gates**
that together testify to the correctness, integrity, and reproducibility of a Moss program:

```
check  →  type safety, effect purity, match coverage
trace  →  rule evaluation provenance (source-mapped)
golden →  output stability against recorded snapshot
lock   →  source file integrity (SHA-256 module hashing)
selfhost→  self-host parser equivalence
```

## New in 0.58.0

### Commands
```
moss artifact <file>              ← generate a Trust Artifact
moss artifact-project <dir>       ← project-wide Trust Artifact
moss artifact-verify <bundle>     ← verify Trust Artifact against source

# Legacy aliases still work:
moss trust / trust-project / trust-verify
```

### --strict verification
```powershell
moss artifact-verify --strict --source file.moss bundle.json
```
- Rejects on `file_redirected` (bundle points to wrong file)
- Rejects if any check diagnostics contain warnings

### Documentation
- `docs/trust-artifact.md` — Formal Trust Artifact format specification v1.0
- `docs/threat-model.md` — Complete security analysis with gate-by-gate threat model

## Audit Provenance

| Version | Audit | Vectors | Result |
|---------|-------|---------|--------|
| v0.55.0 | Round 1 | 16 | V1-V6 fixed |
| v0.56.0 | Round 2 (saturation) | 22 | V7-V11 fixed |
| v0.56.1 | Root cause | — | V5+V8 fixed |
| v0.56.2 | V6 final | — | trust-verify command |
| v0.57.0 | Nuke audit | 40 | F1-F7 fixed |
| v0.57.1 | Hardening | — | F1 file-redirect |

**78 total attack vectors, 18 vulnerabilities, 0 remaining.**

## Trust Artifact Claims

The Trust Artifact does **not** claim to be a mathematical proof.  
It is **structured, reproducible evidence** from five orthogonal verification dimensions.

For the full threat model — what the artifact can and cannot defend against — see `docs/threat-model.md`.

## Verification

```powershell
python -m pytest tests/test_mosslang.py -q
# 133 passed, 22 subtests

python -m mosslang.cli selfhost --quick
# 5/5 sketch tests pass

python -m mosslang.cli selfhost-compare examples
# 9/9 comparison passed
```

## Install

```powershell
git clone https://github.com/Fujo930/moss-lang.git
cd moss-lang
git checkout ds-Mosslang
pip install -e .
```

Built by Reasonix for Fujo930.
