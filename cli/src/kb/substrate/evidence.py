"""Evidence recording/lookup mixin."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from kb.substrate.records import KBEvidence


class _EvidenceMixin:
    def add_evidence(
        self,
        *,
        source_type: str,
        source_ref: str,
        summary: str,
        score: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KBEvidence:
        """Record evidence statement with provenance."""
        next_id = int(self._data.get("next_evidence_id", 1))
        evidence_id = f"e:{next_id}"
        self._data["next_evidence_id"] = next_id + 1
        ev = KBEvidence(
            id=evidence_id,
            source_type=(source_type or "unknown").lower(),
            source_ref=source_ref or "",
            summary=(summary or "")[:2000],
            score=max(0.0, min(1.0, float(score))),
            tags=tags or [],
            metadata=metadata or {},
        )
        self._data["evidence"][evidence_id] = asdict(ev)
        return ev

    def get_evidence(self, evidence_id: str) -> KBEvidence | None:
        rec = self._data["evidence"].get(evidence_id)
        if not rec:
            return None
        return KBEvidence(**rec)
