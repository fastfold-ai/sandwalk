"""omics.dataset_info: inspect local dataset files (h5ad/tabular). Split from tools/omics.py."""
from pathlib import Path

from tools import omics as _omics
from tools import registry


@registry.register(
    name="omics.dataset_info",
    description="Inspect a downloaded dataset file and return metadata summary",
    category="omics",
    parameters={
        "path": "Path to the downloaded dataset file (h5ad, CSV, TSV, or matrix.txt.gz)",
    },
    usage_guide=(
        "Inspect a downloaded omics file before analysis. Returns shape, columns, "
        "metadata. Use after omics.*_fetch to understand the data before running "
        "singlecell.* or code.execute on it."
    ),
)
def dataset_info(path: str, **kwargs) -> dict:
    """Inspect a downloaded dataset file and return metadata."""
    if not path:
        return {"error": "Path is required", "summary": "No path provided"}

    filepath = Path(path).expanduser()
    if not filepath.exists():
        return {"error": f"File not found: {path}", "summary": f"File not found: {path}"}

    size_mb = round(filepath.stat().st_size / (1024 * 1024), 2)
    suffix = filepath.suffix.lower()

    # Handle .gz suffix
    if suffix == ".gz":
        inner_suffix = Path(filepath.stem).suffix.lower()
        suffix = inner_suffix + suffix  # e.g. ".txt.gz"

    try:
        if suffix == ".h5ad":
            return _omics._inspect_h5ad(filepath, size_mb)
        elif suffix in (".csv", ".tsv", ".txt"):
            return _omics._inspect_tabular(filepath, size_mb, sep="," if suffix == ".csv" else "\t")
        elif suffix in (".txt.gz",):
            return _omics._inspect_matrix_gz(filepath, size_mb)
        else:
            return {
                "path": str(filepath),
                "file_type": suffix,
                "size_mb": size_mb,
                "summary": f"File type '{suffix}' not directly inspectable. Size: {size_mb} MB. Try loading with code.execute.",
            }
    except Exception as exc:
        return {
            "error": f"Inspection failed: {str(exc)[:200]}",
            "path": str(filepath),
            "size_mb": size_mb,
            "summary": f"Could not inspect {filepath.name}: {str(exc)[:100]}",
        }


def _inspect_h5ad(filepath: Path, size_mb: float) -> dict:
    """Inspect an h5ad file using scanpy."""
    sc = _omics._check_scanpy()
    if sc is None:
        return {
            "path": str(filepath),
            "file_type": "h5ad",
            "size_mb": size_mb,
            "error": "scanpy not installed. Install with: pip install scanpy",
            "summary": f"h5ad file ({size_mb} MB) — install scanpy to inspect: pip install scanpy",
        }

    adata = sc.read_h5ad(filepath)
    obs_cols = list(adata.obs.columns)
    var_cols = list(adata.var.columns)
    layers = list(adata.layers.keys()) if adata.layers else []

    return {
        "path": str(filepath),
        "file_type": "h5ad",
        "size_mb": size_mb,
        "n_cells": adata.n_obs,
        "n_genes": adata.n_vars,
        "obs_columns": obs_cols[:20],
        "var_columns": var_cols[:20],
        "layers": layers,
        "obs_preview": {col: list(adata.obs[col].unique()[:5]) for col in obs_cols[:5]},
        "summary": (
            f"h5ad: {adata.n_obs:,} cells x {adata.n_vars:,} genes ({size_mb} MB). "
            f"Obs columns: {', '.join(obs_cols[:8])}. "
            f"Layers: {', '.join(layers) if layers else 'X only'}."
        ),
    }


def _inspect_tabular(filepath: Path, size_mb: float, sep: str = ",") -> dict:
    """Inspect a CSV/TSV file."""
    import pandas as pd

    # Read just the first rows to get shape info without loading everything
    df_head = pd.read_csv(filepath, sep=sep, nrows=5, index_col=0)
    # Get full shape by counting lines
    with open(filepath) as f:
        n_lines = sum(1 for _ in f) - 1  # subtract header

    columns = list(df_head.columns)
    dtypes = {col: str(dtype) for col, dtype in df_head.dtypes.items()}

    return {
        "path": str(filepath),
        "file_type": "csv" if sep == "," else "tsv",
        "size_mb": size_mb,
        "shape": [n_lines, len(columns)],
        "columns": columns[:30],
        "dtypes": dict(list(dtypes.items())[:15]),
        "head_preview": df_head.head(3).to_dict(),
        "summary": (
            f"Tabular: {n_lines:,} rows x {len(columns)} columns ({size_mb} MB). "
            f"Columns: {', '.join(columns[:8])}"
        ),
    }
