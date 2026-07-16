"""data_api.drug_info: PubChem property/pharmacology/synonym fetch helpers. Split from tools/data_api.py."""
from tools import data_api as _data_api
from tools.data_api_druginfo_resolve import PUG_BASE, PUGVIEW_BASE


def fetch_properties(cid: int) -> dict:
    try:
        props_resp = _data_api._http_get(
            f"{PUG_BASE}/compound/cid/{cid}/property/"
            "MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,"
            "XLogP,ExactMass,TPSA,HBondDonorCount,HBondAcceptorCount,"
            "RotatableBondCount,HeavyAtomCount,Complexity,InChIKey/JSON",
            timeout=10,
            retries=2,
        )
        if props_resp.status_code == 200:
            prop_table = props_resp.json().get("PropertyTable", {}).get("Properties", [])
            if prop_table:
                return prop_table[0]
    except Exception:
        pass
    return {}


def fetch_pharmacology(cid: int, include: list) -> tuple[dict, list, dict]:
    """Returns (pharmacology, interactions, drug_info) from PUG View."""
    pharmacology: dict = {}
    interactions: list = []
    drug_info: dict = {}

    if "pharmacology" not in include and "interactions" not in include:
        return pharmacology, interactions, drug_info

    try:
        view_resp = _data_api._http_get(
            f"{PUGVIEW_BASE}/data/compound/{cid}/JSON",
            params={"heading": "Drug and Medication Information"},
            timeout=15,
            retries=2,
        )
        if view_resp.status_code != 200:
            return pharmacology, interactions, drug_info
        view_data = view_resp.json()
        sections = view_data.get("Record", {}).get("Section", [])

        for section in sections:
            for subsection in section.get("Section", []):
                sub_heading = subsection.get("TOCHeading", "")
                info_list = subsection.get("Information", [])

                if sub_heading == "Drug Indication":
                    for info in info_list:
                        val = info.get("Value", {}).get("StringWithMarkup", [])
                        if val:
                            drug_info["indication"] = val[0].get("String", "")[:500]
                elif sub_heading == "Mechanism of Action":
                    for info in info_list:
                        val = info.get("Value", {}).get("StringWithMarkup", [])
                        if val:
                            pharmacology["mechanism_of_action"] = val[0].get("String", "")[:500]
                elif sub_heading == "Pharmacology":
                    for info in info_list:
                        val = info.get("Value", {}).get("StringWithMarkup", [])
                        if val:
                            pharmacology["pharmacology"] = val[0].get("String", "")[:500]
                elif sub_heading == "Absorption":
                    for info in info_list:
                        val = info.get("Value", {}).get("StringWithMarkup", [])
                        if val:
                            pharmacology["absorption"] = val[0].get("String", "")[:300]
                elif "Drug Interaction" in sub_heading or "Drug-Drug" in sub_heading:
                    for info in info_list:
                        val = info.get("Value", {}).get("StringWithMarkup", [])
                        if val:
                            interactions.append(val[0].get("String", "")[:200])
    except Exception:
        pass

    return pharmacology, interactions, drug_info


def fetch_synonyms(cid: int) -> tuple[list, str]:
    """Returns (synonyms, drugbank_id)."""
    synonyms: list = []
    try:
        syn_resp = _data_api._http_get(f"{PUG_BASE}/compound/cid/{cid}/synonyms/JSON", timeout=10, retries=2)
        if syn_resp.status_code == 200:
            syn_list = syn_resp.json().get("InformationList", {}).get("Information", [])
            if syn_list:
                synonyms = syn_list[0].get("Synonym", [])[:15]
    except Exception:
        pass

    drugbank_id = ""
    for syn in synonyms:
        if syn.upper().startswith("DB") and len(syn) == 7 and syn[2:].isdigit():
            drugbank_id = syn
            break

    return synonyms, drugbank_id
