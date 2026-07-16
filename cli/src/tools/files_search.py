"""
files.list_directory / search_files / search_content tools.

Split from tools/files.py.
"""

import re
from pathlib import Path

from tools import registry
from tools.files_paths import _is_allowed, _is_within_cwd


@registry.register(
    name="files.list_directory",
    description="List directory entries with metadata",
    category="files",
    parameters={
        "path": "Directory path to inspect (default CWD)",
        "recursive": "If true, recurse through subdirectories (default false)",
        "max_entries": "Maximum entries to return (default 200)",
        "show_hidden": "Include dotfiles/directories (default false)",
    },
    usage_guide="Use to inspect workspace structure before reading or modifying files.",
)
def list_directory(
    path: str = "",
    recursive: bool = False,
    max_entries: int = 200,
    show_hidden: bool = False,
    **kwargs,
) -> dict:
    """List directory contents in a safe, bounded way."""
    base = Path(path).expanduser() if path else Path.cwd()
    # If absolute path is outside CWD or doesn't exist, try the basename under CWD
    if not base.exists() or not _is_within_cwd(base):
        if path:
            cwd_candidate = Path.cwd() / Path(path).name
            if cwd_candidate.exists() and cwd_candidate.is_dir():
                base = cwd_candidate
    if not _is_within_cwd(base) and base != Path.cwd():
        # Check if it's in allowed paths (extra_read_dirs, data dirs)
        config = getattr(kwargs.get("_session"), "config", None) if kwargs.get("_session") else None
        if not _is_allowed(base, config):
            return {"summary": f"Access denied: {path} is outside working directory.", "error": "path_not_allowed"}
    if not base.exists():
        return {"summary": f"Path not found: {base}", "error": "file_not_found"}
    if not base.is_dir():
        return {"summary": f"Not a directory: {base}", "error": "not_directory"}

    max_entries = min(max(int(max_entries), 1), 1000)
    cwd = Path.cwd().resolve()
    entries = []

    iterator = base.rglob("*") if recursive else base.iterdir()
    try:
        for p in sorted(iterator):
            name = p.name
            if not show_hidden and name.startswith("."):
                continue
            try:
                rel = str(p.resolve().relative_to(cwd))
            except ValueError:
                continue
            item = {
                "path": rel,
                "name": name,
                "type": "dir" if p.is_dir() else "file",
            }
            if p.is_file():
                try:
                    item["size"] = p.stat().st_size
                except OSError:
                    item["size"] = None
            entries.append(item)
            if len(entries) >= max_entries:
                break
    except Exception as e:
        return {"summary": f"Error listing directory: {e}", "error": str(e)}

    return {
        "summary": f"Listed {len(entries)} entries under {base}",
        "entries": entries,
        "count": len(entries),
        "directory": str(base.resolve()),
    }


@registry.register(
    name="files.search_files",
    description="Search for files by glob pattern within the working directory",
    category="files",
    parameters={
        "pattern": "Glob pattern (e.g., '**/*.py', '*.csv', 'src/**/*.ts')",
        "path": "Subdirectory to search in (default: CWD)",
    },
    usage_guide="Use to find files by name pattern. Returns file paths, names, and sizes.",
)
def search_files(pattern: str, path: str = "", **kwargs) -> dict:
    """Glob-based file search within CWD."""
    base = Path(path).expanduser() if path else Path.cwd()

    if not _is_within_cwd(base) and base != Path.cwd():
        return {"summary": f"Access denied: {path} is outside working directory.", "error": "path_not_allowed"}

    try:
        cwd = Path.cwd().resolve()
        matches = []
        for p in sorted(base.glob(pattern)):
            if p.is_file():
                try:
                    rel = str(p.resolve().relative_to(cwd))
                except ValueError:
                    continue  # Skip files outside CWD
                matches.append({
                    "path": str(p.resolve()),
                    "name": p.name,
                    "relative": rel,
                    "size": p.stat().st_size,
                })
                if len(matches) >= 100:
                    break
    except Exception as e:
        return {"summary": f"Search error: {e}", "error": str(e)}

    if not matches:
        return {"summary": f"No files matching '{pattern}'.", "files": [], "count": 0}

    listing = "\n".join(f"  {m['relative']} ({m['size']} bytes)" for m in matches[:20])
    more = f"\n  ... and {len(matches) - 20} more" if len(matches) > 20 else ""
    return {
        "summary": f"Found {len(matches)} files matching '{pattern}':\n{listing}{more}",
        "files": matches,
        "count": len(matches),
    }


@registry.register(
    name="files.search_content",
    description="Search file contents by regex pattern (like grep)",
    category="files",
    parameters={
        "pattern": "Regex pattern to search for",
        "path": "Subdirectory to search in (default: CWD)",
        "glob": "File glob filter (default: '**/*')",
        "max_results": "Maximum matches to return (default: 50)",
    },
    usage_guide=(
        "Use to search for text patterns across files — find function definitions, "
        "variable usage, TODOs, error messages, etc. Skips binary and large files."
    ),
)
def search_content(pattern: str, path: str = "", glob: str = "**/*",
                   max_results: int = 50, **kwargs) -> dict:
    """Regex content search across files in CWD."""
    base = Path(path).expanduser() if path else Path.cwd()

    if not _is_within_cwd(base) and base != Path.cwd():
        return {"summary": f"Access denied: {path} is outside working directory.", "error": "path_not_allowed"}

    try:
        compiled = re.compile(pattern)
    except re.error as e:
        return {"summary": f"Invalid regex: {e}", "error": str(e)}

    cwd = Path.cwd().resolve()
    matches = []
    files_searched = 0

    try:
        for fp in sorted(base.glob(glob)):
            if not fp.is_file():
                continue
            # Skip large files (>1MB) and likely binary files
            try:
                size = fp.stat().st_size
            except OSError:
                continue
            if size > 1_000_000:
                continue
            # Skip common binary extensions
            if fp.suffix.lower() in ('.pyc', '.pyo', '.so', '.dll', '.exe', '.bin',
                                     '.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf',
                                     '.zip', '.tar', '.gz', '.bz2', '.whl', '.egg'):
                continue

            try:
                content = fp.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            files_searched += 1
            for line_num, line in enumerate(content.splitlines(), 1):
                if compiled.search(line):
                    try:
                        rel = str(fp.resolve().relative_to(cwd))
                    except ValueError:
                        continue
                    preview = line.strip()
                    if len(preview) > 200:
                        preview = preview[:197] + "..."
                    matches.append({
                        "file": rel,
                        "line": line_num,
                        "text": preview,
                    })
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break
    except Exception as e:
        return {"summary": f"Search error: {e}", "error": str(e)}

    if not matches:
        return {
            "summary": f"No matches for '{pattern}' in {files_searched} files.",
            "matches": [],
            "count": 0,
            "files_searched": files_searched,
        }

    listing = "\n".join(f"  {m['file']}:{m['line']}: {m['text']}" for m in matches[:15])
    more = f"\n  ... and {len(matches) - 15} more" if len(matches) > 15 else ""
    return {
        "summary": f"Found {len(matches)} matches for '{pattern}' across {files_searched} files:\n{listing}{more}",
        "matches": matches,
        "count": len(matches),
        "files_searched": files_searched,
    }
