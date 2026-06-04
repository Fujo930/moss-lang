# Moss Studio

Moss Studio is a local browser editor backed by the same parser, checker, and
runtime as the CLI.

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
- shows output, diagnostics, AST, and tokens
- opens local `.moss` files and downloads the current buffer

## Implementation

The server lives in `src/mosslang/studio.py`. The browser assets live in
`src/mosslang/studio_assets`.

The API surface is intentionally small:

- `GET /api/examples`
- `POST /api/check`
- `POST /api/run`

Each API accepts or returns plain JSON so a future desktop app, VS Code panel,
or hosted playground can reuse the same backend shape.
