"""omics.deseq2 R backend (via rpy2). Split from tools/omics.py."""
from tools.omics_deseq2_helpers import _resolve_target_gene, _target_gene_summary_text


def run_r_deseq2(ctx: dict, params: dict) -> dict:
    """Run DESeq2 via the R package (through rpy2). Raises on any failure."""
    import rpy2.robjects as ro
    from rpy2.robjects import pandas2ri
    from rpy2.robjects.conversion import localconverter
    from rpy2.robjects.packages import importr

    counts = ctx["counts"]
    metadata = ctx["metadata"]
    condition_col = params["condition_col"]
    test, ref = ctx["test"], ctx["ref"]
    alpha = params["alpha"]
    lfc_shrink = params["lfc_shrink"]
    design_formula = ctx["design_formula"]

    # Ensure DESeq2 is available in either user or system R library.
    ro.r(".libPaths(c('~/R/library', .libPaths()))")
    importr("DESeq2")
    if lfc_shrink:
        try:
            importr("apeglm")
        except Exception:
            # Shrinkage is optional; proceed without if apeglm unavailable.
            lfc_shrink = False

    counts_r = counts.astype(int)
    meta_r = metadata.copy()
    # R expects colData rownames to match countData colnames.
    meta_r.index = counts_r.columns

    with localconverter(ro.default_converter + pandas2ri.converter):
        ro.globalenv["counts_df"] = counts_r
        ro.globalenv["meta_df"] = meta_r

    ro.globalenv["design_formula_str"] = design_formula
    ro.globalenv["condition_col_str"] = condition_col
    ro.globalenv["test_level_str"] = test
    ro.globalenv["ref_level_str"] = ref
    ro.globalenv["alpha_val"] = float(alpha)
    ro.globalenv["do_shrink"] = bool(lfc_shrink)

    r_script = """
    suppressPackageStartupMessages(library(DESeq2))
    if (isTRUE(do_shrink)) {
      suppressPackageStartupMessages(library(apeglm))
    }
    counts_mat <- as.matrix(counts_df)
    mode(counts_mat) <- "integer"
    meta <- as.data.frame(meta_df)
    cond_vals <- as.character(meta[[condition_col_str]])
    meta[[condition_col_str]] <- factor(cond_vals)
    meta[[condition_col_str]] <- relevel(meta[[condition_col_str]], ref = ref_level_str)
    dds <- DESeqDataSetFromMatrix(
      countData = counts_mat,
      colData = meta,
      design = as.formula(design_formula_str)
    )
    dds <- DESeq(dds, quiet = TRUE)
    res <- results(
      dds,
      contrast = c(condition_col_str, test_level_str, ref_level_str),
      alpha = alpha_val
    )
    shrink_coeff <- NA_character_
    if (isTRUE(do_shrink)) {
      rn <- resultsNames(dds)
      cand <- rn[grepl(paste0("^", condition_col_str, "_"), rn)]
      if (length(cand) > 0) {
        shrink_coeff <- cand[1]
        res <- lfcShrink(dds, coef = shrink_coeff, type = "apeglm")
      }
    }
    res_df <- as.data.frame(res)
    res_df$gene_id <- rownames(res_df)
    """
    ro.r(r_script)
    with localconverter(ro.default_converter + pandas2ri.converter):
        res_df = ro.conversion.rpy2py(ro.globalenv["res_df"])
    shrink_coeff = str(ro.globalenv["shrink_coeff"][0]) if "shrink_coeff" in ro.globalenv else None
    if shrink_coeff in {"NA", "NA_character_", "None"}:
        shrink_coeff = None

    if "baseMean" not in res_df.columns or "padj" not in res_df.columns:
        raise ValueError("R DESeq2 results missing required columns")
    res_df = res_df.set_index("gene_id")
    results = res_df.sort_values("padj")

    n_sig = int((results["padj"] < alpha).sum())
    n_up = int(((results["padj"] < alpha) & (results["log2FoldChange"] > 0)).sum())
    n_down = int(((results["padj"] < alpha) & (results["log2FoldChange"] < 0)).sum())
    target_gene = params["target_gene"]
    target_gene_result = _resolve_target_gene(
        results, target_gene, params["counts_path"], params["gene_map_path"],
        params["gene_id_col"], params["gene_symbol_col"],
    )
    target_gene_summary = _target_gene_summary_text(target_gene_result, target_gene)
    infer_metadata, metadata_path = params["infer_metadata"], params["metadata_path"]
    return {
        "method": "DESeq2 (R via rpy2)",
        "n_genes_tested": len(results),
        "n_significant": n_sig,
        "n_upregulated": n_up,
        "n_downregulated": n_down,
        "contrast": f"{test} vs {ref}",
        "design": design_formula,
        "covariates": ctx["covars"],
        "n_samples_ref": ctx["n_ref"],
        "n_samples_test": ctx["n_test"],
        "n_shared_samples": ctx["n_shared_samples"],
        "prefilter": {
            "min_count": int(params["prefilter_min_count"]),
            "min_samples": int(params["prefilter_min_samples"]),
            "n_genes_after": int(len(results)),
        },
        "metadata_inferred": bool(infer_metadata and not metadata_path),
        "alpha": alpha,
        "lfc_shrink": bool(lfc_shrink),
        "lfc_shrink_coeff": shrink_coeff,
        "top_hits": results.head(20).to_dict("index"),
        "target_gene_result": target_gene_result,
        "summary": (
            f"DESeq2 (R): {len(results):,} genes tested ({test} vs {ref}) with design {design_formula}. "
            f"{n_sig} significant (padj<{alpha}): {n_up} up, {n_down} down."
            + (" Metadata was inferred from sample order (exploratory)." if infer_metadata and not metadata_path else "")
            + target_gene_summary
        ),
    }
