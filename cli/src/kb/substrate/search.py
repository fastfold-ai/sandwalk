"""Entity text-search mixin."""

from __future__ import annotations

import re

from kb.substrate.records import KBEntity


class _SearchMixin:
    def search_entities(self, query: str, limit: int = 20) -> list[KBEntity]:
        """Simple text search by canonical name/synonyms."""
        q = (query or "").strip().lower()
        if not q:
            return []
        hits: list[tuple[float, KBEntity]] = []
        terms = set(re.findall(r"[a-z0-9-]{2,}", q))
        for rec in self._data["entities"].values():
            entity = KBEntity(**rec)
            haystack = " ".join([entity.name] + entity.synonyms).lower()
            if q in haystack:
                score = 1.0
            else:
                tokens = set(re.findall(r"[a-z0-9-]{2,}", haystack))
                score = len(terms & tokens) / max(len(terms), 1)
            if score <= 0:
                continue
            hits.append((score, entity))
        hits.sort(key=lambda x: (x[0], x[1].last_seen), reverse=True)
        return [h[1] for h in hits[: max(limit, 0)]]
