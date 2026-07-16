"""genomics.coloc: GWAS-eQTL/pQTL colocalization lookup orchestrator. Split from tools/genomics.py."""
from tools import registry
from tools.genomics_coloc_resolve import gene_symbol_candidates, resolve_ensembl_id
from tools.genomics_coloc_run import query_target_coloc
from tools.genomics_coloc_summary import build_result


@registry.register(
    name="genomics.coloc",
    description="Look up GWAS-eQTL/pQTL colocalization evidence for a gene via Open Targets Platform",
    category="genomics",
    parameters={
        "gene": "Gene symbol (e.g. 'PCSK9', 'IL6R')",
        "study_id": "Specific GWAS study ID to filter (optional)",
    },
    requires_data=[],
    usage_guide="You want to assess whether a GWAS signal and an eQTL/pQTL signal share the same "
                "causal variant at a locus — the gold standard for connecting genetic associations "
                "to gene function. High H4 posterior probability (>0.8) indicates strong colocalization. "
                "Use for target validation and causal gene assignment at GWAS loci.",
)
def coloc(gene: str, study_id: str = None, **kwargs) -> dict:
    """Look up colocalization evidence from Open Targets Platform GraphQL API.

    Queries the Open Targets credibleSets and colocalisations data for a gene
    target, returning GWAS-QTL colocalization information including H4 posterior
    probabilities (evidence of shared causal variant), study details, and tissues.
    """
    try:
        import httpx  # noqa: F401
    except ImportError:
        return {"error": "httpx required (pip install httpx)", "summary": "httpx required (pip install httpx)"}

    # Try primary symbol first, then common aliases (e.g., GBA1 -> GBA) if needed.
    gene_candidates = gene_symbol_candidates(gene)
    ensembl_id = None
    target_data = None
    candidate_errors = []
    query_failures = []
    resolved_candidates = []

    for gene_candidate in gene_candidates:
        ensembl_candidate, resolve_error = resolve_ensembl_id(gene_candidate)
        if resolve_error:
            candidate_errors.append(resolve_error)
            continue
        resolved_candidates.append((gene_candidate, ensembl_candidate))

        payload, query_error = query_target_coloc(ensembl_candidate)
        if query_error:
            candidate_errors.append(f"{gene_candidate}: {query_error}")
            query_failures.append((gene_candidate, ensembl_candidate, query_error))
            continue

        target_candidate = (payload or {}).get("data", {}).get("target")
        if not target_candidate:
            candidate_errors.append(f"{gene_candidate}: Open Targets has no entry for {ensembl_candidate}")
            query_failures.append((gene_candidate, ensembl_candidate, f"Open Targets has no entry for {ensembl_candidate}"))
            continue

        ensembl_id = ensembl_candidate
        target_data = target_candidate
        break

    if not target_data:
        last_error = candidate_errors[-1] if candidate_errors else "Open Targets colocalization query failed"
        if candidate_errors and all("not found in Ensembl" in e for e in candidate_errors):
            return {"error": last_error, "summary": f"Gene symbol {gene} could not be resolved to an Ensembl ID"}
        # Resolved gene(s) but Open Targets could not return colocalization payload.
        # Return a non-fatal unavailable result so workflows can continue.
        if resolved_candidates:
            chosen_symbol, chosen_ensembl = resolved_candidates[0]
            warning = query_failures[0][2] if query_failures else last_error
            return {
                "summary": (
                    f"Colocalization for {chosen_symbol}: unavailable from Open Targets "
                    f"(query failed). Try genomics.eqtl_lookup for orthogonal evidence."
                ),
                "gene": chosen_symbol,
                "ensembl_id": chosen_ensembl,
                "total_gwas_loci": 0,
                "n_colocalizations": 0,
                "n_strong_coloc": 0,
                "n_moderate_coloc": 0,
                "n_tissues": 0,
                "n_studies": 0,
                "tissues": [],
                "colocalizations": [],
                "data_unavailable": True,
                "warning": warning,
            }
        if "GraphQL errors" in last_error:
            return {"error": last_error, "summary": f"GraphQL query errors for {gene} colocalization"}
        return {"error": last_error, "summary": f"Open Targets colocalization query failed for {gene}"}

    return build_result(target_data, gene, study_id, ensembl_id)
