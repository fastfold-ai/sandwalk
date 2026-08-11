"""chemistry.pubchem_lookup: PubChem compound lookup orchestrator. Split from tools/chemistry.py."""
from tools import registry
from tools.chemistry_pubchem_fetch import fetch_properties, fetch_synonyms, resolve_cid


@registry.register(
    name="chemistry.pubchem_lookup",
    description="Look up compound data from PubChem by name or SMILES",
    category="chemistry",
    parameters={
        "query": "Compound name or SMILES string",
        "query_type": "Type of query: 'name' or 'smiles' (default 'name')",
    },
    usage_guide="You need compound information (structure, properties, synonyms, CID) from PubChem. Use when identifying a compound by name or validating a SMILES string. Returns canonical SMILES, physicochemical properties, and identifiers.",
)
def pubchem_lookup(query: str, query_type: str = "name", **kwargs) -> dict:
    """Look up compound data from PubChem PUG REST API.

    Supports lookup by compound name or SMILES string. Returns CID, canonical
    SMILES, molecular properties, and synonyms.
    """
    cid, error = resolve_cid(query, query_type)
    if error:
        return error

    properties = fetch_properties(cid)
    synonyms = fetch_synonyms(cid)

    canonical = properties.get("canonical_smiles", "N/A")
    mw = properties.get("molecular_weight", "N/A")
    formula = properties.get("molecular_formula", "N/A")
    xlogp = properties.get("xlogp", "N/A")

    summary_lines = [
        f"PubChem: {query} (CID {cid})",
        f"Formula: {formula}, MW: {mw}, XLogP: {xlogp}",
        f"SMILES: {canonical}",
    ]
    if synonyms:
        summary_lines.append(f"Also known as: {', '.join(synonyms[:5])}")

    return {
        "summary": "\n".join(summary_lines),
        "cid": cid,
        "canonical_smiles": properties.get("canonical_smiles"),
        "properties": properties,
        "synonyms": synonyms,
        "pubchem_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
    }
