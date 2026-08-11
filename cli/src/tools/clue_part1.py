"""clue — part 1 of split module. See tools/clue.py."""
from tools.clue_base import Config, Path, lru_cache, pd, registry


def _get_clue_key() -> str | None:
    """Get CLUE API key from config/environment (for API-based fallback)."""
    import os
    cfg = Config.load()
    return cfg.get("clue.api_key") or os.environ.get("CLUE_API_KEY")
_LINCS_DIR = Path("/mnt2/bronze/lincs")
_PROFILES_PATH = _LINCS_DIR / "l1000_compound_profiles.parquet"
_METADATA_PATH = _LINCS_DIR / "l1000_pert_metadata.parquet"


@lru_cache(maxsize=1)
def _load_profiles() -> pd.DataFrame:
    """Load compound profiles (19,811 compounds × 978 landmark genes)."""
    # Check configured path first
    cfg = Config.load()
    path = cfg.get("data.l1000_profiles")
    if path:
        p = Path(path)
        if p.is_file():
            return pd.read_parquet(p)

    if _PROFILES_PATH.exists():
        return pd.read_parquet(_PROFILES_PATH)

    # Search in data.base
    base = cfg.get("data.base")
    if base:
        candidate = Path(base) / "lincs" / "l1000_compound_profiles.parquet"
        if candidate.exists():
            return pd.read_parquet(candidate)

    raise FileNotFoundError(
        "L1000 compound profiles not found. "
        "Expected at: /mnt2/bronze/lincs/l1000_compound_profiles.parquet"
    )
@lru_cache(maxsize=1)
def _load_pert_metadata() -> pd.DataFrame:
    """Load perturbagen metadata (SMILES, PubChem CID, etc.)."""
    if _METADATA_PATH.exists():
        return pd.read_parquet(_METADATA_PATH)
    return pd.DataFrame()
def _find_compound(name: str, profiles: pd.DataFrame) -> str | None:
    """Find a compound in profiles by case-insensitive name matching."""
    name_lower = name.lower().strip()
    # Build lowercase index for matching
    idx_lower = {c.lower(): c for c in profiles.index}
    if name_lower in idx_lower:
        return idx_lower[name_lower]
    # Try partial match
    for key, original in idx_lower.items():
        if name_lower in key or key in name_lower:
            return original
    return None
@registry.register(
    name="clue.compound_signature",
    description="Get the L1000 transcriptomic signature (up/down-regulated genes) for a compound",
    category="clue",
    parameters={
        "compound": "Compound name (e.g. 'vorinostat', 'lenalidomide', 'bortezomib')",
        "top_n": "Number of top up/down genes to return (default 50)",
    },
    usage_guide=(
        "You need the transcriptomic signature (up/down genes) of a compound from L1000/CMap. "
        "Use to understand a compound's mechanism of action or as input for connectivity queries. "
        "Covers ~19,800 compounds from the Broad LINCS dataset."
    ),
)
def compound_signature(compound: str, top_n: int = 50, **kwargs) -> dict:
    """Get the L1000 transcriptomic signature for a compound from local data."""
    if not compound or not isinstance(compound, str):
        return {
            "error": "compound parameter required",
            "summary": "Provide a compound name (e.g. 'lenalidomide').",
        }

    try:
        profiles = _load_profiles()
    except FileNotFoundError as e:
        return {"error": str(e), "summary": str(e)}

    # Find compound in profiles
    matched = _find_compound(compound, profiles)
    if matched is None:
        return {
            "error": f"Compound '{compound}' not found in L1000 data ({len(profiles)} compounds available).",
            "summary": f"Compound '{compound}' not found in L1000/CMap database.",
        }

    # Extract profile
    profile = profiles.loc[matched]

    # Get top up and down regulated genes
    sorted_genes = profile.sort_values(ascending=False)
    up_genes = [
        {"gene": g, "z_score": round(float(v), 4)}
        for g, v in sorted_genes.head(top_n).items()
    ]
    down_genes = [
        {"gene": g, "z_score": round(float(v), 4)}
        for g, v in sorted_genes.tail(top_n).iloc[::-1].items()
    ]

    # Get metadata if available
    meta = _load_pert_metadata()
    pert_id = ""
    smiles = ""
    pubchem_cid = ""
    if matched in meta.index:
        row = meta.loc[matched]
        pert_id = str(row.get("pert_id", "")) if pd.notna(row.get("pert_id")) else ""
        smiles = str(row.get("canonical_smiles", "")) if pd.notna(row.get("canonical_smiles")) else ""
        pubchem_cid = str(row.get("pubchem_cid", "")) if pd.notna(row.get("pubchem_cid")) else ""

    summary = (
        f"L1000 signature for {matched}: "
        f"{top_n} up-regulated genes (top: {up_genes[0]['gene']} z={up_genes[0]['z_score']}), "
        f"{top_n} down-regulated genes (top: {down_genes[0]['gene']} z={down_genes[0]['z_score']})"
    )

    return {
        "summary": summary,
        "compound": matched,
        "pert_id": pert_id,
        "smiles": smiles,
        "pubchem_cid": pubchem_cid,
        "n_signatures_aggregated": len(profiles),
        "up_genes": up_genes,
        "down_genes": down_genes,
    }
