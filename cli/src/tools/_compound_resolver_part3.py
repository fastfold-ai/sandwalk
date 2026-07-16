"""_compound_resolver — part 3 of split module. See tools/_compound_resolver.py."""
from tools._compound_resolver_base import _CMPD_PATTERN, _YU_PATTERN
from tools._compound_resolver_part1 import _load_prot_mapping, _tanimoto_search
from tools._compound_resolver_part2 import resolve_to_smiles
from tools._compound_resolver_part4 import _get_dataset_compounds

def resolve_compound(name_or_id: str, dataset: str = "prism") -> str:
    """Resolve a compound name or ID to a dataset-specific ID.

    Parameters
    ----------
    name_or_id : str
        Drug name (e.g. "lenalidomide"), YU code, or Cmpd ID.
    dataset : str
        Target dataset: "prism", "l1000", or "proteomics".

    Returns
    -------
    str
        Resolved compound ID for the target dataset.
        For L1000 with compound-named index, returns the compound name directly.
        For proteomics, returns the full Cmpd_well ID if possible.
        Falls back to the original input if resolution fails.
    """
    if not name_or_id or not isinstance(name_or_id, str):
        return name_or_id

    name_or_id = name_or_id.strip()

    # For L1000: check if the index uses compound names (new format) vs YU codes (legacy)
    if dataset == "l1000":
        try:
            from data.loaders import load_l1000
            l1000 = load_l1000()
            sample_idx = str(l1000.index[0]) if len(l1000) > 0 else ""
            if not _YU_PATTERN.match(sample_idx):
                # New compound-named index: case-insensitive lookup
                name_lower = name_or_id.lower().strip()
                idx_lower = {c.lower(): c for c in l1000.index}
                if name_lower in idx_lower:
                    return idx_lower[name_lower]
                # Try partial match
                for key, original in idx_lower.items():
                    if name_lower in key or key in name_lower:
                        return original
                return name_or_id
        except (FileNotFoundError, ImportError):
            pass

    # Already a YU code — return as-is for PRISM/L1000, convert for proteomics
    if _YU_PATTERN.match(name_or_id):
        if dataset == "proteomics":
            return _yu_to_proteomics_col(name_or_id) or name_or_id
        return name_or_id

    # Already a Cmpd ID — return as-is for proteomics, convert for PRISM/L1000
    if _CMPD_PATTERN.match(name_or_id):
        if dataset == "proteomics":
            return name_or_id
        prot_to_yu, _ = _load_prot_mapping()
        base = name_or_id.split("_")[0]
        yu_id = prot_to_yu.get(base)
        return yu_id if yu_id else name_or_id

    # Drug name — try to resolve SMILES via API, then find closest match in dataset
    try:
        drug_smi = resolve_to_smiles(name_or_id)
    except ValueError:
        return name_or_id  # Cannot resolve to SMILES, return as-is

    # Dynamic SMILES-based resolution (cached)
    # Get candidate compounds from the target dataset
    candidates = _get_dataset_compounds(dataset)
    if not candidates:
        return name_or_id

    result = _tanimoto_search(drug_smi, frozenset(candidates))
    if result is None:
        return name_or_id

    yu_id, sim = result
    # Low-similarity proxies produce misleading data — return the original
    # name so the tool reports "not found" and synthesis uses LLM knowledge
    if sim < 0.65:
        return name_or_id
    if dataset == "proteomics":
        return _yu_to_proteomics_col(yu_id) or yu_id
    return yu_id
def resolve_proteomics_id(yu_id: str) -> str | None:
    """Convert a YU compound ID to the proteomics Cmpd_well column name.

    Returns None if no mapping exists.
    """
    return _yu_to_proteomics_col(yu_id)
def _yu_to_proteomics_col(yu_id: str) -> str | None:
    """Map YU ID → full proteomics column name (Cmpd##_well)."""
    _, yu_to_prot = _load_prot_mapping()
    base_cmpd = yu_to_prot.get(yu_id)
    if base_cmpd is None:
        return None

    # Find the full column name in proteomics data
    try:
        from data.loaders import load_proteomics
        prot = load_proteomics()
        for col in prot.columns:
            if col.startswith(base_cmpd + "_"):
                return col
    except (FileNotFoundError, ImportError):
        pass

    return base_cmpd
