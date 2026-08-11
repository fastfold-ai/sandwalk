"""
Omics data discovery, download, and inspection tools.

Provides search and fetch capabilities for major public omics repositories:
- NCBI GEO (Gene Expression Omnibus)
- CELLxGENE Discover (Chan Zuckerberg Initiative)
- TCGA/GDC (The Cancer Genome Atlas via Genomic Data Commons)

Also provides local dataset inspection for downloaded files, plus a range of
per-modality analysis tools (methylation, proteomics, ATAC/ChIP-seq, spatial,
CyTOF, Hi-C, DESeq2, multi-omics integration, KEGG ORA).

Split across tools/omics_*.py sibling modules; re-exported here for backward
compatibility. This module is the canonical patch target for tests
(e.g. ``patch("tools.omics.request_json")``); submodules access shared
helpers indirectly via ``from tools import omics as _omics`` so that such
patches take effect regardless of which submodule performs the call.
"""

from agent.config import CONFIG_DIR
from tools.http_client import request, request_json
from tools.omics_atac import atac_peak_annotate, chipseq_enrich
from tools.omics_cellxgene_fetch import cellxgene_fetch
from tools.omics_cellxgene_search import cellxgene_search
from tools.omics_chromatin import chromatin_accessibility, hic_compartments
from tools.omics_common import (
    _check_episcanpy,
    _check_muon,
    _check_pydeseq2,
    _check_scanpy,
    _downloads_dir,
    _max_download_mb,
    _stream_download,
    logger,
)
from tools.omics_cytof import cytof_cluster
from tools.omics_deseq2 import deseq2
from tools.omics_geo_fetch import geo_fetch
from tools.omics_geo_search import geo_search
from tools.omics_inspect import _inspect_h5ad, _inspect_tabular, dataset_info
from tools.omics_kegg import KEGG_ORA_SYSTEM_PROMPT, kegg_ora
from tools.omics_loaders import _inspect_matrix_gz, _load_tabular
from tools.omics_methylation_cluster import methylation_cluster
from tools.omics_methylation_diff import methylation_diff, methylation_profile
from tools.omics_multiomics import multiomics_integrate
from tools.omics_proteomics_diff import proteomics_diff
from tools.omics_proteomics_enrich import proteomics_enrich
from tools.omics_spatial import spatial_cluster
from tools.omics_spatial_autocorrelation import spatial_autocorrelation
from tools.omics_stats import (
    _enrichr_libraries_for_organism,
    _fdr_correct,
    _parse_gene_list_file,
    _parse_sample_groups,
)
from tools.omics_tcga_fetch import tcga_fetch
from tools.omics_tcga_search import tcga_search

__all__ = [
    "CONFIG_DIR",
    "request",
    "request_json",
    "logger",
    "_downloads_dir",
    "_max_download_mb",
    "_stream_download",
    "_check_scanpy",
    "_check_pydeseq2",
    "_check_muon",
    "_check_episcanpy",
    "dataset_info",
    "_inspect_h5ad",
    "_inspect_tabular",
    "_inspect_matrix_gz",
    "_load_tabular",
    "_parse_sample_groups",
    "_fdr_correct",
    "_parse_gene_list_file",
    "_enrichr_libraries_for_organism",
    "geo_search",
    "geo_fetch",
    "cellxgene_search",
    "cellxgene_fetch",
    "tcga_search",
    "tcga_fetch",
    "methylation_diff",
    "methylation_profile",
    "proteomics_diff",
    "proteomics_enrich",
    "atac_peak_annotate",
    "chromatin_accessibility",
    "chipseq_enrich",
    "spatial_cluster",
    "spatial_autocorrelation",
    "cytof_cluster",
    "hic_compartments",
    "deseq2",
    "multiomics_integrate",
    "methylation_cluster",
    "KEGG_ORA_SYSTEM_PROMPT",
    "kegg_ora",
]
