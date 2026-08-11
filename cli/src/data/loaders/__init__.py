"""
Data loaders for common drug discovery datasets.

Each loader checks configured paths, then the ct-data sister project,
and supports both CSV and Parquet formats.
Data paths are configured via sandwalk config.
"""

from agent.config import CONFIG_DIR, Config
from data.loaders.depmap import load_crispr, load_model_metadata, load_mutations
from data.loaders.genesets import load_msigdb
from data.loaders.omics import load_l1000, load_prism, load_proteomics
from data.loaders.paths import (
    _DATA_SEARCH_PATHS,
    _data_path,
    _find_file,
    _read_tabular,
    _resolve_path,
)

__all__ = [
    "CONFIG_DIR",
    "Config",
    "load_crispr",
    "load_model_metadata",
    "load_mutations",
    "load_msigdb",
    "load_l1000",
    "load_prism",
    "load_proteomics",
    "_data_path",
    "_DATA_SEARCH_PATHS",
    "_find_file",
    "_read_tabular",
    "_resolve_path",
]
