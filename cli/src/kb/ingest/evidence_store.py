"""Ingestion from the local evidence log (session steps + synthesis)."""

from __future__ import annotations

import json
import time
from typing import Any

from kb.substrate import KnowledgeSubstrate


class _EvidenceStoreMixin:
    def ingest_evidence_store(self, *, scan_limit: int = 1000) -> dict[str, Any]:
        """Ingest new rows from local evidence log."""
        if not self.evidence_path.exists():
            return {
                "summary": "No local evidence store found.",
                "source": "evidence_store",
                "ingested_records": 0,
            }

        try:
            lines = self.evidence_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            return {"error": f"Failed reading evidence store: {exc}"}

        start = int(self._state.get("evidence_line_offset", 0))
        if start >= len(lines):
            return {
                "summary": "No new evidence records to ingest.",
                "source": "evidence_store",
                "ingested_records": 0,
            }

        new_lines = lines[start:][: max(scan_limit, 0)]
        ingested = 0
        linked_entities = 0
        for line in new_lines:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            entities = self._ingest_evidence_record(record)
            linked_entities += entities
            ingested += 1

        self._state["evidence_line_offset"] = start + len(new_lines)
        self._state["source_runs"]["evidence_store"] = time.time()
        self.save_state()
        self.substrate.save()
        return {
            "summary": (
                f"Ingested {ingested} evidence record(s) from local store; "
                f"linked {linked_entities} entity mention(s)."
            ),
            "source": "evidence_store",
            "ingested_records": ingested,
            "linked_entities": linked_entities,
            "new_offset": self._state["evidence_line_offset"],
        }

    def _ingest_evidence_record(self, record: dict[str, Any]) -> int:
        query = str(record.get("query", "")).strip()
        synthesis = str(record.get("synthesis_preview", "")).strip()
        session_id = str(record.get("session_id", "")).strip()
        steps = record.get("steps", []) or []

        query_entities = self._extract_entity_mentions(query)
        if not query_entities and query:
            query_entities = [query]

        ev = self.substrate.add_evidence(
            source_type="session",
            source_ref=session_id or "unknown_session",
            summary=synthesis or query,
            score=0.6,
            tags=["session", "evidence_store"],
            metadata={"n_completed_steps": int(record.get("n_completed_steps", 0) or 0)},
        )

        entity_ids = []
        for mention in query_entities:
            entity_type = KnowledgeSubstrate.infer_entity_type(mention)
            entity = self.substrate.upsert_entity(entity_type=entity_type, name=mention)
            entity_ids.append(entity.id)

        for i, left in enumerate(entity_ids):
            for right in entity_ids[i + 1:]:
                self.substrate.link_entities(
                    subject_id=left,
                    predicate="co_mentioned_in_query",
                    object_id=right,
                    evidence_id=ev.id,
                    polarity="support",
                    score=0.55,
                    metadata={"source": "query"},
                )

        linked = len(entity_ids)
        for step in steps:
            linked = self._ingest_step(step, entity_ids, query_entities, session_id, linked)
        return linked

    def _ingest_step(self, step, entity_ids, query_entities, session_id, linked) -> int:
        tool_name = str(step.get("tool", "")).strip()
        step_desc = str(step.get("description", "")).strip()
        step_summary = str(step.get("result_summary", "")).strip()
        if not tool_name:
            return linked

        tool_entity = self.substrate.upsert_entity(
            entity_type="tool",
            name=tool_name,
            identifier=tool_name,
        )
        step_ev = self.substrate.add_evidence(
            source_type="tool",
            source_ref=tool_name,
            summary=(step_summary or step_desc)[:1200],
            score=0.65,
            tags=["step_result"],
            metadata={"step_id": step.get("id"), "session_id": session_id},
        )

        for eid in entity_ids:
            self.substrate.link_entities(
                subject_id=eid,
                predicate="analyzed_with",
                object_id=tool_entity.id,
                evidence_id=step_ev.id,
                polarity="support",
                score=0.65,
                metadata={"step_id": step.get("id")},
            )

        step_entities = self._extract_entity_mentions(f"{step_desc} {step_summary}")
        for mention in step_entities:
            if mention in query_entities:
                continue
            se = self.substrate.upsert_entity(
                entity_type=KnowledgeSubstrate.infer_entity_type(mention),
                name=mention,
            )
            linked += 1
            for eid in entity_ids:
                self.substrate.link_entities(
                    subject_id=eid,
                    predicate="associated_with",
                    object_id=se.id,
                    evidence_id=step_ev.id,
                    polarity="support",
                    score=0.6,
                )
        return linked
