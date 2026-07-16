"""genomics.mendelian_randomization_lookup: gene/disease ID resolution via Open Targets. Split from tools/genomics.py."""
from tools import genomics as _genomics

OT_URL = "https://api.platform.opentargets.org/api/v4/graphql"
OT_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


def resolve_gene(gene: str) -> tuple[str | None, str, dict | None]:
    """Resolve a gene symbol to an Ensembl ID. Returns (ensembl_id, target_name, error)."""
    search_query = """
    query searchTarget($queryString: String!) {
        search(queryString: $queryString, entityNames: ["target"], page: {size: 5, index: 0}) {
            hits {
                id
                entity
                name
                description
            }
        }
    }
    """
    search_data, error = _genomics.request_json(
        "POST", OT_URL, json={"query": search_query, "variables": {"queryString": gene}}, headers=OT_HEADERS, timeout=10, retries=2,
    )
    if error:
        return None, "", {"error": f"Open Targets search failed: {error}", "summary": f"Open Targets search failed: {error}"}
    hits = search_data.get("data", {}).get("search", {}).get("hits", [])
    target_hits = [h for h in hits if h.get("entity") == "target"]

    if not target_hits:
        return None, "", {"error": f"Gene '{gene}' not found in Open Targets", "summary": f"Gene '{gene}' not found in Open Targets"}

    for hit in target_hits:
        if hit.get("name", "").upper() == gene.upper():
            return hit["id"], hit.get("name", ""), None
    return target_hits[0]["id"], target_hits[0].get("name", ""), None


def resolve_disease(disease: str) -> tuple[str | None, str, dict | None]:
    """Resolve a disease name to an EFO/MONDO/HP ID. Returns (efo_id, disease_name, error)."""
    if disease.upper().startswith(("EFO_", "MONDO_", "HP_")):
        return disease, disease, None

    disease_search_query = """
    query searchDisease($queryString: String!) {
        search(queryString: $queryString, entityNames: ["disease"], page: {size: 5, index: 0}) {
            hits {
                id
                entity
                name
                description
            }
        }
    }
    """
    disease_data, error = _genomics.request_json(
        "POST", OT_URL, json={"query": disease_search_query, "variables": {"queryString": disease}}, headers=OT_HEADERS, timeout=10, retries=2,
    )
    if error:
        return None, "", {"error": f"Open Targets disease search failed: {error}", "summary": f"Open Targets disease search failed: {error}"}
    disease_hits = disease_data.get("data", {}).get("search", {}).get("hits", [])
    disease_hits = [h for h in disease_hits if h.get("entity") == "disease"]

    if not disease_hits:
        return None, "", {"error": f"Disease '{disease}' not found in Open Targets", "summary": f"Disease '{disease}' not found in Open Targets"}
    return disease_hits[0]["id"], disease_hits[0].get("name", disease), None
