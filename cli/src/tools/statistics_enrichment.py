"""statistics.enrichment_test: gene set over-representation analysis.

Split from tools/statistics.py.
"""

from __future__ import annotations

from tools import registry


@registry.register(
    name="statistics.enrichment_test",
    description="Gene set over-representation analysis using hypergeometric test with FDR correction",
    category="statistics",
    parameters={
        "gene_list": "List of gene symbols (your query genes)",
        "gene_set": "Dict of set_name:gene_list, or 'hallmark' for built-in MSigDB hallmark sets",
        "background_size": "Total background gene count (default 20000)",
    },
    requires_data=[],
    usage_guide="You have a list of genes (e.g. differentially expressed, mutated, degraded) and want "
                "to know which pathways or gene sets they are enriched in. Provide your gene list and "
                "optionally a custom gene set dict, or use built-in hallmark sets. Returns FDR-corrected p-values.",
)
def enrichment_test(gene_list: list = None, gene_set: dict | str = "hallmark",
                    background_size: int = 20000, **kwargs) -> dict:
    """Gene set over-representation analysis (ORA) with hypergeometric test.

    For each gene set, computes:
    - Hypergeometric p-value (Fisher's exact one-tailed)
    - Fold enrichment = (overlap/query) / (set_size/background)
    - Benjamini-Hochberg FDR correction

    Parameters
    ----------
    gene_list : list of str
        Query genes (e.g. upregulated genes, hit list).
    gene_set : dict or str
        Dict mapping set names to gene lists, or "hallmark" for built-in.
    background_size : int
        Total number of genes in the background (default 20000).
    """
    from scipy.stats import hypergeom

    if gene_list is None or len(gene_list) == 0:
        return {"error": "Provide a non-empty gene_list", "summary": "Provide a non-empty gene_list"}
    gene_list = [str(g).upper() for g in gene_list]
    query_set = set(gene_list)
    n_query = len(query_set)

    # Load or use provided gene sets
    if isinstance(gene_set, str):
        if gene_set == "hallmark":
            gene_set = _get_hallmark_sets()
        else:
            return {"error": f"Unknown gene set collection: {gene_set}. Provide a dict or 'hallmark'", "summary": f"Unknown gene set collection: {gene_set}. Provide a dict or 'hallmark'"}
    if not isinstance(gene_set, dict) or len(gene_set) == 0:
        return {"error": "gene_set must be a non-empty dict of set_name: gene_list", "summary": "gene_set must be a non-empty dict of set_name: gene_list"}
    N = int(background_size)  # total background genes
    results = []

    for set_name, set_genes in gene_set.items():
        set_genes_upper = [str(g).upper() for g in set_genes]
        set_size = len(set_genes_upper)
        gene_set_set = set(set_genes_upper)

        # Overlap
        overlap = query_set & gene_set_set
        k = len(overlap)

        if k == 0:
            continue

        # Hypergeometric test
        # P(X >= k) where X ~ Hypergeometric(N, K, n)
        # N = background, K = set_size, n = query_size
        p_value = float(hypergeom.sf(k - 1, N, set_size, n_query))

        # Fold enrichment
        expected = (set_size / N) * n_query if N > 0 else 0
        fold_enrichment = k / expected if expected > 0 else float('inf')

        results.append({
            "gene_set": set_name,
            "overlap_count": k,
            "overlap_genes": sorted(overlap),
            "set_size": set_size,
            "p_value": p_value,
            "fold_enrichment": round(float(fold_enrichment), 2),
        })

    if not results:
        return {
            "summary": f"No enrichment found: {n_query} query genes had no overlap with {len(gene_set)} gene sets",
            "n_query_genes": n_query,
            "n_gene_sets_tested": len(gene_set),
            "enriched": [],
        }

    # Sort by p-value
    results.sort(key=lambda x: x["p_value"])

    # Benjamini-Hochberg FDR correction
    n_tests = len(results)
    for i, r in enumerate(results):
        rank = i + 1
        r["fdr"] = round(min(r["p_value"] * n_tests / rank, 1.0), 6)

    # Enforce monotonicity (FDR should be non-decreasing from bottom)
    for i in range(n_tests - 2, -1, -1):
        results[i]["fdr"] = min(results[i]["fdr"], results[i + 1]["fdr"])

    # Round p-values for output
    for r in results:
        r["p_value"] = round(r["p_value"], 8)

    significant = [r for r in results if r["fdr"] < 0.05]

    # Top 10 for summary
    top = results[:10]
    top_str = "\n".join(
        f"  {r['gene_set']}: {r['overlap_count']}/{r['set_size']} genes, "
        f"FE={r['fold_enrichment']:.1f}x, FDR={r['fdr']:.2g}"
        for r in top
    )

    summary = (
        f"Gene set enrichment ({n_query} query genes, {len(gene_set)} sets tested):\n"
        f"Significant (FDR<0.05): {len(significant)}/{n_tests}\n"
        f"Top enriched:\n{top_str}"
    )

    return {
        "summary": summary,
        "n_query_genes": n_query,
        "n_gene_sets_tested": len(gene_set),
        "n_significant": len(significant),
        "enriched": results,
    }


