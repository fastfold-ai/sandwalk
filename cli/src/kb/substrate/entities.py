"""Entity upsert/lookup mixin."""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from kb.substrate.records import KBEntity


class _EntityMixin:
    def upsert_entity(
        self,
        *,
        entity_type: str,
        name: str,
        identifier: str | None = None,
        synonyms: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KBEntity:
        """Insert/update entity and return canonical record."""
        canonical = self.normalize_identifier(entity_type, identifier or name)
        entity_id = f"{entity_type.lower()}:{canonical}"
        now = time.time()
        existing = self._data["entities"].get(entity_id)
        syn_items = list(synonyms or []) + [name]
        if identifier:
            syn_items.append(str(identifier))
        syn = sorted(set(syn_items))
        if existing:
            existing_syn = set(existing.get("synonyms", []))
            existing["synonyms"] = sorted(existing_syn | set(syn))
            if metadata:
                existing_meta = existing.get("metadata", {})
                existing_meta.update(metadata)
                existing["metadata"] = existing_meta
            existing["last_seen"] = now
            self._data["entities"][entity_id] = existing
            return KBEntity(**existing)

        entity = KBEntity(
            id=entity_id,
            entity_type=entity_type.lower(),
            name=name,
            synonyms=syn,
            metadata=metadata or {},
            first_seen=now,
            last_seen=now,
        )
        self._data["entities"][entity_id] = asdict(entity)
        return entity

    def get_entity(self, entity_id: str) -> KBEntity | None:
        rec = self._data["entities"].get(entity_id)
        if not rec:
            return None
        return KBEntity(**rec)
