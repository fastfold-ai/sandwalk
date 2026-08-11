"""Perturbation/viability loaders: proteomics, L1000, PRISM."""

from functools import lru_cache
from pathlib import Path

import pandas as pd

from agent.config import Config
from data.loaders.paths import _read_tabular, _resolve_path


@lru_cache(maxsize=1)
def load_proteomics() -> pd.DataFrame:
    """Load proteomics LFC matrix."""
    from data.loaders import _find_file

    _prot_files = ["proteomics_log2fc_matrix.parquet", "proteomics_log2fc_matrix.csv", "merged_proteomics.csv"]
    # Check configured path
    cfg = Config.load()
    explicit = cfg.get("data.proteomics")
    if explicit:
        p = _resolve_path(Path(explicit), _prot_files)
        if p:
            return _read_tabular(p, index_col=0)

    # Search common locations
    for name in ["merged_proteomics.csv", "proteomics_log2fc_matrix.parquet",
                 "proteomics_log2fc_matrix.csv"]:
        path = _find_file(name)
        if path:
            return _read_tabular(path, index_col=0)

    raise FileNotFoundError(
        "Proteomics data not found. "
        "Set: sandwalk config set data.proteomics /path/to/file"
    )


@lru_cache(maxsize=1)
def load_l1000() -> pd.DataFrame:
    """Load L1000 landmark gene expression data.

    Prefers the compound-named profiles parquet (19,811 compounds × 978 genes)
    built from the Broad LINCS GSE92742 Level 5 GCTX. Falls back to legacy
    formats (YU-indexed parquet/CSV).
    """
    from data.loaders import _find_file

    cfg = Config.load()

    # 1. Prefer compound-named profiles (from LINCS GCTX, 19,811 compounds)
    lincs_path = Path("/mnt2/bronze/lincs/l1000_compound_profiles.parquet")
    if lincs_path.exists():
        return _read_tabular(lincs_path, index_col=0)

    # 2. Check data.base for compound profiles
    base = cfg.get("data.base")
    if base:
        candidate = Path(base) / "lincs" / "l1000_compound_profiles.parquet"
        if candidate.exists():
            return _read_tabular(candidate, index_col=0)

    # 3. Check explicit config (may point to legacy YU-indexed data)
    explicit = cfg.get("data.l1000")
    if explicit:
        _l1000_files = [
            "l1000_compound_profiles.parquet",
            "l1000_landmark_only.parquet",
            "L1000_landmark_LFC.csv",
            "l1000_expression_matrix.parquet",
            "l1000_landmark_only.csv",
        ]
        p = _resolve_path(Path(explicit), _l1000_files)
        if p:
            return _read_tabular(p, index_col=0)

    # 4. Fall back to legacy formats
    for name in ["l1000_compound_profiles.parquet", "L1000_landmark_LFC.csv",
                 "l1000_landmark_only.parquet", "l1000_expression_matrix.parquet",
                 "l1000_landmark_only.csv"]:
        path = _find_file(name, subdirs=["", "lincs", "l1000"])
        if path:
            return _read_tabular(path, index_col=0)

    raise FileNotFoundError(
        "L1000 data not found. "
        "Set: sandwalk config set data.l1000 /path/to/file"
    )


@lru_cache(maxsize=1)
def load_prism() -> pd.DataFrame:
    """Load PRISM cell viability data."""
    from data.loaders import _find_file

    _prism_files = ["prism_LFC_COLLAPSED.csv", "prism_LFC_COLLAPSED.parquet"]
    cfg = Config.load()
    explicit = cfg.get("data.prism")
    if explicit:
        p = _resolve_path(Path(explicit), _prism_files)
        if p:
            return _read_tabular(p)

    for name in ["prism_LFC_COLLAPSED.csv", "prism_LFC_COLLAPSED.parquet"]:
        path = _find_file(name)
        if path:
            return _read_tabular(path)

    raise FileNotFoundError(
        "PRISM data not found. "
        "Run: sandwalk data pull prism\n"
        "Or set: sandwalk config set data.prism /path/to/file"
    )
