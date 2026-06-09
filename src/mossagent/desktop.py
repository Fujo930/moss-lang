"""Corvus Desktop — PySide6 QML application.

Architecture:
  QML (UI) ←→ QML bridge properties ←→ Python (Corvus core)

The bridge exposes Corvus APIs as Qt properties and slots.
QML reads from bridge properties, calls bridge slots on user actions.
All Agent logic stays in core.py, chat.py, generator.py — unchanged.

Run:
    python -m mossagent.desktop
    pyinstaller --onefile --windowed --add-data "src/mossagent/ui:ui" src/mossagent/desktop.py
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from io import StringIO

# ── Qt style fix: Basic supports background customization ─────
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Fusion")

try:
    from PySide6.QtCore import QObject, Signal, Slot, Property, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
except ImportError as e:
    raise ImportError(
        "PySide6 is required for the desktop GUI. Install it:\n"
        "  pip install PySide6"
    ) from e

from .core import Corvus
from .chat import ChatSession
from .generator import Generator
from .agent import Agent
from .tools import dispatch_tool, TOOL_REGISTRY
from .llm import create_adapter

from _version import MOSS_VERSION, AGENT_VERSION


# ── QML Bridge ──────────────────────────────────────────────────────

class CorvusBridge(QObject):
    """Python ↔ QML bridge. All UI state flows through this class."""

    # Signals → QML
    messageAdded = Signal(str, str, object)  # role, content, toolCall dict
    gateUpdated = Signal(str, str)            # gate name, status
    progressChanged = Signal(str)             # status bar message + task results (JSON)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cv = Corvus()
        self._chat_session: ChatSession | None = None
        self._adapter = None
        self._agent: Agent | None = None
        self._generator: Generator | None = None
        self._busy = False
        self._active_source = ""
        self._file_tree: list[dict] = []
        self._memories: list[dict] = []
        self._stats: dict = {}

        # Initialize workspace
        self._refresh_workspace()

    # ── Properties exposed to QML ──────────────────────────────

    def _get_version(self) -> dict:
        return {"moss": MOSS_VERSION, "agent": AGENT_VERSION}

    def _get_file_tree(self) -> list:
        return self._file_tree

    def _get_memories(self) -> list:
        return self._memories

    def _get_stats(self) -> dict:
        return self._stats

    version = Property("QVariantMap", fget=_get_version, constant=True)
    fileTree = Property("QVariantList", fget=_get_file_tree, notify=progressChanged)
    memories = Property("QVariantList", fget=_get_memories, notify=progressChanged)
    stats = Property("QVariantMap", fget=_get_stats, notify=progressChanged)

    # ── Slots called from QML ─────────────────────────────────

    @Slot()
    def onUIReady(self):
        """Called when QML is fully loaded."""
        self.progressChanged.emit("Ready. Set LLM_API_KEY env var to enable AI features.")
        # Try to auto-load adapter
        try:
            provider = os.environ.get("LLM_PROVIDER", "openai")
            self._adapter = create_adapter(provider)
            self._chat_session = ChatSession().bind(self._adapter.generate)
            self._generator = Generator(self._cv, self._adapter.generate)
            self._agent = Agent(self._adapter.generate)
            self.progressChanged.emit("Ready — AI connected.")
        except Exception:
            self.progressChanged.emit("Ready — AI not configured. Set LLM_API_KEY.")

    @Slot(str)
    def sendChat(self, message: str):
        """User sent a chat message."""
        if self._busy:
            self.messageAdded.emit("system", "Agent is busy. Please wait.", None)
            return

        self._busy = True
        self.progressChanged.emit("Corvus is thinking...")

        def _do():
            try:
                if self._chat_session is None:
                    # Lazy init adapter
                    provider = os.environ.get("LLM_PROVIDER", "openai")
                    self._adapter = create_adapter(provider)
                    self._chat_session = ChatSession().bind(self._adapter.generate)

                result = self._chat_session.send(message)
                self.messageAdded.emit("assistant", result.answer, None)
                self._chat_session.save("corvus_chat.json")
                self._update_stats(self._chat_session.stats())
                self.progressChanged.emit(
                    f"Done · cache hit {result.cache_hit_pct}% · {result.elapsed_s}s"
                )
            except Exception as e:
                self.messageAdded.emit("system", f"Error: {e}", None)
                self.progressChanged.emit("Error — see message.")
            finally:
                self._busy = False

        threading.Thread(target=_do, daemon=True).start()

    @Slot(str)
    def runVerify(self, source: str):
        """Run Moss Trust verification."""
        self._busy = True
        self.progressChanged.emit("Verifying...")
        self._reset_gates()

        def _do():
            try:
                vr = self._cv.verify(source)
                gates = {
                    "check": vr.check_ok, "trace": vr.trace_ok,
                    "golden": vr.golden_ok, "lock": vr.lock_ok,
                    "selfhost": vr.selfhost_ok,
                }
                for name, ok in gates.items():
                    status = "PASS" if ok is True else ("FAIL" if ok is False else "SKIP")
                    self.gateUpdated.emit(name, status)

                summary = json.dumps({"ok": vr.trust, "summary": f"{'PASS' if vr.trust else 'FAIL'} {vr.gates}/{vr.gates_total} gates · {vr.elapsed_ms}ms"})
                self.progressChanged.emit(summary)
                self.messageAdded.emit("system", summary, None)
                self.progressChanged.emit("Verify complete.")
            except Exception as e:
                self.messageAdded.emit("system", f"Verify error: {e}", None)
                self.progressChanged.emit("Error during verification.")
            finally:
                self._busy = False

        threading.Thread(target=_do, daemon=True).start()

    @Slot(str)
    def runExecute(self, source: str):
        """Compile and run Moss code."""
        self._busy = True
        self.progressChanged.emit("Running...")

        def _do():
            try:
                er = self._cv.execute(source)
                if er.ok:
                    output = er.output.strip() or "(no output)"
                    self.messageAdded.emit("system", f"Output:\n{output}", None)
                    self.progressChanged.emit(f"OK · {er.elapsed_ms}ms")
                else:
                    self.messageAdded.emit("system", f"Error: {er.error}", None)
                    self.progressChanged.emit("Execution failed.")
            except Exception as e:
                self.messageAdded.emit("system", f"Execute error: {e}", None)
                self.progressChanged.emit("Error.")
            finally:
                self._busy = False

        threading.Thread(target=_do, daemon=True).start()

    @Slot()
    def promptGenerate(self):
        """Open a generate prompt (placeholder)."""
        self.messageAdded.emit("system", 
            "✨ Generator ready. Type a task description and I'll generate Moss code.\n"
            "Example: 'write a function that sorts a list of numbers'", None)

    @Slot(str)
    def runGenerate(self, spec: str):
        """AI generate Moss code from a spec."""
        if not self._generator:
            self.messageAdded.emit("system", "AI not configured. Set LLM_API_KEY.", None)
            return

        self._busy = True
        self.progressChanged.emit("Generating Moss code...")
        self._reset_gates()

        def _do():
            try:
                result = self._generator.generate(spec)
                if result.trust:
                    self.messageAdded.emit("system", f"✅ Generated ({result.attempts} attempts):\n```moss\n{result.moss_code}\n```", None)
                    self.progressChanged.emit("Trust passed!")
                else:
                    self.messageAdded.emit("system", f"❌ Failed after {result.attempts} attempts: {result.final_error}", None)
                    self.progressChanged.emit("Generation failed.")
                self.progressChanged.emit(json.dumps({"ok": result.trust, "summary": f"{result.attempts} attempts"}))
            except Exception as e:
                self.messageAdded.emit("system", f"Generate error: {e}", None)
                self.progressChanged.emit("Error.")
            finally:
                self._busy = False

        threading.Thread(target=_do, daemon=True).start()

    @Slot()
    def refreshWorkspace(self):
        """Refresh the workspace file tree."""
        self._refresh_workspace()
        self.progressChanged.emit("Workspace refreshed.")

    @Slot(str)
    def toggleDirectory(self, path: str):
        """Toggle directory expansion."""
        pass  # Future: expand/collapse directory nodes

    @Slot(str)
    def openFile(self, path: str):
        """Load a file into the active source (silent — no chat message)."""
        try:
            self._active_source = Path(path).read_text(encoding="utf-8", errors="replace")
            self.progressChanged.emit(f"Loaded {path} ({len(self._active_source)} chars)")
        except Exception as e:
            self.progressChanged.emit(f"Error opening {path}: {e}")

    @Slot(result=str)
    def getActiveSource(self) -> str:
        return self._active_source

    # ── Internal ──────────────────────────────────────────────

    def _refresh_workspace(self):
        """Scan project directory for .moss, .py, .md, .toml files."""
        entries = []
        try:
            root = Path(".")
            for f in sorted(root.iterdir()):
                if f.name.startswith(".") or f.name.startswith("__"):
                    continue
                if f.name == "node_modules":
                    continue
                if f.is_dir():
                    if f.name in ("src", "tests", "examples", "docs", "build"):
                        entries.append({"name": f.name + "/", "path": str(f), "isDir": True})
                    elif f.name in ("dist", ".git", "__pycache__", ".pytest_cache"):
                        continue
                    else:
                        entries.append({"name": f.name + "/", "path": str(f), "isDir": True})
                elif f.suffix in (".moss", ".py", ".md", ".toml", ".json", ".c", ".h", ".txt"):
                    entries.append({"name": f.name, "path": str(f), "isDir": False})

            # Expand src/
            for d in ("src", "tests", "examples"):
                p = Path(d)
                if p.is_dir():
                    for f in sorted(p.rglob("*")):
                        if f.name.startswith(".") or f.name.startswith("__"):
                            continue
                        if f.suffix in (".moss", ".py", ".md", ".toml", ".json", ".c", ".h", ".qml", ".js"):
                            entries.append({
                                "name": str(f),
                                "path": str(f),
                                "isDir": False,
                            })
        except Exception:
            pass

        self._file_tree = entries

        # Memories: project context
        mems = [
            {"key": "Moss version", "value": MOSS_VERSION},
            {"key": "Agent version", "value": AGENT_VERSION},
        ]
        if self._chat_session:
            stats = self._chat_session.stats()
            mems.append({"key": "Chat turns", "value": str(stats["turns"])})
            mems.append({"key": "Cache hit", "value": str(stats.get("estimated_cache_hit_pct", "—")) + "%"})
        self._memories = mems
        self.progressChanged.emit("")  # trigger property refresh

    def _reset_gates(self):
        for gate in ("check", "trace", "golden", "lock", "selfhost"):
            self.gateUpdated.emit(gate, "—")

    def _update_stats(self, stats: dict):
        self._stats = stats
        self.progressChanged.emit("")  # trigger refresh


# ── Application entry ───────────────────────────────────────────────

def main():
    # Ensure we can find QML files
    ui_dir = Path(__file__).parent / "ui"
    if not (ui_dir / "main.qml").is_file():
        print(f"Error: QML files not found at {ui_dir}", file=sys.stderr)
        print("Run from project root: python -m mossagent.desktop", file=sys.stderr)
        return 1

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Corvus")
    app.setOrganizationName("Moss")

    engine = QQmlApplicationEngine()

    # Register bridge
    bridge = CorvusBridge()
    engine.rootContext().setContextProperty("bridge", bridge)

    # Load main QML
    engine.load(QUrl.fromLocalFile(str(ui_dir / "main.qml")))

    if not engine.rootObjects():
        print("Error: failed to load QML", file=sys.stderr)
        return 1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
