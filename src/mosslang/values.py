from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __str__(self) -> str:
        return f"{self.amount.normalize()}.{self.currency}"


@dataclass(frozen=True)
class Variant:
    name: str
    payload: tuple[Any, ...] = ()

    def __str__(self) -> str:
        if not self.payload:
            return self.name
        inner = ", ".join(format_value(value) for value in self.payload)
        return f"{self.name}({inner})"


@dataclass(frozen=True)
class Result:
    ok: bool
    value: Any

    def __str__(self) -> str:
        tag = "Ok" if self.ok else "Err"
        return f"{tag}({format_value(self.value)})"


def format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, dict):
        fields = ", ".join(f"{key}: {format_value(item)}" for key, item in value.items())
        return "{" + fields + "}"
    return str(value)
