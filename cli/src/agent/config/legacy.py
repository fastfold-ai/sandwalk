"""Pure helpers for one-time legacy install-dir migration (copy-if-missing)."""

import logging
from pathlib import Path

_logger = logging.getLogger("config")


def migrate_tree(src_root: Path, dest_root: Path, *, label: str) -> None:
    """Copy files from *src_root* into *dest_root* when the destination is missing."""
    if not src_root.exists():
        return
    import shutil

    for src in src_root.rglob("*"):
        if not src.is_file():
            continue
        relative = src.relative_to(src_root)
        dest = dest_root / relative
        if dest.exists():
            continue
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            _logger.info("Migrated %s %s → %s", label, src, dest)
        except Exception as exc:
            _logger.warning("Could not migrate %s %s: %s", label, src, exc)
