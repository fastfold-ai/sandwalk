"""
Clean-room parity tools built from public/open APIs.

Adds practical connectors and utilities inspired by commonly requested platform
capabilities while staying implementation-original inside ct.

Split across tools/parity_common.py (shared helpers), tools/parity_bioentity.py
(mygene_lookup/mydisease_lookup/myvariant_lookup/mytaxon_lookup/mychem_lookup),
tools/parity_search.py (pdbe_search/reactome_pathway_search/preprint_search),
and tools/parity_chemistry.py (sa_score); re-exported here for backward
compatibility. This module is the canonical patch target for tests
(e.g. ``patch("tools.parity.request_json")``); submodules access
``request``/``request_json`` indirectly via ``from tools import parity as
_parity`` so that such patches take effect regardless of which submodule
performs the call.
"""

from __future__ import annotations

from tools.http_client import request, request_json
from tools.parity_bioentity import (
    mychem_lookup,
    mydisease_lookup,
    mygene_lookup,
    mytaxon_lookup,
    myvariant_lookup,
)
from tools.parity_chemistry import _count_aromatic_rings, sa_score
from tools.parity_common import (
    _clip,
    _coerce_int,
    _flatten_hits,
    _MYGENE_SPECIES_MAP,
    _normalize_mygene_species,
)
from tools.parity_search import pdbe_search, preprint_search, reactome_pathway_search

__all__ = [
    "request",
    "request_json",
    "_clip",
    "_coerce_int",
    "_flatten_hits",
    "_MYGENE_SPECIES_MAP",
    "_normalize_mygene_species",
    "mygene_lookup",
    "mydisease_lookup",
    "myvariant_lookup",
    "mytaxon_lookup",
    "mychem_lookup",
    "pdbe_search",
    "reactome_pathway_search",
    "preprint_search",
    "_count_aromatic_rings",
    "sa_score",
]
