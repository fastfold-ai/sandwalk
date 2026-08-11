"""Combination therapy tool: metabolic vulnerability triangle (L1000 x CRISPR x PRISM)."""

import numpy as np
import pandas as pd

from tools import registry
from tools.combination_metabolic_data import METABOLIC_INHIBITORS, METABOLIC_PATHWAYS


def _score_l1000_pathways(l1000, pathways_to_test: dict) -> pd.DataFrame:
    """Z-score each pathway's gene set against L1000 to get per-compound pathway activity."""
    l1000_genes = set(l1000.columns)
    pathway_scores = {}
    for pw_name, genes in pathways_to_test.items():
        found = [g for g in genes if g in l1000_genes]
        if len(found) < 2:
            continue
        sub = l1000[found]
        zscored = (sub - sub.mean()) / sub.std()
        pathway_scores[pw_name] = zscored.mean(axis=1)
    return pd.DataFrame(pathway_scores)


def _crispr_dependency_masks(crispr, pathways_to_test: dict) -> dict:
    """Per-pathway boolean mask of cell lines dependent on that pathway (any gene CERES < -0.5)."""
    crispr_genes = set(crispr.columns)
    dep_binary = {}
    for pw_name, genes in pathways_to_test.items():
        found = [g for g in genes if g in crispr_genes]
        if found:
            dep_binary[pw_name] = (crispr[found].min(axis=1) < -0.5)
    return dep_binary


def _map_prism_to_models(prism, model) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pivot PRISM to wide compound-by-cell-line and attach DepMap ModelIDs."""
    ccle_to_model_id = {}
    for _, row in model.iterrows():
        ccle = row.get("CCLEName", "")
        mid = row.get("ModelID", "")
        if pd.notna(ccle) and pd.notna(mid):
            ccle_to_model_id[ccle] = mid

    prism_hd = prism[prism["pert_dose"] == prism["pert_dose"].max()]
    prism_wide = prism_hd.pivot_table(index="ccle_name", columns="pert_name", values="LFC", aggfunc="mean")
    prism_wide["ModelID"] = prism_wide.index.map(ccle_to_model_id)
    prism_mapped = prism_wide.dropna(subset=["ModelID"])
    return prism_wide, prism_mapped


@registry.register(
    name="combination.metabolic_vulnerability",
    description="Map metabolic vulnerabilities: compounds that suppress metabolic pathways where dependent cells are more sensitive",
    category="combination",
    parameters={
        "compound_id": "Compound to profile (or 'all')",
        "pathway": "Specific metabolic pathway (or 'all')",
    },
    requires_data=["l1000", "depmap_crispr", "prism", "depmap_model"],
    usage_guide="You want to exploit metabolic dependencies — find pathways a compound suppresses where dependent cells are more sensitive. Use to identify metabolic inhibitor combinations (e.g., add metformin to exploit OxPhos dependency).",
)
def metabolic_vulnerability(compound_id: str = "all", pathway: str = "all", **kwargs) -> dict:
    """Identify exploitable metabolic vulnerabilities (the vulnerability triangle).

    Triangle: compound suppresses pathway (L1000) + pathway-dependent cells more
    sensitive (PRISM) = exploitable vulnerability.
    """
    from scipy import stats

    from data.loaders import load_crispr, load_l1000, load_model_metadata, load_prism
    from tools._compound_resolver import resolve_compound

    if compound_id != "all":
        compound_id = resolve_compound(compound_id, dataset="l1000")

    l1000 = load_l1000()
    crispr = load_crispr()
    prism = load_prism()
    model = load_model_metadata()

    pathways_to_test = {pathway: METABOLIC_PATHWAYS[pathway]} if pathway != "all" else METABOLIC_PATHWAYS
    pw_score_df = _score_l1000_pathways(l1000, pathways_to_test)
    if pw_score_df.empty:
        return {"error": "No metabolic pathways have sufficient gene coverage in L1000", "summary": "No metabolic pathways have sufficient gene coverage in L1000"}

    dep_binary = _crispr_dependency_masks(crispr, pathways_to_test)
    prism_wide, prism_mapped = _map_prism_to_models(prism, model)

    overlap = set(crispr.index) & set(prism_mapped["ModelID"])
    if len(overlap) < 20:
        return {"error": f"Insufficient overlap: only {len(overlap)} cell lines in both PRISM and DepMap", "summary": f"Insufficient overlap: only {len(overlap)} cell lines in both PRISM and DepMap"}
    overlap_list = sorted(overlap)
    compounds_to_test = [compound_id] if compound_id != "all" else [
        c for c in pw_score_df.index if c in prism_wide.columns
    ]

    vulnerabilities = []
    prism_by_model = prism_mapped.set_index("ModelID")
    for pw_name in dep_binary:
        if pw_name not in pw_score_df.columns:
            continue
        dep_mask = dep_binary[pw_name].reindex(overlap_list).fillna(False)
        n_dep = dep_mask.sum()
        n_indep = (~dep_mask).sum()
        if n_dep < 5 or n_indep < 5:
            continue

        for cpd in compounds_to_test:
            if cpd not in pw_score_df.index or cpd not in prism_wide.columns or cpd not in prism_by_model.columns:
                continue

            l1000_z = pw_score_df.loc[cpd, pw_name]
            if abs(l1000_z) < 1.0:
                continue

            lfc_vals = prism_by_model.loc[overlap_list, cpd].values
            valid = ~np.isnan(lfc_vals)

            dep_lfc = lfc_vals[valid & dep_mask.values[:len(valid)]]
            indep_lfc = lfc_vals[valid & ~dep_mask.values[:len(valid)]]

            if len(dep_lfc) < 5 or len(indep_lfc) < 5:
                continue

            t_stat, p_val = stats.ttest_ind(dep_lfc, indep_lfc, equal_var=False)
            delta_lfc = float(np.mean(dep_lfc) - np.mean(indep_lfc))

            # Classify
            if l1000_z < -1.0 and delta_lfc < 0:
                vuln_type = "EXPLOIT"
            elif l1000_z > 1.0 and delta_lfc < 0:
                vuln_type = "ACTIVATION_SENSITIZES"
            elif l1000_z < -1.0 and delta_lfc > 0:
                vuln_type = "PARADOXICAL_RESISTANCE"
            else:
                vuln_type = "WEAK_SIGNAL"

            combo_drugs = METABOLIC_INHIBITORS.get(pw_name, [])

            vulnerabilities.append({
                "compound": cpd,
                "pathway": pw_name,
                "l1000_zscore": round(float(l1000_z), 3),
                "delta_lfc": round(delta_lfc, 3),
                "p_value": round(float(p_val), 4),
                "n_dependent": int(dep_mask.sum()),
                "n_independent": int((~dep_mask).sum()),
                "vulnerability_type": vuln_type,
                "suggested_combinations": combo_drugs[:3] if vuln_type == "EXPLOIT" else [],
            })

    df = pd.DataFrame(vulnerabilities)
    exploits = df[df["vulnerability_type"] == "EXPLOIT"] if len(df) > 0 else df

    return {
        "summary": (
            f"Metabolic vulnerability analysis: {len(df)} compound-pathway pairs tested\n"
            f"Exploitable vulnerabilities: {len(exploits)}\n"
            f"Pathways screened: {', '.join(pathways_to_test.keys())}"
        ),
        "n_total": len(df),
        "n_exploitable": len(exploits),
        "vulnerabilities": df.to_dict("records") if len(df) < 200 else exploits.to_dict("records"),
    }
