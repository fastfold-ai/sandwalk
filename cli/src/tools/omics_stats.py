"""omics: sample-group parsing, FDR, and gene-list helpers. Split from tools/omics.py."""
from pathlib import Path


def _parse_sample_groups(
    df,
    group1: str = "",
    group2: str = "",
    *,
    auto_grouping: bool = False,
    min_group_size: int = 2,
    group_names: tuple[str, str] = ("group1", "group2"),
) -> tuple[list[str], list[str], dict | None]:
    """Resolve and validate group sample assignments for two-group comparisons."""
    all_samples = [str(c) for c in df.columns]
    g1_label, g2_label = group_names
    g1_samples = [s.strip() for s in group1.split(",") if s.strip()] if group1 else []
    g2_samples = [s.strip() for s in group2.split(",") if s.strip()] if group2 else []

    # Require explicit groups unless user opts in to auto-splitting.
    if not g1_samples and not g2_samples:
        if not auto_grouping:
            return [], [], {
                "error": (
                    f"Explicit sample groups are required. Provide {g1_label} and {g2_label} "
                    "as comma-separated sample names. "
                    "Set auto_grouping=True only for quick exploratory analysis."
                ),
                "available_samples": all_samples[:30],
                "n_samples": len(all_samples),
                "summary": (
                    f"No groups provided. Define {g1_label}/{g2_label} using sample names "
                    f"(found {len(all_samples)} samples)."
                ),
            }

        if len(all_samples) < (min_group_size * 2):
            return [], [], {
                "error": (
                    f"Need at least {min_group_size * 2} samples for auto_grouping "
                    f"({min_group_size} per group), found {len(all_samples)}."
                ),
                "available_samples": all_samples[:30],
                "summary": f"Too few samples for auto_grouping: {len(all_samples)}",
            }

        mid = len(all_samples) // 2
        g1_samples = all_samples[:mid]
        g2_samples = all_samples[mid:]

    elif (g1_samples and not g2_samples) or (g2_samples and not g1_samples):
        return [], [], {
            "error": f"Both {g1_label} and {g2_label} must be provided together.",
            "available_samples": all_samples[:30],
            "summary": f"Incomplete group definition: need both {g1_label} and {g2_label}",
        }

    missing = [s for s in (g1_samples + g2_samples) if s not in all_samples]
    if missing:
        return [], [], {
            "error": f"Samples not found: {missing}",
            "available_samples": all_samples[:30],
            "summary": f"Sample names not found in matrix. Available: {', '.join(all_samples[:10])}",
        }

    overlap = sorted(set(g1_samples).intersection(g2_samples))
    if overlap:
        return [], [], {
            "error": f"Samples cannot appear in both groups: {overlap}",
            "summary": "Group overlap detected",
        }

    if len(g1_samples) < min_group_size or len(g2_samples) < min_group_size:
        return [], [], {
            "error": (
                f"Each group needs at least {min_group_size} samples. "
                f"Got {g1_label}={len(g1_samples)}, {g2_label}={len(g2_samples)}."
            ),
            "summary": "Insufficient replicates per group",
        }

    return g1_samples, g2_samples, None


def _fdr_correct(pvalues):
    """Benjamini-Hochberg FDR correction. Returns array of q-values."""
    import numpy as np

    pvals = np.asarray(pvalues, dtype=float)
    n = len(pvals)
    if n == 0:
        return pvals
    ranked = pvals.argsort().argsort() + 1  # 1-based rank
    qvals = pvals * n / ranked
    # Enforce monotonicity (from largest p-value down)
    order = pvals.argsort()[::-1]
    qvals_sorted = qvals[order]
    for i in range(1, len(qvals_sorted)):
        if qvals_sorted[i] > qvals_sorted[i - 1]:
            qvals_sorted[i] = qvals_sorted[i - 1]
    qvals[order] = qvals_sorted
    return np.clip(qvals, 0, 1)


def _parse_gene_list_file(path: str) -> tuple[set[str], str | None]:
    """Load a gene list from text/CSV/TSV file and return an uppercase gene set."""
    import pandas as pd

    fp = Path(path).expanduser()
    if not fp.exists():
        return set(), f"Background file not found: {path}"

    suffix = fp.suffix.lower()
    try:
        if suffix == ".txt":
            genes = {
                line.strip().split("\t")[0].split(",")[0].strip().upper()
                for line in fp.read_text(errors="replace").splitlines()
                if line.strip()
            }
            return {g for g in genes if g}, None

        if suffix in {".csv", ".tsv"}:
            sep = "," if suffix == ".csv" else "\t"
            df = pd.read_csv(fp, sep=sep)
            if df.empty:
                return set(), f"Background file is empty: {path}"
            first_col = df.columns[0]
            genes = {
                str(v).strip().upper()
                for v in df[first_col].dropna().tolist()
                if str(v).strip()
            }
            return genes, None

        # Fallback: treat as newline-delimited text.
        genes = {
            line.strip().split("\t")[0].split(",")[0].strip().upper()
            for line in fp.read_text(errors="replace").splitlines()
            if line.strip()
        }
        return {g for g in genes if g}, None
    except Exception as exc:
        return set(), f"Failed to parse background file: {str(exc)[:200]}"


def _enrichr_libraries_for_organism(organism: str) -> tuple[list[str] | None, str | None]:
    """Map organism names to Enrichr libraries."""
    org = (organism or "Homo sapiens").strip().lower()
    human_aliases = {"human", "homo sapiens", "hs", "h. sapiens"}
    mouse_aliases = {"mouse", "mus musculus", "mm", "m. musculus"}

    if org in human_aliases:
        return ["KEGG_2021_Human", "Reactome_2022", "GO_Biological_Process_2023"], None
    if org in mouse_aliases:
        return ["KEGG_2021_Mouse", "WikiPathway_2021_Mouse", "GO_Biological_Process_2023"], None
    return None, (
        f"Unsupported organism '{organism}'. "
        "Supported: Homo sapiens, Mus musculus."
    )
