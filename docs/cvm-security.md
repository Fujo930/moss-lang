# Moss C VM — Security Analysis

**Version**: v0.60.0  
**Binary**: `bin/mossvm.exe` (~120 KB, C99, no external deps except libm)

---

## Threat Model

The C VM executes pre-compiled `.mbc` bytecode files. The compiler (`moss compile`) and
checker (`moss check`) run on the Python side. Malformed or malicious `.mbc` files are the
primary attack surface.

### Assumed attacker capabilities
- Can craft arbitrary `.mbc` files (bypassing the Python compiler)
- Can pass arbitrary command-line arguments
- Cannot modify the C VM binary itself
- Cannot attach a debugger to a running C VM process

### Out of scope
- Physical attacks / side channels
- Python VM attacks (separate threat model in `docs/threat-model.md`)
- Kernel-level attacks

---

## Defenses (v0.60.0)

### Stack depth guard
- `MAX_FRAME_DEPTH = 1000`
- Recursive Moss function calls exceeding this limit cause `exit(1)` with a clear error message
- Prevents stack overflow → segfault on deeply recursive programs

### Input boundary checks
- `read_string()`: refuses strings longer than `MAX_STRING_LEN` (1 MB)
- `readText()`: refuses files larger than 1 MB, returns empty string
- These prevent malloc OOM and buffer overflow from crafted .mbc headers

### Library-alloc-free memory model
- All values are heap-allocated via `calloc/malloc` with corresponding `free` calls
- No use-after-free paths identified in the current codebase
- Stack-allocated arrays use fixed sizes (256 chars for paths/file names, 32 for call args)

### No `system()` or `exec()` calls
- The C VM has no process-spawning capability
- `processRun` / `processRunJson` builtins return empty JSON stubs

---

## Known Limitations

### Memory leaks in error paths
- On `exit(1)`, heap memory is not freed. This is acceptable for a short-lived CLI process;
  the OS reclaims all memory on exit.

### No ASLR/DEP enforcement
- The binary relies on the host OS and compiler flags for exploit mitigations.
- Building with `-fstack-protector-strong -D_FORTIFY_SOURCE=2` is recommended for
  production builds.

### Fuzzing coverage
- A basic Python fuzzer (`tools/fuzz_mossvm.py`) generates random Moss source files,
  compiles them with the Python compiler, and feeds the resulting `.mbc` to the C VM.
- Target: 24h of continuous fuzzing with crash detection.
- See `tools/fuzz_mossvm.py` for the fuzzer script.

### Valgrind / MemorySanitizer
- Not yet run on Windows. Recommended for Linux CI:
  ```
  valgrind --leak-check=full --track-origins=yes bin/mossvm program.mbc
  ```
- Expected: 0 leaks (all memory freed on normal exit), 0 invalid reads/writes.

---

## Build Hardening Recommendations

```sh
# Production build with all available mitigations
gcc -O2 -std=c99 \
    -fstack-protector-strong \
    -D_FORTIFY_SOURCE=2 \
    -Wl,-z,relro \
    -Wl,-z,now \
    -o mossvm src/vm/mossvm.c -lm
```

---

*This document is part of the Moss v0.60.0 release. See `docs/threat-model.md` for the Trust Artifact security analysis.*
