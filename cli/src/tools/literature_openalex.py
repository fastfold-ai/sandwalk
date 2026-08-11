"""literature.openalex_search: OpenAlex academic publication search.

Split from tools/literature.py. Calls ``request_json`` indirectly via the
``tools.literature`` hub module so that ``patch("tools.literature.request_json")``
in tests continues to work regardless of which submodule performs the call.
"""

from tools import literature as _literature
from tools import registry


@registry.register(
    name="literature.openalex_search",
    description="Search OpenAlex for academic publications with citation data and open access links",
    category="literature",
    parameters={
        "query": "Search query",
        "max_results": "Maximum results (default 20)",
    },
    usage_guide="You want academic publications with citation metrics and open access links. Broader than PubMed — covers all scientific literature. Use for comprehensive literature reviews.",
)
def openalex_search(query: str, max_results: int = 20, **kwargs) -> dict:
    """Search OpenAlex for publications with citation metrics."""
    try:
        import httpx
    except ImportError:
        return {"error": "httpx required (pip install httpx)", "summary": "httpx required (pip install httpx)"}
    url = "https://api.openalex.org/works"
    params = {
        "search": query,
        "per_page": max_results,
        "sort": "relevance_score:desc",
        "mailto": "ct@celltype.bio",
    }

    data, error = _literature.request_json(
        "GET",
        url,
        params=params,
        timeout=30,
        retries=2,
    )
    if error:
        return {"error": f"OpenAlex search failed: {error}", "summary": f"OpenAlex search failed: {error}"}
    results_data = data.get("results", [])
    total_count = data.get("meta", {}).get("count", 0)

    articles = []
    for work in results_data:
        authorships = work.get("authorships", [])
        first_author = ""
        if authorships:
            author_info = authorships[0].get("author", {})
            first_author = author_info.get("display_name", "")

        primary_loc = work.get("primary_location") or {}
        source = primary_loc.get("source") or {}

        articles.append({
            "title": work.get("title", ""),
            "first_author": first_author,
            "publication_year": work.get("publication_year"),
            "cited_by_count": work.get("cited_by_count", 0),
            "doi": work.get("doi", ""),
            "open_access": (work.get("open_access") or {}).get("is_oa", False),
            "source": source.get("display_name", ""),
            "type": work.get("type", ""),
        })

    return {
        "summary": f"OpenAlex search '{query}': {total_count} total, showing {len(articles)}",
        "query": query,
        "total_count": total_count,
        "articles": articles,
    }
