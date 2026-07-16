"""omics.geo_search: search NCBI GEO for datasets. Split from tools/omics.py."""
from tools import registry

from tools import omics as _omics


@registry.register(
    name="omics.geo_search",
    description="Search NCBI GEO for datasets by keyword, organism, and study type",
    category="omics",
    parameters={
        "query": "Search terms (gene, disease, compound, etc.)",
        "organism": "Organism filter (default 'Homo sapiens')",
        "study_type": "Filter: 'scRNA-seq', 'bulk RNA-seq', 'methylation', 'ATAC-seq', 'ChIP-seq', or 'all'",
        "max_results": "Maximum results to return (default 10)",
    },
    usage_guide=(
        "Search NCBI GEO for public omics datasets. Use before omics.geo_fetch "
        "to find relevant accessions. Supports filtering by organism and study type."
    ),
)
def geo_search(
    query: str,
    organism: str = "Homo sapiens",
    study_type: str = "all",
    max_results: int = 10,
    **kwargs,
) -> dict:
    """Search NCBI GEO for datasets."""
    if not query or not query.strip():
        return {"error": "Query is required", "summary": "No query provided"}

    # Build search term
    terms = [query.strip()]
    if organism and organism.lower() != "all":
        terms.append(f'"{organism}"[Organism]')

    study_type_keywords = {
        "scrna-seq": "single cell RNA-seq",
        "bulk rna-seq": "RNA-seq",
        "methylation": "methylation profiling",
        "atac-seq": "ATAC-seq",
        "chip-seq": "ChIP-seq",
    }
    st = study_type.lower().strip()
    if st != "all" and st in study_type_keywords:
        terms.append(study_type_keywords[st])

    search_term = " AND ".join(terms)

    # Step 1: esearch
    esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    data, error = _omics.request_json(
        "GET",
        esearch_url,
        params={
            "db": "gds",
            "term": search_term,
            "retmax": str(min(max_results, 50)),
            "retmode": "json",
        },
        timeout=15,
    )
    if error:
        return {"error": f"GEO search failed: {error}", "summary": f"GEO search error: {error}"}

    esearch_result = data.get("esearchresult", {})
    id_list = esearch_result.get("idlist", [])
    if not id_list:
        return {
            "datasets": [],
            "query": search_term,
            "count": 0,
            "summary": f"No GEO datasets found for '{query}' (organism={organism}, type={study_type})",
        }

    # Step 2: esummary
    esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    summary_data, error = _omics.request_json(
        "GET",
        esummary_url,
        params={
            "db": "gds",
            "id": ",".join(id_list),
            "retmode": "json",
        },
        timeout=15,
    )
    if error:
        return {"error": f"GEO summary fetch failed: {error}", "summary": f"GEO summary error: {error}"}

    result_block = summary_data.get("result", {})
    datasets = []
    for uid in id_list:
        entry = result_block.get(uid, {})
        if not entry or isinstance(entry, str):
            continue
        accession = entry.get("accession", "")
        # GDS entries may not have GSE accession directly; extract from related
        if not accession.startswith("GSE"):
            gse = entry.get("gse", "")
            if gse:
                accession = f"GSE{gse}"
        datasets.append({
            "accession": accession,
            "title": entry.get("title", ""),
            "summary": (entry.get("summary", "") or "")[:300],
            "organism": entry.get("taxon", ""),
            "platform": entry.get("gpl", ""),
            "sample_count": entry.get("n_samples", 0),
            "study_type": entry.get("gdstype", study_type),
            "date": entry.get("pdat", ""),
        })

    return {
        "datasets": datasets,
        "query": search_term,
        "count": len(datasets),
        "summary": (
            f"Found {len(datasets)} GEO dataset(s) for '{query}'. "
            + "; ".join(
                f"{d['accession']}: {d['title'][:60]}" for d in datasets[:3]
            )
        ),
    }
