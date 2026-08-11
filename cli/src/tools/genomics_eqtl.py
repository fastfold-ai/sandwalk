"""genomics.eqtl_lookup: eQTL Catalogue lookup. Split from tools/genomics.py."""
from tools import genomics as _genomics
from tools import registry


@registry.register(
    name="genomics.eqtl_lookup",
    description="Query GTEx for expression quantitative trait loci (eQTLs) for a gene across tissues",
    category="genomics",
    parameters={
        "gene": "Gene symbol (e.g. 'BRCA1', 'TP53')",
        "tissue": "GTEx tissue name to filter (optional, e.g. 'Liver', 'Brain_Cortex')",
    },
    requires_data=[],
    usage_guide="You want to find genetic variants that regulate gene expression in specific tissues. Use to understand tissue-specific regulation, identify regulatory variants, and connect GWAS signals to gene function.",
)
def eqtl_lookup(gene: str, tissue: str = None, **kwargs) -> dict:
    """Query the GTEx API for significant eQTLs for a gene."""
    try:
        import httpx  # noqa: F401
    except ImportError:
        return {"error": "httpx required (pip install httpx)", "summary": "httpx required (pip install httpx)"}
    gtex_base = "https://gtexportal.org/api/v2"

    # Step 1: Resolve gene symbol to GENCODE ID
    gene_url = f"{gtex_base}/reference/gene"
    gene_params = {"geneId": gene}

    gene_data, error = _genomics.request_json(
        "GET",
        gene_url,
        params=gene_params,
        timeout=10,
        retries=2,
    )
    if error:
        return {"error": f"GTEx gene lookup failed: {error}", "summary": f"GTEx gene lookup failed: {error}"}
    genes_list = gene_data.get("data", [])
    if not genes_list:
        return {
            "error": f"Gene '{gene}' not found in GTEx GENCODE v26 reference",
            "suggestion": "Try using the official HGNC gene symbol",
        }

    # Use the first matching gene entry
    gene_info = genes_list[0]
    gencode_id = gene_info.get("gencodeId", "")
    gene_symbol = gene_info.get("geneSymbol", gene)
    description = gene_info.get("description", "")

    if not gencode_id:
        return {"error": f"Could not resolve GENCODE ID for {gene}", "summary": f"Could not resolve GENCODE ID for {gene}"}
    # Step 2: Query significant single-tissue eQTLs
    eqtl_url = f"{gtex_base}/association/singleTissueEqtl"
    eqtl_params = {
        "gencodeId": gencode_id,
        "datasetId": "gtex_v8",
    }
    if tissue:
        eqtl_params["tissueSiteDetailId"] = tissue

    eqtl_data, error = _genomics.request_json(
        "GET",
        eqtl_url,
        params=eqtl_params,
        timeout=10,
        retries=2,
    )
    if error:
        return {"error": f"GTEx eQTL query failed: {error}", "summary": f"GTEx eQTL query failed: {error}"}
    eqtls_raw = eqtl_data.get("data", [])

    if not eqtls_raw:
        tissue_str = f" in {tissue}" if tissue else ""
        return {
            "summary": f"No significant eQTLs found for {gene_symbol}{tissue_str} in GTEx v8",
            "gene": gene_symbol,
            "gencode_id": gencode_id,
            "eqtls": [],
            "n_eqtls": 0,
        }

    # Parse eQTL results
    eqtls = []
    tissues_found = set()

    for eqtl in eqtls_raw:
        tissue_id = eqtl.get("tissueSiteDetailId", "")
        tissues_found.add(tissue_id)

        eqtls.append({
            "variant_id": eqtl.get("variantId", ""),
            "snp_id": eqtl.get("snpId", ""),
            "tissue": tissue_id,
            "p_value": eqtl.get("pValue"),
            "nes": eqtl.get("nes"),  # Normalized effect size
            "chromosome": eqtl.get("chromosome", ""),
            "pos": eqtl.get("pos"),
            "gene_symbol": eqtl.get("geneSymbol", gene_symbol),
        })

    # Sort by absolute NES (largest effect first)
    eqtls.sort(key=lambda x: abs(x["nes"]) if x["nes"] is not None else 0, reverse=True)

    tissue_str = f" in {tissue}" if tissue else f" across {len(tissues_found)} tissues"
    return {
        "summary": (
            f"GTEx eQTLs for {gene_symbol} ({gencode_id}){tissue_str}: "
            f"{len(eqtls)} significant eQTLs found"
        ),
        "gene": gene_symbol,
        "gencode_id": gencode_id,
        "gene_description": description,
        "n_eqtls": len(eqtls),
        "n_tissues": len(tissues_found),
        "tissues": sorted(tissues_found),
        "eqtls": eqtls[:50],  # Return top 50 by effect size
    }
