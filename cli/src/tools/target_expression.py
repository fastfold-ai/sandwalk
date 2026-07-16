"""
target.expression_profile: tissue expression via GTEx + Human Protein Atlas.

Split from tools/target.py.
"""

from tools import registry
from tools.http_client import request


@registry.register(
    name="target.expression_profile",
    description="Get tissue expression profile for a gene using GTEx Portal API and Human Protein Atlas",
    category="target",
    parameters={
        "gene": "Gene symbol (e.g. TP53, EGFR, BRCA1)",
        "top_n": "Number of top tissues to return (default 10)",
    },
    requires_data=[],
    usage_guide="You want to understand where a target is expressed — tissue specificity, cancer vs normal, and cell type expression. Critical for safety assessment and indication selection.",
)
def expression_profile(gene: str, top_n: int = 10, **kwargs) -> dict:
    """Get tissue expression profile for a gene from GTEx and Human Protein Atlas.

    Resolves gene symbol to GENCODE ID via the GTEx reference API, then
    fetches median expression per tissue from GTEx v8. Also queries HPA
    for protein-level and single-cell expression. Computes a tissue
    specificity index (tau) from the GTEx TPM values.
    """
    # --- Step 1: Resolve gene symbol to GENCODE ID via GTEx reference API ---
    def _gene_symbol_candidates(input_gene: str) -> list[str]:
        alias_map = {
            "GBA1": "GBA",
            "PARK2": "PRKN",
        }
        token = (input_gene or "").strip()
        if not token:
            return []
        candidates = [token]
        mapped = alias_map.get(token.upper())
        if mapped:
            candidates.append(mapped)
        if token.endswith("1") and len(token) > 1:
            candidates.append(token[:-1])

        deduped = []
        seen = set()
        for c in candidates:
            k = c.upper()
            if k in seen:
                continue
            seen.add(k)
            deduped.append(c)
        return deduped

    gencode_id = None
    gene_symbol = gene
    gene_candidates = _gene_symbol_candidates(gene)

    for gene_candidate in gene_candidates:
        ref_resp, ref_error = request(
            "GET",
            "https://gtexportal.org/api/v2/reference/gene",
            params={"geneId": gene_candidate},
            timeout=10,
            raise_for_status=False,
        )
        if ref_error or ref_resp.status_code != 200:
            continue
        try:
            ref_data = ref_resp.json()
        except Exception:
            continue
        genes_list = ref_data.get("data", [])
        if genes_list:
            gene_info = genes_list[0]
            gencode_id = gene_info.get("gencodeId", "")
            gene_symbol = gene_info.get("geneSymbol", gene_candidate)
            break

    # --- Step 2: GTEx median gene expression per tissue ---
    gtex_expression = []

    if gencode_id:
        gtex_resp, gtex_error = request(
            "GET",
            "https://gtexportal.org/api/v2/expression/medianGeneExpression",
            params={
                "gencodeId": gencode_id,
                "datasetId": "gtex_v8",
            },
            timeout=10,
            raise_for_status=False,
        )
        if not gtex_error and gtex_resp.status_code == 200:
            try:
                gtex_data = gtex_resp.json()
                for entry in gtex_data.get("data", []):
                    gtex_expression.append({
                        "tissue": entry.get("tissueSiteDetailId", ""),
                        "median_tpm": entry.get("median", 0),
                    })
                gtex_expression.sort(key=lambda x: x.get("median_tpm", 0), reverse=True)
            except Exception:
                gtex_expression = []

    # --- Step 3: Compute tissue specificity index (tau) ---
    # Tau ranges from 0 (ubiquitous) to 1 (tissue-specific)
    tau = None
    if gtex_expression:
        tpm_values = [t["median_tpm"] for t in gtex_expression]
        max_tpm = max(tpm_values) if tpm_values else 0
        if max_tpm > 0 and len(tpm_values) > 1:
            n = len(tpm_values)
            tau = sum(1.0 - (x / max_tpm) for x in tpm_values) / (n - 1)
            tau = round(tau, 4)

    # --- Step 4: Human Protein Atlas ---
    hpa_data = {}
    tissue_rna = []
    tissue_protein = []
    cancer_expression = []
    cell_type_expression = []
    ensembl_id = None

    # Try to extract Ensembl ID from GENCODE ID (strip version suffix)
    if gencode_id:
        ensembl_id = gencode_id.split(".")[0]

    # Query HPA using Ensembl ID if available, then gene aliases.
    hpa_queries = []
    if ensembl_id:
        hpa_queries.append(ensembl_id)
    if gene_symbol:
        hpa_queries.append(gene_symbol)
    hpa_queries.extend(gene_candidates)

    # Stable de-dup for query candidates.
    deduped_hpa_queries = []
    seen_hpa = set()
    for q in hpa_queries:
        key = str(q).upper()
        if key in seen_hpa:
            continue
        seen_hpa.add(key)
        deduped_hpa_queries.append(q)

    for hpa_query in deduped_hpa_queries:
        hpa_resp, hpa_error = request(
            "GET",
            f"https://www.proteinatlas.org/{hpa_query}.json",
            timeout=10,
            headers={"Accept": "application/json"},
            raise_for_status=False,
        )
        if hpa_error or hpa_resp is None or hpa_resp.status_code != 200:
            continue
        try:
            hpa_data = hpa_resp.json()
        except Exception:
            hpa_data = {}
        if hpa_data:
            break

    if hpa_data:
        # RNA tissue expression
        for entry in hpa_data.get("RNATissue", {}).get("data", []):
            tissue_rna.append({
                "tissue": entry.get("Tissue", ""),
                "tpm": entry.get("TPM", 0),
                "ntpm": entry.get("nTPM", 0),
            })
        tissue_rna.sort(key=lambda x: x.get("tpm", 0), reverse=True)

        # Protein tissue expression
        for entry in hpa_data.get("ProteinTissue", {}).get("data", []):
            tissue_protein.append({
                "tissue": entry.get("Tissue", ""),
                "level": entry.get("Level", ""),
                "cell_type": entry.get("CellType", ""),
            })

        # Cancer expression
        for entry in hpa_data.get("RNACancer", {}).get("data", []):
            cancer_expression.append({
                "cancer": entry.get("Cancer", ""),
                "tpm": entry.get("TPM", 0),
                "ntpm": entry.get("nTPM", 0),
            })
        cancer_expression.sort(key=lambda x: x.get("tpm", 0), reverse=True)

        # Cell type expression
        for entry in hpa_data.get("RNASingleCell", {}).get("data", []):
            cell_type_expression.append({
                "cell_type": entry.get("CellType", ""),
                "ntpm": entry.get("nTPM", 0),
            })
        cell_type_expression.sort(key=lambda x: x.get("ntpm", 0), reverse=True)

    # --- Build response ---
    # Prefer GTEx for top tissues (quantitative TPM), fall back to HPA
    top_tissues = gtex_expression[:top_n] if gtex_expression else tissue_rna[:top_n]
    if not top_tissues and not hpa_data:
        return {
            "summary": f"No expression data found for {gene} from GTEx or Human Protein Atlas",
            "gene": gene,
            "error": "No data returned from GTEx or HPA APIs",
        }

    n_tissues = len(gtex_expression) if gtex_expression else len(tissue_rna)

    # Build summary line matching the spec format
    if gtex_expression:
        tissue_strs = [
            f"{t['tissue']} ({t['median_tpm']:.1f} TPM)" for t in gtex_expression[:top_n]
        ]
        summary = f"{gene_symbol} expression: highest in {', '.join(tissue_strs[:5])}"
    elif tissue_rna:
        tissue_strs = [
            f"{t['tissue']} ({t['tpm']:.1f} TPM)" for t in tissue_rna[:top_n]
        ]
        summary = f"{gene_symbol} expression: highest in {', '.join(tissue_strs[:5])}"
    else:
        summary = f"Expression profile for {gene_symbol}: {n_tissues} tissues profiled"

    if tau is not None:
        specificity_label = (
            "tissue-specific" if tau > 0.8
            else "tissue-enriched" if tau > 0.5
            else "broadly expressed"
        )
        summary += f". Specificity: {specificity_label} (tau={tau:.3f})"

    # RNA tissue specificity category from HPA
    rna_specificity = hpa_data.get("RNATissue", {}).get("summary", "")

    return {
        "summary": summary,
        "gene": gene_symbol,
        "gencode_id": gencode_id,
        "ensembl_id": ensembl_id,
        "tissue_specificity_tau": tau,
        "rna_specificity_hpa": rna_specificity,
        "gtex_expression": gtex_expression[:top_n],
        "tissue_rna_hpa": tissue_rna[:top_n],
        "tissue_protein": tissue_protein[:30],
        "cancer_expression": cancer_expression[:20],
        "cell_type_expression": cell_type_expression[:20],
        "n_tissues_profiled": n_tissues,
        "top_expressing_tissues": top_tissues[:top_n],
    }
