"""data_api.drug_info: aggregated PubChem drug information lookup. Split from tools/data_api.py."""
from tools import data_api as _data_api
from tools import registry
from tools.data_api_druginfo_fetch import fetch_pharmacology, fetch_properties, fetch_synonyms
from tools.data_api_druginfo_resolve import resolve_cid


@registry.register(
    name="data_api.drug_info",
    description="Look up comprehensive drug information: pharmacology, properties, interactions, indications",
    category="data_api",
    parameters={
        "query": "Drug name (e.g. 'imatinib') or compound name",
        "include": "Information to include: list of 'pharmacology', 'interactions', 'properties' (default ['pharmacology', 'interactions'])",
    },
    requires_data=[],
    usage_guide="You want drug pharmacology, properties, and interaction data. Uses PubChem PUG REST and PUG View APIs for comprehensive drug information.",
)
def drug_info(query: str, include: list = None, **kwargs) -> dict:
    """Look up drug information via PubChem REST API.

    Uses PubChem PUG REST and PUG View APIs to retrieve drug properties,
    pharmacology, and interaction data.
    """
    if include is None:
        include = ["pharmacology", "interactions"]

    raw_query = query
    query = _data_api._normalize_drug_query(query)
    if not query:
        return {"error": "Drug query is required", "summary": "PubChem: query cannot be empty"}

    cid, resolved_query, error = resolve_cid(raw_query)
    if error:
        return error

    properties = fetch_properties(cid)
    pharmacology, interactions, drug_info_section = fetch_pharmacology(cid, include)
    synonyms, drugbank_id = fetch_synonyms(cid)

    mw = properties.get("MolecularWeight", "N/A")
    formula = properties.get("MolecularFormula", "N/A")
    smiles = properties.get("CanonicalSMILES", "N/A")
    mechanism = pharmacology.get("mechanism_of_action", "N/A")

    drugbank_str = f" ({drugbank_id})" if drugbank_id else ""
    mech_short = mechanism[:80] + "..." if len(mechanism) > 80 else mechanism
    resolved_note = ""
    if resolved_query.lower() != raw_query.lower():
        resolved_note = f" [resolved as '{resolved_query}']"

    return {
        "summary": (
            f"{raw_query}{resolved_note}{drugbank_str}: {mech_short}, "
            f"MW {mw}, {len(interactions)} known drug interactions."
        ),
        "query": raw_query,
        "resolved_query": resolved_query,
        "cid": cid,
        "drugbank_id": drugbank_id,
        "properties": {
            "molecular_formula": formula,
            "molecular_weight": mw,
            "canonical_smiles": smiles,
            "isomeric_smiles": properties.get("IsomericSMILES", ""),
            "xlogp": properties.get("XLogP"),
            "tpsa": properties.get("TPSA"),
            "hbd": properties.get("HBondDonorCount"),
            "hba": properties.get("HBondAcceptorCount"),
            "rotatable_bonds": properties.get("RotatableBondCount"),
            "inchi_key": properties.get("InChIKey", ""),
        },
        "pharmacology": pharmacology,
        "drug_info": drug_info_section,
        "interactions": interactions[:20],
        "n_interactions": len(interactions),
        "synonyms": synonyms,
        "pubchem_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
    }
