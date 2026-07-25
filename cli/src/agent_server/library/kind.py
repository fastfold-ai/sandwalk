"""Map filename extensions to Library filter kinds."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

LibraryKind = Literal["image", "document", "structure", "code", "other"]

_IMAGE = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".tif",
    ".tiff",
    ".bmp",
}
_DOCUMENT = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
    ".md",
    ".csv",
    ".tsv",
    ".rtf",
}
_STRUCTURE = {
    ".pdb",
    ".cif",
    ".mmcif",
    ".bcif",
    ".sdf",
    ".mol",
    ".mol2",
}
_CODE = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".sh",
    ".bash",
    ".zsh",
    ".rs",
    ".go",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".r",
    ".ipynb",
    ".sql",
    ".html",
    ".css",
    ".xml",
}


def library_kind_for_name(name: str) -> LibraryKind:
    suffix = Path(name).suffix.lower()
    if suffix in _IMAGE:
        return "image"
    if suffix in _DOCUMENT:
        return "document"
    if suffix in _STRUCTURE:
        return "structure"
    if suffix in _CODE:
        return "code"
    return "other"
