"""omics.deseq2 setup: load counts/metadata and validate the requested contrast. Split from tools/omics.py."""
from tools import omics as _omics
from tools.omics_deseq2_helpers import _resolve_level_name


def prepare_deseq2_design(
    counts_path: str,
    metadata_path: str,
    condition_col: str,
    ref_level: str,
    test_level: str,
    covariates: str,
    infer_metadata: bool,
    prefilter_min_count: int,
    prefilter_min_samples: int,
) -> dict:
    """Load and validate deseq2 inputs.

    Returns a dict either containing an "error" key, or a "ctx" key with the
    prepared (counts, metadata, ref, test, covars, design_formula, ...) context.
    """
    import pandas as pd

    df, error = _omics._load_tabular(counts_path)
    if error:
        return {"error": error, "summary": f"Could not load counts: {error}"}

    if metadata_path:
        metadata, meta_error = _omics._load_tabular(metadata_path)
        if meta_error:
            return {"error": meta_error, "summary": f"Metadata load failed: {meta_error}"}
    else:
        if not infer_metadata:
            samples = list(df.columns)
            return {
                "error": (
                    "metadata_path is required for reliable DESeq2 analysis. "
                    "Set infer_metadata=True only for quick exploratory analysis."
                ),
                "available_samples": samples[:30],
                "summary": f"No metadata provided for {len(samples)} samples; cannot define conditions.",
            }

        # Exploratory-only mode: split samples into two halves.
        samples = list(df.columns)
        mid = len(samples) // 2
        if mid < 2:
            return {"error": "Need at least 4 samples (2 per group) without metadata", "summary": "Too few samples"}
        metadata = pd.DataFrame(
            {"condition": ["control"] * mid + ["treatment"] * (len(samples) - mid)},
            index=samples,
        )

    if condition_col not in metadata.columns:
        return {
            "error": f"Column '{condition_col}' not in metadata. Available: {list(metadata.columns)}",
            "summary": f"Missing condition column: {condition_col}",
        }

    # Align samples (drop metadata-only and counts-only samples deterministically)
    common = df.columns.intersection(metadata.index)
    if len(common) < 4:
        return {"error": f"Need \u22654 shared samples, found {len(common)}", "summary": "Too few matching samples"}
    counts = df[common]
    metadata = metadata.loc[common]

    # Optional pre-filtering to stabilize dispersion fitting and reduce noise.
    if prefilter_min_count > 0:
        required = max(int(prefilter_min_samples), 1)
        keep_mask = (counts >= int(prefilter_min_count)).sum(axis=1) >= required
        counts = counts.loc[keep_mask]
        if counts.empty:
            return {
                "error": "All genes were removed by prefilter.",
                "summary": "No genes left after prefilter; relax prefilter thresholds.",
            }

    levels = sorted(metadata[condition_col].unique())
    if len(levels) < 2:
        return {"error": "Need at least 2 condition levels", "summary": "Only one condition level found"}
    ref = _resolve_level_name(ref_level if ref_level else levels[0], levels)
    test = _resolve_level_name(test_level if test_level else levels[1], levels)
    if ref not in levels or test not in levels:
        return {
            "error": f"Requested contrast levels not found. Levels available: {levels}",
            "summary": f"Invalid contrast levels: ref={ref}, test={test}",
        }
    if ref == test:
        return {"error": "ref_level and test_level must be different", "summary": "Invalid contrast: identical levels"}

    n_ref = int((metadata[condition_col] == ref).sum())
    n_test = int((metadata[condition_col] == test).sum())
    if n_ref < 2 or n_test < 2:
        return {
            "error": f"Need at least 2 replicates per condition for {ref} vs {test} (found {n_ref} and {n_test})",
            "summary": "Insufficient biological replicates per condition",
        }

    # Build design formula with optional covariates.
    if isinstance(covariates, (list, tuple)):
        covars = [str(c).strip() for c in covariates if str(c).strip()]
    else:
        raw = str(covariates or "").strip()
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]
        covars = [c.strip().strip("'\"") for c in raw.split(",") if c.strip().strip("'\"")]
    missing_covars = [c for c in covars if c not in metadata.columns]
    if missing_covars:
        return {
            "error": f"Covariate column(s) not in metadata: {missing_covars}",
            "summary": f"Missing covariates: {', '.join(missing_covars)}",
        }
    design_terms = covars + [condition_col]
    design_formula = "~ " + " + ".join(design_terms)

    # Ensure categorical encoding for design variables. Coerce to string first
    # so mixed numeric/string covariates (e.g., batch IDs) convert cleanly
    # through pandas2ri into R factors.
    metadata = metadata.copy()
    for col in design_terms:
        metadata[col] = metadata[col].astype(str).astype("category")
    if ref in metadata[condition_col].cat.categories:
        ordered_levels = [ref] + [x for x in metadata[condition_col].cat.categories if x != ref]
        metadata[condition_col] = metadata[condition_col].cat.reorder_categories(ordered_levels)

    return {
        "ctx": {
            "counts": counts,
            "metadata": metadata,
            "ref": ref,
            "test": test,
            "covars": covars,
            "design_formula": design_formula,
            "n_ref": n_ref,
            "n_test": n_test,
            "n_shared_samples": int(len(common)),
        }
    }
