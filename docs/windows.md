# Moss for Windows

Moss can be built as a normal per-user Windows application that does not
require Python on the target computer.

Build it from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_windows.ps1
```

The build creates:

- `build/windows/moss/moss.exe`: standalone command-line compiler
- `build/windows/moss/Moss Studio.exe`: desktop Studio launcher
- `installer/Moss-0.4.0-alpha-Windows-Setup.exe`: Windows installer

The installer places Moss under `%LOCALAPPDATA%\Programs\Moss`, can add the
compiler to the user PATH, creates Start menu shortcuts, and registers a
standard Windows uninstaller. Moss Studio creates and edits files inside
`%USERPROFILE%\Documents\Moss Workspace` by default.

The packaged compiler includes the self-hosting examples and can run
`moss selfhost --quick` without the source repository or a Python installation.
