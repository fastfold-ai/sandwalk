"""
files.write_report / write_csv / list_outputs tools.

Split from tools/files.py.
"""

import csv
import io

from tools import registry
from tools.files_paths import _output_dir, _resolve_output_path


@registry.register(
    name="files.write_report",
    description="Write a report to the output directory",
    category="files",
    parameters={
        "content": "Report content (markdown text)",
        "filename": "Output filename (e.g., 'report.md')",
        "format": "Output format: 'markdown' (default) or 'text'",
        "overwrite": "Whether to overwrite existing file (default False)",
    },
    usage_guide=(
        "Use to save analysis results as a formatted report. "
        "Output goes to the configured output directory (./outputs by default)."
    ),
)
def write_report(content: str, filename: str = "report.md",
                 format: str = "markdown", overwrite: bool = False,
                 _session=None, **kwargs) -> dict:
    """Write a report to the output directory."""
    config = _session.config if _session else None
    out_dir = _output_dir(config)

    # Ensure filename has appropriate extension
    if format == "markdown" and not filename.endswith((".md", ".markdown")):
        filename = filename + ".md"

    out_path, error = _resolve_output_path(out_dir, filename)
    if error:
        return {
            "summary": f"Invalid filename '{filename}': {error}",
            "error": "invalid_filename",
        }

    if not overwrite and out_path.exists():
        suffix = "".join(out_path.suffixes)
        stem = out_path.name[: -len(suffix)] if suffix else out_path.name
        counter = 2
        candidate = out_path.parent / f"{stem}_{counter}{suffix}"
        while candidate.exists():
            counter += 1
            candidate = out_path.parent / f"{stem}_{counter}{suffix}"
        out_path = candidate

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        return {
            "summary": f"Report saved to {out_path}",
            "path": str(out_path),
            "size": len(content),
        }
    except Exception as e:
        return {"summary": f"Error writing report: {e}", "error": str(e)}


@registry.register(
    name="files.write_csv",
    description="Write structured data as a CSV file",
    category="files",
    parameters={
        "data": "List of dicts to write (each dict = one row)",
        "filename": "Output filename (e.g., 'results.csv')",
    },
    usage_guide=(
        "Use to export structured results (tables, rankings, gene lists) as CSV. "
        "Input is a list of dicts; keys become column headers."
    ),
)
def write_csv(data: list, filename: str = "results.csv",
              _session=None, **kwargs) -> dict:
    """Write structured data as CSV."""
    config = _session.config if _session else None
    out_dir = _output_dir(config)

    if not filename.endswith(".csv"):
        filename = filename + ".csv"

    out_path, error = _resolve_output_path(out_dir, filename)
    if error:
        return {
            "summary": f"Invalid filename '{filename}': {error}",
            "error": "invalid_filename",
        }

    if not data:
        return {"summary": "No data to write.", "error": "empty_data"}

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Get column headers from first row
        if isinstance(data[0], dict):
            fieldnames = list(data[0].keys())
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
            out_path.write_text(buf.getvalue(), encoding="utf-8")
        else:
            # Fallback: list of lists
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerows(data)
            out_path.write_text(buf.getvalue(), encoding="utf-8")

        return {
            "summary": f"CSV saved to {out_path} ({len(data)} rows).",
            "path": str(out_path),
            "rows": len(data),
        }
    except Exception as e:
        return {"summary": f"Error writing CSV: {e}", "error": str(e)}


@registry.register(
    name="files.list_outputs",
    description="List all files in the output directory",
    category="files",
    parameters={},
    usage_guide="Use to see what reports and exports have been generated this session.",
)
def list_outputs(_session=None, **kwargs) -> dict:
    """List all files in the output directory."""
    config = _session.config if _session else None
    out_dir = _output_dir(config)

    files = []
    if out_dir.exists():
        for p in sorted(out_dir.iterdir()):
            if p.is_file():
                files.append({
                    "name": p.name,
                    "size": p.stat().st_size,
                    "path": str(p),
                })

    if not files:
        return {"summary": f"Output directory is empty: {out_dir}", "files": []}

    listing = "\n".join(f"  {f['name']} ({f['size']} bytes)" for f in files)
    return {
        "summary": f"Output directory ({out_dir}):\n{listing}",
        "files": files,
        "directory": str(out_dir),
    }
