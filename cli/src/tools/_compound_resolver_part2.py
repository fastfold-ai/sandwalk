"""_compound_resolver — part 2 of split module. See tools/_compound_resolver.py."""

def resolve_to_smiles(name_or_smiles: str) -> str:
    """Resolve a compound name or SMILES string to a canonical SMILES string.

    Resolution order:
    1. Try parsing as SMILES with RDKit (if installed)
    2. Try PubChem lookup via API
    3. Try ChEMBL lookup via API
    4. Raise ValueError if all methods fail

    Parameters
    ----------
    name_or_smiles : str
        Drug name (e.g. "lenalidomide") or SMILES string.

    Returns
    -------
    str
        Canonical SMILES string.

    Raises
    ------
    ValueError
        If the input cannot be resolved to a SMILES string.
    """
    if not name_or_smiles or not isinstance(name_or_smiles, str):
        raise ValueError(f"Invalid input: {name_or_smiles}")

    name_or_smiles = name_or_smiles.strip()
    if not name_or_smiles:
        raise ValueError("Empty input")

    # 1. Try RDKit parse — is it already a valid SMILES?
    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(name_or_smiles)
        if mol is not None:
            return name_or_smiles
    except ImportError:
        # No RDKit — heuristic: if it has typical SMILES characters, assume it's SMILES
        if any(c in name_or_smiles for c in "=#()[]"):
            return name_or_smiles

    # 2. Try PubChem lookup
    try:
        from tools.chemistry import pubchem_lookup

        result = pubchem_lookup(name_or_smiles, query_type="name")
        smiles = (result.get("properties") or {}).get("canonical_smiles")
        if smiles:
            return smiles
    except Exception:
        pass

    # 3. Try ChEMBL lookup
    try:
        from tools.literature import chembl_query

        result = chembl_query(name_or_smiles, query_type="molecule", max_results=1)
        molecules = result.get("molecules", [])
        if molecules and molecules[0].get("smiles"):
            return molecules[0]["smiles"]
    except Exception:
        pass

    raise ValueError(
        f"Could not resolve '{name_or_smiles}' to a SMILES string. "
        "Tried: RDKit SMILES parse, PubChem, ChEMBL."
    )
