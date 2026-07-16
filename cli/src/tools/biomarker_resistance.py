"""Biomarker tools: resistance mechanism profiling."""

import pandas as pd

from tools import registry


@registry.register(
    name="biomarker.resistance_profile",
    description="Profile resistance mechanisms for a compound (lineage, mutation, dependency enrichment)",
    category="biomarker",
    parameters={"compound_id": "Compound YU ID"},
    requires_data=["prism", "depmap_crispr", "depmap_mutations", "depmap_model"],
    usage_guide="You want to understand why some cell lines resist a compound — lineage effects, specific mutations, or dependency patterns. Use to anticipate clinical resistance mechanisms.",
)
def resistance_profile(compound_id: str, **kwargs) -> dict:
    """Comprehensive resistance profiling for a compound."""
    from data.loaders import load_model_metadata, load_prism
    from tools._compound_resolver import resolve_compound

    compound_id = resolve_compound(compound_id, dataset="prism")

    prism = load_prism()
    model = load_model_metadata()

    cpd = prism[prism["pert_name"] == compound_id]
    if len(cpd) == 0:
        return {"error": f"Compound {compound_id} not in PRISM", "summary": f"Compound {compound_id} not found in PRISM data"}

    max_dose = cpd["pert_dose"].max()
    cpd_hd = cpd[cpd["pert_dose"] == max_dose].groupby("ccle_name")["LFC"].mean()

    n_sensitive = (cpd_hd < -0.5).sum()
    n_resistant = (cpd_hd > -0.1).sum()
    n_intermediate = len(cpd_hd) - n_sensitive - n_resistant

    # Lineage enrichment
    ccle_to_lineage = {}
    for _, row in model.iterrows():
        ccle = row.get("CCLEName", "")
        lin = row.get("OncotreeLineage", "Unknown")
        if pd.notna(ccle) and pd.notna(lin):
            ccle_to_lineage[ccle] = lin

    sens_lineages = [ccle_to_lineage.get(c, "Unknown") for c in cpd_hd[cpd_hd < -0.5].index]
    res_lineages = [ccle_to_lineage.get(c, "Unknown") for c in cpd_hd[cpd_hd > -0.1].index]

    lineage_counts = {}
    for lin in set(sens_lineages + res_lineages):
        if lin == "Unknown":
            continue
        s = sens_lineages.count(lin)
        r = res_lineages.count(lin)
        if s + r >= 3:
            lineage_counts[lin] = {"sensitive": s, "resistant": r, "total": s + r}

    return {
        "summary": (
            f"Resistance profile for {compound_id}:\n"
            f"  Sensitive: {n_sensitive}, Intermediate: {n_intermediate}, Resistant: {n_resistant}\n"
            f"  {len(lineage_counts)} lineages profiled"
        ),
        "compound": compound_id,
        "n_sensitive": int(n_sensitive),
        "n_resistant": int(n_resistant),
        "n_intermediate": int(n_intermediate),
        "lineage_profiles": lineage_counts,
    }
