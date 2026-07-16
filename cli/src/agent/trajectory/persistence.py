"""Save/load and usage-data persistence for Trajectory."""

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .turn import Turn


class PersistenceMixin:
    """Adds `save`, `load`, and usage-data accessors to Trajectory."""

    turns: list[Turn]
    session_id: str | None
    title: str | None
    created_at: float
    updated_at: float
    model: str | None
    usage_data: dict[str, Any]

    def save(self, path: Path | None = None):
        """Persist trajectory to a JSONL file."""
        if path is None:
            if not self.session_id:
                raise ValueError("Cannot save trajectory without session_id.")
            path = self.session_path(self.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            # First line: session metadata
            meta = {
                "type": "meta",
                "session_id": self.session_id,
                "title": self.title,
                "created_at": self.created_at,
                "updated_at": self.updated_at or self.created_at,
                "model": self.model,
                "n_turns": len(self.turns),
                "usage_data": self.usage_data,
            }
            f.write(json.dumps(meta) + "\n")
            # Subsequent lines: turns
            for turn in self.turns:
                record = {"type": "turn", **asdict(turn)}
                f.write(json.dumps(record) + "\n")

    @classmethod
    def load(cls, path_or_session_id: Path | str) -> "PersistenceMixin":
        """Load a trajectory from a JSONL file path or session id/prefix."""
        path = cls.resolve_session_path(path_or_session_id)
        trajectory = cls()
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    import logging
                    logging.getLogger("trajectory").warning(
                        "Skipping corrupted line in trajectory %s: %s", path, e,
                    )
                    continue
                if record.get("type") == "meta":
                    trajectory.session_id = record.get("session_id")
                    trajectory.title = record.get("title")
                    trajectory.created_at = record.get("created_at", 0)
                    trajectory.updated_at = record.get("updated_at", trajectory.created_at)
                    trajectory.model = record.get("model")
                    usage_data = record.get("usage_data", {})
                    trajectory.usage_data = usage_data if isinstance(usage_data, dict) else {}
                elif record.get("type") == "turn":
                    turn = Turn(
                        query=record.get("query", ""),
                        answer=record.get("answer", ""),
                        entities=record.get("entities", []),
                        tools_used=record.get("tools_used", []),
                        timestamp=record.get("timestamp", 0),
                    )
                    trajectory.turns.append(turn)
        return trajectory

    def set_usage_data(self, usage_data: dict[str, Any]) -> None:
        """Persisted usage metadata for /usage restoration on resume."""
        self.usage_data = dict(usage_data or {})
        self.updated_at = time.time()

    def get_usage_data(self) -> dict[str, Any]:
        """Return persisted usage metadata for this session."""
        return dict(self.usage_data or {})
