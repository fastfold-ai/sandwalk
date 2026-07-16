"""data_api.chembl_advanced: mechanism-of-action and drug-indication lookups. Split from tools/data_api.py."""
from tools import data_api as _data_api


def _chembl_mechanism(query: str, base: str, headers: dict) -> dict:
    """Look up drug mechanisms of action."""
    try:
        resp = _data_api._http_get(
            f"{base}/mechanism.json", params={"molecule_chembl_id": query, "limit": 20}, headers=headers, timeout=15, retries=2,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"error": f"ChEMBL mechanism query failed: {e}", "summary": f"ChEMBL mechanism query failed: {e}"}
    mechanisms = data.get("mechanisms", [])

    # If no results by molecule ID, try searching by name
    if not mechanisms:
        try:
            mol_resp = _data_api._http_get(
                f"{base}/molecule/search.json", params={"q": query, "limit": 1}, headers=headers, timeout=10, retries=2,
            )
            mol_resp.raise_for_status()
            mol_data = mol_resp.json()
            mols = mol_data.get("molecules", [])
            if mols:
                mol_id = mols[0].get("molecule_chembl_id", "")
                resp2 = _data_api._http_get(
                    f"{base}/mechanism.json", params={"molecule_chembl_id": mol_id, "limit": 20}, headers=headers, timeout=10, retries=2,
                )
                resp2.raise_for_status()
                mechanisms = resp2.json().get("mechanisms", [])
        except Exception:
            pass

    if not mechanisms:
        return {"summary": f"No mechanisms of action found in ChEMBL for '{query}'", "query": query, "mechanisms": []}

    parsed = []
    for mech in mechanisms:
        parsed.append({
            "mechanism": mech.get("mechanism_of_action", ""),
            "action_type": mech.get("action_type", ""),
            "target_name": mech.get("target_chembl_id", ""),
            "molecule_chembl_id": mech.get("molecule_chembl_id", ""),
            "max_phase": mech.get("max_phase"),
            "direct_interaction": mech.get("direct_interaction"),
        })

    return {
        "summary": f"ChEMBL mechanisms for {query}: {len(parsed)} mechanism(s). " + "; ".join(m["mechanism"] for m in parsed[:3]),
        "query": query,
        "n_mechanisms": len(parsed),
        "mechanisms": parsed,
    }


def _chembl_drug_indication(query: str, base: str, headers: dict) -> dict:
    """Look up approved drug indications."""
    mol_id = query
    try:
        if not query.upper().startswith("CHEMBL"):
            mol_resp = _data_api._http_get(
                f"{base}/molecule/search.json", params={"q": query, "limit": 1}, headers=headers, timeout=10, retries=2,
            )
            mol_resp.raise_for_status()
            mols = mol_resp.json().get("molecules", [])
            if mols:
                mol_id = mols[0].get("molecule_chembl_id", "")
    except Exception:
        pass

    try:
        resp = _data_api._http_get(
            f"{base}/drug_indication.json", params={"molecule_chembl_id": mol_id, "limit": 30}, headers=headers, timeout=15, retries=2,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"error": f"ChEMBL indication query failed: {e}", "summary": f"ChEMBL indication query failed: {e}"}
    indications = data.get("drug_indications", [])
    if not indications:
        return {"summary": f"No drug indications found in ChEMBL for '{query}'", "query": query, "indications": []}

    parsed = []
    for ind in indications:
        parsed.append({
            "indication": ind.get("mesh_heading", ""),
            "mesh_id": ind.get("mesh_id", ""),
            "efo_id": ind.get("efo_id", ""),
            "max_phase": ind.get("max_phase_for_ind"),
            "molecule_chembl_id": ind.get("molecule_chembl_id", ""),
        })

    approved = [p for p in parsed if p.get("max_phase") == 4]
    return {
        "summary": (
            f"ChEMBL indications for {query} ({mol_id}): "
            f"{len(parsed)} total, {len(approved)} approved. "
            + "; ".join(p["indication"] for p in parsed[:5])
        ),
        "query": query,
        "molecule_chembl_id": mol_id,
        "n_indications": len(parsed),
        "n_approved": len(approved),
        "indications": parsed,
    }
