"""Moss + Moss Agent shared version constants.

This file is the single source of truth for both packages' version requirements.
Both `mosslang` and `mossagent` import from here — Agent self-checks Moss version
at startup to guarantee compatibility.

Moss version: the language, VM, compiler, Trust pipeline.
Agent requires: minimum compatible Moss version.

Update MOSS_REQUIRED when Agent depends on new Moss features.
Increment MOSS_VERSION after every Moss change landed in this branch.
"""

from __future__ import annotations

# ── Moss language version (updated with each Moss change) ─────────────
MOSS_VERSION = "0.1.0"

# ── Moss Agent version (updated with each Agent change) ───────────────
AGENT_VERSION = "0.1.0-dev"

# ── Minimum Moss version the Agent requires to function ───────────────
# Agent will refuse to start if the installed Moss is older than this.
MOSS_REQUIRED = "0.1.0"
