"""literature.chembl_query: ChEMBL compound/target/activity/similarity search.

Split from tools/literature.py. Calls ``request_json`` indirectly via the
``tools.literature`` hub module so that ``patch("tools.literature.request_json")``
in tests continues to work regardless of which submodule performs the call.
"""

from tools import literature as _literature
from tools import registry


@registry.register(
    name="literature.chembl_query",
    description="Query ChEMBL for compound bioactivity, targets, and SAR data",
    category="literature",
    parameters={
        "query": "Compound name, SMILES, or ChEMBL ID",
        "query_type": "'molecule', 'target', 'activity', or 'similarity'",
        "max_results": "Maximum results (default 20)",
    },
    usage_guide="You want to look up known bioactivity data, find related compounds, or check if a target has known ligands. Use ChEMBL for chemical and pharmacological context.",
)
def chembl_query(query: str, query_type: str = "molecule", max_results: int = 20, **kwargs) -> dict:
    """Query ChEMBL database for compound/target/activity data."""
    try:
        import httpx
    except ImportError:
        return {"error": "httpx required (pip install httpx)", "summary": "httpx required (pip install httpx)"}
    query = str(query or "").strip()
    query_type_raw = str(query_type or "molecule").strip().lower()
    query_type_aliases = {
        "compound": "molecule",
        "drug": "molecule",
        "molecules": "molecule",
        "compounds": "molecule",
        "protein": "target",
        "gene": "target",
        "bioactivity": "activity",
        "activities": "activity",
        "similar": "similarity",
    }
    query_type = query_type_aliases.get(query_type_raw, query_type_raw)
    base = "https://www.ebi.ac.uk/chembl/api/data"
    headers = {"Accept": "application/json"}

    # Accept common aliases
    if query_type == "compound":
        query_type = "molecule"

    try:
        if query_type == "molecule":
            url = f"{base}/molecule/search.json"
            params = {"q": query, "limit": max_results}
            data, error = _literature.request_json(
                "GET",
                url,
                params=params,
                headers=headers,
                timeout=30,
                retries=2,
            )
            if error:
                return {"error": f"ChEMBL query failed: {error}", "summary": f"ChEMBL query failed: {error}"}
            molecules = []
            for mol in data.get("molecules", []):
                props = mol.get("molecule_properties", {}) or {}
                molecules.append({
                    "chembl_id": mol.get("molecule_chembl_id", ""),
                    "pref_name": mol.get("pref_name", ""),
                    "molecule_type": mol.get("molecule_type", ""),
                    "max_phase": mol.get("max_phase", 0),
                    "mw": props.get("full_mwt"),
                    "logp": props.get("alogp"),
                    "smiles": (mol.get("molecule_structures", {}) or {}).get("canonical_smiles", ""),
                })

            return {
                "summary": f"ChEMBL molecule search '{query}': {len(molecules)} hits",
                "query": query,
                "molecules": molecules,
            }

        elif query_type == "target":
            url = f"{base}/target/search.json"
            params = {"q": query, "limit": max_results}
            data, error = _literature.request_json(
                "GET",
                url,
                params=params,
                headers=headers,
                timeout=30,
                retries=2,
            )
            if error:
                return {"error": f"ChEMBL query failed: {error}", "summary": f"ChEMBL query failed: {error}"}
            targets = []
            for tgt in data.get("targets", []):
                targets.append({
                    "chembl_id": tgt.get("target_chembl_id", ""),
                    "pref_name": tgt.get("pref_name", ""),
                    "organism": tgt.get("organism", ""),
                    "target_type": tgt.get("target_type", ""),
                })

            return {
                "summary": f"ChEMBL target search '{query}': {len(targets)} hits",
                "query": query,
                "targets": targets,
            }

        elif query_type == "activity":
            # Support both target and molecule ChEMBL IDs
            # If query starts with CHEMBL, determine if it's a target or molecule
            # Also support compound names: resolve to molecule ChEMBL ID first
            molecule_id = None
            target_id = None

            if query.startswith("CHEMBL"):
                # Could be target or molecule — try molecule activity first
                molecule_id = query
            else:
                # Try to resolve compound name to ChEMBL molecule ID
                search_url = f"{base}/molecule/search.json"
                search_params = {"q": query, "limit": 5}
                search_data, search_error = _literature.request_json(
                    "GET",
                    search_url,
                    params=search_params,
                    headers=headers,
                    timeout=30,
                    retries=2,
                )
                if not search_error:
                    mols = search_data.get("molecules", [])
                    if mols:
                        molecule_id = mols[0].get("molecule_chembl_id", "")

            # Query activities by molecule ChEMBL ID
            activities = []
            if molecule_id:
                url = f"{base}/activity.json"
                params = {
                    "molecule_chembl_id": molecule_id,
                    "limit": max_results,
                }
                data, error = _literature.request_json(
                    "GET",
                    url,
                    params=params,
                    headers=headers,
                    timeout=30,
                    retries=2,
                )
                if not error:
                    for act in data.get("activities", []):
                        activities.append({
                            "molecule_chembl_id": act.get("molecule_chembl_id", ""),
                            "molecule_name": act.get("molecule_pref_name", ""),
                            "target_chembl_id": act.get("target_chembl_id", ""),
                            "target_name": act.get("target_pref_name", ""),
                            "standard_type": act.get("standard_type", ""),
                            "standard_value": act.get("standard_value"),
                            "standard_units": act.get("standard_units", ""),
                            "pchembl_value": act.get("pchembl_value"),
                            "assay_type": act.get("assay_type", ""),
                            "assay_description": (act.get("assay_description", "") or "")[:200],
                        })

            # If no results from molecule lookup, try target lookup
            if not activities:
                target_id = query if query.startswith("CHEMBL") else None
                if target_id:
                    url = f"{base}/activity.json"
                    params = {
                        "target_chembl_id": target_id,
                        "limit": max_results,
                        "standard_type__in": "IC50,Ki,Kd,EC50",
                    }
                    data, error = _literature.request_json(
                        "GET",
                        url,
                        params=params,
                        headers=headers,
                        timeout=30,
                        retries=2,
                    )
                    if not error:
                        for act in data.get("activities", []):
                            activities.append({
                                "molecule_chembl_id": act.get("molecule_chembl_id", ""),
                                "molecule_name": act.get("molecule_pref_name", ""),
                                "target_chembl_id": act.get("target_chembl_id", ""),
                                "target_name": act.get("target_pref_name", ""),
                                "standard_type": act.get("standard_type", ""),
                                "standard_value": act.get("standard_value"),
                                "standard_units": act.get("standard_units", ""),
                                "pchembl_value": act.get("pchembl_value"),
                                "assay_type": act.get("assay_type", ""),
                                "assay_description": (act.get("assay_description", "") or "")[:200],
                            })

            resolved_id = molecule_id or target_id or query
            return {
                "summary": f"ChEMBL activities for {query} ({resolved_id}): {len(activities)} results",
                "query": query,
                "chembl_id": resolved_id,
                "activities": activities,
            }

        elif query_type == "similarity":
            url = f"{base}/similarity/{query}/70.json"
            params = {"limit": max_results}
            data, error = _literature.request_json(
                "GET",
                url,
                params=params,
                headers=headers,
                timeout=30,
                retries=2,
            )
            if error:
                return {"error": f"ChEMBL query failed: {error}", "summary": f"ChEMBL query failed: {error}"}
            hits = []
            for mol in data.get("molecules", []):
                hits.append({
                    "chembl_id": mol.get("molecule_chembl_id", ""),
                    "pref_name": mol.get("pref_name", ""),
                    "similarity": mol.get("similarity", 0),
                    "smiles": (mol.get("molecule_structures", {}) or {}).get("canonical_smiles", ""),
                })

            return {
                "summary": f"ChEMBL similarity search: {len(hits)} hits (>70% similar)",
                "query": query,
                "hits": hits,
            }

        else:
            return {"error": f"Unknown query_type: {query_type_raw}. Use 'molecule', 'target', 'activity', or 'similarity'", "summary": f"Unknown query_type: {query_type_raw}. Use 'molecule', 'target', 'activity', or 'similarity'"}
    except Exception as e:
        return {"error": f"ChEMBL query failed: {e}", "summary": f"ChEMBL query failed: {e}"}
