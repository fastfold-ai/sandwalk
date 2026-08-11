"""data_api.pdb_search: RCSB PDB structure search orchestrator. Split from tools/data_api.py."""
from tools import registry
from tools.data_api_pdb_detail import fetch_pdb_entry, fetch_structures
from tools.data_api_pdb_query import build_search_query, run_search


@registry.register(
    name="data_api.pdb_search",
    description="Search RCSB PDB for protein structures by gene name, UniProt ID, or PDB ID",
    category="data_api",
    parameters={
        "query": "Gene name, UniProt accession, or 4-character PDB ID",
        "method": "Optional experimental method filter: 'X-RAY', 'EM', 'NMR'",
        "max_results": "Maximum number of structures to return (default 10)",
    },
    requires_data=[],
    usage_guide="You want to find 3D protein structures for a target — PDB IDs, resolution, method, ligands. Use for structure-based drug design and target assessment.",
)
def pdb_search(query: str, method: str = None, max_results: int = 10, **kwargs) -> dict:
    """Search RCSB PDB for structures using the search and data APIs."""
    query_clean = query.strip()

    # If query looks like a PDB ID (4 chars), fetch directly
    if len(query_clean) == 4 and query_clean.isalnum():
        return fetch_pdb_entry(query_clean)

    terms = query_clean.split() or [query_clean]
    query_json, method_value, error = build_search_query(terms, method, max_results)
    if error:
        return error

    result_set, total_count, fallback_note, error = run_search(query_json, terms, method, method_value, max_results, query)
    if error:
        return error

    if not result_set:
        return {"summary": f"No PDB structures found for '{query}'", "query": query, "total_count": 0, "structures": []}

    pdb_ids = [r.get("identifier", "") for r in result_set if r.get("identifier")]
    structures = fetch_structures(pdb_ids, max_results)

    resolutions = [s["resolution"] for s in structures if s.get("resolution")]
    best_res = min(resolutions) if resolutions else None
    best_id = None
    if best_res is not None:
        for s in structures:
            if s.get("resolution") == best_res:
                best_id = s["pdb_id"]
                break

    method_str = f" ({method})" if method else ""
    best_str = f", best resolution {best_res:.1f}A ({best_id})" if best_res and best_id else ""

    return {
        "summary": f"PDB structures for {query}{method_str}: {total_count} total{best_str}{fallback_note}",
        "query": query,
        "total_count": total_count,
        "n_returned": len(structures),
        "best_resolution": best_res,
        "best_pdb_id": best_id,
        "structures": structures,
    }
