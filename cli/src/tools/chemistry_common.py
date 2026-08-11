"""chemistry: shared SMILES extraction/resolution helper. Split from tools/chemistry.py."""

def _extract_smiles(smiles) -> str:
    """Extract a SMILES string from various input types and resolve drug names.

    Handles the case where a dict (e.g., full pubchem_lookup result) is passed
    instead of a plain SMILES string — typically when the planner uses $step.1
    instead of $step.1.canonical_smiles.

    Also resolves drug names (e.g. "lenalidomide") to SMILES via
    _compound_resolver.resolve_to_smiles.
    """
    if isinstance(smiles, dict):
        smiles = (smiles.get("canonical_smiles") or smiles.get("smiles")
                  or smiles.get("summary", ""))
    smiles = str(smiles).strip()

    # Try to resolve name → SMILES (handles both valid SMILES and drug names)
    try:
        from tools._compound_resolver import resolve_to_smiles
        return resolve_to_smiles(smiles)
    except (ValueError, ImportError):
        return smiles  # Fall through — tool will handle invalid SMILES
