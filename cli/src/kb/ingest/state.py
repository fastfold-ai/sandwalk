"""Ingestion run-state persistence mixin (evidence offsets, per-source run timestamps)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from agent.config import CONFIG_DIR
from kb.substrate import KnowledgeSubstrate


class _StateMixin:
    """Constructor and JSON state load/save for the ingestion pipeline."""

    def __init__(
        self,
        substrate: KnowledgeSubstrate | None = None,
        *,
        state_path: Path | None = None,
        evidence_path: Path | None = None,
    ):
        self.substrate = substrate or KnowledgeSubstrate()
        self.state_path = state_path or (CONFIG_DIR / "knowledge" / "ingest_state.json")
        self.evidence_path = evidence_path or (CONFIG_DIR / "evidence" / "evidence.jsonl")
        self._state = self._load_state()

    def _default_state(self) -> dict[str, Any]:
        return {
            "updated_at": time.time(),
            "evidence_line_offset": 0,
            "source_runs": {},
        }

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._default_state()
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._default_state()
        if not isinstance(data, dict):
            return self._default_state()
        data.setdefault("updated_at", time.time())
        data.setdefault("evidence_line_offset", 0)
        data.setdefault("source_runs", {})
        return data

    def save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state["updated_at"] = time.time()
        self.state_path.write_text(
            json.dumps(self._state, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
