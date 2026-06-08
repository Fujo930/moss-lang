# Moss Trust Artifact — Format Specification v1.0

**Version**: v0.58.0  
**Spec version**: 1.0  
**Status**: formal specification

---

## 1. Overview

A Moss Trust Artifact is a JSON document that contains **structured, machine-verifiable evidence** about a Moss source file. It is produced by `moss artifact <file>` (alias: `moss trust`) and verified by `moss artifact-verify <bundle>` (alias: `moss trust-verify`).

The artifact records the results of **five independent verification gates** — check, trace, golden, lock, and selfhost — along with source identity and integrity metadata.

---

## 2. JSON Structure

```json
{
  "artifact": "Moss Trust Artifact v0.58.0",
  "moss": "0.58.0",
  "file": "<absolute path to source>",
  "source_sha256": "<sha256 hex>",
  "trust": true,
  "check": { ... },
  "lock": { ... },
  "trace": { ... },
  "golden": { ... },
  "selfhost": { ... }
}
```

### 2.1 Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `artifact` | string | Yes | Brand identifier: `"Moss Trust Artifact v<version>"` |
| `moss` | string | Yes | Moss version that produced the artifact |
| `file` | string | Yes | **Absolute** path to the source file |
| `source_sha256` | string | Yes | SHA-256 hex digest of source (UTF-8) |
| `trust` | boolean | Yes | Overall trust verdict: `true` if ALL active gates pass |
| `check` | object | Yes | Check gate results |
| `lock` | object | Yes | Lock gate results |
| `trace` | object | Yes | Trace gate results |
| `golden` | object | Yes | Golden gate results |
| `selfhost` | object | Yes | Selfhost gate results |
| `_error` | object | No | Present only on exception — `{type, message}` |
| `_hash_verified` | boolean | No | Present in stdout/file output: hash self-check result |

### 2.2 Trust Verdict Logic

`trust` is `true` only when **all** of the following hold:
- `check.ok` is `true`
- `trace.ok` is `true`
- `golden.ok` is `true` or `null` (missing golden is not a failure)
- `lock.ok` is `true` or `null` (missing lock is not a failure)
- `selfhost.ok` is `true`

Any gate returning `ok: false` flips `trust` to `false`.

---

## 3. Check Gate

### 3.1 Fields

