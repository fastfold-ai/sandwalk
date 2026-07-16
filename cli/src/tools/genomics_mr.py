"""genomics.mendelian_randomization_lookup: causal genetic evidence orchestrator. Split from tools/genomics.py."""
from tools import registry
from tools.genomics_mr_evidence import fetch_evidence
from tools.genomics_mr_format import format_result
from tools.genomics_mr_resolve import resolve_disease, resolve_gene


@registry.register(
    name="genomics.mendelian_randomization_lookup",
    description="Look up Mendelian randomization and genetic evidence for a gene-disease pair via Open Targets",
    category="genomics",
    parameters={
        "gene": "Gene symbol (e.g. 'PCSK9', 'IL6R')",
        "disease": "Disease name or EFO ID (e.g. 'coronary artery disease' or 'EFO_0001645')",
    },
    requires_data=[],
    usage_guide="You want causal genetic evidence linking a gene to a disease. Use to evaluate target-disease relationships using Mendelian randomization, GWAS colocalisation, and genetic association evidence from Open Targets.",
)
def mendelian_randomization_lookup(gene: str, disease: str, **kwargs) -> dict:
    """Look up MR and genetic evidence from Open Targets Platform GraphQL API."""
    try:
        import httpx  # noqa: F401
    except ImportError:
        return {"error": "httpx required (pip install httpx)", "summary": "httpx required (pip install httpx)"}

    ensembl_id, _target_name, error = resolve_gene(gene)
    if error:
        return error

    efo_id, disease_name, error = resolve_disease(disease)
    if error:
        return error

    data, error = fetch_evidence(ensembl_id, efo_id)
    if error:
        return error

    return format_result(data, gene, disease, ensembl_id, efo_id, disease_name)
