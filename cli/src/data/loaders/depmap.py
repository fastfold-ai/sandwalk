"""DepMap-derived loaders: CRISPR gene effect, cell-line metadata, mutations."""

from functools import lru_cache

import pandas as pd

from data.loaders.paths import _read_tabular


@lru_cache(maxsize=1)
def load_crispr() -> pd.DataFrame:
    """Load DepMap CRISPR gene effect data."""
    from data.loaders import _find_file

    # Try configured path first
    path = _find_file("CRISPRGeneEffect.csv", subdirs=["", "depmap"])
    if path is None:
        raise FileNotFoundError(
            "DepMap CRISPR data not found. "
            "Run: sandwalk data pull depmap\n"
            "Or set: sandwalk config set data.base /path/to/data"
        )
    df = _read_tabular(path, index_col=0)
    # Clean column names: "TP53 (7157)" → "TP53"
    df.columns = [c.split(' (')[0] for c in df.columns]
    return df


@lru_cache(maxsize=1)
def load_model_metadata() -> pd.DataFrame:
    """Load DepMap cell line metadata."""
    from data.loaders import _find_file

    path = _find_file("Model.csv", subdirs=["", "depmap"])
    if path is None:
        raise FileNotFoundError(
            "Model metadata not found. "
            "Run: sandwalk data pull depmap"
        )
    return _read_tabular(path)


@lru_cache(maxsize=1)
def load_mutations() -> pd.DataFrame:
    """Load DepMap somatic mutation data (one copy per process, like the others)."""
    from data.loaders import _find_file

    path = _find_file("OmicsSomaticMutationsMatrixDamaging.csv", subdirs=["", "depmap"])
    if path is None:
        raise FileNotFoundError(
            "Mutation data not found. "
            "Run: sandwalk data pull depmap"
        )

    df = _read_tabular(path)
    meta_cols = ['Unnamed: 0', 'SequencingID', 'ModelConditionID',
                 'IsDefaultEntryForModel', 'IsDefaultEntryForMC']

    if 'IsDefaultEntryForModel' in df.columns:
        df = df[df['IsDefaultEntryForModel'] == 'Yes']

    if 'ModelID' in df.columns:
        df = df.set_index('ModelID')
    elif 'Unnamed: 0' in df.columns and df['Unnamed: 0'].astype(str).str.startswith('ACH-').any():
        df = df.set_index('Unnamed: 0')
        df.index.name = 'ModelID'
    df = df.drop(columns=[c for c in meta_cols if c in df.columns], errors='ignore')
    df.columns = [c.split(' (')[0] for c in df.columns]
    return df
