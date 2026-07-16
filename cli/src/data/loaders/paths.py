"""Path resolution and tabular-read helpers shared by the dataset loaders.

``_find_file`` re-imports ``_DATA_SEARCH_PATHS`` from the top-level
``data.loaders`` package on every call (rather than using its own module
global) so that tests can ``monkeypatch.setattr(loaders, "_DATA_SEARCH_PATHS", ...)``
and have the effective search path change even though this function lives in
a submodule.
"""

from pathlib import Path
from typing import Any

import pandas as pd

from agent.config import CONFIG_DIR, Config

# Search order for data files (first match wins)
_DATA_SEARCH_PATHS = [
    Path.home() / "Projects" / "CellType" / "ct-data",         # Primary: ct-data repo
    Path.home() / "Projects" / "CellType" / "crews-glue-discovery",  # Legacy fallback
]


def _data_path(key: str) -> Path:
    """Get configured data path."""
    cfg = Config.load()
    path = cfg.get(f"data.{key}")
    if path:
        return Path(path)
    base = cfg.get("data.base")
    if base:
        return Path(base) / key
    return CONFIG_DIR / "data" / key


def _find_file(name: str, subdirs: list[str] | None = None) -> Path | None:
    """Search for a file across configured paths and common locations."""
    from data.loaders import _DATA_SEARCH_PATHS as search_paths

    subdirs = subdirs or [""]
    stem = Path(name).stem

    # 1. Check configured data.base
    cfg = Config.load()
    base = cfg.get("data.base")
    search_dirs = []
    if base:
        search_dirs.append(Path(base))

    # 2. Check known data locations
    search_dirs.extend(search_paths)

    # 3. Check ~/.sandwalk/data
    search_dirs.append(CONFIG_DIR / "data")

    for base_dir in search_dirs:
        for sub in subdirs:
            d = base_dir / sub if sub else base_dir
            if not d.exists():
                continue
            # Exact match
            candidate = d / name
            if candidate.exists():
                return candidate
            # Try parquet variant
            parquet = d / f"{stem}.parquet"
            if parquet.exists():
                return parquet

    return None


def _resolve_path(p: Path, filenames: list[str]) -> Path | None:
    """If p is a directory, search for one of filenames inside it. If p is a file, return it."""
    if p.is_file():
        return p
    if p.is_dir():
        for name in filenames:
            candidate = p / name
            if candidate.exists():
                return candidate
    return None


def _read_tabular(path: Path, **kwargs: Any) -> pd.DataFrame:
    """Read a CSV or Parquet file based on extension."""
    if path.suffix == ".parquet":
        return pd.read_parquet(path, **{k: v for k, v in kwargs.items() if k != "index_col"})
    return pd.read_csv(path, **kwargs)
