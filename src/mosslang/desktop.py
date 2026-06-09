"""Moss Studio browser launcher.

Opens Moss Studio (web-based workbench) in the default browser.
This is a thin launcher, not a native desktop application — it creates
a workspace directory, starts the Studio HTTP server, and opens the browser.
"""

import os
import threading
import webbrowser
from pathlib import Path

from .studio import run_studio


def main() -> None:
    workspace = Path.home() / "Documents" / "Moss Workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MOSS_WORKSPACE", str(workspace))
    threading.Timer(0.8, lambda: webbrowser.open("http://127.0.0.1:8765/")).start()
    run_studio()


if __name__ == "__main__":
    main()
