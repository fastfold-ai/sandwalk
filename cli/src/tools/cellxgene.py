"""
CELLxGENE Census tools for querying single-cell expression data.

Uses the CZ CELLxGENE Census API to query gene expression across tissues
and cell types without downloading terabytes of local data.

Split across cellxgene_expression.py, cellxgene_markers.py, and
cellxgene_datasets.py; re-exported here for backward compatibility.
"""

from tools.cellxgene_common import _check_census_sdk
from tools.cellxgene_datasets import dataset_search
from tools.cellxgene_expression import gene_expression
from tools.cellxgene_markers import cell_type_markers

__all__ = [
    "_check_census_sdk",
    "gene_expression",
    "cell_type_markers",
    "dataset_search",
]
