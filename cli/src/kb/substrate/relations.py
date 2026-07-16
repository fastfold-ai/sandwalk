"""Relation linking/traversal mixin."""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from kb.substrate.records import KBClaim, KBRelation


class _RelationMixin:
    def link_entities(
        self,
        *,
        subject_id: str,
        predicate: str,
        object_id: str,
        evidence_id: str,
        polarity: str = "support",
        score: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> KBRelation:
        """Create or update relation edge with evidence claim."""
        relation_id = f"{subject_id}|{predicate}|{object_id}"
        now = time.time()
        claim = KBClaim(
            evidence_id=evidence_id,
            polarity=polarity if polarity in {"support", "contradict", "neutral"} else "neutral",
            score=max(0.0, min(1.0, float(score))),
            timestamp=now,
        )
        existing = self._data["relations"].get(relation_id)
        if existing:
            existing_claims = [
                KBClaim(**c) if isinstance(c, dict) else c for c in existing.get("claims", [])
            ]
            existing_claims.append(claim)
            existing["claims"] = [asdict(c) for c in existing_claims]
            if metadata:
                existing_meta = existing.get("metadata", {})
                existing_meta.update(metadata)
                existing["metadata"] = existing_meta
            existing["last_seen"] = now
            self._data["relations"][relation_id] = existing
            return KBRelation(
                id=relation_id,
                subject_id=existing["subject_id"],
                predicate=existing["predicate"],
                object_id=existing["object_id"],
                claims=[KBClaim(**c) for c in existing["claims"]],
                metadata=existing.get("metadata", {}),
                first_seen=float(existing.get("first_seen", now)),
                last_seen=float(existing.get("last_seen", now)),
            )

        rel = KBRelation(
            id=relation_id,
            subject_id=subject_id,
            predicate=predicate,
            object_id=object_id,
            claims=[claim],
            metadata=metadata or {},
            first_seen=now,
            last_seen=now,
        )
        self._data["relations"][relation_id] = {
            "id": rel.id,
            "subject_id": rel.subject_id,
            "predicate": rel.predicate,
            "object_id": rel.object_id,
            "claims": [asdict(claim)],
            "metadata": rel.metadata,
            "first_seen": rel.first_seen,
            "last_seen": rel.last_seen,
        }
        return rel

    def related_entities(
        self,
        entity_id: str,
        *,
        predicate: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List entities connected via relations with aggregate claim stats."""
        rows = []
        for rel in self._data["relations"].values():
            if rel.get("subject_id") != entity_id and rel.get("object_id") != entity_id:
                continue
            if predicate and rel.get("predicate") != predicate:
                continue
            claims = [KBClaim(**c) for c in rel.get("claims", [])]
            support = sum(1 for c in claims if c.polarity == "support")
            contradict = sum(1 for c in claims if c.polarity == "contradict")
            neutral = sum(1 for c in claims if c.polarity == "neutral")
            avg_score = sum(c.score for c in claims) / max(len(claims), 1)
            other = rel["object_id"] if rel["subject_id"] == entity_id else rel["subject_id"]
            rows.append(
                {
                    "relation_id": rel["id"],
                    "predicate": rel["predicate"],
                    "other_entity_id": other,
                    "support_claims": support,
                    "contradict_claims": contradict,
                    "neutral_claims": neutral,
                    "claim_count": len(claims),
                    "average_claim_score": round(avg_score, 4),
                    "last_seen": float(rel.get("last_seen", 0)),
                }
            )
        rows.sort(
            key=lambda r: (r["support_claims"] - r["contradict_claims"], r["average_claim_score"], r["last_seen"]),
            reverse=True,
        )
        return rows[: max(limit, 0)]

    def list_relations(self) -> list[KBRelation]:
        items = []
        for rec in self._data["relations"].values():
            items.append(
                KBRelation(
                    id=rec["id"],
                    subject_id=rec["subject_id"],
                    predicate=rec["predicate"],
                    object_id=rec["object_id"],
                    claims=[KBClaim(**c) for c in rec.get("claims", [])],
                    metadata=rec.get("metadata", {}),
                    first_seen=float(rec.get("first_seen", 0)),
                    last_seen=float(rec.get("last_seen", 0)),
                )
            )
        return items