def _get_hallmark_sets() -> dict:
    """Get built-in hallmark-lite gene sets for enrichment analysis."""
    # Try to load full MSigDB hallmark sets first
    try:
        from data.loaders import load_msigdb
        msigdb = load_msigdb("h")
        # MSigDB JSON: {set_name: {geneSymbols: [...]}}
        if isinstance(msigdb, dict):
            parsed = {}
            for name, data in msigdb.items():
                if isinstance(data, dict) and "geneSymbols" in data:
                    parsed[name] = data["geneSymbols"]
                elif isinstance(data, list):
                    parsed[name] = data
            if parsed:
                return parsed
    except (FileNotFoundError, ImportError):
        pass

    # Fallback: curated hallmark-lite sets
    return {
        "HALLMARK_P53_PATHWAY": ["CDKN1A", "MDM2", "BAX", "GADD45A", "SFN", "DDB2",
                                  "SESN1", "TP53I3", "PMAIP1", "BBC3"],
        "HALLMARK_APOPTOSIS": ["BCL2", "BAX", "BAK1", "BID", "CASP3", "CASP8",
                                "CASP9", "CYCS", "APAF1", "FADD"],
        "HALLMARK_MTORC1_SIGNALING": ["SLC7A5", "SLC3A2", "DDIT4", "VEGFA", "HK2",
                                       "PKM", "LDHA", "SLC2A1", "RPS6", "EIF4E"],
        "HALLMARK_MYC_TARGETS_V1": ["ODC1", "LDHA", "CDK4", "NCL", "NPM1", "NOP56",
                                     "BOP1", "MRTO4", "RRP12", "WDR12"],
        "HALLMARK_E2F_TARGETS": ["CCNE1", "MCM2", "PCNA", "RRM2", "MCM3", "MCM4",
                                  "MCM5", "MCM6", "CDC6", "ORC1"],
        "HALLMARK_G2M_CHECKPOINT": ["CDK1", "CCNB1", "CCNB2", "BUB1", "BUB1B",
                                     "AURKA", "AURKB", "PLK1", "TOP2A", "BIRC5"],
        "HALLMARK_DNA_REPAIR": ["BRCA1", "BRCA2", "RAD51", "ATM", "ATR", "CHEK1",
                                 "CHEK2", "MSH2", "MSH6", "MLH1"],
        "HALLMARK_INFLAMMATORY_RESPONSE": ["TNF", "IL6", "IL1B", "CXCL8", "CCL2",
                                            "ICAM1", "VCAM1", "SELE", "PTGS2", "MMP9"],
        "HALLMARK_TNFA_SIGNALING_VIA_NFKB": ["NFKBIA", "TNF", "IL6", "CXCL8", "CCL2",
                                               "TNFAIP3", "BIRC3", "TRAF1", "RELB", "BCL3"],
        "HALLMARK_INTERFERON_GAMMA_RESPONSE": ["STAT1", "IRF1", "GBP1", "GBP2", "CXCL10",
                                                "CXCL9", "IDO1", "TAP1", "PSMB9", "B2M"],
        "HALLMARK_INTERFERON_ALPHA_RESPONSE": ["ISG15", "MX1", "MX2", "IFIT1", "IFIT2",
                                                "IFIT3", "OAS1", "OAS2", "RSAD2", "IFI44L"],
        "HALLMARK_HYPOXIA": ["VEGFA", "SLC2A1", "LDHA", "PDK1", "BNIP3", "DDIT4",
                              "ENO1", "PGK1", "ALDOA", "HK2"],
        "HALLMARK_GLYCOLYSIS": ["HK2", "PFKM", "ALDOA", "GAPDH", "PKM", "LDHA",
                                 "ENO1", "TPI1", "PGK1", "GPI"],
        "HALLMARK_OXIDATIVE_PHOSPHORYLATION": ["NDUFA1", "SDHA", "UQCRC1", "COX5A",
                                                "ATP5F1A", "NDUFS1", "SDHB", "COX7A2",
                                                "UQCRB", "ATP5F1B"],
        "HALLMARK_UNFOLDED_PROTEIN_RESPONSE": ["HSPA5", "DDIT3", "ATF4", "XBP1",
                                                "HERPUD1", "DNAJB9", "PDIA4", "ERN1",
                                                "ATF6", "EDEM1"],
        "HALLMARK_WNT_BETA_CATENIN_SIGNALING": ["CTNNB1", "LEF1", "TCF7", "MYC",
                                                  "CCND1", "AXIN2", "DKK1", "WNT3A",
                                                  "FZD1", "LRP6"],
        "HALLMARK_NOTCH_SIGNALING": ["NOTCH1", "HES1", "HEY1", "JAG1", "DLL1",
                                      "RBPJ", "MAML1", "NRARP", "DTX1", "HEYL"],
        "HALLMARK_HEDGEHOG_SIGNALING": ["SHH", "SMO", "PTCH1", "GLI1", "GLI2",
                                         "GLI3", "SUFU", "HHIP", "GAS1", "BOC"],
        "HALLMARK_EPITHELIAL_MESENCHYMAL_TRANSITION": ["VIM", "CDH2", "FN1", "SNAI1",
                                                        "SNAI2", "TWIST1", "ZEB1", "ZEB2",
                                                        "MMP2", "MMP9"],
        "HALLMARK_ANGIOGENESIS": ["VEGFA", "KDR", "FLT1", "PECAM1", "ANGPT1",
                                   "ANGPT2", "TEK", "NRP1", "ENG", "HIF1A"],
    }
