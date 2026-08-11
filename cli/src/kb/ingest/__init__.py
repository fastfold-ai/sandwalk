"""
Knowledge ingestion and normalization pipeline.

Builds the knowledge substrate from:
- local evidence logs (always available)
- optional live APIs (PubMed, OpenAlex, Open Targets)

``KnowledgeIngestionPipeline`` is assembled from focused mixins (state,
dispatch, evidence store, literature, Open Targets) so each source stays in
its own module.
"""

from __future__ import annotations

from kb.ingest.dispatch import _DispatchMixin
from kb.ingest.evidence_store import _EvidenceStoreMixin
from kb.ingest.literature import _LiteratureMixin
from kb.ingest.opentargets import _OpenTargetsMixin
from kb.ingest.state import _StateMixin

__all__ = ["KnowledgeIngestionPipeline"]


class KnowledgeIngestionPipeline(
    _StateMixin,
    _DispatchMixin,
    _EvidenceStoreMixin,
    _LiteratureMixin,
    _OpenTargetsMixin,
):
    """Incremental ingestion pipeline into the canonical knowledge substrate."""
