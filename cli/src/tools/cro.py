"""
CRO (Contract Research Organization) tools: search, match, compare, and contact CROs.

PLACEHOLDER IMPLEMENTATION: All CRO data comes from a static JSON file bundled with ct.
This is not a live database — CRO listings, pricing, and turnaround times may be
outdated or incomplete. A real implementation would integrate with CRO directories
or vendor APIs. Treat results as illustrative, not authoritative.

Split across cro_search.py, cro_match.py, cro_compare.py, and cro_inquiry.py
(+ cro_common.py for shared DB loading/scoring); re-exported here for
backward compatibility.
"""

from tools.cro_common import _cro_db_cache, _load_cro_db, _score_cro
from tools.cro_compare import compare
from tools.cro_inquiry import draft_inquiry, send_inquiry
from tools.cro_match import match_experiment
from tools.cro_search import search

__all__ = [
    "search",
    "match_experiment",
    "compare",
    "draft_inquiry",
    "send_inquiry",
    "_load_cro_db",
    "_score_cro",
    "_cro_db_cache",
]
