"""
expression.diff_expression: Mann-Whitney differential expression between
two sample groups, with DepMap-lineage label resolution fallback.

Split from tools/expression.py.
"""

import numpy as np
import pandas as pd

from tools import registry


def _resolve_groups_by_lineage(
    group_a: list, group_b: list, expr: "pd.DataFrame"
) -> tuple:
    """Resolve descriptive group labels to L1000 compound IDs.

    When group labels (e.g. 'multiple_myeloma', 'solid_tumor') don't match
    L1000 index entries, try to map them via DepMap Model.csv lineage info.
    As a fallback, split available compounds into two halves so the analysis
    can still proceed.
    """
    _all_ids = list(expr.index)

    # Try DepMap lineage mapping
    try:
        from data.loaders import load_depmap_model
        models = load_depmap_model()

        # Build lineage -> set of cell line IDs mapping
        lineage_col = None
        for col in ["OncotreeLineage", "lineage", "Lineage", "primary_disease",
                     "PrimaryDisease", "disease"]:
            if col in models.columns:
                lineage_col = col
                break

        if lineage_col is not None:
            # Normalise lineage values for fuzzy matching
            def _norm(s):
                return str(s).lower().replace(" ", "_").replace("-", "_")

            lineage_map = {}
            for _, row in models.iterrows():
                lin = _norm(row[lineage_col])
                # Use ModelID or DepMap_ID as identifier
                mid = None
                for id_col in ["ModelID", "DepMap_ID", "stripped_cell_line_name",
                                "StrippedCellLineName"]:
                    if id_col in models.columns and pd.notna(row.get(id_col)):
                        mid = str(row[id_col])
                        break
                if mid and mid in expr.index:
                    lineage_map.setdefault(lin, []).append(mid)

            if lineage_map:
                norm_a = [_norm(label) for label in group_a]
                norm_b = [_norm(label) for label in group_b]

                matched_a = []
                for label in norm_a:
                    for lin, ids in lineage_map.items():
                        if label in lin or lin in label:
                            matched_a.extend(ids)
                matched_b = []
                for label in norm_b:
                    for lin, ids in lineage_map.items():
                        if label in lin or lin in label:
                            matched_b.extend(ids)

                if len(matched_a) >= 2 and len(matched_b) >= 2:
                    return list(set(matched_a)), list(set(matched_b))
    except Exception:
        pass

    return [], []


