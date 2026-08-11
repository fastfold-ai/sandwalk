"""
expression.pathway_enrichment: L1000-based pathway activation/suppression scoring.

Split from tools/expression.py.
"""

import pandas as pd

from tools import registry


@registry.register(
    name="expression.pathway_enrichment",
    description="Score compounds for pathway activation/suppression using L1000 gene expression signatures",
    category="expression",
    parameters={
        "compound_id": "Compound ID to score (or 'all' for full library)",
        "pathways": "Pathway collection: hallmark, kegg, reactome, go_bp, or custom dict",
    },
    requires_data=["l1000"],
    usage_guide="You want to understand which biological pathways a compound activates or suppresses. Use for mechanism of action investigation and to identify pathway-level effects from transcriptomic data.",
)
def pathway_enrichment(compound_id: str = "all", pathways: str = "hallmark",
                       gene_sets: dict = None, **kwargs) -> dict:
    """Score compounds for pathway enrichment using mean z-score method."""
    from data.loaders import load_l1000
    from tools._compound_resolver import resolve_compound

    if compound_id != "all":
        compound_id = resolve_compound(compound_id, dataset="l1000")

    l1000 = load_l1000()

    # Z-score normalize per gene (replace zero std with NaN to avoid inf)
    std = l1000.std()
    std = std.replace(0, float("nan"))
    z = (l1000 - l1000.mean()) / std

    # Load or use provided gene sets
    if gene_sets is None:
        gene_sets = _get_default_gene_sets(pathways)

    results = []
    compounds = [compound_id] if compound_id != "all" else z.index.tolist()
    compounds_not_found = []
    low_coverage_pathways = 0

    for cpd in compounds:
        if cpd not in z.index:
            compounds_not_found.append(cpd)
            continue
        row = z.loc[cpd]

        for pathway_name, genes in gene_sets.items():
            available = [g for g in genes if g in row.index]
            if len(available) < 3:
                low_coverage_pathways += 1
                continue
            score = row[available].mean()
            results.append({
                "compound": cpd,
                "pathway": pathway_name,
                "score": round(float(score), 4),
                "n_genes": len(available),
                "coverage": round(len(available) / len(genes), 2),
            })

    df = pd.DataFrame(results)

    if compound_id != "all" and len(df) > 0:
        top_activated = df.nlargest(5, "score")
        top_suppressed = df.nsmallest(5, "score")
        summary = (
            f"Pathway enrichment for {compound_id}:\n"
            f"Top activated: {', '.join(top_activated['pathway'].tolist())}\n"
            f"Top suppressed: {', '.join(top_suppressed['pathway'].tolist())}"
        )
    else:
        summary = f"Scored {len(df)} compound-pathway pairs"

    result = {"summary": summary, "results": df.to_dict("records") if len(df) < 1000 else f"{len(df)} rows"}

    # Add diagnostics for empty results
    if len(df) == 0:
        diag_parts = []
        if compounds_not_found:
            diag_parts.append(
                f"Compound(s) not found in L1000 data: {', '.join(compounds_not_found)}. "
                "L1000 uses BRD IDs (e.g., BRD-K12345678) — try resolving via chemistry.pubchem_lookup first."
            )
        if low_coverage_pathways > 0:
            diag_parts.append(
                f"{low_coverage_pathways} pathways skipped due to <3 genes overlapping with L1000 landmark genes."
            )
        if not diag_parts:
            diag_parts.append("No compound-pathway pairs scored. Check compound ID format.")
        result["summary"] = "No pathway enrichment results. " + " ".join(diag_parts)
        result["compounds_not_found"] = compounds_not_found
        result["low_coverage_pathways"] = low_coverage_pathways

    return result


def _get_default_gene_sets(collection: str) -> dict:
    """Get default gene sets for pathway enrichment."""
    # Hallmark-lite: key pathways for drug discovery
    if collection == "hallmark":
        return {
            "androgen_response": ["KLK3", "KLK2", "FKBP5", "TMPRSS2", "NKX3-1", "PMEPA1"],
            "ifn_alpha": ["ISG15", "MX1", "MX2", "IFIT1", "IFIT2", "IFIT3", "OAS1", "OAS2"],
            "apoptosis": ["BCL2", "BAX", "BAK1", "BID", "CASP3", "CASP8", "CASP9", "CYCS"],
            "p53_pathway": ["CDKN1A", "MDM2", "BAX", "GADD45A", "SFN", "DDB2", "SESN1"],
            "mtorc1_signaling": ["SLC7A5", "SLC3A2", "DDIT4", "VEGFA", "HK2", "PKM", "LDHA"],
            "unfolded_protein_response": ["HSPA5", "DDIT3", "ATF4", "XBP1", "HERPUD1", "DNAJB9"],
            "nfkb_signaling": ["NFKB1", "NFKB2", "RELA", "NFKBIA", "BCL2", "TNFAIP3"],
            "oxidative_phosphorylation": ["NDUFA1", "SDHA", "UQCRC1", "COX5A", "ATP5F1A"],
            "glycolysis": ["HK2", "PFKM", "ALDOA", "GAPDH", "PKM", "LDHA", "ENO1"],
            "dna_repair": ["BRCA1", "BRCA2", "RAD51", "ATM", "ATR", "CHEK1", "CHEK2"],
        }

    # Return empty if collection not recognized
    return {}
