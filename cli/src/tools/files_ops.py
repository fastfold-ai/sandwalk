"""
files.move_file / copy_file / create_directory / extract_archive tools.

Split from tools/files.py.
"""

import shutil
from pathlib import Path

from tools import registry
from tools.files_paths import _is_protected, _resolve_cwd_path


@registry.register(
    name="files.move_file",
    description="Move or rename a file within the working directory",
    category="files",
    parameters={
        "source_path": "Path to source file (must be within CWD)",
        "dest_path": "Path to destination file (must be within CWD)",
        "overwrite": "Whether to overwrite destination if it exists (default false)",
    },
    usage_guide=(
        "Use to rename files or reorganize outputs in the workspace. "
        "Both source and destination must stay inside the current working directory."
    ),
)
def move_file(source_path: str, dest_path: str, overwrite: bool = False, **kwargs) -> dict:
    """Move a file safely within CWD."""
    src, err = _resolve_cwd_path(source_path)
    if err:
        return {"summary": f"Access denied: {source_path} is outside working directory.", "error": err}
    dst, err = _resolve_cwd_path(dest_path)
    if err:
        return {"summary": f"Access denied: {dest_path} is outside working directory.", "error": err}
    if _is_protected(src) or _is_protected(dst):
        return {"summary": "Protected path cannot be moved.", "error": "path_protected"}
    if not src.exists():
        return {"summary": f"File not found: {source_path}", "error": "file_not_found"}
    if src.is_dir():
        return {"summary": f"Source is a directory: {source_path}", "error": "is_directory"}
    if dst.exists() and not overwrite:
        return {"summary": f"Destination exists: {dest_path}", "error": "file_exists"}
    if dst.exists() and dst.is_dir():
        return {"summary": f"Destination is a directory: {dest_path}", "error": "is_directory"}
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.replace(dst)
    except Exception as e:
        return {"summary": f"Error moving file: {e}", "error": str(e)}
    return {"summary": f"Moved {src.name} to {dst}", "source": str(src), "destination": str(dst)}


@registry.register(
    name="files.copy_file",
    description="Copy a file within the working directory",
    category="files",
    parameters={
        "source_path": "Path to source file (must be within CWD)",
        "dest_path": "Path to destination file (must be within CWD)",
        "overwrite": "Whether to overwrite destination if it exists (default false)",
    },
    usage_guide=(
        "Use to duplicate templates, data files, or reports in the workspace "
        "without editing the original."
    ),
)
def copy_file(source_path: str, dest_path: str, overwrite: bool = False, **kwargs) -> dict:
    """Copy a file safely within CWD."""
    src, err = _resolve_cwd_path(source_path)
    if err:
        return {"summary": f"Access denied: {source_path} is outside working directory.", "error": err}
    dst, err = _resolve_cwd_path(dest_path)
    if err:
        return {"summary": f"Access denied: {dest_path} is outside working directory.", "error": err}
    if _is_protected(src) or _is_protected(dst):
        return {"summary": "Protected path cannot be copied.", "error": "path_protected"}
    if not src.exists():
        return {"summary": f"File not found: {source_path}", "error": "file_not_found"}
    if src.is_dir():
        return {"summary": f"Source is a directory: {source_path}", "error": "is_directory"}
    if dst.exists() and not overwrite:
        return {"summary": f"Destination exists: {dest_path}", "error": "file_exists"}
    if dst.exists() and dst.is_dir():
        return {"summary": f"Destination is a directory: {dest_path}", "error": "is_directory"}
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    except Exception as e:
        return {"summary": f"Error copying file: {e}", "error": str(e)}
    return {"summary": f"Copied {src.name} to {dst}", "source": str(src), "destination": str(dst)}


