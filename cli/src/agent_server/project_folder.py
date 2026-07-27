"""Validate project folder paths and mount them into session workspaces."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_FOLDER_LINK_NAME = "project"

ALLOWED_PROJECT_ICONS = frozenset(
    {
        "folder",
        "book",
        "flask",
        "brain",
        "code",
        "terminal",
        "briefcase",
        "globe",
        "heart",
        "music",
        "palette",
        "pencil",
        "rocket",
        "sparkles",
        "stethoscope",
        "wrench",
    }
)

ALLOWED_PROJECT_COLORS = frozenset(
    {
        "neutral",
        "red",
        "orange",
        "yellow",
        "green",
        "blue",
        "purple",
        "pink",
    }
)


def normalize_project_icon(value: str | None, *, default: str = "folder") -> str:
    key = str(value or "").strip().lower() or default
    if key not in ALLOWED_PROJECT_ICONS:
        raise ValueError(f"Unsupported project icon: {value}")
    return key


def normalize_project_color(value: str | None, *, default: str = "neutral") -> str:
    key = str(value or "").strip().lower() or default
    if key not in ALLOWED_PROJECT_COLORS:
        raise ValueError(f"Unsupported project color: {value}")
    return key


def validate_project_folder_path(value: str | None) -> str | None:
    """Return a resolved absolute directory path, or None when cleared/empty."""
    raw = str(value or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Project folder does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"Project folder must be a directory: {path}")
    return str(path)


def sync_project_folder_link(workspace: Path, folder_path: str | None) -> None:
    """Ensure ``workspace/project`` symlinks to ``folder_path``, or remove it."""
    root = workspace.expanduser().resolve()
    link = root / PROJECT_FOLDER_LINK_NAME
    target = validate_project_folder_path(folder_path) if folder_path else None

    if target is None:
        _remove_project_link(link)
        return

    target_path = Path(target)
    if link.is_symlink():
        try:
            if link.resolve() == target_path:
                return
        except OSError:
            pass
        link.unlink()
    elif link.exists():
        # Never clobber a real directory/file named project/.
        return

    os.symlink(target_path, link, target_is_directory=True)


def _remove_project_link(link: Path) -> None:
    if link.is_symlink():
        link.unlink()
        return
    # Leave real directories alone.


def project_mount_target(workspace: Path) -> Path | None:
    """Resolved target of ``workspace/project`` when that mount exists."""
    link = workspace.expanduser().resolve() / PROJECT_FOLDER_LINK_NAME
    if not link.exists() and not link.is_symlink():
        return None
    try:
        target = link.resolve()
    except OSError:
        return None
    return target if target.is_dir() else None


def path_under_workspace_or_project(
    path: Path, workspace: Path
) -> Path | None:
    """Return a resolved path when it lives in the session workspace or project mount.

    ``workspace/project`` is an intentional symlink to an external folder. Callers
    that ``Path.resolve()`` then ``relative_to(workspace)`` would reject those
    paths; this helper keeps the mount writable for agents (shell, file tools).
    """
    root = workspace.expanduser().resolve()
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate

    try:
        # Keep the final name so missing files can still be created.
        resolved = candidate.parent.resolve() / candidate.name
    except OSError:
        return None

    try:
        if resolved == root or resolved.is_relative_to(root):
            return resolved
    except (OSError, ValueError):
        pass

    # Lexical path must still be under workspace/project/... (not a bare
    # absolute path into the linked folder, which would bypass the mount).
    try:
        lexical = Path(os.path.normpath(str(candidate)))
        rel = lexical.relative_to(root)
    except (OSError, ValueError):
        return None
    if not rel.parts or rel.parts[0] != PROJECT_FOLDER_LINK_NAME:
        return None

    target = project_mount_target(root)
    if target is None:
        return None
    try:
        if resolved == target or resolved.is_relative_to(target):
            return resolved
    except (OSError, ValueError):
        return None
    return None


def workspace_rel_via_project_mount(
    resolved: Path, workspace: Path
) -> str | None:
    """Map a resolved path under the project mount back to ``project/...``."""
    root = workspace.expanduser().resolve()
    target = project_mount_target(root)
    if target is None:
        return None
    try:
        if resolved == target:
            return PROJECT_FOLDER_LINK_NAME
        rel = resolved.relative_to(target).as_posix()
    except (OSError, ValueError):
        return None
    return f"{PROJECT_FOLDER_LINK_NAME}/{rel}"
