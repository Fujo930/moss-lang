# Moss Studio

Moss Studio is a local browser editor backed by the same parser, checker, and
runtime as the CLI.

Like the rest of Moss, Studio was designed, implemented, debugged, documented,
committed, and pushed by DeepSeek in collaboration with Fujo930. It is part of the
`0.5.0` release, not a hosted product.

Start it from the project folder:

```powershell
moss studio
```

Then open:

```text
http://127.0.0.1:8765
```

## What it does

- edits `.moss` source with line numbers and cursor status
- keeps a local autosaved scratch buffer
- loads bundled examples
- runs `check` automatically after edits
- runs the program on demand
- runs top-level `test` blocks
- shows output, source-located diagnostics with a live issue count, AST, and
  tokens
- lists declaration symbols and jumps to their source locations
- shows the current project's deterministic reachable module graph
- runs source-mapped rule traces
- compares bundled programs through the host and Moss-written frontends
- opens browser-selected `.moss` files and downloads the current buffer
- opens and saves workspace-relative paths inside the Moss repository
- can open the self-hosting sketches so users can inspect Moss code that checks
  Moss code

The toolbar is grouped into source selection, file commands, and Moss commands.
The status bar summarizes imports, effects, types, callables, and tests. The
branching M mark and green/gold/blue palette follow `docs/identity.md`.

## Keyboard

- `Ctrl+Enter` or `Cmd+Enter`: run the current source
- `Ctrl+S` or `Cmd+S`: save the current workspace path
- `Tab`: insert two spaces

## Implementation

The server lives in `src/mosslang/studio.py`. The browser assets live in
`src/mosslang/studio_assets`.

The API surface is intentionally small:

- `GET /api/examples`
- `POST /api/check`
- `POST /api/run`
- `POST /api/test`
- `POST /api/file/read`
- `POST /api/file/write`
- `POST /api/project/info`
- `POST /api/selfhost/compare`
- `POST /api/trace`

Each API accepts or returns plain JSON so a future desktop app, VS Code panel,
or hosted playground can reuse the same backend shape.

File read/write requests are constrained to the repository workspace.

Studio is deliberately a small workbench rather than a separate compiler. Its
diagnostic and symbol entries can be clicked to move the editor cursor to their
source location. The same compiler-facing analysis model is shared with the
language server, keeping editor integrations and Studio results aligned.