@registry.register(
    name="expression.diff_expression",
    description="Differential expression analysis between two groups of samples using L1000 data",
    category="expression",
    parameters={
        "gene": "Gene symbol to test, or 'all' to test all landmark genes",
        "group_a": "List of compound IDs or cell line names for group A",
        "group_b": "List of compound IDs or cell line names for group B",
        "dataset": "Expression dataset to use (default 'l1000')",
    },
    requires_data=["l1000"],
    usage_guide="You want to compare gene expression between two conditions — e.g. treated vs control, "
                "or two compound classes. Use Mann-Whitney U for robust rank-based testing. "
                "Set gene='all' for genome-wide differential expression with FDR correction.",
)
def diff_expression(
    gene: str = "all",
    group_a: list = None,
    group_b: list = None,
    dataset: str = "l1000",
    **kwargs,
) -> dict:
    """Differential expression between two groups of samples.

    Uses Mann-Whitney U test (rank-based, non-parametric) to compare expression
    of one or all landmark genes between two sample groups. Computes fold change,
    p-value, effect size (Cohen's d), and Benjamini-Hochberg FDR correction when
    testing multiple genes.
    """
    from scipy import stats as scipy_stats

    if group_a is None or group_b is None:
        return {"error": "Both group_a and group_b must be provided as lists of sample IDs", "summary": "Both group_a and group_b must be provided as lists of sample IDs"}
    if not group_a or not group_b:
        return {"error": "Both group_a and group_b must be non-empty lists", "summary": "Both group_a and group_b must be non-empty lists"}
    # Load expression data
    from data.loaders import load_l1000
    expr = load_l1000()

    # Normalise inputs to lists
    if isinstance(group_a, str):
        group_a = [group_a]
    if isinstance(group_b, str):
        group_b = [group_b]

    if not group_a or not group_b:
        return {"error": "Both group_a and group_b must be non-empty lists"}

    # Identify which group samples are in the data (rows = samples/compounds)
    available_a = [s for s in group_a if s in expr.index]
    available_b = [s for s in group_b if s in expr.index]

    # If either group has too few direct matches, try resolving via DepMap lineage
    if len(available_a) < 2 or len(available_b) < 2:
        resolved_a, resolved_b = _resolve_groups_by_lineage(
            group_a, group_b, expr
        )
        if len(resolved_a) >= 2 and len(resolved_b) >= 2:
            available_a, available_b = resolved_a, resolved_b

    sample_hint = ", ".join(list(expr.index[:5])) + ", ..."
    if len(available_a) < 2:
        return {"error": f"Group A: only {len(available_a)} of {len(group_a)} labels found in data (need >=2). "
                         f"Provide compound IDs matching the L1000 index. Examples: {sample_hint}",
                 "summary": f"Group A: only {len(available_a)} of {len(group_a)} samples found in data (need >=2)"}
    if len(available_b) < 2:
        return {"error": f"Group B: only {len(available_b)} of {len(group_b)} labels found in data (need >=2). "
                         f"Provide compound IDs matching the L1000 index. Examples: {sample_hint}",
                 "summary": f"Group B: only {len(available_b)} of {len(group_b)} samples found in data (need >=2)"}
    data_a = expr.loc[available_a]
    data_b = expr.loc[available_b]

    # Determine which genes to test
    if gene == "all":
        genes_to_test = list(expr.columns)
    else:
        if gene not in expr.columns:
            return {"error": f"Gene '{gene}' not found in {dataset} expression data", "summary": f"Gene '{gene}' not found in {dataset} expression data"}
        genes_to_test = [gene]

    results = []
    for g in genes_to_test:
        vals_a = data_a[g].dropna()
        vals_b = data_b[g].dropna()

        if len(vals_a) < 2 or len(vals_b) < 2:
            continue

        mean_a = float(vals_a.mean())
        mean_b = float(vals_b.mean())

        # Fold change (group_a vs group_b): positive means higher in A
        fold_change = mean_a - mean_b  # log-scale data, so difference = log2 FC

        # Mann-Whitney U test
        try:
            stat, pval = scipy_stats.mannwhitneyu(vals_a, vals_b, alternative="two-sided")
        except ValueError:
            continue

        # Cohen's d effect size
        pooled_std = np.sqrt(
            ((len(vals_a) - 1) * vals_a.std() ** 2 + (len(vals_b) - 1) * vals_b.std() ** 2)
            / (len(vals_a) + len(vals_b) - 2)
        )
        cohens_d = fold_change / pooled_std if pooled_std > 0 else 0.0

        direction = "up_in_A" if fold_change > 0 else "up_in_B" if fold_change < 0 else "unchanged"

        results.append({
            "gene": g,
            "mean_a": round(mean_a, 4),
            "mean_b": round(mean_b, 4),
            "log2_fold_change": round(fold_change, 4),
            "direction": direction,
            "p_value": float(pval),
            "cohens_d": round(float(cohens_d), 4),
            "n_a": len(vals_a),
            "n_b": len(vals_b),
        })

    if not results:
        return {
            "summary": f"No testable genes found between groups (group_a={len(available_a)}, group_b={len(available_b)} samples)",
            "results": [],
        }

    df = pd.DataFrame(results).sort_values("p_value")

    # Benjamini-Hochberg FDR correction
    if len(df) > 1:
        n_tests = len(df)
        ranks = df["p_value"].rank(method="first")
        df["fdr"] = (df["p_value"] * n_tests / ranks).clip(upper=1.0)
        # Ensure monotonicity: work backward from largest rank
        fdr_vals = np.array(df.sort_values("p_value", ascending=False)["fdr"], dtype=float)
        for i in range(1, len(fdr_vals)):
            fdr_vals[i] = min(fdr_vals[i], fdr_vals[i - 1])
        df.loc[df.sort_values("p_value", ascending=False).index, "fdr"] = fdr_vals
        df = df.sort_values("p_value")
    else:
        df["fdr"] = df["p_value"]

    n_sig = int((df["p_value"] < 0.05).sum())
    n_fdr_sig = int((df["fdr"] < 0.05).sum())

    if gene != "all":
        row = df.iloc[0]
        summary = (
            f"Differential expression of {gene}: "
            f"log2FC={row['log2_fold_change']:.3f} ({row['direction']}), "
            f"p={row['p_value']:.2e}, Cohen's d={row['cohens_d']:.3f}"
        )
    else:
        top_genes = df.head(5)
        top_str = ", ".join(
            f"{r['gene']}(FC={r['log2_fold_change']:.2f}, p={r['p_value']:.2e})"
            for _, r in top_genes.iterrows()
        )
        summary = (
            f"Differential expression: {len(results)} genes tested, "
            f"{n_sig} nominally significant (p<0.05), {n_fdr_sig} FDR-significant. "
            f"Top: {top_str}"
        )

    return {
        "summary": summary,
        "n_tested": len(results),
        "n_significant_nominal": n_sig,
        "n_significant_fdr": n_fdr_sig,
        "group_a_size": len(available_a),
        "group_b_size": len(available_b),
        "results": df.to_dict("records"),
    }
