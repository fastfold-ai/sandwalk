"""
expression.immune_score / expression.deconvolution: immune pathway and cell
composition scoring from gene expression.

Split from tools/expression.py. Reads ``pathway_enrichment`` indirectly via the
``tools.expression`` hub module so that ``patch("tools.expression.pathway_enrichment")``
in tests continues to work regardless of which submodule performs the call.
"""

import numpy as np
import pandas as pd

from tools import expression as _expression
from tools import registry

# ---- Marker gene sets for immune cell deconvolution ----
IMMUNE_MARKERS = {
    "T cells": ["CD3D", "CD3E", "CD8A", "CD4"],
    "B cells": ["CD19", "MS4A1", "CD79A"],
    "NK cells": ["NKG7", "GNLY", "KLRD1"],
    "Monocytes": ["CD14", "LYZ", "FCGR3A"],
    "Macrophages": ["CD68", "CD163", "CSF1R"],
    "Dendritic cells": ["ITGAX", "CLEC4C", "CD1C"],
    "Neutrophils": ["FCGR3B", "CSF3R", "CXCR2"],
    "Tregs": ["FOXP3", "IL2RA", "CTLA4"],
}


@registry.register(
    name="expression.immune_score",
    description="Score compounds for immune pathway activation (IFN-gamma, antigen presentation, IO potential)",
    category="expression",
    parameters={"compound_id": "Compound ID (or 'all')"},
    requires_data=["l1000"],
    usage_guide="You want to assess a compound's immuno-oncology potential — IFN-gamma response, antigen presentation, immune checkpoint effects. Use when evaluating IO combination strategies or immunogenic cell death.",
)
def immune_score(compound_id: str = "all", **kwargs) -> dict:
    """Score compounds across 11 immune gene sets."""
    immune_sets = {
        "ifn_gamma": ["STAT1", "IRF1", "GBP1", "GBP2", "CXCL10", "CXCL9", "IDO1", "TAP1",
                      "PSMB9", "PSMB8", "B2M", "HLA-A", "HLA-B", "HLA-C", "HLA-E"],
        "antigen_presentation": ["TAP1", "TAP2", "TAPBP", "B2M", "HLA-A", "HLA-B", "HLA-C",
                                  "HLA-DRA", "HLA-DRB1", "PSMB8", "PSMB9", "CALR", "CANX"],
        "nfkb": ["NFKB1", "NFKB2", "RELA", "RELB", "REL", "NFKBIA", "NFKBIB", "TNFAIP3",
                 "BCL2", "BCL2L1", "XIAP", "BIRC3", "CFLAR", "TRAF1", "TRAF2"],
        "t_cell_cytotoxicity": ["GZMA", "GZMB", "GZMK", "PRF1", "IFNG", "TNF", "FASLG",
                                 "CD8A", "CD8B"],
        "immune_checkpoints": ["CD274", "PDCD1LG2", "CTLA4", "HAVCR2", "LAG3", "TIGIT",
                                "CD47", "SIRPA", "CD80", "CD86"],
        "icd": ["CALR", "HMGB1", "ATP", "ANXA1", "HSP90AA1", "HSPA1A", "HSPA1B"],
    }

    result = _expression.pathway_enrichment(compound_id=compound_id, gene_sets=immune_sets)

    # Compute composite IO score
    if isinstance(result["results"], list):
        df = pd.DataFrame(result["results"])
        if len(df) > 0 and compound_id != "all":
            io_pathways = ["ifn_gamma", "antigen_presentation", "icd"]
            io_scores = df[df["pathway"].isin(io_pathways)]["score"]
            io_potential = io_scores.mean() if len(io_scores) > 0 else 0

            hot_pathways = ["ifn_gamma", "t_cell_cytotoxicity"]
            hot_scores = df[df["pathway"].isin(hot_pathways)]["score"]
            hot_tumor = hot_scores.mean() if len(hot_scores) > 0 else 0

            result["io_potential"] = round(float(io_potential), 4)
            result["hot_tumor_signature"] = round(float(hot_tumor), 4)
            result["immune_classification"] = (
                "immune_hot" if io_potential > 0.3 else
                "immune_cold" if io_potential < -0.3 else
                "neutral"
            )
            result["summary"] += (
                f"\nIO potential: {io_potential:.3f} ({result['immune_classification']})"
                f"\nHot tumor signature: {hot_tumor:.3f}"
            )

    return result


