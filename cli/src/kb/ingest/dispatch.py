"""Source dispatch and shared entity-mention extraction helpers."""

from __future__ import annotations

import re
from typing import Any

from kb.substrate import KnowledgeSubstrate


class _DispatchMixin:
    def ingest(
        self,
        *,
        source: str,
        query: str | None = None,
        max_results: int = 10,
        scan_limit: int = 1000,
    ) -> dict[str, Any]:
        """Ingest from one source into substrate."""
        src = (source or "").strip().lower()
        if src == "evidence_store":
            return self.ingest_evidence_store(scan_limit=scan_limit)
        if src == "pubmed":
            if not query:
                return {"error": "query is required for source=pubmed"}
            return self.ingest_pubmed(query=query, max_results=max_results)
        if src == "openalex":
            if not query:
                return {"error": "query is required for source=openalex"}
            return self.ingest_openalex(query=query, max_results=max_results)
        if src == "opentargets":
            if not query:
                return {"error": "query is required for source=opentargets"}
            return self.ingest_opentargets(query=query)
        return {"error": f"Unknown source '{source}'"}

    def _get_or_create_query_entities(self, query: str) -> list[str]:
        mentions = self._extract_entity_mentions(query)
        if not mentions and query:
            mentions = [query]
        ids = []
        for mention in mentions:
            entity = self.substrate.upsert_entity(
                entity_type=KnowledgeSubstrate.infer_entity_type(mention),
                name=mention,
            )
            ids.append(entity.id)
        return ids

    def _extract_entity_mentions(self, text: str) -> list[str]:
        mentions = []
        # Add PMID/NCT mentions if present.
        mentions.extend(re.findall(r"\bPMID[:\s]?\d+\b", text or "", flags=re.IGNORECASE))
        mentions.extend(re.findall(r"\bNCT\d{8}\b", text or "", flags=re.IGNORECASE))
        dedup = []
        seen = set()
        for m in mentions:
            norm = m.strip()
            if not norm:
                continue
            key = norm.lower()
            if key in seen:
                continue
            seen.add(key)
            dedup.append(norm)
        return dedup
