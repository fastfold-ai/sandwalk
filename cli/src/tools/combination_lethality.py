"""Combination therapy tool: synthetic lethal partner mining from DepMap CRISPR data."""

import pandas as pd

from tools import registry


@registry.register(
    name="combination.synthetic_lethality",
    description="Mine DepMap CRISPR data for synthetic lethal gene pairs with a target",
    category="combination",
    parameters={
        "gene": "Target gene to find synthetic lethal partners for",
        "top_n": "Number of top partners to return",
    },
    requires_data=["depmap_crispr"],
    usage_guide="You want to find genes whose loss is lethal only when your target gene is also disrupted. Use for identifying combination targets and understanding genetic dependencies.",
)
def synthetic_lethality(gene: str, top_n: int = 20, **kwargs) -> dict:
    """Find synthetic lethal partners via anti-correlated CRISPR dependencies.

    Genes with strong negative correlation in DepMap CRISPR effect = when one is
    essential, the other is dispensable -> synthetic lethality.
    """
    from scipy import stats

    from data.loaders import load_crispr

    crispr = load_crispr()

    if gene not in crispr.columns:
        return {"error": f"Gene {gene} not found in DepMap CRISPR data", "summary": f"Gene {gene} not found in DepMap CRISPR data"}
    target_vals = crispr[gene].dropna()

    # Compute anti-correlations (negative r = synthetic lethal)
    results = []
    for other_gene in crispr.columns:
        if other_gene == gene:
            continue
        other_vals = crispr[other_gene].dropna()
        common = target_vals.index.intersection(other_vals.index)
        if len(common) < 50:
            continue

        r, p = stats.pearsonr(target_vals[common], other_vals[common])
        if r < -0.1:  # only anti-correlated
            results.append({
                "gene": other_gene,
                "correlation": round(float(r), 4),
                "p_value": float(p),
                "n_cell_lines": len(common),
            })

    if not results:
        return {
            "summary": f"Synthetic lethality screen for {gene}: no anti-correlated genes found",
            "target_gene": gene,
            "n_candidates": 0,
            "top_partners": [],
        }

    df = pd.DataFrame(results).sort_values("correlation")

    # Classify synthetic lethal strength
    for i, row in df.iterrows():
        if row["correlation"] < -0.3:
            df.at[i, "strength"] = "strong"
        elif row["correlation"] < -0.2:
            df.at[i, "strength"] = "moderate"
        else:
            df.at[i, "strength"] = "weak"

    top_sl = df.head(top_n)

    return {
        "summary": (
            f"Synthetic lethality screen for {gene}: {len(df)} anti-correlated genes\n"
            f"Strong (r < -0.3): {(df['correlation'] < -0.3).sum()}, "
            f"Moderate (r < -0.2): {((df['correlation'] >= -0.3) & (df['correlation'] < -0.2)).sum()}"
        ),
        "target_gene": gene,
        "n_candidates": len(df),
        "top_partners": top_sl.to_dict("records"),
    }
