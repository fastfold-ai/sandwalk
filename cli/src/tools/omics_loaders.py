"""omics: matrix.gz inspection + tabular loader helper. Split from tools/omics.py."""
import gzip
from pathlib import Path
from typing import Any


def _inspect_matrix_gz(filepath: Path, size_mb: float) -> dict:
    """Inspect a GEO series matrix .txt.gz file."""
    metadata = {}
    n_rows = 0
    columns = []

    with gzip.open(filepath, "rt", errors="replace") as f:
        for line in f:
            if line.startswith("!"):
                # Parse metadata lines
                parts = line.strip().split("\t", 1)
                if len(parts) == 2:
                    key = parts[0].lstrip("!").strip()
                    val = parts[1].strip().strip('"')
                    if key not in metadata:
                        metadata[key] = val
                    elif isinstance(metadata[key], list):
                        metadata[key].append(val)
                    else:
                        metadata[key] = [metadata[key], val]
            elif line.startswith('"ID_REF"') or line.startswith("ID_REF"):
                columns = [c.strip('"') for c in line.strip().split("\t")]
            elif not line.startswith("!") and line.strip():
                n_rows += 1

    # Extract key metadata fields
    title = metadata.get("Series_title", "")
    organism = metadata.get("Series_organism", "")
    n_samples = len(columns) - 1 if columns else 0

    return {
        "path": str(filepath),
        "file_type": "matrix.txt.gz",
        "size_mb": size_mb,
        "title": title,
        "organism": organism,
        "n_probes_or_genes": n_rows,
        "n_samples": n_samples,
        "sample_ids": columns[1:11] if columns else [],
        "metadata_keys": list(metadata.keys())[:15],
        "summary": (
            f"GEO matrix: {n_rows:,} probes/genes x {n_samples} samples ({size_mb} MB). "
            f"Title: {title[:80]}. Organism: {organism}."
        ),
    }


# ===========================================================================
# Analysis tools — modality-specific processing of downloaded data
# ===========================================================================


def _load_tabular(path: str, **read_kwargs) -> "tuple[Any | None, str | None]":
    """Load a tabular file, returning (df, error)."""
    import pandas as pd

    filepath = Path(path).expanduser()
    if not filepath.exists():
        return None, f"File not found: {path}"
    suffix = filepath.suffix.lower()
    kwargs = dict(read_kwargs)
    try:
        # Keep prior behavior by defaulting to first column as index,
        # while allowing callers to override.
        kwargs.setdefault("index_col", 0)
        if suffix in {".xlsx", ".xls"}:
            df = pd.read_excel(filepath, **kwargs)
            return df, None
        if suffix == ".csv":
            df = pd.read_csv(filepath, sep=",", **kwargs)
            return df, None
        if suffix in {".tsv", ".tab"}:
            df = pd.read_csv(filepath, sep="\t", **kwargs)
            return df, None
        if suffix == ".txt":
            # Many omics count matrices are whitespace-delimited.
            try:
                df = pd.read_csv(filepath, sep=r"\s+", engine="python", **kwargs)
                return df, None
            except Exception:
                df = pd.read_csv(filepath, sep="\t", **kwargs)
                return df, None
        # Generic fallback: delimiter sniffing for unknown text-like files.
        df = pd.read_csv(filepath, sep=None, engine="python", **kwargs)
        return df, None
    except Exception as exc:
        return None, f"Failed to read {filepath.name}: {str(exc)[:200]}"
