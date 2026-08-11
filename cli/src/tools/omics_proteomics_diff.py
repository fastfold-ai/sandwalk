"""omics.proteomics_diff: differential proteomics abundance. Split from tools/omics.py."""
from tools import omics as _omics
from tools import registry


@registry.register(
    name="omics.proteomics_diff",
    description="Differential protein abundance analysis between two groups",
    category="omics",
    parameters={
        "path": "Path to protein abundance matrix (rows=proteins, cols=samples)",
        "group1": "Comma-separated sample names for group 1",
        "group2": "Comma-separated sample names for group 2",
        "auto_grouping": "If true, splits samples by column order for exploratory use (default false)",
        "fc_cutoff": "Minimum absolute log2 fold-change (default 1.0)",
        "fdr_cutoff": "FDR significance threshold (default 0.05)",
    },
    usage_guide=(
        "Differential protein abundance from proteomics data (e.g., TMT, LFQ). "
        "Input is a protein x sample matrix of log2 abundances or intensities. "
        "Provide explicit group1/group2 sample lists for production analyses."
    ),
)
def proteomics_diff(
    path: str,
    group1: str = "",
    group2: str = "",
    auto_grouping: bool = False,
    fc_cutoff: float = 1.0,
    fdr_cutoff: float = 0.05,
    **kwargs,
) -> dict:
    """Differential protein abundance analysis."""
    import numpy as np
    from scipy import stats

    df, error = _omics._load_tabular(path)
    if error:
        return {"error": error, "summary": f"Could not load proteomics data: {error}"}

    g1_samples, g2_samples, group_error = _omics._parse_sample_groups(
        df,
        group1=group1,
        group2=group2,
        auto_grouping=auto_grouping,
        min_group_size=2,
    )
    if group_error:
        return group_error

    g1 = df[g1_samples]
    g2 = df[g2_samples]

    mean1 = g1.mean(axis=1)
    mean2 = g2.mean(axis=1)
    log2fc = mean2 - mean1  # already log2 if input is log2

    pvals = []
    for prot in df.index:
        v1 = g1.loc[prot].dropna().values
        v2 = g2.loc[prot].dropna().values
        if len(v1) >= 2 and len(v2) >= 2:
            _, p = stats.mannwhitneyu(v1, v2, alternative="two-sided")
            pvals.append(p)
        else:
            pvals.append(1.0)

    pvals = np.array(pvals)
    qvals = _omics._fdr_correct(pvals)

    sig_mask = (qvals < fdr_cutoff) & (np.abs(log2fc.values) >= fc_cutoff)
    n_sig = int(sig_mask.sum())
    n_up = int(((qvals < fdr_cutoff) & (log2fc.values >= fc_cutoff)).sum())
    n_down = int(((qvals < fdr_cutoff) & (log2fc.values <= -fc_cutoff)).sum())

    import pandas as pd

    results_df = pd.DataFrame({
        "mean_group1": mean1,
        "mean_group2": mean2,
        "log2fc": log2fc,
        "pvalue": pvals,
        "fdr": qvals,
    }, index=df.index)
    results_df = results_df.sort_values("fdr")

    return {
        "n_proteins_tested": len(df.index),
        "n_significant": n_sig,
        "n_upregulated": n_up,
        "n_downregulated": n_down,
        "group1_samples": g1_samples,
        "group2_samples": g2_samples,
        "auto_grouping_used": bool(auto_grouping and not group1 and not group2),
        "top_hits": results_df.head(20).to_dict("index"),
        "summary": (
            f"Tested {len(df.index):,} proteins: {n_sig} significant "
            f"(FDR<{fdr_cutoff}, |log2FC|≥{fc_cutoff}). {n_up} up, {n_down} down."
        ),
    }