@registry.register(
    name="files.create_directory",
    description="Create a directory within the working directory",
    category="files",
    parameters={
        "path": "Directory path to create (must be within CWD)",
        "exist_ok": "If true, do not error when directory already exists (default true)",
    },
    usage_guide="Use to create folders for outputs, reports, and structured project organization.",
)
def create_directory(path: str, exist_ok: bool = True, **kwargs) -> dict:
    """Create a directory safely within CWD."""
    p, err = _resolve_cwd_path(path)
    if err:
        return {"summary": f"Access denied: {path} is outside working directory.", "error": err}
    if _is_protected(p):
        return {"summary": f"Protected path: {path} cannot be created.", "error": "path_protected"}
    if p.exists() and p.is_file():
        return {"summary": f"Path exists as a file: {path}", "error": "is_file"}
    try:
        p.mkdir(parents=True, exist_ok=bool(exist_ok))
    except FileExistsError:
        return {"summary": f"Directory already exists: {path}", "error": "file_exists"}
    except Exception as e:
        return {"summary": f"Error creating directory: {e}", "error": str(e)}
    return {"summary": f"Directory ready: {p}", "path": str(p.resolve())}


@registry.register(
    name="files.extract_archive",
    description=(
        "Extract a ZIP, tar, tar.gz, or tar.bz2 archive. "
        "Supports extracting the full archive or specific files by pattern."
    ),
    category="files",
    parameters={
        "path": "Path to the archive file",
        "destination": "Directory to extract into (default: current working directory)",
        "pattern": "Optional glob pattern to extract only matching files (e.g. '*.mafft', '156083at2759*')",
    },
    usage_guide=(
        "Use to extract ZIP, tar, tar.gz, or tar.bz2 archives. Safer and more reliable "
        "than shell.run for archive extraction. Supports selective extraction via pattern."
    ),
)
def extract_archive(
    path: str,
    destination: str = ".",
    pattern: str = "",
    _session=None,
    **kwargs,
) -> dict:
    """Extract an archive file."""
    import fnmatch
    import logging
    import tarfile
    import zipfile
    _log = logging.getLogger("tools.files")
    _log.debug("extract_archive: path=%r destination=%r pattern=%r kwargs=%r", path, destination, pattern, kwargs)

    src = Path(path).expanduser()
    if not src.exists():
        # Try relative to extra_read_dirs
        config = _session.config if _session else None
        if config:
            extra = config.get("sandbox.extra_read_dirs")
            if extra:
                for d in str(extra).split(","):
                    candidate = Path(d.strip()) / path
                    if candidate.exists():
                        src = candidate
                        break
    if not src.exists():
        return {"summary": f"Archive not found: {path}", "error": "file_not_found"}

    # Sanitize destination: only allow relative paths under CWD
    dest = Path(destination)
    cwd = Path.cwd()
    if dest.is_absolute():
        try:
            dest.resolve().relative_to(cwd.resolve())
        except ValueError:
            # Absolute path outside CWD — ignore it, use CWD
            _log.warning("Ignoring absolute destination %s, extracting to CWD", dest)
            dest = cwd
    else:
        # Relative path — resolve relative to CWD
        dest = cwd / dest
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        _log.warning("Permission denied for %s, falling back to CWD", dest)
        dest = cwd

    extracted = []
    try:
        if src.suffix == ".zip":
            with zipfile.ZipFile(src, "r") as zf:
                members = zf.namelist()
                if pattern:
                    members = [m for m in members if fnmatch.fnmatch(Path(m).name, pattern)]
                for m in members:
                    zf.extract(m, dest)
                    extracted.append(m)
        elif src.suffix in (".gz", ".bz2", ".xz", ".tar") or ".tar." in src.name:
            with tarfile.open(src, "r:*") as tf:
                members = tf.getnames()
                if pattern:
                    members = [m for m in members if fnmatch.fnmatch(Path(m).name, pattern)]
                    for m in members:
                        tf.extract(m, dest, filter="data")
                        extracted.append(m)
                else:
                    tf.extractall(dest, filter="data")
                    extracted = members
        else:
            return {"summary": f"Unsupported archive format: {src.suffix}", "error": "unsupported_format"}
    except Exception as e:
        return {"summary": f"Extraction error: {e}", "error": str(e)}

    summary = f"Extracted {len(extracted)} files from {src.name} to {dest}"
    if pattern:
        summary += f" (pattern: {pattern})"

    return {
        "summary": summary,
        "extracted_count": len(extracted),
        "destination": str(dest.resolve()),
        "files": extracted[:50],  # Cap for large archives
    }
