"""
Data API tools: rich wrappers for major biomedical data platforms.

Provides general-purpose access to DepMap, Open Targets, UniProt, PDB,
Ensembl, NCBI, ChEMBL, and DrugBank/PubChem.

Split across tools/data_api_*.py sibling modules; re-exported here for
backward compatibility. This module is the canonical patch target for tests
(e.g. ``patch("tools.data_api._http_get")``); submodules access shared
helpers indirectly via ``from tools import data_api as _data_api`` so that
such patches take effect regardless of which submodule performs the call.
"""

from tools.data_api_common import _http_get, _http_post, _logger, _normalize_drug_query, _normalize_gene_name
from tools.data_api_depmap import depmap_search
from tools.data_api_opentargets import opentargets_search
from tools.data_api_uniprot_helpers import (
    _build_uniprot_search_candidates,
    _extract_species_phrases,
    _keyword_fallback_query,
    _query_has_non_human_hints,
    _UNIPROT_NON_HUMAN_HINTS,
    _UNIPROT_QUERY_STOPWORDS,
)
from tools.data_api_uniprot_scoring import _entry_relevance_score, _entry_text_blob
from tools.data_api_uniprot import uniprot_lookup
from tools.data_api_pdb_detail import fetch_pdb_entry as _fetch_pdb_entry
from tools.data_api_pdb import pdb_search
from tools.data_api_ensembl import ensembl_lookup
from tools.data_api_ncbi import ncbi_gene
from tools.data_api_chembl_compound import _chembl_compound_search
from tools.data_api_chembl_activities import _chembl_target_activities
from tools.data_api_chembl_mechanism import _chembl_drug_indication, _chembl_mechanism
from tools.data_api_chembl import chembl_advanced
from tools.data_api_druginfo import drug_info

__all__ = [
    "_http_get",
    "_http_post",
    "_logger",
    "_normalize_gene_name",
    "_normalize_drug_query",
    "depmap_search",
    "opentargets_search",
    "_query_has_non_human_hints",
    "_keyword_fallback_query",
    "_extract_species_phrases",
    "_build_uniprot_search_candidates",
    "_entry_text_blob",
    "_entry_relevance_score",
    "_UNIPROT_NON_HUMAN_HINTS",
    "_UNIPROT_QUERY_STOPWORDS",
    "uniprot_lookup",
    "pdb_search",
    "_fetch_pdb_entry",
    "ensembl_lookup",
    "ncbi_gene",
    "chembl_advanced",
    "_chembl_compound_search",
    "_chembl_target_activities",
    "_chembl_mechanism",
    "_chembl_drug_indication",
    "drug_info",
]
