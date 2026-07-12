#!/usr/bin/env python3
"""Package an agent skill directory into a distributable .skill zip.

Usage:
    python scripts/package_skill.py <path/to/skill> [output-dir]

Writes the resulting archive path to stdout.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

_EXCLUDE_DIRS = {".git", "__pycache__", "evals", "node_modules"}
_EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def _should_include(path: Path) -> bool:
    if any(part in _EXCLUDE_DIRS for part in path.parts):
        return False
    if path.suffix in _EXCLUDE_SUFFIXES:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package a skill into a .skill zip.")
    parser.add_argument("path", help="Path to the skill directory")
    parser.add_argument("output_dir", nargs="?", default=".", help="Output directory (default: cwd)")
    args = parser.parse_args(argv)

    skill_dir = Path(args.path).expanduser().resolve()
    if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
        print(f"Error: {skill_dir} is not a valid skill directory (no SKILL.md).", file=sys.stderr)
        return 2

    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"{skill_dir.name}.skill"

    count = 0
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(skill_dir.rglob("*")):
            if not item.is_file() or not _should_include(item.relative_to(skill_dir)):
                continue
            arcname = Path(skill_dir.name) / item.relative_to(skill_dir)
            zf.write(item, arcname)
            count += 1

    print(f"Packaged {count} file(s) into {archive}", file=sys.stderr)
    print(str(archive))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
