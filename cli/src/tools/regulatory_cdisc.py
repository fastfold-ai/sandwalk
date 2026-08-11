"""regulatory.cdisc_lint: CDISC-like tabular dataset linting.

Split from tools/regulatory.py.
"""

from __future__ import annotations

from pathlib import Path

from tools import registry
from tools.regulatory_common import (
    _COLUMN_RE,
    _DOMAIN_REQUIRED,
    _infer_domain_from_path,
    _ISO8601_PARTIAL_RE,
    _issue,
    _read_tabular,
    _score_quality,
)


@registry.register(
    name="regulatory.cdisc_lint",
    description="Lint a CDISC-like tabular dataset for naming, key, required-variable, and date-format issues",
    category="regulatory",
    parameters={
        "dataset_path": "Path to SDTM/ADaM-like dataset file (.csv, .tsv, .parquet, .xpt)",
        "domain": "Optional expected domain (e.g., AE, DM, LB); auto-inferred when omitted",
        "required_columns": "Optional list of additional required column names",
        "strict": "If true, treat variable-name length violations as errors",
        "max_issues": "Maximum issues returned (default 100)",
    },
    usage_guide=(
        "Use before submission-package handoff to catch high-impact CDISC data quality issues early. "
        "Best for SDTM-like domains with STUDYID/USUBJID and --DTC fields."
    ),
)
def cdisc_lint(
    dataset_path: str,
    domain: str = "",
    required_columns: list[str] | None = None,
    strict: bool = False,
    max_issues: int = 100,
    **kwargs,
) -> dict:
    """Run pragmatic CDISC-style lint checks on a tabular dataset."""
    del kwargs

    if not dataset_path:
        return {"summary": "dataset_path is required.", "error": "missing_dataset_path"}

    path = Path(dataset_path).expanduser()
    if not path.exists():
        return {"summary": f"Dataset file not found: {path}", "error": "file_not_found"}
    if path.is_dir():
        return {"summary": f"dataset_path must be a file: {path}", "error": "path_is_directory"}

    frame, read_error = _read_tabular(path)
    if read_error:
        return {"summary": read_error, "error": "read_failed"}

    assert frame is not None  # For type checkers.

    issues: list[dict] = []
    n_rows = int(len(frame))
    n_cols = int(len(frame.columns))

    requested_domain = str(domain or "").strip().upper()
    inferred_domain = requested_domain or _infer_domain_from_path(path)

    columns = [str(c).strip() for c in frame.columns.tolist()]
    dup_cols = sorted({c for c in columns if columns.count(c) > 1})
    for col in dup_cols:
        _issue(issues, "error", "duplicate_column", f"Duplicate column name: {col}", field=col)

    for col in columns:
        if not _COLUMN_RE.match(col):
            _issue(
                issues,
                "error",
                "invalid_variable_name",
                "Variable names must be uppercase A-Z, 0-9, underscore, starting with a letter.",
                field=col,
            )
        if len(col) > 8:
            sev = "error" if strict else "warning"
            _issue(
                issues,
                sev,
                "variable_name_too_long",
                f"Variable name exceeds 8 characters ({len(col)}).",
                field=col,
            )

    required = ["STUDYID", "USUBJID"]
    if inferred_domain:
        required.append("DOMAIN")
    required.extend(_DOMAIN_REQUIRED.get(inferred_domain, []))
    if required_columns:
        required.extend([str(c).strip().upper() for c in required_columns if str(c).strip()])
    required = sorted(set(required))

    missing_required = [c for c in required if c not in columns]
    for col in missing_required:
        _issue(issues, "error", "missing_required_column", "Missing required column.", field=col)

    if "DOMAIN" in columns and inferred_domain:
        observed = sorted(
            {
                str(v).strip().upper()
                for v in frame["DOMAIN"].dropna().astype(str).tolist()
                if str(v).strip()
            }
        )
        if observed and observed != [inferred_domain]:
            _issue(
                issues,
                "error",
                "domain_mismatch",
                f"DOMAIN values {observed} do not match expected domain {inferred_domain}.",
                field="DOMAIN",
            )

    if n_rows == 0:
        _issue(issues, "warning", "empty_dataset", "Dataset has zero rows.")

    # Missingness on required columns present in data.
    for col in required:
        if col not in frame.columns:
            continue
        series = frame[col]
        missing_count = int(series.isna().sum())
        if series.dtype == object:
            missing_count += int(series.astype(str).str.strip().eq("").sum())
        if missing_count > 0:
            _issue(
                issues,
                "error",
                "required_column_missing_values",
                f"{missing_count} missing/blank values in required column.",
                field=col,
            )

    key_cols = [c for c in ["STUDYID", "USUBJID"] if c in frame.columns]
    seq_col = f"{inferred_domain}SEQ" if inferred_domain else ""
    if seq_col and seq_col in frame.columns:
        key_cols.append(seq_col)
    if len(key_cols) >= 2 and n_rows > 0:
        dup_rows = int(frame.duplicated(subset=key_cols).sum())
        if dup_rows > 0:
            _issue(
                issues,
                "error",
                "duplicate_keys",
                f"{dup_rows} duplicate rows detected for key {key_cols}.",
            )

    date_cols = [c for c in columns if c.endswith("DTC")]
    for col in date_cols:
        raw = frame[col].dropna().astype(str).str.strip()
        if len(raw) == 0:
            continue
        bad = raw[~raw.str.match(_ISO8601_PARTIAL_RE, na=False)]
        if len(bad) > 0:
            _issue(
                issues,
                "error",
                "invalid_datetime_format",
                f"{len(bad)} values are not ISO8601/partial ISO8601 compliant.",
                field=col,
            )

    n_errors = sum(1 for x in issues if x["severity"] == "error")
    n_warnings = sum(1 for x in issues if x["severity"] == "warning")
    score = _score_quality(n_errors, n_warnings)
    max_issues = max(1, int(max_issues or 100))

    summary = (
        f"CDISC lint for {path.name}: {n_errors} error(s), {n_warnings} warning(s), "
        f"quality score {score}/100."
    )

    return {
        "summary": summary,
        "dataset_path": str(path),
        "domain": inferred_domain or None,
        "n_rows": n_rows,
        "n_columns": n_cols,
        "required_columns_checked": required,
        "error_count": n_errors,
        "warning_count": n_warnings,
        "quality_score": score,
        "issues": issues[:max_issues],
    }
