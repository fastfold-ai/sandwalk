"""omics.proteomics_enrich: pathway enrichment for protein lists. Split from tools/omics.py."""
from pathlib import Path

from tools import registry

from tools import omics as _omics


@registry.register(
    name="omics.proteomics_enrich",
    description="Pathway enrichment analysis from a list of differentially abundant proteins",
    category="omics",
    parameters={
        "proteins": "Comma-separated list of protein/gene symbols",
        "background_path": "Path to full protein list (optional, for background set)",
        "organism": "Organism for gene set lookup (default 'Homo sapiens')",
    },
    usage_guide=(
        "Run over-representation analysis on a set of differentially expressed proteins. "
        "Uses Enrichr API for pathway databases (KEGG, Reactome, GO)."
    ),
)
def proteomics_enrich(
    proteins: str = "",
    background_path: str = "",
    organism: str = "Homo sapiens",
    **kwargs,
) -> dict:
    """Pathway enrichment for a protein list via Enrichr."""
    seen = set()
    gene_list = []
    for gene in (g.strip() for g in proteins.split(",") if g.strip()):
        key = gene.upper()
        if key not in seen:
            seen.add(key)
            gene_list.append(gene)
    if not gene_list:
        return {"error": "No proteins provided", "summary": "Empty protein list"}

    libraries, org_error = _omics._enrichr_libraries_for_organism(organism)
    if org_error:
        return {"error": org_error, "summary": org_error}

    background_info = {}
    if background_path:
        background_genes, bg_error = _omics._parse_gene_list_file(background_path)
        if bg_error:
            return {"error": bg_error, "summary": bg_error}
        if not background_genes:
            return {
                "error": "Background file contains no genes after parsing",
                "summary": f"Empty background set: {background_path}",
            }

        original_n = len(gene_list)
        gene_list = [g for g in gene_list if g.upper() in background_genes]
        if not gene_list:
            return {
                "error": "None of the input genes were found in the provided background set",
                "background_gene_count": len(background_genes),
                "summary": "No overlap between input list and background set",
            }

        background_info = {
            "background_path": str(Path(background_path).expanduser()),
            "background_gene_count": len(background_genes),
            "n_proteins_before_background_filter": original_n,
            "n_proteins_after_background_filter": len(gene_list),
            # Enrichr endpoint has no custom-universe parameter; we apply background as input filter.
            "background_mode": "input_filter_only",
        }

    # Submit to Enrichr
    add_url = "https://maayanlab.cloud/Enrichr/addList"
    payload = {"list": (None, "\n".join(gene_list)), "description": (None, "ct proteomics enrichment")}

    import httpx

    try:
        resp = httpx.post(add_url, files=payload, timeout=15)
        resp.raise_for_status()
        user_list_id = resp.json().get("userListId")
    except Exception as exc:
        return {"error": f"Enrichr submission failed: {str(exc)[:200]}", "summary": f"Enrichr error: {str(exc)[:100]}"}

    if not user_list_id:
        return {"error": "Enrichr did not return a list ID", "summary": "Enrichr submission failed"}

    # Query key libraries
    all_results = {}
    library_errors = {}

    for lib in libraries:
        enrich_url = f"https://maayanlab.cloud/Enrichr/enrich?userListId={user_list_id}&backgroundType={lib}"
        try:
            resp = httpx.get(enrich_url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            terms = data.get(lib, [])
            top_terms = []
            for term in terms[:10]:
                top_terms.append({
                    "term": term[1],
                    "pvalue": term[2],
                    "adj_pvalue": term[6],
                    "odds_ratio": term[3],
                    "genes": term[5],
                })
            all_results[lib] = top_terms
        except Exception as exc:
            all_results[lib] = []
            library_errors[lib] = str(exc)[:200]

    # Flatten top hits
    top_summary = []
    for _lib, terms in all_results.items():
        for t in terms[:3]:
            if t["adj_pvalue"] < 0.05:
                top_summary.append(f"{t['term']} (q={t['adj_pvalue']:.2e})")

    return {
        "n_proteins_submitted": len(gene_list),
        "organism": organism,
        "libraries": libraries,
        "enrichment_results": all_results,
        "library_errors": library_errors,
        **background_info,
        "summary": (
            f"Enrichment of {len(gene_list)} proteins. "
            + (f"Top enriched: {'; '.join(top_summary[:5])}" if top_summary else "No significant enrichments (FDR<0.05).")
            + (" Background set applied as input filter." if background_path else "")
        ),
    }
