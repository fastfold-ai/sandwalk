"""clinical.tcga_stratify: TCGA/Human Protein Atlas expression-based patient stratification.

Split from tools/clinical.py. Calls ``request``/``request_json`` indirectly via the
``tools.clinical`` hub module so that ``patch("tools.clinical.request")`` in tests
continues to work regardless of which submodule performs the call.
"""

from tools import clinical as _clinical
from tools import registry


@registry.register(
    name="clinical.tcga_stratify",
    description="Stratify patients by target expression using TCGA data from Human Protein Atlas",
    category="clinical",
    parameters={
        "gene": "Gene symbol to query (e.g. CDC25C, GATA2)",
    },
    usage_guide="You want to check if a target gene is expressed in patient tumors — queries TCGA expression data from Human Protein Atlas. Use for clinical biomarker validation and patient stratification strategy.",
)
def tcga_stratify(gene: str, **kwargs) -> dict:
    """Query Human Protein Atlas for TCGA expression data.

    Returns expression levels across cancer types and prognostic associations.
    Convergence = log2(median_FPKM + 1) x |compound_LFC| (when PRISM data available).
    """
    import math
    import re

    try:
        import httpx
    except ImportError:
        return {"error": "httpx required for TCGA queries (pip install httpx)", "summary": "httpx required for TCGA queries (pip install httpx)"}
    # Fast-path cache for common targets (avoids API call)
    _GENE_ENSEMBL_CACHE = {
        "CDC25C": "ENSG00000158402", "GATA2": "ENSG00000179348",
        "RBCK1": "ENSG00000125826", "ZNF687": "ENSG00000143373",
        "BCOR": "ENSG00000183337", "CEP57": "ENSG00000166037",
        "BTBD1": "ENSG00000084693", "FLCN": "ENSG00000154803",
        "LYZ": "ENSG00000090382", "CRBN": "ENSG00000113851",
        "PDCD2": "ENSG00000126249",
    }

    ensembl_id = _GENE_ENSEMBL_CACHE.get(gene.upper())
    if not ensembl_id:
        # Look up via Ensembl REST API — works for any human gene symbol
        try:
            xref_url = f"https://rest.ensembl.org/xrefs/symbol/homo_sapiens/{gene}"
            xref_data, xref_error = _clinical.request_json(
                "GET",
                xref_url,
                timeout=15,
                retries=2,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "ct-celltype/0.1",
                },
            )
            if not xref_error and isinstance(xref_data, list):
                for xref in xref_data:
                    if xref.get("type") == "gene" and xref.get("id", "").startswith("ENSG"):
                        ensembl_id = xref["id"]
                        break
        except Exception:
            pass

    if not ensembl_id:
        return {"error": f"Could not resolve Ensembl ID for gene '{gene}'. Check the gene symbol is correct.", "summary": f"Could not resolve Ensembl ID for gene '{gene}'. Check the gene symbol is correct."}
    # Fetch gene data from HPA JSON API
    url = f"https://www.proteinatlas.org/{ensembl_id}.json"
    resp, error = _clinical.request(
        "GET",
        url,
        timeout=30,
        retries=2,
        headers={"User-Agent": "ct-celltype/0.1"},
        raise_for_status=False,
    )
    if error:
        return {"error": f"Failed to fetch HPA data: {error}", "summary": f"Failed to fetch HPA data: {error}"}
    if resp.status_code != 200:
        return {"error": f"HPA API returned status {resp.status_code} for {gene}", "summary": f"HPA API error for {gene}"}
    content_type = ""
    try:
        ct_raw = resp.headers.get("content-type", "")
        if isinstance(ct_raw, str):
            content_type = ct_raw.lower()
    except Exception:
        pass
    if content_type and "json" not in content_type:
        return {"error": f"HPA API returned {content_type} instead of JSON for {gene}", "summary": f"HPA returned non-JSON for {gene}"}
    try:
        gene_json = resp.json()
    except Exception:
        return {"error": f"HPA API returned invalid JSON for {gene}", "summary": f"HPA invalid JSON for {gene}"}

    # Extract prognostic data
    prognostics = []
    for key, val in gene_json.items():
        if key.startswith("Cancer prognostics -") and val is not None:
            m = re.match(r"Cancer prognostics - (.+?) \((TCGA|validation)\)", key)
            if m and val.get("is_prognostic"):
                prognostics.append({
                    "cancer_type": m.group(1),
                    "dataset": m.group(2),
                    "direction": val.get("prognostic type", ""),
                    "status": val.get("prognostic", ""),
                    "p_value": val.get("p_val", ""),
                })

    gene_info = {
        "cancer_specificity": gene_json.get("RNA cancer specificity", ""),
        "cancer_distribution": gene_json.get("RNA cancer distribution", ""),
        "tissue_specificity": gene_json.get("RNA tissue specificity", ""),
    }

    # Extract RNA expression by cancer type
    rna_cancer = gene_json.get("RNA cancer sample", {})
    cancer_expression = []
    if isinstance(rna_cancer, dict):
        for cancer_type, data in rna_cancer.items():
            if isinstance(data, dict):
                fpkm = data.get("value", 0)
                cancer_expression.append({
                    "cancer_type": cancer_type,
                    "fpkm": float(fpkm) if fpkm else 0,
                    "expr_score": round(math.log2(float(fpkm) + 1), 3) if fpkm else 0,
                })

    cancer_expression.sort(key=lambda x: x["fpkm"], reverse=True)

    # Classify expression levels
    for entry in cancer_expression:
        fpkm = entry["fpkm"]
        if fpkm >= 10:
            entry["level"] = "HIGH"
        elif fpkm >= 3:
            entry["level"] = "MEDIUM"
        elif fpkm >= 1:
            entry["level"] = "LOW"
        else:
            entry["level"] = "VERY_LOW"

    high_expr = [e for e in cancer_expression if e["level"] in ("HIGH", "MEDIUM")]

    return {
        "summary": (
            f"TCGA stratification for {gene}:\n"
            f"Expressed (FPKM>=3) in {len(high_expr)}/{len(cancer_expression)} cancer types\n"
            f"Prognostic in {len(prognostics)} cancer types\n"
            f"Cancer specificity: {gene_info['cancer_specificity']}"
        ),
        "gene": gene,
        "gene_info": gene_info,
        "cancer_expression": cancer_expression,
        "prognostics": prognostics,
    }
