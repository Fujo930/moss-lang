from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import MossError
from .nodes import ImportDecl, Program
from .parser import parse_source


MANIFEST_NAME = "moss.toml"


@dataclass(frozen=True)
class ProjectManifest:
    root: Path
    name: str
    version: str
    entry: Path
    source_roots: tuple[Path, ...]

    @property
    def path(self) -> Path:
        return self.root / MANIFEST_NAME


@dataclass
class ProjectGraph:
    manifest: ProjectManifest
    programs: dict[Path, Program]
    imports: dict[Path, list[Path]]
    diagnostics: list[dict[str, Any]]

    def relative(self, path: Path) -> str:
        return path.relative_to(self.manifest.root).as_posix()

    def as_json(self) -> dict[str, Any]:
        return {
            "package": {
                "name": self.manifest.name,
                "version": self.manifest.version,
                "entry": self.relative(self.manifest.entry),
            },
            "modules": [
                {
                    "path": self.relative(path),
                    "imports": [self.relative(dependency) for dependency in self.imports.get(path, [])],
                }
                for path in sorted(self.programs)
            ],
            "diagnostics": self.diagnostics,
        }

    def combined_program(self) -> Program:
        items: list[Any] = []
        for path in self.module_order():
            items.extend(item for item in self.programs[path].items if not isinstance(item, ImportDecl))
        return Program(items)

    def module_order(self) -> list[Path]:
        result: list[Path] = []
        seen: set[Path] = set()

        def append(path: Path) -> None:
            if path in seen:
                return
            seen.add(path)
            for dependency in self.imports.get(path, []):
                append(dependency)
            result.append(path)

        append(self.manifest.entry)
        return result


def find_manifest(path: Path) -> Path | None:
    candidate = path.resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for directory in (candidate, *candidate.parents):
        manifest = directory / MANIFEST_NAME
        if manifest.is_file():
            return manifest
    return None


def load_manifest(path: Path) -> ProjectManifest:
    manifest_path = path if path.name == MANIFEST_NAME else path / MANIFEST_NAME
    manifest_path = manifest_path.resolve()
    with manifest_path.open("rb") as handle:
        payload = tomllib.load(handle)

    package = payload.get("package")
    if not isinstance(package, dict):
        raise ValueError("moss.toml must contain a [package] table")
    name = required_text(package, "name")
    version = required_text(package, "version")
    entry_text = required_text(package, "entry")

    paths = payload.get("paths", {})
    if not isinstance(paths, dict):
        raise ValueError("[paths] must be a table")
    source_values = paths.get("source", ["."])
    if isinstance(source_values, str):
        source_values = [source_values]
    if not isinstance(source_values, list) or not source_values or not all(isinstance(item, str) for item in source_values):
        raise ValueError("paths.source must be a non-empty string or list of strings")

    root = manifest_path.parent
    entry = contained_path(root, root / entry_text, "package.entry")
    source_roots = tuple(contained_path(root, root / item, "paths.source") for item in source_values)
    if entry.suffix != ".moss":
        raise ValueError("package.entry must point to a .moss file")
    if not entry.is_file():
        raise ValueError(f"package.entry not found: {entry_text}")
    return ProjectManifest(root, name, version, entry, source_roots)


def build_project_graph(manifest: ProjectManifest) -> ProjectGraph:
    programs: dict[Path, Program] = {}
    imports: dict[Path, list[Path]] = {}
    diagnostics: list[dict[str, Any]] = []
    visiting: list[Path] = []

    def visit(path: Path) -> None:
        if path in visiting:
            cycle = visiting[visiting.index(path) :] + [path]
            diagnostics.append(
                {
                    "level": "error",
                    "file": manifest_relative(manifest, visiting[-1]),
                    "message": "import cycle: " + " -> ".join(manifest_relative(manifest, item) for item in cycle),
                }
            )
            return
        if path in programs:
            return
        visiting.append(path)
        try:
            program = parse_source(path.read_text(encoding="utf-8-sig"))
        except (OSError, MossError) as exc:
            diagnostics.append(
                {"level": "error", "file": manifest_relative(manifest, path), "message": getattr(exc, "message", str(exc))}
            )
            visiting.pop()
            return

        programs[path] = program
        dependencies: list[Path] = []
        for item in program.items:
            if not isinstance(item, ImportDecl):
                continue
            try:
                dependency = resolve_project_import(manifest, path, item.path)
            except ValueError as exc:
                diagnostics.append({"level": "error", "file": manifest_relative(manifest, path), "message": str(exc)})
                continue
            dependencies.append(dependency)
            visit(dependency)
        imports[path] = sorted(set(dependencies))
        visiting.pop()

    visit(manifest.entry)
    return ProjectGraph(manifest, programs, imports, diagnostics)


def resolve_project_import(manifest: ProjectManifest, importer: Path, import_text: str) -> Path:
    raw = Path(import_text)
    candidates = [importer.parent / raw, *(source_root / raw for source_root in manifest.source_roots)]
    for candidate in candidates:
        try:
            resolved = contained_path(manifest.root, candidate, f"import '{import_text}'")
        except ValueError:
            continue
        if resolved.is_file():
            if resolved.suffix != ".moss":
                raise ValueError(f"import must point to a .moss file: {import_text}")
            return resolved
    try:
        contained_path(manifest.root, importer.parent / raw, f"import '{import_text}'")
    except ValueError as exc:
        raise exc
    raise ValueError(f"import not found: {import_text}")


def required_text(table: dict[str, Any], key: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"package.{key} must be a non-empty string")
    return value


def contained_path(root: Path, path: Path, label: str) -> Path:
    root = root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside the project root") from exc
    return resolved


def manifest_relative(manifest: ProjectManifest, path: Path) -> str:
    try:
        return path.relative_to(manifest.root).as_posix()
    except ValueError:
        return str(path)


def initialize_project(directory: Path, name: str) -> ProjectManifest:
    root = directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / MANIFEST_NAME
    entry_path = root / "src" / "main.moss"
    if manifest_path.exists():
        raise ValueError(f"{manifest_path} already exists")
    if entry_path.exists():
        raise ValueError(f"{entry_path} already exists")
    entry_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        f'[package]\nname = "{name}"\nversion = "0.1.0"\nentry = "src/main.moss"\n\n[paths]\nsource = ["src"]\n',
        encoding="utf-8",
    )
    entry_path.write_text('print("Hello from Moss")\n', encoding="utf-8")
    return load_manifest(manifest_path)
