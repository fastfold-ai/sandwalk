"""data_api.pdb_search: per-entry PDB detail fetching. Split from tools/data_api.py."""
from tools import data_api as _data_api


def fetch_pdb_entry(pdb_id: str) -> dict:
    """Fetch a single PDB entry by ID."""
    try:
        resp = _data_api._http_get(f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}", timeout=10, retries=2)
        if resp.status_code == 404:
            return {"error": f"PDB entry {pdb_id} not found", "summary": f"No PDB entry for {pdb_id}"}
        if resp.status_code != 200:
            return {"error": f"PDB API returned HTTP {resp.status_code}", "summary": f"PDB API error: HTTP {resp.status_code}"}
        detail = resp.json()
    except Exception as e:
        return {"error": f"PDB API error: {e}", "summary": f"PDB API error: {e}"}
    struct_info = detail.get("struct", {})
    exptl = detail.get("exptl", [{}])[0] if detail.get("exptl") else {}
    rcsb_info = detail.get("rcsb_entry_info", {})

    resolution = None
    for refl in detail.get("reflns", []):
        resolution = refl.get("d_resolution_high")
    if resolution is None:
        res_list = rcsb_info.get("resolution_combined", [])
        resolution = res_list[0] if isinstance(res_list, list) and res_list else None

    return {
        "summary": f"PDB {pdb_id}: {struct_info.get('title', 'N/A')} ({exptl.get('method', 'N/A')}, {resolution or 'N/A'}A)",
        "pdb_id": pdb_id,
        "title": struct_info.get("title", ""),
        "method": exptl.get("method", ""),
        "resolution": resolution,
        "deposition_date": detail.get("rcsb_accession_info", {}).get("deposit_date", ""),
        "total_count": 1,
        "structures": [{
            "pdb_id": pdb_id,
            "title": struct_info.get("title", ""),
            "method": exptl.get("method", ""),
            "resolution": resolution,
        }],
    }


def fetch_structures(pdb_ids: list[str], max_results: int) -> list[dict]:
    """Fetch summary detail (title/method/resolution/ligand count) for each PDB ID."""
    structures = []
    for pdb_id in pdb_ids[:max_results]:
        try:
            detail_resp = _data_api._http_get(f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}", timeout=10, retries=2)
            if detail_resp.status_code != 200:
                structures.append({"pdb_id": pdb_id, "error": "detail fetch failed"})
                continue
            detail = detail_resp.json()

            struct_info = detail.get("struct", {})
            exptl = detail.get("exptl", [{}])[0] if detail.get("exptl") else {}
            rcsb_info = detail.get("rcsb_entry_info", {})

            resolution = None
            for refl in detail.get("reflns", []):
                resolution = refl.get("d_resolution_high")
            if resolution is None:
                resolution = rcsb_info.get("resolution_combined", [None])
                resolution = resolution[0] if isinstance(resolution, list) and resolution else resolution

            ligands = list(detail.get("rcsb_entry_container_identifiers", {}).get("non_polymer_entity_ids", []))

            structures.append({
                "pdb_id": pdb_id,
                "title": struct_info.get("title", ""),
                "method": exptl.get("method", ""),
                "resolution": resolution,
                "deposition_date": detail.get("rcsb_accession_info", {}).get("deposit_date", ""),
                "organism": detail.get("rcsb_entry_info", {}).get("deposited_model_count", ""),
                "n_ligands": len(ligands),
            })
        except Exception:
            structures.append({"pdb_id": pdb_id, "error": "detail fetch failed"})
    return structures
