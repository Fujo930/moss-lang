"""Corvus Tool Layer — file system, shell, git, and Moss operations.

All tools return structured dicts with an 'ok' field so the LLM can
inspect results and decide next actions.  Tools never crash — they
always return an error dict.

Architecture: tools are stateless callables that the Agent loop
dispatches.  The LLM sees tool names, descriptions, and results in
its context window.  This mirrors Reasonix's tool-use pattern.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from dataclasses import dataclass


# ── Tool result type ───────────────────────────────────────────────

@dataclass
class ToolResult:
    ok: bool
    output: str
    error: str | None = None
    data: dict | None = None


def _ok(output: str = "", data: dict | None = None) -> dict:
    result = {"ok": True, "output": output}
    if data:
        result.update(data)
    return result


def _err(error: str) -> dict:
    return {"ok": False, "error": error}


# ── File system tools ──────────────────────────────────────────────

def tool_read_file(path: str, offset: int = 0, limit: int = 200) -> dict:
    """Read a file. Returns lines with line numbers."""
    try:
        p = Path(path)
        if not p.is_file():
            return _err(f"file not found: {path}")
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        total = len(lines)
        chunk = lines[offset:offset + limit]
        numbered = "\n".join(
            f"{offset + i + 1:4d}|{line}"
            for i, line in enumerate(chunk)
        )
        header = f"// {path}  lines {offset + 1}-{min(offset + limit, total)} of {total}"
        return _ok(f"{header}\n{numbered}", {"lines": total, "start": offset, "end": min(offset + limit, total)})
    except Exception as e:
        return _err(str(e))


def tool_write_file(path: str, content: str) -> dict:
    """Write content to a file. Creates parent directories."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return _ok(f"wrote {len(content)} bytes to {path}", {"bytes": len(content)})
    except Exception as e:
        return _err(str(e))


def tool_list_files(path: str = ".", recursive: bool = False) -> dict:
    """List directory contents."""
    try:
        p = Path(path)
        if not p.is_dir():
            return _err(f"not a directory: {path}")
        entries = []
        if recursive:
            for f in sorted(p.rglob("*")):
                if ".git" in f.parts or "__pycache__" in f.parts:
                    continue
                suffix = "/" if f.is_dir() else ""
                entries.append(f"{f.relative_to(p)}{suffix}")
        else:
            for f in sorted(p.iterdir()):
                if f.name.startswith("."):
                    continue
                suffix = "/" if f.is_dir() else ""
                entries.append(f"{f.name}{suffix}")
        return _ok("\n".join(entries), {"count": len(entries)})
    except Exception as e:
        return _err(str(e))


def tool_glob_find(pattern: str) -> dict:
    """Find files matching a glob pattern (e.g. '**/*.py')."""
    try:
        matches = sorted(f.as_posix() for f in Path(".").glob(pattern))
        return _ok("\n".join(matches), {"count": len(matches), "pattern": pattern})
    except Exception as e:
        return _err(str(e))


# ── Shell tools ────────────────────────────────────────────────────

