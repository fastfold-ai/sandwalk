"""
Literature and database tools: PubMed, OpenAlex, ChEMBL, and patent search.

These are REST API wrappers -- no local data required.

Split across tools/literature_pubmed.py, tools/literature_chembl.py,
tools/literature_openalex.py, and tools/literature_patents.py; re-exported here
for backward compatibility. This module is the canonical patch target for tests
(e.g. ``patch("tools.literature.request_json")``, ``monkeypatch.setattr("tools.literature.pubmed_search", ...)``);
submodules access shared helpers and cross-cluster tools indirectly via
``from tools import literature as _literature`` so that such patches take effect
regardless of which submodule performs the call.
"""

from tools.http_client import request, request_json
from tools.literature_chembl import chembl_query
from tools.literature_openalex import openalex_search
from tools.literature_patents import (
    _patent_search_epo,
    _patent_search_lens,
    _patent_search_pubmed_fallback,
    patent_search,
)
from tools.literature_pubmed import _normalize_pubmed_query, _simplify_query, pubmed_search

__all__ = [
    "request",
    "request_json",
    "_normalize_pubmed_query",
    "_simplify_query",
    "pubmed_search",
    "chembl_query",
    "openalex_search",
    "patent_search",
    "_patent_search_lens",
    "_patent_search_epo",
    "_patent_search_pubmed_fallback",
]
