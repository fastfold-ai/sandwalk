"""Persistence mixin: load/save the JSON-backed substrate and summary stats."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from agent.config import CONFIG_DIR
from kb.substrate.normalize import infer_entity_type, normalize_identifier


class _StoreMixin:
    """Local persistent knowledge substrate — load/save/summary."""

    SCHEMA_VERSION = 1

    def __init__(self, path: Path | None = None):
        self.path = path or (CONFIG_DIR / "knowledge" / "substrate.json")
        self._data = self._load()

    normalize_identifier = staticmethod(normalize_identifier)
    infer_entity_type = staticmethod(infer_entity_type)

    def _default(self) -> dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "created_at": time.time(),
            "updated_at": time.time(),
            "next_evidence_id": 1,
            "entities": {},
            "evidence": {},
            "relations": {},
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._default()

        if not isinstance(payload, dict):
            return self._default()
        payload.setdefault("schema_version", self.SCHEMA_VERSION)
        payload.setdefault("created_at", time.time())
        payload.setdefault("updated_at", time.time())
        payload.setdefault("next_evidence_id", 1)
        payload.setdefault("entities", {})
        payload.setdefault("evidence", {})
        payload.setdefault("relations", {})
        return payload

    def save(self) -> None:
        """Persist substrate to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data["updated_at"] = time.time()
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def summary(self) -> dict[str, Any]:
        """High-level substrate stats."""
        entity_types: dict[str, int] = {}
        for rec in self._data["entities"].values():
            et = rec.get("entity_type", "unknown")
            entity_types[et] = entity_types.get(et, 0) + 1
        return {
            "path": str(self.path),
            "schema_version": self._data.get("schema_version", self.SCHEMA_VERSION),
            "n_entities": len(self._data["entities"]),
            "n_relations": len(self._data["relations"]),
            "n_evidence": len(self._data["evidence"]),
            "entity_types": entity_types,
            "updated_at": self._data.get("updated_at"),
        }
