"""omics.deseq2 fallback: Mann-Whitney U when pydeseq2/R DESeq2 are unavailable. Split from tools/omics.py."""
from tools.omics_deseq2_helpers import _resolve_target_gene, _target_gene_summary_text


def run_mannwhitney_fallback(ctx: dict, params: dict) -> dict:
    """Simple non-parametric fallback differential expression test."""
    import numpy as np
    import pandas as pd
    from scipy import stats

    counts, metadata = ctx["counts"], ctx["metadata"]
    condition_col = params["condition_col"]
    test, ref = ctx["test"], ctx["ref"]
    alpha = params["alpha"]

    g1_samples = metadata.index[metadata[condition_col] == ref].tolist()
    g2_samples = metadata.index[metadata[condition_col] == test].tolist()
    g1 = counts[g1_samples]
    g2 = counts[g2_samples]

    log2fc = np.log2((g2.mean(axis=1) + 1) / (g1.mean(axis=1) + 1))
    pvals = []
    for gene in counts.index:
        v1 = g1.loc[gene].dropna().values
        v2 = g2.loc[gene].dropna().values
        if len(v1) >= 2 and len(v2) >= 2:
            _, p = stats.mannwhitneyu(v1, v2, alternative="two-sided")
            pvals.append(p)
        else:
            pvals.append(1.0)

    pvals = np.array(pvals)
    from tools import omics as _omics

    qvals = _omics._fdr_correct(pvals)

    n_sig = int((qvals < alpha).sum())
    n_up = int(((qvals < alpha) & (log2fc.values > 0)).sum())
    n_down = int(((qvals < alpha) & (log2fc.values < 0)).sum())

    results = pd.DataFrame(
        {"log2FoldChange": log2fc, "pvalue": pvals, "padj": qvals}, index=counts.index
    ).sort_values("padj")
    target_gene = params["target_gene"]
    target_gene_result = _resolve_target_gene(
        results, target_gene, params["counts_path"], params["gene_map_path"],
        params["gene_id_col"], params["gene_symbol_col"],
    )
    target_gene_summary = _target_gene_summary_text(target_gene_result, target_gene)
    infer_metadata, metadata_path = params["infer_metadata"], params["metadata_path"]

    return {
        "method": "Mann-Whitney U (fallback \u2014 install pydeseq2 for proper DESeq2)",
        "n_genes_tested": len(results),
        "n_significant": n_sig,
        "n_upregulated": n_up,
        "n_downregulated": n_down,
        "contrast": f"{test} vs {ref}",
        "n_samples_ref": ctx["n_ref"],
        "n_samples_test": ctx["n_test"],
        "metadata_inferred": bool(infer_metadata and not metadata_path),
        "alpha": alpha,
        "top_hits": results.head(20).to_dict("index"),
        "target_gene_result": target_gene_result,
        "summary": (
            f"Differential expression (Mann-Whitney fallback): {len(results):,} genes ({test} vs {ref}). "
            f"{n_sig} significant (FDR<{alpha}): {n_up} up, {n_down} down. "
            f"Install pydeseq2 for proper negative binomial modeling."
            + (" Metadata was inferred from sample order (exploratory)." if infer_metadata and not metadata_path else "")
            + target_gene_summary
        ),
    }