def tool_bash(command: str, timeout: int = 30) -> dict:
    """Execute a shell command. Returns stdout, stderr, and exit code."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd="."
        )
        return _ok(
            result.stdout or "(no output)",
            {
                "stderr": result.stderr,
                "exit_code": result.returncode,
            }
        )
    except subprocess.TimeoutExpired:
        return _err(f"command timed out after {timeout}s")
    except Exception as e:
        return _err(str(e))


def tool_grep(pattern: str, path: str = ".") -> dict:
    """Search for a pattern in files. Returns matching lines."""
    try:
        import re
        results = []
        p = Path(path)
        files = p.rglob("*") if p.is_dir() else [p]
        for f in files:
            if not f.is_file():
                continue
            if f.suffix not in (".py", ".moss", ".c", ".h", ".md", ".toml", ".json", ".txt"):
                continue
            if ".git" in f.parts or "__pycache__" in f.parts:
                continue
            try:
                for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if re.search(pattern, line):
                        results.append(f"{f}:{i}: {line}")
                        if len(results) >= 50:
                            break
                if len(results) >= 50:
                    break
            except Exception:
                pass
        return _ok("\n".join(results) or "(no matches)", {"count": len(results)})
    except Exception as e:
        return _err(str(e))


# ── Git tools ──────────────────────────────────────────────────────

def tool_git(command: str) -> dict:
    """Run a git command. Valid: status, log, diff, branch, commit, add."""
    allowed = {"status", "log", "diff", "branch", "add", "commit",
               "checkout", "stash", "pop", "push", "pull"}
    cmd_name = command.split()[0]
    if cmd_name not in allowed:
        return _err(f"git command '{cmd_name}' not allowed. Allowed: {', '.join(sorted(allowed))}")
    try:
        result = subprocess.run(
            f"git {command}", shell=True, capture_output=True, text=True,
            timeout=10, cwd="."
        )
        return _ok(
            result.stdout or result.stderr or "(no output)",
            {"exit_code": result.returncode}
        )
    except Exception as e:
        return _err(str(e))


# ── Moss tools ─────────────────────────────────────────────────────

def tool_moss_verify(source: str) -> dict:
    """Run Moss Trust verification on source code."""
    from mossagent import Corvus
    cv = Corvus()
    vr = cv.verify(source)
    return {
        "ok": vr.trust,
        "trust": vr.trust,
        "gates": vr.gates,
        "gates_total": vr.gates_total,
        "failed_gates": vr.failed_gates,
        "fix_hints": [f"line {h.get('line')}: {h.get('hint')}" for h in vr.fix_hints],
        "hash": vr.source_hash,
        "ms": vr.elapsed_ms,
    }


def tool_moss_execute(source: str) -> dict:
    """Compile and run Moss source code. Returns output."""
    from mossagent import Corvus
    cv = Corvus()
    er = cv.execute(source)
    return {
        "ok": er.ok,
        "output": er.output.strip() if er.output else "(no output)",
        "error": er.error,
        "ms": er.elapsed_ms,
    }


def tool_moss_tokenize(source: str) -> dict:
    """Extract Token Artifact from Moss source."""
    from mossagent import Corvus
    cv = Corvus()
    t = cv.token(source)
    return {"ok": t.get("t", True), "token": t}


# ── Tool registry ──────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, dict] = {
    "read_file": {
        "fn": tool_read_file,
        "description": "Read a file. Returns line-numbered content.",
        "parameters": {
            "path": "file path to read",
            "offset": "line offset (default 0)",
            "limit": "max lines (default 200)",
        },
    },
    "write_file": {
        "fn": tool_write_file,
        "description": "Write content to a file. Creates parent directories.",
        "parameters": {
            "path": "file path",
            "content": "content to write",
        },
    },
    "ls": {
        "fn": tool_list_files,
        "description": "List directory contents.",
        "parameters": {
            "path": "directory path (default .)",
            "recursive": "true/false (default false)",
        },
    },
    "glob": {
        "fn": tool_glob_find,
        "description": "Find files matching a glob pattern (e.g. 'src/**/*.py').",
        "parameters": {
            "pattern": "glob pattern",
        },
    },
    "bash": {
        "fn": tool_bash,
        "description": "Execute a shell command. Returns stdout, stderr, exit code.",
        "parameters": {
            "command": "shell command",
            "timeout": "timeout in seconds (default 30)",
        },
    },
    "grep": {
        "fn": tool_grep,
        "description": "Search for a regex pattern in files.",
        "parameters": {
            "pattern": "regex pattern",
            "path": "file or directory path (default .)",
        },
    },
    "git": {
        "fn": tool_git,
        "description": "Run a git command. Allowed: status, log, diff, branch, add, commit, checkout, stash, push, pull.",
        "parameters": {
            "command": "git command (e.g. 'status', 'log --oneline -5')",
        },
    },
    "moss_verify": {
        "fn": tool_moss_verify,
        "description": "Run Moss Trust verification (5-gate pipeline). Returns gate results and fix hints.",
        "parameters": {
            "source": "Moss source code",
        },
    },
    "moss_execute": {
        "fn": tool_moss_execute,
        "description": "Compile and run Moss source code. Returns program output.",
        "parameters": {
            "source": "Moss source code",
        },
    },
    "moss_tokenize": {
        "fn": tool_moss_tokenize,
        "description": "Extract Token Artifact (structure skeleton) from Moss source.",
        "parameters": {
            "source": "Moss source code",
        },
    },
}

# Ordered list for prompt generation
TOOL_LIST = [
    ("read_file", "path, offset, limit — read file with line numbers"),
    ("write_file", "path, content — write content to a file"),
    ("ls", "path, recursive — list directory"),
    ("glob", "pattern — find files by glob"),
    ("bash", "command, timeout — run shell command"),
    ("grep", "pattern, path — search text in files"),
    ("git", "command — git status/log/diff/branch/commit"),
    ("moss_verify", "source — run Trust verification on Moss code"),
    ("moss_execute", "source — compile and run Moss code"),
    ("moss_tokenize", "source — extract Token Artifact from Moss code"),
]


def dispatch_tool(name: str, params: dict) -> dict:
    """Call a tool by name. Returns the tool's result dict."""
    tool = TOOL_REGISTRY.get(name)
    if not tool:
        return _err(f"unknown tool: {name}. Available: {', '.join(TOOL_REGISTRY)}")
    try:
        return tool["fn"](**params)
    except TypeError as e:
        return _err(f"invalid parameters for {name}: {e}")
    except Exception as e:
        return _err(f"tool {name} failed: {e}")
