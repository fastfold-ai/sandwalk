"""literature.pubmed_search: NCBI E-utilities PubMed search. Split from tools/literature.py.

Calls ``request_json`` indirectly via the ``tools.literature`` hub module so that
``patch("tools.literature.request_json")`` in tests continues to work regardless of
which submodule performs the call.
"""

import re as _re

from tools import literature as _literature
from tools import registry


def _normalize_pubmed_query(query: str) -> str:
    """Normalize a PubMed query for NCBI E-utilities.

    - Uppercase standalone boolean operators (and→AND, or→OR, not→NOT)
    - Preserve text inside quoted phrases
    - Normalize whitespace
    """
    # Split on quoted phrases to preserve them
    parts = _re.split(r'(".*?")', query)
    normalized = []
    for _i, part in enumerate(parts):
        if part.startswith('"'):
            # Quoted phrase — keep as-is
            normalized.append(part)
        else:
            # Uppercase standalone boolean operators
            part = _re.sub(r'\b(and)\b', 'AND', part, flags=_re.IGNORECASE)
            part = _re.sub(r'\b(or)\b', 'OR', part, flags=_re.IGNORECASE)
            part = _re.sub(r'\b(not)\b', 'NOT', part, flags=_re.IGNORECASE)
            normalized.append(part)
    result = "".join(normalized)
    # Normalize whitespace
    return " ".join(result.split())


def _simplify_query(query: str) -> list[str]:
    """Generate progressively simpler queries by dropping terms.

    PubMed ANDs all terms by default, so long queries (8+ terms) often return
    zero results. We try shorter versions as fallbacks.
    """
    # Remove parenthesized groups and quoted phrases for counting
    clean = _re.sub(r'\([^)]*\)', '', query)
    clean = _re.sub(r'"[^"]*"', '', clean)
    # Split on whitespace, ignoring boolean operators
    words = [w for w in query.split() if w.upper() not in ("AND", "OR", "NOT")]

    if len(words) <= 4:
        return []  # Already short enough

    # Try keeping just the most distinctive terms (drop common qualifiers)
    # Strategy: take first N words from the original query
    shorter = []
    if len(words) > 6:
        shorter.append(" ".join(words[:5]))
    if len(words) > 4:
        shorter.append(" ".join(words[:3]))
    return shorter


@registry.register(
    name="literature.pubmed_search",
    description="Search PubMed for publications via NCBI E-utilities API",
    category="literature",
    parameters={
        "query": "Search query (e.g. 'molecular glue degrader CRBN')",
        "max_results": "Maximum number of results (default 20)",
    },
    usage_guide="You need recent publications on a target, compound, or mechanism. Use to support or challenge computational findings with published evidence.",
)
def pubmed_search(query: str, max_results: int = 20, **kwargs) -> dict:
    """Search PubMed using NCBI E-utilities (ESearch + ESummary)."""
    try:
        import httpx
    except ImportError:
        return {"error": "httpx required (pip install httpx)", "summary": "httpx required (pip install httpx)"}
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    # Step 1: ESearch to get PMIDs
    search_url = f"{base}/esearch.fcgi"
    normalized = _normalize_pubmed_query(query)
    params = {
        "db": "pubmed",
        "term": normalized,
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
    }

    search_data, error = _literature.request_json(
        "GET",
        search_url,
        params=params,
        timeout=30,
        retries=2,
    )
    if error:
        return {"error": f"PubMed search failed: {error}", "summary": f"PubMed search failed: {error}"}
    result = search_data.get("esearchresult", {})
    pmids = result.get("idlist", [])
    total_count = int(result.get("count", 0))

    # If no results with a long query, retry with progressively simpler versions
    used_query = query
    if not pmids:
        for simpler in _simplify_query(query):
            params["term"] = _normalize_pubmed_query(simpler)
            search_data, fallback_error = _literature.request_json(
                "GET",
                search_url,
                params=params,
                timeout=30,
                retries=2,
            )
            if fallback_error:
                continue
            result = search_data.get("esearchresult", {})
            pmids = result.get("idlist", [])
            total_count = int(result.get("count", 0))
            if pmids:
                used_query = simpler
                break

    if not pmids:
        return {"summary": f"No results for '{query}'", "total_count": 0, "articles": []}

    # Step 2: ESummary for article details
    summary_url = f"{base}/esummary.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
    }

    summary_data, error = _literature.request_json(
        "GET",
        summary_url,
        params=params,
        timeout=30,
        retries=2,
    )
    if error:
        return {"error": f"PubMed summary failed: {error}", "summary": f"PubMed summary failed: {error}"}
    articles = []
    for pmid in pmids:
        info = summary_data.get("result", {}).get(pmid, {})
        if not info or pmid == "uids":
            continue

        authors = info.get("authors", [])
        first_author = authors[0].get("name", "") if authors else ""

        articles.append({
            "pmid": pmid,
            "title": info.get("title", ""),
            "first_author": first_author,
            "journal": info.get("source", ""),
            "pub_date": info.get("pubdate", ""),
            "doi": next((a.get("value", "") for a in info.get("articleids", [])
                        if a.get("idtype") == "doi"), ""),
        })

    summary = f"PubMed search '{used_query}': {total_count} total, showing {len(articles)}"
    if used_query != query:
        summary += f" (simplified from: '{query}')"

    return {
        "summary": summary,
        "query": used_query,
        "original_query": query,
        "total_count": total_count,
        "articles": articles,
    }
