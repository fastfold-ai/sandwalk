"""data_api.ncbi_gene: NCBI Entrez gene/database lookup. Split from tools/data_api.py."""
from tools import data_api as _data_api
from tools import registry


@registry.register(
    name="data_api.ncbi_gene",
    description="Query NCBI databases for gene information, ClinVar variants, or dbSNP data",
    category="data_api",
    parameters={
        "query": "Gene symbol (e.g. BRCA1) or NCBI Gene ID (e.g. 672)",
        "database": "Database to query: 'gene', 'clinvar', or 'dbsnp' (default 'gene')",
    },
    requires_data=[],
    usage_guide="You need NCBI gene summaries, ClinVar clinical variant data, or dbSNP information for a gene. Use for gene annotation, variant interpretation, and clinical genetics.",
)
def ncbi_gene(query: str, database: str = "gene", **kwargs) -> dict:
    """Query NCBI E-utilities for gene, ClinVar, or dbSNP data."""
    valid_dbs = ("gene", "clinvar", "dbsnp")
    if database not in valid_dbs:
        return {"error": f"Invalid database '{database}'. Choose from: {', '.join(valid_dbs)}", "summary": f"Invalid NCBI database '{database}'"}

    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    # Step 1: Search for the gene/variant
    if database == "gene":
        search_term = f"{query}[Gene Name] AND Homo sapiens[Organism]"
        db = "gene"
    elif database == "clinvar":
        search_term = f"{query}[Gene Name]"
        db = "clinvar"
    else:  # dbsnp
        search_term = f"{query}[Gene Name]"
        db = "snp"

    try:
        search_resp = _data_api._http_get(
            f"{base}/esearch.fcgi",
            params={
                "db": db,
                "term": search_term,
                "retmax": 20,
                "retmode": "json",
                "sort": "relevance",
            },
            timeout=15,
            retries=2,
        )
        search_resp.raise_for_status()
        search_data = search_resp.json()
    except Exception as e:
        return {"error": f"NCBI search failed: {e}", "summary": f"NCBI query failed for '{query}'"}

    result = search_data.get("esearchresult", {})
    ids = result.get("idlist", [])
    total_count = int(result.get("count", 0))

    if not ids:
        return {
            "summary": f"No NCBI {database} results for '{query}'",
            "query": query,
            "database": database,
            "total_count": 0,
            "results": [],
        }

    # Step 2: Fetch summaries
    try:
        summary_resp = _data_api._http_get(
            f"{base}/esummary.fcgi",
            params={
                "db": db,
                "id": ",".join(ids[:20]),
                "retmode": "json",
            },
            timeout=15,
            retries=2,
        )
        summary_resp.raise_for_status()
        summary_data = summary_resp.json()
    except Exception as e:
        return {"error": f"NCBI summary failed: {e}", "summary": f"NCBI summary lookup failed for '{query}'"}

    results_dict = summary_data.get("result", {})

    if database == "gene":
        gene_results = []
        for gid in ids:
            info = results_dict.get(gid, {})
            if not info or gid == "uids":
                continue
            gene_results.append({
                "gene_id": gid,
                "symbol": info.get("name", ""),
                "description": info.get("description", ""),
                "chromosome": info.get("chromosome", ""),
                "organism": info.get("organism", {}).get("scientificname", ""),
                "aliases": info.get("otheraliases", ""),
                "summary": info.get("summary", ""),
                "gene_type": info.get("geneticSource", ""),
                "map_location": info.get("maplocation", ""),
            })

        top = gene_results[0] if gene_results else {}
        return {
            "summary": (
                f"NCBI Gene {top.get('gene_id', '')} ({top.get('symbol', query)}): "
                f"{top.get('description', 'N/A')}, "
                f"chr{top.get('chromosome', '?')}, "
                f"{total_count} total ClinVar variants"
            ),
            "query": query,
            "database": "gene",
            "total_count": total_count,
            "genes": gene_results,
        }

    elif database == "clinvar":
        variants = []
        for vid in ids:
            info = results_dict.get(vid, {})
            if not info or vid == "uids":
                continue
            variants.append({
                "uid": vid,
                "title": info.get("title", ""),
                "clinical_significance": info.get("clinical_significance", {}).get("description", ""),
                "gene_sort": info.get("gene_sort", ""),
                "variation_set": info.get("variation_set", []),
                "obj_type": info.get("obj_type", ""),
            })

        return {
            "summary": f"ClinVar for {query}: {total_count} total variants, showing {len(variants)}",
            "query": query,
            "database": "clinvar",
            "total_count": total_count,
            "variants": variants,
        }

    else:  # dbsnp
        snps = []
        for sid in ids:
            info = results_dict.get(sid, {})
            if not info or sid == "uids":
                continue
            snps.append({
                "uid": sid,
                "snp_id": info.get("snp_id", sid),
                "snp_class": info.get("snp_class", ""),
                "global_maf": info.get("global_mafs", []),
                "genes": info.get("genes", []),
                "clinical_significance": info.get("clinical_significance", ""),
            })

        return {
            "summary": f"dbSNP for {query}: {total_count} total SNPs, showing {len(snps)}",
            "query": query,
            "database": "dbsnp",
            "total_count": total_count,
            "snps": snps,
        }


# ---------------------------------------------------------------------------
# 7. ChEMBL advanced
# ---------------------------------------------------------------------------
