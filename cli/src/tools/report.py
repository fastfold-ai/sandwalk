"""
Report utility tools for decision-ready communication outputs.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from tools import registry
from tools.report_markdown import _build_brief_markdown, _extract_evidence_lines, _slug


@registry.register(
    name="report.pharma_brief",
    description="Generate a one-page pharma decision brief and optionally save as markdown/HTML",
    category="report",
    parameters={
        "query": "Original research question or program objective",
        "program_thesis": "Concise recommendation statement",
        "target_rationale": "Mechanistic rationale (optional)",
        "biomarker_strategy": "Biomarker/patient-selection strategy (optional)",
        "safety_review": "Top liabilities and mitigation strategy (optional)",
        "competitive_differentiation": "Differentiation thesis vs landscape (optional)",
        "evidence": "Optional evidence payload (string/list/dict) to anchor key bullets",
        "save": "Whether to save markdown brief to output directory (default True)",
        "publish_html": "Whether to also publish a shareable HTML page (default True)",
        "filename": "Optional output filename stem",
    },
    usage_guide=(
        "Use at the end of an analysis to create a board/investor/pharma-partner-ready brief "
        "with explicit thesis, risk, and differentiation framing."
    ),
)
def pharma_brief(
    query: str,
    program_thesis: str = "",
    target_rationale: str = "",
    biomarker_strategy: str = "",
    safety_review: str = "",
    competitive_differentiation: str = "",
    evidence=None,
    save: bool = True,
    publish_html: bool = True,
    filename: str = "",
    _session=None,
    **kwargs,
) -> dict:
    """Create a decision-ready pharma brief and optionally persist it."""
    del kwargs
    query = (query or "").strip()
    if not query:
        return {"summary": "query is required.", "error": "missing_query"}

    thesis = (program_thesis or "").strip() or "Recommendation pending deeper evidence synthesis."
    target_rationale = (target_rationale or "").strip() or "Mechanism rationale not yet specified."
    biomarker_strategy = (
        biomarker_strategy or ""
    ).strip() or "Biomarker strategy not yet specified."
    safety_review = (safety_review or "").strip() or "Safety review pending."
    competitive_differentiation = (
        competitive_differentiation or ""
    ).strip() or "Differentiation statement pending competitor benchmarking."

    evidence_lines = _extract_evidence_lines(evidence)[:12]
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    markdown = _build_brief_markdown(
        query,
        thesis,
        target_rationale,
        biomarker_strategy,
        safety_review,
        competitive_differentiation,
        evidence_lines,
        generated_at,
    )

    output_md = None
    output_html = None

    if save:
        output_base = None
        if _session is not None and getattr(_session, "config", None) is not None:
            output_base = _session.config.get("sandbox.output_dir")
        out_dir = (
            Path(output_base) / "reports" if output_base else Path.cwd() / "outputs" / "reports"
        )
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = _slug(filename or query)
        output_md = out_dir / f"{stem}_pharma_brief.md"
        counter = 2
        while output_md.exists():
            output_md = out_dir / f"{stem}_pharma_brief_{counter}.md"
            counter += 1
        output_md.write_text(markdown, encoding="utf-8")

        if publish_html:
            from reports.html import publish_report

            output_html = publish_report(output_md)

    summary = (
        f"Generated pharma brief for '{query}'."
        + (f" Saved: {output_md}" if output_md else "")
        + (f" HTML: {output_html}" if output_html else "")
    )

    return {
        "summary": summary,
        "query": query,
        "markdown": markdown,
        "markdown_path": str(output_md) if output_md else None,
        "html_path": str(output_html) if output_html else None,
    }
