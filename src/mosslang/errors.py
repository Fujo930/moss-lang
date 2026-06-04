from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLocation:
    line: int
    column: int

    def format(self) -> str:
        return f"{self.line}:{self.column}"


class MossError(Exception):
    """Base class for user-facing Moss errors."""


class MossSyntaxError(MossError):
    def __init__(self, message: str, location: SourceLocation | None = None):
        self.message = message
        self.location = location
        if location is None:
            super().__init__(message)
        else:
            super().__init__(f"{location.format()}: {message}")


class MossRuntimeError(MossError):
    pass
