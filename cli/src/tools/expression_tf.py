"""
expression.tf_activity: transcription factor activity inference from regulons.

Split from tools/expression.py.
"""

import numpy as np

from tools import registry

# ---- Curated TF regulons (TF -> target genes) ----
TF_REGULONS = {
    "TP53": ["CDKN1A", "MDM2", "BAX", "BBC3", "PUMA"],
    "MYC": ["ODC1", "LDHA", "CDK4", "NCL"],
    "NFkB": ["NFKBIA", "TNF", "IL6", "CXCL8"],
    "HIF1A": ["VEGFA", "SLC2A1", "LDHA", "PDK1"],
    "STAT3": ["BCL2L1", "MMP9", "VEGFA", "MYC"],
    "E2F": ["CCNE1", "MCM2", "PCNA", "RRM2"],
    "AP1": ["FOS", "JUN", "MMP1", "IL8"],
}


@registry.register(
    name="expression.tf_activity",
    description="Infer transcription factor activity from gene expression signatures using curated regulons",
    category="expression",
    parameters={
        "gene_expression": "Dict of gene:value pairs (expression changes), OR omit and provide compound_id",
        "compound_id": "Compound ID to pull L1000 signature for (optional)",
    },
    requires_data=[],
    usage_guide="You want to infer which transcription factors are activated or suppressed by a compound or "
                "in a condition. Uses curated regulons (TF -> target gene sets) to score TF activity from "
                "expression data. Provide a gene expression dict or compound_id for L1000 lookup.",
)
def tf_activity(gene_expression: dict = None, compound_id: str = None, **kwargs) -> dict:
    """Infer transcription factor activity from expression signatures.

    For each TF, scores activity as the mean expression change of its known target
    genes (regulon). Positive score = TF activated, negative = TF suppressed.
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

    # Score each TF by mean expression of its targets
    tf_scores = {}
    tf_details = {}
    for tf_name, targets in TF_REGULONS.items():
        available = [g for g in targets if g in gene_expression]
        if not available:
            tf_details[tf_name] = {"n_targets": 0, "found": [], "score": None}
            continue
        values = [gene_expression[g] for g in available]
        score = float(np.mean(values))
        tf_scores[tf_name] = score
        tf_details[tf_name] = {
            "n_targets": len(available),
            "found": available,
            "score": round(score, 4),
            "target_values": {g: round(gene_expression[g], 4) for g in available},
        }

    if not tf_scores:
        return {
            "summary": "No TF regulon targets found in expression data",
            "tf_scores": {},
            "activated": [],
            "suppressed": [],
        }

    # Rank by absolute activity
    sorted_tfs = sorted(tf_scores.items(), key=lambda x: abs(x[1]), reverse=True)

    # Classify as activated (> threshold) or suppressed (< threshold)
    activation_threshold = 0.3
    activated = [(tf, round(s, 4)) for tf, s in sorted_tfs if s > activation_threshold]
    suppressed = [(tf, round(s, 4)) for tf, s in sorted_tfs if s < -activation_threshold]
    neutral = [(tf, round(s, 4)) for tf, s in sorted_tfs
               if -activation_threshold <= s <= activation_threshold]

    # Build summary
    source = f"compound {compound_id}" if compound_id else "provided expression"
    act_str = ", ".join(f"{tf}(+{s:.2f})" for tf, s in activated) if activated else "none"
    sup_str = ", ".join(f"{tf}({s:.2f})" for tf, s in suppressed) if suppressed else "none"

    summary = (
        f"TF activity analysis ({source}):\n"
        f"Activated: {act_str}\n"
        f"Suppressed: {sup_str}\n"
        f"TFs scored: {len(tf_scores)}/{len(TF_REGULONS)}"
    )

    return {
        "summary": summary,
        "tf_scores": dict(sorted_tfs),
        "activated": [{"tf": tf, "score": s} for tf, s in activated],
        "suppressed": [{"tf": tf, "score": s} for tf, s in suppressed],
        "neutral": [{"tf": tf, "score": s} for tf, s in neutral],
        "details": tf_details,
    }
