"""
Path-safety helpers shared by the tools/files_*.py siblings.

Split from tools/files.py.
"""

from pathlib import Path

from agent.config import CONFIG_DIR, LEGACY_CONFIG_DIRS


def _allowed_paths(config=None) -> list[Path]:
    """Return list of directories the user is allowed to read from."""
    allowed = [CONFIG_DIR, *LEGACY_CONFIG_DIRS]

    if config:
        for key in ("data.base", "data.depmap", "data.prism", "data.l1000",
                     "data.msigdb", "sandbox.output_dir"):
            val = config.get(key)
            if val:
                p = Path(val)
                # Add the directory (or parent if it's a file path)
                allowed.append(p if p.is_dir() else p.parent)

        # Also allow sandbox extra read dirs (e.g. capsule data directories)
        extra = config.get("sandbox.extra_read_dirs")
        if extra:
            for d in str(extra).split(","):
                d = d.strip()
                if d:
                    allowed.append(Path(d))

    return allowed


def _is_allowed(path: Path, config=None) -> bool:
    """Check if a path is within allowed directories."""
    resolved = path.resolve()
    for allowed in _allowed_paths(config):
        try:
            resolved.relative_to(allowed.resolve())
            return True
        except ValueError:
            continue
    return False


def _is_within_cwd(path: Path) -> bool:
    """Check if a resolved path is under the current working directory.

    Resolves symlinks before checking to prevent traversal via symlinks
    (e.g., ./data -> /etc would be rejected).
    """
    try:
        resolved = path.resolve(strict=False)
        cwd = Path.cwd().resolve()
        resolved.relative_to(cwd)
        # Extra check: if path contains a symlink, verify each component
        # stays within CWD after resolution
        if path.is_symlink():
            target = path.resolve()
            target.relative_to(cwd)
        return True
    except ValueError:
        return False


# Paths that must never be edited or deleted
_PROTECTED_PATTERNS = (
    "/.git/",
    ".env",
)


def _is_protected(path: Path) -> bool:
    """Check if a path is in the protected blocklist."""
    resolved = str(path.resolve())
    name = path.name.lower()

    # .ssh — block private keys but allow .pub
    if ".ssh/" in resolved or ".ssh\\" in resolved:
        # Allow public keys
        if name.endswith(".pub"):
            return False
        return True

    for pattern in _PROTECTED_PATTERNS:
        if pattern in resolved:
            return True

    # Block private keys outside .ssh too
    if name.startswith("id_") and not name.endswith(".pub"):
        return True
    return False


def _output_dir(config=None) -> Path:
    """Get the output directory, creating it if needed."""
    if config:
        out = config.get("sandbox.output_dir")
        if out:
            p = Path(out)
            p.mkdir(parents=True, exist_ok=True)
            return p
    default = Path.cwd() / "outputs"
    default.mkdir(parents=True, exist_ok=True)
    return default


def _resolve_output_path(out_dir: Path, filename: str) -> tuple[Path | None, str | None]:
    """Resolve an output filename safely within out_dir."""
    raw_name = (filename or "").strip()
    if not raw_name:
        return None, "Filename cannot be empty."

    rel_path = Path(raw_name)
    if rel_path.is_absolute():
        return None, "Absolute paths are not allowed."

    resolved = (out_dir / rel_path).resolve()
    try:
        resolved.relative_to(out_dir.resolve())
    except ValueError:
        return None, "Path traversal detected."

    if resolved.name in {"", ".", ".."}:
        return None, "Filename must point to a file."

    return resolved, None


def _resolve_cwd_path(path: str) -> tuple[Path | None, str | None]:
    """Resolve path and enforce current-working-directory containment."""
    p = Path(path).expanduser()
    if not _is_within_cwd(p):
        return None, "path_not_allowed"
    return p, None
