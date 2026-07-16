"""chemistry.pubchem_lookup: PubChem PUG REST fetch helpers (CID/properties/synonyms). Split from tools/chemistry.py."""
from tools import chemistry as _chemistry

BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


def resolve_cid(query: str, query_type: str) -> tuple[int | None, dict | None]:
    """Resolve a compound name or SMILES to a PubChem CID. Returns (cid, error)."""
    if query_type == "smiles":
        resp, error = _chemistry.request("POST", f"{BASE_URL}/compound/smiles/JSON", data={"smiles": query}, timeout=10, retries=2, raise_for_status=False)
    else:
        import urllib.parse
        encoded_query = urllib.parse.quote(query, safe="")
        resp, error = _chemistry.request("GET", f"{BASE_URL}/compound/name/{encoded_query}/JSON", timeout=10, retries=2, raise_for_status=False)

    if error:
        return None, {"error": f"HTTP error: {error}", "summary": f"PubChem lookup failed: {error}"}
    if resp.status_code == 404:
        return None, {"error": f"Compound not found: {query}", "summary": f"PubChem: no compound found for '{query}' (query_type={query_type})"}
    if resp.status_code != 200:
        return None, {"error": f"PubChem API error (HTTP {resp.status_code})", "summary": f"PubChem lookup failed with status {resp.status_code}"}

    try:
        data = resp.json()
    except Exception:
        return None, {"error": "Failed to parse PubChem response", "summary": "PubChem returned invalid JSON"}

    compounds = data.get("PC_Compounds", [])
    if not compounds:
        return None, {"error": "No compound data in response", "summary": f"PubChem returned empty result for '{query}'"}

    cid = compounds[0].get("id", {}).get("id", {}).get("cid")
    if not cid:
        return None, {"error": "Could not extract CID", "summary": "PubChem response missing CID"}
    return cid, None


def fetch_properties(cid: int) -> dict:
    props_url = (
        f"{BASE_URL}/compound/cid/{cid}/property/"
        "MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,"
        "XLogP,ExactMass,TPSA,HBondDonorCount,HBondAcceptorCount,"
        "RotatableBondCount,HeavyAtomCount,Complexity/JSON"
    )
    props_resp, props_error = _chemistry.request("GET", props_url, timeout=10, retries=2, raise_for_status=False)
    if props_error:
        props_data = {}
    else:
        try:
            props_data = props_resp.json() if props_resp.status_code == 200 else {}
        except Exception:
            props_data = {}

    properties = {}
    prop_table = props_data.get("PropertyTable", {}).get("Properties", [])
    if prop_table:
        p = prop_table[0]
        # PubChem may return SMILES as "CanonicalSMILES", "SMILES", or "ConnectivitySMILES"
        canonical = p.get("CanonicalSMILES") or p.get("SMILES") or p.get("ConnectivitySMILES")
        properties = {
            "cid": p.get("CID"),
            "molecular_formula": p.get("MolecularFormula"),
            "molecular_weight": p.get("MolecularWeight"),
            "canonical_smiles": canonical,
            "isomeric_smiles": p.get("IsomericSMILES") or canonical,
            "xlogp": p.get("XLogP"),
            "exact_mass": p.get("ExactMass"),
            "tpsa": p.get("TPSA"),
            "hbd": p.get("HBondDonorCount"),
            "hba": p.get("HBondAcceptorCount"),
            "rotatable_bonds": p.get("RotatableBondCount"),
            "heavy_atoms": p.get("HeavyAtomCount"),
            "complexity": p.get("Complexity"),
        }
    return properties


def fetch_synonyms(cid: int) -> list:
    syn_resp, syn_error = _chemistry.request("GET", f"{BASE_URL}/compound/cid/{cid}/synonyms/JSON", timeout=10, retries=2, raise_for_status=False)
    if syn_error or syn_resp.status_code != 200:
        return []
    try:
        syn_list = syn_resp.json().get("InformationList", {}).get("Information", [])
        if syn_list:
            return syn_list[0].get("Synonym", [])[:20]  # cap at 20
    except Exception:
        pass
    return []