```json
{
  "ok": true,
  "diagnostics": [
    {
      "level": "error",
      "message": "...",
      "line": 1,
      "column": 1
    }
  ],
  "summary": {
    "effects": 1,
    "imports": 0,
    "types": 2,
    "callables": 2,
    "tests": 1
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | `false` if any `error`-level diagnostic exists |
| `diagnostics` | array | List of diagnostic objects |
| `diagnostics[].level` | string | `"error"` or `"warning"` |
| `diagnostics[].message` | string | Human-readable diagnostic message |
| `diagnostics[].line` | number \| null | Source line (1-based) |
| `diagnostics[].column` | number \| null | Source column (1-based) |
| `summary.effects` | number | Count of effect declarations |
| `summary.imports` | number | Count of import declarations |
| `summary.types` | number | Count of type declarations |
| `summary.callables` | number | Count of rule + function declarations |
| `summary.tests` | number | Count of test declarations |

### 3.2 What check.ok means

- `true`: No errors found. Warnings may still be present.
- `false`: At least one `error`-level diagnostic exists.

### 3.3 Diagnostic levels in trust verdict

- `error` → `check.ok = false` → `trust = false`
- `warning` → `check.ok` stays `true` → `trust` unaffected (unless `--strict`)

---

## 4. Lock Gate

### 4.1 Fields

```json
{
  "ok": true,
  "locked": true,
  "diagnostics": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean \| null | `null` if no lock file found; otherwise lock validation result |
| `locked` | boolean | Whether a `moss.lock` file was found |
| `diagnostics` | array \| null | Lock validation errors; `null` if clean |
| `note` | string | Present when lock cannot be found or parsed |
| `error` | string | Present on lock validation exception |

### 4.2 Lock resolution

Since v0.55.0, `_find_lock()` walks **upward** from the source file's directory to find `moss.lock`, matching `find_manifest()` behavior.

---

## 5. Trace Gate

### 5.1 Fields

```json
{
  "ok": true,
  "rules_declared": 1,
  "events_captured": 1,
  "events": [
    {
      "rule": "canShip",
      "arguments": {"order": "{id: A-100, status: Paid, total: 42.usd}"},
      "result": "true",
      "file": "examples/order.moss",
      "line": 10,
      "column": 1
    }
  ],
  "note": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | `false` if rules are declared but no events were captured |
| `rules_declared` | number | Count of `RuleDecl` items in the program |
| `events_captured` | number | Count of trace events captured during execution |
| `events` | array | List of trace event objects |
| `events[].rule` | string | Rule name |
| `events[].arguments` | object | Rule arguments (stringified) |
| `events[].result` | string | Rule return value (stringified) |
| `events[].file` | string | Source file path |
| `events[].line` | number | Source line |
| `events[].column` | number | Source column |
| `note` | string \| null | Explanation when trace validation fails |

### 5.2 Independent validation

Since v0.55.0, `trace.ok` is **independent** of `check.ok`:
- `rules_declared > 0 and events_captured == 0` → `trace.ok = false`
- This detects rules that are declared but never evaluated during execution

---

## 6. Golden Gate

### 6.1 Fields

```json
{
  "ok": true,
  "snapshot": "status: Shipped\nstored: Shipped\n",
  "expected": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean \| null | `null` if no `.golden` file exists; otherwise `snapshot == expected` |
| `snapshot` | string \| null | Actual program output; `null` if check failed (execution skipped) |
| `expected` | string \| null | Golden file content when mismatch; `null` when match or golden absent |
| `note` | string | Present when no `.golden` file found |

### 6.2 Golden file naming

Golden files use the source file's path with `.golden` appended: `order.moss.golden`.

---

## 7. Selfhost Gate

### 7.1 Fields

```json
{
  "ok": true,
  "declarations_match": true,
  "names_match": true,
  "bodies_match": true,
  "metadata_match": true,
  "expressions_match": true,
  "host_summary": {"effects": 1, "imports": 0, "types": 2, "callables": 2, "tests": 1},
  "selfhost_summary": {"effects": 1, "imports": 0, "types": 2, "callables": 2, "tests": 1},
  "selfhost_errors": null,
  "expression_error": null,
  "host_names": null,
  "selfhost_names": null,
  "host_bodies": null,
  "selfhost_bodies": null,
  "host_metadata": null,
  "selfhost_metadata": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | AND of all five match fields |
| `declarations_match` | boolean | Host and selfhost count the same effects/imports/types/callables/tests |
| `names_match` | boolean | Host and selfhost produce identical declaration name lists |
| `bodies_match` | boolean | Host and selfhost produce matching body statement structures |
| `metadata_match` | boolean | Host and selfhost agree on parameter types, return types, effect uses |
| `expressions_match` | boolean | Host and selfhost produce equivalent expression ASTs |
| `host_summary` | object | Host's declaration counts |
| `selfhost_summary` | object | Selfhost's declaration counts |
| `selfhost_errors` | array \| null | Selfhost parser errors; `null` if none |
| `expression_error` | string \| null | Expression comparison error; `null` if expressions match |
| `host_names` | object \| null | Host name map (shown only on mismatch) |
| `selfhost_names` | object \| null | Selfhost name map (shown only on mismatch) |
| `host_bodies` | object \| null | Host body structure map (shown only on mismatch) |
| `selfhost_bodies` | object \| null | Selfhost body structure map (shown only on mismatch) |
| `host_metadata` | object \| null | Host metadata map (shown only on mismatch) |
| `selfhost_metadata` | object \| null | Selfhost metadata map (shown only on mismatch) |

### 7.2 Self-hosting paradox

The selfhost parser IS Moss code. It runs in the bytecode VM. If an attacker wrote both the source file and the self-host parser, the selfhost gate provides no independent evidence — it's comparing the attacker's parser output against the host parser output.

The Trust Artifact does not resolve this paradox. It **exposes it as structured data** so the consumer can make an informed decision. See `docs/threat-model.md` for the full analysis.

---

## 8. Artifact Verification (artifact-verify)

### 8.1 Command

```
moss artifact-verify <bundle.json> [--source <file>] [--strict]
```

### 8.2 Verification steps

1. Read bundle JSON, extract `file` and `source_sha256`
2. Resolve source file path (use `--source` if provided)
3. Detect `file_redirected` (bundle `file` != resolved file, since v0.57.1)
4. Re-read source, compute SHA-256, compare to stored hash
5. **Re-run all five gates** on the source file (since v0.57.0)
6. Report `verified: true/false`

### 8.3 Verified output

```json
{
  "bundle": "<path to bundle>",
  "source": "<resolved source path>",
  "bundle_file": "<file field from bundle>",
  "strict": false,
  "hash_match": true,
  "file_redirected": false,
  "gates_trust": true,
  "check_ok": true,
  "trace_ok": true,
  "golden_ok": true,
  "lock_ok": true,
  "selfhost_ok": true,
  "verified": true
}
```

### 8.4 --strict mode

With `--strict` (since v0.58.0):
- `file_redirected == true` → `verified = false`
- Any `warning`-level check diagnostic → `verified = false`

---

## 9. Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `moss artifact <file>` | `moss trust` | Generate a Trust Artifact |
| `moss artifact-project <dir>` | `moss trust-project` | Generate a project-wide Trust Artifact |
| `moss artifact-verify <bundle>` | `moss trust-verify` | Verify a Trust Artifact |

---

## 10. Version History

| Spec Version | Moss Version | Changes |
|-------------|-------------|---------|
| 1.0 | 0.58.0 | Initial formal specification. `artifact` field, `--strict` mode, `trust-verify` re-runs gates. |
| — | 0.57.1 | Absolute `file` paths, `file_redirected` detection, `--source` flag |
| — | 0.57.0 | `trust-verify` re-runs all five gates |
| — | 0.56.2 | `trust-verify` command introduced (hash-only) |
| — | 0.55.0 | Trust bundle format stabilized, all 10 initial vulns fixed |

---

*This specification defines the Moss Trust Artifact format and verification protocol. See `docs/threat-model.md` for the security analysis.*
