"""omics.deseq2 pyDESeq2 backend + optional post-DE enrichment. Split from tools/omics.py."""
from tools import omics as _omics
from tools.omics_deseq2_helpers import _resolve_target_gene, _target_gene_summary_text


def run_pydeseq2(ctx: dict, params: dict) -> dict:
    """Run DESeq2 via pyDESeq2, with optional Enrichr enrichment. Raises on failure."""
    from pydeseq2.dds import DeseqDataSet
    from pydeseq2.default_inference import DefaultInference
    from pydeseq2.ds import DeseqStats

    counts, metadata = ctx["counts"], ctx["metadata"]
    condition_col = params["condition_col"]
    test, ref = ctx["test"], ctx["ref"]
    alpha, lfc_shrink = params["alpha"], params["lfc_shrink"]

    inference = DefaultInference(n_cpus=1)
    # pyDESeq2 wants samples as rows, genes as columns
    dds = DeseqDataSet(
        counts=counts.T,
        metadata=metadata,
        design=ctx["design_formula"],
        refit_cooks=True,
        inference=inference,
        quiet=True,
    )
    dds.deseq2()

    stat = DeseqStats(dds, contrast=[condition_col, test, ref], alpha=alpha, inference=inference, quiet=True)
    stat.summary()

    # Optional apeglm shrinkage on the requested condition coefficient.
    shrink_coeff = None
    if lfc_shrink and hasattr(dds, "varm") and "LFC" in dds.varm:
        coeffs = list(dds.varm["LFC"].columns)
        preferred = [c for c in coeffs if condition_col in c and (test in c or test.replace("-", "_") in c)]
        if preferred:
            shrink_coeff = preferred[0]
            try:
                stat.lfc_shrink(coeff=shrink_coeff)
            except Exception as exc:
                _omics.logger.warning("LFC shrinkage failed for coeff %s: %s", shrink_coeff, exc)

    results = stat.results_df.sort_values("padj")
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

    result_payload = {
        "method": "DESeq2 (pydeseq2)",
        "n_genes_tested": len(results),
        "n_significant": n_sig,
        "n_upregulated": n_up,
        "n_downregulated": n_down,
        "contrast": f"{test} vs {ref}",
        "design": ctx["design_formula"],
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
            f"DESeq2: {len(results):,} genes tested ({test} vs {ref}) with design {ctx['design_formula']}. "
            f"{n_sig} significant (padj<{alpha}): {n_up} up, {n_down} down."
            + (" Metadata was inferred from sample order (exploratory)." if infer_metadata and not metadata_path else "")
            + target_gene_summary
        ),
    }

    if params["enrichment_library"]:
        _run_enrichment(result_payload, results, params)

    return result_payload


def _run_enrichment(result_payload: dict, results, params: dict) -> None:
    """Enrichr enrichment over significant DEGs with effect filters (mutates result_payload)."""
    alpha = params["alpha"]
    enrichment_library, pathway_term = params["enrichment_library"], params["pathway_term"]
    gene_map_path, gene_id_col, gene_symbol_col = params["gene_map_path"], params["gene_id_col"], params["gene_symbol_col"]

    sig = results[results["padj"] < alpha].copy()
    if params["min_abs_lfc"] > 0:
        sig = sig[sig["log2FoldChange"].abs() >= float(params["min_abs_lfc"])]
    if params["min_base_mean"] > 0 and "baseMean" in sig.columns:
        sig = sig[sig["baseMean"] >= float(params["min_base_mean"])]

    genes_for_enrichment = list(sig.index.astype(str))
    mapped_gene_count = None
    if gene_map_path:
        gm, gm_err = _omics._load_tabular(gene_map_path, index_col=None)
        if gm_err:
            result_payload["enrichment_error"] = f"Gene map load failed: {gm_err}"
            return
        id_col = gene_id_col or ("ENSG_ID" if "ENSG_ID" in gm.columns else gm.columns[0])
        sym_col = gene_symbol_col or (
            "gene_name" if "gene_name" in gm.columns else ("symbol" if "symbol" in gm.columns else gm.columns[-1])
        )
        gm2 = gm[[id_col, sym_col]].dropna().copy()
        gm2[id_col] = gm2[id_col].astype(str)
        gm2[sym_col] = gm2[sym_col].astype(str)
        mapper = dict(zip(gm2[id_col], gm2[sym_col]))
        mapped = []
        for gid in genes_for_enrichment:
            mapped_sym = mapper.get(gid, mapper.get(gid.split(".")[0]))
            if mapped_sym:
                mapped.append(mapped_sym)
        genes_for_enrichment = sorted(set(mapped))
        mapped_gene_count = len(genes_for_enrichment)

    if not genes_for_enrichment:
        return
    try:
        import gseapy

        enr = gseapy.enrichr(gene_list=genes_for_enrichment, gene_sets=enrichment_library, outdir=None, no_plot=True)
        enr_df = enr.results.copy()
        result_payload["enrichment"] = {
            "library": enrichment_library,
            "n_input_genes": len(genes_for_enrichment),
            "mapped_gene_count": mapped_gene_count,
            "n_terms": int(len(enr_df)),
            "top_terms": enr_df.head(20).to_dict("records"),
        }

        if pathway_term:
            terms = enr_df["Term"].astype(str)
            exact = enr_df[terms.str.lower() == pathway_term.lower()]
            target_df = exact if not exact.empty else enr_df[terms.str.contains(pathway_term, case=False, na=False)]
            if not target_df.empty:
                target = target_df.iloc[0].to_dict()
                result_payload["pathway_match"] = target
                result_payload["pathway_odds_ratio"] = target.get("Odds Ratio")
                result_payload["summary"] += (
                    f" Enrichment: '{target.get('Term', pathway_term)}' odds ratio {target.get('Odds Ratio')}."
                )
            else:
                result_payload["pathway_match"] = None
                result_payload["summary"] += f" Enrichment ran but pathway '{pathway_term}' was not found."
    except Exception as exc:
        result_payload["enrichment_error"] = str(exc)
        result_payload["summary"] += " Enrichment step failed."
