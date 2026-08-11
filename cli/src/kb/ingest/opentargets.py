"""Ingestion from the Open Targets target-disease association API."""

from __future__ import annotations

import time
from typing import Any


class _OpenTargetsMixin:
    def ingest_opentargets(self, *, query: str) -> dict[str, Any]:
        from tools.data_api import opentargets_search

        result = opentargets_search(query=query, entity_type="target")
        if result.get("error"):
            return {"error": result["error"], "source": "opentargets"}

        target_name = str(result.get("name", query)).strip() or query
        target_symbol = str(result.get("symbol", "")).strip()
        target_key = target_symbol or target_name
        target = self.substrate.upsert_entity(
            entity_type="gene",
            name=target_name,
            identifier=target_key,
            synonyms=[target_symbol] if target_symbol else [],
            metadata={"opentargets_id": result.get("entity_id", "")},
        )

        associations = result.get("top_disease_associations", []) or result.get("associations", []) or []
        created = 0
        for assoc in associations[:20]:
            disease_name = str(assoc.get("disease_name") or assoc.get("disease", "")).strip()
            if not disease_name:
                continue
            disease = self.substrate.upsert_entity(entity_type="disease", name=disease_name)
            score = float(assoc.get("overall_score", 0.5) or 0.5)
            ev = self.substrate.add_evidence(
                source_type="opentargets",
                source_ref=str(result.get("entity_id", "")),
                summary=f"{target_name} association with {disease_name}",
                score=max(0.4, min(score, 1.0)),
                tags=["genetics", "target_disease"],
                metadata={"association_score": score},
            )
            self.substrate.link_entities(
                subject_id=target.id,
                predicate="associated_with_disease",
                object_id=disease.id,
                evidence_id=ev.id,
                polarity="support",
                score=max(0.4, min(score, 1.0)),
                metadata={"source": "opentargets"},
            )
            created += 1

        self._state["source_runs"]["opentargets"] = time.time()
        self.save_state()
        self.substrate.save()
        return {
            "summary": f"Ingested Open Targets associations for '{query}' ({created} relation(s)).",
            "source": "opentargets",
            "relations_created": created,
        }
