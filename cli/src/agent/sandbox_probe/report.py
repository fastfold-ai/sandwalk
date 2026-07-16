"""Probe report data structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ProbeStep:
    name: str
    ok: bool
    detail: str


@dataclass
class ProbeReport:
    ok: bool
    steps: list[ProbeStep]
    skipped: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "skipped": self.skipped,
            "steps": [
                {"name": s.name, "ok": s.ok, "detail": s.detail} for s in self.steps
            ],
        }
