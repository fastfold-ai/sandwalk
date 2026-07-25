"""Shared limits and text-file heuristics for the workspace service."""

from __future__ import annotations

MAX_FILE_SIZE = 40 * 1024 * 1024
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
    ".sdf",
    ".svg",
    ".toml",
    ".ts",
    ".tsv",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
