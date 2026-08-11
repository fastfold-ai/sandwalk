"""regulatory.submission_package_check: cross-file submission package checks.

Split from tools/regulatory.py. Calls ``cdisc_lint``/``define_xml_lint``
indirectly via the ``tools.regulatory`` hub module so that
``patch("tools.regulatory.cdisc_lint")`` / ``patch("tools.regulatory.define_xml_lint")``
in tests continue to work regardless of which submodule performs the call.
"""

from __future__ import annotations

from pathlib import Path

from tools import registry
from tools import regulatory as _regulatory
from tools.regulatory_common import _extract_leaf_hrefs, _issue, _score_quality


@registry.register(
    name="regulatory.submission_package_check",
    description="Run cross-file submission package checks across datasets and Define-XML",
    category="regulatory",
    parameters={
        "package_dir": "Submission package root directory",
        "define_xml_path": "Optional explicit define.xml path (auto-discovered when omitted)",
        "max_datasets": "Maximum dataset files to lint (default 30)",
        "strict": "If true, tighten checks (warnings promoted where applicable)",
    },
    usage_guide=(
        "Use before external handoff to validate end-to-end package consistency: "
        "Define-XML integrity, dataset linting, and cross-file reference checks."
    ),
)
def submission_package_check(
    package_dir: str,
    define_xml_path: str = "",
    max_datasets: int = 30,
    strict: bool = False,
    **kwargs,
) -> dict:
    """Run cross-file validation for a submission package directory."""
    del kwargs
    if not package_dir:
        return {"summary": "package_dir is required.", "error": "missing_package_dir"}

    root = Path(package_dir).expanduser()
    if not root.exists():
        return {"summary": f"Package directory not found: {root}", "error": "package_not_found"}
    if not root.is_dir():
        return {"summary": f"package_dir must be a directory: {root}", "error": "not_a_directory"}

    max_datasets = max(1, min(int(max_datasets or 30), 200))
    issues: list[dict] = []

    # Resolve define.xml
    define_paths = []
    if define_xml_path:
        candidate = Path(define_xml_path).expanduser()
        if not candidate.exists():
            _issue(issues, "error", "define_xml_missing", f"define_xml_path not found: {candidate}")
        else:
            define_paths = [candidate]
    else:
        define_paths = sorted(
            [p for p in root.rglob("*.xml") if "define" in p.name.lower()],
            key=lambda p: p.name.lower(),
        )
        if not define_paths:
            _issue(issues, "warning", "define_xml_not_found", "No define.xml discovered in package directory.")

    define_results = []
    for p in define_paths[:2]:
        lint = _regulatory.define_xml_lint(define_xml_path=str(p), strict=strict, max_issues=200)
        define_results.append(lint)
        if "error" in lint:
            _issue(issues, "error", "define_xml_lint_failed", lint["summary"], field=str(p))

    # Dataset discovery
    dataset_paths = sorted(
        [
            p
            for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in {".xpt", ".csv", ".tsv", ".parquet"}
        ]
    )
    if not dataset_paths:
        _issue(issues, "error", "no_datasets_found", "No dataset files (*.xpt/*.csv/*.tsv/*.parquet) found.")

    dataset_lints = []
    for p in dataset_paths[:max_datasets]:
        result = _regulatory.cdisc_lint(
            dataset_path=str(p),
            strict=strict,
            max_issues=50,
        )
        dataset_lints.append(result)
        if result.get("error_count", 0) > 0:
            _issue(
                issues,
                "error",
                "dataset_errors",
                f"{p.name}: {result.get('error_count', 0)} error(s) from CDISC lint.",
                field=str(p),
            )

    # Cross-file leaf href resolution against package files.
    referenced_files = set()
    missing_leaf_files = []
    for d in define_results:
        define_path = d.get("define_xml_path")
        if not define_path:
            continue
        hrefs, href_error = _extract_leaf_hrefs(Path(define_path))
        if href_error:
            _issue(
                issues,
                "warning",
                "leaf_parse_failed",
                f"Could not parse leaf href values for {define_path}: {href_error}",
            )
            continue
        base_dir = Path(define_path).parent
        for href in hrefs:
            normalized = href.replace("\\", "/").strip()
            referenced_files.add(normalized)
            candidate = (base_dir / normalized).resolve()
            if not candidate.exists():
                # Fallback check relative to package root.
                candidate = (root / normalized).resolve()
            if not candidate.exists():
                missing_leaf_files.append(normalized)

    for href in sorted(set(missing_leaf_files)):
        _issue(
            issues,
            "error",
            "missing_leaf_target",
            f"Define-XML leaf href does not resolve to a file in package: {href}",
        )

    # Orphan dataset warning: files that are present but not referenced in define.xml.
    if referenced_files:
        dataset_relpaths = {
            str(p.relative_to(root)).replace("\\", "/"): p
            for p in dataset_paths
            if p.is_file()
        }
        unreferenced = []
        ref_suffixes = {Path(x).name.lower() for x in referenced_files}
        for rel, path_obj in dataset_relpaths.items():
            if path_obj.name.lower() not in ref_suffixes:
                unreferenced.append(rel)
        for rel in sorted(unreferenced)[:20]:
            _issue(
                issues,
                "warning",
                "unreferenced_dataset",
                f"Dataset not referenced by define.xml leaf entries: {rel}",
            )

    n_errors = sum(1 for x in issues if x["severity"] == "error")
    n_warnings = sum(1 for x in issues if x["severity"] == "warning")
    readiness_score = _score_quality(n_errors, n_warnings)
    if n_errors == 0 and readiness_score >= 85:
        readiness = "ready"
    elif n_errors <= 3 and readiness_score >= 60:
        readiness = "needs_review"
    else:
        readiness = "not_ready"

    summary = (
        f"Submission package check for {root}: {readiness} "
        f"(score={readiness_score}/100, errors={n_errors}, warnings={n_warnings}). "
        f"Datasets linted: {len(dataset_lints)}/{len(dataset_paths)}."
    )

    return {
        "summary": summary,
        "package_dir": str(root),
        "readiness": readiness,
        "readiness_score": readiness_score,
        "error_count": n_errors,
        "warning_count": n_warnings,
        "define_xml_results": define_results,
        "dataset_lints": dataset_lints,
        "datasets_discovered": len(dataset_paths),
        "datasets_linted": len(dataset_lints),
        "issues": issues,
    }
