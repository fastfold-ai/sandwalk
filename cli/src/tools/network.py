"""
Network biology tools: protein-protein interaction analysis (STRING) and pathway crosstalk (Reactome).

These are REST API wrappers -- no local data required.

Split across network_ppi.py (+ network_ppi_stats.py) and network_pathway.py
(+ network_pathway_stats.py); re-exported here for backward compatibility.
"""

from tools.network_common import _coerce_gene_list
from tools.network_pathway import pathway_crosstalk
from tools.network_ppi import ppi_analysis

__all__ = ["ppi_analysis", "pathway_crosstalk", "_coerce_gene_list"]
