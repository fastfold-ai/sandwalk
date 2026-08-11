"""literature.patent_search: tiered patent search (Lens.org, EPO OPS, PubMed fallback).

Split from tools/literature.py. Calls ``request``/``pubmed_search`` indirectly via
the ``tools.literature`` hub module so that ``patch("tools.literature.pubmed_search")``
in tests continues to work regardless of which submodule performs the call.
"""

from tools import literature as _literature
from tools import registry


@registry.register(
    name="literature.patent_search",
    description="Search patent databases for drug discovery-relevant patents (Lens.org, EPO OPS, or PubMed fallback)",
    category="literature",
    parameters={
        "query": "Patent search query (e.g. 'CRBN molecular glue degrader')",
        "max_results": "Maximum number of results (default 20)",
    },
    usage_guide="You need to find relevant patents for a target, compound class, or technology. Use to assess patent landscape, freedom to operate, or find prior art. Tries Lens.org API first (if api.lens_key configured), then EPO Open Patent Services, then falls back to PubMed patent-related literature.",
)
def patent_search(query: str, max_results: int = 20, **kwargs) -> dict:
    """Search patent databases for drug discovery-relevant patents.

    Uses a tiered approach:
    1. Lens.org Patent API (if API key is configured via api.lens_key)
    2. EPO Open Patent Services (free, no key required for basic search)
    3. PubMed fallback (searches for patent-related publications)
    """
    # Try Lens.org first
    session = kwargs.get("_session", None)
    lens_key = None
    if session and hasattr(session, "config"):
        lens_key = session.config.get("api.lens_key", None)

    if lens_key:
        result = _patent_search_lens(query, max_results, lens_key)
        if result and "error" not in result:
            return result

    # Try EPO OPS (free, no key required)
    result = _patent_search_epo(query, max_results)
    if result and "error" not in result:
        return result

    # Fall back to PubMed patent search
    return _patent_search_pubmed_fallback(query, max_results)


def _patent_search_lens(query: str, max_results: int, api_key: str) -> dict:
    """Search Lens.org Patent API."""
    url = "https://api.lens.org/patent/search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "query": {
            "match": query,
        },
        "size": max_results,
        "sort": [{"relevance": "desc"}],
        "include": [
            "lens_id", "title", "abstract", "applicant",
            "publication_date", "publication_key", "jurisdiction",
            "doc_number", "kind",
        ],
    }

    resp, error = _literature.request(
        "POST",
        url,
        json=payload,
        headers=headers,
        timeout=30,
        retries=2,
        raise_for_status=False,
    )
    if error:
        return {"error": f"Lens.org API request failed: {error}", "summary": f"Lens.org API request failed: {error}"}
    if resp.status_code != 200:
        return {"error": f"Lens.org API returned status {resp.status_code}", "summary": f"Lens.org API returned status {resp.status_code}"}
    try:
        data = resp.json()
    except Exception:
        return {"error": "Lens.org API returned invalid JSON", "summary": "Lens.org API returned invalid JSON"}
    results = data.get("data", [])
    total = data.get("total", 0)

    patents = []
    for item in results:
        title_obj = item.get("title", [])
        title = title_obj[0].get("text", "") if title_obj else ""

        abstract_obj = item.get("abstract", [])
        abstract = abstract_obj[0].get("text", "")[:300] if abstract_obj else ""

        applicants = item.get("applicant", [])
        applicant_names = [a.get("name", "") for a in applicants[:3]] if applicants else []

        patents.append({
            "lens_id": item.get("lens_id", ""),
            "title": title,
            "abstract": abstract,
            "applicants": applicant_names,
            "publication_date": item.get("publication_date", ""),
            "doc_number": item.get("doc_number", ""),
            "jurisdiction": item.get("jurisdiction", ""),
            "kind": item.get("kind", ""),
        })

    # Date range for summary
    dates = [p["publication_date"] for p in patents if p["publication_date"]]
    date_range = ""
    if dates:
        years = sorted({d[:4] for d in dates if len(d) >= 4})
        if years:
            date_range = f" ({years[0]}-{years[-1]})"

    return {
        "summary": f"Patent search '{query}': {total} total, showing {len(patents)}{date_range}",
        "source": "lens.org",
        "query": query,
        "total_count": total,
        "patents": patents,
    }


