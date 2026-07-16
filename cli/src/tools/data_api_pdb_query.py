"""data_api.pdb_search: RCSB search query construction + execution. Split from tools/data_api.py."""
from tools import data_api as _data_api

_SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"

_METHOD_MAP = {"X-RAY": "X-RAY DIFFRACTION", "EM": "ELECTRON MICROSCOPY", "NMR": "SOLUTION NMR"}
_VALID_METHODS = ("X-RAY DIFFRACTION", "ELECTRON MICROSCOPY", "SOLUTION NMR", "X-RAY", "EM", "NMR")


def build_search_query(terms: list[str], method: str | None, max_results: int) -> tuple[dict, str | None, dict | None]:
    """Build the RCSB search JSON body. Returns (query_json, method_value, error)."""
    text_nodes = [{"type": "terminal", "service": "full_text", "parameters": {"value": term}} for term in terms]
    query_json = {
        "query": {"type": "group", "logical_operator": "and", "nodes": text_nodes},
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": 0, "rows": max_results},
            "sort": [{"sort_by": "score", "direction": "desc"}],
        },
    }

    method_value = None
    if method:
        method_upper = method.upper()
        if method_upper not in _VALID_METHODS:
            return {}, None, {"error": f"Invalid method '{method}'. Use 'X-RAY', 'EM', or 'NMR'", "summary": f"Invalid PDB method '{method}'"}
        method_value = _METHOD_MAP.get(method_upper, method_upper)
        query_json["query"]["nodes"].append({
            "type": "terminal",
            "service": "text",
            "parameters": {"attribute": "exptl.method", "operator": "exact_match", "value": method_value},
        })

    return query_json, method_value, None


def run_search(query_json: dict, terms: list[str], method: str | None, method_value: str | None, max_results: int, query: str) -> tuple[list, int, str, dict | None]:
    """Execute the RCSB search, retrying with a broadened query if needed.

    Returns (result_set, total_count, fallback_note, error).
    """
    try:
        resp = _data_api._http_post(_SEARCH_URL, json=query_json, timeout=15, retries=2)
        if resp.status_code != 200:
            return [], 0, "", {
                "error": f"RCSB PDB search failed (HTTP {resp.status_code})",
                "summary": f"PDB search failed for '{query}'",
            }
        data = resp.json()
    except Exception as e:
        return [], 0, "", {"error": f"PDB search error: {e}", "summary": f"PDB search failed for '{query}'"}

    total_count = data.get("total_count", 0)
    result_set = data.get("result_set", [])
    fallback_note = ""

    if not result_set and len(terms) > 1:
        fallback_json = {
            "query": {
                "type": "group",
                "logical_operator": "and",
                "nodes": [{"type": "terminal", "service": "full_text", "parameters": {"value": terms[0]}}],
            },
            "return_type": "entry",
            "request_options": {
                "paginate": {"start": 0, "rows": max_results},
                "sort": [{"sort_by": "score", "direction": "desc"}],
            },
        }
        if method and method_value:
            fallback_json["query"]["nodes"].append({
                "type": "terminal",
                "service": "text",
                "parameters": {"attribute": "exptl.method", "operator": "exact_match", "value": method_value},
            })
        try:
            resp2 = _data_api._http_post(_SEARCH_URL, json=fallback_json, timeout=15, retries=2)
            if resp2.status_code == 200:
                data2 = resp2.json()
                result_set = data2.get("result_set", [])
                total_count = data2.get("total_count", 0)
                if result_set:
                    fallback_note = f" (broadened from '{query}' to '{terms[0]}')"
        except Exception:
            pass  # Keep original empty result

    return result_set, total_count, fallback_note, None
