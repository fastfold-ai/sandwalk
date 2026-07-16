"""Biomarker tools: mutation-sensitivity association testing."""

import pandas as pd
from scipy import stats

from tools import registry


@registry.register(
    name="biomarker.mutation_sensitivity",
    description="Test whether specific mutations sensitize or confer resistance to a compound",
    category="biomarker",
    parameters={"compound_id": "Compound YU ID", "gene": "Gene to test (or 'all' for genome-wide)"},
    requires_data=["prism", "depmap_mutations", "depmap_model"],
    usage_guide="You want to find predictive biomarkers — which mutations make cells more or less sensitive to a compound. Use for patient stratification and clinical trial design.",
)
def mutation_sensitivity(compound_id: str, gene: str = "all", **kwargs) -> dict:
    """Test mutation-sensitivity associations."""
    from data.loaders import load_model_metadata, load_mutations, load_prism
    from tools._compound_resolver import resolve_compound

    compound_id = resolve_compound(compound_id, dataset="prism")

    prism = load_prism()
    mutations = load_mutations()
    model = load_model_metadata()

    # Map PRISM cell lines to DepMap ModelIDs
    ccle_to_model = {}
    for _, row in model.iterrows():
        ccle = row.get("CCLEName", "")
        mid = row.get("ModelID", "")
        if pd.notna(ccle) and pd.notna(mid):
            ccle_to_model[ccle] = mid

    # Get compound sensitivity at highest dose
    cpd = prism[prism["pert_name"] == compound_id]
    if len(cpd) == 0:
        return {"error": f"Compound {compound_id} not in PRISM", "summary": f"Compound {compound_id} not found in PRISM data"}

    max_dose = cpd["pert_dose"].max()
    cpd_hd = cpd[cpd["pert_dose"] == max_dose].groupby("ccle_name")["LFC"].mean()

    # Map to ModelIDs
    sensitivity = {}
    for ccle, lfc in cpd_hd.items():
        mid = ccle_to_model.get(ccle)
        if mid and mid in mutations.index:
            sensitivity[mid] = lfc

    if len(sensitivity) < 20:
        return {"error": f"Insufficient overlap: only {len(sensitivity)} cell lines mapped", "summary": f"Insufficient cell line overlap ({len(sensitivity)} < 20 required)"}

    # Test genes
    genes_to_test = [gene] if gene != "all" else [g for g in mutations.columns if mutations[g].sum() >= 3]
    model_ids = list(sensitivity.keys())
    lfc_values = pd.Series(sensitivity)

    results = []
    for g in genes_to_test:
        if g not in mutations.columns:
            continue

        mut_status = mutations.loc[model_ids, g].reindex(model_ids).fillna(0)
        mutant_ids = [m for m in model_ids if mut_status.loc[m] > 0]
        wt_ids = [m for m in model_ids if mut_status.loc[m] == 0]

        if len(mutant_ids) < 3 or len(wt_ids) < 3:
            continue

        mut_lfc = lfc_values[mutant_ids]
        wt_lfc = lfc_values[wt_ids]
        stat, pval = stats.mannwhitneyu(mut_lfc, wt_lfc, alternative="two-sided")

        results.append({
            "gene": g,
            "mut_mean_lfc": round(float(mut_lfc.mean()), 3),
            "wt_mean_lfc": round(float(wt_lfc.mean()), 3),
            "delta": round(float(mut_lfc.mean() - wt_lfc.mean()), 3),
            "direction": "sensitizing" if mut_lfc.mean() < wt_lfc.mean() else "resistance",
            "pval": float(pval),
            "n_mutant": len(mutant_ids),
            "n_wt": len(wt_ids),
        })

    if not results:
        return {
            "summary": (
                f"Mutation sensitivity for {compound_id}: {len(genes_to_test)} genes tested, "
                f"0 significant (p<0.05). No genes met minimum sample size (3 mutant, 3 WT)."
            ),
            "compound": compound_id,
            "significant_mutations": [],
            "n_tested": 0,
        }

    df = pd.DataFrame(results).sort_values("pval")
    if len(df) > 0:
        # Benjamini-Hochberg FDR: p * m / rank (monotonicity enforced)
        ranks = df["pval"].rank(method="first")
        df["fdr"] = (df["pval"] * len(df) / ranks).clip(upper=1.0)
        # Enforce monotonicity: walk backwards to ensure FDR is non-decreasing with p-value
        fdr_arr = df["fdr"].values.copy()
        for i in range(len(fdr_arr) - 2, -1, -1):
            fdr_arr[i] = min(fdr_arr[i], fdr_arr[i + 1])
        df["fdr"] = fdr_arr

    sig = df[df["pval"] < 0.05]

    return {
        "summary": (
            f"Mutation sensitivity for {compound_id}: {len(genes_to_test)} genes tested, "
            f"{len(sig)} significant (p<0.05)"
        ),
        "compound": compound_id,
        "significant_mutations": sig.head(20).to_dict("records") if len(sig) > 0 else [],
        "n_tested": len(results),
    }
