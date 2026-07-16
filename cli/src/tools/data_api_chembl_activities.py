"""data_api.chembl_advanced: target bioactivity statistics aggregation. Split from tools/data_api.py."""
from tools import data_api as _data_api


def _chembl_target_activities(query: str, base: str, headers: dict) -> dict:
    """Get aggregated bioactivity statistics for a target."""
    # Find the target. ChEMBL's /target/search endpoint can intermittently 5xx, so
    # fall back to filtered /target lookups before failing the tool.
    targets = []
    target_search_errors = []
    target_search_attempts = [
        ("target_search", f"{base}/target/search.json", {"q": query, "limit": 5}),
        ("target_synonym", f"{base}/target.json", {"target_synonym__icontains": query, "limit": 5}),
        ("target_pref_name", f"{base}/target.json", {"pref_name__icontains": query, "limit": 5}),
    ]
    for _, endpoint, params in target_search_attempts:
        try:
            tgt_resp = _data_api._http_get(endpoint, params=params, headers=headers, timeout=15, retries=2)
            tgt_resp.raise_for_status()
            tgt_data = tgt_resp.json()
        except Exception as e:
            target_search_errors.append(str(e))
            continue
        targets = tgt_data.get("targets", []) or []
        if targets:
            break
    if not targets:
        if target_search_errors:
            joined = " | ".join(err for err in target_search_errors if err) or "unknown error"
            return {"error": f"ChEMBL target search failed: {joined}", "summary": f"ChEMBL target search failed: {joined}"}
        return {"summary": f"No ChEMBL target found for '{query}'", "query": query}

    # Prefer human SINGLE PROTEIN
    target = None
    for t in targets:
        if t.get("organism") == "Homo sapiens" and t.get("target_type") == "SINGLE PROTEIN":
            target = t
            break
    if not target:
        target = targets[0]

    chembl_target_id = target.get("target_chembl_id", "")
    target_name = target.get("pref_name", query)

    try:
        act_resp = _data_api._http_get(
            f"{base}/activity.json",
            params={"target_chembl_id": chembl_target_id, "limit": 100, "standard_type__in": "IC50,Ki,Kd,EC50"},
            headers=headers,
            timeout=15,
            retries=2,
        )
        act_resp.raise_for_status()
        act_data = act_resp.json()
    except Exception as e:
        return {"error": f"ChEMBL activity query failed: {e}", "summary": f"ChEMBL activity query failed: {e}"}
    activities = act_data.get("activities", [])

    import statistics

    by_type = {}
    unique_molecules = set()
    for act in activities:
        mol_id = act.get("molecule_chembl_id", "")
        unique_molecules.add(mol_id)
        std_type = act.get("standard_type", "")
        std_value = act.get("standard_value")
        if std_value is not None:
            try:
                val = float(std_value)
                by_type.setdefault(std_type, []).append(val)
            except (ValueError, TypeError):
                pass

    stats = {}
    for activity_type, values in by_type.items():
        stats[activity_type] = {
            "count": len(values),
            "min_nM": round(min(values), 2),
            "max_nM": round(max(values), 2),
            "median_nM": round(statistics.median(values), 2),
            "mean_nM": round(statistics.mean(values), 2),
        }

    total_activities = sum(s["count"] for s in stats.values())
    median_str = ""
    if "IC50" in stats:
        median_str = f", median IC50 = {stats['IC50']['median_nM']:.0f} nM"

    return {
        "summary": (
            f"ChEMBL target {chembl_target_id} ({target_name}): "
            f"{total_activities} activities, "
            f"{len(unique_molecules)} unique compounds"
            f"{median_str}"
        ),
        "query": query,
        "target_chembl_id": chembl_target_id,
        "target_name": target_name,
        "organism": target.get("organism", ""),
        "target_type": target.get("target_type", ""),
        "n_unique_compounds": len(unique_molecules),
        "n_activities": total_activities,
        "activity_statistics": stats,
    }
