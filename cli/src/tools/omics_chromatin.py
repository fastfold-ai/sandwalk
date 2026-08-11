"""omics.chromatin_accessibility / hic_compartments. Split from tools/omics.py."""
from tools import omics as _omics
from tools import registry


@registry.register(
    name="omics.chromatin_accessibility",
    description="Differential chromatin accessibility analysis between two sample groups",
    category="omics",
    parameters={
        "path": "Path to peak count matrix (rows=peaks/genes, cols=samples)",
        "group1": "Comma-separated sample names for group 1",
        "group2": "Comma-separated sample names for group 2",
        "auto_grouping": "If true, splits samples by column order for exploratory use (default false)",
        "fdr_cutoff": "FDR threshold (default 0.05)",
    },
    usage_guide=(
        "Compare chromatin accessibility between groups from ATAC-seq count matrices. "
        "Works on peak-level or gene-level accessibility scores. "
        "Provide explicit group1/group2 sample lists for robust comparisons."
    ),
)
def chromatin_accessibility(
    path: str,
    group1: str = "",
    group2: str = "",
    auto_grouping: bool = False,
    fdr_cutoff: float = 0.05,
    **kwargs,
) -> dict:
    """Differential chromatin accessibility analysis."""
    import numpy as np
    from scipy import stats

    df, error = _omics._load_tabular(path)
    if error:
        return {"error": error, "summary": f"Could not load: {error}"}

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
    # Log2 fold-change (add pseudocount to avoid log(0))
    log2fc = np.log2((mean2 + 1) / (mean1 + 1))

    pvals = []
    for region in df.index:
        v1 = g1.loc[region].dropna().values
        v2 = g2.loc[region].dropna().values
        if len(v1) >= 2 and len(v2) >= 2:
            _, p = stats.mannwhitneyu(v1, v2, alternative="two-sided")
            pvals.append(p)
        else:
            pvals.append(1.0)

    pvals = np.array(pvals)
    qvals = _omics._fdr_correct(pvals)

    sig_mask = qvals < fdr_cutoff
    n_sig = int(sig_mask.sum())
    n_more_open = int((sig_mask & (log2fc.values > 0)).sum())
    n_more_closed = int((sig_mask & (log2fc.values < 0)).sum())

    import pandas as pd

    results_df = pd.DataFrame({
        "mean_group1": mean1, "mean_group2": mean2,
        "log2fc": log2fc, "pvalue": pvals, "fdr": qvals,
    }, index=df.index).sort_values("fdr")

    return {
        "n_regions_tested": len(df.index),
        "n_significant": n_sig,
        "n_more_accessible": n_more_open,
        "n_less_accessible": n_more_closed,
        "group1_samples": g1_samples,
        "group2_samples": g2_samples,
        "auto_grouping_used": bool(auto_grouping and not group1 and not group2),
        "top_hits": results_df.head(20).to_dict("index"),
        "summary": (
            f"Tested {len(df.index):,} regions: {n_sig} differentially accessible "
            f"(FDR<{fdr_cutoff}). {n_more_open} gained, {n_more_closed} lost accessibility."
        ),
    }


@registry.register(
    name="omics.hic_compartments",
    description="Identify A/B compartments from Hi-C contact matrices",
    category="omics",
    parameters={
        "path": "Path to Hi-C contact matrix (CSV/TSV, symmetric matrix with genomic bins)",
        "resolution": "Bin resolution description (for reporting, e.g. '50kb')",
    },
    usage_guide=(
        "Identify chromatin A/B compartments from Hi-C contact frequency matrices. "
        "A compartments are gene-rich/active, B compartments are gene-poor/repressed. "
        "Input should be a symmetric bin x bin contact matrix."
    ),
)
def hic_compartments(path: str, resolution: str = "unknown", **kwargs) -> dict:
    """Identify A/B compartments from Hi-C contact matrix via PCA."""
    import numpy as np

    df, error = _omics._load_tabular(path)
    if error:
        return {"error": error, "summary": f"Could not load: {error}"}

    n_bins = df.shape[0]
    if df.shape[0] != df.shape[1]:
        return {
            "error": f"Expected symmetric matrix, got {df.shape[0]}x{df.shape[1]}",
            "summary": "Hi-C contact matrix must be square (symmetric)",
        }

    if n_bins < 3:
        return {"error": f"Too few bins ({n_bins})", "summary": "Need at least 3 bins for compartment analysis"}

    # Convert to numpy, handle NaN
    matrix = df.values.astype(float)
    matrix = np.nan_to_num(matrix, nan=0.0)

    # Normalize: observed/expected
    row_sums = matrix.sum(axis=1)
    row_sums[row_sums == 0] = 1  # avoid division by zero
    expected = np.outer(row_sums, row_sums) / row_sums.sum()
    expected[expected == 0] = 1
    oe_matrix = matrix / expected

    # Correlation matrix
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = np.corrcoef(oe_matrix)
        corr = np.nan_to_num(corr, nan=0.0)

    # PCA — first eigenvector gives A/B compartments
    eigenvalues, eigenvectors = np.linalg.eigh(corr)
    # Take the eigenvector with largest eigenvalue
    pc1 = eigenvectors[:, -1]

    # A compartments = positive PC1 (convention: gene-rich is positive)
    compartments = np.where(pc1 > 0, "A", "B")
    n_A = int((compartments == "A").sum())
    n_B = int((compartments == "B").sum())
    frac_A = n_A / n_bins

    # Compartment runs (contiguous blocks)
    transitions = 0
    for i in range(1, len(compartments)):
        if compartments[i] != compartments[i - 1]:
            transitions += 1

    return {
        "n_bins": n_bins,
        "resolution": resolution,
        "n_compartment_A": n_A,
        "n_compartment_B": n_B,
        "fraction_A": round(frac_A, 3),
        "n_transitions": transitions,
        "pc1_values": pc1.tolist()[:50],
        "compartment_assignments": compartments.tolist()[:50],
        "explained_variance": round(float(eigenvalues[-1] / eigenvalues.sum()), 4),
        "summary": (
            f"Hi-C compartments ({resolution} resolution): {n_bins} bins → "
            f"{n_A} A-compartment ({frac_A:.0%}), {n_B} B-compartment ({1-frac_A:.0%}). "
            f"{transitions} A/B transitions. PC1 explains {eigenvalues[-1]/eigenvalues.sum():.1%} of variance."
        ),
    }


# ===========================================================================
# Specialized library integrations (optional deps)
# ===========================================================================
