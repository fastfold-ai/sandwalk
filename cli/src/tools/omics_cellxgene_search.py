"""omics.cellxgene_search: search CELLxGENE Discover. Split from tools/omics.py."""
from tools import registry

from tools import omics as _omics


_CELLXGENE_API = "https://api.cellxgene.cziscience.com/curation/v1"


@registry.register(
    name="omics.cellxgene_search",
    description="Search CELLxGENE Discover for curated single-cell datasets",
    category="omics",
    parameters={
        "query": "Search terms (gene, disease, tissue, etc.)",
        "tissue": "Filter by tissue (optional)",
        "disease": "Filter by disease (optional)",
        "organism": "Filter by organism (default 'Homo sapiens')",
        "max_results": "Maximum results to return (default 10)",
    },
    usage_guide=(
        "Search the CZI CELLxGENE Discover portal for curated, analysis-ready "
        "single-cell datasets. Use before omics.cellxgene_fetch to get dataset IDs."
    ),
)
def cellxgene_search(
    query: str,
    tissue: str = "",
    disease: str = "",
    organism: str = "Homo sapiens",
    max_results: int = 10,
    **kwargs,
) -> dict:
    """Search CELLxGENE Discover for single-cell datasets."""
    if not query or not query.strip():
        return {"error": "Query is required", "summary": "No query provided"}

    # Fetch collections
    url = f"{_CELLXGENE_API}/collections"
    data, error = _omics.request_json("GET", url, timeout=20)
    if error:
        return {"error": f"CELLxGENE search failed: {error}", "summary": f"CELLxGENE error: {error}"}

    if not isinstance(data, list):
        return {"error": "Unexpected CELLxGENE response format", "summary": "CELLxGENE returned unexpected format"}

    query_lower = query.lower().strip()
    query_terms = query_lower.split()
    results = []

    for collection in data:
        # Check collection-level match
        col_title = (collection.get("name") or "").lower()
        col_desc = (collection.get("description") or "").lower()
        col_text = col_title + " " + col_desc

        col_matches = any(term in col_text for term in query_terms)

        for dataset in collection.get("datasets", []):
            ds_title = (dataset.get("title") or dataset.get("name") or "").lower()
            ds_text = ds_title + " " + col_text

            # Match query
            if not col_matches and not any(term in ds_text for term in query_terms):
                continue

            # Filter organism
            ds_organisms = [
                o.get("label", "").lower()
                for o in (dataset.get("organism", []) if isinstance(dataset.get("organism"), list) else [])
            ]
            if organism and organism.lower() not in " ".join(ds_organisms) and ds_organisms:
                continue

            # Filter tissue
            ds_tissues = [
                t.get("label", "").lower()
                for t in (dataset.get("tissue", []) if isinstance(dataset.get("tissue"), list) else [])
            ]
            if tissue and tissue.lower() not in " ".join(ds_tissues):
                continue

            # Filter disease
            ds_diseases = [
                d.get("label", "").lower()
                for d in (dataset.get("disease", []) if isinstance(dataset.get("disease"), list) else [])
            ]
            if disease and disease.lower() not in " ".join(ds_diseases):
                continue

            # Extract assay info
            ds_assays = [
                a.get("label", "")
                for a in (dataset.get("assay", []) if isinstance(dataset.get("assay"), list) else [])
            ]

            results.append({
                "dataset_id": dataset.get("dataset_id", ""),
                "collection_id": collection.get("collection_id", ""),
                "title": dataset.get("title") or dataset.get("name") or col_title,
                "description": (col_desc[:200] if col_desc else ""),
                "tissue": ", ".join(t.get("label", "") for t in (dataset.get("tissue", []) if isinstance(dataset.get("tissue"), list) else [])),
                "disease": ", ".join(d.get("label", "") for d in (dataset.get("disease", []) if isinstance(dataset.get("disease"), list) else [])),
                "cell_count": dataset.get("cell_count", 0),
                "organism": ", ".join(o.get("label", "") for o in (dataset.get("organism", []) if isinstance(dataset.get("organism"), list) else [])),
                "assay": ", ".join(ds_assays),
            })

            if len(results) >= max_results:
                break
        if len(results) >= max_results:
            break

    return {
        "datasets": results,
        "query": query,
        "count": len(results),
        "summary": (
            f"Found {len(results)} CELLxGENE dataset(s) for '{query}'. "
            + ("; ".join(f"{d['title'][:50]} ({d['cell_count']} cells)" for d in results[:3]) if results else "Try broader search terms.")
        ),
    }
