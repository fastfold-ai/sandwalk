"""data_api.chembl_advanced: compound search with full property details. Split from tools/data_api.py."""
from tools import data_api as _data_api


def _chembl_compound_search(query: str, base: str, headers: dict) -> dict:
    """Search ChEMBL for a compound with full property details."""
    try:
        resp = _data_api._http_get(
            f"{base}/molecule/search.json",
            params={"q": query, "limit": 5},
            headers=headers,
            timeout=15,
            retries=2,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"error": f"ChEMBL compound search failed: {e}", "summary": f"ChEMBL compound search failed: {e}"}
    molecules = data.get("molecules", [])
    if not molecules:
        return {
            "summary": f"No ChEMBL compounds found for '{query}'",
            "query": query,
            "compounds": [],
        }

    compounds = []
    for mol in molecules:
        props = mol.get("molecule_properties", {}) or {}
        structs = mol.get("molecule_structures", {}) or {}
        chembl_id = mol.get("molecule_chembl_id", "")

        compounds.append({
            "chembl_id": chembl_id,
            "pref_name": mol.get("pref_name", ""),
            "molecule_type": mol.get("molecule_type", ""),
            "max_phase": mol.get("max_phase", 0),
            "oral": mol.get("oral", False),
            "parenteral": mol.get("parenteral", False),
            "topical": mol.get("topical", False),
            "natural_product": mol.get("natural_product", -1),
            "canonical_smiles": structs.get("canonical_smiles", ""),
            "inchi_key": structs.get("standard_inchi_key", ""),
            "molecular_weight": props.get("full_mwt"),
            "alogp": props.get("alogp"),
            "hba": props.get("hba"),
            "hbd": props.get("hbd"),
            "psa": props.get("psa"),
            "rtb": props.get("rtb"),
            "ro5_violations": props.get("num_ro5_violations"),
            "aromatic_rings": props.get("aromatic_rings"),
            "heavy_atoms": props.get("heavy_atoms"),
            "qed_weighted": props.get("qed_weighted"),
        })

    top = compounds[0]
    return {
        "summary": (
            f"ChEMBL compound {top['chembl_id']} ({top['pref_name'] or query}): "
            f"MW={top['molecular_weight'] or 'N/A'}, ALogP={top['alogp'] or 'N/A'}, "
            f"max phase {top['max_phase']}"
        ),
        "query": query,
        "n_results": len(compounds),
        "compounds": compounds,
    }
