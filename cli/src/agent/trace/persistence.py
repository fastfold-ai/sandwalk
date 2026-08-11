"""Save/load and text rendering for TraceLogger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent.config import CONFIG_DIR


class PersistenceMixin:
    """Adds `traces_dir`, `save`, `load`, and `to_text` to TraceLogger."""

    session_id: str
    events: list[dict[str, Any]]

    @staticmethod
    def traces_dir() -> Path:
        d = CONFIG_DIR / "traces"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save(self, path: Path | None = None) -> Path:
        out = path or (self.traces_dir() / f"{self.session_id}.trace.jsonl")
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            for event in self.events:
                f.write(json.dumps(event, default=str) + "\n")
        return out

    @classmethod
    def load(cls, path: Path | str):
        p = Path(path)
        events: list[dict[str, Any]] = []
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        session_id = ""
        for e in events:
            if e.get("type") == "query_start" and e.get("session_id"):
                session_id = str(e["session_id"])
                break
        if not session_id:
            session_id = p.stem.replace(".trace", "")
        obj = cls(session_id=session_id)
        obj.events = events
        return obj

    def to_text(self) -> str:
        return "\n".join(json.dumps(e, default=str) for e in self.events)
