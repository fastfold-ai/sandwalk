"""viability — part 2 of split module. See tools/viability.py."""
from tools.viability_base import pd, registry
from tools.viability_part1 import dose_response

@registry.register(
    name="viability.tissue_selectivity",
    description="Identify which tissue/cancer types are most sensitive to a compound",
    category="viability",
    parameters={"compound_id": "Compound YU ID", "dose": "Dose in uM (default: highest)", "lfc_threshold": "LFC threshold for sensitivity (default: -0.5)"},
    requires_data=["prism", "depmap_model"],
    usage_guide="You want to know which cancer types respond best to a compound. Use for indication selection and to assess whether killing is selective or broadly toxic.",
)
def tissue_selectivity(compound_id: str, dose: float = None, lfc_threshold: float = -0.5, **kwargs) -> dict:
    """Profile tissue-level sensitivity for a compound."""
    from data.loaders import load_model_metadata, load_prism
    from tools._compound_resolver import resolve_compound

    original_name = compound_id
    compound_id = resolve_compound(compound_id, dataset="prism")
    proxy_warning = ""
    if original_name != compound_id:
        proxy_warning = (
            f" Note: '{original_name}' resolved to proxy compound "
            f"{compound_id}. Results are for the proxy, not {original_name}."
        )

    prism = load_prism()
    model = load_model_metadata()

    cpd_data = prism[prism["pert_name"] == compound_id]
    if len(cpd_data) == 0:
        return {"error": f"Compound {compound_id} not found in PRISM data", "summary": f"Compound {compound_id} not found in PRISM data"}
    if dose is None:
        dose = cpd_data["pert_dose"].max()
    cpd_dose = cpd_data[cpd_data["pert_dose"] == dose]

    # Map cell lines to lineages
    ccle_to_lineage = {}
    for _, row in model.iterrows():
        ccle = row.get("CCLEName", "")
        lineage = row.get("OncotreeLineage", "Unknown")
        if pd.notna(ccle) and pd.notna(lineage):
            ccle_to_lineage[ccle] = lineage

    cpd_dose = cpd_dose.copy()
    cpd_dose["lineage"] = cpd_dose["ccle_name"].map(ccle_to_lineage)

    # Per-lineage statistics
    tissue_stats = []
    for lineage, group in cpd_dose.groupby("lineage"):
        if lineage == "Unknown" or len(group) < 3:
            continue
        tissue_stats.append({
            "lineage": lineage,
            "mean_lfc": round(float(group["LFC"].mean()), 3),
            "median_lfc": round(float(group["LFC"].median()), 3),
            "pct_sensitive": round(float((group["LFC"] < lfc_threshold).mean() * 100), 1),
            "n_cells": len(group),
        })

    if not tissue_stats:
        return {
            "summary": f"No tissue selectivity data for {compound_id} at {dose}uM (no lineages with >=3 cell lines)",
            "compound": compound_id,
            "dose_um": dose,
            "tissue_profiles": [],
        }

    tissue_df = pd.DataFrame(tissue_stats).sort_values("mean_lfc")

    sensitive = tissue_df[tissue_df["pct_sensitive"] > 50]
    resistant = tissue_df[tissue_df["pct_sensitive"] < 20]

    result = {
        "summary": (
            f"Tissue selectivity for {compound_id} at {dose}uM:\n"
            f"Most sensitive: {', '.join(sensitive['lineage'].head(3).tolist()) if len(sensitive) > 0 else 'none'}\n"
            f"Most resistant: {', '.join(resistant['lineage'].tail(3).tolist()) if len(resistant) > 0 else 'none'}"
            + proxy_warning
        ),
        "compound": compound_id,
        "dose_um": dose,
        "tissue_profiles": tissue_df.to_dict("records"),
    }
    if original_name != compound_id:
        result["original_query"] = original_name
        result["is_proxy"] = True
    return result
@registry.register(
    name="viability.compare_compounds",
    description="Compare potency and selectivity profiles of multiple compounds",
    category="viability",
    parameters={"compound_ids": "List of compound IDs to compare"},
    requires_data=["prism"],
    usage_guide="You have multiple compounds and want to rank them by potency and selectivity. Use for lead selection when choosing between compound candidates.",
)
def compare_compounds(compound_ids: list, **kwargs) -> dict:
    """Compare multiple compounds on potency and selectivity metrics."""
    results = []
    for cpd_id in compound_ids:
        dr = dose_response(cpd_id)
        if "error" in dr:
            continue
        results.append({
            "compound": cpd_id,
            "ic50_um": dr.get("ic50_um"),
            "n_sensitive": dr.get("n_sensitive"),
            "n_resistant": dr.get("n_resistant"),
            "n_cell_lines": dr.get("n_cell_lines"),
            "sensitivity_rate": round(dr["n_sensitive"] / dr["n_cell_lines"] * 100, 1) if dr["n_cell_lines"] else 0,
        })

    if not results:
        return {
            "summary": f"No compounds found in PRISM data from: {', '.join(compound_ids)}",
            "comparison": [],
        }

    df = pd.DataFrame(results).sort_values("ic50_um", na_position="last")

    return {
        "summary": f"Compared {len(results)} compounds. Most potent: {df.iloc[0]['compound'] if len(df) > 0 else 'N/A'}",
        "comparison": df.to_dict("records"),
    }
