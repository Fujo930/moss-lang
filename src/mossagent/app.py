"""Corvus Desktop — tkinter GUI for Moss Agent.

Usage:
    python -m mossagent.app
    pyinstaller --onefile --windowed src/mossagent/app.py  →  one .exe

Architecture: thin shell around Corvus core.  Zero logic — all
decisions delegated to core.py.  The window is replaceable.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path
from io import StringIO

from .core import Corvus


class CorvusApp:
    """Moss Agent desktop window."""

    def __init__(self, root: tk.Tk, cv: Corvus | None = None) -> None:
        self.root = root
        self.root.title("Moss Agent (Corvus)")
        self.root.geometry("720x580")
        self.cv = cv or Corvus()

        self._build_ui()
        self._status("Ready. Paste Moss code or enter a requirement.")

    # ── UI construction ────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Top bar
        top = ttk.Frame(self.root, padding=4)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Source / Requirement:").pack(anchor=tk.W)

        # Input area
        self.input = scrolledtext.ScrolledText(
            self.root, height=10, wrap=tk.WORD, font=("Consolas", 10)
        )
        self.input.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # Button row
        btns = ttk.Frame(self.root, padding=4)
        btns.pack(fill=tk.X)

        ttk.Button(btns, text="▶ Verify (Trust)", command=self._on_verify).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btns, text="▶ Execute (Run)", command=self._on_execute).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btns, text="▶ Safe (Verify+Run)", command=self._on_safe).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btns, text="📋 Token", command=self._on_token).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btns, text="🤖 Generate", command=self._on_generate).pack(
            side=tk.LEFT, padx=2
        )
        self.generating_label = ttk.Label(btns, text="")
        self.generating_label.pack(side=tk.LEFT, padx=4)

        # Gate progress
        self.gates_frame = ttk.LabelFrame(self.root, text="Trust Gates", padding=4)
        self.gates_frame.pack(fill=tk.X, padx=4, pady=2)

        self.gate_bars: dict[str, ttk.Progressbar] = {}
        self.gate_labels: dict[str, ttk.Label] = {}
        for gate in ("check", "trace", "golden", "lock", "selfhost"):
            row = ttk.Frame(self.gates_frame)
            row.pack(fill=tk.X, pady=1)
            label = ttk.Label(row, text=f"{gate:>10}", width=10)
            label.pack(side=tk.LEFT)
            bar = ttk.Progressbar(row, length=300, mode="determinate")
            bar.pack(side=tk.LEFT, padx=4)
            status = ttk.Label(row, text="—", width=10)
            status.pack(side=tk.LEFT)
            self.gate_bars[gate] = bar
            self.gate_labels[gate] = status

        # Output area
        self.output = scrolledtext.ScrolledText(
            self.root, height=8, wrap=tk.WORD, font=("Consolas", 9), state=tk.DISABLED
        )
        self.output.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        # Status bar
        self.status_bar = ttk.Label(self.root, text="", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # ── Gate display ───────────────────────────────────────────────

    def _show_gates(self, vr) -> None:
        """Update gate progress bars from a VerifyResult."""
        gates = {
            "check": vr.check_ok,
            "trace": vr.trace_ok,
            "golden": vr.golden_ok,
            "lock": vr.lock_ok,
            "selfhost": vr.selfhost_ok,
        }
        for name, ok in gates.items():
            bar = self.gate_bars[name]
            label = self.gate_labels[name]
            if ok is True:
                bar["value"] = 100
                bar["style"] = "green.Horizontal.TProgressbar" if hasattr(ttk, "Style") else "TProgressbar"
                label.config(text="PASS", foreground="green")
            elif ok is False:
                bar["value"] = 100
                bar["style"] = "red.Horizontal.TProgressbar" if hasattr(ttk, "Style") else "TProgressbar"
                label.config(text="FAIL", foreground="red")
            else:
                bar["value"] = 0
                label.config(text="SKIP", foreground="gray")

    def _reset_gates(self) -> None:
        for bar in self.gate_bars.values():
            bar["value"] = 0
        for label in self.gate_labels.values():
            label.config(text="—", foreground="black")

    # ── Output ─────────────────────────────────────────────────────

    def _set_output(self, text: str) -> None:
        self.output.config(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.insert("1.0", text)
        self.output.config(state=tk.DISABLED)

    def _status(self, msg: str) -> None:
        self.status_bar.config(text=msg)

    # ── Actions ────────────────────────────────────────────────────

    def _get_source(self) -> str:
        return self.input.get("1.0", tk.END).strip()

    def _on_verify(self) -> None:
        self._reset_gates()
        source = self._get_source()
        if not source:
            self._status("Nothing to verify.")
            return

        self._status("Verifying...")
        self.root.update_idletasks()

        vr = self.cv.verify(source)
        self._show_gates(vr)

        if vr.trust:
            self._status(f"✅ PASS — {vr.gates}/{vr.gates_total} gates · {vr.elapsed_ms}ms · hash={vr.source_hash}")
            self._set_output("All gates passed.\n\n" + "\n".join(
                f"  {g}: OK" for g in ("check", "trace", "golden", "lock", "selfhost")
                if getattr(vr, f"{g}_ok") is not None
            ))
        else:
            hints = "\n".join(
                f"  line {h.get('line')}: {h.get('hint')}"
                for h in (vr.fix_hints or [])
            )
            self._status(f"❌ FAIL — {', '.join(vr.failed_gates)}")
            self._set_output(f"Failed gates: {vr.failed_gates}\n\nFix hints:\n{hints}")

    def _on_execute(self) -> None:
        source = self._get_source()
        if not source:
            self._status("Nothing to run.")
            return

        self._status("Running...")
        self.root.update_idletasks()

        er = self.cv.execute(source)
        if er.ok:
            self._status(f"✅ OK · {er.elapsed_ms}ms")
            self._set_output(er.output or "(no output)")
        else:
            self._status(f"❌ Error: {er.error}")
            self._set_output(f"ERROR: {er.error}")

    def _on_safe(self) -> None:
        self._reset_gates()
        source = self._get_source()
        if not source:
            self._status("Nothing to do.")
            return

        self._status("Verifying + Running...")
        self.root.update_idletasks()

        vr, er = self.cv.safe_execute(source)
        self._show_gates(vr)

        if er:
            self._status(f"✅ PASS + EXECUTED · {er.elapsed_ms}ms")
            self._set_output(er.output or "(no output)")
        else:
            self._status(f"❌ SKIPPED — gates failed: {vr.failed_gates}")

    def _on_token(self) -> None:
        import json
        source = self._get_source()
        if not source:
            self._status("Nothing to tokenize.")
            return

        t = self.cv.token(source)
        self._status(f"Token artifact · {t.get('c', {})}")
        self._set_output(json.dumps(t, indent=2))

    def _on_generate(self) -> None:
        """Placeholder — requires an LLM integration to be wired."""
        self._status("Generator: wire generate_fn to an LLM API (see generator.py)")


def main() -> None:
    root = tk.Tk()
    app = CorvusApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
