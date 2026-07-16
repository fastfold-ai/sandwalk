"""
Canonical R&D knowledge substrate.

Stores normalized entities, evidence, and typed relations in a local JSON store.
This is the foundational layer for cross-modal pharma knowledge accumulation.

``KnowledgeSubstrate`` is assembled from focused mixins (persistence, entities,
evidence, relations, search) so each concern stays in its own module.
"""

from __future__ import annotations

from kb.substrate.entities import _EntityMixin
from kb.substrate.evidence import _EvidenceMixin
from kb.substrate.records import KBClaim, KBEntity, KBEvidence, KBRelation
from kb.substrate.relations import _RelationMixin
from kb.substrate.search import _SearchMixin
from kb.substrate.store import _StoreMixin

__all__ = [
    "KnowledgeSubstrate",
    "KBEntity",
    "KBEvidence",
    "KBClaim",
    "KBRelation",
]


class KnowledgeSubstrate(_StoreMixin, _EntityMixin, _EvidenceMixin, _RelationMixin, _SearchMixin):
    """Local persistent knowledge substrate."""
