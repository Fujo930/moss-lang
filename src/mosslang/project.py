from __future__ import annotations

import tomllib
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import MossError
from .nodes import ImportDecl, Program
from .parser import parse_source


MANIFEST_NAME = "moss.toml"
LOCK_NAME = "moss.lock"
PROJECT_TEMPLATES = {
    "basic": {
        "src/main.moss": 'print("Hello from Moss")\n',
    },
    "cli": {
        "src/main.moss": 'fn main() {\n  print("Hello from a Moss CLI")\n}\n\nmain()\n',
    },
    "rules": {
        "src/main.moss": (
            "type Request =\n"
            "  approved: Bool\n"
            "  amount: Number\n\n"
            "rule mayProceed(request: Request) -> Bool =\n"
            "  request.approved and request.amount > 0\n\n"
            'let request = { approved: true, amount: 10}\n'
            'print("may proceed:", mayProceed(request))\n\n'
            'test "approved positive request may proceed" {\n'
            "  assert(mayProceed(request))\n"
            "}\n"
        ),
    },
    "library": {
        "src/main.moss": 'import "lib.moss"\n\nprint(greeting("Moss"))\n',
        "src/lib.moss": 'fn greeting(name: Text) -> Text {\n  return "Hello, " + name\n}\n',
    },
    "trust": {
        "src/main.moss": (
            'effect Database\n\n'
            'type Order =\n'
            '  id: Text\n'
            '  status: Pending | Paid | Shipped\n'
            '  total: Money\n\n'
            'type ShipError = NotReady | Missing\n\n'
            'rule canShip(o: Order) -> Bool = o.status == Paid and o.total > 0.usd\n\n'
            'fn ship(o: Order) -> Result<Order, ShipError> uses Database {\n'
            '  require canShip(o) else ShipError.NotReady(o.status)\n'
            '  updated = o with status = Shipped\n'
            '  dbPut(o.id, updated)\n'
            '  return Ok(updated)\n'
            '}\n\n'
            'let order = { id: "TR-001", status: Paid, total: 99.usd }\n'
            'let shipped = ship(order)?\n'
            'print("shipped:", shipped.status)\n\n'
            'test "ship paid order" {\n'
            '  result = ship(order)?\n'
            '  assert(result.status == Shipped, "expected shipped")\n'
            '}\n\n'
            'test "reject pending" {\n'
            '  pending = order with status = Pending\n'
            '  rejected = ship(pending)\n'
            '  assert(rejected == Err(ShipError.NotReady(Pending)), "expected NotReady")\n'
            '}\n'
        ),
    },
}


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


def initialize_project(directory: Path, name: str, template: str = "basic") -> ProjectManifest:
    root = directory.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / MANIFEST_NAME
    files = PROJECT_TEMPLATES.get(template)
    if files is None:
        raise ValueError(f"unknown project template '{template}'")
    if manifest_path.exists():
        raise ValueError(f"{manifest_path} already exists")
    for relative in files:
        path = root / relative
        if path.exists():
            raise ValueError(f"{path} already exists")
    manifest_path.write_text(
        f'[package]\nname = "{name}"\nversion = "0.1.0"\nentry = "src/main.moss"\n\n[paths]\nsource = ["src"]\n',
        encoding="utf-8",
    )
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    return load_manifest(manifest_path)


def project_lock_payload(graph: ProjectGraph) -> dict[str, Any]:
    return {
        "format": 1,
        "package": graph.as_json()["package"],
        "modules": [
            {
                "path": graph.relative(path),
                "sha256": source_hash(path),
                "imports": [graph.relative(dependency) for dependency in graph.imports.get(path, [])],
            }
            for path in sorted(graph.programs)
        ],
    }


def source_hash(path: Path) -> str:
    source = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def write_project_lock(graph: ProjectGraph) -> Path:
    path = graph.manifest.root / LOCK_NAME
    path.write_text(json.dumps(project_lock_payload(graph), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def verify_project_lock(graph: ProjectGraph) -> list[dict[str, Any]]:
    path = graph.manifest.root / LOCK_NAME
    if not path.is_file():
        return [{"level": "error", "file": LOCK_NAME, "message": "lock file missing; run moss project-lock"}]
    try:
        locked = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [{"level": "error", "file": LOCK_NAME, "message": f"invalid lock file: {exc}"}]
    if not isinstance(locked, dict) or not isinstance(locked.get("modules"), list):
        return [{"level": "error", "file": LOCK_NAME, "message": "invalid lock file: expected an object with modules"}]
    current = project_lock_payload(graph)
    if locked == current:
        return []
    locked_modules = {item.get("path"): item for item in locked.get("modules", []) if isinstance(item, dict)}
    current_modules = {item["path"]: item for item in current["modules"]}
    messages: list[str] = []
    for module in sorted(set(locked_modules) | set(current_modules)):
        if module not in locked_modules:
            messages.append(f"module added: {module}")
        elif module not in current_modules:
            messages.append(f"module removed: {module}")
        elif locked_modules[module] != current_modules[module]:
            messages.append(f"module changed: {module}")
    if locked.get("package") != current["package"]:
        messages.append("package metadata changed")
    if locked.get("format") != current["format"]:
        messages.append("lock format changed")
    return [{"level": "error", "file": LOCK_NAME, "message": message} for message in messages or ["lock file changed"]]
