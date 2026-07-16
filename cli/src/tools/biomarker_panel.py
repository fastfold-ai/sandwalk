"""Biomarker tools: ML-based biomarker panel selection."""

import numpy as np
import pandas as pd

from tools import registry
from tools.biomarker_panel_ml import _compute_importances, _cross_val_auc


@registry.register(
    name="biomarker.panel_select",
    description="ML-based biomarker panel selection: identify top predictive mutations for compound sensitivity",
    category="biomarker",
    parameters={
        "compound_id": "Compound ID (PRISM pert_name)",
        "n_features": "Number of top biomarker features to return (default 10)",
        "method": "Feature selection method: 'mutual_info', 'lasso', or 'random_forest' (default 'mutual_info')",
    },
    requires_data=["prism", "depmap_mutations", "depmap_model"],
    usage_guide="You want to select the best biomarker panel for predicting compound response — "
                "which mutations best predict sensitivity. Use for patient stratification, companion "
                "diagnostic design, and clinical trial enrichment. Methods: mutual_info (fast, nonlinear), "
                "lasso (sparse linear), random_forest (handles interactions).",
)
def panel_select(
    compound_id: str,
    n_features: int = 10,
    method: str = "mutual_info",
    **kwargs,
) -> dict:
    """ML-based biomarker panel selection using sklearn.

    Uses PRISM sensitivity as target (LFC < -0.5 = sensitive) and the DepMap
    mutation matrix as features. Supports three methods:
    - mutual_info: mutual information classification (fast, captures nonlinear)
    - lasso: LassoCV with L1 regularization (sparse, linear)
    - random_forest: random forest feature importances (handles interactions)

    Returns ranked list of biomarker genes with importance scores and
    cross-validation AUC.
    """
    from data.loaders import load_model_metadata, load_mutations, load_prism
    from tools._compound_resolver import resolve_compound

    compound_id = resolve_compound(compound_id, dataset="prism")

    valid_methods = ("mutual_info", "lasso", "random_forest")
    if method not in valid_methods:
        return {"error": f"Unknown method '{method}'. Choose from: {', '.join(valid_methods)}", "summary": f"Unknown method '{method}'. Choose from: {', '.join(valid_methods)}"}
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
        return {"error": f"Compound {compound_id} not found in PRISM data", "summary": f"Compound {compound_id} not found in PRISM data"}
    max_dose = cpd["pert_dose"].max()
    cpd_hd = cpd[cpd["pert_dose"] == max_dose].groupby("ccle_name")["LFC"].mean()

    # Map to ModelIDs and build target vector
    sensitivity = {}
    for ccle, lfc in cpd_hd.items():
        mid = ccle_to_model.get(ccle)
        if mid and mid in mutations.index:
            sensitivity[mid] = lfc

    if len(sensitivity) < 20:
        return {
            "error": f"Insufficient overlap: only {len(sensitivity)} cell lines mapped between PRISM and mutation data (need >=20)",
        }

    common_ids = list(sensitivity.keys())
    y_lfc = np.array([sensitivity[mid] for mid in common_ids])
    y_binary = (y_lfc < -0.5).astype(int)  # 1 = sensitive

    n_sensitive = int(y_binary.sum())
    n_resistant = int(len(y_binary) - n_sensitive)

    if n_sensitive < 3 or n_resistant < 3:
        return {
            "error": f"Insufficient class balance: {n_sensitive} sensitive, {n_resistant} resistant (need >=3 each)",
        }

    # --- Build feature matrix (mutation status) ---
    # Filter to genes with at least 3 mutated samples
    X_full = mutations.loc[common_ids].fillna(0)
    gene_counts = (X_full > 0).sum()
    usable_genes = gene_counts[(gene_counts >= 3) & (gene_counts <= len(common_ids) - 3)].index.tolist()

    if len(usable_genes) < 3:
        return {
            "error": f"Only {len(usable_genes)} genes with sufficient mutation frequency for feature selection",
        }

    X = X_full[usable_genes].values
    feature_names = usable_genes

    importances = _compute_importances(method, X, y_binary, y_lfc, n_sensitive, n_resistant)

    ranked_idx = np.argsort(importances)[::-1]
    top_idx = ranked_idx[:n_features]

    biomarkers = []
    for i in top_idx:
        gene_name = feature_names[i]
        imp = float(importances[i])
        if imp <= 0 and method != "lasso":
            continue  # Skip zero-importance features
        n_mut = int((X[:, i] > 0).sum())
        biomarkers.append({
            "gene": gene_name,
            "importance": round(imp, 6),
            "n_mutated": n_mut,
            "mutation_frequency": round(n_mut / len(common_ids), 4),
        })

    cv_auc = _cross_val_auc(X, y_binary, feature_names, biomarkers, n_sensitive, n_resistant)

    # --- Summary ---
    top_genes_str = ", ".join(
        f"{b['gene']}({b['importance']:.4f})" for b in biomarkers[:5]
    )
    auc_str = f", CV-AUC={cv_auc:.3f}" if cv_auc is not None else ""
    summary = (
        f"Biomarker panel for {compound_id} ({method}): "
        f"{len(biomarkers)} features selected from {len(usable_genes)} candidates. "
        f"Top: {top_genes_str}{auc_str}"
    )

    return {
        "summary": summary,
        "compound": compound_id,
        "method": method,
        "n_cell_lines": len(common_ids),
        "n_sensitive": n_sensitive,
        "n_resistant": n_resistant,
        "n_features_tested": len(usable_genes),
        "biomarkers": biomarkers,
        "cv_auc": cv_auc,
    }
