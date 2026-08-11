"""viability — part 1 of split module. See tools/viability.py."""
from tools.viability_base import registry


@registry.register(
    name="viability.dose_response",
    description="Analyze dose-response curves for a compound across PRISM cell lines",
    category="viability",
    parameters={"compound_id": "Compound YU ID", "lfc_threshold": "LFC threshold for sensitivity (default: -0.5)"},
    requires_data=["prism"],
    usage_guide="You want to understand a compound's potency across cell lines — IC50 estimates, sensitivity vs resistance distribution. Use early in hit characterization.",
)
def dose_response(compound_id: str, lfc_threshold: float = -0.5, **kwargs) -> dict:
    """Analyze PRISM dose-response for a compound."""
    from data.loaders import load_prism
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
    cpd_data = prism[prism["pert_name"] == compound_id]

    if len(cpd_data) == 0:
        return {"error": f"Compound {compound_id} not found in PRISM data", "summary": f"Compound {compound_id} not found in PRISM data"}
    doses = sorted(cpd_data["pert_dose"].unique())
    n_cells = cpd_data["ccle_name"].nunique()

    # Per-dose statistics
    dose_stats = []
    for dose in doses:
        dose_data = cpd_data[cpd_data["pert_dose"] == dose]["LFC"]
        dose_stats.append({
            "dose_um": dose,
            "mean_lfc": round(float(dose_data.mean()), 3),
            "median_lfc": round(float(dose_data.median()), 3),
            "pct_killing": round(float((dose_data < lfc_threshold).mean() * 100), 1),
            "n_cells": len(dose_data),
        })

    # Classify cell lines
    high_dose = cpd_data[cpd_data["pert_dose"] == max(doses)]
    per_cell = high_dose.groupby("ccle_name")["LFC"].mean()
    n_sensitive = (per_cell < lfc_threshold).sum()
    n_resistant = (per_cell > -0.1).sum()

    # Estimate IC50 from 3-point dose-response
    mean_lfcs = [s["mean_lfc"] for s in dose_stats]
    if len(doses) >= 3 and mean_lfcs[-1] < lfc_threshold:
        # Linear interpolation to find dose at LFC = threshold
        for i in range(len(doses) - 1):
            if mean_lfcs[i] > lfc_threshold >= mean_lfcs[i + 1]:
                denom = mean_lfcs[i + 1] - mean_lfcs[i]
                if abs(denom) < 1e-12:
                    ic50 = (doses[i] + doses[i + 1]) / 2  # midpoint if flat
                else:
                    frac = (lfc_threshold - mean_lfcs[i]) / denom
                    ic50 = doses[i] + frac * (doses[i + 1] - doses[i])
                break
        else:
            ic50 = None
    else:
        ic50 = None

    result = {
        "summary": (
            f"Dose-response for {compound_id}: {n_cells} cell lines, {len(doses)} doses\n"
            f"Sensitive (LFC<{lfc_threshold} at {max(doses)}uM): {n_sensitive}/{len(per_cell)} "
            f"({n_sensitive/len(per_cell)*100:.0f}%)\n"
            f"Estimated IC50: {f'{ic50:.2f} uM' if ic50 else 'N/A'}"
            + proxy_warning
        ),
        "compound": compound_id,
        "dose_stats": dose_stats,
        "n_cell_lines": n_cells,
        "n_sensitive": int(n_sensitive),
        "n_resistant": int(n_resistant),
        "ic50_um": round(ic50, 3) if ic50 else None,
    }
    if original_name != compound_id:
        result["original_query"] = original_name
        result["is_proxy"] = True
    return result