@registry.register(
    name="expression.deconvolution",
    description="Estimate immune cell type composition from bulk gene expression using marker gene-based deconvolution",
    category="expression",
    parameters={
        "gene_expression": "Dict of gene:value pairs (expression levels), OR omit and provide compound_id",
        "compound_id": "Compound ID to pull L1000 signature for (optional, used if gene_expression not provided)",
    },
    requires_data=[],
    usage_guide="You want to estimate the immune cell type composition implied by a gene expression profile. "
                "Useful for understanding immune microenvironment effects of compounds or patient samples. "
                "Provide a gene expression dict directly, or a compound_id to pull from L1000 data.",
)
def deconvolution(gene_expression: dict = None, compound_id: str = None, **kwargs) -> dict:
    """Estimate immune cell type proportions from bulk gene expression using marker genes.

    Uses a simple marker gene averaging approach: for each immune cell type, compute
    the mean expression of its marker genes, then normalize to proportions. This is
    a lightweight alternative to CIBERSORT that requires no license.
    """
    if gene_expression is None and compound_id is None:
        return {"error": "Provide either gene_expression (dict) or compound_id", "summary": "Provide either gene_expression (dict) or compound_id"}
    # If compound_id provided, pull expression from L1000
    if gene_expression is None:
        from data.loaders import load_l1000
        from tools._compound_resolver import resolve_compound
        compound_id = resolve_compound(compound_id, dataset="l1000")
        l1000 = load_l1000()
        if compound_id not in l1000.index:
            return {"error": f"Compound {compound_id} not found in L1000 data", "summary": f"Compound {compound_id} not found in L1000 data"}
        row = l1000.loc[compound_id]
        gene_expression = row.to_dict()

    # Score each cell type by mean expression of its markers
    cell_scores = {}
    marker_details = {}
    for cell_type, markers in IMMUNE_MARKERS.items():
        available = [g for g in markers if g in gene_expression]
        if not available:
            cell_scores[cell_type] = 0.0
            marker_details[cell_type] = {"n_markers": 0, "found": [], "mean_expr": 0.0}
            continue
        values = [gene_expression[g] for g in available]
        mean_val = float(np.mean(values))
        cell_scores[cell_type] = max(mean_val, 0.0)  # clamp negatives to 0
        marker_details[cell_type] = {
            "n_markers": len(available),
            "found": available,
            "mean_expr": round(mean_val, 4),
        }

    # Normalize to proportions
    total = sum(cell_scores.values())
    if total > 0:
        proportions = {ct: round(v / total, 4) for ct, v in cell_scores.items()}
    else:
        proportions = {ct: round(1.0 / len(cell_scores), 4) for ct in cell_scores}

    # Sort by proportion (descending)
    sorted_props = dict(sorted(proportions.items(), key=lambda x: x[1], reverse=True))
    dominant = next(iter(sorted_props))
    dominant_pct = sorted_props[dominant]

    # Compute aggregate immune score (sum of raw marker means, higher = more immune)
    immune_score_total = round(sum(max(v, 0) for v in cell_scores.values()), 4)

    # Format proportions for summary
    top3 = list(sorted_props.items())[:3]
    top3_str = ", ".join(f"{ct} {pct:.1%}" for ct, pct in top3)

    source = f"compound {compound_id}" if compound_id else "provided expression"
    summary = (
        f"Immune deconvolution ({source}):\n"
        f"Dominant: {dominant} ({dominant_pct:.1%})\n"
        f"Top 3: {top3_str}\n"
        f"Immune score: {immune_score_total:.2f}"
    )

    return {
        "summary": summary,
        "proportions": sorted_props,
        "dominant_cell_type": dominant,
        "immune_score": immune_score_total,
        "marker_details": marker_details,
    }
