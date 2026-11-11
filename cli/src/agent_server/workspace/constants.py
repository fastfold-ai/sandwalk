"""Shared text-file heuristics for the workspace service."""

from __future__ import annotations

from pathlib import Path

TEXT_SUFFIXES = {
    ".cif",
    ".css",
    ".csv",
    ".html",
    ".htm",
    ".j2",
    ".jinja",
    ".jinja2",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mmcif",
    ".pdb",
    ".py",
    ".bash",
    ".csh",
    ".fish",
    ".ksh",
    ".sbatch",
    ".sdf",
    ".sh",
    ".slurm",
    ".svg",
    ".toml",
    ".zsh",
    ".ts",
    ".tsv",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

# MIME types that are source/text but do not start with ``text/``.
# macOS reports ``job.sh`` as ``application/x-sh``.
TEXT_MIMES = {
    "application/javascript",
    "application/json",
    "application/toml",
    "application/x-csh",
    "application/x-sh",
    "application/x-shellscript",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
    "text/x-script.python",
    "text/x-sh",
    "text/x-shellscript",
}


def is_workspace_text(name: str, mime_type: str | None) -> bool:
    """True when a workspace file should be read and previewed as UTF-8 text."""
    mime = (mime_type or "").split(";", 1)[0].strip().lower()
    suffix = Path(name).suffix.lower()
    return mime.startswith("text/") or mime in TEXT_MIMES or suffix in TEXT_SUFFIXES
