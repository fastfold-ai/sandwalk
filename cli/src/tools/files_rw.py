"""
files.read_file / edit_file / create_file / delete_file tools.

Split from tools/files.py.
"""

from pathlib import Path

from tools import registry
from tools.files_paths import _is_allowed, _is_protected, _is_within_cwd


@registry.register(
    name="files.read_file",
    description="Read a text file and return its contents",
    category="files",
    parameters={"path": "Path to the file to read"},
    usage_guide=(
        "Use to read data files, prior reports, configuration files, or any file in the "
        "current working directory. Also reads from ~/.sandwalk/ and configured data directories."
    ),
)
def read_file(path: str, _session=None, **kwargs) -> dict:
    """Read a text file and return its contents."""
    config = _session.config if _session else None
    p = Path(path).expanduser()

    if not _is_allowed(p, config) and not _is_within_cwd(p):
        return {
            "summary": f"Access denied: {path} is outside allowed directories.",
            "error": "path_not_allowed",
        }

    if _is_protected(p):
        return {
            "summary": f"Access denied: {path} is a protected file.",
            "error": "path_protected",
        }

    if not p.exists():
        return {
            "summary": f"File not found: {path}",
            "error": "file_not_found",
        }

    try:
        content = p.read_text(encoding="utf-8")
        lines = content.count("\n") + 1
        return {
            "summary": f"Read {p.name} ({lines} lines, {len(content)} chars).",
            "path": str(p),
            "content": content,
            "lines": lines,
        }
    except UnicodeDecodeError:
        # Handle common binary tabular formats with a structured preview
        # rather than hard-failing decode.
        suffix = p.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            try:
                import pandas as pd

                xls = pd.ExcelFile(p)
                sheet_names = xls.sheet_names
                if not sheet_names:
                    return {
                        "summary": f"Excel file has no sheets: {p.name}",
                        "path": str(p),
                        "sheets": [],
                    }

                df = pd.read_excel(p, sheet_name=sheet_names[0], nrows=50)
                rows = len(df)
                cols = [str(c) for c in df.columns]
                preview = df.head(5).to_dict(orient="records")
                return {
                    "summary": (
                        f"Read Excel file {p.name}: {len(sheet_names)} sheet(s), "
                        f"previewed '{sheet_names[0]}' ({rows} rows, {len(cols)} columns in preview)."
                    ),
                    "path": str(p),
                    "format": "excel",
                    "sheets": sheet_names,
                    "sheet": sheet_names[0],
                    "columns": cols,
                    "rows_previewed": rows,
                    "preview": preview,
                }
            except Exception as e:
                return {"summary": f"Error reading Excel file {path}: {e}", "error": str(e)}
        return {
            "summary": (
                f"{p.name} appears to be a binary/non-UTF8 file. "
                "Use code.execute or a format-specific tool to parse it."
            ),
            "path": str(p),
            "error": "binary_file",
        }
    except Exception as e:
        return {"summary": f"Error reading {path}: {e}", "error": str(e)}


@registry.register(
    name="files.edit_file",
    description="Edit a file by replacing an exact string match with new content",
    category="files",
    parameters={
        "path": "Path to the file to edit (must be within CWD)",
        "old_string": "Exact string to find and replace (must be unique in the file)",
        "new_string": "Replacement string",
    },
    usage_guide=(
        "Use to make targeted edits to files in the current working directory. "
        "The old_string must appear exactly once in the file for unambiguous replacement."
    ),
)
def edit_file(path: str, old_string: str, new_string: str, **kwargs) -> dict:
    """Edit a file by exact string replacement."""
    p = Path(path).expanduser()

    if not _is_within_cwd(p):
        return {"summary": f"Access denied: {path} is outside working directory.", "error": "path_not_allowed"}
    if _is_protected(p):
        return {"summary": f"Protected path: {path} cannot be edited.", "error": "path_protected"}
    if not p.exists():
        return {"summary": f"File not found: {path}", "error": "file_not_found"}

    try:
        content = p.read_text(encoding="utf-8")
    except Exception as e:
        return {"summary": f"Error reading {path}: {e}", "error": str(e)}

    count = content.count(old_string)
    if count == 0:
        return {"summary": f"String not found in {p.name}.", "error": "string_not_found"}
    if count > 1:
        return {
            "summary": f"Ambiguous: '{old_string[:50]}...' appears {count} times in {p.name}. Provide more context.",
            "error": "ambiguous_match",
            "match_count": count,
        }

    new_content = content.replace(old_string, new_string, 1)
    try:
        p.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return {"summary": f"Error writing {path}: {e}", "error": str(e)}

    return {
        "summary": f"Edited {p.name}: replaced {len(old_string)} chars with {len(new_string)} chars.",
        "path": str(p.resolve()),
        "old_length": len(old_string),
        "new_length": len(new_string),
    }


@registry.register(
    name="files.create_file",
    description="Create a new file with the given content",
    category="files",
    parameters={
        "path": "Path for the new file (must be within CWD)",
        "content": "Content to write to the file",
    },
    usage_guide=(
        "Use to create new files (scripts, configs, data files) in the working directory. "
        "Will not overwrite existing files — use edit_file for modifications."
    ),
)
def create_file(path: str, content: str, **kwargs) -> dict:
    """Create a new file. Refuses to overwrite existing files."""
    p = Path(path).expanduser()

    if not _is_within_cwd(p):
        return {"summary": f"Access denied: {path} is outside working directory.", "error": "path_not_allowed"}
    if _is_protected(p):
        return {"summary": f"Protected path: {path} cannot be created.", "error": "path_protected"}
    if p.exists():
        try:
            existing = p.read_text(encoding="utf-8")
            if existing == content:
                lines = content.count("\n") + 1
                return {
                    "summary": f"File already exists with identical content: {p.name}.",
                    "path": str(p.resolve()),
                    "lines": lines,
                    "size": len(content),
                    "unchanged": True,
                }
            return {"summary": f"File already exists: {path}. Use edit_file to modify.", "error": "file_exists"}
        except Exception:
            # Keep default behavior for non-text/unreadable files.
            pass
        return {"summary": f"File already exists: {path}. Use edit_file to modify.", "error": "file_exists"}

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    except Exception as e:
        return {"summary": f"Error creating {path}: {e}", "error": str(e)}

    lines = content.count("\n") + 1
    return {
        "summary": f"Created {p.name} ({lines} lines, {len(content)} chars).",
        "path": str(p.resolve()),
        "lines": lines,
        "size": len(content),
    }


@registry.register(
    name="files.delete_file",
    description="Delete a file from the working directory",
    category="files",
    parameters={"path": "Path to the file to delete (must be within CWD)"},
    usage_guide="Use to remove files from the working directory. Cannot delete directories.",
)
def delete_file(path: str, **kwargs) -> dict:
    """Delete a single file."""
    p = Path(path).expanduser()

    if not _is_within_cwd(p):
        return {"summary": f"Access denied: {path} is outside working directory.", "error": "path_not_allowed"}
    if _is_protected(p):
        return {"summary": f"Protected path: {path} cannot be deleted.", "error": "path_protected"}
    if not p.exists():
        return {"summary": f"File not found: {path}", "error": "file_not_found"}
    if p.is_dir():
        return {"summary": f"Cannot delete directory: {path}. Only files.", "error": "is_directory"}

    try:
        size = p.stat().st_size
        p.unlink()
    except Exception as e:
        return {"summary": f"Error deleting {path}: {e}", "error": str(e)}

    return {
        "summary": f"Deleted {p.name} ({size} bytes).",
        "path": str(p.resolve()),
    }
