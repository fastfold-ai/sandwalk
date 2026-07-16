"""omics.atac_peak_annotate / chipseq_enrich. Split from tools/omics.py."""
from pathlib import Path

from tools import registry


@registry.register(
    name="omics.atac_peak_annotate",
    description="Annotate ATAC-seq peaks by genomic features and summarize accessibility landscape",
    category="omics",
    parameters={
        "path": "Path to peak file (BED-like CSV/TSV with chr, start, end columns or peak count matrix)",
    },
    usage_guide=(
        "Summarize ATAC-seq peak data: genomic distribution, peak sizes, "
        "chromosome distribution. Works on BED-like files or peak count matrices. "
        "Use after omics.geo_fetch to download ATAC-seq data."
    ),
)
def atac_peak_annotate(path: str, **kwargs) -> dict:
    """Annotate and summarize ATAC-seq peaks."""
    import pandas as pd

    filepath = Path(path).expanduser()
    if not filepath.exists():
        return {"error": f"File not found: {path}", "summary": f"File not found: {path}"}

    suffix = filepath.suffix.lower()
    sep = "," if suffix == ".csv" else "\t"

    try:
        df = pd.read_csv(filepath, sep=sep, comment="#")
    except Exception as exc:
        return {"error": f"Failed to read: {str(exc)[:200]}", "summary": f"Parse error: {str(exc)[:100]}"}

    # Detect BED-like format: look for chr/start/end columns
    col_lower = {c.lower(): c for c in df.columns}
    chr_col = col_lower.get("chr") or col_lower.get("chrom") or col_lower.get("chromosome")
    start_col = col_lower.get("start") or col_lower.get("chromstart")
    end_col = col_lower.get("end") or col_lower.get("chromend")

    # Also try positional (first 3 columns as chr, start, end)
    if not chr_col and len(df.columns) >= 3:
        first_col_vals = df.iloc[:, 0].astype(str)
        if first_col_vals.str.startswith("chr").mean() > 0.5:
            chr_col = df.columns[0]
            start_col = df.columns[1]
            end_col = df.columns[2]

    if chr_col and start_col and end_col:
        # BED-like format
        peaks = df[[chr_col, start_col, end_col]].copy()
        peaks.columns = ["chr", "start", "end"]
        peaks["start"] = pd.to_numeric(peaks["start"], errors="coerce")
        peaks["end"] = pd.to_numeric(peaks["end"], errors="coerce")
        peaks = peaks.dropna()
        peaks["width"] = peaks["end"] - peaks["start"]

        n_peaks = len(peaks)
        chr_counts = peaks["chr"].value_counts().head(24).to_dict()
        width_stats = {
            "mean": round(float(peaks["width"].mean()), 0),
            "median": round(float(peaks["width"].median()), 0),
            "min": int(peaks["width"].min()),
            "max": int(peaks["width"].max()),
        }

        # Estimate genomic feature distribution by peak width heuristic
        promoter_like = int((peaks["width"] < 500).sum())
        enhancer_like = int(((peaks["width"] >= 500) & (peaks["width"] < 2000)).sum())
        broad_peaks = int((peaks["width"] >= 2000).sum())

        return {
            "n_peaks": n_peaks,
            "chromosome_distribution": chr_counts,
            "peak_width_stats": width_stats,
            "promoter_like_peaks": promoter_like,
            "enhancer_like_peaks": enhancer_like,
            "broad_peaks": broad_peaks,
            "summary": (
                f"ATAC-seq: {n_peaks:,} peaks. Median width: {width_stats['median']:.0f} bp. "
                f"Estimated: {promoter_like:,} promoter-like (<500bp), "
                f"{enhancer_like:,} enhancer-like (500-2000bp), {broad_peaks:,} broad (>2000bp). "
                f"Top chromosomes: {', '.join(f'{k}:{v}' for k, v in list(chr_counts.items())[:5])}"
            ),
        }
    else:
        # Peak count matrix (peaks x samples)
        n_peaks, n_samples = df.shape
        return {
            "n_peaks": n_peaks,
            "n_samples": n_samples,
            "columns": list(df.columns[:20]),
            "summary": (
                f"ATAC-seq count matrix: {n_peaks:,} peaks x {n_samples} samples. "
                f"Use omics.chromatin_accessibility for differential analysis."
            ),
        }


# ---------------------------------------------------------------------------
@registry.register(
    name="omics.chipseq_enrich",
    description="Enrichment analysis of ChIP-seq target genes",
    category="omics",
    parameters={
        "path": "Path to peak file with gene annotations (CSV/TSV with a gene column)",
        "gene_column": "Column name containing gene symbols (default auto-detect)",
    },
    usage_guide=(
        "Extract target genes from ChIP-seq peak annotations and run pathway "
        "enrichment. Works on peak files that include nearest-gene annotations."
    ),
)
def chipseq_enrich(path: str, gene_column: str = "", **kwargs) -> dict:
    """Enrichment analysis of ChIP-seq target genes."""
    import pandas as pd

    filepath = Path(path).expanduser()
    if not filepath.exists():
        return {"error": f"File not found: {path}", "summary": f"File not found: {path}"}

    suffix = filepath.suffix.lower()
    sep = "," if suffix == ".csv" else "\t"
    try:
        df = pd.read_csv(filepath, sep=sep, comment="#")
    except Exception as exc:
        return {"error": f"Failed to read: {str(exc)[:200]}", "summary": f"Parse error: {str(exc)[:100]}"}

    # Auto-detect gene column
    if gene_column and gene_column in df.columns:
        gcol = gene_column
    else:
        candidates = ["gene", "gene_name", "symbol", "gene_symbol", "nearest_gene",
                       "GENE", "Gene", "SYMBOL", "geneName"]
        gcol = None
        for c in candidates:
            if c in df.columns:
                gcol = c
                break
        if gcol is None:
            # Try case-insensitive
            col_lower = {c.lower(): c for c in df.columns}
            for c in ["gene", "gene_name", "symbol"]:
                if c in col_lower:
                    gcol = col_lower[c]
                    break

    if gcol is None:
        return {
            "error": "No gene column found. Provide gene_column parameter.",
            "available_columns": list(df.columns[:20]),
            "summary": f"Could not auto-detect gene column. Columns: {', '.join(df.columns[:10])}",
        }

    genes = df[gcol].dropna().unique().tolist()
    genes = [str(g).strip() for g in genes if str(g).strip() and str(g).strip().upper() != "NAN"]

    if not genes:
        return {"error": "No genes found in column", "summary": "Empty gene list after filtering"}

    # Delegate to Enrichr
    from tools.omics_proteomics_enrich import proteomics_enrich

    return proteomics_enrich(proteins=",".join(genes), **kwargs)
