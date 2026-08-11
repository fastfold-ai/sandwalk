"""
Chemistry tools: molecular descriptors, SAR analysis, similarity search.

Split across tools/chemistry_*.py sibling modules; re-exported here for
backward compatibility. This module is the canonical patch target for tests
(e.g. ``patch("tools.chemistry._extract_smiles")``); submodules access shared
helpers indirectly via ``from tools import chemistry as _chemistry`` so that
such patches take effect regardless of which submodule performs the call.
"""

from tools.chemistry_common import _extract_smiles
from tools.chemistry_descriptors import descriptors
from tools.chemistry_mmp import mmp_analysis
from tools.chemistry_pharmacophore import pharmacophore
from tools.chemistry_pubchem import pubchem_lookup
from tools.chemistry_retrosynthesis import retrosynthesis
from tools.chemistry_sar import sar_analyze
from tools.chemistry_scaffold_hop import scaffold_hop
from tools.chemistry_similarity import pairwise_similarity, similarity_search
from tools.http_client import request

__all__ = [
    "request",
    "_extract_smiles",
    "descriptors",
    "pairwise_similarity",
    "similarity_search",
    "sar_analyze",
    "mmp_analysis",
    "scaffold_hop",
    "pubchem_lookup",
    "retrosynthesis",
    "pharmacophore",
]
