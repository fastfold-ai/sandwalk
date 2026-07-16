"""omics.methylation_diff / methylation_profile. Split from tools/omics.py."""
from tools import registry

from tools import omics as _omics


@registry.register(
    name="omics.methylation_diff",
    description="Differential methylation analysis between two sample groups",
    category="omics",
    parameters={
        "path": "Path to methylation beta-value matrix (rows=CpG sites, cols=samples)",
        "group1": "Comma-separated sample names for group 1",
        "group2": "Comma-separated sample names for group 2",
        "auto_grouping": "If true, splits samples by column order for exploratory use (default false)",
        "delta_beta_cutoff": "Minimum absolute delta-beta to call DMR (default 0.2)",
        "fdr_cutoff": "FDR significance threshold (default 0.05)",
    },
    usage_guide=(
        "Analyze differential methylation from beta-value matrices (e.g., Illumina 450K/EPIC). "
        "Requires a matrix with CpG sites as rows and samples as columns. "
        "Use after omics.geo_fetch or omics.tcga_fetch to download methylation data. "
        "For reliable analysis, provide explicit group1/group2 sample lists."
    ),
)
def methylation_diff(
    path: str,
    group1: str = "",
    group2: str = "",
    auto_grouping: bool = False,
    delta_beta_cutoff: float = 0.2,
    fdr_cutoff: float = 0.05,
    **kwargs,
) -> dict:
    """Differential methylation analysis between two groups."""
    import numpy as np
    from scipy import stats

    df, error = _omics._load_tabular(path)
    if error:
        return {"error": error, "summary": f"Could not load methylation data: {error}"}

    g1_samples, g2_samples, group_error = _omics._parse_sample_groups(
        df,
        group1=group1,
        group2=group2,
        auto_grouping=auto_grouping,
        min_group_size=2,
    )
    if group_error:
        return group_error

    g1 = df[g1_samples].dropna(how="all")
    g2 = df[g2_samples].dropna(how="all")
    common_sites = g1.index.intersection(g2.index)
    g1 = g1.loc[common_sites]
    g2 = g2.loc[common_sites]

    # Calculate delta-beta and p-values
    mean1 = g1.mean(axis=1)
    mean2 = g2.mean(axis=1)
    delta_beta = mean2 - mean1

    pvals = []
    for site in common_sites:
        v1 = g1.loc[site].dropna().values
        v2 = g2.loc[site].dropna().values
        if len(v1) >= 2 and len(v2) >= 2:
            _, p = stats.mannwhitneyu(v1, v2, alternative="two-sided")
            pvals.append(p)
        else:
            pvals.append(1.0)

    pvals = np.array(pvals)
    qvals = _omics._fdr_correct(pvals)

    # Identify DMRs
    sig_mask = (qvals < fdr_cutoff) & (np.abs(delta_beta.values) >= delta_beta_cutoff)
    n_sig = int(sig_mask.sum())
    hyper = int(((qvals < fdr_cutoff) & (delta_beta.values >= delta_beta_cutoff)).sum())
    hypo = int(((qvals < fdr_cutoff) & (delta_beta.values <= -delta_beta_cutoff)).sum())

    # Top hits
    import pandas as pd

    results_df = pd.DataFrame({
        "mean_group1": mean1,
        "mean_group2": mean2,
        "delta_beta": delta_beta,
        "pvalue": pvals,
        "fdr": qvals,
    }, index=common_sites)
    results_df = results_df.sort_values("fdr")
    top_hits = results_df.head(20).to_dict("index")

    return {
        "n_sites_tested": len(common_sites),
        "n_significant": n_sig,
        "n_hypermethylated": hyper,
        "n_hypomethylated": hypo,
        "group1_samples": g1_samples,
        "group2_samples": g2_samples,
        "auto_grouping_used": bool(auto_grouping and not group1 and not group2),
        "delta_beta_cutoff": delta_beta_cutoff,
        "fdr_cutoff": fdr_cutoff,
        "top_hits": top_hits,
        "summary": (
            f"Tested {len(common_sites):,} CpG sites: {n_sig} significant (FDR<{fdr_cutoff}, "
            f"|Δβ|≥{delta_beta_cutoff}). {hyper} hypermethylated, {hypo} hypomethylated."
        ),
    }


# ---------------------------------------------------------------------------
# 9. omics.methylation_profile
# ---------------------------------------------------------------------------


@registry.register(
    name="omics.methylation_profile",
    description="Summarize methylation landscape: distribution, variability, and global patterns",
    category="omics",
    parameters={
        "path": "Path to methylation beta-value matrix",
    },
    usage_guide=(
        "Get an overview of a methylation dataset: global methylation levels, "
        "bimodal distribution (typical of 450K/EPIC), most variable CpGs. "
        "Use as a first step before methylation_diff."
    ),
)
def methylation_profile(path: str, **kwargs) -> dict:
    """Summarize methylation dataset landscape."""
    import numpy as np

    df, error = _omics._load_tabular(path)
    if error:
        return {"error": error, "summary": f"Could not load: {error}"}

    n_sites, n_samples = df.shape
    all_vals = df.values.flatten()
    all_vals = all_vals[~np.isnan(all_vals)]

    # Global statistics
    global_mean = float(np.mean(all_vals))
    global_median = float(np.median(all_vals))
    frac_low = float(np.mean(all_vals < 0.2))  # unmethylated
    frac_mid = float(np.mean((all_vals >= 0.2) & (all_vals <= 0.8)))  # intermediate
    frac_high = float(np.mean(all_vals > 0.8))  # methylated

    # Most variable sites
    site_var = df.var(axis=1).dropna().sort_values(ascending=False)
    top_variable = list(site_var.head(20).index)

    # Per-sample mean methylation
    sample_means = df.mean(axis=0).to_dict()

    return {
        "n_sites": n_sites,
        "n_samples": n_samples,
        "global_mean_beta": round(global_mean, 4),
        "global_median_beta": round(global_median, 4),
        "fraction_unmethylated": round(frac_low, 3),
        "fraction_intermediate": round(frac_mid, 3),
        "fraction_methylated": round(frac_high, 3),
        "top_variable_sites": top_variable,
        "sample_mean_betas": {k: round(v, 4) for k, v in list(sample_means.items())[:20]},
        "summary": (
            f"Methylation profile: {n_sites:,} sites x {n_samples} samples. "
            f"Global mean β={global_mean:.3f}. "
            f"Distribution: {frac_low:.0%} low (<0.2), {frac_mid:.0%} intermediate, {frac_high:.0%} high (>0.8)."
        ),
    }