def _patent_search_epo(query: str, max_results: int) -> dict:
    """Search EPO Open Patent Services (Espacenet OPS) — free, no key required."""
    import xml.etree.ElementTree as ET

    # EPO OPS biblio search endpoint
    url = "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"
    params = {
        "q": query,
        "Range": f"1-{min(max_results, 100)}",
    }
    headers = {
        "Accept": "application/xml",
    }

    resp, error = _literature.request(
        "GET",
        url,
        params=params,
        headers=headers,
        timeout=30,
        retries=0,
        raise_for_status=False,
    )
    if error:
        return {"error": f"EPO OPS request failed: {error}", "summary": f"EPO OPS request failed: {error}"}
    if resp.status_code == 404:
        return {"error": "No patents found via EPO OPS", "summary": "No patents found via EPO OPS"}
    if resp.status_code == 403:
        # Rate limited or auth required
        return {"error": "EPO OPS rate limited or requires authentication", "summary": "EPO OPS rate limited or requires authentication"}
    if resp.status_code != 200:
        return {"error": f"EPO OPS returned status {resp.status_code}", "summary": f"EPO OPS returned status {resp.status_code}"}
    # Validate Content-Type before XML parsing
    content_type = ""
    try:
        ct_raw = resp.headers.get("content-type", "")
        if isinstance(ct_raw, str):
            content_type = ct_raw.lower()
    except Exception:
        pass
    if content_type and "xml" not in content_type and "text/plain" not in content_type:
        return {"error": f"EPO OPS returned {content_type}, expected XML", "summary": "EPO OPS returned non-XML response"}

    # Parse XML response
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        return {"error": f"Failed to parse EPO OPS XML: {e}", "summary": "Failed to parse EPO patent XML"}

    # EPO OPS XML namespaces
    ns = {
        "ops": "http://ops.epo.org",
        "epo": "http://www.epo.org/exchange",
        "exch": "http://www.epo.org/exchange",
    }

    patents = []
    total_count = 0

    # Try to get total count
    total_elem = root.find(".//ops:biblio-search", ns)
    if total_elem is not None:
        total_count = int(total_elem.get("total-result-count", 0))

    # Extract patent documents
    for doc in root.findall(".//exch:exchange-document", ns):
        doc_id = doc.get("doc-number", "")
        country = doc.get("country", "")
        kind = doc.get("kind", "")

        # Title
        title = ""
        for title_elem in doc.findall(".//exch:invention-title", ns):
            if title_elem.get("lang", "") == "en" or not title:
                title = title_elem.text or ""

        # Applicants
        applicants = []
        for app in doc.findall(".//exch:applicant/exch:applicant-name/exch:name", ns):
            if app.text:
                applicants.append(app.text)

        # Publication date
        pub_date = ""
        for pub_ref in doc.findall(".//exch:publication-reference//exch:date", ns):
            if pub_ref.text:
                pub_date = pub_ref.text
                break

        # Abstract
        abstract = ""
        for abs_elem in doc.findall(".//exch:abstract", ns):
            if abs_elem.get("lang", "") == "en" or not abstract:
                parts = []
                for p in abs_elem.findall(".//exch:p", ns):
                    if p.text:
                        parts.append(p.text)
                if parts:
                    abstract = " ".join(parts)[:300]

        patent_number = f"{country}{doc_id}{kind}" if country else doc_id

        patents.append({
            "patent_number": patent_number,
            "title": title,
            "abstract": abstract,
            "applicants": applicants[:3],
            "publication_date": pub_date,
            "country": country,
            "kind": kind,
        })

    if not patents:
        return {"error": "EPO OPS returned no parseable patents", "summary": "EPO OPS returned no parseable patents"}
    # Date range for summary
    dates = [p["publication_date"] for p in patents if p["publication_date"]]
    date_range = ""
    if dates:
        years = sorted({d[:4] for d in dates if len(d) >= 4})
        if years:
            date_range = f" ({years[0]}-{years[-1]})"

    return {
        "summary": f"Patent search '{query}': {total_count} patents found via EPO{date_range}",
        "source": "epo_ops",
        "query": query,
        "total_count": total_count,
        "patents": patents,
    }


def _patent_search_pubmed_fallback(query: str, max_results: int) -> dict:
    """Fall back to PubMed search for patent-related publications."""
    # Add patent-related terms to the query
    patent_query = f"({query}) AND (patent OR intellectual property OR claims OR USPTO OR EPO)"

    result = _literature.pubmed_search(query=patent_query, max_results=max_results)

    if "error" in result:
        return result

    # Re-label for clarity
    return {
        "summary": f"Patent search '{query}' (PubMed fallback): {result.get('total_count', 0)} "
                   f"patent-related publications found",
        "source": "pubmed_fallback",
        "query": query,
        "note": "No patent API available — showing patent-related PubMed publications. "
                "Configure api.lens_key for direct patent search via Lens.org.",
        "total_count": result.get("total_count", 0),
        "articles": result.get("articles", []),
    }
