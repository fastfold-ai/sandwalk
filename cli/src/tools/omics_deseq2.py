"""omics.deseq2: differential expression orchestrator (R DESeq2 -> pyDESeq2 -> Mann-Whitney). Split from tools/omics.py."""
from tools import omics as _omics
from tools import registry
from tools.omics_deseq2_setup import prepare_deseq2_design


@registry.register(
    name="omics.deseq2",
    description="Differential expression with DESeq2 (negative binomial model for count data)",
    category="omics",
    parameters={
        "counts_path": "Path to raw count matrix (genes as rows, samples as columns)",
        "metadata_path": "Path to sample metadata table (CSV/TSV/TXT/XLSX; must have a condition column; required unless infer_metadata=true)",
        "condition_col": "Column in metadata for the contrast (default 'condition')",
        "ref_level": "Reference level for contrast (default: alphabetically first)",
        "test_level": "Test level for contrast (default: alphabetically second)",
        "covariates": "Optional comma-separated covariates to include in design (e.g., 'sex,batch')",
        "infer_metadata": "If true, infer two groups from sample column order for exploratory use only (default false)",
        "alpha": "Significance threshold for adjusted p-values (default 0.05)",
        "use_r_deseq2": "If true, prefer R DESeq2 backend via rpy2 when available (default true)",
        "prefilter_min_count": "Optional prefilter threshold: minimum count per sample (default 0 disables prefilter)",
        "prefilter_min_samples": "Optional prefilter threshold: minimum number of samples meeting prefilter_min_count (default 1)",
        "lfc_shrink": "If true, apply apeglm LFC shrinkage when possible (default false)",
        "enrichment_library": "Optional gseapy/Enrichr library name (e.g., Reactome_2022) for post-DE enrichment",
        "pathway_term": "Optional pathway term to match and extract odds ratio from enrichment results",
        "gene_map_path": "Optional gene ID -> symbol mapping table used before enrichment",
        "gene_id_col": "Optional gene ID column name in mapping table",
        "gene_symbol_col": "Optional symbol column name in mapping table",
        "min_abs_lfc": "Optional absolute log2FC threshold for enrichment gene list",
        "min_base_mean": "Optional baseMean threshold for enrichment gene list",
        "target_gene": "Optional target gene symbol/ID to report explicitly (returns log2FoldChange/baseMean/padj even if not in top hits)",
    },
    usage_guide=(
        "Proper count-based differential expression using the DESeq2 negative binomial model. "
        "Preferred over Mann-Whitney for bulk RNA-seq count data. Requires pydeseq2: "
        "pip install pydeseq2. Falls back to scipy Mann-Whitney if not installed. "
        "Supports optional covariate-adjusted design, LFC shrinkage, and optional gseapy enrichment "
        "from DE genes (including pathway-specific odds ratio extraction). "
        "Use explicit sample metadata in production; inferred metadata is exploratory only."
    ),
)
def deseq2(
    counts_path: str,
    metadata_path: str = "",
    condition_col: str = "condition",
    ref_level: str = "",
    test_level: str = "",
    covariates: str = "",
    infer_metadata: bool = False,
    alpha: float = 0.05,
    use_r_deseq2: bool = True,
    prefilter_min_count: int = 0,
    prefilter_min_samples: int = 1,
    lfc_shrink: bool = False,
    enrichment_library: str = "",
    pathway_term: str = "",
    gene_map_path: str = "",
    gene_id_col: str = "",
    gene_symbol_col: str = "",
    min_abs_lfc: float = 0.0,
    min_base_mean: float = 0.0,
    target_gene: str = "",
    **kwargs,
) -> dict:
    """Run DESeq2 differential expression on count data."""
    prepared = prepare_deseq2_design(
        counts_path, metadata_path, condition_col, ref_level, test_level, covariates,
        infer_metadata, prefilter_min_count, prefilter_min_samples,
    )
    if "error" in prepared:
        return prepared
    ctx = prepared["ctx"]

    params = {
        "condition_col": condition_col,
        "alpha": alpha,
        "lfc_shrink": lfc_shrink,
        "infer_metadata": infer_metadata,
        "metadata_path": metadata_path,
        "counts_path": counts_path,
        "target_gene": target_gene,
        "gene_map_path": gene_map_path,
        "gene_id_col": gene_id_col,
        "gene_symbol_col": gene_symbol_col,
        "prefilter_min_count": prefilter_min_count,
        "prefilter_min_samples": prefilter_min_samples,
        "enrichment_library": enrichment_library,
        "pathway_term": pathway_term,
        "min_abs_lfc": min_abs_lfc,
        "min_base_mean": min_base_mean,
    }

    if use_r_deseq2:
        try:
            from tools.omics_deseq2_r import run_r_deseq2

            return run_r_deseq2(ctx, params)
        except Exception as exc:
            _omics.logger.warning("R DESeq2 backend failed, falling back to pyDESeq2: %s", exc)

    if _omics._check_pydeseq2():
        try:
            from tools.omics_deseq2_py import run_pydeseq2

            return run_pydeseq2(ctx, params)
        except Exception as exc:
            _omics.logger.warning("pyDESeq2 failed, falling back to Mann-Whitney: %s", exc)

    from tools.omics_deseq2_fallback import run_mannwhitney_fallback

    return run_mannwhitney_fallback(ctx, params)
